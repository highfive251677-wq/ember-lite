"""
Ember Bridge Transport — SQLite Message Bus
============================================
Premium Design:
- WAL Mode for concurrent reads
- Idempotency Keys
- Lamport Timestamps
- Heartbeats
- Dead Letter Queue

Design Principle: "Transport is not Orchestration"
"""

import sqlite3
import uuid
import json
import os
import time
from datetime import datetime, timezone


DB_PATH = os.path.join(os.path.dirname(__file__), "bridge.db")


# =========================================================
# SCHEMA
# =========================================================

def init_bridge_db():
    """Bridge Database ဖန်တီးခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    
    # WAL Mode = Concurrent Reads + Crash Safety
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    
    c = conn.cursor()
    
    # Channels
    c.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Messages (with Idempotency + Lamport)
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE NOT NULL,
            channel TEXT NOT NULL,
            sender TEXT NOT NULL,
            recipient TEXT,
            payload TEXT NOT NULL,
            idempotency_key TEXT UNIQUE,
            lamport_clock INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivered_at TIMESTAMP,
            acked_at TIMESTAMP,
            retry_count INTEGER DEFAULT 0,
            FOREIGN KEY (channel) REFERENCES channels(name)
        )
    """)
    
    # Dead Letter Queue
    c.execute("""
        CREATE TABLE IF NOT EXISTS dead_letters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            reason TEXT,
            original_payload TEXT,
            failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Heartbeats
    c.execute("""
        CREATE TABLE IF NOT EXISTS heartbeats (
            terminal TEXT PRIMARY KEY,
            status TEXT DEFAULT 'active',
            last_beat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT
        )
    """)
    
    # Indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_msg_channel ON messages(channel)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_msg_status ON messages(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_msg_recipient ON messages(recipient)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_msg_lamport ON messages(lamport_clock)")
    
    conn.commit()
    conn.close()
    return DB_PATH


# =========================================================
# CHANNEL MANAGEMENT
# =========================================================

def create_channel(name: str, description: str = "") -> bool:
    """Channel အသစ် ဖန်တီးခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO channels (name, description) VALUES (?, ?)",
            (name, description)
        )
        conn.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def list_channels() -> list:
    """Channel တွေ စာရင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, description, created_at FROM channels ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return [
        {"name": r[0], "description": r[1], "created_at": r[2]}
        for r in rows
    ]


# =========================================================
# MESSAGE OPERATIONS
# =========================================================

def _next_lamport_clock() -> int:
    """Lamport Clock ကို တိုးခြင်း (Distributed Ordering အတွက်)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT MAX(lamport_clock) FROM messages")
    current = c.fetchone()[0] or 0
    conn.close()
    return current + 1


