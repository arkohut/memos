from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import time
import random
from fastapi import Response, HTTPException
from datetime import datetime

app = FastAPI()
libraries = []


class Folder(BaseModel):
    path: str
    libraryId: int


class Library(BaseModel):
    id: int
    name: str
    description: str | None
    folders: List[Folder] = []
    lastScanAt: datetime | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "name": "Main Library",
                    "description": "A primary collection of various documents.",
                    "folders": [
                        {"path": "/documents/reports", "libraryId": 1},
                        {"path": "/documents/notes", "libraryId": 1},
                    ],
                    "lastScanAt": "2023-10-04T14:48:00",
                }
            ]
        }
    }


@app.get("/")
async def root():
    return "ok"


@app.get("/libraries", response_model=List[Library])
async def get_libraries():
    return libraries


@app.get("/libraries/{library_id}", response_model=Library)
async def get_library(library_id: int):
    for library in libraries:
        if library.id == library_id:
            return library
    raise HTTPException(status_code=404, detail="Library not found")


class LibraryParam(BaseModel):
    name: str
    description: str | None
    folders: List[str]


@app.post("/libraries", status_code=201)
async def create_library(library: LibraryParam):
    nextid = int(time.time()) + random.randint(1, 1000)
    new_library = Library(
        id=nextid,
        name=library.name,
        description=library.description,
        folders=[Folder(path=path, libraryId=nextid) for path in library.folders],
    )
    libraries.append(new_library)
    return new_library


@app.put("/libraries/{library_id}")
async def update_library(library_id: int, library: LibraryParam):
    for lib in libraries:
        if lib.id == library_id:
            lib.name = library.name
            lib.description = library.description
            lib.folders = [
                Folder(path=path, libraryId=library_id) for path in library.folders
            ]
            return Response(status_code=204)
    raise HTTPException(status_code=404, detail="Library not found")


@app.delete("/libraries/{library_id}", status_code=204)
async def delete_library(library_id: int):
    for lib in libraries:
        if lib.id == library_id:
            libraries.remove(lib)
            return Response(status_code=204)
    raise HTTPException(status_code=404, detail="Library not found")


@app.post("/libraries/{library_id}/scan_tasks", status_code=202)
async def request_scan_library(library_id):
    pass
