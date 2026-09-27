import pytest

from app.api import health as health_api


@pytest.mark.asyncio
async def test_healthcheck_returns_ok_when_dependencies_are_available(
    client,
    monkeypatch,
) -> None:
    async def fake_check_postgres() -> bool:
        return True

    async def fake_check_elasticsearch() -> bool:
        return True

    monkeypatch.setattr(health_api, "_check_postgres", fake_check_postgres)
    monkeypatch.setattr(health_api, "_check_elasticsearch", fake_check_elasticsearch)

    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "postgres": True,
        "elasticsearch": True,
    }


@pytest.mark.asyncio
async def test_healthcheck_returns_503_when_dependency_is_unavailable(
    client,
    monkeypatch,
) -> None:
    async def fake_check_postgres() -> bool:
        return True

    async def fake_check_elasticsearch() -> bool:
        return False

    monkeypatch.setattr(health_api, "_check_postgres", fake_check_postgres)
    monkeypatch.setattr(health_api, "_check_elasticsearch", fake_check_elasticsearch)

    response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "postgres": True,
        "elasticsearch": False,
    }


@pytest.mark.asyncio
async def test_elasticsearch_healthcheck_closes_client(monkeypatch) -> None:
    events = []

    class Client:
        def __init__(self, url: str) -> None:
            events.append(("create", url))

        async def ping(self) -> bool:
            events.append(("ping",))
            return True

        async def close(self) -> None:
            events.append(("close",))

    monkeypatch.setattr(health_api, "AsyncElasticsearch", Client)

    assert await health_api._check_elasticsearch()
    assert events == [
        ("create", "http://localhost:9200"),
        ("ping",),
        ("close",),
    ]
