# main.py
"""
MindSQL – AI-Powered Database Terminal
Main entry point and interactive shell.
"""

import re
import sys
import os
import csv
import getpass
import time

import typer
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import make_url
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich import box

import config
from ui import console, print_banner, draw_ascii_bar_chart
from database import load_file, save_file, perform_connection, execute_sql
from validator import validate_plot_sql, validate_sql_schema, extract_sql
from ai_engine import mindsql_start, chat_with_model
from sql_completer import SQLCompleter
from schema_manager import update_schema_context

app = typer.Typer(help="MindSQL – AI-Powered Database Terminal", add_completion=False)

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPTS
# ─────────────────────────────────────────────────────────────────────────────
PLOT_INSTRUCTION = (
    "You are a Data Visualization Assistant. Output ONLY raw SQL.\n"
    "RULES:\n"
    "1. TWO COLUMNS: Alias col 1 as 'LABEL' (text), col 2 as 'VALUE' (number).\n"
    "2. AGGREGATE: Always use SUM/COUNT/AVG with GROUP BY.\n"
    "3. No explanations. Output only the SELECT statement."
)
ANS_INSTRUCTION = (
    "You are a Database Expert and SQL tutor.\n"
    "STEP 1: Briefly state which tables/columns you will use.\n"
    "STEP 2: Write the SQL.\n"
    "RULES:\n"
    "1. Use EXACT names from the schema context.\n"
    "2. Treat proper nouns not in schema as WHERE-clause values.\n"
    "3. If info is missing output 'CLARIFICATION_NEEDED:' + reason.\n"
    "4. For structure questions output 'SCHEMA_ANSWER:' + plain-English answer."
)
STRICT_INSTRUCTION = (
    "You are a strict SQL generator. Output ONLY SQL.\n"
    "RULES:\n"
    "1. Use EXACT table/column names from the schema. Never guess.\n"
    "2. Capitalised words not in schema = WHERE clause values.\n"
    "3. If info is missing output 'CLARIFICATION_NEEDED:' + reason.\n"
    "4. For structure questions output 'SCHEMA_ANSWER:' + plain-English answer."
)

def _instruction(mode):
    return {"plot": PLOT_INSTRUCTION, "ans": ANS_INSTRUCTION}.get(mode, STRICT_INSTRUCTION)


# ─────────────────────────────────────────────────────────────────────────────
# INTERACTIVE CONNECTION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _ask(label, default="", password=False):
    """Prompts the user for input. Uses getpass for passwords (hidden input)."""
    if password:
        return getpass.getpass(f"  {label}: ")
    display = f"  {label} [{default}]: " if default else f"  {label}: "
    val = input(display).strip()
    return val if val else default


