import os
import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import List, Annotated
from pathlib import Path
import asyncio
import logging  # Import logging module

import typesense

from .config import get_database_path, settings
from . import crud
from . import indexing
from .schemas import (
    Library,
    Folder,
    Entity,
    Plugin,
    NewLibraryParam,
    NewFoldersParam,
    NewEntityParam,
    UpdateEntityParam,
    NewPluginParam,
    NewLibraryPluginParam,
    UpdateEntityTagsParam,
    UpdateEntityMetadataParam,
    MetadataType,
    EntityIndexItem,
    MetadataIndexItem,
    EntitySearchResult,
)

# Import the logging configuration
from .logging_config import LOGGING_CONFIG

# Configure logging to include datetime
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

engine = create_engine(f"sqlite:///{get_database_path()}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize Typesense client
client = typesense.Client(
    {
        "nodes": [
            {
                "host": settings.typesense_host,
                "port": settings.typesense_port,
                "protocol": settings.typesense_protocol,
            }
        ],
        "api_key": settings.typesense_api_key,
        "connection_timeout_seconds": settings.typesense_connection_timeout_seconds,
    }
)

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


current_dir = os.path.dirname(__file__)

app.mount(
    "/_app", StaticFiles(directory=os.path.join(current_dir, "static/_app"), html=True)
)


@app.get("/favicon.png", response_class=FileResponse)
async def favicon_png():
    return FileResponse(os.path.join(current_dir, "static/favicon.png"))


@app.get("/favicon.ico", response_class=FileResponse)
async def favicon_ico():
    return FileResponse(os.path.join(current_dir, "static/favicon.png"))


@app.get("/")
async def serve_spa():
    return FileResponse(os.path.join(current_dir, "static/app.html"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/libraries", response_model=Library, tags=["library"])
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


@app.get("/libraries", response_model=List[Library], tags=["library"])
def list_libraries(db: Session = Depends(get_db)):
    libraries = crud.get_libraries(db)
    return libraries


@app.get("/libraries/{library_id}", response_model=Library, tags=["library"])
def get_library_by_id(library_id: int, db: Session = Depends(get_db)):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )
    return library


@app.post("/libraries/{library_id}/folders", response_model=Library, tags=["library"])
def new_folders(
    library_id: int,
    folders: NewFoldersParam,
    db: Session = Depends(get_db),
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )

    existing_folders = [folder.path for folder in library.folders]
    if any(str(folder) in existing_folders for folder in folders.folders):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder already exists in the library",
        )

    return crud.add_folders(library_id=library.id, folders=folders, db=db)


async def trigger_webhooks(
    library: Library, entity: Entity, request: Request, plugins: List[int] = None
):
    async with httpx.AsyncClient() as client:
        tasks = []
        for plugin in library.plugins:
            if plugins is None or plugin.id in plugins:
                if plugin.webhook_url:
                    location = str(
                        request.url_for("get_entity_by_id", entity_id=entity.id)
                    )
                    task = client.post(
                        plugin.webhook_url,
                        json=entity.model_dump(mode="json"),
                        headers={"Location": location},
                        timeout=60.0,
                    )
                    tasks.append(task)

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for plugin, response in zip(library.plugins, responses):
            if plugins is None or plugin.id in plugins:
                if isinstance(response, Exception):
                    print(
                        f"Error triggering webhook for plugin {plugin.id}: {response}"
                    )
                elif response.status_code >= 400:
                    print(
                        f"Error triggering webhook for plugin {plugin.id}: {response.status_code} - {response.text}"
                    )


@app.post("/libraries/{library_id}/entities", response_model=Entity, tags=["entity"])
async def new_entity(
    new_entity: NewEntityParam,
    library_id: int,
    request: Request,
    db: Session = Depends(get_db),
    plugins: Annotated[List[int] | None, Query()] = None,
):
    library = crud.get_library_by_id(library_id, db)
    if library is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
        )

    entity = crud.create_entity(library_id, new_entity, db)
    await trigger_webhooks(library, entity, request, plugins)
    return entity


@app.get(
    "/libraries/{library_id}/folders/{folder_id}/entities",
    response_model=List[Entity],
    tags=["entity"],
)
def list_entities_in_folder(
    library_id: int,
    folder_id: int,
    limit: Annotated[int, Query(ge=1, le=400)] = 10,
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

    entities, total_count = crud.get_entities_of_folder(
        library_id, folder_id, db, limit, offset
    )
    return JSONResponse(
        content=jsonable_encoder(entities), headers={"X-Total-Count": str(total_count)}
    )


@app.get(
    "/libraries/{library_id}/entities/by-filepath",
    response_model=Entity,
    tags=["entity"],
)
def get_entity_by_filepath(
    library_id: int, filepath: str, db: Session = Depends(get_db)
):
    entity = crud.get_entity_by_filepath(filepath, db)
    if entity is None or entity.library_id != library_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found"
        )
    return entity


@app.post(
    "/libraries/{library_id}/entities/by-filepaths",
    response_model=List[Entity],
    tags=["entity"],
)
def get_entities_by_filepaths(
    library_id: int, filepaths: List[str], db: Session = Depends(get_db)
):
    entities = crud.get_entities_by_filepaths(filepaths, db)
    return [entity for entity in entities if entity.library_id == library_id]


@app.get("/entities/{entity_id}", response_model=Entity, tags=["entity"])
def get_entity_by_id(entity_id: int, db: Session = Depends(get_db)):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found"
        )
    return entity


