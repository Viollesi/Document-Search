.PHONY: up down migrate import-data test functional-test docs docs-check

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	docker compose run --rm api alembic upgrade head

import-data:
	docker compose run --rm api python -m app.scripts.import_data

test:
	.venv/bin/python -m pytest -q --ignore=tests/functional

functional-test:
	./scripts/run_functional_tests.sh

docs:
	.venv/bin/python -m app.scripts.generate_openapi

docs-check:
	.venv/bin/python -m pytest -q tests/test_openapi.py
