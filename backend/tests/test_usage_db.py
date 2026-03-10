"""Tests for integrations/usage_db.py"""

import pytest
from unittest.mock import patch
from datetime import datetime
import pytz

from integrations.usage_db import UsageDB


def test_initial_usage_is_zero(db_path):
    db = UsageDB(db_path, timezone="America/New_York")
    assert db.get_usage("claude") == 0
    db.close()


def test_add_and_get_usage(db_path):
    db = UsageDB(db_path)
    db.add_usage("claude", 1000)
    assert db.get_usage("claude") == 1000
    db.close()


def test_usage_accumulates(db_path):
    db = UsageDB(db_path)
    db.add_usage("claude", 500)
    db.add_usage("claude", 300)
    assert db.get_usage("claude") == 800
    db.close()


def test_different_providers_are_independent(db_path):
    db = UsageDB(db_path)
    db.add_usage("claude", 1000)
    db.add_usage("gemini", 500)
    assert db.get_usage("claude") == 1000
    assert db.get_usage("gemini") == 500
    db.close()


def test_get_all_usage_returns_today(db_path):
    db = UsageDB(db_path)
    db.add_usage("claude", 100)
    db.add_usage("groq", 200)

    rows = db.get_all_usage()
    providers = {r["provider"] for r in rows}
    assert "claude" in providers
    assert "groq" in providers
    db.close()


def test_usage_resets_on_new_day(db_path):
    """Usage from a different date should not appear in today's count."""
    db = UsageDB(db_path)

    # Write usage for "yesterday"
    db._conn.execute(
        "INSERT INTO usage (provider, date, tokens_used, last_request_ts) VALUES (?, ?, ?, 0)",
        ("claude", "2000-01-01", 9999),
    )
    db._conn.commit()

    # Today's usage should still be 0
    assert db.get_usage("claude") == 0
    db.close()


def test_timezone_affects_date(db_path):
    """DB should use the configured timezone for date keying."""
    db = UsageDB(db_path, timezone="America/New_York")
    db.add_usage("claude", 42)
    tz = pytz.timezone("America/New_York")
    expected_date = datetime.now(tz).strftime("%Y-%m-%d")

    rows = db._conn.execute(
        "SELECT date FROM usage WHERE provider = 'claude'"
    ).fetchall()
    assert rows[0][0] == expected_date
    db.close()
