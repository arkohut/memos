import json
import argparse
from .utils import get_image_metadata


def read_metadata(image_path):
    try:
        metadata = get_image_metadata(image_path)

        if metadata is None:
            print("No metadata found or unsupported file format.")
            return None

        return metadata if metadata else None

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Read metadata from a screenshot")
    parser.add_argument("image_path", type=str, help="Path to the screenshot image")
    args = parser.parse_args()

    metadata = read_metadata(args.image_path)
    if metadata is not None:
        print(json.dumps(metadata, indent=4))


if __name__ == "__main__":
    main()