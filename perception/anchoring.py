"""
Ember External Anchoring (Phase 6)
====================================
Copilot Phase 6: Blockchain-Compatible Evidence Anchoring

Design:
    Local anchor file — always written, no network required.
    Remote anchor commitment — optional, when connectivity allows.

Anchoring Commitment:
    - anchor_id
    - device_id
    - sequence_number
    - merkle_root (of N blocks)
    - block_range [first_index, last_index]
    - created_at
    - previous_anchor_hash (chain of anchors)

Does NOT require a blockchain node.
Pure Python stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from perception.merkle import hash_leaf, root_hash


ANCHOR_DB_PATH = os.path.join(os.path.dirname(__file__), "anchors.db")
ANCHOR_FILE_DIR = os.path.join(os.path.dirname(__file__), "anchors")

SCHEMA_VERSION = "1.0"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _hash(p: Any) -> str:
    return hashlib.sha256(
        json.dumps(p, sort_keys=True, separators=(",", ":"),
                   default=str).encode()
    ).hexdigest()


# =========================================================
# SCHEMA
# =========================================================

def init_anchor_db() -> str:
    conn = sqlite3.connect(ANCHOR_DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anchors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anchor_id TEXT UNIQUE NOT NULL,
                schema_version TEXT NOT NULL,
                device_id TEXT NOT NULL,
                sequence_number INTEGER NOT NULL,
                merkle_root TEXT NOT NULL,
                first_block_index INTEGER,
                last_block_index INTEGER,
                block_count INTEGER,
                previous_anchor_hash TEXT,
                anchor_hash TEXT UNIQUE NOT NULL,
                signature TEXT,
                public_key TEXT,
                created_at TEXT,
                published INTEGER DEFAULT 0,
                published_at TEXT,
                remote_ref TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_anchor_seq
            ON anchors(device_id, sequence_number)
        """)
        conn.commit()
    finally:
        conn.close()
    os.makedirs(ANCHOR_FILE_DIR, exist_ok=True)
    return ANCHOR_DB_PATH


# =========================================================
# BUILD ANCHOR
# =========================================================

def _last_anchor(conn: sqlite3.Connection, device_id: str) -> dict | None:
    row = conn.execute("""
        SELECT anchor_hash, sequence_number, last_block_index
        FROM anchors WHERE device_id = ?
        ORDER BY sequence_number DESC LIMIT 1
    """, (device_id,)).fetchone()
    if not row:
        return None
    return {
        "anchor_hash": row[0],
        "sequence_number": row[1],
        "last_block_index": row[2],
    }


