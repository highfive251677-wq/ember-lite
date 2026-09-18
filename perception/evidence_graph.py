"""
Ember Evidence Graph
ဆုံးဖြတ်ချက်များရဲ့ ဆက်စပ်မှုကို Graph အနေနဲ့ မှတ်တမ်းတင်ခြင်း
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "evidence_graph.db")


def init_graph_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_type TEXT,
            label TEXT,
            data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER,
            target_id INTEGER,
            relation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES nodes(id),
            FOREIGN KEY (target_id) REFERENCES nodes(id)
        )
    """)
    conn.commit()
    conn.close()


def add_node(node_type, label, data=""):
    init_graph_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO nodes (node_type, label, data) VALUES (?, ?, ?)",
        (node_type, label, str(data))
    )
    node_id = c.lastrowid
    conn.commit()
    conn.close()
    return node_id


def add_edge(source_id, target_id, relation):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO edges (source_id, target_id, relation) VALUES (?, ?, ?)",
        (source_id, target_id, relation)
    )
    conn.commit()
    conn.close()


def get_graph_summary():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM nodes")
    nodes = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM edges")
    edges = c.fetchone()[0]
    conn.close()
    return {"nodes": nodes, "edges": edges}


if __name__ == "__main__":
    init_graph_db()
    n1 = add_node("signal", "Backend Health", "healthy")
    n2 = add_node("evidence", "Health Check Result", "status: 200")
    add_edge(n1, n2, "generates")
    print(get_graph_summary())
