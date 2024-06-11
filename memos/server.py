import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import List, Annotated
import asyncio

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
    UpdateEntityTagsParam,
    UpdateEntityMetadataParam,
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


async def trigger_webhooks(library: Library, entity: Entity, request: Request):
    async with httpx.AsyncClient() as client:
        tasks = []
        for plugin in library.plugins:
            if plugin.webhook_url:
                location = str(
                    request.url_for(
                        "get_entity_by_id", entity_id=entity.id
                    )
                )
                task = client.post(
                    plugin.webhook_url,
                    json=entity.model_dump(mode="json"),
                    headers={"Location": location},
                    timeout=10.0,  # Adding a timeout of 10 seconds
                )
                tasks.append(task)

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for plugin, response in zip(library.plugins, responses):
            if isinstance(response, Exception):
                print(f"Error triggering webhook for plugin {plugin.id}: {response}")
            elif response.status_code >= 400:
                print(
                    f"Error triggering webhook for plugin {plugin.id}: {response.status_code} - {response.text}"
                )


@app.post("/libraries/{library_id}/entities", response_model=Entity)
async def new_entity(
    new_entity: NewEntityParam,
    library_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )

    entity = crud.create_entity(library_id, new_entity, db)
    await trigger_webhooks(library, entity, request)
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


@app.get("/entities/{entity_id}", response_model=Entity)
def get_entity_by_id(entity_id: int, db: Session = Depends(get_db)):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found"
        )
    return entity


@app.get("/libraries/{library_id}/entities/{entity_id}", response_model=Entity)
def get_entity_by_id_in_library(library_id: int, entity_id: int, db: Session = Depends(get_db)):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None or entity.library_id != library_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found"
        )
    return entity


@app.put("/entities/{entity_id}", response_model=Entity)
async def update_entity(
    entity_id: int,
    updated_entity: UpdateEntityParam,
    request: Request,
    db: Session = Depends(get_db),
    trigger_webhooks_flag: bool = False,
):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    entity = crud.update_entity(entity_id, updated_entity, db)
    if trigger_webhooks_flag:
        library = crud.get_library_by_id(entity.library_id, db)
        if library is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
            )
        await trigger_webhooks(library, entity, request)
    return entity


@app.patch("/entities/{entity_id}/tags", response_model=Entity)
@app.put("/entities/{entity_id}/tags", response_model=Entity)
def patch_entity_tags(
    entity_id: int,
    update_tags: UpdateEntityTagsParam,
    db: Session = Depends(get_db)
):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    # Use the CRUD function to update the tags
    entity = crud.update_entity_tags(entity_id, update_tags.tags, db)
    return entity


@app.patch("/entities/{entity_id}/metadata", response_model=Entity)
def patch_entity_metadata(
    entity_id: int,
    update_metadata: UpdateEntityMetadataParam,
    db: Session = Depends(get_db)
):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    # Use the CRUD function to update the metadata entries
    entity = crud.update_entity_metadata_entries(entity_id, update_metadata.metadata_entries, db)
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
