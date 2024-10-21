from sqlalchemy import (
    create_engine,
    Integer,
    String,
    Text,
    DateTime,
    Enum,
    ForeignKey,
    func,
    Index,
    event,
)
from datetime import datetime
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column, Session
from typing import List
from .schemas import MetadataSource, MetadataType, FolderType
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from .config import get_database_path, settings
from sqlalchemy import text
import sqlite_vec
import sys
from pathlib import Path
import json
from .embedding import get_embeddings
from sqlite_vec import serialize_float32
import asyncio
import threading


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class LibraryModel(Base):
    __tablename__ = "libraries"
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    folders: Mapped[List["FolderModel"]] = relationship(
        "FolderModel",
        back_populates="library",
        lazy="joined",
        primaryjoin="and_(LibraryModel.id==FolderModel.library_id, FolderModel.type=='DEFAULT')",
    )
    plugins: Mapped[List["PluginModel"]] = relationship(
        "PluginModel", secondary="library_plugins", lazy="joined"
    )


class FolderModel(Base):
    __tablename__ = "folders"
    path: Mapped[str] = mapped_column(String, nullable=False)
    library_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("libraries.id"), nullable=False
    )
    library: Mapped["LibraryModel"] = relationship(
        "LibraryModel", back_populates="folders"
    )
    entities: Mapped[List["EntityModel"]] = relationship(
        "EntityModel", back_populates="folder"
    )
    type: Mapped[FolderType] = mapped_column(Enum(FolderType), nullable=False)
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=False)


class EntityModel(Base):
    __tablename__ = "entities"
    filepath: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    file_last_modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    file_type: Mapped[str] = mapped_column(String, nullable=False)
    file_type_group: Mapped[str] = mapped_column(String, nullable=False)
    last_scan_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )
    library_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("libraries.id"), nullable=False
    )
    folder_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("folders.id"), nullable=False
    )
    folder: Mapped["FolderModel"] = relationship(
        "FolderModel", back_populates="entities"
    )
    metadata_entries: Mapped[List["EntityMetadataModel"]] = relationship(
        "EntityMetadataModel", lazy="joined", cascade="all, delete-orphan"
    )
    tags: Mapped[List["TagModel"]] = relationship(
        "TagModel",
        secondary="entity_tags",
        lazy="joined",
        cascade="all, delete",
        overlaps="entities",
    )

    # 添加索引
    __table_args__ = (
        Index("idx_filepath", "filepath"),
        Index("idx_filename", "filename"),
        Index("idx_file_type", "file_type"),
        Index("idx_library_id", "library_id"),
        Index("idx_folder_id", "folder_id"),
    )

    @classmethod
    def update_last_scan_at(cls, session: Session, entity: "EntityModel"):
        entity.last_scan_at = func.now()
        session.add(entity)


class TagModel(Base):
    __tablename__ = "tags"
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    # source: Mapped[str | None] = mapped_column(String, nullable=True)


class EntityTagModel(Base):
    __tablename__ = "entity_tags"
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), nullable=False)
    source: Mapped[MetadataSource] = mapped_column(Enum(MetadataSource), nullable=False)

    __table_args__ = (
        Index("idx_entity_tag_entity_id", "entity_id"),
        Index("idx_entity_tag_tag_id", "tag_id"),
    )


class EntityMetadataModel(Base):
    __tablename__ = "metadata_entries"
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id"), nullable=False
    )
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[MetadataSource] = mapped_column(
        Enum(MetadataSource), nullable=False
    )
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    data_type: Mapped[MetadataType] = mapped_column(Enum(MetadataType), nullable=False)
    entity = relationship("EntityModel", back_populates="metadata_entries")

    __table_args__ = (
        Index("idx_metadata_entity_id", "entity_id"),
        Index("idx_metadata_key", "key"),
    )


class PluginModel(Base):
    __tablename__ = "plugins"
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_url: Mapped[str] = mapped_column(String, nullable=False)


class LibraryPluginModel(Base):
    __tablename__ = "library_plugins"
    library_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("libraries.id"), nullable=False
    )
    plugin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plugins.id"), nullable=False
    )


