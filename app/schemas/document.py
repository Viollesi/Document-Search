from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: str
    rubrics: list[str]
    text: str
    created_date: datetime

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    postgres: bool
    elasticsearch: bool
