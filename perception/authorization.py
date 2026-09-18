"""
Ember Authorization FSM (Phase 3 — Enforced Human Control)
============================================================
Copilot Phase 3: Action-Bound Approval

Core Principle:
    Approval for one action cannot be reused for another.
    Approval is cryptographically bound to:
        action_id + evidence_root + policy_hash + expires_at

Key Distinction:
    assessment != authorization

FSM States:
    pending -> partial -> approved -> consumed
                       -> expired
                       -> revoked
"""

from __future__ import annotations

import sqlite3
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any


DB_PATH = os.path.join(os.path.dirname(__file__), "authorization.db")

SCHEMA_VERSION = "1.0"

# FSM transitions (allowed)
TRANSITIONS = {
    "pending":   {"partial", "approved", "expired", "revoked"},
    "partial":   {"approved", "expired", "revoked"},
    "approved":  {"consumed", "expired", "revoked"},
    "consumed":  set(),
    "expired":   set(),
    "revoked":   set(),
}


# =========================================================
# HELPERS
# =========================================================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _canonical_bytes(p: Any) -> bytes:
    return json.dumps(
        p, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    ).encode("utf-8")


def _hash(p: Any) -> str:
    return hashlib.sha256(_canonical_bytes(p)).hexdigest()


# =========================================================
# SCHEMA
# =========================================================

def init_auth_db() -> str:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT UNIQUE NOT NULL,
                schema_version TEXT NOT NULL,
                incident_id TEXT,
                action_type TEXT NOT NULL,
                target TEXT,
                risk_tier TEXT NOT NULL,
                evidence_root TEXT,
                policy_id TEXT,
                policy_hash TEXT,
                required_approvals INTEGER DEFAULT 1,
                current_approvals INTEGER DEFAULT 0,
                state TEXT DEFAULT 'pending',
                action_digest TEXT UNIQUE NOT NULL,
                expires_at TEXT,
                created_at TEXT,
                state_changed_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT NOT NULL,
                approver TEXT NOT NULL,
                approval_digest TEXT NOT NULL,
                signature TEXT,
                public_key TEXT,
                signed_payload TEXT,
                signed_at TEXT,
                UNIQUE(action_id, approver)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT UNIQUE NOT NULL,
                receipt_json TEXT NOT NULL,
                receipt_hash TEXT NOT NULL,
                receipt_signature TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()
    return DB_PATH


# =========================================================
# CANONICAL ACTION OBJECT
# =========================================================

def build_action_digest(action: dict) -> str:
    """Canonical digest for an action. Same fields always = same digest."""
    canonical = {
        "action_id": action["action_id"],
        "incident_id": action.get("incident_id"),
        "action_type": action["action_type"],
        "target": action.get("target"),
        "risk_tier": action["risk_tier"],
        "evidence_root": action.get("evidence_root"),
        "policy_hash": action.get("policy_hash"),
        "expires_at": action.get("expires_at"),
    }
    return _hash(canonical)


def build_approval_digest(action: dict, approver: str) -> str:
    """Approval is bound to the exact action + approver."""
    canonical = {
        "action_digest": action["action_digest"],
        "approver": approver,
    }
    return _hash(canonical)


# =========================================================
# ACTION LIFECYCLE
# =========================================================

