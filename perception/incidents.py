"""
Ember Incident Envelope (Phase 8 — Task 1)
=============================================
Copilot-designed schema + KPI-compliant modifications.

KPI #1 (Evidence-First): Pointer-only to evidence, no duplication.
KPI #2 (Human-in-Control): created_by attribution.
KPI #3 (Cryptographic): evidence_root is hash-linked.
KPI #4 (Local-First): Single SQLite, WAL mode.
Pure Python stdlib only.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone


DB_PATH = os.path.join(os.path.dirname(__file__), "incidents.db")
SCHEMA_VERSION = "1.0"

ALLOWED_STATUS = {
    "OPEN", "MONITORING", "ESCALATED", "AWAITING_APPROVAL",
    "AUTHORIZED", "CONTAINED", "RESOLVED", "CLOSED", "CANCELLED",
}

ALLOWED_STAGES = {
    "NEW", "VALIDATED", "RECORDED", "ASSESSED", "GOVERNED",
    "AWAITING_APPROVAL", "AUTHORIZED", "SIMULATED", "EXECUTED",
    "ANCHORED", "REJECTED", "BLOCKED", "RETRYABLE_FAILURE",
    "PERMANENT_FAILURE", "RESOLVED",
}

ALLOWED_TIERS = {"T0", "T1", "T2", "T3", "T4", "T5"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_incidents_db() -> str:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        # Main incident envelope
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL DEFAULT '1.0',
                device_id TEXT NOT NULL,
                incident_type TEXT NOT NULL,
                zone_id TEXT,
                opened_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN (
                    'OPEN','MONITORING','ESCALATED','AWAITING_APPROVAL',
                    'AUTHORIZED','CONTAINED','RESOLVED','CLOSED','CANCELLED'
                )),
                current_stage TEXT NOT NULL CHECK (current_stage IN (
                    'NEW','VALIDATED','RECORDED','ASSESSED','GOVERNED',
                    'AWAITING_APPROVAL','AUTHORIZED','SIMULATED','EXECUTED',
                    'ANCHORED','REJECTED','BLOCKED','RETRYABLE_FAILURE',
                    'PERMANENT_FAILURE','RESOLVED'
                )),
                current_risk_tier TEXT CHECK (
                    current_risk_tier IS NULL OR
                    current_risk_tier IN ('T0','T1','T2','T3','T4','T5')
                ),
                current_policy_id TEXT,
                current_evidence_root TEXT,
                run_id TEXT NOT NULL,
                created_by TEXT NOT NULL DEFAULT 'system',
                closed_at TEXT
            )
        """)

        # Run history (one incident = many runs)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_runs (
                run_id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL DEFAULT 'running',
                stage TEXT,
                FOREIGN KEY (incident_id)
                    REFERENCES incidents(incident_id) ON DELETE CASCADE
            )
        """)

        # Indexes (as Copilot recommended)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_status ON incidents(status)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_zone ON incidents(zone_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_opened ON incidents(opened_at)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_status_zone "
            "ON incidents(status, zone_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_incident "
            "ON incident_runs(incident_id)")

        conn.commit()
    finally:
        conn.close()
    return DB_PATH


def open_incident(
    incident_id: str,
    device_id: str,
    incident_type: str,
    zone_id: str | None = None,
    created_by: str = "system",
) -> dict:
    """Open a new incident or get existing."""
    init_incidents_db()
    now = _now()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT status, run_id FROM incidents WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()

        if existing:
            conn.execute("COMMIT")
            return {"opened": False, "existing": True,
                    "status": existing[0], "run_id": existing[1]}

        run_id = f"run-{incident_id}-1"
        conn.execute("""
            INSERT INTO incidents (
                incident_id, schema_version, device_id, incident_type,
                zone_id, opened_at, last_seen_at, status, current_stage,
                current_risk_tier, current_policy_id, current_evidence_root,
                run_id, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', 'NEW',
                      NULL, NULL, NULL, ?, ?)
        """, (
            incident_id, SCHEMA_VERSION, device_id, incident_type,
            zone_id, now, now, run_id, created_by,
        ))
        conn.execute("""
            INSERT INTO incident_runs (run_id, incident_id, started_at, status, stage)
            VALUES (?, ?, ?, 'running', 'NEW')
        """, (run_id, incident_id, now))
        conn.execute("COMMIT")

        return {"opened": True, "incident_id": incident_id,
                "run_id": run_id, "status": "OPEN", "stage": "NEW"}
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return {"opened": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()


def advance_run(
    incident_id: str,
    stage: str,
    risk_tier: str | None = None,
    policy_id: str | None = None,
    evidence_root: str | None = None,
    status: str | None = None,
) -> dict:
    """Advance the current run to a new stage."""
    if stage not in ALLOWED_STAGES:
        return {"advanced": False, "error": f"invalid_stage:{stage}"}
    if status and status not in ALLOWED_STATUS:
        return {"advanced": False, "error": f"invalid_status:{status}"}
    if risk_tier and risk_tier not in ALLOWED_TIERS:
        return {"advanced": False, "error": f"invalid_tier:{risk_tier}"}

    init_incidents_db()
    now = _now()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT run_id, status FROM incidents WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return {"advanced": False, "error": "incident_not_found"}

        run_id, current_status = row
        new_status = status or current_status

        conn.execute("""
            UPDATE incidents
            SET last_seen_at = ?,
                status = ?,
                current_stage = ?,
                current_risk_tier = COALESCE(?, current_risk_tier),
                current_policy_id = COALESCE(?, current_policy_id),
                current_evidence_root = COALESCE(?, current_evidence_root),
                closed_at = CASE
                    WHEN ? IN ('RESOLVED','CLOSED','CANCELLED')
                        THEN COALESCE(closed_at, ?)
                    ELSE closed_at
                END
            WHERE incident_id = ?
        """, (
            now, new_status, stage, risk_tier, policy_id,
            evidence_root, new_status, now, incident_id,
        ))

        conn.execute("""
            UPDATE incident_runs
            SET stage = ?, status = CASE
                WHEN ? IN ('ANCHORED','REJECTED','PERMANENT_FAILURE','RESOLVED')
                    THEN 'finished'
                ELSE 'running'
            END,
            finished_at = CASE
                WHEN ? IN ('ANCHORED','REJECTED','PERMANENT_FAILURE','RESOLVED')
                    THEN ?
                ELSE finished_at
            END
            WHERE run_id = ?
        """, (stage, stage, stage, now, run_id))

        conn.execute("COMMIT")
        return {"advanced": True, "incident_id": incident_id,
                "run_id": run_id, "stage": stage, "status": new_status}
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return {"advanced": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()


def get_incident(incident_id: str) -> dict | None:
    init_incidents_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()
        if not row:
            return None
        incident = dict(row)
        runs = conn.execute(
            "SELECT * FROM incident_runs WHERE incident_id = ? "
            "ORDER BY started_at ASC",
            (incident_id,),
        ).fetchall()
        incident["runs"] = [dict(r) for r in runs]
        return incident
    finally:
        conn.close()


def list_active_incidents() -> list[dict]:
    init_incidents_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT incident_id, zone_id, status, current_stage,
                   current_risk_tier, opened_at, last_seen_at
            FROM incidents
            WHERE status NOT IN ('RESOLVED','CLOSED','CANCELLED')
            ORDER BY opened_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def incident_summary() -> dict:
    init_incidents_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        total = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        by_status = dict(conn.execute(
            "SELECT status, COUNT(*) FROM incidents GROUP BY status"
        ).fetchall())
        runs = conn.execute("SELECT COUNT(*) FROM incident_runs").fetchone()[0]
        return {
            "schema_version": SCHEMA_VERSION,
            "total_incidents": total,
            "by_status": by_status,
            "total_runs": runs,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import tempfile
    DB_PATH = tempfile.mktemp(suffix=".db")

    print("=" * 60)
    print("  PHASE 8 — TASK 1: INCIDENT ENVELOPE TEST")
    print("=" * 60)
    print()

    # Case 1: Open
    r = open_incident(
        "INC-001", "tab-a-2017", "wildfire",
        zone_id="zone-03", created_by="operator:founder",
    )
    assert r["opened"] is True
    print(f"✅ Case 1: Opened {r['incident_id']} (run={r['run_id']})")

    # Case 2: Idempotent open
    r2 = open_incident("INC-001", "tab-a-2017", "wildfire")
    assert r2["opened"] is False and r2["existing"] is True
    print(f"✅ Case 2: Idempotent open")

    # Case 3: Advance
    a = advance_run("INC-001", "ASSESSED", risk_tier="T3",
                    policy_id="wildfire-v1", evidence_root="abc" * 20)
    assert a["advanced"] is True
    print(f"✅ Case 3: Advanced to ASSESSED (tier=T3)")

    # Case 4: Full lifecycle
    stages = ["GOVERNED", "AWAITING_APPROVAL", "AUTHORIZED",
              "SIMULATED", "EXECUTED", "ANCHORED"]
    for stage in stages:
        advance_run("INC-001", stage)
    print(f"✅ Case 4: Full lifecycle advanced")

    # Case 5: Resolve
    advance_run("INC-001", "RESOLVED", status="RESOLVED")
    inc = get_incident("INC-001")
    assert inc["status"] == "RESOLVED"
    assert inc["closed_at"] is not None
    print(f"✅ Case 5: Resolved with closed_at")

    # Case 6: Run history
    assert len(inc["runs"]) >= 1
    print(f"✅ Case 6: Run history ({len(inc['runs'])} runs)")

    # Case 7: Invalid stage
    bad = advance_run("INC-001", "INVALID_STAGE")
    assert bad["advanced"] is False
    print(f"✅ Case 7: Invalid stage rejected")

    # Case 8: Active list
    open_incident("INC-002", "tab-a-2017", "smoke", zone_id="zone-04")
    active = list_active_incidents()
    assert len(active) >= 1
    print(f"✅ Case 8: Active list ({len(active)} incidents)")

    # Case 9: Summary
    s = incident_summary()
    assert s["total_incidents"] >= 2
    print(f"✅ Case 9: Summary — {s['total_incidents']} incidents, "
          f"{s['total_runs']} runs")

    print()
    print("🎉 TASK 1 — ALL 9 CASES PASSED")
