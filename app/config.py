import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CAST_DATA_PATH = DATA_DIR / "cast.json"
DB_PATH = BASE_DIR / "dwts.db"

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
ADMIN_USERNAME = os.getenv("DWTS_ADMIN_USERNAME", "emma")
ADMIN_PASSWORD = os.getenv("DWTS_ADMIN_PASSWORD", "admin")
ADMIN_KEY = os.getenv("DWTS_ADMIN_KEY", "dwts-admin-dev-key")
