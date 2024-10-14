from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from .schemas import (
    Library,
    NewLibraryParam,
    Folder,
    NewEntityParam,
    Entity,
    Plugin,
    NewPluginParam,
    UpdateEntityParam,
    NewFoldersParam,
    MetadataSource,
    EntityMetadataParam,
)
from .models import (
    LibraryModel,
    FolderModel,
    EntityModel,
    EntityModel,
    PluginModel,
    LibraryPluginModel,
    TagModel,
    EntityMetadataModel,
    EntityTagModel,
)
import numpy as np
from collections import defaultdict
from .embedding import get_embeddings
import logging
from sqlite_vec import serialize_float32
import time
import asyncio

logger = logging.getLogger(__name__)


def get_library_by_id(library_id: int, db: Session) -> Library | None:
    return db.query(LibraryModel).filter(LibraryModel.id == library_id).first()


def create_library(library: NewLibraryParam, db: Session) -> Library:
    db_library = LibraryModel(name=library.name)
    db.add(db_library)
    db.commit()
    db.refresh(db_library)

    for folder in library.folders:
        db_folder = FolderModel(
            path=str(folder.path),
            library_id=db_library.id,
            last_modified_at=folder.last_modified_at,
            type=folder.type,
        )
        db.add(db_folder)

    db.commit()
    return Library(
        id=db_library.id,
        name=db_library.name,
        folders=[
            Folder(
                id=db_folder.id,
                path=db_folder.path,
                last_modified_at=db_folder.last_modified_at,
                type=db_folder.type,
            )
            for db_folder in db_library.folders
        ],
        plugins=[],
    )


def get_libraries(db: Session) -> List[Library]:
    return db.query(LibraryModel).all()


def get_library_by_name(library_name: str, db: Session) -> Library | None:
    return (
        db.query(LibraryModel)
        .filter(func.lower(LibraryModel.name) == library_name.lower())
        .first()
    )


def add_folders(library_id: int, folders: NewFoldersParam, db: Session) -> Library:
    for folder in folders.folders:
        db_folder = FolderModel(
            path=str(folder.path),
            library_id=library_id,
            last_modified_at=folder.last_modified_at,
            type=folder.type,
        )
        db.add(db_folder)
        db.commit()
        db.refresh(db_folder)

    db_library = db.query(LibraryModel).filter(LibraryModel.id == library_id).first()
    return Library(**db_library.__dict__)


def create_entity(library_id: int, entity: NewEntityParam, db: Session) -> Entity:
    tags = entity.tags
    metadata_entries = entity.metadata_entries

    # Remove tags and metadata_entries from entity
    entity.tags = None
    entity.metadata_entries = None

    db_entity = EntityModel(
        **entity.model_dump(exclude_none=True), library_id=library_id
    )
    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)

    # Handle tags separately
    if tags:
        for tag_name in tags:
            tag = db.query(TagModel).filter(TagModel.name == tag_name).first()
            if not tag:
                tag = TagModel(name=tag_name)
                db.add(tag)
                db.commit()
                db.refresh(tag)
            entity_tag = EntityTagModel(
                entity_id=db_entity.id,
                tag_id=tag.id,
                source=MetadataSource.PLUGIN_GENERATED,
            )
            db.add(entity_tag)
        db.commit()

    # Handle attrs separately
    if metadata_entries:
        for attr in metadata_entries:
            entity_metadata = EntityMetadataModel(
                entity_id=db_entity.id,
                key=attr.key,
                value=attr.value,
                source=attr.source,
                source_type=MetadataSource.PLUGIN_GENERATED if attr.source else None,
                data_type=attr.data_type,
            )
            db.add(entity_metadata)
    db.commit()
    db.refresh(db_entity)
    return Entity(**db_entity.__dict__)


def get_entity_by_id(entity_id: int, db: Session) -> Entity | None:
    return db.query(EntityModel).filter(EntityModel.id == entity_id).first()


def get_entities_of_folder(
    library_id: int, folder_id: int, db: Session, limit: int = 10, offset: int = 0
) -> Tuple[List[Entity], int]:
    folder = (
        db.query(FolderModel)
        .filter(FolderModel.id == folder_id, FolderModel.library_id == library_id)
        .first()
    )
    if folder is None:
        return [], 0

    query = db.query(EntityModel).filter(EntityModel.folder_id == folder_id)

    total_count = query.count()

    entities = query.limit(limit).offset(offset).all()

    return entities, total_count


