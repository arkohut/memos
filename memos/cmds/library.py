# Standard library imports
import time
import math
import re
import os
import threading
import asyncio
import logging
import logging.config
from pathlib import Path
from datetime import datetime
from enum import Enum
from typing import List, Tuple, Dict, Any, Optional, Set
from functools import lru_cache
from collections import defaultdict, deque

# Third-party imports
import typer
import httpx
from tqdm import tqdm
from tabulate import tabulate
import psutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from concurrent.futures import ThreadPoolExecutor

# Local imports
from memos.config import settings
from memos.utils import get_image_metadata
from memos.schemas import MetadataSource
from memos.logging_config import LOGGING_CONFIG


logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

lib_app = typer.Typer()

file_detector = None

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


def init_file_detector():
    """Initialize the global file detector if not already initialized"""
    global file_detector
    if file_detector is None:
        from magika import Magika

        file_detector = Magika()
    return file_detector


def get_file_type(file_path):
    """Get file type using lazy-loaded detector"""
    detector = init_file_detector()
    file_result = detector.identify_path(file_path)
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
        f"{BASE_URL}/libraries", json={"name": name, "folders": absolute_folders}
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


async def loop_files(library_id, folder, folder_path, force, plugins, batch_size):
    """
    Process files in the folder

    Args:
        library_id: Library ID
        folder: Folder information
        folder_path: Folder path
        force: Whether to force update
        plugins: List of plugins
        batch_size: Batch size

    Returns:
        Tuple[int, int, int]: (Number of files added, Number of files updated, Number of files deleted)
    """
    updated_file_count = 0
    added_file_count = 0
    deleted_file_count = 0
    semaphore = asyncio.Semaphore(batch_size)

    async with httpx.AsyncClient(timeout=60) as client:
        # 1. Collect candidate files
        candidate_files = await collect_candidate_files(folder_path)
        scanned_files = set(candidate_files)

        # 2. Process file batches
        added_file_count, updated_file_count = await process_file_batches(
            client,
            library_id,
            folder,
            candidate_files,
            force,
            plugins,
            semaphore,
        )

        # 3. Check for deleted files
        deleted_file_count = await check_deleted_files(
            client, library_id, folder, folder_path, scanned_files
        )

        return added_file_count, updated_file_count, deleted_file_count


@lib_app.command("scan")
def scan(
    library_id: int,
    path: str = typer.Argument(None, help="Path to scan within the library"),
    force: bool = False,
    plugins: List[int] = typer.Option(None, "--plugin", "-p"),
    folders: List[int] = typer.Option(None, "--folder", "-f"),
    batch_size: int = typer.Option(
        1, "--batch-size", "-bs", help="Batch size for processing files"
    ),
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

        added_file_count, updated_file_count, deleted_file_count = asyncio.run(
            loop_files(library_id, folder, folder_path, force, plugins, batch_size)
        )
        total_files_added += added_file_count
        total_files_updated += updated_file_count
        total_files_deleted += deleted_file_count

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
                    params=(
                        {"plugins": plugins, "update_index": "true"}
                        if plugins
                        else {"update_index": "true"}
                    ),
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
                        "update_index": "true",
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
    batch_size: int = typer.Option(
        1, "--batch-size", "-bs", help="Batch size for processing entities"
    ),
):
    print(f"Reindexing library {library_id}")

    from memos.models import recreate_fts_and_vec_tables

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

    with httpx.Client() as client:
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

                    # Collect entity IDs to be processed
                    entity_ids = [
                        entity["id"]
                        for entity in entities
                        if entity["id"] not in scanned_entities
                    ]

                    # Process in batches
                    for i in range(0, len(entity_ids), batch_size):
                        batch_ids = entity_ids[i : i + batch_size]
                        if batch_ids:
                            batch_response = client.post(
                                f"{BASE_URL}/entities/batch-index",
                                json={"entity_ids": batch_ids},
                                timeout=60,
                            )
                            if batch_response.status_code != 204:
                                print(
                                    f"Failed to update batch: {batch_response.status_code} - {batch_response.text}"
                                )
                            pbar.update(len(batch_ids))
                            scanned_entities.update(batch_ids)

                    offset += limit

    print(f"Reindexing completed for library {library_id}")


