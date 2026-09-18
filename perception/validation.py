"""
Ember Input Validation Layer (Phase 1 — Truth Boundary)
=========================================================
Copilot Route: Input Validation and Canonical Data Contracts

Core Principle:
    Malformed, stale, unsigned, or contradictory sensor data
    must NOT produce an apparently authoritative decision.

KPI #1 Evidence-First:
    Missing data = "unknown", NOT a numeric default.
    Never reduce conditions to 0, 50, or 100.

Pure Python stdlib only. No external dependencies.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


# =========================================================
# ALLOWED STATUS VOCABULARY (Strict)
# =========================================================

VALID_STATUSES = {
    "valid",         # Data present and reasonable
    "unknown",       # Data missing
    "stale",         # Data too old
    "invalid",       # Data malformed or out of range
    "unavailable",   # Source not reachable
    "conflicting",   # Data contradicts other data
}

# Default staleness threshold (seconds)
DEFAULT_STALE_SECONDS = 300  # 5 minutes

# Physical range limits
PM25_MIN, PM25_MAX = 0.0, 2000.0
TEMP_MIN, TEMP_MAX = -50.0, 80.0
HUMIDITY_MIN, HUMIDITY_MAX = 0.0, 100.0
WIND_MIN, WIND_MAX = 0.0, 300.0

# Required fields for a canonical event
EVENT_REQUIRED = [
    "event_id", "sensor_id", "zone_id",
    "captured_at", "pm25", "temperature_c",
    "humidity_percent",
]


# =========================================================
# HELPERS
# =========================================================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str) -> datetime | None:
    """Parse an ISO-8601 timestamp. Return None if invalid."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _result(status: str, value: Any = None,
            reason: str = "", refs: list | None = None) -> dict:
    """Build a canonical validation result."""
    if status not in VALID_STATUSES:
        status = "invalid"
    return {
        "status": status,
        "value": value,
        "reason": reason,
        "source_refs": list(refs or []),
    }


# =========================================================
# FIELD VALIDATORS
# =========================================================

def validate_timestamp(ts: Any, ref: str = "",
                       stale_seconds: int = DEFAULT_STALE_SECONDS) -> dict:
    """Validate an ISO-8601 timestamp with staleness check."""
    parsed = _parse_iso(ts)
    if parsed is None:
        return _result("invalid", None, "timestamp_unparseable", [ref])

    age = (_now() - parsed).total_seconds()
    if age < 0:
        # Future timestamp — clock skew or bad data
        if age < -60:
            return _result("invalid", ts, "timestamp_in_future", [ref])
        return _result("valid", ts, "timestamp_ok", [ref])

    if age > stale_seconds:
        return _result("stale", ts, f"stale_{int(age)}s", [ref])

    return _result("valid", ts, "timestamp_ok", [ref])


def validate_range(value: Any, lo: float, hi: float,
                   ref: str = "", field: str = "value") -> dict:
    """Validate a numeric field within a physical range."""
    if value is None:
        return _result("unknown", None, f"{field}_missing", [ref])
    if not _is_positive_number(value):
        return _result("invalid", None, f"{field}_not_number", [ref])
    if value < lo or value > hi:
        return _result("invalid", value,
                       f"{field}_out_of_range_{lo}_{hi}", [ref])
    return _result("valid", float(value), f"{field}_ok", [ref])


def validate_identifier(value: Any, field: str = "id",
                        ref: str = "") -> dict:
    """Validate a non-empty string identifier."""
    if value is None or value == "":
        return _result("unknown", None, f"{field}_missing", [ref])
    if not isinstance(value, str):
        return _result("invalid", None, f"{field}_not_string", [ref])
    if not re.match(r"^[A-Za-z0-9_\-\.:]+$", value):
        return _result("invalid", value,
                       f"{field}_invalid_chars", [ref])
    return _result("valid", value, f"{field}_ok", [ref])


# =========================================================
# EVENT VALIDATION
# =========================================================

