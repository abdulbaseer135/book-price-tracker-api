from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Book(Base):
    """SQLAlchemy ORM Model representing a book scraped from books.toscrape.com."""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    availability: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False, index=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        # Composite index for optimized queries filtering by both category and price range
        Index("ix_books_category_price", "category", "price"),
    )

    def __repr__(self) -> str:
        return f"<Book(id={self.id}, title='{self.title[:30]}...', price={self.price}, category='{self.category}')>"