def load_extension(dbapi_conn, connection_record):
    dbapi_conn.enable_load_extension(True)

    # load simple tokenizer
    current_dir = Path(__file__).parent.resolve()
    if sys.platform.startswith("linux"):
        lib_path = current_dir / "simple_tokenizer" / "linux" / "libsimple"
    elif sys.platform == "win32":
        lib_path = current_dir / "simple_tokenizer" / "windows" / "simple"
    elif sys.platform == "darwin":
        lib_path = current_dir / "simple_tokenizer" / "macos" / "libsimple"
    else:
        raise OSError(f"Unsupported operating system: {sys.platform}")

    dbapi_conn.load_extension(str(lib_path))
    dict_path = current_dir / "simple_tokenizer" / "dict"
    dbapi_conn.execute(f"SELECT jieba_dict('{dict_path}')")

    # load vector ext
    sqlite_vec.load(dbapi_conn)

    # Set WAL mode after loading extensions
    dbapi_conn.execute("PRAGMA journal_mode=WAL")


def recreate_fts_and_vec_tables():
    """Recreate the entities_fts and entities_vec tables without repopulating data."""
    db_path = get_database_path()
    engine = create_engine(f"sqlite:///{db_path}")
    event.listen(engine, "connect", load_extension)

    Session = sessionmaker(bind=engine)

    with Session() as session:
        try:
            # Drop existing tables
            session.execute(text("DROP TABLE IF EXISTS entities_fts"))
            session.execute(text("DROP TABLE IF EXISTS entities_vec"))

            # Recreate entities_fts table
            session.execute(
                text(
                    """
                CREATE VIRTUAL TABLE entities_fts USING fts5(
                    id, filepath, tags, metadata,
                    tokenize = 'simple 0'
                )
            """
                )
            )

            # Recreate entities_vec table
            session.execute(
                text(
                    f"""
                CREATE VIRTUAL TABLE entities_vec USING vec0(
                    embedding float[{settings.embedding.num_dim}]
                )
            """
                )
            )

            session.commit()
            print("Successfully recreated entities_fts and entities_vec tables.")
        except Exception as e:
            session.rollback()
            print(f"Error recreating tables: {e}")


def init_database():
    """Initialize the database."""
    db_path = get_database_path()
    engine = create_engine(f"sqlite:///{db_path}")

    # Use a single event listener for both extension loading and WAL mode setting
    event.listen(engine, "connect", load_extension)

    try:
        Base.metadata.create_all(engine)
        print(f"Database initialized successfully at {db_path}")

        # Create FTS and Vec tables
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
                    id, filepath, tags, metadata,
                    tokenize = 'simple 0'
                )
            """
                )
            )

            conn.execute(
                text(
                    f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS entities_vec USING vec0(
                    embedding float[{settings.embedding.num_dim}]
                )
            """
                )
            )

        # Initialize default plugins
        Session = sessionmaker(bind=engine)
        with Session() as session:
            default_plugins = initialize_default_plugins(session)
            init_default_libraries(session, default_plugins)

        return True
    except OperationalError as e:
        print(f"Error initializing database: {e}")
        return False


def initialize_default_plugins(session):
    default_plugins = [
        PluginModel(
            name="builtin_vlm", description="VLM Plugin", webhook_url="/plugins/vlm"
        ),
        PluginModel(
            name="builtin_ocr", description="OCR Plugin", webhook_url="/plugins/ocr"
        ),
    ]

    for plugin in default_plugins:
        existing_plugin = session.query(PluginModel).filter_by(name=plugin.name).first()
        if not existing_plugin:
            session.add(plugin)

    session.commit()

    return default_plugins


def init_default_libraries(session, default_plugins):
    default_libraries = [
        LibraryModel(name=settings.default_library),
    ]

    for library in default_libraries:
        existing_library = (
            session.query(LibraryModel).filter_by(name=library.name).first()
        )
        if not existing_library:
            session.add(library)

    for plugin in default_plugins:
        bind_response = session.query(PluginModel).filter_by(name=plugin.name).first()
        if bind_response:
            # Check if the LibraryPluginModel already exists
            existing_library_plugin = session.query(LibraryPluginModel).filter_by(
                library_id=1, plugin_id=bind_response.id
            ).first()
            
            if not existing_library_plugin:
                library_plugin = LibraryPluginModel(
                    library_id=1, plugin_id=bind_response.id
                )  # Assuming library_id=1 for default libraries
                session.add(library_plugin)

    session.commit()


@event.listens_for(EntityTagModel, "after_insert")
@event.listens_for(EntityTagModel, "after_delete")
def update_entity_last_scan_at_for_tags(mapper, connection, target):
    session = Session(bind=connection)
    entity = session.query(EntityModel).get(target.entity_id)
    if entity:
        EntityModel.update_last_scan_at(session, entity)
    session.commit()


