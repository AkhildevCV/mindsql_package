# main.py

"""
The Main Entry Point and Shell Loop for MindSQL.
"""
from sql_completer import SQLCompleter
import re
from prompt_toolkit.completion import Completer, Completion
from schema_manager import update_schema_context
import typer
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.panel import Panel
from rich.syntax import Syntax
from sqlalchemy import inspect

import config
from ui import console, print_banner, draw_ascii_bar_chart
from database import load_file, perform_connection, execute_sql
from validator import validate_plot_sql, validate_sql_schema, extract_sql
from ai_engine import mindsql_start, chat_with_model

app = typer.Typer(help="MindSQL Modular CLI", add_completion=False)


# ==========================================
# THIN PROMPTS (ROUTER PATTERN)
# ==========================================

plot_instruction = (
    "You are a Data Visualization Assistant. Your ONLY goal is to write a single SQL query for a chart. Output ONLY raw SQL.\n"
    "RULES:\n"
    "1. TWO COLUMNS: Return EXACTLY 2 columns. Alias column 1 as 'LABEL' (Text) and column 2 as 'VALUE' (Number).\n"
    "2. AGGREGATE: You MUST use math (SUM, COUNT, AVG) for the VALUE column and include a GROUP BY clause.\n"
    "3. EDUCATED GUESSES: If a metric is ambiguous, make a logical assumption based on the schema.\n"
    "4. NO TEXT: Never ask for clarification or explain yourself. Output only the SELECT statement."
)

ans_instruction = (
    "You are a Database Expert. Your goal is to write accurate SQL.\n"
    "STEP 1: Briefly list the exact tables/columns you will use.\n"
    "STEP 2: Write the SQL script.\n"
    "RULES:\n"
    "1. VERIFY: You must use exact names from the provided Context.\n"
    "2. IDENTIFIER VS VALUE: Treat specific proper nouns/conditions not in the schema as data VALUES for a WHERE clause.\n"
    "3. MINIMAL JOINS: Only join tables strictly necessary for the query.\n"
    "4. GUARDRAIL: If critical schema info is missing, output 'CLARIFICATION_NEEDED:' followed by an explanation.\n"
    "5. METADATA: If the user asks about database structure (e.g., tables, columns, primary/foreign keys), DO NOT write SQL. Output exactly 'SCHEMA_ANSWER:\n' followed by the plain English answer based on the Context."
)

strict_instruction = (
    "You are a strict SQL generator. Output ONLY SQL code. Separate with semicolons (;).\n"
    "RULES:\n"
    "1. VERIFY: Use EXACT table/column names from schema. Never guess.\n"
    "2. VALUES: Capitalized words not in the schema are WHERE clause values, not columns.\n"
    "3. GUARDRAIL: If information is missing, halt and reply exactly with 'CLARIFICATION_NEEDED:' followed by what is missing.\n"
    "4. METADATA: If asked about database structure (e.g., tables, columns, primary/foreign keys), DO NOT write SQL. Output exactly 'SCHEMA_ANSWER:\n' followed by the plain English answer based on the Context."
)

def get_system_instruction(mode: str) -> str:
    """Routes the prompt based on the explicitly selected CLI mode."""
    if mode == "plot": return plot_instruction
    elif mode == "ans": return ans_instruction
    else: return strict_instruction

# ==========================================

@app.command()
def connect(connection_string: str):
    pass 

