from fastapi import FastAPI, HTTPException
import torch
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from qwen_vl_utils import process_vision_info
import time
from memos_ml_backends.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelData,
    ModelsResponse,
    get_image_from_url,
)

MODEL_INFO = {"name": "Qwen2-VL-2B-Instruct", "max_model_len": 32768}

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

# Load Qwen2VL model
qwen2vl_model = Qwen2VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2-VL-2B-Instruct",
    torch_dtype=torch_dtype,
    device_map="auto",
).to(device, torch_dtype)
qwen2vl_processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-2B-Instruct-GPTQ-Int4")

app = FastAPI()


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


# 添加新的 GET /v1/models 端点
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

    parser = argparse.ArgumentParser(description="Run the Qwen2VL server")
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run the server on"
    )
    args = parser.parse_args()

    print("Using Qwen2VL model")
    uvicorn.run(app, host="0.0.0.0", port=args.port)
