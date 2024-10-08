import typesense
from .config import settings, TYPESENSE_COLLECTION_NAME
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the schema for the Typesense collection
schema = {
    "name": TYPESENSE_COLLECTION_NAME,
    "enable_nested_fields": True,
    "fields": [
        {"name": "filepath", "type": "string", "infix": True},
        {"name": "filename", "type": "string", "infix": True},
        {"name": "size", "type": "int32"},
        {"name": "file_created_at", "type": "int64", "facet": False},
        {
            "name": "created_date",
            "type": "string",
            "facet": True,
            "optional": True,
            "sort": True,
        },
        {
            "name": "created_month",
            "type": "string",
            "facet": True,
            "optional": True,
            "sort": True,
        },
        {
            "name": "created_year",
            "type": "string",
            "facet": True,
            "optional": True,
            "sort": True,
        },
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
            "num_dim": settings.embedding.num_dim,
            "optional": True,
        },
        {
            "name": "image_embedding",
            "type": "float[]",
            "optional": True,
        },
    ],
    "token_separators": [":", "/", " ", "\\"],
}

def update_collection_fields(client, schema):
    existing_collection = client.collections[TYPESENSE_COLLECTION_NAME].retrieve()
    existing_fields = {field["name"]: field for field in existing_collection["fields"]}
    new_fields = {field["name"]: field for field in schema["fields"]}

    fields_to_add = []
    for name, field in new_fields.items():
        if name not in existing_fields:
            fields_to_add.append(field)
        else:
            # Check if the field can be updated
            updatable_properties = ["facet", "optional"]
            for prop in updatable_properties:
                if prop in field and field[prop] != existing_fields[name].get(prop):
                    fields_to_add.append(field)
                    break

    if fields_to_add:
        client.collections[TYPESENSE_COLLECTION_NAME].update({"fields": fields_to_add})
        print(
            f"Added/updated {len(fields_to_add)} fields in the '{TYPESENSE_COLLECTION_NAME}' collection."
        )
    else:
        print(
            f"No new fields to add or update in the '{TYPESENSE_COLLECTION_NAME}' collection."
        )

def init_typesense():
    """Initialize the Typesense collection."""
    if not settings.typesense.enabled:
        logger.warning("Typesense is not enabled. Skipping initialization.")
        return False

    try:
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

        existing_collections = client.collections.retrieve()
        collection_names = [c["name"] for c in existing_collections]
        if TYPESENSE_COLLECTION_NAME not in collection_names:
            client.collections.create(schema)
            logger.info(f"Typesense collection '{TYPESENSE_COLLECTION_NAME}' created successfully.")
        else:
            update_collection_fields(client, schema)
            logger.info(f"Typesense collection '{TYPESENSE_COLLECTION_NAME}' already exists. Updated fields if necessary.")
        return True
    except Exception as e:
        logger.error(f"Error initializing Typesense collection: {e}")
        return False

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Drop the collection before initializing")
    args = parser.parse_args()

    if not settings.typesense.enabled:
        logger.warning("Typesense is not enabled. Please enable it in the configuration if you want to use Typesense.")
        sys.exit(0)

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

    if args.force:
        try:
            client.collections[TYPESENSE_COLLECTION_NAME].delete()
            logger.info(f"Dropped collection '{TYPESENSE_COLLECTION_NAME}'.")
        except Exception as e:
            logger.error(f"Error dropping collection: {e}")

    if not init_typesense():
        sys.exit(1)
