from typing import List
from sentence_transformers import SentenceTransformer
import torch
import numpy as np
from modelscope import snapshot_download
from .config import settings
import logging

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
model = None
device = None

def init_embedding_model():
    global model, device
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    if settings.embedding.use_modelscope:
        model_dir = snapshot_download(settings.embedding.model)
        logger.info(f"Model downloaded from ModelScope to: {model_dir}")
    else:
        model_dir = settings.embedding.model
        logger.info(f"Using model: {model_dir}")

    model = SentenceTransformer(model_dir, trust_remote_code=True)
    model.to(device)
    logger.info(f"Embedding model initialized on device: {device}")

def generate_embeddings(texts: List[str]) -> List[List[float]]:
    global model
    
    if model is None:
        init_embedding_model()
    
    if not texts:
        return []

    embeddings = model.encode(texts, convert_to_tensor=True)
    embeddings = embeddings.cpu().numpy()
    
    # Normalize embeddings
    norms = np.linalg.norm(embeddings, ord=2, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms
    
    return embeddings.tolist()