"""
Ember Cross-DB Audit (Phase 7)
================================
Read-only reader that joins records across all DBs by incident_id.

Answers:
    What happened for incident X, across all subsystems?
"""

from __future__ import annotations

import os
import sqlite3


def audit_incident(incident_id: str) -> dict:
    report = {"incident_id": incident_id, "sections": {}}

    # Decisions
    try:
        import perception.decision_log as dl
        if os.path.exists(dl.DB_PATH):
            conn = sqlite3.connect(dl.DB_PATH)
            rows = conn.execute("""
                SELECT id, assessment, severity, confidence,
                       requires_human_approval, created_at
                FROM decisions WHERE incident_id = ?
                ORDER BY id ASC
            """, (incident_id,)).fetchall()
            conn.close()
            report["sections"]["decisions"] = [
                {"id": r[0], "assessment": r[1], "severity": r[2],
                 "confidence": r[3], "approval_required": bool(r[4]),
                 "at": r[5]} for r in rows
            ]
    except Exception as exc:
        report["sections"]["decisions"] = {"error": str(exc)}

    # Authorization actions
    try:
        import perception.authorization as auth
        if os.path.exists(auth.DB_PATH):
            conn = sqlite3.connect(auth.DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT action_id, action_type, risk_tier, state,
                       required_approvals, current_approvals, created_at
                FROM actions WHERE incident_id = ?
                ORDER BY id ASC
            """, (incident_id,)).fetchall()
            conn.close()
            report["sections"]["actions"] = [dict(r) for r in rows]
    except Exception as exc:
        report["sections"]["actions"] = {"error": str(exc)}

    # Contracts
    try:
        import perception.action_contract as ctr
        if os.path.exists(ctr.DB_PATH):
            conn = sqlite3.connect(ctr.DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT contract_id, action_id, risk_tier, contract_hash,
                       signed, created_at
                FROM contracts WHERE incident_id = ?
                ORDER BY id ASC
            """, (incident_id,)).fetchall()
            conn.close()
            report["sections"]["contracts"] = [dict(r) for r in rows]
    except Exception as exc:
        report["sections"]["contracts"] = {"error": str(exc)}

    # Receipts
    try:
        import perception.action_contract as ctr
        if os.path.exists(ctr.DB_PATH):
            conn = sqlite3.connect(ctr.DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT receipt_id, contract_id, execution_status,
                       outcome, created_at
                FROM receipts
                WHERE contract_id IN (
                    SELECT contract_id FROM contracts WHERE incident_id = ?
                )
                ORDER BY id ASC
            """, (incident_id,)).fetchall()
            conn.close()
            report["sections"]["receipts"] = [dict(r) for r in rows]
    except Exception as exc:
        report["sections"]["receipts"] = {"error": str(exc)}

    # Total count
    total = sum(
        len(v) if isinstance(v, list) else 0
        for v in report["sections"].values()
    )
    report["total_records"] = total
    return report


def format_audit(report: dict) -> str:
    lines = [
        "=" * 60,
        f"  🔍 AUDIT — {report['incident_id']}",
        "=" * 60,
    ]
    for section, data in report["sections"].items():
        if isinstance(data, dict) and "error" in data:
            lines.append(f"  {section}: ERROR {data['error']}")
        else:
            lines.append(f"  {section} ({len(data)}):")
            for item in data[:5]:
                lines.append(f"    - {item}")
    lines.append(f"\n  Total records: {report['total_records']}")
    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    import perception.evidence_chain as chain
    import perception.authorization as auth
    import perception.action_contract as ctr
    chain.DB_PATH = tempfile.mktemp(suffix=".db")
    auth.DB_PATH = tempfile.mktemp(suffix=".db")
    ctr.DB_PATH = tempfile.mktemp(suffix=".db")
    chain.init_chain_db()
    auth.init_auth_db()
    ctr.init_contract_db()

    from perception.pipeline import run_pipeline
    from datetime import datetime, timezone
    event = {
        "event_id": "AUD-E1", "sensor_id": "AUD-S1", "zone_id": "z1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "pm25": 176.0, "temperature_c": 42.1, "humidity_percent": 24.0,
        "health_status": "healthy",
    }
    run_pipeline(
        incident_id="AUD-001", event=event,
        baseline={"pm25": 18.0, "temperature_c": 30.0, "humidity_percent": 42.0},
        action_type="notify_zone", auto_approve=True,
    )
    print(format_audit(audit_incident("AUD-001")))
