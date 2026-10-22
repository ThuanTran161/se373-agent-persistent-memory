import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()

MEMORY_DIR = BASE_DIR / "memory_store"
CONVENTIONS_FILE = MEMORY_DIR / "conventions.json"
MARKDOWN_CONVENTIONS_FILE = MEMORY_DIR / "AGENTS.md"
MEMORY_HISTORY_FILE = MEMORY_DIR / "history.json"

MEMORY_DIR.mkdir(parents=True, exist_ok=True)
