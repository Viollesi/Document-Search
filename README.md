# Document Search

Асинхронный HTTP-сервис поиска по текстам документов. PostgreSQL хранит полные
документы, Elasticsearch — только поисковые поля `id` и `text`.

## Стек и требования

- Python 3.12 или новее;
- FastAPI, SQLAlchemy Async, asyncpg, Alembic;
- PostgreSQL 16;
- Elasticsearch 8.x (Compose использует 8.17.0, Python-клиент ограничен 8.x);
- Docker с Compose v2 — для основного и функционального сценариев.

## Данные и технические допущения

Исходный CSV: <https://disk.yandex.ru/d/UYooXd9q2yqTMQ>. Скачайте `posts.csv` в
`data/posts.csv`; файл исключён из Git.

CSV обязан содержать `text`, `created_date`, `rubrics`; колонка `id`
необязательна. Если `id` отсутствует, пуст или состоит из пробелов, импортер
назначает строковые ID `"1"`, `"2"`, … по порядку записей. Поэтому такие ID
стабильны для неизменённого файла, но зависят от порядка строк. Дубликаты ID
отклоняются до обращения к хранилищам.

Принятые проектом допущения (исходное задание их однозначно не задаёт):

- Elasticsearch ранжирует совпадения по релевантности;
- сервис ограниченно просматривает до 100 совпадений и собирает первые 20
  уникальных ID, для которых документы ещё существуют в PostgreSQL;
- итоговая выборка сортируется по `created_date DESC`, затем по строковому `id`;
- дата без timezone считается UTC, `Z` считается UTC, явный offset переводится
  в UTC. Это техническое правило импорта, а не утверждение о timezone источника.

Повторный импорт работает как upsert и обновляет, в том числе, изменившийся
`text`. Записи, исчезнувшие из нового CSV, автоматически не удаляются.
PostgreSQL и Elasticsearch не образуют общую транзакцию: если индексирование
сломалось после коммита PostgreSQL, импортер завершится ошибкой, а повторный
запуск восстановит индекс. Удаление также не является распределённо атомарным:
транзакция PostgreSQL коммитится только после успешной очистки Elasticsearch.

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

## Функциональная проверка

Изолированный сценарий использует проект Compose `document-search-test`, порты
`18000`, `15432`, `19200` и `tmpfs`, не затрагивая volumes основного окружения.
Он собирает image, ожидает readiness, выполняет `upgrade`, `downgrade`, повторный
`upgrade` и безопасный повторный `upgrade`, дважды импортирует небольшой fixture,
проверяет PostgreSQL, mapping и
`_source` Elasticsearch, health, поиск, лимит, сортировку и повторный DELETE.
Тестовое окружение удаляется обработчиком завершения:

```bash
make functional-test
```

Если реальный CSV уже скачан вне репозитория, тот же сценарий дополнительно
проверит полный импорт 1500 записей:

```bash
REAL_DATASET_PATH=/absolute/path/to/posts.csv make functional-test
```

## OpenAPI

`docs.json` генерируется непосредственно из `app.openapi()`:

```bash
make docs
make docs-check
```

Интерактивные страницы запущенного API: <http://localhost:8000/docs> и
<http://localhost:8000/redoc>.

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
