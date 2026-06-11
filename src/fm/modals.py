from __future__ import annotations

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static, TextArea


class ConfirmModal(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmModal { align: center middle; }
    ConfirmModal > Container {
        width: 62; height: auto; padding: 1 2;
        background: $surface-lighten-1; border: solid $accent;
    }
    ConfirmModal Label { text-align: center; width: 100%; padding: 1; }
    ConfirmModal Horizontal { height: auto; align: center middle; margin-top: 1; }
    ConfirmModal Button { margin: 0 1; }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._msg = message

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self._msg)
            with Horizontal():
                yield Button("Да [y]", variant="error", id="yes")
                yield Button("Нет [Esc]", variant="primary", id="no")

    def on_button_pressed(self, e: Button.Pressed) -> None:
        self.dismiss(e.button.id == "yes")

    def on_key(self, e) -> None:
        if e.key in ("escape", "n"):
            self.dismiss(False)
        elif e.key == "y":
            self.dismiss(True)


class InputModal(ModalScreen[Optional[str]]):
    DEFAULT_CSS = """
    InputModal { align: center middle; }
    InputModal > Container {
        width: 62; height: auto; padding: 1 2;
        background: $surface-lighten-1; border: solid $accent;
    }
    InputModal Label { text-align: center; width: 100%; padding: 0 0 1 0; }
    InputModal Input { margin-bottom: 1; }
    InputModal Horizontal { height: auto; align: center middle; }
    InputModal Button { margin: 0 1; }
    """

    def __init__(self, title: str, default: str = "") -> None:
        super().__init__()
        self._title = title
        self._default = default

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self._title)
            yield Input(value=self._default, id="inp")
            with Horizontal():
                yield Button("OK", variant="primary", id="ok")
                yield Button("Отмена", id="cancel")

    def on_mount(self) -> None:
        inp = self.query_one("#inp", Input)
        inp.focus()
        inp.cursor_position = len(self._default)

    def on_button_pressed(self, e: Button.Pressed) -> None:
        if e.button.id == "ok":
            self.dismiss(self.query_one("#inp", Input).value.strip() or None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, e: Input.Submitted) -> None:
        self.dismiss(e.value.strip() or None)

    def on_key(self, e) -> None:
        if e.key == "escape":
            self.dismiss(None)


class HelpModal(ModalScreen):
    _TEXT = """\
 ┌────────────────────┬──────────────────────────────────────┐
 │ Навигация          │                                      │
 │  ↑ ↓  /  k j       │ Перемещение курсора                  │
 │  Tab               │ Переключить активную панель          │
 │  Enter             │ Открыть папку / файл / архив         │
 │  Backspace         │ Выйти на уровень выше                │
 │  Alt+← / Alt+→    │ История назад / вперёд               │
 ├────────────────────┼──────────────────────────────────────┤
 │ Файловые операции  │                                      │
 │  F5                │ Копировать → другая панель           │
 │  F6                │ Переместить → другая панель          │
 │  F2                │ Переименовать                        │
 │  F7                │ Создать папку                        │
 │  F8 / Del          │ Удалить (в корзину)                  │
 │  F3                │ Просмотр файла                       │
 │  F4                │ Редактировать (встроенный редактор)  │
 │  Ctrl+D            │ Дублировать в этой же папке          │
 │  Ctrl+R            │ Массовое переименование выделенных   │
 ├────────────────────┼──────────────────────────────────────┤
 │ Архивы             │                                      │
 │  Enter на архиве   │ Войти внутрь архива (.zip, .tar…)    │
 │  Ctrl+E            │ Извлечь архив в текущую папку        │
 │  Ctrl+Z            │ Создать .zip из выделенных файлов    │
 ├────────────────────┼──────────────────────────────────────┤
 │ Выделение          │                                      │
 │  Space             │ Выделить / снять выделение           │
 │  Ctrl+A            │ Выделить всё / снять всё             │
 ├────────────────────┼──────────────────────────────────────┤
 │ Поиск и вид        │                                      │
 │  /                 │ Поиск в текущей папке                │
 │  Ctrl+F            │ Поиск по всем подпапкам              │
 │  Esc               │ Закрыть поиск                        │
 │  .                 │ Показать / скрыть скрытые файлы      │
 │  s                 │ Сортировка: имя → размер → дата      │
 ├────────────────────┼──────────────────────────────────────┤
 │ Редактор (F4)      │                                      │
 │  Ctrl+S            │ Сохранить файл                       │
 │  Esc               │ Отменить редактирование              │
 ├────────────────────┼──────────────────────────────────────┤
 │ Командная строка   │                                      │
 │  :                 │ Открыть командную строку             │
 │  : echo hi         │ Выполнить shell-команду              │
 │  : git status      │ Вывод отображается прямо в fm        │
 │  : help            │ Справка  │  : q — Выход             │
 ├────────────────────┼──────────────────────────────────────┤
 │ Закладки           │                                      │
 │  b                 │ Добавить текущую папку               │
 │  '                 │ Открыть список закладок              │
 ├────────────────────┼──────────────────────────────────────┤
 │ Разное             │                                      │
 │  !                 │ Открыть терминал в текущей папке     │
 │  ?                 │ Эта справка                          │
 │  q                 │ Выход                                │
 └────────────────────┴──────────────────────────────────────┘\
"""
    DEFAULT_CSS = """
    HelpModal { align: center middle; }
    HelpModal > Container {
        width: 64; height: 80%; padding: 1 1;
        background: $surface-lighten-1; border: solid $accent;
        overflow: auto;
    }
    HelpModal Static { color: $text; }
    HelpModal Button { margin-top: 1; width: 100%; }
    """

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(self._TEXT)
            yield Button("Закрыть  [Esc]", variant="primary", id="close")

    def on_button_pressed(self, e: Button.Pressed) -> None:
        self.dismiss()

    def on_key(self, e) -> None:
        if e.key in ("escape", "q", "question_mark"):
            self.dismiss()


