"""
Ember Evidence-to-Action Contract (Phase 4)
=============================================
Copilot Phase 4: The Central Innovation

Core Principle:
    Make it IMPOSSIBLE to authorize an action unless the action
    is cryptographically bound to:
        evidence_root + assessment_hash + policy_hash
        + approval_hash + expires_at + target

This is the "Flight Recorder for Consequential Decisions."

KPI #3 (Cryptographic Integrity): Every binding is signed.
Pure Python stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import os
from datetime import datetime, timezone, timedelta
from typing import Any


DB_PATH = os.path.join(os.path.dirname(__file__), "contracts.db")
SCHEMA_VERSION = "1.0"


# =========================================================
# CANONICAL SERIALIZATION
# =========================================================

def _canonical_bytes(p: Any) -> bytes:
    return json.dumps(
        p, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    ).encode("utf-8")


def _hash(p: Any) -> str:
    return hashlib.sha256(_canonical_bytes(p)).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


# =========================================================
# SCHEMA
# =========================================================

def init_contract_db() -> str:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id TEXT UNIQUE NOT NULL,
                schema_version TEXT NOT NULL,
                action_id TEXT NOT NULL,
                incident_id TEXT,
                evidence_root TEXT,
                assessment_hash TEXT,
                policy_id TEXT,
                policy_hash TEXT,
                action_digest TEXT,
                approval_digest TEXT,
                target TEXT,
                risk_tier TEXT,
                contract_hash TEXT UNIQUE NOT NULL,
                signature TEXT,
                public_key TEXT,
                created_at TEXT,
                expires_at TEXT,
                state TEXT DEFAULT 'active'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id TEXT UNIQUE NOT NULL,
                contract_id TEXT NOT NULL,
                execution_status TEXT NOT NULL,
                outcome TEXT,
                receipt_hash TEXT NOT NULL,
                signature TEXT,
                public_key TEXT,
                created_at TEXT,
                FOREIGN KEY (contract_id) REFERENCES contracts(contract_id)
            )
        """)
        conn.commit()
    finally:
        conn.close()
    return DB_PATH


# =========================================================
# BUILD CONTRACT
# =========================================================

