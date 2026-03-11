"""
SQLite-backed token budget tracker.

Schema: (provider TEXT, date TEXT, tokens_used INTEGER,
          requests_this_minute INTEGER, last_request_ts REAL)

- date is always stored as YYYY-MM-DD in the configured local timezone.
- Resets happen implicitly: no row for today's date means zero usage.
- Writes are atomic (single UPDATE or INSERT per call).
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path

import pytz

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    provider              TEXT NOT NULL,
    date                  TEXT NOT NULL,
    tokens_used           INTEGER NOT NULL DEFAULT 0,
    requests_this_minute  INTEGER NOT NULL DEFAULT 0,
    last_request_ts       REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (provider, date)
);
"""


class UsageDB:
    def __init__(self, db_path: str, timezone: str = "America/New_York"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.tz = pytz.timezone(timezone)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def _today(self) -> str:
        return datetime.now(self.tz).strftime("%Y-%m-%d")

    def get_usage(self, provider: str) -> int:
        today = self._today()
        row = self._conn.execute(
            "SELECT tokens_used FROM usage WHERE provider = ? AND date = ?",
            (provider, today),
        ).fetchone()
        return row[0] if row else 0

    def add_usage(self, provider: str, tokens: int) -> None:
        today = self._today()
        self._conn.execute(
            """
            INSERT INTO usage (provider, date, tokens_used, last_request_ts)
                VALUES (?, ?, ?, strftime('%s','now'))
            ON CONFLICT(provider, date) DO UPDATE SET
                tokens_used = tokens_used + excluded.tokens_used,
                last_request_ts = excluded.last_request_ts
            """,
            (provider, today, tokens),
        )
        self._conn.commit()

    def get_all_usage(self) -> list[dict]:
        """Return all usage rows for the current day."""
        today = self._today()
        rows = self._conn.execute(
            "SELECT provider, tokens_used FROM usage WHERE date = ?",
            (today,),
        ).fetchall()
        return [{"provider": r[0], "tokens_used": r[1], "date": today} for r in rows]

    def get_historical_usage(self) -> list[dict]:
        """Return all usage rows across all days, newest first."""
        rows = self._conn.execute(
            "SELECT provider, date, tokens_used FROM usage ORDER BY date DESC, provider ASC",
        ).fetchall()
        return [{"provider": r[0], "date": r[1], "tokens_used": r[2]} for r in rows]

    def get_totals_by_provider(self) -> list[dict]:
        """Return total tokens used per provider across all time."""
        rows = self._conn.execute(
            "SELECT provider, SUM(tokens_used) AS total, COUNT(*) AS days_active "
            "FROM usage GROUP BY provider ORDER BY total DESC",
        ).fetchall()
        return [{"provider": r[0], "total_tokens": r[1], "days_active": r[2]} for r in rows]

    def close(self) -> None:
        self._conn.close()
