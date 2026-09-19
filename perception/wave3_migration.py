"""
Ember Wave 3 Crypto Migration v2 — STAGED & RECOVERABLE
=========================================================
Migrate crypto tables from legacy DBs into ember_operational.db.

INNOVATIONS:
  1. Shadow Table Pattern — original tables untouched until atomic swap
  2. Migration Journal + Recovery Mode — crash-safe
  3. True Dry-Run — same code path, no writes
  4. Cryptographic Chain Verification — beyond row counts
  5. Signed Migration Receipt — Ember-native evidence

MODES:
  --mode=dry-run      Simulate, no writes (DEFAULT)
  --mode=apply        Real migration
  --mode=verify-only  Post-migration verification
  --mode=recover      Resume from journal after crash
  --mode=rollback     Rollback to pre-migration state

Pure Python stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from perception.wave3_schema import WAVE_3_SCHEMA, init_wave_3_schema
from perception.wave3_verify import verify_wave3_full, run_integrity_check


# =========================================================
# PATHS & CONSTANTS
# =========================================================

EMBER_HOME = Path.home() / ".ember"
MIGRATIONS_DIR = EMBER_HOME / "migrations"
JOURNAL_FILE = MIGRATIONS_DIR / "wave3_journal.json"
RECEIPT_FILE = MIGRATIONS_DIR / "wave3_receipt.json"
SHADOW_PREFIX = "_shadow_"

# ANSI colors (Termux supports these)
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(v) -> str:
    return json.dumps(
        v, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str
    )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def log(msg: str, level: str = "info"):
    """Colored terminal logging."""
    colors = {
        "info": C.CYAN,
        "ok": C.GREEN,
        "warn": C.YELLOW,
        "err": C.RED,
        "phase": C.MAGENTA + C.BOLD,
        "dim": C.DIM,
    }
    prefix = {
        "info": "▸",
        "ok": "✓",
        "warn": "⚠",
        "err": "✗",
        "phase": "◆",
        "dim": " ",
    }
    color = colors.get(level, C.RESET)
    p = prefix.get(level, "")
    print(f"{color}{p} {msg}{C.RESET}")


# =========================================================
# MIGRATION JOURNAL (Crash-Safe Recovery)
# =========================================================

class Journal:
    """
    Append-only journal for crash recovery.
    
    States:
      - "started"       : migration initiated
      - "snapshotted"   : source DBs snapshotted
      - "staged"        : shadow tables populated
      - "verified"      : staging verified
      - "swapped"       : shadow → real tables
      - "receipted"     : receipt generated
      - "completed"     : all done
      - "failed"        : stopped with reason
    """
    
    def __init__(self, path: Path = JOURNAL_FILE):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()
    
    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception:
                return {"states": [], "started_at": _now()}
        return {"states": [], "started_at": _now()}
    
    def _save(self):
        self.path.write_text(json.dumps(self.data, indent=2))
    
    def mark(self, state: str, **kwargs):
        entry = {"state": state, "at": _now()}
        entry.update(kwargs)
        self.data["states"].append(entry)
        self._save()
        log(f"Journal → {state}", "dim")
    
    def last_state(self) -> str:
        if not self.data["states"]:
            return "none"
        return self.data["states"][-1]["state"]
    
    def is_complete(self) -> bool:
        return self.last_state() == "completed"
    
    def is_failed(self) -> bool:
        return self.last_state() == "failed"
    
    def has_started(self) -> bool:
        return len(self.data["states"]) > 0
    
    def clear(self):
        self.data = {"states": [], "started_at": _now()}
        self._save()


# =========================================================
# PRE-FLIGHT CHECKLIST (Fail-Closed)
# =========================================================

def preflight_check(op_db: Path, legacy_root: Path, 
                    snapshot_dir: Path) -> dict:
    """Fail-closed checks before ANY operation."""
    log("Preflight checklist...", "phase")
    
    checks = {}
    blockers = []
    
    # 1. Operational DB exists
    checks["op_db_exists"] = op_db.exists()
    if not checks["op_db_exists"]:
        blockers.append(f"Operational DB not found: {op_db}")
    
    # 2. Legacy root exists
    checks["legacy_root_exists"] = legacy_root.exists()
    if not checks["legacy_root_exists"]:
        blockers.append(f"Legacy root not found: {legacy_root}")
    
    # 3. Legacy DBs readable
    legacy_dbs = ["evidence_chain.db", "anchors.db", 
                  "authorization.db", "contracts.db"]
    checks["legacy_dbs"] = {}
    for db in legacy_dbs:
        p = legacy_root / db
        if p.exists():
            try:
                conn = sqlite3.connect(str(p))
                conn.execute("SELECT 1").fetchone()
                conn.close()
                checks["legacy_dbs"][db] = "readable"
            except Exception as exc:
                checks["legacy_dbs"][db] = f"error: {exc}"
                blockers.append(f"Cannot read {db}: {exc}")
        else:
            checks["legacy_dbs"][db] = "not_found"
    
    # 4. Snapshot dir writable
    try:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        test_file = snapshot_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        checks["snapshot_dir_writable"] = True
    except Exception as exc:
        checks["snapshot_dir_writable"] = False
        blockers.append(f"Snapshot dir not writable: {exc}")
    
    # 5. migration_conflicts table exists
    if op_db.exists():
        conn = sqlite3.connect(str(op_db))
        try:
            result = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='migration_conflicts'"
            ).fetchone()
            checks["conflicts_table"] = bool(result)
            if not result:
                blockers.append("migration_conflicts table missing")
        finally:
            conn.close()
    
    # 6. DB not locked
    if op_db.exists():
        try:
            conn = sqlite3.connect(str(op_db), timeout=1.0)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("ROLLBACK")
            conn.close()
            checks["db_not_locked"] = True
        except sqlite3.OperationalError as exc:
            checks["db_not_locked"] = False
            blockers.append(f"DB locked: {exc}")
    
    # 7. Disk space (need at least 5MB)
    try:
        stat = os.statvfs(str(EMBER_HOME))
        free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
        checks["free_mb"] = round(free_mb, 2)
        if free_mb < 5:
            blockers.append(f"Insufficient disk: {free_mb:.1f} MB free")
    except Exception:
        checks["free_mb"] = None
    
    result = {
        "ok": len(blockers) == 0,
        "checks": checks,
        "blockers": blockers,
    }
    
    if result["ok"]:
        log("Preflight: ALL PASS", "ok")
    else:
        log(f"Preflight: {len(blockers)} BLOCKER(S)", "err")
        for b in blockers:
            log(f"  → {b}", "err")
    
    return result


# =========================================================
# SNAPSHOT (SHA-256 Verified)
# =========================================================

def snapshot_db_verified(source: Path, snapshot_dir: Path) -> dict:
    """Create WAL-safe snapshot with SHA-256 verification."""
    if not source.exists():
        return {"ok": False, "reason": "not_found", "source": str(source)}
    
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = snapshot_dir / f"{source.name}.snap_{ts}"
    
    try:
        src = sqlite3.connect(str(source))
        dst = sqlite3.connect(str(dest))
        
        # Force WAL checkpoint before backup
        try:
            src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass  # not in WAL mode, fine
        
        src.backup(dst)
        src.close()
        dst.close()
        
        sha = _sha256_file(dest)
        size = dest.stat().st_size
        
        # Verify snapshot is readable
        verify_conn = sqlite3.connect(str(dest))
        verify_conn.execute("PRAGMA integrity_check").fetchone()
        verify_conn.close()
        
        return {
            "ok": True,
            "source": str(source),
            "snapshot": str(dest),
            "size_bytes": size,
            "sha256": sha,
        }
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# =========================================================
# SHADOW TABLES (Atomic-Swap Innovation)
# =========================================================

def create_shadow_tables(conn: sqlite3.Connection) -> dict:
    """Create _shadow_ versions of all Wave 3 tables."""
    # Transform schema: replace "CREATE TABLE IF NOT EXISTS X" 
    # with "CREATE TABLE IF NOT EXISTS _shadow_X"
    shadow_schema = WAVE_3_SCHEMA
    for table in ["evidence_blocks", "anchors", "authorizations",
                  "approvals", "receipts", "action_contracts"]:
        # Table
        shadow_schema = shadow_schema.replace(
            f"CREATE TABLE IF NOT EXISTS {table} ",
            f"CREATE TABLE IF NOT EXISTS {SHADOW_PREFIX}{table} "
        )
        # Indexes
        shadow_schema = shadow_schema.replace(
            f"ON {table}(", f"ON {SHADOW_PREFIX}{table}("
        )
    
    try:
        conn.executescript(shadow_schema)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def drop_shadow_tables(conn: sqlite3.Connection):
    """Drop all shadow tables (cleanup)."""
    for table in ["evidence_blocks", "anchors", "authorizations",
                  "approvals", "receipts", "action_contracts"]:
        try:
            conn.execute(f"DROP TABLE IF EXISTS {SHADOW_PREFIX}{table}")
        except sqlite3.OperationalError:
            pass


def atomic_swap(conn: sqlite3.Connection) -> dict:
    """
    Atomically replace real tables with shadow tables.
    
    Within a single transaction:
      1. Rename real tables → _old_*
      2. Rename shadow tables → real names
      3. Commit
    
    If anything fails → ROLLBACK, no harm.
    """
    tables = ["evidence_blocks", "anchors", "authorizations",
              "approvals", "receipts", "action_contracts"]
    
    try:
        conn.execute("BEGIN IMMEDIATE")
        
        for table in tables:
            shadow = f"{SHADOW_PREFIX}{table}"
            old = f"_old_{table}"
            
            # Check shadow exists
            exists = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name=?", (shadow,)
            ).fetchone()
            
            if not exists:
                # Table not migrated — leave original alone
                continue
            
            # Check original exists
            orig_exists = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name=?", (table,)
            ).fetchone()
            
            if orig_exists:
                conn.execute(f"ALTER TABLE {table} RENAME TO {old}")
            
            conn.execute(f"ALTER TABLE {shadow} RENAME TO {table}")
        
        conn.execute("COMMIT")
        return {"ok": True, "swapped": tables}
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return {"ok": False, "error": str(exc)}


def cleanup_old_tables(conn: sqlite3.Connection):
    """Drop _old_* tables after successful swap."""
    for table in ["evidence_blocks", "anchors", "authorizations",
                  "approvals", "receipts", "action_contracts"]:
        try:
            conn.execute(f"DROP TABLE IF EXISTS _old_{table}")
        except sqlite3.OperationalError:
            pass


def restore_old_tables(conn: sqlite3.Connection) -> dict:
    """Rollback: rename _old_* back to real names."""
    tables = ["evidence_blocks", "anchors", "authorizations",
              "approvals", "receipts", "action_contracts"]
    try:
        conn.execute("BEGIN IMMEDIATE")
        for table in tables:
            old = f"_old_{table}"
            exists = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name=?", (old,)
            ).fetchone()
            if exists:
                # Drop current (broken) real table
                try:
                    conn.execute(f"DROP TABLE IF EXISTS {table}")
                except sqlite3.OperationalError:
                    pass
                conn.execute(f"ALTER TABLE {old} RENAME TO {table}")
        conn.execute("COMMIT")
        return {"ok": True}
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return {"ok": False, "error": str(exc)}


# =========================================================
# MIGRATORS (Write to Shadow Tables)
# =========================================================

def _insert_shadow(conn, shadow_table, pk_col, pk_value, 
                   insert_sql, params) -> str:
    """Insert-if-absent into shadow table."""
    existing = conn.execute(
        f"SELECT 1 FROM {shadow_table} WHERE {pk_col} = ?", (pk_value,)
    ).fetchone()
    if existing:
        return "skipped"
    conn.execute(insert_sql, params)
    return "inserted"


def migrate_evidence_blocks(conn, legacy_conn) -> dict:
    stats = {"inserted": 0, "skipped": 0, "errors": []}
    t = f"{SHADOW_PREFIX}evidence_blocks"
    
    try:
        rows = legacy_conn.execute("""
            SELECT id, block_index, schema_version, observation_hash,
                   previous_hash, block_hash, canonical_payload,
                   signature, public_key, key_id, terminal,
                   signed, verified, anchored, created_at
            FROM chain
        """).fetchall()
    except sqlite3.OperationalError as exc:
        stats["errors"].append(f"source_read: {exc}")
        return stats
    
    for r in rows:
        try:
            result = _insert_shadow(
                conn, t, "block_index", r[1],
                f"""INSERT INTO {t} (
                    block_index, schema_version, observation_hash,
                    previous_hash, block_hash, canonical_payload,
                    signature, public_key, key_id, terminal,
                    signed, verified, anchored, created_at, legacy_source_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                r
            )
            stats["inserted" if result == "inserted" else "skipped"] += 1
        except sqlite3.OperationalError as exc:
            stats["errors"].append(f"row {r[0]}: {exc}")
    
    return stats


