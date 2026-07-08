from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    """Документ для хранения в PostgreSQL."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    rubrics: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
