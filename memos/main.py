from fastapi import FastAPI

app = FastAPI()

@app.get("/libraries")
async def get_libraries():
    return [{"name": "Library1"}, {"name": "Library2"}]
