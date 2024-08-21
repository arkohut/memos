import argparse
import os
import subprocess
from PIL import Image
from multiprocessing import Pool, Manager
from tqdm import tqdm

from memos.utils import write_image_metadata, get_image_metadata

parser = argparse.ArgumentParser(description="Compress and save image(s) with metadata")
parser.add_argument("path", type=str, help="path to the directory or image file")
args = parser.parse_args()
input_path = args.path.rstrip("/")


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

        # call the function with the filename of the image
        # add_datetime_to_image(os.path.join(directory, filename), os.path.join(directory, filename))


def process_directory(directory):
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

            # Modify the ffmpeg command to support WebP
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

        # Compress and save all images after video generation
        for screen in screens:
            files = [
                f
                for f in os.listdir(directory)
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                and screen in f
            ]

            for frame, filename in enumerate(
                tqdm(sorted(files), desc=f"Compressing {screen} images", unit="file")
            ):
                compress_and_save_image(os.path.join(directory, filename), frame)

        # for filename in os.listdir(directory):
        #     if filename.endswith(('.jpg', '.png')):
        #         os.remove(os.path.join(directory, filename))


def main():
    if os.path.isdir(input_path):
        process_directory(input_path)
    elif os.path.isfile(input_path):
        compress_and_save_image(input_path, 0)
    else:
        print("Invalid path. Please provide a valid directory or file path.")


if __name__ == "__main__":
    main()
