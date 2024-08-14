import argparse
import json
import os
from PIL import Image
import piexif
from PIL.PngImagePlugin import PngInfo
from tqdm import tqdm
from .utils import get_image_metadata, write_image_metadata


def add_sequence_to_image(image_path, order):
    metadata = get_image_metadata(image_path)
    if metadata is not None:
        metadata["sequence"] = order
        write_image_metadata(image_path, metadata)
        return image_path
    return None


def get_screen_name(filename):
    parts = filename.split("-of-")
    return parts[-1].rsplit(".", 1)[0]


def process_directory(directory):
    image_files = [
        f
        for f in os.listdir(directory)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".tiff"))
    ]

    # Group images by screen
    screens = {}
    for filename in image_files:
        screen = get_screen_name(filename)
        if screen not in screens:
            screens[screen] = []
        screens[screen].append(filename)

    # Process each screen
    for screen, files in screens.items():
        print(f"Processing screen: {screen}")
        for order, filename in enumerate(
            tqdm(sorted(files), desc=f"Adding sequence to {screen}", unit="file")
        ):
            image_path = os.path.join(directory, filename)
            add_sequence_to_image(image_path, order)


def main():
    parser = argparse.ArgumentParser(
        description="Add sequence metadata to image(s) grouped by screen"
    )
    parser.add_argument("path", type=str, help="path to the directory or image file")
    args = parser.parse_args()
    input_path = args.path.rstrip("/")

    if os.path.isdir(input_path):
        process_directory(input_path)
    elif os.path.isfile(input_path):
        screen = get_screen_name(os.path.basename(input_path))
        print(f"Processing single file for screen: {screen}")
        add_sequence_to_image(input_path, 0)
    else:
        print("Invalid path. Please provide a valid directory or file path.")


if __name__ == "__main__":
    main()
