import asyncio
from typing import List
from fastapi import APIRouter, HTTPException
import logging
import uvicorn
from sentence_transformers import SentenceTransformer
import torch
import numpy as np
from pydantic import BaseModel

PLUGIN_NAME = "embedding"

router = APIRouter(tags=[PLUGIN_NAME], responses={404: {"description": "Not found"}})

# Global variables
enabled = False
model = None
num_dim = None
endpoint = None
model_name = None
device = None

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_embedding_model():
    global model, device
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    model = SentenceTransformer(model_name, trust_remote_code=True)
    model.to(device)
    logger.info(f"Embedding model initialized on device: {device}")


def generate_embeddings(input_texts: List[str]) -> List[List[float]]:
    embeddings = model.encode(input_texts, convert_to_tensor=True)
    embeddings = embeddings.cpu().numpy()
    # Normalize embeddings
    norms = np.linalg.norm(embeddings, ord=2, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms
    return embeddings.tolist()


class EmbeddingRequest(BaseModel):
    input: List[str]


class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]


@router.get("/")
async def read_root():
    return {"healthy": True, "enabled": enabled}


@router.post("", include_in_schema=False)
@router.post("/", response_model=EmbeddingResponse)
async def embed(request: EmbeddingRequest):
    try:
        if not request.input:
            return EmbeddingResponse(embeddings=[])

        # Run the embedding generation in a separate thread to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, generate_embeddings, request.input)
        return EmbeddingResponse(embeddings=embeddings)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating embeddings: {str(e)}"
        )


def init_plugin(config):
    global enabled, num_dim, endpoint, model_name
    enabled = config.enabled
    num_dim = config.num_dim
    endpoint = config.endpoint
    model_name = config.model

    if enabled:
        init_embedding_model()

    logger.info("Embedding plugin initialized")
    logger.info(f"Enabled: {enabled}")
    logger.info(f"Number of dimensions: {num_dim}")
    logger.info(f"Endpoint: {endpoint}")
    logger.info(f"Model: {model_name}")


if __name__ == "__main__":
    import argparse
    from fastapi import FastAPI

    parser = argparse.ArgumentParser(description="Embedding Plugin Configuration")
    parser.add_argument(
        "--num-dim", type=int, default=768, help="Number of embedding dimensions"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="jinaai/jina-embeddings-v2-base-zh",
        help="Embedding model name",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run the server on"
    )

    args = parser.parse_args()

    class Config:
        def __init__(self, args):
            self.enabled = True
            self.num_dim = args.num_dim
            self.endpoint = "what ever"
            self.model = args.model

    init_plugin(Config(args))

    app = FastAPI()
    app.include_router(router)

    uvicorn.run(app, host="0.0.0.0", port=args.port)
