import logging
import time
import os
import json
import argparse
import imagehash
from PIL import ImageGrab, Image
import win32gui
import win32process
import psutil
from memos.utils import write_image_metadata
import ctypes
from screeninfo import get_monitors

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

    os.makedirs(os.path.join(base_dir, date), exist_ok=True)
    worklog_path = os.path.join(base_dir, date, "worklog")

    with open(worklog_path, "a") as worklog:
        for monitor in get_monitors():
            safe_monitor_name = ''.join(c for c in monitor.name if c.isalnum() or c in ('_', '-'))
            logging.info(f"Processing monitor: {safe_monitor_name}")
            
            webp_filename = os.path.join(base_dir, date, f"screenshot-{timestamp}-of-{safe_monitor_name}.webp")
            
            img = ImageGrab.grab(bbox=(monitor.x, monitor.y, monitor.x + monitor.width, monitor.y + monitor.height))
            img = img.convert("RGB")
            current_hash = str(imagehash.phash(img))

            if safe_monitor_name in previous_hashes and imagehash.hex_to_hash(current_hash) - imagehash.hex_to_hash(previous_hashes[safe_monitor_name]) < threshold:
                logging.info(f"Screenshot for {safe_monitor_name} is similar to the previous one. Skipping.")
                worklog.write(f"{timestamp} - {safe_monitor_name} - Skipped (similar to previous)\n")
                continue

            previous_hashes[safe_monitor_name] = current_hash
            screen_sequences[safe_monitor_name] = screen_sequences.get(safe_monitor_name, 0) + 1

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

            screenshots.append(webp_filename)
            worklog.write(f"{timestamp} - {safe_monitor_name} - Saved\n")

    return screenshots

def is_screen_locked():
    user32 = ctypes.windll.User32
    return user32.GetForegroundWindow() == 0

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

def run_screen_recorder_once(args, base_dir, previous_hashes):
    if not is_screen_locked():
        date = time.strftime("%Y%m%d")
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        screen_sequences = load_screen_sequences(base_dir, date)
        screenshot_files = take_screenshot(
            base_dir, previous_hashes, args.threshold, screen_sequences, date, timestamp
        )
        for screenshot_file in screenshot_files:
            logging.info(f"Screenshot saved: {screenshot_file}")
        save_previous_hashes(base_dir, previous_hashes)
    else:
        logging.info("Screen is locked. Skipping screenshot.")

def run_screen_recorder(args, base_dir, previous_hashes):
    while True:
        try:
            if not is_screen_locked():
                date = time.strftime("%Y%m%d")
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                screen_sequences = load_screen_sequences(base_dir, date)
                screenshot_files = take_screenshot(
                    base_dir, previous_hashes, args.threshold, screen_sequences, date, timestamp
                )
                for screenshot_file in screenshot_files:
                    logging.info(f"Screenshot saved: {screenshot_file}")
            else:
                logging.info("Screen is locked. Skipping screenshot.")
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}. Skipping this iteration.")

        time.sleep(5)

def main():
    parser = argparse.ArgumentParser(description="Screen Recorder for Windows")
    parser.add_argument("--threshold", type=int, default=4, help="Threshold for image similarity")
    parser.add_argument("--base-dir", type=str, default="~/tmp", help="Base directory for screenshots")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    base_dir = os.path.expanduser(args.base_dir)
    previous_hashes = load_previous_hashes(base_dir)

    if args.once:
        run_screen_recorder_once(args, base_dir, previous_hashes)
    else:
        while True:
            try:
                run_screen_recorder(args, base_dir, previous_hashes)
            except Exception as e:
                logging.error(f"Critical error occurred, program will restart in 10 seconds: {str(e)}")
                time.sleep(10)



if __name__ == "__main__":
    main()