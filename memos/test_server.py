import json
import os
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pathlib import Path


from memos.server import app, get_db
from memos.schemas import (
    NewPluginParam,
    NewLibraryParam,
    NewEntityParam,
    UpdateEntityParam,
    NewFoldersParam,
    EntityMetadataParam,
    MetadataType,
    UpdateEntityTagsParam,
    UpdateEntityMetadataParam,
)
from memos.models import Base


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def load_fixture(filename):
    with open(Path(__file__).parent / "fixtures" / filename, "r") as file:
        return json.load(file)


def setup_library_with_entity(client):
    # Create a new library
    new_library = NewLibraryParam(name="Test Library for Metadata")
    library_response = client.post(
        "/libraries", json=new_library.model_dump(mode="json")
    )
    assert library_response.status_code == 200
    library_id = library_response.json()["id"]

    # Create a new folder in the library
    new_folder = NewFoldersParam(folders=["/tmp"])
    folder_response = client.post(
        f"/libraries/{library_id}/folders", json=new_folder.model_dump(mode="json")
    )
    assert folder_response.status_code == 200
    folder_id = folder_response.json()["folders"][0]["id"]

    # Create a new entity in the folder
    new_entity = NewEntityParam(
        filename="metadata_test_file.txt",
        filepath="/tmp/metadata_folder/metadata_test_file.txt",
        size=5678,
        file_created_at="2023-01-01T00:00:00",
        file_last_modified_at="2023-01-01T00:00:00",
        file_type="txt",
        file_type_group="text",
        folder_id=folder_id,
    )
    entity_response = client.post(
        f"/libraries/{library_id}/entities", json=new_entity.model_dump(mode="json")
    )
    assert entity_response.status_code == 200
    entity_id = entity_response.json()["id"]

    return library_id, folder_id, entity_id


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# Setup a fixture for the FastAPI test client
@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        yield client
    Base.metadata.drop_all(bind=engine)


# Test the new_library endpoint
def test_new_library(client):
    library_param = NewLibraryParam(name="Test Library")
    # Make a POST request to the /libraries endpoint
    response = client.post("/libraries", json=library_param.model_dump())
    # Check that the response is successful
    assert response.status_code == 200
    # Check the response data
    assert response.json() == {
        "id": 1,
        "name": "Test Library",
        "folders": [],
        "plugins": [],
    }

    # Test for duplicate library name
    duplicate_response = client.post("/libraries", json=library_param.model_dump())
    # Check that the response indicates a failure due to duplicate name
    assert duplicate_response.status_code == 400
    assert duplicate_response.json() == {
        "detail": "Library with this name already exists"
    }


def test_list_libraries(client):
    # Setup data: Create a new library
    new_library = NewLibraryParam(name="Sample Library", folders=["/tmp"])
    client.post("/libraries", json=new_library.model_dump(mode="json"))

    # Make a GET request to the /libraries endpoint
    response = client.get("/libraries")

    # Check that the response is successful
    assert response.status_code == 200

    # Check the response data
    expected_data = [
        {
            "id": 1,
            "name": "Sample Library",
            "folders": [{"id": 1, "path": "/tmp"}],
            "plugins": [],
        }
    ]
    assert response.json() == expected_data


def test_new_entity(client):
    # Setup data: Create a new library
    new_library = NewLibraryParam(name="Library for Entity Test", folders=["/tmp"])
    library_response = client.post(
        "/libraries", json=new_library.model_dump(mode="json")
    )
    library_id = library_response.json()["id"]
    folder_id = library_response.json()["folders"][0]["id"]

    # Create a new entity
    new_entity = NewEntityParam(
        filename="test_entity.txt",
        filepath="test_entity.txt",
        size=150,
        file_created_at="2023-01-01T00:00:00",
        file_last_modified_at="2023-01-01T00:00:00",
        file_type="txt",
        file_type_group="text",
        folder_id=folder_id,
    )
    entity_response = client.post(
        f"/libraries/{library_id}/entities", json=new_entity.model_dump(mode="json")
    )

    # Check that the response is successful
    assert entity_response.status_code == 200

    # Check the response data
    entity_data = entity_response.json()
    assert entity_data["filename"] == "test_entity.txt"
    assert entity_data["filepath"] == "test_entity.txt"
    assert entity_data["size"] == 150
    assert entity_data["file_created_at"] == "2023-01-01T00:00:00"
    assert entity_data["file_last_modified_at"] == "2023-01-01T00:00:00"
    assert entity_data["file_type"] == "txt"
    assert entity_data["file_type_group"] == "text"
    assert entity_data["folder_id"] == 1

    # Test for library not found
    invalid_entity_response = client.post(
        "/libraries/9999/entities", json=new_entity.model_dump(mode="json")
    )
    assert invalid_entity_response.status_code == 404
    assert invalid_entity_response.json() == {"detail": "Library not found"}


