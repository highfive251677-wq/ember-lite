"""
Ember Storage Abstraction (Preflight — Truthful Modes)
========================================================
Modes:
    legacy_mode=True   → per-module legacy DBs (perception/*.db)
    legacy_mode=False  → consolidated ember_operational.db

KPI #4 (Local-First): Pure Python stdlib.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DB_DIR = Path.home() / ".ember"
DEFAULT_OPERATIONAL_DB = DEFAULT_DB_DIR / "ember_operational.db"
DEFAULT_LEGACY_DIR = Path(__file__).parent


WAVE_1_TABLES = {
    "incidents", "incident_runs", "pipeline_runs", "pipeline_stages",
    "outbox", "audit_events", "schema_migrations", "schema_meta",
}
WAVE_2_TABLES = {"decisions", "lessons", "sensor_events"}
WAVE_3_TABLES = {
    "evidence_blocks", "anchors", "anchor_members",
    "authorizations", "approvals", "action_contracts", "receipts",
}

LEGACY_DB_MAP = {
    "evidence_chain": "evidence_chain.db",
    "anchors": "anchors.db",
    "authorization": "authorization.db",
    "contracts": "contracts.db",
    "lessons": "lessons.db",
    "decision_log": "lessons.db",
    "sensor_buffer": "sensor_buffer.db",
    "incidents": "incidents.db",
    "pipeline_state": "pipeline_state.db",
}


class Storage:
    """Truthful storage abstraction. Two modes only."""

    def __init__(self, db_path=None, legacy_mode=False, legacy_root=None):
        self.db_path = Path(db_path) if db_path else DEFAULT_OPERATIONAL_DB
        self.legacy_mode = legacy_mode
        self.legacy_root = Path(legacy_root) if legacy_root else DEFAULT_LEGACY_DIR

    # =========================================================
    # LEGACY MODE
    # =========================================================

    def connect_legacy(self, module_name: str) -> sqlite3.Connection:
        """Connect to a SPECIFIC legacy DB by module name."""
        if module_name not in LEGACY_DB_MAP:
            raise ValueError(f"Unknown legacy module: {module_name}")
        db_file = self.legacy_root / LEGACY_DB_MAP[module_name]
        if not db_file.exists():
            raise FileNotFoundError(f"Legacy DB not found: {db_file}")
        conn = sqlite3.connect(str(db_file), timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    # =========================================================
    # OPERATIONAL MODE
    # =========================================================

    def connect_operational(self) -> sqlite3.Connection:
        """Connect to consolidated operational DB."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    # =========================================================
    # MODE-AWARE DISPATCH
    # =========================================================

    def connect(self, module_name: str | None = None) -> sqlite3.Connection:
        """Mode-aware connect. Legacy requires module_name."""
        if self.legacy_mode:
            if not module_name:
                raise ValueError(
                    "legacy_mode requires module_name. "
                    "Use connect_legacy('module') or connect_operational()."
                )
            return self.connect_legacy(module_name)
        return self.connect_operational()

    # =========================================================
    # STATUS
    # =========================================================

    def is_operational_db_present(self) -> bool:
        return self.db_path.exists()

    def wave_status(self) -> dict:
        if not self.is_operational_db_present():
            return {"operational_db": False,
                    "wave_1": False, "wave_2": False, "wave_3": False}
        try:
            conn = sqlite3.connect(str(self.db_path))
            try:
                tables = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )}
            finally:
                conn.close()
            return {
                "operational_db": True,
                "wave_1": WAVE_1_TABLES.issubset(tables),
                "wave_2": WAVE_2_TABLES.issubset(tables),
                "wave_3": WAVE_3_TABLES.issubset(tables),
                "tables_present": sorted(tables),
            }
        except Exception as exc:
            return {"operational_db": False, "error": str(exc)}

    def init_wave_1(self) -> dict:
        conn = self.connect_operational()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL DEFAULT '1.0',
                    device_id TEXT NOT NULL,
                    incident_type TEXT NOT NULL,
                    zone_id TEXT,
                    opened_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_stage TEXT NOT NULL,
                    current_risk_tier TEXT,
                    current_policy_id TEXT,
                    current_evidence_root TEXT,
                    run_id TEXT NOT NULL,
                    created_by TEXT NOT NULL DEFAULT 'system',
                    closed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS incident_runs (
                    run_id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL DEFAULT 'running',
                    stage TEXT,
                    FOREIGN KEY (incident_id)
                        REFERENCES incidents(incident_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL DEFAULT '1.0',
                    incident_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    current_stage TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    last_error TEXT
                );
                CREATE TABLE IF NOT EXISTS pipeline_stages (
                    run_id TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    stage_order INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT,
                    finished_at TEXT,
                    heartbeat_at TEXT,
                    result_json TEXT,
                    result_digest TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    PRIMARY KEY (run_id, stage_name),
                    FOREIGN KEY (run_id)
                        REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
                    UNIQUE (run_id, stage_order)
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    outbox_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    incident_id TEXT,
                    target_store TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    applied_at TEXT,
                    applied_digest TEXT
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT,
                    run_id TEXT,
                    event_type TEXT NOT NULL,
                    actor_id TEXT,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    backup_path TEXT,
                    attestation_id TEXT
                );
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_inc_status ON incidents(status);
                CREATE INDEX IF NOT EXISTS idx_inc_zone ON incidents(zone_id);
                CREATE INDEX IF NOT EXISTS idx_runs_incident ON incident_runs(incident_id);
                CREATE INDEX IF NOT EXISTS idx_pr_incident ON pipeline_runs(incident_id);
                CREATE INDEX IF NOT EXISTS idx_ps_run_order ON pipeline_stages(run_id, stage_order);
                CREATE INDEX IF NOT EXISTS idx_obx_status ON outbox(status);
                CREATE INDEX IF NOT EXISTS idx_audit_incident ON audit_events(incident_id);
            """)
            return {"wave": 1, "created": True, "db_path": str(self.db_path)}
        except Exception as exc:
            return {"wave": 1, "created": False,
                    "error": f"{type(exc).__name__}: {exc}"}
        finally:
            conn.close()

    def list_legacy_dbs(self) -> list:
        result = []
        for name in ["evidence_chain.db", "anchors.db",
                     "authorization.db", "contracts.db",
                     "lessons.db", "sensor_buffer.db",
                     "incidents.db", "pipeline_state.db"]:
            path = self.legacy_root / name
            if path.exists():
                result.append({
                    "name": name,
                    "size_bytes": path.stat().st_size,
                })
        return result


if __name__ == "__main__":
    print("=" * 60)
    print("  STORAGE — LEGACY vs OPERATIONAL MODES")
    print("=" * 60)
    print()

    op = Storage()
    print(f"1. Operational: legacy_mode={op.legacy_mode}")
    print(f"   DB path: {op.db_path}")
    if not op.is_operational_db_present():
        r = op.init_wave_1()
        print(f"   Wave 1 init: {r.get('created')}")
    status = op.wave_status()
    print(f"   wave_1: {status.get('wave_1')}")
    print()

    leg = Storage(legacy_mode=True)
    print(f"2. Legacy: legacy_mode={leg.legacy_mode}")
    legacy_dbs = leg.list_legacy_dbs()
    print(f"   Legacy DBs: {len(legacy_dbs)}")
    for d in legacy_dbs[:5]:
        print(f"     • {d['name']} ({d['size_bytes']} bytes)")
    print()

    print("3. Mode-aware connect():")
    try:
        op.connect()
        print("   ✅ Operational connect() OK")
    except Exception as e:
        print(f"   ❌ Operational: {e}")

    try:
        leg.connect()
        print("   ❌ Legacy should raise")
    except ValueError:
        print("   ✅ Legacy connect() rejected (correct)")

    if legacy_dbs:
        module = legacy_dbs[0]["name"].replace(".db", "")
        try:
            leg.connect_legacy(module)
            print(f"   ✅ connect_legacy('{module}') OK")
        except Exception as e:
            print(f"   ⚠️  connect_legacy: {e}")

    print()
    print("🎉 STORAGE MODES TRUTHFUL")
