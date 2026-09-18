#!/usr/bin/env python3
"""
Ember Lite - Self-Aware Conversational Agent
"""

import subprocess
import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from provenance import init_db, log_action, log_approval, get_action_history
from safety import check_command, requires_approval
from ember_identity import EMBER_IDENTITY, describe_self
from ember_brain import EmberBrain

console = Console()


class EmberAgent:
    def __init__(self):
        init_db()
        self.operator = os.getenv("USER", "unknown")
        self.name = EMBER_IDENTITY["name"]
        self.brain = None
        
        try:
            self.brain = EmberBrain(provider="openrouter")
            brain_status = "[green]✓ Online[/green]"
        except ValueError as e:
            brain_status = f"[red]✗ Offline[/red]"
        
        console.print(Panel.fit(
            f"[bold green]🌸 {self.name}[/bold green]\n"
            f"[dim]\"{EMBER_IDENTITY['tagline']}\"[/dim]\n"
            f"[dim]Brain: {brain_status}[/dim]\n"
            f"[dim]Operator: {self.operator}[/dim]",
            border_style="green"
        ))
    
    def execute(self, command):
        level, reason = check_command(command)
        action_id, content_hash = log_action(
            "terminal_command", command, "ember_agent", f"Safety: {level}"
        )
        
        color = {
            'SAFE': 'green', 'MEDIUM': 'yellow',
            'HIGH': 'orange1', 'CRITICAL': 'red'
        }.get(level, 'white')
        
        console.print(f"\n[{color}]🔒 Safety Level: {level}[/{color}]")
        console.print(f"[dim]   Reason: {reason}[/dim]")
        console.print(f"[dim]   Hash: {content_hash}[/dim]")
        
        if requires_approval(level):
            if level == 'CRITICAL':
                console.print("[bold red]⛔ CRITICAL - Blocked![/bold red]")
                return False
            if not Confirm.ask(f"Execute: {command}?"):
                console.print("[dim]❌ Cancelled.[/dim]")
                return False
            log_approval(action_id, self.operator, "Approved")
            console.print("[green]✅ Approved and logged.[/green]")
        
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
    
    def ask_ember(self, user_message):
        if not self.brain:
            console.print("[red]❌ Ember's brain is offline.[/red]")
            return
        
        console.print("\n[dim]🧠 Ember စဉ်းစားနေသည်...[/dim]")
        
        recent = get_action_history(3)
        context = "Recent actions:\n" + "\n".join(
            f"- {r[1]}: {r[2][:50]} ({r[3]})" for r in recent
        ) if recent else "No recent actions."
        
        response = self.brain.think(user_message, EMBER_IDENTITY, context)
        
        console.print(Panel(
            response,
            title="🌸 Ember",
            border_style="cyan"
        ))
        
        log_action("llm_thought", user_message, "ember_brain", response[:200])
    
    def whoami(self):
        console.print(Panel.fit(
            f"[bold cyan]Identity:[/bold cyan] {EMBER_IDENTITY['name']}\n"
            f"[bold cyan]Tagline:[/bold cyan] {EMBER_IDENTITY['tagline']}\n"
            f"[bold cyan]Archetype:[/bold cyan] {EMBER_IDENTITY['personality']['archetype']}\n"
            f"[bold cyan]Category:[/bold cyan] {EMBER_IDENTITY['market_identity']['category']}",
            title="🌸 Ember Self-Awareness",
            border_style="cyan"
        ))
    
    def history(self):
        table = Table(title="Action History")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Command", style="white")
        table.add_column("Status", style="green")
        table.add_column("Approved By", style="yellow")
        for row in get_action_history(10):
            table.add_row(
                str(row[0]), row[1], row[2][:40],
                row[3], row[4] or "-"
            )
        console.print(table)
    
    def help(self):
        console.print(Panel.fit(
            "[bold]Commands:[/bold]\n"
            "  [cyan]ask[/cyan] <question>  - Ember ကို မေးရန်\n"
            "  [cyan]whoami[/cyan]          - သူ့ကိုယ်သူ ဖော်ပြရန်\n"
            "  [cyan]identity[/cyan]        - Identity အပြည့်အစုံ\n"
            "  [cyan]history[/cyan]         - Action မှတ်တမ်း\n"
            "  [cyan]help[/cyan]            - ဒီစာသား\n"
            "  [cyan]exit[/cyan]            - ထွက်ရန်",
            title="📖 Help",
            border_style="blue"
        ))
    
    def run(self):
        console.print("\n[dim]Type 'help' or 'ask <question>' to talk to Ember.[/dim]\n")
        
        while True:
            try:
                cmd = Prompt.ask("[bold cyan]ember[/bold cyan]")
                cmd_stripped = cmd.strip()
                
                if cmd_stripped.lower() in ['exit', 'quit']:
                    console.print("[dim]👋 Goodbye![/dim]")
                    break
                if cmd_stripped.lower() == 'whoami':
                    self.whoami(); continue
                if cmd_stripped.lower() == 'identity':
                    console.print(describe_self()); continue
                if cmd_stripped.lower() == 'history':
                    self.history(); continue
                if cmd_stripped.lower() == 'help':
                    self.help(); continue
                if cmd_stripped.lower().startswith('ask '):
                    question = cmd_stripped[4:].strip()
                    if question:
                        self.ask_ember(question)
                    else:
                        console.print("[yellow]Usage: ask <your question>[/yellow]")
                    continue
                if not cmd_stripped:
                    continue
                
                self.execute(cmd_stripped)
                console.print()
            except KeyboardInterrupt:
                console.print("\n[dim]👋 Interrupted.[/dim]")
                break
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")


if __name__ == "__main__":
    EmberAgent().run()