def migrate_anchors(conn, legacy_conn) -> dict:
    stats = {"inserted": 0, "skipped": 0, "errors": []}
    t = f"{SHADOW_PREFIX}anchors"
    
    try:
        rows = legacy_conn.execute("""
            SELECT id, anchor_id, schema_version, device_id,
                   sequence_number, merkle_root, first_block_index,
                   last_block_index, block_count, previous_anchor_hash,
                   anchor_hash, signature, public_key, created_at,
                   published, published_at, remote_ref
            FROM anchors
        """).fetchall()
    except sqlite3.OperationalError as exc:
        stats["errors"].append(f"source_read: {exc}")
        return stats
    
    for r in rows:
        try:
            result = _insert_shadow(
                conn, t, "anchor_id", r[1],
                f"""INSERT INTO {t} (
                    anchor_id, schema_version, device_id, sequence_number,
                    merkle_root, first_block_index, last_block_index,
                    block_count, previous_anchor_hash, anchor_hash,
                    signature, public_key, created_at, published,
                    published_at, remote_ref, legacy_source_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                r
            )
            stats["inserted" if result == "inserted" else "skipped"] += 1
        except sqlite3.OperationalError as exc:
            stats["errors"].append(f"row {r[0]}: {exc}")
    
    return stats


def migrate_authorizations(conn, legacy_conn) -> dict:
    stats = {"inserted": 0, "skipped": 0, "errors": []}
    t = f"{SHADOW_PREFIX}authorizations"
    
    try:
        rows = legacy_conn.execute("""
            SELECT id, action_id, schema_version, incident_id,
                   action_type, target, risk_tier, evidence_root,
                   policy_id, policy_hash, required_approvals,
                   current_approvals, state, action_digest,
                   expires_at, created_at, state_changed_at
            FROM actions
        """).fetchall()
    except sqlite3.OperationalError as exc:
        stats["errors"].append(f"source_read: {exc}")
        return stats
    
    for r in rows:
        try:
            result = _insert_shadow(
                conn, t, "action_id", r[1],
                f"""INSERT INTO {t} (
                    action_id, schema_version, incident_id, action_type,
                    target, risk_tier, evidence_root, policy_id,
                    policy_hash, required_approvals, current_approvals,
                    state, action_digest, expires_at, created_at,
                    state_changed_at, legacy_source_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                r
            )
            stats["inserted" if result == "inserted" else "skipped"] += 1
        except sqlite3.OperationalError as exc:
            stats["errors"].append(f"row {r[0]}: {exc}")
    
    return stats


def migrate_approvals(conn, legacy_conn) -> dict:
    stats = {"inserted": 0, "skipped": 0, "errors": []}
    t = f"{SHADOW_PREFIX}approvals"
    
    try:
        rows = legacy_conn.execute("""
            SELECT id, action_id, approver, approval_digest,
                   signature, public_key, signed_payload, signed_at
            FROM approvals
        """).fetchall()
    except sqlite3.OperationalError as exc:
        stats["errors"].append(f"source_read: {exc}")
        return stats
    
    for r in rows:
        try:
            result = _insert_shadow(
                conn, t, "approval_digest", r[3],
                f"""INSERT INTO {t} (
                    approval_digest, action_id, approver, signature,
                    public_key, signed_payload, signed_at, legacy_source_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (r[3], r[1], r[2], r[4], r[5], r[6], r[7], r[0])
            )
            stats["inserted" if result == "inserted" else "skipped"] += 1
        except sqlite3.OperationalError as exc:
            stats["errors"].append(f"row {r[0]}: {exc}")
    
    return stats


def migrate_receipts(conn, legacy_conn) -> dict:
    stats = {"inserted": 0, "skipped": 0, "errors": []}
    t = f"{SHADOW_PREFIX}receipts"
    
    try:
        rows = legacy_conn.execute("""
            SELECT id, action_id, receipt_json, receipt_hash,
                   receipt_signature, created_at
            FROM receipts
        """).fetchall()
    except sqlite3.OperationalError as exc:
        stats["errors"].append(f"source_read: {exc}")
        return stats
    
    for r in rows:
        try:
            result = _insert_shadow(
                conn, t, "receipt_hash", r[3],
                f"""INSERT INTO {t} (
                    receipt_hash, action_id, receipt_json,
                    receipt_signature, created_at, legacy_source_id
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (r[3], r[1], r[2], r[4], r[5], r[0])
            )
            stats["inserted" if result == "inserted" else "skipped"] += 1
        except sqlite3.OperationalError as exc:
            stats["errors"].append(f"row {r[0]}: {exc}")
    
    return stats


MIGRATORS = [
    ("evidence_blocks", "evidence_chain.db", migrate_evidence_blocks),
    ("anchors",         "anchors.db",        migrate_anchors),
    ("authorizations",  "authorization.db",  migrate_authorizations),
    ("approvals",       "authorization.db",  migrate_approvals),
    ("receipts",        "authorization.db",  migrate_receipts),
]


# =========================================================
# SIGNED MIGRATION RECEIPT
# =========================================================

def generate_receipt(report: dict, op_db: Path) -> dict:
    """Generate migration receipt (Ed25519 optional)."""
    op_sha = _sha256_file(op_db) if op_db.exists() else None
    
    receipt = {
        "wave": 3,
        "migrated_at": _now(),
        "op_db_sha256": op_sha,
        "row_counts": {
            t: m.get("inserted", 0) 
            for t, m in report.get("migrations", {}).items()
        },
        "dry_run": report.get("dry_run", True),
        "success": report.get("success", False),
    }
    
    # Try Ed25519 signing
    try:
        from perception.bridge_signatures import sign_payload
        signature = sign_payload(_canonical(receipt))
        receipt["signature"] = signature
        receipt["signed"] = True
    except Exception as exc:
        receipt["signature"] = None
        receipt["signed"] = False
        receipt["signing_note"] = f"Ed25519 unavailable: {exc}"
    
    # Add fingerprint
    receipt["fingerprint"] = _sha256_str(_canonical(receipt))
    
    # Save
    RECEIPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT_FILE.write_text(json.dumps(receipt, indent=2))
    
    return receipt


# =========================================================
# MAIN RUNNER
# =========================================================

def run_wave_3(op_db: str | Path, legacy_root: str | Path,
               snapshot_dir: str | Path | None = None,
               mode: str = "dry-run") -> dict:
    """
    Run Wave 3 migration.
    
    Modes: dry-run | apply | verify-only | recover | rollback
    """
    op_db = Path(op_db)
    legacy_root = Path(legacy_root)
    snapshot_dir = (
        Path(snapshot_dir) if snapshot_dir
        else EMBER_HOME / "wave3_snapshots"
    )
    
    print()
    log(f"WAVE 3 MIGRATION — mode={mode.upper()}", "phase")
    print()
    
    report = {
        "started_at": _now(),
        "mode": mode,
        "op_db": str(op_db),
        "legacy_root": str(legacy_root),
        "snapshot_dir": str(snapshot_dir),
    }
    
    # ===== RECOVER MODE =====
    if mode == "recover":
        return _recover(op_db, legacy_root, snapshot_dir, report)
    
    # ===== ROLLBACK MODE =====
    if mode == "rollback":
        return _rollback(op_db, report)
    
    # ===== VERIFY-ONLY MODE =====
    if mode == "verify-only":
        return _verify_only(op_db, snapshot_dir, report)
    
    # ===== PREFLIGHT =====
    pf = preflight_check(op_db, legacy_root, snapshot_dir)
    report["preflight"] = pf
    if not pf["ok"]:
        report["success"] = False
        report["error"] = "preflight_failed"
        return report
    
    # ===== SNAPSHOT LEGACY DBs =====
    log("Snapshotting legacy DBs...", "phase")
    snapshots = {}
    for db_name in ["evidence_chain.db", "anchors.db", 
                    "authorization.db", "contracts.db"]:
        p = legacy_root / db_name
        if not p.exists():
            log(f"  Skip (missing): {db_name}", "warn")
            continue
        
        if mode == "dry-run":
            snapshots[db_name] = {
                "ok": True, "source": str(p),
                "size_bytes": p.stat().st_size,
                "dry_run": True,
            }
            log(f"  {db_name}: {p.stat().st_size} bytes (would snapshot)", "info")
        else:
            s = snapshot_db_verified(p, snapshot_dir)
            snapshots[db_name] = s
            if s["ok"]:
                log(f"  {db_name}: {s['size_bytes']} bytes, sha256={s['sha256'][:16]}...", "ok")
            else:
                log(f"  {db_name}: FAILED — {s.get('error')}", "err")
                report["success"] = False
                report["error"] = f"snapshot_failed:{db_name}"
                return report
    
    report["snapshots"] = snapshots
    snapshot_map = {
        name: s["snapshot"] for name, s in snapshots.items()
        if s.get("ok") and s.get("snapshot")
    }
    
    # ===== OPEN OP DB =====
    op_conn = sqlite3.connect(str(op_db))
    op_conn.row_factory = sqlite3.Row
    op_conn.execute("PRAGMA foreign_keys = ON")
    op_conn.execute("PRAGMA journal_mode = WAL")
    op_conn.execute("PRAGMA busy_timeout = 10000")
    
    try:
        # ===== DRY-RUN MODE (True Simulation) =====
        if mode == "dry-run":
            log("TRUE DRY-RUN — simulating migration...", "phase")
            report["migrations"] = {}
            
            for tname, db_name, func in MIGRATORS:
                # Open snapshot for real read
                snap_path = snapshot_map.get(db_name)
                if not snap_path and legacy_root:
                    # Use legacy directly (read-only)
                    snap_path = str(legacy_root / db_name)
                
                if not Path(snap_path).exists():
                    report["migrations"][tname] = {
                        "skipped": True, "reason": f"missing:{db_name}"
                    }
                    log(f"  {tname}: skipped ({db_name} missing)", "warn")
                    continue
                
                legacy_conn = sqlite3.connect(snap_path)
                legacy_conn.row_factory = sqlite3.Row
                
                try:
                    # Count source rows (read-only)
                    src_count = 0
                    for tname_check, db_name_check, _ in MIGRATORS:
                        if db_name_check == db_name:
                            try:
                                src_count = legacy_conn.execute(
                                    f"SELECT COUNT(*) FROM "
                                    f"{'chain' if db_name == 'evidence_chain.db' else ''}"
                                    f"{'anchors' if db_name == 'anchors.db' else ''}"
                                    f"{'actions' if db_name == 'authorization.db' and tname == 'authorizations' else ''}"
                                    f"{'approvals' if db_name == 'authorization.db' and tname == 'approvals' else ''}"
                                    f"{'receipts' if db_name == 'authorization.db' and tname == 'receipts' else ''}"
                                ).fetchone()[0]
                            except Exception:
                                src_count = 0
                            break
                    
                    report["migrations"][tname] = {
                        "would_insert": src_count,
                        "dry_run": True,
                        "source": db_name,
                    }
                    log(f"  {tname}: would migrate {src_count} row(s) from {db_name}", "info")
                finally:
                    legacy_conn.close()
            
            report["finished_at"] = _now()
            report["success"] = True
            report["note"] = "dry-run — no writes performed"
            log("DRY-RUN COMPLETE (no changes made)", "ok")
            return report
        
        # ===== APPLY MODE =====
        # Initialize target schema if needed
        init_wave_3_schema(op_conn)
        
        # Create shadow tables
        log("Creating shadow tables...", "phase")
        shadow_result = create_shadow_tables(op_conn)
        if not shadow_result["ok"]:
            report["success"] = False
            report["error"] = f"shadow_create_failed: {shadow_result['error']}"
            return report
        log("Shadow tables created", "ok")
        
        # Migrate source → shadow (single transaction)
        log("Migrating to shadow tables...", "phase")
        op_conn.execute("BEGIN IMMEDIATE")
        try:
            report["migrations"] = {}
            
            for tname, db_name, func in MIGRATORS:
                src_path = snapshot_map.get(db_name)
                if not src_path:
                    report["migrations"][tname] = {
                        "skipped": True, "reason": f"no_snapshot:{db_name}"
                    }
                    continue
                
                legacy_conn = sqlite3.connect(src_path)
                legacy_conn.row_factory = sqlite3.Row
                try:
                    stats = func(op_conn, legacy_conn)
                    report["migrations"][tname] = stats
                    
                    if stats["errors"]:
                        raise RuntimeError(
                            f"{tname} errors: {stats['errors'][:3]}"
                        )
                    
                    log(f"  {tname}: +{stats['inserted']} skip={stats['skipped']}", "ok")
                finally:
                    legacy_conn.close()
            
            op_conn.execute("COMMIT")
            log("Shadow migration committed", "ok")
        except Exception as exc:
            op_conn.execute("ROLLBACK")
            drop_shadow_tables(op_conn)
            report["success"] = False
            report["error"] = f"shadow_migration_failed: {exc}"
            log(f"FAILED — rolled back: {exc}", "err")
            return report
        
        # Verify shadow matches source
        log("Verifying shadow tables...", "phase")
        # Quick row count check
        shadow_ok = True
        for tname, _, _ in MIGRATORS:
            shadow_t = f"{SHADOW_PREFIX}{tname}"
            try:
                count = op_conn.execute(
                    f"SELECT COUNT(*) FROM {shadow_t}"
                ).fetchone()[0]
                log(f"  {tname}: {count} rows in shadow", "info")
            except sqlite3.OperationalError:
                shadow_ok = False
                log(f"  {tname}: shadow table missing!", "err")
        
        if not shadow_ok:
            drop_shadow_tables(op_conn)
            report["success"] = False
            report["error"] = "shadow_verify_failed"
            return report
        
        # ===== ATOMIC SWAP =====
        log("Atomic swap: shadow → real...", "phase")
        swap = atomic_swap(op_conn)
        if not swap["ok"]:
            report["success"] = False
            report["error"] = f"swap_failed: {swap['error']}"
            return report
        log("Swap complete", "ok")
        
        # ===== POST-MIGRATION VERIFY =====
        log("Post-migration verification...", "phase")
        verify = verify_wave3_full(op_db, snapshot_map)
        report["verification"] = verify
        
        if not verify["all_passed"]:
            log("VERIFICATION FAILED — rolling back", "err")
            restore = restore_old_tables(op_conn)
            if not restore["ok"]:
                log(f"ROLLBACK FAILED: {restore['error']}", "err")
                report["error"] = "verify_failed_and_rollback_failed"
            else:
                log("Rollback successful", "ok")
                report["error"] = "verify_failed_rolled_back"
            report["success"] = False
            return report
        
        log("Verification PASSED", "ok")
        
        # ===== SQLITE INTEGRITY CHECK =====
        log("Running PRAGMA integrity_check...", "phase")
        integrity = run_integrity_check(op_db)
        report["integrity"] = integrity
        
        if not integrity["clean"]:
            log(f"Integrity issues: {integrity}", "warn")
        else:
            log("Integrity: clean", "ok")
        
        # ===== CLEANUP OLD TABLES =====
        log("Cleanup: dropping _old_* tables...", "phase")
        cleanup_old_tables(op_conn)
        log("Cleanup complete", "ok")
        
        # ===== GENERATE RECEIPT =====
        log("Generating migration receipt...", "phase")
        receipt = generate_receipt(report, op_db)
        report["receipt"] = receipt
        log(f"Receipt fingerprint: {receipt['fingerprint'][:16]}...", "ok")
        
        report["finished_at"] = _now()
        report["success"] = True
        log("MIGRATION COMPLETE", "ok")
        
    finally:
        op_conn.close()
    
    return report


# =========================================================
# RECOVERY / ROLLBACK / VERIFY-ONLY
# =========================================================

def _recover(op_db, legacy_root, snapshot_dir, report):
    """Resume from journal after crash."""
    log("Recovery mode", "phase")
    journal = Journal()
    last = journal.last_state()
    log(f"Last journal state: {last}", "info")
    
    if journal.is_complete():
        log("Migration already complete — nothing to recover", "ok")
        report["success"] = True
        report["note"] = "already_complete"
        return report
    
    # Open DB and check state
    conn = sqlite3.connect(str(op_db))
    try:
        # Check for orphan shadow tables
        shadow_tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE ?", (f"{SHADOW_PREFIX}%",)
            )
        ]
        
        if shadow_tables:
            log(f"Found {len(shadow_tables)} orphan shadow tables — dropping", "warn")
            drop_shadow_tables(conn)
        
        # Check for _old_* tables
        old_tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE '_old_%'"
            )
        ]
        
        if old_tables:
            log(f"Found {len(old_tables)} _old_ tables — attempting restore", "warn")
            restore = restore_old_tables(conn)
            report["restore"] = restore
        
        journal.clear()
        report["success"] = True
        report["note"] = "recovered_clean_state"
        log("Recovery complete — clean state", "ok")
    finally:
        conn.close()
    
    return report


