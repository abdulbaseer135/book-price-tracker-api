from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.core.logging import logger
from app.models.base import Base

# Database engine configuration
database_url = settings.sync_database_url

# Configure connect_args based on DB dialect (e.g. SQLite thread check)
connect_args = {}
if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    database_url,
    echo=False,
    pool_pre_ping=True,  # Proactively validates connections before issuing queries
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def init_db() -> None:
    """Initializes database tables based on Declarative Base metadata."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
    except Exception as exc:
        logger.error(
            "Database initialization failed (%s). Schema setup could not complete.",
            type(exc).__name__,
        )
        raise


def check_db_connection() -> bool:
    """Returns True when the configured database accepts a simple connectivity query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error(
            "Database connectivity check failed (%s). Database is unavailable.",
            type(exc).__name__,
        )
        return False


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a scoped database session per request,
    guaranteeing proper teardown and cleanup upon request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
