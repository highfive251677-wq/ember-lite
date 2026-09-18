"""
Ember Wildfire Assessment
==========================
Wildfire-specific evidence assessment engine.
Signal → Evidence → Inference → Action

KPI Compliance:
- KPI #1 Evidence-First: No fake defaults. Missing = unknown.
- KPI #2 Human-in-Control: Physical actions require approval.
- KPI #3 Cryptographic Integrity: Integrates with evidence_chain.
- KPI #4 Local-First: Pure Python stdlib only.
- KPI #6 Self-Learning: Integrates with decision_log.
"""

import json
from datetime import datetime, timezone
from typing import Any


# =========================================================
# ALLOWED VOCABULARY (Strict — matches BRAND.md)
# =========================================================

ALLOWED_ASSESSMENTS = {
    "normal", "sensor_anomaly", "suspicious_signal",
    "possible_smoke", "corroborated_event", "confirmed_fire",
    "threatening_zone", "emergency", "insufficient_data"
}

ALLOWED_SEVERITIES = {"info", "low", "medium", "high", "critical"}

ALLOWED_PRIORITIES = {"low", "medium", "high", "critical"}


# =========================================================
# HELPERS
# =========================================================

def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_number(data: dict, key: str) -> float | None:
    """
    KPI #1: မရှိရင် None ပြန် — Default မသုံး
    """
    if key not in data:
        return None
    value = data.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evidence_item(statement: str, refs: list, confidence: float) -> dict:
    return {
        "statement": statement,
        "source_refs": list(refs),
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
    }


def action_item(action: str, reason: str, priority: str,
                requires_approval: bool) -> dict:
    if priority not in ALLOWED_PRIORITIES:
        priority = "medium"
    return {
        "action": action,
        "reason": reason,
        "priority": priority,
        "requires_approval": requires_approval,
    }


# =========================================================
# BASELINE VALIDATION (KPI #1)
# =========================================================

def validate_baseline(baseline: dict | None) -> dict:
    """
    KPI #1: Baseline မရှိရင် 'insufficient_data'
    """
    if not baseline:
        return {"valid": False, "reason": "Baseline is missing entirely"}

    required = ["pm25", "temperature_c", "humidity_percent"]
    missing = [k for k in required if get_number(baseline, k) is None]

    if missing:
        return {
            "valid": False,
            "reason": f"Baseline missing fields: {', '.join(missing)}"
        }

    return {"valid": True, "reason": "Baseline complete"}


# =========================================================
# TEMPORAL ANALYSIS (Commit 3 target)
# =========================================================

def compute_temporal_trend(history: list) -> dict:
    """
    KPI #1: <3 observations ဆိုရင် 'unavailable' ပြန် — Fabricate မလုပ်
    """
    valid = [h for h in history if h.get("captured_at")]
    valid.sort(key=lambda h: h["captured_at"])

    if len(valid) < 3:
        return {
            "available": False,
            "reason": f"temporal_trend_unavailable: only {len(valid)} valid observations (need ≥3)"
        }

    first, last = valid[0], valid[-1]
    try:
        t1 = datetime.fromisoformat(first["captured_at"].replace("Z", "+00:00"))
        t2 = datetime.fromisoformat(last["captured_at"].replace("Z", "+00:00"))
        dt = (t2 - t1).total_seconds()
    except (ValueError, KeyError):
        return {"available": False, "reason": "temporal_trend_unavailable: bad timestamps"}

    if dt <= 0:
        return {"available": False, "reason": "temporal_trend_unavailable: zero duration"}

    p1 = get_number(first, "pm25")
    p2 = get_number(last, "pm25")
    t1v = get_number(first, "temperature_c")
    t2v = get_number(last, "temperature_c")

    trend = {"available": True, "duration_seconds": dt}
    if p1 is not None and p2 is not None:
        trend["pm25_rate_per_sec"] = round((p2 - p1) / dt, 4)
    if t1v is not None and t2v is not None:
        trend["temperature_rate_per_sec"] = round((t2v - t1v) / dt, 4)

    return trend


