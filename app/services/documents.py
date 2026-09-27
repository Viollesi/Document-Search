from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document


async def get_documents_by_ids(
    session: AsyncSession,
    document_ids: list[str],
) -> list[Document]:
    if not document_ids:
        return []

    result = await session.execute(
        select(Document)
        .where(Document.id.in_(document_ids))
        .order_by(desc(Document.created_date), Document.id.asc())
    )
    return list(result.scalars().all())


async def delete_document(session: AsyncSession, document_id: str) -> bool:
    """Подготавливает удаление документа без завершения транзакции."""
    result = await session.execute(
        delete(Document)
        .where(Document.id == document_id)
        .returning(Document.id)
    )
    deleted_id = result.scalar_one_or_none()

    return deleted_id is not None
