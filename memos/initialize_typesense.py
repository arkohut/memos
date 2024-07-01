import typesense
from memos.config import settings

# Initialize Typesense client
client = typesense.Client(
    {
        "nodes": [
            {
                "host": settings.typesense_host,
                "port": settings.typesense_port,
                "protocol": settings.typesense_protocol,
            }
        ],
        "api_key": settings.typesense_api_key,
        "connection_timeout_seconds": settings.typesense_connection_timeout_seconds,
    }
)

# Define the schema for the Typesense collection
schema = {
    "name": "entities",
    "enable_nested_fields": True,
    "fields": [
        {"name": "filepath", "type": "string"},
        {"name": "filename", "type": "string"},
        {"name": "size", "type": "int32"},
        {"name": "file_created_at", "type": "int64", "facet": False},
        {"name": "file_last_modified_at", "type": "int64", "facet": False},
        {"name": "file_type", "type": "string", "facet": True},
        {"name": "file_type_group", "type": "string", "facet": True},
        {"name": "last_scan_at", "type": "int64", "facet": False, "optional": True},
        {"name": "library_id", "type": "int32", "facet": True},
        {"name": "folder_id", "type": "int32", "facet": True},
        {
            "name": "tags",
            "type": "string[]",
            "facet": True,
            "optional": True,
            "locale": "zh",
        },
        {
            "name": "metadata_entries",
            "type": "object[]",
            "optional": True,
            "locale": "zh",
        },
        {"name": "metadata_text", "type": "string", "optional": True, "locale": "zh"},
        {
            "name": "embedding",
            "type": "float[]",
            "embed": {
                "from": ["filepath", "filename", "metadata_text"],
                "model_config": {"model_name": "ts/multilingual-e5-small"},
            },
            "optional": True,
        },
    ],
    "token_separators": [":", "/", ".", " ", "-", "\\"],
}


if __name__ == "__main__":

    import sys

    # Check if "--force" parameter is provided
    force_recreate = "--force" in sys.argv

    # Drop the collection if it exists and "--force" parameter is provided
    if force_recreate:
        try:
            client.collections["entities"].delete()
            print("Existing Typesense collection 'entities' deleted successfully.")
        except Exception as e:
            print(
                f"Failed to delete existing Typesense collection 'entities': {str(e)}"
            )

    # Recreate the collection in Typesense
    client.collections.create(schema)
    print("Typesense collection 'entities' created successfully.")