# =========================================================
# SCORING — TEMPORARY (Commit 1 will replace this)
# =========================================================

def calculate_evidence_score(event: dict, baseline: dict,
                             neighbors: list) -> tuple[float, dict]:
    """
    Returns: (confidence 0.0-1.0, breakdown dict)

    NOTE: This function will be refined in Commit 1 to remove
    any hardcoded fallback values.
    """
    breakdown = {"components": [], "penalties": []}
    score = 0.0

    pm25 = get_number(event, "pm25")
    base_pm25 = get_number(baseline, "pm25") if baseline else None
    temp = get_number(event, "temperature_c")
    base_temp = get_number(baseline, "temperature_c") if baseline else None
    hum = get_number(event, "humidity_percent")
    base_hum = get_number(baseline, "humidity_percent") if baseline else None

    # PM2.5
    if pm25 is not None and base_pm25 is not None and base_pm25 > 0:
        ratio = pm25 / base_pm25
        if ratio >= 5.0:
            score += 0.30
            breakdown["components"].append(f"pm25_ratio={ratio:.1f}x (+0.30)")
        elif ratio >= 3.0:
            score += 0.20
            breakdown["components"].append(f"pm25_ratio={ratio:.1f}x (+0.20)")
        elif ratio >= 2.0:
            score += 0.10
            breakdown["components"].append(f"pm25_ratio={ratio:.1f}x (+0.10)")

    # Temperature
    if temp is not None and base_temp is not None:
        delta = temp - base_temp
        if delta >= 10:
            score += 0.20
            breakdown["components"].append(f"temp_delta={delta:.1f}C (+0.20)")
        elif delta >= 5:
            score += 0.10
            breakdown["components"].append(f"temp_delta={delta:.1f}C (+0.10)")

    # Humidity
    if hum is not None and base_hum is not None:
        delta = base_hum - hum
        if delta >= 15:
            score += 0.15
            breakdown["components"].append(f"humidity_drop={delta:.1f}pp (+0.15)")
        elif delta >= 5:
            score += 0.08
            breakdown["components"].append(f"humidity_drop={delta:.1f}pp (+0.08)")

    # Neighbors
    n = len(neighbors)
    if n >= 2:
        score += 0.20
        breakdown["components"].append(f"{n}_neighbors (+0.20)")
    elif n == 1:
        score += 0.10
        breakdown["components"].append(f"1_neighbor (+0.10)")

    # Sensor health penalty
    if event.get("health_status") in ("fault", "offline"):
        score *= 0.4
        breakdown["penalties"].append("health_penalty=x0.4")
    if event.get("is_stale"):
        score *= 0.7
        breakdown["penalties"].append("stale_penalty=x0.7")

    return min(round(score, 2), 1.0), breakdown


# =========================================================
# SEVERITY — INDEPENDENT FROM CONFIDENCE (Commit 2 target)
# =========================================================

def calculate_severity(event: dict, neighbors: list,
                       wind_toward_zone: bool) -> str:
    """
    KPI #1, #2: Severity = operational priority (independent)
    Low confidence can still be high severity.
    """
    if event.get("health_status") in ("fault", "offline"):
        return "info"

    pm25 = get_number(event, "pm25")
    temp = get_number(event, "temperature_c")

    # High: strong signal + wind + neighbors
    if pm25 and pm25 > 100 and wind_toward_zone and len(neighbors) >= 1:
        return "critical"
    # High: strong signal + wind
    if pm25 and pm25 > 100 and wind_toward_zone:
        return "high"
    # High: extreme signal
    if pm25 and pm25 > 150:
        return "high"
    # Medium
    if pm25 and pm25 > 50:
        return "medium"
    if temp and temp > 40:
        return "medium"
    # Low
    if pm25 and pm25 > 25:
        return "low"
    return "info"


