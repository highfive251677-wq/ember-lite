"""
Ember Wave 3 Crypto Migration (Fixed & Safe)
==============================================
Fixes applied:
1. Explicit tuple unpacking to prevent SELECT/INSERT column shift.
2. Removed isolation_level=None to enable proper transactions.
3. Added BEGIN IMMEDIATE / ROLLBACK boundaries.
4. Added post-migration PRAGMA integrity_check.
5. Added argparse CLI (--apply required for production writes).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(v) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


# =========================================================
# SNAPSHOT (SQLite Backup API — WAL-safe)
# =========================================================

def snapshot_db(source_path: Path, snapshot_dir: Path) -> dict:
    if not source_path.exists():
        return {"snapshotted": False, "reason": "not_found", "source": str(source_path)}

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = snapshot_dir / f"{source_path.name}.snapshot_{timestamp}"

    try:
        src = sqlite3.connect(str(source_path))
        dst = sqlite3.connect(str(dest))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()

        with open(dest, "rb") as f:
            data = f.read()
        sha = hashlib.sha256(data).hexdigest()

        return {"snapshotted": True, "source": str(source_path), "snapshot": str(dest), "size_bytes": len(data), "sha256": sha}
    except Exception as exc:
        return {"snapshotted": False, "error": f"{type(exc).__name__}: {exc}"}


# =========================================================
# CONFLICT LOG
# =========================================================

def _log_conflict(conn, wave, source_table, source_pk, conflict_type, details):
    try:
        conn.execute("""
            INSERT INTO migration_conflicts
            (migration_wave, source_table, source_pk, conflict_type, details_json, detected_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (wave, source_table, source_pk, conflict_type, _canonical(details), _now()))
    except sqlite3.OperationalError:
        pass


# =========================================================
# COPY HELPER
# =========================================================

def _insert_if_absent(conn, table, pk_col, pk_value, insert_sql, params):
    existing = conn.execute(f"SELECT 1 FROM {table} WHERE {pk_col} = ?", (pk_value,)).fetchone()
    if existing:
        return "skipped"
    conn.execute(insert_sql, params)
    return "inserted"


# =========================================================
# MIGRATORS (FIXED: Explicit Unpacking)
# =========================================================

def migrate_evidence_blocks(op_conn, legacy_conn) -> dict:
    stats = {"inserted": 0, "skipped": 0, "conflicts": 0, "errors": []}
    try:
        rows = legacy_conn.execute("SELECT id, block_index, schema_version, observation_hash, previous_hash, block_hash, canonical_payload, signature, public_key, key_id, terminal, signed, verified, anchored, created_at FROM chain").fetchall()
    except sqlite3.OperationalError as exc:
        stats["errors"].append(f"source_read: {exc}")
        return stats

    for r in rows:
        (legacy_id, block_index, schema_version, observation_hash, previous_hash, block_hash, canonical_payload, signature, public_key, key_id, terminal, signed, verified, anchored, created_at) = r
        params = (block_index, schema_version, observation_hash, previous_hash, block_hash, canonical_payload, signature, public_key, key_id, terminal, signed, verified, anchored, created_at, legacy_id)
        try:
            res = _insert_if_absent(op_conn, "evidence_blocks", "block_index", block_index, "INSERT INTO evidence_blocks (block_index, schema_version, observation_hash, previous_hash, block_hash, canonical_payload, signature, public_key, key_id, terminal, signed, verified, anchored, created_at, legacy_source_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", params)
            stats["inserted" if res == "inserted" else "skipped"] += 1
        except sqlite3.OperationalError as exc:
            stats["conflicts"] += 1
            _log_conflict(op_conn, 3, "chain", str(legacy_id), "insert_error", {"error": str(exc)})
    return stats


