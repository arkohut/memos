import asyncio
import os
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

import httpx
import typer
from .server import run_server
from tabulate import tabulate
from tqdm import tqdm
from enum import Enum
from magika import Magika

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})

lib_app = typer.Typer()
plugin_app = typer.Typer()

app.add_typer(plugin_app, name="plugin")
app.add_typer(lib_app, name="lib")

file_detector = Magika()

BASE_URL = "http://localhost:8080"

ignore_files = [".DS_Store"]

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Set the logging level to WARNING or higher
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Optionally, you can set the logging level for specific libraries
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("typer").setLevel(logging.ERROR)


class FileStatus(Enum):
    UPDATED = "updated"
    ADDED = "added"


def format_timestamp(timestamp):
    if isinstance(timestamp, str):
        return timestamp
    return (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        .replace(tzinfo=None)
        .isoformat()
    )


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


@app.command()
def serve():
    run_server()


@lib_app.command("ls")
def ls():
    response = httpx.get(f"{BASE_URL}/libraries")
    libraries = response.json()
    display_libraries(libraries)


@lib_app.command("create")
def add(name: str, folders: List[str]):

    absolute_folders = [str(Path(folder).resolve()) for folder in folders]
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
    absolute_folders = [str(Path(folder).resolve()) for folder in folders]
    response = httpx.post(
        f"{BASE_URL}/libraries/{library_id}/folders",
        json={"folders": absolute_folders},
    )
    if 200 <= response.status_code < 300:
        print("Folders added successfully")
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


async def loop_files(library_id, folder, folder_path, force, plugins):
    updated_file_count = 0
    added_file_count = 0
    scanned_files = set()
    semaphore = asyncio.Semaphore(8)
    async with httpx.AsyncClient() as client:
        tasks = []
        for root, _, files in os.walk(folder_path):
            with tqdm(
                total=len(files), desc=f"Scanning {folder_path}", leave=False
            ) as pbar:
                condidate_files = []
                for file in files:
                    file_path = Path(root) / file
                    absolute_file_path = file_path.resolve()  # Get absolute path
                    if file in ignore_files:
                        continue

                    scanned_files.add(str(absolute_file_path))
                    condidate_files.append(str(absolute_file_path))

                batching = 200
                for i in range(0, len(condidate_files), batching):
                    batch = condidate_files[i : i + batching]

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

                            if (
                                force
                                or existing_created_at != new_created_at
                                or existing_modified_at != new_modified_at
                            ):
                                # Update the existing entity
                                tasks.append(
                                    update_entity(
                                        client,
                                        semaphore,
                                        plugins,
                                        new_entity,
                                        existing_entity,
                                    )
                                )
                        else:
                            # Add the new entity
                            tasks.append(
                                add_entity(
                                    client, semaphore, library_id, plugins, new_entity
                                )
                            )
                    pbar.update(len(batch))

        for future in tqdm(
            asyncio.as_completed(tasks),
            desc=f"Processing {folder_path}",
            total=len(tasks),
            leave=False,
        ):
            file_path, file_status, succeeded, response = await future
            if file_status == FileStatus.ADDED:
                if succeeded:
                    added_file_count += 1
                    tqdm.write(f"Added file to library: {file_path}")
                else:
                    tqdm.write(
                        f"Failed to add file: {response.status_code} - {response.text}"
                    )
            elif file_status == FileStatus.UPDATED:
                if succeeded:
                    updated_file_count += 1
                    tqdm.write(f"Updated file in library: {file_path}")
                else:
                    tqdm.write(
                        f"Failed to update file: {response.status_code} - {response.text}"
                    )

    return added_file_count, updated_file_count, scanned_files


@lib_app.command("scan")
def scan(
    library_id: int,
    force: bool = False,
    plugins: List[int] = typer.Option(None, "--plugin", "-p"),
    folders: List[int] = typer.Option(None, "--folder", "-f"),
):

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
        with tqdm(total=total_entities, desc="Checking for deleted files", leave=True) as pbar2:
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
                    if existing_file["filepath"] not in scanned_files:
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
        post_response = await client.post(
            f"{BASE_URL}/libraries/{library_id}/entities",
            json=new_entity,
            params={"plugins": plugins} if plugins else {},
            timeout=60,
        )
        if 200 <= post_response.status_code < 300:
            return new_entity["filepath"], FileStatus.ADDED, True, post_response
        else:
            return new_entity["filepath"], FileStatus.ADDED, False, post_response


