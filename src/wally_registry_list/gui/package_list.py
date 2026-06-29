"""Virtualized scrollable package card list."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from typing import Callable

import customtkinter as ctk

from packaging.version import InvalidVersion, Version

from wally_registry_list.models import PackageRecord

CARD_HEIGHT = 84
CARD_PADY = 5
STRIDE = CARD_HEIGHT + CARD_PADY
VISIBLE_BUFFER = 3
DESCRIPTION_MAX_LEN = 120
RESIZE_DEBOUNCE_MS = 80
WHEEL_PIXELS = 56

BG = "#2b2b2b"
CARD_BG = "#333333"
CARD_BG_HOVER = "#3a3a3a"
CARD_BG_SELECTED = "#1f538d"
CARD_BORDER = "#3b8ed0"
FG = "#ffffff"
FG_DIM = "#b0b0b0"

_FONTS: dict[str, tkfont.Font] | None = None


def _fonts(master: tk.Misc) -> dict[str, tkfont.Font]:
    global _FONTS
    if _FONTS is None:
        _FONTS = {
            "title": tkfont.Font(master, family="Segoe UI", size=11, weight="bold"),
            "meta": tkfont.Font(master, family="Segoe UI", size=9),
            "desc": tkfont.Font(master, family="Segoe UI", size=9),
        }
    return _FONTS

SORT_OPTIONS = {
    "Name": lambda r: (r.name.lower(), r.scope.lower()),
    "Package": lambda r: r.full_name.lower(),
    "Scope": lambda r: (r.scope.lower(), r.name.lower()),
    "Version": lambda r: _version_sort_key(r.latest_version),
    "License": lambda r: r.license.lower(),
    "Realm": lambda r: r.realm.lower(),
}


def _version_sort_key(version: str) -> tuple:
    try:
        return (0, Version(version))
    except InvalidVersion:
        return (1, version.lower())


class _CardWidget(tk.Frame):
    def __init__(self, master: tk.Misc, list_view: PackageCardList) -> None:
        super().__init__(master, bg=CARD_BG, cursor="hand2", height=CARD_HEIGHT)
        self.pack_propagate(False)
        self._list_view = list_view
        self._record: PackageRecord | None = None
        self._display_key: tuple[str, str, bool] | None = None
        self._wraplength = 0
        fonts = _fonts(master)

        self._title = tk.Label(
            self, bg=CARD_BG, fg=FG, anchor="w", font=fonts["title"]
        )
        self._title.pack(anchor="w", padx=12, pady=(8, 0))

        self._meta = tk.Label(
            self, bg=CARD_BG, fg=FG_DIM, anchor="w", font=fonts["meta"]
        )
        self._meta.pack(anchor="w", padx=12, pady=(1, 0))

        self._description = tk.Label(
            self,
            bg=CARD_BG,
            fg=FG,
            anchor="w",
            justify="left",
            font=fonts["desc"],
        )
        self._description.pack(anchor="w", padx=12, pady=(2, 8))

        for widget in (self, self._title, self._meta, self._description):
            widget.bind("<Button-1>", self._handle_click)
            widget.bind("<Enter>", self._handle_enter)
            widget.bind("<Leave>", self._handle_leave)

    def _handle_click(self, _event: tk.Event) -> None:
        self._list_view._on_card_click(self)

    def _handle_enter(self, _event: tk.Event) -> None:
        if self._record is None:
            return
        selected = (
            self._list_view._selected_name is not None
            and self._record.full_name == self._list_view._selected_name
        )
        if not selected:
            self._apply_colors(CARD_BG_HOVER)

    def _handle_leave(self, _event: tk.Event) -> None:
        if self._record is None:
            return
        selected = (
            self._list_view._selected_name is not None
            and self._record.full_name == self._list_view._selected_name
        )
        self._apply_colors(CARD_BG_SELECTED if selected else CARD_BG)

    def _apply_colors(self, bg: str) -> None:
        self.configure(bg=bg)
        for label in (self._title, self._meta, self._description):
            label.configure(bg=bg)

    def set_record(
        self,
        record: PackageRecord,
        selected: bool,
        wraplength: int,
    ) -> None:
        key = (record.full_name, record.latest_version, selected)
        if key == self._display_key and wraplength == self._wraplength:
            return

        self._record = record
        self._display_key = key
        self._wraplength = wraplength

        bg = CARD_BG_SELECTED if selected else CARD_BG
        self.configure(
            bg=bg,
            highlightthickness=2 if selected else 0,
            highlightbackground=CARD_BORDER,
        )
        for label in (self._title, self._meta, self._description):
            label.configure(bg=bg)

        self._title.configure(text=record.full_name)
        self._meta.configure(
            text=(
                f"v{record.latest_version}  ·  {record.license or '—'}"
                f"  ·  {record.realm or '—'}"
            )
        )
        self._description.configure(
            text=_truncate(record.description, DESCRIPTION_MAX_LEN) or "(no description)",
            wraplength=max(120, wraplength - 24),
        )

    def move_to(self, x: int, y: int, width: int) -> None:
        self.place(x=x, y=y, width=width, height=CARD_HEIGHT)

    def hide(self) -> None:
        self.place_forget()
        self._record = None
        self._display_key = None


class PackageCardList(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_select: Callable[[PackageRecord | None], None],
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._records: list[PackageRecord] = []
        self._displayed: list[PackageRecord] = []
        self._sort_key = SORT_OPTIONS["Name"]
        self._sort_reverse = False
        self._selected_name: str | None = None
        self._pool: list[_CardWidget] = []
        self._pool_capacity = 0
        self._resize_after_id: str | None = None
        self._visible_first = -1
        self._canvas_width = 400
        self._canvas_height = 400
        self._total_height = 400
        self._wraplength = 360
        self._pending_filter = ""
        self._wheel_bound = False

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=4, pady=(0, 6))

        ctk.CTkLabel(header, text="Sort by:").pack(side="left", padx=(0, 8))
        self._sort_var = tk.StringVar(value="Name")
        ctk.CTkOptionMenu(
            header,
            variable=self._sort_var,
            values=list(SORT_OPTIONS.keys()),
            command=self._on_sort_changed,
            width=120,
        ).pack(side="left", padx=(0, 8))

        self._sort_dir_btn = ctk.CTkButton(
            header,
            text="A → Z",
            width=70,
            command=self._toggle_sort_direction,
        )
        self._sort_dir_btn.pack(side="left")

        self._shown_label = ctk.CTkLabel(header, text="")
        self._shown_label.pack(side="right")

        self._canvas = tk.Canvas(self, highlightthickness=0, bg=BG, borderwidth=0)
        self._scrollbar = ctk.CTkScrollbar(self, command=self._on_scrollbar)
        self._canvas.configure(yscrollcommand=self._on_yscroll)

        self._inner = tk.Frame(self._canvas, bg=BG)
        self._canvas_window = self._canvas.create_window(
            (0, 0),
            window=self._inner,
            anchor="nw",
        )

        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind("<Enter>", self._bind_mousewheel)
        self._inner.bind("<Enter>", self._bind_mousewheel)
        self._canvas.bind("<Leave>", self._check_unbind_mousewheel)
        self.bind("<Map>", self._on_mapped)

    def _bind_mousewheel(self, _event: tk.Event) -> None:
        if self._wheel_bound:
            return
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self._wheel_bound = True

    def _check_unbind_mousewheel(self, _event: tk.Event) -> None:
        self.after_idle(self._maybe_unbind_mousewheel)

    def _maybe_unbind_mousewheel(self) -> None:
        try:
            x, y = self.winfo_pointerxy()
            widget = self.winfo_containing(x, y)
        except tk.TclError:
            self._unbind_mousewheel()
            return
        if widget is None or not str(widget).startswith(str(self)):
            self._unbind_mousewheel()

    def _unbind_mousewheel(self) -> None:
        if not self._wheel_bound:
            return
        self._canvas.unbind_all("<MouseWheel>")
        self._wheel_bound = False

    def _on_mapped(self, _event: tk.Event) -> None:
        self._read_viewport()
        if self._records:
            self._full_refresh()

    def set_packages(self, records: list[PackageRecord]) -> None:
        self._records = list(records)
        self._pending_filter = ""
        self.after_idle(self._apply_pending)

    def apply_search(self, query: str) -> None:
        self._pending_filter = query
        self.after_idle(self._apply_pending)

    def _apply_pending(self) -> None:
        self._apply_filter(self._pending_filter)

    def _apply_filter(self, query: str) -> None:
        needle = query.strip().lower()
        if needle:
            self._displayed = [
                r
                for r in self._records
                if needle in r.full_name.lower()
                or needle in r.description.lower()
                or needle in r.license.lower()
                or needle in r.scope.lower()
                or needle in r.name.lower()
            ]
        else:
            self._displayed = list(self._records)
        self._selected_name = None
        self._on_select(None)
        self._update_shown_label()
        self._rebuild_display_list()

    def _rebuild_display_list(self) -> None:
        self._displayed = sorted(
            self._displayed,
            key=self._sort_key,
            reverse=self._sort_reverse,
        )
        self._apply_sort_refresh()

    def _apply_sort_refresh(self) -> None:
        """Re-render from the top after sort/filter changes."""
        self._invalidate_pool()
        self._visible_first = -1
        self._canvas.yview_moveto(0)
        self.update_idletasks()
        self._read_viewport()
        self._ensure_pool_capacity()
        self._sync_scroll_area()
        self._render_visible(force_first=0)

    def _invalidate_pool(self) -> None:
        for card in self._pool:
            card._display_key = None

    def _on_sort_changed(self, choice: str) -> None:
        self._sort_key = SORT_OPTIONS[choice]
        self._rebuild_display_list()

    def _toggle_sort_direction(self) -> None:
        self._sort_reverse = not self._sort_reverse
        self._sort_dir_btn.configure(text="Z → A" if self._sort_reverse else "A → Z")
        self._rebuild_display_list()

    def _update_shown_label(self) -> None:
        total = len(self._records)
        shown = len(self._displayed)
        if shown == total:
            self._shown_label.configure(text=f"{shown} shown")
        else:
            self._shown_label.configure(text=f"{shown} of {total}")

    def _on_scrollbar(self, *args: str) -> None:
        self._canvas.yview(*args)
        self._render_visible()

    def _on_yscroll(self, first: str, last: str) -> None:
        self._scrollbar.set(first, last)

    def _on_mousewheel(self, event: tk.Event) -> None:
        direction = -1 if event.delta > 0 else 1
        self._scroll_by_pixels(direction * WHEEL_PIXELS)

    def _scroll_by_pixels(self, pixels: int) -> None:
        total = self._total_height
        view_h = self._canvas_height
        max_scroll = max(total - view_h, 0)
        if max_scroll <= 0:
            return
        top = self._canvas.canvasy(0)
        new_top = max(0, min(max_scroll, top + pixels))
        self._canvas.yview_moveto(new_top / total)
        self._render_visible()

    def _on_canvas_resize(self, event: tk.Event) -> None:
        if event.width < 2 or event.height < 2:
            return
        self._canvas_width = event.width
        self._canvas_height = event.height
        self._wraplength = max(120, event.width - 48)
        self._canvas.itemconfigure(self._canvas_window, width=event.width)
        card_width = max(event.width - 8, 100)
        for card in self._pool:
            if card._record is not None:
                card.place_configure(width=card_width)
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(RESIZE_DEBOUNCE_MS, self._on_resize_debounced)

    def _on_resize_debounced(self) -> None:
        self._resize_after_id = None
        self._visible_first = -1
        self._ensure_pool_capacity()
        self._full_refresh()

    def _read_viewport(self) -> None:
        width = self._canvas.winfo_width()
        height = self._canvas.winfo_height()
        if width > 1:
            self._canvas_width = width
        if height > 1:
            self._canvas_height = height
        self._wraplength = max(120, self._canvas_width - 48)

    def _ensure_pool_capacity(self) -> None:
        needed = self._visible_slot_count()
        if needed <= self._pool_capacity:
            return
        self._pool_capacity = needed
        while len(self._pool) < self._pool_capacity:
            self._pool.append(_CardWidget(self._inner, list_view=self))

    def _visible_slot_count(self) -> int:
        slots = int(self._canvas_height // STRIDE) + (VISIBLE_BUFFER * 2) + 4
        return max(slots, 8)

    def _sync_scroll_area(self) -> None:
        count = len(self._displayed)
        total_height = max(count * STRIDE, self._canvas_height)
        inner_w = self._canvas_width
        if total_height != self._total_height or inner_w < 2:
            self._total_height = total_height
            self._inner.configure(width=inner_w, height=total_height)
            self._canvas.itemconfigure(
                self._canvas_window,
                width=inner_w,
                height=total_height,
            )
            self._canvas.configure(scrollregion=(0, 0, inner_w, total_height))

    def _full_refresh(self) -> None:
        self._read_viewport()
        self._ensure_pool_capacity()
        self._sync_scroll_area()
        self._render_visible()

    def _render_visible(self, *, force_first: int | None = None) -> None:
        count = len(self._displayed)
        if count == 0:
            for card in self._pool:
                card.hide()
            self._visible_first = -1
            return

        if force_first is not None:
            first = force_first
        else:
            scroll_top = self._canvas.canvasy(0)
            first = max(0, int(scroll_top // STRIDE) - VISIBLE_BUFFER)

        slots = self._visible_slot_count()
        last = min(count, first + slots)

        if first == self._visible_first and force_first is None:
            return

        self._visible_first = first
        selected = self._selected_name
        card_width = max(self._canvas_width - 8, 100)

        for slot in range(self._pool_capacity):
            index = first + slot
            if index < last:
                record = self._displayed[index]
                card = self._pool[slot]
                card.set_record(record, record.full_name == selected, self._wraplength)
                card.move_to(4, index * STRIDE, card_width)
            elif slot < len(self._pool):
                self._pool[slot].hide()

    def _on_card_click(self, card: _CardWidget) -> None:
        if card._record is None:
            return
        previous = self._selected_name
        self._selected_name = card._record.full_name
        self._on_select(card._record)
        for pool_card in self._pool:
            if pool_card._record is None:
                continue
            name = pool_card._record.full_name
            if name == previous or name == self._selected_name:
                pool_card._display_key = None
                pool_card.set_record(
                    pool_card._record,
                    name == self._selected_name,
                    self._wraplength,
                )


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
