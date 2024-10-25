import math
import typer
import httpx
import asyncio
import logging
import threading

from tqdm import tqdm
from pathlib import Path
from tabulate import tabulate
from memos.config import settings
from magika import Magika
from datetime import datetime
from enum import Enum
from typing import List, Tuple
from functools import lru_cache

import re
import os
import time
import psutil

from collections import defaultdict, deque
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from concurrent.futures import ThreadPoolExecutor

from memos.models import recreate_fts_and_vec_tables
from memos.utils import get_image_metadata
from memos.schemas import MetadataSource
from memos.logging_config import LOGGING_CONFIG
import logging.config


logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

lib_app = typer.Typer()

file_detector = Magika()

IS_THUMBNAIL = "is_thumbnail"

BASE_URL = settings.server_endpoint

include_files = [".jpg", ".jpeg", ".png", ".webp"]


class FileStatus(Enum):
    UPDATED = "updated"
    ADDED = "added"


def format_timestamp(timestamp):
    if isinstance(timestamp, str):
        return timestamp
    return datetime.fromtimestamp(timestamp).replace(tzinfo=None).isoformat()


def get_file_type(file_path):
    file_result = file_detector.identify_path(file_path)
    return file_result.output.ct_label, file_result.output.group


def display_libraries(libraries):
    table = []
    for library in libraries:
        table.append(
            [
                library["id"],
                library["name"],
                "\n".join(
                    f"{folder['id']}: {folder['path']}" for folder in library["folders"]
                ),
                "\n".join(
                    f"{plugin['id']}: {plugin['name']} {plugin['webhook_url']}"
                    for plugin in library["plugins"]
                ),
            ]
        )

    print(
        tabulate(table, headers=["ID", "Name", "Folders", "Plugins"], tablefmt="plain")
    )


@lib_app.command("ls")
def ls():
    response = httpx.get(f"{BASE_URL}/libraries")
    libraries = response.json()
    display_libraries(libraries)


@lib_app.command("create")
def add(name: str, folders: List[str]):
    absolute_folders = []
    for folder in folders:
        folder_path = Path(folder).resolve()
        absolute_folders.append(
            {
                "path": str(folder_path),
                "last_modified_at": datetime.fromtimestamp(
                    folder_path.stat().st_mtime
                ).isoformat(),
            }
        )

    response = httpx.post(
        f"{BASE_URL}/libraries",
        json={"name": name, "folders": absolute_folders},
    )
    if 200 <= response.status_code < 300:
        print("Library created successfully")
    else:
        print(f"Failed to create library: {response.status_code} - {response.text}")


@lib_app.command("add-folder")
def add_folder(library_id: int, folders: List[str]):
    absolute_folders = []
    for folder in folders:
        folder_path = Path(folder).resolve()
        absolute_folders.append(
            {
                "path": str(folder_path),
                "last_modified_at": datetime.fromtimestamp(
                    folder_path.stat().st_mtime
                ).isoformat(),
            }
        )

    response = httpx.post(
        f"{BASE_URL}/libraries/{library_id}/folders",
        json={"folders": absolute_folders},
    )
    if 200 <= response.status_code < 300:
        print("Folders added successfully")
        library = response.json()
        display_libraries([library])
    else:
        print(f"Failed to add folders: {response.status_code} - {response.text}")


@lib_app.command("show")
def show(library_id: int):
    response = httpx.get(f"{BASE_URL}/libraries/{library_id}")
    if response.status_code == 200:
        library = response.json()
        display_libraries([library])
    else:
        print(f"Failed to retrieve library: {response.status_code} - {response.text}")


def is_temp_file(filename):
    return (
        filename.startswith(".")
        or filename.startswith("tmp")
        or filename.startswith("temp")
    )


