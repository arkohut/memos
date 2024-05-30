import os

# Define the default database path
DEFAULT_DB_PATH = os.path.expanduser("~/.memos/database.db")

# Function to get the database path from environment variable or default
def get_database_path():
    return os.getenv("MEMOS_DATABASE_PATH", DEFAULT_DB_PATH)

# Ensure the directory exists
os.makedirs(os.path.dirname(DEFAULT_DB_PATH), exist_ok=True)