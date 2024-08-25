from rapidocr_onnxruntime import RapidOCR
from PIL import Image
import numpy as np
import logging
from fastapi import FastAPI, Body, HTTPException
import base64
import io
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pydantic import BaseModel, Field
from typing import List

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI()

# Initialize OCR engine (will be updated later)
ocr = None

# 创建一个线程池
thread_pool = None


def init_thread_pool(max_workers):
    global thread_pool
    thread_pool = ThreadPoolExecutor(max_workers=max_workers)


def init_ocr(use_gpu):
    global ocr
    config_path = "ppocr-gpu.yaml" if use_gpu else "ppocr.yaml"
    ocr = RapidOCR(config_path=config_path)


def convert_ocr_results(results):
    if results is None:
        return []
    
    converted = []
    for result in results:
        item = {"dt_boxes": result[0], "rec_txt": result[1], "score": result[2]}
        converted.append(item)
    return converted


def predict(image: Image.Image):
    # Convert PIL Image to numpy array if necessary
    img_array = np.array(image)
    results, _ = ocr(img_array)
    # Convert results to desired format
    converted_results = convert_ocr_results(results)

    return converted_results


def convert_to_python_type(item):
    if isinstance(item, np.ndarray):
        return item.tolist()
    elif isinstance(item, np.generic):  # This includes numpy scalars like numpy.float32
        return item.item()
    elif isinstance(item, list):
        return [convert_to_python_type(sub_item) for sub_item in item]
    elif isinstance(item, dict):
        return {key: convert_to_python_type(value) for key, value in item.items()}
    else:
        return item


async def async_predict(image: Image.Image):
    loop = asyncio.get_running_loop()
    # 在线程池中运行同步的 OCR 处理
    results = await loop.run_in_executor(thread_pool, partial(predict, image))
    return results


class OCRResult(BaseModel):
    dt_boxes: List[List[float]] = Field(..., description="Bounding box coordinates")
    rec_txt: str = Field(..., description="Recognized text")
    score: float = Field(..., description="Confidence score")


@app.post("/predict", response_model=List[OCRResult])
async def predict_base64(image_base64: str = Body(..., embed=True)):
    try:
        if not image_base64:
            raise HTTPException(status_code=400, detail="Missing image_base64 field")

        # Remove header part if present
        if image_base64.startswith("data:image"):
            image_base64 = image_base64.split(",")[1]

        # Decode the base64 image
        image_data = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_data))

        # 使用异步函数进行 OCR 处理
        ocr_result = await async_predict(image)

        return convert_to_python_type(ocr_result)

    except Exception as e:
        logging.error(f"Error during OCR processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="OCR Service")
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the OCR service on",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Maximum number of worker threads for OCR processing",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Use GPU for OCR processing",
    )

    args = parser.parse_args()
    port = args.port
    max_workers = args.max_workers
    use_gpu = args.gpu

    init_thread_pool(max_workers)
    init_ocr(use_gpu)

    uvicorn.run(app, host="0.0.0.0", port=port)