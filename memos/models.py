from sqlalchemy import (
    create_engine,
    Integer,
    String,
    Text,
    DateTime,
    Enum
)
from datetime import datetime
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from enum import Enum as PyEnum
from typing import List
from .config import get_database_path


class MetadataSource(PyEnum):
    USER_GENERATED = "user_generated"
    SYSTEM_GENERATED = "system_generated"
    PLUGIN_GENERATED = "plugin_generated"


class MetadataType(PyEnum):
    EXTRACONTENT = "extra_content"
    ATTRIBUTE = "attribute"


class Base(DeclarativeBase):
    pass


class Library(Base):
    __tablename__ = "libraries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    folders: Mapped[List["Folder"]] = relationship("Folder", back_populates="library")
    plugins: Mapped[List["Plugin"]] = relationship("LibraryPlugin", back_populates="library")


class Folder(Base):
    __tablename__ = "folders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    path: Mapped[str] = mapped_column(String, nullable=False)
    library_id: Mapped[int] = mapped_column(Integer, nullable=False)
    library: Mapped["Library"] = relationship("Library", back_populates="folders")
    entities: Mapped[List["Entity"]] = relationship("Entity", back_populates="folder")


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    path: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    filetype: Mapped[str] = mapped_column(String, nullable=False)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    folder_id: Mapped[int] = mapped_column(Integer, nullable=False)
    folder: Mapped["Folder"] = relationship("Folder", back_populates="entities")
    metadata_entries: Mapped[List["EntityMetadata"]] = relationship("EntityMetadata", back_populates="entity")


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EntityTag(Base):
    __tablename__ = "entity_tags"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    tag_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[MetadataSource] = mapped_column(Enum(MetadataSource), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class EntityMetadata(Base):
    __tablename__ = "metadata_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[MetadataSource] = mapped_column(Enum(MetadataSource), nullable=False)
    datetype: Mapped[MetadataType] = mapped_column(Enum(MetadataType), nullable=False)
    entity = relationship("Entity", back_populates="metadata_entries")


class Plugin(Base):
    __tablename__ = "plugins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    webhook_url: Mapped[str] = mapped_column(String, nullable=False)
    libraries = relationship("LibraryPlugin", back_populates="plugin")


class LibraryPlugin(Base):
    __tablename__ = "library_plugins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    library_id: Mapped[int] = mapped_column(Integer, nullable=False)
    plugin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    library = relationship("Library", back_populates="plugins")
    plugin = relationship("Plugin", back_populates="libraries")


# Create the database engine with the path from config
engine = create_engine(f"sqlite:///{get_database_path()}", echo=True)
Base.metadata.create_all(engine)
