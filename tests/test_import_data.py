from datetime import UTC, datetime

from app.scripts.import_data import parse_documents, parse_rubrics


def test_parse_documents_reads_required_csv_fields() -> None:
    csv_content = (
        "id,rubrics,text,created_date\n"
        "1,\"['news', 'sport']\",Document text,2024-01-01T00:00:00Z\n"
    )

    documents = parse_documents(csv_content)

    assert documents == [
        {
            "id": "1",
            "rubrics": ["news", "sport"],
            "text": "Document text",
            "created_date": datetime(2024, 1, 1, tzinfo=UTC),
        }
    ]


def test_parse_rubrics_supports_delimited_string() -> None:
    assert parse_rubrics("news; sport; tech") == ["news", "sport", "tech"]
