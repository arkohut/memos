import piexif
import json
import argparse
from PIL import Image

def read_metadata(image_path):
    try:
        img = Image.open(image_path)
        exif_data = img.info.get('exif')
        if not exif_data:
            print("No EXIF metadata found.")
            return

        exif_dict = piexif.load(exif_data)
        metadata_json = exif_dict["0th"].get(piexif.ImageIFD.ImageDescription)
        if metadata_json:
            metadata = json.loads(metadata_json.decode())
            print("Metadata:", json.dumps(metadata, indent=4))
        else:
            print("No metadata found in the ImageDescription field.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Read metadata from a screenshot")
    parser.add_argument("image_path", type=str, help="Path to the screenshot image")
    args = parser.parse_args()

    read_metadata(args.image_path)

if __name__ == "__main__":
    main()