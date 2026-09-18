#!/usr/bin/env python3
"""
Ember Lite - Multi-Agent Orchestration Agent (P3)
===================================================
Ember Signal ရဲ့ Terminal Operator
Tagline: "Signals to Evidence"

Features:
- Identity Awareness
- LLM Brain
- Perception (P1)
- Proactive Suggestions (P2)
- Multi-Agent Orchestration (P3) ← NEW!
- Evidence Graph (P3) ← NEW!
- Self-Learning Lessons
"""

import sys
import subprocess
import os
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table


# =========================================================
# SAFE IMPORTS
# =========================================================

console = Console()

# Identity
try:
    from ember_identity import EMBER_IDENTITY, describe_self
    IDENTITY_OK = True
except ImportError as e:
    IDENTITY_OK = False
    IDENTITY_ERROR = str(e)

# Brain
try:
    from ember_brain import EmberBrain
    BRAIN_OK = True
except ImportError as e:
    BRAIN_OK = False
    BRAIN_ERROR = str(e)

# Safety
try:
    from safety import check_command, requires_approval
    SAFETY_OK = True
except ImportError as e:
    SAFETY_OK = False
    SAFETY_ERROR = str(e)

# Provenance
try:
    from provenance import (
        init_db, log_action, log_approval, get_action_history
    )
    PROVENANCE_OK = True
except ImportError as e:
    PROVENANCE_OK = False
    PROVENANCE_ERROR = str(e)

# Perception (P1)
try:
    from perception.layer import perceive, perceive_summary
    PERCEPTION_OK = True
except ImportError as e:
    PERCEPTION_OK = False
    PERCEPTION_ERROR = str(e)

# Proactive (P2)
try:
    from perception.triggers import TriggerEngine
    from perception.suggestion import SuggestionGenerator
    from perception.monitor import PerceptionMonitor
    PROACTIVE_OK = True
except ImportError as e:
    PROACTIVE_OK = False
    PROACTIVE_ERROR = str(e)

# Lessons
try:
    from perception.lessons import (
        get_lessons, check_for_pattern, summary as lessons_summary
    )
    LESSONS_OK = True
except ImportError as e:
    LESSONS_OK = False
    LESSONS_ERROR = str(e)

# Orchestrator (P3)
try:
    from perception.orchestrator import (
        AgentRegistry, researcher_agent, coder_agent, reviewer_agent
    )
    from perception.evidence_graph import (
        init_graph_db, add_node, add_edge, get_graph_summary
    )
    ORCHESTRATOR_OK = True
except ImportError as e:
    ORCHESTRATOR_OK = False
    ORCHESTRATOR_ERROR = str(e)


# =========================================================
# EMBER AGENT
# =========================================================

