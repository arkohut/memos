from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import httpx
from PIL import Image
import base64
import io

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

class ModelData(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "transformers"
    root: str = "models"
    parent: Optional[str] = None
    max_model_len: int
    permission: List[Dict[str, Any]]

class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[ModelData]

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

