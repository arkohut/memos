import logging
import time
import os
import json
import argparse
import platform
from screen_recorder.common import (
    load_screen_sequences,
    save_screen_sequences,
    load_previous_hashes,
    save_previous_hashes,
    take_screenshot,
    is_screen_locked,
)

# 在文件开头添加日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    parser = argparse.ArgumentParser(description="Screen Recorder")
    parser.add_argument(
        "--threshold", type=int, default=4, help="Threshold for image similarity"
    )
    parser.add_argument(
        "--base-dir", type=str, default="~/tmp", help="Base directory for screenshots"
    )
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