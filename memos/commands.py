# Standard library imports
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List

# Third-party imports
import httpx
import typer

# Local imports
from .config import settings, display_config

import sys
import subprocess
import platform

from .cmds.plugin import plugin_app
from .cmds.library import lib_app

import psutil
import signal
from tabulate import tabulate


app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})

BASE_URL = settings.server_endpoint

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Set the logging level to WARNING or higher
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Optionally, you can set the logging level for specific libraries
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("typer").setLevel(logging.ERROR)


def check_server_health():
    """Check if the server is running and healthy."""
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except httpx.RequestException:
        return False


def callback(ctx: typer.Context):
    """Callback to check server health before running any command."""
    # List of commands that require the server to be running
    server_dependent_commands = [
        "scan",
        "reindex",
        "watch",
        "ls",
        "create",
        "add-folder",
        "show",
        "sync",
        "bind",
        "unbind",
    ]

    if ctx.invoked_subcommand in server_dependent_commands:
        if not check_server_health():
            typer.echo("Error: Server is not running. Please start the server first.")
            raise typer.Exit(code=1)


app.add_typer(plugin_app, name="plugin")
app.add_typer(lib_app, name="lib", callback=callback)


@app.command()
def serve():
    """Run the server after initializing if necessary."""
    from .models import init_database

    db_success = init_database()
    if db_success:
        from .server import run_server

        run_server()
    else:
        print("Server initialization failed. Unable to start the server.")


@app.command()
def init():
    """Initialize the database."""
    from .models import init_database

    db_success = init_database()
    if db_success:
        print("Initialization completed successfully.")
    else:
        print("Initialization failed. Please check the error messages above.")


def get_or_create_default_library():
    """
    Get the default library or create it if it doesn't exist.
    Ensure the library has at least one folder.
    """
    from .cmds.plugin import bind

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
        screenshots_dir = Path(settings.resolved_screenshots_dir).resolve()
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
def scan_default_library(
    force: bool = typer.Option(True, "--force", help="Force update all indexes"),
    path: str = typer.Argument(None, help="Path to scan within the library"),
    plugins: List[int] = typer.Option(None, "--plugin", "-p"),
    folders: List[int] = typer.Option(None, "--folder", "-f"),
    batch_size: int = typer.Option(
        1, "--batch-size", "-bs", help="Batch size for processing files"
    ),
):
    """
    Scan the screenshots directory and add it to the library if empty.
    """
    from .cmds.library import scan

    default_library = get_or_create_default_library()
    if not default_library:
        return

    print(f"Scanning library: {default_library['name']}")
    scan(
        default_library["id"],
        path=path,
        plugins=plugins,
        folders=folders,
        force=force,
        batch_size=batch_size,
    )


@app.command("reindex")
def reindex_default_library(
    force: bool = typer.Option(
        False, "--force", help="Force recreate FTS and vector tables before reindexing"
    ),
    batch_size: int = typer.Option(
        1, "--batch-size", "-bs", help="Batch size for processing files"
    ),
):
    """
    Reindex the default library for memos.
    """
    from .cmds.library import reindex

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

    # Reindex the library
    print(f"Reindexing library: {default_library['name']}")
    reindex(default_library["id"], force=force, folders=None, batch_size=batch_size)


@app.command("record")
def record(
    threshold: int = typer.Option(4, help="Threshold for image similarity"),
    base_dir: str = typer.Option(None, help="Base directory for screenshots"),
    once: bool = typer.Option(False, help="Run once and exit"),
):
    """
    Record screenshots of the screen.
    """
    from .record import (
        run_screen_recorder_once,
        run_screen_recorder,
        load_previous_hashes,
    )

    base_dir = (
        os.path.expanduser(base_dir) if base_dir else settings.resolved_screenshots_dir
    )
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
        10, "--window-size", "-ws", help="Window size for rate calculation"
    ),
    sparsity_factor: float = typer.Option(
        3.0, "--sparsity-factor", "-sf", help="Sparsity factor for file processing"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
):
    """
    Watch the default library for file changes and sync automatically.
    """
    from .cmds.library import watch

    default_library = get_or_create_default_library()
    if not default_library:
        return

    watch(
        default_library["id"],
        folders=None,
        window_size=window_size,
        sparsity_factor=sparsity_factor,
        verbose=verbose,
    )


def get_python_path():
    return sys.executable


