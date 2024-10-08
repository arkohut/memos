import os
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


class VLMSettings(BaseModel):
    enabled: bool = True
    modelname: str = "moondream"
    endpoint: str = "http://localhost:11434"
    token: str = ""
    concurrency: int = 1
    force_jpeg: bool = False
    prompt: str = "请帮描述这个图片中的内容，包括画面格局、出现的视觉元素等"


class OCRSettings(BaseModel):
    enabled: bool = True
    endpoint: str = "http://localhost:5555/predict"
    token: str = ""
    concurrency: int = 1
    use_local: bool = True
    force_jpeg: bool = False


class EmbeddingSettings(BaseModel):
    enabled: bool = True
    num_dim: int = 768
    endpoint: str = "http://localhost:11434/api/embed"
    model: str = "jinaai/jina-embeddings-v2-base-zh"
    use_modelscope: bool = False


class TypesenseSettings(BaseModel):
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

    base_dir: str = str(Path.home() / ".memos")
    database_path: str = os.path.join(base_dir, "database.db")
    default_library: str = "screenshots"
    screenshots_dir: str = os.path.join(base_dir, "screenshots")

    # Server settings
    server_host: str = "0.0.0.0"
    server_port: int = 8080

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

    default_plugins: List[str] = ["builtin_vlm", "builtin_ocr"]

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

# Register the representer and constructor only for specific fields
yaml.add_representer(SecretStr, secret_str_representer)


def create_default_config():
    config_path = Path.home() / ".memos" / "config.yaml"
    if not config_path.exists():
        settings = Settings()
        os.makedirs(config_path.parent, exist_ok=True)
        
        # 将设置转换为字典并确保顺序
        settings_dict = settings.model_dump()
        ordered_settings = OrderedDict(
            (key, settings_dict[key]) for key in settings.model_fields.keys()
        )
        
        # 使用 io.StringIO 作为中间步骤
        with io.StringIO() as string_buffer:
            yaml.dump(ordered_settings, string_buffer, allow_unicode=True, Dumper=yaml.Dumper)
            yaml_content = string_buffer.getvalue()
        
        # 将内容写入文件，确保使用 UTF-8 编码
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

# Create default config if it doesn't exist
create_default_config()


settings = Settings()

# Define the default database path
os.makedirs(settings.base_dir, exist_ok=True)

# Global variable for Typesense collection name
TYPESENSE_COLLECTION_NAME = settings.typesense.collection_name


# Function to get the database path from environment variable or default
def get_database_path():
    return settings.database_path
