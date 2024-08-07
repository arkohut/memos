import json
from typing import List

from .schemas import (
    MetadataType,
    EntityMetadata,
    EntityIndexItem,
    MetadataIndexItem,
    EntitySearchResult,
)


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


def bulk_upsert(client, entities):
    documents = [
        EntityIndexItem(
            id=str(entity.id),
            filepath=entity.filepath,
            filename=entity.filename,
            size=entity.size,
            file_created_at=int(entity.file_created_at.timestamp()),
            file_last_modified_at=int(entity.file_last_modified_at.timestamp()),
            file_type=entity.file_type,
            file_type_group=entity.file_type_group,
            last_scan_at=(
                int(entity.last_scan_at.timestamp()) if entity.last_scan_at else None
            ),
            library_id=entity.library_id,
            folder_id=entity.folder_id,
            tags=[tag.name for tag in entity.tags],
            metadata_entries=[
                MetadataIndexItem(
                    key=metadata.key,
                    value=convert_metadata_value(metadata),
                    source=metadata.source,
                )
                for metadata in entity.metadata_entries
            ],
            metadata_text="\n\n".join(
                [
                    (
                        f"key: {metadata.key}\nvalue:\n{json.dumps(json.loads(metadata.value), indent=2)}"
                        if metadata.data_type == MetadataType.JSON_DATA
                        else f"key: {metadata.key}\nvalue:\n{metadata.value}"
                    )
                    for metadata in entity.metadata_entries
                ]
            ),
        ).model_dump(mode='json')
        for entity in entities
    ]

    # Sync the entity data to Typesense
    try:
        response = client.collections["entities"].documents.import_(documents, {'action': 'upsert'})
        return response
    except Exception as e:
        raise Exception(
            f"Failed to sync entities to Typesense: {str(e)}",
        )


def upsert(client, entity):
    entity_data = EntityIndexItem(
        id=str(entity.id),
        filepath=entity.filepath,
        filename=entity.filename,
        size=entity.size,
        file_created_at=int(entity.file_created_at.timestamp()),
        file_last_modified_at=int(entity.file_last_modified_at.timestamp()),
        file_type=entity.file_type,
        file_type_group=entity.file_type_group,
        last_scan_at=(
            int(entity.last_scan_at.timestamp()) if entity.last_scan_at else None
        ),
        library_id=entity.library_id,
        folder_id=entity.folder_id,
        tags=[tag.name for tag in entity.tags],
        metadata_entries=[
            MetadataIndexItem(
                key=metadata.key,
                value=convert_metadata_value(metadata),
                source=metadata.source,
            )
            for metadata in entity.metadata_entries
        ],
        metadata_text="\n\n".join(
            [
                (
                    f"key: {metadata.key}\nvalue:\n{json.dumps(json.loads(metadata.value), indent=2)}"
                    if metadata.data_type == MetadataType.JSON_DATA
                    else f"key: {metadata.key}\nvalue:\n{metadata.value}"
                )
                for metadata in entity.metadata_entries
            ]
        ),
    )

    # Sync the entity data to Typesense
    try:
        client.collections["entities"].documents.upsert(entity_data.model_dump_json())
    except Exception as e:
        raise Exception(
            f"Failed to sync entity to Typesense: {str(e)}",
        )


def remove_entity_by_id(client, entity_id):
    try:
        client.collections["entities"].documents[entity_id].delete()
    except Exception as e:
        raise Exception(
            f"Failed to remove entity from Typesense: {str(e)}",
        )


