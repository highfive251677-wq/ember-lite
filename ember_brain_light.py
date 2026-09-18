"""
Ember Brain - Lightweight API Orchestrator
===========================================
No heavy frameworks. Pure Python.
Zero-Dependency LLM integration.
"""

import os
import json
import urllib.request
import urllib.error

class EmberBrainLight:
    """Ember ရဲ့ ပေါ့ပါးတဲ့ ဦးနှောက် - API တိုက်ရိုက်ခေါ်တယ်"""
    
    def __init__(self, provider="openrouter"):
        self.provider = provider
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        
        if not self.api_key:
            raise ValueError("❌ OPENROUTER_API_KEY not set. Please run: export OPENROUTER_API_KEY='your-key'")
    
    def think(self, prompt: str, system_prompt: str = "You are Ember Signal, a helpful AI assistant focused on evidence-based decisions.") -> str:
        """LLM ကို မေးပြီး အဖြေယူတယ်"""
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        payload = {
            "model": "openrouter/free",  # Free model router
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1024
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            return f"❌ HTTP Error {e.code}: {e.read().decode('utf-8')[:200]}"
        except Exception as e:
            return f"❌ Error: {e}"

if __name__ == "__main__":
    try:
        brain = EmberBrainLight()
        print("✅ Ember Brain Light is online.")
        print(brain.think("Who are you?"))
    except ValueError as e:
        print(e)