@event.listens_for(EntityMetadataModel, "after_insert")
@event.listens_for(EntityMetadataModel, "after_update")
@event.listens_for(EntityMetadataModel, "after_delete")
def update_entity_last_scan_at_for_metadata(mapper, connection, target):
    session = Session(bind=connection)
    entity = session.query(EntityModel).get(target.entity_id)
    if entity:
        EntityModel.update_last_scan_at(session, entity)
    session.commit()


async def update_or_insert_entities_vec(session, target_id, embedding):
    try:
        # First, try to update the existing row
        result = session.execute(
            text("UPDATE entities_vec SET embedding = :embedding WHERE rowid = :id"),
            {
                "id": target_id,
                "embedding": serialize_float32(embedding),
            },
        )

        # If no row was updated (i.e., the row doesn't exist), then insert a new row
        if result.rowcount == 0:
            session.execute(
                text(
                    "INSERT INTO entities_vec (rowid, embedding) VALUES (:id, :embedding)"
                ),
                {
                    "id": target_id,
                    "embedding": serialize_float32(embedding),
                },
            )

        session.commit()
    except Exception as e:
        print(f"Error updating entities_vec: {e}")
        session.rollback()


def update_or_insert_entities_fts(session, target_id, filepath, tags, metadata):
    try:
        # First, try to update the existing row
        result = session.execute(
            text(
                """
                UPDATE entities_fts 
                SET filepath = :filepath, tags = :tags, metadata = :metadata 
                WHERE id = :id
                """
            ),
            {
                "id": target_id,
                "filepath": filepath,
                "tags": tags,
                "metadata": metadata,
            },
        )

        # If no row was updated (i.e., the row doesn't exist), then insert a new row
        if result.rowcount == 0:
            session.execute(
                text(
                    """
                    INSERT INTO entities_fts(id, filepath, tags, metadata)
                    VALUES(:id, :filepath, :tags, :metadata)
                    """
                ),
                {
                    "id": target_id,
                    "filepath": filepath,
                    "tags": tags,
                    "metadata": metadata,
                },
            )

        session.commit()
    except Exception as e:
        print(f"Error updating entities_fts: {e}")
        session.rollback()


async def update_fts_and_vec(mapper, connection, target):
    session = Session(bind=connection)

    # Prepare FTS data
    tags = ", ".join([tag.name for tag in target.tags])

    # Process metadata entries
    def process_ocr_result(value, max_length=4096):
        try:
            ocr_data = json.loads(value)
            if isinstance(ocr_data, list) and all(
                isinstance(item, dict)
                and "dt_boxes" in item
                and "rec_txt" in item
                and "score" in item
                for item in ocr_data
            ):
                return " ".join(item["rec_txt"] for item in ocr_data[:max_length])
            else:
                return json.dumps(ocr_data, indent=2)
        except json.JSONDecodeError:
            return value

    fts_metadata = "\n".join(
        [
            f"{entry.key}: {process_ocr_result(entry.value) if entry.key == 'ocr_result' else entry.value}"
            for entry in target.metadata_entries
        ]
    )

    # Update FTS table
    update_or_insert_entities_fts(session, target.id, target.filepath, tags, fts_metadata)

    # Prepare vector data
    metadata_text = "\n".join(
        [
            f"{entry.key}: {entry.value}"
            for entry in target.metadata_entries
            if entry.key != "ocr_result"
        ]
    )

    # Add ocr_result at the end of metadata_text using process_ocr_result
    ocr_result = next(
        (entry.value for entry in target.metadata_entries if entry.key == "ocr_result"),
        ""
    )
    processed_ocr_result = process_ocr_result(ocr_result, max_length=128)
    metadata_text += f"\nocr_result: {processed_ocr_result}"

    # Use the new get_embeddings function
    embeddings = await get_embeddings([metadata_text])
    if not embeddings:
        embedding = []
    else:
        embedding = embeddings[0]

    # Update vector table
    if embedding:
        await update_or_insert_entities_vec(session, target.id, embedding)


def delete_fts_and_vec(mapper, connection, target):
    connection.execute(
        text("DELETE FROM entities_fts WHERE id = :id"), {"id": target.id}
    )
    connection.execute(
        text("DELETE FROM entities_vec WHERE rowid = :id"), {"id": target.id}
    )


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def update_fts_and_vec_sync(mapper, connection, target):
    def run_in_thread():
        run_async(update_fts_and_vec(mapper, connection, target))

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()


# Replace the old event listener with the new sync version
event.listen(EntityModel, "after_insert", update_fts_and_vec_sync)
event.listen(EntityModel, "after_update", update_fts_and_vec_sync)
event.listen(EntityModel, "after_delete", delete_fts_and_vec)
