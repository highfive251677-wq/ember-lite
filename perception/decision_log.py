"""
Ember Wildfire Decision Log
===========================

Assessment-pattern history is intentionally separate from lessons.py.

- perception/lessons.py stores actual mistakes and prevention rules.
- This module stores assessment decisions for later outcome analysis.

Both use the existing perception/lessons.db SQLite file.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any


DB_PATH = os.path.join(os.path.dirname(__file__), "lessons.db")


def init_decision_log() -> str:
    """Create the decisions table in the existing lessons database."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT,
                assessment TEXT,
                severity TEXT,
                confidence REAL,
                requires_human_approval INTEGER,
                pattern TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    return DB_PATH


def record_decision(
    incident_id: str | None,
    assessment: str,
    severity: str,
    confidence: float,
    requires_human_approval: bool,
    pattern: str | None = None,
) -> int:
    """Record one assessment decision. Does NOT write to lessons table."""
    init_decision_log()

    confidence_value = max(0.0, min(1.0, float(confidence)))

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            """
            INSERT INTO decisions (
                incident_id, assessment, severity,
                confidence, requires_human_approval, pattern
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id, assessment, severity,
                confidence_value,
                int(bool(requires_human_approval)),
                pattern,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_decisions(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent assessment decisions."""
    init_decision_log()

    safe_limit = max(1, min(int(limit), 1000))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, incident_id, assessment, severity,
                   confidence, requires_human_approval,
                   pattern, created_at
            FROM decisions
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    finally:
        conn.close()

    return [dict(row) for row in rows]


def count_decisions() -> int:
    """Return the number of recorded assessment decisions."""
    init_decision_log()

    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


if __name__ == "__main__":
    decision_id = record_decision(
        incident_id="TEST-001",
        assessment="suspicious_signal",
        severity="high",
        confidence=0.62,
        requires_human_approval=True,
        pattern="pm25_rising_without_valid_baseline",
    )

    print(f"Decision recorded: {decision_id}")
    print(f"Total decisions: {count_decisions()}")
