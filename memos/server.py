import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import List

from .config import get_database_path
import memos.crud as crud
from .schemas import (
    Library,
    Folder,
    Entity,
    Plugin,
    NewLibraryParam,
    NewFolderParam,
    NewEntityParam,
    UpdateEntityParam,
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


@app.get("/")
def root():
    return {"healthy": True}


@app.post("/libraries", response_model=Library)
def new_library(library_param: NewLibraryParam, db: Session = Depends(get_db)):
    library = crud.create_library(library_param, db)
    return library


@app.get("/libraries", response_model=List[Library])
def list_libraries(db: Session = Depends(get_db)):
    libraries = crud.get_libraries(db)
    return libraries


@app.post("/libraries/{library_id}/folders", response_model=Folder)
def new_folder(
    library_id: int,
    folder: NewFolderParam,
    db: Session = Depends(get_db),
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(status_code=404, detail="Library not found")

    db_folder = Folder(path=folder.path, library_id=library.id)
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)
    return db_folder


@app.post("/libraries/{library_id}/entities", response_model=Entity)
def new_entity(
    new_entity: NewEntityParam, library_id: int, db: Session = Depends(get_db)
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(status_code=404, detail="Library not found")
    
    entity = crud.create_entity(library_id, new_entity, db)
    return entity


@app.put("/libraries/{library_id}/entities/{entity_id}", response_model=Entity)
def update_entity(
    library_id: int,
    entity_id: int,
    updated_entity: UpdateEntityParam,
    db: Session = Depends(get_db),
):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None or entity.library_id != library_id:
        raise HTTPException(
            status_code=404, detail="Entity not found in the specified library"
        )

    entity = crud.update_entity(entity_id, updated_entity, db)
    return entity


@app.post("/plugins", response_model=Plugin)
def new_plugin(new_plugin: NewPluginParam, db: Session = Depends(get_db)):
    plugin = crud.create_plugin(new_plugin, db)
    return plugin


@app.post("/libraries/{library_id}/plugins", status_code=status.HTTP_204_NO_CONTENT)
def add_library_plugin(
    library_id: int, new_plugin: NewLibraryPluginParam, db: Session = Depends(get_db)
):
    crud.add_plugin_to_library(library_id, new_plugin.plugin_id, db)


def run_server():
    uvicorn.run("memos.server:app", host="0.0.0.0", port=8080, reload=True)
