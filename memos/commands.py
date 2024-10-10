import os
import logging
from pathlib import Path
from datetime import datetime

import httpx
import typer
from .config import settings
from .models import init_database
from .initialize_typesense import init_typesense
from .record import (
    run_screen_recorder_once,
    run_screen_recorder,
    load_previous_hashes,
)
import time
import sys
import subprocess
import platform
from .cmds.plugin import plugin_app, bind
from .cmds.library import lib_app, scan, index, watch


app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})

app.add_typer(plugin_app, name="plugin")
app.add_typer(lib_app, name="lib")

BASE_URL = f"http://{settings.server_host}:{settings.server_port}"

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Set the logging level to WARNING or higher
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Optionally, you can set the logging level for specific libraries
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("typer").setLevel(logging.ERROR)


@app.command()
def serve():
    """Run the server after initializing if necessary."""
    db_success = init_database()
    ts_success = True
    if settings.typesense.enabled:
        ts_success = init_typesense()
    if db_success and (ts_success or not settings.typesense.enabled):
        from .server import run_server

        run_server()
    else:
        print("Server initialization failed. Unable to start the server.")


@app.command()
def init():
    """Initialize the database and Typesense collection if enabled."""
    db_success = init_database()
    ts_success = True
    if settings.typesense.enabled:
        ts_success = init_typesense()
    if db_success and (ts_success or not settings.typesense.enabled):
        print("Initialization completed successfully.")
    else:
        print("Initialization failed. Please check the error messages above.")


def get_or_create_default_library():
    """
    Get the default library or create it if it doesn't exist.
    Ensure the library has at least one folder.
    """
    response = httpx.get(f"{BASE_URL}/libraries")
    if response.status_code != 200:
        print(f"Failed to retrieve libraries: {response.status_code} - {response.text}")
        return None

    libraries = response.json()
    default_library = next(
        (lib for lib in libraries if lib["name"] == settings.default_library), None
    )

    if not default_library:
        # Create the default library if it doesn't exist
        response = httpx.post(
            f"{BASE_URL}/libraries",
            json={"name": settings.default_library, "folders": []},
        )
        if response.status_code != 200:
            print(
                f"Failed to create default library: {response.status_code} - {response.text}"
            )
            return None
        default_library = response.json()

    for plugin in settings.default_plugins:
        bind(default_library["id"], plugin)

    # Check if the library is empty
    if not default_library["folders"]:
        # Add the screenshots directory to the library
        screenshots_dir = Path(settings.screenshots_dir).resolve()
        folder = {
            "path": str(screenshots_dir),
            "last_modified_at": datetime.fromtimestamp(
                screenshots_dir.stat().st_mtime
            ).isoformat(),
        }
        response = httpx.post(
            f"{BASE_URL}/libraries/{default_library['id']}/folders",
            json={"folders": [folder]},
        )
        if response.status_code != 200:
            print(
                f"Failed to add screenshots directory: {response.status_code} - {response.text}"
            )
            return None
        print(f"Added screenshots directory: {screenshots_dir}")

    return default_library


@app.command("scan")
def scan_default_library(force: bool = False):
    """
    Scan the screenshots directory and add it to the library if empty.
    """
    default_library = get_or_create_default_library()
    if not default_library:
        return

    # Scan the library
    print(f"Scanning library: {default_library['name']}")
    scan(default_library["id"], plugins=None, folders=None, force=force)


@app.command("index")
def index_default_library(
    batchsize: int = typer.Option(
        4, "--batchsize", "-bs", help="Number of entities to index in a batch"
    ),
    force: bool = typer.Option(False, "--force", help="Force update all indexes"),
):
    """
    Index the default library for memos.
    """
    # Get the default library
    response = httpx.get(f"{BASE_URL}/libraries")
    if response.status_code != 200:
        print(f"Failed to retrieve libraries: {response.status_code} - {response.text}")
        return

    libraries = response.json()
    default_library = next(
        (lib for lib in libraries if lib["name"] == settings.default_library), None
    )

    if not default_library:
        print("Default library does not exist.")
        return

    index(default_library["id"], force=force, folders=None, batchsize=batchsize)


@app.command("record")
def record(
    threshold: int = typer.Option(4, help="Threshold for image similarity"),
    base_dir: str = typer.Option(None, help="Base directory for screenshots"),
    once: bool = typer.Option(False, help="Run once and exit"),
):
    """
    Record screenshots of the screen.
    """
    base_dir = os.path.expanduser(base_dir) if base_dir else settings.screenshots_dir
    previous_hashes = load_previous_hashes(base_dir)

    if once:
        run_screen_recorder_once(threshold, base_dir, previous_hashes)
    else:
        while True:
            try:
                run_screen_recorder(threshold, base_dir, previous_hashes)
            except Exception as e:
                logging.error(
                    f"Critical error occurred, program will restart in 10 seconds: {str(e)}"
                )
                time.sleep(10)