async def loop_files(library_id, folder, folder_path, force, plugins):
    updated_file_count = 0
    added_file_count = 0
    scanned_files = set()
    semaphore = asyncio.Semaphore(settings.batchsize)
    async with httpx.AsyncClient(timeout=60) as client:
        tasks = []
        for root, _, files in os.walk(folder_path):
            with tqdm(total=len(files), desc=f"Scanning {root}", leave=True) as pbar:
                candidate_files = []
                for file in files:
                    file_path = Path(root) / file
                    absolute_file_path = file_path.resolve()  # Get absolute path
                    relative_path = absolute_file_path.relative_to(folder_path)

                    # Check if the file extension is in the include_files list and not a temp file
                    if file_path.suffix.lower() in include_files and not is_temp_file(
                        file
                    ):
                        scanned_files.add(str(absolute_file_path))
                        candidate_files.append(str(absolute_file_path))

                batching = 200
                for i in range(0, len(candidate_files), batching):
                    batch = candidate_files[i : i + batching]

                    # Get batch of entities
                    get_response = await client.post(
                        f"{BASE_URL}/libraries/{library_id}/entities/by-filepaths",
                        json=batch,
                    )

                    if get_response.status_code == 200:
                        existing_entities = get_response.json()
                    else:
                        print(
                            f"Failed to get entities: {get_response.status_code} - {get_response.text}"
                        )
                        continue

                    existing_entities_dict = {
                        entity["filepath"]: entity for entity in existing_entities
                    }

                    for file_path in batch:
                        absolute_file_path = Path(file_path).resolve()
                        file_stat = absolute_file_path.stat()
                        file_type, file_type_group = get_file_type(absolute_file_path)

                        new_entity = {
                            "filename": absolute_file_path.name,
                            "filepath": str(absolute_file_path),
                            "size": file_stat.st_size,
                            "file_created_at": format_timestamp(file_stat.st_ctime),
                            "file_last_modified_at": format_timestamp(
                                file_stat.st_mtime
                            ),
                            "file_type": file_type,
                            "file_type_group": file_type_group,
                            "folder_id": folder["id"],
                        }

                        is_thumbnail = False

                        if file_type_group == "image":
                            metadata = get_image_metadata(absolute_file_path)
                            if metadata:
                                if (
                                    "active_window" in metadata
                                    and "active_app" not in metadata
                                ):
                                    metadata["active_app"] = metadata[
                                        "active_window"
                                    ].split(" - ")[0]
                                new_entity["metadata_entries"] = [
                                    {
                                        "key": key,
                                        "value": str(value),
                                        "source": MetadataSource.SYSTEM_GENERATED.value,
                                        "data_type": (
                                            "number"
                                            if isinstance(value, (int, float))
                                            else "text"
                                        ),
                                    }
                                    for key, value in metadata.items()
                                    if key != IS_THUMBNAIL
                                ]
                                if "active_app" in metadata:
                                    new_entity.setdefault("tags", []).append(
                                        metadata["active_app"]
                                    )
                                is_thumbnail = metadata.get(IS_THUMBNAIL, False)

                        existing_entity = existing_entities_dict.get(
                            str(absolute_file_path)
                        )
                        if existing_entity:
                            existing_created_at = format_timestamp(
                                existing_entity["file_created_at"]
                            )
                            new_created_at = format_timestamp(
                                new_entity["file_created_at"]
                            )
                            existing_modified_at = format_timestamp(
                                existing_entity["file_last_modified_at"]
                            )
                            new_modified_at = format_timestamp(
                                new_entity["file_last_modified_at"]
                            )

                            # Ignore file changes for thumbnails
                            if is_thumbnail:
                                new_entity["file_created_at"] = existing_entity[
                                    "file_created_at"
                                ]
                                new_entity["file_last_modified_at"] = existing_entity[
                                    "file_last_modified_at"
                                ]
                                new_entity["file_type"] = existing_entity["file_type"]
                                new_entity["file_type_group"] = existing_entity[
                                    "file_type_group"
                                ]
                                new_entity["size"] = existing_entity["size"]

                            # Merge existing metadata with new metadata
                            if new_entity.get("metadata_entries"):
                                new_metadata_keys = {
                                    entry["key"]
                                    for entry in new_entity["metadata_entries"]
                                }
                                for existing_entry in existing_entity[
                                    "metadata_entries"
                                ]:
                                    if existing_entry["key"] not in new_metadata_keys:
                                        new_entity["metadata_entries"].append(
                                            existing_entry
                                        )

                            if (
                                force
                                or existing_created_at != new_created_at
                                or existing_modified_at != new_modified_at
                            ):
                                tasks.append(
                                    update_entity(
                                        client,
                                        semaphore,
                                        plugins,
                                        new_entity,
                                        existing_entity,
                                    )
                                )
                        elif not is_thumbnail:  # Ignore thumbnails
                            tasks.append(
                                add_entity(
                                    client, semaphore, library_id, plugins, new_entity
                                )
                            )
                    pbar.update(len(batch))
                    pbar.set_postfix({"Candidates": len(tasks)}, refresh=True)

        # Process all tasks after they've been created
        for future in tqdm(
            asyncio.as_completed(tasks),
            desc=f"Processing {folder_path}",
            total=len(tasks),
            leave=True,
        ):
            file_path, file_status, succeeded, response = await future
            if file_status == FileStatus.ADDED:
                if succeeded:
                    added_file_count += 1
                    tqdm.write(f"Added file to library: {file_path}")
                else:
                    error_message = "Failed to add file"
                    if hasattr(response, "status_code"):
                        error_message += f": {response.status_code}"
                    if hasattr(response, "text"):
                        error_message += f" - {response.text}"
                    else:
                        error_message += " - Unknown error occurred"
                    tqdm.write(error_message)
            elif file_status == FileStatus.UPDATED:
                if succeeded:
                    updated_file_count += 1
                    tqdm.write(f"Updated file in library: {file_path}")
                else:
                    error_message = "Failed to update file"
                    if hasattr(response, "status_code"):
                        error_message += f": {response.status_code}"
                    elif hasattr(response, "text"):
                        error_message += f" - {response.text}"
                    else:
                        error_message += f" - Unknown error occurred"
                    tqdm.write(error_message)

        return added_file_count, updated_file_count, scanned_files


