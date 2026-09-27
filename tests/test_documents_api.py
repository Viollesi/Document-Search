from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from elasticsearch import ConnectionError
from sqlalchemy.exc import OperationalError

from app.api import documents as documents_api


def make_document(document_id: str, created_date: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        id=document_id,
        rubrics=["rubric"],
        text=f"document {document_id}",
        created_date=created_date,
    )


@pytest.mark.asyncio
async def test_search_normalizes_query_and_sorts_documents(client, monkeypatch) -> None:
    calls = []
    same_date = datetime(2024, 1, 2, tzinfo=UTC)

    async def fake_search(_, query: str, limit: int, offset: int) -> list[str]:
        calls.append((query, limit, offset))
        return ["2", "1", "3"]

    async def fake_get(_, document_ids: list[str]):
        assert document_ids == ["2", "1", "3"]
        return [
            make_document("2", same_date),
            make_document("1", same_date),
            make_document("3", same_date - timedelta(days=1)),
        ]

    monkeypatch.setattr(documents_api, "search_document_ids", fake_search)
    monkeypatch.setattr(documents_api, "get_documents_by_ids", fake_get)

    response = await client.get("/documents/search", params={"q": "  документ  "})

    assert response.status_code == 200
    assert calls == [("документ", 20, 0)]
    assert [document["id"] for document in response.json()] == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_search_returns_empty_list(client, monkeypatch) -> None:
    async def fake_search(*args, **kwargs) -> list[str]:
        return []

    async def fake_get(*args, **kwargs):
        raise AssertionError("PostgreSQL не должен вызываться без ID")

    monkeypatch.setattr(documents_api, "search_document_ids", fake_search)
    monkeypatch.setattr(documents_api, "get_documents_by_ids", fake_get)

    response = await client.get("/documents/search", params={"q": "missing"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
async def test_search_rejects_empty_query(client, query: str) -> None:
    response = await client.get("/documents/search", params={"q": query})
    assert response.status_code == 422
    assert response.json() == {"detail": "Некорректные параметры запроса"}


@pytest.mark.asyncio
async def test_search_deduplicates_ids_and_fills_stale_results(client, monkeypatch) -> None:
    first_page = [str(index) for index in range(1, 21)]
    pages = {0: first_page, 20: ["20", "21"]}

    async def fake_search(_, query: str, limit: int, offset: int) -> list[str]:
        return pages[offset]

    async def fake_get(_, document_ids: list[str]):
        # ID 1 отсутствует в PostgreSQL, ID 20 повторяется во второй странице.
        return [
            make_document(document_id, datetime(2024, 1, int(document_id), tzinfo=UTC))
            for document_id in document_ids
            if document_id != "1"
        ]

    monkeypatch.setattr(documents_api, "search_document_ids", fake_search)
    monkeypatch.setattr(documents_api, "get_documents_by_ids", fake_get)

    response = await client.get("/documents/search", params={"q": "text"})

    assert response.status_code == 200
    assert len(response.json()) == 20
    assert len({document["id"] for document in response.json()}) == 20


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dependency",
    ["elasticsearch", "postgres", "postgres_connection"],
)
async def test_search_returns_503_for_dependency_errors(
    client,
    monkeypatch,
    dependency: str,
) -> None:
    async def fake_search(*args, **kwargs) -> list[str]:
        if dependency == "elasticsearch":
            raise ConnectionError("unavailable")
        return ["1"]

    async def fake_get(*args, **kwargs):
        if dependency == "postgres_connection":
            raise OSError("unavailable")
        raise OperationalError("select", {}, Exception("unavailable"))

    monkeypatch.setattr(documents_api, "search_document_ids", fake_search)
    monkeypatch.setattr(documents_api, "get_documents_by_ids", fake_get)

    response = await client.get("/documents/search", params={"q": "text"})

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_delete_commits_after_index_cleanup(client, client_session, monkeypatch) -> None:
    calls = []

    async def fake_delete_db(*args) -> bool:
        calls.append("db")
        return True

    async def fake_delete_index(*args) -> bool:
        calls.append("index")
        return True

    client_session.events = calls
    monkeypatch.setattr(documents_api, "delete_document", fake_delete_db)
    monkeypatch.setattr(documents_api, "delete_document_from_index", fake_delete_index)

    response = await client.delete("/documents/1")

    assert response.status_code == 204
    assert response.content == b""
    assert calls == ["db", "index", "commit"]


@pytest.mark.asyncio
async def test_delete_missing_document_cleans_stale_index(
    client,
    client_session,
    monkeypatch,
) -> None:
    calls = []

    async def fake_delete_db(*args) -> bool:
        calls.append("db")
        return False

    async def fake_delete_index(*args) -> bool:
        calls.append("index")
        return False

    client_session.events = calls
    monkeypatch.setattr(documents_api, "delete_document", fake_delete_db)
    monkeypatch.setattr(documents_api, "delete_document_from_index", fake_delete_index)

    response = await client.delete("/documents/missing")

    assert response.status_code == 404
    assert calls == ["db", "index", "rollback"]


@pytest.mark.asyncio
async def test_delete_rolls_back_when_elasticsearch_fails(
    client,
    client_session,
    monkeypatch,
) -> None:
    async def fake_delete_db(*args) -> bool:
        return True

    async def fake_delete_index(*args) -> bool:
        raise ConnectionError("unavailable")

    monkeypatch.setattr(documents_api, "delete_document", fake_delete_db)
    monkeypatch.setattr(documents_api, "delete_document_from_index", fake_delete_index)

    response = await client.delete("/documents/1")

    assert response.status_code == 503
    assert client_session.events == ["rollback"]


@pytest.mark.asyncio
async def test_delete_returns_503_for_postgres_connection_error(
    client,
    client_session,
    monkeypatch,
) -> None:
    async def fake_delete_db(*args):
        raise OSError("unavailable")

    async def fake_delete_index(*args):
        raise AssertionError("Elasticsearch не должен вызываться после ошибки PostgreSQL")

    monkeypatch.setattr(documents_api, "delete_document", fake_delete_db)
    monkeypatch.setattr(documents_api, "delete_document_from_index", fake_delete_index)

    response = await client.delete("/documents/1")

    assert response.status_code == 503
    assert client_session.events == ["rollback"]
