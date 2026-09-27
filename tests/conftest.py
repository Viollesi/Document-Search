from collections.abc import AsyncGenerator

import httpx
import pytest

from app.db.session import get_session
from app.main import app
from app.search.client import get_elasticsearch_client


class FakeSession:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def commit(self) -> None:
        self.events.append("commit")

    async def rollback(self) -> None:
        self.events.append("rollback")


async def override_elasticsearch_client() -> AsyncGenerator[object, None]:
    yield object()


@pytest.fixture
def client_session() -> FakeSession:
    return FakeSession()


@pytest.fixture
async def client(client_session: FakeSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    async def override_session() -> AsyncGenerator[FakeSession, None]:
        yield client_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_elasticsearch_client] = override_elasticsearch_client

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
