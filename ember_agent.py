#!/usr/bin/env python3
"""
Ember Lite - Self-Aware Terminal Agent
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

console = Console()


class EmberAgent:
    def __init__(self):
        init_db()
        self.operator = os.getenv("USER", "unknown")
        self.name = EMBER_IDENTITY["name"]
        self.tagline = EMBER_IDENTITY["tagline"]
        
        console.print(Panel.fit(
            f"[bold green]{self.name}[/bold green]\n"
            f"[dim]\"{self.tagline}\"[/dim]\n"
            f"[dim]Operator: {self.operator}[/dim]",
            border_style="green"
        ))
    
    def execute(self, command):
        """Command တစ်ခုကို လုံခြုံစွာ လုပ်ဆောင်ခြင်း"""
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
                console.print("[bold red]⛔ CRITICAL action - Blocked by policy![/bold red]")
                return False
            approved = Confirm.ask(f"Execute: {command}?")
            if not approved:
                console.print("[dim]❌ Action cancelled.[/dim]")
                return False
            log_approval(action_id, self.operator, "Approved via Ember Agent")
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
            console.print("[red]⏱️  Command timed out (30s)[/red]")
            return False
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            return False
    
    def whoami(self):
        """Ember က သူ့ကိုယ်သူ ဖော်ပြခြင်း"""
        console.print(Panel.fit(
            f"[bold cyan]Identity:[/bold cyan] {EMBER_IDENTITY['name']}\n"
            f"[bold cyan]Tagline:[/bold cyan] {EMBER_IDENTITY['tagline']}\n"
            f"[bold cyan]Archetype:[/bold cyan] {EMBER_IDENTITY['personality']['archetype']}\n"
            f"[bold cyan]Category:[/bold cyan] {EMBER_IDENTITY['market_identity']['category']}",
            title="🌸 Ember Self-Awareness",
            border_style="cyan"
        ))
        console.print("\n[bold]My Values:[/bold]")
        for v in EMBER_IDENTITY['personality']['values']:
            console.print(f"  • [italic]{v}[/italic]")
        
        console.print("\n[bold]My Layers:[/bold]")
        for layer, info in EMBER_IDENTITY['capabilities'].items():
            console.print(f"  • [yellow]{layer}[/yellow]: {info['what']}")
        
        console.print("\n[bold]What I Am:[/bold]")
        for item in EMBER_IDENTITY['market_identity']['is_a']:
            console.print(f"  ✅ {item}")
        
        console.print("\n[bold]What I Am NOT:[/bold]")
        for item in EMBER_IDENTITY['market_identity']['not_a']:
            console.print(f"  ❌ {item}")
        
        console.print(f"\n[dim]{EMBER_IDENTITY['market_identity']['differentiation']}[/dim]")
    
    def history(self):
        """Action မှတ်တမ်း"""
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
        """Built-in commands များ"""
        console.print(Panel.fit(
            "[bold]Built-in Commands:[/bold]\n"
            "  [cyan]whoami[/cyan]   - Ember က သူ့ကိုယ်သူ ဖော်ပြခြင်း\n"
            "  [cyan]identity[/cyan] - Identity အပြည့်အစုံ\n"
            "  [cyan]history[/cyan]  - Action မှတ်တမ်း\n"
            "  [cyan]help[/cyan]     - ဒီစာသား\n"
            "  [cyan]exit[/cyan]     - ထွက်ရန်\n\n"
            "[dim]ကျန်တာတွေက Terminal Command တွေပါ။[/dim]",
            title="📖 Help",
            border_style="blue"
        ))
    
    def run(self):
        console.print("\n[dim]Type 'help' for commands, 'whoami' to meet Ember.[/dim]\n")
        
        while True:
            try:
                cmd = Prompt.ask("[bold cyan]ember[/bold cyan]")
                
                if cmd.lower() in ['exit', 'quit']:
                    console.print("[dim]👋 Goodbye![/dim]")
                    break
                if cmd.lower() == 'whoami':
                    self.whoami(); continue
                if cmd.lower() == 'identity':
                    console.print(describe_self()); continue
                if cmd.lower() == 'history':
                    self.history(); continue
                if cmd.lower() == 'help':
                    self.help(); continue
                if not cmd.strip():
                    continue
                
                self.execute(cmd)
                console.print()
            except KeyboardInterrupt:
                console.print("\n[dim]👋 Interrupted.[/dim]")
                break
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")


if __name__ == "__main__":
    EmberAgent().run()
