# Document Search

Простой поисковик по текстам документов.

## Локальный запуск

Перед импортом данных положите CSV-файл в директорию:

```text
data/documents.csv
```

Сам CSV-файл не хранится в git. В репозитории есть только пустая директория `data/`.

Для запуска внутри Docker будет использоваться путь:

```env
DATASET_URL=file:///app/data/documents.csv
```

При локальном запуске без Docker можно указать абсолютный путь к файлу:

```env
DATASET_URL=file:///absolute/path/to/test-work/data/documents.csv
```

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

После запуска приложение доступно по адресу:

```text
http://localhost:8000
```
