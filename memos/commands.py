import mimetypes
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

app = typer.Typer()
lib_app = typer.Typer()
app.add_typer(lib_app, name="lib")


def format_timestamp(timestamp):
    if isinstance(timestamp, str):
        return timestamp
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None).isoformat()


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
            ]
        )

    print(tabulate(table, headers=["ID", "Name", "Folders"], tablefmt="plain"))


@app.command()
def serve():
    run_server()


@lib_app.command("ls")
def ls():
    response = httpx.get("http://localhost:8080/libraries")
    libraries = response.json()
    display_libraries(libraries)


@lib_app.command("create")
def add(name: str, folders: List[str]):

    absolute_folders = [str(Path(folder).resolve()) for folder in folders]
    response = httpx.post(
        "http://localhost:8080/libraries",
        json={"name": name, "folders": absolute_folders},
    )
    if 200 <= response.status_code < 300:
        print("Library created successfully")
    else:
        print(f"Failed to create library: {response.status_code} - {response.text}")


@lib_app.command("show")
def show(library_id: int):
    response = httpx.get(f"http://localhost:8080/libraries/{library_id}")
    if response.status_code == 200:
        library = response.json()
        display_libraries([library])
    else:
        print(f"Failed to retrieve library: {response.status_code} - {response.text}")


@lib_app.command("scan")
def scan(library_id: int):

    response = httpx.get(f"http://localhost:8080/libraries/{library_id}")
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
                    relative_file_path = file_path.relative_to(
                        folder_path
                    )  # Get relative path
                    scanned_files.add(str(relative_file_path))  # Add to scanned files set
                    file_stat = file_path.stat()
                    file_type = (
                        mimetypes.guess_type(file_path)[0] or "application/octet-stream"
                    )
                    new_entity = {
                        "filename": file_path.name,
                        "filepath": str(relative_file_path),  # Save relative path
                        "size": file_stat.st_size,
                        "file_created_at": format_timestamp(file_stat.st_ctime),
                        "file_last_modified_at": format_timestamp(file_stat.st_mtime),
                        "file_type": file_type,
                        "folder_id": folder["id"],
                    }

                    # Check if the entity already exists
                    get_response = httpx.get(
                        f"http://localhost:8080/libraries/{library_id}/entities/by-filepath",
                        params={
                            "filepath": str(relative_file_path)
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
                            existing_created_at != new_created_at
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
                                f"http://localhost:8080/libraries/{library_id}/entities/{existing_entity['id']}",
                                json=new_entity,
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
                        f"http://localhost:8080/libraries/{library_id}/entities",
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
        limit = 200  # Adjust the limit as needed
        offset = 0
        while True:
            existing_files_response = httpx.get(
                f"http://localhost:8080/libraries/{library_id}/folders/{folder['id']}/entities",
                params={"limit": limit, "offset": offset}
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
                        f"http://localhost:8080/libraries/{library_id}/entities/{existing_file['id']}"
                    )
                    if 200 <= delete_response.status_code < 300:
                        tqdm.write(f"Deleted file from library: {existing_file['filepath']}")
                        total_files_deleted += 1
                    else:
                        tqdm.write(
                            f"Failed to delete file: {delete_response.status_code} - {delete_response.text}"
                        )

            offset += limit

    print(f"Total files added: {total_files_added}")
    print(f"Total files updated: {total_files_updated}")
    print(f"Total files deleted: {total_files_deleted}")


if __name__ == "__main__":
    app()
