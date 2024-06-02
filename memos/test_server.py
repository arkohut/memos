import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pathlib import Path


from memos.server import app, get_db
from memos.schemas import Library, NewLibraryParam, NewEntityParam, UpdateEntityParam
from memos.models import Base


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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


def test_read_main(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"healthy": True}


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
    library_response = client.post("/libraries", json=new_library.model_dump(mode="json"))
    library_id = library_response.json()["id"]
    folder_id = library_response.json()["folders"][0]["id"]

    # Create a new entity
    new_entity = NewEntityParam(
        filename="test_entity.txt",
        filepath="/tmp/test_entity.txt",
        size=150,
        file_created_at="2023-01-01T00:00:00",
        file_last_modified_at="2023-01-01T00:00:00",
        file_type="text/plain",
        folder_id=folder_id
    )
    entity_response = client.post(f"/libraries/{library_id}/entities", json=new_entity.model_dump(mode="json"))

    # Check that the response is successful
    assert entity_response.status_code == 200

    # Check the response data
    entity_data = entity_response.json()
    assert entity_data["filename"] == "test_entity.txt"
    assert entity_data["filepath"] == "/tmp/test_entity.txt"
    assert entity_data["size"] == 150
    assert entity_data["file_created_at"] == "2023-01-01T00:00:00"
    assert entity_data["file_last_modified_at"] == "2023-01-01T00:00:00"
    assert entity_data["file_type"] == "text/plain"
    assert entity_data["folder_id"] == 1

    # Test for library not found
    invalid_entity_response = client.post("/libraries/9999/entities", json=new_entity.model_dump(mode="json"))
    assert invalid_entity_response.status_code == 404
    assert invalid_entity_response.json() == {"detail": "Library not found"}



def test_update_entity(client):
    # Setup data: Create a new library and entity
    new_library = NewLibraryParam(name="Library for Update Test", folders=["/tmp"])
    library_response = client.post("/libraries", json=new_library.model_dump(mode="json"))
    library_id = library_response.json()["id"]

    new_entity = NewEntityParam(
        filename="test.txt",
        filepath="/tmp/test.txt",
        size=100,
        file_created_at="2023-01-01T00:00:00",
        file_last_modified_at="2023-01-01T00:00:00",
        file_type="text/plain",
        folder_id=1
    )
    entity_response = client.post(f"/libraries/{library_id}/entities", json=new_entity.model_dump(mode="json"))
    entity_id = entity_response.json()["id"]

    # Update the entity
    updated_entity = UpdateEntityParam(
        size=200,
        file_created_at="2023-01-02T00:00:00",
        file_last_modified_at="2023-01-02T00:00:00",
        file_type="text/markdown"
    )
    update_response = client.put(f"/libraries/{library_id}/entities/{entity_id}", json=updated_entity.model_dump(mode="json"))

    # Check that the response is successful
    assert update_response.status_code == 200

    # Check the response data
    updated_data = update_response.json()
    assert updated_data["id"] == entity_id
    assert updated_data["size"] == 200
    assert updated_data["file_created_at"] == "2023-01-02T00:00:00"
    assert updated_data["file_last_modified_at"] == "2023-01-02T00:00:00"
    assert updated_data["file_type"] == "text/markdown"

    # Test for entity not found
    invalid_update_response = client.put(f"/libraries/{library_id}/entities/9999", json=updated_entity.model_dump(mode="json"))
    assert invalid_update_response.status_code == 404
    assert invalid_update_response.json() == {"detail": "Entity not found in the specified library"}

    # Test for library not found
    invalid_update_response = client.put(f"/libraries/9999/entities/{entity_id}", json=updated_entity.model_dump(mode="json"))
    assert invalid_update_response.status_code == 404
    assert invalid_update_response.json() == {"detail": "Entity not found in the specified library"}
