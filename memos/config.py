import os
import shutil
from pathlib import Path
from typing import Tuple, Type, List
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)
from pydantic import BaseModel, SecretStr
import yaml
from collections import OrderedDict
import io
import typer


class VLMSettings(BaseModel):
    modelname: str = "minicpm-v"
    endpoint: str = "http://localhost:11434"
    token: str = ""
    concurrency: int = 1
    # some vlm models do not support webp
    force_jpeg: bool = True
    # prompt for vlm to extract caption
    prompt: str = "请帮描述这个图片中的内容，包括画面格局、出现的视觉元素等"


class OCRSettings(BaseModel):
    # will by ignored if use_local is True
    endpoint: str = "http://localhost:5555/predict"
    token: str = ""
    concurrency: int = 1
    use_local: bool = True
    force_jpeg: bool = False


class EmbeddingSettings(BaseModel):
    num_dim: int = 768
    # will be ignored if use_local is True
    endpoint: str = "http://localhost:11434/api/embed"
    model: str = "jinaai/jina-embeddings-v2-base-zh"
    # pull model from huggingface by default, make it true if you want to pull from modelscope
    use_modelscope: bool = False
    use_local: bool = True


class TypesenseSettings(BaseModel):
    # is disabled by default, and right now is quite unnecessary
    enabled: bool = False
    host: str = "localhost"
    port: str = "8108"
    protocol: str = "http"
    api_key: str = "xyz"
    connection_timeout_seconds: int = 10
    collection_name: str = "entities"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file=str(Path.home() / ".memos" / "config.yaml"),
        yaml_file_encoding="utf-8",
        env_prefix="MEMOS_",
    )

    base_dir: str = "~/.memos"
    database_path: str = "database.db"
    default_library: str = "screenshots"
    screenshots_dir: str = "screenshots"

    # Server settings
    server_host: str = "127.0.0.1"
    server_port: int = 8839

    # VLM plugin settings
    vlm: VLMSettings = VLMSettings()

    # OCR plugin settings
    ocr: OCRSettings = OCRSettings()

    # Embedding settings
    embedding: EmbeddingSettings = EmbeddingSettings()

    # Typesense settings
    typesense: TypesenseSettings = TypesenseSettings()

    batchsize: int = 1

    auth_username: str = "admin"
    auth_password: SecretStr = SecretStr("changeme")

    default_plugins: List[str] = ["builtin_ocr"]

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

    @property
    def resolved_base_dir(self) -> Path:
        return Path(self.base_dir).expanduser().resolve()

    @property
    def resolved_database_path(self) -> Path:
        return self.resolved_base_dir / self.database_path

    @property
    def resolved_screenshots_dir(self) -> Path:
        return self.resolved_base_dir / self.screenshots_dir
    
    @property
    def server_endpoint(self) -> str:
        host = "127.0.0.1" if self.server_host == "0.0.0.0" else self.server_host
        return f"http://{host}:{self.server_port}"


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


# Register the representer and constructor only for specific fields
yaml.add_representer(SecretStr, secret_str_representer)


def create_default_config():
    config_path = Path.home() / ".memos" / "config.yaml"
    if not config_path.exists():
        template_path = Path(__file__).parent / "default_config.yaml"
        os.makedirs(config_path.parent, exist_ok=True)
        shutil.copy(template_path, config_path)
        print(f"Created default configuration at {config_path}")


# Create default config if it doesn't exist
create_default_config()

settings = Settings()

# Define the default database path
os.makedirs(settings.resolved_base_dir, exist_ok=True)

# Global variable for Typesense collection name
TYPESENSE_COLLECTION_NAME = settings.typesense.collection_name


# Function to get the database path from environment variable or default
def get_database_path():
    return str(settings.resolved_database_path)


def format_value(value):
    if isinstance(
        value, (VLMSettings, OCRSettings, EmbeddingSettings, TypesenseSettings)
    ):
        return (
            "{\n"
            + "\n".join(f"    {k}: {v}" for k, v in value.model_dump().items())
            + "\n  }"
        )
    elif isinstance(value, (list, tuple)):
        return f"[{', '.join(map(str, value))}]"
    elif isinstance(value, SecretStr):
        return "********"  # Hide the actual value of SecretStr
    else:
        return str(value)


def display_config():
    settings = Settings()
    config_dict = settings.model_dump()
    max_key_length = max(len(key) for key in config_dict.keys())

    typer.echo("Current configuration settings:")
    for key, value in config_dict.items():
        formatted_value = format_value(value)
        if key in ["base_dir", "database_path", "screenshots_dir"]:
            resolved_value = getattr(settings, f"resolved_{key}")
            formatted_value += f" (resolved: {resolved_value})"
        if "\n" in formatted_value:
            typer.echo(f"{key}:")
            for line in formatted_value.split("\n"):
                typer.echo(f"  {line}")
        else:
            typer.echo(f"{key.ljust(max_key_length)} : {formatted_value}")
