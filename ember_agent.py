#!/usr/bin/env python3
"""
Ember Lite - Self-Aware Perception Agent
==========================================
Ember Signal ရဲ့ Terminal Operator
Tagline: "Signals to Evidence"

Features:
- Identity Awareness
- LLM Brain Integration
- Perception Layer (P1)
- Proactive Suggestions (P2)
- Self-Learning Lessons
- Safety + Provenance
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
# SAFE IMPORTS — Module တစ်ခုချင်း Fail ဖြစ်ရင် Handle
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


# =========================================================
# EMBER AGENT CLASS
# =========================================================

class EmberAgent:
    """Ember Signal Terminal Operator"""
    
    def __init__(self):
        # Operator
        self.operator = os.getenv("USER", "unknown")
        self.name = "Ember Signal"
        self.tagline = "Signals to Evidence"
        
        # Initialize DB
        if PROVENANCE_OK:
            try:
                init_db()
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
        
        # Welcome Banner
        self._print_banner()
    
    # =========================================================
    # BANNER
    # =========================================================
    
    def _print_banner(self):
        """Welcome Banner ပြသခြင်း"""
        # Status Checks
        brain_status = "[green]✓ Online[/green]" if self.brain else "[red]✗ Offline[/red]"
        perception_status = "[green]✓ Ready[/green]" if PERCEPTION_OK else "[red]✗ Missing[/red]"
        proactive_status = "[green]✓ Ready[/green]" if PROACTIVE_OK else "[red]✗ Missing[/red]"
        lessons_status = "[green]✓ Ready[/green]" if LESSONS_OK else "[red]✗ Missing[/red]"
        safety_status = "[green]✓ Ready[/green]" if SAFETY_OK else "[red]✗ Missing[/red]"
        
        banner = (
            f"[bold green]🌸 {self.name}[/bold green]\n"
            f"[dim]\"{self.tagline}\"[/dim]\n\n"
            f"[dim]Operator:  {self.operator}[/dim]\n"
            f"[dim]Brain:     {brain_status}[/dim]\n"
            f"[dim]Safety:    {safety_status}[/dim]\n"
            f"[dim]Perception:{perception_status}[/dim]\n"
            f"[dim]Proactive: {proactive_status}[/dim]\n"
            f"[dim]Lessons:   {lessons_status}[/dim]"
        )
        
        console.print(Panel.fit(banner, border_style="green"))
        
        # Warning တွေ
        if not PERCEPTION_OK:
            console.print(f"[yellow]⚠️  Perception unavailable: {PERCEPTION_ERROR}[/yellow]")
        if not PROACTIVE_OK:
            console.print(f"[yellow]⚠️  Proactive unavailable: {PROACTIVE_ERROR}[/yellow]")
        if not LESSONS_OK:
            console.print(f"[yellow]⚠️  Lessons unavailable: {LESSONS_ERROR}[/yellow]")
        if not SAFETY_OK:
            console.print(f"[red]❌ Safety unavailable: {SAFETY_ERROR}[/red]")
    
    # =========================================================
    # CORE EXECUTION
    # =========================================================
    
    def execute(self, command: str) -> bool:
        """Command တစ်ခုကို လုံခြုံစွာ run လုပ်ခြင်း"""
        if not SAFETY_OK:
            console.print("[red]❌ Safety module missing. Cannot execute.[/red]")
            return False
        
        # Safety Check
        level, reason = check_command(command)
        
        # Provenance Log
        action_id, content_hash = None, None
        if PROVENANCE_OK:
            try:
                action_id, content_hash = log_action(
                    "terminal_command", command, "ember_agent",
                    f"Safety: {level}"
                )
            except Exception:
                pass
        
        # Display
        color = {
            "SAFE": "green", "MEDIUM": "yellow",
            "HIGH": "orange1", "CRITICAL": "red"
        }.get(level, "white")
        
        console.print(f"\n[{color}]🔒 Safety Level: {level}[/{color}]")
        console.print(f"[dim]   Reason: {reason}[/dim]")
        if content_hash:
            console.print(f"[dim]   Hash: {content_hash}[/dim]")
        
        # Approval
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
        
        # Execute
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
        """Perception Layer ကို Run လုပ်ခြင်း"""
        if not PERCEPTION_OK:
            console.print("[red]❌ Perception module missing.[/red]")
            return
        
        console.print("\n[dim]🔍 Ember က အားလုံးကို စောင့်ကြည့်နေသည်...[/dim]\n")
        
        with console.status("[bold green]Collecting observations..."):
            try:
                report = perceive(observer_filter=observer_filter, save=True)
            except Exception as e:
                console.print(f"[red]❌ Perception error: {e}[/red]")
                return
        
        self.last_perception = report
        console.print(perceive_summary(report))
        
        if PROVENANCE_OK:
            try:
                log_action(
                    "perception",
                    f"perceive({observer_filter or 'all'})",
                    "ember_perception",
                    f"Status: {report['analysis'].get('overall_status')}"
                )
            except Exception:
                pass
    
    def do_analyze(self):
        """Perception ကို LLM နဲ့ ခွဲခြမ်းစိတ်ဖြာခြင်း"""
        if not self.last_perception:
            console.print("[yellow]⚠️  'perceive' ကို အရင် run ပါ။[/yellow]")
            return
        
        if not self.brain:
            console.print("[red]❌ Brain offline. Cannot analyze.[/red]")
            return
        
        console.print("\n[dim]🧠 Ember က ခွဲခြမ်းစိတ်ဖြာနေသည်...[/dim]\n")
        
        summary = perceive_summary(self.last_perception)
        prompt = f"""ဒီ Perception Report ကို ခွဲခြမ်းစိတ်ဖြာပါ:

