import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.database import get_db
from app.schemas.book import ScrapeResponse
from app.scraper.book_scraper import BookScraper, ScrapeResult
from app.services.book_service import BookService

router = APIRouter(prefix="/scrape", tags=["Scraper"])


def _build_scrape_response(
    result: ScrapeResult,
    inserted: int,
    updated: int,
    duration: float,
) -> ScrapeResponse:
    """Maps a ScrapeResult to the appropriate API response."""
    if result.failed_urls:
        message = (
            f"Scrape partially completed in {duration}s with {len(result.failed_urls)} "
            f"failed page(s). Processed {len(result.books)} books "
            f"({inserted} inserted, {updated} updated)."
        )
        return ScrapeResponse(
            status="partial",
            message=message,
            total_scraped=len(result.books),
            inserted=inserted,
            updated=updated,
            duration_seconds=duration,
            failed_urls=result.failed_urls,
        )

    if not result.books:
        return ScrapeResponse(
            status="completed_empty",
            message=(
                f"Scrape completed in {duration}s. No books were found in "
                f"{result.categories_discovered} categor(ies)."
            ),
            total_scraped=0,
            inserted=0,
            updated=0,
            duration_seconds=duration,
        )

    message = (
        f"Scraping completed in {duration}s. Processed {len(result.books)} books "
        f"({inserted} inserted, {updated} updated)."
    )
    return ScrapeResponse(
        status="success",
        message=message,
        total_scraped=len(result.books),
        inserted=inserted,
        updated=updated,
        duration_seconds=duration,
    )


@router.post(
    "",
    response_model=ScrapeResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger web scraper",
    description=(
        "Triggers the web scraper to crawl books.toscrape.com and upsert records into the database. "
        "Duplicate prevention: existing records are updated and new ones are inserted. "
        "Optional query parameters limit categories, pages, or total books for quick runs.\n\n"
        "**Outcomes:** `status=success` (full run), `status=partial` with `failed_urls` "
        "(some pages failed — scraped books may already be saved), "
        "`status=completed_empty` (reachable site, no books), "
        "or HTTP 502/503/500 on hard failures."
    ),
    responses={
        200: {
            "description": (
                "Scrape finished with status success, completed_empty, or partial "
                "(partial responses include failed_urls; books already scraped may be saved)."
            )
        },
        502: {"description": "Required pages failed and no books were retrieved."},
        503: {"description": "Target website unreachable or category discovery failed."},
        500: {"description": "Unexpected scraper or database operation failed."},
    },
)
def trigger_scrape(
    max_categories: Optional[int] = Query(
        None,
        ge=1,
        description="Limit the number of categories to scrape (useful for quick test runs)",
    ),
    max_pages_per_category: Optional[int] = Query(
        None,
        ge=1,
        description="Limit pagination depth per category",
    ),
    max_total_books: Optional[int] = Query(
        None,
        ge=1,
        description="Limit the total number of books scraped",
    ),
    db: Session = Depends(get_db),
):
    """Triggers the book scraper and updates PostgreSQL with zero duplicates."""
    start_time = time.time()
    logger.info("Initiating scrape task via POST /scrape endpoint...")

    try:
        scraper = BookScraper()
        result = scraper.scrape_all_books(
            max_categories=max_categories,
            max_pages_per_category=max_pages_per_category,
            max_total_books=max_total_books,
        )
    except Exception as exc:
        logger.error(f"Scraper execution failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Scraper failed during execution.",
        )

    duration = round(time.time() - start_time, 2)

    if result.homepage_failed:
        logger.error("Scrape aborted: homepage/category discovery failed.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scraper could not reach the target website for category discovery.",
        )

    if result.categories_discovered == 0:
        logger.error("Scrape aborted: no categories discovered on target homepage.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scraper could not discover any book categories on the target website.",
        )

    if result.failed_urls and not result.books:
        logger.error(
            "Scrape aborted: %s page(s) failed and no books were retrieved.",
            len(result.failed_urls),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Scraper could not retrieve any books because required pages failed to load.",
        )

    inserted = 0
    updated = 0
    if result.books:
        try:
            inserted, updated = BookService.upsert_scraped_books(
                db=db,
                scraped_books=result.books,
            )
        except Exception as exc:
            logger.error(f"Database error during upsert: {exc}", exc_info=True)
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database transaction error during book upsert.",
            )

    response = _build_scrape_response(result, inserted, updated, duration)
    logger.info(response.message)
    return response
