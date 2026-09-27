"""Regression tests for POST /scrape failure reporting."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.scraper.book_scraper import ScrapeResult, ScrapedBook


def _book(title: str, url_suffix: str) -> ScrapedBook:
    return ScrapedBook(
        title=title,
        price=10.0,
        rating=3,
        availability="In stock",
        category="Fiction",
        source_url=f"https://books.toscrape.com/{url_suffix}",
    )


def test_post_scrape_homepage_failure_returns_503(client: TestClient):
    """Discovery failure must not return completed_empty."""
    failed = ScrapeResult(
        books=[],
        failed_urls=["https://books.toscrape.com/"],
        homepage_failed=True,
        categories_discovered=0,
    )
    with patch("app.routes.scraper.BookScraper") as mock_scraper:
        mock_scraper.return_value.scrape_all_books.return_value = failed
        response = client.post("/scrape")

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Scraper could not reach the target website for category discovery."
    )


def test_post_scrape_partial_success_not_reported_as_success(client: TestClient):
    """Partial scrapes must not use status=success."""
    partial = ScrapeResult(
        books=[_book("Book One", "book-one.html")],
        failed_urls=["https://books.toscrape.com/page-2.html"],
        homepage_failed=False,
        categories_discovered=1,
    )
    with patch("app.routes.scraper.BookScraper") as mock_scraper:
        mock_scraper.return_value.scrape_all_books.return_value = partial
        response = client.post("/scrape")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "partial"
    assert body["total_scraped"] == 1
    assert body["inserted"] == 1
    assert body["failed_urls"] == ["https://books.toscrape.com/page-2.html"]
    assert "failed page(s)" in body["message"]


def test_post_scrape_partial_with_no_books_returns_502(client: TestClient):
    """If every required page failed, the endpoint must fail."""
    partial = ScrapeResult(
        books=[],
        failed_urls=["https://books.toscrape.com/page-1.html"],
        homepage_failed=False,
        categories_discovered=1,
    )
    with patch("app.routes.scraper.BookScraper") as mock_scraper:
        mock_scraper.return_value.scrape_all_books.return_value = partial
        response = client.post("/scrape")

    assert response.status_code == 502
    assert "could not retrieve any books" in response.json()["detail"]


def test_post_scrape_genuine_empty_catalog_returns_completed_empty(client: TestClient):
    """A successful scrape with zero books remains completed_empty."""
    empty = ScrapeResult(
        books=[],
        failed_urls=[],
        homepage_failed=False,
        categories_discovered=1,
    )
    with patch("app.routes.scraper.BookScraper") as mock_scraper:
        mock_scraper.return_value.scrape_all_books.return_value = empty
        response = client.post("/scrape")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed_empty"
    assert body["total_scraped"] == 0
    assert body["failed_urls"] == []


def test_post_scrape_unexpected_error_hides_exception_text(client: TestClient):
    """Scraper exceptions must not leak raw exception strings to clients."""
    with patch("app.routes.scraper.BookScraper") as mock_scraper:
        mock_scraper.return_value.scrape_all_books.side_effect = RuntimeError(
            "super secret network detail"
        )
        response = client.post("/scrape")

    assert response.status_code == 500
    assert response.json()["detail"] == "Scraper failed during execution."
    assert "super secret" not in response.json()["detail"]
