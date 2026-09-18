"""
Ember Bridge Router + Signed Evidence Graph
============================================
Premium: Route + Sign + Graph in one module
"""

import sqlite3
import json
import os
import uuid
from datetime import datetime

from perception.bridge_transport import (
    init_bridge_db, send_message, receive_messages,
    create_channel, heartbeat, get_transport_stats
)
from perception.bridge_signatures import sign, verify


DB_PATH = os.path.join(os.path.dirname(__file__), "bridge_graph.db")


# =========================================================
# ROUTER
# =========================================================

ROUTES = {
    "@": "ember://ashell/main",
    "T": "ember://termux/main"
}


def route_command(command: str, sender: str) -> dict:
    """Terminal Label ကနေ Channel ကို Route လုပ်ခြင်း"""
    channel = ROUTES.get(sender)
    if not channel:
        return {"status": "error", "error": f"Unknown sender: {sender}"}
    
    create_channel(channel)
    
    # Sign the payload
    payload = {
        "command": command,
        "terminal": sender,
        "issued_at": datetime.now().isoformat()
    }
    signed = sign(payload, terminal=sender)
    payload["signature"] = signed["signature"]
    payload["public_key"] = signed["public_key"]
    
    recipient = "@" if sender == "T" else "T"
    
    result = send_message(
        channel=channel,
        sender=sender,
        payload=payload,
        recipient=recipient,
        idempotency_key=f"{sender}:{uuid.uuid4().hex[:12]}"
    )
    
    # Add to graph
    if result.get("status") in ("sent", "duplicate"):
        _add_signed_node(
            node_type="command",
            label=command[:60],
            data=payload,
            terminal=sender
        )
    
    return {
        "status": result.get("status"),
        "channel": channel,
        "signed": True,
        "message_id": result.get("message_id")
    }


def process_inbox(terminal: str, limit: int = 5) -> list:
    """Terminal တစ်ခုအတွက် Messages ရယူခြင်း"""
    messages = receive_messages(terminal, limit=limit)
    
    for m in messages:
        payload = m.get("payload", {})
        sig = payload.get("signature")
        pub = payload.get("public_key")
        
        if sig and pub:
            verified = verify(
                {k: v for k, v in payload.items()
                 if k not in ("signature", "public_key")},
                sig, pub
            )
            m["verified"] = verified
        else:
            m["verified"] = False
    
    return messages


# =========================================================
# SIGNED GRAPH
# =========================================================

def init_graph_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_type TEXT,
            label TEXT,
            data TEXT,
            terminal TEXT,
            signature TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER,
            target_id INTEGER,
            relation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _add_signed_node(node_type, label, data, terminal):
    init_graph_db()
    signed = sign(data, terminal=terminal)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO nodes (node_type, label, data, terminal, signature)
        VALUES (?, ?, ?, ?, ?)
    """, (node_type, label, json.dumps(data), terminal, signed["signature"]))
    node_id = c.lastrowid
    conn.commit()
    conn.close()
    return node_id


def add_edge(source_id, target_id, relation):
    init_graph_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO edges (source_id, target_id, relation) VALUES (?, ?, ?)",
        (source_id, target_id, relation)
    )
    conn.commit()
    conn.close()


def graph_summary() -> dict:
    init_graph_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM nodes")
    nodes = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM edges")
    edges = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT terminal) FROM nodes WHERE terminal IS NOT NULL")
    terminals = c.fetchone()[0]
    conn.close()
    return {"nodes": nodes, "edges": edges, "terminals": terminals}


def verify_graph_integrity() -> dict:
    """Graph ထဲက Nodes အားလုံးရဲ့ Signatures ကို စစ်ဆေးခြင်း"""
    init_graph_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, data, terminal, signature FROM nodes")
    rows = c.fetchall()
    conn.close()
    
    valid, invalid = 0, 0
    for _id, data_str, terminal, sig in rows:
        if not sig:
            invalid += 1
            continue
        try:
            payload = json.loads(data_str)
            from perception.bridge_signatures import _load_public, _load_private
            import base64
            priv = _load_private(terminal or "T")
            pub_bytes = priv.public_key().public_bytes_raw()
            pub_b64 = base64.b64encode(pub_bytes).decode()
            if verify(payload, sig, pub_b64):
                valid += 1
            else:
                invalid += 1
        except Exception:
            invalid += 1
    
    return {"total": len(rows), "valid": valid, "invalid": invalid}


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Testing Bridge Router + Graph (P4.3 + P4.4)")
    print("=" * 60)
    print()
    
    init_bridge_db()
    init_graph_db()
    
    # Send commands from both terminals
    print("📤 Routing commands...")
    r1 = route_command("curl https://example.com/health", "@")
    print(f"   @ → {r1['status']} (signed={r1['signed']})")
    
    r2 = route_command("git status --short", "T")
    print(f"   T → {r2['status']} (signed={r2['signed']})")
    print()
    
    # Process inbox
    print("📥 Processing inbox...")
    msgs = process_inbox("T")
    for m in msgs:
        icon = "✅" if m.get("verified") else "❌"
        print(f"   {icon} from {m['sender']}: {m['payload'].get('command')}")
    print()
    
    # Graph
    print("📊 Graph Summary:")
    gs = graph_summary()
    for k, v in gs.items():
        print(f"   {k}: {v}")
    print()
    
    # Verify
    print("🔍 Graph Integrity:")
    vi = verify_graph_integrity()
    for k, v in vi.items():
        print(f"   {k}: {v}")
    print()
    
    print("✅ P4.3 + P4.4 complete.")
