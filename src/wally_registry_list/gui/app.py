"""Main application window."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from datetime import datetime

import customtkinter as ctk

from wally_registry_list.cache import PackageCache
from wally_registry_list.config import CACHE_TTL_SECONDS
from wally_registry_list.gui.detail_panel import DetailPanel
from wally_registry_list.gui.package_list import PackageCardList
from wally_registry_list.index_fetcher import download_index_archive, index_is_fresh
from wally_registry_list.index_parser import parse_index
from wally_registry_list.models import PackageRecord

logger = logging.getLogger(__name__)


class WallyRegistryApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Wally Registry List")
        self.geometry("1200x700")
        self.minsize(900, 500)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._cache = PackageCache()
        self._packages: list[PackageRecord] = []
        self._loading = False
        self._search_after_id: str | None = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.after(0, self._load_from_cache)
        if not self._cache.has_packages() or not index_is_fresh(CACHE_TTL_SECONDS):
            self._refresh_index_async(force=not self._cache.has_packages())
        else:
            self.after(0, lambda: self._set_status("Index cache is up to date."))

    def _build_ui(self) -> None:
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(toolbar, text="Search:").pack(side="left", padx=(0, 8))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        search_entry = ctk.CTkEntry(toolbar, textvariable=self._search_var, width=280)
        search_entry.pack(side="left", padx=(0, 12))

        self._refresh_btn = ctk.CTkButton(
            toolbar,
            text="Refresh Index",
            command=lambda: self._refresh_index_async(force=True),
            width=130,
        )
        self._refresh_btn.pack(side="left", padx=(0, 12))

        self._count_label = ctk.CTkLabel(toolbar, text="0 packages")
        self._count_label.pack(side="left", padx=(0, 12))

        self._sync_label = ctk.CTkLabel(toolbar, text="")
        self._sync_label.pack(side="left")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=6)
        content.grid_columnconfigure(0, weight=7)
        content.grid_columnconfigure(1, weight=3)
        content.grid_rowconfigure(0, weight=1)

        self._list = PackageCardList(content, on_select=self._on_package_selected)
        self._list.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self._detail = DetailPanel(content)
        self._detail.grid(row=0, column=1, sticky="nsew")

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill="x", padx=12, pady=(0, 12))

        self._status_label = ctk.CTkLabel(status_frame, text="Ready", anchor="w")
        self._status_label.pack(side="left", fill="x", expand=True)

        self._progress = ctk.CTkProgressBar(status_frame, mode="indeterminate", width=180)
        self._progress.pack(side="right")
        self._progress.stop()
        self._progress.pack_forget()

    def _load_from_cache(self) -> None:
        if not self._cache.has_packages():
            self._set_status("No cached data. Downloading index...")
            return
        self._packages = self._cache.load_all()
        self._list.set_packages(self._packages)
        self._update_counts()
        last_sync = self._cache.get_last_sync()
        if last_sync:
            self._sync_label.configure(
                text=f"Last sync: {_format_timestamp(last_sync)}"
            )
        self._set_status(f"Loaded {len(self._packages)} packages from cache.")

    def _update_counts(self) -> None:
        self._count_label.configure(text=f"{len(self._packages)} packages")

    def _on_search_changed(self, *_args) -> None:
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(150, self._apply_search)

    def _apply_search(self) -> None:
        self._search_after_id = None
        self._list.apply_search(self._search_var.get())

    def _on_package_selected(self, record: PackageRecord | None) -> None:
        self._detail.show_package(record)

    def _refresh_index_async(self, force: bool) -> None:
        if self._loading:
            return
        if not force and index_is_fresh(CACHE_TTL_SECONDS) and self._cache.has_packages():
            return
        self._loading = True
        self._refresh_btn.configure(state="disabled")
        self._show_progress(True)
        self._set_status("Refreshing index from GitHub...")

        def worker() -> None:
            error: str | None = None
            packages: list[PackageRecord] = []
            status_messages: list[str] = []

            def on_progress(message: str) -> None:
                status_messages.append(message)

            try:
                root = download_index_archive(on_progress=on_progress)
                on_progress("Parsing package metadata...")
                packages = parse_index(root)
            except Exception as exc:
                logger.exception("Index refresh failed")
                error = str(exc)

            final_status = status_messages[-1] if status_messages else ""
            self.after(
                0,
                lambda: self._on_refresh_complete(packages, error, final_status),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _on_refresh_complete(
        self,
        packages: list[PackageRecord],
        error: str | None,
        progress_message: str,
    ) -> None:
        self._loading = False
        self._refresh_btn.configure(state="normal")
        self._show_progress(False)

        if packages:
            try:
                self._cache.replace_all(packages)
            except Exception as exc:
                logger.exception("Failed to save package cache")
                if error is None:
                    error = f"Loaded packages but cache save failed: {exc}"
            self._packages = packages
            self._list.set_packages(self._packages)
            self._list.apply_search(self._search_var.get())
            self._update_counts()
            last_sync = self._cache.get_last_sync()
            if last_sync:
                self._sync_label.configure(
                    text=f"Last sync: {_format_timestamp(last_sync)}"
                )
            self._set_status(f"Loaded {len(packages)} packages. {progress_message}")
        elif error:
            if self._packages:
                self._set_status(
                    f"Refresh failed ({error}). Showing cached data."
                )
            else:
                self._set_status(f"Failed to load index: {error}")

    def _set_status(self, message: str) -> None:
        self._status_label.configure(text=message)

    def _show_progress(self, visible: bool) -> None:
        if visible:
            self._progress.pack(side="right")
            self._progress.start()
        else:
            self._progress.stop()
            self._progress.pack_forget()

    def _on_close(self) -> None:
        self._cache.close()
        self.destroy()


def _format_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
