import piexif
import json
import argparse
from PIL import Image, PngImagePlugin


def read_metadata(image_path):
    try:
        img = Image.open(image_path)
        exif_data = img.info.get("exif")
        png_info = img.info if isinstance(img, PngImagePlugin.PngImageFile) else None

        if not exif_data and not png_info:
            print("No EXIF or PNG metadata found.")
            return None

        metadata = {}

        if exif_data:
            exif_dict = piexif.load(exif_data)
            metadata_json = exif_dict["0th"].get(piexif.ImageIFD.ImageDescription)
            if metadata_json:
                metadata["exif"] = json.loads(metadata_json.decode())
                print("EXIF Metadata:", json.dumps(metadata["exif"], indent=4))
            else:
                print("No metadata found in the ImageDescription field of EXIF.")

        if png_info:
            metadata_json = png_info.get("Description")
            if metadata_json:
                metadata["png"] = json.loads(metadata_json)
                print("PNG Metadata:", json.dumps(metadata["png"], indent=4))
            else:
                print("No metadata found in the Description field of PNG.")

        return metadata if metadata else None

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Read metadata from a screenshot")
    parser.add_argument("image_path", type=str, help="Path to the screenshot image")
    args = parser.parse_args()

    read_metadata(args.image_path)


if __name__ == "__main__":
    main()
