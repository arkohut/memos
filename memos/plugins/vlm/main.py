import base64
import httpx
from PIL import Image
import asyncio
from typing import Optional
from fastapi import APIRouter, FastAPI, Request, HTTPException
from memos.schemas import Entity, MetadataType
import logging
import uvicorn

PLUGIN_NAME = "vlm"
PROMPT = "描述这张图片的内容"

router = APIRouter(
    tags=[PLUGIN_NAME],
    responses={404: {"description": "Not found"}}
)

modelname = None
endpoint = None
token = None
concurrency = None
semaphore = None

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def image2base64(img_path):
    try:
        # Attempt to open and verify the image
        with Image.open(img_path) as img:
            img.verify()  # Verify that it's a valid image file

        # If verification passes, encode the image
        with open(img_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded_string
    except Exception as e:
        logger.error(f"Error processing image {img_path}: {str(e)}")
        return None


async def fetch(endpoint: str, client, request_data, headers: Optional[dict] = None):
    async with semaphore:  # 使用信号量控制并发
        response = await client.post(
            f"{endpoint}/v1/chat/completions",
            json=request_data,
            timeout=60,
            headers=headers,
        )
        if response.status_code != 200:
            return None
        result = response.json()
        choices = result.get("choices", [])
        if choices and "message" in choices[0] and "content" in choices[0]["message"]:
            return choices[0]["message"]["content"]
        return ""


async def predict(
    endpoint: str, modelname: str, img_path: str, token: Optional[str] = None
) -> Optional[str]:
    img_base64 = image2base64(img_path)
    if not img_base64:
        return None

    request_data = {
        "model": modelname,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/;base64,{img_base64}"},
                        "detail": "high",
                    },
                ],
            }
        ],
        "stream": False,
        "max_tokens": 1024,
        "temperature": 0.1,
        "repetition_penalty": 1.1,
        "top_p": 0.8,
    }
    async with httpx.AsyncClient() as client:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return await fetch(endpoint, client, request_data, headers=headers)


@router.get("/")
async def read_root():
    return {"healthy": True}


@router.post("/")
async def vlm(entity: Entity, request: Request):
    global modelname, endpoint, token
    metadata_field_name = f"{modelname.replace('-', '_')}_result"
    if not entity.file_type_group == "image":
        return {metadata_field_name: ""}

    # Check if the METADATA_FIELD_NAME field is empty or null
    existing_metadata = entity.get_metadata_by_key(metadata_field_name)
    if (
        existing_metadata
        and existing_metadata.value
        and existing_metadata.value.strip()
    ):
        logger.info(
            f"Skipping processing for file: {entity.filepath} due to existing metadata"
        )
        # If the field is not empty, return without processing
        return {metadata_field_name: existing_metadata.value}

    # Check if the entity contains the tag "low_info"
    if any(tag.name == "low_info" for tag in entity.tags):
        # If the tag is present, return without processing
        logger.info(
            f"Skipping processing for file: {entity.filepath} due to 'low_info' tag"
        )
        return {metadata_field_name: ""}

    location_url = request.headers.get("Location")
    if not location_url:
        raise HTTPException(status_code=400, detail="Location header is missing")

    patch_url = f"{location_url}/metadata"

    vlm_result = await predict(endpoint, modelname, entity.filepath, token=token)

    print(vlm_result)
    if not vlm_result:
        print(f"No VLM result found for file: {entity.filepath}")
        return {metadata_field_name: "{}"}

    async with httpx.AsyncClient() as client:
        response = await client.patch(
            patch_url,
            json={
                "metadata_entries": [
                    {
                        "key": metadata_field_name,
                        "value": vlm_result,
                        "source": PLUGIN_NAME,
                        "data_type": MetadataType.TEXT_DATA.value,
                    }
                ]
            },
            timeout=30,
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, detail="Failed to patch entity metadata"
        )

    return {
        metadata_field_name: vlm_result,
    }


def init_plugin(config):
    global modelname, endpoint, token, concurrency, semaphore
    modelname = config.modelname
    endpoint = config.endpoint
    token = config.token
    concurrency = config.concurrency
    semaphore = asyncio.Semaphore(concurrency)


if __name__ == "__main__":
    import argparse
    from fastapi import FastAPI

    parser = argparse.ArgumentParser(description="VLM Plugin Configuration")
    parser.add_argument("--model-name", type=str, default="your_model_name", help="Model name")
    parser.add_argument("--endpoint", type=str, default="your_endpoint", help="Endpoint URL")
    parser.add_argument("--token", type=str, default="your_token", help="Access token")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrency level")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")

    args = parser.parse_args()

    init_plugin(args)

    print(f"Model Name: {args.model_name}")
    print(f"Endpoint: {args.endpoint}")
    print(f"Token: {args.token}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Port: {args.port}")

    app = FastAPI()
    app.include_router(router)

    uvicorn.run(app, host="0.0.0.0", port=args.port)