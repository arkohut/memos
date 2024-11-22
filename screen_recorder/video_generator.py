import argparse
import os
import subprocess
from PIL import Image
from multiprocessing import Pool, Manager
from tqdm import tqdm

from memos.utils import write_image_metadata, get_image_metadata


def compress_and_save_image(image_path, order):
    # Open the image
    img = Image.open(image_path)

    existing_metadata = get_image_metadata(image_path)
    existing_metadata["sequence"] = order
    existing_metadata["is_thumbnail"] = True

    # Compress the image
    img = img.convert("RGB")
    max_size = (960, 960)  # Define the maximum size for the thumbnail
    img.thumbnail(max_size)

    write_image_metadata(image_path, existing_metadata)

    if image_path.lower().endswith(".png"):
        img.save(image_path, "PNG", optimize=True)
    elif image_path.lower().endswith(".webp"):
        img.save(image_path, "WebP", quality=30)
    else:  # JPEG and TIFF
        img.save(image_path, "JPEG", quality=30)

    return image_path


def process_image(args):
    filename, screens = args
    if filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        parts = filename.split("-of-")
        display_name = parts[-1].rsplit(".", 1)[0]
        screens.append(display_name)


def process_directory(directory, compress=False):
    screens = []
    with Manager() as manager:
        screens = manager.list()
        with Pool(min(8, os.cpu_count())) as p:
            list(
                tqdm(
                    p.imap(
                        process_image,
                        [(filename, screens) for filename in os.listdir(directory)],
                    ),
                    total=len(os.listdir(directory)),
                )
            )

        screens = set(screens)
        print(screens)

        for screen in screens:
            # Check if there are jpg, png, or webp files for the screen
            jpg_files = [
                f
                for f in os.listdir(directory)
                if f.lower().endswith((".jpg", ".jpeg")) and screen in f
            ]
            png_files = [
                f
                for f in os.listdir(directory)
                if f.lower().endswith(".png") and screen in f
            ]
            webp_files = [
                f
                for f in os.listdir(directory)
                if f.lower().endswith(".webp") and screen in f
            ]

            if jpg_files:
                input_pattern = f"{directory}/*{screen}*.jpg"
                files = jpg_files
            elif png_files:
                input_pattern = f"{directory}/*{screen}*.png"
                files = png_files
            elif webp_files:
                input_pattern = f"{directory}/*{screen}*.webp"
                files = webp_files
            else:
                continue  # Skip if no matching files are found

            # Create the frames.txt file
            with open(f"{directory}/{screen}.frames.txt", "w") as f:
                for frame, filename in enumerate(sorted(files)):
                    f.write(f"{frame},{filename}\n")

            # Adjust the params to fit your quality or storage requirements
            # For example to get a smaller file size, you can use libx265 instead of libx264
            command = f"ffmpeg -y -framerate 15 -pattern_type glob -i '{input_pattern}' -c:v libx264 -pix_fmt yuv420p {directory}/{screen}.mp4"

            # Start the process
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            )

            # Print the output in real-time
            for line in process.stdout:
                print(line, end="")

        if compress:
            for screen in screens:
                files = [
                    f
                    for f in os.listdir(directory)
                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                    and screen in f
                ]

                for frame, filename in enumerate(
                    tqdm(
                        sorted(files), desc=f"Compressing {screen} images", unit="file"
                    )
                ):
                    compress_and_save_image(os.path.join(directory, filename), frame)


def main():
    parser = argparse.ArgumentParser(
        description="Generate videos from images and optionally compress them"
    )
    parser.add_argument("path", type=str, help="path to the directory or image file")
    parser.add_argument(
        "--compress", action="store_true", help="compress images after video generation"
    )
    args = parser.parse_args()

    input_path = args.path.rstrip("/")

    if os.path.isdir(input_path):
        process_directory(input_path, compress=args.compress)
    elif os.path.isfile(input_path):
        if args.compress:
            compress_and_save_image(input_path, 0)
        else:
            print("Skipping compression as --compress flag is not set")
    else:
        print("Invalid path. Please provide a valid directory or file path.")


if __name__ == "__main__":
    main()
