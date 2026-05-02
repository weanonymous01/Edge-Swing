"""
Rich CLI formatter — beautiful terminal output for trading signals.
Uses ASCII-safe characters for Windows compatibility.
"""

import os
import sys

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console(force_terminal=True)

ACTION_STYLES = {
    "BUY":   ("bold white on green",  "[BUY]"),
    "WATCH": ("bold white on yellow", "[WATCH]"),
    "SKIP":  ("bold white on red",    "[SKIP]"),
}


def display_header():
    header = Text()
    header.append(">> EDGE SWING ", style="bold cyan")
    header.append("- ETF Swing Trading CLI Assistant (India)", style="dim")
    console.print()
    console.print(Panel(header, border_style="cyan", box=box.DOUBLE_EDGE))
    console.print()


def display_market_mood(mood: str):
    console.print(Panel(
        f"[bold]Market Mood:[/bold] {mood}",
        border_style="blue",
        title="[Overview]",
        title_align="left",
    ))
    console.print()


def display_signals(signals: list[dict]):
    buys = [s for s in signals if s["action"] == "BUY"]
    watches = [s for s in signals if s["action"] == "WATCH"]
    skips = [s for s in signals if s["action"] == "SKIP"]

    if buys:
        console.print("[bold green]=== BUY SIGNALS ===[/bold green]")
        for sig in buys:
            _display_signal_card(sig)

    if watches:
        console.print("[bold yellow]=== WATCH LIST ===[/bold yellow]")
        for sig in watches:
            _display_signal_card(sig)

    if skips:
        console.print("[bold red]=== SKIP ===[/bold red]")
        _display_skip_table(skips)


def _display_signal_card(sig: dict):
    style, icon = ACTION_STYLES.get(sig["action"], ("", "[?]"))
    breakdown = sig.get("score_breakdown", {})

    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Field", style="dim", width=18)
    table.add_column("Value", style="bold")

    table.add_row("Entry Price", f"Rs.{sig['entry_price']}")
    table.add_row("Stop Loss", f"Rs.{sig['stop_loss']}")
    table.add_row("Target 1 (+3%)", f"Rs.{sig['target1']}")
    table.add_row("Target 2 (+6%)", f"Rs.{sig['target2']}")
    table.add_row("Entry Type", sig.get("entry_type", "-").upper())
    table.add_row("Units", str(sig.get("units", 0)))
    table.add_row("Position Size", f"Rs.{sig.get('position_size', 0):,.2f}")
    table.add_row("Risk Amount", f"Rs.{sig.get('risk_amount', 0):,.2f}")
    table.add_row("", "")
    table.add_row("Sector Momentum", f"{breakdown.get('sector_momentum', 0)}/25")
    table.add_row("Trend Score", f"{breakdown.get('trend_score', 0)}/20")
    table.add_row("RSI Score", f"{breakdown.get('rsi_score', 0)}/20")
    table.add_row("Volume Score", f"{breakdown.get('volume_score', 0)}/15")
    table.add_row("Risk-Reward", f"{breakdown.get('risk_reward_score', 0)}/20")

    title = f"{icon} {sig['etf']}  -  [{style}] {sig['action']} [/{style}]  (Score: {sig['score']}/100)"
    border = "green" if sig["action"] == "BUY" else "yellow"

    reason = sig.get("reason", "")
    if reason:
        console.print(Panel(
            table,
            title=title,
            subtitle=f"> {reason}",
            border_style=border,
            title_align="left",
            subtitle_align="left",
        ))
    else:
        console.print(Panel(table, title=title, border_style=border, title_align="left"))
    console.print()


def _display_skip_table(skips: list[dict]):
    table = Table(box=box.ROUNDED, border_style="red")
    table.add_column("ETF", style="bold")
    table.add_column("Score", justify="center")
    table.add_column("Reason", style="dim")
    for sig in skips:
        table.add_row(sig["etf"], str(sig["score"]), sig.get("reason", "-")[:80])
    console.print(table)
    console.print()


def display_avoid_list(avoid: list):
    if not avoid:
        return
    console.print("[bold red]!! Avoid List:[/bold red]")
    for item in avoid:
        console.print(f"  [red]*[/red] {item}")
    console.print()


def display_summary(summary: str):
    console.print(Panel(
        summary,
        title="[Summary]",
        border_style="cyan",
        title_align="left",
    ))
    console.print()


def display_json_output(result: dict):
    import json
    clean_signals = []
    for sig in result.get("signals", []):
        clean = {k: v for k, v in sig.items() if k != "data"}
        clean_signals.append(clean)
    output = {
        "signals": clean_signals,
        "market_mood": result.get("market_mood", ""),
        "avoid": result.get("avoid", []),
        "summary": result.get("summary", ""),
    }
    console.print_json(json.dumps(output, indent=2))


def display_error(message: str):
    console.print(f"[bold red]ERROR:[/bold red] {message}")


def display_progress(message: str):
    console.print(f"[dim]  ... {message}[/dim]")


def display_success(message: str):
    console.print(f"[green]  [OK] {message}[/green]")


def display_warning(message: str):
    console.print(f"[yellow]  [!] {message}[/yellow]")
