# ui.py

"""
User Interface elements for MindSQL using the Rich library.
"""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

# Create a single shared console instance for the whole application
console = Console()

def print_banner(db_url):
    """Clears the screen and prints the welcome banner."""
    console.clear()
    banner_text = Text("MindSQL v10.3 (Chain of Thought)", style="bold magenta", justify="center")
    
    info_text = f"\n[bold cyan]Connected to:[/bold cyan] {db_url}\n"
    info_text += "[dim]──────────────────────────────────────────────[/dim]\n"
    info_text += "• [bold cyan]mindsql <text>[/bold cyan]       : Strict SQL\n"
    info_text += "• [bold cyan]mindsql_ans <text>[/bold cyan]   : Chat & Explain\n"
    info_text += "• [bold yellow]mindsql_plot <text>[/bold yellow]  : Generate Charts 📊\n"
    info_text += "• [bold red]exit[/bold red]                  : Quit"

    console.print(Panel(
        info_text,
        title=banner_text,
        border_style="blue",
        box=box.ROUNDED,
        padding=(1, 2)
    ))

def draw_ascii_bar_chart(data):
    """
    Expects data as a list of tuples: [("Label", Value), ...]
    Draws a color-coded bar chart directly in the terminal.
    """
    if not data:
        console.print("[yellow]No data to plot.[/yellow]")
        return

    try:
        clean_data = [(str(row[0]), float(row[1])) for row in data if row[1] is not None]
    except ValueError:
        console.print("[red]Error: Plot data must contain a Label and a Number.[/red]")
        return

    if not clean_data:
        console.print("[yellow]No valid numeric data found.[/yellow]")
        return

    max_label_len = max(len(d[0]) for d in clean_data)
    max_val = max(d[1] for d in clean_data)
    bar_width = 40 

    console.print()
    console.print(Panel("[bold]📊 Analysis Result[/bold]", style="blue", box=box.MINIMAL, expand=False))

    # 1. Define a list of visually distinct colors
    color_palette = [
        "spring_green1", "cyan", "magenta", 
        "yellow", "dodger_blue1", "dark_orange"
    ]

    for i, (label, value) in enumerate(clean_data):
        if max_val > 0:
            filled_len = int((value / max_val) * bar_width)
        else:
            filled_len = 0
            
        bar = "█" * filled_len
        
        # 2. Assign color by cycling through the palette using the modulo operator
        color = color_palette[i % len(color_palette)]

        console.print(f"{label.rjust(max_label_len)} │ [{color}]{bar}[/{color}]  [bold white]{value}[/bold white]")
    
    console.print()