# =========================================================
# ASSESSMENT CLASSIFICATION
# =========================================================

def classify_assessment(confidence: float, neighbors: int,
                        health_ok: bool, baseline_valid: bool) -> str:
    if not baseline_valid:
        return "insufficient_data"
    if not health_ok:
        return "sensor_anomaly"
    if confidence < 0.15:
        return "normal"
    if confidence < 0.30:
        return "insufficient_data"
    if confidence < 0.50:
        return "suspicious_signal"
    if confidence < 0.70:
        return "possible_smoke"
    if neighbors >= 2 and confidence >= 0.85:
        return "corroborated_event"
    return "possible_smoke"


# =========================================================
# MAIN ASSESSOR
# =========================================================

def assess_wildfire(
    incident_id: str,
    event: dict,
    baseline: dict | None,
    neighbors: list | None = None,
    history: list | None = None,
    wind_toward_zone: bool = False,
    analysis_timestamp: str | None = None,
) -> dict:
    """
    Signal → Evidence → Inference → Action
    """
    neighbors = neighbors or []
    history = history or []
    analysis_timestamp = analysis_timestamp or iso_now()

    obs = []
    calcs = []
    support = []
    counter = []
    uncertainties = []
    alternatives = []

    # --- Baseline Validation (KPI #1) ---
    baseline_check = validate_baseline(baseline)
    baseline_valid = baseline_check["valid"]

    if not baseline_valid:
        uncertainties.append(evidence_item(
            f"Baseline unavailable: {baseline_check['reason']}. "
            f"Abnormality cannot be measured against a local baseline.",
            [event.get("event_id", "unknown")],
            1.0
        ))

    # --- Observations ---
    if event.get("pm25") is not None:
        obs.append(evidence_item(
            f"Sensor {event.get('sensor_id', '?')} reports PM2.5 at {event['pm25']} µg/m³.",
            [event.get("event_id", "unknown")], 0.95
        ))
    if event.get("temperature_c") is not None:
        obs.append(evidence_item(
            f"Temperature at {event['temperature_c']}°C.",
            [event.get("event_id", "unknown")], 0.95
        ))

    # --- Calculations (only if baseline valid) ---
    if baseline_valid:
        pm25 = get_number(event, "pm25")
        b_pm25 = get_number(baseline, "pm25")
        if pm25 is not None and b_pm25 and b_pm25 > 0:
            calcs.append(evidence_item(
                f"PM2.5 is {round(pm25 / b_pm25, 2)}x baseline.",
                [event.get("event_id", "?"), f"BASE-{event.get('sensor_id', '?')}"],
                0.9
            ))

        temp = get_number(event, "temperature_c")
        b_temp = get_number(baseline, "temperature_c")
        if temp is not None and b_temp is not None:
            calcs.append(evidence_item(
                f"Temperature is {round(temp - b_temp, 1)}°C above baseline.",
                [event.get("event_id", "?"), f"BASE-{event.get('sensor_id', '?')}"],
                0.9
            ))

    # --- Temporal Trend (Commit 3) ---
    trend = compute_temporal_trend(history)
    if trend.get("available"):
        if "pm25_rate_per_sec" in trend:
            calcs.append(evidence_item(
                f"PM2.5 changing at {trend['pm25_rate_per_sec']} µg/m³/s "
                f"over {trend['duration_seconds']}s.",
                [h.get("event_id", "?") for h in history],
                0.85
            ))
    else:
        uncertainties.append(evidence_item(
            trend.get("reason", "Temporal trend unavailable."),
            [event.get("event_id", "?")], 1.0
        ))

    # --- Corroboration ---
    if neighbors:
        support.append(evidence_item(
            f"{len(neighbors)} nearby sensor(s) show related changes.",
            [n.get("event_id", "?") for n in neighbors], 0.8
        ))
    else:
        counter.append(evidence_item(
            "No nearby sensors corroborate the event.",
            [event.get("event_id", "?")], 0.7
        ))

    # --- Wind ---
    if wind_toward_zone:
        support.append(evidence_item(
            "Wind is moving toward monitored zone.",
            ["WIND-001"], 0.8
        ))

    # --- Alternatives ---
    alternatives.append(evidence_item(
        "Dust, controlled burn, sensor contamination, or equipment exhaust "
        "remain possible explanations.",
        [event.get("event_id", "?")], 0.5
    ))

    # --- Confidence (independent) ---
    health_ok = event.get("health_status") not in ("fault", "offline")
    confidence, breakdown = calculate_evidence_score(
        event, baseline or {}, neighbors
    )

    # --- Severity (independent from confidence) ---
    severity = calculate_severity(event, neighbors, wind_toward_zone)

    # --- Classification ---
    assessment = classify_assessment(
        confidence, len(neighbors), health_ok, baseline_valid
    )

    # --- Approval Requirement ---
    requires_approval = assessment not in {"normal", "sensor_anomaly"}

    # --- Recommended Actions ---
    actions = []
    if requires_approval:
        actions.append(action_item(
            "Notify zone operator and request visual verification.",
            "Sensor signal is not yet visually confirmed.",
            "high", True
        ))
    if assessment in {"possible_smoke", "corroborated_event"}:
        actions.append(action_item(
            "Prepare defense systems but do NOT activate.",
            "Physical activation requires explicit human approval.",
            "high", True
        ))
    if not baseline_valid:
        actions.append(action_item(
            "Establish a baseline for this sensor before reassessment.",
            "Missing baseline reduces assessment reliability.",
            "medium", False
        ))

    # --- Summary ---
    summary = (
        f"Assessment: {assessment}. Severity: {severity}. "
        f"Confidence: {confidence}. "
        f"{'Human approval required.' if requires_approval else 'Monitoring.'}"
    )[:500]

    return {
        "schema_version": "1.0",
        "incident_id": incident_id,
        "assessment": assessment,
        "severity": severity,
        "confidence": confidence,
        "summary": summary,
        "observations": obs,
        "calculations": calcs,
        "supporting_evidence": support,
        "counter_evidence": counter,
        "uncertainties": uncertainties,
        "alternative_explanations": alternatives,
        "recommended_actions": actions,
        "requires_human_approval": requires_approval,
        "source_references": [event.get("event_id", "?")] + [n.get("event_id", "?") for n in neighbors],
        "analysis_timestamp": analysis_timestamp,
        "_debug": {"score_breakdown": breakdown},
    }


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  🔥 Ember Wildfire Assessment — Smoke Test")
    print("=" * 60)
    print()

    event = {
        "event_id": "EVT-1001",
        "sensor_id": "ES-104",
        "zone_id": "zone-03",
        "captured_at": "2026-09-18T12:00:00Z",
        "pm25": 176.0,
        "temperature_c": 42.1,
        "humidity_percent": 24.0,
        "health_status": "healthy",
        "is_stale": False,
    }

    baseline = {
        "pm25": 18.0,
        "temperature_c": 30.0,
        "humidity_percent": 42.0,
    }

    neighbors = [{
        "event_id": "EVT-1002",
        "sensor_id": "ES-105",
        "captured_at": "2026-09-18T12:00:40Z",
        "pm25": 121.0,
        "temperature_c": 38.8,
        "humidity_percent": 27.0,
    }]

    history = [
        {"event_id": "EVT-0999", "captured_at": "2026-09-18T11:58:00Z", "pm25": 18.0, "temperature_c": 30.0},
        {"event_id": "EVT-1000", "captured_at": "2026-09-18T11:59:00Z", "pm25": 45.0, "temperature_c": 34.0},
        event,
    ]

    result = assess_wildfire(
        incident_id="INC-2026-0918-001",
        event=event,
        baseline=baseline,
        neighbors=neighbors,
        history=history,
        wind_toward_zone=True,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
