import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel

class VLMSettings(BaseModel):
    enabled: bool = False
    modelname: str = "internvl-1.5"
    endpoint: str = "http://localhost:11434"

class OCRSettings(BaseModel):
    enabled: bool = True
    endpoint: str = "http://localhost:5555/predict"
    token: str = ""
    concurrency: int = 4


class EmbeddingSettings(BaseModel):
    num_dim: int = 1536
    ollama_endpoint: str = "http://host.docker.internal:11434"
    ollama_model: str = "arkohut/gte-qwen2-1.5b-instruct:q8_0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file=str(Path.home() / ".memos" / "config.yaml"),
        yaml_file_encoding="utf-8",
        env_prefix="MEMOS_",
    )

    base_dir: str = str(Path.home() / ".memos")
    database_path: str = os.path.join(base_dir, "database.db")
    typesense_host: str = "localhost"
    typesense_port: str = "8108"
    typesense_protocol: str = "http"
    typesense_api_key: str = "xyz"
    typesense_connection_timeout_seconds: int = 2
    typesense_collection_name: str = "entities"
    # Server settings
    server_port: int = 8080

    # VLM plugin settings
    vlm: VLMSettings = VLMSettings()

    # OCR plugin settings
    ocr: OCRSettings = OCRSettings()

    # Embedding settings
    embedding: EmbeddingSettings = EmbeddingSettings()


settings = Settings()

# Define the default database path
os.makedirs(settings.base_dir, exist_ok=True)

# Global variable for Typesense collection name
TYPESENSE_COLLECTION_NAME = settings.typesense_collection_name

# Function to get the database path from environment variable or default
def get_database_path():
    return settings.database_path