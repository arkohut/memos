import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMOS_")

    base_dir: str = str(Path.home() / ".memos")
    database_path: str = os.path.join(base_dir, "database.db")
    typesense_host: str = "localhost"
    typesense_port: str = "8108"
    typesense_protocol: str = "http"
    typesense_api_key: str = "xyz"
    typesense_connection_timeout_seconds: int = 2
    typesense_collection_name: str = "entities"


settings = Settings()

# Define the default database path
os.makedirs(settings.base_dir, exist_ok=True)

# Global variable for Typesense collection name
TYPESENSE_COLLECTION_NAME = settings.typesense_collection_name


# Function to get the database path from environment variable or default
def get_database_path():
    return settings.database_path