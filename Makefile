.PHONY: up down migrate import-data test docs

up:
	docker compose up -d --build

down:
	docker compose down

migrate:
	docker compose run --rm api alembic upgrade head

import-data:
	docker compose run --rm api python -m app.scripts.import_data

test:
	docker compose run --rm api pytest

docs:
	python -m app.scripts.generate_openapi
