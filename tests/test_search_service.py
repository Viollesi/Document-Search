from types import SimpleNamespace

import pytest

from app.services import search as search_service


@pytest.mark.asyncio
async def test_search_uses_match_query_and_pagination(monkeypatch) -> None:
    calls = []

    class Client:
        async def search(self, **kwargs):
            calls.append(kwargs)
            return {"hits": {"hits": [{"_source": {"id": "1"}}, {"_id": "2"}]}}

    monkeypatch.setattr(
        search_service,
        "get_settings",
        lambda: SimpleNamespace(elasticsearch_index="documents"),
    )

    result = await search_service.search_document_ids(Client(), "текст + символы", 20, 40)

    assert result == ["1", "2"]
    assert calls == [
        {
            "index": "documents",
            "query": {"match": {"text": "текст + символы"}},
            "size": 20,
            "from_": 40,
            "_source": ["id"],
        }
    ]


@pytest.mark.asyncio
async def test_bulk_index_uses_only_id_and_text_and_waits_for_refresh(monkeypatch) -> None:
    captured = {}

    async def fake_bulk(client, actions, **kwargs):
        captured["actions"] = actions
        captured["kwargs"] = kwargs
        return 1, []

    monkeypatch.setattr(search_service, "async_bulk", fake_bulk)
    monkeypatch.setattr(
        search_service,
        "get_settings",
        lambda: SimpleNamespace(elasticsearch_index="documents"),
    )

    count = await search_service.bulk_index_documents(
        object(),
        [{"id": "1", "text": "text"}],
    )

    assert count == 1
    assert captured == {
        "actions": [
            {
                "_op_type": "index",
                "_index": "documents",
                "_id": "1",
                "id": "1",
                "text": "text",
            }
        ],
        "kwargs": {"raise_on_error": False, "refresh": "wait_for"},
    }


@pytest.mark.asyncio
async def test_bulk_index_reports_partial_failures(monkeypatch) -> None:
    async def fake_bulk(*args, **kwargs):
        return 1, [{"index": {"_id": "broken", "status": 500}}]

    monkeypatch.setattr(search_service, "async_bulk", fake_bulk)
    monkeypatch.setattr(
        search_service,
        "get_settings",
        lambda: SimpleNamespace(elasticsearch_index="documents"),
    )

    with pytest.raises(RuntimeError, match="broken"):
        await search_service.bulk_index_documents(
            object(),
            [{"id": "1", "text": "text"}],
        )


@pytest.mark.asyncio
async def test_delete_waits_for_refresh_and_accepts_missing_document(monkeypatch) -> None:
    calls = []

    class Client:
        def options(self, **kwargs):
            calls.append(("options", kwargs))
            return self

        async def delete(self, **kwargs):
            calls.append(("delete", kwargs))
            return {"result": "not_found"}

    monkeypatch.setattr(
        search_service,
        "get_settings",
        lambda: SimpleNamespace(elasticsearch_index="documents"),
    )

    assert not await search_service.delete_document_from_index(Client(), "1")
    assert calls == [
        ("options", {"ignore_status": 404}),
        (
            "delete",
            {"index": "documents", "id": "1", "refresh": "wait_for"},
        ),
    ]
