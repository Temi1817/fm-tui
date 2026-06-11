from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            tomllib = None  # type: ignore[assignment]

try:
    import tomli_w

    _HAS_TOMLI_W = True
except ImportError:
    _HAS_TOMLI_W = False

CONFIG_DIR = Path.home() / ".config" / "fm"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG: dict = {
    "theme": "dark",
    "show_hidden": False,
    "sort_by": "name",
    "sort_reverse": False,
    "icons": False,
    "bookmarks": [],
}


def load_config() -> dict:
    if not CONFIG_FILE.exists() or tomllib is None:
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
        cfg = dict(DEFAULT_CONFIG)
        cfg.update(data)
        return cfg
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if _HAS_TOMLI_W:
        with open(CONFIG_FILE, "wb") as f:
            tomli_w.dump(config, f)
    else:
        _write_toml_fallback(config)


def _write_toml_fallback(config: dict) -> None:
    lines: list[str] = []
    for key, value in config.items():
        if key == "bookmarks":
            continue
        if isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
    lines.append("")
    lines.append("bookmarks = [")
    for bm in config.get("bookmarks", []):
        safe = bm.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'  "{safe}",')
    lines.append("]")
    CONFIG_FILE.write_text("\n".join(lines), encoding="utf-8")


def add_bookmark(config: dict, path: str) -> None:
    bookmarks: list = config.setdefault("bookmarks", [])
    if path not in bookmarks:
        bookmarks.append(path)
    save_config(config)


def remove_bookmark(config: dict, path: str) -> None:
    bookmarks: list = config.get("bookmarks", [])
    if path in bookmarks:
        bookmarks.remove(path)
    save_config(config)