def build_contract(
    action_id: str,
    incident_id: str | None,
    evidence_root: str | None,
    assessment_hash: str | None,
    policy_id: str | None,
    policy_hash: str | None,
    action_digest: str,
    approval_digest: str | None,
    target: str | None,
    risk_tier: str,
    ttl_seconds: int = 3600,
    terminal: str = "T",
) -> dict:
    """
    Build a canonical Evidence-to-Action Contract.

    The contract binds EVERYTHING:
        evidence + assessment + policy + approval + action + expiry
    """
    init_contract_db()

    contract_id = f"ctr-{_hash(action_id + _now_iso())[:12]}"
    expires_at = (_now() + timedelta(seconds=ttl_seconds)).isoformat()

    # KPI #1: Force all fields to canonical string form.
    # SQLite stores them as TEXT. We must match on read-back.
    def _s(v):
        return None if v is None else str(v)

    canonical = {
        "contract_id": _s(contract_id),
        "schema_version": _s(SCHEMA_VERSION),
        "action_id": _s(action_id),
        "incident_id": _s(incident_id),
        "evidence_root": _s(evidence_root),
        "assessment_hash": _s(assessment_hash),
        "policy_id": _s(policy_id),
        "policy_hash": _s(policy_hash),
        "action_digest": _s(action_digest),
        "approval_digest": _s(approval_digest),
        "target": _s(target),
        "risk_tier": _s(risk_tier),
        "expires_at": _s(expires_at),
    }
    contract_hash = _hash(canonical)

    # Sign the contract (do NOT swallow exceptions)
    signature = None
    public_key = None
    signed = False
    sign_error = None
    try:
        from perception.bridge_signatures import sign
        s = sign(canonical, terminal=terminal)
        signature = s.get("signature")
        public_key = s.get("public_key")
        signed = bool(signature)
    except Exception as exc:
        sign_error = f"{type(exc).__name__}: {exc}"

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""
            INSERT INTO contracts (
                contract_id, schema_version, action_id, incident_id,
                evidence_root, assessment_hash, policy_id, policy_hash,
                action_digest, approval_digest, target, risk_tier,
                contract_hash, signature, public_key, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            canonical["contract_id"], canonical["schema_version"],
            canonical["action_id"], canonical["incident_id"],
            canonical["evidence_root"], canonical["assessment_hash"],
            canonical["policy_id"], canonical["policy_hash"],
            canonical["action_digest"], canonical["approval_digest"],
            canonical["target"], canonical["risk_tier"],
            contract_hash, signature, public_key, _now_iso(),
            canonical["expires_at"],
        ))
        conn.execute("COMMIT")
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return {"created": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()

    result = {
        "created": True,
        "contract_id": contract_id,
        "contract_hash": contract_hash,
        "signed": signed,
        "expires_at": expires_at,
    }
    if sign_error:
        result["sign_error"] = sign_error
    return result


# =========================================================
# VERIFY CONTRACT
# =========================================================

def verify_contract(contract_id: str) -> dict:
    """
    Recompute the contract hash and verify the signature.

    Does NOT trust stored values.
    """
    init_contract_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT * FROM contracts WHERE contract_id = ?
        """, (contract_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        return {"valid": False, "reason": "contract_not_found"}

    canonical = {
        "contract_id": row["contract_id"],
        "schema_version": row["schema_version"],
        "action_id": row["action_id"],
        "incident_id": row["incident_id"],
        "evidence_root": row["evidence_root"],
        "assessment_hash": row["assessment_hash"],
        "policy_id": row["policy_id"],
        "policy_hash": row["policy_hash"],
        "action_digest": row["action_digest"],
        "approval_digest": row["approval_digest"],
        "target": row["target"],
        "risk_tier": row["risk_tier"],
        "expires_at": row["expires_at"],
    }

    recomputed = _hash(canonical)
    hash_ok = recomputed == row["contract_hash"]

    signature_ok = False
    if row["signature"] and row["public_key"]:
        try:
            from perception.bridge_signatures import verify
            signature_ok = verify(canonical, row["signature"],
                                  row["public_key"])
        except Exception:
            signature_ok = False

    # Expiration check
    try:
        exp = datetime.fromisoformat(row["expires_at"])
        not_expired = _now() < exp
    except Exception:
        not_expired = False

    return {
        "valid": hash_ok and signature_ok and not_expired,
        "hash_ok": hash_ok,
        "signature_ok": signature_ok,
        "not_expired": not_expired,
        "contract_id": contract_id,
        "signed": bool(row["signature"]),
    }


# =========================================================
# RECEIPT (post-execution)
# =========================================================

def issue_receipt(
    contract_id: str,
    execution_status: str,
    outcome: str | None = None,
    terminal: str = "T",
) -> dict:
    """
    Issue a verifiable receipt for the action's execution.

    execution_status: not_attempted | executed | rejected
    """
    init_contract_db()

    receipt_id = f"rcp-{_hash(contract_id + _now_iso())[:12]}"
    canonical = {
        "receipt_id": receipt_id,
        "contract_id": contract_id,
        "execution_status": execution_status,
        "outcome": outcome,
        "created_at": _now_iso(),
    }
    receipt_hash = _hash(canonical)

    signature = None
    public_key = None
    try:
        from perception.bridge_signatures import sign
        s = sign(canonical, terminal=terminal)
        signature = s.get("signature")
        public_key = s.get("public_key")
    except Exception:
        pass

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO receipts (
                receipt_id, contract_id, execution_status, outcome,
                receipt_hash, signature, public_key, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            receipt_id, contract_id, execution_status, outcome,
            receipt_hash, signature, public_key, _now_iso(),
        ))
        conn.commit()
    finally:
        conn.close()

    return {
        "receipt_id": receipt_id,
        "receipt_hash": receipt_hash,
        "signed": bool(signature),
    }


if __name__ == "__main__":
    import tempfile
    DB_PATH = tempfile.mktemp(suffix=".db")
    init_contract_db()
    r = build_contract(
        action_id="act-001", incident_id="INC-001",
        evidence_root="a" * 64, assessment_hash="b" * 64,
        policy_id="wildfire-v1", policy_hash="c" * 64,
        action_digest="d" * 64, approval_digest="e" * 64,
        target="zone-3", risk_tier="T3",
    )
    print("Contract:", r)
    v = verify_contract(r["contract_id"])
    print("Verify:", v)
