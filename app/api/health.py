from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.session import engine
from app.search.client import get_elasticsearch_client

router = APIRouter(tags=["health"])


@router.get("/health")
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
        return False

    return True


async def _check_elasticsearch() -> bool:
    try:
        async for client in get_elasticsearch_client():
            return await client.ping()
    except Exception:
        return False

    return False
