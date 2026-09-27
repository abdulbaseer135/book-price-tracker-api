# Book Price Tracker API

A FastAPI backend that scrapes book data from [books.toscrape.com](https://books.toscrape.com/), stores it in PostgreSQL, and exposes it through REST endpoints. Built as a Backend Development Internship Task using BeautifulSoup4, SQLAlchemy, and Docker Compose.

---

## Key Features

- **Web Scraper:** BeautifulSoup4 + HTTPX scraper that walks categories and pages, parsing title, price, rating, availability, and category.
- **Duplicate Handling:** Upserts by unique `source_url`. Re-running the scraper updates existing rows instead of inserting duplicates; within a single batch, the last record for a URL wins.
- **Querying & Filtering:** Filter books by category (case-insensitive) and price range (`min_price`, `max_price`), with pagination (`page`, `limit`).
- **Separated Responsibilities:** Routes handle HTTP, services hold query/upsert logic, ORM models map tables, and Pydantic schemas validate responses.
- **Docker Compose:** Runs the API and PostgreSQL together with a single compose command.
- **Automated Tests:** Pytest coverage for book listing/filtering, readiness checks, scrape outcome reporting, duplicate prevention, and HTML parsing.
- **API Docs:** OpenAPI via Swagger UI (`/docs`) and ReDoc (`/redoc`).

---

## Technology Stack

| Component | Technology | Notes |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Docker image uses **Python 3.11**; local automated tests ran on **Python 3.14** |
| **Web Framework** | FastAPI | Request/response validation and OpenAPI generation |
| **ASGI Server** | Uvicorn | Serves the FastAPI application |
| **Database** | PostgreSQL 16 | Used by the Compose stack and local/non-Docker setup |
| **ORM** | SQLAlchemy 2.0+ | Models, sessions, and queries |
| **Data Validation** | Pydantic v2 | Response and query-parameter contracts |
| **Web Scraping** | BeautifulSoup4 + HTTPX | HTML parsing with retries and timeouts |
| **Containerization** | Docker & Docker Compose | API + PostgreSQL services |
| **Testing** | Pytest | Isolated SQLite-based unit and API tests |

---

## System Architecture

```text
                                  +-----------------------+
                                  |  books.toscrape.com   |
                                  +-----------------------+
                                              ^
                                              | HTTP GET
                                              v
+------------------+             +-------------------------+
|   REST Client    | <=========> |   FastAPI Application   |
| (Browser / Curl) |  HTTP JSON  |      (app/main.py)      |
+------------------+             +-------------------------+
                                              |
                         +--------------------+--------------------+
                         |                    |                    |
                         v                    v                    v
                  +-------------+      +-------------+      +-------------+
                  | /books API  |      | /scrape API |      | BookScraper |
                  |   Router    |      |   Router    |      |   Engine    |
                  +-------------+      +-------------+      +-------------+
                         \                    |                   /
                          \                   v                  /
                           +------> +-------------------+ <-----+
                                    |    BookService    |
                                    | (Upsert / Filter) |
                                    +-------------------+
                                              |
                                              v
                                    +-------------------+
                                    |  SQLAlchemy ORM   |
                                    +-------------------+
                                              |
                                              v
                                    +-------------------+
                                    | PostgreSQL 16 DB  |
                                    +-------------------+
```

---

## Project Structure

```text
book-price-tracker/
│
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application, lifespan & readiness
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # Settings & environment variable loader
│   │   └── logging.py              # Application logging configuration
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   └── database.py             # Engine, SessionLocal, get_db, readiness check
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                 # Declarative Base
│   │   └── book.py                 # SQLAlchemy Book model
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── book.py                 # Pydantic response models
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── books.py                # GET /books, GET /books/{id}
│   │   └── scraper.py              # POST /scrape
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   └── book_service.py         # Filtering, pagination, upsert
│   │
│   └── scraper/
│       ├── __init__.py
│       └── book_scraper.py         # BeautifulSoup scraper engine
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # In-memory SQLite fixtures; stubs init_db / readiness
│   ├── test_api.py                 # GET /books, GET /books/{id}, GET / readiness
│   ├── test_scrape_api.py          # POST /scrape outcome reporting (mocked scraper)
│   ├── test_health.py              # Database connectivity helper tests
│   ├── test_scraper.py             # HTML parsing, navigation failure, empty catalog
│   └── test_service.py             # Upsert, cross-run and within-batch deduplication
│
├── .env.example                    # Template environment variables
├── .gitignore                      # Git ignore patterns (protects secrets)
├── .dockerignore                   # Files excluded from Docker build context
├── Dockerfile                      # Application image (HEALTHCHECK uses GET /)
├── docker-compose.yml              # Multi-container orchestration (FastAPI + PostgreSQL)
├── requirements.txt                # Project dependencies
└── README.md                       # Project documentation
```

---

## Environment Variables

The application is configured using environment variables. See [`.env.example`](./.env.example).

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `POSTGRES_USER` | *(required)* | PostgreSQL username |
| `POSTGRES_PASSWORD` | *(required)* | PostgreSQL password (set in `.env`; never commit real secrets) |
| `POSTGRES_DB` | *(required)* | Database name |
| `POSTGRES_HOST` | `localhost` locally; Compose sets `postgres` | Database hostname |
| `POSTGRES_PORT` | `5432` | Database port |
| `DATABASE_URL` | *(optional; otherwise assembled from POSTGRES_\*)* | Full connection string |
| `SCRAPER_BASE_URL` | `https://books.toscrape.com/` | Target scraper URL |
| `SCRAPER_REQUEST_TIMEOUT` | `15.0` | HTTP request timeout in seconds |
| `SCRAPER_MAX_RETRIES` | `3` | Retries on network failures |

**Required setup:** copy [`.env.example`](./.env.example) to `.env` and set your credentials before starting the app (Docker or local).

```bash
# Linux / macOS
cp .env.example .env

# Windows Command Prompt
copy .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Edit `.env` and replace `change_me` with your PostgreSQL password. Docker Compose reads `.env` for variable substitution and connects the API to the service hostname `postgres`. Local (non-Docker) runs should keep `POSTGRES_HOST=localhost`.

---

## Running the Project

### Option 1: Running with Docker Compose (Recommended)

```bash
# 1. Create and configure environment file
cp .env.example .env   # or: copy .env.example .env

# 2. Edit .env and set POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB

# 3. Build and launch PostgreSQL + FastAPI
docker compose up --build
```
*(Or `docker-compose up --build` if using Docker Compose v1)*

Once booted:
- **FastAPI API / readiness:** [http://localhost:8000](http://localhost:8000) — **200** when PostgreSQL is reachable, **503** when it is not
- **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc UI:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

Compose starts PostgreSQL first (`depends_on` + `pg_isready` healthcheck), then the API. Database data is stored in the named volume `postgres_data`.

To stop the containers (keeps the database volume):
```bash
docker compose down
```

---

### Option 2: Running Locally

#### 1. Setup Virtual Environment
```bash
python -m venv .venv

# Linux/macOS:
source .venv/bin/activate
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 3. Configure Database
Ensure a local PostgreSQL instance is running with a database named `book_tracker`. Create `.env` from `.env.example` (see above) and keep `POSTGRES_HOST=localhost`, or set `DATABASE_URL`.

#### 4. Run the API Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Running the Scraper

### Method 1: Via the REST API (Recommended)

```bash
# Scrape the first 2 categories (quick run)
curl -X POST "http://localhost:8000/scrape?max_categories=2"

# Trigger a full scrape across all categories
curl -X POST "http://localhost:8000/scrape"
```

`POST /scrape` outcomes:

| HTTP | `status` field | Meaning |
| :--- | :--- | :--- |
| 200 | `success` | Full scrape finished; books upserted |
| 200 | `partial` | Some pages failed; books that were scraped **may already be saved**. Response includes `failed_urls` |
| 200 | `completed_empty` | Target was reachable and categories were found, but no book items were returned |
| 502 | *(error body)* | Required pages failed and **no** books were retrieved |
| 503 | *(error body)* | Homepage/category discovery failed (site unreachable or unusable) |
| 500 | *(error body)* | Unexpected scraper or database error (generic message only) |

### Method 2: As a Standalone CLI Script

Prints sample scrape results; does not write to the database by itself:

```bash
python -m app.scraper.book_scraper
```

---

## Running Automated Tests

```bash
pytest -v
```

Tests use an **isolated in-memory SQLite** database for request and service assertions. In `tests/conftest.py`, an autouse fixture stubs `init_db` and `check_db_connection` so TestClient startup/readiness checks do **not** contact a local PostgreSQL instance. Scraper network I/O in API scrape tests is mocked.

### What the suite covers
- **`tests/test_api.py`:** `GET /` readiness (healthy + unhealthy), pagination, category/price filters, combined filters, invalid price range (400), book-by-id 200/404/422
- **`tests/test_scrape_api.py`:** `POST /scrape` outcomes — homepage failure (503), partial (200), total page failure (502), genuine empty catalog, generic 500 without leaking exception text to clients
- **`tests/test_scraper.py`:** HTML parsing (including out-of-stock availability), homepage failure, partial page failure, genuine empty catalog
- **`tests/test_service.py`:** Cross-run upsert deduplication and within-batch duplicate `source_url` handling (last record wins)
- **`tests/test_health.py`:** `check_db_connection` helper against SQLite / mocked unreachable engine

The suite does **not** run a live scrape against books.toscrape.com, start Docker Compose, or assert against a real PostgreSQL database.

---

## API Documentation & Endpoints

Interactive Swagger UI: **[http://localhost:8000/docs](http://localhost:8000/docs)**

### Summary of Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Readiness check (200 when PostgreSQL is reachable; 503 when unavailable) |
| `GET` | `/books` | Retrieve paginated books with optional category and price filters |
| `GET` | `/books/{id}` | Retrieve a specific book by ID (returns 404 if not found) |
| `POST` | `/scrape` | Trigger scrape + upsert (`success` / `partial` / `completed_empty`, or 502/503/500) |

---

#### Readiness example (`GET /`)

Illustrative responses:

**Healthy (`200 OK`):**
```json
{
  "status": "healthy",
  "app": "Book Price Tracker API",
  "version": "1.0.0",
  "docs_url": "/docs",
  "redoc_url": "/redoc"
}
```

**Database unavailable (`503 Service Unavailable`):**
```json
{
  "status": "unhealthy",
  "detail": "Database is unavailable.",
  "app": "Book Price Tracker API",
  "version": "1.0.0",
  "docs_url": "/docs",
  "redoc_url": "/redoc"
}
```

---

### Endpoint Examples

Sample JSON below is **illustrative** (field shapes and status codes). Counts, IDs, and titles will differ based on your database contents.

#### 1. List Books with Pagination
```http
GET /books?page=1&limit=2 HTTP/1.1
Host: localhost:8000
```
**Illustrative response (`200 OK`):**
```json
{
  "items": [
    {
      "title": "It's Only the Himalayas",
      "price": 45.17,
      "rating": 2,
      "availability": "In stock",
      "category": "Travel",
      "source_url": "https://books.toscrape.com/catalogue/its-only-the-himalayas_981/index.html",
      "id": 1,
      "scraped_at": "2026-09-26T15:11:34.123456Z"
    },
    {
      "title": "Full Moon over Noah's Ark",
      "price": 49.43,
      "rating": 4,
      "availability": "In stock",
      "category": "Travel",
      "source_url": "https://books.toscrape.com/catalogue/full-moon-over-noahs-ark_811/index.html",
      "id": 2,
      "scraped_at": "2026-09-26T15:11:34.123456Z"
    }
  ],
  "total": 11,
  "page": 1,
  "limit": 2,
  "total_pages": 6
}
```

---

#### 2. Get Book by ID
```http
GET /books/1 HTTP/1.1
Host: localhost:8000
```
**Illustrative response (`200 OK`):**
```json
{
  "id": 1,
  "title": "It's Only the Himalayas",
  "price": 45.17,
  "rating": 2,
  "availability": "In stock",
  "category": "Travel",
  "source_url": "https://books.toscrape.com/catalogue/its-only-the-himalayas_981/index.html",
  "scraped_at": "2026-09-26T15:11:34.123456Z"
}
```

**Non-existent ID (`404 Not Found`):**
```json
{
  "detail": "Book with id 99999 not found."
}
```

---

#### 3. Filter by Category
```http
GET /books?category=Travel HTTP/1.1
Host: localhost:8000
```

---

#### 4. Filter by Price Range
```http
GET /books?min_price=20&max_price=50 HTTP/1.1
Host: localhost:8000
```

---

#### 5. Combined Filters and Pagination
```http
GET /books?category=Travel&min_price=20&max_price=50&page=1&limit=10 HTTP/1.1
Host: localhost:8000
```

---

#### 6. Trigger Web Scraper
```http
POST /scrape?max_categories=1 HTTP/1.1
Host: localhost:8000
```
**Illustrative response — success (`200 OK`):**
```json
{
  "status": "success",
  "message": "Scraping completed in 2.15s. Processed 11 books (11 inserted, 0 updated).",
  "total_scraped": 11,
  "inserted": 11,
  "updated": 0,
  "duration_seconds": 2.15,
  "failed_urls": []
}
```

**Illustrative response — partial (`200 OK`):** some pages failed; scraped books may already be in the database.
```json
{
  "status": "partial",
  "message": "Scrape partially completed in 1.20s with 1 failed page(s). Processed 5 books (5 inserted, 0 updated).",
  "total_scraped": 5,
  "inserted": 5,
  "updated": 0,
  "duration_seconds": 1.2,
  "failed_urls": ["https://books.toscrape.com/catalogue/category/books/fiction_1/page-2.html"]
}
```

---

## Troubleshooting

| Problem | What to check |
| :--- | :--- |
| **Docker daemon not running** | Start Docker Desktop (or your Docker engine), then retry `docker compose up --build`. |
| **Port 8000 or 5432 already in use** | Stop the other process, or change the left-hand side of the port mappings in `docker-compose.yml` (for example `"8001:8000"`). |
| **`GET /` returns 503 / container unhealthy** | PostgreSQL is not reachable from the API. Confirm the `postgres` service is healthy (`docker compose ps`), credentials match, and (in Compose) `POSTGRES_HOST` is `postgres`. |
| **Local `uvicorn` fails to connect** | Ensure PostgreSQL is running and `POSTGRES_HOST=localhost` (or a correct `DATABASE_URL`) in `.env`. |
| **Scrape returns 503** | The target site homepage could not be loaded for category discovery. Check network access to books.toscrape.com. |
| **Scrape returns `partial`** | Some category pages failed; books that were scraped may already be saved. Inspect `failed_urls` in the response. |

**Destructive (optional):** `docker compose down -v` stops containers **and deletes** the `postgres_data` volume (all stored books). Prefer `docker compose down` for a normal stop.

---

## Security Notes

- **Secrets:** Credentials come from environment variables; `.env` is listed in `.gitignore`. Do not commit real secrets.
- **SQL:** Queries use SQLAlchemy parameterization.
- **Input validation:** Query/path parameters are validated via FastAPI and Pydantic.
- **Client error bodies:** Scraper and database failures return **generic** messages to API clients (no raw stack traces in JSON responses).
- **Server logs:** Startup and readiness checks log exception **types** only. Some request handlers still log exception objects or stack traces server-side for debugging; treat logs as sensitive.

---

## GitHub Submission Instructions

This project already has a local Git repository (currently on branch `master`, with no commits yet in a fresh clone). Do **not** run `git init` again.

```bash
# 1. Inspect local state
git status
git remote -v
git branch

# 2. Stage only intended project files (source, tests, Docker, docs)
git add app tests Dockerfile docker-compose.yml requirements.txt README.md .env.example .gitignore .dockerignore

# 3. Review the staged file list before committing
git diff --cached --name-only
```

Confirm that list does **not** include `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.sqlite*`, or database volume data. Those paths are ignored by `.gitignore` and must stay unstaged.

```bash
# 4. Commit
git commit -m "Initial implementation: Book Price Tracker API"

# 5. Optional: rename the current branch to main
# (skip if you prefer to keep master)
git branch -M main

# 6. Add a GitHub remote only if origin is missing
# Replace the URL with your real repository URL.
git remote -v
# If origin is not listed:
git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPOSITORY_NAME>.git

# 7. Push the branch you are on (main or master)
git push -u origin HEAD
```
