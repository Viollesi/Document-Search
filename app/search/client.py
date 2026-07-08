from collections.abc import AsyncGenerator

from elasticsearch import AsyncElasticsearch

from app.core.config import get_settings


async def get_elasticsearch_client() -> AsyncGenerator[AsyncElasticsearch, None]:
    settings = get_settings()
    client = AsyncElasticsearch(settings.elasticsearch_url)

    try:
        yield client
    finally:
        await client.close()