{summary}

Format:
1. SITUATION: လက်ရှိ အခြေအနေ (၁-၂ ကြောင်း)
2. PRIORITY: အာရုံစိုက်ရမယ့် အရာ (၁ ခု)
3. NEXT ACTION: နောက်တစ်ဆင့် (bounded action)
4. REASON: ဘာကြောင့် ဒီ Action လဲ

Ember ရဲ့ ကိုယ်ရည်ကိုယ်သွေးနဲ့ ဖြေပါ။"""
        
        try:
            response = self.brain.think(prompt, EMBER_IDENTITY)
            console.print(Panel(response, title="🌸 Ember's Analysis", border_style="cyan"))
        except Exception as e:
            console.print(f"[red]❌ Brain error: {e}[/red]")
    
    # =========================================================
    # PROACTIVE (P2)
    # =========================================================
    
    def do_suggest(self):
        """Triggers ကနေ Suggestions ထုတ်ခြင်း"""
        if not PERCEPTION_OK or not PROACTIVE_OK:
            console.print("[red]❌ Perception/Proactive module missing.[/red]")
            return
        
        console.print("\n[dim]💡 Ember က အကြံပြုချက် စဉ်းစားနေသည်...[/dim]\n")
        
        try:
            report = perceive(save=True)
        except Exception as e:
            console.print(f"[red]❌ Perception error: {e}[/red]")
            return
        
        self.last_perception = report
        
        engine = TriggerEngine()
        triggers = engine.evaluate(report["analysis"])
        
        if not triggers:
            console.print(Panel(
                "✨ အကြံပြုချက် မရှိပါ။ အားလုံး ကောင်းမွန်နေပါတယ်။",
                title="🌸 Ember",
                border_style="green"
            ))
            return
        
        generator = SuggestionGenerator(brain=self.brain)
        suggestions = generator.generate(triggers)
        
        console.print(engine.summary())
        console.print()
        console.print(generator.format_suggestions(suggestions))
        
        # Deep Analysis (Brain + Critical)
        if self.brain and engine.has_critical():
            console.print("\n[dim]🧠 Ember က နက်ရှိုင်းစွာ ခွဲခြမ်းစိတ်ဖြာနေသည်...[/dim]")
            try:
                llm_analysis = generator.generate_with_brain(triggers)
                console.print(Panel(
                    llm_analysis,
                    title="🌸 Ember's Deep Analysis",
                    border_style="red"
                ))
            except Exception as e:
                console.print(f"[red]❌ Brain error: {e}[/red]")
    
    def do_monitor(self, iterations: int = 3):
        """Monitor ကို Run လုပ်ခြင်း"""
        if not PROACTIVE_OK:
            console.print("[red]❌ Monitor module missing.[/red]")
            return
        
        console.print(f"\n[dim]👁️  Ember Monitor ({iterations} iterations)...[/dim]\n")
        
        if not self.monitor:
            self.monitor = PerceptionMonitor(interval_minutes=15, brain=self.brain)
        
        def on_suggestion(suggestions):
            console.print()
            for s in suggestions:
                icon = {
                    "critical": "🚨", "high": "⚠️",
                    "medium": "⚡", "low": "ℹ️"
                }.get(s["severity"], "•")
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
                console.print(f"[red]❌ Monitor error: {e}[/red]")
        
        console.print("\n[bold]📊 Monitor Stats:[/bold]")
        stats = self.monitor.get_stats()
        for k, v in stats.items():
            console.print(f"   {k}: {v}")
    
    def do_stats(self):
        """Monitor Stats ပြသခြင်း"""
        if not self.monitor:
            console.print("[yellow]⚠️  'monitor' ကို အရင် run ပါ။[/yellow]")
            return
        
        table = Table(title="📊 Monitor Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        for k, v in self.monitor.get_stats().items():
            table.add_row(k, str(v))
        console.print(table)
    
    def do_suggestions_history(self):
        """Suggestion သမိုင်းကြောင်း"""
        if not self.monitor or not self.monitor.suggestions_history:
            console.print("[yellow]⚠️  သမိုင်းကြောင်း မရှိပါ။[/yellow]")
            return
        
        table = Table(title="💡 Suggestion History")
        table.add_column("#", style="cyan")
        table.add_column("Time", style="magenta")
        table.add_column("Count", style="yellow")
        table.add_column("Top Suggestion", style="white")
        
        for i, h in enumerate(reversed(self.monitor.suggestions_history[-10:]), 1):
            top = h["suggestions"][0] if h["suggestions"] else {}
            table.add_row(
                str(i),
                h["timestamp"][:19],
                str(h["count"]),
                top.get("message", "")[:50]
            )
        console.print(table)
    
    # =========================================================
    # LESSONS (Self-Learning)
    # =========================================================
    
    def do_lessons(self):
        """Lessons Summary ပြသခြင်း"""
        if not LESSONS_OK:
            console.print("[red]❌ Lessons module missing.[/red]")
            return
        
        console.print()
        try:
            console.print(lessons_summary())
        except Exception as e:
            console.print(f"[red]❌ Lessons error: {e}[/red]")
            return
        
        lessons = get_lessons(limit=5)
        if lessons:
            table = Table(title="📚 Top Lessons")
            table.add_column("ID", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Mistake", style="white")
            table.add_column("Count", style="yellow")
            table.add_column("Severity", style="red")
            
            for lesson in lessons:
                table.add_row(
                    f"#{lesson['id']}",
                    lesson["type"],
                    lesson["mistake"][:40],
                    f"{lesson['times_encountered']}x",
                    lesson["severity"].upper()
                )
            console.print(table)
    
    def do_check_lessons(self, code: str):
        """Code ကို Lessons Database နဲ့ စစ်ဆေးခြင်း"""
        if not LESSONS_OK:
            console.print("[red]❌ Lessons module missing.[/red]")
            return
        
        if not code:
            console.print("[yellow]Usage: check <code>[/yellow]")
            return
        
        console.print(f"\n[dim]🔍 Ember က Code ကို စစ်ဆေးနေသည်...[/dim]")
        console.print(f"[dim]   Code: {code[:60]}{'...' if len(code) > 60 else ''}[/dim]\n")
        
        warnings = check_for_pattern(code)
        
        if not warnings:
            console.print(Panel(
                "✅ ဒီ Code မှာ သိထားတဲ့ ပြဿနာ မရှိပါ။",
                title="🌸 Ember Lessons Check",
                border_style="green"
            ))
            return
        
        console.print(Panel(
            f"⚠️  {len(warnings)} ခုသော သတိပေးချက် တွေ့ရှိပါတယ်",
            title="🌸 Ember Lessons Check",
            border_style="yellow"
        ))
        
        for w in warnings:
            icon = {
                "critical": "🚨", "high": "⚠️",
                "medium": "⚡", "low": "ℹ️"
            }.get(w["severity"], "•")
            console.print(
                f"\n{icon} [bold red][{w['severity'].upper()}] "
                f"Lesson #{w['lesson_id']}[/bold red]"
            )
            console.print(f"   [yellow]Mistake:[/yellow] {w['warning']}")
            console.print(f"   [green]Fix:[/green] {w['fix']}")
        console.print()
    
    # =========================================================
    # IDENTITY / ASK / HISTORY
    # =========================================================
    
    def do_ask(self, question: str):
        """Ember ကို မေးခွန်း မေးခြင်း"""
        if not self.brain:
            console.print("[red]❌ Brain offline.[/red]")
            return
        
        console.print("\n[dim]🧠 Ember စဉ်းစားနေသည်...[/dim]")
        
        # Context
        context_parts = []
        if PROVENANCE_OK:
            try:
                recent = get_action_history(3)
                if recent:
                    context_parts.append("Recent actions:")
                    for r in recent:
                        context_parts.append(f"- {r[1]}: {r[2][:50]} ({r[3]})")
            except Exception:
                pass
        
        if self.last_perception:
            analysis = self.last_perception.get("analysis", {})
            context_parts.append(
                f"\nLast perception: {analysis.get('overall_status')} "
                f"(confidence: {analysis.get('overall_confidence')}%)"
            )
        
        context = "\n".join(context_parts) if context_parts else "No context."
        
        try:
            response = self.brain.think(question, EMBER_IDENTITY, context)
            console.print(Panel(response, title="🌸 Ember", border_style="cyan"))
            
            if PROVENANCE_OK:
                try:
                    log_action("llm_thought", question, "ember_brain", response[:200])
                except Exception:
                    pass
        except Exception as e:
            console.print(f"[red]❌ Brain error: {e}[/red]")
    
    def do_whoami(self):
        """Ember က သူ့ကိုယ်သူ ဖော်ပြခြင်း"""
        if not IDENTITY_OK:
            console.print("[red]❌ Identity module missing.[/red]")
            return
        
        console.print(Panel.fit(
            f"[bold cyan]Identity:[/bold cyan] {EMBER_IDENTITY['name']}\n"
            f"[bold cyan]Tagline:[/bold cyan] {EMBER_IDENTITY['tagline']}\n"
            f"[bold cyan]Archetype:[/bold cyan] {EMBER_IDENTITY['personality']['archetype']}\n"
            f"[bold cyan]Category:[/bold cyan] {EMBER_IDENTITY['market_identity']['category']}\n"
            f"[bold cyan]Role:[/bold cyan] Evidence & Audit Layer",
            title="🌸 Ember Self-Awareness",
            border_style="cyan"
        ))
        
        console.print("\n[bold]My Values:[/bold]")
        for v in EMBER_IDENTITY["personality"]["values"]:
            console.print(f"  • [italic]{v}[/italic]")
    
    def do_identity(self):
        """Identity အပြည့်အစုံ"""
        if not IDENTITY_OK:
            console.print("[red]❌ Identity module missing.[/red]")
            return
        console.print(describe_self())
    
    def do_history(self):
        """Action History"""
        if not PROVENANCE_OK:
            console.print("[red]❌ Provenance module missing.[/red]")
            return
        
        table = Table(title="📜 Action History")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Command", style="white")
        table.add_column("Status", style="green")
        table.add_column("Approved By", style="yellow")
        
        try:
            for row in get_action_history(10):
                table.add_row(
                    str(row[0]), row[1], row[2][:40],
                    row[3], row[4] or "-"
                )
            console.print(table)
        except Exception as e:
            console.print(f"[red]❌ History error: {e}[/red]")
    
    def do_help(self):
        """Help Panel"""
        console.print(Panel.fit(
            "[bold]📖 Ember Commands[/bold]\n\n"
            "[bold cyan]🔍 Perception:[/bold cyan]\n"
            "  perceive            - အားလုံးကို စောင့်ကြည့်\n"
            "  perceive backend    - တစ်ခုချင်း\n"
            "  analyze             - LLM နဲ့ ခွဲခြမ်းစိတ်ဖြာ\n\n"
            "[bold cyan]💡 Proactive:[/bold cyan]\n"
            "  suggest             - အကြံပြုချက် ထုတ်\n"
            "  monitor             - Monitor Run (3 iter)\n"
            "  monitor 5           - 5 iterations\n"
            "  stats               - Monitor Stats\n"
            "  suggestions         - သမိုင်းကြောင်း\n\n"
            "[bold cyan]📚 Lessons:[/bold cyan]\n"
            "  lessons             - သင်ခန်းစာ စာရင်း\n"
            "  check <code>        - Code ကို စစ်ဆေးရန်\n\n"
            "[bold cyan]🌸 Identity:[/bold cyan]\n"
            "  ask <q>             - Ember ကို မေးရန်\n"
            "  whoami              - သူ့ကိုယ်သူ\n"
            "  identity            - Identity အပြည့်အစုံ\n"
            "  history             - Action မှတ်တမ်း\n"
            "  help                - ဒီစာသား\n"
            "  exit                - ထွက်ရန်\n\n"
            "[dim]Terminal Commands တွေလည်း run လို့ရပါတယ်။[/dim]",
            title="📖 Help",
            border_style="blue"
        ))
    
    # =========================================================
    # MAIN LOOP
    # =========================================================
    
    def run(self):
        """Agent ရဲ့ Main Loop"""
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
                if cmd_lower == "whoami":
                    self.do_whoami(); continue
                if cmd_lower == "identity":
                    self.do_identity(); continue
                if cmd_lower == "history":
                    self.do_history(); continue
                if cmd_lower == "help":
                    self.do_help(); continue
                
                # ===== PERCEPTION (P1) =====
                if cmd_lower == "perceive":
                    self.do_perceive(); continue
                if cmd_lower.startswith("perceive "):
                    filter_name = cmd_stripped[9:].strip()
                    self.do_perceive(observer_filter=[filter_name]); continue
                if cmd_lower == "analyze":
                    self.do_analyze(); continue
                
                # ===== PROACTIVE (P2) =====
                if cmd_lower == "suggest":
                    self.do_suggest(); continue
                if cmd_lower == "monitor":
                    self.do_monitor(iterations=3); continue
                if cmd_lower.startswith("monitor "):
                    try:
                        n = int(cmd_stripped[8:].strip())
                        self.do_monitor(iterations=n)
                    except ValueError:
                        console.print("[yellow]Usage: monitor [number][/yellow]")
                    continue
                if cmd_lower == "stats":
                    self.do_stats(); continue
                if cmd_lower == "suggestions":
                    self.do_suggestions_history(); continue
                
                # ===== LESSONS =====
                if cmd_lower == "lessons":
                    self.do_lessons(); continue
                if cmd_lower.startswith("check "):
                    code_to_check = cmd_stripped[6:].strip()
                    self.do_check_lessons(code_to_check); continue
                
                # ===== ASK =====
                if cmd_lower.startswith("ask "):
                    question = cmd_stripped[4:].strip()
                    if question:
                        self.do_ask(question)
                    else:
                        console.print("[yellow]Usage: ask <question>[/yellow]")
                    continue
                
                # ===== TERMINAL COMMAND =====
                self.execute(cmd_stripped)
                console.print()
            
            except KeyboardInterrupt:
                console.print("\n[dim]👋 Interrupted.[/dim]")
                break
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")


# =========================================================
# MAIN ENTRY POINT — MUST HAVE!
# =========================================================

def main():
    """Main entry point"""
    try:
        agent = EmberAgent()
        agent.run()
    except Exception as e:
        console.print(f"[red]❌ Fatal error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