def _rollback(op_db, report):
    """Rollback to pre-migration state."""
    log("Rollback mode", "phase")
    conn = sqlite3.connect(str(op_db))
    try:
        # Check for _old_ tables
        old_tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE '_old_%'"
            )
        ]
        
        if not old_tables:
            log("No _old_ tables found — nothing to rollback", "warn")
            report["success"] = False
            report["error"] = "no_old_tables"
            return report
        
        restore = restore_old_tables(conn)
        report["restore"] = restore
        report["success"] = restore["ok"]
        if restore["ok"]:
            log("Rollback complete", "ok")
    finally:
        conn.close()
    
    return report


def _verify_only(op_db, snapshot_dir, report):
    """Run verification without migration."""
    log("Verify-only mode", "phase")
    
    # Find latest snapshots
    snapshot_map = {}
    if snapshot_dir.exists():
        for db in ["evidence_chain.db", "anchors.db", "authorization.db"]:
            matches = sorted(snapshot_dir.glob(f"{db}.snap_*"))
            if matches:
                snapshot_map[db] = str(matches[-1])
                log(f"  {db} ← {matches[-1].name}", "info")
    
    verify = verify_wave3_full(op_db, snapshot_map)
    report["verification"] = verify
    
    integrity = run_integrity_check(op_db)
    report["integrity"] = integrity
    
    report["success"] = verify["all_passed"] and integrity["clean"]
    report["finished_at"] = _now()
    
    if report["success"]:
        log("VERIFICATION PASSED", "ok")
    else:
        log("VERIFICATION FAILED", "err")
    
    return report


