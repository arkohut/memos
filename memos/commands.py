import typer
import httpx
from memos.server import run_server
from tabulate import tabulate
from typing import List
from pathlib import Path

app = typer.Typer()
lib_app = typer.Typer()
app.add_typer(lib_app, name="lib")


def display_libraries(libraries):
    table = []
    for library in libraries:
        table.append(
            [
                library["id"],
                library["name"],
                "\n".join(
                    f"{folder['id']}: {folder['path']}" for folder in library["folders"]
                ),
            ]
        )

    print(tabulate(table, headers=["ID", "Name", "Folders"], tablefmt="plain"))


@app.command()
def serve():
    run_server()


@lib_app.command("ls")
def ls():
    response = httpx.get("http://localhost:8080/libraries")
    libraries = response.json()
    display_libraries(libraries)


@lib_app.command("create")
def add(name: str, folders: List[str]):

    absolute_folders = [str(Path(folder).resolve()) for folder in folders]
    response = httpx.post(
        "http://localhost:8080/libraries",
        json={"name": name, "folders": absolute_folders},
    )
    if 200 <= response.status_code < 300:
        print("Library created successfully")
    else:
        print(f"Failed to create library: {response.status_code} - {response.text}")


if __name__ == "__main__":
    app()
