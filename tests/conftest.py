"""Pytest test suite configuration and fixtures."""
import os

# Required before importing app settings (no hardcoded credential defaults in config).
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db
from app.models.base import Base
from app.models.book import Book


@pytest.fixture(autouse=True)
def prevent_live_database_init(monkeypatch):
    """Prevent TestClient startup and health checks from touching localhost PostgreSQL."""
    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr("app.main.check_db_connection", lambda: True)

# In-memory SQLite engine for tests
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Creates fresh database tables for each test and yields an isolated session."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session):
    """FastAPI TestClient with overridden get_db dependency pointing to the test database."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def seed_books(db_session: Session):
    """Populates the test database with diverse sample book records."""
    now = datetime.now(timezone.utc)
    books = [
        Book(
            title="A Light in the Attic",
            price=51.77,
            rating=3,
            availability="In stock",
            category="Poetry",
            source_url="https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
            scraped_at=now,
        ),
        Book(
            title="Tipping the Velvet",
            price=53.74,
            rating=1,
            availability="In stock",
            category="Historical Fiction",
            source_url="https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html",
            scraped_at=now,
        ),
        Book(
            title="Soumission",
            price=50.10,
            rating=1,
            availability="In stock",
            category="Fiction",
            source_url="https://books.toscrape.com/catalogue/soumission_998/index.html",
            scraped_at=now,
        ),
        Book(
            title="Sharp Objects",
            price=47.82,
            rating=4,
            availability="In stock",
            category="Mystery",
            source_url="https://books.toscrape.com/catalogue/sharp-objects_997/index.html",
            scraped_at=now,
        ),
        Book(
            title="Sapiens: A Brief History of Humankind",
            price=54.23,
            rating=5,
            availability="In stock",
            category="History",
            source_url="https://books.toscrape.com/catalogue/sapiens-a-brief-history-of-humankind_996/index.html",
            scraped_at=now,
        ),
        Book(
            title="The Requiem Red",
            price=22.65,
            rating=1,
            availability="In stock",
            category="Young Adult",
            source_url="https://books.toscrape.com/catalogue/the-requiem-red_995/index.html",
            scraped_at=now,
        ),
        Book(
            title="The Dirty Little Secrets of Getting Your Dream Job",
            price=33.34,
            rating=4,
            availability="In stock",
            category="Business",
            source_url="https://books.toscrape.com/catalogue/the-dirty-little-secrets_994/index.html",
            scraped_at=now,
        ),
    ]
    db_session.add_all(books)
    db_session.commit()
    return books
