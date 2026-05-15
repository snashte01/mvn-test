#!/usr/bin/env python3
"""ZeroOps CLI — SAP Basis automation."""
import logging
import typer
from rich.console import Console
from rich.table import Table
from rich import box
from core.inventory import load_inventory, get_system
from modules.stop_start.orchestrator import stop, start

app = typer.Typer(help="ZeroOps — SAP Basis automation platform")
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
)


@app.command(name="list")
def list_systems():
    """List all SAP systems in the inventory."""
    systems = load_inventory()
    table = Table(title="SAP Systems", box=box.ROUNDED)
    table.add_column("SID", style="cyan bold")
    table.add_column("Description")
    table.add_column("Pacemaker")
    table.add_column("App Hosts")
    table.add_column("HANA Primary")
    table.add_column("HSR")

    for s in systems:
        app_hosts = ", ".join(i.host for i in s.app_instances)
        table.add_row(
            s.sid,
            s.description,
            "yes" if s.pacemaker_enabled else "no",
            app_hosts,
            s.hana.primary_host,
            "yes" if s.hana.hsr_enabled else "no",
        )

    console.print(table)


@app.command(name="stop")
def stop_cmd(
    sid: str = typer.Argument(..., help="SAP system SID (e.g. ERP)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview steps without executing"),
):
    """Stop a SAP system (Pacemaker-aware)."""
    system = get_system(sid)
    _print_plan("STOP", system, dry_run)
    result = stop(system, dry_run=dry_run)
    _print_result(result)
    if not result.success:
        raise typer.Exit(code=1)


@app.command(name="start")
def start_cmd(
    sid: str = typer.Argument(..., help="SAP system SID (e.g. ERP)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview steps without executing"),
):
    """Start a SAP system (Pacemaker-aware)."""
    system = get_system(sid)
    _print_plan("START", system, dry_run)
    result = start(system, dry_run=dry_run)
    _print_result(result)
    if not result.success:
        raise typer.Exit(code=1)


def _print_plan(action: str, system, dry_run: bool):
    mode = "[yellow]DRY-RUN[/yellow]" if dry_run else "[red]LIVE[/red]"
    console.rule(f"[bold]{action}[/bold] {system.sid}  {mode}")
    console.print(f"  Description : {system.description}")
    console.print(f"  Pacemaker   : {'yes' if system.pacemaker_enabled else 'no'}")
    console.print(f"  App hosts   : {', '.join(i.host for i in system.app_instances)}")
    console.print(f"  HANA primary: {system.hana.primary_host}")
    if system.hana.secondary_host:
        console.print(f"  HANA secondary: {system.hana.secondary_host}")
    console.print()


def _print_result(result):
    table = Table(box=box.SIMPLE)
    table.add_column("Step")
    table.add_column("Status")
    table.add_column("Message")

    for step in result.steps:
        color = {"ok": "green", "error": "red", "dry-run": "yellow"}.get(step.status, "white")
        table.add_row(step.step, f"[{color}]{step.status}[/{color}]", step.message)

    console.print(table)

    if result.error:
        console.print(f"\n[bold red]FAILED:[/bold red] {result.error}")
    else:
        status = "DRY-RUN complete" if result.dry_run else "SUCCESS"
        console.print(f"\n[bold green]{status}[/bold green]")


if __name__ == "__main__":
    app()
