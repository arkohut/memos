from typing import List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
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


def get_library_by_id(library_id: int, db: Session) -> Library | None:
    return db.query(LibraryModel).filter(LibraryModel.id == library_id).first()


def create_library(library: NewLibraryParam, db: Session) -> Library:
    db_library = LibraryModel(name=library.name)
    db.add(db_library)
    db.commit()
    db.refresh(db_library)

    for folder_path in library.folders:
        db_folder = FolderModel(path=str(folder_path), library_id=db_library.id)
        db.add(db_folder)

    db.commit()
    return Library(
        id=db_library.id,
        name=db_library.name,
        folders=[
            Folder(id=db_folder.id, path=db_folder.path)
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
    db_folders = []
    for folder_path in folders.folders:
        db_folder = FolderModel(path=str(folder_path), library_id=library_id)
        db.add(db_folder)
        db.commit()
        db.refresh(db_folder)
        db_folders.append(Folder(id=db_folder.id, path=db_folder.path))

    db_library = db.query(LibraryModel).filter(LibraryModel.id == library_id).first()
    return Library(**db_library.__dict__)


def create_entity(library_id: int, entity: NewEntityParam, db: Session) -> Entity:
    tags = entity.tags
    metadata_entries = entity.metadata_entries

    # Remove tags and metadata_entries from entity
    entity.tags = None
    entity.metadata_entries = None

    db_entity = EntityModel(**entity.model_dump(exclude_none=True), library_id=library_id)
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
    library_plugin = db.query(LibraryPluginModel).filter(
        LibraryPluginModel.library_id == library_id,
        LibraryPluginModel.plugin_id == plugin_id
    ).first()
    
    if library_plugin:
        db.delete(library_plugin)
        db.commit()
    else:
        raise ValueError(f"Plugin {plugin_id} not found in library {library_id}")