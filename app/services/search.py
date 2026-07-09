from collections.abc import Iterable
from typing import TypedDict

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from app.core.config import get_settings


class SearchDocument(TypedDict):
    id: str
    text: str


INDEX_MAPPINGS = {
    "properties": {
        "id": {"type": "keyword"},
        "text": {"type": "text"},
    },
}


async def ensure_documents_index(client: AsyncElasticsearch) -> None:
    """Создаёт индекс документов, если он ещё не существует."""
    settings = get_settings()
    exists = await client.indices.exists(index=settings.elasticsearch_index)

    if not exists:
        await client.indices.create(
            index=settings.elasticsearch_index,
            mappings=INDEX_MAPPINGS,
        )


async def search_document_ids(
    client: AsyncElasticsearch,
    query: str,
    limit: int = 20,
) -> list[str]:
    """Ищет документы в индексе и возвращает только их id."""
    settings = get_settings()
    response = await client.search(
        index=settings.elasticsearch_index,
        query={"match": {"text": query}},
        size=limit,
        _source=["id"],
    )

    document_ids: list[str] = []
    for hit in response["hits"]["hits"]:
        source = hit.get("_source") or {}
        document_ids.append(source.get("id") or hit["_id"])

    return document_ids


async def bulk_index_documents(
    client: AsyncElasticsearch,
    documents: Iterable[SearchDocument],
) -> int:
    """Индексирует документы в Elasticsearch через bulk API."""
    settings = get_settings()
    actions = [
        {
            "_op_type": "index",
            "_index": settings.elasticsearch_index,
            "_id": document["id"],
            "id": document["id"],
            "text": document["text"],
        }
        for document in documents
    ]

    if not actions:
        return 0

    indexed_count, _ = await async_bulk(client, actions)
    return indexed_count


async def delete_document_from_index(
    client: AsyncElasticsearch,
    document_id: str,
) -> bool:
    """Удаляет документ из индекса по id."""
    settings = get_settings()
    response = await client.options(ignore_status=404).delete(
        index=settings.elasticsearch_index,
        id=document_id,
    )

    return response.get("result") == "deleted"
