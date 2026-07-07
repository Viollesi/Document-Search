from fastapi import FastAPI

from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": settings.app_name, "version": settings.app_version}

    return app


app = create_app()