def migrate_anchors(op_conn, legacy_conn) -> dict:
    stats = {"inserted": 0, "skipped": 0, "conflicts": 0, "errors": []}
    try:
        rows = legacy_conn.execute("SELECT id, anchor_id, schema_version, device_id, sequence_number, merkle_root, first_block_index, last_block_index, block_count, previous_anchor_hash, anchor_hash, signature, public_key, created_at, published, published_at, remote_ref FROM anchors").fetchall()
    except sqlite3.OperationalError as exc:
        stats["errors"].append(f"source_read: {exc}")
        return stats

    for r in rows:
        (legacy_id, anchor_id, schema_version, device_id, sequence_number, merkle_root, first_block_index, last_block_index, block_count, previous_anchor_hash, anchor_hash, signature, public_key, created_at, published, published_at, remote_ref) = r
        params = (anchor_id, schema_version, device_id, sequence_number, merkle_root, first_block_index, last_block_index, block_count, previous_anchor_hash, anchor_hash, signature, public_key, created_at, published, published_at, remote_ref, legacy_id)
        try:
            res = _insert_if_absent(op_conn, "anchors", "anchor_id", anchor_id, "INSERT INTO anchors (anchor_id, schema_version, device_id, sequence_number, merkle_root, first_block_index, last_block_index, block_count, previous_anchor_hash, anchor_hash, signature, public_key, created_at, published, published_at, remote_ref, legacy_source_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", params)
            stats["inserted" if res == "inserted" else "skipped"] += 1
        except sqlite3.OperationalError as exc:
            stats["conflicts"] += 1
            _log_conflict(op_conn, 3, "anchors", str(legacy_id), "insert_error", {"error": str(exc)})
    return stats


def migrate_authorizations(op_conn, legacy_conn) -> dict:
    stats = {"inserted": 0, "skipped": 0, "conflicts": 0, "errors": []}
    try:
        rows = legacy_conn.execute("SELECT id, action_id, schema_version, incident_id, action_type, target, risk_tier, evidence_root, policy_id, policy_hash, required_approvals, current_approvals, state, action_digest, expires_at, created_at, state_changed_at FROM actions").fetchall()
    except sqlite3.OperationalError as exc:
        stats["errors"].append(f"source_read: {exc}")
        return stats

    for r in rows:
        (legacy_id, action_id, schema_version, incident_id, action_type, target, risk_tier, evidence_root, policy_id, policy_hash, required_approvals, current_approvals, state, action_digest, expires_at, created_at, state_changed_at) = r
        params = (action_id, schema_version, incident_id, action_type, target, risk_tier, evidence_root, policy_id, policy_hash, required_approvals, current_approvals, state, action_digest, expires_at, created_at, state_changed_at, legacy_id)
        try:
            res = _insert_if_absent(op_conn, "authorizations", "action_id", action_id, "INSERT INTO authorizations (action_id, schema_version, incident_id, action_type, target, risk_tier, evidence_root, policy_id, policy_hash, required_approvals, current_approvals, state, action_digest, expires_at, created_at, state_changed_at, legacy_source_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", params)
            stats["inserted" if res == "inserted" else "skipped"] += 1
        except sqlite3.OperationalError as exc:
            stats["conflicts"] += 1
            _log_conflict(op_conn, 3, "actions", str(legacy_id), "insert_error", {"error": str(exc)})
    return stats


def migrate_approvals(op_conn, legacy_conn) -> dict:
    stats = {"inserted": 0, "skipped": 0, "conflicts": 0, "errors": []}
    try:
        rows = legacy_conn.execute("SELECT id, action_id, approver, approval_digest, signature, public_key, signed_payload, signed_at FROM approvals").fetchall()
    except sqlite3.OperationalError as exc:
        stats["errors"].append(f"source_read: {exc}")
        return stats

    for r in rows:
        (legacy_id, action_id, approver, approval_digest, signature, public_key, signed_payload, signed_at) = r
        params = (approval_digest, action_id, approver, signature, public_key, signed_payload, signed_at, legacy_id)
        try:
            res = _insert_if_absent(op_conn, "approvals", "approval_digest", approval_digest, "INSERT INTO approvals (approval_digest, action_id, approver, signature, public_key, signed_payload, signed_at, legacy_source_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", params)
            stats["inserted" if res == "inserted" else "skipped"] += 1
        except sqlite3.OperationalError as exc:
            stats["conflicts"] += 1
            _log_conflict(op_conn, 3, "approvals", str(legacy_id), "insert_error", {"error": str(exc)})
    return stats


def migrate_receipts(op_conn, legacy_conn) -> dict:
    stats = {"inserted": 0, "skipped": 0, "conflicts": 0, "errors": []}
    try:
        rows = legacy_conn.execute("SELECT id, action_id, receipt_json, receipt_hash, receipt_signature, created_at FROM receipts").fetchall()
    except sqlite3.OperationalError as exc:
        stats["errors"].append(f"source_read: {exc}")
        return stats

    for r in rows:
        (legacy_id, action_id, receipt_json, receipt_hash, receipt_signature, created_at) = r
        params = (receipt_hash, action_id, receipt_json, receipt_signature, created_at, legacy_id)
        try:
            res = _insert_if_absent(op_conn, "receipts", "receipt_hash", receipt_hash, "INSERT INTO receipts (receipt_hash, action_id, receipt_json, receipt_signature, created_at, legacy_source_id) VALUES (?, ?, ?, ?, ?, ?)", params)
            stats["inserted" if res == "inserted" else "skipped"] += 1
        except sqlite3.OperationalError as exc:
            stats["conflicts"] += 1
            _log_conflict(op_conn, 3, "receipts", str(legacy_id), "insert_error", {"error": str(exc)})
    return stats


