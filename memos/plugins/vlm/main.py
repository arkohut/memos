import base64
import httpx
from PIL import Image
import asyncio
from typing import Optional
from fastapi import APIRouter, FastAPI, Request, HTTPException
from memos.schemas import Entity, MetadataType
import logging
import uvicorn
import os
import io
import numpy as np


PLUGIN_NAME = "vlm"

router = APIRouter(tags=[PLUGIN_NAME], responses={404: {"description": "Not found"}})

modelname = None
endpoint = None
token = None
concurrency = None
semaphore = None
force_jpeg = None
prompt = None

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def image2base64(img_path):
    try:
        with Image.open(img_path) as img:
            img.verify()  # Verify the image file

        with Image.open(img_path) as img:
            # Check image size and skip if it's too small
            if img.width < 10 or img.height < 10:
                logger.warning(f"Image is too small: {img.width}x{img.height}. Skipping processing.")
                return None

            # Convert image to RGB mode (removes alpha channel if present)
            img = img.convert("RGB")
            
            # Convert to numpy array and check shape
            img_array = np.array(img)
            logger.info(f"Image shape: {img_array.shape}")

            if img_array.shape[2] != 3:
                logger.warning(f"Unexpected number of channels: {img_array.shape[2]}. Expected 3. Skipping processing.")
                return None
            
            if force_jpeg:
                # Save as JPEG in memory
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG")
                buffer.seek(0)
                encoded_string = base64.b64encode(buffer.getvalue()).decode("utf-8")
            else:
                # Use original format, but ensure it's RGB
                buffer = io.BytesIO()
                img.save(buffer, format=img.format or "JPEG")
                buffer.seek(0)
                encoded_string = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return encoded_string
    except Exception as e:
        logger.error(f"Error processing image {img_path}: {str(e)}")
        return None


async def fetch(endpoint: str, client, request_data, headers: Optional[dict] = None):
    async with semaphore:  # 使用信号量控制并发
        try:
            response = await client.post(
                f"{endpoint}/v1/chat/completions",
                json=request_data,
                timeout=60,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()
            choices = result.get("choices", [])
            if (
                choices
                and "message" in choices[0]
                and "content" in choices[0]["message"]
            ):
                return choices[0]["message"]["content"]
            return ""
        except Exception as e:
            logger.error(f"Exception occurred: {str(e)}")
            return None


async def predict(
    endpoint: str, modelname: str, img_path: str, token: Optional[str] = None
) -> Optional[str]:
    return await predict_remote(endpoint, modelname, img_path, token)


async def predict_remote(
    endpoint: str, modelname: str, img_path: str, token: Optional[str] = None
) -> Optional[str]:
    img_base64 = image2base64(img_path)
    if not img_base64:
        logger.warning(f"Skipping processing for file: {img_path} due to invalid or small image")
        return None

    mime_type = (
        "image/jpeg" if force_jpeg else "image/jpeg"
    )  # Default to JPEG if force_jpeg is True

    if not force_jpeg:
        # Only determine MIME type if not forcing JPEG
        _, file_extension = os.path.splitext(img_path)
        file_extension = file_extension.lower()[1:]
        mime_types = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
        }
        mime_type = mime_types.get(file_extension, "image/jpeg")

    request_data = {
        "model": modelname,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{img_base64}"},
                    },
                    {"type": "text", "text": prompt},  # Use the global prompt variable here
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


@router.post("", include_in_schema=False)
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

    logger.info(vlm_result)
    if not vlm_result:
        logger.info(f"No VLM result found for file: {entity.filepath}")
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
    global modelname, endpoint, token, concurrency, semaphore, force_jpeg, prompt

    modelname = config.modelname
    endpoint = config.endpoint
    token = config.token
    concurrency = config.concurrency
    force_jpeg = config.force_jpeg
    prompt = config.prompt
    semaphore = asyncio.Semaphore(concurrency)

    # Print the parameters
    logger.info("VLM plugin initialized")
    logger.info(f"Model Name: {modelname}")
    logger.info(f"Endpoint: {endpoint}")
    logger.info(f"Token: {token}")
    logger.info(f"Concurrency: {concurrency}")
    logger.info(f"Force JPEG: {force_jpeg}")
    logger.info(f"Prompt: {prompt}")

