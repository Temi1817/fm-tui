from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView, Static

from .operations import extract_archive, format_size, get_file_info, is_archive, open_path

ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz", ".tar.gz"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp", ".tiff"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".opus", ".wma"}
TEXT_EXTS = {
    ".txt", ".md", ".rst", ".log", ".csv", ".json", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".conf", ".py", ".js", ".ts", ".html", ".css", ".sh",
    ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd", ".c", ".cpp", ".h",
    ".rs", ".go", ".java", ".rb", ".php", ".xml", ".sql", ".r", ".lua",
}

ICONS_NERD = {
    "dir": " ",
    "archive": " ",
    "image": " ",
    "video": " ",
    "audio": " ",
    "text": " ",
    "exec": " ",
    "link": " ",
    "default": " ",
}


@dataclass
class FileEntry:
    path: Path
    name: str
    is_dir: bool
    size: int
    modified: float
    selected: bool = field(default=False, compare=False)

    def color(self) -> str:
        if self.name.startswith("."):
            return "dim"
        if self.is_dir:
            return "bold blue"
        if self.path.is_symlink():
            return "bold cyan"
        if os.access(self.path, os.X_OK):
            return "bold green"
        ext = self.path.suffix.lower()
        if ext in ARCHIVE_EXTS:
            return "bold red"
        if ext in IMAGE_EXTS:
            return "bold magenta"
        if ext in VIDEO_EXTS:
            return "bold cyan"
        if ext in AUDIO_EXTS:
            return "bold yellow"
        if ext in TEXT_EXTS:
            return "white"
        return "white"

    def icon(self, use_icons: bool) -> str:
        if not use_icons:
            return ""
        if self.is_dir:
            return ICONS_NERD["dir"]
        ext = self.path.suffix.lower()
        if ext in ARCHIVE_EXTS:
            return ICONS_NERD["archive"]
        if ext in IMAGE_EXTS:
            return ICONS_NERD["image"]
        if ext in VIDEO_EXTS:
            return ICONS_NERD["video"]
        if ext in AUDIO_EXTS:
            return ICONS_NERD["audio"]
        if ext in TEXT_EXTS:
            return ICONS_NERD["text"]
        if self.path.is_symlink():
            return ICONS_NERD["link"]
        if os.access(self.path, os.X_OK):
            return ICONS_NERD["exec"]
        return ICONS_NERD["default"]


