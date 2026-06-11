from __future__ import annotations

from pathlib import Path
from typing import Optional

from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, TextArea

from .operations import (
    IMAGE_EXTS, get_file_info, get_image_info, get_preview_text,
    format_size, is_archive, list_archive,
)

SYNTAX_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".jsx": "jsx", ".tsx": "tsx", ".html": "html", ".css": "css",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".sh": "bash", ".bash": "bash", ".zsh": "bash", ".fish": "fish",
    ".rs": "rust", ".go": "go", ".c": "c", ".cpp": "cpp", ".h": "c",
    ".java": "java", ".rb": "ruby", ".php": "php", ".xml": "xml",
    ".md": "markdown", ".sql": "sql", ".lua": "lua", ".r": "r",
    ".ps1": "powershell", ".bat": "batch", ".cmd": "batch",
}


class _EditorArea(TextArea):
    """TextArea that emits Save/Cancel messages on Ctrl+S / Escape."""

    class Save(Message):
        pass

    class Cancel(Message):
        pass

    BINDINGS = [
        Binding("ctrl+s", "save",   show=False, priority=True),
        Binding("escape", "cancel", show=False, priority=True),
    ]

    def action_save(self) -> None:
        self.post_message(self.Save())

    def action_cancel(self) -> None:
        self.post_message(self.Cancel())


class PreviewPanel(Widget):
    """Right-side panel: read-only preview + optional inline editor."""

    class EditSaved(Message):
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    DEFAULT_CSS = """
    PreviewPanel {
        width: 1fr;
        border: solid $surface-lighten-1;
        background: $surface-darken-1;
    }
    #preview-title {
        height: 1;
        background: $surface-lighten-1;
        color: $accent;
        padding: 0 1;
    }
    #preview-meta {
        height: 5;
        background: $surface-darken-1;
        padding: 0 1;
        border-bottom: solid $surface-lighten-1;
    }
    #preview-content {
        height: 1fr;
        background: $surface-darken-1;
        padding: 0 1;
        overflow: auto auto;
    }
    #preview-editor {
        height: 1fr;
        display: none;
    }
    #edit-hint {
        height: 1;
        background: $success-darken-2;
        color: $success;
        padding: 0 1;
        display: none;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._edit_path: Optional[Path] = None
        self._preview_path: Optional[Path] = None

    def compose(self) -> ComposeResult:
        yield Static("", id="preview-title")
        yield Static("", id="preview-meta")
        yield Static("Ctrl+S — сохранить   Esc — отмена", id="edit-hint")
        yield Static("", id="preview-content", expand=True)
        yield _EditorArea("", id="preview-editor", show_line_numbers=True)

    # ── public API ────────────────────────────────────────────────────────────

    def update(self, path: Optional[Path]) -> None:  # type: ignore[override]
        if self._edit_path is not None:
            return  # don't clobber an active edit session
        self._preview_path = path
        self._render_preview(path)

    def enter_edit(self, path: Path) -> None:
        """Switch preview panel into inline-edit mode for *path*."""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        self._edit_path = path

        ta = self.query_one("#preview-editor", _EditorArea)
        ext = path.suffix.lower()
        lang = SYNTAX_MAP.get(ext)
        try:
            ta.language = lang  # type: ignore[assignment]
        except Exception:
            ta.language = None  # type: ignore[assignment]
        ta.load_text(text)

        self.query_one("#preview-content").display = False
        self.query_one("#edit-hint").display = True
        ta.display = True
        ta.focus()

        self.query_one("#preview-title", Static).update(
            f" [EDIT]  {path.name}"
        )

    @property
    def is_editing(self) -> bool:
        return self._edit_path is not None

    # ── internal ──────────────────────────────────────────────────────────────

    def _exit_edit(self) -> None:
        self._edit_path = None
        ta = self.query_one("#preview-editor", _EditorArea)
        ta.display = False
        self.query_one("#edit-hint").display = False
        self.query_one("#preview-content").display = True
        self._render_preview(self._preview_path)

    def on__editor_area_save(self, _: _EditorArea.Save) -> None:
        if self._edit_path is None:
            return
        ta = self.query_one("#preview-editor", _EditorArea)
        try:
            self._edit_path.write_text(ta.text, encoding="utf-8")
            self.post_message(self.EditSaved(self._edit_path))
        except OSError as exc:
            self.notify(f"Ошибка сохранения: {exc}", severity="error")
        self._exit_edit()

    def on__editor_area_cancel(self, _: _EditorArea.Cancel) -> None:
        self._exit_edit()

    def _render_preview(self, path: Optional[Path]) -> None:
        title   = self.query_one("#preview-title", Static)
        meta    = self.query_one("#preview-meta",  Static)
        content = self.query_one("#preview-content", Static)

        if path is None:
            title.update("")
            meta.update("")
            content.update("")
            return

        title.update(f" {path.name}")

        info = get_file_info(path)
        mt = Text()
        mt.append(f" Size:  {info['size_fmt']}\n", style="cyan")
        mt.append(f" Perms: {info['permissions']}\n", style="green")
        mt.append(f" Mod:   {info['modified']}\n", style="yellow")
        if path.is_symlink():
            try:
                mt.append(f" Link:  {path.resolve()}\n", style="magenta")
            except OSError:
                pass
        meta.update(mt)

        if path.is_dir():
            try:
                items = list(path.iterdir())
                n_dirs  = sum(1 for i in items if i.is_dir())
                n_files = sum(1 for i in items if not i.is_dir())
                ct = Text()
                ct.append("\n  Directory\n\n", style="bold blue")
                ct.append(f"  {n_dirs} folder(s)\n", style="blue")
                ct.append(f"  {n_files} file(s)\n", style="white")
                content.update(ct)
            except PermissionError:
                content.update(Text("  Permission denied", style="red"))
            return

        # ── image preview ─────────────────────────────────────────────
        if path.suffix.lower() in IMAGE_EXTS:
            img_info = get_image_info(path)
            ct = Text()
            ct.append("\n  Изображение\n\n", style="bold magenta")
            if img_info:
                ct.append(f"  {img_info['width']} × {img_info['height']} px\n", style="cyan")
                ct.append(f"  Формат:  {img_info['format']}\n", style="white")
                ct.append(f"  Режим:   {img_info['mode']}\n", style="dim")
            else:
                ct.append("  (установите Pillow для метаданных)\n", style="dim")
                ct.append("  pip install Pillow\n", style="dim")
            content.update(ct)
            return

        # ── archive preview ───────────────────────────────────────────
        if is_archive(path):
            entries = list_archive(path)
            ct = Text()
            ct.append(f"\n  Архив — {len(entries)} файл(ов)\n\n", style="bold red")
            for name in entries[:60]:
                ct.append(f"  {name}\n", style="white" if not name.endswith("/") else "bold blue")
            if len(entries) > 60:
                ct.append(f"\n  … ещё {len(entries) - 60} файл(ов)\n", style="dim")
            content.update(ct)
            return

        text = get_preview_text(path)
        if text is None:
            content.update(Text("  [Binary file — no preview]", style="dim"))
            return

        ext  = path.suffix.lower()
        lang = SYNTAX_MAP.get(ext)
        if lang:
            try:
                content.update(Syntax(
                    text[:6000], lang,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                ))
                return
            except Exception:
                pass

        content.update(Text(text[:6000]))
