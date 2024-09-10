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
)
from datetime import datetime
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from typing import List
from .schemas import MetadataSource, MetadataType
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from .config import get_database_path, settings


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
        "FolderModel", back_populates="library", lazy="joined"
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


def init_database():
    """Initialize the database."""
    db_path = get_database_path()
    engine = create_engine(f"sqlite:///{db_path}")

    try:
        Base.metadata.create_all(engine)
        print(f"Database initialized successfully at {db_path}")

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
            library_plugin = LibraryPluginModel(
                library_id=1, plugin_id=bind_response.id
            )  # Assuming library_id=1 for default libraries
            session.add(library_plugin)

    session.commit()
