import os
from pathlib import Path
from typing import Tuple, Type
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)
from pydantic import BaseModel, SecretStr
import yaml
from collections import OrderedDict


class VLMSettings(BaseModel):
    enabled: bool = True
    modelname: str = "moondream"
    endpoint: str = "http://localhost:11434"
    token: str = ""
    concurrency: int = 4
    force_jpeg: bool = False
    use_local: bool = True


class OCRSettings(BaseModel):
    enabled: bool = True
    endpoint: str = "http://localhost:5555/predict"
    token: str = ""
    concurrency: int = 4
    use_local: bool = True
    use_gpu: bool = False
    force_jpeg: bool = False


class EmbeddingSettings(BaseModel):
    enabled: bool = True
    num_dim: int = 768
    endpoint: str = "http://localhost:11434/api/embed"
    model: str = "jinaai/jina-embeddings-v2-base-zh"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file=str(Path.home() / ".memos" / "config.yaml"),
        yaml_file_encoding="utf-8",
        env_prefix="MEMOS_",
    )

    base_dir: str = str(Path.home() / ".memos")
    database_path: str = os.path.join(base_dir, "database.db")
    default_library: str = "screenshots"
    screenshots_dir: str = os.path.join(base_dir, "screenshots")

    typesense_host: str = "localhost"
    typesense_port: str = "8108"
    typesense_protocol: str = "http"
    typesense_api_key: str = "xyz"
    typesense_connection_timeout_seconds: int = 10
    typesense_collection_name: str = "entities"

    # Server settings
    server_host: str = "0.0.0.0"
    server_port: int = 8080

    # VLM plugin settings
    vlm: VLMSettings = VLMSettings()

    # OCR plugin settings
    ocr: OCRSettings = OCRSettings()

    # Embedding settings
    embedding: EmbeddingSettings = EmbeddingSettings()

    batchsize: int = 4

    auth_username: str = "admin"
    auth_password: SecretStr = SecretStr("changeme")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            env_settings,
            YamlConfigSettingsSource(settings_cls),
        )


def dict_representer(dumper, data):
    return dumper.represent_dict(data.items())


yaml.add_representer(OrderedDict, dict_representer)


# Custom representer for SecretStr
def secret_str_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", data.get_secret_value())


# Custom constructor for SecretStr
def secret_str_constructor(loader, node):
    value = loader.construct_scalar(node)
    return SecretStr(value)


yaml.add_representer(SecretStr, secret_str_representer)
yaml.add_constructor("tag:yaml.org,2002:str", secret_str_constructor)


def create_default_config():
    config_path = Path.home() / ".memos" / "config.yaml"
    if not config_path.exists():
        settings = Settings()
        os.makedirs(config_path.parent, exist_ok=True)
        with open(config_path, "w") as f:
            # Convert settings to a dictionary and ensure order
            settings_dict = settings.model_dump()
            ordered_settings = OrderedDict(
                (key, settings_dict[key]) for key in settings.model_fields.keys()
            )
            yaml.dump(ordered_settings, f, Dumper=yaml.Dumper)


# Create default config if it doesn't exist
create_default_config()


settings = Settings()

# Define the default database path
os.makedirs(settings.base_dir, exist_ok=True)

# Global variable for Typesense collection name
TYPESENSE_COLLECTION_NAME = settings.typesense_collection_name


# Function to get the database path from environment variable or default
def get_database_path():
    return settings.database_path
