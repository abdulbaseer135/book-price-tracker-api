"""Tests for BookScraper HTML parsing, normalization, and resilience."""
from unittest.mock import patch

from bs4 import BeautifulSoup
from app.scraper.book_scraper import BookScraper


MOCK_PRODUCT_POD_HTML = """
<article class="product_pod">
    <div class="image_container">
        <a href="../../../mock-book_123/index.html">
            <img src="../../../media/cache/mock.jpg" alt="Mock Book Title" class="thumbnail">
        </a>
    </div>
    <p class="star-rating Four">
        <i class="icon-star"></i>
    </p>
    <h3>
        <a href="../../../mock-book_123/index.html" title="Mock Book Title: The Comprehensive Guide">
            Mock Book Title: The Comprehensive Guide
        </a>
    </h3>
    <div class="product_price">
        <p class="price_color">£34.50</p>
        <p class="instock availability">
            <i class="icon-ok"></i>
            In stock (19 available)
        </p>
    </div>
</article>
"""


def test_parse_rating():
    """Verifies star-rating class conversion into integers."""
    scraper = BookScraper()

    # Valid ratings
    for word, expected in [("One", 1), ("Two", 2), ("Three", 3), ("Four", 4), ("Five", 5)]:
        tag = BeautifulSoup(f'<p class="star-rating {word}"></p>', "html.parser").p
        assert scraper.parse_rating(tag) == expected

    # Missing or invalid rating
    empty_tag = BeautifulSoup('<p class="star-rating"></p>', "html.parser").p
    assert scraper.parse_rating(empty_tag) == 0
    assert scraper.parse_rating(None) == 0


def test_parse_price():
    """Verifies numeric extraction and currency symbol stripping."""
    scraper = BookScraper()
    assert scraper.parse_price("£51.77") == 51.77
    assert scraper.parse_price("Â£10.99") == 10.99
    assert scraper.parse_price("€99.00") == 99.00
    assert scraper.parse_price("$0.00") == 0.0
    assert scraper.parse_price("free") == 0.0
    assert scraper.parse_price(None) == 0.0
    assert scraper.parse_price("") == 0.0


def test_parse_availability():
    """Verifies stock text normalization."""
    scraper = BookScraper()
    assert scraper.parse_availability("\n  In stock (22 available)\n") == "In stock"
    assert scraper.parse_availability("Out of stock") == "Out of stock"
    assert scraper.parse_availability(None) == "Unknown"
    assert scraper.parse_availability("") == "Unknown"


def test_parse_book_element_complete():
    """Verifies parsing of a standard product pod HTML element."""
    scraper = BookScraper()
    soup = BeautifulSoup(MOCK_PRODUCT_POD_HTML, "html.parser")
    pod = soup.select_one("article.product_pod")

    base_url = "https://books.toscrape.com/catalogue/category/books/mystery_3/index.html"
    book = scraper.parse_book_element(pod, page_url=base_url, category="Mystery")

    assert book is not None
    assert book.title == "Mock Book Title: The Comprehensive Guide"
    assert book.price == 34.50
    assert book.rating == 4
    assert book.availability == "In stock"
    assert book.category == "Mystery"
    assert book.source_url == "https://books.toscrape.com/catalogue/mock-book_123/index.html"


OUT_OF_STOCK_POD_HTML = """
<article class="product_pod">
    <h3>
        <a href="../../../sold-out-book_456/index.html" title="Sold Out Book">
            Sold Out Book
        </a>
    </h3>
    <p class="star-rating One"></p>
    <div class="product_price">
        <p class="price_color">£30.00</p>
        <p class="availability">Out of stock</p>
    </div>
</article>
"""


