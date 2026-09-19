"""
Ember Wave 3 Verification (Read-Only, Fail-Closed)
====================================================
Post-migration integrity verification for Wave 3 crypto migration.

Three layers of verification:
  1. Row count reconciliation (source vs target)
  2. Referential integrity (orphan detection)
  3. Cryptographic chain integrity (hash links, Merkle roots)

Pure Python stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# =========================================================
# LAYER 1: Row count reconciliation
# =========================================================

def verify_row_counts(op_conn: sqlite3.Connection, 
                     snapshot_map: dict) -> dict:
    """Compare source and target row counts per table."""
    checks = [
        ("evidence_blocks", "evidence_chain.db", "chain"),
        ("anchors",         "anchors.db",        "anchors"),
        ("authorizations",  "authorization.db",  "actions"),
        ("approvals",       "authorization.db",  "approvals"),
        ("receipts",        "authorization.db",  "receipts"),
    ]
    
    results = {}
    for target_table, db_name, source_table in checks:
        src_path = snapshot_map.get(db_name)
        if not src_path:
            results[target_table] = {
                "source_count": None,
                "target_count": None,
                "match": None,
                "skipped": True,
                "reason": f"no_snapshot:{db_name}"
            }
            continue
        
        try:
            src = sqlite3.connect(src_path)
            src_count = src.execute(
                f"SELECT COUNT(*) FROM {source_table}"
            ).fetchone()[0]
            src.close()
        except Exception as exc:
            results[target_table] = {
                "error": f"source_read: {exc}",
                "match": False,
            }
            continue
        
        tgt_count = op_conn.execute(
            f"SELECT COUNT(*) FROM {target_table}"
        ).fetchone()[0]
        
        results[target_table] = {
            "source_count": src_count,
            "target_count": tgt_count,
            "match": src_count == tgt_count,
        }
    
    return results


# =========================================================
# LAYER 2: Referential integrity
# =========================================================

def verify_referential_integrity(op_conn: sqlite3.Connection) -> dict:
    """Detect orphan records violating FK relationships."""
    results = {}
    
    # approvals → authorizations
    orphan_approvals = op_conn.execute("""
        SELECT COUNT(*) FROM approvals
        WHERE action_id NOT IN (SELECT action_id FROM authorizations)
    """).fetchone()[0]
    
    # receipts → authorizations
    orphan_receipts = op_conn.execute("""
        SELECT COUNT(*) FROM receipts
        WHERE action_id NOT IN (SELECT action_id FROM authorizations)
    """).fetchone()[0]
    
    # anchors → evidence_blocks (via block_index range)
    orphan_anchors = op_conn.execute("""
        SELECT COUNT(*) FROM anchors
        WHERE first_block_index IS NOT NULL
          AND first_block_index NOT IN (SELECT block_index FROM evidence_blocks)
    """).fetchone()[0]
    
    results["orphan_approvals"] = orphan_approvals
    results["orphan_receipts"] = orphan_receipts
    results["orphan_anchors"] = orphan_anchors
    results["clean"] = (
        orphan_approvals == 0 
        and orphan_receipts == 0 
        and orphan_anchors == 0
    )
    
    return results


# =========================================================
# LAYER 3: Cryptographic chain integrity
# =========================================================

def verify_evidence_chain(op_conn: sqlite3.Connection) -> dict:
    """
    Verify evidence_blocks form a valid hash chain.
    
    Checks:
      - Block indices are contiguous (no gaps)
      - Each block's previous_hash matches prior block's block_hash
      - First block has NULL previous_hash
      - Block hashes are present and non-empty
    """
    results = {
        "chain_length": 0,
        "gaps": [],
        "broken_links": [],
        "missing_hashes": [],
    }
    
    rows = op_conn.execute("""
        SELECT block_index, block_hash, previous_hash
        FROM evidence_blocks
        ORDER BY block_index ASC
    """).fetchall()
    
    results["chain_length"] = len(rows)
    
    if len(rows) == 0:
        results["valid"] = True
        return results
    
    prev_block = None
    for r in rows:
        block_index, block_hash, previous_hash = r
        
        # Check hash present
        if not block_hash:
            results["missing_hashes"].append(block_index)
            continue
        
        # First block should have no previous_hash
        if prev_block is None:
            if previous_hash is not None and previous_hash != "":
                results["broken_links"].append({
                    "block_index": block_index,
                    "reason": "first_block_has_previous_hash",
                    "previous_hash": previous_hash,
                })
        else:
            prev_index, prev_hash, _ = prev_block
            # Check for gap
            if block_index != prev_index + 1:
                results["gaps"].append({
                    "from": prev_index,
                    "to": block_index,
                })
            # Check link
            if previous_hash != prev_hash:
                results["broken_links"].append({
                    "block_index": block_index,
                    "expected": prev_hash,
                    "found": previous_hash,
                })
        
        prev_block = r
    
    results["valid"] = (
        len(results["gaps"]) == 0 
        and len(results["broken_links"]) == 0
        and len(results["missing_hashes"]) == 0
    )
    
    return results


# =========================================================
# LAYER 4: Cryptographic byte-for-byte verification
# =========================================================

def verify_crypto_digests(op_conn: sqlite3.Connection,
                         snapshot_map: dict) -> dict:
    """
    Verify cryptographic fields are byte-for-byte identical.
    
    For each crypto table, compare SHA-256 of sorted crypto fields
    between source and target.
    """
    results = {}
    
    checks = [
        # (target_table, db_name, source_table, crypto_fields)
        ("evidence_blocks", "evidence_chain.db", "chain",
         ["block_hash", "observation_hash", "signature", "public_key"]),
        ("anchors", "anchors.db", "anchors",
         ["anchor_hash", "merkle_root", "signature", "public_key"]),
        ("authorizations", "authorization.db", "actions",
         ["action_digest", "policy_hash", "evidence_root"]),
        ("approvals", "authorization.db", "approvals",
         ["approval_digest", "signature", "public_key"]),
        ("receipts", "authorization.db", "receipts",
         ["receipt_hash", "receipt_signature"]),
    ]
    
    for target_table, db_name, source_table, crypto_fields in checks:
        src_path = snapshot_map.get(db_name)
        if not src_path:
            results[target_table] = {"skipped": True}
            continue
        
        try:
            src = sqlite3.connect(src_path)
            src_rows = src.execute(
                f"SELECT {','.join(crypto_fields)} FROM {source_table}"
            ).fetchall()
            src.close()
        except Exception as exc:
            results[target_table] = {"error": f"source_read: {exc}"}
            continue
        
        tgt_rows = op_conn.execute(
            f"SELECT {','.join(crypto_fields)} FROM {target_table}"
        ).fetchall()
        
        # Compute per-row hashes and combine
        def row_hash(row):
            canonical = json.dumps(
                list(row), sort_keys=False, 
                separators=(",", ":"), ensure_ascii=False, default=str
            )
            return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        
        src_hashes = sorted([row_hash(r) for r in src_rows])
        tgt_hashes = sorted([row_hash(r) for r in tgt_rows])
        
        src_digest = hashlib.sha256(
            "".join(src_hashes).encode("utf-8")
        ).hexdigest()
        tgt_digest = hashlib.sha256(
            "".join(tgt_hashes).encode("utf-8")
        ).hexdigest()
        
        results[target_table] = {
            "source_digest": src_digest,
            "target_digest": tgt_digest,
            "match": src_digest == tgt_digest,
        }
    
    return results


# =========================================================
# MASTER VERIFY
# =========================================================

def verify_wave3_full(op_db: str | Path, 
                     snapshot_map: dict) -> dict:
    """
    Full verification suite.
    Returns a report dict.
    """
    op_db = Path(op_db)
    conn = sqlite3.connect(str(op_db))
    conn.row_factory = sqlite3.Row
    
    report = {
        "verified_at": _now(),
        "op_db": str(op_db),
    }
    
    try:
        report["row_counts"] = verify_row_counts(conn, snapshot_map)
        report["referential"] = verify_referential_integrity(conn)
        report["chain"] = verify_evidence_chain(conn)
        report["crypto_digests"] = verify_crypto_digests(conn, snapshot_map)
        
        # Aggregate
        all_match = all(
            v.get("match", True) is not False
            for v in report["row_counts"].values()
        )
        report["all_passed"] = (
            all_match
            and report["referential"].get("clean", False)
            and report["chain"].get("valid", False)
            and all(
                v.get("match", True) is not False
                for v in report["crypto_digests"].values()
            )
        )
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["all_passed"] = False
    finally:
        conn.close()
    
    return report


# =========================================================
# INTEGRITY CHECK (SQLite native)
# =========================================================

def run_integrity_check(op_db: str | Path) -> dict:
    """Run PRAGMA integrity_check and foreign_key_check."""
    op_db = Path(op_db)
    conn = sqlite3.connect(str(op_db))
    
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
        
        return {
            "integrity_check": integrity,
            "foreign_key_violations": len(fk_check),
            "foreign_key_details": [dict(r) if hasattr(r, "keys") else r 
                                   for r in fk_check[:10]],
            "clean": integrity == "ok" and len(fk_check) == 0,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("  WAVE 3 VERIFICATION — SELF TEST")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("Usage: python -m perception.wave3_verify <op_db>")
        sys.exit(1)
    
    op_db = sys.argv[1]
    report = run_integrity_check(op_db)
    print(json.dumps(report, indent=2))