@app.command()
def shell():
    print("Initialising......")
    
    db_url = load_file(config.DB_URL_FILE)
    engine = None
    
    if db_url: 
        print(f"Found saved database configuration. Auto-connecting...")
        engine, tables = perform_connection(db_url)
        if engine:
            schema_context = update_schema_context(engine)
    
    schema_context = load_file(config.SCHEMA_FILE)
    style = Style.from_dict({ 'prompt': 'ansicyan bold' })
    session = PromptSession(history=FileHistory(config.HISTORY_FILE), style=style, completer=SQLCompleter())

    if engine: print_banner(db_url)

    while True:
        try:
            user_input = session.prompt([('class:prompt', 'SQL> ')]).strip()
            print("User typed : ", user_input)
            if not user_input: continue
            
            if user_input.lower().startswith("sql>"): user_input = user_input[4:].strip()
            if user_input.lower() in ["exit", "quit"]: break

            # --- CONNECT MODE ---
            # --- CONNECT MODE ---
            # --- CONNECT MODE ---
            if user_input.lower().startswith("mindsql connect ") or user_input.lower().startswith("connect "):
                target = user_input.split("connect ", 1)[1].strip()
                
                # If the user only typed a database name (no protocol like "://")
                if "://" not in target:
                    # Prioritize config.py settings over the cached db_config.txt
                    if hasattr(config, 'BASE_DB_URL'):
                        base = config.BASE_DB_URL
                        if not base.endswith('/'):
                            base += '/'
                        target = base + target
                    elif db_url:
                        try: 
                            target = str(make_url(db_url).set(database=target))
                        except: 
                            pass
                
                # DEBUG: Print the exact target string being used
                console.print(f"[dim yellow]DEBUG: Attempting to connect via -> {target}[/dim yellow]")
                
                new_engine, tables = perform_connection(target)
                if new_engine:
                    engine = new_engine
                    db_url = target
                    schema_context = update_schema_context(engine)
                    print_banner(target)
                continue

            # --- PLOT MODE ---
            if user_input.lower().startswith("mindsql_plot"):
                if not engine:
                    console.print("[red]❌ Not connected.[/red]")
                    continue
                
                natural_prompt = user_input[12:].strip()
                system_instruction = get_system_instruction("plot")
                
                formatted_input = f"Context:\n{schema_context}\n\nQuestion: {natural_prompt}"
                messages = [
                    {'role': 'system', 'content': system_instruction},
                    {'role': 'user', 'content': formatted_input}
                ]
                
                for attempt in range(config.MAX_RETRIES):
                    with console.status(f"[bold yellow]📊 Generating Plot Data (Attempt {attempt+1})...[/bold yellow]", spinner="earth"):
                        sql_code = mindsql_start(messages)

                    if sql_code and sql_code.startswith("CLARIFICATION_NEEDED:"):
                        warning_msg = sql_code.replace("CLARIFICATION_NEEDED:", "").strip()
                        console.print(Panel(f"[bold yellow]⚠ Missing Information:[/bold yellow]\n{warning_msg}", style="yellow"))
                        break

                    # Sanitize AI output
                    sql_code = extract_sql(sql_code) or sql_code

                    if sql_code and validate_plot_sql(sql_code):
                        
                        # Python Schema Validator to prevent hallucinated joins
                        is_valid = validate_sql_schema(sql_code, config.SCHEMA_MAP)
                        if not is_valid:
                            console.print(Panel("[bold red]❌ Schema Validation Failed[/bold red]", style="red"))
                            if attempt < config.MAX_RETRIES - 1:
                                messages[1]['content'] = formatted_input + f"\n\n⚠ Failed SQL: {sql_code}\nError: You used an invalid table or column. Re-read Context."
                            continue

                        from rich import box
                        console_print_box = config.box.ROUNDED if hasattr(config, 'box') else box.ROUNDED
                        console.print(Panel(Syntax(sql_code, "sql", theme="monokai"), title="✨ Plotting SQL", border_style="yellow", box=console_print_box))
                        
                        if input("🚀 Run Plot? (y/n): ").strip().lower() == 'y':
                            print("Commencing sql execution....")
                            try:
                                data = execute_sql(engine, sql_code, return_data=True)
                                
                                # Empty data check so it doesn't fail silently
                                if data: 
                                    draw_ascii_bar_chart(data)
                                else:
                                    console.print(Panel("[bold yellow]⚠ Query executed successfully, but returned 0 rows. Nothing to plot![/bold yellow]", border_style="yellow"))
                                break 
                            except Exception as e:
                                console.print(f"[bold red]Execution Error:[/bold red] {e}")
                                if attempt < config.MAX_RETRIES - 1:
                                     messages[1]['content'] = formatted_input + f"\n\n⚠ Database Error: {e}\nFix the query logic."
                                else:
                                    break
                        else:
                            break
                    else:
                        if not validate_plot_sql(sql_code):
                            console.print("[red]❌ Invalid plot SQL. Must return LABEL + VALUE only.[/red]")
                        break 
                
                continue 

            # --- CHAT MODE (Chain of Thought) ---
            elif user_input.lower().startswith("mindsql_ans"):
                print("Entering chat mode...")
                if not engine:
                    console.print("[red]❌ Not connected.[/red]")
                    continue

                natural_prompt = user_input[11:].strip()
                
                # --- THE AI BYPASS INTERCEPTOR ---
                lower_prompt = natural_prompt.lower()
                if "tables" in lower_prompt and any(w in lower_prompt for w in ["what", "list", "show", "all"]):
                    inspector = inspect(engine)
                    tables = inspector.get_table_names()
                    console.print(Panel(f"[bold cyan]Database Tables:[/bold cyan]\n{', '.join(tables)}", border_style="cyan"))
                    continue 

                if "columns" in lower_prompt or "describe" in lower_prompt or "what is in" in lower_prompt:
                    target_table = next((t for t in config.SCHEMA_MAP.keys() if t in lower_prompt), None)
                    if target_table:
                        inspector = inspect(engine)
                        columns = inspector.get_columns(target_table)
                        col_details = "\n".join([f"- {c['name']} ({c['type']})" for c in columns])
                        console.print(Panel(f"[bold cyan]Columns in '{target_table}':[/bold cyan]\n{col_details}", border_style="cyan"))
                        continue 
                # ---------------------------------

                system_instruction = get_system_instruction("ans")
                formatted_input = f"Context:\n{schema_context}\n\nQuestion: {natural_prompt}"
                messages = [
                    {'role': 'system', 'content': system_instruction},
                    {'role': 'user', 'content': formatted_input}
                ]

                for attempt in range(config.MAX_RETRIES):
                    with console.status(f"[bold green]💬 Asking AI (Attempt {attempt+1})...[/bold green]", spinner="dots"):
                        response = chat_with_model(messages)
                        full_response = response['message']['content']
                    
                    if full_response.startswith("SCHEMA_ANSWER:"):
                        answer_text = full_response.replace("SCHEMA_ANSWER:", "").strip()
                        console.print(Panel(answer_text, title="🏗️ Schema Architecture", border_style="cyan"))
                        break

                    console.print(Panel(full_response, title="🤖 AI Answer", border_style="green"))
                    sql_code = extract_sql(full_response)
                    
                    if sql_code:
                        if input("▶ Execute suggested SQL? (y/n): ").strip().lower() == 'y':
                            try:
                                execute_sql(engine, sql_code, raise_error=True)
                                
                                # --- THE AUTO-SYNC TRIGGER ---
                                if sql_code.strip().upper().startswith(("CREATE ", "DROP ", "ALTER ")):
                                    console.print("[bold cyan]🔄 Structural change detected. Re-syncing schema...[/bold cyan]")
                                    schema_context = update_schema_context(engine)
                                # -----------------------------
                                break 
                            except Exception as e:
                                if attempt < config.MAX_RETRIES - 1:
                                    console.print(f"[yellow]⚠ Script Error: {e}. Retrying...[/yellow]")
                                    error_context = (
                                        f"\n\n⚠ WARNING: Your previous execution failed.\n"
                                        f"Failed SQL: {sql_code}\n"
                                        f"Database Error: {str(e)}\n"
                                        f"Re-read the Context and fix the logic."
                                    )
                                    messages[1]['content'] = formatted_input + error_context
                                else:
                                    console.print(f"[bold red]❌ Failed after {config.MAX_RETRIES} attempts.[/bold red]")
                        else: break
                    else: break
                continue

            # --- STRICT MODE ---
            elif user_input.lower().startswith("mindsql"):
                print("Strict mode on ")
                if not engine:
                    console.print("[red]❌ Not connected.[/red]")
                    continue
                
                natural_prompt = user_input[7:].strip()
                
                # --- THE AI BYPASS INTERCEPTOR ---
                lower_prompt = natural_prompt.lower()
                if "tables" in lower_prompt and any(w in lower_prompt for w in ["what", "list", "show", "all"]):
                    inspector = inspect(engine)
                    tables = inspector.get_table_names()
                    console.print(Panel(f"[bold cyan]Database Tables:[/bold cyan]\n{', '.join(tables)}", border_style="cyan"))
                    continue 

                if "columns" in lower_prompt or "describe" in lower_prompt or "what is in" in lower_prompt:
                    target_table = next((t for t in config.SCHEMA_MAP.keys() if t in lower_prompt), None)
                    if target_table:
                        inspector = inspect(engine)
                        columns = inspector.get_columns(target_table)
                        col_details = "\n".join([f"- {c['name']} ({c['type']})" for c in columns])
                        console.print(Panel(f"[bold cyan]Columns in '{target_table}':[/bold cyan]\n{col_details}", border_style="cyan"))
                        continue 
                # ---------------------------------

                system_instruction = get_system_instruction("strict")
                formatted_input = f"Context:\n{schema_context}\n\nQuestion: {natural_prompt}"
                messages = [
                    {'role': 'system', 'content': system_instruction},
                    {'role': 'user', 'content': formatted_input}
                ]
                
                for attempt in range(config.MAX_RETRIES):
                    with console.status(f"[bold yellow]🧠 Thinking (Attempt {attempt+1})...[/bold yellow]", spinner="earth"):
                        generated_sql = mindsql_start(messages)

                    if generated_sql.startswith("CLARIFICATION_NEEDED:"):
                        warning_msg = generated_sql.replace("CLARIFICATION_NEEDED:", "").strip()
                        console.print(Panel(f"[bold yellow]⚠ Guardrail Triggered:[/bold yellow]\n{warning_msg}", style="yellow"))
                        break
                        
                    if generated_sql.startswith("SCHEMA_ANSWER:"):
                        answer_text = generated_sql.replace("SCHEMA_ANSWER:", "").strip()
                        console.print(Panel(answer_text, title="🏗️ Schema Architecture", border_style="cyan"))
                        break

                    generated_sql = extract_sql(generated_sql) or generated_sql

                    console.print(Panel(Syntax(generated_sql, "sql", theme="monokai"), title="✨ Generated SQL", border_style="yellow"))
                    
                    if input("🚀 Execute SQL? (y/n): ").strip().lower() != 'y':
                        break

                    is_valid = validate_sql_schema(generated_sql, config.SCHEMA_MAP)
                    if not is_valid:
                        console.print(Panel("[bold red]❌ Schema Validation Failed[/bold red]", style="red"))
                        
                        if attempt < config.MAX_RETRIES - 1:
                            error_context = (
                                f"\n\n⚠ WARNING: Your previous attempt failed validation.\n"
                                f"Failed SQL: {generated_sql}\n"
                                f"Error: You used a column or table that does not exist. "
                                f"Re-read the Context exactly and fix the aliases/columns."
                            )
                            messages[1]['content'] = formatted_input + error_context
                        continue
                    else:
                        console.print(Panel("[bold green]✅ Schema Validation Passed[/bold green]", style="green"))
                        execute_sql(engine, generated_sql)
                        
                        # --- THE AUTO-SYNC TRIGGER ---
                        if generated_sql.strip().upper().startswith(("CREATE ", "DROP ", "ALTER ")):
                            console.print("[bold cyan]🔄 Structural change detected. Re-syncing schema...[/bold cyan]")
                            schema_context = update_schema_context(engine)
                        # -----------------------------
                        break

            # --- STANDARD SQL ---
            else:
                print("Reverting to normal mode....")
                if not engine:
                    console.print("[red]❌ Not connected.[/red]")
                    continue
                execute_sql(engine, user_input)

        except KeyboardInterrupt: continue
        except Exception as e: console.print(Panel(f"Error: {e}", style="red"))

if __name__ == "__main__":
    app()