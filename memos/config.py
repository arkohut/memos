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
import typer


class VLMSettings(BaseModel):
    modelname: str = "minicpm-v"
    endpoint: str = "http://localhost:11434"
    token: str = ""
    concurrency: int = 8
    # some vlm models do not support webp
    force_jpeg: bool = True
    # prompt for vlm to extract caption
    prompt: str = "请帮描述这个图片中的内容，包括画面格局、出现的视觉元素等"


class OCRSettings(BaseModel):
    # will by ignored if use_local is True
    endpoint: str = "http://localhost:5555/predict"
    token: str = ""
    concurrency: int = 8
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        yaml_file=str(Path.home() / ".memos" / "config.yaml"),
        yaml_file_encoding="utf-8",
        env_prefix="MEMOS_",
        extra="ignore",
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

    auth_username: str = ""
    auth_password: SecretStr = SecretStr("")

    default_plugins: List[str] = ["builtin_ocr"]

    record_interval: int = 4

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
    # the config file is always created in the home directory
    # not influenced by the base_dir setting
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


# Function to get the database path from environment variable or default
def get_database_path():
    return str(settings.resolved_database_path)


def format_value(value):
    if isinstance(value, dict):
        # Format nested dictionary with proper indentation
        formatted_items = []
        for k, v in value.items():
            # Add proper indentation and alignment for nested items
            formatted_value = str(v)
            formatted_items.append(f"    {k:<12} : {formatted_value}")
        return "\n" + "\n".join(formatted_items)
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
        
        # 如果值包含换行符，使用多行格式打印
        if "\n" in formatted_value:
            typer.echo(f"{key.ljust(max_key_length)} :{formatted_value}")
        else:
            # 对于单行值，在同一行打印
            typer.echo(f"{key.ljust(max_key_length)} : {formatted_value}")
