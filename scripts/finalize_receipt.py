#!/data/data/com.termux/files/usr/bin/python3
"""Build receipt + insert into DB."""
import sys, sqlite3, json, hashlib
from pathlib import Path
from datetime import datetime, timezone

OP_DB = Path.home() / ".ember" / "ember_operational.db"
REPO = Path.home() / "ember-lite"
sys.path.insert(0, str(REPO))

def hdr(t):
    print(); print("=" * 60); print(f"  {t}"); print("=" * 60)


# ── 1. Rebuild receipt (get full dict) ────────────
hdr("1. BUILD RECEIPT")

from perception import action_contract

receipt = action_contract.issue_receipt(
    contract_id="anc-769bcba9cb19",
    execution_status="anchor_published",
)

print(f"  receipt_id:      {receipt.get('receipt_id')}")
print(f"  receipt_hash:    {receipt.get('receipt_hash', '')[:32]}...")
print(f"  signed:          {receipt.get('signed')}")
print(f"  keys:            {list(receipt.keys())}")
print()


# ── 2. Insert into receipts table ─────────────────
hdr("2. INSERT INTO RECEIPTS TABLE")

conn = sqlite3.connect(str(OP_DB))
cols = [d[1] for d in conn.execute("PRAGMA table_info(receipts)")]
print(f"  receipts columns: {cols}")

r_hash = receipt.get("receipt_hash")
if not r_hash:
    r_hash = hashlib.sha256(json.dumps(receipt, sort_keys=True, default=str).encode()).hexdigest()

existing = conn.execute(
    "SELECT receipt_hash FROM receipts WHERE receipt_hash=?", (r_hash,)
).fetchone()

if existing:
    print(f"  ⚠ Already present: {existing[0][:16]}...")
else:
    try:
        conn.execute("""
            INSERT INTO receipts
            (receipt_hash, action_id, receipt_json, receipt_signature, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            r_hash,
            receipt.get("action_id", "anc-769bcba9cb19"),
            json.dumps(receipt, default=str),
            receipt.get("signature") or receipt.get("receipt_signature"),
            receipt.get("created_at") or datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()
        print(f"  ✓ Receipt inserted: {r_hash[:16]}...")
    except Exception as e:
        print(f"  ⚠ {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()


# ── 3. Final vault status ─────────────────────────
hdr("3. FINAL VAULT STATUS")

targets = {"evidence_blocks": 13, "anchors": 1, "receipts": 1}
all_pass = True
for tbl, tgt in targets.items():
    n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    ok = n >= tgt
    all_pass = all_pass and ok
    print(f"  {'✅' if ok else '⏳'} {tbl:20s} {n:5d}  (target: {tgt})")

print()
print("=" * 60)
print("  🎉 VAULT COMPLETE" if all_pass else "  ⏳ VAULT PARTIAL")
print("=" * 60)

conn.close()
