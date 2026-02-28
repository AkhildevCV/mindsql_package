# validator.py
"""
Security, SQL parsing, and validation logic using SQLGlot.
"""

import re
import sqlglot
from sqlglot import exp
from sql_metadata import Parser

import config
from ui import console


def extract_sql(text: str) -> str | None:
    """
    Extracts the first valid SQL statement from AI output.
    Handles markdown code fences and raw SQL text.
    """
    if not text:
        return None

    # 1. Try markdown fences first
    for pattern in (r"```sql\s*(.*?)\s*```", r"```\s*(.*?)\s*```"):
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()

    # 2. Raw SQL – strip trailing hallucinations
    clean = text.strip()
    keywords = (
        "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE",
        "DROP", "SET", "ALTER", "BEGIN", "WITH", "SHOW", "DESCRIBE",
    )
    if clean.upper().startswith(keywords):
        valid = []
        for stmt in clean.split(";"):
            stmt = stmt.strip()
            if stmt and stmt.upper().startswith(keywords):
                valid.append(stmt)
        if valid:
            return ";\n".join(valid) + ";"
        return clean

    return None


def validate_sql_schema(sql_code: str, schema_map: dict) -> bool:
    """
    Validates tables and columns against the known schema.
    Bypasses validation for DDL and admin commands.
    """
    upper = sql_code.strip().upper()

    # Fast-pass for DDL / admin commands
    if upper.startswith(("SHOW ", "DESCRIBE ", "CREATE ", "DROP ", "ALTER ",
                          "TRUNCATE ", "GRANT ", "REVOKE ")):
        return True

    try:
        parser = Parser(sql_code)
        sql_tables = parser.tables

        # Validate tables
        for table in sql_tables:
            if table not in schema_map:
                console.print(f"[red]Validation Error:[/red] Table '{table}' not found in schema.")
                return False

        # Validate columns
        for col_ref in parser.columns:
            if "(" in col_ref or "*" in col_ref:
                continue
            if "." in col_ref:
                tbl, col = col_ref.split(".", 1)
                tbl_cols = schema_map.get(tbl, {})
                actual_cols = tbl_cols if isinstance(tbl_cols, list) else tbl_cols.get("columns", [])
                if tbl in schema_map and col not in actual_cols:
                    console.print(f"[red]Validation Error:[/red] Column '{col}' not in table '{tbl}'.")
                    return False
            else:
                found = False
                for tbl in sql_tables:
                    tbl_data = schema_map.get(tbl, {})
                    cols = tbl_data if isinstance(tbl_data, list) else tbl_data.get("columns", [])
                    if col_ref in cols:
                        found = True
                        break
                if not found and sql_tables:
                    console.print(f"[red]Validation Error:[/red] Column '{col_ref}' not found.")
                    return False

        return True

    except Exception as exc:
        console.print(f"[yellow]Parser warning:[/yellow] {exc}")
        return True   # Be lenient on parse errors to avoid blocking valid SQL


def validate_plot_sql(sql: str) -> bool:
    """Ensures plotting SQL returns exactly 2 columns with an aggregate."""
    if not sql.upper().strip().startswith("SELECT"):
        return False
    try:
        select_part = sql.upper().split("FROM")[0]
        columns = select_part.replace("SELECT", "").split(",")
        if len(columns) != 2:
            return False
        return any(k in columns[1] for k in ("COUNT", "SUM", "AVG", "MIN", "MAX"))
    except Exception:
        return False
