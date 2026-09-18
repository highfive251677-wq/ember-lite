"""
Ember Evidence Chain v2 — Hardened Integrity
=============================================
Copilot Phase 2: Evidence Integrity

Core Change:
    Expose 4 separate assurance flags:
        recorded, signed, verified, anchored

Never claim "cryptographic integrity" unless each flag is true.

KPI #3 (Cryptographic Integrity):
    - Canonical serialization
    - Hash recomputation in verification
    - Signing failures NEVER swallowed
    - SQLite transactions for append
    - Schema version + key ID

Pure Python stdlib only. Backward-compatible with v1 callers.
"""

from __future__ import annotations

import sqlite3
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any


DB_PATH = os.path.join(os.path.dirname(__file__), "evidence_chain.db")

SCHEMA_VERSION = "2.0"


# =========================================================
# CANONICAL SERIALIZATION
# =========================================================

def _canonical_bytes(payload: Any) -> bytes:
    """
    Canonical serialization: sorted keys, no whitespace, UTF-8.
    Same input always produces same bytes.
    """
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    ).encode("utf-8")


def _hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =========================================================
# SCHEMA
# =========================================================

def init_chain_db() -> str:
    """Initialize or migrate the evidence chain database."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chain (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                block_index INTEGER UNIQUE NOT NULL,
                schema_version TEXT NOT NULL DEFAULT '1.0',
                observation_hash TEXT NOT NULL,
                previous_hash TEXT,
                block_hash TEXT UNIQUE NOT NULL,
                canonical_payload TEXT NOT NULL,
                signature TEXT,
                public_key TEXT,
                key_id TEXT,
                terminal TEXT,
                signed INTEGER DEFAULT 0,
                verified INTEGER DEFAULT 0,
                anchored INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()
    return DB_PATH


# =========================================================
# APPEND (with transaction)
# =========================================================

def _get_last_block(conn: sqlite3.Connection) -> dict:
    row = conn.execute("""
        SELECT block_index, block_hash
        FROM chain ORDER BY block_index DESC LIMIT 1
    """).fetchone()
    if not row:
        return {"index": 0, "hash": "0" * 64}
    return {"index": row[0], "hash": row[1]}


def add_observation(observation: dict, terminal: str = "cloud") -> dict:
    """
    Append an observation to the evidence chain.

    Returns a structured result with 4 separate flags:
        recorded, signed, verified, anchored
    """
    init_chain_db()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        conn.execute("BEGIN IMMEDIATE")

        last = _get_last_block(conn)
        next_index = last["index"] + 1

        # Canonical observation hash
        obs_hash = _hash(observation)

        # Canonical block payload — EVERYTHING that should be signed
        block_payload = {
            "index": next_index,
            "schema_version": SCHEMA_VERSION,
            "observation_hash": obs_hash,
            "previous_hash": last["hash"],
            "created_at": _now_iso(),
        }
        block_hash = _hash(block_payload)

        # Sign block payload (NEVER swallow exceptions silently)
        signature = None
        public_key = None
        key_id = None
        signed = False
        sign_error = None
        try:
            from perception.bridge_signatures import sign
            signed_result = sign(block_payload, terminal=terminal)
            signature = signed_result.get("signature")
            public_key = signed_result.get("public_key")
            key_id = signed_result.get("lib", "unknown")
            signed = bool(signature)
        except Exception as exc:
            sign_error = f"{type(exc).__name__}: {exc}"

        # Insert
        conn.execute("""
            INSERT INTO chain (
                block_index, schema_version, observation_hash,
                previous_hash, block_hash, canonical_payload,
                signature, public_key, key_id, terminal, signed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            next_index, SCHEMA_VERSION, obs_hash,
            last["hash"], block_hash,
            json.dumps(block_payload, sort_keys=True, separators=(",", ":")),
            signature, public_key, key_id, terminal, int(signed),
        ))

        conn.execute("COMMIT")

        result = {
            "block_index": next_index,
            "block_hash": block_hash,
            "previous_hash": last["hash"],
            "observation_hash": obs_hash,
            "schema_version": SCHEMA_VERSION,
            "recorded": True,
            "signed": signed,
            "verified": False,   # not yet re-verified
            "anchored": False,   # local-only
        }
        if sign_error:
            result["sign_error"] = sign_error
        return result

    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return {
            "recorded": False,
            "signed": False,
            "verified": False,
            "anchored": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        conn.close()


# =========================================================
# VERIFY (recompute hashes)
# =========================================================

def verify_chain() -> dict:
    """
    Verify chain integrity by recomputing every block hash.

    Does NOT trust stored block_hash values.
    """
    init_chain_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT block_index, schema_version, observation_hash,
                   previous_hash, block_hash, canonical_payload,
                   signature, public_key, signed
            FROM chain ORDER BY block_index ASC
        """).fetchall()
    finally:
        conn.close()

    if not rows:
        return {
            "valid": True, "blocks": 0, "broken_at": None,
            "verified": 0, "unverified": 0, "tip": "0" * 64,
        }

    previous_hash = "0" * 64
    verified = 0
    unverified = 0
    broken_at = None
    broken_reason = None

    for row in rows:
        idx = row["block_index"]

        # 1. Chain link
        if row["previous_hash"] != previous_hash:
            broken_at = idx
            broken_reason = f"broken_link_at_{idx}"
            break

        # 2. Recompute block hash from stored canonical payload
        try:
            payload = json.loads(row["canonical_payload"])
            recomputed = _hash(payload)
        except Exception as exc:
            broken_at = idx
            broken_reason = f"payload_unparseable_{exc}"
            break

        if recomputed != row["block_hash"]:
            broken_at = idx
            broken_reason = f"hash_mismatch_at_{idx}"
            break

        # 3. Verify signature (if present)
        if row["signed"] and row["signature"] and row["public_key"]:
            try:
                from perception.bridge_signatures import verify
                ok = verify(payload, row["signature"], row["public_key"])
                if ok:
                    verified += 1
                else:
                    unverified += 1
            except Exception:
                unverified += 1
        else:
            unverified += 1

        previous_hash = row["block_hash"]

    return {
        "valid": broken_at is None,
        "blocks": len(rows),
        "broken_at": broken_at,
        "broken_reason": broken_reason,
        "verified": verified,
        "unverified": unverified,
        "tip": previous_hash[:16],
    }


# =========================================================
# SUMMARY
# =========================================================

def get_chain_summary() -> dict:
    init_chain_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("""
            SELECT COUNT(*), MAX(block_index),
                   SUM(signed), SUM(verified)
            FROM chain
        """).fetchone()
    finally:
        conn.close()

    count = row[0] or 0
    latest = row[1] or 0
    signed = row[2] or 0
    verified = row[3] or 0

    tip = "0" * 16
    if count > 0:
        conn = sqlite3.connect(DB_PATH)
        try:
            r = conn.execute("""
                SELECT block_hash FROM chain
                ORDER BY block_index DESC LIMIT 1
            """).fetchone()
            if r:
                tip = r[0][:16]
        finally:
            conn.close()

    return {
        "blocks": count,
        "latest_index": latest,
        "signed": signed,
        "verified": verified,
        "anchored": 0,
        "tip_hash": tip,
        "schema_version": SCHEMA_VERSION,
    }


if __name__ == "__main__":
    init_chain_db()
    print("Schema:", SCHEMA_VERSION)
    r = add_observation({"test": "phase2", "value": 42}, terminal="T")
    print("Add:", r)
    v = verify_chain()
    print("Verify:", v)
    print("Summary:", get_chain_summary())
