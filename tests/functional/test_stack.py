import os
from datetime import datetime

import asyncpg
import httpx
import pytest
from elasticsearch import AsyncElasticsearch


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_FUNCTIONAL") != "1",
        reason="Запускается только в изолированном Compose-окружении",
    ),
]


async def test_import_search_and_delete() -> None:
    api_url = os.environ["FUNCTIONAL_API_URL"]
    database_url = os.environ["FUNCTIONAL_DATABASE_URL"]
    elasticsearch_url = os.environ["FUNCTIONAL_ELASTICSEARCH_URL"]
    index = os.environ["FUNCTIONAL_ELASTICSEARCH_INDEX"]

    async with httpx.AsyncClient(base_url=api_url) as client:
        health = await client.get("/health")
        assert health.status_code == 200

        search = await client.get("/documents/search", params={"q": "common"})
        assert search.status_code == 200
        documents = search.json()
        assert len(documents) == 20
        ordering = [
            (-datetime.fromisoformat(document["created_date"]).timestamp(), document["id"])
            for document in documents
        ]
        assert ordering == sorted(ordering)
        assert all(set(document) == {"id", "rubrics", "text", "created_date"} for document in documents)

        deleted = await client.delete("/documents/22")
        assert deleted.status_code == 204
        assert deleted.content == b""
        repeated = await client.delete("/documents/22")
        assert repeated.status_code == 404

    connection = await asyncpg.connect(database_url)
    try:
        assert await connection.fetchval("SELECT count(*) FROM documents") == 21
        assert await connection.fetchval(
            "SELECT count(*) FROM documents WHERE id = '22'",
        ) == 0
        assert await connection.fetchval(
            "SELECT count(*) FROM documents WHERE created_date IS NULL",
        ) == 0
    finally:
        await connection.close()

    elasticsearch = AsyncElasticsearch(elasticsearch_url)
    try:
        assert (await elasticsearch.count(index=index))["count"] == 21
        assert not await elasticsearch.exists(index=index, id="22")
        mapping = (await elasticsearch.indices.get_mapping(index=index))[index]["mappings"]
        assert mapping["properties"] == {
            "id": {"type": "keyword"},
            "text": {"type": "text"},
        }
        sample = await elasticsearch.get(index=index, id="1")
        assert set(sample["_source"]) == {"id", "text"}
    finally:
        await elasticsearch.close()