def list_all_entities(
    client, library_id: int, folder_id: int, limit=100, offset=0
) -> List[EntityIndexItem]:
    try:
        response = client.collections["entities"].documents.search(
            {
                "q": "*",
                "filter_by": f"library_id:={library_id} && folder_id:={folder_id}",
                "per_page": limit,
                "page": offset // limit + 1,
            }
        )
        return [
            EntityIndexItem(
                id=hit["document"]["id"],
                filepath=hit["document"]["filepath"],
                filename=hit["document"]["filename"],
                size=hit["document"]["size"],
                file_created_at=hit["document"]["file_created_at"],
                file_last_modified_at=hit["document"]["file_last_modified_at"],
                file_type=hit["document"]["file_type"],
                file_type_group=hit["document"]["file_type_group"],
                last_scan_at=hit["document"].get("last_scan_at"),
                library_id=hit["document"]["library_id"],
                folder_id=hit["document"]["folder_id"],
                tags=hit["document"]["tags"],
                metadata_entries=[
                    MetadataIndexItem(
                        key=entry["key"], value=entry["value"], source=entry["source"]
                    )
                    for entry in hit["document"]["metadata_entries"]
                ],
                metadata_text=hit["document"]["metadata_text"],
            )
            for hit in response["hits"]
        ]
    except Exception as e:
        raise Exception(
            f"Failed to list entities for library {library_id} and folder {folder_id}: {str(e)}",
        )


def search_entities(
    client,
    q: str,
    library_ids: List[int] = None,
    folder_ids: List[int] = None,
    limit: int = 48,
    offset: int = 0,
    start: int = None,
    end: int = None,
) -> List[EntitySearchResult]:
    try:
        filter_by = []
        if library_ids:
            filter_by.append(f"library_id:[{','.join(map(str, library_ids))}]")
        if folder_ids:
            filter_by.append(f"folder_id:[{','.join(map(str, folder_ids))}]")
        if start is not None and end is not None:
            filter_by.append(f"file_created_at:={start}..{end}")

        filter_by_str = " && ".join(filter_by) if filter_by else ""
        search_parameters = {
            "q": q,
            "query_by": "tags,metadata_text,embedding,filename,filepath",
            "infix": "off,off,off,always,always",
            "filter_by": (
                f"{filter_by_str} && file_type_group:=image"
                if filter_by_str
                else "file_type_group:=image"
            ),
            "limit": limit,
            "offset": offset,
            "exclude_fields": "metadata_text,embedding",
            "sort_by": "_text_match:desc",
        }
        search_results = client.collections["entities"].documents.search(
            search_parameters
        )
        return [
            EntitySearchResult(
                id=hit["document"]["id"],
                filepath=hit["document"]["filepath"],
                filename=hit["document"]["filename"],
                size=hit["document"]["size"],
                file_created_at=hit["document"]["file_created_at"],
                file_last_modified_at=hit["document"]["file_last_modified_at"],
                file_type=hit["document"]["file_type"],
                file_type_group=hit["document"]["file_type_group"],
                last_scan_at=hit["document"].get("last_scan_at"),
                library_id=hit["document"]["library_id"],
                folder_id=hit["document"]["folder_id"],
                tags=hit["document"]["tags"],
                metadata_entries=[
                    MetadataIndexItem(
                        key=entry["key"], value=entry["value"], source=entry["source"]
                    )
                    for entry in hit["document"]["metadata_entries"]
                ],
            )
            for hit in search_results["hits"]
        ]
    except Exception as e:
        raise Exception(
            f"Failed to search entities: {str(e)}",
        )


def fetch_entity_by_id(client, id: str) -> EntityIndexItem:
    try:
        document = client.collections["entities"].documents[id].retrieve()
        return EntitySearchResult(
            id=document["id"],
            filepath=document["filepath"],
            filename=document["filename"],
            size=document["size"],
            file_created_at=document["file_created_at"],
            file_last_modified_at=document["file_last_modified_at"],
            file_type=document["file_type"],
            file_type_group=document["file_type_group"],
            last_scan_at=document.get("last_scan_at"),
            library_id=document["library_id"],
            folder_id=document["folder_id"],
            tags=document["tags"],
            metadata_entries=[
                MetadataIndexItem(
                    key=entry["key"], value=entry["value"], source=entry["source"]
                )
                for entry in document["metadata_entries"]
            ],
        )
    except Exception as e:
        raise Exception(
            f"Failed to fetch document by id: {str(e)}",
        )
