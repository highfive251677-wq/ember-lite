#!/data/data/com.termux/files/usr/bin/python3
"""
Ember Orchestrator v2 — Full Vault Pipeline
==============================================
One script to rule them all:
  1. Setup paths + override DB_PATHs
  2. Init Wave 3 schema
  3. Run Phase 5 replay (13 scenarios)
  4. Migrate chain → evidence_blocks
  5. Build anchor (Merkle + Ed25519)
  6. Build receipt
  7. Final verification

Idempotent, safe, and pure stdlib.
"""
from __future__ import annotations

import sys
import sqlite3
import tempfile
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone


# ══════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════

EMBER_HOME = Path.home() / ".ember"
EMBER_HOME.mkdir(exist_ok=True)
OP_DB = EMBER_HOME / "ember_operational.db"
REPO = Path.home() / "ember-lite"
DEVICE_ID = "ember-tab-a"

sys.path.insert(0, str(REPO))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hdr(title: str):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


# ══════════════════════════════════════════════════════
# PHASE 0: Redirect tempfile + override DB_PATHs
# ══════════════════════════════════════════════════════

_hdr("PHASE 0 — SETUP")

_orig_mktemp = tempfile.mktemp
tempfile.mktemp = lambda *a, **k: str(OP_DB)
print(f"  ✓ tempfile redirected → {OP_DB.name}")

from perception import (
    evidence_chain,
    authorization,
    action_contract,
    replay,
    merkle,
    anchoring,
)
from perception.wave3_schema import init_wave_3_schema

for name, mod in [
    ("evidence_chain", evidence_chain),
    ("authorization", authorization),
    ("action_contract", action_contract),
    ("merkle", merkle),
    ("anchoring", anchoring),
]:
    if hasattr(mod, "DB_PATH"):
        old = mod.DB_PATH
        mod.DB_PATH = str(OP_DB)
        print(f"  ✓ {name}.DB_PATH: {Path(old).name} → {OP_DB.name}")


# ══════════════════════════════════════════════════════
# PHASE 1: Schema init + vault clear
# ══════════════════════════════════════════════════════

_hdr("PHASE 1 — SCHEMA INIT")

conn = sqlite3.connect(str(OP_DB))
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA journal_mode = WAL")
init_wave_3_schema(conn)

for tbl in ["evidence_blocks", "anchors", "receipts"]:
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        if n > 0:
            conn.execute(f"DELETE FROM {tbl}")
            print(f"  Cleared {tbl}: {n} rows")
    except sqlite3.OperationalError:
        pass
conn.commit()
print("  ✓ Wave 3 schema ready")


# ══════════════════════════════════════════════════════
# PHASE 2: Run replay
# ══════════════════════════════════════════════════════

_hdr("PHASE 2 — REPLAY")

replay_result = None
try:
    replay_result = replay.run_replay()
    if isinstance(replay_result, dict):
        print(f"  ✓ Replay: {replay_result.get('passed')}/{replay_result.get('total')} passed")
except Exception as e:
    print(f"  ⚠ Replay error: {type(e).__name__}: {e}")
    import traceback; traceback.print_exc()

tempfile.mktemp = _orig_mktemp


# ══════════════════════════════════════════════════════
# PHASE 3: Migrate chain → evidence_blocks
# ══════════════════════════════════════════════════════

_hdr("PHASE 3 — MIGRATE chain → evidence_blocks")

