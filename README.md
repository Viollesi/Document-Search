# Document Search

Простой сервис поиска по текстам документов.

## Стек

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy async
- asyncpg
- Alembic
- Elasticsearch
- Pydantic Settings
- pytest, pytest-asyncio, httpx
- Docker, docker-compose

## Возможности

- `GET /documents/search?q=...` — поиск документов по тексту.
- `DELETE /documents/{document_id}` — удаление документа из PostgreSQL и Elasticsearch.
- `GET /health` — проверка доступности API, PostgreSQL и Elasticsearch.
- `app/scripts/import_data.py` — импорт CSV в PostgreSQL и Elasticsearch.

## Настройка окружения

Скопируйте пример переменных окружения:

```bash
cp .env.example .env
```

Пример `.env`:

```env
APP_NAME=Document Search
APP_VERSION=0.1.0
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/documents
ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX=documents
DATASET_URL=file:///app/data/posts.csv
```

При запуске через Docker значения подключения к PostgreSQL и Elasticsearch уже заданы в `docker-compose.yml`.

## CSV-файл

CSV-файл не хранится в репозитории. Перед импортом положите его сюда:

```text
data/posts.csv
```

В Docker эта директория монтируется как `/app/data`, поэтому значение для импорта:

```env
DATASET_URL=file:///app/data/posts.csv
```


## Запуск в Docker

Поднимите сервисы:

```bash
make up
```

Примените миграции:

```bash
make migrate
```

Импортируйте данные:

```bash
make import-data
```

API будет доступен по адресу:

```text
http://localhost:8000
```

## Примеры запросов

Healthcheck:

```bash
curl http://localhost:8000/health
```

Поиск:

```bash
curl "http://localhost:8000/documents/search?q=example"
```

Удаление:

```bash
curl -X DELETE http://localhost:8000/documents/1
```

## OpenAPI

OpenAPI-документация лежит в корне проекта:

```text
docs.json
```

Сгенерировать файл заново:

```bash
make docs
```

Также после запуска API доступны стандартные страницы FastAPI:

```text
http://localhost:8000/docs
http://localhost:8000/redoc
```

## Тесты

Запуск тестов в Docker:

```bash
make test
```

Локальный запуск:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Остановка

Остановить контейнеры:

```bash
make down
```

## Примечания

- CSV не читается при поисковом запросе, он используется только на этапе импорта.
- Elasticsearch хранит только `id` и `text`.
- Полные документы возвращаются из PostgreSQL.
- Повторный импорт идемпотентен: существующие документы обновляются по `id`.