def test_update_entity(client):
    library_id, _, entity_id = setup_library_with_entity(client)

    # Update the entity
    updated_entity = UpdateEntityParam(
        size=200,
        file_created_at="2023-01-02T00:00:00",
        file_type="markdown",
        file_type_group="text",
    )
    update_response = client.put(
        f"/entities/{entity_id}",
        json=updated_entity.model_dump(mode="json"),
    )

    # Check that the response is successful
    assert update_response.status_code == 200

    # Check the response data
    updated_data = update_response.json()
    assert updated_data["id"] == entity_id
    assert updated_data["size"] == 200
    assert updated_data["file_created_at"] == "2023-01-02T00:00:00"
    assert updated_data["file_last_modified_at"] == "2023-01-01T00:00:00"
    assert updated_data["file_type"] == "markdown"
    assert updated_data["file_type_group"] == "text"

    # Test for entity not found
    invalid_update_response = client.put(
        f"/entities/9999",
        json=updated_entity.model_dump(mode="json"),
    )
    assert invalid_update_response.status_code == 404
    assert invalid_update_response.json() == {"detail": "Entity not found"}


# Test for getting an entity by filepath
def test_get_entity_by_filepath(client):
    # Setup data: Create a new library and entity
    new_library = NewLibraryParam(name="Library for Get Entity Test", folders=["/tmp"])
    library_response = client.post(
        "/libraries", json=new_library.model_dump(mode="json")
    )
    library_id = library_response.json()["id"]

    new_entity = NewEntityParam(
        filename="test_get.txt",
        filepath="test_get.txt",
        size=100,
        file_created_at="2023-01-01T00:00:00",
        file_last_modified_at="2023-01-01T00:00:00",
        file_type="txt",
        file_type_group="text",
        folder_id=1,
    )
    entity_response = client.post(
        f"/libraries/{library_id}/entities", json=new_entity.model_dump(mode="json")
    )
    entity_id = entity_response.json()["id"]

    get_response = client.get(
        f"/libraries/{library_id}/entities/by-filepath",
        params={"filepath": new_entity.filepath},
    )

    # Check that the response is successful
    assert get_response.status_code == 200

    # Check the response data
    entity_data = get_response.json()
    assert entity_data["id"] == entity_id
    assert entity_data["filepath"] == new_entity.filepath
    assert entity_data["filename"] == new_entity.filename
    assert entity_data["size"] == new_entity.size
    assert entity_data["file_type"] == new_entity.file_type
    assert entity_data["file_type_group"] == new_entity.file_type_group

    # Test for entity not found
    invalid_get_response = client.get(
        f"/libraries/{library_id}/entities/by-filepath",
        params={"filepath": "nonexistent.txt"},
    )
    assert invalid_get_response.status_code == 404
    assert invalid_get_response.json() == {"detail": "Entity not found"}

    # Test for library not found
    invalid_get_response = client.get(
        f"/libraries/9999/entities/by-filepath",
        params={"filepath": new_entity.filepath},
    )
    assert invalid_get_response.status_code == 404
    assert invalid_get_response.json() == {"detail": "Entity not found"}


