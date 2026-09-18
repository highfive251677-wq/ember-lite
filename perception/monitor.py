"""
Ember Perception - Monitor
နောက်ခံမှာ Periodically Perceive လုပ်ခြင်း
"""

import time
from datetime import datetime

from perception.layer import perceive
from perception.triggers import TriggerEngine
from perception.suggestion import SuggestionGenerator


class PerceptionMonitor:
    """
    Monitor က Periodically Perceive လုပ်ပြီး
    Triggers ရှိရင် Suggestions ထုတ်ပေးတယ်
    """
    
    def __init__(self, interval_minutes: int = 15, brain=None):
        """
        Args:
            interval_minutes: ဘယ်လောက်ကြာတစ်ခါ စစ်မလဲ
            brain: Optional EmberBrain for enhanced suggestions
        """
        self.interval = interval_minutes * 60
        self.brain = brain
        self.trigger_engine = TriggerEngine()
        self.suggestion_generator = SuggestionGenerator(brain=brain)
        
        # History
        self.run_count = 0
        self.suggestions_history = []
        self.last_run = None
    
    def run_once(self, callback=None) -> dict:
        """တစ်ခါ Perceive လုပ်ခြင်း"""
        self.run_count += 1
        self.last_run = datetime.now().isoformat()
        
        # 1. Perceive
        report = perceive(save=True)
        
        # 2. Triggers Evaluate
        triggers = self.trigger_engine.evaluate(report["analysis"])
        
        # 3. Suggestions Generate
        suggestions = self.suggestion_generator.generate(triggers)
        
        # 4. History
        if suggestions:
            self.suggestions_history.append({
                "timestamp": self.last_run,
                "count": len(suggestions),
                "suggestions": suggestions
            })
            
            if len(self.suggestions_history) > 50:
                self.suggestions_history = self.suggestions_history[-50:]
        
        result = {
            "run_number": self.run_count,
            "ran_at": self.last_run,
            "triggers_count": len(triggers),
            "suggestions_count": len(suggestions),
            "suggestions": suggestions,
            "overall_status": report["analysis"].get("overall_status"),
            "overall_confidence": report["analysis"].get("overall_confidence")
        }
        
        # Callback
        if callback and suggestions:
            callback(suggestions)
        
        return result
    
    def run_forever(self, callback=None, max_iterations: int = None):
        """အဆက်မပြတ် Monitor လုပ်ခြင်း (Loop)"""
        iteration = 0
        
        try:
            while True:
                if max_iterations and iteration >= max_iterations:
                    break
                
                result = self.run_once(callback=callback)
                iteration += 1
                
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(
                    f"[{timestamp}] "
                    f"Run #{result['run_number']}: "
                    f"{result['overall_status']} "
                    f"({result['overall_confidence']}%) | "
                    f"Triggers: {result['triggers_count']} | "
                    f"Suggestions: {result['suggestions_count']}"
                )
                
                time.sleep(self.interval)
        except KeyboardInterrupt:
            print("\n🛑 Monitor stopped.")
    
    def get_stats(self) -> dict:
        """Monitor ရဲ့ Statistics"""
        total_suggestions = sum(
            h["count"] for h in self.suggestions_history
        )
        
        return {
            "total_runs": self.run_count,
            "last_run": self.last_run,
            "interval_minutes": self.interval // 60,
            "suggestions_generated": total_suggestions,
            "history_size": len(self.suggestions_history)
        }


if __name__ == "__main__":
    print("=" * 60)
    print("  Testing Perception Monitor")
    print("=" * 60)
    print()
    
    monitor = PerceptionMonitor(interval_minutes=15)
    
    print("📡 Running 2 iterations (with 3s gap for testing)...")
    print()
    
    for i in range(2):
        result = monitor.run_once()
        print(
            f"Run #{result['run_number']}: "
            f"{result['overall_status']} "
            f"({result['overall_confidence']}%) | "
            f"Triggers: {result['triggers_count']} | "
            f"Suggestions: {result['suggestions_count']}"
        )
        if result['suggestions']:
            print("  Suggestions:")
            for s in result['suggestions']:
                print(f"    • [{s['severity']}] {s['message']}")
        print()
        
        if i < 1:
            time.sleep(3)
    
    print("📊 Monitor Stats:")
    for k, v in monitor.get_stats().items():
        print(f"   {k}: {v}")
    
    print("\n✅ Monitor test complete.")
