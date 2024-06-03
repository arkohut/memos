import mimetypes
import os
import time
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

    for folder in library["folders"]:
        folder_path = Path(folder["path"])
        if not folder_path.exists() or not folder_path.is_dir():
            tqdm.write(f"Folder does not exist or is not a directory: {folder_path}")
            continue

        start_time = time.time()  # Start the timer
        file_count = 0  # Initialize the file counter

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
                    relative_file_path = file_path.relative_to(folder_path)  # Get relative path
                    file_stat = file_path.stat()
                    file_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
                    new_entity = {
                        "filename": file_path.name,
                        "filepath": str(relative_file_path),  # Save relative path
                        "size": file_stat.st_size,
                        "file_created_at": file_stat.st_ctime,
                        "file_last_modified_at": file_stat.st_mtime,
                        "file_type": file_type,
                        "folder_id": folder["id"],
                    }

                    # Check if the entity already exists
                    get_response = httpx.get(
                        f"http://localhost:8080/libraries/{library_id}/entities",
                        params={"filepath": str(relative_file_path)},  # Use relative path
                    )
                    if get_response.status_code == 200:
                        tqdm.write(f"File already exists in library: {file_path}")
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

    print(f"Total files added: {total_files_added}")


if __name__ == "__main__":
    app()
