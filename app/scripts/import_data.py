import ast
import asyncio
import csv
import logging
from datetime import UTC, datetime
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

        try:
            csv_content = await read_csv_content(settings.dataset_url)
            documents = parse_documents(csv_content)
        except Exception as error:
            raise RuntimeError(f"Ошибка чтения или разбора CSV: {error}") from error

        if not documents:
            logger.info("CSV не содержит документов для импорта")
            return

        try:
            await upsert_documents(documents)
        except Exception as error:
            raise RuntimeError(f"Ошибка сохранения в PostgreSQL: {error}") from error

        try:
            indexed_count = await index_documents(documents)
        except Exception as error:
            raise RuntimeError(f"Ошибка индексации в Elasticsearch: {error}") from error

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
    document_rows: dict[str, int] = {}
    for row_number, row in enumerate(reader, start=2):
        document = parse_document_row(row, row_number)
        previous_row = document_rows.get(document["id"])
        if previous_row is not None:
            raise ValueError(
                f"В строке {row_number} дублируется id {document['id']!r} "
                f"из строки {previous_row}",
            )
        document_rows[document["id"]] = row_number
        documents.append(document)

    return documents


def parse_document_row(row: dict[str, str], row_number: int) -> DocumentRow:
    raw_document_id = row.get("id")
    document_id = (raw_document_id or "").strip() or str(row_number - 1)
    text = row.get("text") or ""
    created_date = (row.get("created_date") or "").strip()

    if not created_date:
        raise ValueError(f"В строке {row_number} не заполнено поле created_date")

    return {
        "id": document_id,
        "rubrics": parse_rubrics(row.get("rubrics") or "", row_number),
        "text": text,
        "created_date": parse_created_date(created_date, row_number),
    }


def parse_rubrics(value: str, row_number: int | None = None) -> list[str]:
    value = value.strip()

    if not value:
        return []

    if value.startswith("[") or value.endswith("]"):
        try:
            parsed_value = ast.literal_eval(value)
        except (ValueError, SyntaxError) as error:
            raise _rubrics_error(row_number) from error

        if not isinstance(parsed_value, list) or any(
            not isinstance(item, str) for item in parsed_value
        ):
            raise _rubrics_error(row_number)
        return [item.strip() for item in parsed_value if item.strip()]

    if any(character in value for character in "[]{}()"):
        raise _rubrics_error(row_number)

    separator = ";" if ";" in value else ","
    rubrics = []
    for item in value.split(separator):
        item = item.strip()
        if "'" in item or '"' in item:
            if len(item) < 2 or item[0] not in "'\"" or item[-1] != item[0]:
                raise _rubrics_error(row_number)
            item = item[1:-1].strip()
        rubrics.append(item)
    if any(not item for item in rubrics):
        raise _rubrics_error(row_number)
    return rubrics


def _rubrics_error(row_number: int | None) -> ValueError:
    location = f" в строке {row_number}" if row_number is not None else ""
    return ValueError(f"Некорректный формат поля rubrics{location}")


def parse_created_date(value: str, row_number: int) -> datetime:
    normalized_value = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value

    try:
        parsed_date = datetime.fromisoformat(normalized_value)
    except ValueError as error:
        raise ValueError(
            f"В строке {row_number} некорректное поле created_date: {value}",
        ) from error

    if parsed_date.tzinfo is None:
        return parsed_date.replace(tzinfo=UTC)
    return parsed_date.astimezone(UTC)


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
        async with session.begin():
            await session.execute(statement)

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