def create_action(
    action_type: str,
    incident_id: str | None,
    risk_tier: str,
    evidence_root: str | None,
    policy_hash: str | None,
    required_approvals: int = 1,
    ttl_seconds: int = 3600,
    target: str | None = None,
) -> dict:
    """Create a new action in the authorization ledger."""
    init_auth_db()

    action_id = f"act-{uuid.uuid4().hex[:12]}"
    expires_at = (_now() + timedelta(seconds=ttl_seconds)).isoformat()

    action = {
        "action_id": action_id,
        "incident_id": incident_id,
        "action_type": action_type,
        "target": target,
        "risk_tier": risk_tier,
        "evidence_root": evidence_root,
        "policy_hash": policy_hash,
        "required_approvals": required_approvals,
        "expires_at": expires_at,
    }
    action["action_digest"] = build_action_digest(action)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""
            INSERT INTO actions (
                action_id, schema_version, incident_id, action_type, target,
                risk_tier, evidence_root, policy_id, policy_hash,
                required_approvals, state, action_digest, expires_at,
                created_at, state_changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
        """, (
            action_id, SCHEMA_VERSION, incident_id, action_type, target,
            risk_tier, evidence_root, None, policy_hash,
            required_approvals, action["action_digest"], expires_at,
            _now_iso(), _now_iso(),
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

    return {
        "created": True,
        "action_id": action_id,
        "action_digest": action["action_digest"],
        "state": "pending",
        "required_approvals": required_approvals,
        "expires_at": expires_at,
    }


def _get_action(conn: sqlite3.Connection, action_id: str) -> dict | None:
    row = conn.execute("""
        SELECT action_id, action_type, incident_id, target, risk_tier,
               evidence_root, policy_hash, required_approvals,
               current_approvals, state, action_digest, expires_at
        FROM actions WHERE action_id = ?
    """, (action_id,)).fetchone()
    if not row:
        return None
    return {
        "action_id": row[0], "action_type": row[1], "incident_id": row[2],
        "target": row[3], "risk_tier": row[4], "evidence_root": row[5],
        "policy_hash": row[6], "required_approvals": row[7],
        "current_approvals": row[8], "state": row[9],
        "action_digest": row[10], "expires_at": row[11],
    }


def _transition(conn, action_id: str, new_state: str) -> None:
    conn.execute("""
        UPDATE actions
        SET state = ?, state_changed_at = ?
        WHERE action_id = ?
    """, (new_state, _now_iso(), action_id))


def approve_action(
    action_id: str,
    approver: str,
    signature: str | None = None,
    public_key: str | None = None,
) -> dict:
    """
    Approve an action.

    Approval is bound to (action_digest, approver) — cannot be reused.
    """
    init_auth_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("BEGIN IMMEDIATE")
        action = _get_action(conn, action_id)
        if not action:
            conn.execute("ROLLBACK")
            return {"approved": False, "error": "action_not_found"}

        if action["state"] not in ("pending", "partial"):
            conn.execute("ROLLBACK")
            return {"approved": False,
                    "error": f"cannot_approve_in_state_{action['state']}"}

        # Expiration check
        try:
            exp = datetime.fromisoformat(action["expires_at"])
            if _now() > exp:
                _transition(conn, action_id, "expired")
                conn.execute("COMMIT")
                return {"approved": False, "error": "action_expired"}
        except Exception:
            pass

        # Binding
        approval_digest = build_approval_digest(action, approver)

        # Insert approval (idempotent via UNIQUE)
        try:
            conn.execute("""
                INSERT INTO approvals (
                    action_id, approver, approval_digest,
                    signature, public_key, signed_payload, signed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                action_id, approver, approval_digest,
                signature, public_key, None, _now_iso(),
            ))
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK")
            return {"approved": False, "error": "duplicate_approver"}

        new_count = action["current_approvals"] + 1
        required = action["required_approvals"]

        if new_count >= required:
            new_state = "approved"
        else:
            new_state = "partial"

        conn.execute("""
            UPDATE actions
            SET current_approvals = ?, state = ?, state_changed_at = ?
            WHERE action_id = ?
        """, (new_count, new_state, _now_iso(), action_id))

        conn.execute("COMMIT")

        return {
            "approved": True,
            "action_id": action_id,
            "state": new_state,
            "current_approvals": new_count,
            "required_approvals": required,
            "approval_digest": approval_digest,
        }
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return {"approved": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()


# =========================================================
# AUTHORIZATION CHECK (the action gate)
# =========================================================

def authorize_action(action_id: str) -> dict:
    """
    Check whether an action may execute.

    This is the ENFORCEMENT point. Assessment != Authorization.
    """
    init_auth_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        action = _get_action(conn, action_id)
        if not action:
            return {"authorized": False, "reason": "action_not_found"}

        if action["state"] == "approved":
            # Expiration re-check
            try:
                exp = datetime.fromisoformat(action["expires_at"])
                if _now() > exp:
                    _transition(conn, action_id, "expired")
                    conn.commit()
                    return {"authorized": False, "reason": "expired"}
            except Exception:
                pass

            # Consume the approval (one-shot)
            _transition(conn, action_id, "consumed")
            conn.commit()
            return {
                "authorized": True,
                "action_id": action_id,
                "action_type": action["action_type"],
                "risk_tier": action["risk_tier"],
                "consumed": True,
            }

        return {
            "authorized": False,
            "reason": f"state_{action['state']}",
            "required_approvals": action["required_approvals"],
            "current_approvals": action["current_approvals"],
        }
    finally:
        conn.close()


def revoke_action(action_id: str, reason: str = "") -> dict:
    init_auth_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        action = _get_action(conn, action_id)
        if not action:
            return {"revoked": False, "error": "action_not_found"}
        if "revoked" not in TRANSITIONS.get(action["state"], set()):
            return {"revoked": False, "error": f"cannot_revoke_from_{action['state']}"}
        _transition(conn, action_id, "revoked")
        conn.commit()
        return {"revoked": True, "action_id": action_id, "reason": reason}
    finally:
        conn.close()


def expire_stale_actions() -> dict:
    """Move all expired pending/partial actions to 'expired' state."""
    init_auth_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("""
            SELECT action_id, expires_at FROM actions
            WHERE state IN ('pending', 'partial', 'approved')
        """).fetchall()
        expired = []
        for aid, exp in rows:
            try:
                if _now() > datetime.fromisoformat(exp):
                    _transition(conn, aid, "expired")
                    expired.append(aid)
            except Exception:
                continue
        conn.commit()
        return {"expired_count": len(expired), "action_ids": expired}
    finally:
        conn.close()


def get_action_state(action_id: str) -> dict | None:
    init_auth_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        return _get_action(conn, action_id)
    finally:
        conn.close()


if __name__ == "__main__":
    print("Authorization FSM v1")
    init_auth_db()
    r = create_action(
        action_type="notify_zone",
        incident_id="INC-001",
        risk_tier="T3",
        evidence_root="abc" * 20,
        policy_hash="def" * 20,
        required_approvals=1,
    )
    print("Created:", r["action_id"], "state:", r["state"])
    a = approve_action(r["action_id"], "operator-1")
    print("Approved:", a.get("state"))
    auth = authorize_action(r["action_id"])
    print("Authorized:", auth.get("authorized"))
    auth2 = authorize_action(r["action_id"])
    print("Re-authorized:", auth2.get("authorized"), "(should be False)")
