"""
Ember Unified Pipeline (Phase 7)
==================================
Runs Phase 1-6 in a single function.

Flow:
    1. Validate inputs          (Phase 1)
    2. Append to evidence chain (Phase 2)
    3. Compute reliability      (Phase 4)
    4. Assess wildfire          (Phase 0)
    5. Evaluate wildfire gate   (Phase 5)
    6. Compute risk tier        (Phase 3)
    7. Evaluate policy          (Phase 3)
    8. Create action            (Phase 3)
    9. Build contract           (Phase 4)
   10. Simulate action          (Phase 4)
   11. Anchor (optional)        (Phase 6)

KPI #1 (Evidence-First): Every step's status is visible.
KPI #4 (Local-First): Pure Python, no network.
Pure Python stdlib only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_pipeline(
    incident_id: str,
    event: dict,
    baseline: dict | None,
    neighbors: list | None = None,
    history: list | None = None,
    wind_toward_zone: bool = False,
    action_type: str | None = None,
    affected_population: int = 0,
    auto_approve: bool = False,
    approver: str = "operator",
    anchor: bool = False,
) -> dict:
    """
    Run the full Ember pipeline end-to-end.

    Each step is failure-isolated: if a step fails, subsequent
    steps receive the failure marker and may be skipped.
    """
    result = {
        "incident_id": incident_id,
        "started_at": _now(),
        "steps": {},
        "status": "pending",
    }

    # ---------- STEP 1: Validate ----------
    try:
        from perception.validation import validate_inputs
        val = validate_inputs(event, baseline, neighbors, history)
        result["steps"]["1_validation"] = {
            "status": val["overall_status"],
            "problems": [],
        }
        if val["overall_status"] not in ("valid", "unknown"):
            result["status"] = "blocked_validation"
            return result
    except Exception as exc:
        result["steps"]["1_validation"] = {"status": "error",
                                            "error": str(exc)}
        result["status"] = "error_validation"
        return result

    # ---------- STEP 2: Chain append ----------
    try:
        from perception.evidence_chain import add_observation
        chain_r = add_observation({"event": event}, terminal="T")
        result["steps"]["2_chain"] = {
            "recorded": chain_r.get("recorded"),
            "signed": chain_r.get("signed"),
            "block_hash": chain_r.get("block_hash"),
            "block_index": chain_r.get("block_index"),
        }
    except Exception as exc:
        result["steps"]["2_chain"] = {"error": str(exc)}
        chain_r = {"block_hash": None, "signed": False, "recorded": False}

    # ---------- STEP 3: Reliability ----------
    try:
        from perception.reliability import compute_reliability
        rel = compute_reliability(event, neighbors, history, chain_r)
        result["steps"]["3_reliability"] = {
            "reliability": rel["reliability"],
            "grade": rel["grade"],
        }
    except Exception as exc:
        result["steps"]["3_reliability"] = {"error": str(exc)}
        rel = {"reliability": 0.0, "grade": "INSUFFICIENT"}

    # ---------- STEP 4: Wildfire assessment ----------
    try:
        from perception.wildfire_assessment import (
            assess_wildfire, persist_wildfire_decision,
        )
        alert = assess_wildfire(
            incident_id=incident_id, event=event, baseline=baseline,
            neighbors=neighbors or [], history=history or [],
            wind_toward_zone=wind_toward_zone,
        )
        alert = persist_wildfire_decision(alert)
        result["steps"]["4_assessment"] = {
            "assessment": alert["assessment"],
            "severity": alert["severity"],
            "confidence": alert["confidence"],
            "requires_human_approval": alert["requires_human_approval"],
        }
    except Exception as exc:
        result["steps"]["4_assessment"] = {"error": str(exc)}
        result["status"] = "error_assessment"
        return result

    # ---------- STEP 5: Wildfire gate ----------
    try:
        from perception.wildfire_gate import evaluate_wildfire_gate
        chain = alert.get("chain", {})
        gate_ctx = {
            "evidence_quality": int(alert["confidence"] * 100),
            "sensor_health": 90 if event.get("health_status") == "healthy" else 30,
            "corroboration": min(100, 50 + len(alert.get("supporting_evidence", [])) * 25),
            "temporal_consistency": 70 if alert.get("calculations") else 40,
            "policy_compliance": 100 if chain.get("available") else 0,
            "requires_human_approval": alert["requires_human_approval"],
        }
        gate = evaluate_wildfire_gate(gate_ctx)
        result["steps"]["5_gate"] = {
            "decision": gate["decision"],
            "score": gate["score"],
        }
    except Exception as exc:
        result["steps"]["5_gate"] = {"error": str(exc)}
        gate = {"decision": "INSUFFICIENT_DATA", "score": 0}

    # ---------- If no action requested, stop here ----------
    if not action_type:
        result["status"] = "assessment_complete"
        result["finished_at"] = _now()
        return result

    # ---------- STEP 6: Risk tier ----------
    try:
        from perception.risk_policy import compute_risk_tier, evaluate_policy
        tier_r = compute_risk_tier(
            evidence_confidence=rel["reliability"],
            integrity_ok=chain_r.get("signed", False),
            cross_sensor_agreement=len(neighbors or []),
            temporal_persistence=0.7 if history else 0.3,
            action_reversibility="irreversible",
            affected_population=affected_population,
        )
        result["steps"]["6_risk_tier"] = {"tier": tier_r["tier"]}
        tier = tier_r["tier"]

        policy_d = evaluate_policy(action_type, tier)
        result["steps"]["7_policy"] = {
            "decision": policy_d["decision"],
            "required_approval": policy_d["required_approval"],
            "policy_id": policy_d["policy_id"],
        }
    except Exception as exc:
        result["steps"]["6_risk_tier"] = {"error": str(exc)}
        result["status"] = "error_tier"
        return result

    # ---------- STEP 8: Create action ----------
    try:
        from perception.authorization import (
            create_action, approve_action, authorize_action,
        )
        required = 1
        if policy_d["required_approval"] == "two_person":
            required = 2

        act = create_action(
            action_type=action_type, incident_id=incident_id,
            risk_tier=tier, evidence_root=chain_r.get("block_hash"),
            policy_hash=policy_d["policy_hash"],
            required_approvals=required,
        )
        result["steps"]["8_action"] = {
            "action_id": act.get("action_id"),
            "state": act.get("state"),
            "required_approvals": required,
        }

        # Auto-approve path (for demo / test)
        if auto_approve and act.get("created"):
            for i in range(required):
                approve_action(act["action_id"], f"{approver}-{i+1}")
            auth_r = authorize_action(act["action_id"])
            result["steps"]["10_authorization"] = {
                "authorized": auth_r.get("authorized"),
                "reason": auth_r.get("reason"),
            }
    except Exception as exc:
        result["steps"]["8_action"] = {"error": str(exc)}
        result["status"] = "error_action"
        return result

    # ---------- STEP 9: Contract ----------
    try:
        from perception.action_contract import build_contract
        ctr = build_contract(
            action_id=act["action_id"], incident_id=incident_id,
            evidence_root=chain_r.get("block_hash"),
            assessment_hash=rel["reliability"],
            policy_id=policy_d["policy_id"],
            policy_hash=policy_d["policy_hash"],
            action_digest=act["action_digest"],
            approval_digest=None, target=None, risk_tier=tier,
        )
        result["steps"]["9_contract"] = {
            "contract_id": ctr.get("contract_id"),
            "signed": ctr.get("signed"),
        }
    except Exception as exc:
        result["steps"]["9_contract"] = {"error": str(exc)}
        ctr = {"contract_id": None}

    # ---------- STEP 10b: Simulate ----------
    try:
        from perception.action_simulator import simulate_action
        sim = simulate_action(
            action_type=action_type, risk_tier=tier,
            evidence_reliability=rel["reliability"],
            policy_decision=policy_d,
            affected_population=affected_population,
        )
        result["steps"]["11_simulation"] = {
            "recommendation": sim["recommendation"],
            "activation": sim["activation"],
        }
    except Exception as exc:
        result["steps"]["11_simulation"] = {"error": str(exc)}

    # ---------- STEP 11: Anchor (optional) ----------
    if anchor and chain_r.get("block_hash"):
        try:
            from perception.anchoring import build_anchor
            anc = build_anchor(
                device_id="tab-a-2017",
                block_hashes=[chain_r["block_hash"]],
                first_block_index=chain_r.get("block_index", 1),
                last_block_index=chain_r.get("block_index", 1),
            )
            result["steps"]["12_anchor"] = {
                "anchor_id": anc.get("anchor_id"),
                "signed": anc.get("signed"),
            }
        except Exception as exc:
            result["steps"]["12_anchor"] = {"error": str(exc)}

    result["status"] = "complete"
    result["finished_at"] = _now()
    return result


def format_pipeline_report(result: dict) -> str:
    """Human-readable pipeline report."""
    lines = [
        "=" * 60,
        f"  🔗 EMBER PIPELINE — {result['incident_id']}",
        "=" * 60,
        f"  Status: {result['status']}",
        "",
    ]
    for step, data in result["steps"].items():
        icon = "✅" if "error" not in data else "❌"
        detail_parts = []
        for k, v in data.items():
            if k == "error":
                detail_parts.append(f"ERROR: {v}")
            else:
                detail_parts.append(f"{k}={v}")
        lines.append(f"  {icon} {step}: {', '.join(detail_parts[:4])}")

    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    import perception.evidence_chain as chain
    import perception.authorization as auth
    import perception.action_contract as ctr
    import perception.anchoring as anch

    chain.DB_PATH = tempfile.mktemp(suffix=".db")
    auth.DB_PATH = tempfile.mktemp(suffix=".db")
    ctr.DB_PATH = tempfile.mktemp(suffix=".db")
    anch.ANCHOR_DB_PATH = tempfile.mktemp(suffix=".db")
    anch.ANCHOR_FILE_DIR = tempfile.mkdtemp()

    chain.init_chain_db()
    auth.init_auth_db()
    ctr.init_contract_db()
    anch.init_anchor_db()

    from datetime import datetime, timezone
    event = {
        "event_id": "P7-E1", "sensor_id": "P7-S1", "zone_id": "z1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "pm25": 176.0, "temperature_c": 42.1, "humidity_percent": 24.0,
        "health_status": "healthy", "battery_percent": 85,
    }
    baseline = {"pm25": 18.0, "temperature_c": 30.0, "humidity_percent": 42.0}
    neighbors = [{"event_id": "P7-N1", "sensor_id": "P7-S2",
                  "captured_at": datetime.now(timezone.utc).isoformat(),
                  "pm25": 121.0}]

    r = run_pipeline(
        incident_id="P7-INC-001",
        event=event, baseline=baseline,
        neighbors=neighbors,
        action_type="notify_zone",
        affected_population=50,
        auto_approve=True,
        anchor=True,
    )
    print(format_pipeline_report(r))
