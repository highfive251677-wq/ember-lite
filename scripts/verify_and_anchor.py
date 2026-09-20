#!/data/data/com.termux/files/usr/bin/python3
"""Verify vault + build anchor + receipt."""
import sys, sqlite3, json
from pathlib import Path

OP_DB = Path.home() / ".ember" / "ember_operational.db"
REPO = Path.home() / "ember-lite"
sys.path.insert(0, str(REPO))

print("=" * 60)
print("  1. VERIFY EVIDENCE_BLOCKS")
print("=" * 60)

conn = sqlite3.connect(str(OP_DB))
total = conn.execute("SELECT COUNT(*) FROM evidence_blocks").fetchone()[0]
signed = conn.execute("SELECT COUNT(*) FROM evidence_blocks WHERE signed=1").fetchone()[0]
has_hash = conn.execute("SELECT COUNT(*) FROM evidence_blocks WHERE block_hash IS NOT NULL").fetchone()[0]
print(f"  Total: {total}")
print(f"  Signed: {signed}")
print(f"  With block_hash: {has_hash}")

first = conn.execute("SELECT block_index, substr(block_hash,1,16) FROM evidence_blocks ORDER BY block_index LIMIT 1").fetchone()
last = conn.execute("SELECT block_index, substr(block_hash,1,16) FROM evidence_blocks ORDER BY block_index DESC LIMIT 1").fetchone()
print(f"  First: #{first[0]} {first[1]}...")
print(f"  Last:  #{last[0]} {last[1]}...")
print()

print("=" * 60)
print("  2. DISCOVER API")
print("=" * 60)

from perception import merkle, anchoring

merkle_api = [x for x in dir(merkle) if not x.startswith("_") and callable(getattr(merkle, x))]
print(f"  merkle.py: {merkle_api}")

anchoring_api = [x for x in dir(anchoring) if not x.startswith("_") and callable(getattr(anchoring, x))]
print(f"  anchoring.py: {anchoring_api}")
print()

# Override DB_PATHs
merkle.DB_PATH = str(OP_DB) if hasattr(merkle, 'DB_PATH') else None
anchoring.DB_PATH = str(OP_DB) if hasattr(anchoring, 'DB_PATH') else None

print("=" * 60)
print("  3. BUILD ANCHOR")
print("=" * 60)

# Try common function names
result = None
for fn_name in ["anchor_chain", "build_anchor", "create_anchor"]:
    if hasattr(anchoring, fn_name):
        fn = getattr(anchoring, fn_name)
        print(f"  Using anchoring.{fn_name}()")
        try:
            # Try with device_id
            try:
                result = fn(device_id="ember-tab-a")
            except TypeError:
                try:
                    result = fn("ember-tab-a")
                except TypeError:
                    result = fn()
            print(f"  Result: {result}")
            break
        except Exception as e:
            print(f"  ⚠ {fn_name}: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()

print()

print("=" * 60)
print("  4. BUILD RECEIPT")
print("=" * 60)

# Look for receipt builder
try:
    from perception import action_contract
    action_contract.DB_PATH = str(OP_DB)
    ac_api = [x for x in dir(action_contract) if not x.startswith("_") and callable(getattr(action_contract, x))]
    print(f"  action_contract.py: {ac_api}")
    
    for fn_name in ["issue_receipt", "build_receipt", "create_receipt"]:
        if hasattr(action_contract, fn_name):
            fn = getattr(action_contract, fn_name)
            print(f"  Using action_contract.{fn_name}()")
            try:
                result = fn(anchor_id="anc-001")
                print(f"  Result: {result}")
                break
            except Exception as e:
                print(f"  ⚠ {fn_name}: {type(e).__name__}: {e}")
except Exception as e:
    print(f"  ⚠ {e}")

print()

print("=" * 60)
print("  5. FINAL VAULT STATUS")
print("=" * 60)

for tbl in ["evidence_blocks", "anchors", "receipts"]:
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        mark = "✅" if n > 0 else "⏳"
        print(f"  {mark} {tbl:20s} {n:8d}")
    except Exception as e:
        print(f"  ❌ {tbl}: {e}")

conn.close()
print()
print("🎉 DONE")
