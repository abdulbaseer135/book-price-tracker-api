from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.book import BookResponse, BookListResponse
from app.services.book_service import BookService

router = APIRouter(prefix="/books", tags=["Books"])


@router.get(
    "",
    response_model=BookListResponse,
    summary="List books with pagination and filtering",
    description=(
        "Retrieves a paginated list of books from the database. "
        "Supports filtering by category and price range (min_price, max_price). "
        "Filters can be combined seamlessly."
    ),
    responses={
        200: {"description": "Successfully retrieved paginated books list."},
        400: {"description": "Invalid query parameters (e.g. min_price > max_price)."},
    },
)
def list_books(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(10, ge=1, le=100, description="Number of items per page (max 100)"),
    category: Optional[str] = Query(None, description="Filter books by category (case-insensitive)"),
    min_price: Optional[float] = Query(None, ge=0.0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0.0, description="Maximum price filter"),
    db: Session = Depends(get_db),
):
    """Retrieves paginated books with optional category and price range filters."""
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'min_price' cannot be greater than 'max_price'.",
        )

    items, total, total_pages = BookService.get_books(
        db=db,
        category=category,
        min_price=min_price,
        max_price=max_price,
        page=page,
        limit=limit,
    )

    return BookListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.get(
    "/{id}",
    response_model=BookResponse,
    summary="Get book by ID",
    description="Retrieves detailed information for a single book by its primary key ID.",
    responses={
        200: {"description": "Book details retrieved successfully."},
        404: {"description": "Book with the specified ID was not found."},
    },
)
def get_book(
    id: int = Path(..., ge=1, description="Database primary key ID of the book"),
    db: Session = Depends(get_db),
):
    """Retrieves a single book by ID, returning 404 if it does not exist."""
    book = BookService.get_book_by_id(db=db, book_id=id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with id {id} not found.",
        )
    return book
