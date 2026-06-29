"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path

from wally_registry_list import __version__

APP_NAME = "WallyRegistryList"
REPO_URL = "https://github.com/joear/WallyRegistryList"

INDEX_ARCHIVE_URL = (
    "https://github.com/UpliftGames/wally-index/archive/refs/heads/main.zip"
)
INDEX_REPO_URL = "https://github.com/UpliftGames/wally-index"
WALLY_RUN_BASE = "https://wally.run"

CACHE_TTL_SECONDS = 24 * 60 * 60
HTTP_TIMEOUT_SECONDS = 120
HTTP_MAX_RETRIES = 3

USER_AGENT = f"{APP_NAME}/{__version__} (+{REPO_URL})"


def app_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / ".local" / "share"
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def index_cache_dir() -> Path:
    path = app_data_dir() / "index"
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return app_data_dir() / "cache.db"


def github_token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
