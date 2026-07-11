import ast
import asyncio
import csv
import logging
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import TypedDict
from urllib.parse import unquote, urlparse

import httpx
from elasticsearch import AsyncElasticsearch
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.db.models import Document
from app.db.session import async_session_factory, engine
from app.services.search import bulk_index_documents, ensure_documents_index

logger = logging.getLogger(__name__)


class DocumentRow(TypedDict):
    id: str
    rubrics: list[str]
    text: str
    created_date: datetime


REQUIRED_FIELDS = ("text", "created_date", "rubrics")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    settings = get_settings()

    try:
        if not settings.dataset_url:
            raise ValueError("Не задана переменная окружения DATASET_URL")

        csv_content = await read_csv_content(settings.dataset_url)
        documents = parse_documents(csv_content)

        if not documents:
            logger.info("CSV не содержит документов для импорта")
            return

        await upsert_documents(documents)
        indexed_count = await index_documents(documents)

        logger.info(
            "Импорт завершён: документов в БД %s, в индексе %s",
            len(documents),
            indexed_count,
        )
    finally:
        await engine.dispose()


async def read_csv_content(dataset_url: str) -> str:
    parsed_url = urlparse(dataset_url)

    if parsed_url.scheme in {"http", "https"}:
        async with httpx.AsyncClient() as client:
            response = await client.get(dataset_url)
            response.raise_for_status()
            return response.text

    if parsed_url.scheme == "file":
        file_path = Path(unquote(parsed_url.path))

        if not file_path.is_file():
            raise FileNotFoundError(f"CSV-файл не найден: {file_path}")

        return file_path.read_text(encoding="utf-8")

    raise ValueError("DATASET_URL должен начинаться с http://, https:// или file://")


def parse_documents(csv_content: str) -> list[DocumentRow]:
    reader = csv.DictReader(StringIO(csv_content))

    if reader.fieldnames is None:
        raise ValueError("CSV не содержит заголовков")

    missing_fields = set(REQUIRED_FIELDS) - set(reader.fieldnames)
    if missing_fields:
        fields = ", ".join(sorted(missing_fields))
        raise ValueError(f"В CSV отсутствуют обязательные поля: {fields}")

    documents: list[DocumentRow] = []
    for row_number, row in enumerate(reader, start=2):
        documents.append(parse_document_row(row, row_number))

    return documents


def parse_document_row(row: dict[str, str], row_number: int) -> DocumentRow:
    document_id = (row.get("id") or str(row_number - 1)).strip()
    text = row.get("text") or ""
    created_date = (row.get("created_date") or "").strip()

    if not document_id:
        raise ValueError(f"В строке {row_number} не заполнено поле id")

    if not created_date:
        raise ValueError(f"В строке {row_number} не заполнено поле created_date")

    return {
        "id": document_id,
        "rubrics": parse_rubrics(row.get("rubrics") or ""),
        "text": text,
        "created_date": parse_created_date(created_date, row_number),
    }


def parse_rubrics(value: str) -> list[str]:
    value = value.strip()

    if not value:
        return []

    try:
        parsed_value = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        parsed_value = None

    if isinstance(parsed_value, list):
        return [str(item).strip() for item in parsed_value if str(item).strip()]

    separator = ";" if ";" in value else ","
    return [item.strip().strip("'\"") for item in value.split(separator) if item.strip()]


def parse_created_date(value: str, row_number: int) -> datetime:
    normalized_value = value.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(normalized_value)
    except ValueError as error:
        raise ValueError(
            f"В строке {row_number} некорректное поле created_date: {value}",
        ) from error


async def upsert_documents(documents: list[DocumentRow]) -> None:
    statement = insert(Document).values(documents)
    update_columns = {
        "rubrics": statement.excluded.rubrics,
        "text": statement.excluded.text,
        "created_date": statement.excluded.created_date,
    }
    statement = statement.on_conflict_do_update(
        index_elements=[Document.id],
        set_=update_columns,
    )

    async with async_session_factory() as session:
        await session.execute(statement)
        await session.commit()

    logger.info("Документы сохранены в PostgreSQL: %s", len(documents))


async def index_documents(documents: list[DocumentRow]) -> int:
    settings = get_settings()
    client = AsyncElasticsearch(settings.elasticsearch_url)

    try:
        await ensure_documents_index(client)
        return await bulk_index_documents(
            client,
            [
                {"id": document["id"], "text": document["text"]}
                for document in documents
            ],
        )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