@lib_app.command("scan")
def scan(
    library_id: int,
    path: str = typer.Argument(None, help="Path to scan within the library"),
    force: bool = False,
    plugins: List[int] = typer.Option(None, "--plugin", "-p"),
    folders: List[int] = typer.Option(None, "--folder", "-f"),
):
    # Check if both path and folders are provided
    if path and folders:
        print("Error: You cannot specify both a path and folders at the same time.")
        return

    response = httpx.get(f"{BASE_URL}/libraries/{library_id}")
    if response.status_code != 200:
        print(f"Failed to retrieve library: {response.status_code} - {response.text}")
        return

    library = response.json()
    total_files_added = 0
    total_files_updated = 0
    total_files_deleted = 0

    # Filter folders if the folders parameter is provided
    if folders:
        library_folders = [
            folder for folder in library["folders"] if folder["id"] in folders
        ]
    else:
        library_folders = library["folders"]

    # Check if a specific path is provided
    if path:
        path = Path(path).expanduser().resolve()
        # Check if the path is a folder or a subdirectory of a library folder
        folder = next(
            (
                folder
                for folder in library_folders
                if path.is_relative_to(Path(folder["path"]).resolve())
            ),
            None,
        )
        if not folder:
            print(f"Error: The path {path} is not part of any folder in the library.")
            return
        # Only scan the specified path
        library_folders = [{"id": folder["id"], "path": str(path)}]

    for folder in library_folders:
        folder_path = Path(folder["path"])
        if not folder_path.exists() or not folder_path.is_dir():
            tqdm.write(f"Folder does not exist or is not a directory: {folder_path}")
            continue

        added_file_count, updated_file_count, scanned_files = asyncio.run(
            loop_files(library_id, folder, folder_path, force, plugins)
        )
        total_files_added += added_file_count
        total_files_updated += updated_file_count

        # Check for deleted files
        limit = 100
        offset = 0
        total_entities = 0  # We'll update this after the first request
        with tqdm(
            total=total_entities, desc="Checking for deleted files", leave=True
        ) as pbar2:
            while True:
                existing_files_response = httpx.get(
                    f"{BASE_URL}/libraries/{library_id}/folders/{folder['id']}/entities",
                    params={"limit": limit, "offset": offset},
                    timeout=60,
                )
                if existing_files_response.status_code != 200:
                    pbar2.write(
                        f"Failed to retrieve existing files: {existing_files_response.status_code} - {existing_files_response.text}"
                    )
                    break

                existing_files = existing_files_response.json()
                if not existing_files:
                    break

                # Update total if this is the first request
                if offset == 0:
                    total_entities = int(
                        existing_files_response.headers.get(
                            "X-Total-Count", total_entities
                        )
                    )
                    pbar2.total = total_entities
                    pbar2.refresh()

                for existing_file in existing_files:
                    if (
                        Path(existing_file["filepath"]).is_relative_to(folder_path)
                        and existing_file["filepath"] not in scanned_files
                    ):
                        # File has been deleted
                        delete_response = httpx.delete(
                            f"{BASE_URL}/libraries/{library_id}/entities/{existing_file['id']}"
                        )
                        if 200 <= delete_response.status_code < 300:
                            pbar2.write(
                                f"Deleted file from library: {existing_file['filepath']}"
                            )
                            total_files_deleted += 1
                        else:
                            pbar2.write(
                                f"Failed to delete file: {delete_response.status_code} - {delete_response.text}"
                            )
                    pbar2.update(1)

                offset += limit

    print(f"Total files added: {total_files_added}")
    print(f"Total files updated: {total_files_updated}")
    print(f"Total files deleted: {total_files_deleted}")


