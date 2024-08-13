import argparse
import json
import os
import glob
import subprocess
from PIL import Image
import piexif
from PIL.PngImagePlugin import PngInfo

from multiprocessing import Pool, Manager
from tqdm import tqdm

parser = argparse.ArgumentParser(description='Compress and save image(s) with metadata')
parser.add_argument('path', type=str, help='path to the directory or image file')
args = parser.parse_args()
input_path = args.path.rstrip('/')


def compress_and_save_image(image_path, order):
    # Open the image
    img = Image.open(image_path)
    
    if image_path.endswith(('.jpg', '.jpeg', '.tiff')):
        # Add order to the image metadata for JPEG/TIFF
        exif_dict = piexif.load(image_path)
        existing_description = exif_dict["0th"].get(piexif.ImageIFD.ImageDescription, b'{}')
        try:
            existing_data = json.loads(existing_description.decode('utf-8'))
        except json.JSONDecodeError:
            existing_data = {}
        existing_data["sequence"] = order
        existing_data["is_thumbnail"] = True
        updated_description = json.dumps(existing_data).encode('utf-8')
        exif_dict["0th"][piexif.ImageIFD.ImageDescription] = updated_description
        exif_bytes = piexif.dump(exif_dict)
    elif image_path.endswith('.png'):
        # Add order to the image metadata for PNG
        metadata = PngInfo()
        existing_description = img.info.get("Description", '{}')
        try:
            existing_data = json.loads(existing_description)
        except json.JSONDecodeError:
            existing_data = {}
        existing_data["sequence"] = order
        existing_data["is_thumbnail"] = True
        updated_description = json.dumps(existing_data)
        metadata.add_text("Description", updated_description)
    else:
        print(f"Skipping unsupported file format: {image_path}")
        return

    # Compress the image
    img = img.convert("RGB")
    if image_path.endswith('.png'):
        img.save(image_path, "PNG", optimize=True, pnginfo=metadata)
    else:
        img.save(image_path, "JPEG", quality=30)  # Lower quality for higher compression
    
    # Resize the image proportionally
    max_size = (960, 960)  # Define the maximum size for the thumbnail
    img.thumbnail(max_size)
    if image_path.endswith('.png'):
        img.save(image_path, "PNG", optimize=True, pnginfo=metadata)
    else:
        img.save(image_path, "JPEG", quality=30)  # Lower quality for higher compression
    
    if image_path.endswith(('.jpg', '.jpeg', '.tiff')):
        # Insert updated EXIF data for JPEG/TIFF
        piexif.insert(exif_bytes, image_path)
    
    return image_path


def process_image(args):
    filename, screens = args
    if filename.endswith(('.jpg', '.png')):  # consider files with .jpg or .png extension
        parts = filename.split('-of-')  # split the file name at the "-of-" string
        display_name = parts[-1].rsplit('.', 1)[0]  # get the last part and remove the extension
        screens.append(display_name)  # add the display name to the set of screens

        # call the function with the filename of the image
        # add_datetime_to_image(os.path.join(directory, filename), os.path.join(directory, filename))


def process_directory(directory):
    screens = []
    with Manager() as manager:
        screens = manager.list()
        with Pool(min(8, os.cpu_count())) as p:
            list(tqdm(p.imap(process_image, [(filename, screens) for filename in os.listdir(directory)]), total=len(os.listdir(directory))))

        screens = set(screens)
        print(screens)

        for screen in screens:
            # Check if there are jpg or png files for the screen
            jpg_files = [f for f in os.listdir(directory) if f.endswith('.jpg') and screen in f]
            png_files = [f for f in os.listdir(directory) if f.endswith('.png') and screen in f]

            if jpg_files:
                input_pattern = f"{directory}/*{screen}*.jpg"
                files = jpg_files
            elif png_files:
                input_pattern = f"{directory}/*{screen}*.png"
                files = png_files
            else:
                continue  # Skip if no matching files are found

            # Create the frames.txt file
            with open(f"{directory}/{screen}.frames.txt", 'w') as f:
                for frame, filename in enumerate(sorted(files)):
                    f.write(f"{frame},{filename}\n")

            # Define the command to run
            command = f"ffmpeg -y -framerate 15 -pattern_type glob -i '{input_pattern}' -c:v libx264 -pix_fmt yuv420p {directory}/{screen}.mp4"

            # Start the process
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

            # Print the output in real-time
            for line in process.stdout:
                print(line, end='')

        # Compress and save all images after video generation
        for screen in screens:
            jpg_pattern = f"{directory}/*{screen}*.jpg"
            png_pattern = f"{directory}/*{screen}*.png"
            
            for pattern in [jpg_pattern, png_pattern]:
                files = glob.glob(pattern)
                for order, input_path in enumerate(tqdm(files, desc=f"Compressing {screen} images", unit="file")):
                    compress_and_save_image(input_path, order)

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

if __name__ == '__main__':
    main()