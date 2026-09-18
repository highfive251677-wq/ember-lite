"""
Ember Federated Verification (Phase 6)
========================================
Cross-device verification of anchor commitments.

Model:
    Device A produces an anchor (merkle_root, sequence, hash).
    Device B (or any verifier) checks:
        1. Anchor is signed and hash-valid.
        2. Merkle root matches the batch of blocks it claims.
        3. Optionally: 2+ devices agree on the same root (quorum).

Note:
    This is NOT consensus. It is cross-verification.
    No blockchain node. No vote. Just independent checks.

Pure Python stdlib only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from perception.merkle import hash_leaf, root_hash


def _hash(p: Any) -> str:
    return hashlib.sha256(
        json.dumps(p, sort_keys=True, separators=(",", ":"),
                   default=str).encode()
    ).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =========================================================
# SINGLE ANCHOR VERIFICATION
# =========================================================

def verify_anchor_bundle(
    anchor: dict,
    block_hashes: list[str] | None = None,
) -> dict:
    """
    Verify an anchor commitment object.

    If block_hashes is provided, recompute the Merkle root
    from the claimed leaves and compare.
    """
    required = [
        "anchor_id", "schema_version", "device_id", "sequence_number",
        "merkle_root", "first_block_index", "last_block_index",
        "block_count", "previous_anchor_hash", "created_at",
        "anchor_hash",
    ]
    for k in required:
        if k not in anchor:
            return {"valid": False, "reason": f"missing_field:{k}"}

    # 1. Recompute anchor hash
    canonical = {k: anchor[k] for k in required if k != "anchor_hash"}
    recomputed = _hash(canonical)
    hash_ok = recomputed == anchor["anchor_hash"]

    # 2. Signature
    sig_ok = False
    if anchor.get("signature") and anchor.get("public_key"):
        try:
            from perception.bridge_signatures import verify
            sig_ok = verify(canonical, anchor["signature"],
                            anchor["public_key"])
        except Exception:
            sig_ok = False

    # 3. Merkle root recomputation (if leaves provided)
    merkle_ok = None
    if block_hashes is not None:
        if len(block_hashes) != anchor.get("block_count"):
            merkle_ok = False
        else:
            leaves = [hash_leaf(bh) for bh in block_hashes]
            merkle_ok = root_hash(leaves) == anchor["merkle_root"]

    return {
        "valid": hash_ok and sig_ok and (merkle_ok is not False),
        "hash_ok": hash_ok,
        "signature_ok": sig_ok,
        "merkle_ok": merkle_ok,
        "anchor_id": anchor["anchor_id"],
        "device_id": anchor["device_id"],
        "sequence_number": anchor["sequence_number"],
    }


# =========================================================
# QUORUM (cross-device agreement)
# =========================================================

def quorum_check(
    anchor_bundles: list[dict],
    min_agreement: int = 2,
) -> dict:
    """
    Check whether at least min_agreement independent devices
    agree on the same merkle_root at the same sequence.

    anchor_bundles: list of anchor dicts from various devices.
    """
    if not anchor_bundles:
        return {"quorum": False, "reason": "no_anchors",
                "agreement": 0, "total": 0}

    # Group by (sequence_number, merkle_root)
    groups: dict[tuple, list[str]] = {}
    for a in anchor_bundles:
        key = (a.get("sequence_number"), a.get("merkle_root"))
        groups.setdefault(key, []).append(a.get("device_id", "?"))

    # Find best group
    best_key = None
    best_devices = []
    for key, devs in groups.items():
        unique_devs = sorted(set(devs))
        if len(unique_devs) > len(best_devices):
            best_key = key
            best_devices = unique_devs

    agreement = len(best_devices)
    has_quorum = agreement >= min_agreement

    return {
        "quorum": has_quorum,
        "agreement": agreement,
        "total": len(anchor_bundles),
        "min_required": min_agreement,
        "agreed_on": {
            "sequence_number": best_key[0] if best_key else None,
            "merkle_root": best_key[1] if best_key else None,
        } if best_key else None,
        "devices": best_devices,
        "checked_at": _now_iso(),
    }


# =========================================================
# CONFLICT DETECTION
# =========================================================

def detect_conflict(anchor_a: dict, anchor_b: dict) -> dict:
    """
    Two anchors with the same sequence but different roots = conflict.
    """
    if anchor_a.get("sequence_number") != anchor_b.get("sequence_number"):
        return {"conflict": False, "reason": "different_sequence"}

    same_root = anchor_a.get("merkle_root") == anchor_b.get("merkle_root")
    return {
        "conflict": not same_root,
        "reason": "same_root" if same_root else "root_mismatch",
        "sequence_number": anchor_a.get("sequence_number"),
        "root_a": anchor_a.get("merkle_root"),
        "root_b": anchor_b.get("merkle_root"),
        "device_a": anchor_a.get("device_id"),
        "device_b": anchor_b.get("device_id"),
    }


if __name__ == "__main__":
    # Simulate 3 devices with matching roots
    root = "a" * 64
    devices = ["tab-a-2017", "matebook-d14", "cloud-runner-1"]
    bundles = []
    for i, dev in enumerate(devices):
        a = {
            "anchor_id": f"anc-{i}",
            "schema_version": "1.0",
            "device_id": dev,
            "sequence_number": 1,
            "merkle_root": root,
            "first_block_index": 1,
            "last_block_index": 3,
            "block_count": 3,
            "previous_anchor_hash": None,
            "created_at": _now_iso(),
        }
        a["anchor_hash"] = _hash(a)
        bundles.append(a)

    q = quorum_check(bundles, min_agreement=2)
    print("Quorum:", q["quorum"], "agreement:", q["agreement"])

    # Inject a conflicting anchor
    bad = dict(bundles[0])
    bad["anchor_id"] = "anc-bad"
    bad["device_id"] = "rogue-device"
    bad["merkle_root"] = "b" * 64
    bad["anchor_hash"] = _hash({k: bad[k] for k in bad if k != "anchor_hash"})

    conflict = detect_conflict(bundles[0], bad)
    print("Conflict:", conflict["conflict"], "reason:", conflict["reason"])