def get_entity_by_filepath(filepath: str, db: Session) -> Entity | None:
    return db.query(EntityModel).filter(EntityModel.filepath == filepath).first()


def get_entities_by_filepaths(filepaths: List[str], db: Session) -> List[Entity]:
    return db.query(EntityModel).filter(EntityModel.filepath.in_(filepaths)).all()


def remove_entity(entity_id: int, db: Session):
    entity = db.query(EntityModel).filter(EntityModel.id == entity_id).first()
    if entity:
        db.delete(entity)
        db.commit()
    else:
        raise ValueError(f"Entity with id {entity_id} not found")


def create_plugin(newPlugin: NewPluginParam, db: Session) -> Plugin:
    db_plugin = PluginModel(**newPlugin.model_dump(mode="json"))
    db.add(db_plugin)
    db.commit()
    db.refresh(db_plugin)
    return db_plugin


def get_plugins(db: Session) -> List[Plugin]:
    return db.query(PluginModel).all()


def get_plugin_by_name(plugin_name: str, db: Session) -> Plugin | None:
    return (
        db.query(PluginModel)
        .filter(func.lower(PluginModel.name) == plugin_name.lower())
        .first()
    )


def add_plugin_to_library(library_id: int, plugin_id: int, db: Session):
    library_plugin = LibraryPluginModel(library_id=library_id, plugin_id=plugin_id)
    db.add(library_plugin)
    db.commit()
    db.refresh(library_plugin)


def find_entity_by_id(entity_id: int, db: Session) -> Entity | None:
    db_entity = db.query(EntityModel).filter(EntityModel.id == entity_id).first()
    if db_entity is None:
        return None
    return Entity(**db_entity.__dict__)


def find_entities_by_ids(entity_ids: List[int], db: Session) -> List[Entity]:
    db_entities = db.query(EntityModel).filter(EntityModel.id.in_(entity_ids)).all()
    return [Entity(**entity.__dict__) for entity in db_entities]


def update_entity(
    entity_id: int, updated_entity: UpdateEntityParam, db: Session
) -> Entity:
    db_entity = db.query(EntityModel).filter(EntityModel.id == entity_id).first()

    if db_entity is None:
        raise ValueError(f"Entity with id {entity_id} not found")

    # Update the main fields of the entity
    for key, value in updated_entity.model_dump().items():
        if key not in ["tags", "metadata_entries"] and value is not None:
            setattr(db_entity, key, value)

    # Handle tags separately
    if updated_entity.tags is not None:
        # Clear existing tags
        db.query(EntityTagModel).filter(EntityTagModel.entity_id == entity_id).delete()
        db.commit()

        for tag_name in updated_entity.tags:
            tag = db.query(TagModel).filter(TagModel.name == tag_name).first()
            if not tag:
                tag = TagModel(name=tag_name)
                db.add(tag)
                db.commit()
                db.refresh(tag)
            entity_tag = EntityTagModel(
                entity_id=db_entity.id,
                tag_id=tag.id,
                source=MetadataSource.PLUGIN_GENERATED,
            )
            db.add(entity_tag)
        db.commit()

    # Handle attrs separately
    if updated_entity.metadata_entries is not None:
        # Clear existing attrs
        db.query(EntityMetadataModel).filter(
            EntityMetadataModel.entity_id == entity_id
        ).delete()
        db.commit()

        for attr in updated_entity.metadata_entries:
            entity_metadata = EntityMetadataModel(
                entity_id=db_entity.id,
                key=attr.key,
                value=attr.value,
                source=attr.source if attr.source is not None else None,
                source_type=(
                    MetadataSource.PLUGIN_GENERATED if attr.source is not None else None
                ),
                data_type=attr.data_type,
            )
            db.add(entity_metadata)
            db_entity.metadata_entries.append(entity_metadata)

    db.commit()
    db.refresh(db_entity)
    return Entity(**db_entity.__dict__)


def touch_entity(entity_id: int, db: Session) -> bool:
    db_entity = db.query(EntityModel).filter(EntityModel.id == entity_id).first()
    if db_entity:
        db_entity.last_scan_at = func.now()
        db.commit()
        db.refresh(db_entity)
        return True
    else:
        return False


