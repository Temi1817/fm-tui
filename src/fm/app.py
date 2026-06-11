from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Footer, Input, Static

from .config import add_bookmark, load_config, save_config
from .modals import BookmarkModal, BulkRenameModal, CommandModal, ConfirmModal, HelpModal, InputModal, OutputModal
from .operations import (
    copy_path, delete_path, get_disk_usage, get_file_info,
    create_zip, duplicate_path, is_archive, make_dir, move_path,
    open_editor, open_terminal, rename_path,
)
from .panels import FilePanel
from .preview import PreviewPanel


class _SearchBar(Container):
    """Inline search bar docked to bottom. Auto-focuses Input on mount."""
    DEFAULT_CSS = """
    _SearchBar {
        dock: bottom; height: 1;
        background: #313244; layout: horizontal; padding: 0 1;
    }
    _SearchBar Static { width: 8; color: #a6e3a1; }
    _SearchBar Input {
        height: 1; border: none; padding: 0;
        background: #313244; color: #cdd6f4; width: 1fr;
    }
    """

    def __init__(self, prefix: str, placeholder: str, **kw) -> None:
        super().__init__(id="search-bar", **kw)
        self._prefix = prefix
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield Static(self._prefix)
        yield Input(placeholder=self._placeholder, id="search-input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    async def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            await self.app._close_all_search()


class FileManagerApp(App):
    TITLE = "fm — файловый менеджер"

    DEFAULT_CSS = """
    Screen { background: #1e1e2e; }

    #status-bar {
        height: 1; dock: top;
        background: #313244; color: #cdd6f4; padding: 0 1;
    }
    #main-layout { height: 1fr; }

    FilePanel { width: 1fr; border: solid #45475a; background: #1e1e2e; }
    FilePanel.active { border: solid #89b4fa; }

    .panel-crumb { height: 1; background: #313244; color: #89b4fa; padding: 0 1; }
    .panel-status { height: 1; background: #313244; color: #a6adc8; padding: 0 1; }

    ListView { height: 1fr; background: #1e1e2e; }
    ListItem { background: #1e1e2e; }
    ListItem.--highlight { background: #313244; }
    ListItem:focus { background: #45475a; }

    PreviewPanel { width: 1fr; border: solid #45475a; background: #181825; }
    #preview-title { height: 1; background: #313244; color: #cba6f7; padding: 0 1; }
    #preview-meta { height: 5; background: #181825; padding: 0 1; border-bottom: solid #45475a; }
    #preview-content { height: 1fr; background: #181825; padding: 0 1; overflow: auto auto; }

    Footer { background: #313244; }
    """

    BINDINGS = [
        Binding("tab",              "switch_panel",   "Панели",    show=True),
        Binding("backspace",        "go_up",          "Выше",      show=False),
        Binding("f2",               "rename",         "Переим.",   show=True),
        Binding("f3",               "view_file",      "Просм.",    show=True),
        Binding("f4",               "edit_file",      "Ред.",      show=True),
        Binding("f5",               "copy_files",     "Копир.",    show=True),
        Binding("f6",               "move_files",     "Перем.",    show=True),
        Binding("f7",               "mkdir",          "МкДир",     show=True),
        Binding("f8",               "delete_files",   "Удал.",     show=True),
        Binding("delete",           "delete_files",   "Удал.",     show=False),
        Binding("space",            "toggle_select",  "Выдел.",    show=False),
        Binding("ctrl+a",           "select_all",     "Вдл.всё",  show=False),
        Binding("ctrl+d",           "duplicate",      "Дублир.",   show=False),
        Binding("ctrl+r",           "bulk_rename",    "МассРен.",  show=False),
        Binding("ctrl+z",           "zip_selection",  "В архив",   show=False),
        Binding("ctrl+e",           "extract_here",   "Извлечь",   show=False),
        Binding("period",           "toggle_hidden",  "Скрытые",   show=False),
        Binding("s",                "cycle_sort",     "Сорт.",     show=False),
        Binding("slash",            "start_search",   "Поиск",     show=False),
        Binding("ctrl+f",           "global_search",  "Найти",     show=True),
        Binding("colon",            "command_mode",   ":Команда",  show=True),
        Binding("b",                "add_bookmark",   "Закл.",     show=False),
        Binding("apostrophe",       "open_bookmarks", "Закладки",  show=False),
        Binding("exclamation_mark", "open_terminal",  "Терминал",  show=False),
        Binding("question_mark",    "show_help",      "Справка",   show=True),
        Binding("alt+left",         "history_back",   "Назад",     show=False),
        Binding("alt+right",        "history_fwd",    "Вперёд",   show=False),
        Binding("q",                "quit",           "Выход",     show=True),
    ]

    def __init__(self, start_path: Path, icons: bool = False) -> None:
        super().__init__()
        self.start_path = start_path
        self.icons = icons
        self.config = load_config()
        self._active: str = "left"
        self._history: dict[str, list[Path]] = {"left": [], "right": []}
        self._hist_idx: dict[str, int] = {"left": -1, "right": -1}
        self._searching = False
        self._global_search_root: Optional[Path] = None

    def compose(self) -> ComposeResult:
        yield Static("", id="status-bar")
        with Horizontal(id="main-layout"):
            yield FilePanel(
                start_path=self.start_path,
                show_hidden=self.config.get("show_hidden", False),
                icons=self.icons,
                id="panel-left", classes="active",
            )
            yield FilePanel(
                start_path=Path.home(),
                show_hidden=self.config.get("show_hidden", False),
                icons=self.icons,
                id="panel-right",
            )
            yield PreviewPanel(id="preview")
        yield Footer()

    def on_mount(self) -> None:
        self._panel("left").focus_list()
        self._update_status()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _panel(self, side: str) -> FilePanel:
        return self.query_one(f"#panel-{side}", FilePanel)

    def _active_panel(self) -> FilePanel:
        return self._panel(self._active)

    def _other_panel(self) -> FilePanel:
        return self._panel("right" if self._active == "left" else "left")

    def _update_status(self) -> None:
        panel = self._active_panel()
        entry = panel.current_entry()
        bar = self.query_one("#status-bar", Static)
        disk = get_disk_usage(panel.current_path)
        if entry:
            info = get_file_info(entry.path)
            bar.update(f" {info['size_fmt']}  {info['permissions']}  {info['modified']}  │  {disk}")
        else:
            bar.update(f"  {disk}")

    def _push_history(self, path: Path) -> None:
        hist = self._history[self._active]
        idx = self._hist_idx[self._active]
        hist = hist[: idx + 1]
        hist.append(path)
        self._history[self._active] = hist
        self._hist_idx[self._active] = len(hist) - 1

    # ── message handlers ─────────────────────────────────────────────────────

    def on_file_panel_cursor_moved(self, e: FilePanel.CursorMoved) -> None:
        if e.panel is self._active_panel():
            self.query_one("#preview", PreviewPanel).update(
                e.entry.path if e.entry else None
            )
            self._update_status()

    def on_file_panel_dir_changed(self, e: FilePanel.DirChanged) -> None:
        if e.panel is self._active_panel():
            self._push_history(e.path)
            self._update_status()

    def on_file_panel_focused(self, e: FilePanel.Focused) -> None:
        new_active = "left" if e.panel is self._panel("left") else "right"
        if new_active == self._active:
            return
        self._active = new_active
        lp, rp = self._panel("left"), self._panel("right")
        if self._active == "left":
            lp.add_class("active"); rp.remove_class("active")
        else:
            rp.add_class("active"); lp.remove_class("active")
        entry = self._active_panel().current_entry()
        self.query_one("#preview", PreviewPanel).update(entry.path if entry else None)
        self._update_status()

    # ── search helpers ────────────────────────────────────────────────────────

    async def _open_search(self, prefix: str, placeholder: str, global_root: Optional[Path]) -> None:
        """Await-remove old bar, then mount new one and focus."""
        self._searching = True
        self._global_search_root = global_root
        try:
            await self.query_one("#search-bar").remove()
        except Exception:
            pass
        await self.mount(_SearchBar(prefix, placeholder))

    async def action_start_search(self) -> None:
        if self._searching:
            return
        await self._open_search("/  ", "поиск в папке…", global_root=None)

    async def action_global_search(self) -> None:
        root = self._active_panel().current_path
        await self._open_search("Ctrl+F  ", "имя файла (все подпапки)…", global_root=root)

    # single on_input_changed — routes by _global_search_root
    def on_input_changed(self, e: Input.Changed) -> None:
        if e.input.id != "search-input":
            return
        value = e.value
        if self._global_search_root is not None:
            if value.strip():
                self._run_global_search(self._global_search_root, value)
        else:
            self._active_panel().set_search(value)

    async def on_input_submitted(self, e: Input.Submitted) -> None:
        if e.input.id != "search-input":
            return
        await self._close_all_search()

    async def _close_all_search(self) -> None:
        if not self._searching:
            return
        self._searching = False
        root = self._global_search_root
        self._global_search_root = None
        try:
            await self.query_one("#search-bar").remove()
        except Exception:
            pass
        if root is not None:
            self._active_panel().navigate_to(root)
        else:
            self._active_panel().set_search("")
        self._active_panel().focus_list()

    @work(thread=True, exclusive=True)
    def _run_global_search(self, root: Path, query: str) -> None:
        import os as _os
        results: list[Path] = []
        q = query.lower()
        limit = 1000

        _SKIP = {"__pycache__", ".git", ".svn", "node_modules", ".venv", "venv", ".tox"}

        # os.walk skips inaccessible dirs via onerror instead of crashing
        for dirpath, dirnames, filenames in _os.walk(
            str(root), followlinks=False, onerror=lambda _: None
        ):
            dp = Path(dirpath)
            # prune dirs we never want to descend into or show
            dirnames[:] = [
                d for d in dirnames
                if d not in _SKIP
                and (self.config.get("show_hidden", False) or not d.startswith("."))
            ]

            for name in dirnames + filenames:
                if q in name.lower():
                    results.append(dp / name)
                    if len(results) >= limit:
                        self.call_from_thread(
                            self._apply_global_results, results, root, query, True
                        )
                        return

        self.call_from_thread(self._apply_global_results, results, root, query, False)

    def _apply_global_results(
        self, results: list[Path], root: Path, query: str, truncated: bool
    ) -> None:
        self._active_panel().show_search_results(results, root)
        suffix = " (показаны первые 1000)" if truncated else ""
        self.notify(f"Найдено: {len(results)} файлов по '{query}'{suffix}")

    # ── panel actions ─────────────────────────────────────────────────────────

    def action_switch_panel(self) -> None:
        self._active = "right" if self._active == "left" else "left"
        lp, rp = self._panel("left"), self._panel("right")
        if self._active == "left":
            lp.add_class("active"); rp.remove_class("active"); lp.focus_list()
        else:
            rp.add_class("active"); lp.remove_class("active"); rp.focus_list()
        entry = self._active_panel().current_entry()
        self.query_one("#preview", PreviewPanel).update(entry.path if entry else None)
        self._update_status()

    async def action_go_up(self) -> None:
        if self._searching:
            await self._close_all_search()
            return
        self._active_panel().go_up()

    def action_toggle_select(self) -> None:
        self._active_panel().toggle_select()

    def action_select_all(self) -> None:
        self._active_panel().select_all()

    def action_duplicate(self) -> None:
        paths = self._active_panel().selected_paths()
        if not paths:
            return
        errs: list[str] = []
        for p in paths:
            try:
                duplicate_path(p)
            except Exception as exc:
                errs.append(str(exc))
        self._active_panel().reload()
        if errs:
            self.notify(f"Ошибка: {errs[0]}", severity="error")
        else:
            self.notify(f"Дублировано: {len(paths)}")

    def action_bulk_rename(self) -> None:
        paths = self._active_panel().selected_paths()
        if len(paths) < 2:
            self.notify("Выделите 2+ файла (Space) для массового переименования", severity="warning")
            return

        def _apply(pairs: list | None) -> None:
            if not pairs:
                return
            errs: list[str] = []
            for p, new_name in pairs:
                try:
                    rename_path(p, new_name)
                except Exception as exc:
                    errs.append(str(exc))
            self._active_panel().reload()
            if errs:
                self.notify(f"Ошибка: {errs[0]}", severity="error")
            else:
                self.notify(f"Переименовано: {len(pairs)}")

        self.push_screen(BulkRenameModal(paths), _apply)

    def action_zip_selection(self) -> None:
        paths = self._active_panel().selected_paths()
        if not paths:
            return
        default = (paths[0].name if len(paths) == 1 else "archive") + ".zip"

        def _create(name: str | None) -> None:
            if not name:
                return
            name = name.strip()
            if not name.endswith(".zip"):
                name += ".zip"
            dst = self._active_panel().current_path / name
            try:
                create_zip(paths, dst)
                self._active_panel().reload()
                self.notify(f"Создан архив: {name}")
            except Exception as exc:
                self.notify(f"Ошибка архивации: {exc}", severity="error")

        self.push_screen(
            __import__("fm.modals", fromlist=["InputModal"]).InputModal(
                "Имя архива", default
            ),
            _create,
        )

    def action_extract_here(self) -> None:
        entry = self._active_panel().current_entry()
        if not entry or not is_archive(entry.path):
            self.notify("Курсор должен быть на архиве (.zip, .tar…)", severity="warning")
            return
        dst = self._active_panel().current_path
        try:
            from .operations import extract_archive
            extract_archive(entry.path, dst / entry.path.stem)
            self._active_panel().reload()
            self.notify(f"Извлечено → {entry.path.stem}/")
        except Exception as exc:
            self.notify(f"Ошибка извлечения: {exc}", severity="error")

    def action_toggle_hidden(self) -> None:
        panel = self._active_panel()
        panel.toggle_hidden()
        self.config["show_hidden"] = panel.show_hidden
        save_config(self.config)

    def action_cycle_sort(self) -> None:
        name = self._active_panel().cycle_sort()
        self.notify(f"Сортировка: {name}")

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    def action_command_mode(self) -> None:
        cwd = str(self._active_panel().current_path)

        def _handle(cmd: str | None) -> None:
            if not cmd:
                return
            word = cmd.strip().lower().split()[0]
            if word in ("help", "?"):
                self.push_screen(HelpModal())
            elif word in ("q", "quit", "exit"):
                self.exit()
            else:
                self.run_worker(self._run_shell(cmd), exclusive=False)

        self.push_screen(CommandModal(cwd=cwd), _handle)

    async def _run_shell(self, cmd: str) -> None:
        import asyncio as _aio
        import subprocess as _sp
        cwd = self._active_panel().current_path

        def _execute() -> tuple[str, int]:
            try:
                res = _sp.run(
                    cmd, shell=True, cwd=str(cwd),
                    stdout=_sp.PIPE, stderr=_sp.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    timeout=60,
                )
                return res.stdout, res.returncode
            except _sp.TimeoutExpired:
                return "[fm] Команда превысила таймаут (60 сек)", 124
            except Exception as exc:
                return f"[fm] Ошибка: {exc}", -1

        output, rc = await _aio.get_event_loop().run_in_executor(None, _execute)
        self._active_panel().reload()
        self.push_screen(OutputModal(cmd=cmd, output=output, rc=rc))

    def action_add_bookmark(self) -> None:
        path = str(self._active_panel().current_path)
        add_bookmark(self.config, path)
        self.notify(f"Добавлено в закладки: {path}")

    def action_open_bookmarks(self) -> None:
        bms: list[str] = self.config.get("bookmarks", [])

        def _go(result: Optional[str]) -> None:
            if result:
                p = Path(result)
                if p.is_dir():
                    self._active_panel().navigate_to(p)

        self.push_screen(BookmarkModal(bms), _go)

    def action_open_terminal(self) -> None:
        open_terminal(self._active_panel().current_path)

    def action_rename(self) -> None:
        panel = self._active_panel()
        entry = panel.current_entry()
        if not entry:
            return

        def _do(name: Optional[str]) -> None:
            if name and name != entry.name:
                try:
                    rename_path(entry.path, name)
                    panel.reload()
                    self.notify(f"Переименовано: {name}")
                except Exception as exc:
                    self.notify(str(exc), severity="error")

        self.push_screen(InputModal(f"Переименовать '{entry.name}'", entry.name), _do)

    def action_mkdir(self) -> None:
        panel = self._active_panel()

        def _do(name: Optional[str]) -> None:
            if name:
                try:
                    make_dir(panel.current_path, name)
                    panel.reload()
                    self.notify(f"Создано: {name}/")
                except Exception as exc:
                    self.notify(str(exc), severity="error")

        self.push_screen(InputModal("Имя новой папки"), _do)

    def action_delete_files(self) -> None:
        panel = self._active_panel()
        paths = panel.selected_paths()
        if not paths:
            return
        preview = ", ".join(p.name for p in paths[:3])
        if len(paths) > 3:
            preview += f" (+{len(paths) - 3})"

        def _do(yes: bool) -> None:
            if not yes:
                return
            errs: list[str] = []
            for p in paths:
                try:
                    delete_path(p)
                except Exception as exc:
                    errs.append(str(exc))
            panel.reload()
            if errs:
                self.notify(errs[0], severity="error")
            else:
                self.notify(f"Удалено: {len(paths)} объект(ов)")

        self.push_screen(ConfirmModal(f"Удалить {preview}?"), _do)

    @staticmethod
    def _unique_dst(dst: Path) -> Path:
        """Return dst unchanged if it doesn't exist, otherwise add (копия) suffix."""
        if not dst.exists():
            return dst
        stem = dst.stem
        suffix = dst.suffix
        parent = dst.parent
        counter = 1
        while True:
            candidate = parent / f"{stem} (копия{f' {counter}' if counter > 1 else ''}){suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def action_copy_files(self) -> None:
        src, dst = self._active_panel(), self._other_panel()
        paths = src.selected_paths()
        if not paths:
            return
        dst_dir = dst.current_path
        if src.current_path == dst_dir:
            self.notify("Обе панели в одной папке — откройте другую папку в правой панели", severity="warning")
            return
        preview = ", ".join(p.name for p in paths[:2])
        if len(paths) > 2:
            preview += f" (+{len(paths) - 2})"

        def _do(yes: bool) -> None:
            if not yes:
                return
            errs: list[str] = []
            for p in paths:
                try:
                    copy_path(p, self._unique_dst(dst_dir / p.name))
                except Exception as exc:
                    errs.append(str(exc))
            dst.reload()
            if errs:
                self.notify(f"Ошибка копирования: {errs[0]}", severity="error")
            else:
                self.notify(f"Скопировано {len(paths)} → {dst_dir.name}/")

        self.push_screen(ConfirmModal(f"Копировать {preview} → {dst_dir.name}/?"), _do)

    def action_move_files(self) -> None:
        src, dst = self._active_panel(), self._other_panel()
        paths = src.selected_paths()
        if not paths:
            return
        dst_dir = dst.current_path
        if src.current_path == dst_dir:
            self.notify("Обе панели в одной папке — откройте другую папку в правой панели", severity="warning")
            return
        preview = ", ".join(p.name for p in paths[:2])
        if len(paths) > 2:
            preview += f" (+{len(paths) - 2})"

        def _do(yes: bool) -> None:
            if not yes:
                return
            errs: list[str] = []
            for p in paths:
                try:
                    move_path(p, dst_dir / p.name)
                except Exception as exc:
                    errs.append(str(exc))
            src.reload(); dst.reload()
            if errs:
                self.notify(f"Ошибка перемещения: {errs[0]}", severity="error")
            else:
                self.notify(f"Перемещено {len(paths)} → {dst_dir.name}/")

        self.push_screen(ConfirmModal(f"Переместить {preview} → {dst_dir.name}/?"), _do)

    def action_view_file(self) -> None:
        entry = self._active_panel().current_entry()
        if entry and not entry.is_dir:
            open_editor(entry.path)

    def action_edit_file(self) -> None:
        entry = self._active_panel().current_entry()
        if not entry or entry.is_dir:
            return
        self.query_one("#preview", PreviewPanel).enter_edit(entry.path)

    def on_preview_panel_edit_saved(self, e: PreviewPanel.EditSaved) -> None:
        self._active_panel().reload()

    def action_history_back(self) -> None:
        hist = self._history[self._active]
        idx = self._hist_idx[self._active]
        if idx > 0:
            self._hist_idx[self._active] = idx - 1
            self._active_panel().navigate_to(hist[idx - 1])

    def action_history_fwd(self) -> None:
        hist = self._history[self._active]
        idx = self._hist_idx[self._active]
        if idx < len(hist) - 1:
            self._hist_idx[self._active] = idx + 1
            self._active_panel().navigate_to(hist[idx + 1])

    def action_quit(self) -> None:
        self.exit()
