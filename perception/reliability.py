"""
Ember Cross-Sensor Reliability (Phase 4)
==========================================
Copilot Phase 4: Reliability as First-Class Object

Key Principle:
    Do NOT call it "truth." Call it "reliability."
    Show the components — no opaque numbers.

Formula:
    reliability = freshness × sensor_health × spatial_agreement
                × temporal_persistence × provenance

Each factor ∈ [0.0, 1.0]. Product ∈ [0.0, 1.0].

KPI #1 (Evidence-First): Every factor is observable and explainable.
Pure Python stdlib only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# =========================================================
# FACTOR FUNCTIONS
# =========================================================

def _parse_iso(ts: str) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def freshness_factor(captured_at: str, max_age_seconds: int = 300) -> dict:
    """
    Freshness: 1.0 if just captured, 0.0 if way past max age.
    """
    ts = _parse_iso(captured_at)
    if ts is None:
        return {"value": 0.0, "status": "invalid",
                "reason": "timestamp_unparseable"}
    age = (_now() - ts).total_seconds()
    if age < 0:
        # Future timestamp
        if age < -60:
            return {"value": 0.0, "status": "invalid",
                    "reason": "timestamp_in_future"}
        return {"value": 1.0, "status": "valid",
                "reason": "timestamp_ok", "age_seconds": 0}
    if age >= max_age_seconds:
        return {"value": 0.0, "status": "stale",
                "reason": "stale", "age_seconds": int(age)}
    # Linear decay
    f = 1.0 - (age / max_age_seconds)
    return {"value": round(f, 3), "status": "valid",
            "reason": "fresh", "age_seconds": int(age)}


def sensor_health_factor(health_status: str,
                         battery_percent: float | None = None) -> dict:
    """
    Sensor health: 1.0 healthy, 0.5 degraded, 0.0 fault/offline.
    Battery < 20% applies a penalty.
    """
    status = (health_status or "unknown").lower()
    base = {
        "healthy": 1.0, "ok": 1.0,
        "degraded": 0.5, "warning": 0.5,
        "fault": 0.0, "offline": 0.0, "unknown": 0.3,
    }.get(status, 0.3)

    if base > 0 and battery_percent is not None:
        try:
            b = float(battery_percent)
            if b < 10:
                base *= 0.3
            elif b < 20:
                base *= 0.6
        except (TypeError, ValueError):
            pass

    return {"value": round(base, 3), "status": "valid",
            "reason": f"health={status}"}


def spatial_agreement_factor(neighbors: list | None,
                             max_expected: int = 3) -> dict:
    """
    Spatial agreement: how many neighbors corroborate.
    0 neighbors → 0.4 (not 0 — no disagreement, just none).
    """
    n = len(neighbors or [])
    if n == 0:
        return {"value": 0.4, "status": "unknown",
                "reason": "no_neighbors", "neighbor_count": 0}
    # Saturate at max_expected
    f = min(1.0, 0.5 + 0.5 * (n / max_expected))
    return {"value": round(f, 3), "status": "valid",
            "reason": f"{n}_neighbors", "neighbor_count": n}


def temporal_persistence_factor(history: list | None,
                                required: int = 3) -> dict:
    """
    Temporal persistence: how many observations in history.
    <required → penalty.
    """
    n = len(history or [])
    if n == 0:
        return {"value": 0.0, "status": "unknown",
                "reason": "no_history", "observation_count": 0}
    if n < required:
        f = n / required * 0.6  # partial
        return {"value": round(f, 3), "status": "unknown",
                "reason": f"insufficient_{n}_of_{required}",
                "observation_count": n}
    f = min(1.0, 0.6 + 0.4 * (n / (required * 2)))
    return {"value": round(f, 3), "status": "valid",
            "reason": f"{n}_observations", "observation_count": n}


def provenance_factor(chain: dict | None) -> dict:
    """
    Provenance: 1.0 if signed+recorded+verified, 0.0 if unsigned.
    """
    if not chain:
        return {"value": 0.0, "status": "unknown",
                "reason": "no_chain"}
    recorded = bool(chain.get("recorded"))
    signed = bool(chain.get("signed"))
    verified = bool(chain.get("verified"))
    anchored = bool(chain.get("anchored"))

    if recorded and signed and verified:
        f = 1.0
    elif recorded and signed:
        f = 0.8
    elif recorded:
        f = 0.5
    else:
        f = 0.0

    if anchored:
        f = min(1.0, f + 0.1)

    return {"value": round(f, 3), "status": "valid",
            "reason": f"recorded={recorded},signed={signed},"
                      f"verified={verified},anchored={anchored}"}


# =========================================================
# MASTER RELIABILITY
# =========================================================

def compute_reliability(
    event: dict,
    neighbors: list | None = None,
    history: list | None = None,
    chain: dict | None = None,
) -> dict:
    """
    Compute a reliability index from multiple factors.

    Returns:
        reliability: float (0.0 - 1.0)
        components: dict of individual factors
        grade: HIGH | MEDIUM | LOW | INSUFFICIENT
        reasons: human-readable summary
    """
    f_fresh = freshness_factor(event.get("captured_at", ""))
    f_health = sensor_health_factor(
        event.get("health_status", "unknown"),
        event.get("battery_percent"),
    )
    f_spatial = spatial_agreement_factor(neighbors)
    f_temporal = temporal_persistence_factor(history)
    f_provenance = provenance_factor(chain)

    components = {
        "freshness": f_fresh,
        "sensor_health": f_health,
        "spatial_agreement": f_spatial,
        "temporal_persistence": f_temporal,
        "provenance": f_provenance,
    }

    # Product of factors
    reliability = 1.0
    for c in components.values():
        reliability *= c["value"]

    reliability = round(reliability, 3)

    if reliability >= 0.70:
        grade = "HIGH"
    elif reliability >= 0.40:
        grade = "MEDIUM"
    elif reliability > 0.0:
        grade = "LOW"
    else:
        grade = "INSUFFICIENT"

    reasons = [
        f"{k}={v['value']} ({v['reason']})"
        for k, v in components.items()
    ]

    return {
        "reliability": reliability,
        "grade": grade,
        "components": components,
        "reasons": reasons,
    }


if __name__ == "__main__":
    from datetime import timedelta
    now = _now().isoformat()
    event = {
        "captured_at": now,
        "health_status": "healthy",
        "battery_percent": 85,
    }
    neighbors = [{"event_id": "N1"}, {"event_id": "N2"}]
    history = [{"event_id": f"H{i}"} for i in range(4)]
    chain = {"recorded": True, "signed": True, "verified": True}

    result = compute_reliability(event, neighbors, history, chain)
    print("Reliability:", result["reliability"])
    print("Grade:", result["grade"])
    for r in result["reasons"]:
        print("  ", r)
