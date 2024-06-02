from pydantic import BaseModel, ConfigDict, DirectoryPath, HttpUrl
from typing import List
from datetime import datetime
from enum import Enum


class MetadataSource(Enum):
    USER_GENERATED = "user_generated"
    SYSTEM_GENERATED = "system_generated"
    PLUGIN_GENERATED = "plugin_generated"


class MetadataType(Enum):
    EXTRACONTENT = "extra_content"
    ATTRIBUTE = "attribute"


class NewLibraryParam(BaseModel):
    name: str
    folders: List[DirectoryPath] = []


class NewFolderParam(BaseModel):
    path: DirectoryPath


class NewEntityParam(BaseModel):
    filename: str
    filepath: str
    size: int
    file_created_at: datetime
    file_last_modified_at: datetime
    file_type: str
    folder_id: int


class UpdateEntityParam(BaseModel):
    size: int
    file_created_at: datetime
    file_last_modified_at: datetime
    file_type: str


class UpdateTagParam(BaseModel):
    description: str | None
    color: str | None


class UpdateEntityTagsParam(BaseModel):
    tags: List[str] = []


class EntityMetadataParam(BaseModel):
    key: str
    value: str
    source: MetadataSource
    data_type: MetadataType


class UpdateEntityMetadataParam(BaseModel):
    metadata_entries: List[EntityMetadataParam]


class NewPluginParam(BaseModel):
    name: str
    description: str | None
    webhook_url: HttpUrl


class NewLibraryPluginParam(BaseModel):
    plugin_id: int


class Folder(BaseModel):
    id: int
    path: str

    model_config = ConfigDict(from_attributes=True)


class Plugin(BaseModel):
    id: int
    name: str
    description: str | None
    webhook_url: str

    model_config = ConfigDict(from_attributes=True)


class Library(BaseModel):
    id: int
    name: str
    folders: List[Folder] = []
    plugins: List[Plugin] = []

    model_config = ConfigDict(from_attributes=True)


class Entity(BaseModel):
    id: int
    filepath: str
    filename: str
    size: int
    file_created_at: datetime
    file_last_modified_at: datetime
    file_type: str
    last_scan_at: datetime | None
    folder_id: int
    library_id: int

    model_config = ConfigDict(from_attributes=True)


class Tag(BaseModel):
    id: int
    name: str
    description: str | None
    color: str | None
    created_at: datetime
    source: str

    model_config = ConfigDict(from_attributes=True)


class EntityMetadata(BaseModel):
    id: int
    entity_id: int
    key: str
    value: str
    source: str
    date_type: MetadataType

    model_config = ConfigDict(from_attributes=True)
