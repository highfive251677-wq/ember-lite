"""
Ember Merkle Tree (Phase 6)
=============================
Minimal, auditable Merkle tree for evidence-chain batching.

Design:
    - SHA-256, canonical leaf ordering (ascending block_index)
    - Non-recursive construction (fits Tab A memory)
    - Proof generation and verification
    - No external dependencies

Why Merkle:
    A single daily root hash commits to every block in the chain.
    Anyone can verify any block is included without seeing the rest.

Pure Python stdlib only.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


# =========================================================
# HASHING
# =========================================================

def _hash_leaf(data: Any) -> str:
    """Leaf hash: SHA256(0x00 || canonical_bytes)."""
    if isinstance(data, (dict, list)):
        payload = json.dumps(
            data, sort_keys=True, separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    elif isinstance(data, bytes):
        payload = data
    else:
        payload = str(data).encode("utf-8")
    return hashlib.sha256(b"\x00" + payload).hexdigest()


def _hash_pair(left: str, right: str) -> str:
    """Internal node: SHA256(0x01 || left || right)."""
    return hashlib.sha256(
        b"\x01" + left.encode("ascii") + right.encode("ascii")
    ).hexdigest()


# =========================================================
# TREE CONSTRUCTION
# =========================================================

def build_tree(leaves: list[str]) -> list[list[str]]:
    """
    Build a Merkle tree bottom-up.

    Returns list of levels: levels[0] = leaf hashes,
    levels[-1] = [root].
    """
    if not leaves:
        return [[hashlib.sha256(b"\x00").hexdigest()]]

    current = list(leaves)
    levels = [current]

    while len(current) > 1:
        if len(current) % 2 == 1:
            # Duplicate last leaf (Bitcoin-style)
            current = current + [current[-1]]
        next_level = []
        for i in range(0, len(current), 2):
            next_level.append(_hash_pair(current[i], current[i + 1]))
        current = next_level
        levels.append(current)

    return levels


def root_hash(leaves: list[str]) -> str:
    levels = build_tree(leaves)
    return levels[-1][0]


# =========================================================
# PROOF
# =========================================================

def build_proof(leaves: list[str], index: int) -> list[dict]:
    """
    Build a Merkle proof for the leaf at `index`.

    Proof is a list of {position: 'left'|'right', hash: str}.
    """
    if not leaves:
        return []
    if index < 0 or index >= len(leaves):
        raise IndexError(f"index {index} out of range")

    levels = build_tree(leaves)
    proof = []
    idx = index

    for level in levels[:-1]:
        # Pad if needed
        if len(level) % 2 == 1:
            level = level + [level[-1]]

        if idx % 2 == 0:
            sibling_pos = "right"
            sibling_idx = idx + 1
        else:
            sibling_pos = "left"
            sibling_idx = idx - 1

        if sibling_idx < len(level):
            proof.append({
                "position": sibling_pos,
                "hash": level[sibling_idx],
            })

        idx = idx // 2

    return proof


def verify_proof(leaf: str, proof: list[dict], expected_root: str) -> bool:
    """Recompute the root from a leaf + proof and compare."""
    current = leaf
    for step in proof:
        if step["position"] == "left":
            current = _hash_pair(step["hash"], current)
        elif step["position"] == "right":
            current = _hash_pair(current, step["hash"])
        else:
            return False
    return current == expected_root


# =========================================================
# PUBLIC API
# =========================================================

def merkle_root_from_payloads(payloads: list[Any]) -> str:
    """Convenience: hash a list of payloads and return the root."""
    leaves = [_hash_leaf(p) for p in payloads]
    return root_hash(leaves)


def hash_leaf(data: Any) -> str:
    """Public wrapper for leaf hashing."""
    return _hash_leaf(data)


if __name__ == "__main__":
    # Smoke test
    payloads = [{"i": i, "v": f"obs-{i}"} for i in range(7)]
    leaves = [_hash_leaf(p) for p in payloads]
    root = root_hash(leaves)
    print("Root:", root[:24], "...")

    for i in range(len(leaves)):
        proof = build_proof(leaves, i)
        ok = verify_proof(leaves[i], proof, root)
        assert ok, f"proof failed for leaf {i}"
    print(f"✅ All {len(leaves)} proofs verified")

    # Tamper check
    bad_proof = build_proof(leaves, 0)
    bad_leaf = _hash_leaf({"tampered": True})
    assert not verify_proof(bad_leaf, bad_proof, root)
    print("✅ Tampered leaf rejected")
