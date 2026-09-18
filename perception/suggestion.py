"""
Ember Perception - Suggestion Generator
Trigger တွေကို အခြေခံပြီး အကြံပြုချက် ဖန်တီးခြင်း
"""

from datetime import datetime


class SuggestionGenerator:
    """
    Trigger တွေကို ကြည့်ပြီး Bounded Suggestions ဖန်တီးခြင်း
    """
    
    def __init__(self, brain=None):
        self.brain = brain
    
    # =========================================================
    # RULE-BASED SUGGESTIONS
    # =========================================================
    
    RULES = {
        "error_appeared": {
            "template": "🚨 {source} မှာ {error_type} Error တက်နေတယ်။",
            "actions": {
                "network_timeout": "Backend Health Check ကို ပြန် run ပါ",
                "auth_error": "API Key တွေကို ပြန်စစ်ပါ",
                "not_found": "Endpoint URL ကို စစ်ပါ",
                "server_error": "Backend Log တွေကို ကြည့်ပါ",
                "network_error": "Internet Connection ကို စစ်ပါ"
            }
        },
        "status_change": {
            "template": "{source} ရဲ့ Status က {from_val} ကနေ {to_val} ကို ပြောင်းသွားတယ်။",
            "actions": {
                "critical": "ဒီအကြောင်းရင်းကို ချက်ချင်း စစ်ဆေးပါ",
                "recovery": "ပြန်ကောင်းသွားပြီ၊ ဒါပေမယ့် စောင့်ကြည့်နေပါ",
                "warning": "သတိထားပြီး စောင့်ကြည့်ပါ"
            }
        },
        "confidence_drop": {
            "template": "{source} ရဲ့ ယုံကြည်စိတ်ချရမှုက {drop}% ကျဆင်းသွားတယ်။",
            "actions": {
                "high": "Source ကို ပြန်စစ်ဆေးပါ",
                "medium": "နောက်တစ်ကြိမ် Perceive လုပ်တဲ့အထိ စောင့်ပါ"
            }
        },
        "correlation_alert": {
            "template": "🔗 {insight}",
            "actions": {
                "default": "{action_val}"
            }
        },
        "overall_critical": {
            "template": "🚨 System တစ်ခုလုံး CRITICAL အခြေအနေမှာ ရှိနေတယ်။",
            "actions": {
                "default": "အားလုံးကို ရပ်ပြီး အကြောင်းရင်းကို စစ်ဆေးပါ"
            }
        },
        "overall_warning": {
            "template": "⚠️ System မှာ Warning ရှိနေတယ်။",
            "actions": {
                "default": "သတိထားပြီး စောင့်ကြည့်ပါ"
            }
        }
    }
    
    def generate(self, triggers: list, context: dict = None) -> list:
        """Triggers တွေကနေ Suggestions ဖန်တီးခြင်း"""
        suggestions = []
        
        for trigger in triggers:
            suggestion = self._build_suggestion(trigger)
            if suggestion:
                suggestions.append(suggestion)
        
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        suggestions.sort(key=lambda s: severity_order.get(s["severity"], 99))
        
        return suggestions
    
    def _build_suggestion(self, trigger: dict) -> dict:
        """Trigger တစ်ခုကနေ Suggestion တစ်ခု ဖန်တီးခြင်း"""
        t_type = trigger["type"]
        rule = self.RULES.get(t_type)
        
        if not rule:
            return None
        
        source = trigger.get("source", "system")
        context = trigger.get("context", {})
        severity = trigger.get("severity", "medium")
        
        # Template ကို Fill လုပ်ခြင်း
        try:
            message = rule["template"].format(
                source=source,
                error_type=context.get("error_type", "unknown"),
                from_val=context.get("from", "?"),
                to_val=context.get("to", "?"),
                drop=context.get("drop", 0),
                insight=context.get("insight", trigger.get("message", "")),
                action_val=context.get("action", "စစ်ဆေးပါ")
            )
        except (KeyError, IndexError) as e:
            message = trigger.get("message", f"Unknown trigger: {e}")
        
        action = self._pick_action(t_type, severity, context)
        
        return {
            "trigger_type": t_type,
            "source": source,
            "severity": severity,
            "message": message,
            "action": action,
            "context": context,
            "generated_at": datetime.now().isoformat()
        }
    
    def _pick_action(self, t_type: str, severity: str, context: dict) -> str:
        """သင့်တော်တဲ့ Action ကို ရွေးချယ်ခြင်း"""
        rule = self.RULES.get(t_type, {})
        actions = rule.get("actions", {})
        
        if t_type == "error_appeared":
            error_type = context.get("error_type", "")
            if error_type in actions:
                return actions[error_type]
        
        if t_type == "status_change":
            change_sev = context.get("change_severity", "")
            if change_sev in actions:
                return actions[change_sev]
        
        if t_type == "confidence_drop":
            drop = context.get("drop", 0)
            if drop >= 30 and "high" in actions:
                return actions["high"]
            if "medium" in actions:
                return actions["medium"]
        
        if t_type == "correlation_alert":
            return context.get("action", "စစ်ဆေးပါ")
        
        return actions.get("default", "စောင့်ကြည့်ပါ")
    
    def generate_with_brain(self, triggers: list, context: dict = None) -> str:
        """LLM ကို သုံးပြီး ပိုပြီး နက်ရှိုင်းတဲ့ အကြံပြုချက် ဖန်တီးခြင်း"""
        if not self.brain:
            return "❌ Brain offline. Cannot generate LLM suggestions."
        
        trigger_text = "\n".join(
            f"- [{t['severity'].upper()}] {t['message']}" for t in triggers
        )
        
        prompt = f"""ဒီ Triggers တွေကို ကြည့်ပြီး Ember ရဲ့ ကိုယ်ရည်ကိုယ်သွေးနဲ့ အကြံပြုချက် ပေးပါ။

TRIGGERS:
{trigger_text}

CONTEXT:
{context or 'No additional context'}

Format:
1. SITUATION: လက်ရှိ အခြေအနေ (၁-၂ ကြောင်း)
2. PRIORITY: အာရုံစိုက်ရမယ့် အရာ (၁ ခု)
3. NEXT ACTION: နောက်တစ်ဆင့် (bounded action)
4. REASON: ဘာကြောင့် ဒီ Action လဲ"""
        
        return self.brain.think(prompt, context)
    
    def format_suggestions(self, suggestions: list) -> str:
        """Suggestions တွေကို လှပတဲ့ Text အဖြစ် ပြောင်းခြင်း"""
        if not suggestions:
            return "✨ အကြံပြုချက် မရှိပါ။ အားလုံး ကောင်းမွန်နေပါတယ်။"
        
        lines = [f"💡 Ember ရဲ့ အကြံပြုချက် {len(suggestions)} ခု:", ""]
        
        for i, s in enumerate(suggestions, 1):
            icon = {
                "critical": "🚨", "high": "⚠️",
                "medium": "⚡", "low": "ℹ️"
            }.get(s["severity"], "•")
            
            lines.append(f"{i}. {icon} [{s['severity'].upper()}] {s['message']}")
            lines.append(f"   → Action: {s['action']}")
            lines.append("")
        
        return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 60)
    print("  Testing Suggestion Generator")
    print("=" * 60)
    
    triggers = [
        {
            "type": "error_appeared",
            "source": "backend",
            "severity": "critical",
            "message": "backend မှာ Error တက်နေသည်: network_timeout",
            "context": {"error_type": "network_timeout"}
        },
        {
            "type": "status_change",
            "source": "repo",
            "severity": "medium",
            "message": "repo status: clean → dirty",
            "context": {"from": "clean", "to": "dirty", "change_severity": "warning"}
        },
        {
            "type": "confidence_drop",
            "source": "evidence",
            "severity": "high",
            "message": "evidence confidence ကျဆင်း: 95% → 60%",
            "context": {"drop": 35, "old": 95, "new": 60}
        }
    ]
    
    generator = SuggestionGenerator()
    suggestions = generator.generate(triggers)
    
    print()
    print(generator.format_suggestions(suggestions))
    print("✅ Suggestion Generator test complete.")