def send_message(
    channel: str,
    sender: str,
    payload: dict,
    recipient: str = None,
    idempotency_key: str = None,
    priority: int = 5
) -> dict:
    """
    Message ပို့ခြင်း (Idempotent)
    
    Args:
        channel: Channel နာမည်
        sender: ပို့သူ (terminal label)
        payload: Dict payload
        recipient: လက်ခံသူ (None = broadcast)
        idempotency_key: Duplicate ကာကွယ်ဖို့
        priority: 1 (highest) - 9 (lowest)
    
    Returns: result dict
    """
    # Idempotency Key မရှိရင် Auto-generate
    if not idempotency_key:
        idempotency_key = f"{channel}:{sender}:{uuid.uuid4().hex[:16]}"
    
    # Duplicate Check
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT message_id FROM messages WHERE idempotency_key = ?",
        (idempotency_key,)
    )
    existing = c.fetchone()
    
    if existing:
        conn.close()
        return {
            "status": "duplicate",
            "message_id": existing[0],
            "idempotency_key": idempotency_key
        }
    
    # Channel ရှိမရှိ စစ်
    c.execute("SELECT name FROM channels WHERE name = ?", (channel,))
    if not c.fetchone():
        create_channel(channel)
    
    # Message ထည့်
    message_id = str(uuid.uuid4())
    lamport = _next_lamport_clock()
    
    try:
        c.execute("""
            INSERT INTO messages
            (message_id, channel, sender, recipient, payload,
             idempotency_key, lamport_clock, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message_id, channel, sender, recipient,
            json.dumps(payload), idempotency_key, lamport, priority
        ))
        conn.commit()
        
        return {
            "status": "sent",
            "message_id": message_id,
            "lamport_clock": lamport,
            "idempotency_key": idempotency_key
        }
    except sqlite3.Error as e:
        conn.close()
        return {"status": "error", "error": str(e)}
    finally:
        if conn:
            conn.close()


def receive_messages(
    terminal: str,
    channel: str = None,
    limit: int = 10,
    mark_delivered: bool = True
) -> list:
    """
    Terminal တစ်ခုအတွက် Message တွေ ရယူခြင်း
    
    Args:
        terminal: Terminal label (@ or T)
        channel: Channel filter (None = all)
        limit: အများဆုံး ဘယ်နှစ်ခု
        mark_delivered: ရယူပြီးရင် Delivered လို့ သတ်မှတ်
    
    Returns: list of messages
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    query = """
        SELECT message_id, channel, sender, payload,
               lamport_clock, priority, created_at, status
        FROM messages
        WHERE status = 'pending'
        AND (recipient IS NULL OR recipient = ?)
    """
    params = [terminal]
    
    if channel:
        query += " AND channel = ?"
        params.append(channel)
    
    query += " ORDER BY priority ASC, lamport_clock ASC LIMIT ?"
    params.append(limit)
    
    c.execute(query, params)
    rows = c.fetchall()
    
    messages = []
    for r in rows:
        messages.append({
            "message_id": r[0],
            "channel": r[1],
            "sender": r[2],
            "payload": json.loads(r[3]),
            "lamport_clock": r[4],
            "priority": r[5],
            "created_at": r[6],
            "status": r[7]
        })
        
        if mark_delivered:
            c.execute("""
                UPDATE messages
                SET status = 'delivered', delivered_at = CURRENT_TIMESTAMP
                WHERE message_id = ?
            """, (r[0],))
    
    conn.commit()
    conn.close()
    return messages


def ack_message(message_id: str) -> bool:
    """Message ကို Acknowledge လုပ်ခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE messages
        SET status = 'acked', acked_at = CURRENT_TIMESTAMP
        WHERE message_id = ?
    """, (message_id,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def move_to_dlq(message_id: str, reason: str) -> bool:
    """Message ကို Dead Letter Queue ထဲ ရွှေ့ခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute(
        "SELECT payload FROM messages WHERE message_id = ?",
        (message_id,)
    )
    row = c.fetchone()
    
    if not row:
        conn.close()
        return False
    
    c.execute("""
        INSERT INTO dead_letters (message_id, reason, original_payload)
        VALUES (?, ?, ?)
    """, (message_id, reason, row[0]))
    
    c.execute("DELETE FROM messages WHERE message_id = ?", (message_id,))
    
    conn.commit()
    conn.close()
    return True


# =========================================================
# HEARTBEATS
# =========================================================

def heartbeat(terminal: str, metadata: dict = None):
    """Terminal တစ်ခုရဲ့ Heartbeat"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO heartbeats
        (terminal, status, last_beat, metadata)
        VALUES (?, 'active', CURRENT_TIMESTAMP, ?)
    """, (terminal, json.dumps(metadata or {})))
    conn.commit()
    conn.close()


def get_active_terminals(max_age_seconds: int = 300) -> list:
    """Active Terminal တွေ စာရင်း (၅ မိနစ်အတွင်း Heartbeat ရှိသူ)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT terminal, last_beat, metadata
        FROM heartbeats
        WHERE (strftime('%s', 'now') - strftime('%s', last_beat)) < ?
        ORDER BY terminal
    """, (max_age_seconds,))
    rows = c.fetchall()
    conn.close()
    return [
        {"terminal": r[0], "last_beat": r[1], "metadata": json.loads(r[2] or "{}")}
        for r in rows
    ]


# =========================================================
# STATISTICS
# =========================================================

def get_transport_stats() -> dict:
    """Transport Statistics"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM channels")
    channels = c.fetchone()[0]
    
    c.execute("SELECT status, COUNT(*) FROM messages GROUP BY status")
    by_status = dict(c.fetchall())
    
    c.execute("SELECT COUNT(*) FROM dead_letters")
    dlq = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM heartbeats")
    heartbeats = c.fetchone()[0]
    
    conn.close()
    
    return {
        "channels": channels,
        "messages_by_status": by_status,
        "dead_letters": dlq,
        "known_terminals": heartbeats
    }


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Testing Bridge Transport (P4.1)")
    print("=" * 60)
    print()
    
    # Init
    path = init_bridge_db()
    print(f"✅ Database: {path}")
    
    # Create channels
    create_channel("ember://ashell/main", "a-Shell main channel")
    create_channel("ember://termux/main", "Termux main channel")
    print(f"✅ Channels: {list_channels()}")
    print()
    
    # Send messages
    print("📤 Sending messages...")
    r1 = send_message(
        "ember://ashell/main", "@",
        {"command": "curl https://api.example.com/health", "type": "http_check"},
        recipient="T",
        idempotency_key="health-check-001"
    )
    print(f"   Sent 1: {r1['status']} (lamport={r1.get('lamport_clock')})")
    
    # Duplicate test
    r2 = send_message(
        "ember://ashell/main", "@",
        {"command": "curl https://api.example.com/health", "type": "http_check"},
        recipient="T",
        idempotency_key="health-check-001"  # Same key
    )
    print(f"   Sent 2 (duplicate): {r2['status']}")
    
    r3 = send_message(
        "ember://termux/main", "T",
        {"status": "clean", "files": 0},
        recipient="@"
    )
    print(f"   Sent 3: {r3['status']} (lamport={r3.get('lamport_clock')})")
    print()
    
    # Receive
    print("📥 Receiving messages (Terminal T)...")
    messages = receive_messages("T", limit=10)
    for m in messages:
        print(f"   • [{m['channel']}] from {m['sender']}: {m['payload']}")
    print()
    
    # Heartbeats
    print("💓 Heartbeats...")
    heartbeat("@", {"device": "iPhone", "os": "iOS"})
    heartbeat("T", {"device": "Tab A 2017", "os": "Android"})
    active = get_active_terminals()
    for t in active:
        print(f"   • {t['terminal']}: {t['metadata']}")
    print()
    
    # Stats
    print("📊 Transport Stats:")
    stats = get_transport_stats()
    for k, v in stats.items():
        print(f"   {k}: {v}")
    
    print()
    print("✅ P4.1 Transport test complete.")
