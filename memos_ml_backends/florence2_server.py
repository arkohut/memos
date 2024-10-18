from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import httpx
import torch
from PIL import Image
import base64
import io
from transformers import AutoProcessor, AutoModelForCausalLM
import time
from memos_ml_backends.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelData,
    ModelsResponse,
    get_image_from_url,
)

MODEL_INFO = {"name": "florence2-base-ft", "max_model_len": 2048}

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

app = FastAPI()


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

    parsed_answer = florence_processor.post_process_generation(
        generated_texts[0],
        task=task_prompt,
        image_size=(image_input.width, image_input.height),
    )

    return parsed_answer.get(task_prompt, "")


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    try:
        last_message = request.messages[-1]
        text_input = last_message.get("content", "")
        image_input = None

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

        parsed_answer = await generate_florence_result(
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


@app.get("/v1/models", response_model=ModelsResponse)
async def get_models():
    model_data = ModelData(
        id=MODEL_INFO["name"],
        created=int(time.time()),
        max_model_len=MODEL_INFO["max_model_len"],
        permission=[
            {
                "id": f"modelperm-{MODEL_INFO['name']}",
                "object": "model_permission",
                "created": int(time.time()),
                "allow_create_engine": False,
                "allow_sampling": False,
                "allow_logprobs": False,
                "allow_search_indices": False,
                "allow_view": False,
                "allow_fine_tuning": False,
                "organization": "*",
                "group": None,
                "is_blocking": False,
            }
        ],
    )

    return ModelsResponse(data=[model_data])


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the Florence-2 server")
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run the server on"
    )
    args = parser.parse_args()

    print("Using Florence-2 model")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
