"""
Ember Wave 3 Target Schema (Crypto Tables)
============================================
Tables for crypto data migration to ember_operational.db.

Source → Target mapping:
    evidence_chain.db:chain      → evidence_blocks
    anchors.db:anchors           → anchors
    authorization.db:actions     → authorizations
    authorization.db:approvals   → approvals
    authorization.db:receipts    → receipts
    contracts.db:contracts       → action_contracts  (skip if not found)
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = "1.0"

WAVE_3_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_blocks (
    block_index INTEGER PRIMARY KEY,
    schema_version TEXT NOT NULL DEFAULT '1.0',
    observation_hash TEXT NOT NULL,
    previous_hash TEXT,
    block_hash TEXT NOT NULL UNIQUE,
    canonical_payload TEXT NOT NULL,
    signature TEXT,
    public_key TEXT,
    key_id TEXT,
    terminal TEXT,
    signed INTEGER DEFAULT 0,
    verified INTEGER DEFAULT 0,
    anchored INTEGER DEFAULT 0,
    created_at TEXT,
    legacy_source_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_eb_hash
    ON evidence_blocks(block_hash);
CREATE INDEX IF NOT EXISTS idx_eb_prev
    ON evidence_blocks(previous_hash);

CREATE TABLE IF NOT EXISTS anchors (
    anchor_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL DEFAULT '1.0',
    device_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,
    merkle_root TEXT NOT NULL,
    first_block_index INTEGER,
    last_block_index INTEGER,
    block_count INTEGER,
    previous_anchor_hash TEXT,
    anchor_hash TEXT NOT NULL UNIQUE,
    signature TEXT,
    public_key TEXT,
    created_at TEXT,
    published INTEGER DEFAULT 0,
    published_at TEXT,
    remote_ref TEXT,
    legacy_source_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_anchors_device
    ON anchors(device_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_anchors_hash
    ON anchors(anchor_hash);

CREATE TABLE IF NOT EXISTS authorizations (
    action_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL DEFAULT '1.0',
    incident_id TEXT,
    action_type TEXT NOT NULL,
    target TEXT,
    risk_tier TEXT NOT NULL,
    evidence_root TEXT,
    policy_id TEXT,
    policy_hash TEXT,
    required_approvals INTEGER DEFAULT 1,
    current_approvals INTEGER DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'pending',
    action_digest TEXT NOT NULL UNIQUE,
    expires_at TEXT,
    created_at TEXT,
    state_changed_at TEXT,
    legacy_source_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_auth_incident
    ON authorizations(incident_id);
CREATE INDEX IF NOT EXISTS idx_auth_state
    ON authorizations(state);

CREATE TABLE IF NOT EXISTS approvals (
    approval_digest TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    approver TEXT NOT NULL,
    signature TEXT,
    public_key TEXT,
    signed_payload TEXT,
    signed_at TEXT,
    legacy_source_id INTEGER,
    UNIQUE (action_id, approver)
);

CREATE INDEX IF NOT EXISTS idx_appr_action
    ON approvals(action_id);

CREATE TABLE IF NOT EXISTS receipts (
    receipt_hash TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    receipt_json TEXT NOT NULL,
    receipt_signature TEXT,
    created_at TEXT,
    legacy_source_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_receipt_action
    ON receipts(action_id);

CREATE TABLE IF NOT EXISTS action_contracts (
    contract_hash TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    incident_id TEXT,
    evidence_root TEXT,
    assessment_hash TEXT,
    policy_hash TEXT,
    approval_digest TEXT,
    target TEXT,
    risk_tier TEXT,
    expires_at TEXT,
    contract_json TEXT NOT NULL,
    signature TEXT,
    public_key TEXT,
    created_at TEXT,
    legacy_source_id INTEGER,
    UNIQUE (action_id, contract_hash)
);

CREATE INDEX IF NOT EXISTS idx_contract_action
    ON action_contracts(action_id);
"""


def init_wave_3_schema(conn: sqlite3.Connection) -> dict:
    """Create Wave 3 tables in operational DB."""
    try:
        conn.executescript(WAVE_3_SCHEMA)
        return {"wave": 3, "created": True}
    except Exception as exc:
        return {"wave": 3, "created": False,
                "error": f"{type(exc).__name__}: {exc}"}


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    print("=" * 60)
    print("  WAVE 3 SCHEMA — SELF TEST")
    print("=" * 60)
    print()

    db = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(db)
    try:
        r = init_wave_3_schema(conn)
        print(f"Init: {r.get('created')}")

        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        print(f"Tables ({len(tables)}):")
        for t in tables:
            print(f"  • {t}")
    finally:
        conn.close()

    print()
    print("🎉 WAVE 3 SCHEMA READY")