def generate_windows_bat():
    memos_dir = settings.resolved_base_dir
    python_path = get_python_path()
    pythonw_path = python_path.replace("python.exe", "pythonw.exe")
    conda_prefix = os.environ.get("CONDA_PREFIX")
    log_dir = memos_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    if conda_prefix:
        # If we're in a Conda environment
        activate_path = os.path.join(conda_prefix, "Scripts", "activate.bat")
        content = f"""@echo off
call "{activate_path}"
start /B "" "{pythonw_path}" -m memos.commands record > "{log_dir / 'record.log'}" 2>&1
start /B "" "{pythonw_path}" -m memos.commands serve > "{log_dir / 'serve.log'}" 2>&1
timeout /t 15 /nobreak >nul
start /B "" "{pythonw_path}" -m memos.commands watch > "{log_dir / 'watch.log'}" 2>&1
"""
    else:
        # If we're not in a Conda environment
        content = f"""@echo off
start /B "" "{pythonw_path}" -m memos.commands record > "{log_dir / 'record.log'}" 2>&1
start /B "" "{pythonw_path}" -m memos.commands serve > "{log_dir / 'serve.log'}" 2>&1
timeout /t 15 /nobreak >nul
start /B "" "{pythonw_path}" -m memos.commands watch > "{log_dir / 'watch.log'}" 2>&1
"""

    bat_path = memos_dir / "launch.bat"
    with open(bat_path, "w") as f:
        f.write(content)
    return bat_path


def generate_launch_sh():
    memos_dir = settings.resolved_base_dir
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

# wait for 15 seconds before starting memos watch
sleep 15

# run memos watch
{python_path} -m memos.commands watch &

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
    shortcut.WindowStyle = 7  # Minimized
    shortcut.save()


def generate_plist():
    memos_dir = settings.resolved_base_dir
    python_dir = os.path.dirname(get_python_path())
    log_dir = memos_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

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
    <key>StandardOutPath</key>
    <string>{log_dir}/memos.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/memos.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{python_dir}:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
"""
    plist_dir = Path.home() / "Library/LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / "com.user.memos.plist"
    with open(plist_path, "w") as f:
        f.write(plist_content)
    return plist_path


def is_service_loaded(service_name):
    try:
        result = subprocess.run(
            ["launchctl", "list", service_name],
            capture_output=True,
            text=True,
            check=True,
        )
        return "0" in result.stdout
    except subprocess.CalledProcessError:
        return False


def load_plist(plist_path):
    service_name = "com.user.memos"

    if is_service_loaded(service_name):
        subprocess.run(["launchctl", "unload", str(plist_path)], check=False)

    subprocess.run(["launchctl", "load", str(plist_path)], check=True)


def is_macos():
    return platform.system() == "Darwin"


def is_windows():
    return platform.system() == "Windows"


def remove_windows_autostart():
    startup_folder = (
        Path(os.getenv("APPDATA")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
    )
    shortcut_path = startup_folder / "Memos.lnk"

    if shortcut_path.exists():
        shortcut_path.unlink()
        return True
    return False


def generate_systemd_service():
    """Generate systemd service file for Linux."""
    memos_dir = settings.resolved_base_dir
    python_path = get_python_path()
    log_dir = memos_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    service_content = f"""[Unit]
Description=Memos Service
After=network.target

[Service]
Type=simple
Environment="PATH={os.environ['PATH']}"
ExecStart={python_path} -m memos.commands record
ExecStart={python_path} -m memos.commands serve
ExecStartPre=/bin/sleep 15
ExecStart={python_path} -m memos.commands watch
Restart=always
User={os.getenv('USER')}
StandardOutput=append:{log_dir}/memos.log
StandardError=append:{log_dir}/memos.error.log