def validate_event(event: dict | None,
                   stale_seconds: int = DEFAULT_STALE_SECONDS) -> dict:
    """
    Validate a canonical sensor event.

    Returns a structured report. Does NOT raise.
    Status is one of: valid | unknown | stale | invalid | unavailable
    """
    if not event or not isinstance(event, dict):
        return _result("unavailable", None, "event_missing")

    ref = str(event.get("event_id", "unknown"))
    fields: dict[str, dict] = {}
    problems: list[str] = []

    # Required identifiers
    for key in ("event_id", "sensor_id", "zone_id"):
        r = validate_identifier(event.get(key), key, ref)
        fields[key] = r
        if r["status"] not in ("valid",):
            problems.append(f"{key}:{r['reason']}")

    # Timestamp
    ts_res = validate_timestamp(event.get("captured_at"), ref, stale_seconds)
    fields["captured_at"] = ts_res
    if ts_res["status"] not in ("valid",):
        problems.append(f"captured_at:{ts_res['reason']}")

    # Physical measurements
    fields["pm25"] = validate_range(
        event.get("pm25"), PM25_MIN, PM25_MAX, ref, "pm25")
    fields["temperature_c"] = validate_range(
        event.get("temperature_c"), TEMP_MIN, TEMP_MAX, ref, "temperature_c")
    fields["humidity_percent"] = validate_range(
        event.get("humidity_percent"), HUMIDITY_MIN, HUMIDITY_MAX, ref,
        "humidity_percent")

    for key in ("pm25", "temperature_c", "humidity_percent"):
        if fields[key]["status"] != "valid":
            problems.append(f"{key}:{fields[key]['reason']}")

    # Optional health
    health = event.get("health_status", "unknown")
    if health in ("fault", "offline"):
        problems.append(f"health:{health}")

    # Determine overall status
    if not problems:
        overall = "valid"
    else:
        # If the event itself cannot be identified, it's unavailable
        if fields.get("event_id", {}).get("status") == "unknown":
            overall = "unavailable"
        # If any critical field is invalid → invalid
        elif any(
            ("out_of_range" in p or "not_number" in p
             or "not_string" in p or "unparseable" in p
             or "in_future" in p or "invalid_chars" in p)
            for p in problems
        ):
            overall = "invalid"
        # If any timestamp is stale → stale
        elif fields["captured_at"]["status"] == "stale":
            overall = "stale"
        # Otherwise unknown (missing required fields)
        else:
            overall = "unknown"

    return {
        "status": overall,
        "problems": problems,
        "fields": fields,
        "source_refs": [ref],
    }


# =========================================================
# BASELINE VALIDATION
# =========================================================

def validate_baseline(baseline: dict | None) -> dict:
    """
    Validate a baseline record.

    Missing baseline → status = "unknown" (NOT default values).
    """
    if not baseline or not isinstance(baseline, dict):
        return _result("unknown", None, "baseline_missing")

    ref = str(baseline.get("sensor_id", "baseline"))
    fields: dict[str, dict] = {}
    problems: list[str] = []

    fields["pm25"] = validate_range(
        baseline.get("pm25"), PM25_MIN, PM25_MAX, ref, "baseline_pm25")
    fields["temperature_c"] = validate_range(
        baseline.get("temperature_c"), TEMP_MIN, TEMP_MAX, ref,
        "baseline_temperature_c")
    fields["humidity_percent"] = validate_range(
        baseline.get("humidity_percent"), HUMIDITY_MIN, HUMIDITY_MAX, ref,
        "baseline_humidity_percent")

    for key, r in fields.items():
        if r["status"] != "valid":
            problems.append(f"{key}:{r['reason']}")

    if not problems:
        overall = "valid"
    elif any(fields[k]["status"] == "invalid" for k in fields):
        overall = "invalid"
    else:
        overall = "unknown"

    return {
        "status": overall,
        "problems": problems,
        "fields": fields,
        "source_refs": [ref],
    }


# =========================================================
# HISTORY VALIDATION
# =========================================================

def validate_history(history: list | None,
                     sensor_id: str | None = None) -> dict:
    """
    Validate a list of historical observations.

    - <3 valid observations → status = "unknown"
    - Mixed sensors → status = "conflicting"
    """
    if not history or not isinstance(history, list):
        return _result("unknown", None, "history_empty")

    valid_items = []
    problems: list[str] = []
    seen_sensors = set()

    for item in history:
        if not isinstance(item, dict):
            problems.append("item_not_dict")
            continue
        ts_res = validate_timestamp(item.get("captured_at"),
                                    str(item.get("event_id", "?")))
        if ts_res["status"] not in ("valid", "stale"):
            problems.append(f"bad_timestamp:{ts_res['reason']}")
            continue
        sid = item.get("sensor_id")
        if sid:
            seen_sensors.add(sid)
        valid_items.append(item)

    if sensor_id and len(seen_sensors) > 1:
        return {
            "status": "conflicting",
            "value": len(valid_items),
            "reason": "history_mixed_sensors",
            "sensors": sorted(seen_sensors),
            "problems": problems,
            "source_refs": [],
        }

    if len(valid_items) < 3:
        return {
            "status": "unknown",
            "value": len(valid_items),
            "reason": f"history_insufficient_{len(valid_items)}_need_3",
            "problems": problems,
            "source_refs": [],
        }

    return {
        "status": "valid",
        "value": len(valid_items),
        "reason": "history_ok",
        "problems": problems,
        "source_refs": [],
    }


