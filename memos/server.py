import uvicorn

def run_server():
    uvicorn.run("memos.main:app", host="0.0.0.0", port=8080, reload=True)
