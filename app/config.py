import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CAST_DATA_PATH = DATA_DIR / "cast.json"

raw_db_path = os.getenv("DWTS_DB_PATH")
if raw_db_path:
    DB_PATH = Path(raw_db_path).expanduser()
    if not DB_PATH.is_absolute():
        DB_PATH = (BASE_DIR / DB_PATH).resolve()
else:
    DB_PATH = BASE_DIR / "dwts.db"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

front_dir = os.getenv("DWTS_FRONTEND_DIR")
if front_dir:
    FRONTEND_DIR = Path(front_dir).expanduser()
    if not FRONTEND_DIR.is_absolute():
        FRONTEND_DIR = (BASE_DIR / FRONTEND_DIR).resolve()
else:
    FRONTEND_DIR = BASE_DIR / "frontend"

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
ADMIN_USERNAME = os.getenv("DWTS_ADMIN_USERNAME", "emma")
ADMIN_PASSWORD = os.getenv("DWTS_ADMIN_PASSWORD", "admin")
ADMIN_KEY = os.getenv("DWTS_ADMIN_KEY", "dwts-admin-dev-key")