class BookmarkModal(ModalScreen[Optional[str]]):
    DEFAULT_CSS = """
    BookmarkModal { align: center middle; }
    BookmarkModal > Container {
        width: 62; height: auto; max-height: 20; padding: 1 2;
        background: $surface-lighten-1; border: solid $accent;
    }
    BookmarkModal Label { padding: 0 0 1 0; }
    BookmarkModal ListView { height: auto; max-height: 12; }
    BookmarkModal Button { margin-top: 1; width: 100%; }
    """

    def __init__(self, bookmarks: list[str]) -> None:
        super().__init__()
        self._bookmarks = bookmarks

    def compose(self) -> ComposeResult:
        items = [ListItem(Label(bm)) for bm in self._bookmarks]
        if not items:
            items = [ListItem(Label("[dim]Закладок нет — нажми 'b' чтобы добавить[/dim]"))]
        with Container():
            yield Label("Закладки  (Enter — перейти)")
            yield ListView(*items, id="blist")
            yield Button("Отмена  [Esc]", id="cancel")

    def on_list_view_selected(self, e: ListView.Selected) -> None:
        idx = self.query_one("#blist", ListView).index
        if idx is not None and idx < len(self._bookmarks):
            self.dismiss(self._bookmarks[idx])
        else:
            self.dismiss(None)

    def on_button_pressed(self, e: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, e) -> None:
        if e.key == "escape":
            self.dismiss(None)


