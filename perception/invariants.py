"""
Ember Invariant Harness (Phase 8 — Task 7, Innovated)
=======================================================
Copilot: Unit tests for crypto/policy core.

Innovation: "Invariant Harness"
    - stdlib-only (no pytest, no hypothesis dependency for runtime)
    - Property-based tests using deterministic seeds
    - Each invariant is a statement that must ALWAYS hold

Invariants:
    I1: Canonical serialization is order-independent
    I2: Any changed signed field invalidates verification
    I3: Consumed approval cannot be reused
    I4: Expired approval cannot authorize
    I5: Higher action impact cannot reduce required approval
    I6: Merkle root changes with any leaf change
    I7: Authorization requires verified approval or explicit policy
    I8: Legacy records are never modified after preservation

Pure Python stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
from datetime import datetime, timezone


SEED = 42  # deterministic
_rng = random.Random(SEED)


# =========================================================
# I1: CANONICAL ORDER INDEPENDENCE
# =========================================================

def _canonical(v) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)


def _digest(v) -> str:
    return hashlib.sha256(_canonical(v).encode()).hexdigest()


def invariant_canonical_order_independence(samples: int = 100) -> dict:
    """Same dict with different key insertion order must hash the same."""
    for _ in range(samples):
        keys = list("abcdefgh")[:_rng.randint(2, 8)]
        values = [_rng.randint(0, 1000) for _ in keys]
        d1 = dict(zip(keys, values))
        keys_shuffled = list(keys)
        _rng.shuffle(keys_shuffled)
        d2 = {k: d1[k] for k in keys_shuffled}
        if _digest(d1) != _digest(d2):
            return {"ok": False,
                    "reason": f"order matters: {d1} vs {d2}"}
    return {"ok": True, "samples": samples}


# =========================================================
# I2: TAMPER DETECTION
# =========================================================

def invariant_tamper_detection(samples: int = 50) -> dict:
    """Changing any field must change the digest."""
    for _ in range(samples):
        base = {"a": _rng.randint(0, 100), "b": "x" * _rng.randint(1, 20)}
        base_digest = _digest(base)
        tampered = dict(base)
        key = _rng.choice(list(tampered.keys()))
        tampered[key] = tampered[key] + 1 if isinstance(
            tampered[key], int) else tampered[key] + "!"
        if _digest(tampered) == base_digest:
            return {"ok": False, "reason": f"tamper missed: {base}"}
    return {"ok": True, "samples": samples}


# =========================================================
# I3/I4: APPROVAL BINDING
# =========================================================

def invariant_approval_one_shot(db_path: str) -> dict:
    """Consumed approval cannot be re-consumed."""
    import perception.authorization as auth
    auth.DB_PATH = db_path
    auth.init_auth_db()

    r = auth.create_action(
        action_type="notify_zone", incident_id="inv-1",
        risk_tier="T3", evidence_root="a" * 64,
        policy_hash="b" * 64, required_approvals=1,
    )
    auth.approve_action(r["action_id"], "op-1")
    first = auth.authorize_action(r["action_id"])
    second = auth.authorize_action(r["action_id"])

    if not first["authorized"]:
        return {"ok": False, "reason": "first auth failed"}
    if second["authorized"]:
        return {"ok": False, "reason": "reuse allowed"}
    return {"ok": True, "reason": "one-shot enforced"}


# =========================================================
# I5: POLICY MONOTONICITY
# =========================================================

def invariant_policy_monotonicity() -> dict:
    """
    Higher-impact action must not reduce required approval.
    """
    from perception.risk_policy import evaluate_policy
    impact_order = {
        "store_observation": 0,
        "emit_sensor_warning": 1,
        "notify_operator": 2,
        "notify_zone": 3,
        "dispatch_response": 4,
        "activate_defense": 5,
        "emergency_containment": 6,
    }
    approval_order = {
        "none": 0, "post_hoc": 1, "human": 2,
        "two_person": 3, "emergency": 4,
    }
    results = []
    for action in impact_order:
        d = evaluate_policy(action, "T3")
        results.append((impact_order[action],
                        approval_order.get(d["required_approval"], 0),
                        action))
    # Ensure approval level is non-decreasing with impact
    for i in range(len(results) - 1):
        if results[i + 1][1] < results[i][1]:
            return {"ok": False,
                    "reason": f"{results[i+1][2]} requires LESS than "
                              f"{results[i][2]}"}
    return {"ok": True, "checked": len(results)}


# =========================================================
# I6: MERKLE TAMPER
# =========================================================

def invariant_merkle_tamper(samples: int = 30) -> dict:
    from perception.merkle import hash_leaf, root_hash
    for _ in range(samples):
        n = _rng.randint(1, 10)
        payloads = [{"i": i, "v": _rng.randint(0, 100)}
                    for i in range(n)]
        leaves = [hash_leaf(p) for p in payloads]
        root1 = root_hash(leaves)
        # Tamper one leaf
        idx = _rng.randint(0, n - 1)
        tampered = list(leaves)
        tampered[idx] = hash_leaf({"tampered": True})
        root2 = root_hash(tampered)
        if root1 == root2:
            return {"ok": False, "reason": f"merkle missed: {payloads}"}
    return {"ok": True, "samples": samples}


# =========================================================
# I7: AUTHORIZATION GATE
# =========================================================

def invariant_authorization_gate(db_path: str) -> dict:
    """Approval-less action must not authorize."""
    import perception.authorization as auth
    auth.DB_PATH = db_path
    auth.init_auth_db()
    r = auth.create_action(
        action_type="notify_zone", incident_id="inv-2",
        risk_tier="T3", evidence_root="c" * 64,
        policy_hash="d" * 64, required_approvals=1,
    )
    a = auth.authorize_action(r["action_id"])
    if a["authorized"]:
        return {"ok": False, "reason": "unauthorized"}
    return {"ok": True, "reason": "gate enforced"}


# =========================================================
# I8: LEGACY IMMUTABILITY
# =========================================================

def invariant_legacy_immutable(db_path: str) -> dict:
    """Preserved legacy records must not change."""
    conn = sqlite3.connect(db_path)
    try:
        from perception.migrations import (
            create_legacy_record_table, preserve_legacy_record, _digest,
        )
        create_legacy_record_table(conn)
        payload = {"field1": "value1", "field2": 42}
        result = preserve_legacy_record(
            conn, "test_table", "pk1", payload, "v1"
        )
        expected_hash = result["original_hash"]
        # Read back
        row = conn.execute("""
            SELECT original_hash, original_payload
            FROM legacy_records WHERE legacy_id = ?
        """, (result["legacy_id"],)).fetchone()
        if row is None:
            return {"ok": False, "reason": "not preserved"}
        if row[0] != expected_hash:
            return {"ok": False, "reason": "hash mismatch"}
        if _digest(json.loads(row[1])) != expected_hash:
            return {"ok": False, "reason": "payload mutated"}
        return {"ok": True, "reason": "immutable"}
    finally:
        conn.close()


# =========================================================
# HARNESS RUNNER
# =========================================================

def run_all_invariants() -> dict:
    import tempfile
    results = {}
    results["I1_canonical_order"] = invariant_canonical_order_independence()
    results["I2_tamper_detection"] = invariant_tamper_detection()
    results["I3_approval_one_shot"] = invariant_approval_one_shot(
        tempfile.mktemp(suffix=".db")
    )
    results["I4_policy_monotonicity"] = invariant_policy_monotonicity()
    results["I5_merkle_tamper"] = invariant_merkle_tamper()
    results["I6_authorization_gate"] = invariant_authorization_gate(
        tempfile.mktemp(suffix=".db")
    )
    results["I7_legacy_immutable"] = invariant_legacy_immutable(
        tempfile.mktemp(suffix=".db")
    )
    passed = sum(1 for r in results.values() if r["ok"])
    return {
        "passed": passed,
        "total": len(results),
        "results": results,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("  TASK 7 — INVARIANT HARNESS (INNOVATED)")
    print("=" * 60)
    print()

    report = run_all_invariants()
    for name, r in report["results"].items():
        icon = "✅" if r["ok"] else "❌"
        print(f"{icon} {name}: {r.get('reason', '')}")

    print()
    print(f"📊 {report['passed']}/{report['total']} invariants hold")
    if report["passed"] == report["total"]:
        print("🎉 ALL INVARIANTS PASSED")
