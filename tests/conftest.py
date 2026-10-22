"""
Test fixtures: every test runs against real SQLite files in a temp dir.

Each module's DB_PATH is pointed at a temporary database so tests exercise the
real code paths (no mocks). The P1–P6 perception layer is explicit SQLite I/O.
"""

import sqlite3

import pytest

from perception import (
    bridge_router,
    bridge_transport,
    database,
    evidence_chain,
    release_gate,
)
import provenance

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence INTEGER DEFAULT 50,
    data TEXT,
    provenance_hash TEXT,
    cost_ms INTEGER DEFAULT 0,
    error_type TEXT,
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@pytest.fixture
def isolated_dbs(tmp_path, monkeypatch):
    """Redirect every persistence layer at a fresh temp database."""
    paths = {
        "chain": tmp_path / "evidence_chain.db",
        "gate": tmp_path / "release_gate.db",
        "perception": tmp_path / "perception.db",
        "graph": tmp_path / "bridge_graph.db",
        "transport": tmp_path / "bridge.db",
        "provenance": tmp_path / "provenance.db",
    }
    monkeypatch.setattr(evidence_chain, "DB_PATH", str(paths["chain"]))
    monkeypatch.setattr(release_gate, "DB_PATH", str(paths["gate"]))
    monkeypatch.setattr(database, "DB_PATH", str(paths["perception"]))
    monkeypatch.setattr(bridge_router, "DB_PATH", str(paths["graph"]))
    monkeypatch.setattr(bridge_transport, "DB_PATH", str(paths["transport"]))
    monkeypatch.setattr(provenance, "DB_PATH", str(paths["provenance"]))
    return paths


@pytest.fixture
def perception_db(isolated_dbs):
    """Initialise an empty perception observations store at the patched path."""
    conn = sqlite3.connect(str(isolated_dbs["perception"]))
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    return str(isolated_dbs["perception"])


@pytest.fixture(autouse=True)
def provisioned_identity(tmp_path, monkeypatch):
    """
    Evidence-hash contract: identity is fail-closed — nothing mints keys
    silently. Every test therefore runs against an isolated KEY_DIR with an
    explicitly provisioned terminal "T" identity (the terminal the signing
    call sites use), so tests exercise the real provisioned-identity path.
    """
    from perception import bridge_signatures as bs

    key_dir = tmp_path / "keys"
    monkeypatch.setattr(bs, "KEY_DIR", str(key_dir))
    bs.generate_keypair("T")
    return str(key_dir)
