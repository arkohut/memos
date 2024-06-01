import typer
import httpx
from memos.server import run_server
from tabulate import tabulate

app = typer.Typer()

@app.command()
def serve():
    run_server()

@app.command()
def ls():
    response = httpx.get("http://localhost:8080/libraries")
    libraries = response.json()

    table = []
    for library in libraries:
        table.append([library['id'], library['name'], "\n".join(folder['path'] for folder in library['folders'])])
    
    print(tabulate(table, headers=["ID", "Name", "Folders"]))

if __name__ == "__main__":
    app()
