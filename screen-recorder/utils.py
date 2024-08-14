from PIL import Image
import piexif
from PIL.PngImagePlugin import PngInfo
import json


def write_image_metadata(image_path, metadata):
    img = Image.open(image_path)

    if image_path.lower().endswith((".jpg", ".jpeg", ".tiff")):
        exif_dict = piexif.load(image_path)
        updated_description = json.dumps(metadata).encode("utf-8")
        exif_dict["0th"][piexif.ImageIFD.ImageDescription] = updated_description
        exif_bytes = piexif.dump(exif_dict)
        img.save(image_path, exif=exif_bytes)
    elif image_path.lower().endswith(".png"):
        metadata_info = PngInfo()
        metadata_info.add_text("Description", json.dumps(metadata))
        img.save(image_path, "PNG", pnginfo=metadata_info)
    else:
        print(f"Skipping unsupported file format: {image_path}")


def get_image_metadata(image_path):
    img = Image.open(image_path)

    if image_path.lower().endswith((".jpg", ".jpeg", ".tiff")):
        exif_dict = piexif.load(image_path)
        existing_description = exif_dict["0th"].get(
            piexif.ImageIFD.ImageDescription, b"{}"
        )
        try:
            return json.loads(existing_description.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
    elif image_path.lower().endswith(".png"):
        existing_description = img.info.get("Description", "{}")
        try:
            return json.loads(existing_description)
        except json.JSONDecodeError:
            return {}
    else:
        print(f"Unsupported file format: {image_path}")
        return None
