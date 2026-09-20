#!/data/data/com.termux/files/usr/bin/python3
"""
Ember Vault Fill v2 — diagnostic + auto-migrate
"""
import sys, sqlite3, tempfile
from pathlib import Path

OP_DB = Path.home() / ".ember" / "ember_operational.db"
REPO = Path.home() / "ember-lite"
sys.path.insert(0, str(REPO))

print("=" * 60)
print("  EMBER VAULT FILL v2")
print("=" * 60)
print(f"OP_DB: {OP_DB}")
print()

# 1. Redirect tempfile
_orig = tempfile.mktemp
tempfile.mktemp = lambda *a, **k: str(OP_DB)

# 2. Import modules
from perception import evidence_chain, authorization, action_contract
from perception import replay
from perception.wave3_schema import init_wave_3_schema

# 3. Override DB_PATHs explicitly
for name, mod in [("evidence_chain", evidence_chain),
                  ("authorization", authorization),
                  ("action_contract", action_contract)]:
    print(f"  {name}.DB_PATH before: {getattr(mod, 'DB_PATH', 'N/A')}")
    if hasattr(mod, 'DB_PATH'):
        mod.DB_PATH = str(OP_DB)

print("  → All DB_PATHs overridden to OP_DB")
print()

# 4. Init schema, clear vault
conn = sqlite3.connect(str(OP_DB))
conn.execute("PRAGMA foreign_keys = ON")
init_wave_3_schema(conn)
for tbl in ["evidence_blocks", "anchors", "receipts"]:
    try: conn.execute(f"DELETE FROM {tbl}")
    except: pass
conn.commit()
conn.close()
print("✓ Wave 3 schema ready, vault cleared")
print()

# 5. Run replay
print("=" * 60)
print("  RUNNING REPLAY")
print("=" * 60)
try:
    result = replay.run_replay()
    if isinstance(result, dict):
        print(f"  passed: {result.get('passed')}/{result.get('total')}")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()
print()

tempfile.mktemp = _orig

# 6. Inventory
print("=" * 60)
print("  OP_DB TABLE INVENTORY")
print("=" * 60)
conn = sqlite3.connect(str(OP_DB))
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
for t in tables:
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:30s} {n:8d}")
    except Exception as e:
        print(f"  {t:30s} ERR: {e}")
print()

# 7. Auto-migrate chain → evidence_blocks
print("=" * 60)
print("  AUTO-MIGRATE: chain → evidence_blocks")
print("=" * 60)
chain_tables = [t for t in tables if "chain" in t.lower()]
print(f"  Candidates: {chain_tables}")

migrated = 0
for ct in chain_tables:
    try:
        cols = [d[0] for d in conn.execute(f"SELECT * FROM {ct} LIMIT 0").description]
        print(f"  {ct} cols: {cols}")
        
        m = {}
        for c in cols:
            lc = c.lower()
            if "block_index" in lc or lc == "idx": m["bi"] = c
            elif "observation_hash" in lc: m["oh"] = c
            elif "previous_hash" in lc or "prev" in lc: m["ph"] = c
            elif "block_hash" in lc or lc == "hash": m["bh"] = c
            elif "canonical" in lc or "payload" in lc: m["pl"] = c
            elif "signature" in lc or lc == "sig": m["sg"] = c
            elif "public_key" in lc or lc == "pub": m["pk"] = c
            elif "created_at" in lc or "timestamp" in lc: m["ca"] = c
        
        if "bi" not in m or "bh" not in m:
            print(f"  ⚠ {ct} missing block_index/block_hash")
            continue
        
        rows = conn.execute(f"SELECT * FROM {ct} ORDER BY {m['bi']}").fetchall()
        print(f"  Found {len(rows)} rows")
        
        for r in rows:
            d = dict(zip(cols, r))
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO evidence_blocks
                    (block_index, schema_version, observation_hash,
                     previous_hash, block_hash, canonical_payload,
                     signature, public_key, signed, created_at)
                    VALUES (?, '1.0', ?, ?, ?, ?, ?, ?, 1, ?)
                """, (
                    d.get(m["bi"]),
                    d.get(m.get("oh", ""), ""),
                    d.get(m.get("ph", ""), None),
                    d.get(m["bh"]),
                    d.get(m.get("pl", ""), ""),
                    d.get(m.get("sg", ""), None),
                    d.get(m.get("pk", ""), None),
                    d.get(m.get("ca", ""), None),
                ))
                migrated += 1
            except Exception as e:
                print(f"    block {d.get(m['bi'])}: {e}")
        
        conn.commit()
        print(f"  ✓ Migrated {migrated} rows")
    except Exception as e:
        print(f"  ERROR on {ct}: {e}")

print()

# 8. Final status
print("=" * 60)
print("  FINAL VAULT STATUS")
print("=" * 60)
for tbl in ["evidence_blocks", "anchors", "receipts"]:
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        mark = "✓" if n > 0 else "⚠"
        print(f"  {mark} {tbl:20s} {n:8d}")
    except Exception as e:
        print(f"  ❌ {tbl}: {e}")

conn.close()
print()
print("🎉 DONE")