class FilePanel(Widget):
    class CursorMoved(Message):
        def __init__(self, panel: "FilePanel", entry: Optional[FileEntry]) -> None:
            super().__init__()
            self.panel = panel
            self.entry = entry

    class DirChanged(Message):
        def __init__(self, panel: "FilePanel", path: Path) -> None:
            super().__init__()
            self.panel = panel
            self.path = path

    class Focused(Message):
        def __init__(self, panel: "FilePanel") -> None:
            super().__init__()
            self.panel = panel

    show_hidden: reactive[bool] = reactive(False)

    def __init__(self, start_path: Path, show_hidden: bool = False,
                 icons: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_path = start_path
        self.show_hidden = show_hidden
        self.icons = icons
        self._entries: list[FileEntry] = []
        self._visible: list[FileEntry] = []
        self._selected: set[Path] = set()
        self._sort_by = "name"
        self._sort_rev = False
        self._search = ""
        self._cursor = 0
        self._archive_origin: Optional[Path] = None   # dir to return to after exiting archive
        self._archive_tmp: Optional[Path] = None      # temp extraction dir

    def compose(self) -> ComposeResult:
        yield Static("", id="crumb", classes="panel-crumb")
        yield ListView(id="flist")
        yield Static("", id="pstatus", classes="panel-status")

    def on_mount(self) -> None:
        self._reload()

    def on_descendant_focus(self) -> None:
        self.post_message(self.Focused(self))

    def _reload(self) -> None:
        entries: list[FileEntry] = []
        try:
            for item in self.current_path.iterdir():
                try:
                    st = item.stat()
                    entries.append(FileEntry(
                        path=item, name=item.name,
                        is_dir=item.is_dir(),
                        size=st.st_size, modified=st.st_mtime,
                    ))
                except (OSError, PermissionError):
                    entries.append(FileEntry(
                        path=item, name=item.name,
                        is_dir=item.is_dir(), size=0, modified=0,
                    ))
        except (OSError, PermissionError):
            pass
        self._entries = entries
        self._apply_filter_and_sort()
        self._redraw()

    def _apply_filter_and_sort(self) -> None:
        filtered = self._entries
        if not self.show_hidden:
            filtered = [e for e in filtered if not e.name.startswith(".")]
        if self._search:
            q = self._search.lower()
            filtered = [e for e in filtered if q in e.name.lower()]
        key_map = {
            "name": lambda e: e.name.lower(),
            "size": lambda e: e.size,
            "date": lambda e: e.modified,
        }
        key_fn = key_map.get(self._sort_by, key_map["name"])
        dirs = sorted([e for e in filtered if e.is_dir], key=key_fn, reverse=self._sort_rev)
        files = sorted([e for e in filtered if not e.is_dir], key=key_fn, reverse=self._sort_rev)
        self._visible = dirs + files

    def _redraw(self) -> None:
        lv = self.query_one("#flist", ListView)
        lv.clear()
        for entry in self._visible:
            t = Text()
            mark = "● " if entry.path in self._selected else "  "
            t.append(mark, style="bold yellow" if entry.path in self._selected else "dim")
            t.append(entry.icon(self.icons))
            name = entry.name + "/" if entry.is_dir else entry.name
            t.append(name, style=entry.color())
            if not entry.is_dir:
                t.append(f"  {format_size(entry.size)}", style="dim")
            lv.append(ListItem(Label(t)))
        self._update_crumb()
        self._update_status()
        # Restore cursor position
        if self._visible:
            lv.index = min(self._cursor, len(self._visible) - 1)

    def _update_crumb(self) -> None:
        if self._archive_origin is not None and self._archive_tmp is not None:
            try:
                rel = self.current_path.relative_to(self._archive_tmp)
                inner = str(rel) if str(rel) != "." else ""
                arc_name = next(
                    (p for p in self._archive_origin.iterdir()
                     if self._archive_tmp.name.startswith("fm_") and p.is_file() and is_archive(p)),
                    None,
                )
            except Exception:
                inner = ""
            # show archive label in crumb
            label = f"[архив] {inner}" if inner else "[архив]"
            self.query_one("#crumb", Static).update(f" {label}")
            return
        parts = self.current_path.parts
        text = " › ".join(parts[-3:]) if len(parts) > 3 else str(self.current_path)
        self.query_one("#crumb", Static).update(f" {text}")

    def _update_status(self) -> None:
        total = len(self._visible)
        sel = len(self._selected)
        sort_label = f"{self._sort_by}{'↓' if self._sort_rev else '↑'}"
        msg = f" {sel} sel / {total}  [{sort_label}]" if sel else f" {total} items  [{sort_label}]"
        self.query_one("#pstatus", Static).update(msg)

    def navigate_to(self, path: Path) -> None:
        self.current_path = path
        self._selected.clear()
        self._cursor = 0
        self._search = ""
        self._reload()
        self.post_message(self.DirChanged(self, path))

    def go_up(self) -> None:
        # Exit archive view back to the directory that contained the archive
        if self._archive_origin is not None:
            if self.current_path != self._archive_tmp:
                # Still inside archive subdirectory — go up within archive
                parent = self.current_path.parent
                self.navigate_to(parent)
                return
            self._exit_archive()
            return
        parent = self.current_path.parent
        if parent == self.current_path:
            return
        old = self.current_path
        self.navigate_to(parent)
        for i, e in enumerate(self._visible):
            if e.path == old:
                self._cursor = i
                lv = self.query_one("#flist", ListView)
                lv.index = i
                break

    def enter_archive(self, archive_path: Path) -> None:
        import tempfile, shutil as _sh
        tmp = Path(tempfile.mkdtemp(prefix="fm_arch_"))
        try:
            extract_archive(archive_path, tmp)
        except Exception as exc:
            _sh.rmtree(tmp, ignore_errors=True)
            self.app.notify(f"Ошибка распаковки: {exc}", severity="error")
            return
        self._archive_origin = archive_path.parent
        self._archive_tmp = tmp
        self.navigate_to(tmp)

    def _exit_archive(self) -> None:
        import shutil as _sh
        origin = self._archive_origin or Path.home()
        tmp = self._archive_tmp
        self._archive_origin = None
        self._archive_tmp = None
        self.navigate_to(origin)
        if tmp:
            _sh.rmtree(tmp, ignore_errors=True)

    def current_entry(self) -> Optional[FileEntry]:
        lv = self.query_one("#flist", ListView)
        idx = lv.index if lv.index is not None else self._cursor
        if 0 <= idx < len(self._visible):
            return self._visible[idx]
        return None

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        lv = self.query_one("#flist", ListView)
        if lv.index is not None:
            self._cursor = lv.index
        self.post_message(self.CursorMoved(self, self.current_entry()))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        entry = self.current_entry()
        if entry is None:
            return
        if entry.is_dir:
            self.navigate_to(entry.path)
        elif is_archive(entry.path):
            self.enter_archive(entry.path)
        else:
            open_path(entry.path)

    def toggle_select(self) -> None:
        entry = self.current_entry()
        if entry is None:
            return
        if entry.path in self._selected:
            self._selected.discard(entry.path)
        else:
            self._selected.add(entry.path)
        saved = self._cursor
        self._redraw()
        lv = self.query_one("#flist", ListView)
        lv.index = saved

    def select_all(self) -> None:
        if len(self._selected) == len(self._visible):
            self._selected.clear()
        else:
            self._selected = {e.path for e in self._visible}
        saved = self._cursor
        self._redraw()
        lv = self.query_one("#flist", ListView)
        lv.index = saved

    def set_search(self, query: str) -> None:
        self._search = query
        self._cursor = 0
        self._apply_filter_and_sort()
        self._redraw()

    def cycle_sort(self) -> str:
        order = ["name", "size", "date"]
        idx = order.index(self._sort_by) if self._sort_by in order else 0
        self._sort_by = order[(idx + 1) % len(order)]
        self._apply_filter_and_sort()
        self._redraw()
        return self._sort_by

    def toggle_hidden(self) -> None:
        self.show_hidden = not self.show_hidden
        self._apply_filter_and_sort()
        self._redraw()

    def reload(self) -> None:
        cur = self.current_entry()
        self._reload()
        if cur:
            for i, e in enumerate(self._visible):
                if e.path == cur.path:
                    self._cursor = i
                    lv = self.query_one("#flist", ListView)
                    lv.index = i
                    break

    def focus_list(self) -> None:
        self.query_one("#flist", ListView).focus()

    def selected_paths(self) -> list[Path]:
        if self._selected:
            return list(self._selected)
        e = self.current_entry()
        return [e.path] if e else []

    def show_search_results(self, paths: list[Path], root: Optional[Path] = None) -> None:
        """Display a flat list of search results (overrides normal directory view)."""
        entries: list[FileEntry] = []
        for path in paths:
            try:
                st = path.stat()
                display = str(path.relative_to(root)) if root else path.name
                entries.append(FileEntry(
                    path=path, name=display,
                    is_dir=path.is_dir(),
                    size=st.st_size, modified=st.st_mtime,
                ))
            except (OSError, PermissionError):
                entries.append(FileEntry(
                    path=path, name=path.name,
                    is_dir=path.is_dir(), size=0, modified=0,
                ))
        self._visible = entries
        self._selected.clear()
        self._cursor = 0
        self._redraw()
        self.query_one("#crumb", Static).update(
            f" [Результаты поиска: {len(entries)} файлов]"
        )
