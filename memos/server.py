import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import List

from .config import get_database_path
from .crud import get_library_by_id, create_library
from .schemas import (
    Library,
    Folder,
    Entity,
    Plugin,
    NewLibraryParam,
    NewFolderParam,
    NewEntityParam,
    NewPluginParam,
    NewLibraryPluginParam,
)

engine = create_engine(f"sqlite:///{get_database_path()}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/libraries", response_model=Library)
def new_library(library_param: NewLibraryParam, db: Session = Depends(get_db)):
    library = create_library(library_param, db)
    return library


@app.post("/libraries/{library_id}/folders", response_model=Folder)
def new_folder(
    library_id: int,
    folder: NewFolderParam, db: Session = Depends(get_db),
):
    library = get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(status_code=404, detail="Library not found")
    
    db_folder = Folder(path=folder.path, library_id=library.id)
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)
    return db_folder


@app.post("/libraries/{library_id}/entities", response_model=Entity)
def new_entity(
    entity: NewEntityParam, library_id: int, db: Session = Depends(get_db)
):

    db_entity = Entity(**entity.model_dump(), library_id=library_id)
    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    return db_entity


@app.post("/plugins", response_model=Plugin)
def new_plugin(plugin: NewPluginParam, db: Session = Depends(get_db)):
    db_plugin = Plugin(**plugin.model_dump())
    db.add(db_plugin)
    db.commit()
    db.refresh(db_plugin)
    return db_plugin


@app.post("/libraries/{library_id}/plugins", status_code=status.HTTP_204_NO_CONTENT)
def add_library_plugin(
    library_id: int, plugin: NewLibraryPluginParam, db: Session = Depends(get_db)
):
    db_library_plugin = LibrayPlugin(library_id=library_id, plugin_id=plugin.plugin_id)
    db.add(db_library_plugin)
    db.commit()
    db.refresh(db_library_plugin)


def run_server():
    uvicorn.run("memos.server:app", host="0.0.0.0", port=8080, reload=True)
