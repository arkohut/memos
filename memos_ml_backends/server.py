from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import numpy as np
import httpx
import torch
from PIL import Image
import base64
import io
from transformers import (
    AutoProcessor,
    AutoModelForCausalLM,
    Qwen2VLForConditionalGeneration,
)
from qwen_vl_utils import process_vision_info
import time
import argparse

# 检测可用的设备
if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")

torch_dtype = (
    torch.float32
    if (torch.cuda.is_available() and torch.cuda.get_device_capability()[0] <= 6)
    or (not torch.cuda.is_available() and not torch.backends.mps.is_available())
    else torch.float16
)
print(f"Using device: {device}")


# Add a configuration option to choose the model
parser = argparse.ArgumentParser(description="Run the server with specified model")
parser.add_argument("--florence", action="store_true", help="Use Florence-2 model")
parser.add_argument("--qwen2vl", action="store_true", help="Use Qwen2VL model")
args = parser.parse_args()

# Replace the USE_FLORANCE_MODEL configuration with this
use_florence_model = args.florence if (args.florence or args.qwen2vl) else True

# Initialize models based on the configuration
if use_florence_model:
    # Load Florence-2 model
    florence_model = AutoModelForCausalLM.from_pretrained(
        "microsoft/Florence-2-base-ft",
        torch_dtype=torch_dtype,
        attn_implementation="sdpa",
        trust_remote_code=True,
    ).to(device, torch_dtype)
    florence_processor = AutoProcessor.from_pretrained(
        "microsoft/Florence-2-base-ft", trust_remote_code=True
    )
else:
    # Load Qwen2VL model
    qwen2vl_model = Qwen2VLForConditionalGeneration.from_pretrained(
        "Qwen/Qwen2-VL-2B-Instruct-GPTQ-Int4",
        torch_dtype=torch_dtype,
        device_map="auto",
    ).to(device, torch_dtype)
    qwen2vl_processor = AutoProcessor.from_pretrained(
        "Qwen/Qwen2-VL-2B-Instruct-GPTQ-Int4"
    )


async def get_image_from_url(image_url):
    if image_url.startswith("data:image/"):
        image_data = base64.b64decode(image_url.split(",")[1])
        return Image.open(io.BytesIO(image_data))
    elif image_url.startswith("file://"):
        file_path = image_url[len("file://") :]
        return Image.open(file_path)
    else:
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            response.raise_for_status()
            image_data = response.content
            return Image.open(io.BytesIO(image_data))


async def generate_florence_result(text_input, image_input, max_tokens):
    task_prompt = "<MORE_DETAILED_CAPTION>"
    prompt = task_prompt + ""

    inputs = florence_processor(
        text=prompt, images=image_input, return_tensors="pt"
    ).to(device, torch_dtype)

    generated_ids = florence_model.generate(
        input_ids=inputs["input_ids"],
        pixel_values=inputs["pixel_values"],
        max_new_tokens=max_tokens or 1024,
        do_sample=False,
        num_beams=3,
    )

    generated_texts = florence_processor.batch_decode(
        generated_ids, skip_special_tokens=False
    )

    # 处理生成的文本
    parsed_answer = florence_processor.post_process_generation(
        generated_texts[0],
        task=task_prompt,
        image_size=(image_input.width, image_input.height),
    )

    return parsed_answer.get(task_prompt, "")


async def generate_qwen2vl_result(text_input, image_input, max_tokens):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image_input},
                {"type": "text", "text": text_input},
            ],
        }
    ]

    text = qwen2vl_processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    image_inputs, video_inputs = process_vision_info(messages)

    inputs = qwen2vl_processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to(device)

    generated_ids = qwen2vl_model.generate(**inputs, max_new_tokens=(max_tokens or 512))

    generated_ids_trimmed = [
        out_ids[len(in_ids) :]
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]

    output_text = qwen2vl_processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )

    return output_text[0] if output_text else ""


app = FastAPI()


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]]
    max_tokens: Optional[int] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    try:
        last_message = request.messages[-1]
        text_input = last_message.get("content", "")
        image_input = None

        # Process text and image input
        if isinstance(text_input, list):
            for content in text_input:
                if content.get("type") == "image_url":
                    image_url = content["image_url"].get("url")
                    image_input = await get_image_from_url(image_url)
                    break
            text_input = " ".join(
                [
                    content["text"]
                    for content in text_input
                    if content.get("type") == "text"
                ]
            )

        if image_input is None:
            raise ValueError("Image input is required")

        # Use the selected model for generation
        if use_florence_model:
            parsed_answer = await generate_florence_result(
                text_input, image_input, request.max_tokens
            )
        else:
            parsed_answer = await generate_qwen2vl_result(
                text_input, image_input, request.max_tokens
            )

        result = ChatCompletionResponse(
            id=str(int(time.time())),
            object="chat.completion",
            created=int(time.time()),
            model=request.model,
            choices=[
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": parsed_answer,
                    },
                    "finish_reason": "stop",
                }
            ],
            usage={
                "prompt_tokens": 0,
                "total_tokens": 0,
                "completion_tokens": 0,
            },
        )

        return result
    except Exception as e:
        print(f"Error generating chat completion: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error generating chat completion: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(
        description="Run the server with specified model and port"
    )
    parser.add_argument("--florence", action="store_true", help="Use Florence-2 model")
    parser.add_argument("--qwen2vl", action="store_true", help="Use Qwen2VL model")
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run the server on"
    )
    args = parser.parse_args()

    if args.florence and args.qwen2vl:
        print("Error: Please specify only one model (--florence or --qwen2vl)")
        exit(1)
    elif not args.florence and not args.qwen2vl:
        print("No model specified, using default (Florence-2)")

    use_florence_model = args.florence if (args.florence or args.qwen2vl) else True
    print(f"Using {'Florence-2' if use_florence_model else 'Qwen2VL'} model")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
