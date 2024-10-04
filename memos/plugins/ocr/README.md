# OCR Plugin

This is a README file for the OCR plugin. This plugin uses the `RapidOCR` library to perform OCR (Optical Character Recognition) on image files and updates the metadata of the entity with the OCR results.

## How to Run

To run this OCR plugin, follow the steps below:

1. **Install the required dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the FastAPI application:**

   You can run the FastAPI application using `uvicorn`. Make sure you are in the directory where `main.py` is located.

   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

3. **Integration with memos:**

   ```sh
   $ python -m memos.commands plugin create ocr http://localhost:8000
   Plugin created successfully
   ```

   ```sh
   $ python -m memos.commands plugin ls

   ID  Name    Description    Webhook URL
    1  ocr                    http://localhost:8000/
   ```

   ```sh
   $ python -m memos.commands plugin bind --lib 1 --plugin 1
   Plugin bound to library successfully
   ```

## Endpoints

- `GET /`: Health check endpoint. Returns `{"healthy": True}` if the service is running.
- `POST /`: OCR endpoint. Accepts an `Entity` object and a `Location` header. Performs OCR on the image file and updates the entity's metadata with the OCR results.

## Metadata

The OCR results are stored in the metadata field named `ocr_result` with the following structure:
