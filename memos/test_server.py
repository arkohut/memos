import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pathlib import Path


from memos.server import app, get_db
from memos.schemas import Library, NewLibraryParam
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
