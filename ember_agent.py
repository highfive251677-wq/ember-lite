#!/usr/bin/env python3
"""
Ember Lite - Full Stack Agent (P1 → P4)
=========================================
Ember Signal Terminal Operator
Tagline: "Signals to Evidence"

Layers:
- P1: Perception (Observers + Analysis)
- P2: Proactive (Triggers + Suggestions + Monitor)
- P3: Orchestration (Agent Registry + Evidence Graph)
- P4: Bridge (Transport + Signatures + Signed Graph + MCP)
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
    from ember_brain_light import EmberBrainLight
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
    ORCHESTRATOR_OK = True
except ImportError as e:
    ORCHESTRATOR_OK = False
    ORCHESTRATOR_ERROR = str(e)

# Wildfire AI (lazy — imported inside do_wildfire to save startup)
WILDFIRE_OK = True  # actual import checked at runtime

# Release Gate (P5)
try:
    from perception.release_gate import (
        evaluate_release as gate_evaluate,
        get_evaluation_history as gate_history,
        format_gate_report as gate_format
    )
    GATE_OK = True
except ImportError as e:
    GATE_OK = False
    GATE_ERROR = str(e)

# Bridge (P4)
try:
    from perception.bridge_transport import (
        init_bridge_db as bridge_init,
        heartbeat as bridge_heartbeat,
        get_transport_stats as bridge_stats
    )
    from perception.bridge_router import (
        route_command as bridge_route,
        process_inbox as bridge_inbox,
        graph_summary as bridge_graph,
        verify_graph_integrity as bridge_verify_graph
    )
    from perception.bridge_signatures import (
        sign as bridge_sign, verify as bridge_verify
    )
    from perception.bridge_mcp import get_mcp_info as bridge_mcp_info
    BRIDGE_OK = True
except ImportError as e:
    BRIDGE_OK = False
    BRIDGE_ERROR = str(e)


# =========================================================
# EMBER AGENT
# =========================================================

class EmberAgent:
    """Ember Signal Terminal Operator - Full Stack"""
    
    def __init__(self):
        self.operator = os.getenv("USER", "unknown")
        self.name = "Ember Signal"
        self.tagline = "Signals to Evidence"
        
        # Init DBs
        if PROVENANCE_OK:
            try:
                init_db()
            except Exception:
                pass
        
        if BRIDGE_OK:
            try:
                bridge_init()
            except Exception:
                pass
        
        # Brain
        self.brain = None
        if BRAIN_OK:
            try:
                self.brain = EmberBrainLight(provider="openrouter")
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
                self.registry.register("researcher", researcher_agent, "Web research")
                self.registry.register("coder", coder_agent, "Code generation")
                self.registry.register("reviewer", reviewer_agent, "Code review")
            except Exception:
                self.registry = None
        
        self._print_banner()
    
    # =========================================================
    # BANNER
    # =========================================================
    
    def _print_banner(self):
        def st(ok):
            return "[green]✓[/green]" if ok else "[red]✗[/red]"
        
        banner = (
            f"[bold green]🌸 {self.name}[/bold green]\n"
            f"[dim]\"{self.tagline}\"[/dim]\n\n"
            f"[dim]Operator:     {self.operator}[/dim]\n"
            f"[dim]Brain:        {st(self.brain is not None)}[/dim]\n"
            f"[dim]Safety:       {st(SAFETY_OK)}[/dim]\n"
            f"[dim]Perception:   {st(PERCEPTION_OK)}[/dim]\n"
            f"[dim]Proactive:    {st(PROACTIVE_OK)}[/dim]\n"
            f"[dim]Orchestrator: {st(ORCHESTRATOR_OK)}[/dim]\n"
            f"[dim]Bridge:       {st(BRIDGE_OK)}[/dim]\n"
            f"[dim]Release Gate: {st(GATE_OK)}[/dim]\n"
            f"[dim]Lessons:      {st(LESSONS_OK)}[/dim]"
        )
        console.print(Panel.fit(banner, border_style="green"))
        
        # Warnings
        if not BRIDGE_OK:
            console.print(f"[yellow]⚠️  Bridge: {BRIDGE_ERROR}[/yellow]")
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
                    "terminal_command", command, "ember_agent", f"Safety: {level}"
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
        
        if PROVENANCE_OK:
            try:
                log_action(
                    "perception", f"perceive({observer_filter or 'all'})",
                    "ember_perception",
                    f"Status: {report['analysis'].get('overall_status')}"
                )
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
                console.print(
                    f"   Triggers: {result['triggers_count']} | "
                    f"Suggestions: {result['suggestions_count']}"
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
    # ORCHESTRATION (P3)
    # =========================================================
    
    def do_agents(self):
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
        if not ORCHESTRATOR_OK or not self.registry:
            console.print("[red]❌ Orchestrator missing.[/red]")
            return
        if not task:
            console.print("[yellow]Usage: orchestrate <task>[/yellow]")
            return
        
        console.print(f"\n[dim]🎭 Orchestrating: {task}[/dim]\n")
        results = {}
        
        for agent_name in self.registry.list_agents():
            console.print(f"[bold cyan]▶ Calling {agent_name}...[/bold cyan]")
            try:
                result = self.registry.call(agent_name, task)
                results[agent_name] = result
                console.print(f"[green]   ✓ {result}[/green]")
            except Exception as e:
                console.print(f"[red]   ✗ {agent_name}: {e}[/red]")
                results[agent_name] = f"ERROR: {e}"
        
        if self.brain and results:
            console.print("\n[dim]🧠 Ember က ပေါင်းစပ်နေသည်...[/dim]")
            results_text = "\n".join(f"- {k}: {v}" for k, v in results.items())
            prompt = f"""Agent ရလဒ်တွေကို ပေါင်းစပ်ပါ:

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
                log_action("orchestration", task, "ember_orchestrator",
                           f"{len(results)} agents")
            except Exception:
                pass
    
    # =========================================================
    # BRIDGE (P4)
    # =========================================================
    
    def do_route(self, command: str, sender: str):
        if not BRIDGE_OK:
            console.print("[red]❌ Bridge missing.[/red]")
            return
        if not command:
            console.print(f"[yellow]Usage: {sender} <command>[/yellow]")
            return
        
        console.print(f"\n[dim]📤 Routing from {sender}: {command}[/dim]")
        try:
            result = bridge_route(command, sender)
            if result.get("status") in ("sent", "duplicate"):
                icon = "✅" if result.get("signed") else "⚠️"
                console.print(f"[green]{icon} Routed ({result['status']})[/green]")
                console.print(f"[dim]   Channel: {result['channel']}[/dim]")
                console.print(f"[dim]   Signed: {result.get('signed')}[/dim]")
            else:
                console.print(f"[red]❌ {result.get('error')}[/red]")
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
    
    def do_bridge_status(self):
        if not BRIDGE_OK:
            console.print("[red]❌ Bridge missing.[/red]")
            return
        try:
            stats = bridge_stats()
            table = Table(title="🌉 Bridge Status")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            for k, v in stats.items():
                table.add_row(k, str(v))
            console.print(table)
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
    
    def do_bridge_inbox(self):
        if not BRIDGE_OK:
            console.print("[red]❌ Bridge missing.[/red]")
            return
        try:
            msgs = bridge_inbox("T", limit=10)
            if not msgs:
                console.print("[dim]📭 No pending messages.[/dim]")
                return
            
            table = Table(title="📥 Inbox (Termux)")
            table.add_column("From", style="cyan")
            table.add_column("Command", style="white")
            table.add_column("Verified", style="green")
            table.add_column("Time", style="dim")
            
            for m in msgs:
                icon = "✅" if m.get("verified") else "❌"
                cmd_text = str(m["payload"].get("command", ""))[:40]
                table.add_row(
                    m["sender"], cmd_text, icon,
                    m.get("created_at", "")[:19]
                )
            console.print(table)
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
    
    def do_sign(self, text: str):
        if not BRIDGE_OK:
            console.print("[red]❌ Bridge missing.[/red]")
            return
        if not text:
            console.print("[yellow]Usage: sign <text>[/yellow]")
            return
        try:
            result = bridge_sign(text, terminal="T")
            console.print(Panel.fit(
                f"[cyan]Payload:[/cyan]   {text[:60]}\n"
                f"[cyan]Signature:[/cyan] {result['signature'][:48]}...\n"
                f"[cyan]Algorithm:[/cyan] {result['algorithm']}",
                title="🔐 Signature",
                border_style="cyan"
            ))
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
    
    def do_graph(self):
        if not BRIDGE_OK:
            console.print("[red]❌ Bridge missing.[/red]")
            return
        try:
            gs = bridge_graph()
            console.print(Panel.fit(
                f"[cyan]Nodes:[/cyan]      {gs['nodes']}\n"
                f"[cyan]Edges:[/cyan]      {gs['edges']}\n"
                f"[cyan]Terminals:[/cyan]  {gs['terminals']}",
                title="📊 Signed Evidence Graph",
                border_style="cyan"
            ))
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
    
    def do_verify_graph(self):
        if not BRIDGE_OK:
            console.print("[red]❌ Bridge missing.[/red]")
            return
        try:
            vi = bridge_verify_graph()
            color = "green" if vi["invalid"] == 0 else "red"
            console.print(Panel.fit(
                f"[cyan]Total:[/cyan]    {vi['total']}\n"
                f"[green]Valid:[/green]    {vi['valid']}\n"
                f"[{color}]Invalid:[/{color}]  {vi['invalid']}",
                title="🔍 Graph Integrity",
                border_style=color
            ))
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
    
    def do_mcp(self):
        if not BRIDGE_OK:
            console.print("[red]❌ Bridge missing.[/red]")
            return
        try:
            info = bridge_mcp_info()
            tools = info["capabilities"]["tools"]
            terminals = info["capabilities"]["terminals"]
            console.print(Panel.fit(
                f"[cyan]Name:[/cyan]       {info['name']}\n"
                f"[cyan]Version:[/cyan]    {info['version']}\n"
                f"[cyan]Tools:[/cyan]      {len(tools)}\n"
                f"[cyan]Transport:[/cyan]  {info['capabilities']['transport']}\n"
                f"[cyan]Terminals:[/cyan]  {', '.join(terminals)}",
                title="🔌 MCP Interface",
                border_style="cyan"
            ))
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
    
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
    # IDENTITY / ASK / HISTORY / HELP
    # =========================================================
    

    # =========================================================
    # RELEASE GATE METHODS (P5)
    # =========================================================
    
    def do_gate(self):
        """Release Gate Evaluation ကို Run လုပ်ခြင်း"""
        if not GATE_OK:
            console.print("[red]❌ Release Gate missing.[/red]")
            return
        
        console.print("\n[dim]🚦 Ember က Release Gate ကို စစ်ဆေးနေသည်...[/dim]\n")
        
        with console.status("[bold green]Evaluating 6 gates..."):
            try:
                result = gate_evaluate(self.last_perception)
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")
                return
        
        console.print(gate_format(result))
    
    def do_gate_history(self):
        """Release Gate သမိုင်းကြောင်း"""
        if not GATE_OK:
            console.print("[red]❌ Release Gate missing.[/red]")
            return
        
        history = gate_history(10)
        if not history:
            console.print("[yellow]⚠️  သမိုင်းကြောင်း မရှိပါ။[/yellow]")
            return
        
        table = Table(title="🚦 Release Gate History")
        table.add_column("ID", style="cyan")
        table.add_column("Decision", style="magenta")
        table.add_column("Score", style="yellow")
        table.add_column("Gates", style="white")
        table.add_column("At", style="dim")
        
        for h in history:
            icon = {"SHIP": "✅", "HOLD": "⚠️",
                    "REVIEW": "🔶", "NO_SHIP": "⛔"}.get(h["decision"], "•")
            table.add_row(
                h["id"], f"{icon} {h['decision']}",
                str(h["score"]), h["passed"], h["at"][:19]
            )
        console.print(table)

    # =========================================================
    # WILDFIRE METHODS (Task B)
    # =========================================================

    def do_wildfire(self, argument: str = ""):
        """Run wildfire assessment demo. Lazy import to save startup."""
        try:
            from perception.wildfire_assessment import (
                assess_wildfire, persist_wildfire_decision,
            )
            from perception.wildfire_gate import evaluate_wildfire_gate
        except ImportError as e:
            console.print(f"[red]❌ Wildfire module missing: {e}[/red]")
            return

        argument = (argument or "demo").strip().lower()

        if argument not in ("", "demo", "status"):
            console.print("[yellow]Usage: wildfire [demo|status][/yellow]")
            return

        if argument == "status":
            from perception.decision_log import count_decisions, get_decisions
            from perception.evidence_chain import get_chain_summary
            try:
                table = Table(title="🔥 Wildfire Status")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                table.add_row("Decisions logged", str(count_decisions()))
                chain = get_chain_summary()
                table.add_row("Chain blocks", str(chain.get("blocks", 0)))
                table.add_row("Chain tip", str(chain.get("tip_hash", "-")))
                console.print(table)
            except Exception as e:
                console.print(f"[red]❌ Status error: {e}[/red]")
            return

        # Demo mode
        console.print("\n[dim]🔥 Ember Wildfire — Demo Assessment[/dim]\n")

        event = {
            "event_id": "CLI-EVT-001",
            "sensor_id": "CLI-SENSOR-001",
            "zone_id": "zone-demo",
            "captured_at": "2026-09-18T12:00:00Z",
            "pm25": 176.0,
            "temperature_c": 42.1,
            "humidity_percent": 24.0,
            "health_status": "healthy",
            "is_stale": False,
        }
        baseline = {
            "pm25": 18.0,
            "temperature_c": 30.0,
            "humidity_percent": 42.0,
        }
        neighbors = [{
            "event_id": "CLI-EVT-002",
            "sensor_id": "CLI-SENSOR-002",
            "pm25": 121.0,
        }]

        alert = assess_wildfire(
            incident_id="CLI-INC-001",
            event=event,
            baseline=baseline,
            neighbors=neighbors,
            wind_toward_zone=True,
        )

        # Gate context
        conf = alert.get("confidence", 0.0)
        chain = alert.get("chain", {})
        gate_ctx = {
            "evidence_quality": int(conf * 100),
            "sensor_health": 90,
            "corroboration": 75,
            "temporal_consistency": 60,
            "policy_compliance": 100 if chain.get("available") else 0,
            "requires_human_approval": alert.get("requires_human_approval", True),
        }
        alert["gate"] = evaluate_wildfire_gate(gate_ctx)
        alert = persist_wildfire_decision(alert)

        # Display
        console.print(Panel.fit(
            f"[bold]Assessment:[/bold]  {alert['assessment']}\n"
            f"[bold]Severity:[/bold]    {alert['severity']}\n"
            f"[bold]Confidence:[/bold]  {alert['confidence']}\n"
            f"[bold]Gate:[/bold]        {alert['gate']['decision']} "
            f"({alert['gate']['score']}/100)\n"
            f"[bold]Human Approval:[/bold] "
            f"{'REQUIRED' if alert['requires_human_approval'] else 'NOT REQUIRED'}\n"
            f"[bold]Chain:[/bold]       "
            f"{'OK' if chain.get('available') else 'FAILED'}\n"
            f"[bold]Decision Log:[/bold] "
            f"{'recorded #' + str(alert['decision_log']['decision_id']) if alert['decision_log']['available'] else 'FAILED'}",
            title="🔥 Wildfire Result",
            border_style="red"
        ))
        console.print(f"\n[dim]{alert['summary']}[/dim]\n")

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
            f"[bold cyan]Name:[/bold cyan]       {EMBER_IDENTITY['name']}\n"
            f"[bold cyan]Tagline:[/bold cyan]    {EMBER_IDENTITY['tagline']}\n"
            f"[bold cyan]Archetype:[/bold cyan]  {EMBER_IDENTITY['personality']['archetype']}\n"
            f"[bold cyan]Category:[/bold cyan]   {EMBER_IDENTITY['market_identity']['category']}\n"
            f"[bold cyan]Role:[/bold cyan]       Evidence & Audit Layer",
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
            "  agents / orchestrate <task>\n\n"
            "[bold cyan]🌉 Bridge (P4):[/bold cyan]\n"
            "  @ <cmd>        - a-Shell ကို ပို့\n"
            "  T <cmd>        - Termux ကို ပို့\n"
            "  bridge         - Bridge Status\n"
            "  bridge inbox   - Messages ရယူ\n"
            "  sign <text>    - Ed25519 Sign\n"
            "  graph          - Signed Graph\n"
            "  graph verify   - Integrity Check\n"
            "  mcp            - MCP Interface\n\n"
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
                
                # ===== EXIT =====
                if cmd_lower in ["exit", "quit"]:
                    console.print("[dim]👋 Goodbye![/dim]")
                    break
                
                # ===== IDENTITY =====
                if cmd_lower == "whoami": self.do_whoami(); continue
                if cmd_lower == "identity": self.do_identity(); continue
                if cmd_lower == "history": self.do_history(); continue
                if cmd_lower == "help": self.do_help(); continue
                
                # ===== PERCEPTION =====
                if cmd_lower == "perceive": self.do_perceive(); continue
                if cmd_lower.startswith("perceive "):
                    f = cmd_stripped[9:].strip()
                    self.do_perceive(observer_filter=[f]); continue
                if cmd_lower == "analyze": self.do_analyze(); continue
                
                # ===== PROACTIVE =====
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
                
                # ===== ORCHESTRATION =====
                if cmd_lower == "agents": self.do_agents(); continue
                if cmd_lower.startswith("orchestrate "):
                    task = cmd_stripped[12:].strip()
                    self.do_orchestrate(task); continue
                
                # ===== BRIDGE (P4) =====
                if cmd_stripped.startswith("@ "):
                    self.do_route(cmd_stripped[2:].strip(), "@"); continue
                if cmd_stripped.startswith("T "):
                    self.do_route(cmd_stripped[2:].strip(), "T"); continue
                if cmd_lower == "bridge": self.do_bridge_status(); continue
                if cmd_lower == "bridge inbox": self.do_bridge_inbox(); continue
                if cmd_lower.startswith("sign "):
                    self.do_sign(cmd_stripped[5:].strip()); continue
                if cmd_lower == "graph": self.do_graph(); continue
                if cmd_lower == "graph verify": self.do_verify_graph(); continue
                if cmd_lower == "mcp": self.do_mcp(); continue

                # ===== RELEASE GATE (P5) =====
                if cmd_lower == "gate":
                    self.do_gate(); continue
                if cmd_lower == "gate history":
                    self.do_gate_history(); continue

                
                # ===== LESSONS =====
                # ===== WILDFIRE (Task B) =====
                if cmd_lower == "wildfire":
                    self.do_wildfire("demo"); continue
                if cmd_lower.startswith("wildfire "):
                    self.do_wildfire(cmd_stripped[9:].strip()); continue

                if cmd_lower == "lessons": self.do_lessons(); continue
                if cmd_lower.startswith("check "):
                    self.do_check_lessons(cmd_stripped[6:].strip()); continue
                
                # ===== ASK =====
                if cmd_lower.startswith("ask "):
                    q = cmd_stripped[4:].strip()
                    if q:
                        self.do_ask(q)
                    else:
                        console.print("[yellow]Usage: ask <q>[/yellow]")
                    continue
                
                # ===== TERMINAL =====
                self.execute(cmd_stripped)
                console.print()
            
            except KeyboardInterrupt:
                console.print("\n[dim]👋 Interrupted.[/dim]")
                break
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")


# =========================================================
# MAIN
# =========================================================

def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() == "verify":
        from ember_release import main as verify_main
        original_argv = sys.argv[:]
        try:
            sys.argv = ["ember-signal verify", *sys.argv[2:]]
            raise SystemExit(verify_main())
        finally:
            sys.argv = original_argv
    try:
        agent = EmberAgent()
        agent.run()
    except Exception as e:
        console.print(f"[red]❌ Fatal: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
