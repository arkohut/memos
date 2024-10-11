import os
import time
import sys
import argparse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 定义图片文件扩展名
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp")


class ImageHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_modified = {}

    def is_image_file(self, path):
        return path.lower().endswith(IMAGE_EXTENSIONS)

    def is_temp_file(self, path):
        filename = os.path.basename(path)
        return (
            filename.startswith(".")
            or filename.startswith("tmp")
            or filename.startswith("temp")
        )

    def handle_event(self, event):
        if (
            not event.is_directory
            and self.is_image_file(event.src_path)
            and not self.is_temp_file(event.src_path)
        ):
            current_time = time.time()
            last_modified_time = self.last_modified.get(event.src_path, 0)
            if current_time - last_modified_time > 1:  # 防止重复触发
                self.last_modified[event.src_path] = current_time
                return True
        return False

    def on_modified(self, event):
        if self.handle_event(event):
            print(f"Image file modified: {event.src_path}")

    def on_created(self, event):
        if self.handle_event(event):
            print(f"Image file created: {event.src_path}")

    def on_deleted(self, event):
        if self.handle_event(event):
            print(f"Image file deleted: {event.src_path}")


def watch_folders(folders, recursive):
    event_handler = ImageHandler()
    observer = Observer()

    # 监听多个文件夹
    for folder in folders:
        observer.schedule(event_handler, folder, recursive=recursive)

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


# main 函数保持不变
def main():
    parser = argparse.ArgumentParser(
        description="Watch for image file changes in specified folders."
    )
    parser.add_argument(
        "folders",
        metavar="FOLDER",
        type=str,
        nargs="+",
        help="One or more folders to watch for image file changes.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Watch folders recursively (may impact performance for large directories).",
    )

    args = parser.parse_args()

    # 确认所有提供的目录都存在
    for folder in args.folders:
        if not os.path.isdir(folder):
            print(f"Error: {folder} is not a valid directory.")
            sys.exit(1)

    watch_folders(args.folders, args.recursive)


if __name__ == "__main__":
    main()