async def update_entity(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    plugins,
    new_entity,
    existing_entity,
) -> Tuple[FileStatus, bool, httpx.Response]:
    async with semaphore:
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
            return new_entity["filepath"], FileStatus.UPDATED, True, update_response
        else:
            return new_entity["filepath"], FileStatus.UPDATED, False, update_response


@lib_app.command("index")
def index(
    library_id: int,
    folders: List[int] = typer.Option(None, "--folder", "-f"),
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

    # Iterate through folders
    for folder in library_folders:
        tqdm.write(f"Processing folder: {folder['id']}")

        # List all entities in the folder
        offset = 0
        while True:
            entities_response = httpx.get(
                f"{BASE_URL}/libraries/{library_id}/folders/{folder['id']}/entities",
                params={"limit": 200, "offset": offset},
                timeout=60,
            )
            if entities_response.status_code != 200:
                tqdm.write(
                    f"Failed to get entities: {entities_response.status_code} - {entities_response.text}"
                )
                break

            entities = entities_response.json()
            if not entities:
                break

            # Index each entity
            for entity in tqdm(entities, desc="Indexing entities", leave=False):
                index_response = httpx.post(f"{BASE_URL}/entities/{entity['id']}/index")
                if index_response.status_code == 204:
                    tqdm.write(f"Indexed entity: {entity['id']}")
                else:
                    tqdm.write(
                        f"Failed to index entity {entity['id']}: {index_response.status_code} - {index_response.text}"
                    )

                scanned_entities.add(str(entity["id"]))

            offset += 200

        # List all indexed entities in the folder
        offset = 0
        while True:
            index_response = httpx.get(
                f"{BASE_URL}/libraries/{library_id}/folders/{folder['id']}/index",
                params={"limit": 200, "offset": offset},
                timeout=60,
            )
            if index_response.status_code != 200:
                tqdm.write(
                    f"Failed to get indexed entities: {index_response.status_code} - {index_response.text}"
                )
                break

            indexed_entities = index_response.json()
            if not indexed_entities:
                break

            # Delete indexes for entities not in scanned_entities
            for indexed_entity in tqdm(
                indexed_entities, desc="Cleaning up indexes", leave=False
            ):
                if indexed_entity["id"] not in scanned_entities:
                    delete_response = httpx.delete(
                        f"{BASE_URL}/entities/{indexed_entity['id']}/index"
                    )
                    if delete_response.status_code == 204:
                        tqdm.write(f"Deleted index for entity: {indexed_entity['id']}")
                    else:
                        tqdm.write(
                            f"Failed to delete index for entity {indexed_entity['id']}: {delete_response.status_code} - {delete_response.text}"
                        )

            offset += 200

    print("Indexing completed")


def display_plugins(plugins):
    table = []
    for plugin in plugins:
        table.append(
            [plugin["id"], plugin["name"], plugin["description"], plugin["webhook_url"]]
        )
    print(
        tabulate(
            table,
            headers=["ID", "Name", "Description", "Webhook URL"],
            tablefmt="plain",
        )
    )


@plugin_app.command("ls")
def ls():
    response = httpx.get(f"{BASE_URL}/plugins")
    plugins = response.json()
    display_plugins(plugins)


@plugin_app.command("create")
def create(name: str, webhook_url: str, description: str = ""):
    response = httpx.post(
        f"{BASE_URL}/plugins",
        json={"name": name, "description": description, "webhook_url": webhook_url},
    )
    if 200 <= response.status_code < 300:
        print("Plugin created successfully")
    else:
        print(f"Failed to create plugin: {response.status_code} - {response.text}")


@plugin_app.command("bind")
def bind(
    library_id: int = typer.Option(..., "--lib", help="ID of the library"),
    plugin_id: int = typer.Option(..., "--plugin", help="ID of the plugin"),
):
    response = httpx.post(
        f"{BASE_URL}/libraries/{library_id}/plugins",
        json={"plugin_id": plugin_id},
    )
    if 200 <= response.status_code < 300:
        print("Plugin bound to library successfully")
    else:
        print(
            f"Failed to bind plugin to library: {response.status_code} - {response.text}"
        )


if __name__ == "__main__":
    app()
