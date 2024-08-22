import logging
import datetime
import time
import os
import json
import argparse
import imagehash
from PIL import Image
import win32gui
import win32process
import psutil
from mss import mss
from memos.utils import write_image_metadata
import win32api
import pywintypes
import ctypes
import ctypes.wintypes
from screeninfo import get_monitors

# 在文件开头添加日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_monitor_info():
    return {monitor.name: monitor for monitor in get_monitors()}

def get_active_window_info():
    try:
        window = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(window)
        app_name = psutil.Process(pid).name()
        window_title = win32gui.GetWindowText(window)
        return app_name, window_title
    except:
        return "", ""

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

def take_screenshot(base_dir, previous_hashes, threshold, screen_sequences, date, timestamp):
    screenshots = []
    app_name, window_title = get_active_window_info()

    # Create date directory
    os.makedirs(os.path.join(base_dir, date), exist_ok=True)
    worklog_path = os.path.join(base_dir, date, "worklog")

    monitor_infos = get_monitor_info()

    # Open worklog file
    with open(worklog_path, "a") as worklog:
        with mss() as sct:
            for i, monitor in enumerate(sct.monitors[1:], 1):  # Skip the first full-screen monitor
                monitor_name = monitor_infos.get(f"\\\\.\\DISPLAY{i}", f"screen_{i}").name
                safe_monitor_name = ''.join(c for c in monitor_name if c.isalnum() or c in ('_', '-'))
                logging.info(f"Processing monitor: {safe_monitor_name}")  # Debug output
                
                jpeg_filename = os.path.join(base_dir, date, f"screenshot-{timestamp}-of-{safe_monitor_name}.jpg")
                
                screen = sct.grab(monitor)
                img = Image.frombytes("RGB", screen.size, screen.bgra, "raw", "BGRX")
                
                # Calculate hash of current screenshot
                current_hash = imagehash.phash(img)

                # Check if current screenshot is similar to the previous one
                if safe_monitor_name in previous_hashes and current_hash - previous_hashes[safe_monitor_name] < threshold:
                    logging.info(f"Screenshot for {safe_monitor_name} is similar to the previous one. Skipping.")
                    worklog.write(
                        f"{timestamp} - {safe_monitor_name} - Skipped (similar to previous)\n"
                    )
                    continue

                # Update previous screenshot hash
                previous_hashes[safe_monitor_name] = current_hash

                # Update sequence number
                screen_sequences[safe_monitor_name] = screen_sequences.get(safe_monitor_name, 0) + 1

                # Prepare metadata
                metadata = {
                    "timestamp": timestamp,
                    "active_app": app_name,
                    "active_window": window_title,
                    "screen_name": safe_monitor_name,
                    "sequence": screen_sequences[safe_monitor_name],  # Add sequence number to metadata
                }

                # Save image and write metadata
                img.save(jpeg_filename, format="JPEG", quality=85)
                write_image_metadata(jpeg_filename, metadata)
                save_screen_sequences(base_dir, screen_sequences, date)

                screenshots.append(jpeg_filename)
                # Record successful screenshot
                worklog.write(f"{timestamp} - {safe_monitor_name} - Saved\n")

    return screenshots

def is_screen_locked():
    import ctypes
    user32 = ctypes.windll.User32
    return user32.GetForegroundWindow() == 0

def main():
    parser = argparse.ArgumentParser(description="Screen Recorder for Windows")
    parser.add_argument(
        "--threshold", type=int, default=4, help="Threshold for image similarity"
    )
    parser.add_argument(
        "--base-dir", type=str, default="~/tmp", help="Base directory for screenshots"
    )
    args = parser.parse_args()

    base_dir = os.path.expanduser(args.base_dir)
    previous_hashes = {}

    while True:
        try:
            if not is_screen_locked():
                date = time.strftime("%Y%m%d")
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                screen_sequences = load_screen_sequences(base_dir, date)
                screenshot_files = take_screenshot(
                    base_dir,
                    previous_hashes,
                    args.threshold,
                    screen_sequences,
                    date,
                    timestamp,
                )
                for screenshot_file in screenshot_files:
                    logging.info(f"Screenshot taken: {screenshot_file}")
            else:
                logging.info("Screen is locked. Skipping screenshot.")
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}. Skipping this iteration.")

        time.sleep(5)

if __name__ == "__main__":
    main()