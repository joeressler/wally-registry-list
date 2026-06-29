"""Construct wally.run and dependency URLs from index data."""

from __future__ import annotations

from wally_registry_list.config import INDEX_REPO_URL, WALLY_RUN_BASE


def package_page_url(scope: str, name: str, version: str) -> str:
    return f"{WALLY_RUN_BASE}/package/{scope}/{name}?version={version}"


def dependency_spec(scope: str, name: str, version: str) -> str:
    return f"{scope}/{name}@{version}"


def index_file_url(scope: str, name: str) -> str:
    return f"{INDEX_REPO_URL}/blob/main/{scope}/{name}"
