import logging
from typing import Annotated

from asyncpg import PostgresError
from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import TransportError
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.document import DocumentResponse, ErrorResponse
from app.search.client import get_elasticsearch_client
from app.services.documents import delete_document, get_documents_by_ids
from app.services.search import delete_document_from_index, search_document_ids

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)

SEARCH_LIMIT = 20
SEARCH_BATCH_SIZE = 20
SEARCH_SCAN_LIMIT = 100


@router.get(
    "/search",
    response_model=list[DocumentResponse],
    responses={
        422: {"model": ErrorResponse, "description": "Некорректный поисковый запрос"},
        503: {"model": ErrorResponse, "description": "Хранилище недоступно"},
    },
)
async def search_documents(
    q: Annotated[str, Query(min_length=1, pattern=r".*\S.*")],
    session: Annotated[AsyncSession, Depends(get_session)],
    elasticsearch: Annotated[AsyncElasticsearch, Depends(get_elasticsearch_client)],
) -> list[DocumentResponse]:
    normalized_query = q.strip()
    documents_by_id = {}
    seen_ids: set[str] = set()

    try:
        for offset in range(0, SEARCH_SCAN_LIMIT, SEARCH_BATCH_SIZE):
            document_ids = await search_document_ids(
                elasticsearch,
                normalized_query,
                limit=SEARCH_BATCH_SIZE,
                offset=offset,
            )
            unique_ids = [
                document_id
                for document_id in document_ids
                if document_id not in seen_ids
            ]
            seen_ids.update(unique_ids)

            if unique_ids:
                for document in await get_documents_by_ids(session, unique_ids):
                    documents_by_id[document.id] = document
                    if len(documents_by_id) == SEARCH_LIMIT:
                        break

            if len(documents_by_id) == SEARCH_LIMIT or len(document_ids) < SEARCH_BATCH_SIZE:
                break
    except (TransportError, SQLAlchemyError, PostgresError, OSError):
        logger.exception("Ошибка зависимости при поиске документов")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Хранилище документов недоступно",
        )
    except Exception:
        logger.exception("Непредвиденная ошибка при поиске документов")
        raise

    documents = sorted(
        documents_by_id.values(),
        key=lambda document: (-document.created_date.timestamp(), document.id),
    )
    return [DocumentResponse.model_validate(document) for document in documents]


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse, "description": "Документ не найден"},
        503: {"model": ErrorResponse, "description": "Хранилище недоступно"},
    },
)
async def remove_document(
    document_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    elasticsearch: Annotated[AsyncElasticsearch, Depends(get_elasticsearch_client)],
) -> Response:
    try:
        is_deleted = await delete_document(session, document_id)
        await delete_document_from_index(elasticsearch, document_id)
        if not is_deleted:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Документ не найден",
            )
        await session.commit()
    except HTTPException:
        raise
    except (TransportError, SQLAlchemyError, PostgresError, OSError):
        await session.rollback()
        logger.exception("Ошибка зависимости при удалении документа id=%s", document_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Хранилище документов недоступно",
        )
    except Exception:
        await session.rollback()
        logger.exception("Непредвиденная ошибка при удалении документа id=%s", document_id)
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)
