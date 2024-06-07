import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import List, Annotated

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
    # Check if a library with the same name (case insensitive) already exists
    existing_library = crud.get_library_by_name(library_param.name, db)
    if existing_library:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Library with this name already exists",
        )

    # Remove duplicate folders from the library_param
    unique_folders = list(set(library_param.folders))
    library_param.folders = unique_folders
    library = crud.create_library(library_param, db)
    return library


@app.get("/libraries", response_model=List[Library])
def list_libraries(db: Session = Depends(get_db)):
    libraries = crud.get_libraries(db)
    return libraries


@app.get("/libraries/{library_id}", response_model=Library)
def get_library_by_id(library_id: int, db: Session = Depends(get_db)):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )
    return library


@app.post("/libraries/{library_id}/folders", response_model=Folder)
def new_folder(
    library_id: int,
    folder: NewFolderParam,
    db: Session = Depends(get_db),
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )

    existing_folders = [folder.path for folder in library.folders]
    if str(folder.path) in existing_folders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder already exists in the library",
        )

    return crud.add_folder(library_id=library.id, folder=folder, db=db)


@app.post("/libraries/{library_id}/entities", response_model=Entity)
def new_entity(
    new_entity: NewEntityParam, library_id: int, db: Session = Depends(get_db)
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )

    entity = crud.create_entity(library_id, new_entity, db)
    return entity


@app.get(
    "/libraries/{library_id}/folders/{folder_id}/entities", response_model=List[Entity]
)
def list_entities_in_folder(
    library_id: int,
    folder_id: int,
    limit: Annotated[int, Query(ge=1, le=200)] = 10,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )

    if folder_id not in [folder.id for folder in library.folders]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Folder not found in the specified library",
        )

    return crud.get_entities_of_folder(library_id, folder_id, db, limit, offset)


@app.get("/libraries/{library_id}/entities/by-filepath", response_model=Entity)
def get_entity_by_filepath(
    library_id: int, filepath: str, db: Session = Depends(get_db)
):
    entity = crud.get_entity_by_filepath(filepath, db)
    if entity is None or entity.library_id != library_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found"
        )
    return entity


@app.get("/libraries/{library_id}/entities/{entity_id}", response_model=Entity)
def get_entity_by_id(library_id: int, entity_id: int, db: Session = Depends(get_db)):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None or entity.library_id != library_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found"
        )
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found in the specified library",
        )

    entity = crud.update_entity(entity_id, updated_entity, db)
    return entity


@app.delete(
    "/libraries/{library_id}/entities/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_entity(library_id: int, entity_id: int, db: Session = Depends(get_db)):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None or entity.library_id != library_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found in the specified library",
        )

    crud.remove_entity(entity_id, db)


@app.post("/plugins", response_model=Plugin)
def new_plugin(new_plugin: NewPluginParam, db: Session = Depends(get_db)):
    existing_plugin = crud.get_plugin_by_name(new_plugin.name, db)
    if existing_plugin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plugin with this name already exists",
        )
    plugin = crud.create_plugin(new_plugin, db)
    return plugin


@app.get("/plugins", response_model=List[Plugin])
def list_plugins(db: Session = Depends(get_db)):
    plugins = crud.get_plugins(db)
    return plugins



@app.post("/libraries/{library_id}/plugins", status_code=status.HTTP_204_NO_CONTENT)
def add_library_plugin(
    library_id: int, new_plugin: NewLibraryPluginParam, db: Session = Depends(get_db)
):
    library = crud.get_library_by_id(library_id, db)
    if any(plugin.id == new_plugin.plugin_id for plugin in library.plugins):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plugin already exists in the library",
        )
    crud.add_plugin_to_library(library_id, new_plugin.plugin_id, db)


def run_server():
    uvicorn.run("memos.server:app", host="0.0.0.0", port=8080, reload=True)
