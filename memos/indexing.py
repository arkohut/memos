import json

from .schemas import MetadataType, EntityMetadata


def convert_metadata_value(metadata: EntityMetadata):
    if metadata.data_type == MetadataType.NUMBER_DATA:
        try:
            return int(metadata.value)
        except ValueError:
            return float(metadata.value)
    elif metadata.data_type == MetadataType.JSON_DATA:
        return json.loads(metadata.value)
    else:
        return metadata.value


def upsert(client, entity):
    # Prepare the entity data for Typesense
    entity_data = {
        "id": str(entity.id),
        "filepath": entity.filepath,
        "filename": entity.filename,
        "size": entity.size,
        "file_created_at": int(entity.file_created_at.timestamp()),
        "file_last_modified_at": int(entity.file_last_modified_at.timestamp()),
        "file_type": entity.file_type,
        "file_type_group": entity.file_type_group,
        "last_scan_at": (
            int(entity.last_scan_at.timestamp()) if entity.last_scan_at else None
        ),
        "library_id": entity.library_id,
        "folder_id": entity.folder_id,
        "tags": [tag.name for tag in entity.tags],
        "metadata_entries": [
            {
                "key": metadata.key,
                "value": convert_metadata_value(metadata),
                "source": metadata.source,
            }
            for metadata in entity.metadata_entries
        ],
        "metadata_text": "\n\n".join(
            [
                (
                    f"key: {metadata.key}\nvalue:\n{json.dumps(json.loads(metadata.value), indent=2)}"
                    if metadata.data_type == MetadataType.JSON_DATA
                    else f"key: {metadata.key}\nvalue:\n{metadata.value}"
                )
                for metadata in entity.metadata_entries
            ]
        ),
    }

    # Sync the entity data to Typesense
    try:
        client.collections["entities"].documents.upsert(entity_data)
    except Exception as e:
        raise Exception(
            f"Failed to sync entity to Typesense: {str(e)}",
        )
