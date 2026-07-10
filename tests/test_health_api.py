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
