"""
Ember Wildfire Governance Bridge (Phase 3)
============================================
Connects wildfire assessment → risk policy → authorization FSM.

Flow:
    assessment → risk_tier → policy decision → create_action → approval
                                                              → authorize
"""
from __future__ import annotations

from perception.risk_policy import (
    compute_risk_tier, evaluate_policy, policy_hash, DEFAULT_POLICY,
)
from perception.authorization import create_action, get_action_state


def govern_wildfire_alert(alert: dict, action_type: str,
                          affected_population: int = 0) -> dict:
    """
    Take a wildfire alert and route it through the governance pipeline.

    Returns a governance result that includes:
        - risk_tier
        - policy_decision
        - action_id (if created)
        - required_approval
    """
    # 1. Extract signals from alert
    conf = alert.get("confidence", 0.0)
    chain = alert.get("chain", {})
    integrity_ok = bool(chain.get("signed")) and bool(chain.get("recorded"))
    support = len(alert.get("supporting_evidence", []))
    temporal = 0.7 if alert.get("calculations") else 0.3

    # 2. Compute risk tier
    tier_result = compute_risk_tier(
        evidence_confidence=conf,
        integrity_ok=integrity_ok,
        cross_sensor_agreement=support,
        temporal_persistence=temporal,
        action_reversibility="external_visible",
        affected_population=affected_population,
    )
    tier = tier_result["tier"]

    # 3. Evaluate policy
    policy_decision = evaluate_policy(action_type, tier, DEFAULT_POLICY)

    # 4. If approval required, create action
    action_result = None
    if policy_decision["decision"] == "hold":
        required = 1
        if policy_decision["required_approval"] == "two_person":
            required = 2
        elif policy_decision["required_approval"] == "emergency":
            required = 1

        action_result = create_action(
            action_type=action_type,
            incident_id=alert.get("incident_id"),
            risk_tier=tier,
            evidence_root=chain.get("block_hash"),
            policy_hash=policy_decision["policy_hash"],
            required_approvals=required,
            ttl_seconds=3600,
        )

    return {
        "risk_tier": tier,
        "tier_components": tier_result["components"],
        "policy_decision": policy_decision,
        "action": action_result,
        "assessment_passed": alert.get("assessment"),
        "requires_authorization": policy_decision["decision"] == "hold",
    }


if __name__ == "__main__":
    import tempfile
    import os
    import perception.authorization as auth
    auth.DB_PATH = tempfile.mktemp(suffix=".db")
    auth.init_auth_db()

    sample_alert = {
        "incident_id": "INC-P3-001",
        "assessment": "possible_smoke",
        "confidence": 0.75,
        "chain": {"signed": True, "recorded": True, "block_hash": "abc" * 20},
        "supporting_evidence": [1, 2],
        "calculations": [1],
    }
    result = govern_wildfire_alert(sample_alert, "notify_zone",
                                   affected_population=50)
    print("Tier:", result["risk_tier"])
    print("Policy decision:", result["policy_decision"]["decision"])
    print("Action:", result["action"])
