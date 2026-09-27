"""Tests for FastAPI endpoints: GET /books, GET /books/{id}, and root health check."""
import pytest
from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    """Verifies that the root readiness endpoint returns 200 when the database is healthy."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Book Price Tracker API" in data["app"]
    assert data["docs_url"] == "/docs"


def test_root_endpoint_unhealthy_when_database_unavailable(
    client: TestClient, monkeypatch
):
    """Readiness must report unhealthy (503) when PostgreSQL is unavailable."""
    monkeypatch.setattr("app.main.check_db_connection", lambda: False)

    response = client.get("/")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["detail"] == "Database is unavailable."
    assert "Book Price Tracker API" in data["app"]
    assert data["docs_url"] == "/docs"
    assert "password" not in response.text.lower()


def test_list_books_default_pagination(client: TestClient, seed_books):
    """Verifies default pagination returns all 7 seeded books within limit 10."""
    response = client.get("/books")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 7
    assert data["page"] == 1
    assert data["limit"] == 10
    assert data["total_pages"] == 1
    assert len(data["items"]) == 7


def test_list_books_custom_pagination(client: TestClient, seed_books):
    """Verifies custom limit and page numbers calculate total_pages and slice items."""
    # Page 1, limit 3
    response_p1 = client.get("/books?page=1&limit=3")
    assert response_p1.status_code == 200
    data_p1 = response_p1.json()
    assert data_p1["total"] == 7
    assert data_p1["page"] == 1
    assert data_p1["limit"] == 3
    assert data_p1["total_pages"] == 3
    assert len(data_p1["items"]) == 3

    # Page 3, limit 3 (should have 1 item: 7 - 6 = 1)
    response_p3 = client.get("/books?page=3&limit=3")
    assert response_p3.status_code == 200
    data_p3 = response_p3.json()
    assert len(data_p3["items"]) == 1


def test_filter_by_category(client: TestClient, seed_books):
    """Verifies filtering by category returns only books matching that category."""
    response = client.get("/books?category=Mystery")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Sharp Objects"
    assert data["items"][0]["category"] == "Mystery"


def test_filter_by_category_case_insensitive(client: TestClient, seed_books):
    """Verifies category filtering works regardless of letter casing."""
    response = client.get("/books?category=poetry")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "A Light in the Attic"


def test_filter_by_price_range(client: TestClient, seed_books):
    """Verifies filtering by min_price and max_price."""
    # Price between 20.0 and 35.0 (The Requiem Red @ 22.65, The Dirty Little Secrets @ 33.34)
    response = client.get("/books?min_price=20.0&max_price=35.0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    prices = [item["price"] for item in data["items"]]
    assert all(20.0 <= p <= 35.0 for p in prices)


def test_combined_filters_and_pagination(client: TestClient, seed_books):
    """Verifies combining category, price bounds, and pagination simultaneously."""
    response = client.get("/books?category=Young Adult&min_price=20&max_price=30&page=1&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "The Requiem Red"


def test_invalid_price_range_returns_400(client: TestClient):
    """Verifies that setting min_price > max_price returns an HTTP 400 Bad Request."""
    response = client.get("/books?min_price=50.0&max_price=20.0")
    assert response.status_code == 400
    data = response.json()
    assert "min_price" in data["detail"]


def test_get_book_by_id_success(client: TestClient, seed_books):
    """Verifies fetching an existing book by its primary key ID."""
    first_book_id = seed_books[0].id
    response = client.get(f"/books/{first_book_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == first_book_id
    assert data["title"] == "A Light in the Attic"
    assert data["price"] == 51.77
    assert data["rating"] == 3
    assert data["category"] == "Poetry"
    assert data["availability"] == "In stock"
    assert "source_url" in data


def test_get_book_by_id_not_found(client: TestClient, seed_books):
    """Verifies that querying a non-existent ID returns HTTP 404 with standard error."""
    response = client.get("/books/999999")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_get_book_invalid_id_type(client: TestClient):
    """Verifies that passing a string for integer ID returns HTTP 422 Unprocessable Entity."""
    response = client.get("/books/abc")
    assert response.status_code == 422
