from datetime import datetime, timezone
from math import ceil
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.book import Book
from app.scraper.book_scraper import ScrapedBook


class BookService:
    """Encapsulates all database query logic, filtering, pagination, and upsert handling."""

    @staticmethod
    def _dedupe_batch_by_source_url(scraped_books: List[ScrapedBook]) -> List[ScrapedBook]:
        """
        Collapse duplicate source_url entries within one scrape batch.
        Rule: the last record in the batch wins (later scrape order overrides earlier).
        """
        deduped: dict[str, ScrapedBook] = {}
        for item in scraped_books:
            deduped[item.source_url] = item
        return list(deduped.values())

    @staticmethod
    def get_books(
        db: Session,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        page: int = 1,
        limit: int = 10,
    ) -> Tuple[List[Book], int, int]:
        """
        Retrieves paginated books with optional filtering by category and price range.
        Returns: (items, total_count, total_pages)
        """
        query = select(Book)

        # Apply category filter (case-insensitive)
        if category:
            query = query.where(func.lower(Book.category) == category.strip().lower())

        # Apply price range filters
        if min_price is not None:
            query = query.where(Book.price >= min_price)
        if max_price is not None:
            query = query.where(Book.price <= max_price)

        # Calculate total matching count
        count_query = select(func.count()).select_from(query.subquery())
        total_count = db.scalar(count_query) or 0

        # Calculate total pages
        total_pages = ceil(total_count / limit) if total_count > 0 else 0

        # Apply pagination (offset & limit) and ordering
        offset = (page - 1) * limit
        paginated_query = query.order_by(Book.id.asc()).offset(offset).limit(limit)
        items = list(db.scalars(paginated_query).all())

        return items, total_count, total_pages

    @staticmethod
    def get_book_by_id(db: Session, book_id: int) -> Optional[Book]:
        """Fetches a single book by its primary key ID."""
        return db.get(Book, book_id)

    @staticmethod
    def upsert_scraped_books(
        db: Session,
        scraped_books: List[ScrapedBook],
    ) -> Tuple[int, int]:
        """
        Inserts new books or updates existing records identified by source_url.
        Guarantees that multiple scraper runs never produce duplicate records.
        Returns: (inserted_count, updated_count)
        """
        inserted_count = 0
        updated_count = 0
        now = datetime.now(timezone.utc)
        scraped_books = BookService._dedupe_batch_by_source_url(scraped_books)

        for item in scraped_books:
            existing = db.scalars(
                select(Book).where(Book.source_url == item.source_url)
            ).first()

            if existing:
                # Update existing book record with latest scraped metrics
                existing.title = item.title
                existing.price = item.price
                existing.rating = item.rating
                existing.availability = item.availability
                existing.category = item.category
                existing.scraped_at = now
                updated_count += 1
            else:
                # Insert brand new book
                new_book = Book(
                    title=item.title,
                    price=item.price,
                    rating=item.rating,
                    availability=item.availability,
                    category=item.category,
                    source_url=item.source_url,
                    scraped_at=now,
                )
                db.add(new_book)
                inserted_count += 1

        db.commit()
        logger.info(
            f"Upsert batch complete: {inserted_count} inserted, {updated_count} updated."
        )
        return inserted_count, updated_count
