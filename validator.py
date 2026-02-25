# validator.py

"""
Security, SQL parsing, and validation logic using SQLGlot.
"""
from sql_metadata import Parser
import config
from ui import console
import re
import sqlglot
from sqlglot import exp

def extract_sql(text):
    """Extracts raw SQL code and strips trailing hallucinations."""
    # 1. Look for markdown blocks
    import re
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match: return match.group(1).strip()
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match: return match.group(1).strip()
    
    # 2. Look for raw SQL statements and sanitize them
    clean_text = text.strip()
    keywords = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "SET", "ALTER", "BEGIN", "WITH", "SHOW", "DESCRIBE")
    
    if clean_text.upper().startswith(keywords):
        # Strip trailing hallucinations (like 'ErrorHandler:')
        valid_statements = []
        for stmt in clean_text.split(';'):
            stmt = stmt.strip()
            if not stmt: 
                continue
            # Only keep statements that start with a valid SQL keyword
            if stmt.upper().startswith(keywords):
                valid_statements.append(stmt)
        
        if valid_statements:
            return ";\n".join(valid_statements) + ";"
        return clean_text
        
    return None

def extract_tables(sql):
    """Extracts all table names and aliases from a SQL query."""
    parsed = sqlglot.parse_one(sql)
    tables = set()
    alias_map = {}
    for table in parsed.find_all(exp.Table):  
        real_name = table.name     
        tables.add(real_name)
        if table.alias:
            alias_map[table.alias.name] = real_name
    return tables, alias_map

def extract_columns(sql):
    """Extracts all column names and their associated tables/aliases."""
    parsed = sqlglot.parse_one(sql)
    columns = []
    for column in parsed.find_all(exp.Column):
        columns.append({
            "table": column.table,
            "column": column.name
        })
    return columns

def validate_sql_schema(sql_code, schema_map):
    """
    Validates that all tables and columns in the generated SQL actually exist.
    Bypasses deep parsing for administrative and DDL commands.
    """
    upper_sql = sql_code.strip().upper()
    
    # 1. THE FAST-PASS: Allow Admin and Creation queries to skip the parser
    bypass_keywords = ("SHOW ", "DESCRIBE ", "CREATE ", "DROP ", "ALTER ")
    if upper_sql.startswith(bypass_keywords):
        return True

    try:
        parser = Parser(sql_code)
        
        # 1. Extract and Validate Tables
        sql_tables = parser.tables 
        for table in sql_tables:
            if table not in schema_map:
                console.print(f"[bold red]Validation Error:[/bold red] Table '{table}' does not exist.")
                return False
                
        # 2. Extract and Validate Columns
        sql_columns = parser.columns
        for col_ref in sql_columns:
            if "(" in col_ref or "*" in col_ref:
                continue 
                
            if "." in col_ref:
                table_part, col_part = col_ref.split(".", 1)
                if table_part in schema_map and col_part not in schema_map[table_part]:
                    console.print(f"[bold red]Validation Error:[/bold red] Column '{col_part}' not found in table '{table_part}'.")
                    return False
            else:
                found = any(col_ref in schema_map[t] for t in sql_tables if t in schema_map)
                if not found:
                    console.print(f"[bold red]Validation Error:[/bold red] Column '{col_ref}' not found in the queried tables.")
                    return False

        return True

    except Exception as e:
        console.print(f"[bold red]Parser Error:[/bold red] Could not parse SQL structure. {e}")
        return False

def validate_plot_sql(sql: str) -> bool:
    """Ensures plotting SQL returns exactly 2 columns (LABEL and VALUE)."""
    sql_upper = sql.upper()

    # Must be SELECT
    if not sql_upper.startswith("SELECT"):
        return False

    # Count selected columns naively
    select_part = sql_upper.split("FROM")[0]
    columns = select_part.replace("SELECT", "").split(",")

    if len(columns) != 2:
        return False

    # VALUE must be aggregated or numeric
    if not any(k in columns[1] for k in ["COUNT", "SUM", "AVG", "MIN", "MAX"]):
        return False

    return True