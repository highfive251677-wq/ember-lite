"""
Ember Action Simulator (Phase 4)
==================================
Copilot Phase 4: Reversible-Action Simulator

Before allowing a real action, run it in simulation mode.

Safety Questions:
    1. Would this action affect external systems?
    2. Would it notify people?
    3. Would it be reversible?
    4. Which evidence and policy caused it?
    5. What if the evidence were stale?

KPI #2 (Human-in-Control): Action preview before approval.
Pure Python stdlib only.
"""

from __future__ import annotations

from typing import Any


# =========================================================
# ACTION CATALOG (what each action does)
# =========================================================

ACTION_CATALOG = {
    "store_observation": {
        "external_effect": False,
        "notifies_people": False,
        "reversible": True,
        "reversibility_class": "reversible",
        "activation": False,
        "cost_usd": 0.0,
        "affected_systems": [],
    },
    "emit_sensor_warning": {
        "external_effect": False,
        "notifies_people": False,
        "reversible": True,
        "reversibility_class": "reversible",
        "activation": False,
        "cost_usd": 0.0,
        "affected_systems": ["local_log"],
    },
    "notify_operator": {
        "external_effect": True,
        "notifies_people": True,
        "reversible": False,
        "reversibility_class": "external_visible",
        "activation": False,
        "cost_usd": 0.0,
        "affected_systems": ["operator_channel"],
    },
    "notify_zone": {
        "external_effect": True,
        "notifies_people": True,
        "reversible": False,
        "reversibility_class": "external_visible",
        "activation": False,
        "cost_usd": 0.0,
        "affected_systems": ["zone_owners", "notification_service"],
    },
    "dispatch_response": {
        "external_effect": True,
        "notifies_people": True,
        "reversible": False,
        "reversibility_class": "irreversible",
        "activation": True,
        "cost_usd": 500.0,
        "affected_systems": ["fire_department", "zone_owners",
                             "structure_defense"],
    },
    "activate_defense": {
        "external_effect": True,
        "notifies_people": True,
        "reversible": False,
        "reversibility_class": "irreversible",
        "activation": True,
        "cost_usd": 200.0,
        "affected_systems": ["structure_defense", "water_system",
                             "zone_owners"],
    },
    "emergency_containment": {
        "external_effect": True,
        "notifies_people": True,
        "reversible": False,
        "reversibility_class": "irreversible",
        "activation": True,
        "cost_usd": 5000.0,
        "affected_systems": ["emergency_services", "evacuation",
                             "structure_defense"],
    },
}


# =========================================================
# SIMULATE
# =========================================================

def simulate_action(
    action_type: str,
    risk_tier: str,
    evidence_reliability: float,
    policy_decision: dict,
    affected_population: int = 0,
    dry_run: bool = True,
) -> dict:
    """
    Simulate an action without executing it.

    Returns a structured report that answers all 5 safety questions.
    """
    catalog = ACTION_CATALOG.get(action_type)
    if catalog is None:
        return {
            "simulated": False,
            "error": f"unknown_action_type:{action_type}",
        }

    # Safety questions
    q1_external = catalog["external_effect"]
    q2_notifies = catalog["notifies_people"]
    q3_reversible = catalog["reversible"]
    q4_caused_by = {
        "risk_tier": risk_tier,
        "policy_id": policy_decision.get("policy_id"),
        "policy_hash": policy_decision.get("policy_hash", "")[:16],
        "evidence_reliability": evidence_reliability,
        "policy_decision": policy_decision.get("decision"),
    }
    q5_stale_scenario = _simulate_stale_scenario(
        action_type, evidence_reliability, policy_decision)

    # Compute a safety score
    safety_concerns = []
    if q1_external:
        safety_concerns.append("external_effect")
    if q2_notifies:
        safety_concerns.append("notifies_people")
    if not q3_reversible:
        safety_concerns.append("irreversible")
    if catalog["activation"]:
        safety_concerns.append("physical_activation")

    # Recommend
    if catalog["activation"]:
        recommendation = "REQUIRE_EXPLICIT_APPROVAL"
    elif q2_notifies:
        recommendation = "REQUIRE_APPROVAL"
    elif q1_external:
        recommendation = "REVIEW_BEFORE_EXECUTE"
    else:
        recommendation = "SAFE_TO_EXECUTE"

    return {
        "simulated": True,
        "dry_run": dry_run,
        "action_type": action_type,
        "risk_tier": risk_tier,
        "questions": {
            "affects_external_systems": q1_external,
            "notifies_people": q2_notifies,
            "is_reversible": q3_reversible,
            "caused_by": q4_caused_by,
            "stale_scenario": q5_stale_scenario,
        },
        "activation": catalog["activation"],
        "cost_usd": catalog["cost_usd"],
        "affected_systems": catalog["affected_systems"],
        "affected_population": affected_population,
        "safety_concerns": safety_concerns,
        "recommendation": recommendation,
    }


def _simulate_stale_scenario(
    action_type: str,
    current_reliability: float,
    policy_decision: dict,
) -> dict:
    """What would happen if the evidence were stale?"""
    degraded_reliability = current_reliability * 0.5
    would_hold = degraded_reliability < 0.40
    return {
        "reliability_if_stale": round(degraded_reliability, 3),
        "would_be_held": would_hold,
        "reason": (
            "reliability_below_threshold"
            if would_hold else "still_above_threshold"
        ),
    }


def format_simulation_report(sim: dict) -> str:
    """Human-readable simulation report."""
    if not sim.get("simulated"):
        return f"❌ Simulation failed: {sim.get('error')}"

    q = sim["questions"]
    lines = [
        "=" * 60,
        "  🔬 ACTION SIMULATION (DRY RUN)",
        "=" * 60,
        f"  Action:      {sim['action_type']}",
        f"  Risk Tier:   {sim['risk_tier']}",
        f"  Activation:  {sim['activation']}",
        f"  Cost:        ${sim['cost_usd']}",
        "",
        "  Safety Questions:",
        f"    External effect:   {q['affects_external_systems']}",
        f"    Notifies people:   {q['notifies_people']}",
        f"    Reversible:        {q['is_reversible']}",
        f"    Caused by policy:  {q['caused_by']['policy_id']}",
        f"    If evidence stale: {q['stale_scenario']['would_be_held']}",
        "",
        f"  Affected Systems:  {', '.join(sim['affected_systems']) or 'none'}",
        f"  Safety Concerns:   {', '.join(sim['safety_concerns']) or 'none'}",
        "",
        f"  ✅ Recommendation: {sim['recommendation']}",
        "=" * 60,
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sim = simulate_action(
        action_type="activate_defense",
        risk_tier="T4",
        evidence_reliability=0.75,
        policy_decision={
            "decision": "hold", "policy_id": "wildfire-v1",
            "policy_hash": "abc" * 20,
        },
        affected_population=50,
    )
    print(format_simulation_report(sim))