def test_list_entities_in_folder(client):
    # Setup data: Create a new library and folder
    new_library = NewLibraryParam(name="Library for List Entities Test", folders=[])
    library_response = client.post(
        "/libraries", json=new_library.model_dump(mode="json")
    )
    library_id = library_response.json()["id"]

    new_folder = NewFoldersParam(folders=["/tmp"])
    folder_response = client.post(
        f"/libraries/{library_id}/folders", json=new_folder.model_dump(mode="json")
    )
    folder_id = folder_response.json()["folders"][0]["id"]

    # Create a new entity in the folder
    new_entity = NewEntityParam(
        filename="test_list.txt",
        filepath="test_list.txt",
        size=100,
        file_created_at="2023-01-01T00:00:00",
        file_last_modified_at="2023-01-01T00:00:00",
        file_type="txt",
        file_type_group="text",
        folder_id=folder_id,
    )
    entity_response = client.post(
        f"/libraries/{library_id}/entities", json=new_entity.model_dump(mode="json")
    )
    entity_id = entity_response.json()["id"]

    # List entities in the folder
    list_response = client.get(f"/libraries/{library_id}/folders/{folder_id}/entities")

    # Check that the response is successful
    assert list_response.status_code == 200

    # Check the response data
    entities_data = list_response.json()
    assert len(entities_data) == 1
    assert entities_data[0]["id"] == entity_id
    assert entities_data[0]["filepath"] == new_entity.filepath
    assert entities_data[0]["filename"] == new_entity.filename
    assert entities_data[0]["size"] == new_entity.size
    assert entities_data[0]["file_type"] == new_entity.file_type
    assert entities_data[0]["file_type_group"] == new_entity.file_type_group

    # Test for folder not found
    invalid_list_response = client.get(f"/libraries/{library_id}/folders/9999/entities")
    assert invalid_list_response.status_code == 404
    assert invalid_list_response.json() == {
        "detail": "Folder not found in the specified library"
    }

    # Test for library not found
    invalid_list_response = client.get(f"/libraries/9999/folders/{folder_id}/entities")
    assert invalid_list_response.status_code == 404
    assert invalid_list_response.json() == {"detail": "Library not found"}


def test_remove_entity(client):
    library_id, _, entity_id = setup_library_with_entity(client)

    # Delete the entity
    delete_response = client.delete(f"/libraries/{library_id}/entities/{entity_id}")
    assert delete_response.status_code == 204

    # Verify the entity is deleted
    get_response = client.get(f"/libraries/{library_id}/entities/{entity_id}")
    assert get_response.status_code == 404
    assert get_response.json() == {"detail": "Entity not found"}

    # Test for entity not found in the specified library
    invalid_delete_response = client.delete(f"/libraries/{library_id}/entities/9999")
    assert invalid_delete_response.status_code == 404
    assert invalid_delete_response.json() == {
        "detail": "Entity not found in the specified library"
    }


def test_add_folder_to_library(client):
    # Prepare tmp folders for the test
    tmp_folder_path = "/tmp/new_folder"
    if not os.path.exists(tmp_folder_path):
        os.makedirs(tmp_folder_path)

    # Create a new library
    new_library = NewLibraryParam(name="Test Library", folders=[])
    library_response = client.post(
        "/libraries", json=new_library.model_dump(mode="json")
    )
    library_id = library_response.json()["id"]

    # Add a new folder to the library
    new_folders = NewFoldersParam(folders=[tmp_folder_path])
    folder_response = client.post(
        f"/libraries/{library_id}/folders", json=new_folders.model_dump(mode="json")
    )
    assert folder_response.status_code == 200
    assert any(
        folder["path"] == tmp_folder_path
        for folder in folder_response.json()["folders"]
    )

    # Verify the folder is added
    library_response = client.get(f"/libraries/{library_id}")
    assert library_response.status_code == 200
    library_data = library_response.json()
    folder_paths = [folder["path"] for folder in library_data["folders"]]
    assert tmp_folder_path in folder_paths

    # Test for adding a folder that already exists
    duplicate_folder_response = client.post(
        f"/libraries/{library_id}/folders", json=new_folders.model_dump(mode="json")
    )
    assert duplicate_folder_response.status_code == 400
    assert duplicate_folder_response.json() == {
        "detail": "Folder already exists in the library"
    }

    # Test for adding a folder to a non-existent library
    invalid_folder_response = client.post(
        f"/libraries/9999/folders", json=new_folders.model_dump(mode="json")
    )
    assert invalid_folder_response.status_code == 404
    assert invalid_folder_response.json() == {"detail": "Library not found"}


