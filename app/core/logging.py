import logging
import sys


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configures structured, clean logging for the application."""
    log_format = "%(asctime)s | %(levelname)-7s | %(name)s:%(lineno)d - %(message)s"

    # Avoid duplicate handlers if already configured
    logger = logging.getLogger("book_tracker")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    return logger


logger = setup_logging()
