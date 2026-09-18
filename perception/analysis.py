"""
Ember Perception - Analysis Engine
Observation တွေကို နားလည်တဲ့ ဦးနှောက်
"""

from datetime import datetime
from perception.database import (
    get_latest_observation, log_change, save_observation
)


# =========================================================
# 1. CHANGE DETECTOR — ဘာပြောင်းလဲသွားလဲ?
# =========================================================

class ChangeDetector:
    """Observation အသစ်နဲ့ အဟောင်း နှိုင်းယှဉ်ခြင်း"""
    
    # ပြောင်းလဲမှုကို ခြေရာခံမယ့် Field များ
    TRACKED_FIELDS = ["status", "confidence", "error_type"]
    
    def detect(self, new_obs: dict, old_obs: dict) -> dict:
        """
        Observation အသစ်နဲ့ အဟောင်း နှိုင်းယှဉ်ခြင်း
        Returns: change report
        """
        # ပထမဆုံး Observation ဆိုရင်
        if not old_obs:
            return {
                "changed": False,
                "is_first": True,
                "changes": {}
            }
        
        changes = {}
        for field in self.TRACKED_FIELDS:
            old_val = old_obs.get(field)
            new_val = new_obs.get(field)
            
            if old_val != new_val:
                changes[field] = {
                    "from": old_val,
                    "to": new_val,
                    "severity": self._severity(field, old_val, new_val)
                }
        
        # ပြောင်းလဲမှုကို Database ထဲ မှတ်တမ်းတင်ခြင်း
        for field, change in changes.items():
            log_change(
                new_obs["source"], field,
                change["from"], change["to"]
            )
        
        return {
            "changed": len(changes) > 0,
            "is_first": False,
            "changes": changes,
            "change_count": len(changes)
        }
    
    def _severity(self, field: str, old_val, new_val) -> str:
        """ပြောင်းလဲမှုရဲ့ ပြင်းထန်မှုကို သတ်မှတ်ခြင်း"""
        if field == "status":
            # healthy → down = critical
            if old_val == "healthy" and new_val in ["down", "error", "critical"]:
                return "critical"
            if old_val in ["down", "error", "critical"] and new_val == "healthy":
                return "recovery"
            return "warning"
        
        if field == "confidence":
            try:
                diff = int(new_val) - int(old_val)
                if diff <= -20:
                    return "critical"
                if diff <= -10:
                    return "warning"
                if diff >= 10:
                    return "improvement"
            except (ValueError, TypeError):
                pass
            return "info"
        
        if field == "error_type":
            if old_val is None and new_val is not None:
                return "critical"
            if old_val is not None and new_val is None:
                return "recovery"
            return "warning"
        
        return "info"


# =========================================================
# 2. CORRELATION ENGINE — Signal တွေ ဘယ်လို ဆက်စပ်နေလဲ?
# =========================================================

class CorrelationEngine:
    """Signal တွေ ကြားက ဆက်စပ်မှုကို ရှာခြင်း"""
    
    # Pattern → Insight များ
    PATTERNS = [
        {
            "requires": ["backend:down", "repo:clean"],
            "insight": "Backend ပျက်နေတယ်၊ ဒါပေမယ့် Code က သန့်ရှင်းတယ်",
            "action": "Railway Deployment Log တွေကို စစ်ပါ",
            "confidence": 85,
            "severity": "critical"
        },
        {
            "requires": ["backend:healthy", "repo:dirty"],
            "insight": "Backend ကောင်းနေတယ်၊ Commit လုပ်ဖို့ အဆင်သင့်ဖြစ်နေတယ်",
            "action": "Pending changes တွေကို Commit & Push လုပ်ပါ",
            "confidence": 90,
            "severity": "info"
        },
        {
            "requires": ["backend:healthy", "repo:clean", "evidence:clear"],
            "insight": "Signals အားလုံး ကိုက်ညီနေတယ် — Release အတွက် အဆင်သင့်",
            "action": "Release Gate Evaluation ကို ဆက်လုပ်ပါ",
            "confidence": 87,
            "severity": "success"
        },
        {
            "requires": ["evidence:backlog", "backend:healthy"],
            "insight": "Backend ကောင်းပေမယ့် Approvals တွေ စုပုံနေတယ်",
            "action": "Pending approvals တွေကို Review လုပ်ပါ",
            "confidence": 80,
            "severity": "warning"
        },
        {
            "requires": ["local:critical"],
            "insight": "Disk Space ကုန်ခါနီးနေတယ်",
            "action": "မလိုအပ်တဲ့ ဖိုင်တွေ ရှင်းပါ",
            "confidence": 95,
            "severity": "critical"
        },
        {
            "requires": ["backend:degraded"],
            "insight": "Backend က အားနည်းနေတယ် (Degraded)",
            "action": "Backend response time ကို စောင့်ကြည့်ပါ",
            "confidence": 75,
            "severity": "warning"
        }
    ]
    
    def correlate(self, observations: dict) -> list:
        """
        Observations တွေကို ဆက်စပ်ကြည့်ခြင်း
        Args:
            observations: {"backend": obs_dict, "repo": obs_dict, ...}
        Returns: List of matched insights
        """
        # Signal တွေကို "source:status" format နဲ့ ဖန်တီး
        signals = set()
        for source, obs in observations.items():
            if obs:
                signals.add(f"{source}:{obs['status']}")
        
        matches = []
        for pattern in self.PATTERNS:
            required = set(pattern["requires"])
            if required.issubset(signals):
                matches.append({
                    "pattern": " + ".join(sorted(pattern["requires"])),
                    "insight": pattern["insight"],
                    "action": pattern["action"],
                    "confidence": pattern["confidence"],
                    "severity": pattern["severity"],
                    "matched_signals": list(required)
                })
        
        # Confidence အလိုက် Sort
        matches.sort(key=lambda x: x["confidence"], reverse=True)
        return matches