async def add_entity(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    library_id,
    plugins,
    new_entity,
) -> Tuple[FileStatus, bool, httpx.Response]:
    async with semaphore:
        MAX_RETRIES = 3
        RETRY_DELAY = 2.0
        for attempt in range(MAX_RETRIES):
            try:
                post_response = await client.post(
                    f"{BASE_URL}/libraries/{library_id}/entities",
                    json=new_entity,
                    params={"plugins": plugins} if plugins else {},
                    timeout=60,
                )
                if 200 <= post_response.status_code < 300:
                    return new_entity["filepath"], FileStatus.ADDED, True, post_response
                else:
                    return (
                        new_entity["filepath"],
                        FileStatus.ADDED,
                        False,
                        post_response,
                    )
            except Exception as e:
                logging.error(
                    f"Error while adding entity (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    return new_entity["filepath"], FileStatus.ADDED, False, None


async def update_entity(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    plugins,
    new_entity,
    existing_entity,
) -> Tuple[FileStatus, bool, httpx.Response]:
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                update_response = await client.put(
                    f"{BASE_URL}/entities/{existing_entity['id']}",
                    json=new_entity,
                    params={
                        "trigger_webhooks_flag": "true",
                        **({"plugins": plugins} if plugins else {}),
                    },
                    timeout=60,
                )
                if 200 <= update_response.status_code < 300:
                    return (
                        new_entity["filepath"],
                        FileStatus.UPDATED,
                        True,
                        update_response,
                    )
                else:
                    return (
                        new_entity["filepath"],
                        FileStatus.UPDATED,
                        False,
                        update_response,
                    )
            except Exception as e:
                logging.error(
                    f"Error while updating entity {existing_entity['id']} (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    return new_entity["filepath"], FileStatus.UPDATED, False, None


@lib_app.command("reindex")
def reindex(
    library_id: int,
    folders: List[int] = typer.Option(None, "--folder", "-f"),
    force: bool = typer.Option(
        False, "--force", help="Force recreate FTS and vector tables before reindexing"
    ),
):
    print(f"Reindexing library {library_id}")

    # Get the library
    response = httpx.get(f"{BASE_URL}/libraries/{library_id}")
    if response.status_code != 200:
        print(f"Failed to get library: {response.status_code} - {response.text}")
        return

    library = response.json()
    scanned_entities = set()

    # Filter folders if the folders parameter is provided
    if folders:
        library_folders = [
            folder for folder in library["folders"] if folder["id"] in folders
        ]
    else:
        library_folders = library["folders"]

    if force:
        print("Force flag is set. Recreating FTS and vector tables...")
        recreate_fts_and_vec_tables()
        print("FTS and vector tables have been recreated.")

    with httpx.Client(timeout=60) as client:
        total_entities = 0

        # Get total entity count for all folders
        for folder in library_folders:
            response = client.get(
                f"{BASE_URL}/libraries/{library_id}/folders/{folder['id']}/entities",
                params={"limit": 1, "offset": 0},
            )
            if response.status_code == 200:
                total_entities += int(response.headers.get("X-Total-Count", 0))
            else:
                print(
                    f"Failed to get entity count for folder {folder['id']}: {response.status_code} - {response.text}"
                )

        # Now process entities with a progress bar
        with tqdm(total=total_entities, desc="Reindexing entities") as pbar:
            for folder in library_folders:
                print(f"Processing folder: {folder['id']}")

                # List all entities in the folder
                limit = 200
                offset = 0
                while True:
                    entities_response = client.get(
                        f"{BASE_URL}/libraries/{library_id}/folders/{folder['id']}/entities",
                        params={"limit": limit, "offset": offset},
                    )
                    if entities_response.status_code != 200:
                        print(
                            f"Failed to get entities: {entities_response.status_code} - {entities_response.text}"
                        )
                        break

                    entities = entities_response.json()
                    if not entities:
                        break

                    # Update last_scan_at for each entity
                    for entity in entities:
                        if entity["id"] in scanned_entities:
                            continue

                        update_response = client.post(
                            f"{BASE_URL}/entities/{entity['id']}/last-scan-at"
                        )
                        if update_response.status_code != 204:
                            print(
                                f"Failed to update last_scan_at for entity {entity['id']}: {update_response.status_code} - {update_response.text}"
                            )
                        else:
                            scanned_entities.add(entity["id"])

                        pbar.update(1)

                    offset += limit

    print(f"Reindexing completed for library {library_id}")


async def check_and_index_entity(client, entity_id, entity_last_scan_at):
    try:
        index_response = await client.get(f"{BASE_URL}/entities/{entity_id}/index")
        if index_response.status_code == 200:
            index_data = index_response.json()
            if index_data["last_scan_at"] is None:
                return entity_last_scan_at is not None
            index_last_scan_at = datetime.fromtimestamp(index_data["last_scan_at"])
            entity_last_scan_at = datetime.fromisoformat(entity_last_scan_at)

            if index_last_scan_at >= entity_last_scan_at:
                return False  # Index is up to date, no need to update
        return True  # Index doesn't exist or needs update
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return True  # Index doesn't exist, need to create
        raise  # Re-raise other HTTP errors


async def index_batch(client, entity_ids):
    index_response = await client.post(
        f"{BASE_URL}/entities/batch-index",
        json=entity_ids,
        timeout=60,
    )
    return index_response


@lib_app.command("typesense-index")
def typesense_index(
    library_id: int,
    folders: List[int] = typer.Option(None, "--folder", "-f"),
    force: bool = typer.Option(False, "--force", help="Force update all indexes"),
    batchsize: int = typer.Option(
        4, "--batchsize", "-bs", help="Number of entities to index in a batch"
    ),
):
    print(f"Indexing library {library_id}")

    # Get the library
    response = httpx.get(f"{BASE_URL}/libraries/{library_id}")
    if response.status_code != 200:
        print(f"Failed to get library: {response.status_code} - {response.text}")
        return

    library = response.json()
    scanned_entities = set()

    # Filter folders if the folders parameter is provided
    if folders:
        library_folders = [
            folder for folder in library["folders"] if folder["id"] in folders
        ]
    else:
        library_folders = library["folders"]

    async def process_folders():
        async with httpx.AsyncClient(timeout=60) as client:
            # Iterate through folders
            for folder in library_folders:
                tqdm.write(f"Processing folder: {folder['id']}")

                # List all entities in the folder
                limit = 200
                offset = 0
                total_entities = 0  # We'll update this after the first request
                with tqdm(
                    total=total_entities, desc="Indexing entities", leave=True
                ) as pbar:
                    while True:
                        entities_response = await client.get(
                            f"{BASE_URL}/libraries/{library_id}/folders/{folder['id']}/entities",
                            params={"limit": limit, "offset": offset},
                        )
                        if entities_response.status_code != 200:
                            pbar.write(
                                f"Failed to get entities: {entities_response.status_code} - {entities_response.text}"
                            )
                            break

                        entities = entities_response.json()
                        if not entities:
                            break

                        # Update total if this is the first request
                        if offset == 0:
                            total_entities = int(
                                entities_response.headers.get(
                                    "X-Total-Count", total_entities
                                )
                            )
                            pbar.total = total_entities
                            pbar.refresh()

                        # Index each entity
                        for i in range(0, len(entities), batchsize):
                            batch = entities[i : i + batchsize]
                            to_index = []

                            for entity in batch:
                                needs_indexing = force or await check_and_index_entity(
                                    client, entity["id"], entity["last_scan_at"]
                                )
                                if needs_indexing:
                                    to_index.append(entity["id"])

                            if to_index:
                                index_response = await index_batch(client, to_index)
                                if index_response.status_code == 204:
                                    pbar.write(
                                        f"Indexed batch of {len(to_index)} entities"
                                    )
                                else:
                                    pbar.write(
                                        f"Failed to index batch: {index_response.status_code} - {index_response.text}"
                                    )

                            scanned_entities.update(
                                str(entity["id"]) for entity in batch
                            )
                            pbar.update(len(batch))

                        offset += limit

                # List all indexed entities in the folder
                offset = 0
                print(f"Starting cleanup process for folder {folder['id']}")
                while True:
                    index_response = await client.get(
                        f"{BASE_URL}/libraries/{library_id}/folders/{folder['id']}/index",
                        params={"limit": 200, "offset": offset},
                    )
                    if index_response.status_code != 200:
                        tqdm.write(
                            f"Failed to get indexed entities: {index_response.status_code} - {index_response.text}"
                        )
                        break

                    indexed_entities = index_response.json()
                    if not indexed_entities:
                        print("No more indexed entities to process")
                        break

                    # Delete indexes for entities not in scanned_entities
                    for indexed_entity in tqdm(
                        indexed_entities, desc="Cleaning up indexes", leave=False
                    ):
                        if indexed_entity["id"] not in scanned_entities:
                            tqdm.write(
                                f"Entity {indexed_entity['id']} not in scanned entities, deleting index"
                            )
                            delete_response = await client.delete(
                                f"{BASE_URL}/entities/{indexed_entity['id']}/index"
                            )
                            if delete_response.status_code == 204:
                                tqdm.write(
                                    f"Deleted index for entity: {indexed_entity['id']}"
                                )
                            else:
                                tqdm.write(
                                    f"Failed to delete index for entity {indexed_entity['id']}: {delete_response.status_code} - {delete_response.text}"
                                )

                    offset += 200

                print(f"Finished cleanup process for folder {folder['id']}")

    asyncio.run(process_folders())
    print("Indexing completed")


@lib_app.command("sync")
def sync(
    library_id: int,
    filepath: str,
    force: bool = typer.Option(
        False, "--force", "-f", help="Force update the file even if it hasn't changed"
    ),
):
    """
    Sync a specific file with the library.
    """
    # 1. Get library by id and check if it exists
    response = httpx.get(f"{BASE_URL}/libraries/{library_id}")
    if response.status_code != 200:
        typer.echo(f"Error: Library with id {library_id} not found.")
        raise typer.Exit(code=1)

    library = response.json()

    # Convert filepath to absolute path
    file_path = Path(filepath).resolve()

    if not file_path.is_file():
        typer.echo(f"Error: File {file_path} does not exist.")
        raise typer.Exit(code=1)

    # 2. Check if the file exists in the library
    response = httpx.get(
        f"{BASE_URL}/libraries/{library_id}/entities/by-filepath",
        params={"filepath": str(file_path)},
    )

    file_stat = file_path.stat()
    file_type, file_type_group = get_file_type(file_path)

    new_entity = {
        "filename": file_path.name,
        "filepath": str(file_path),
        "size": file_stat.st_size,
        "file_created_at": format_timestamp(file_stat.st_ctime),
        "file_last_modified_at": format_timestamp(file_stat.st_mtime),
        "file_type": file_type,
        "file_type_group": file_type_group,
    }

    # Handle metadata
    is_thumbnail = False
    if file_type_group == "image":
        metadata = get_image_metadata(file_path)
        if metadata:
            if "active_window" in metadata and "active_app" not in metadata:
                metadata["active_app"] = metadata["active_window"].split(" - ")[0]
            new_entity["metadata_entries"] = [
                {
                    "key": key,
                    "value": str(value),
                    "source": MetadataSource.SYSTEM_GENERATED.value,
                    "data_type": (
                        "number" if isinstance(value, (int, float)) else "text"
                    ),
                }
                for key, value in metadata.items()
                if key != IS_THUMBNAIL
            ]
            if "active_app" in metadata:
                new_entity.setdefault("tags", []).append(metadata["active_app"])
            is_thumbnail = metadata.get(IS_THUMBNAIL, False)

    if response.status_code == 200:
        # File exists, update it
        existing_entity = response.json()
        new_entity["folder_id"] = existing_entity["folder_id"]

        if is_thumbnail:
            new_entity["file_created_at"] = existing_entity["file_created_at"]
            new_entity["file_last_modified_at"] = existing_entity[
                "file_last_modified_at"
            ]
            new_entity["file_type"] = existing_entity["file_type"]
            new_entity["file_type_group"] = existing_entity["file_type_group"]
            new_entity["size"] = existing_entity["size"]

        # Merge existing metadata with new metadata
        if new_entity.get("metadata_entries"):
            new_metadata_keys = {
                entry["key"] for entry in new_entity["metadata_entries"]
            }
            for existing_entry in existing_entity["metadata_entries"]:
                if existing_entry["key"] not in new_metadata_keys:
                    new_entity["metadata_entries"].append(existing_entry)

        if force or (
            existing_entity["file_last_modified_at"]
            != new_entity["file_last_modified_at"]
            or existing_entity["size"] != new_entity["size"]
        ):
            update_response = httpx.put(
                f"{BASE_URL}/entities/{existing_entity['id']}",
                json=new_entity,
                params={"trigger_webhooks_flag": "true"},
                timeout=60,
            )
            if update_response.status_code == 200:
                typer.echo(f"Updated file: {file_path}")
            else:
                typer.echo(
                    f"Error updating file: {update_response.status_code} - {update_response.text}"
                )
        else:
            typer.echo(f"File {file_path} is up to date. No changes made.")

    else:
        # 3. File doesn't exist, check if it belongs to a folder in the library
        folder = next(
            (
                folder
                for folder in library["folders"]
                if str(file_path).startswith(folder["path"])
            ),
            None,
        )

        if folder:
            # Create new entity
            new_entity["folder_id"] = folder["id"]

            create_response = httpx.post(
                f"{BASE_URL}/libraries/{library_id}/entities",
                json=new_entity,
                timeout=60,
            )

            if create_response.status_code == 200:
                typer.echo(f"Created new entity for file: {file_path}")
            else:
                typer.echo(
                    f"Error creating entity: {create_response.status_code} - {create_response.text}"
                )

        else:
            # 4. File doesn't belong to any folder in the library
            typer.echo(
                f"Error: File {file_path} does not belong to any folder in the library."
            )
            raise typer.Exit(code=1)


@lru_cache(maxsize=1)
def is_on_battery():
    try:
        battery = psutil.sensors_battery()
        return battery is not None and not battery.power_plugged
    except:
        return False  # If unable to detect battery status, assume not on battery


# Modify the LibraryFileHandler class
class LibraryFileHandler(FileSystemEventHandler):
    def __init__(
        self,
        library_id,
        include_files,
        max_workers=2,
        sparsity_factor=3,
        window_size=10,
    ):
        self.library_id = library_id
        self.include_files = include_files
        self.inode_pattern = re.compile(r"\._.+")
        self.pending_files = defaultdict(lambda: {"timestamp": 0, "last_size": 0})
        self.buffer_time = 2
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = threading.Lock()

        self.sparsity_window = 12
        self.sparsity_factor = sparsity_factor
        self.window_size = window_size

        self.pending_times = deque(maxlen=window_size)
        self.sync_times = deque(maxlen=window_size)

        self.file_count = 0
        self.file_submitted = 0
        self.file_synced = 0
        self.file_skipped = 0
        self.logger = logger

        self.base_sparsity_window = self.sparsity_window
        self.last_battery_check = 0
        self.battery_check_interval = 60  # Check battery status every 60 seconds

    def handle_event(self, event):
        if not event.is_directory and self.is_valid_file(event.src_path):
            current_time = time.time()
            with self.lock:
                file_info = self.pending_files[event.src_path]

                if current_time - file_info["timestamp"] > self.buffer_time:
                    file_info["timestamp"] = current_time
                    self.pending_times.append(current_time)

                file_info["last_size"] = os.path.getsize(event.src_path)

            return True
        return False

    def process_pending_files(self):
        current_time = time.time()
        files_to_process = []
        processed_in_current_loop = 0
        with self.lock:
            for path, file_info in list(self.pending_files.items()):
                if current_time - file_info["timestamp"] > self.buffer_time:
                    processed_in_current_loop += 1
                    if os.path.exists(path) and os.path.getsize(path) > 0:
                        self.file_count += 1
                        if self.file_count % self.sparsity_window == 0:
                            files_to_process.append(path)
                            print(
                                f"file_count % sparsity_window: {self.file_count} % {self.sparsity_window} == 0"
                            )
                            print(f"Picked file for processing: {path}")
                        else:
                            self.file_skipped += 1
                        del self.pending_files[path]
                    elif not os.path.exists(path):
                        del self.pending_files[path]

        for path in files_to_process:
            self.executor.submit(self.process_file, path)
            self.file_submitted += 1

        if processed_in_current_loop > 0:
            self.logger.info(
                f"File count: {self.file_count}, Files submitted: {self.file_submitted}, Files synced: {self.file_synced}, Files skipped: {self.file_skipped}"
            )

        self.update_sparsity_window()

    def process_file(self, path):
        self.logger.debug(f"Processing file: {path}")
        start_time = time.time()
        sync(self.library_id, path)
        end_time = time.time()
        with self.lock:
            self.sync_times.append(end_time - start_time)
            self.file_synced += 1

    def update_sparsity_window(self):
        min_samples = max(3, self.window_size // 3)
        max_interval = 60  # Maximum allowed interval between events in seconds

        if (
            len(self.pending_times) >= min_samples
            and len(self.sync_times) >= min_samples
        ):
            # Filter out large time gaps
            filtered_intervals = [
                self.pending_times[i] - self.pending_times[i - 1]
                for i in range(1, len(self.pending_times))
                if self.pending_times[i] - self.pending_times[i - 1] <= max_interval
            ]

            if filtered_intervals:
                avg_interval = sum(filtered_intervals) / len(filtered_intervals)
                pending_files_per_second = 1 / avg_interval if avg_interval > 0 else 0
            else:
                pending_files_per_second = 0

            sync_time_total = sum(self.sync_times)
            sync_files_per_second = (
                len(self.sync_times) / sync_time_total if sync_time_total > 0 else 0
            )

            if pending_files_per_second > 0 and sync_files_per_second > 0:
                rate = pending_files_per_second / sync_files_per_second
                new_sparsity_window = max(1, math.ceil(self.sparsity_factor * rate))

                current_time = time.time()
                if current_time - self.last_battery_check > self.battery_check_interval:
                    self.last_battery_check = current_time
                    is_on_battery.cache_clear()  # Clear the cache to get fresh battery status
                new_sparsity_window = (
                    new_sparsity_window * 2 if is_on_battery() else new_sparsity_window
                )

                if new_sparsity_window != self.sparsity_window:
                    old_sparsity_window = self.sparsity_window
                    self.sparsity_window = new_sparsity_window
                    self.logger.info(
                        f"Updated sparsity window: {old_sparsity_window} -> {self.sparsity_window}"
                    )
                    self.logger.debug(
                        f"Pending files per second: {pending_files_per_second:.2f}"
                    )
                    self.logger.debug(
                        f"Sync files per second: {sync_files_per_second:.2f}"
                    )
                    self.logger.debug(f"Rate (pending/sync): {rate:.2f}")

    def is_valid_file(self, path):
        filename = os.path.basename(path)
        return (
            any(path.lower().endswith(ext) for ext in self.include_files)
            and not is_temp_file(filename)
            and not self.inode_pattern.match(filename)
        )

    def on_created(self, event):
        self.handle_event(event)

    def on_modified(self, event):
        self.handle_event(event)

    def on_moved(self, event):
        if self.handle_event(event):
            # For moved events, we need to update the key in pending_files
            with self.lock:
                self.pending_files[event.dest_path] = self.pending_files.pop(
                    event.src_path, {"timestamp": time.time(), "last_size": 0}
                )

    def on_deleted(self, event):
        if self.is_valid_file(event.src_path):
            self.logger.info(f"File deleted: {event.src_path}")
            # Remove from pending files if it was there
            with self.lock:
                self.pending_files.pop(event.src_path, None)
            # Add logic for handling deleted files if needed


@lib_app.command("watch")
def watch(
    library_id: int,
    folders: List[int] = typer.Option(
        None, "--folder", "-f", help="Specify folders to watch"
    ),
    sparsity_factor: float = typer.Option(
        3.0, "--sparsity-factor", "-sf", help="Sparsity factor for file processing"
    ),
    window_size: int = typer.Option(
        10, "--window-size", "-ws", help="Window size for rate calculation"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
):
    """
    Watch for file changes in the library folders and sync automatically.
    """
    # Set the logging level based on the verbose flag
    log_level = "DEBUG" if verbose else "INFO"
    logger.setLevel(log_level)

    logger.info(f"Watching library {library_id} for changes...")

    # Get the library
    response = httpx.get(f"{BASE_URL}/libraries/{library_id}")
    if response.status_code != 200:
        print(f"Error: Library with id {library_id} not found.")
        raise typer.Exit(code=1)

    library = response.json()

    # Filter folders if the folders parameter is provided
    if folders:
        library_folders = [
            folder for folder in library["folders"] if folder["id"] in folders
        ]
    else:
        library_folders = library["folders"]

    if not library_folders:
        print("No folders to watch.")
        return

    # Create an observer and handler for each folder in the library
    observer = Observer()
    handlers = []
    for folder in library_folders:
        folder_path = Path(folder["path"])
        event_handler = LibraryFileHandler(
            library_id,
            include_files,
            sparsity_factor=sparsity_factor,
            window_size=window_size,
        )
        handlers.append(event_handler)
        observer.schedule(event_handler, str(folder_path), recursive=True)
        print(f"Watching folder: {folder_path}")

    observer.start()
    try:
        while True:
            time.sleep(5)
            for handler in handlers:
                handler.process_pending_files()
    except KeyboardInterrupt:
        observer.stop()
        for handler in handlers:
            handler.executor.shutdown(wait=True)
    observer.join()