[Install]
WantedBy=default.target
"""

    service_path = Path.home() / ".config/systemd/user"
    service_path.mkdir(parents=True, exist_ok=True)
    service_file = service_path / "memos.service"
    with open(service_file, "w") as f:
        f.write(service_content)
    return service_file


def is_linux():
    return platform.system() == "Linux"


@app.command()
def enable():
    """Enable memos to run at startup (without starting it immediately)"""
    if not sys.executable:
        typer.echo("Error: Unable to detect Python environment.")
        raise typer.Exit(code=1)

    memos_dir = settings.resolved_base_dir
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
        typer.echo("Loaded plist file. Memos will run at next startup.")
    elif is_linux():
        service_file = generate_systemd_service()
        typer.echo(f"Generated systemd service file at {service_file}")
        # Enable and start the service
        subprocess.run(["systemctl", "--user", "enable", "memos.service"], check=True)
        typer.echo("Enabled memos systemd service for current user.")
    else:
        typer.echo("Unsupported operating system.")


@app.command()
def disable():
    """Disable memos from running at startup"""
    if is_windows():
        if remove_windows_autostart():
            typer.echo("Removed Memos shortcut from startup folder.")
        else:
            typer.echo("Memos shortcut not found in startup folder.")
    elif is_macos():
        plist_path = Path.home() / "Library/LaunchAgents/com.user.memos.plist"
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], check=True)
            plist_path.unlink()
            typer.echo("Unloaded and removed plist file.")
        else:
            typer.echo("Plist file does not exist.")
    elif is_linux():
        service_file = Path.home() / ".config/systemd/user/memos.service"
        if service_file.exists():
            subprocess.run(
                ["systemctl", "--user", "disable", "memos.service"], check=True
            )
            subprocess.run(["systemctl", "--user", "stop", "memos.service"], check=True)
            service_file.unlink()
            typer.echo("Disabled and removed memos systemd service.")
        else:
            typer.echo("Systemd service file does not exist.")
    else:
        typer.echo("Unsupported operating system.")


@app.command()
def start():
    """Start all Memos processes"""
    memos_dir = settings.resolved_base_dir

    if is_windows():
        bat_path = memos_dir / "launch.bat"
        if not bat_path.exists():
            typer.echo("Launch script not found. Please run 'memos enable' first.")
            return
        try:
            subprocess.Popen(
                [str(bat_path)], shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            typer.echo("Started Memos processes.")
        except Exception as e:
            typer.echo(f"Failed to start Memos processes: {str(e)}")
    elif is_macos():
        service_name = "com.user.memos"
        subprocess.run(["launchctl", "start", service_name], check=True)
        typer.echo("Started Memos processes.")
    elif is_linux():
        try:
            subprocess.run(
                ["systemctl", "--user", "start", "memos.service"], check=True
            )
            typer.echo("Started Memos processes.")
        except subprocess.CalledProcessError as e:
            typer.echo(f"Failed to start Memos processes: {str(e)}")
    else:
        typer.echo("Unsupported operating system.")


@app.command()
def stop():
    """Stop all running Memos processes"""
    if is_windows():
        services = ["serve", "watch", "record"]
        stopped = False
        for service in services:
            processes = [
                p
                for p in psutil.process_iter(["pid", "name", "cmdline"])
                if "python" in p.info["name"].lower()
                and p.info["cmdline"] is not None
                and "memos.commands" in p.info["cmdline"]
                and service in p.info["cmdline"]
            ]

            for process in processes:
                try:
                    os.kill(process.info["pid"], signal.SIGTERM)
                    typer.echo(
                        f"Stopped {service} process (PID: {process.info['pid']})"
                    )
                    stopped = True
                except ProcessLookupError:
                    typer.echo(
                        f"Process {service} (PID: {process.info['pid']}) not found"
                    )
                except PermissionError:
                    typer.echo(
                        f"Permission denied to stop {service} process (PID: {process.info['pid']})"
                    )

        if not stopped:
            typer.echo("No running Memos processes found")
    elif is_macos():
        service_name = "com.user.memos"
        try:
            subprocess.run(["launchctl", "stop", service_name], check=True)
            typer.echo("Stopped Memos processes.")
        except subprocess.CalledProcessError:
            typer.echo("Failed to stop Memos processes. They may not be running.")
    elif is_linux():
        try:
            subprocess.run(["systemctl", "--user", "stop", "memos.service"], check=True)
            typer.echo("Stopped Memos processes.")
        except subprocess.CalledProcessError:
            # Fallback to manual process killing if systemd service fails
            services = ["serve", "watch", "record"]
            stopped = False
            for service in services:
                try:
                    output = subprocess.check_output(
                        ["pgrep", "-f", f"memos.commands {service}"]
                    )
                    pids = output.decode().strip().split()
                    for pid in pids:
                        os.kill(int(pid), signal.SIGTERM)
                        typer.echo(f"Stopped {service} process (PID: {pid})")
                        stopped = True
                except (subprocess.CalledProcessError, ProcessLookupError):
                    continue

            if not stopped:
                typer.echo("No running Memos processes found")
    else:
        typer.echo("Unsupported operating system.")


@app.command()
def ps():
    """Show the status of Memos processes"""
    services = ["serve", "watch", "record"]
    table_data = []

    for service in services:
        processes = [
            p
            for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"])
            if "python" in p.info["name"].lower()
            and p.info["cmdline"] is not None
            and "memos.commands" in p.info["cmdline"]
            and service in p.info["cmdline"]
        ]

        if processes:
            for process in processes:
                create_time = datetime.fromtimestamp(
                    process.info["create_time"]
                ).strftime("%Y-%m-%d %H:%M:%S")
                running_time = str(
                    timedelta(seconds=int(time.time() - process.info["create_time"]))
                )
                table_data.append(
                    [service, "Running", process.info["pid"], create_time, running_time]
                )
        else:
            table_data.append([service, "Not Running", "-", "-", "-"])

    headers = ["Name", "Status", "PID", "Started At", "Running For"]
    typer.echo(tabulate(table_data, headers=headers, tablefmt="plain"))


@app.command()
def config():
    """Show current configuration settings"""
    display_config()


if __name__ == "__main__":
    app()