def _interactive_connect(current_db_url=None):
    """
    Guided step-by-step MySQL connection.

    Flow:
      1. Ask: host, port, username, password
      2. Connect to MySQL server (no specific DB)
      3. Show list of available databases
      4. Ask user to pick a database by name or number
      5. Connect to that database and return
    """
    console.print()
    console.print(Panel(
        "[bold cyan]MySQL Connection Setup[/bold cyan]\n"
        "[dim]Press Enter to keep the default shown in [brackets][/dim]",
        border_style="cyan", padding=(0, 2)
    ))
    console.print()

    # ── Step 1: Gather credentials ────────────────────────────────────────
    host     = _ask("Host",     default="localhost")
    port     = _ask("Port",     default="3306")
    username = _ask("Username", default="root")
    password = _ask("Password", password=True)  # hidden input

    # Save for this session so `mindsql use` can reuse them
    config.LAST_HOST     = host
    config.LAST_PORT     = port
    config.LAST_USERNAME = username
    config.LAST_PASSWORD = password

    # ── Step 2: Connect to server and list databases ───────────────────────
    server_url = f"mysql+pymysql://{username}:{password}@{host}:{port}/"
    console.print()

    with console.status("[cyan]Connecting to MySQL server…[/cyan]", spinner="dots"):
        try:
            tmp = create_engine(server_url, connect_args={"connect_timeout": 10})
            with tmp.connect() as conn:
                rows = conn.execute(text("SHOW DATABASES;")).fetchall()
            databases = [r[0] for r in rows]
            tmp.dispose()
        except Exception as exc:
            console.print(Panel(
                f"[red]❌  Connection failed[/red]\n\n{exc}\n\n"
                "[dim]Check that MySQL is running and your credentials are correct.[/dim]",
                border_style="red"
            ))
            return None, None, ""

    # ── Step 3: Show available databases ──────────────────────────────────
    system_dbs = {"information_schema", "performance_schema", "mysql", "sys"}
    user_dbs   = [db for db in databases if db.lower() not in system_dbs]
    show_list  = user_dbs if user_dbs else databases

    console.print()
    tbl = Table(title="Available Databases", box=box.ROUNDED, border_style="cyan")
    tbl.add_column("#",        style="dim",        width=5)
    tbl.add_column("Database", style="bold cyan")
    for i, db in enumerate(show_list, 1):
        tbl.add_row(str(i), db)
    console.print(tbl)
    console.print()

    # ── Step 4: Ask which database ────────────────────────────────────────
    db_choice = _ask("Enter database name  (or its number from the list above)").strip()

    if not db_choice:
        console.print("[yellow]⚠  No database selected. Not connected.[/yellow]")
        return None, None, ""

    # Allow selecting by number
    if db_choice.isdigit():
        idx = int(db_choice) - 1
        if 0 <= idx < len(show_list):
            db_choice = show_list[idx]
        else:
            console.print(f"[red]❌  Invalid number. Pick 1–{len(show_list)}.[/red]")
            return None, None, ""

    # ── Step 5: Connect to the chosen database ────────────────────────────
    full_url = f"mysql+pymysql://{username}:{password}@{host}:{port}/{db_choice}"
    engine, _ = perform_connection(full_url)
    if engine:
        schema_context = update_schema_context(engine)
        return engine, full_url, schema_context
    return None, None, ""


def _switch_database(db_name, current_db_url=None):
    """
    Switches to a different database using the credentials already saved
    in config from the last `mindsql connect` call.
    Falls back to parsing the saved URL if no session credentials exist.
    """
    host     = getattr(config, "LAST_HOST",     None)
    port     = getattr(config, "LAST_PORT",     None)
    username = getattr(config, "LAST_USERNAME", None)
    password = getattr(config, "LAST_PASSWORD", None)

    # Try to extract from saved URL if session creds are missing
    if not all([host, username]) and current_db_url:
        try:
            p = make_url(current_db_url)
            host     = host     or str(p.host)
            port     = port     or str(p.port or "3306")
            username = username or str(p.username)
            password = password or str(p.password or "")
        except Exception:
            pass

    if not all([host, username]):
        console.print("[yellow]No saved credentials. Running guided connect…[/yellow]")
        return _interactive_connect(current_db_url)

    new_url = f"mysql+pymysql://{username}:{password}@{host}:{port}/{db_name}"
    console.print(f"\n[cyan]Switching to[/cyan] [bold cyan]{db_name}[/bold cyan]…")
    engine, _ = perform_connection(new_url)
    if engine:
        schema_context = update_schema_context(engine)
        return engine, new_url, schema_context
    return None, current_db_url, ""


