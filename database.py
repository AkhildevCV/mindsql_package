# database.py
"""
Database connection, schema extraction, and SQL execution.
Supports MySQL, PostgreSQL, SQLite, and MSSQL.
"""

import os
from sqlalchemy import create_engine, inspect, text, event
from sqlalchemy.engine.url import make_url
from rich.table import Table
from rich.panel import Panel
from rich import box

import config
from ui import console


# ── File helpers ───────────────────────────────────────────────────────────────
def load_file(filename: str) -> str | None:
    if not os.path.exists(filename):
        return None
    with open(filename, "r", encoding="utf-8") as f:
        return f.read().strip() or None


def save_file(filename: str, content: str):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)


# ── Schema extraction ──────────────────────────────────────────────────────────
def load_schema_map(engine) -> dict:
    """Builds the in-memory schema dict {table: {columns, foreign_keys}}."""
    schema = {}
    inspector = inspect(engine)
    for table in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns(table)]
        foreign_keys = [
            {
                "child_columns": fk["constrained_columns"],
                "parent_table": fk["referred_table"],
                "parent_columns": fk["referred_columns"],
            }
            for fk in inspector.get_foreign_keys(table)
        ]
        schema[table] = {"columns": columns, "foreign_keys": foreign_keys}
    return schema


# ── Connection ─────────────────────────────────────────────────────────────────
def perform_connection(connection_string: str):
    """
    Connects to any SQLAlchemy-supported database,
    saves the URL, and returns (engine, table_names).
    """
    dialect = connection_string.split("://")[0] if "://" in connection_string else "unknown"
    label = _dialect_label(dialect)

    with console.status(
        f"[bold blue]🔌 Connecting to {label}…[/bold blue]", spinner="dots"
    ):
        try:
            engine = create_engine(
                connection_string,
                pool_pre_ping=True,        # Detect stale connections
                pool_recycle=3600,         # Recycle after 1 hour
                connect_args=_connect_args(dialect),
            )
            inspector = inspect(engine)
            table_names = inspector.get_table_names()

            if not table_names:
                console.print("[yellow]⚠ Connected, but database is empty.[/yellow]")
            else:
                _write_schema_file(engine, inspector, table_names)

            save_file(config.DB_URL_FILE, connection_string)
            config.SCHEMA_MAP = load_schema_map(engine)

            console.print(
                Panel(
                    f"[green]✅ Connected to [bold]{label}[/bold]\n"
                    f"   {len(table_names)} table(s) found.[/green]",
                    border_style="green",
                )
            )
            return engine, table_names

        except Exception as exc:
            console.print(
                Panel(
                    f"[bold red]Connection Failed[/bold red]\n{exc}\n\n"
                    "[dim]Supported formats:[/dim]\n"
                    + "\n".join(f"  {k}: {v}" for k, v in config.SUPPORTED_DIALECTS.items()),
                    style="red",
                )
            )
            return None, []


def _dialect_label(dialect: str) -> str:
    return {
        "mysql":          "MySQL",
        "mysql+pymysql":  "MySQL (PyMySQL)",
        "postgresql":     "PostgreSQL",
        "postgresql+psycopg2": "PostgreSQL",
        "sqlite":         "SQLite",
        "mssql":          "SQL Server",
        "mssql+pyodbc":   "SQL Server (ODBC)",
    }.get(dialect, dialect)


def _connect_args(dialect: str) -> dict:
    """Dialect-specific connection arguments."""
    if "mysql" in dialect:
        return {"connect_timeout": 10}
    if "postgresql" in dialect:
        return {"connect_timeout": 10, "application_name": "MindSQL"}
    if "sqlite" in dialect:
        return {"timeout": 10}
    return {}


def _write_schema_file(engine, inspector, table_names: list):
    """Writes a human-readable CREATE TABLE schema to disk for AI context."""
    with open(config.SCHEMA_FILE, "w", encoding="utf-8") as f:
        for table in table_names:
            cols = inspector.get_columns(table)
            f.write(f"CREATE TABLE {table} (\n")
            col_defs = [f"    {c['name']} {c['type']}" for c in cols]
            f.write(",\n".join(col_defs))
            f.write("\n);\n")
            pks = inspector.get_pk_constraint(table).get("constrained_columns", [])
            if pks:
                f.write(f"-- Primary Keys: {', '.join(pks)}\n")
            for fk in inspector.get_foreign_keys(table):
                f.write(
                    f"-- Foreign Key: ({', '.join(fk['constrained_columns'])}) "
                    f"→ {fk['referred_table']}({', '.join(fk['referred_columns'])})\n"
                )
            f.write("\n")


# ── SQL Execution ──────────────────────────────────────────────────────────────
def execute_sql(engine, sql: str, raise_error: bool = False, return_data: bool = False):
    """
    Executes one or more SQL statements safely.
    - return_data=True → returns list of tuples (for plotting/export)
    - raise_error=True → re-raises exceptions (for retry loops)
    """
    last_data: list[tuple] = []

    try:
        commands = [c.strip() for c in sql.split(";") if c.strip()]

        with engine.connect() as conn:
            trans = conn.begin()
            try:
                for cmd in commands:
                    if cmd.upper() in ("BEGIN", "COMMIT", "ROLLBACK"):
                        continue
                    result = conn.execute(text(cmd))

                    if result.returns_rows:
                        rows = result.fetchall()
                        last_data = [tuple(r) for r in rows]

                        if not return_data:
                            _print_result_table(result, rows)

                trans.commit()
            except Exception as exc:
                trans.rollback()
                raise exc

        if return_data:
            return last_data

        if not return_data and commands:
            console.print(
                Panel(
                    f"[bold green]✓ Executed {len(commands)} statement(s) successfully.[/bold green]",
                    style="green",
                )
            )

    except Exception as exc:
        if raise_error:
            raise
        console.print(
            Panel(f"[bold red]SQL Error[/bold red]\n{exc}", style="red")
        )
        return []


def _print_result_table(result, rows: list):
    """Renders query results as a rich Table."""
    if not rows:
        console.print("[dim]Query returned no rows.[/dim]")
        return
    tbl = Table(box=box.ROUNDED, border_style="dim", show_lines=False)
    for key in result.keys():
        tbl.add_column(str(key), style="cyan", no_wrap=False)
    for row in rows:
        tbl.add_row(*[str(v) if v is not None else "[dim]NULL[/dim]" for v in row])
    console.print(tbl)
    console.print(f"[dim]{len(rows)} row(s)[/dim]")
