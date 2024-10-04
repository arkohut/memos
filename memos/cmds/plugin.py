import typer
import httpx
from tabulate import tabulate
from memos.config import settings

BASE_URL = f"http://{settings.server_host}:{settings.server_port}"


plugin_app = typer.Typer()


def display_plugins(plugins):
    table = []
    for plugin in plugins:
        table.append(
            [plugin["id"], plugin["name"], plugin["description"], plugin["webhook_url"]]
        )
    print(
        tabulate(
            table,
            headers=["ID", "Name", "Description", "Webhook URL"],
            tablefmt="plain",
        )
    )


@plugin_app.command("ls")
def ls():
    response = httpx.get(f"{BASE_URL}/plugins")
    plugins = response.json()
    display_plugins(plugins)


@plugin_app.command("create")
def create(name: str, webhook_url: str, description: str = ""):
    response = httpx.post(
        f"{BASE_URL}/plugins",
        json={"name": name, "description": description, "webhook_url": webhook_url},
    )
    if 200 <= response.status_code < 300:
        print("Plugin created successfully")
    else:
        print(f"Failed to create plugin: {response.status_code} - {response.text}")


@plugin_app.command("bind")
def bind(
    library_id: int = typer.Option(..., "--lib", help="ID of the library"),
    plugin: str = typer.Option(..., "--plugin", help="ID or name of the plugin"),
):
    try:
        plugin_id = int(plugin)
        plugin_param = {"plugin_id": plugin_id}
    except ValueError:
        plugin_param = {"plugin_name": plugin}

    response = httpx.post(
        f"{BASE_URL}/libraries/{library_id}/plugins",
        json=plugin_param,
    )
    if response.status_code == 204:
        print("Plugin bound to library successfully")
    else:
        print(
            f"Failed to bind plugin to library: {response.status_code} - {response.text}"
        )


@plugin_app.command("unbind")
def unbind(
    library_id: int = typer.Option(..., "--lib", help="ID of the library"),
    plugin_id: int = typer.Option(..., "--plugin", help="ID of the plugin"),
):
    response = httpx.delete(
        f"{BASE_URL}/libraries/{library_id}/plugins/{plugin_id}",
    )
    if response.status_code == 204:
        print("Plugin unbound from library successfully")
    else:
        print(
            f"Failed to unbind plugin from library: {response.status_code} - {response.text}"
        )