# =========================================================
# MAIN RUNNER
# =========================================================

def run_wave_3(op_db, legacy_root, snapshot_dir=None, dry_run=True):
    from perception.wave3_schema import init_wave_3_schema

    op_db = Path(op_db)
    legacy_root = Path(legacy_root)
    snapshot_dir = Path(snapshot_dir) if snapshot_dir else legacy_root.parent / "wave3_snapshots"

    report = {"started_at": _now(), "dry_run": dry_run, "op_db": str(op_db), "legacy_root": str(legacy_root), "snapshots": [], "migrations": {}, "skipped_dbs": []}

    if not op_db.exists():
        report["error"] = "operational_db_not_found"
        return report

    for db_name in ["evidence_chain.db", "anchors.db", "authorization.db", "contracts.db"]:
        p = legacy_root / db_name
        if not p.exists():
            report["skipped_dbs"].append(db_name)
            continue
        if dry_run:
            report["snapshots"].append({"name": db_name, "would_snapshot": True, "size_bytes": p.stat().st_size})
        else:
            s = snapshot_db(p, snapshot_dir)
            s["name"] = db_name
            report["snapshots"].append(s)

    if dry_run:
        for tname in ["evidence_blocks", "anchors", "authorizations", "approvals", "receipts"]:
            report["migrations"][tname] = {"dry_run": True}
        report["finished_at"] = _now()
        report["success"] = True
        return report

    op_conn = sqlite3.connect(str(op_db))
    op_conn.execute("PRAGMA foreign_keys = ON")
    op_conn.execute("PRAGMA journal_mode = WAL")
    op_conn.execute("PRAGMA busy_timeout = 5000")

    try:
        init_wave_3_schema(op_conn)
        snapshot_map = {s["name"]: s["snapshot"] for s in report["snapshots"] if s.get("snapshotted")}

        migrators = [
            ("evidence_blocks", "evidence_chain.db", migrate_evidence_blocks),
            ("anchors", "anchors.db", migrate_anchors),
            ("authorizations", "authorization.db", migrate_authorizations),
            ("approvals", "authorization.db", migrate_approvals),
            ("receipts", "authorization.db", migrate_receipts),
        ]

        op_conn.execute("BEGIN IMMEDIATE")
        try:
            for tname, db_name, func in migrators:
                src_path = snapshot_map.get(db_name)
                if not src_path:
                    report["migrations"][tname] = {"skipped": True, "reason": f"no_snapshot:{db_name}"}
                    continue
                legacy_conn = sqlite3.connect(src_path)
                try:
                    stats = func(op_conn, legacy_conn)
                    report["migrations"][tname] = stats
                finally:
                    legacy_conn.close()
            op_conn.execute("COMMIT")
        except Exception as exc:
            op_conn.execute("ROLLBACK")
            report["error"] = f"migration_rolled_back: {exc}"
            report["success"] = False
            return report

        integrity = op_conn.execute("PRAGMA integrity_check").fetchone()[0]
        report["integrity_check"] = integrity
        report["success"] = (integrity == "ok") and all(m.get("conflicts", 0) == 0 and not m.get("errors") for m in report["migrations"].values() if isinstance(m, dict))

    finally:
        op_conn.close()

    report["finished_at"] = _now()
    return report


if __name__ == "__main__":
    from perception.storage import Storage

    parser = argparse.ArgumentParser(description="Wave 3 Crypto Migration")
    parser.add_argument("--apply", action="store_true", help="Execute actual migration (default is dry-run)")
    args = parser.parse_args()

    storage = Storage()
    op_db = storage.db_path
    legacy_root = Path("perception").resolve()

    print("=" * 60)
    print(f"  WAVE 3 MIGRATION — {'APPLY' if args.apply else 'DRY RUN'}")
    print("=" * 60)

    report = run_wave_3(op_db, legacy_root, dry_run=not args.apply)
    print(json.dumps(report, indent=2, default=str))
    print("\n🎉 COMPLETE" if report.get("success") else "\n❌ FAILED")
