"""
Ember Tool Caller — Zero-Dependency
====================================
Function calling with pure Python + OpenRouter.
No heavy frameworks needed.
"""

import os
import json
import urllib.request
import urllib.error


class ToolCaller:
    """LLM ကို Tools ပေးပြီး Tool Calling လုပ်တဲ့ Engine"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "openrouter/free"
        self.tools = {}
    
    def register_tool(self, name: str, description: str, 
                      parameters: dict, func):
        """Tool တစ်ခု Register လုပ်ခြင်း"""
        self.tools[name] = {
            "definition": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters
                }
            },
            "func": func
        }
    
    def _tool_definitions(self) -> list:
        return [t["definition"] for t in self.tools.values()]
    
    def _execute_tool(self, name: str, args: dict) -> str:
        if name not in self.tools:
            return f"Error: Unknown tool '{name}'"
        try:
            result = self.tools[name]["func"](**args)
            return json.dumps(result) if not isinstance(result, str) else result
        except Exception as e:
            return f"Error: {e}"
    
    def think(self, prompt: str, system: str = "You are Ember.") -> str:
        """Tool Calling Loop နဲ့ စဉ်းစားခြင်း"""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
        
        for iteration in range(5):  # Max 5 iterations
            payload = {
                "model": self.model,
                "messages": messages,
                "tools": self._tool_definitions(),
                "temperature": 0.7,
                "max_tokens": 1024
            }
            
            req = urllib.request.Request(
                self.url,
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
            except urllib.error.HTTPError as e:
                return f"❌ HTTP {e.code}: {e.read().decode('utf-8')[:200]}"
            except Exception as e:
                return f"❌ Error: {e}"
            
            choice = data["choices"][0]["message"]
            messages.append(choice)
            
            # Tool calls ရှိလား?
            tool_calls = choice.get("tool_calls", [])
            if not tool_calls:
                return choice.get("content", "No response")
            
            # Tool တွေ Run
            for tc in tool_calls:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                
                result = self._execute_tool(name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result
                })
        
        return "Max iterations reached."
