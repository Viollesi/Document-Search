from typing import Annotated

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.document import DocumentResponse
from app.search.client import get_elasticsearch_client
from app.services.documents import delete_document, get_documents_by_ids
from app.services.search import delete_document_from_index, search_document_ids

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/search", response_model=list[DocumentResponse])
async def search_documents(
    q: Annotated[str, Query(min_length=1)],
    session: Annotated[AsyncSession, Depends(get_session)],
    elasticsearch: Annotated[AsyncElasticsearch, Depends(get_elasticsearch_client)],
) -> list[DocumentResponse]:
    document_ids = await search_document_ids(elasticsearch, q, limit=20)

    if not document_ids:
        return []

    documents = await get_documents_by_ids(session, document_ids)
    return [DocumentResponse.model_validate(document) for document in documents]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document(
    document_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    elasticsearch: Annotated[AsyncElasticsearch, Depends(get_elasticsearch_client)],
) -> Response:
    is_deleted = await delete_document(session, document_id)

    if not is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Документ не найден",
        )

    await delete_document_from_index(elasticsearch, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
