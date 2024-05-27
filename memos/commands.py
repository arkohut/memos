import typer
import httpx
from memos.server import run_server

app = typer.Typer()

@app.command()
def serve():
    run_server()

@app.command()
def ls():
    response = httpx.get("http://localhost:8080/libraries")
    libraries = response.json()
    for library in libraries:
        print(library['name'])

if __name__ == "__main__":
    app()
