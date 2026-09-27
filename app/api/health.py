import logging

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine
from app.schemas.document import HealthResponse

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Зависимость недоступна"}},
)
async def healthcheck() -> JSONResponse:
    postgres_ok = await _check_postgres()
    elasticsearch_ok = await _check_elasticsearch()
    is_healthy = postgres_ok and elasticsearch_ok

    return JSONResponse(
        status_code=status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if is_healthy else "error",
            "postgres": postgres_ok,
            "elasticsearch": elasticsearch_ok,
        },
    )


async def _check_postgres() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Проверка PostgreSQL завершилась ошибкой")
        return False

    return True


async def _check_elasticsearch() -> bool:
    client = AsyncElasticsearch(get_settings().elasticsearch_url)
    try:
        is_healthy = await client.ping()
    except Exception:
        logger.exception("Проверка Elasticsearch завершилась ошибкой")
        is_healthy = False

    try:
        await client.close()
    except Exception:
        logger.exception("Закрытие клиента Elasticsearch завершилось ошибкой")
        return False

    return is_healthy
