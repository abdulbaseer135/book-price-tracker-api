from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BookBase(BaseModel):
    """Shared attributes for a book resource."""
    title: str = Field(..., description="Book title", examples=["A Light in the Attic"])
    price: float = Field(..., ge=0.0, description="Book price in GBP", examples=[51.77])
    rating: int = Field(..., ge=0, le=5, description="Star rating from 0 to 5", examples=[3])
    availability: str = Field(..., description="Stock availability status", examples=["In stock"])
    category: str = Field(..., description="Book category/genre", examples=["Poetry"])
    source_url: str = Field(
        ...,
        description="Canonical URL of the book on books.toscrape.com",
        examples=["https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"],
    )


class BookCreate(BookBase):
    """Schema for creating or upserting a book record."""
    pass


class BookResponse(BookBase):
    """Schema returned by the API representing a stored book."""
    id: int = Field(..., description="Unique database identifier", examples=[1])
    scraped_at: datetime = Field(..., description="Timestamp of when the book was scraped (UTC)")

    # Enables automatic serialization from SQLAlchemy ORM models (Pydantic v2)
    model_config = ConfigDict(from_attributes=True)


class BookListResponse(BaseModel):
    """Paginated list response for books."""
    items: List[BookResponse] = Field(..., description="List of books on the current page")
    total: int = Field(..., ge=0, description="Total number of books matching filters", examples=[100])
    page: int = Field(..., ge=1, description="Current page number", examples=[1])
    limit: int = Field(..., ge=1, description="Items per page limit", examples=[10])
    total_pages: int = Field(..., ge=0, description="Total number of available pages", examples=[10])


class ScrapeResponse(BaseModel):
    """Response returned when a scraping task completes."""
    status: str = Field(
        "success",
        description="Scrape outcome: success, partial, or completed_empty",
        examples=["success", "partial", "completed_empty"],
    )
    message: str = Field(..., description="Summary message of the operation")
    total_scraped: int = Field(..., ge=0, description="Total books processed from the target site", examples=[20])
    inserted: int = Field(..., ge=0, description="Number of new books created in the database", examples=[15])
    updated: int = Field(..., ge=0, description="Number of existing books updated in the database", examples=[5])
    duration_seconds: float = Field(..., ge=0.0, description="Execution time in seconds", examples=[2.34])
    failed_urls: List[str] = Field(
        default_factory=list,
        description="URLs that could not be fetched during the scrape (partial runs only)",
    )
