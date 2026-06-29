"""Parse NDJSON package files from the wally-index."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from packaging.version import InvalidVersion, Version

from wally_registry_list.models import PackageRecord, PackageVersion

logger = logging.getLogger(__name__)

SKIP_FILES = {"config.json"}
SKIP_SUFFIXES = (".json",)


def is_package_file(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    parts = relative.parts
    if len(parts) != 2:
        return False
    if path.name in SKIP_FILES or path.name.endswith(SKIP_SUFFIXES):
        return False
    return path.is_file()


def parse_index(root: Path) -> list[PackageRecord]:
    records: list[PackageRecord] = []
    for path in sorted(root.rglob("*")):
        if not is_package_file(path, root):
            continue
        scope, name = path.relative_to(root).parts
        try:
            record = _parse_package_file(scope, name, path)
        except Exception as exc:
            logger.warning("Skipping %s: %s", path, exc)
            continue
        if record is not None:
            records.append(record)
    records.sort(key=lambda r: r.full_name.lower())
    return records


def _parse_package_file(scope: str, name: str, path: Path) -> PackageRecord | None:
    versions: list[PackageVersion] = []
    text = path.read_text(encoding="utf-8")
    for line_order, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            manifest = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid JSON in %s line %s: %s", path, line_order + 1, exc)
            continue
        version = _manifest_to_version(manifest, line_order)
        if version is not None:
            versions.append(version)

    if not versions:
        return None

    versions = _dedupe_versions(versions)
    latest = _pick_latest_version(versions)
    return PackageRecord(
        scope=scope,
        name=name,
        latest_version=latest.version,
        description=latest.description,
        license=latest.license,
        realm=latest.realm,
        authors=latest.authors,
        homepage=latest.homepage,
        repository=latest.repository,
        dependency_count=latest.dependency_count,
        server_dependency_count=latest.server_dependency_count,
    )


def _manifest_to_version(manifest: dict, line_order: int) -> PackageVersion | None:
    package = manifest.get("package")
    if not isinstance(package, dict):
        return None
    version_str = package.get("version")
    if not isinstance(version_str, str) or not version_str:
        return None

    authors_raw = package.get("authors") or []
    authors = [a for a in authors_raw if isinstance(a, str)]

    deps = manifest.get("dependencies") or {}
    server_deps = manifest.get("server-dependencies") or {}
    dev_deps = manifest.get("dev-dependencies") or {}

    return PackageVersion(
        version=version_str,
        description=str(package.get("description") or ""),
        license=str(package.get("license") or ""),
        realm=str(package.get("realm") or ""),
        authors=authors,
        homepage=package.get("homepage"),
        repository=package.get("repository"),
        dependency_count=len(deps) if isinstance(deps, dict) else 0,
        server_dependency_count=len(server_deps) if isinstance(server_deps, dict) else 0,
        dev_dependency_count=len(dev_deps) if isinstance(dev_deps, dict) else 0,
        line_order=line_order,
    )


def _parse_version(version_str: str) -> Version | None:
    try:
        return Version(version_str)
    except InvalidVersion:
        return None


def _version_sort_key(version: PackageVersion) -> tuple:
    parsed = _parse_version(version.version)
    if parsed is not None:
        return (1, parsed)
    return (0, version.line_order, version.version)


def _dedupe_versions(versions: list[PackageVersion]) -> list[PackageVersion]:
    by_version: dict[str, PackageVersion] = {}
    for version in versions:
        existing = by_version.get(version.version)
        if existing is None or version.line_order >= existing.line_order:
            by_version[version.version] = version
    return list(by_version.values())


def _pick_latest_version(versions: list[PackageVersion]) -> PackageVersion:
    stable = [v for v in versions if _is_stable(v.version)]
    candidates = stable if stable else versions
    return max(candidates, key=_version_sort_key)


def _is_stable(version_str: str) -> bool:
    parsed = _parse_version(version_str)
    if parsed is None:
        return True
    return not parsed.is_prerelease and not parsed.is_devrelease
