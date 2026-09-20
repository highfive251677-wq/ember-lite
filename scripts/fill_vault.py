#!/data/data/com.termux/files/usr/bin/python3
"""
Ember Vault Fill — Phase 5 replay → operational DB
====================================================
Root cause fix: replay.py uses tempfile.mktemp() which orphans
all evidence. This script redirects tempfile BEFORE importing
replay, so evidence lands in the real operational DB.
"""
import sys
import sqlite3
import tempfile
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

# ── 1. Setup paths ────────────────────────────────
EMBER_HOME = Path.home() / ".ember"
EMBER_HOME.mkdir(exist_ok=True)
OP_DB = EMBER_HOME / "ember_operational.db"

REPO = Path.home() / "ember-lite"
sys.path.insert(0, str(REPO))

print(f"Operational DB: {OP_DB}")
print(f"Repo: {REPO}")
print()

# ── 2. Monkeypatch tempfile BEFORE importing replay ──
_orig_mktemp = tempfile.mktemp

def _redirected_mktemp(*args, **kwargs):
    """Every temp DB request → operational DB."""
    return str(OP_DB)

tempfile.mktemp = _redirected_mktemp
print("✓ tempfile.mktemp redirected → operational DB")
print()

# ── 3. Init Wave 3 schema ─────────────────────────
from perception.wave3_schema import init_wave_3_schema

conn = sqlite3.connect(str(OP_DB))
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA journal_mode = WAL")
init_wave_3_schema(conn)
print("✓ Wave 3 schema ready")
print()

# ── 4. Clear prior vault rows (idempotent) ────────
for tbl in ["evidence_blocks", "anchors", "receipts"]:
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        if n > 0:
            print(f"  Clearing {tbl}: {n} existing rows")
            conn.execute(f"DELETE FROM {tbl}")
    except sqlite3.OperationalError:
        pass
conn.commit()
print()

# ── 5. Discover replay API ────────────────────────
from perception import replay
replay_api = [x for x in dir(replay) if not x.startswith("_") and callable(getattr(replay, x))]
print(f"replay.py API: {replay_api[:15]}")
print()

# Find the runner
runner_name = None
for candidate in ["run_replay", "run_all_scenarios", "run_scenarios",
                  "run_all", "main", "replay_all", "run"]:
    if hasattr(replay, candidate):
        runner_name = candidate
        break

if not runner_name:
    print("❌ No runner function found in replay.py")
    print("Available callables:")
    for name in replay_api:
        print(f"  - {name}")
    sys.exit(1)

print(f"✓ Found runner: {runner_name}()")
print()

# ── 6. Run the replay ─────────────────────────────
print("=" * 60)
print("  RUNNING PHASE 5 REPLAY")
print("=" * 60)

runner = getattr(replay, runner_name)
try:
    result = runner()
    print()
    print(f"✓ Replay complete: {result}")
except Exception as e:
    print(f"⚠️  Replay error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print()

# ── 7. Restore tempfile ───────────────────────────
tempfile.mktemp = _orig_mktemp

# ── 8. Migrate legacy chain → evidence_blocks ─────
print("=" * 60)
print("  MIGRATING CHAIN → EVIDENCE_BLOCKS")
print("=" * 60)

legacy_dbs = [
    REPO / "perception" / "evidence_chain.db",
    Path.home() / ".ember" / "evidence_chain.db",
]

migrated = 0
for legacy in legacy_dbs:
    if not legacy.exists():
        continue
    try:
        lconn = sqlite3.connect(str(legacy))
        tables = [r[0] for r in lconn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )]
        if "chain" not in tables:
            lconn.close()
            continue

        rows = lconn.execute(
            "SELECT id, block_index, observation_hash, previous_hash, "
            "block_hash, canonical_payload, signature, public_key, "
            "created_at FROM chain ORDER BY block_index"
        ).fetchall()
        lconn.close()

        for r in rows:
            (legacy_id, block_index, obs_hash, prev_hash,
             block_hash, payload, sig, pub, created) = r
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO evidence_blocks
                    (block_index, schema_version, observation_hash,
                     previous_hash, block_hash, canonical_payload,
                     signature, public_key, signed, created_at,
                     legacy_source_id)
                    VALUES (?, '1.0', ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """, (block_index, obs_hash, prev_hash, block_hash,
                      payload, sig, pub, created, legacy_id))
                migrated += 1
            except sqlite3.OperationalError as e:
                print(f"  ⚠️ block {block_index}: {e}")

        conn.commit()
        print(f"✓ Migrated from {legacy.name}: {migrated} rows")
    except Exception as e:
        print(f"  ⚠️ {legacy}: {e}")

print()

# ── 9. Summary ────────────────────────────────────
print("=" * 60)
print("  VAULT STATUS")
print("=" * 60)

for tbl, target in [("evidence_blocks", ">0"), ("anchors", ">0"), ("receipts", ">0")]:
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        mark = "✓" if n > 0 else "⚠️"
        print(f"  {mark} {tbl:20s} {n:5d} rows  (target: {target})")
    except sqlite3.OperationalError as e:
        print(f"  ❌ {tbl}: {e}")

print()

# Latest block preview
try:
    row = conn.execute("""
        SELECT block_index, substr(block_hash,1,16), signed, created_at
        FROM evidence_blocks
        ORDER BY block_index DESC LIMIT 1
    """).fetchone()
    if row:
        print(f"  Latest block: #{row[0]} hash={row[1]}... signed={row[2]} at {row[3]}")
except Exception:
    pass

conn.close()
print()
print("🎉 VAULT FILL COMPLETE")
