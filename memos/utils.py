from PIL import Image
import piexif
from PIL.PngImagePlugin import PngInfo
import json


def write_image_metadata(image_path, metadata):
    img = Image.open(image_path)
    image_path_str = str(image_path)

    if image_path_str.lower().endswith((".jpg", ".jpeg", ".tiff", ".webp")):
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        exif_dict["0th"][piexif.ImageIFD.ImageDescription] = json.dumps(
            metadata
        ).encode("utf-8")
        exif_bytes = piexif.dump(exif_dict)
        img.save(image_path, exif=exif_bytes)
    elif image_path_str.lower().endswith(".png"):
        metadata_info = PngInfo()
        metadata_info.add_text("Description", json.dumps(metadata))
        img.save(image_path, "PNG", pnginfo=metadata_info)
    else:
        print(f"Skipping unsupported file format: {image_path_str}")


def get_image_metadata(image_path):
    img = Image.open(image_path)
    image_path_str = str(image_path)

    if image_path_str.lower().endswith((".jpg", ".jpeg", ".tiff", ".webp")):
        try:
            exif_dict = piexif.load(image_path_str)
            existing_description = exif_dict["0th"].get(
                piexif.ImageIFD.ImageDescription, b"{}"
            )
            return json.loads(existing_description.decode("utf-8"))
        except Exception as e:
            print(f"Error decoding EXIF metadata for {image_path_str}: {e}")
            return None
    elif image_path_str.lower().endswith(".png"):
        existing_description = img.info.get("Description", "{}")
        try:
            return json.loads(existing_description)
        except json.JSONDecodeError as e:
            print(f"Error decoding PNG metadata for {image_path_str}: {e}")
            return None
    else:
        print(f"Unsupported file format: {image_path_str}")
        return None
