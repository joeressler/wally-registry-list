"""Detail panel for a selected package (latest version only)."""

from __future__ import annotations

import webbrowser

import customtkinter as ctk

from wally_registry_list.models import PackageRecord
from wally_registry_list.urls import (
    dependency_spec,
    index_file_url,
    package_page_url,
)


class DetailPanel(ctk.CTkScrollableFrame):
    def __init__(self, master: ctk.CTkBaseClass, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._record: PackageRecord | None = None

        self._title = ctk.CTkLabel(
            self, text="Select a package", font=ctk.CTkFont(size=18, weight="bold")
        )
        self._title.pack(anchor="w", padx=8, pady=(8, 4))

        self._meta = ctk.CTkLabel(self, text="", justify="left", anchor="w")
        self._meta.pack(anchor="w", padx=8, pady=4)

        self._description = ctk.CTkTextbox(self, height=140, wrap="word")
        self._description.pack(fill="x", padx=8, pady=4)
        self._description.configure(state="disabled")

        link_row = ctk.CTkFrame(self, fg_color="transparent")
        link_row.pack(fill="x", padx=8, pady=4)

        self._homepage_btn = ctk.CTkButton(
            link_row,
            text="Homepage",
            command=self._open_homepage,
            width=110,
        )
        self._homepage_btn.pack(side="left", padx=(0, 8))

        self._repo_btn = ctk.CTkButton(
            link_row,
            text="Repository",
            command=self._open_repository,
            width=110,
        )
        self._repo_btn.pack(side="left")

        button_row = ctk.CTkFrame(self, fg_color="transparent")
        button_row.pack(fill="x", padx=8, pady=8)

        self._open_btn = ctk.CTkButton(
            button_row,
            text="Open on wally.run",
            command=self._open_wally_page,
            width=160,
        )
        self._open_btn.pack(side="left", padx=(0, 8))

        self._copy_btn = ctk.CTkButton(
            button_row,
            text="Copy dependency",
            command=self._copy_dependency,
            width=160,
        )
        self._copy_btn.pack(side="left", padx=(0, 8))

        self._index_btn = ctk.CTkButton(
            button_row,
            text="View index file",
            command=self._open_index_file,
            width=140,
        )
        self._index_btn.pack(side="left")

        self._set_empty()

    def show_package(self, record: PackageRecord | None) -> None:
        self._record = record
        if record is None:
            self._set_empty()
            return

        self._title.configure(text=record.full_name)
        deps = record.dependency_count + record.server_dependency_count
        self._meta.configure(
            text=(
                f"Version: {record.latest_version}\n"
                f"License: {record.license or '—'}\n"
                f"Realm: {record.realm or '—'}\n"
                f"Authors: {', '.join(record.authors) if record.authors else '—'}\n"
                f"Dependencies: {deps}"
            )
        )

        self._description.configure(state="normal")
        self._description.delete("1.0", "end")
        self._description.insert("1.0", record.description or "(no description)")
        self._description.configure(state="disabled")

        self._homepage_btn.configure(state="normal" if record.homepage else "disabled")
        self._repo_btn.configure(state="normal" if record.repository else "disabled")
        self._open_btn.configure(state="normal")
        self._copy_btn.configure(state="normal")
        self._index_btn.configure(state="normal")

    def _set_empty(self) -> None:
        self._title.configure(text="Select a package")
        self._meta.configure(text="")
        self._description.configure(state="normal")
        self._description.delete("1.0", "end")
        self._description.configure(state="disabled")
        for btn in (
            self._homepage_btn,
            self._repo_btn,
            self._open_btn,
            self._copy_btn,
            self._index_btn,
        ):
            btn.configure(state="disabled")

    def _open_wally_page(self) -> None:
        if self._record is None:
            return
        webbrowser.open(
            package_page_url(
                self._record.scope,
                self._record.name,
                self._record.latest_version,
            )
        )

    def _copy_dependency(self) -> None:
        if self._record is None:
            return
        self._copy_to_clipboard(
            dependency_spec(
                self._record.scope,
                self._record.name,
                self._record.latest_version,
            )
        )

    def _open_homepage(self) -> None:
        if self._record is None or not self._record.homepage:
            return
        webbrowser.open(self._record.homepage)

    def _open_repository(self) -> None:
        if self._record is None or not self._record.repository:
            return
        webbrowser.open(self._record.repository)

    def _open_index_file(self) -> None:
        if self._record is None:
            return
        webbrowser.open(index_file_url(self._record.scope, self._record.name))

    def _copy_to_clipboard(self, text: str) -> None:
        root = self.winfo_toplevel()
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update_idletasks()