# =========================================================
# 3. CONFIDENCE SCORER — ဘယ်လောက် ယုံကြည်ရလဲ?
# =========================================================

class ConfidenceScorer:
    """Observation တစ်ခုချင်းစီရဲ့ Confidence ကို တွက်ချက်ခြင်း"""
    
    def score(self, obs: dict, history: list) -> int:
        """
        Source Reliability + Freshness + Consistency ကို ပေါင်းစပ်
        Returns: 0-100
        """
        base = obs.get("confidence", 50)
        
        # 1. Freshness (အသစ်လား၊ ဟောင်းလား)
        freshness = self._freshness_score(obs.get("observed_at"))
        
        # 2. Consistency (အရင်က တူတူလား)
        consistency = self._consistency_score(obs, history)
        
        # Weighted Average
        final = int(
            (base * 0.50) +
            (freshness * 0.25) +
            (consistency * 0.25)
        )
        
        return max(0, min(100, final))
    
    def _freshness_score(self, timestamp_str: str) -> int:
        """အချိန် ဘယ်လောက်ကြာပြီလဲ ဆိုတာ တွက်ချက်ခြင်း"""
        if not timestamp_str:
            return 50
        
        try:
            ts = datetime.fromisoformat(timestamp_str)
            age_seconds = (datetime.now() - ts).total_seconds()
            age_minutes = age_seconds / 60
            
            if age_minutes < 5:
                return 100
            if age_minutes < 15:
                return 90
            if age_minutes < 60:
                return 70
            if age_minutes < 360:
                return 50
            return 30
        except (ValueError, TypeError):
            return 50
    
    def _consistency_score(self, obs: dict, history: list) -> int:
        """အရင်က Observation တွေနဲ့ ကိုက်ညီမှုရှိလား"""
        if not history:
            return 50
        
        same_status = sum(
            1 for h in history if h.get("status") == obs.get("status")
        )
        ratio = same_status / len(history)
        
        # 70%+ တူတူဆို ယုံကြည်မှု မြင့်
        if ratio >= 0.9:
            return 100
        if ratio >= 0.7:
            return 85
        if ratio >= 0.5:
            return 70
        return 50


# =========================================================
# 4. ANALYSIS PIPELINE — အားလုံးကို ပေါင်းစပ်ခြင်း
# =========================================================

