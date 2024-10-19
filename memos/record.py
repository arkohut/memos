import json
import os
import time
import logging
import platform
import subprocess
import argparse
from PIL import Image
import imagehash
from memos.utils import write_image_metadata
import ctypes
from mss import mss
from pathlib import Path
from memos.config import settings

# Import platform-specific modules
if platform.system() == "Windows":
    import win32gui
    import win32process
    import psutil
elif platform.system() == "Darwin":
    from AppKit import NSWorkspace
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        CGSessionCopyCurrentDictionary,
    )

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# Functions moved from common.py
def load_screen_sequences(base_dir, date):
    try:
        with open(os.path.join(base_dir, date, ".screen_sequences"), "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_screen_sequences(base_dir, screen_sequences, date):
    with open(os.path.join(base_dir, date, ".screen_sequences"), "w") as f:
        json.dump(screen_sequences, f)
        f.flush()
        os.fsync(f.fileno())


def load_previous_hashes(base_dir):
    date = time.strftime("%Y%m%d")
    hash_file = os.path.join(base_dir, date, ".previous_hashes")
    try:
        with open(hash_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_previous_hashes(base_dir, previous_hashes):
    date = time.strftime("%Y%m%d")
    hash_file = os.path.join(base_dir, date, ".previous_hashes")
    os.makedirs(os.path.dirname(hash_file), exist_ok=True)
    with open(hash_file, "w") as f:
        json.dump(previous_hashes, f)


def get_active_window_info_darwin():
    active_app = NSWorkspace.sharedWorkspace().activeApplication()
    app_name = active_app["NSApplicationName"]
    app_pid = active_app["NSApplicationProcessIdentifier"]

    windows = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly, kCGNullWindowID
    )
    for window in windows:
        if window["kCGWindowOwnerPID"] == app_pid:
            window_title = window.get("kCGWindowName", "")
            if window_title:
                return app_name, window_title

    return app_name, ""  # 如果没有找到窗口标题，则返回空字符串作为标题


def get_active_window_info_windows():
    try:
        window = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(window)
        app_name = psutil.Process(pid).name()
        window_title = win32gui.GetWindowText(window)
        return app_name, window_title
    except:
        return "", ""


def get_active_window_info():
    if platform.system() == "Darwin":
        return get_active_window_info_darwin()
    elif platform.system() == "Windows":
        return get_active_window_info_windows()


def take_screenshot_macos(
    base_dir,
    previous_hashes,
    threshold,
    screen_sequences,
    date,
    timestamp,
    app_name,
    window_title,
):
    screenshots = []
    result = subprocess.check_output(["system_profiler", "SPDisplaysDataType", "-json"])
    displays_info = json.loads(result)["SPDisplaysDataType"][0]["spdisplays_ndrvs"]
    screen_names = {}

    for display_index, display_info in enumerate(displays_info):
        base_screen_name = display_info["_name"].replace(" ", "_").lower()
        if base_screen_name in screen_names:
            screen_names[base_screen_name] += 1
            screen_name = f"{base_screen_name}_{screen_names[base_screen_name]}"
        else:
            screen_names[base_screen_name] = 1
            screen_name = base_screen_name

        temp_filename = os.path.join(
            base_dir, date, f"temp_screenshot-{timestamp}-of-{screen_name}.png"
        )
        subprocess.run(
            ["screencapture", "-C", "-x", "-D", str(display_index + 1), temp_filename]
        )

        with Image.open(temp_filename) as img:
            img = img.convert("RGB")
            current_hash = str(imagehash.phash(img))

            if (
                screen_name in previous_hashes
                and imagehash.hex_to_hash(current_hash)
                - imagehash.hex_to_hash(previous_hashes[screen_name])
                < threshold
            ):
                logging.info(
                    f"Screenshot for {screen_name} is similar to the previous one. Skipping."
                )
                os.remove(temp_filename)
                yield screen_name, None, "Skipped (similar to previous)"
                continue

            previous_hashes[screen_name] = current_hash
            screen_sequences[screen_name] = screen_sequences.get(screen_name, 0) + 1

            metadata = {
                "timestamp": timestamp,
                "active_app": app_name,
                "active_window": window_title,
                "screen_name": screen_name,
                "sequence": screen_sequences[screen_name],
            }

            # Save as WebP with metadata included
            webp_filename = os.path.join(
                base_dir, date, f"screenshot-{timestamp}-of-{screen_name}.webp"
            )
            img.save(webp_filename, format="WebP", quality=85)
            write_image_metadata(webp_filename, metadata)

            save_screen_sequences(base_dir, screen_sequences, date)

        os.remove(temp_filename)
        screenshots.append(webp_filename)
        yield screen_name, webp_filename, "Saved"


def take_screenshot_windows(
    base_dir,
    previous_hashes,
    threshold,
    screen_sequences,
    date,
    timestamp,
    app_name,
    window_title,
):
    with mss() as sct:
        for i, monitor in enumerate(
            sct.monitors[1:], 1
        ):  # Skip the first monitor (entire screen)
            safe_monitor_name = f"monitor_{i}"
            logging.info(f"Processing monitor: {safe_monitor_name}")

            webp_filename = os.path.join(
                base_dir, date, f"screenshot-{timestamp}-of-{safe_monitor_name}.webp"
            )

            img = sct.grab(monitor)
            img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            current_hash = str(imagehash.phash(img))

            if (
                safe_monitor_name in previous_hashes
                and imagehash.hex_to_hash(current_hash)
                - imagehash.hex_to_hash(previous_hashes[safe_monitor_name])
                < threshold
            ):
                logging.info(
                    f"Screenshot for {safe_monitor_name} is similar to the previous one. Skipping."
                )
                yield safe_monitor_name, None, "Skipped (similar to previous)"
                continue

            previous_hashes[safe_monitor_name] = current_hash
            screen_sequences[safe_monitor_name] = (
                screen_sequences.get(safe_monitor_name, 0) + 1
            )

            metadata = {
                "timestamp": timestamp,
                "active_app": app_name,
                "active_window": window_title,
                "screen_name": safe_monitor_name,
                "sequence": screen_sequences[safe_monitor_name],
            }

            img.save(webp_filename, format="WebP", quality=85)
            write_image_metadata(webp_filename, metadata)
            save_screen_sequences(base_dir, screen_sequences, date)

            yield safe_monitor_name, webp_filename, "Saved"


def take_screenshot(
    base_dir, previous_hashes, threshold, screen_sequences, date, timestamp
):
    app_name, window_title = get_active_window_info()
    os.makedirs(os.path.join(base_dir, date), exist_ok=True)
    worklog_path = os.path.join(base_dir, date, "worklog")

    with open(worklog_path, "a") as worklog:
        if platform.system() == "Darwin":
            screenshot_generator = take_screenshot_macos(
                base_dir,
                previous_hashes,
                threshold,
                screen_sequences,
                date,
                timestamp,
                app_name,
                window_title,
            )
        elif platform.system() == "Windows":
            screenshot_generator = take_screenshot_windows(
                base_dir,
                previous_hashes,
                threshold,
                screen_sequences,
                date,
                timestamp,
                app_name,
                window_title,
            )
        else:
            raise NotImplementedError(
                f"Unsupported operating system: {platform.system()}"
            )

        screenshots = []
        for screen_name, screenshot_file, status in screenshot_generator:
            worklog.write(f"{timestamp} - {screen_name} - {status}\n")
            if screenshot_file:
                screenshots.append(screenshot_file)

    return screenshots


def is_screen_locked():
    if platform.system() == "Darwin":
        session_dict = CGSessionCopyCurrentDictionary()
        if session_dict:
            screen_locked = session_dict.get("CGSSessionScreenIsLocked", 0)
            return bool(screen_locked)
        return False
    elif platform.system() == "Windows":
        user32 = ctypes.windll.User32
        return user32.GetForegroundWindow() == 0


def run_screen_recorder_once(threshold, base_dir, previous_hashes):
    if not is_screen_locked():
        date = time.strftime("%Y%m%d")
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        screen_sequences = load_screen_sequences(base_dir, date)
        screenshot_files = take_screenshot(
            base_dir, previous_hashes, threshold, screen_sequences, date, timestamp
        )
        for screenshot_file in screenshot_files:
            logging.info(f"Screenshot saved: {screenshot_file}")
        save_previous_hashes(base_dir, previous_hashes)
    else:
        logging.info("Screen is locked. Skipping screenshot.")


def run_screen_recorder(threshold, base_dir, previous_hashes):
    while True:
        try:
            if not is_screen_locked():
                date = time.strftime("%Y%m%d")
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                screen_sequences = load_screen_sequences(base_dir, date)
                screenshot_files = take_screenshot(
                    base_dir,
                    previous_hashes,
                    threshold,
                    screen_sequences,
                    date,
                    timestamp,
                )
                for screenshot_file in screenshot_files:
                    logging.info(f"Screenshot saved: {screenshot_file}")
            else:
                logging.info("Screen is locked. Skipping screenshot.")
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}. Skipping this iteration.")

        time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="Screen Recorder")
    parser.add_argument(
        "--threshold", type=int, default=4, help="Threshold for image similarity"
    )
    parser.add_argument("--base-dir", type=str, help="Base directory for screenshots")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    base_dir = (
        os.path.expanduser(args.base_dir) if args.base_dir else settings.resolved_screenshots_dir
    )
    previous_hashes = load_previous_hashes(base_dir)

    if args.once:
        run_screen_recorder_once(args, base_dir, previous_hashes)
    else:
        while True:
            try:
                run_screen_recorder(args, base_dir, previous_hashes)
            except Exception as e:
                logging.error(
                    f"Critical error occurred, program will restart in 10 seconds: {str(e)}"
                )
                time.sleep(10)


if __name__ == "__main__":
    main()
