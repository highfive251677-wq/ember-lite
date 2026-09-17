import sqlite3
import hashlib
from datetime import datetime

DB_PATH = "provenance.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL,
            command TEXT NOT NULL,
            source TEXT,
            content_hash TEXT,
            approved_by TEXT,
            approved_at TIMESTAMP,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_action(action_type, command, source=None, notes=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    content_hash = hashlib.sha256(command.encode()).hexdigest()[:16]
    c.execute("""
        INSERT INTO actions (action_type, command, source, content_hash, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (action_type, command, source, content_hash, notes))
    action_id = c.lastrowid
    conn.commit()
    conn.close()
    return action_id, content_hash

def log_approval(action_id, approver, reason=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE actions SET approved_by = ?, approved_at = CURRENT_TIMESTAMP, status = 'approved'
        WHERE id = ?
    """, (approver, action_id))
    conn.commit()
    conn.close()

def get_action_history(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, action_type, command, status, approved_by, executed_at FROM actions ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
    print("✅ Provenance Database initialized.")