# =========================================================
# NEIGHBOR VALIDATION
# =========================================================

def validate_neighbors(neighbors: list | None,
                       zone_id: str | None = None) -> dict:
    """Validate a list of neighbor observations."""
    if not neighbors or not isinstance(neighbors, list):
        return _result("unknown", 0, "neighbors_empty")

    valid = []
    cross_zone = 0
    problems: list[str] = []

    for n in neighbors:
        if not isinstance(n, dict):
            problems.append("neighbor_not_dict")
            continue
        ts_res = validate_timestamp(n.get("captured_at", ""),
                                    str(n.get("event_id", "?")))
        if ts_res["status"] == "invalid":
            problems.append("neighbor_bad_timestamp")
            continue
        if zone_id and n.get("zone_id") and n["zone_id"] != zone_id:
            cross_zone += 1
        valid.append(n)

    if not valid:
        return _result("unavailable", 0, "neighbors_all_invalid")

    status = "valid" if cross_zone == 0 else "conflicting"
    return {
        "status": status,
        "value": len(valid),
        "reason": "neighbors_ok" if status == "valid"
                  else f"neighbors_cross_zone_{cross_zone}",
        "problems": problems,
        "source_refs": [str(n.get("event_id", "?")) for n in valid],
    }


# =========================================================
# MASTER VALIDATION
# =========================================================

def validate_inputs(event: dict | None,
                    baseline: dict | None,
                    neighbors: list | None = None,
                    history: list | None = None,
                    stale_seconds: int = DEFAULT_STALE_SECONDS) -> dict:
    """
    Master validation entry point.

    Returns a structured report. Callers should treat any non-"valid"
    status as a signal to reduce confidence or block scoring.
    """
    ev = validate_event(event, stale_seconds)
    bl = validate_baseline(baseline)
    nb = validate_neighbors(
        neighbors, (event or {}).get("zone_id"))
    hi = validate_history(
        history, (event or {}).get("sensor_id"))

    # Overall truth-boundary status
    statuses = [ev["status"], bl["status"], nb["status"], hi["status"]]
    if "invalid" in statuses:
        overall = "invalid"
    elif "unavailable" in statuses:
        overall = "unavailable"
    elif "conflicting" in statuses:
        overall = "conflicting"
    elif "stale" in statuses:
        overall = "stale"
    elif all(s == "valid" for s in statuses):
        overall = "valid"
    else:
        overall = "unknown"

    return {
        "overall_status": overall,
        "event": ev,
        "baseline": bl,
        "neighbors": nb,
        "history": hi,
        "validated_at": _now().isoformat(),
    }


if __name__ == "__main__":
    # Quick smoke test
    event = {
        "event_id": "EVT-001", "sensor_id": "ES-104", "zone_id": "zone-03",
        "captured_at": _now().isoformat(),
        "pm25": 176.0, "temperature_c": 42.1, "humidity_percent": 24.0,
        "health_status": "healthy",
    }
    baseline = {
        "sensor_id": "ES-104",
        "pm25": 18.0, "temperature_c": 30.0, "humidity_percent": 42.0,
    }
    neighbors = [{"event_id": "N1", "sensor_id": "ES-105",
                  "captured_at": _now().isoformat(), "zone_id": "zone-03"}]
    history = [
        {"event_id": "H1", "sensor_id": "ES-104",
         "captured_at": _now().isoformat()},
        {"event_id": "H2", "sensor_id": "ES-104",
         "captured_at": _now().isoformat()},
        {"event_id": "H3", "sensor_id": "ES-104",
         "captured_at": _now().isoformat()},
    ]
    report = validate_inputs(event, baseline, neighbors, history)
    print("Overall:", report["overall_status"])
    print("Event:", report["event"]["status"])
    print("Baseline:", report["baseline"]["status"])
    print("Neighbors:", report["neighbors"]["status"])
    print("History:", report["history"]["status"])
