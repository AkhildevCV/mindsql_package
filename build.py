# build.py
"""
MindSQL Build Script
====================
Compiles the MindSQL application and installer into standalone executables
using PyInstaller. Source code is hidden from end users.

Usage:
    python build.py

Output:
    dist/
    ├── MindSQLSetup.exe    ← Distribute this to users
    └── mindsql/            ← Bundled into the installer via --add-data
        └── mindsql.exe

Requirements:
    pip install pyinstaller pywin32 customtkinter
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"

# Files to embed INSIDE the installer so it can copy them on install
APP_FILES = [
    "main.py",
    "ai_engine.py",
    "config.py",
    "database.py",
    "ui.py",
    "validator.py",
    "sql_completer.py",
    "schema_manager.py",
]


def clean():
    print("🧹 Cleaning previous build…")
    shutil.rmtree(DIST, ignore_errors=True)
    shutil.rmtree(BUILD, ignore_errors=True)
    for spec in ROOT.glob("*.spec"):
        spec.unlink()


def build_main_app():
    """
    Compile main.py + all modules into a single mindsql executable.
    This is what gets installed on the user's machine.
    """
    print("🔨 Building mindsql application…")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "mindsql",
        "--distpath", str(DIST / "app"),
        "--workpath", str(BUILD / "app"),
        "--specpath", str(BUILD),
        "--hidden-import", "sqlalchemy.dialects.mysql.pymysql",
        "--hidden-import", "sqlalchemy.dialects.postgresql.psycopg2",
        "--hidden-import", "sqlalchemy.dialects.sqlite.pysqlite",
        "--hidden-import", "sql_metadata",
        "--hidden-import", "sqlglot",
        "--hidden-import", "prompt_toolkit",
        "--hidden-import", "rich",
        "--hidden-import", "ollama",
        "--collect-all", "customtkinter",
        "--collect-all", "sql_metadata",
        # Embed all app modules so no source is needed at runtime
        "--add-data", "config.py:.",
        "--add-data", "ai_engine.py:.",
        "--add-data", "database.py:.",
        "--add-data", "ui.py:.",
        "--add-data", "validator.py:.",
        "--add-data", "sql_completer.py:.",
        "--add-data", "schema_manager.py:.",
        "main.py",
    ]
    subprocess.run(cmd, check=True)
    print("✅ mindsql executable built.")


def build_installer():
    """
    Compile installer.py into a standalone setup executable.
    Embeds the compiled mindsql.exe so users only download ONE file.
    """
    print("🔨 Building MindSQLSetup installer…")

    mindsql_exe = DIST / "app" / "mindsql.exe"
    if not mindsql_exe.exists():
        # Linux / macOS builds
        mindsql_exe = DIST / "app" / "mindsql"

    if not mindsql_exe.exists():
        print("⚠ mindsql executable not found – building installer without bundled app.")
        add_data_args = []
    else:
        add_data_args = ["--add-data", f"{mindsql_exe}:app_payload"]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "MindSQLSetup",
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "installer"),
        "--specpath", str(BUILD),
        "--windowed",                      # No console window for installer
        "--hidden-import", "winreg",
        "--collect-all", "customtkinter",
        *add_data_args,
        "installer.py",
    ]
    subprocess.run(cmd, check=True)
    print("✅ MindSQLSetup.exe built.")


def show_summary():
    print("\n" + "═" * 50)
    print("  Build Complete!")
    print("═" * 50)
    for f in DIST.rglob("*"):
        if f.is_file():
            size_mb = f.stat().st_size / 1_048_576
            print(f"  📦 {f.relative_to(DIST)}  ({size_mb:.1f} MB)")
    print("\n  Distribute: dist/MindSQLSetup.exe")
    print("  Users run it once → 'mindsql' works everywhere.\n")


if __name__ == "__main__":
    clean()
    build_main_app()
    build_installer()
    show_summary()
