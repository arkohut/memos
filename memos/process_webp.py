from pathlib import Path
from PIL import Image
import piexif
import json
from memos.utils import write_image_metadata, get_image_metadata
from tqdm import tqdm

def convert_webp_metadata(directory):
    webp_files = list(Path(directory).glob('**/*.webp'))

    for webp_file in tqdm(webp_files, desc="Converting WebP metadata", unit="file"):
        try:
            # Try to get metadata using the new method
            new_metadata = get_image_metadata(webp_file)

            if new_metadata:
                tqdm.write(f"Skipping {webp_file}: Already in new format")
                continue

            # If new method fails, try to get old metadata
            img = Image.open(webp_file)
            old_metadata = img.info.get("exif", None)

            if old_metadata is None:
                tqdm.write(f"Skipping {webp_file}: No metadata found")
                continue

            if isinstance(old_metadata, bytes):
                try:
                    old_metadata = old_metadata.decode('utf-8')
                except UnicodeDecodeError:
                    tqdm.write(f"Skipping {webp_file}: Unable to decode metadata")
                    continue

            try:
                metadata = json.loads(old_metadata)
            except json.JSONDecodeError:
                tqdm.write(f"Skipping {webp_file}: Invalid metadata format")
                continue

            # Convert to new format
            write_image_metadata(webp_file, metadata)
            tqdm.write(f"Converted metadata for {webp_file}")

        except Exception as e:
            tqdm.write(f"Error processing {webp_file}: {str(e)}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python convert_webp_metadata.py <directory>")
        sys.exit(1)

    directory = sys.argv[1]
    convert_webp_metadata(directory)