def test_new_plugin(client):
    new_plugin = NewPluginParam(
        name="Test Plugin",
        description="A test plugin",
        webhook_url="http://example.com/webhook",
    )

    # Make a POST request to the /plugins endpoint
    response = client.post("/plugins", json=new_plugin.model_dump(mode="json"))

    # Check that the response is successful
    assert response.status_code == 200

    # Check the response data
    plugin_data = response.json()
    assert plugin_data["name"] == "Test Plugin"
    assert plugin_data["description"] == "A test plugin"
    assert plugin_data["webhook_url"] == "http://example.com/webhook"

    # Test for duplicate plugin name
    duplicate_response = client.post(
        "/plugins", json=new_plugin.model_dump(mode="json")
    )
    # Check that the response indicates a failure due to duplicate name
    assert duplicate_response.status_code == 400
    assert duplicate_response.json() == {
        "detail": "Plugin with this name already exists"
    }

    # Test for another duplicate plugin name
    another_duplicate_response = client.post(
        "/plugins", json=new_plugin.model_dump(mode="json")
    )
    # Check that the response indicates a failure due to duplicate name
    assert another_duplicate_response.status_code == 400
    assert another_duplicate_response.json() == {
        "detail": "Plugin with this name already exists"
    }


def test_update_entity_with_tags(client):
    library_id, _, entity_id = setup_library_with_entity(client)

    # Update the entity with tags
    update_entity_param = UpdateEntityParam(tags=["tag1", "tag2"])

    # Make a PUT request to the /libraries/{library_id}/entities/{entity_id} endpoint
    update_response = client.put(
        f"/entities/{entity_id}",
        json=update_entity_param.model_dump(mode="json"),
    )

    # Check that the response is successful
    assert update_response.status_code == 200

    # Check the response data
    updated_entity_data = update_response.json()
    assert "tags" in updated_entity_data
    assert len(updated_entity_data["tags"]) == 2
    assert "tag1" in [tag["name"] for tag in updated_entity_data["tags"]]
    assert "tag2" in [tag["name"] for tag in updated_entity_data["tags"]]


def test_patch_tags_to_entity(client):
    library_id, _, entity_id = setup_library_with_entity(client)

    # Initial tags
    initial_tags = ["tag1", "tag2"]
    update_entity_param = UpdateEntityTagsParam(tags=initial_tags)

    # Make a PUT request to add initial tags
    initial_update_response = client.put(
        f"/entities/{entity_id}/tags",
        json=update_entity_param.model_dump(mode="json"),
    )

    # Check that the initial update is successful
    assert initial_update_response.status_code == 200
    initial_entity_data = initial_update_response.json()
    assert len(initial_entity_data["tags"]) == 2
    assert set([tag["name"] for tag in initial_entity_data["tags"]]) == set(
        initial_tags
    )

    # New tags to patch
    new_tags = ["tag3", "tag4"]
    patch_entity_param = UpdateEntityTagsParam(tags=new_tags)

    # Make a PATCH request to add new tags
    patch_response = client.patch(
        f"/entities/{entity_id}/tags",
        json=patch_entity_param.model_dump(mode="json"),
    )

    # Check that the patch response is successful
    assert patch_response.status_code == 200

    # Check the response data
    patched_entity_data = patch_response.json()
    assert "tags" in patched_entity_data
    assert len(patched_entity_data["tags"]) == 4
    assert set([tag["name"] for tag in patched_entity_data["tags"]]) == set(
        initial_tags + new_tags
    )

    # Verify that the tags were actually added by making a GET request
    get_response = client.get(f"/libraries/{library_id}/entities/{entity_id}")
    assert get_response.status_code == 200
    get_entity_data = get_response.json()
    assert "tags" in get_entity_data
    assert len(get_entity_data["tags"]) == 4
    assert set([tag["name"] for tag in get_entity_data["tags"]]) == set(
        initial_tags + new_tags
    )


def test_add_metadata_entry_to_entity_success(client):
    library_id, _, entity_id = setup_library_with_entity(client)

    # Add metadata entry to the entity
    metadata_entry = EntityMetadataParam(
        key="author",
        value="John Doe",
        source="plugin_generated",
        data_type=MetadataType.TEXT_DATA,
    )
    update_entity_param = UpdateEntityParam(metadata_entries=[metadata_entry])

    # Make a PUT request to the /libraries/{library_id}/entities/{entity_id} endpoint
    update_response = client.put(
        f"/entities/{entity_id}",
        json=update_entity_param.model_dump(mode="json"),
    )

    # Check that the response is successful
    assert update_response.status_code == 200

    # Check the response data
    updated_entity_data = update_response.json()
    expected_metadata_entry = load_fixture(
        "add_metadata_entry_to_entity_sucess_response.json"
    )
    assert "metadata_entries" in updated_entity_data
    assert len(updated_entity_data["metadata_entries"]) == 1
    assert updated_entity_data["metadata_entries"][0] == expected_metadata_entry


