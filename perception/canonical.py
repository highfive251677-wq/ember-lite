"""
Canonical serialization for the evidence plane — single source of truth.
=========================================================================

The evidence-hash contract (docs/EVIDENCE_HASH_CONTRACT.md) pins exactly ONE
canonical serialization for every hash and every NEW signature:

    json.dumps(payload, sort_keys=True, separators=(",", ":"),
               ensure_ascii=False, default=str).encode("utf-8")

Properties: deterministic across processes and platforms, no whitespace
ambiguity, stable Unicode handling, and non-JSON types degrade explicitly
via str() instead of raising mid-hash.

The pre-contract serialization used by bridge_signatures v2.0 (default
separators, ensure_ascii=True) is LEGACY: verifiers still accept it for
historical artifacts, but nothing new may be produced with it.

Pure Python stdlib only.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_bytes(payload: Any) -> bytes:
    """
    THE canonical serialization: sorted keys, no whitespace, UTF-8.
    Same input always produces the same bytes on every platform.
    """
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    ).encode("utf-8")


def legacy_bytes(payload: Any) -> bytes:
    """
    v2.0 bridge_signatures serialization (default separators, ensure_ascii).
    Verification-only: accepted for historical signatures, never produced.
    """
    return json.dumps(payload, sort_keys=True).encode()


def hash_hex(payload: Any) -> str:
    """sha256 hex digest over the canonical serialization."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()
