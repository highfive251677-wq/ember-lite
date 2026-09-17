#!/usr/bin/env python3
import subprocess
import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from provenance import init_db, log_action, log_approval, get_action_history
from safety import check_command, requires_approval

console = Console()

class EmberAgent:
    def __init__(self):
        init_db()
        self.operator = os.getenv("USER", "unknown")
        console.print(Panel.fit("[bold green]Ember Lite[/bold green]\n[dim]Provenance-first Terminal Agent[/dim]", border_style="green"))
    
    def execute(self, command):
        level, reason = check_command(command)
        action_id, content_hash = log_action("terminal_command", command, "ember_agent", f"Safety: {level}")
        color = {'SAFE':'green','MEDIUM':'yellow','HIGH':'orange1','CRITICAL':'red'}.get(level,'white')
        console.print(f"\n[{color}]🔒 Safety Level: {level}[/{color}]")
        console.print(f"[dim]   Hash: {content_hash}[/dim]")
        
        if requires_approval(level):
            if level == 'CRITICAL':
                console.print("[bold red]⛔ CRITICAL - Blocked![/bold red]")
                return False
            if not Confirm.ask(f"Execute: {command}?"):
                return False
            log_approval(action_id, self.operator, "Approved")
        
        console.print(f"\n[bold]▶ Executing:[/bold] {command}\n")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            if result.stdout: console.print(result.stdout)
            if result.stderr: console.print(f"[red]{result.stderr}[/red]")
            return True
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            return False
    
    def history(self):
        table = Table(title="Action History")
        for col in ["ID","Type","Command","Status","Approved By"]:
            table.add_column(col)
        for row in get_action_history(10):
            table.add_row(str(row[0]), row[1], row[2][:40], row[3], row[4] or "-")
        console.print(table)
    
    def run(self):
        while True:
            try:
                cmd = Prompt.ask("[bold cyan]ember[/bold cyan]")
                if cmd.lower() in ['exit','quit']: break
                if cmd.lower() == 'history': self.history(); continue
                if not cmd.strip(): continue
                self.execute(cmd)
                console.print()
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    EmberAgent().run()