class EmberAgent:
    """Ember Signal Terminal Operator - Multi-Agent Edition"""
    
    def __init__(self):
        self.operator = os.getenv("USER", "unknown")
        self.name = "Ember Signal"
        self.tagline = "Signals to Evidence"
        
        # DB Init
        if PROVENANCE_OK:
            try:
                init_db()
            except Exception:
                pass
        
        if ORCHESTRATOR_OK:
            try:
                init_graph_db()
            except Exception:
                pass
        
        # Brain
        self.brain = None
        if BRAIN_OK:
            try:
                self.brain = EmberBrain(provider="openrouter")
            except Exception:
                self.brain = None
        
        # Monitor
        self.monitor = None
        self.last_perception = None
        
        # Agent Registry (P3)
        self.registry = None
        if ORCHESTRATOR_OK:
            try:
                self.registry = AgentRegistry()
                self.registry.register(
                    "researcher", researcher_agent, "Web research"
                )
                self.registry.register(
                    "coder", coder_agent, "Code generation"
                )
                self.registry.register(
                    "reviewer", reviewer_agent, "Code review"
                )
            except Exception:
                self.registry = None
        
        self._print_banner()
    
    # =========================================================
    # BANNER
    # =========================================================
    
    def _print_banner(self):
        brain_status = "[green]✓[/green]" if self.brain else "[red]✗[/red]"
        perception_status = "[green]✓[/green]" if PERCEPTION_OK else "[red]✗[/red]"
        proactive_status = "[green]✓[/green]" if PROACTIVE_OK else "[red]✗[/red]"
        lessons_status = "[green]✓[/green]" if LESSONS_OK else "[red]✗[/red]"
        safety_status = "[green]✓[/green]" if SAFETY_OK else "[red]✗[/red]"
        orch_status = "[green]✓[/green]" if ORCHESTRATOR_OK else "[red]✗[/red]"
        
        banner = (
            f"[bold green]🌸 {self.name}[/bold green]\n"
            f"[dim]\"{self.tagline}\"[/dim]\n\n"
            f"[dim]Operator:     {self.operator}[/dim]\n"
            f"[dim]Brain:        {brain_status}[/dim]\n"
            f"[dim]Safety:       {safety_status}[/dim]\n"
            f"[dim]Perception:   {perception_status}[/dim]\n"
            f"[dim]Proactive:    {proactive_status}[/dim]\n"
            f"[dim]Orchestrator: {orch_status}[/dim]\n"
            f"[dim]Lessons:      {lessons_status}[/dim]"
        )
        
        console.print(Panel.fit(banner, border_style="green"))
        
        if not ORCHESTRATOR_OK:
            console.print(f"[yellow]⚠️  Orchestrator: {ORCHESTRATOR_ERROR}[/yellow]")
    
    # =========================================================
    # EXECUTE (Core)
    # =========================================================
    
    def execute(self, command: str) -> bool:
        if not SAFETY_OK:
            console.print("[red]❌ Safety module missing.[/red]")
            return False
        
        level, reason = check_command(command)
        
        action_id, content_hash = None, None
        if PROVENANCE_OK:
            try:
                action_id, content_hash = log_action(
                    "terminal_command", command, "ember_agent",
                    f"Safety: {level}"
                )
            except Exception:
                pass
        
        color = {
            "SAFE": "green", "MEDIUM": "yellow",
            "HIGH": "orange1", "CRITICAL": "red"
        }.get(level, "white")
        
        console.print(f"\n[{color}]🔒 Safety Level: {level}[/{color}]")
        console.print(f"[dim]   Reason: {reason}[/dim]")
        if content_hash:
            console.print(f"[dim]   Hash: {content_hash}[/dim]")
        
        if requires_approval(level):
            if level == "CRITICAL":
                console.print("[bold red]⛔ CRITICAL - Blocked![/bold red]")
                return False
            if not Confirm.ask(f"Execute: {command}?"):
                console.print("[dim]❌ Cancelled.[/dim]")
                return False
            if PROVENANCE_OK and action_id:
                try:
                    log_approval(action_id, self.operator, "Approved")
                except Exception:
                    pass
            console.print("[green]✅ Approved.[/green]")
        
        console.print(f"\n[bold]▶ Executing:[/bold] {command}\n")
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True,
                text=True, timeout=30
            )
            if result.stdout:
                console.print(result.stdout)
            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]")
            console.print(f"\n[dim]Exit code: {result.returncode}[/dim]")
            return True
        except subprocess.TimeoutExpired:
            console.print("[red]⏱️  Timeout (30s)[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            return False
    
    # =========================================================
    # PERCEPTION (P1)
    # =========================================================
    
    def do_perceive(self, observer_filter=None):
        if not PERCEPTION_OK:
            console.print("[red]❌ Perception missing.[/red]")
            return
        console.print("\n[dim]🔍 Ember က စောင့်ကြည့်နေသည်...[/dim]\n")
        with console.status("[bold green]Collecting..."):
            try:
                report = perceive(observer_filter=observer_filter, save=True)
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")
                return
        self.last_perception = report
        console.print(perceive_summary(report))
        
        # Evidence Graph ထဲ မှတ်တမ်းတင်ခြင်း (P3)
        if ORCHESTRATOR_OK:
            try:
                obs_node = add_node(
                    "observation",
                    f"perceive({observer_filter or 'all'})",
                    report["analysis"].get("overall_status")
                )
                for source, obs in report["observations"].items():
                    src_node = add_node("source", source, obs.get("status"))
                    add_edge(obs_node, src_node, "observed_from")
            except Exception:
                pass
    
    def do_analyze(self):
        if not self.last_perception:
            console.print("[yellow]⚠️  Run 'perceive' first.[/yellow]")
            return
        if not self.brain:
            console.print("[red]❌ Brain offline.[/red]")
            return
        
        console.print("\n[dim]🧠 Ember က ခွဲခြမ်းစိတ်ဖြာနေသည်...[/dim]\n")
        summary = perceive_summary(self.last_perception)
        prompt = f"""Perception Report ကို ခွဲခြမ်းစိတ်ဖြာပါ:

{summary}

Format:
1. SITUATION: (၁-၂ ကြောင်း)
2. PRIORITY: (၁ ခု)
3. NEXT ACTION: (bounded)
4. REASON:"""
        
        try:
            response = self.brain.think(prompt, EMBER_IDENTITY)
            console.print(Panel(response, title="🌸 Ember's Analysis", border_style="cyan"))
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
    
    # =========================================================
    # PROACTIVE (P2)
    # =========================================================
    
    def do_suggest(self):
        if not PERCEPTION_OK or not PROACTIVE_OK:
            console.print("[red]❌ Modules missing.[/red]")
            return
        console.print("\n[dim]💡 စဉ်းစားနေသည်...[/dim]\n")
        try:
            report = perceive(save=True)
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            return
        self.last_perception = report
        
        engine = TriggerEngine()
        triggers = engine.evaluate(report["analysis"])
        
        if not triggers:
            console.print(Panel(
                "✨ အကြံပြုချက် မရှိပါ။",
                title="🌸 Ember", border_style="green"
            ))
            return
        
        generator = SuggestionGenerator(brain=self.brain)
        suggestions = generator.generate(triggers)
        console.print(engine.summary())
        console.print()
        console.print(generator.format_suggestions(suggestions))
        
        if self.brain and engine.has_critical():
            console.print("\n[dim]🧠 Deep analysis...[/dim]")
            try:
                llm_analysis = generator.generate_with_brain(triggers)
                console.print(Panel(
                    llm_analysis,
                    title="🌸 Deep Analysis", border_style="red"
                ))
            except Exception as e:
                console.print(f"[red]❌ {e}[/red]")
    
    def do_monitor(self, iterations: int = 3):
        if not PROACTIVE_OK:
            console.print("[red]❌ Monitor missing.[/red]")
            return
        console.print(f"\n[dim]👁️  Monitor ({iterations} iter)...[/dim]\n")
        if not self.monitor:
            self.monitor = PerceptionMonitor(interval_minutes=15, brain=self.brain)
        
        def on_suggestion(suggestions):
            console.print()
            for s in suggestions:
                icon = {"critical": "🚨", "high": "⚠️",
                        "medium": "⚡", "low": "ℹ️"}.get(s["severity"], "•")
                console.print(f"   {icon} [{s['severity'].upper()}] {s['message']}")
                console.print(f"      → {s['action']}")
        
        for i in range(iterations):
            console.print(f"\n[bold]🔍 Iteration {i + 1}/{iterations}[/bold]")
            try:
                result = self.monitor.run_once(callback=on_suggestion)
                console.print(
                    f"\n   Status: {result['overall_status']} "
                    f"({result['overall_confidence']}%)"
                )
            except Exception as e:
                console.print(f"[red]❌ {e}[/red]")
        
        console.print("\n[bold]📊 Stats:[/bold]")
        for k, v in self.monitor.get_stats().items():
            console.print(f"   {k}: {v}")
    
    def do_stats(self):
        if not self.monitor:
            console.print("[yellow]⚠️  Run 'monitor' first.[/yellow]")
            return
        table = Table(title="📊 Monitor Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        for k, v in self.monitor.get_stats().items():
            table.add_row(k, str(v))
        console.print(table)
    
    def do_suggestions_history(self):
        if not self.monitor or not self.monitor.suggestions_history:
            console.print("[yellow]⚠️  No history.[/yellow]")
            return
        table = Table(title="💡 Suggestion History")
        table.add_column("#", style="cyan")
        table.add_column("Time", style="magenta")
        table.add_column("Count", style="yellow")
        table.add_column("Top", style="white")
        for i, h in enumerate(reversed(self.monitor.suggestions_history[-10:]), 1):
            top = h["suggestions"][0] if h["suggestions"] else {}
            table.add_row(str(i), h["timestamp"][:19], str(h["count"]),
                          top.get("message", "")[:50])
        console.print(table)
    
    # =========================================================
    # ORCHESTRATOR (P3) - NEW!
    # =========================================================
    
    def do_agents(self):
        """Register လုပ်ထားတဲ့ Agent စာရင်း"""
        if not ORCHESTRATOR_OK or not self.registry:
            console.print("[red]❌ Orchestrator missing.[/red]")
            return
        
        console.print()
        table = Table(title="🤖 Agent Registry")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="green")
        
        for name in self.registry.list_agents():
            info = self.registry.agents[name]
            table.add_row(name, info.get("description", ""))
        
        console.print(table)
    
    def do_orchestrate(self, task: str):
        """Agent တွေကို ခေါ်ပြီး Task လုပ်ခိုင်းခြင်း"""
        if not ORCHESTRATOR_OK or not self.registry:
            console.print("[red]❌ Orchestrator missing.[/red]")
            return
        
        if not task:
            console.print("[yellow]Usage: orchestrate <task>[/yellow]")
            return
        
        console.print(f"\n[dim]🎭 Orchestrating: {task}[/dim]\n")
        
        # Task Node ကို Graph ထဲ ထည့်
        try:
            task_node = add_node("task", task, "orchestration")
        except Exception:
            task_node = None
        
        results = {}
        
        # Agent အားလုံးကို ခေါ်
        for agent_name in self.registry.list_agents():
            console.print(f"[bold cyan]▶ Calling {agent_name}...[/bold cyan]")
            try:
                result = self.registry.call(agent_name, task)
                results[agent_name] = result
                console.print(f"[green]   ✓ {result}[/green]")
                
                # Graph ထဲ မှတ်တမ်းတင်ခြင်း
                if task_node:
                    try:
                        agent_node = add_node(
                            "agent_output", agent_name, result
                        )
                        add_edge(task_node, agent_node, "produced_by")
                    except Exception:
                        pass
            except Exception as e:
                console.print(f"[red]   ✗ {agent_name}: {e}[/red]")
                results[agent_name] = f"ERROR: {e}"
        
        # Brain ရှိရင် Synthesis လုပ်ခိုင်း
        if self.brain and results:
            console.print("\n[dim]🧠 Ember က ရလဒ်တွေကို ပေါင်းစပ်နေသည်...[/dim]")
            
            results_text = "\n".join(
                f"- {k}: {v}" for k, v in results.items()
            )
            prompt = f"""ဒီ Agent ရလဒ်တွေကို ပေါင်းစပ်ပါ:

TASK: {task}

RESULTS:
{results_text}

Format:
1. SYNTHESIS: (၂-၃ ကြောင်း)
2. RECOMMENDATION: (bounded)
3. CONFIDENCE: (0-100)"""
            
            try:
                synthesis = self.brain.think(prompt, EMBER_IDENTITY)
                console.print(Panel(
                    synthesis,
                    title="🌸 Orchestration Synthesis",
                    border_style="green"
                ))
            except Exception as e:
                console.print(f"[red]❌ {e}[/red]")
        
        if PROVENANCE_OK:
            try:
                log_action(
                    "orchestration", task, "ember_orchestrator",
                    f"{len(results)} agents"
                )
            except Exception:
                pass
    
    def do_graph(self):
        """Evidence Graph Summary"""
        if not ORCHESTRATOR_OK:
            console.print("[red]❌ Graph missing.[/red]")
            return
        
        try:
            summary = get_graph_summary()
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
            return
        
        console.print()
        console.print(Panel.fit(
            f"[bold cyan]Evidence Graph[/bold cyan]\n\n"
            f"[dim]Nodes: {summary['nodes']}[/dim]\n"
            f"[dim]Edges: {summary['edges']}[/dim]",
            title="📊 Graph Summary",
            border_style="cyan"
        ))
    
    # =========================================================
    # LESSONS
    # =========================================================
    
    def do_lessons(self):
        if not LESSONS_OK:
            console.print("[red]❌ Lessons missing.[/red]")
            return
        console.print()
        try:
            console.print(lessons_summary())
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
            return
        
        lessons = get_lessons(limit=5)
        if lessons:
            table = Table(title="📚 Top Lessons")
            table.add_column("ID", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Mistake", style="white")
            table.add_column("Count", style="yellow")
            for lesson in lessons:
                table.add_row(
                    f"#{lesson['id']}", lesson["type"],
                    lesson["mistake"][:40],
                    f"{lesson['times_encountered']}x"
                )
            console.print(table)
    
    def do_check_lessons(self, code: str):
        if not LESSONS_OK:
            console.print("[red]❌ Lessons missing.[/red]")
            return
        if not code:
            console.print("[yellow]Usage: check <code>[/yellow]")
            return
        
        warnings = check_for_pattern(code)
        if not warnings:
            console.print(Panel("✅ ပြဿနာ မရှိပါ။",
                                title="🌸 Check", border_style="green"))
            return
        
        console.print(Panel(
            f"⚠️  {len(warnings)} warning(s)",
            title="🌸 Check", border_style="yellow"
        ))
        for w in warnings:
            icon = {"critical": "🚨", "high": "⚠️",
                    "medium": "⚡", "low": "ℹ️"}.get(w["severity"], "•")
            console.print(f"\n{icon} [red][{w['severity'].upper()}] "
                          f"Lesson #{w['lesson_id']}[/red]")
            console.print(f"   [yellow]Mistake:[/yellow] {w['warning']}")
            console.print(f"   [green]Fix:[/green] {w['fix']}")
    
    # =========================================================
    # IDENTITY / ASK
    # =========================================================
    
    def do_ask(self, question: str):
        if not self.brain:
            console.print("[red]❌ Brain offline.[/red]")
            return
        console.print("\n[dim]🧠 စဉ်းစားနေသည်...[/dim]")
        
        context_parts = []
        if PROVENANCE_OK:
            try:
                recent = get_action_history(3)
                if recent:
                    context_parts.append("Recent:")
                    for r in recent:
                        context_parts.append(f"- {r[1]}: {r[2][:50]}")
            except Exception:
                pass
        
        if self.last_perception:
            a = self.last_perception.get("analysis", {})
            context_parts.append(
                f"Last perception: {a.get('overall_status')} "
                f"({a.get('overall_confidence')}%)"
            )
        
        context = "\n".join(context_parts) if context_parts else "No context."
        
        try:
            response = self.brain.think(question, EMBER_IDENTITY, context)
            console.print(Panel(response, title="🌸 Ember", border_style="cyan"))
            if PROVENANCE_OK:
                log_action("llm_thought", question, "ember_brain", response[:200])
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
    
    def do_whoami(self):
        if not IDENTITY_OK:
            console.print("[red]❌ Identity missing.[/red]")
            return
        console.print(Panel.fit(
            f"[bold cyan]Name:[/bold cyan] {EMBER_IDENTITY['name']}\n"
            f"[bold cyan]Tagline:[/bold cyan] {EMBER_IDENTITY['tagline']}\n"
            f"[bold cyan]Archetype:[/bold cyan] {EMBER_IDENTITY['personality']['archetype']}\n"
            f"[bold cyan]Category:[/bold cyan] {EMBER_IDENTITY['market_identity']['category']}\n"
            f"[bold cyan]Role:[/bold cyan] Evidence & Audit Layer",
            title="🌸 Ember Self-Awareness",
            border_style="cyan"
        ))
        console.print("\n[bold]Values:[/bold]")
        for v in EMBER_IDENTITY["personality"]["values"]:
            console.print(f"  • [italic]{v}[/italic]")
    
    def do_identity(self):
        if not IDENTITY_OK:
            console.print("[red]❌ Identity missing.[/red]")
            return
        console.print(describe_self())
    
    def do_history(self):
        if not PROVENANCE_OK:
            console.print("[red]❌ Provenance missing.[/red]")
            return
        table = Table(title="📜 Action History")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Command", style="white")
        table.add_column("Status", style="green")
        table.add_column("Approved", style="yellow")
        try:
            for row in get_action_history(10):
                table.add_row(str(row[0]), row[1], row[2][:40],
                              row[3], row[4] or "-")
            console.print(table)
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
    
    def do_help(self):
        console.print(Panel.fit(
            "[bold]📖 Ember Commands[/bold]\n\n"
            "[bold cyan]🔍 Perception (P1):[/bold cyan]\n"
            "  perceive / perceive backend / analyze\n\n"
            "[bold cyan]💡 Proactive (P2):[/bold cyan]\n"
            "  suggest / monitor / monitor 5 / stats / suggestions\n\n"
            "[bold cyan]🎭 Orchestration (P3):[/bold cyan]\n"
            "  agents              - Agent စာရင်း\n"
            "  orchestrate <task>  - Agent တွေ ခေါ်ရန်\n"
            "  graph               - Evidence Graph Summary\n\n"
            "[bold cyan]📚 Lessons:[/bold cyan]\n"
            "  lessons / check <code>\n\n"
            "[bold cyan]🌸 Identity:[/bold cyan]\n"
            "  ask <q> / whoami / identity / history / help / exit\n\n"
            "[dim]Terminal Commands တွေလည်း run လို့ရပါတယ်။[/dim]",
            title="📖 Help", border_style="blue"
        ))
    
    # =========================================================
    # MAIN LOOP
    # =========================================================
    
    def run(self):
        console.print("\n[dim]Type 'help' for commands.[/dim]\n")
        
        while True:
            try:
                cmd = Prompt.ask("[bold cyan]ember[/bold cyan]")
                cmd_stripped = cmd.strip()
                cmd_lower = cmd_stripped.lower()
                
                if not cmd_stripped:
                    continue
                
                # Exit
                if cmd_lower in ["exit", "quit"]:
                    console.print("[dim]👋 Goodbye![/dim]")
                    break
                
                # Identity
                if cmd_lower == "whoami": self.do_whoami(); continue
                if cmd_lower == "identity": self.do_identity(); continue
                if cmd_lower == "history": self.do_history(); continue
                if cmd_lower == "help": self.do_help(); continue
                
                # Perception
                if cmd_lower == "perceive": self.do_perceive(); continue
                if cmd_lower.startswith("perceive "):
                    f = cmd_stripped[9:].strip()
                    self.do_perceive(observer_filter=[f]); continue
                if cmd_lower == "analyze": self.do_analyze(); continue
                
                # Proactive
                if cmd_lower == "suggest": self.do_suggest(); continue
                if cmd_lower == "monitor": self.do_monitor(iterations=3); continue
                if cmd_lower.startswith("monitor "):
                    try:
                        n = int(cmd_stripped[8:].strip())
                        self.do_monitor(iterations=n)
                    except ValueError:
                        console.print("[yellow]Usage: monitor [n][/yellow]")
                    continue
                if cmd_lower == "stats": self.do_stats(); continue
                if cmd_lower == "suggestions": self.do_suggestions_history(); continue
                
                # Orchestrator (P3)
                if cmd_lower == "agents": self.do_agents(); continue
                if cmd_lower.startswith("orchestrate "):
                    task = cmd_stripped[12:].strip()
                    self.do_orchestrate(task); continue
                if cmd_lower == "graph": self.do_graph(); continue
                
                # Lessons
                if cmd_lower == "lessons": self.do_lessons(); continue
                if cmd_lower.startswith("check "):
                    self.do_check_lessons(cmd_stripped[6:].strip()); continue
                
                # Ask
                if cmd_lower.startswith("ask "):
                    q = cmd_stripped[4:].strip()
                    if q: self.do_ask(q)
                    else: console.print("[yellow]Usage: ask <q>[/yellow]")
                    continue
                
                # Terminal
                self.execute(cmd_stripped)
                console.print()
            
            except KeyboardInterrupt:
                console.print("\n[dim]👋 Interrupted.[/dim]")
                break
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")


def main():
    try:
        agent = EmberAgent()
        agent.run()
    except Exception as e:
        console.print(f"[red]❌ Fatal: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
