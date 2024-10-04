from pydantic import (
    BaseModel,
    ConfigDict,
    DirectoryPath,
    HttpUrl,
    Field,
    model_validator,
)
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum


class FolderType(Enum):
    DEFAULT = "default"
    DUMMY = "dummy"


class MetadataSource(Enum):
    USER_GENERATED = "user_generated"
    SYSTEM_GENERATED = "system_generated"
    PLUGIN_GENERATED = "plugin_generated"


class MetadataType(Enum):
    JSON_DATA = "json"
    TEXT_DATA = "text"
    NUMBER_DATA = "number"


class NewFolderParam(BaseModel):
    path: DirectoryPath
    last_modified_at: datetime
    type: str = FolderType.DEFAULT


class NewLibraryParam(BaseModel):
    name: str
    folders: List[NewFolderParam] = []


class NewFoldersParam(BaseModel):
    folders: List[NewFolderParam] = []


class EntityMetadataParam(BaseModel):
    key: str
    value: str
    source: str
    data_type: MetadataType


class NewEntityParam(BaseModel):
    filename: str
    filepath: str
    size: int
    file_created_at: datetime
    file_last_modified_at: datetime
    file_type: str
    file_type_group: str
    folder_id: int
    tags: List[str] | None = None
    metadata_entries: List[EntityMetadataParam] | None = None


class UpdateEntityParam(BaseModel):
    size: int | None = None
    file_created_at: datetime | None = None
    file_last_modified_at: datetime | None = None
    file_type: str | None = None
    file_type_group: str | None = None
    tags: List[str] | None = None
    metadata_entries: List[EntityMetadataParam] | None = None


class UpdateTagParam(BaseModel):
    description: str | None
    color: str | None


class UpdateEntityTagsParam(BaseModel):
    tags: List[str] = []


class UpdateEntityMetadataParam(BaseModel):
    metadata_entries: List[EntityMetadataParam]


class NewPluginParam(BaseModel):
    name: str
    description: str | None
    webhook_url: HttpUrl


class NewLibraryPluginParam(BaseModel):
    plugin_id: Optional[int] = None
    plugin_name: Optional[str] = None

    @model_validator(mode="after")
    def check_either_id_or_name(self):
        plugin_id = self.plugin_id
        plugin_name = self.plugin_name
        if not (plugin_id or plugin_name):
            raise ValueError("Either plugin_id or plugin_name must be provided")
        if plugin_id is not None and plugin_name is not None:
            raise ValueError("Only one of plugin_id or plugin_name should be provided")
        return self


class Folder(BaseModel):
    id: int
    path: str
    last_modified_at: datetime
    type: FolderType

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


class Tag(BaseModel):
    id: int
    name: str
    description: str | None
    color: str | None
    created_at: datetime
    # source: str

    model_config = ConfigDict(from_attributes=True)


class EntityMetadata(BaseModel):
    id: int
    entity_id: int
    key: str
    value: str
    source: str
    data_type: MetadataType

    model_config = ConfigDict(from_attributes=True)


class Entity(BaseModel):
    id: int
    filepath: str
    filename: str
    size: int
    file_created_at: datetime
    file_last_modified_at: datetime
    file_type: str
    file_type_group: str
    last_scan_at: datetime | None
    folder_id: int
    library_id: int
    tags: List[Tag] = []
    metadata_entries: List[EntityMetadata] = []

    model_config = ConfigDict(from_attributes=True)

    def get_metadata_by_key(self, key: str) -> Optional[EntityMetadata]:
        """
        Get EntityMetadata by key.

        Args:
            key (str): The key to search for in metadata entries.

        Returns:
            Optional[EntityMetadata]: The EntityMetadata if found, None otherwise.
        """
        for metadata in self.metadata_entries:
            if metadata.key == key:
                return metadata
        return None


class MetadataIndexItem(BaseModel):
    key: str
    value: Any
    source: str


class EntityIndexItem(BaseModel):
    id: str
    filepath: str
    filename: str
    size: int
    file_created_at: int = Field(..., description="Unix timestamp")
    created_date: Optional[str] = None
    created_month: Optional[str] = None
    created_year: Optional[str] = None
    file_last_modified_at: int = Field(..., description="Unix timestamp")
    file_type: str
    file_type_group: str
    last_scan_at: Optional[int] = Field(None, description="Unix timestamp")
    library_id: int
    folder_id: int
    tags: List[str]
    metadata_entries: List[MetadataIndexItem]
    metadata_text: str
    embedding: Optional[List[float]] = Field(None, description="Embedding vector")


class EntitySearchResult(BaseModel):
    id: str
    filepath: str
    filename: str
    size: int
    file_created_at: int = Field(..., description="Unix timestamp")
    created_date: Optional[str] = None
    created_month: Optional[str] = None
    created_year: Optional[str] = None
    file_last_modified_at: int = Field(..., description="Unix timestamp")
    file_type: str
    file_type_group: str
    last_scan_at: Optional[int] = Field(None, description="Unix timestamp")
    library_id: int
    folder_id: int
    tags: List[str]
    metadata_entries: List[MetadataIndexItem]
    facets: Optional[Dict[str, Any]] = None


class FacetCount(BaseModel):
    count: int
    highlighted: str
    value: str


class FacetStats(BaseModel):
    total_values: int


class Facet(BaseModel):
    counts: List[FacetCount]
    field_name: str
    sampled: bool
    stats: FacetStats


class TextMatchInfo(BaseModel):
    best_field_score: str
    best_field_weight: int
    fields_matched: int
    num_tokens_dropped: int
    score: str
    tokens_matched: int
    typo_prefix_score: int


class HybridSearchInfo(BaseModel):
    rank_fusion_score: float


class SearchHit(BaseModel):
    document: EntitySearchResult
    highlight: Dict[str, Any] = {}
    highlights: List[Any] = []
    hybrid_search_info: Optional[HybridSearchInfo] = None
    text_match: Optional[int] = None
    text_match_info: Optional[TextMatchInfo] = None


class RequestParams(BaseModel):
    collection_name: str
    first_q: str
    per_page: int
    q: str


class SearchResult(BaseModel):
    facet_counts: List[Facet]
    found: int
    hits: List[SearchHit]
    out_of: int
    page: int
    request_params: RequestParams
    search_cutoff: bool
    search_time_ms: int
