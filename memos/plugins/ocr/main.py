import asyncio
import logging
import os
from typing import Optional
import httpx
import json
import base64
from PIL import Image
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import yaml
import io
import platform
import cpuinfo

MAX_THUMBNAIL_SIZE = (1920, 1920)

from fastapi import APIRouter, Request, HTTPException
from memos.schemas import Entity, MetadataType

METADATA_FIELD_NAME = "ocr_result"
PLUGIN_NAME = "ocr"

router = APIRouter(tags=[PLUGIN_NAME], responses={404: {"description": "Not found"}})
endpoint = None
token = None
concurrency = None
semaphore = None
use_local = False
ocr = None
thread_pool = None

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def image2base64(img_path):
    try:
        with Image.open(img_path) as img:
            img = img.convert("RGB")
            img.thumbnail(MAX_THUMBNAIL_SIZE)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            encoded_string = base64.b64encode(buffered.getvalue()).decode("utf-8")
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


def convert_ocr_data(ocr_data):
    converted_data = []
    for text, score, bbox in ocr_data:
        x_min, y_min, x_max, y_max = bbox
        dt_boxes = [
            [x_min, y_min],
            [x_max, y_min],
            [x_max, y_max],
            [x_min, y_max]
        ]
        entry = {
            'dt_boxes': dt_boxes,
            'rec_txt': text,
            'score': float(score)
        }
        converted_data.append(entry)
    return converted_data


def predict_local(img_path):
    try:
        if platform.system() == 'Darwin':  # Check if the OS is macOS
            from ocrmac import ocrmac
            result = ocrmac.OCR(img_path, language_preference=['zh-Hans']).recognize(px=True)
            return convert_ocr_data(result)
        else:
            with Image.open(img_path) as img:
                img = img.convert("RGB")
                img.thumbnail(MAX_THUMBNAIL_SIZE)
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
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return await fetch(endpoint, client, image_base64, headers)


@router.get("/")
async def read_root():
    return {"healthy": True}


@router.post("", include_in_schema=False)
@router.post("/")
async def ocr(entity: Entity, request: Request):
    if not entity.file_type_group == "image":
        return {METADATA_FIELD_NAME: "{}"}

    # Check if the metadata field already exists and has a non-empty value
    existing_metadata = entity.get_metadata_by_key(METADATA_FIELD_NAME)
    if existing_metadata and existing_metadata.value and existing_metadata.value.strip():
        logger.info(f"Skipping OCR processing for file: {entity.filepath} due to existing metadata")
        return {METADATA_FIELD_NAME: existing_metadata.value}

    # Check if the entity contains the tag "low_info"
    if any(tag.name == "low_info" for tag in entity.tags):
        logger.info(f"Skipping OCR processing for file: {entity.filepath} due to 'low_info' tag")
        return {METADATA_FIELD_NAME: "{}"}

    location_url = request.headers.get("Location")
    if not location_url:
        raise HTTPException(status_code=400, detail="Location header is missing")

    patch_url = f"{location_url}/metadata"

    ocr_result = await predict(entity.filepath)
    logger.info(ocr_result)
    if not ocr_result:
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
    global endpoint, token, concurrency, semaphore, use_local, ocr, thread_pool
    endpoint = config.endpoint
    token = config.token
    concurrency = config.concurrency
    use_local = config.use_local
    semaphore = asyncio.Semaphore(concurrency)
    
    if use_local:
        config_path = os.path.join(os.path.dirname(__file__), "ppocr.yaml")
        
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
            yaml.safe_dump(ocr_config, f)
        
        if platform.system() == 'Windows' and 'Intel' in cpuinfo.get_cpu_info()['brand_raw']:
            from rapidocr_openvino import RapidOCR
            ocr = RapidOCR(config_path=temp_config_path)
        else:
            from rapidocr_onnxruntime import RapidOCR
            ocr = RapidOCR(config_path=temp_config_path)
        thread_pool = ThreadPoolExecutor(max_workers=concurrency)

    logger.info("OCR plugin initialized")
    logger.info(f"Endpoint: {endpoint}")
    logger.info(f"Token: {token}")
    logger.info(f"Concurrency: {concurrency}")
    logger.info(f"Use local: {use_local}")
    if use_local:
        logger.info(f"OCR library: {'rapidocr_openvino' if platform.system() == 'Windows' and 'Intel' in cpuinfo.get_cpu_info()['brand_raw'] else 'rapidocr_onnxruntime'}")