def test_parse_book_element_out_of_stock():
    """Out-of-stock pods must not be parsed as Unknown availability."""
    scraper = BookScraper()
    pod = BeautifulSoup(OUT_OF_STOCK_POD_HTML, "html.parser").select_one("article.product_pod")
    book = scraper.parse_book_element(
        pod,
        page_url="https://books.toscrape.com/catalogue/category/books/mystery_3/index.html",
        category="Mystery",
    )

    assert book is not None
    assert book.title == "Sold Out Book"
    assert book.price == 30.00
    assert book.availability == "Out of stock"


def test_parse_book_element_missing_fields():
    """Verifies parser does not crash when fields are absent or malformed."""
    scraper = BookScraper()

    # Pod with missing link/title tag
    incomplete_html = '<article class="product_pod"><p>Missing title</p></article>'
    pod = BeautifulSoup(incomplete_html, "html.parser").article
    assert scraper.parse_book_element(pod, page_url="https://books.toscrape.com/") is None

    # Pod with missing price and rating tags
    partial_html = """
    <article class="product_pod">
        <h3><a href="sample.html" title="Sample">Sample</a></h3>
    </article>
    """
    partial_pod = BeautifulSoup(partial_html, "html.parser").article
    book = scraper.parse_book_element(partial_pod, page_url="https://books.toscrape.com/")
    assert book is not None
    assert book.title == "Sample"
    assert book.price == 0.0
    assert book.rating == 0
    assert book.availability == "Unknown"


HOME_HTML = """
<html><body>
<div class="side_categories">
  <ul class="nav-list">
    <li><ul>
      <li><a href="catalogue/category/books/fiction_1/index.html">Fiction</a></li>
    </ul></li>
  </ul>
</div>
</body></html>
"""

CATEGORY_PAGE_WITH_BOOK = """
<html><body>
<article class="product_pod">
  <h3><a href="book-one.html" title="Book One">Book One</a></h3>
  <p class="star-rating Three"></p>
  <p class="price_color">£10.00</p>
  <p class="instock availability">In stock</p>
</article>
<li class="next"><a href="page-2.html">next</a></li>
</body></html>
"""

EMPTY_CATEGORY_PAGE = """
<html><body></body></html>
"""


def test_scrape_all_books_homepage_failure():
    """Homepage fetch failure must be flagged, not treated as an empty catalog."""
    scraper = BookScraper(base_url="https://books.toscrape.com/")
    with patch.object(scraper, "fetch_html", return_value=None):
        result = scraper.scrape_all_books()

    assert result.homepage_failed is True
    assert result.books == []
    assert result.categories_discovered == 0
    assert result.failed_urls == ["https://books.toscrape.com/"]


def test_scrape_all_books_partial_page_failure():
    """A later page failure must be recorded without pretending the run was clean."""
    scraper = BookScraper(base_url="https://books.toscrape.com/")
    call_count = {"n": 0}

    def fetch_side(url):
        call_count["n"] += 1
        if url.rstrip("/").endswith("books.toscrape.com"):
            return HOME_HTML
        if "fiction" in url and call_count["n"] == 2:
            return CATEGORY_PAGE_WITH_BOOK
        return None

    with patch.object(scraper, "fetch_html", side_effect=fetch_side):
        result = scraper.scrape_all_books(max_categories=1, max_pages_per_category=5)

    assert result.homepage_failed is False
    assert len(result.books) == 1
    assert len(result.failed_urls) == 1
    assert result.failed_urls[0].endswith("page-2.html")


def test_scrape_all_books_genuine_empty_catalog():
    """An empty but successful category scrape is not a discovery or fetch failure."""
    scraper = BookScraper(base_url="https://books.toscrape.com/")

    def fetch_side(url):
        if url.rstrip("/").endswith("books.toscrape.com"):
            return HOME_HTML
        return EMPTY_CATEGORY_PAGE

    with patch.object(scraper, "fetch_html", side_effect=fetch_side):
        result = scraper.scrape_all_books(max_categories=1)

    assert result.homepage_failed is False
    assert result.categories_discovered == 1
    assert result.books == []
    assert result.failed_urls == []