class AnalysisEngine:
    """Analysis အလွှာ အားလုံးကို ပေါင်းစပ်ခြင်း"""
    
    def __init__(self):
        self.change_detector = ChangeDetector()
        self.correlation_engine = CorrelationEngine()
        self.confidence_scorer = ConfidenceScorer()
    
    def analyze(self, new_observations: dict) -> dict:
        """
        Observations အသစ်တွေကို ခွဲခြမ်းစိတ်ဖြာခြင်း
        
        Args:
            new_observations: {"backend": obs, "repo": obs, ...}
        
        Returns: Full analysis report
        """
        report = {
            "analyzed_at": datetime.now().isoformat(),
            "observations": {},
            "changes": {},
            "correlations": [],
            "overall_confidence": 0,
            "overall_status": "unknown"
        }
        
        # 1. Observation တစ်ခုချင်းစီကို ခွဲခြမ်းစိတ်ဖြာ
        for source, obs in new_observations.items():
            if not obs:
                continue
            
            # နောက်ဆုံး Observation ကို ရယူ
            old_obs = get_latest_observation(source)
            
            # Change Detection
            change_report = self.change_detector.detect(obs, old_obs)
            
            # Confidence Re-scoring
            history = self._get_source_history(source)
            scored_confidence = self.confidence_scorer.score(obs, history)
            
            obs["scored_confidence"] = scored_confidence
            obs["change_report"] = change_report
            
            report["observations"][source] = obs
            report["changes"][source] = change_report
        
        # 2. Correlation Analysis
        report["correlations"] = self.correlation_engine.correlate(new_observations)
        
        # 3. Overall Confidence
        confidences = [
            o.get("scored_confidence", 0)
            for o in report["observations"].values()
        ]
        if confidences:
            report["overall_confidence"] = int(sum(confidences) / len(confidences))
        
        # 4. Overall Status
        report["overall_status"] = self._overall_status(report["observations"])
        
        return report
    
    def _get_source_history(self, source: str, limit: int = 10) -> list:
        """Source တစ်ခုရဲ့ သမိုင်းကြောင်းကို ရယူခြင်း"""
        from perception.database import DB_PATH
        import sqlite3
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT source, status, confidence, observed_at
            FROM observations
            WHERE source = ?
            ORDER BY id DESC LIMIT ?
        """, (source, limit))
        rows = c.fetchall()
        conn.close()
        
        return [
            {"source": r[0], "status": r[1], "confidence": r[2], "observed_at": r[3]}
            for r in rows
        ]
    
    def _overall_status(self, observations: dict) -> str:
        """အားလုံးရဲ့ စုစုပေါင်း Status ကို သတ်မှတ်ခြင်း"""
        statuses = [o["status"] for o in observations.values() if o]
        
        if not statuses:
            return "unknown"
        if any(s in ["critical", "down", "error"] for s in statuses):
            return "critical"
        if any(s in ["warning", "degraded", "dirty", "backlog"] for s in statuses):
            return "warning"
        if all(s in ["healthy", "clean", "clear"] for s in statuses):
            return "healthy"
        return "attention"


# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":
    from perception.observers import get_all_observers
    from perception.database import init_db, save_observation
    
    print("=" * 60)
    print("  Testing Analysis Engine")
    print("=" * 60)
    
    # Database Initialize
    init_db()
    
    # Observations စုဆောင်းခြင်း
    observations = {}
    observers = get_all_observers()
    
    print("\n📡 Collecting observations...")
    for observer in observers:
        obs = observer.observe()
        save_observation(obs)
        observations[observer.name] = obs
        print(f"   ✓ {observer.name}: {obs['status']}")
    
    # Analysis လုပ်ခြင်း
    print("\n🧠 Running analysis...")
    engine = AnalysisEngine()
    report = engine.analyze(observations)
    
    # ရလဒ် ပြသခြင်း
    print(f"\n{'=' * 60}")
    print(f"  ANALYSIS REPORT")
    print(f"{'=' * 60}")
    
    print(f"\n📊 Overall Status:  {report['overall_status'].upper()}")
    print(f"🎯 Overall Confidence: {report['overall_confidence']}%")
    
    print(f"\n🔍 Observations:")
    for source, obs in report["observations"].items():
        sc = obs.get("scored_confidence", 0)
        print(f"   • {source:10} → {obs['status']:10} (conf: {sc}%)")
    
    print(f"\n🔄 Changes:")
    for source, change in report["changes"].items():
        if change["is_first"]:
            print(f"   • {source}: First observation")
        elif change["changed"]:
            for field, c in change["changes"].items():
                print(f"   • {source}.{field}: {c['from']} → {c['to']} [{c['severity']}]")
        else:
            print(f"   • {source}: No changes")
    
    print(f"\n🔗 Correlations:")
    if report["correlations"]:
        for corr in report["correlations"]:
            print(f"   [{corr['severity'].upper()}] {corr['insight']}")
            print(f"      → {corr['action']} (conf: {corr['confidence']}%)")
    else:
        print(f"   No correlations detected.")
    
    print(f"\n✅ Analysis complete.")
