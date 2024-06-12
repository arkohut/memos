import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMOS_")

    base_dir: str = str(Path.home() / ".memos")
    database_path: str = os.path.join(base_dir, "database.db")


settings = Settings()

# Define the default database path
os.makedirs(settings.base_dir, exist_ok=True)


# Function to get the database path from environment variable or default
def get_database_path():
    return settings.database_path
