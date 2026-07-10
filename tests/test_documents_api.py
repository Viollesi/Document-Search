from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.api import documents as documents_api


def make_document(
    document_id: str,
    created_date: datetime,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=document_id,
        rubrics=["rubric"],
        text=f"document {document_id}",
        created_date=created_date,
    )


@pytest.mark.asyncio
async def test_search_documents_returns_documents_from_postgres(client, monkeypatch) -> None:
    search_calls = []

    async def fake_search_document_ids(elasticsearch, query: str, limit: int) -> list[str]:
        search_calls.append({"query": query, "limit": limit})
        return ["1", "2"]

    async def fake_get_documents_by_ids(session, document_ids: list[str]):
        assert document_ids == ["1", "2"]
        return [
            make_document("2", datetime(2024, 1, 2, tzinfo=UTC)),
            make_document("1", datetime(2024, 1, 1, tzinfo=UTC)),
        ]

    monkeypatch.setattr(documents_api, "search_document_ids", fake_search_document_ids)
    monkeypatch.setattr(documents_api, "get_documents_by_ids", fake_get_documents_by_ids)

    response = await client.get("/documents/search", params={"q": "document"})

    assert response.status_code == 200
    assert search_calls == [{"query": "document", "limit": 20}]
    assert response.json() == [
        {
            "id": "2",
            "rubrics": ["rubric"],
            "text": "document 2",
            "created_date": "2024-01-02T00:00:00Z",
        },
        {
            "id": "1",
            "rubrics": ["rubric"],
            "text": "document 1",
            "created_date": "2024-01-01T00:00:00Z",
        },
    ]


@pytest.mark.asyncio
async def test_search_documents_returns_empty_list_when_index_has_no_matches(
    client,
    monkeypatch,
) -> None:
    async def fake_search_document_ids(elasticsearch, query: str, limit: int) -> list[str]:
        return []

    async def fake_get_documents_by_ids(session, document_ids: list[str]):
        raise AssertionError("PostgreSQL should not be queried without document ids")

    monkeypatch.setattr(documents_api, "search_document_ids", fake_search_document_ids)
    monkeypatch.setattr(documents_api, "get_documents_by_ids", fake_get_documents_by_ids)

    response = await client.get("/documents/search", params={"q": "missing"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_documents_rejects_empty_query(client) -> None:
    response = await client.get("/documents/search", params={"q": ""})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_document_removes_document_from_db_and_index(client, monkeypatch) -> None:
    calls = []

    async def fake_delete_document(session, document_id: str) -> bool:
        calls.append(("db", document_id))
        return True

    async def fake_delete_document_from_index(elasticsearch, document_id: str) -> bool:
        calls.append(("index", document_id))
        return True

    monkeypatch.setattr(documents_api, "delete_document", fake_delete_document)
    monkeypatch.setattr(
        documents_api,
        "delete_document_from_index",
        fake_delete_document_from_index,
    )

    response = await client.delete("/documents/1")

    assert response.status_code == 204
    assert response.content == b""
    assert calls == [("db", "1"), ("index", "1")]


@pytest.mark.asyncio
async def test_delete_document_returns_404_when_document_does_not_exist(
    client,
    monkeypatch,
) -> None:
    async def fake_delete_document(session, document_id: str) -> bool:
        return False

    async def fake_delete_document_from_index(elasticsearch, document_id: str) -> bool:
        raise AssertionError("Elasticsearch should not be touched for missing documents")

    monkeypatch.setattr(documents_api, "delete_document", fake_delete_document)
    monkeypatch.setattr(
        documents_api,
        "delete_document_from_index",
        fake_delete_document_from_index,
    )

    response = await client.delete("/documents/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Документ не найден"}