def test_update_entity_tags(client):
    library_id, _, entity_id = setup_library_with_entity(client)

    # Add tags to the entity
    tags = ["tag1", "tag2", "tag3"]
    update_entity_param = UpdateEntityParam(tags=tags)

    # Make a PUT request to the /libraries/{library_id}/entities/{entity_id} endpoint
    update_response = client.put(
        f"/entities/{entity_id}",
        json=update_entity_param.model_dump(mode="json"),
    )

    # Check that the response is successful
    assert update_response.status_code == 200

    # Check the response data
    updated_entity_data = update_response.json()
    assert "tags" in updated_entity_data
    assert sorted([t["name"] for t in updated_entity_data["tags"]]) == sorted(
        tags, key=str
    )


def test_patch_entity_metadata_entries(client):
    library_id, _, entity_id = setup_library_with_entity(client)

    # Patch metadata entries of the entity
    patch_metadata_entries = [
        {
            "key": "author",
            "value": "Jane Smith",
            "source": "user_generated",
            "data_type": MetadataType.TEXT_DATA.value,
        },
        {
            "key": "year",
            "value": "2023",
            "source": "user_generated",
            "data_type": MetadataType.TEXT_DATA.value,
        },
    ]
    update_entity_param = UpdateEntityParam(
        metadata_entries=[
            EntityMetadataParam(**entry) for entry in patch_metadata_entries
        ]
    )

    # Make a PUT request to the /libraries/{library_id}/entities/{entity_id} endpoint
    patch_response = client.put(
        f"/entities/{entity_id}",
        json=update_entity_param.model_dump(mode="json"),
    )

    # Check that the response is successful
    assert patch_response.status_code == 200

    # Check the response data
    patched_entity_data = patch_response.json()
    expected_data = load_fixture("patch_entity_metadata_response.json")
    assert patched_entity_data == expected_data

    # Update the "author" attribute of the entity
    updated_metadata_entries = [
        {
            "key": "author",
            "value": "John Doe",
            "source": "user_generated",
            "data_type": MetadataType.TEXT_DATA.value,
        }
    ]
    update_entity_param = UpdateEntityMetadataParam(
        metadata_entries=[
            EntityMetadataParam(**entry) for entry in updated_metadata_entries
        ]
    )

    # Make a PATCH request to the /libraries/{library_id}/entities/{entity_id}/metadata endpoint
    update_response = client.patch(
        f"/entities/{entity_id}/metadata",
        json=update_entity_param.model_dump(mode="json"),
    )

    # Check that the response is successful
    assert update_response.status_code == 200

    # Check the response data
    updated_entity_data = update_response.json()
    assert "metadata_entries" in updated_entity_data
    assert any(
        entry["key"] == "author" and entry["value"] == "John Doe"
        for entry in updated_entity_data["metadata_entries"]
    )

    # Add a new attribute "media_type" with value "book"
    new_metadata_entry = {
        "key": "media_type",
        "value": "book",
        "source": "user_generated",
        "data_type": MetadataType.TEXT_DATA.value,
    }
    updated_metadata_entries.append(new_metadata_entry)

    update_entity_param = UpdateEntityMetadataParam(
        metadata_entries=[
            EntityMetadataParam(**entry) for entry in updated_metadata_entries
        ]
    )

    # Make a PATCH request to the /libraries/{library_id}/entities/{entity_id}/metadata endpoint
    update_response = client.patch(
        f"/entities/{entity_id}/metadata",
        json=update_entity_param.model_dump(mode="json"),
    )

    # Check that the response is successful
    assert update_response.status_code == 200

    # Check the response data
    updated_entity_data = update_response.json()
    assert "metadata_entries" in updated_entity_data
    assert any(
        entry["key"] == "media_type" and entry["value"] == "book"
        for entry in updated_entity_data["metadata_entries"]
    )
