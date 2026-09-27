"""Tests for BookService business logic and duplicate prevention upserting."""
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.book import Book
from app.scraper.book_scraper import ScrapedBook
from app.services.book_service import BookService


def test_upsert_scraped_books_inserts_and_prevents_duplicates(db_session: Session):
    """
    Critical requirement test:
    Running the scraper batch twice with the same canonical URL must update
    the existing record and NEVER create duplicate rows.
    """
    # Batch 1: Initial scrape with 2 books
    initial_batch = [
        ScrapedBook(
            title="Book Alpha",
            price=25.00,
            rating=4,
            availability="In stock",
            category="Science",
            source_url="https://books.toscrape.com/catalogue/book-alpha_1/index.html",
        ),
        ScrapedBook(
            title="Book Beta",
            price=40.00,
            rating=2,
            availability="In stock",
            category="Art",
            source_url="https://books.toscrape.com/catalogue/book-beta_2/index.html",
        ),
    ]

    inserted, updated = BookService.upsert_scraped_books(db_session, initial_batch)
    assert inserted == 2
    assert updated == 0

    # Verify database has exactly 2 records
    total = db_session.query(Book).count()
    assert total == 2

    # Batch 2: Subsequent scrape containing updated prices and ratings for the SAME books
    subsequent_batch = [
        ScrapedBook(
            title="Book Alpha (Updated Edition)",
            price=19.99,  # Price dropped
            rating=5,      # Rating increased
            availability="In stock",
            category="Science",
            source_url="https://books.toscrape.com/catalogue/book-alpha_1/index.html",  # Identical URL
        ),
        ScrapedBook(
            title="Book Beta",
            price=42.50,  # Price increased
            rating=3,
            availability="Out of stock",  # Stock changed
            category="Art",
            source_url="https://books.toscrape.com/catalogue/book-beta_2/index.html",  # Identical URL
        ),
        ScrapedBook(
            title="Book Gamma",  # Brand new book
            price=15.00,
            rating=4,
            availability="In stock",
            category="History",
            source_url="https://books.toscrape.com/catalogue/book-gamma_3/index.html",
        ),
    ]

    inserted_2, updated_2 = BookService.upsert_scraped_books(db_session, subsequent_batch)
    assert inserted_2 == 1  # Only Book Gamma is new
    assert updated_2 == 2   # Book Alpha and Beta were updated

    # Total in database must now be exactly 3, NOT 5
    all_books = db_session.scalars(select(Book).order_by(Book.id)).all()
    assert len(all_books) == 3

    # Check that Book Alpha's price and rating were updated
    book_alpha = db_session.scalars(
        select(Book).where(Book.source_url == "https://books.toscrape.com/catalogue/book-alpha_1/index.html")
    ).first()
    assert book_alpha is not None
    assert book_alpha.title == "Book Alpha (Updated Edition)"
    assert book_alpha.price == 19.99
    assert book_alpha.rating == 5

    # Check Book Beta
    book_beta = db_session.scalars(
        select(Book).where(Book.source_url == "https://books.toscrape.com/catalogue/book-beta_2/index.html")
    ).first()
    assert book_beta.price == 42.50
    assert book_beta.availability == "Out of stock"


def test_upsert_scraped_books_dedupes_within_batch_last_wins(db_session: Session):
    """
    Duplicate source_url values in one batch must not raise IntegrityError.
    Rule: the last record in the batch wins.
    """
    duplicate_url = "https://books.toscrape.com/catalogue/dup-book_99/index.html"
    batch = [
        ScrapedBook(
            title="First Seen Title",
            price=10.00,
            rating=1,
            availability="In stock",
            category="Poetry",
            source_url=duplicate_url,
        ),
        ScrapedBook(
            title="Last Seen Title",
            price=25.50,
            rating=4,
            availability="Out of stock",
            category="Poetry",
            source_url=duplicate_url,
        ),
    ]

    inserted, updated = BookService.upsert_scraped_books(db_session, batch)
    assert inserted == 1
    assert updated == 0

    rows = db_session.scalars(select(Book)).all()
    assert len(rows) == 1
    assert rows[0].title == "Last Seen Title"
    assert rows[0].price == 25.50
    assert rows[0].rating == 4
    assert rows[0].availability == "Out of stock"


def test_book_service_filtering_and_pagination(db_session: Session, seed_books):
    """Verifies service-layer get_books query builder directly."""
    # Test min_price filter
    items, total, total_pages = BookService.get_books(db=db_session, min_price=50.0)
    assert total == 4
    for b in items:
        assert b.price >= 50.0

    # Test category filter
    items, total, _ = BookService.get_books(db=db_session, category="History")
    assert total == 1
    assert items[0].title == "Sapiens: A Brief History of Humankind"
