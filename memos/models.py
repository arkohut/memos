from sqlalchemy import (
    create_engine,
    Integer,
    String,
    Text,
    DateTime,
    Enum,
    ForeignKey,
    func,
)
from datetime import datetime
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from typing import List
from .config import get_database_path
from .schemas import MetadataSource, MetadataType


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
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
        "EntityMetadataModel", lazy="joined"
    )
    tags: Mapped[List["TagModel"]] = relationship("TagModel", secondary="entity_tags", lazy="joined")



class TagModel(Base):
    __tablename__ = "tags"
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    # source: Mapped[str | None] = mapped_column(String, nullable=True)


class EntityTagModel(Base):
    __tablename__ = "entity_tags"
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id"), nullable=False
    )
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), nullable=False)
    source: Mapped[MetadataSource] = mapped_column(Enum(MetadataSource), nullable=False)


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


# Create the database engine with the path from config
engine = create_engine(f"sqlite:///{get_database_path()}")
Base.metadata.create_all(engine)