def update_entity_tags(entity_id: int, tags: List[str], db: Session) -> Entity:
    db_entity = get_entity_by_id(entity_id, db)
    if not db_entity:
        raise ValueError(f"Entity with id {entity_id} not found")

    # Clear existing tags
    db.query(EntityTagModel).filter(EntityTagModel.entity_id == entity_id).delete()
    db.commit()

    for tag_name in tags:
        tag = db.query(TagModel).filter(TagModel.name == tag_name).first()
        if not tag:
            tag = TagModel(name=tag_name)
            db.add(tag)
            db.commit()
            db.refresh(tag)
        entity_tag = EntityTagModel(
            entity_id=db_entity.id,
            tag_id=tag.id,
            source=MetadataSource.PLUGIN_GENERATED,
        )
        db.add(entity_tag)
    db.commit()
    db.refresh(db_entity)
    return Entity(**db_entity.__dict__)


def add_new_tags(entity_id: int, tags: List[str], db: Session) -> Entity:
    db_entity = get_entity_by_id(entity_id, db)
    if not db_entity:
        raise ValueError(f"Entity with id {entity_id} not found")

    existing_tags = set(tag.name for tag in db_entity.tags)
    new_tags = set(tags) - existing_tags

    for tag_name in new_tags:
        tag = db.query(TagModel).filter(TagModel.name == tag_name).first()
        if not tag:
            tag = TagModel(name=tag_name)
            db.add(tag)
            db.commit()
            db.refresh(tag)
        entity_tag = EntityTagModel(
            entity_id=db_entity.id,
            tag_id=tag.id,
            source=MetadataSource.PLUGIN_GENERATED,
        )
        db.add(entity_tag)
    db.commit()
    db.refresh(db_entity)
    return Entity(**db_entity.__dict__)


def update_entity_metadata_entries(
    entity_id: int, updated_metadata: List[EntityMetadataParam], db: Session
) -> Entity:
    db_entity = get_entity_by_id(entity_id, db)

    existing_metadata_entries = (
        db.query(EntityMetadataModel)
        .filter(EntityMetadataModel.entity_id == db_entity.id)
        .all()
    )

    existing_metadata_dict = {entry.key: entry for entry in existing_metadata_entries}

    for metadata in updated_metadata:
        if metadata.key in existing_metadata_dict:
            existing_metadata = existing_metadata_dict[metadata.key]
            existing_metadata.value = metadata.value
            existing_metadata.source = (
                metadata.source
                if metadata.source is not None
                else existing_metadata.source
            )
            existing_metadata.source_type = (
                MetadataSource.PLUGIN_GENERATED
                if metadata.source is not None
                else existing_metadata.source_type
            )
            existing_metadata.data_type = metadata.data_type
        else:
            entity_metadata = EntityMetadataModel(
                entity_id=db_entity.id,
                key=metadata.key,
                value=metadata.value,
                source=metadata.source if metadata.source is not None else None,
                source_type=(
                    MetadataSource.PLUGIN_GENERATED
                    if metadata.source is not None
                    else None
                ),
                data_type=metadata.data_type,
            )
            db.add(entity_metadata)
            db_entity.metadata_entries.append(entity_metadata)

    db.commit()
    db.refresh(db_entity)
    return Entity(**db_entity.__dict__)


def get_plugin_by_id(plugin_id: int, db: Session) -> Plugin | None:
    return db.query(PluginModel).filter(PluginModel.id == plugin_id).first()


def remove_plugin_from_library(library_id: int, plugin_id: int, db: Session):
    library_plugin = (
        db.query(LibraryPluginModel)
        .filter(
            LibraryPluginModel.library_id == library_id,
            LibraryPluginModel.plugin_id == plugin_id,
        )
        .first()
    )

    if library_plugin:
        db.delete(library_plugin)
        db.commit()
    else:
        raise ValueError(f"Plugin {plugin_id} not found in library {library_id}")


def and_words(input_string):
    words = input_string.split()
    result = " AND ".join(words)
    return result


