"""Download and extract the wally-index archive from GitHub."""

from __future__ import annotations

import io
import logging
import shutil
import time
import zipfile
from collections.abc import Callable
from pathlib import Path

import httpx

from wally_registry_list.config import (
    HTTP_MAX_RETRIES,
    HTTP_TIMEOUT_SECONDS,
    INDEX_ARCHIVE_URL,
    USER_AGENT,
    github_token,
    index_cache_dir,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


def _http_headers() -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    token = github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def download_index_archive(
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Download the index zip and extract it. Returns the extracted root directory."""
    cache_dir = index_cache_dir()
    extracted_marker = cache_dir / ".extracted"
    extract_root = _find_extract_root(cache_dir)

    if extract_root is not None and extracted_marker.exists():
        return extract_root

    if on_progress:
        on_progress("Downloading wally-index from GitHub...")

    content = _download_with_retries(INDEX_ARCHIVE_URL)

    if on_progress:
        on_progress("Extracting index archive...")

    if cache_dir.exists():
        for child in cache_dir.iterdir():
            if child.name == "cache.db":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        archive.extractall(cache_dir)

    extract_root = _find_extract_root(cache_dir)
    if extract_root is None:
        raise RuntimeError("Failed to locate extracted wally-index directory")

    extracted_marker.write_text(str(time.time()), encoding="utf-8")
    return extract_root


def _download_with_retries(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(HTTP_MAX_RETRIES):
        try:
            with httpx.Client(
                headers=_http_headers(),
                timeout=HTTP_TIMEOUT_SECONDS,
                follow_redirects=True,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.content
        except (httpx.HTTPError, OSError) as exc:
            last_error = exc
            logger.warning("Download attempt %s failed: %s", attempt + 1, exc)
            if attempt < HTTP_MAX_RETRIES - 1:
                time.sleep(2**attempt)
    raise RuntimeError(f"Failed to download index after {HTTP_MAX_RETRIES} attempts") from last_error


def _find_extract_root(cache_dir: Path) -> Path | None:
    for child in cache_dir.iterdir():
        if child.is_dir() and child.name.startswith("wally-index"):
            return child
    return None


def index_is_fresh(max_age_seconds: int) -> bool:
    marker = index_cache_dir() / ".extracted"
    if not marker.exists():
        return False
    try:
        fetched_at = float(marker.read_text(encoding="utf-8").strip())
    except ValueError:
        return False
    return (time.time() - fetched_at) < max_age_seconds
