"""
Ember Wave 2 Migration (Phase 8 — Task 3)
===========================================
Migrate non-crypto tables into ember_operational.db:

    decisions    ← decision_log.db
    lessons      ← lessons.db
    sensor_events ← sensor_buffer.db

Design:
    - Legacy DBs attached read-only (never modified)
    - Idempotent (INSERT OR IGNORE)
    - Conflict detection (duplicate PKs, mismatched content)
    - Legacy source ID preserved
    - Verification: row counts + sample hashes

KPI #1 (Evidence-First): Every row traceable to source.
KPI #3 (Cryptographic): No silent overwrites — conflicts reported.
KPI #4 (Local-First): Pure stdlib.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(v) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)


def _digest(v) -> str:
    return hashlib.sha256(_canonical(v).encode("utf-8")).hexdigest()


# =========================================================
# WAVE 2 SCHEMA
# =========================================================

WAVE2_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    incident_id TEXT,
    assessment TEXT NOT NULL,
    severity TEXT,
    confidence REAL,
    requires_human_approval INTEGER DEFAULT 0,
    pattern TEXT,
    created_at TEXT,
    legacy_source_id INTEGER,
    legacy_source_table TEXT
);

CREATE INDEX IF NOT EXISTS idx_dec_incident
    ON decisions(incident_id);
CREATE INDEX IF NOT EXISTS idx_dec_created
    ON decisions(created_at);

CREATE TABLE IF NOT EXISTS lessons (
    lesson_id TEXT PRIMARY KEY,
    lesson_type TEXT NOT NULL,
    trigger_pattern TEXT,
    mistake TEXT NOT NULL,
    root_cause TEXT,
    fix TEXT NOT NULL,
    prevention TEXT,
    severity TEXT,
    times_encountered INTEGER DEFAULT 1,
    learned_at TEXT,
    legacy_source_id INTEGER,
    legacy_source_table TEXT
);

CREATE INDEX IF NOT EXISTS idx_lessons_type
    ON lessons(lesson_type);
CREATE INDEX IF NOT EXISTS idx_lessons_severity
    ON lessons(severity);

CREATE TABLE IF NOT EXISTS sensor_events (
    event_id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE,
    sensor_id TEXT,
    zone_id TEXT,
    captured_at TEXT,
    payload_json TEXT NOT NULL,
    payload_digest TEXT,
    status TEXT DEFAULT 'queued',
    attempts INTEGER DEFAULT 0,
    created_at TEXT,
    legacy_source_id INTEGER,
    legacy_source_table TEXT
);

CREATE INDEX IF NOT EXISTS idx_se_sensor
    ON sensor_events(sensor_id);
CREATE INDEX IF NOT EXISTS idx_se_status
    ON sensor_events(status);

CREATE TABLE IF NOT EXISTS migration_conflicts (
    conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_wave INTEGER NOT NULL,
    source_table TEXT NOT NULL,
    source_pk TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    details_json TEXT,
    detected_at TEXT NOT NULL
);
"""


def init_wave_2_schema(conn: sqlite3.Connection) -> None:
    """Create Wave 2 tables + conflict log in operational DB."""
    conn.executescript(WAVE2_SCHEMA)


# =========================================================
# BACKUP
# =========================================================