def _show_databases(engine):
    """Lists all databases on the connected MySQL server."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SHOW DATABASES;")).fetchall()
        system_dbs = {"information_schema", "performance_schema", "mysql", "sys"}
        tbl = Table(title="Databases on Server", box=box.ROUNDED, border_style="cyan")
        tbl.add_column("#",        style="dim", width=5)
        tbl.add_column("Database", style="bold cyan")
        tbl.add_column("",        style="dim")
        for i, (db,) in enumerate(rows, 1):
            tag = "system" if db.lower() in system_dbs else ""
            tbl.add_row(str(i), db, tag)
        console.print(tbl)
        console.print("[dim]Tip: mindsql use <name>  to switch[/dim]")
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")


# ─────────────────────────────────────────────────────────────────────────────
# SHELL COMMAND
# ─────────────────────────────────────────────────────────────────────────────
@app.command()
def shell():
    """Launch the interactive MindSQL terminal."""
    db_url = load_file(config.DB_URL_FILE)
    engine = None
    schema_context = ""

    # Auto-reconnect to last used database
    if db_url:
        console.print("[dim]Auto-connecting to last database…[/dim]")
        engine, _ = perform_connection(db_url)
        if engine:
            schema_context = update_schema_context(engine)
            # Pre-load credentials from saved URL so `mindsql use` works instantly
            try:
                p = make_url(db_url)
                config.LAST_HOST     = str(p.host)
                config.LAST_PORT     = str(p.port or "3306")
                config.LAST_USERNAME = str(p.username)
                config.LAST_PASSWORD = str(p.password or "")
            except Exception:
                pass

    schema_context = schema_context or load_file(config.SCHEMA_FILE) or ""

    session = PromptSession(
        history=FileHistory(config.HISTORY_FILE),
        style=Style.from_dict({"prompt": "ansicyan bold"}),
        completer=SQLCompleter(),
    )

    if engine:
        print_banner(db_url)
    else:
        console.print(Panel(
            "[yellow]Not connected to a database.[/yellow]\n\n"
            "  Type [bold cyan]mindsql connect[/bold cyan]   "
            "→ guided setup (host / user / password)\n"
            "  Type [bold cyan]help[/bold cyan]               → see all commands",
            title="🧠  MindSQL", border_style="yellow", padding=(1, 2)
        ))

    while True:
        try:
            # Build dynamic prompt showing current DB name
            if engine and db_url:
                try:    db_label = make_url(db_url).database or "?"
                except: db_label = "?"
                prompt_tokens = [
                    ("class:prompt", "MindSQL"),
                    ("", f" ({db_label})"),
                    ("class:prompt", " ❯ "),
                ]
            else:
                prompt_tokens = [("class:prompt", "MindSQL (not connected) ❯ ")]

            raw = session.prompt(prompt_tokens).strip()
            if not raw:
                continue

            cmd = raw.lower().strip()

            # ── EXIT ──────────────────────────────────────────────────────
            if cmd in ("exit", "quit", "\\q"):
                console.print("[dim]Goodbye.[/dim]")
                break

            # ── HELP ──────────────────────────────────────────────────────
            if cmd in ("help", "\\h", "?"):
                _print_help()
                continue

            # ── MINDSQL CONNECT  (no args = guided interactive setup) ─────
            if cmd in ("mindsql connect", "connect"):
                new_engine, new_url, new_schema = _interactive_connect(db_url)
                if new_engine:
                    engine, db_url, schema_context = new_engine, new_url, new_schema
                    print_banner(db_url)
                continue

            # ── MINDSQL CONNECT <raw url>  (advanced users) ───────────────
            if cmd.startswith("mindsql connect "):
                target = raw[16:].strip()
                if "://" in target:
                    new_engine, _ = perform_connection(target)
                    if new_engine:
                        engine, db_url = new_engine, target
                        schema_context = update_schema_context(engine)
                        print_banner(target)
                else:
                    console.print(
                        "[yellow]Just type [bold]mindsql connect[/bold] "
                        "for the guided setup.[/yellow]"
                    )
                continue

            # ── MINDSQL USE <dbname>  (switch database) ───────────────────
            if cmd.startswith("mindsql use ") or cmd.startswith("use "):
                # grab the last word which is the DB name
                db_name = raw.strip().rsplit(None, 1)[-1]
                new_engine, new_url, new_schema = _switch_database(db_name, db_url)
                if new_engine:
                    engine, db_url, schema_context = new_engine, new_url, new_schema
                    print_banner(db_url)
                continue

            # ── MINDSQL DATABASES  (list DBs on server) ───────────────────
            if cmd in ("mindsql databases", "show databases", "\\l"):
                if not engine:
                    console.print("[red]❌  Not connected.[/red]")
                    continue
                _show_databases(engine)
                continue

            # ── EXPORT ────────────────────────────────────────────────────
            if cmd.startswith("mindsql_export "):
                if not engine: console.print("[red]❌  Not connected.[/red]"); continue
                _handle_export(engine, raw[15:].strip())
                continue

            # ── PLOT ──────────────────────────────────────────────────────
            if cmd.startswith("mindsql_plot "):
                if not engine: console.print("[red]❌  Not connected.[/red]"); continue
                _handle_plot(engine, raw[13:].strip(), schema_context)
                continue

            # ── ANS / CHAT ────────────────────────────────────────────────
            if cmd.startswith("mindsql_ans "):
                if not engine: console.print("[red]❌  Not connected.[/red]"); continue
                engine, schema_context = _handle_ans(engine, raw[12:].strip(), schema_context)
                continue

            # ── STRICT AI ─────────────────────────────────────────────────
            if cmd.startswith("mindsql ") or cmd == "mindsql":
                if not engine: console.print("[red]❌  Not connected.[/red]"); continue
                prompt_text = raw[7:].strip()
                if _shortcircuit_schema(engine, prompt_text):
                    continue
                engine, schema_context = _handle_strict(engine, prompt_text, schema_context)
                continue

            # ── RAW SQL ───────────────────────────────────────────────────
            if not engine:
                console.print(
                    "[red]❌  Not connected. "
                    "Type [bold]mindsql connect[/bold] to get started.[/red]"
                )
                continue
            execute_sql(engine, raw)

        except KeyboardInterrupt:
            console.print()
            continue
        except EOFError:
            break
        except Exception as exc:
            console.print(Panel(f"[red]{exc}[/red]", title="Error", border_style="red"))


# ─────────────────────────────────────────────────────────────────────────────
# AI MODE HANDLERS
# ─────────────────────────────────────────────────────────────────────────────
def _handle_plot(engine, natural, schema_context):
    msgs = [
        {"role": "system", "content": _instruction("plot")},
        {"role": "user",   "content": f"Schema:\n{schema_context}\n\nRequest: {natural}"},
    ]
    for attempt in range(config.MAX_RETRIES):
        with console.status(f"[yellow]📊 Generating (attempt {attempt+1})…[/yellow]", spinner="earth"):
            sql = mindsql_start(msgs)
        if sql.startswith("CLARIFICATION_NEEDED:"):
            console.print(Panel(sql.replace("CLARIFICATION_NEEDED:", "").strip(),
                                title="⚠ Clarification Needed", border_style="yellow"))
            return
        if not validate_plot_sql(sql):
            if attempt < config.MAX_RETRIES - 1:
                msgs[1]["content"] += "\n\nERROR: Return exactly 2 cols: LABEL and aggregated VALUE."
            continue
        data = execute_sql(engine, sql, return_data=True)
        if data:
            draw_ascii_bar_chart(data)
        return
    console.print("[red]Plot failed after retries.[/red]")


def _handle_ans(engine, natural, schema_context):
    if _shortcircuit_schema(engine, natural):
        return engine, schema_context
    msgs = [
        {"role": "system", "content": _instruction("ans")},
        {"role": "user",   "content": f"Schema:\n{schema_context}\n\nQuestion: {natural}"},
    ]
    for attempt in range(config.MAX_RETRIES):
        with console.status(f"[green]💬 Thinking (attempt {attempt+1})…[/green]", spinner="dots"):
            resp = chat_with_model(msgs)
        full = resp["message"]["content"]
        if full.startswith("SCHEMA_ANSWER:"):
            console.print(Panel(full.replace("SCHEMA_ANSWER:", "").strip(),
                                title="🏗️ Schema Info", border_style="cyan"))
            return engine, schema_context
        console.print(Panel(full, title="🤖 AI Answer", border_style="green"))
        sql = extract_sql(full)
        if sql:
            if input("▶ Execute suggested SQL? (y/n): ").strip().lower() == "y":
                try:
                    execute_sql(engine, sql, raise_error=True)
                    if _is_ddl(sql):
                        schema_context = update_schema_context(engine)
                    break
                except Exception as exc:
                    if attempt < config.MAX_RETRIES - 1:
                        msgs[1]["content"] += f"\n\nERROR: {exc}\nFix the SQL."
                    else:
                        console.print(f"[red]Failed after {config.MAX_RETRIES} attempts.[/red]")
            else:
                break
        else:
            break
    return engine, schema_context


def _handle_strict(engine, natural, schema_context):
    msgs = [
        {"role": "system", "content": _instruction("strict")},
        {"role": "user",   "content": f"Schema:\n{schema_context}\n\nQuestion: {natural}"},
    ]
    for attempt in range(config.MAX_RETRIES):
        with console.status(f"[yellow]🧠 Generating (attempt {attempt+1})…[/yellow]", spinner="earth"):
            sql = mindsql_start(msgs)
        if sql.startswith("CLARIFICATION_NEEDED:"):
            console.print(Panel(sql.replace("CLARIFICATION_NEEDED:", "").strip(),
                                title="⚠ Clarification Needed", border_style="yellow"))
            return engine, schema_context
        if sql.startswith("SCHEMA_ANSWER:"):
            console.print(Panel(sql.replace("SCHEMA_ANSWER:", "").strip(),
                                title="🏗️ Schema Info", border_style="cyan"))
            return engine, schema_context
        sql = extract_sql(sql) or sql
        console.print(Panel(Syntax(sql, "sql", theme="monokai"),
                            title="✨ Generated SQL", border_style="yellow"))
        if input("🚀 Execute? (y/n): ").strip().lower() != "y":
            return engine, schema_context
        if not validate_sql_schema(sql, config.SCHEMA_MAP):
            console.print("[red]❌ Schema validation failed.[/red]")
            if attempt < config.MAX_RETRIES - 1:
                msgs[1]["content"] += "\n\nERROR: Column/table not found. Re-read schema and fix."
            continue
        execute_sql(engine, sql)
        if _is_ddl(sql):
            schema_context = update_schema_context(engine)
        break
    return engine, schema_context


def _handle_export(engine, natural):
    msgs = [
        {"role": "system", "content": STRICT_INSTRUCTION},
        {"role": "user",   "content": f"Schema:\n{load_file(config.SCHEMA_FILE)}\n\nQuestion: {natural}"},
    ]
    with console.status("[cyan]🗂 Generating export SQL…[/cyan]", spinner="dots"):
        sql = mindsql_start(msgs)
    sql = extract_sql(sql) or sql
    console.print(Panel(Syntax(sql, "sql", theme="monokai"), title="Export SQL", border_style="cyan"))
    if input("Export to CSV? (y/n): ").strip().lower() != "y":
        return
    data = execute_sql(engine, sql, return_data=True)
    if not data:
        console.print("[yellow]No data to export.[/yellow]")
        return
    out_file = f"mindsql_export_{int(time.time())}.csv"
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(data)
    console.print(Panel(f"[green]✅ {len(data)} rows → {out_file}[/green]", border_style="green"))


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────
def _shortcircuit_schema(engine, prompt):
    if not engine: return False
    low = prompt.lower()
    inspector = inspect(engine)
    if any(w in low for w in ("what tables","list tables","show tables","all tables")):
        console.print(Panel(", ".join(inspector.get_table_names()),
                            title="📋 Tables", border_style="cyan"))
        return True
    if any(w in low for w in ("columns","describe","what is in")):
        match = next((t for t in config.SCHEMA_MAP if t in low), None)
        if match:
            cols = inspector.get_columns(match)
            detail = "\n".join(f"  • {c['name']}  ({c['type']})" for c in cols)
            console.print(Panel(detail, title=f"📋 {match}", border_style="cyan"))
            return True
    return False


def _is_ddl(sql):
    return sql.strip().upper().startswith(("CREATE ", "DROP ", "ALTER "))


def _print_help():
    console.print(Panel(
        "[bold cyan]── Connection ───────────────────────────────────────[/bold cyan]\n"
        "  [cyan]mindsql connect[/cyan]           Guided setup  (host / user / pass)\n"
        "  [cyan]mindsql use <database>[/cyan]    Switch database  (reuses credentials)\n"
        "  [cyan]mindsql databases[/cyan]         List all databases on the server\n\n"
        "[bold cyan]── AI Commands ──────────────────────────────────────[/bold cyan]\n"
        "  [cyan]mindsql <question>[/cyan]         Generate & execute strict SQL\n"
        "  [cyan]mindsql_ans <question>[/cyan]     Explain + SQL\n"
        "  [cyan]mindsql_plot <question>[/cyan]    Terminal bar chart  📊\n"
        "  [cyan]mindsql_export <question>[/cyan]  Export results to CSV  🗂\n\n"
        "[bold cyan]── Direct SQL & Other ───────────────────────────────[/bold cyan]\n"
        "  [cyan]<any SQL statement>[/cyan]        Execute directly\n"
        "  [cyan]help[/cyan]   [cyan]exit[/cyan]   [cyan]quit[/cyan]\n"
        "  [dim]Tab = autocomplete  │  Ctrl+R = search history[/dim]",
        title="🧠  MindSQL Help", border_style="blue", padding=(1, 2)
    ))


if __name__ == "__main__":
    app()
