from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(documents_router)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request,
        __: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "Некорректные параметры запроса"},
        )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "version": settings.app_version}

    def custom_openapi() -> dict:
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                routes=app.routes,
            )
            schema["paths"]["/documents/{document_id}"]["delete"]["responses"].pop(
                "422",
                None,
            )
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi

    return app


app = create_app()
