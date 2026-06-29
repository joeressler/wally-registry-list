"""Data models for Wally packages."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PackageVersion:
    version: str
    description: str
    license: str
    realm: str
    authors: list[str] = field(default_factory=list)
    homepage: str | None = None
    repository: str | None = None
    dependency_count: int = 0
    server_dependency_count: int = 0
    dev_dependency_count: int = 0
    line_order: int = 0


@dataclass
class PackageRecord:
    scope: str
    name: str
    latest_version: str
    description: str
    license: str
    realm: str
    authors: list[str] = field(default_factory=list)
    homepage: str | None = None
    repository: str | None = None
    dependency_count: int = 0
    server_dependency_count: int = 0

    @property
    def full_name(self) -> str:
        return f"{self.scope}/{self.name}"
