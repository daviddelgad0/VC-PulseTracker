import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
WATCHLIST_PATH = ROOT_DIR / "config" / "watchlist.yaml"

DATABASE_URL = os.environ["DATABASE_URL"]
SEC_EDGAR_USER_AGENT = os.environ.get(
    "SEC_EDGAR_USER_AGENT", "VC Pulse Tracker (set SEC_EDGAR_USER_AGENT in .env)"
)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
PRODUCTHUNT_API_TOKEN = os.environ.get("PRODUCTHUNT_API_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def load_watchlist() -> dict:
    with open(WATCHLIST_PATH) as f:
        return yaml.safe_load(f)
