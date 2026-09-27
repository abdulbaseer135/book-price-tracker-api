"""
Web Scraper Module for books.toscrape.com
Extracts: title, price, rating, availability, category, and canonical URL.
Handles pagination, missing fields, malformed HTML, and network retries gracefully.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from urllib.parse import urljoin
import re
import time
import httpx
from bs4 import BeautifulSoup, Tag

from app.core.config import settings
from app.core.logging import logger


@dataclass
class ScrapedBook:
    """Normalized data structure representing a scraped book item."""
    title: str
    price: float
    rating: int
    availability: str
    category: str
    source_url: str


@dataclass
class ScrapeResult:
    """Outcome of a scrape run, including books and any fetch failures."""
    books: List[ScrapedBook]
    failed_urls: List[str] = field(default_factory=list)
    homepage_failed: bool = False
    categories_discovered: int = 0


class BookScraper:
    """
    Modular, resilient scraper engine for books.toscrape.com.
    Supports both category-driven and catalog page pagination.
    """

    RATING_MAP: Dict[str, int] = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.SCRAPER_BASE_URL).rstrip("/") + "/"
        self.timeout = timeout or settings.SCRAPER_REQUEST_TIMEOUT
        self.max_retries = max_retries or settings.SCRAPER_MAX_RETRIES

    def _get_client(self) -> httpx.Client:
        """Creates a configured HTTP client with sensible headers and timeouts."""
        return httpx.Client(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; BookPriceTrackerBot/1.0; +https://github.com/)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            timeout=self.timeout,
            follow_redirects=True,
        )

    def fetch_html(self, url: str) -> Optional[str]:
        """
        Fetches HTML with exponential backoff retry mechanism.
        Returns HTML string on success, or None on failure.
        """
        delay = 1.0
        with self._get_client() as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.debug(f"Fetching URL (attempt {attempt}/{self.max_retries}): {url}")
                    response = client.get(url)
                    response.raise_for_status()
                    return response.text
                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    logger.warning(
                        f"Attempt {attempt}/{self.max_retries} failed for {url}: {exc}"
                    )
                    if attempt < self.max_retries:
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts.")
                        return None
        return None

    def parse_rating(self, rating_element: Optional[Tag]) -> int:
        """
        Extracts star rating from class names (e.g., ['star-rating', 'Three'] -> 3).
        Defaults to 0 if not found or unparseable.
        """
        if not rating_element:
            return 0
        classes = rating_element.get("class", [])
        for cls in classes:
            normalized_cls = cls.strip().lower()
            if normalized_cls in self.RATING_MAP:
                return self.RATING_MAP[normalized_cls]
        return 0

    def parse_price(self, price_text: Optional[str]) -> float:
        """
        Extracts numeric price from currency string (e.g., '£51.77' -> 51.77).
        Defaults to 0.0 if not found.
        """
        if not price_text:
            return 0.0
        match = re.search(r"(\d+(?:\.\d+)?)", price_text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return 0.0
        return 0.0

    def parse_availability(self, avail_text: Optional[str]) -> str:
        """Normalizes availability text (removes whitespace/newlines and clarifies status)."""
        if not avail_text:
            return "Unknown"
        cleaned = " ".join(avail_text.split()).strip()
        if "in stock" in cleaned.lower():
            return "In stock"
        elif "out of stock" in cleaned.lower():
            return "Out of stock"
        return cleaned or "Unknown"

    def parse_book_element(
        self,
        element: Tag,
        page_url: str,
        category: str = "General",
    ) -> Optional[ScrapedBook]:
        """
        Parses a single 'article.product_pod' element into a ScrapedBook object.
        Gracefully handles missing or malformed fields.
        """
        try:
            # 1. Title and Source URL
            link_tag = element.select_one("h3 a")
            if not link_tag:
                logger.warning("Skipping book pod: Missing title/link tag.")
                return None

            raw_title = link_tag.get("title") or link_tag.text
            title = raw_title.strip().replace("\ufffd", "'") if raw_title else "Untitled"

            relative_url = link_tag.get("href", "").strip()
            source_url = urljoin(page_url, relative_url)

            # 2. Price
            price_tag = element.select_one(".price_color")
            price = self.parse_price(price_tag.text if price_tag else "")

            # 3. Rating
            rating_tag = element.select_one("p.star-rating")
            rating = self.parse_rating(rating_tag)

            # 4. Availability (in-stock and out-of-stock pods use p.availability)
            stock_tag = element.select_one(".product_price p.availability") or element.select_one(
                "p.availability"
            )
            availability = self.parse_availability(stock_tag.text if stock_tag else "")

            return ScrapedBook(
                title=title,
                price=price,
                rating=rating,
                availability=availability,
                category=category.strip(),
                source_url=source_url,
            )
        except Exception as exc:
            logger.warning(f"Error parsing book element: {exc}")
            return None

    def get_categories(self) -> Tuple[List[Tuple[str, str]], bool]:
        """
        Extracts all categories and their links from the homepage sidebar.
        Returns: (categories, homepage_failed)
        """
        html = self.fetch_html(self.base_url)
        if not html:
            logger.error("Failed to load homepage for category discovery.")
            return [], True

        soup = BeautifulSoup(html, "html.parser")
        cat_links = soup.select(".side_categories ul.nav-list > li > ul > li a")
        categories = []
        for a in cat_links:
            cat_name = a.text.strip()
            rel_href = a.get("href", "").strip()
            full_url = urljoin(self.base_url, rel_href)
            if cat_name and full_url:
                categories.append((cat_name, full_url))

        logger.info(f"Discovered {len(categories)} categories on books.toscrape.com")
        return categories, False

    def scrape_category_pages(
        self,
        category_name: str,
        start_url: str,
        max_pages: Optional[int] = None,
    ) -> Tuple[List[ScrapedBook], List[str]]:
        """Scrapes all paginated books for a specific category."""
        books: List[ScrapedBook] = []
        failed_urls: List[str] = []
        current_url: Optional[str] = start_url
        page_num = 1

        while current_url:
            if max_pages and page_num > max_pages:
                break

            logger.info(f"Scraping category '{category_name}', Page {page_num}: {current_url}")
            html = self.fetch_html(current_url)
            if not html:
                failed_urls.append(current_url)
                break

            soup = BeautifulSoup(html, "html.parser")
            pods = soup.select("article.product_pod")
            for pod in pods:
                book = self.parse_book_element(pod, page_url=current_url, category=category_name)
                if book:
                    books.append(book)

            # Follow pagination (e.g. li.next a)
            next_link = soup.select_one("li.next a")
            if next_link and next_link.get("href"):
                current_url = urljoin(current_url, next_link["href"])
                page_num += 1
            else:
                current_url = None

        return books, failed_urls

    def scrape_all_books(
        self,
        max_categories: Optional[int] = None,
        max_pages_per_category: Optional[int] = None,
        max_total_books: Optional[int] = None,
    ) -> ScrapeResult:
        """
        Crawls through categories, scraping books with their true category,
        ratings, prices, availability, and source URLs.
        """
        categories, homepage_failed = self.get_categories()
        if homepage_failed:
            return ScrapeResult(
                books=[],
                failed_urls=[self.base_url],
                homepage_failed=True,
                categories_discovered=0,
            )

        if max_categories:
            categories = categories[:max_categories]

        all_books: List[ScrapedBook] = []
        failed_urls: List[str] = []
        for cat_name, cat_url in categories:
            cat_books, cat_failed = self.scrape_category_pages(
                category_name=cat_name,
                start_url=cat_url,
                max_pages=max_pages_per_category,
            )
            all_books.extend(cat_books)
            failed_urls.extend(cat_failed)
            if max_total_books and len(all_books) >= max_total_books:
                all_books = all_books[:max_total_books]
                break

        logger.info(f"Total books scraped: {len(all_books)}")
        return ScrapeResult(
            books=all_books,
            failed_urls=failed_urls,
            homepage_failed=False,
            categories_discovered=len(categories),
        )


def scrape_books(
    max_categories: Optional[int] = None,
    max_pages_per_category: Optional[int] = None,
    max_total_books: Optional[int] = None,
) -> ScrapeResult:
    """Convenience functional interface to execute the book scraper."""
    scraper = BookScraper()
    return scraper.scrape_all_books(
        max_categories=max_categories,
        max_pages_per_category=max_pages_per_category,
        max_total_books=max_total_books,
    )


if __name__ == "__main__":
    print("Executing BookScraper standalone test run (first category, 1 page)...")
    result = scrape_books(max_categories=1, max_pages_per_category=1)
    print(f"Scraped {len(result.books)} books.")
    if result.failed_urls:
        print(f"Failed URLs: {result.failed_urls}")
    for b in result.books[:3]:
        print(f" - Title: {b.title}")
        print(f"   Category: {b.category} | Price: {b.price} | Rating: {b.rating} | Avail: {b.availability}")
        print(f"   URL: {b.source_url}\n")
