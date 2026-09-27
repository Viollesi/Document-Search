from datetime import UTC, datetime

import pytest

from app.scripts.import_data import parse_created_date, parse_documents, parse_rubrics


def test_parse_documents_generates_stable_ids_without_id_column() -> None:
    csv_content = (
        "text,created_date,rubrics\n"
        "First,2024-01-01T00:00:00,['news']\n"
        "Second,2024-01-02T00:00:00Z,\n"
    )
    assert [row["id"] for row in parse_documents(csv_content)] == ["1", "2"]


def test_parse_documents_preserves_ids_and_generates_blank_ids() -> None:
    csv_content = (
        "id,text,created_date,rubrics\n"
        "custom,First,2024-01-01T00:00:00Z,news\n"
        ",Second,2024-01-02T00:00:00Z,sport\n"
        "   ,Third,2024-01-03T00:00:00Z,tech\n"
    )
    assert [row["id"] for row in parse_documents(csv_content)] == ["custom", "2", "3"]


def test_parse_documents_rejects_duplicate_ids_with_rows() -> None:
    content = (
        "id,text,created_date,rubrics\n"
        "same,First,2024-01-01T00:00:00Z,news\n"
        "same,Second,2024-01-02T00:00:00Z,sport\n"
    )
    with pytest.raises(ValueError, match="строке 3.*строки 2"):
        parse_documents(content)


@pytest.mark.parametrize("field", ["text", "created_date", "rubrics"])
def test_parse_documents_requires_columns(field: str) -> None:
    fields = [name for name in ("text", "created_date", "rubrics") if name != field]
    with pytest.raises(ValueError, match=field):
        parse_documents(",".join(fields) + "\n")


def test_parse_documents_rejects_file_without_headers() -> None:
    with pytest.raises(ValueError, match="заголовков"):
        parse_documents("")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", []),
        ("['news', 'sport']", ["news", "sport"]),
        ("news; sport; tech", ["news", "sport", "tech"]),
        ("news,sport", ["news", "sport"]),
    ],
)
def test_parse_rubrics(value: str, expected: list[str]) -> None:
    assert parse_rubrics(value) == expected


@pytest.mark.parametrize("value", ["[broken", "broken]", "{'news': 1}", "['ok', 1]"])
def test_parse_rubrics_rejects_invalid_format(value: str) -> None:
    with pytest.raises(ValueError, match="rubrics"):
        parse_rubrics(value, 7)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2024-01-01T12:00:00", datetime(2024, 1, 1, 12, tzinfo=UTC)),
        ("2024-01-01T12:00:00Z", datetime(2024, 1, 1, 12, tzinfo=UTC)),
        ("2024-01-01T15:00:00+03:00", datetime(2024, 1, 1, 12, tzinfo=UTC)),
        ("2024-01-01T09:00:00-03:00", datetime(2024, 1, 1, 12, tzinfo=UTC)),
    ],
)
def test_parse_created_date_normalizes_to_utc(value: str, expected: datetime) -> None:
    assert parse_created_date(value, 2) == expected


def test_parse_created_date_reports_row() -> None:
    with pytest.raises(ValueError, match="строке 9"):
        parse_created_date("not-a-date", 9)
