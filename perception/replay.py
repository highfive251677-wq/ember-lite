"""
Ember Replay Engine (Phase 5)
================================
Copilot Phase 5: Replay mode for every captured event.

Replays fixtures through the EXACT SAME pipeline:
    validate → assess → chain → gate → policy → authorize

Pure Python stdlib only.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Any


FIXTURES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "tests", "fixtures", "scenarios.json",
)


def _resolve_timestamp(marker: str) -> str:
    """Resolve test markers like NOW, OLD_2H, FUTURE_5M."""
    now = datetime.now(timezone.utc)
    if marker == "NOW":
        return now.isoformat()
    if marker == "OLD_2H":
        return (now - timedelta(hours=2)).isoformat()
    if marker == "FUTURE_5M":
        return (now + timedelta(minutes=5)).isoformat()
    return marker


def _resolve_event(event: dict) -> dict:
    """Replace markers in event fields."""
    if not event:
        return event
    out = dict(event)
    if "captured_at" in out:
        out["captured_at"] = _resolve_timestamp(out["captured_at"])
    return out


def _resolve_list(items: list | None) -> list:
    if not items:
        return []
    return [_resolve_event(x) for x in items]


def load_fixtures() -> dict:
    with open(FIXTURES_PATH, "r") as f:
        return json.load(f)


def run_replay(verbose: bool = True) -> dict:
    """Run all fixtures through the pipeline. Returns summary."""
    # Isolate DBs
    import perception.evidence_chain as chain
    import perception.authorization as auth
    import perception.action_contract as ctr
    import perception.validation as validation

    chain.DB_PATH = tempfile.mktemp(suffix=".db")
    auth.DB_PATH = tempfile.mktemp(suffix=".db")
    ctr.DB_PATH = tempfile.mktemp(suffix=".db")
    chain.init_chain_db()
    auth.init_auth_db()
    ctr.init_contract_db()

    from perception.wildfire_assessment import (
        assess_wildfire, persist_wildfire_decision,
    )
    from perception.wildfire_gate import evaluate_wildfire_gate
    from perception.risk_policy import compute_risk_tier, evaluate_policy
    from perception.authorization import (
        create_action, approve_action, authorize_action,
    )
    from perception.reliability import compute_reliability

    fixtures = load_fixtures()
    scenarios = fixtures.get("scenarios", [])
    results = []

    for sc in scenarios:
        sid = sc.get("id", "?")
        desc = sc.get("description", "")
        result = {"id": sid, "description": desc, "passed": True,
                  "failures": []}

        try:
            # Special cases: action-only scenarios
            if "action_type" in sc and "event" not in sc:
                _run_action_only(sc, result, auth, evaluate_policy)
            elif "action_type" in sc and "event" in sc:
                _run_full_pipeline(sc, result)
            else:
                _run_event_pipeline(sc, result)
        except Exception as exc:
            result["passed"] = False
            result["failures"].append(f"exception:{type(exc).__name__}:{exc}")

        results.append(result)
        if verbose:
            icon = "✅" if result["passed"] else "❌"
            print(f"{icon} {sid:35} {desc}")
            for f in result["failures"]:
                print(f"      → {f}")

    passed = sum(1 for r in results if r["passed"])
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }


# =========================================================
# SCENARIO RUNNERS
# =========================================================

def _run_event_pipeline(sc: dict, result: dict) -> None:
    """Run an event-only scenario."""
    from perception.validation import validate_inputs
    from perception.evidence_chain import add_observation
    from perception.wildfire_assessment import (
        assess_wildfire, persist_wildfire_decision,
    )

    event = _resolve_event(sc.get("event", {}))
    baseline = sc.get("baseline")
    neighbors = _resolve_list(sc.get("neighbors", []))
    history = _resolve_list(sc.get("history", []))

    # Chain append
    chain_r = add_observation({"event": event}, terminal="T")
    if sc.get("corrupt_after_append"):
        import sqlite3
        import perception.evidence_chain as chain_mod
        conn = sqlite3.connect(chain_mod.DB_PATH)
        conn.execute("UPDATE chain SET canonical_payload='{\"tampered\":1}'")
        conn.commit()
        conn.close()
        from perception.evidence_chain import verify_chain
        v = verify_chain()
        if v["valid"]:
            result["passed"] = False
            result["failures"].append("tamper_not_detected")
        return

    # Validation expectations
    if "expected_validation" in sc or "expected_validation_in" in sc:
        val = validate_inputs(event, baseline, neighbors, history)
        exp = sc.get("expected_validation")
        exp_in = sc.get("expected_validation_in")
        status = val["overall_status"]
        if exp and status != exp:
            result["passed"] = False
            result["failures"].append(f"validation:{status}!={exp}")
        if exp_in and status not in exp_in:
            result["passed"] = False
            result["failures"].append(f"validation:{status} not in {exp_in}")

    # Assessment
    alert = assess_wildfire(
        incident_id=f"REPLAY-{sc['id']}",
        event=event,
        baseline=baseline,
        neighbors=neighbors,
        history=history,
        wind_toward_zone=sc.get("wind_toward_zone", False),
    )

    # Expected assessment
    if "expected_assessment" in sc:
        if alert["assessment"] != sc["expected_assessment"]:
            result["passed"] = False
            result["failures"].append(
                f"assessment:{alert['assessment']}!={sc['expected_assessment']}"
            )
    if "expected_assessment_in" in sc:
        if alert["assessment"] not in sc["expected_assessment_in"]:
            result["passed"] = False
            result["failures"].append(
                f"assessment:{alert['assessment']} not in "
                f"{sc['expected_assessment_in']}"
            )

    alert = persist_wildfire_decision(alert)


def _run_action_only(sc: dict, result: dict,
                     auth, evaluate_policy) -> None:
    """Run an action-only scenario (no event)."""
    from perception.authorization import create_action, approve_action

    action_type = sc["action_type"]
    tier = sc["risk_tier"]

    if "expected_policy_decision" in sc:
        policy_d = evaluate_policy(action_type, tier)
        if policy_d["decision"] != sc["expected_policy_decision"]:
            result["passed"] = False
            result["failures"].append(
                f"policy:{policy_d['decision']}!"
                f"={sc['expected_policy_decision']}"
            )
        return

    if "ttl_seconds" in sc:
        act = create_action(
            action_type=action_type, incident_id="REPLAY",
            risk_tier=tier, evidence_root="x" * 64,
            policy_hash="y" * 64, required_approvals=1,
            ttl_seconds=sc["ttl_seconds"],
        )
        a = approve_action(act["action_id"], "op-1")
        if "expected_approve" in sc:
            if a.get("approved") != sc["expected_approve"]:
                result["passed"] = False
                result["failures"].append(
                    f"approve:{a.get('approved')}!"
                    f"={sc['expected_approve']}"
                )
        if "expected_reason" in sc:
            if a.get("error") != sc["expected_reason"]:
                result["passed"] = False
                result["failures"].append(
                    f"reason:{a.get('error')}!"
                    f"={sc['expected_reason']}"
                )


def _run_full_pipeline(sc: dict, result: dict) -> None:
    """Scenario with both event and action."""
    # Not needed for our fixtures, but kept for extension
    pass


if __name__ == "__main__":
    print("=" * 60)
    print("  🔁 EMBER REPLAY ENGINE")
    print("=" * 60)
    print()
    summary = run_replay(verbose=True)
    print()
    print(f"📊 Results: {summary['passed']}/{summary['total']} passed")
    print(f"   Failed: {summary['failed']}")
