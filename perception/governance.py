"""
Ember Governance Gateway (P6.1)
================================
Policy Engine + Approval Gating + Capability Boundaries

Based on: IEEE MCP Governance Gateway Framework
"Governance without access to internal model reasoning —
 leverages observable execution evidence."
"""

import sqlite3
import json
import os
import uuid
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(__file__), "governance.db")


# =========================================================
# SCHEMA
# =========================================================

def init_governance_db():
    """Governance Database ဖန်တီးခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Policies
    c.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            rule TEXT NOT NULL,
            threshold TEXT,
            severity TEXT DEFAULT 'medium',
            enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Policy Evaluations
    c.execute("""
        CREATE TABLE IF NOT EXISTS policy_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evaluation_id TEXT NOT NULL,
            policy_id TEXT NOT NULL,
            status TEXT NOT NULL,
            actual_value TEXT,
            details TEXT,
            evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Capability Boundaries
    c.execute("""
        CREATE TABLE IF NOT EXISTS capabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            terminal TEXT NOT NULL,
            capability TEXT NOT NULL,
            allowed INTEGER DEFAULT 1,
            constraints TEXT,
            UNIQUE(terminal, capability)
        )
    """)
    
    # Approval Gates
    c.execute("""
        CREATE TABLE IF NOT EXISTS approval_gates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_hash TEXT UNIQUE NOT NULL,
            action_type TEXT,
            risk_level TEXT,
            required_approvers INTEGER DEFAULT 1,
            current_approvals INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    return DB_PATH


# =========================================================
# POLICY ENGINE
# =========================================================

DEFAULT_POLICIES = [
    {
        "policy_id": "POL-SEC-001",
        "name": "No CRITICAL Commands",
        "category": "security",
        "rule": "critical_command_count == 0",
        "threshold": "0",
        "severity": "critical"
    },
    {
        "policy_id": "POL-CONF-001",
        "name": "Minimum Confidence",
        "category": "performance",
        "rule": "avg_confidence >= 85",
        "threshold": "85",
        "severity": "high"
    },
    {
        "policy_id": "POL-EVID-001",
        "name": "Evidence Integrity",
        "category": "evidence",
        "rule": "invalid_signatures == 0",
        "threshold": "0",
        "severity": "critical"
    },
    {
        "policy_id": "POL-GOV-001",
        "name": "Approval Backlog",
        "category": "governance",
        "rule": "pending_approvals <= 3",
        "threshold": "3",
        "severity": "medium"
    },
    {
        "policy_id": "POL-COST-001",
        "name": "Error Rate",
        "category": "cost",
        "rule": "error_rate <= 5",
        "threshold": "5",
        "severity": "medium"
    }
]


def seed_policies():
    """Default Policies တွေ ထည့်ခြင်း"""
    init_governance_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for p in DEFAULT_POLICIES:
        c.execute("""
            INSERT OR IGNORE INTO policies
            (policy_id, name, category, rule, threshold, severity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            p["policy_id"], p["name"], p["category"],
            p["rule"], p["threshold"], p["severity"]
        ))
    conn.commit()
    conn.close()


def evaluate_policies(context: dict) -> dict:
    """
    Policy အားလုံးကို Context ပေါ်မှာ Evaluate လုပ်ခြင်း
    
    Args:
        context: {
            "critical_command_count": int,
            "avg_confidence": int,
            "invalid_signatures": int,
            "pending_approvals": int,
            "error_rate": float
        }
    
    Returns: Evaluation results
    """
    seed_policies()
    evaluation_id = str(uuid.uuid4())[:12]
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT policy_id, name, rule, severity FROM policies WHERE enabled = 1")
    policies = c.fetchall()
    
    results = []
    for pol_id, name, rule, severity in policies:
        # Simple rule evaluation (safe)
        status = "PASS"
        actual = "N/A"
        details = ""
        
        try:
            if pol_id == "POL-SEC-001":
                actual = context.get("critical_command_count", 0)
                status = "PASS" if actual == 0 else "FAIL"
            elif pol_id == "POL-CONF-001":
                actual = context.get("avg_confidence", 0)
                status = "PASS" if actual >= 85 else "FAIL"
            elif pol_id == "POL-EVID-001":
                actual = context.get("invalid_signatures", 0)
                status = "PASS" if actual == 0 else "FAIL"
            elif pol_id == "POL-GOV-001":
                actual = context.get("pending_approvals", 0)
                status = "PASS" if actual <= 3 else "FAIL"
            elif pol_id == "POL-COST-001":
                actual = context.get("error_rate", 0)
                status = "PASS" if actual <= 5 else "FAIL"
        except Exception:
            status = "UNKNOWN"
        
        c.execute("""
            INSERT INTO policy_evaluations
            (evaluation_id, policy_id, status, actual_value, details)
            VALUES (?, ?, ?, ?, ?)
        """, (evaluation_id, pol_id, status, str(actual), details))
        
        results.append({
            "policy_id": pol_id,
            "name": name,
            "status": status,
            "actual": actual,
            "severity": severity
        })
    
    conn.commit()
    conn.close()
    
    passed = sum(1 for r in results if r["status"] == "PASS")
    
    return {
        "evaluation_id": evaluation_id,
        "total_policies": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
        "overall": "PASS" if passed == len(results) else "FAIL"
    }


# =========================================================
# CAPABILITY BOUNDARIES
# =========================================================

