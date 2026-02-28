# config.py
"""
Centralized configuration for MindSQL.
Automatically resolves paths based on where the app is installed.
"""

import os
import sys
from pathlib import Path

APP_NAME    = "MindSQL"
APP_VERSION = "1.0.0"
MODEL_NAME  = "mindsql-v2"
MAX_RETRIES = 3

# ── Resolve install/working directory ─────────────────────────────────────────
# Works whether running from source, PyInstaller bundle, or installed path.
if getattr(sys, "frozen", False):
    # PyInstaller bundle: use the directory of the exe
    _BASE = Path(sys.executable).parent
else:
    _BASE = Path(__file__).parent

# All data files live alongside the scripts (or in the install directory)
SCHEMA_FILE  = str(_BASE / "schema.txt")
DB_URL_FILE  = str(_BASE / "db_config.txt")
HISTORY_FILE = str(_BASE / "mindsql_history.txt")

# ── Database defaults ──────────────────────────────────────────────────────────
# Supports MySQL, PostgreSQL, SQLite – user can override via 'connect' command
BASE_DB_URL = "mysql+pymysql://trial:1234@localhost:3306/"

# Supported dialects shown in help
SUPPORTED_DIALECTS = {
    "mysql":      "mysql+pymysql://user:pass@host:3306/db",
    "postgresql": "postgresql+psycopg2://user:pass@host:5432/db",
    "sqlite":     "sqlite:///path/to/file.db",
    "mssql":      "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+17+for+SQL+Server",
}

# ── In-memory schema cache (populated at runtime) ────────────────────────────
SCHEMA_MAP: dict[str, list[str]] = {}
