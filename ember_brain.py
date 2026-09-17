"""
Ember's Brain - LLM Integration
Ember ရဲ့ ဦးနှောက် - LLM ချိတ်ဆက်မှု

Supported Providers:
- OpenRouter (recommended, free models available)
- OpenAI
"""

import os
import json
import urllib.request
import urllib.error


class EmberBrain:
    """Ember ရဲ့ ဦးနှောက် - LLM နဲ့ ချိတ်ဆက်ပေးတဲ့ Class"""
    
    PROVIDERS = {
        "openrouter": {
            "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "openrouter/free",
            "env_key": "OPENROUTER_API_KEY"
        },
        "gemini": {
            "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            "model": "gemini-2.0-flash",
            "env_key": "GEMINI_API_KEY"
        },
        "openai": {
            "url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-4o-mini",
            "env_key": "OPENAI_API_KEY"
        }
    }
    
    def __init__(self, provider="openrouter"):
        self.provider = provider
        self.config = self.PROVIDERS.get(provider)
        if not self.config:
            raise ValueError(f"Unknown provider: {provider}")
        
        self.api_key = os.getenv(self.config["env_key"], "")
        if not self.api_key:
            raise ValueError(
                f"❌ {self.config['env_key']} environment variable not set.\n"
                f"   Run: export {self.config['env_key']}='your-key-here'"
            )
    
    def system_prompt(self, identity: dict) -> str:
        """Ember ရဲ့ ကိုယ်ရည်ကိုယ်သွေးကို System Prompt အဖြစ် ပြောင်းခြင်း"""
        return f"""You are {identity['name']}, an AI agent with the tagline "{identity['tagline']}".

PERSONALITY: You are {identity['personality']['archetype']}. {identity['personality']['description']}

YOUR VALUES:
{chr(10).join('- ' + v for v in identity['personality']['values'])}

YOUR CAPABILITIES:
- Provenance: {identity['capabilities']['provenance']['what']}
- Safety: {identity['capabilities']['safety']['what']}
- Human-in-the-Loop: {identity['capabilities']['human_in_the_loop']['what']}
- Observability: {identity['capabilities']['observability']['what']}

YOUR MARKET CATEGORY: {identity['market_identity']['category']}

YOU ARE: {', '.join(identity['market_identity']['is_a'])}
YOU ARE NOT: {', '.join(identity['market_identity']['not_a'])}

YOUR VOICE:
- Tone: {identity['voice']['tone']}
- Style: {identity['voice']['style']}
- Avoid: {', '.join(identity['voice']['avoid'])}
- Embrace: {', '.join(identity['voice']['embrace'])}

IMPORTANT RULES:
1. You never claim success without evidence.
2. You always explain WHY, not just WHAT.
3. You suggest bounded next actions, not open-ended ones.
4. You respect the human's authority — you propose, they decide.
5. You keep responses concise and factual.
6. When you don't know something, you say so.

Respond as Ember. Be calm, factual, and concise."""
    
    def think(self, user_message: str, identity: dict, context: str = "") -> str:
        """Ember က စဉ်းစားပြီး ပြန်ဖြေခြင်း"""
        system = self.system_prompt(identity)
        
        if context:
            system += f"\n\nCURRENT CONTEXT:\n{context}"
        
        if self.provider == "gemini":
            return self._call_gemini(system, user_message)
        else:
            return self._call_openai_compatible(system, user_message)
    
    def _call_openai_compatible(self, system: str, user: str) -> str:
        """OpenAI-compatible API (OpenRouter, OpenAI) ကို ခေါ်ခြင်း"""
        payload = {
            "model": self.config["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "temperature": 0.7,
            "max_tokens": 1024
        }
        
        req = urllib.request.Request(
            self.config["url"],
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/highfive251677-wq/ember-lite",
                "X-Title": "Ember Lite"
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
    
    def _call_gemini(self, system: str, user: str) -> str:
        """Google Gemini API ကို ခေါ်ခြင်း"""
        url = f"{self.config['url']}?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            return f"❌ HTTP Error {e.code}: {e.read().decode('utf-8')[:200]}"
        except Exception as e:
            return f"❌ Error: {e}"


if __name__ == "__main__":
    # စမ်းသပ်ရန်
    from ember_identity import EMBER_IDENTITY
    
    try:
        brain = EmberBrain(provider="openrouter")
        print("🧠 Ember's brain is online.")
        print("Testing...")
        response = brain.think(
            "Who are you and what is your purpose?",
            EMBER_IDENTITY
        )
        print(f"\n{response}")
    except ValueError as e:
        print(e)
