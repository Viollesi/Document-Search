#!/bin/sh
set -eu

project_name="document-search-test"
compose_file="docker-compose.test.yml"

cleanup() {
    docker compose -p "$project_name" -f "$compose_file" down --volumes --remove-orphans
}
trap cleanup EXIT INT TERM

cleanup
docker compose -p "$project_name" -f "$compose_file" build api
docker compose -p "$project_name" -f "$compose_file" up -d --wait postgres elasticsearch
docker compose -p "$project_name" -f "$compose_file" run --rm api alembic upgrade head
docker compose -p "$project_name" -f "$compose_file" run --rm api alembic downgrade base
docker compose -p "$project_name" -f "$compose_file" run --rm api alembic upgrade head
docker compose -p "$project_name" -f "$compose_file" run --rm api alembic upgrade head
docker compose -p "$project_name" -f "$compose_file" run --rm api python -m app.scripts.import_data
docker compose -p "$project_name" -f "$compose_file" run --rm api python -m app.scripts.import_data
docker compose -p "$project_name" -f "$compose_file" up -d --wait api

RUN_FUNCTIONAL=1 \
FUNCTIONAL_API_URL=http://localhost:18000 \
FUNCTIONAL_DATABASE_URL=postgresql://postgres:postgres@localhost:15432/documents_test \
FUNCTIONAL_ELASTICSEARCH_URL=http://localhost:19200 \
FUNCTIONAL_ELASTICSEARCH_INDEX=documents_test \
.venv/bin/python -m pytest -q tests/functional

if [ -n "${REAL_DATASET_PATH:-}" ]; then
    docker compose -p "$project_name" -f "$compose_file" run --rm \
        --volume "$REAL_DATASET_PATH:/tmp/posts.csv:ro" \
        --env DATASET_URL=file:///tmp/posts.csv \
        api python -m app.scripts.import_data
    docker compose -p "$project_name" -f "$compose_file" run --rm \
        --volume "$REAL_DATASET_PATH:/tmp/posts.csv:ro" \
        --env DATASET_URL=file:///tmp/posts.csv \
        api python -m app.scripts.import_data

    RUN_REAL_DATASET=1 \
    FUNCTIONAL_API_URL=http://localhost:18000 \
    FUNCTIONAL_DATABASE_URL=postgresql://postgres:postgres@localhost:15432/documents_test \
    FUNCTIONAL_ELASTICSEARCH_URL=http://localhost:19200 \
    FUNCTIONAL_ELASTICSEARCH_INDEX=documents_test \
    .venv/bin/python -m pytest -q tests/functional/test_real_dataset.py
fi