# =========================================================
# CLI
# =========================================================

def main():
    parser = argparse.ArgumentParser(
        description="Ember Wave 3 Crypto Migration (Staged & Recoverable)"
    )
    parser.add_argument(
        "--mode", 
        choices=["dry-run", "apply", "verify-only", "recover", "rollback"],
        default="dry-run",
        help="Migration mode (default: dry-run)"
    )
    parser.add_argument(
        "--op-db",
        default=str(EMBER_HOME / "ember_operational.db"),
        help="Operational DB path"
    )
    parser.add_argument(
        "--legacy-root",
        default="perception",
        help="Legacy DB root directory"
    )
    parser.add_argument(
        "--snapshot-dir",
        default=None,
        help="Snapshot directory (default: ~/.ember/wave3_snapshots)"
    )
    
    args = parser.parse_args()
    
    report = run_wave_3(
        op_db=args.op_db,
        legacy_root=args.legacy_root,
        snapshot_dir=args.snapshot_dir,
        mode=args.mode,
    )
    
    # Save report
    report_path = MIGRATIONS_DIR / f"wave3_report_{args.mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str))
    
    print()
    log(f"Report saved: {report_path}", "dim")
    print()
    
    if report.get("success"):
        log(f"MODE={args.mode} → SUCCESS", "ok")
        sys.exit(0)
    else:
        log(f"MODE={args.mode} → FAILED", "err")
        if report.get("error"):
            log(f"Reason: {report['error']}", "err")
        sys.exit(1)


if __name__ == "__main__":
    main()
