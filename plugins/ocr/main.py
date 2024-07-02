import httpx
import json

from fastapi import FastAPI, Request, HTTPException
from memos.schemas import Entity, MetadataType

from rapidocr_onnxruntime import RapidOCR, VisRes


engine = RapidOCR()
vis = VisRes()

METADATA_FIELD_NAME = "ocr_result"
PLUGIN_NAME = "ocr"


def predict(img_path):
    result, elapse = engine(img_path)
    if result is None:
        return None, None
    return [
        {"dt_boxes": item[0], "rec_txt": item[1], "score": item[2]} for item in result
    ], elapse


app = FastAPI()


@app.get("/")
async def read_root():
    return {"healthy": True}


@app.post("/")
async def ocr(entity: Entity, request: Request):
    if not entity.file_type_group == "image":
        return {METADATA_FIELD_NAME: "{}"}

    # Get the URL to patch the entity's metadata from the "Location" header
    location_url = request.headers.get("Location")
    if not location_url:
        raise HTTPException(status_code=400, detail="Location header is missing")

    patch_url = f"{location_url}/metadata"

    ocr_result, _ = predict(entity.filepath)

    print(ocr_result)
    if ocr_result is None or not ocr_result:
        print(f"No OCR result found for file: {entity.filepath}")
        return {METADATA_FIELD_NAME: "{}"}

    # Call the URL to patch the entity's metadata
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            patch_url,
            json={
                "metadata_entries": [
                    {
                        "key": METADATA_FIELD_NAME,
                        "value": json.dumps(
                            ocr_result,
                            default=lambda o: o.item() if hasattr(o, "item") else o,
                        ),
                        "source": PLUGIN_NAME,
                        "data_type": MetadataType.JSON_DATA.value,
                    }
                ]
            },
        )

    # Check if the patch request was successful
    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, detail="Failed to patch entity metadata"
        )

    return {
        METADATA_FIELD_NAME: json.dumps(
            ocr_result,
            default=lambda o: o.item() if hasattr(o, "item") else o,
        )
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
