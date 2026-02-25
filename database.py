# database.py

"""
Database connection, schema extraction, and execution logic.
"""

import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import make_url
from rich.table import Table
from rich.panel import Panel
from rich import box

import config
from ui import console

# --- File Helpers ---
def load_file(filename):
    if not os.path.exists(filename):
        return None
    with open(filename, "r") as f:
        return f.read().strip()

def save_file(filename, content):
    with open(filename, "w") as f:
        f.write(content)

# --- Schema Extraction ---
def load_schema_map(engine):
    """Reads the database and builds a dictionary of tables and columns."""
    schema = {}
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    for table in table_names:
        columns = inspector.get_columns(table)
        column_names = [col["name"] for col in columns]
        foreign_keys = []
        for fk in inspector.get_foreign_keys(table):
            foreign_keys.append({
                "child_columns": fk["constrained_columns"],
                "parent_table": fk["referred_table"],
                "parent_columns": fk["referred_columns"]
            })
        schema[table] = {
            "columns": column_names,
            "foreign_keys": foreign_keys
        }
    return schema

# --- Connection Setup ---
def perform_connection(connection_string):
    """Connects to the database, saves the URL, and dumps the schema to a file."""
    with console.status(f"[bold blue]🔌 Connecting to {connection_string}...[/bold blue]", spinner="dots"):
        try:
            engine = create_engine(connection_string)
            inspector = inspect(engine)
            table_names = inspector.get_table_names()
            
            if not table_names:
                console.print("[yellow]⚠ Connected, but DB is empty.[/yellow]")
            else:
                # Save the schema context for the AI
                with open(config.SCHEMA_FILE, "w") as f:
                    for table_name in table_names:
                        columns = inspector.get_columns(table_name)
                        f.write(f"CREATE TABLE {table_name} (\n")
                        col_defs = []
                        for col in columns:
                            col_str = f"    {col['name']} {col['type']}"
                            col_defs.append(col_str)
                        f.write(",\n".join(col_defs))
                        f.write("\n);\n\n")
            
            save_file(config.DB_URL_FILE, connection_string)
            config.SCHEMA_MAP = load_schema_map(engine)
            return engine, table_names
            
        except Exception as e:
            console.print(Panel(f"[bold red]Connection Failed[/bold red]\n{e}", style="red"))
            return None, []

# --- SQL Execution ---
def execute_sql(engine, sql: str, raise_error=False, return_data=False):
    """Executes SQL commands safely and ensures data is returned for plotting."""
    last_result_data = []  # Initialize at the very top of the function
    
    try:
        raw_commands = sql.split(';')
        commands = [c.strip() for c in raw_commands if c.strip()]
        
        with engine.connect() as conn:
            trans = conn.begin() 
            try:
                for i, cmd in enumerate(commands):
                    if cmd.upper() in ['BEGIN', 'COMMIT', 'ROLLBACK']:
                        continue
                        
                    result = conn.execute(text(cmd))
                    
                    if result.returns_rows:
                        rows = result.fetchall()
                        # Force conversion to list of tuples immediately
                        last_result_data = [tuple(row) for row in rows]
                        
                        if not return_data:
                            table = Table(title="Query Result", box=box.ROUNDED)
                            keys = getattr(result, 'keys', lambda: [])()
                            for key in keys:
                                table.add_column(str(key), style="cyan")
                            for row in rows:
                                table.add_row(*[str(item) for item in row])
                            console.print(table)
                
                trans.commit()
            except Exception as script_error:
                trans.rollback()
                raise script_error

        # Return data AFTER the connection block is closed
        if return_data:
            return last_result_data
        
        if not return_data:
            console.print(Panel(f"[bold green]✓ Successfully ran {len(commands)} commands.[/bold green]", style="green"))

    except Exception as e:
        if raise_error:
            raise e
        # This is where the 'substitute' error happens if 'e' is None or malformed
        console.print(Panel(f"[bold red]SQL Execution Error[/bold red]\n{str(e)}", style="red"))
        return [] # Return empty list instead of None to prevent 'NoneType' errors later