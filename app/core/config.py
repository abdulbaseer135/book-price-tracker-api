from typing import Optional
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # Application Metadata
    PROJECT_NAME: str = "Book Price Tracker API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # PostgreSQL Database Credentials (required — no hardcoded password defaults)
    POSTGRES_USER: str = Field(..., description="PostgreSQL username")
    POSTGRES_PASSWORD: str = Field(..., description="PostgreSQL password")
    POSTGRES_DB: str = Field(..., description="PostgreSQL database name")
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Explicit DATABASE_URL (takes precedence if provided)
    DATABASE_URL: Optional[str] = None

    # Web Scraper Configuration
    SCRAPER_BASE_URL: str = "https://books.toscrape.com/"
    SCRAPER_REQUEST_TIMEOUT: float = 15.0
    SCRAPER_MAX_RETRIES: int = 3
    SCRAPER_DEFAULT_MAX_PAGES: int = 50  # books.toscrape.com has 50 pages total (1000 books)

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """Returns DATABASE_URL if explicitly set, otherwise constructs standard PostgreSQL URI."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return url
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
