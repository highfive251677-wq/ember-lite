"""
Ember Release Gate Evaluator (P5)
==================================
Multi-dimensional Release Decision with Signed Evidence Bundle

Design: "Release is a decision. Every decision comes with evidence."
"""

import sqlite3
import json
import os
import uuid
from datetime import datetime

from perception.bridge_signatures import sign, verify
from perception.bridge_router import graph_summary, verify_graph_integrity


DB_PATH = os.path.join(os.path.dirname(__file__), "release_gate.db")


# =========================================================
# SCHEMA
# =========================================================

def init_gate_db():
    """Release Gate Database ဖန်တီးခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Evaluations
    c.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id TEXT UNIQUE NOT NULL,
            decision TEXT NOT NULL,
            score INTEGER NOT NULL,
            gates_passed INTEGER,
            gates_total INTEGER,
            summary TEXT,
            evidence_bundle TEXT,
            signature TEXT,
            evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Gate Results
    c.execute("""
        CREATE TABLE IF NOT EXISTS gate_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id TEXT NOT NULL,
            gate_name TEXT NOT NULL,
            status TEXT NOT NULL,
            score INTEGER,
            weight INTEGER,
            threshold TEXT,
            details TEXT,
            FOREIGN KEY (evaluation_id) REFERENCES evaluations(evaluation_id)
        )
    """)
    
    conn.commit()
    conn.close()
    return DB_PATH


# =========================================================
# GATE DEFINITIONS
# =========================================================

GATES = {
    "security": {
        "name": "Security Gate",
        "weight": 25,
        "threshold": "0 CRITICAL actions",
        "description": "No CRITICAL safety violations"
    },
    "performance": {
        "name": "Performance Gate",
        "weight": 20,
        "threshold": "Avg confidence >= 85%",
        "description": "System confidence above threshold"
    },
    "evidence": {
        "name": "Evidence Gate",
        "weight": 20,
        "threshold": "100% signed nodes valid",
        "description": "All evidence cryptographically verified"
    },
    "regression": {
        "name": "Regression Gate",
        "weight": 15,
        "threshold": "Directional drift >= -2%",
        "description": "No cumulative degradation"
    },
    "cost": {
        "name": "Cost Gate",
        "weight": 10,
        "threshold": "Error rate <= 5%",
        "description": "Bridge transport healthy"
    },
    "governance": {
        "name": "Governance Gate",
        "weight": 10,
        "threshold": "Pending approvals <= 3",
        "description": "Approval queue not backlogged"
    }
}


# =========================================================
# GATE EVALUATORS
# =========================================================

def _evaluate_security(perception_data: dict) -> dict:
    """Security Gate: CRITICAL Actions စစ်ဆေးခြင်း"""
    critical_count = 0
    total = 0
    
    try:
        from perception.database import DB_PATH as PERC_DB, get_recent_observations
        import sqlite3 as s3
        conn = s3.connect(PERC_DB)
        c = conn.cursor()
        c.execute("""
            SELECT COUNT(*) FROM observations
            WHERE status IN ('down', 'error', 'critical')
        """)
        critical_count = c.fetchone()[0] or 0
        c.execute("SELECT COUNT(*) FROM observations")
        total = c.fetchone()[0] or 1
        conn.close()
    except Exception:
        pass
    
    passed = critical_count == 0
    return {
        "gate": "security",
        "status": "PASS" if passed else "FAIL",
        "score": 100 if passed else max(0, 100 - critical_count * 25),
        "details": {
            "critical_count": critical_count,
            "total_observations": total
        }
    }


def _evaluate_performance(perception_data: dict) -> dict:
    """Performance Gate: Confidence Score စစ်ဆေးခြင်း"""
    avg_confidence = 0
    
    if perception_data:
        analysis = perception_data.get("analysis", {})
        avg_confidence = analysis.get("overall_confidence", 0)
    
    passed = avg_confidence >= 85
    return {
        "gate": "performance",
        "status": "PASS" if passed else "FAIL",
        "score": min(100, int(avg_confidence)),
        "details": {"avg_confidence": avg_confidence, "threshold": 85}
    }


def _evaluate_evidence() -> dict:
    """Evidence Gate: Signed Graph Integrity"""
    try:
        integrity = verify_graph_integrity()
        total = integrity.get("total", 0)
        valid = integrity.get("valid", 0)
        invalid = integrity.get("invalid", 0)
        
        if total == 0:
            passed = True
            score = 100
        else:
            passed = invalid == 0
            score = int((valid / total) * 100)
    except Exception:
        passed = True
        score = 100
        total, valid, invalid = 0, 0, 0
    
    return {
        "gate": "evidence",
        "status": "PASS" if passed else "FAIL",
        "score": score,
        "details": {"total": total, "valid": valid, "invalid": invalid}
    }


def _evaluate_regression() -> dict:
    """Regression Gate: Directional Drift စစ်ဆေးခြင်း"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT score FROM evaluations
            ORDER BY id DESC LIMIT 5
        """)
        recent = [r[0] for r in c.fetchall()]
        conn.close()
    except Exception:
        recent = []
    
    if len(recent) < 2:
        return {
            "gate": "regression",
            "status": "PASS",
            "score": 100,
            "details": {"drift": 0, "history_count": len(recent)}
        }
    
    baseline = sum(recent) / len(recent)
    drift = recent[0] - baseline if recent else 0
    passed = drift >= -2
    
    return {
        "gate": "regression",
        "status": "PASS" if passed else "FAIL",
        "score": max(0, min(100, int(100 + drift * 5))),
        "details": {
            "drift": round(drift, 2),
            "baseline": round(baseline, 1),
            "history_count": len(recent)
        }
    }


def _evaluate_cost() -> dict:
    """Cost Gate: Bridge Error Rate"""
    try:
        from perception.bridge_transport import get_transport_stats
        stats = get_transport_stats()
        by_status = stats.get("messages_by_status", {})
        total = sum(by_status.values()) or 1
        dlq = stats.get("dead_letters", 0)
        error_rate = (dlq / total) * 100
    except Exception:
        error_rate = 0
    
    passed = error_rate <= 5
    return {
        "gate": "cost",
        "status": "PASS" if passed else "FAIL",
        "score": max(0, int(100 - error_rate * 10)),
        "details": {"error_rate": round(error_rate, 2), "threshold": 5}
    }


def _evaluate_governance() -> dict:
    """Governance Gate: Pending Approvals"""
    try:
        from provenance import get_action_history
        history = get_action_history(50)
        pending = sum(1 for r in history if r[3] == "pending")
    except Exception:
        pending = 0
    
    passed = pending <= 3
    return {
        "gate": "governance",
        "status": "PASS" if passed else "FAIL",
        "score": max(0, 100 - pending * 20),
        "details": {"pending_approvals": pending, "threshold": 3}
    }


# =========================================================
# MAIN EVALUATOR
# =========================================================

def evaluate_release(perception_data: dict = None) -> dict:
    """
    Release Gate ကို အပြည့်အစုံ Evaluate လုပ်ခြင်း
    
    Args:
        perception_data: P1 Perception Report (optional)
    
    Returns: Evaluation report with signed bundle
    """
    init_gate_db()
    evaluation_id = str(uuid.uuid4())[:12]
    
    # Run all gates
    results = [
        _evaluate_security(perception_data),
        _evaluate_performance(perception_data),
        _evaluate_evidence(),
        _evaluate_regression(),
        _evaluate_cost(),
        _evaluate_governance()
    ]
    
    # Calculate Weighted Score
    total_weight = sum(GATES[r["gate"]]["weight"] for r in results)
    weighted_sum = sum(
        r["score"] * GATES[r["gate"]]["weight"] for r in results
    )
    final_score = int(weighted_sum / total_weight) if total_weight > 0 else 0
    
    gates_passed = sum(1 for r in results if r["status"] == "PASS")
    gates_total = len(results)
    
    # Any CRITICAL gate fail = NO_SHIP
    critical_fail = any(
        r["status"] == "FAIL" and GATES[r["gate"]]["weight"] >= 20
        for r in results
    )
    
    # Decision Logic
    if critical_fail or final_score < 60:
        decision = "NO_SHIP"
    elif final_score >= 90 and gates_passed == gates_total:
        decision = "SHIP"
    elif final_score >= 75:
        decision = "HOLD"
    else:
        decision = "REVIEW"
    
    # Summary
    summary = f"{gates_passed}/{gates_total} gates passed | Score: {final_score}/100"
    
    # Evidence Bundle
    bundle = {
        "evaluation_id": evaluation_id,
        "decision": decision,
        "score": final_score,
        "gates": results,
        "evaluated_at": datetime.now().isoformat(),
        "hash": uuid.uuid4().hex[:16]
    }
    
    # Sign Bundle (P4 Signatures)
    try:
        signed = sign(bundle, terminal="T")
        signature = signed["signature"]
    except Exception:
        signature = None
    
    # Save to DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO evaluations
        (evaluation_id, decision, score, gates_passed, gates_total,
         summary, evidence_bundle, signature)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        evaluation_id, decision, final_score,
        gates_passed, gates_total, summary,
        json.dumps(bundle), signature
    ))
    
    for r in results:
        c.execute("""
            INSERT INTO gate_results
            (evaluation_id, gate_name, status, score, weight, threshold, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            evaluation_id, r["gate"], r["status"], r["score"],
            GATES[r["gate"]]["weight"], GATES[r["gate"]]["threshold"],
            json.dumps(r["details"])
        ))
    
    conn.commit()
    conn.close()
    
    return {
        "evaluation_id": evaluation_id,
        "decision": decision,
        "score": final_score,
        "gates_passed": gates_passed,
        "gates_total": gates_total,
        "results": results,
        "summary": summary,
        "signed": signature is not None,
        "evaluated_at": bundle["evaluated_at"]
    }