@app.get(
    "/libraries/{library_id}/entities/{entity_id}",
    response_model=Entity,
    tags=["entity"],
)
def get_entity_by_id_in_library(
    library_id: int, entity_id: int, db: Session = Depends(get_db)
):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None or entity.library_id != library_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found"
        )
    return entity


@app.put("/entities/{entity_id}", response_model=Entity, tags=["entity"])
async def update_entity(
    entity_id: int,
    request: Request,
    updated_entity: UpdateEntityParam = None,
    db: Session = Depends(get_db),
    trigger_webhooks_flag: bool = False,
    plugins: Annotated[List[int] | None, Query()] = None,
):
    entity = crud.find_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    if updated_entity:
        entity = crud.update_entity(entity_id, updated_entity, db)

    if trigger_webhooks_flag:
        library = crud.get_library_by_id(entity.library_id, db)
        if library is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
            )
        await trigger_webhooks(library, entity, request, plugins)
    return entity


@app.post(
    "/entities/{entity_id}/index",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["entity"],
)
async def sync_entity_to_typesense(entity_id: int, db: Session = Depends(get_db)):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    try:
        indexing.upsert(client, entity)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    return None


@app.post(
    "/entities/batch-index",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["entity"],
)
async def batch_sync_entities_to_typesense(
    entity_ids: List[int], db: Session = Depends(get_db)
):
    entities = crud.find_entities_by_ids(entity_ids, db)
    if not entities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No entities found",
        )

    try:
        indexing.bulk_upsert(client, entities)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    return None


@app.get(
    "/entities/{entity_id}/index",
    response_model=EntitySearchResult,
    tags=["entity"],
)
async def get_entity_index(entity_id: int) -> EntityIndexItem:
    try:
        entity_index_item = indexing.fetch_entity_by_id(client, entity_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return entity_index_item


@app.delete(
    "/entities/{entity_id}/index",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["entity"],
)
async def remove_entity_from_typesense(entity_id: int, db: Session = Depends(get_db)):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    try:
        indexing.remove_entity_by_id(client, entity_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    return None


@app.get(
    "/libraries/{library_id}/folders/{folder_id}/index",
    response_model=List[EntityIndexItem],
    tags=["entity"],
)
def list_entitiy_indices_in_folder(
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

    return indexing.list_all_entities(client, library_id, folder_id, limit, offset)


@app.get("/search", response_model=List[EntitySearchResult], tags=["search"])
async def search_entities(
    q: str,
    library_ids: str = Query(None, description="Comma-separated list of library IDs"),
    folder_ids: str = Query(None, description="Comma-separated list of folder IDs"),
    limit: Annotated[int, Query(ge=1, le=200)] = 48,
    offset: int = 0,
    start: int = None,
    end: int = None,
    db: Session = Depends(get_db),
):
    library_ids = [int(id) for id in library_ids.split(",") if id] if library_ids else None
    folder_ids = [int(id) for id in folder_ids.split(",") if id] if folder_ids else None
    try:
        return indexing.search_entities(
            client, q, library_ids, folder_ids, limit, offset, start, end
        )
    except Exception as e:
        print(f"Error searching entities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@app.put("/entities/{entity_id}/tags", response_model=Entity, tags=["entity"])
def replace_entity_tags(
    entity_id: int, update_tags: UpdateEntityTagsParam, db: Session = Depends(get_db)
):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    return crud.update_entity_tags(entity_id, update_tags.tags, db)


@app.patch("/entities/{entity_id}/tags", response_model=Entity, tags=["entity"])
def patch_entity_tags(
    entity_id: int, update_tags: UpdateEntityTagsParam, db: Session = Depends(get_db)
):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    return crud.add_new_tags(entity_id, update_tags.tags, db)


@app.patch("/entities/{entity_id}/metadata", response_model=Entity, tags=["entity"])
def patch_entity_metadata(
    entity_id: int,
    update_metadata: UpdateEntityMetadataParam,
    db: Session = Depends(get_db),
):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found",
        )

    # Use the CRUD function to update the metadata entries
    entity = crud.update_entity_metadata_entries(
        entity_id, update_metadata.metadata_entries, db
    )
    return entity


@app.delete(
    "/libraries/{library_id}/entities/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["entity"],
)
def remove_entity(library_id: int, entity_id: int, db: Session = Depends(get_db)):
    entity = crud.get_entity_by_id(entity_id, db)
    if entity is None or entity.library_id != library_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity not found in the specified library",
        )

    crud.remove_entity(entity_id, db)


@app.post("/plugins", response_model=Plugin, tags=["plugin"])
def new_plugin(new_plugin: NewPluginParam, db: Session = Depends(get_db)):
    existing_plugin = crud.get_plugin_by_name(new_plugin.name, db)
    if existing_plugin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plugin with this name already exists",
        )
    plugin = crud.create_plugin(new_plugin, db)
    return plugin


@app.get("/plugins", response_model=List[Plugin], tags=["plugin"])
def list_plugins(db: Session = Depends(get_db)):
    plugins = crud.get_plugins(db)
    return plugins


@app.post(
    "/libraries/{library_id}/plugins",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["plugin"],
)
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


@app.get("/files/{file_path:path}", tags=["files"])
async def get_file(file_path: str):
    full_path = Path("/") / file_path.strip("/")
    # Check if the file exists and is a file
    if full_path.is_file():
        return FileResponse(full_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")


def run_server():
    print("Database path:", get_database_path())
    print(
        f"Typesense connection info: Host: {settings.typesense_host}, Port: {settings.typesense_port}, Protocol: {settings.typesense_protocol}"
    )
    uvicorn.run(
        "memos.server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_config=LOGGING_CONFIG,
    )
