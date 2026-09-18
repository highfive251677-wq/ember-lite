"""
Ember Multi-Agent Orchestrator
အထူးပြု Agent များကို စီမံခြင်း
"""

class AgentRegistry:
    """Agent များကို Register လုပ်ခြင်း"""
    
    def __init__(self):
        self.agents = {}
    
    def register(self, name, agent_func, description=""):
        self.agents[name] = {
            "func": agent_func,
            "description": description
        }
        print(f"✓ Agent registered: {name}")
    
    def list_agents(self):
        return list(self.agents.keys())
    
    def call(self, name, *args, **kwargs):
        if name not in self.agents:
            raise ValueError(f"Unknown agent: {name}")
        return self.agents[name]["func"](*args, **kwargs)


# ===== ဥပမာ Agent များ =====

def researcher_agent(query):
    """Web Research လုပ်တဲ့ Agent"""
    return f"[Researcher] Searching for: {query}"

def coder_agent(task):
    """Code ရေးတဲ့ Agent"""
    return f"[Coder] Writing code for: {task}"

def reviewer_agent(code):
    """Code Review လုပ်တဲ့ Agent"""
    return f"[Reviewer] Reviewing: {code[:50]}"


if __name__ == "__main__":
    registry = AgentRegistry()
    registry.register("researcher", researcher_agent, "Web research")
    registry.register("coder", coder_agent, "Code generation")
    registry.register("reviewer", reviewer_agent, "Code review")
    
    print(f"\nRegistered: {registry.list_agents()}")
    print(registry.call("researcher", "AI agents 2026"))
