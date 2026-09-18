"""
Ember Wildfire Gate
===================

Wildfire-specific six-dimension decision gate.

Does NOT import or modify perception.release_gate.py.
Follows same six-gate structure with wildfire semantics:

1. Evidence Quality
2. Sensor Health
3. Corroboration
4. Temporal Consistency
5. Policy Compliance
6. Human Approval Status

The gate does NOT declare that a wildfire exists. It evaluates whether
the available evidence is sufficient for the proposed operational assessment.
"""

from __future__ import annotations

from typing import Any


GATES = {
    "evidence_quality": {"name": "Evidence Quality", "weight": 25},
    "sensor_health": {"name": "Sensor Health", "weight": 20},
    "corroboration": {"name": "Corroboration", "weight": 20},
    "temporal_consistency": {"name": "Temporal Consistency", "weight": 15},
    "policy_compliance": {"name": "Policy Compliance", "weight": 10},
    "human_approval": {"name": "Human Approval Status", "weight": 10},
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(100.0, number))


def _gate(name: str, score: float, passed: bool, details: dict) -> dict:
    return {
        "gate": name,
        "status": "PASS" if passed else "FAIL",
        "score": int(round(_number(score))),
        "details": details,
    }


def evaluate_wildfire_gate(context: dict | None = None) -> dict:
    """
    Evaluate wildfire evidence using six dimensions.

    Expected context keys (all optional — missing = unknown):
        evidence_quality, sensor_health, corroboration,
        temporal_consistency, policy_compliance,
        human_approval, requires_human_approval
    """
    context = context or {}

    evidence_quality = _number(context.get("evidence_quality"))
    sensor_health = _number(context.get("sensor_health"))
    corroboration = _number(context.get("corroboration"))
    temporal_consistency = _number(context.get("temporal_consistency"))
    policy_compliance = _number(context.get("policy_compliance"))

    requires_approval = bool(context.get("requires_human_approval", False))
    approval_value = context.get("human_approval")

    if approval_value is None:
        human_approval = 0.0 if requires_approval else 100.0
        approval_known = not requires_approval
    else:
        human_approval = _number(approval_value)
        approval_known = True

    results = [
        _gate("evidence_quality", evidence_quality,
              evidence_quality >= 70,
              {"score": evidence_quality, "threshold": 70}),
        _gate("sensor_health", sensor_health,
              sensor_health >= 70,
              {"score": sensor_health, "threshold": 70}),
        _gate("corroboration", corroboration,
              corroboration >= 60,
              {"score": corroboration, "threshold": 60}),
        _gate("temporal_consistency", temporal_consistency,
              temporal_consistency >= 60,
              {"score": temporal_consistency, "threshold": 60}),
        _gate("policy_compliance", policy_compliance,
              policy_compliance >= 100,
              {"score": policy_compliance, "threshold": 100}),
        _gate("human_approval", human_approval,
              approval_known and human_approval >= 100,
              {"score": human_approval, "required": requires_approval,
               "known": approval_known,
               "threshold": 100 if requires_approval else 0}),
    ]

    total_weight = sum(GATES[item["gate"]]["weight"] for item in results)
    weighted_score = sum(
        item["score"] * GATES[item["gate"]]["weight"] for item in results
    )
    score = int(weighted_score / total_weight) if total_weight else 0

    critical_gate_names = {"evidence_quality", "sensor_health", "policy_compliance"}
    critical_failure = any(
        item["gate"] in critical_gate_names and item["status"] == "FAIL"
        for item in results
    )

    failed = sum(1 for item in results if item["status"] == "FAIL")
    passed = len(results) - failed

    if critical_failure or score < 60:
        decision = "BLOCK"
    elif failed == 0 and score >= 90:
        decision = "PROCEED"
    elif score >= 75:
        decision = "REVIEW"
    else:
        decision = "INSUFFICIENT_DATA"

    return {
        "decision": decision,
        "score": score,
        "gates_passed": passed,
        "gates_total": len(results),
        "results": results,
        "summary": (
            f"{passed}/{len(results)} wildfire gates passed | "
            f"Score: {score}/100 | Decision: {decision}"
        ),
    }


def format_wildfire_gate_report(result: dict) -> str:
    """Return a concise human-readable wildfire gate report."""
    lines = [
        "=" * 60,
        "  EMBER WILDFIRE GATE",
        "=" * 60,
        f"  Decision: {result['decision']}",
        f"  Score: {result['score']}/100",
        f"  Gates: {result['gates_passed']}/{result['gates_total']} passed",
        "",
        "  Gate Results:",
    ]
    for item in result["results"]:
        icon = "PASS" if item["status"] == "PASS" else "FAIL"
        gate_name = GATES[item["gate"]]["name"]
        lines.append(f"    [{icon}] {gate_name}: {item['score']}/100")
    lines.extend(["", f"  {result['summary']}", "=" * 60])
    return "\n".join(lines)


if __name__ == "__main__":
    sample = evaluate_wildfire_gate({
        "evidence_quality": 90,
        "sensor_health": 90,
        "corroboration": 75,
        "temporal_consistency": 80,
        "policy_compliance": 100,
        "requires_human_approval": False,
    })
    print(format_wildfire_gate_report(sample))