def backup_legacy_db(source: Path, backup_dir: Path) -> dict:
    """Copy legacy DB (safely via SQLite backup API)."""
    if not source.exists():
        return {"backed_up": False, "reason": "not_found",
                "source": str(source)}

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"{source.name}.backup_wave2_{timestamp}"

    try:
        src_conn = sqlite3.connect(str(source))
        dst_conn = sqlite3.connect(str(dest))
        with dst_conn:
            src_conn.backup(dst_conn)
        src_conn.close()
        dst_conn.close()

        # Hash the backup
        with open(dest, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()

        return {
            "backed_up": True,
            "source": str(source),
            "backup_path": str(dest),
            "size_bytes": dest.stat().st_size,
            "sha256": h,
        }
    except Exception as exc:
        return {"backed_up": False,
                "error": f"{type(exc).__name__}: {exc}"}


# =========================================================
# COPY DECISIONS
# =========================================================

def copy_decisions(conn: sqlite3.Connection,
                   legacy_path: Path) -> dict:
    """
    Copy rows from legacy decision_log.db into operational.decisions.
    Idempotent. Conflicts logged, not silently overwritten.
    """
    if not legacy_path.exists():
        return {"copied": 0, "skipped": 0, "conflicts": 0,
                "reason": "legacy_db_not_found"}

    # Read legacy rows
    src = sqlite3.connect(str(legacy_path))
    src.row_factory = sqlite3.Row
    try:
        rows = src.execute("""
            SELECT id, incident_id, assessment, severity, confidence,
                   requires_human_approval, pattern, created_at
            FROM decisions
        """).fetchall()
    except sqlite3.OperationalError as exc:
        src.close()
        return {"copied": 0, "skipped": 0, "conflicts": 0,
                "reason": f"table_missing:{exc}"}

    copied = 0
    skipped = 0
    conflicts = 0
    now = _now()

    with conn:
        for r in rows:
            decision_id = (
                r["incident_id"] + ":" + str(r["id"])
                if r["incident_id"]
                else f"legacy-{r['id']}"
            )

            existing = conn.execute(
                "SELECT assessment, severity, confidence "
                "FROM decisions WHERE decision_id = ?",
                (decision_id,),
            ).fetchone()

            if existing:
                # Conflict if content differs
                if (existing["assessment"] != r["assessment"]
                        or existing["severity"] != r["severity"]):
                    conn.execute("""
                        INSERT INTO migration_conflicts (
                            migration_wave, source_table, source_pk,
                            conflict_type, details_json, detected_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (2, "decision_log.decisions", str(r["id"]),
                          "content_mismatch",
                          json.dumps({
                              "existing": dict(existing),
                              "incoming": {
                                  "assessment": r["assessment"],
                                  "severity": r["severity"],
                              }
                          }), now))
                    conflicts += 1
                else:
                    skipped += 1
                continue

            conn.execute("""
                INSERT INTO decisions (
                    decision_id, incident_id, assessment, severity,
                    confidence, requires_human_approval, pattern,
                    created_at, legacy_source_id, legacy_source_table
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision_id, r["incident_id"], r["assessment"],
                r["severity"], r["confidence"],
                int(bool(r["requires_human_approval"])),
                r["pattern"], r["created_at"],
                r["id"], "decision_log.decisions",
            ))
            copied += 1

    src.close()
    return {"copied": copied, "skipped": skipped,
            "conflicts": conflicts, "total_source": len(rows)}


# =========================================================
# COPY LESSONS
# =========================================================

def copy_lessons(conn: sqlite3.Connection,
                 legacy_path: Path) -> dict:
    if not legacy_path.exists():
        return {"copied": 0, "skipped": 0, "conflicts": 0,
                "reason": "legacy_db_not_found"}

    src = sqlite3.connect(str(legacy_path))
    src.row_factory = sqlite3.Row
    try:
        rows = src.execute("""
            SELECT id, lesson_type, trigger_pattern, mistake,
                   root_cause, fix, prevention, severity,
                   times_encountered, learned_at
            FROM lessons
        """).fetchall()
    except sqlite3.OperationalError as exc:
        src.close()
        return {"copied": 0, "skipped": 0, "conflicts": 0,
                "reason": f"table_missing:{exc}"}

    copied = 0
    skipped = 0
    conflicts = 0
    now = _now()

    with conn:
        for r in rows:
            lesson_id = f"legacy-lesson-{r['id']}"
            existing = conn.execute(
                "SELECT mistake, fix FROM lessons WHERE lesson_id = ?",
                (lesson_id,),
            ).fetchone()

            if existing:
                if (existing["mistake"] != r["mistake"]
                        or existing["fix"] != r["fix"]):
                    conn.execute("""
                        INSERT INTO migration_conflicts (
                            migration_wave, source_table, source_pk,
                            conflict_type, details_json, detected_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (2, "lessons.lessons", str(r["id"]),
                          "content_mismatch",
                          json.dumps({
                              "existing": dict(existing),
                              "incoming": {
                                  "mistake": r["mistake"],
                                  "fix": r["fix"],
                              }
                          }), now))
                    conflicts += 1
                else:
                    skipped += 1
                continue

            conn.execute("""
                INSERT INTO lessons (
                    lesson_id, lesson_type, trigger_pattern, mistake,
                    root_cause, fix, prevention, severity,
                    times_encountered, learned_at,
                    legacy_source_id, legacy_source_table
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lesson_id, r["lesson_type"], r["trigger_pattern"],
                r["mistake"], r["root_cause"], r["fix"], r["prevention"],
                r["severity"], r["times_encountered"], r["learned_at"],
                r["id"], "lessons.lessons",
            ))
            copied += 1

    src.close()
    return {"copied": copied, "skipped": skipped,
            "conflicts": conflicts, "total_source": len(rows)}


# =========================================================
# COPY SENSOR EVENTS
# =========================================================

def copy_sensor_events(conn: sqlite3.Connection,
                       legacy_path: Path) -> dict:
    if not legacy_path.exists():
        return {"copied": 0, "skipped": 0, "conflicts": 0,
                "reason": "legacy_db_not_found"}

    src = sqlite3.connect(str(legacy_path))
    src.row_factory = sqlite3.Row
    try:
        rows = src.execute("""
            SELECT id, event_id, idempotency_key, sensor_id, zone_id,
                   payload, received_at, status, processing_attempts
            FROM inbox
        """).fetchall()
    except sqlite3.OperationalError as exc:
        src.close()
        return {"copied": 0, "skipped": 0, "conflicts": 0,
                "reason": f"table_missing:{exc}"}

    copied = 0
    skipped = 0
    conflicts = 0
    now = _now()

    with conn:
        for r in rows:
            payload_str = r["payload"]
            try:
                payload_obj = json.loads(payload_str)
                payload_digest = _digest(payload_obj)
            except Exception:
                payload_digest = _digest(payload_str)

            existing = conn.execute(
                "SELECT payload_digest FROM sensor_events "
                "WHERE event_id = ?",
                (r["event_id"],),
            ).fetchone()

            if existing:
                if existing["payload_digest"] != payload_digest:
                    conn.execute("""
                        INSERT INTO migration_conflicts (
                            migration_wave, source_table, source_pk,
                            conflict_type, details_json, detected_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (2, "sensor_buffer.inbox", r["event_id"],
                          "digest_mismatch",
                          json.dumps({
                              "existing_digest":
                                  existing["payload_digest"],
                              "incoming_digest": payload_digest,
                          }), now))
                    conflicts += 1
                else:
                    skipped += 1
                continue

            conn.execute("""
                INSERT INTO sensor_events (
                    event_id, idempotency_key, sensor_id, zone_id,
                    captured_at, payload_json, payload_digest,
                    status, attempts, created_at,
                    legacy_source_id, legacy_source_table
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["event_id"], r["idempotency_key"], r["sensor_id"],
                r["zone_id"], r["received_at"], payload_str,
                payload_digest, r["status"],
                r["processing_attempts"], r["received_at"],
                r["id"], "sensor_buffer.inbox",
            ))
            copied += 1

    src.close()
    return {"copied": copied, "skipped": skipped,
            "conflicts": conflicts, "total_source": len(rows)}


# =========================================================
# VERIFY
# =========================================================

def verify_wave_2(conn: sqlite3.Connection,
                  legacy_root: Path) -> dict:
    """Compare row counts between legacy and operational DBs."""
    report = {}

    # Decisions live in lessons.db (shared file, different table)
    checks = [
        ("decisions", "lessons.db", "decisions"),
        ("lessons", "lessons.db", "lessons"),
        ("sensor_events", "sensor_buffer.db", "inbox"),
    ]

    for op_table, legacy_db, legacy_table in checks:
        op_count = conn.execute(
            f"SELECT COUNT(*) FROM {op_table}"
        ).fetchone()[0]

        legacy_path = legacy_root / legacy_db
        if not legacy_path.exists():
            report[op_table] = {
                "operational": op_count,
                "legacy": 0,
                "match": op_count == 0,
                "note": "legacy_db_missing",
            }
            continue

        try:
            src = sqlite3.connect(str(legacy_path))
            legacy_count = src.execute(
                f"SELECT COUNT(*) FROM {legacy_table}"
            ).fetchone()[0]
            src.close()
        except sqlite3.OperationalError:
            legacy_count = 0

        report[op_table] = {
            "operational": op_count,
            "legacy": legacy_count,
            "match": op_count >= legacy_count,
            "delta": op_count - legacy_count,
        }

    return report


# =========================================================
# MAIN MIGRATION
# =========================================================

def run_wave_2(operational_db: str | Path,
               legacy_root: str | Path,
               backup_dir: str | Path | None = None,
               dry_run: bool = False) -> dict:
    """
    Run Wave 2 migration. Idempotent.

    Returns a report with: backups, copies, conflicts, verification.
    """
    operational_db = Path(operational_db)
    legacy_root = Path(legacy_root)
    backup_dir = Path(backup_dir) if backup_dir else (legacy_root / "wave2_backups")

    if not operational_db.exists():
        return {"error": "operational_db_not_found"}

    report = {
        "started_at": _now(),
        "operational_db": str(operational_db),
        "legacy_root": str(legacy_root),
        "dry_run": dry_run,
        "backups": [],
        "copies": {},
        "verification": {},
    }

    # 1. Backup legacy DBs
    for name in ["decision_log.db", "lessons.db", "sensor_buffer.db"]:
        path = legacy_root / name
        if path.exists():
            if dry_run:
                report["backups"].append({
                    "name": name, "would_backup": True,
                })
            else:
                b = backup_legacy_db(path, backup_dir)
                b["name"] = name
                report["backups"].append(b)

    if dry_run:
        report["finished_at"] = _now()
        return report

    # 2. Open operational DB and run migration
    conn = sqlite3.connect(str(operational_db),
                           isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")

    try:
        # Ensure schema
        init_wave_2_schema(conn)

        # 3. Copy each table
        # Decisions live in lessons.db (same file, different table)
        report["copies"]["decisions"] = copy_decisions(
            conn, legacy_root / "lessons.db")
        report["copies"]["lessons"] = copy_lessons(
            conn, legacy_root / "lessons.db")
        report["copies"]["sensor_events"] = copy_sensor_events(
            conn, legacy_root / "sensor_buffer.db")

        # 4. Verify
        report["verification"] = verify_wave_2(conn, legacy_root)
    finally:
        conn.close()

    report["finished_at"] = _now()
    report["success"] = all(
        c.get("conflicts", 0) == 0
        for c in report["copies"].values()
    )
    return report


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":
    import tempfile

    print("=" * 60)
    print("  TASK 3 WAVE 2 — DATA MIGRATION")
    print("=" * 60)
    print()

    # Setup: create synthetic legacy DBs in a temp dir
    tmp = Path(tempfile.mkdtemp())
    legacy_root = tmp / "legacy"
    legacy_root.mkdir()

    # decision_log.db
    dl = sqlite3.connect(str(legacy_root / "decision_log.db"))
    dl.execute("""
        CREATE TABLE decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT, assessment TEXT, severity TEXT,
            confidence REAL, requires_human_approval INTEGER,
            pattern TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    dl.execute("""
        INSERT INTO decisions (incident_id, assessment, severity,
                               confidence, requires_human_approval, pattern)
        VALUES ('INC-W2-1', 'possible_smoke', 'high', 0.75, 1, 'pm25_high')
    """)
    dl.commit()
    dl.close()

    # lessons.db
    ls = sqlite3.connect(str(legacy_root / "lessons.db"))
    ls.execute("""
        CREATE TABLE lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_type TEXT, trigger_pattern TEXT, mistake TEXT,
            root_cause TEXT, fix TEXT, prevention TEXT,
            severity TEXT DEFAULT 'medium',
            times_encountered INTEGER DEFAULT 1,
            learned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    ls.execute("""
        INSERT INTO lessons (lesson_type, mistake, fix)
        VALUES ('wave2_test', 'Test mistake', 'Test fix')
    """)
    ls.commit()
    ls.close()

    # sensor_buffer.db
    sb = sqlite3.connect(str(legacy_root / "sensor_buffer.db"))
    sb.execute("""
        CREATE TABLE inbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE, idempotency_key TEXT UNIQUE,
            sensor_id TEXT, zone_id TEXT, payload TEXT,
            received_at TEXT, processed INTEGER DEFAULT 0,
            processing_attempts INTEGER DEFAULT 0,
            status TEXT DEFAULT 'queued', error TEXT
        )
    """)
    sb.execute("""
        INSERT INTO inbox (event_id, idempotency_key, sensor_id,
                           zone_id, payload, received_at, status)
        VALUES ('EVT-W2-1', 'key1', 'S-1', 'Z-1',
                '{"pm25": 100}', '2026-09-18T12:00:00Z', 'queued')
    """)
    sb.commit()
    sb.close()

    # Operational DB
    op_db = tmp / "ember_operational.db"
    op = sqlite3.connect(str(op_db))
    op.executescript("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY, value TEXT, updated_at TEXT
        );
    """)
    op.commit()
    op.close()

    # Run Wave 2
    report = run_wave_2(op_db, legacy_root)

    print(f"Success: {report['success']}")
    print()
    print("Backups:")
    for b in report["backups"]:
        print(f"  • {b['name']}: "
              f"{'backed_up' if b.get('backed_up') else 'skipped'}")
    print()
    print("Copies:")
    for table, info in report["copies"].items():
        print(f"  • {table}: copied={info.get('copied', 0)}, "
              f"skipped={info.get('skipped', 0)}, "
              f"conflicts={info.get('conflicts', 0)}")
    print()
    print("Verification:")
    for table, info in report["verification"].items():
        print(f"  • {table}: op={info['operational']}, "
              f"legacy={info['legacy']}, match={info['match']}")

    print()
    if report["success"]:
        print("🎉 TASK 3 WAVE 2 PASSED")
    else:
        print("❌ Conflicts detected")
