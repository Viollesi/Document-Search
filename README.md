# Document Search

Асинхронный HTTP-сервис поиска по текстам документов. PostgreSQL хранит полные
документы, Elasticsearch — только поисковые поля `id` и `text`.

## Стек и требования

- Python 3.12 или новее;
- FastAPI, SQLAlchemy Async, asyncpg, Alembic;
- PostgreSQL 16;
- Elasticsearch 8.x (Compose использует 8.17.0, Python-клиент ограничен 8.x);
- Docker с Compose v2 — для основного и функционального сценариев.

## 

## Запуск через Docker

Скопируйте настройки и положите CSV в `data/posts.csv`:

```bash
cp .env.example .env
docker compose up -d --build
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.scripts.import_data
```

Compose передаёт контейнерам собственные адреса зависимостей и путь
`file:///app/data/posts.csv`; `.env.example` одновременно пригоден для локального
запуска из корня репозитория.

После импорта API доступен на <http://localhost:8000>:

```bash
curl http://localhost:8000/health
curl --get --data-urlencode "q=произвольный текст" \
  http://localhost:8000/documents/search
curl -i -X DELETE http://localhost:8000/documents/1
```

Статусы API:

- `GET /health`: `200` либо `503`;
- `GET /documents/search`: `200`, `422` для пустого/пробельного `q`, `503` при
  недоступности хранилища;
- `DELETE /documents/{document_id}`: `204` без тела, `404`, `503`.

Остановка без удаления пользовательских volumes:

```bash
docker compose down
```

## Локальный запуск и быстрые тесты

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q --ignore=tests/functional
```

Локальные PostgreSQL и Elasticsearch для быстрых тестов не нужны. Приложение
можно запустить локально после настройки `.env` и зависимостей:

```bash
alembic upgrade head
python -m app.scripts.import_data
uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

## Команды Makefile

```bash
make up               # собрать и поднять основное окружение
make migrate          # применить миграции
make import-data      # импортировать configured CSV
make test             # быстрые тесты без внешних сервисов
make functional-test  # изолированная полная проверка fixture
make docs             # обновить docs.json
make docs-check       # проверить актуальность docs.json
make down             # остановить основное окружение
```