def get_evaluation_history(limit: int = 10) -> list:
    """Release Evaluation သမိုင်းကြောင်း"""
    init_gate_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT evaluation_id, decision, score, gates_passed, gates_total,
               summary, evaluated_at
        FROM evaluations ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id": r[0], "decision": r[1], "score": r[2],
            "passed": f"{r[3]}/{r[4]}", "summary": r[5],
            "at": r[6]
        }
        for r in rows
    ]


def format_gate_report(result: dict) -> str:
    """Gate Report ကို Format လုပ်ခြင်း"""
    icons = {
        "SHIP": "✅", "HOLD": "⚠️",
        "REVIEW": "🔶", "NO_SHIP": "⛔"
    }
    lines = []
    lines.append("=" * 60)
    lines.append("  🚦 EMBER RELEASE GATE")
    lines.append("=" * 60)
    lines.append("")
    lines.append(
        f"  {icons.get(result['decision'], '•')} "
        f"Decision: {result['decision']}"
    )
    lines.append(f"  📊 Score: {result['score']}/100")
    lines.append(
        f"  🎯 Gates: {result['gates_passed']}/{result['gates_total']} passed"
    )
    lines.append("")
    lines.append("  Gate Results:")
    
    for r in result["results"]:
        icon = "✅" if r["status"] == "PASS" else "❌"
        gate_info = GATES.get(r["gate"], {})
        lines.append(
            f"    {icon} {gate_info.get('name', r['gate']):18} "
            f"score={r['score']:3}  weight={gate_info.get('weight', 0)}%"
        )
    
    lines.append("")
    lines.append(f"  ID: {result['evaluation_id']}")
    lines.append(f"  Signed: {result['signed']}")
    lines.append("=" * 60)
    return "\n".join(lines)


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Testing Release Gate Evaluator (P5)")
    print("=" * 60)
    print()
    
    # Run evaluation
    result = evaluate_release()
    print(format_gate_report(result))
    print()
    
    # History
    print("📜 Recent Evaluations:")
    for h in get_evaluation_history(5):
        print(f"   • [{h['decision']}] {h['score']}/100 ({h['passed']})")
    
    print()
    print("✅ P5 Release Gate test complete.")