DEFAULT_CAPABILITIES = [
    ("@", "http_get", 1, "GET requests only"),
    ("@", "http_post", 0, "POST not allowed"),
    ("@", "file_read", 1, "Read-only filesystem"),
    ("@", "file_write", 0, "No write access"),
    ("T", "http_get", 1, "GET requests allowed"),
    ("T", "http_post", 1, "POST allowed with approval"),
    ("T", "file_read", 1, "Full read access"),
    ("T", "file_write", 1, "Write access with approval"),
    ("T", "shell_exec", 1, "Shell execution allowed"),
    ("T", "git_push", 0, "Git push requires manual approval"),
]


def seed_capabilities():
    """Default Capabilities ထည့်ခြင်း"""
    init_governance_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for terminal, cap, allowed, constraints in DEFAULT_CAPABILITIES:
        c.execute("""
            INSERT OR REPLACE INTO capabilities
            (terminal, capability, allowed, constraints)
            VALUES (?, ?, ?, ?)
        """, (terminal, cap, allowed, constraints))
    conn.commit()
    conn.close()


def check_capability(terminal: str, capability: str) -> dict:
    """Capability တစ်ခုကို စစ်ဆေးခြင်း"""
    seed_capabilities()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT allowed, constraints FROM capabilities
        WHERE terminal = ? AND capability = ?
    """, (terminal, capability))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return {
            "allowed": False,
            "reason": f"Capability '{capability}' not defined for '{terminal}'"
        }
    
    return {
        "allowed": bool(row[0]),
        "constraints": row[1]
    }


# =========================================================
# APPROVAL GATES
# =========================================================

def create_approval_gate(action_hash: str, action_type: str,
                         risk_level: str, required: int = 1) -> dict:
    """Approval Gate အသစ် ဖန်တီးခြင်း"""
    init_governance_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO approval_gates
            (action_hash, action_type, risk_level, required_approvers)
            VALUES (?, ?, ?, ?)
        """, (action_hash, action_type, risk_level, required))
        gate_id = c.lastrowid
        conn.commit()
        status = "created"
    except sqlite3.IntegrityError:
        c.execute("""
            SELECT id, status FROM approval_gates WHERE action_hash = ?
        """, (action_hash,))
        row = c.fetchone()
        gate_id = row[0] if row else None
        status = "exists"
    finally:
        conn.close()
    
    return {
        "gate_id": gate_id,
        "action_hash": action_hash,
        "status": status
    }


def approve_gate(action_hash: str, approver: str) -> dict:
    """Approval Gate ကို အတည်ပြုခြင်း"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE approval_gates
        SET current_approvals = current_approvals + 1,
            status = CASE
                WHEN current_approvals + 1 >= required_approvers THEN 'approved'
                ELSE 'partial'
            END,
            approved_at = CASE
                WHEN current_approvals + 1 >= required_approvers THEN CURRENT_TIMESTAMP
                ELSE approved_at
            END
        WHERE action_hash = ?
    """, (action_hash,))
    
    c.execute("""
        SELECT status, current_approvals, required_approvers
        FROM approval_gates WHERE action_hash = ?
    """, (action_hash,))
    row = c.fetchone()
    conn.commit()
    conn.close()
    
    if not row:
        return {"status": "not_found"}
    
    return {
        "status": row[0],
        "approvals": row[1],
        "required": row[2],
        "approved": row[0] == "approved"
    }


def get_governance_summary() -> dict:
    """Governance Summary"""
    init_governance_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM policies WHERE enabled = 1")
    policies = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM capabilities WHERE allowed = 1")
    capabilities = c.fetchone()[0]
    
    c.execute("SELECT status, COUNT(*) FROM approval_gates GROUP BY status")
    gates = dict(c.fetchall())
    
    conn.close()
    
    return {
        "active_policies": policies,
        "allowed_capabilities": capabilities,
        "approval_gates": gates
    }


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Testing Governance Gateway (P6.1)")
    print("=" * 60)
    print()
    
    init_governance_db()
    seed_policies()
    seed_capabilities()
    
    # Test Policy Evaluation
    context = {
        "critical_command_count": 0,
        "avg_confidence": 92,
        "invalid_signatures": 0,
        "pending_approvals": 1,
        "error_rate": 0.5
    }
    
    print("🔍 Policy Evaluation:")
    result = evaluate_policies(context)
    for r in result["results"]:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"   {icon} [{r['policy_id']}] {r['name']}: {r['status']} (actual={r['actual']})")
    print(f"\n   Overall: {result['overall']} ({result['passed']}/{result['total_policies']})")
    print()
    
    # Test Capability Check
    print("🔒 Capability Check:")
    cap = check_capability("T", "git_push")
    print(f"   T/git_push: allowed={cap['allowed']} ({cap.get('constraints', '')})")
    cap = check_capability("@", "http_post")
    print(f"   @/http_post: allowed={cap['allowed']} ({cap.get('constraints', '')})")
    print()
    
    # Test Approval Gate
    print("🚪 Approval Gate:")
    gate = create_approval_gate("abc123", "git_push", "high", required=2)
    print(f"   Created: {gate['status']}")
    approve = approve_gate("abc123", "user1")
    print(f"   After 1 approval: {approve['status']} ({approve['approvals']}/{approve['required']})")
    approve = approve_gate("abc123", "user2")
    print(f"   After 2 approvals: {approve['status']} (approved={approve['approved']})")
    print()
    
    # Summary
    print("📊 Governance Summary:")
    summary = get_governance_summary()
    for k, v in summary.items():
        print(f"   {k}: {v}")
    
    print()
    print("✅ P6.1 Governance Gateway complete.")
