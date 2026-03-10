"""
Shared pytest fixtures for AutoDev backend tests.
"""

import os
import sys
import tempfile
import pytest

# Ensure backend/ is on sys.path so tests can import modules directly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Minimal env so LLMClient doesn't crash when constructed in tests
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory path as a string."""
    return str(tmp_path)


@pytest.fixture
def session_path(tmp_path):
    """Return a temp path for a session JSON file."""
    return str(tmp_path / "session.json")


@pytest.fixture
def db_path(tmp_path):
    """Return a temp path for the SQLite usage DB."""
    return str(tmp_path / "usage.db")