def full_text_search(
    query: str,
    db: Session,
    limit: int = 200,
    library_ids: Optional[List[int]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> List[int]:
    and_query = and_words(query)

    sql_query = """
    SELECT entities.id FROM entities
    JOIN entities_fts ON entities.id = entities_fts.id
    WHERE entities_fts MATCH jieba_query(:query)
    AND entities.file_type_group = 'image'
    """

    params = {"query": and_query, "limit": limit}

    if library_ids:
        library_ids_str = ", ".join(f"'{id}'" for id in library_ids)
        sql_query += f" AND entities.library_id IN ({library_ids_str})"
    if start is not None and end is not None:
        sql_query += " AND strftime('%s', entities.file_created_at, 'utc') BETWEEN :start AND :end"
        params["start"] = str(start)
        params["end"] = str(end)

    sql_query += " ORDER BY bm25(entities_fts), entities.file_created_at DESC LIMIT :limit"

    result = db.execute(text(sql_query), params).fetchall()

    logger.info(f"Full-text search sql: {sql_query}")
    logger.info(f"Full-text search params: {params}")
    ids = [row[0] for row in result]
    logger.info(f"Full-text search results: {ids}")
    return ids


async def vec_search(
    query: str,
    db: Session,
    limit: int = 200,
    library_ids: Optional[List[int]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> List[int]:
    query_embedding = await get_embeddings([query])
    if not query_embedding:
        return []

    query_embedding = query_embedding[0]

    sql_query = """
    SELECT entities.id FROM entities
    JOIN entities_vec ON entities.id = entities_vec.rowid
    WHERE entities_vec.embedding MATCH :embedding
    AND entities.file_type_group = 'image'
    """

    params = {"embedding": serialize_float32(query_embedding), "limit": limit}

    if library_ids:
        library_ids_str = ", ".join(f"'{id}'" for id in library_ids)
        sql_query += f" AND entities.library_id IN ({library_ids_str})"

    if start is not None and end is not None:
        sql_query += (
            " AND strftime('%s', entities.file_created_at, 'utc') BETWEEN :start AND :end"
        )
        params["start"] = str(start)
        params["end"] = str(end)

    sql_query += " AND K = :limit ORDER BY distance, entities.file_created_at DESC"

    result = db.execute(text(sql_query), params).fetchall()

    ids = [row[0] for row in result]
    logger.info(f"Vector search results: {ids}")
    return ids


def reciprocal_rank_fusion(
    fts_results: List[int], vec_results: List[int], k: int = 60
) -> List[Tuple[int, float]]:
    rank_dict = defaultdict(float)

    for rank, result_id in enumerate(fts_results):
        rank_dict[result_id] += 1 / (k + rank + 1)

    for rank, result_id in enumerate(vec_results):
        rank_dict[result_id] += 1 / (k + rank + 1)

    sorted_results = sorted(rank_dict.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


async def hybrid_search(
    query: str,
    db: Session,
    limit: int = 200,
    library_ids: Optional[List[int]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> List[Entity]:
    start_time = time.time()

    fts_start = time.time()
    fts_results = full_text_search(query, db, limit, library_ids, start, end)
    fts_end = time.time()
    logger.info(f"Full-text search took {fts_end - fts_start:.4f} seconds")

    vec_start = time.time()
    vec_results = await vec_search(query, db, limit, library_ids, start, end)
    vec_end = time.time()
    logger.info(f"Vector search took {vec_end - vec_start:.4f} seconds")

    fusion_start = time.time()
    combined_results = reciprocal_rank_fusion(fts_results, vec_results)
    fusion_end = time.time()
    logger.info(f"Reciprocal rank fusion took {fusion_end - fusion_start:.4f} seconds")

    sorted_ids = [id for id, _ in combined_results][:limit]
    logger.info(f"Hybrid search results (sorted IDs): {sorted_ids}")

    entities_start = time.time()
    entities = find_entities_by_ids(sorted_ids, db)
    entities_end = time.time()
    logger.info(
        f"Finding entities by IDs took {entities_end - entities_start:.4f} seconds"
    )

    # Create a dictionary mapping entity IDs to entities
    entity_dict = {entity.id: entity for entity in entities}

    # Return entities in the order of sorted_ids
    result = [entity_dict[id] for id in sorted_ids if id in entity_dict]

    end_time = time.time()
    total_time = end_time - start_time
    logger.info(f"Total hybrid search time: {total_time:.4f} seconds")

    return result


async def list_entities(
    db: Session,
    limit: int = 200,
    library_ids: Optional[List[int]] = None,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> List[Entity]:
    query = db.query(EntityModel).filter(EntityModel.file_type_group == "image")

    if library_ids:
        query = query.filter(EntityModel.library_id.in_(library_ids))

    if start is not None and end is not None:
        query = query.filter(
            func.strftime("%s", EntityModel.file_created_at, 'utc').between(
                str(start), str(end)
            )
        )

    entities = query.order_by(EntityModel.file_created_at.desc()).limit(limit).all()

    return [Entity(**entity.__dict__) for entity in entities]
