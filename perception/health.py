"""
Ember System Health (Phase 7)
================================
Diagnostics across all subsystems.

Checks:
    - All DBs reachable
    - Evidence chain integrity
    - Anchor signing/verification
    - Authorization DB state
    - Contracts count
    - Buffer queue state

Pure Python stdlib only.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_db(path: str, table: str) -> dict:
    if not os.path.exists(path):
        return {"exists": False, "rows": 0}
    try:
        conn = sqlite3.connect(path)
        rows = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.close()
        return {"exists": True, "rows": rows}
    except Exception as exc:
        return {"exists": True, "error": str(exc)}


def health_check() -> dict:
    checks = {}

    # Evidence chain
    try:
        import perception.evidence_chain as chain
        c = _check_db(chain.DB_PATH, "chain")
        v = chain.verify_chain()
        checks["evidence_chain"] = {
            **c,
            "valid": v["valid"],
            "verified": v.get("verified", 0),
            "unverified": v.get("unverified", 0),
        }
    except Exception as exc:
        checks["evidence_chain"] = {"error": str(exc)}

    # Anchors
    try:
        import perception.anchoring as anch
        a = _check_db(anch.ANCHOR_DB_PATH, "anchors")
        checks["anchors"] = {
            **a,
            "summary": anch.anchor_summary(),
        }
    except Exception as exc:
        checks["anchors"] = {"error": str(exc)}

    # Authorization
    try:
        import perception.authorization as auth
        checks["authorization"] = _check_db(auth.DB_PATH, "actions")
    except Exception as exc:
        checks["authorization"] = {"error": str(exc)}

    # Contracts
    try:
        import perception.action_contract as ctr
        checks["contracts"] = _check_db(ctr.DB_PATH, "contracts")
    except Exception as exc:
        checks["contracts"] = {"error": str(exc)}

    # Decision log
    try:
        import perception.decision_log as dl
        checks["decisions"] = _check_db(dl.DB_PATH, "decisions")
    except Exception as exc:
        checks["decisions"] = {"error": str(exc)}

    # Sensor buffer
    try:
        import perception.sensor_adapter as sa
        checks["sensor_buffer"] = sa.buffer_stats()
    except Exception as exc:
        checks["sensor_buffer"] = {"error": str(exc)}

    # Overall status
    ok = True
    for name, c in checks.items():
        if c.get("error"):
            ok = False
        if name == "evidence_chain" and c.get("valid") is False:
            ok = False

    return {
        "healthy": ok,
        "checked_at": _now(),
        "checks": checks,
    }


def format_health(report: dict) -> str:
    lines = [
        "=" * 60,
        "  🏥 EMBER HEALTH",
        "=" * 60,
        f"  Status: {'✅ HEALTHY' if report['healthy'] else '❌ UNHEALTHY'}",
        f"  At: {report['checked_at']}",
        "",
    ]
    for name, c in report["checks"].items():
        parts = [f"{k}={v}" for k, v in c.items() if k != "summary"]
        lines.append(f"  • {name}: {', '.join(parts[:4])}")
    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_health(health_check()))
