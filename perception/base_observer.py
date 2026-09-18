"""
Ember Perception - Base Observer
Observer တွေရဲ့ အခြေခံ Class
"""

import hashlib
import time
import traceback
from datetime import datetime


class BaseObserver:
    """
    Observer တွေရဲ့ အခြေခံ Class
    Subclass တွေက _fetch() ကို override လုပ်ရမယ်
    """
    
    def __init__(self, name: str, category: str = "general"):
        self.name = name
        self.category = category
    
    def observe(self) -> dict:
        """
        Observation တစ်ခု ပြုလုပ်ခြင်း
        Returns: Observation dict with full metadata
        """
        start = time.time()
        
        try:
            data = self._fetch()
            status = self._classify(data)
            confidence = self._score_confidence(data)
            error_type = None
        except Exception as e:
            data = {
                "error": str(e),
                "trace": traceback.format_exc().split("\n")[-3]
            }
            status = "error"
            confidence = 0
            error_type = self._classify_error(e)
        
        cost_ms = int((time.time() - start) * 1000)
        
        return {
            "source": self.name,
            "category": self.category,
            "status": status,
            "confidence": confidence,
            "data": data,
            "cost_ms": cost_ms,
            "error_type": error_type,
            "provenance_hash": self._hash(data),
            "observed_at": datetime.now().isoformat()
        }
    
    # ===== Subclass က Override လုပ်ရမယ့် Methods =====
    
    def _fetch(self):
        """ဒေတာ ရယူခြင်း — Subclass က Implement လုပ်ရမယ်"""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _fetch()"
        )
    
    def _classify(self, data) -> str:
        """Status ကို သတ်မှတ်ခြင်း — Default: unknown"""
        return "unknown"
    
    def _score_confidence(self, data) -> int:
        """Confidence Score (0-100) — Default: 50"""
        return 50
    
    # ===== Common Helper Methods =====
    
    def _classify_error(self, error: Exception) -> str:
        """Error အမျိုးအစား ခွဲခြားခြင်း"""
        err_str = str(error).lower()
        
        if "timeout" in err_str or "timed out" in err_str:
            return "network_timeout"
        if "401" in err_str or "403" in err_str or "auth" in err_str:
            return "auth_error"
        if "404" in err_str or "not found" in err_str:
            return "not_found"
        if "500" in err_str or "502" in err_str or "503" in err_str:
            return "server_error"
        if "connection" in err_str or "network" in err_str:
            return "network_error"
        if "permission" in err_str:
            return "permission_error"
        return "unknown_error"
    
    def _hash(self, data) -> str:
        """SHA-256 Hash ဖန်တီးခြင်း (Provenance အတွက်)"""
        content = str(data).encode()
        return hashlib.sha256(content).hexdigest()[:16]


# ===== Test အတွက် Dummy Observer =====

class DummyObserver(BaseObserver):
    """Testing အတွက် Dummy Observer"""
    
    def __init__(self, name="dummy", should_fail=False):
        super().__init__(name, category="test")
        self.should_fail = should_fail
    
    def _fetch(self):
        if self.should_fail:
            raise ConnectionError("Simulated network failure")
        return {"message": "Hello from dummy", "value": 42}
    
    def _classify(self, data):
        return "healthy"
    
    def _score_confidence(self, data):
        return 95


if __name__ == "__main__":
    print("=" * 60)
    print("  Testing BaseObserver")
    print("=" * 60)
    
    # Test 1: Success case
    print("\n[Test 1] Successful observation:")
    dummy = DummyObserver("dummy-1")
    obs = dummy.observe()
    for key in ["source", "status", "confidence", "cost_ms", "provenance_hash"]:
        print(f"  {key}: {obs[key]}")
    
    # Test 2: Failure case
    print("\n[Test 2] Failed observation:")
    failing = DummyObserver("dummy-2", should_fail=True)
    obs = failing.observe()
    for key in ["source", "status", "confidence", "error_type"]:
        print(f"  {key}: {obs[key]}")
    
    print("\n✅ BaseObserver test complete.")