def has_entity_changes(new_entity: dict, existing_entity: dict) -> bool:
    """
    Compare new_entity with existing_entity to determine if there are actual changes.
    Returns True if there are differences, False otherwise.
    """
    # Compare basic fields
    basic_fields = [
        "filename",
        "filepath",
        "size",
        "file_created_at",
        "file_last_modified_at",
        "file_type",
        "file_type_group",
    ]

    for field in basic_fields:
        if new_entity.get(field) != existing_entity.get(field):
            return True

    # Compare metadata entries
    new_metadata = {
        (entry["key"], entry["value"])
        for entry in new_entity.get("metadata_entries", [])
    }
    existing_metadata = {
        (entry["key"], entry["value"])
        for entry in existing_entity.get("metadata_entries", [])
    }
    if new_metadata != existing_metadata:
        return True

    # Compare tags
    new_tags = set(new_entity.get("tags", []))
    existing_tags = {tag["name"] for tag in existing_entity.get("tags", [])}
    if new_tags != existing_tags:
        return True

    return False


@lib_app.command("sync")
def sync(
    library_id: int,
    filepath: str,
    force: bool = typer.Option(
        False, "--force", "-f", help="Force update the file even if it hasn't changed"
    ),
    without_webhooks: bool = typer.Option(
        False, "--no-plugins", help="Disable plugin triggers", is_flag=True
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

        if not force:
            # Merge existing metadata with new metadata
            new_metadata_keys = {
                entry["key"] for entry in new_entity.get("metadata_entries", [])
            }
            for existing_entry in existing_entity.get("metadata_entries", []):
                if existing_entry["key"] not in new_metadata_keys:
                    new_entity["metadata_entries"].append(existing_entry)
            
            # Merge existing tags with new tags
            existing_tags = {tag["name"] for tag in existing_entity.get("tags", [])}
            new_tags = set(new_entity.get("tags", []))
            merged_tags = new_tags.union(existing_tags)
            new_entity["tags"] = list(merged_tags)

        # Only update if there are actual changes or force flag is set
        if force or has_entity_changes(new_entity, existing_entity):
            update_response = httpx.put(
                f"{BASE_URL}/entities/{existing_entity['id']}",
                json=new_entity,
                params={
                    "trigger_webhooks_flag": str(not without_webhooks).lower(),
                    "update_index": "true",
                },
                timeout=60,
            )
            if update_response.status_code == 200:
                typer.echo(f"Updated file: {file_path}")
            else:
                typer.echo(
                    f"Error updating file: {update_response.status_code} - {update_response.text}"
                )
        else:
            typer.echo(f"File {file_path} is up to date. No changes detected.")

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
                params={
                    "trigger_webhooks_flag": str(not without_webhooks).lower(),
                    "update_index": "true",
                },
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
        files_to_process_with_plugins = []
        files_to_process_without_plugins = []
        processed_in_current_loop = 0
        with self.lock:
            for path, file_info in list(self.pending_files.items()):
                if current_time - file_info["timestamp"] > self.buffer_time:
                    processed_in_current_loop += 1
                    if os.path.exists(path) and os.path.getsize(path) > 0:
                        self.file_count += 1
                        if self.file_count % self.sparsity_window == 0:
                            files_to_process_with_plugins.append(path)
                            print(
                                f"file_count % sparsity_window: {self.file_count} % {self.sparsity_window} == 0"
                            )
                            print(f"Picked file for processing with plugins: {path}")
                        else:
                            files_to_process_without_plugins.append(path)
                            self.file_skipped += 1
                        del self.pending_files[path]
                    elif not os.path.exists(path):
                        del self.pending_files[path]

        # Process files with plugins - these count as submitted
        for path in files_to_process_with_plugins:
            self.executor.submit(self.process_file, path, False)
            self.file_submitted += 1

        # Process files without plugins - these don't count as submitted
        for path in files_to_process_without_plugins:
            self.executor.submit(self.process_file, path, True)

        if processed_in_current_loop > 0:
            self.logger.info(
                f"File count: {self.file_count}, Files submitted: {self.file_submitted}, Files synced: {self.file_synced}, Files skipped: {self.file_skipped}"
            )

        self.update_sparsity_window()

    def process_file(self, path, no_plugins):
        self.logger.debug(f"Processing file: {path} (with plugins: {not no_plugins})")
        start_time = time.time()
        sync(self.library_id, path, without_webhooks=no_plugins)
        end_time = time.time()
        if not no_plugins:
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


async def collect_candidate_files(folder_path: Path) -> List[str]:
    """
    Collect candidate files to be processed

    Args:
        folder_path: Folder path

    Returns:
        List[str]: List of candidate file paths
    """
    candidate_files = []
    for root, _, files in os.walk(folder_path):
        with tqdm(total=len(files), desc=f"Scanning {root}", leave=True) as pbar:
            for file in files:
                file_path = Path(root) / file
                absolute_file_path = file_path.resolve()

                # Check if the file extension is in the include_files list and is not a temporary file
                if file_path.suffix.lower() in include_files and not is_temp_file(file):
                    candidate_files.append(str(absolute_file_path))
                pbar.update(1)

    return candidate_files


async def prepare_entity(file_path: str, folder_id: int) -> Dict[str, Any]:
    """
    Prepare entity data

    Args:
        file_path: File path
        folder_id: Folder ID

    Returns:
        Dict[str, Any]: Entity data
    """
    file_path = Path(file_path)
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
        "folder_id": folder_id,
    }

    # Handle image metadata
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

    new_entity["is_thumbnail"] = is_thumbnail
    return new_entity


def should_update_entity(
    new_entity: Dict[str, Any], existing_entity: Dict[str, Any], force: bool
) -> bool:
    """
    Determine whether to update the entity

    Args:
        new_entity: New entity data
        existing_entity: Existing entity data
        force: Whether to force update

    Returns:
        bool: Whether to update the entity
    """
    if new_entity.get("is_thumbnail", False):
        return False

    existing_created_at = format_timestamp(existing_entity["file_created_at"])
    new_created_at = format_timestamp(new_entity["file_created_at"])
    existing_modified_at = format_timestamp(existing_entity["file_last_modified_at"])
    new_modified_at = format_timestamp(new_entity["file_last_modified_at"])

    return (
        force
        or existing_created_at != new_created_at
        or existing_modified_at != new_modified_at
    )


def format_error_message(
    file_status: FileStatus, response: Optional[httpx.Response]
) -> str:
    """
    Format error message

    Args:
        file_status: File status
        response: HTTP response

    Returns:
        str: Formatted error message
    """
    action = "add" if file_status == FileStatus.ADDED else "update"
    error_message = f"Failed to {action} file"

    if response:
        if hasattr(response, "status_code"):
            error_message += f": {response.status_code}"
        if hasattr(response, "text"):
            error_message += f" - {response.text}"
    else:
        error_message += " - Unknown error occurred"

    return error_message


async def process_file_batches(
    client: httpx.AsyncClient,
    library_id: int,
    folder: dict,
    candidate_files: list,
    force: bool,
    plugins: list,
    semaphore: asyncio.Semaphore,
) -> Tuple[int, int]:
    """
    Process file batches

    Args:
        client: httpx async client
        library_id: Library ID
        folder: Folder information
        candidate_files: List of candidate files
        force: Whether to force update
        plugins: List of plugins
        semaphore: Concurrency control semaphore

    Returns:
        Tuple[int, int]: (Number of files added, Number of files updated)
    """
    added_file_count = 0
    updated_file_count = 0
    batching = 50

    with tqdm(total=len(candidate_files), desc="Processing files", leave=True) as pbar:
        for i in range(0, len(candidate_files), batching):
            batch = candidate_files[i : i + batching]

            # Get existing entities in the batch
            get_response = await client.post(
                f"{BASE_URL}/libraries/{library_id}/entities/by-filepaths",
                json=batch,
            )

            if get_response.status_code != 200:
                print(
                    f"Failed to get entities: {get_response.status_code} - {get_response.text}"
                )
                pbar.update(len(batch))
                continue

            existing_entities = get_response.json()
            existing_entities_dict = {
                entity["filepath"]: entity for entity in existing_entities
            }

            # Process each file
            tasks = []
            for file_path in batch:
                new_entity = await prepare_entity(file_path, folder["id"])

                existing_entity = existing_entities_dict.get(str(file_path))
                if existing_entity:
                    if should_update_entity(new_entity, existing_entity, force):
                        tasks.append(
                            update_entity(
                                client, semaphore, plugins, new_entity, existing_entity
                            )
                        )
                elif not new_entity.get("is_thumbnail", False):
                    tasks.append(
                        add_entity(client, semaphore, library_id, plugins, new_entity)
                    )

            # Process task results
            if tasks:
                for future in asyncio.as_completed(tasks):
                    file_path, file_status, succeeded, response = await future
                    if succeeded:
                        if file_status == FileStatus.ADDED:
                            added_file_count += 1
                            tqdm.write(f"Added file to library: {file_path}")
                        else:
                            updated_file_count += 1
                            tqdm.write(f"Updated file in library: {file_path}")
                    else:
                        error_message = format_error_message(file_status, response)
                        tqdm.write(error_message)

                    # Update progress bar for each file processed
                    pbar.update(1)
                    pbar.set_postfix(
                        {"Added": added_file_count, "Updated": updated_file_count},
                        refresh=True,
                    )

    return added_file_count, updated_file_count


async def check_deleted_files(
    client: httpx.AsyncClient,
    library_id: int,
    folder: dict,
    folder_path: Path,
    scanned_files: Set[str],
) -> int:
    """
    Check and handle deleted files

    Args:
        client: httpx async client
        library_id: Library ID
        folder: Folder information
        folder_path: Folder path
        scanned_files: Set of scanned files

    Returns:
        int: Number of deleted files
    """
    deleted_count = 0
    limit = 100
    offset = 0
    total_entities = 0

    with tqdm(
        total=total_entities, desc="Checking for deleted files", leave=True
    ) as pbar:
        while True:
            # Add path_prefix parameter to only get entities under the folder_path
            existing_files_response = await client.get(
                f"{BASE_URL}/libraries/{library_id}/folders/{folder['id']}/entities",
                params={
                    "limit": limit,
                    "offset": offset,
                    "path_prefix": str(folder_path),
                },
                timeout=60,
            )

            if existing_files_response.status_code != 200:
                pbar.write(
                    f"Failed to retrieve existing files: {existing_files_response.status_code} - {existing_files_response.text}"
                )
                break

            existing_files = existing_files_response.json()
            if not existing_files:
                break

            # Update total count (if this is the first request)
            if offset == 0:
                total_entities = int(
                    existing_files_response.headers.get("X-Total-Count", total_entities)
                )
                pbar.total = total_entities
                pbar.refresh()

            for existing_file in existing_files:
                if (
                    # path_prefix may include files not in the folder_path,
                    # for example when folder_path is 20241101 but there is another folder 20241101-copy
                    # so check the existing_file is relative_to folder_path is required,
                    # do not remove this.
                    Path(existing_file["filepath"]).is_relative_to(folder_path)
                    and existing_file["filepath"] not in scanned_files
                ):
                    # File has been deleted
                    delete_response = await client.delete(
                        f"{BASE_URL}/libraries/{library_id}/entities/{existing_file['id']}"
                    )
                    if 200 <= delete_response.status_code < 300:
                        pbar.write(
                            f"Deleted file from library: {existing_file['filepath']}"
                        )
                        deleted_count += 1
                    else:
                        pbar.write(
                            f"Failed to delete file: {delete_response.status_code} - {delete_response.text}"
                        )
                pbar.update(1)

            offset += limit

    return deleted_count
