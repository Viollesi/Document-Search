import json
from pathlib import Path

from app.main import app


def test_docs_json_matches_application_openapi() -> None:
    assert json.loads(Path("docs.json").read_text(encoding="utf-8")) == app.openapi()


def test_openapi_documents_actual_responses() -> None:
    paths = app.openapi()["paths"]
    search = paths["/documents/search"]["get"]
    delete = paths["/documents/{document_id}"]["delete"]
    health = paths["/health"]["get"]

    assert set(search["responses"]) == {"200", "422", "503"}
    assert set(delete["responses"]) == {"204", "404", "503"}
    assert set(health["responses"]) == {"200", "503"}
    assert search["parameters"][0]["schema"]["minLength"] == 1
    assert delete["parameters"][0]["schema"]["type"] == "string"
