import os
import re

import asyncpg
import httpx
import pytest
from elasticsearch import AsyncElasticsearch


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("RUN_REAL_DATASET") != "1",
        reason="Запускается только после импорта реального CSV",
    ),
]


async def test_real_dataset_import_and_search() -> None:
    api_url = os.environ["FUNCTIONAL_API_URL"]
    database_url = os.environ["FUNCTIONAL_DATABASE_URL"]
    elasticsearch_url = os.environ["FUNCTIONAL_ELASTICSEARCH_URL"]
    index = os.environ["FUNCTIONAL_ELASTICSEARCH_INDEX"]

    connection = await asyncpg.connect(database_url)
    try:
        row = await connection.fetchrow(
            """
            SELECT count(*) AS total,
                   count(DISTINCT id) AS unique_ids,
                   min(id::integer) AS min_id,
                   max(id::integer) AS max_id
            FROM documents
            """,
        )
        assert dict(row) == {
            "total": 1500,
            "unique_ids": 1500,
            "min_id": 1,
            "max_id": 1500,
        }
        text = await connection.fetchval("SELECT text FROM documents WHERE id = '1'")
    finally:
        await connection.close()

    elasticsearch = AsyncElasticsearch(elasticsearch_url)
    try:
        assert (await elasticsearch.count(index=index))["count"] == 1500
    finally:
        await elasticsearch.close()

    words = re.findall(r"[\w-]{5,}", text, flags=re.UNICODE)
    assert words
    async with httpx.AsyncClient(base_url=api_url) as client:
        response = await client.get("/documents/search", params={"q": words[0]})
        assert response.status_code == 200
        documents = response.json()
        assert 1 <= len(documents) <= 20
        assert all(set(document) == {"id", "rubrics", "text", "created_date"} for document in documents)
