"""Tests for database readiness checks."""
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db import database


def test_check_db_connection_succeeds_with_sqlite_engine(monkeypatch):
    """Connectivity check passes against an in-memory SQLite engine."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(database, "engine", test_engine)

    assert database.check_db_connection() is True


def test_check_db_connection_fails_when_engine_unreachable(monkeypatch):
    """Connectivity check returns False without exposing credentials to callers."""
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("connection refused")

    monkeypatch.setattr(database, "engine", mock_engine)

    assert database.check_db_connection() is False
