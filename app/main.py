from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.logging import logger
from app.db.database import check_db_connection, init_db
from app.routes.books import router as books_router
from app.routes.scraper import router as scraper_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan handler executing application startup and shutdown tasks."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}...")
    try:
        init_db()
        logger.info("Database schemas verified.")
    except Exception as exc:
        # Log exception type only — never dump connection strings or credentials.
        logger.warning(
            "Database initialization failed on startup (%s). "
            "The API will report unhealthy until PostgreSQL is available.",
            type(exc).__name__,
        )
    yield
    logger.info("Application shutting down...")


# OpenAPI Documentation metadata
tags_metadata = [
    {
        "name": "Books",
        "description": "Operations to query, filter, and view books stored in the database.",
    },
    {
        "name": "Scraper",
        "description": "Operations to crawl books.toscrape.com and synchronize the database.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Production-grade REST API built for the Backend Developer Internship Task.\n\n"
        "### Key Features\n"
        "- **Catalog Scraping:** Crawls [books.toscrape.com](https://books.toscrape.com/) with duplicate prevention.\n"
        "- **Advanced Filtering:** Filter books by category and numeric price ranges (min_price, max_price).\n"
        "- **Pagination:** Query books with customizable page and limit parameters.\n"
        "- **Persistence:** Stored in PostgreSQL with SQLAlchemy ORM.\n"
        "- **Interactive Docs:** Full Swagger UI available at `/docs` and ReDoc at `/redoc`."
    ),
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handlers to avoid leaking raw internal stack traces
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Intercepts database exceptions and returns a sanitized JSON error response."""
    logger.error(f"Database error during request {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred while processing the request."},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catches unhandled exceptions gracefully."""
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected server error occurred."},
    )


# Register API Routers
app.include_router(books_router)
app.include_router(scraper_router)


@app.get(
    "/",
    tags=["Root"],
    summary="API readiness and information",
    description=(
        "Readiness check and service metadata. Returns HTTP 200 when PostgreSQL is "
        "reachable; HTTP 503 when the database is unavailable."
    ),
    responses={
        200: {"description": "Application and database are ready."},
        503: {"description": "Application is running but the database is unavailable."},
    },
)
def root():
    """Readiness check and API metadata endpoint."""
    payload = {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }

    if not check_db_connection():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                **payload,
                "status": "unhealthy",
                "detail": "Database is unavailable.",
            },
        )

    return {
        **payload,
        "status": "healthy",
    }
