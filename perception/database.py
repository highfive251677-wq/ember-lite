"""
Ember Perception - Database Manager
Observation Store ကို စီမံခန့်ခွဲခြင်း
"""

import sqlite3
import os
from datetime import datetime

# Database လမ်းကြောင်း
DB_PATH = os.path.join(os.path.dirname(__file__), "perception.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def init_db():
    """Database နဲ့ Tables တွေ ဖန်တီးခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    return DB_PATH


def save_observation(obs: dict) -> int:
    """Observation တစ်ခုကို သိမ်းခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO observations 
        (source, category, status, confidence, data, provenance_hash, cost_ms, error_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        obs.get("source"),
        obs.get("category", "general"),
        obs.get("status"),
        obs.get("confidence", 50),
        str(obs.get("data", {})),
        obs.get("provenance_hash"),
        obs.get("cost_ms", 0),
        obs.get("error_type")
    ))
    obs_id = c.lastrowid
    conn.commit()
    conn.close()
    return obs_id


def get_latest_observation(source: str) -> dict:
    """Source တစ်ခုရဲ့ နောက်ဆုံး Observation ကို ရယူခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT source, category, status, confidence, data, 
               provenance_hash, cost_ms, error_type, observed_at
        FROM observations 
        WHERE source = ?
        ORDER BY id DESC LIMIT 1
    """, (source,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        "source": row[0],
        "category": row[1],
        "status": row[2],
        "confidence": row[3],
        "data": row[4],
        "provenance_hash": row[5],
        "cost_ms": row[6],
        "error_type": row[7],
        "observed_at": row[8]
    }


def get_recent_observations(limit: int = 10) -> list:
    """နောက်ဆုံး Observation တွေကို ရယူခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, source, status, confidence, observed_at
        FROM observations 
        ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows


def log_change(source: str, field: str, old_value, new_value):
    """ပြောင်းလဲမှုကို မှတ်တမ်းတင်ခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO change_log (source, field, old_value, new_value)
        VALUES (?, ?, ?, ?)
    """, (source, field, str(old_value), str(new_value)))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    path = init_db()
    print(f"✅ Database initialized: {path}")
    
    # Test: Observation သိမ်းကြည့်
    test_obs = {
        "source": "test",
        "status": "healthy",
        "confidence": 95,
        "data": {"message": "Test observation"},
        "provenance_hash": "abc123",
        "cost_ms": 100
    }
    obs_id = save_observation(test_obs)
    print(f"✅ Test observation saved with ID: {obs_id}")
    
    # Test: ပြန်ရယူကြည့်
    latest = get_latest_observation("test")
    print(f"✅ Latest observation: {latest['status']}")