def build_anchor(
    device_id: str,
    block_hashes: list[str],
    first_block_index: int,
    last_block_index: int,
    terminal: str = "T",
) -> dict:
    """
    Build a new anchor commitment from a batch of block hashes.

    block_hashes: canonical block_hash values from evidence_chain.
    """
    init_anchor_db()

    if not block_hashes:
        return {"created": False, "error": "no_blocks"}

    # Merkle root over the batch
    leaves = [hash_leaf(bh) for bh in block_hashes]
    merkle_root = root_hash(leaves)

    conn = sqlite3.connect(ANCHOR_DB_PATH)
    try:
        conn.execute("BEGIN IMMEDIATE")
        last = _last_anchor(conn, device_id)
        next_seq = (last["sequence_number"] + 1) if last else 1
        prev_hash = last["anchor_hash"] if last else None

        anchor_id = f"anc-{uuid.uuid4().hex[:12]}"

        canonical = {
            "anchor_id": anchor_id,
            "schema_version": SCHEMA_VERSION,
            "device_id": str(device_id),
            "sequence_number": int(next_seq),
            "merkle_root": str(merkle_root),
            "first_block_index": int(first_block_index),
            "last_block_index": int(last_block_index),
            "block_count": int(len(block_hashes)),
            "previous_anchor_hash": prev_hash,
            "created_at": _now_iso(),
        }
        anchor_hash = _hash(canonical)

        # Sign (do NOT swallow silently)
        signature = None
        public_key = None
        sign_error = None
        try:
            from perception.bridge_signatures import sign
            s = sign(canonical, terminal=terminal)
            signature = s.get("signature")
            public_key = s.get("public_key")
        except Exception as exc:
            sign_error = f"{type(exc).__name__}: {exc}"

        conn.execute("""
            INSERT INTO anchors (
                anchor_id, schema_version, device_id, sequence_number,
                merkle_root, first_block_index, last_block_index,
                block_count, previous_anchor_hash, anchor_hash,
                signature, public_key, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            canonical["anchor_id"], canonical["schema_version"],
            canonical["device_id"], canonical["sequence_number"],
            canonical["merkle_root"], canonical["first_block_index"],
            canonical["last_block_index"], canonical["block_count"],
            canonical["previous_anchor_hash"], anchor_hash,
            signature, public_key, canonical["created_at"],
        ))
        conn.execute("COMMIT")

        # Write local anchor file (offline-friendly)
        anchor_file = os.path.join(ANCHOR_FILE_DIR, f"{anchor_id}.json")
        with open(anchor_file, "w") as f:
            json.dump({**canonical, "anchor_hash": anchor_hash,
                       "signature": signature, "public_key": public_key},
                      f, indent=2, sort_keys=True)

        result = {
            "created": True,
            "anchor_id": anchor_id,
            "sequence_number": next_seq,
            "merkle_root": merkle_root,
            "anchor_hash": anchor_hash,
            "signed": signature is not None,
            "local_file": anchor_file,
            "block_count": len(block_hashes),
        }
        if sign_error:
            result["sign_error"] = sign_error
        return result
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return {"created": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()


# =========================================================
# ANCHOR THE EVIDENCE CHAIN (auto-batch)
# =========================================================

def anchor_chain(device_id: str, since_index: int = 0,
                 max_blocks: int = 100) -> dict:
    """
    Read evidence_chain.db and anchor a batch of blocks.
    """
    from perception.evidence_chain import DB_PATH as CHAIN_DB

    if not os.path.exists(CHAIN_DB):
        return {"created": False, "error": "no_chain_db"}

    conn = sqlite3.connect(CHAIN_DB)
    try:
        rows = conn.execute("""
            SELECT block_index, block_hash FROM chain
            WHERE block_index > ?
            ORDER BY block_index ASC LIMIT ?
        """, (since_index, max_blocks)).fetchall()
    finally:
        conn.close()

    if not rows:
        return {"created": False, "error": "no_new_blocks"}

    indices = [r[0] for r in rows]
    hashes = [r[1] for r in rows]

    return build_anchor(
        device_id=device_id,
        block_hashes=hashes,
        first_block_index=min(indices),
        last_block_index=max(indices),
    )


# =========================================================
# VERIFY ANCHOR
# =========================================================

def verify_anchor(anchor_id: str) -> dict:
    """Recompute the anchor hash and verify signature."""
    init_anchor_db()
    conn = sqlite3.connect(ANCHOR_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM anchors WHERE anchor_id = ?", (anchor_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return {"valid": False, "reason": "anchor_not_found"}

    canonical = {
        "anchor_id": row["anchor_id"],
        "schema_version": row["schema_version"],
        "device_id": row["device_id"],
        "sequence_number": row["sequence_number"],
        "merkle_root": row["merkle_root"],
        "first_block_index": row["first_block_index"],
        "last_block_index": row["last_block_index"],
        "block_count": row["block_count"],
        "previous_anchor_hash": row["previous_anchor_hash"],
        "created_at": row["created_at"],
    }
    recomputed = _hash(canonical)
    hash_ok = recomputed == row["anchor_hash"]

    sig_ok = False
    if row["signature"] and row["public_key"]:
        try:
            from perception.bridge_signatures import verify
            sig_ok = verify(canonical, row["signature"], row["public_key"])
        except Exception:
            sig_ok = False

    return {
        "valid": hash_ok and sig_ok,
        "hash_ok": hash_ok,
        "signature_ok": sig_ok,
        "anchor_id": anchor_id,
        "sequence_number": row["sequence_number"],
        "merkle_root": row["merkle_root"],
    }


def anchor_summary() -> dict:
    init_anchor_db()
    conn = sqlite3.connect(ANCHOR_DB_PATH)
    try:
        row = conn.execute("""
            SELECT COUNT(*), MAX(sequence_number),
                   SUM(published) FROM anchors
        """).fetchone()
    finally:
        conn.close()
    return {
        "total_anchors": row[0] or 0,
        "latest_sequence": row[1] or 0,
        "published_count": row[2] or 0,
    }


if __name__ == "__main__":
    import tempfile
    ANCHOR_DB_PATH = tempfile.mktemp(suffix=".db")
    ANCHOR_FILE_DIR = tempfile.mkdtemp()

    r = build_anchor(
        device_id="tab-a-2017",
        block_hashes=["a" * 64, "b" * 64, "c" * 64],
        first_block_index=1, last_block_index=3,
    )
    print("Anchor:", r.get("anchor_id"), "signed:", r.get("signed"))
    v = verify_anchor(r["anchor_id"])
    print("Verify:", v["valid"])
    print("Summary:", anchor_summary())
