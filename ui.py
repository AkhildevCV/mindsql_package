# ui.py
"""
User Interface elements for MindSQL using the Rich library.
"""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
import config

console = Console()


def print_banner(db_url: str):
    """Prints the MindSQL welcome banner with connection info."""
    console.clear()
    title = Text(f"MindSQL  v{config.APP_VERSION}", style="bold magenta", justify="center")

    info = (
        f"\n[bold cyan]Connected to:[/bold cyan] {db_url}\n"
        "[dim]──────────────────────────────────────────────────[/dim]\n"
        "[bold cyan]mindsql <text>[/bold cyan]           → Strict SQL generation\n"
        "[bold cyan]mindsql_ans <text>[/bold cyan]       → Explain + SQL\n"
        "[bold yellow]mindsql_plot <text>[/bold yellow]       → Terminal bar chart  📊\n"
        "[bold green]mindsql_export <text>[/bold green]   → Export to CSV  🗂\n"
        "[bold cyan]connect <db_name>[/bold cyan]        → Switch database\n"
        "[bold red]exit[/bold red]                      → Quit\n"
        "[dim]Tab = autocomplete  |  Ctrl+R = search history[/dim]"
    )

    console.print(Panel(info, title=title, border_style="blue",
                        box=box.ROUNDED, padding=(1, 2)))


def draw_ascii_bar_chart(data: list):
    """
    Renders a color-coded horizontal bar chart in the terminal.
    Expects: [(label, numeric_value), …]
    """
    if not data:
        console.print("[yellow]No data to plot.[/yellow]")
        return

    try:
        clean = [(str(r[0]), float(r[1])) for r in data if r[1] is not None]
    except (ValueError, TypeError, IndexError):
        console.print("[red]Plot error: data must have a label and a numeric value.[/red]")
        return

    if not clean:
        console.print("[yellow]No valid numeric data.[/yellow]")
        return

    max_label = max(len(d[0]) for d in clean)
    max_val   = max(d[1] for d in clean) or 1
    bar_width = 44

    palette = [
        "spring_green1", "cyan1", "magenta1",
        "yellow1", "dodger_blue1", "dark_orange",
        "orchid1", "chartreuse1",
    ]

    console.print()
    console.print(Panel("[bold]📊 Chart Result[/bold]", style="blue",
                        box=box.MINIMAL, expand=False))

    for i, (label, value) in enumerate(clean):
        filled = int((value / max_val) * bar_width)
        bar    = "█" * filled
        empty  = "░" * (bar_width - filled)
        color  = palette[i % len(palette)]
        pct    = (value / max_val) * 100
        console.print(
            f"{label.rjust(max_label)} │ "
            f"[{color}]{bar}[/{color}][dim]{empty}[/dim]"
            f"  [bold white]{value}[/bold white] [dim]({pct:.1f}%)[/dim]"
        )

    console.print()
    console.print(f"[dim]Total rows: {len(clean)}[/dim]\n")
