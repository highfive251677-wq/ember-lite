"""
Ember Risk Policy Engine (Phase 3 — Tiered Governance)
=========================================================
Copilot Phase 3: Tiered Risk-Based Governance

Core Principle:
    Policies are ACTION-BASED, not merely severity-based.
    A "high severity" observation does not tell us whether
    the proposed ACTION is reversible, visible, or consequential.

Risk Tiers:
    T0 — Informational           (auto-allowed)
    T1 — Low-risk automated      (auto-allowed within limits)
    T2 — Review required         (allowed, post-hoc review)
    T3 — Explicit human approval (blocked until approved)
    T4 — Multi-party approval    (blocked until 2+ approvals)
    T5 — Emergency containment   (pre-authorized narrowly)

Pure Python stdlib only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Any


# =========================================================
# CANONICAL SERIALIZATION
# =========================================================

def _canonical_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    ).encode("utf-8")


def _hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# =========================================================
# RISK TIERS
# =========================================================

TIERS = {
    "T0": {"name": "Informational", "approval": "none",
           "description": "Store observation, no external effect"},
    "T1": {"name": "Low-risk automated", "approval": "none",
           "description": "Local diagnostic, retry, cache cleanup"},
    "T2": {"name": "Review required", "approval": "post_hoc",
           "description": "Notify operator, log warning"},
    "T3": {"name": "Explicit human approval", "approval": "human",
           "description": "Notify zone, change config, escalate"},
    "T4": {"name": "Multi-party approval", "approval": "two_person",
           "description": "Dispatch response, activate defense"},
    "T5": {"name": "Emergency containment", "approval": "emergency",
           "description": "Narrowly pre-authorized protective action"},
}

TIER_ORDER = ["T0", "T1", "T2", "T3", "T4", "T5"]


# =========================================================
# DEFAULT POLICY (Wildfire v1)
# =========================================================

DEFAULT_POLICY = {
    "policy_id": "wildfire-v1",
    "version": 3,
    "rules": [
        {"action": "store_observation",   "max_tier": "T0", "approval": "none"},
        {"action": "emit_sensor_warning", "max_tier": "T1", "approval": "none"},
        {"action": "notify_operator",     "max_tier": "T2", "approval": "post_hoc"},
        {"action": "notify_zone",         "max_tier": "T3", "approval": "human"},
        {"action": "dispatch_response",   "max_tier": "T4", "approval": "two_person"},
        {"action": "activate_defense",    "max_tier": "T4", "approval": "two_person"},
        {"action": "emergency_containment","max_tier": "T5", "approval": "emergency"},
    ],
}


def policy_hash(policy: dict | None = None) -> str:
    """Compute the canonical policy hash."""
    return _hash(policy or DEFAULT_POLICY)


# =========================================================
# TIER COMPUTATION (multi-dimensional)
# =========================================================

def _tier_index(tier: str) -> int:
    try:
        return TIER_ORDER.index(tier)
    except ValueError:
        return 0


def _tier_from_index(idx: int) -> str:
    idx = max(0, min(idx, len(TIER_ORDER) - 1))
    return TIER_ORDER[idx]


def compute_risk_tier(
    evidence_confidence: float = 0.0,
    integrity_ok: bool = False,
    cross_sensor_agreement: int = 0,
    temporal_persistence: float = 0.0,
    action_reversibility: str = "reversible",
    affected_population: int = 0,
) -> dict:
    """
    Compute the risk tier using multi-dimensional factors.

    Returns a dict with:
        - tier: T0..T5
        - components: individual contributions
        - reasons: human-readable explanations

    Note: tier = MAX(evidence_risk, action_risk, integrity_risk, impact_risk)
    """
    evidence_risk = 0
    if evidence_confidence >= 0.85 and cross_sensor_agreement >= 2:
        evidence_risk = 3
    elif evidence_confidence >= 0.70:
        evidence_risk = 2
    elif evidence_confidence >= 0.50:
        evidence_risk = 1
    else:
        evidence_risk = 0

    integrity_risk = 0 if integrity_ok else 3  # unsigned = high risk

    temporal_risk = 0
    if temporal_persistence >= 0.8:
        temporal_risk = 2
    elif temporal_persistence >= 0.5:
        temporal_risk = 1

    action_risk_map = {
        "reversible": 0,
        "external_visible": 1,
        "irreversible": 3,
    }
    action_risk = action_risk_map.get(action_reversibility, 3)

    impact_risk = 0
    if affected_population >= 1000:
        impact_risk = 3
    elif affected_population >= 100:
        impact_risk = 2
    elif affected_population >= 10:
        impact_risk = 1

    final_idx = max(evidence_risk, integrity_risk, temporal_risk,
                    action_risk, impact_risk)
    tier = _tier_from_index(final_idx)

    return {
        "tier": tier,
        "components": {
            "evidence": _tier_from_index(evidence_risk),
            "integrity": _tier_from_index(integrity_risk),
            "temporal": _tier_from_index(temporal_risk),
            "action": _tier_from_index(action_risk),
            "impact": _tier_from_index(impact_risk),
        },
        "reasons": [
            f"evidence={evidence_risk}",
            f"integrity={integrity_risk}",
            f"temporal={temporal_risk}",
            f"action={action_risk}",
            f"impact={impact_risk}",
        ],
    }


# =========================================================
# POLICY EVALUATION
# =========================================================

def evaluate_policy(
    action: str,
    tier: str,
    policy: dict | None = None,
    ttl_seconds: int = 3600,
) -> dict:
    """
    Evaluate whether an action is allowed at this tier.

    Returns:
        decision: allow | deny | hold
        required_approval: none | post_hoc | human | two_person | emergency
        policy_hash, policy_id, tier, expires_at, reasons
    """
    policy = policy or DEFAULT_POLICY
    phash = policy_hash(policy)

    rule = None
    for r in policy.get("rules", []):
        if r.get("action") == action:
            rule = r
            break

    if rule is None:
        return {
            "decision": "deny",
            "risk_tier": tier,
            "required_approval": "human",
            "policy_id": policy.get("policy_id", "unknown"),
            "policy_hash": phash,
            "reasons": [f"no_rule_for_action:{action}"],
            "expires_at": None,
        }

    max_tier = rule.get("max_tier", "T3")
    approval = rule.get("approval", "human")

    if _tier_index(tier) > _tier_index(max_tier):
        return {
            "decision": "deny",
            "risk_tier": tier,
            "required_approval": "human",
            "policy_id": policy["policy_id"],
            "policy_hash": phash,
            "reasons": [f"tier_{tier}_exceeds_max_{max_tier}"],
            "expires_at": None,
        }

    if approval == "none":
        decision = "allow"
    elif approval == "post_hoc":
        decision = "allow"
    else:
        decision = "hold"

    expires_at = (_now() + timedelta(seconds=ttl_seconds)).isoformat()

    return {
        "decision": decision,
        "risk_tier": tier,
        "required_approval": approval,
        "policy_id": policy["policy_id"],
        "policy_hash": phash,
        "reasons": [f"action={action}", f"tier={tier}", f"approval={approval}"],
        "expires_at": expires_at,
    }


if __name__ == "__main__":
    print("Risk Policy Engine v1")
    print("Policy hash:", policy_hash()[:16])
    print()
    result = compute_risk_tier(
        evidence_confidence=0.75, integrity_ok=True,
        cross_sensor_agreement=1, temporal_persistence=0.7,
        action_reversibility="external_visible", affected_population=50,
    )
    print("Tier:", result["tier"])
    print("Components:", result["components"])
    print()
    decision = evaluate_policy("notify_zone", result["tier"])
    print("Decision:", decision["decision"])
    print("Required approval:", decision["required_approval"])
