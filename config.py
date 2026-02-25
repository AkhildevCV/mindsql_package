# config.py

"""
Centralized configuration and settings for MindSQL.
"""

MODEL_NAME = "mindsql-v2"
SCHEMA_FILE = "schema.txt"
DB_URL_FILE = "db_config.txt"
HISTORY_FILE = "mindsql_history.txt"
MAX_RETRIES = 3

# Global Schema Map to store database structure in memory
SCHEMA_MAP = {}
# config.py
# ... (your existing config variables) ...

# Default connection string base (everything before the database name)
BASE_DB_URL = "mysql+pymysql://trial:1234@localhost:3306/"