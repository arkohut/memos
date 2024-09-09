import asyncio
import logging
import os
from typing import Optional
import httpx
import json
import base64
from PIL import Image
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import yaml

from fastapi import APIRouter, FastAPI, Request, HTTPException
from memos.schemas import Entity, MetadataType

METADATA_FIELD_NAME = "ocr_result"
PLUGIN_NAME = "ocr"

router = APIRouter(tags=[PLUGIN_NAME], responses={404: {"description": "Not found"}})
endpoint = None
token = None
concurrency = None
semaphore = None
use_local = False
use_gpu = False
ocr = None
thread_pool = None

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def image2base64(img_path):
    try:
        with Image.open(img_path) as img:
            img.convert("RGB")  # Check if image is not broken
        with open(img_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded_string
    except Exception as e:
        logger.error(f"Error processing image {img_path}: {str(e)}")
        return None


async def fetch(endpoint: str, client, image_base64, headers: Optional[dict] = None):
    async with semaphore:  # 使用信号量控制并发
        response = await client.post(
            f"{endpoint}",
            json={"image_base64": image_base64},
            timeout=60,
            headers=headers,
        )
        if response.status_code != 200:
            return None
        return response.json()


def convert_ocr_results(results):
    if results is None:
        return []
    
    converted = []
    for result in results:
        item = {"dt_boxes": result[0], "rec_txt": result[1], "score": result[2]}
        converted.append(item)
    return converted


def predict_local(img_path):
    try:
        with Image.open(img_path) as img:
            img_array = np.array(img)
        results, _ = ocr(img_array)
        return convert_ocr_results(results)
    except Exception as e:
        logger.error(f"Error processing image {img_path}: {str(e)}")
        return None


async def async_predict_local(img_path):
    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(thread_pool, partial(predict_local, img_path))
    return results


# Modify the predict function to use semaphore
async def predict(img_path):
    if use_local:
        return await async_predict_local(img_path)
    
    image_base64 = image2base64(img_path)
    if not image_base64:
        return None

    async with httpx.AsyncClient() as client:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with semaphore:
            ocr_result = await fetch(endpoint, client, image_base64, headers=headers)
        return ocr_result


@router.get("/")
async def read_root():
    return {"healthy": True}


@router.post("", include_in_schema=False)
@router.post("/")
async def ocr(entity: Entity, request: Request):
    if not entity.file_type_group == "image":
        return {METADATA_FIELD_NAME: "{}"}

    # Get the URL to patch the entity's metadata from the "Location" header
    location_url = request.headers.get("Location")
    if not location_url:
        raise HTTPException(status_code=400, detail="Location header is missing")

    patch_url = f"{location_url}/metadata"

    ocr_result = await predict(entity.filepath)

    if ocr_result is None or not ocr_result:
        logger.info(f"No OCR result found for file: {entity.filepath}")
        return {METADATA_FIELD_NAME: "{}"}

    # Call the URL to patch the entity's metadata
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            patch_url,
            json={
                "metadata_entries": [
                    {
                        "key": METADATA_FIELD_NAME,
                        "value": json.dumps(
                            ocr_result,
                            default=lambda o: o.item() if hasattr(o, "item") else o,
                        ),
                        "source": PLUGIN_NAME,
                        "data_type": MetadataType.JSON_DATA.value,
                    }
                ]
            },
            timeout=30,
        )

    # Check if the patch request was successful
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, detail="Failed to patch entity metadata"
        )

    return {
        METADATA_FIELD_NAME: json.dumps(
            ocr_result,
            default=lambda o: o.item() if hasattr(o, "item") else o,
        )
    }


def init_plugin(config):
    global endpoint, token, concurrency, semaphore, use_local, use_gpu, ocr, thread_pool
    endpoint = config.endpoint
    token = config.token
    concurrency = config.concurrency
    use_local = config.use_local
    use_gpu = config.use_gpu
    semaphore = asyncio.Semaphore(concurrency)
    
    if use_local:
        config_path = os.path.join(os.path.dirname(__file__), "ppocr-gpu.yaml" if use_gpu else "ppocr.yaml")
        
        # Load and update the config file with absolute model paths
        with open(config_path, 'r') as f:
            ocr_config = yaml.safe_load(f)
        
        model_dir = os.path.join(os.path.dirname(__file__), "models")
        ocr_config['Det']['model_path'] = os.path.join(model_dir, os.path.basename(ocr_config['Det']['model_path']))
        ocr_config['Cls']['model_path'] = os.path.join(model_dir, os.path.basename(ocr_config['Cls']['model_path']))
        ocr_config['Rec']['model_path'] = os.path.join(model_dir, os.path.basename(ocr_config['Rec']['model_path']))
        
        # Save the updated config to a temporary file with strings wrapped in double quotes
        temp_config_path = os.path.join(os.path.dirname(__file__), "temp_ppocr.yaml")
        with open(temp_config_path, 'w') as f:
            yaml.safe_dump(ocr_config, f, default_style='"')
        
        ocr = RapidOCR(config_path=temp_config_path)
        thread_pool = ThreadPoolExecutor(max_workers=concurrency)

    logger.info("OCR plugin initialized")
    logger.info(f"Endpoint: {endpoint}")
    logger.info(f"Token: {token}")
    logger.info(f"Concurrency: {concurrency}")
    logger.info(f"Use local: {use_local}")
    logger.info(f"Use GPU: {use_gpu}")


if __name__ == "__main__":
    import uvicorn
    import argparse
    from fastapi import FastAPI

    parser = argparse.ArgumentParser(description="OCR Plugin")
    parser.add_argument(
        "--endpoint",
        type=str,
        default="http://localhost:8080",
        help="The endpoint URL for the OCR service",
    )
    parser.add_argument(
        "--token", type=str, default="", help="The token for authentication"
    )
    parser.add_argument(
        "--concurrency", type=int, default=4, help="The concurrency level"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="The port number to run the server on"
    )
    parser.add_argument(
        "--use-local", action="store_true", help="Use local OCR processing"
    )
    parser.add_argument(
        "--use-gpu", action="store_true", help="Use GPU for local OCR processing"
    )

    args = parser.parse_args()

    init_plugin(args)

    app = FastAPI()
    app.include_router(router)

    uvicorn.run(app, host="0.0.0.0", port=args.port)
