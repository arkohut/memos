# OCR Server

This is a README file for the OCR server. This server uses the `RapidOCR` library to perform OCR (Optical Character Recognition) on image files.

## How to Run

### Install the required dependencies

```bash
pip install -r requirements.txt
```

### Run the server

```bash
export MAX_WORKERS=1 # default is 1
export USE_GPU=false # default is false
uvicorn server:app --host 0.0.0.0 --port 8000
```

## Endpoints

- `GET /docs`: Swagger UI.
- `POST /predict`: OCR endpoint. Accepts an `Entity` object and a `Location` header. Performs OCR on the image file and updates the entity's metadata with the OCR results.