class CommandModal(ModalScreen):
    """Shell command bar — type any command or a built-in (help / q)."""

    DEFAULT_CSS = """
    CommandModal { align: center middle; }
    CommandModal > Container {
        width: 72; height: auto; padding: 1 2;
        background: $surface-lighten-1; border: solid $accent;
    }
    CommandModal #cwd-label { padding: 0 0 1 0; color: $success; }
    CommandModal #hint      { padding: 1 0 0 0; color: $text-muted; }
    CommandModal Input      { margin-bottom: 0; }
    """

    _BUILTINS = {"help", "?", "q", "quit", "exit"}
    _HINT_DEFAULT = "[dim]Любая shell-команда   или: help · q[/dim]"

    def __init__(self, cwd: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._cwd = cwd

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(f" Папка: {self._cwd}", id="cwd-label")
            yield Input(id="cmd-input", placeholder="echo hi / git status / dir …")
            yield Static(self._HINT_DEFAULT, id="hint")

    def on_mount(self) -> None:
        self.query_one("#cmd-input", Input).focus()

    def on_input_changed(self, e: Input.Changed) -> None:
        hint = self.query_one("#hint", Static)
        word = e.value.strip().lower().split()[0] if e.value.strip() else ""
        if word in ("help", "?"):
            hint.update("[green]открыть справку[/green]")
        elif word in ("q", "quit", "exit"):
            hint.update("[green]выйти из fm[/green]")
        elif word:
            hint.update(f"[cyan]> {e.value.strip()}[/cyan]   Enter — выполнить")
        else:
            hint.update(self._HINT_DEFAULT)

    def on_input_submitted(self, e: Input.Submitted) -> None:
        raw = e.value.strip()
        self.dismiss(raw or None)

    def on_key(self, e) -> None:
        if e.key == "escape":
            self.dismiss(None)


class OutputModal(ModalScreen):
    """Show captured shell command output inside fm."""

    DEFAULT_CSS = """
    OutputModal { align: center middle; }
    OutputModal > Container {
        width: 90%; height: 80%; padding: 0;
        background: $surface; border: solid $accent;
    }
    OutputModal #out-title {
        height: 1; background: $accent; color: $background;
        padding: 0 1;
    }
    OutputModal #out-body {
        height: 1fr; overflow: auto auto;
        padding: 0 1;
    }
    OutputModal #out-status {
        height: 1; background: $surface-lighten-1;
        padding: 0 1; color: $text-muted;
    }
    """

    def __init__(self, cmd: str, output: str, rc: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cmd = cmd
        self._output = output
        self._rc = rc

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(f" $ {self._cmd}", id="out-title")
            yield Static(self._output or "[dim](нет вывода)[/dim]", id="out-body")
            color = "red" if self._rc != 0 else "green"
            yield Static(
                f" Код выхода: [{color}]{self._rc}[/{color}]   Esc / q — закрыть",
                id="out-status",
            )

    def on_mount(self) -> None:
        self.query_one("#out-body").focus()

    def on_key(self, e) -> None:
        if e.key in ("escape", "q"):
            self.dismiss()


class BulkRenameModal(ModalScreen[Optional[list[tuple[Path, str]]]]):
    """Edit multiple filenames in a text area — one name per line."""

    DEFAULT_CSS = """
    BulkRenameModal { align: center middle; }
    BulkRenameModal > Container {
        width: 80%; height: 70%; padding: 0;
        background: $surface; border: solid $accent;
    }
    BulkRenameModal #br-title {
        height: 1; background: $accent; color: $background; padding: 0 1;
    }
    BulkRenameModal #br-hint {
        height: 1; background: $surface-lighten-1; color: $text-muted; padding: 0 1;
    }
    BulkRenameModal TextArea { height: 1fr; }
    """

    BINDINGS = [
        Binding("ctrl+s", "apply", show=False, priority=True),
        Binding("escape", "cancel", show=False, priority=True),
    ]

    def __init__(self, paths: list[Path], **kwargs) -> None:
        super().__init__(**kwargs)
        self._paths = paths

    def compose(self) -> ComposeResult:
        names = "\n".join(p.name for p in self._paths)
        with Container():
            yield Static(
                f" Переименовать {len(self._paths)} файл(ов)",
                id="br-title",
            )
            yield TextArea(names, id="br-area")
            yield Static(
                " Ctrl+S — применить   Esc — отмена   (одно имя на строку)",
                id="br-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#br-area", TextArea).focus()

    def action_apply(self) -> None:
        new_names = self.query_one("#br-area", TextArea).text.splitlines()
        if len(new_names) != len(self._paths):
            self.app.notify(
                f"Строк: {len(new_names)}, файлов: {len(self._paths)} — не совпадает",
                severity="error",
            )
            return
        pairs = [
            (p, n.strip())
            for p, n in zip(self._paths, new_names)
            if n.strip() and n.strip() != p.name
        ]
        self.dismiss(pairs or None)

    def action_cancel(self) -> None:
        self.dismiss(None)
