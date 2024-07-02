import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import httpx
import typer
from memos.server import run_server
from tabulate import tabulate
from tqdm import tqdm
from magika import Magika

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})
lib_app = typer.Typer()
plugin_app = typer.Typer()
app.add_typer(plugin_app, name="plugin")
app.add_typer(lib_app, name="lib")

file_detector = Magika()

BASE_URL = "http://localhost:8080"

ignore_files = [".DS_Store"]


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


@lib_app.command("show")
def show(library_id: int):
    response = httpx.get(f"{BASE_URL}/libraries/{library_id}")
    if response.status_code == 200:
        library = response.json()
        display_libraries([library])
    else:
        print(f"Failed to retrieve library: {response.status_code} - {response.text}")


@lib_app.command("scan")
def scan(library_id: int, force: bool = False):

    response = httpx.get(f"{BASE_URL}/libraries/{library_id}")
    if response.status_code != 200:
        print(f"Failed to retrieve library: {response.status_code} - {response.text}")
        return

    library = response.json()
    total_files_added = 0
    total_files_updated = 0
    total_files_deleted = 0

    for folder in library["folders"]:
        folder_path = Path(folder["path"])
        if not folder_path.exists() or not folder_path.is_dir():
            tqdm.write(f"Folder does not exist or is not a directory: {folder_path}")
            continue

        start_time = time.time()  # Start the timer
        file_count = 0  # Initialize the file counter
        scanned_files = set()  # To keep track of scanned files

        for root, _, files in os.walk(folder_path):
            with tqdm(
                total=len(files), desc=f"Scanning {os.path.basename(root)}", leave=False
            ) as pbar:
                for file in files:
                    current_time = time.time() - start_time  # Calculate elapsed time
                    elapsed_time_str = f"{int(current_time // 60):02d}m:{int(current_time % 60):02d}s"  # Format as mm:ss for brevity
                    pbar.set_postfix_str(
                        f"Files: {file_count}, Time: {elapsed_time_str}", refresh=False
                    )
                    pbar.update(1)
                    file_path = Path(root) / file
                    absolute_file_path = file_path.resolve()  # Get absolute path
                    if file in ignore_files:
                        continue
                    scanned_files.add(
                        str(absolute_file_path)
                    )  # Add to scanned files set
                    file_stat = file_path.stat()
                    file_type, file_type_group = get_file_type(absolute_file_path)
                    new_entity = {
                        "filename": file_path.name,
                        "filepath": str(absolute_file_path),  # Save absolute path
                        "size": file_stat.st_size,
                        "file_created_at": format_timestamp(file_stat.st_ctime),
                        "file_last_modified_at": format_timestamp(file_stat.st_mtime),
                        "file_type": file_type,
                        "file_type_group": file_type_group,
                        "folder_id": folder["id"],
                    }
                    # Check if the entity already exists
                    get_response = httpx.get(
                        f"{BASE_URL}/libraries/{library_id}/entities/by-filepath",
                        params={
                            "filepath": str(absolute_file_path)
                        },  # Use relative path
                    )
                    if get_response.status_code == 200:
                        existing_entity = get_response.json()
                        existing_created_at = format_timestamp(
                            existing_entity["file_created_at"]
                        )
                        new_created_at = format_timestamp(new_entity["file_created_at"])
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
                            # Show the difference before update
                            tqdm.write(f"Updating file: {file_path}")
                            tqdm.write(
                                f"Old created at: {existing_created_at}, New created at: {new_created_at}"
                            )
                            tqdm.write(
                                f"Old last modified at: {existing_modified_at}, New last modified at: {new_modified_at}"
                            )
                            # Update the existing entity
                            update_response = httpx.put(
                                f"{BASE_URL}/entities/{existing_entity['id']}",
                                json=new_entity,
                                params={"trigger_webhooks_flag": "true"},
                            )
                            if 200 <= update_response.status_code < 300:
                                tqdm.write(f"Updated file in library: {file_path}")
                                total_files_updated += 1
                            else:
                                tqdm.write(
                                    f"Failed to update file: {update_response.status_code} - {update_response.text}"
                                )
                        else:
                            tqdm.write(
                                f"File already exists in library and is up-to-date: {file_path}"
                            )
                        continue

                    # Add the new entity
                    post_response = httpx.post(
                        f"{BASE_URL}/libraries/{library_id}/entities",
                        json=new_entity,
                    )
                    if 200 <= post_response.status_code < 300:
                        tqdm.write(f"Added file to library: {file_path}")
                        total_files_added += 1
                    else:
                        tqdm.write(
                            f"Failed to add file: {post_response.status_code} - {post_response.text}"
                        )
                    file_count += 1

        # Check for deleted files
        limit = 200
        offset = 0
        while True:
            existing_files_response = httpx.get(
                f"{BASE_URL}/libraries/{library_id}/folders/{folder['id']}/entities",
                params={"limit": limit, "offset": offset},
            )
            if existing_files_response.status_code != 200:
                tqdm.write(
                    f"Failed to retrieve existing files: {existing_files_response.status_code} - {existing_files_response.text}"
                )
                break

            existing_files = existing_files_response.json()
            if not existing_files:
                break

            for existing_file in existing_files:
                if existing_file["filepath"] not in scanned_files:
                    # File has been deleted
                    delete_response = httpx.delete(
                        f"{BASE_URL}/libraries/{library_id}/entities/{existing_file['id']}"
                    )
                    if 200 <= delete_response.status_code < 300:
                        tqdm.write(
                            f"Deleted file from library: {existing_file['filepath']}"
                        )
                        total_files_deleted += 1
                    else:
                        tqdm.write(
                            f"Failed to delete file: {delete_response.status_code} - {delete_response.text}"
                        )

            offset += limit

    print(f"Total files added: {total_files_added}")
    print(f"Total files updated: {total_files_updated}")
    print(f"Total files deleted: {total_files_deleted}")


@lib_app.command("index")
def index(library_id: int):
    print(f"Indexing library {library_id}")

    # Get the library
    response = httpx.get(f"{BASE_URL}/libraries/{library_id}")
    if response.status_code != 200:
        print(f"Failed to get library: {response.status_code} - {response.text}")
        return

    library = response.json()
    scanned_entities = set()

    # Iterate through folders
    for folder in library["folders"]:
        tqdm.write(f"Processing folder: {folder['id']}")

        # List all entities in the folder
        offset = 0
        while True:
            entities_response = httpx.get(
                f"{BASE_URL}/libraries/{library_id}/folders/{folder['id']}/entities",
                params={"limit": 200, "offset": offset},
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
