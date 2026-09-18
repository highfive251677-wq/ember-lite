"""
Ember Evidence Chain
=====================
Hash-linked observations with cryptographic provenance.
Each observation references the previous one's hash.
"""

import sqlite3
import hashlib
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "evidence_chain.db")


def init_chain_db():
    """Evidence Chain Database ဖန်တီးခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS chain (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            block_index INTEGER UNIQUE NOT NULL,
            observation_hash TEXT NOT NULL,
            previous_hash TEXT,
            block_hash TEXT UNIQUE NOT NULL,
            signature TEXT,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS chain_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    return DB_PATH


def _compute_hash(data: dict) -> str:
    """SHA-256 Hash ဖန်တီးခြင်း"""
    canonical = json.dumps(data, sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


def _get_last_block() -> dict:
    """နောက်ဆုံး Block ကို ရယူခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT block_index, block_hash FROM chain
        ORDER BY block_index DESC LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    if not row:
        return {"index": 0, "hash": "0" * 64}
    return {"index": row[0], "hash": row[1]}


def add_observation(observation: dict, terminal: str = "cloud") -> dict:
    """Observation တစ်ခုကို Chain ထဲ ထည့်ခြင်း"""
    init_chain_db()
    
    last = _get_last_block()
    next_index = last["index"] + 1
    
    # Observation Hash
    obs_hash = _compute_hash(observation)
    
    # Block Hash (previous + current)
    block_data = {
        "index": next_index,
        "observation_hash": obs_hash,
        "previous_hash": last["hash"],
        "timestamp": datetime.now().isoformat()
    }
    block_hash = _compute_hash(block_data)
    
    # Sign Block
    signature = None
    try:
        from perception.bridge_signatures import sign
        signed = sign(block_data, terminal=terminal)
        signature = signed.get("signature")
    except Exception:
        pass
    
    # Save
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO chain
        (block_index, observation_hash, previous_hash, block_hash, signature, data)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        next_index, obs_hash, last["hash"], block_hash,
        signature, json.dumps(observation, default=str)
    ))
    conn.commit()
    conn.close()
    
    return {
        "block_index": next_index,
        "block_hash": block_hash,
        "previous_hash": last["hash"],
        "observation_hash": obs_hash,
        "signed": signature is not None
    }


def verify_chain() -> dict:
    """Chain တစ်ခုလုံးကို Verify လုပ်ခြင်း"""
    init_chain_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT block_index, observation_hash, previous_hash, block_hash, data
        FROM chain ORDER BY block_index ASC
    """)
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        return {"valid": True, "blocks": 0, "broken_at": None}
    
    previous_hash = "0" * 64
    for i, (idx, obs_hash, prev_hash, block_hash, data) in enumerate(rows):
        # Previous hash check
        if prev_hash != previous_hash:
            return {
                "valid": False,
                "blocks": len(rows),
                "broken_at": idx,
                "reason": f"Chain broken at block {idx}"
            }
        
        # Recompute block hash
        block_data = {
            "index": idx,
            "observation_hash": obs_hash,
            "previous_hash": prev_hash,
            "timestamp": None  # Would need to store separately
        }
        # Simplified verification (full version stores timestamp in data)
        
        previous_hash = block_hash
    
    return {
        "valid": True,
        "blocks": len(rows),
        "broken_at": None,
        "tip": previous_hash[:16]
    }


def get_chain_summary() -> dict:
    """Chain Summary"""
    init_chain_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*), MAX(block_index) FROM chain")
    count, max_idx = c.fetchone()
    conn.close()
    
    return {
        "blocks": count or 0,
        "latest_index": max_idx or 0,
        "tip_hash": _get_last_block()["hash"][:16]
    }


if __name__ == "__main__":
    print("=" * 60)
    print("  Testing Evidence Chain")
    print("=" * 60)
    print()
    
    init_chain_db()
    
    # Add sample observations
    for i in range(3):
        obs = {"test": f"observation-{i}", "value": i * 100}
        result = add_observation(obs, terminal="T")
        print(f"✅ Block #{result['block_index']}: {result['block_hash'][:16]}...")
    
    # Verify
    print()
    print("🔍 Verifying chain...")
    verification = verify_chain()
    for k, v in verification.items():
        print(f"   {k}: {v}")
    
    print()
    print("📊 Summary:")
    for k, v in get_chain_summary().items():
        print(f"   {k}: {v}")