@app.command("watch")
def watch_default_library(
    window_size: int = typer.Option(
        20, "--window-size", "-ws", help="Window size for rate calculation"
    ),
    sparsity_factor: float = typer.Option(
        2.0, "--sparsity-factor", "-sf", help="Sparsity factor for file processing"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")
):
    """
    Watch the default library for file changes and sync automatically.
    """
    default_library = get_or_create_default_library()
    if not default_library:
        return

    watch(
        default_library["id"],
        folders=None,
        window_size=window_size,
        sparsity_factor=sparsity_factor,
        verbose=verbose
    )


def get_python_path():
    return sys.executable


def get_memos_dir():
    return Path.home() / ".memos"


def generate_windows_bat():
    memos_dir = get_memos_dir()
    python_path = get_python_path()
    conda_prefix = os.environ.get("CONDA_PREFIX")

    if conda_prefix:
        # If we're in a Conda environment
        activate_path = os.path.join(conda_prefix, "Scripts", "activate.bat")
        content = f"""@echo off
call "{activate_path}"
start "" "{python_path}" -m memos.commands record
start "" "{python_path}" -m memos.commands serve
"""
    else:
        # If we're not in a Conda environment, use the original content
        content = f"""@echo off
start "" "{python_path}" -m memos.commands record
start "" "{python_path}" -m memos.commands serve
"""

    bat_path = memos_dir / "launch.bat"
    with open(bat_path, "w") as f:
        f.write(content)
    return bat_path


def generate_launch_sh():
    memos_dir = get_memos_dir()
    python_path = get_python_path()
    content = f"""#!/bin/bash
# activate current python environment
if [ -f "$(dirname "$python_path")/activate" ]; then
    source "$(dirname "$python_path")/activate"
fi

# run memos record
{python_path} -m memos.commands record &

# run memos serve
{python_path} -m memos.commands serve &

# wait for all background processes
wait
"""
    launch_sh_path = memos_dir / "launch.sh"
    with open(launch_sh_path, "w") as f:
        f.write(content)
    launch_sh_path.chmod(0o755)


def setup_windows_autostart(bat_path):
    import win32com.client

    startup_folder = (
        Path(os.getenv("APPDATA")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
    )
    shortcut_path = startup_folder / "Memos.lnk"

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(shortcut_path))
    shortcut.Targetpath = str(bat_path)
    shortcut.WorkingDirectory = str(bat_path.parent)
    shortcut.save()


def generate_plist():
    memos_dir = get_memos_dir()
    python_dir = os.path.dirname(get_python_path())
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.memos</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>{memos_dir}/launch.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/memos.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/memos.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{python_dir}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
"""
    plist_path = Path.home() / "Library/LaunchAgents/com.user.memos.plist"
    with open(plist_path, "w") as f:
        f.write(plist_content)
    return plist_path


def load_plist(plist_path):
    subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
    subprocess.run(["launchctl", "load", str(plist_path)], check=True)


def is_macos():
    return platform.system() == "Darwin"


def is_windows():
    return platform.system() == "Windows"


@app.command()
def enable():
    """Enable memos to run at startup"""
    if not sys.executable:
        typer.echo("Error: Unable to detect Python environment.")
        raise typer.Exit(code=1)

    memos_dir = get_memos_dir()
    memos_dir.mkdir(parents=True, exist_ok=True)

    if is_windows():
        bat_path = generate_windows_bat()
        typer.echo(f"Generated launch script at {bat_path}")
        setup_windows_autostart(bat_path)
        typer.echo("Created startup shortcut for Windows.")
    elif is_macos():
        launch_sh_path = generate_launch_sh()
        typer.echo(f"Generated launch script at {launch_sh_path}")
        plist_path = generate_plist()
        typer.echo(f"Generated plist file at {plist_path}")
        load_plist(plist_path)
        typer.echo("Loaded plist file. Memos will now run at startup.")
    else:
        typer.echo("Unsupported operating system.")


@app.command()
def disable():
    """Disable memos from running at startup"""
    if not is_macos():
        typer.echo("Error: This feature is only supported on macOS.")
        raise typer.Exit(code=1)

    plist_path = Path.home() / "Library/LaunchAgents/com.user.memos.plist"
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
        plist_path.unlink()
        typer.echo(
            "Unloaded and removed plist file. Memos will no longer run at startup."
        )
    else:
        typer.echo("Plist file does not exist. Memos is not set to run at startup.")


if __name__ == "__main__":
    app()
