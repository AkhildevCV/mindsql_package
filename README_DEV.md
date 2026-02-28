# MindSQL Developer Guide

## Project Overview

MindSQL is an AI-powered database terminal. Users type natural language,
the AI generates SQL, it's validated against the live schema, and executed.

---

## Quick-Start (Developer)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run directly (for development)
python main.py shell

# 3. Build distributable installer (hides source code)
python build.py
# → dist/MindSQLSetup.exe
```

---

## Distributing to End-Users

1. Build with `python build.py`
2. Send `dist/MindSQLSetup.exe` to the user
3. User double-clicks it, clicks **"⚡ Install MindSQL"**
4. Everything is automatic:
   - Installs Python packages
   - Installs Ollama (if not present)
   - Downloads the AI model (~2 GB)
   - Creates the Ollama model
   - Adds `mindsql` to system PATH
   - Creates a Desktop shortcut
5. User opens any terminal and types `mindsql`

---

## Architecture

```
MindSQLSetup.exe (installer.py compiled)
└── On install, extracts and sets up:
    ├── mindsql[.exe]         ← compiled main.py + all modules
    ├── db_config.txt         ← saved connection string
    ├── schema.txt            ← AI context (auto-updated)
    └── mindsql_history.txt   ← prompt history

User types in terminal:
  mindsql <question>          → strict SQL generation + execution
  mindsql_ans <question>      → explanation + SQL
  mindsql_plot <question>     → terminal bar chart
  mindsql_export <question>   → results saved to CSV   ← NEW
  connect <db_name>           → switch database
```

---

## User Commands Reference

| Command | Description |
|---------|-------------|
| `mindsql <natural language>` | Generate and execute strict SQL |
| `mindsql_ans <question>` | Get explanation + SQL from AI |
| `mindsql_plot <metric>` | Render a terminal bar chart |
| `mindsql_export <question>` | Export results to timestamped CSV |
| `connect <db_name>` | Switch to another DB (same host) |
| `connect <full_url>` | Connect to any database |
| `<raw SQL>` | Execute SQL directly |
| `exit` / `quit` | Exit MindSQL |

---

## Supported Databases

| Database | Connection String |
|----------|-----------------|
| MySQL | `mysql+pymysql://user:pass@host:3306/db` |
| PostgreSQL | `postgresql+psycopg2://user:pass@host:5432/db` |
| SQLite | `sqlite:///path/to/file.db` |
| SQL Server | `mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server` |

---

## Improvements in This Version

### New Features
- **`mindsql_export`** – Export any AI-generated query to CSV automatically
- **Multi-database support** – PostgreSQL, SQLite, MSSQL added
- **Streaming AI** – `stream_chat()` in `ai_engine.py` for future streaming UI
- **`help` command** – Built-in command reference
- **Connection pooling** – `pool_pre_ping`, `pool_recycle` for reliability
- **Better error messages** – Show supported DB formats on connection failure

### Code Quality
- Removed all debug `print()` statements from production code
- Proper type hints throughout
- `raise_error` / `return_data` patterns in `execute_sql()` are cleaner
- All file paths resolve correctly whether running from source or PyInstaller bundle

### Installer
- Fully automated – single "Install" button
- Animated step-by-step progress UI
- Silent Ollama install (no user interaction needed)
- Adds to Windows PATH via registry + broadcasts `WM_SETTINGCHANGE`
- Creates Desktop shortcut automatically
- Works on Windows, Linux, macOS

---

## File Structure

```
mindsql_project/
├── installer.py       ← One-click GUI installer
├── main.py            ← Shell REPL entry point
├── ai_engine.py       ← Ollama AI communication
├── config.py          ← Centralized configuration
├── database.py        ← SQLAlchemy connection + execution
├── ui.py              ← Rich terminal UI components
├── validator.py       ← SQL validation + extraction
├── sql_completer.py   ← Tab-completion engine
├── schema_manager.py  ← Live schema sync
├── build.py           ← PyInstaller build script  ← NEW
└── requirements.txt
```

---

## Ideas for Future Versions

1. **Web UI** – FastAPI + React frontend (keep the AI engine as backend)
2. **Query History Search** – `Ctrl+R` fuzzy search through past natural-language queries
3. **Auto-explain** – After running a query, auto-show `EXPLAIN` output
4. **Result caching** – Cache identical queries for instant repeat results
5. **Multi-table visual schema** – ASCII art ER diagram from schema
6. **Ollama model selector** – Let user choose between models at runtime
7. **Query cost estimator** – Warn before running `SELECT *` on huge tables
8. **Dark/Light mode toggle** – Adapt Rich theme based on terminal background
