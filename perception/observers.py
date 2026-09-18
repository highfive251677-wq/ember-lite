"""
Ember Perception - Concrete Observers
Backend, Repo, Evidence, Local Observers
"""

import os
import json
import subprocess
import urllib.request
import urllib.error
import shutil

from perception.base_observer import BaseObserver
from perception.database import (
    save_observation, get_latest_observation, log_change
)


# =========================================================
# 1. BACKEND OBSERVER — Backend Health
# =========================================================

class BackendObserver(BaseObserver):
    """Ember Signal Backend ရဲ့ Health ကို စောင့်ကြည့်ခြင်း"""
    
    def __init__(self, url=None):
        super().__init__("backend", category="health")
        self.url = url or "https://ember-signal-backend-production.up.railway.app"
    
    def _fetch(self):
        req = urllib.request.Request(
            f"{self.url}/api/health",
            headers={"User-Agent": "Ember-Perception/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()[:500]
            return {
                "status_code": resp.status,
                "body_preview": body,
                "url": self.url
            }
    
    def _classify(self, data):
        code = data.get("status_code", 0)
        if code == 200:
            return "healthy"
        if 200 < code < 500:
            return "degraded"
        return "down"
    
    def _score_confidence(self, data):
        code = data.get("status_code", 0)
        if code == 200:
            return 98
        if code == 404:
            return 85
        if code >= 500:
            return 60
        return 50


# =========================================================
# 2. REPO OBSERVER — Repository State
# =========================================================

class RepoObserver(BaseObserver):
    """Git Repository ရဲ့ State ကို စောင့်ကြည့်ခြင်း"""
    
    def __init__(self, path=None):
        super().__init__("repo", category="state")
        self.path = path or os.path.expanduser("~/ember-lite")
    
    def _fetch(self):
        result = subprocess.run(
            f"cd {self.path} && "
            f"echo '===STATUS===' && git status --short && "
            f"echo '===LOG===' && git log -3 --oneline && "
            f"echo '===BRANCH===' && git branch --show-current",
            shell=True, capture_output=True, text=True, timeout=15
        )
        
        output = result.stdout
        status_section = output.split("===STATUS===")[1].split("===LOG===")[0]
        log_section = output.split("===LOG===")[1].split("===BRANCH===")[0]
        branch_section = output.split("===BRANCH===")[1]
        
        dirty_files = [
            line.strip() for line in status_section.strip().split("\n")
            if line.strip()
        ]
        recent_commits = [
            line.strip() for line in log_section.strip().split("\n")
            if line.strip()
        ]
        
        return {
            "dirty_files": dirty_files,
            "dirty_count": len(dirty_files),
            "recent_commits": recent_commits,
            "branch": branch_section.strip(),
            "path": self.path
        }
    
    def _classify(self, data):
        if data["dirty_count"] == 0:
            return "clean"
        if data["dirty_count"] < 5:
            return "minor_changes"
        return "dirty"
    
    def _score_confidence(self, data):
        return 95  # Git က အမြဲ ယုံကြည်ရတယ်


# =========================================================
# 3. EVIDENCE OBSERVER — Provenance Check
# =========================================================

class EvidenceObserver(BaseObserver):
    """Provenance Database ရဲ့ အနေအထားကို စောင့်ကြည့်ခြင်း"""
    
    def __init__(self):
        super().__init__("evidence", category="provenance")
    
    def _fetch(self):
        # ember-lite root ထဲက provenance.db ကို ကြည့်
        import sqlite3
        db_path = os.path.expanduser("~/ember-lite/provenance.db")
        
        if not os.path.exists(db_path):
            return {
                "db_exists": False,
                "total_actions": 0,
                "pending": 0,
                "approved": 0
            }
        
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM actions")
        total = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM actions WHERE status = 'pending'")
        pending = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM actions WHERE status = 'approved'")
        approved = c.fetchone()[0]
        
        conn.close()
        
        return {
            "db_exists": True,
            "total_actions": total,
            "pending": pending,
            "approved": approved
        }
    
    def _classify(self, data):
        if not data["db_exists"]:
            return "missing"
        if data["pending"] > 10:
            return "backlog"
        if data["pending"] > 0:
            return "attention"
        return "clear"
    
    def _score_confidence(self, data):
        return 99  # Database က အမြဲ တိကျ


# =========================================================
# 4. LOCAL OBSERVER — Terminal Environment
# =========================================================

class LocalObserver(BaseObserver):
    """Local Terminal Environment ကို စောင့်ကြည့်ခြင်း"""
    
    def __init__(self):
        super().__init__("local", category="environment")
    
    def _fetch(self):
        disk = shutil.disk_usage("/")
        return {
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": int((disk.used / disk.total) * 100),
            "cwd": os.getcwd(),
            "user": os.getenv("USER", "unknown")
        }
    
    def _classify(self, data):
        pct = data["disk_percent"]
        if pct > 90:
            return "critical"
        if pct > 75:
            return "warning"
        return "healthy"
    
    def _score_confidence(self, data):
        return 100  # Local က အမြဲ တိကျ


# =========================================================
# OBSERVER REGISTRY — အားလုံးကို စုစည်းခြင်း
# =========================================================

def get_all_observers():
    """Observers အားလုံးကို ပြန်ပေးခြင်း"""
    return [
        BackendObserver(),
        RepoObserver(),
        EvidenceObserver(),
        LocalObserver()
    ]


if __name__ == "__main__":
    print("=" * 60)
    print("  Testing Concrete Observers")
    print("=" * 60)
    
    observers = get_all_observers()
    
    for observer in observers:
        print(f"\n🔍 [{observer.name.upper()}]")
        obs = observer.observe()
        
        print(f"   Status:     {obs['status']}")
        print(f"   Confidence: {obs['confidence']}")
        print(f"   Cost:       {obs['cost_ms']}ms")
        print(f"   Hash:       {obs['provenance_hash']}")
        
        if obs['error_type']:
            print(f"   ⚠️  Error:  {obs['error_type']}")
        
        # Database ထဲ သိမ်း
        save_observation(obs)
        print(f"   💾 Saved to DB")
    
    print("\n✅ All observers tested.")