migrated = 0
try:
    rows = conn.execute("""
        SELECT id, block_index, schema_version, observation_hash,
               previous_hash, block_hash, canonical_payload,
               signature, public_key, key_id, terminal,
               signed, verified, anchored, created_at
        FROM chain
        ORDER BY block_index
    """).fetchall()

    for r in rows:
        (legacy_id, block_index, schema_version, observation_hash,
         previous_hash, block_hash, canonical_payload,
         signature, public_key, key_id, terminal,
         signed, verified, anchored, created_at) = r

        try:
            conn.execute("""
                INSERT OR IGNORE INTO evidence_blocks
                (block_index, schema_version, observation_hash,
                 previous_hash, block_hash, canonical_payload,
                 signature, public_key, signed, verified, anchored,
                 created_at, legacy_source_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                block_index,
                schema_version or "1.0",
                observation_hash,
                previous_hash,
                block_hash,
                canonical_payload,
                signature,
                public_key,
                signed or 0,
                verified or 0,
                anchored or 0,
                created_at,
                legacy_id,
            ))
            migrated += 1
        except sqlite3.OperationalError as e:
            print(f"  ⚠ block {block_index}: {e}")

    conn.commit()
    print(f"  ✓ Migrated: {migrated} blocks")
except Exception as e:
    print(f"  ⚠ Migration error: {e}")


# ══════════════════════════════════════════════════════
# PHASE 4: Build anchor
# ══════════════════════════════════════════════════════

_hdr("PHASE 4 — BUILD ANCHOR")

anchor_result = None
try:
    # Discover anchor function
    fn = None
    for name in ["anchor_chain", "build_anchor", "create_anchor"]:
        if hasattr(anchoring, name):
            fn = getattr(anchoring, name)
            print(f"  Using anchoring.{name}()")
            break

    if fn:
        try:
            anchor_result = fn(device_id=DEVICE_ID)
        except TypeError:
            try:
                anchor_result = fn(DEVICE_ID)
            except TypeError:
                anchor_result = fn()

        if isinstance(anchor_result, dict):
            print(f"  ✓ Anchor: {anchor_result.get('anchor_id', 'unknown')}")
            print(f"    Merkle root: {str(anchor_result.get('merkle_root', ''))[:32]}...")
            print(f"    Block count: {anchor_result.get('block_count', '?')}")
        else:
            print(f"  ✓ Anchor result: {anchor_result}")
    else:
        print(f"  ⚠ No anchor function found")
        print(f"    anchoring API: {[x for x in dir(anchoring) if not x.startswith('_')][:20]}")
except Exception as e:
    print(f"  ⚠ Anchor error: {type(e).__name__}: {e}")
    import traceback; traceback.print_exc()


# ══════════════════════════════════════════════════════
# PHASE 5: Build receipt
# ══════════════════════════════════════════════════════

_hdr("PHASE 5 — BUILD RECEIPT")

receipt_result = None
if anchor_result and isinstance(anchor_result, dict):
    anchor_id = anchor_result.get("anchor_id")
    try:
        fn = None
        for name in ["issue_receipt", "build_receipt", "create_receipt"]:
            if hasattr(action_contract, name):
                fn = getattr(action_contract, name)
                print(f"  Using action_contract.{name}()")
                break

        if fn and anchor_id:
            try:
                receipt_result = fn(action_id=anchor_id)
            except TypeError:
                try:
                    receipt_result = fn(anchor_id)
                except TypeError:
                    receipt_result = fn()
            print(f"  ✓ Receipt: {receipt_result}")
        else:
            print(f"  ⚠ No receipt function or no anchor_id")
    except Exception as e:
        print(f"  ⚠ Receipt error: {type(e).__name__}: {e}")
else:
    print(f"  ⏭ Skipped (no anchor)")


# ══════════════════════════════════════════════════════
# PHASE 6: Final verification
# ══════════════════════════════════════════════════════

_hdr("PHASE 6 — FINAL VAULT STATUS")

targets = {
    "evidence_blocks": 13,
    "anchors": 1,
    "receipts": 1,
}

all_pass = True
for tbl, target in targets.items():
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        status = "✅" if n >= target else "⏳"
        if n < target:
            all_pass = False
        print(f"  {status} {tbl:20s} {n:5d}  (target: {target})")
    except sqlite3.OperationalError as e:
        print(f"  ❌ {tbl}: {e}")
        all_pass = False

# Show chain integrity
print()
try:
    first = conn.execute(
        "SELECT block_index, substr(block_hash,1,16) FROM evidence_blocks ORDER BY block_index LIMIT 1"
    ).fetchone()
    last = conn.execute(
        "SELECT block_index, substr(block_hash,1,16) FROM evidence_blocks ORDER BY block_index DESC LIMIT 1"
    ).fetchone()
    if first and last:
        print(f"  Chain: #{first[0]} ({first[1]}...) → #{last[0]} ({last[1]}...)")
        print(f"  Length: {last[0] - first[0] + 1} blocks")
except Exception:
    pass

# Show anchor if present
print()
try:
    anchor = conn.execute(
        "SELECT anchor_id, block_count, substr(merkle_root,1,16) FROM anchors LIMIT 1"
    ).fetchone()
    if anchor:
        print(f"  Anchor: {anchor[0]}")
        print(f"  Merkle: {anchor[2]}...")
        print(f"  Blocks: {anchor[1]}")
except Exception:
    pass

conn.close()

print()
print("=" * 60)
if all_pass:
    print("  🎉 VAULT COMPLETE")
else:
    print("  ⏳ VAULT PARTIAL — check output above")
print("=" * 60)


# ══════════════════════════════════════════════════════
# CLI ENTRY
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    pass
