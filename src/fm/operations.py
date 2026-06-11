from __future__ import annotations

import os
import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import send2trash
    _HAS_TRASH = True
except ImportError:
    _HAS_TRASH = False

try:
    from PIL import Image as _PILImage
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tgz"}
IMAGE_EXTS   = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".svg"}


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size //= 1024
    return f"{size} TB"


def format_permissions(path: Path) -> str:
    if platform.system() == "Windows":
        attrs = []
        if path.is_dir():
            attrs.append("D")
        if not os.access(path, os.W_OK):
            attrs.append("R")
        return "".join(attrs) or "RW"
    import stat as _stat

    mode = path.stat().st_mode
    chars = []
    for shift in (6, 3, 0):
        chars.append("r" if mode >> shift & 4 else "-")
        chars.append("w" if mode >> shift & 2 else "-")
        chars.append("x" if mode >> shift & 1 else "-")
    return "".join(chars)


def get_file_info(path: Path) -> dict:
    try:
        st = path.stat()
        return {
            "size": st.st_size,
            "size_fmt": format_size(st.st_size),
            "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "permissions": format_permissions(path),
            "is_dir": path.is_dir(),
        }
    except (OSError, PermissionError):
        return {"size": 0, "size_fmt": "?", "modified": "?", "permissions": "?", "is_dir": False}


def get_disk_usage(path: Path) -> str:
    try:
        usage = shutil.disk_usage(path)
        return f"Free: {format_size(usage.free)} / {format_size(usage.total)}"
    except OSError:
        return ""


def copy_path(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(str(src), str(dst))
    else:
        shutil.copy2(str(src), str(dst))


def move_path(src: Path, dst: Path) -> None:
    shutil.move(str(src), str(dst))


def delete_path(path: Path, use_trash: bool = True) -> None:
    if use_trash and _HAS_TRASH:
        send2trash.send2trash(str(path))
    elif path.is_dir():
        shutil.rmtree(str(path))
    else:
        path.unlink()


def rename_path(path: Path, new_name: str) -> Path:
    new_path = path.parent / new_name
    path.rename(new_path)
    return new_path


def make_dir(parent: Path, name: str) -> Path:
    new_dir = parent / name
    new_dir.mkdir(parents=True, exist_ok=False)
    return new_dir


def open_path(path: Path) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def open_terminal(path: Path) -> None:
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["cmd", "/K", f"cd /d {path}"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        elif system == "Darwin":
            script = f'tell application "Terminal" to do script "cd {path!s}"'
            subprocess.Popen(["osascript", "-e", script])
        else:
            term = os.environ.get("TERMINAL", os.environ.get("TERM_PROGRAM", "xterm"))
            subprocess.Popen([term], cwd=str(path))
    except Exception:
        pass


def get_editor() -> str:
    system = platform.system()
    return os.environ.get("EDITOR") or os.environ.get("VISUAL") or (
        "notepad" if system == "Windows" else "nano"
    )


def open_editor(path: Path) -> None:
    try:
        subprocess.Popen([get_editor(), str(path)])
    except Exception:
        pass


def get_preview_text(path: Path, max_bytes: int = 8192) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            raw = f.read(max_bytes)
        if b"\x00" in raw:
            return None
        return raw.decode("utf-8", errors="replace")
    except (OSError, PermissionError):
        return None


# ── archive helpers ───────────────────────────────────────────────────

def is_archive(path: Path) -> bool:
    return path.suffix.lower() in ARCHIVE_EXTS or _is_tar(path)


def _is_tar(path: Path) -> bool:
    import tarfile
    try:
        return tarfile.is_tarfile(str(path))
    except Exception:
        return False


def extract_archive(src: Path, dst_dir: Path) -> None:
    import zipfile, tarfile as tf
    dst_dir.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(str(src)):
        with zipfile.ZipFile(src) as zf:
            zf.extractall(dst_dir)
    elif tf.is_tarfile(str(src)):
        with tf.open(src) as t:
            t.extractall(dst_dir)
    else:
        raise ValueError(f"Неподдерживаемый формат: {src.name}")


def create_zip(paths: list[Path], dst: Path) -> None:
    import zipfile
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            if p.is_dir():
                for f in sorted(p.rglob("*")):
                    zf.write(f, f.relative_to(p.parent))
            else:
                zf.write(p, p.name)


def list_archive(path: Path) -> list[str]:
    import zipfile, tarfile as tf
    try:
        if zipfile.is_zipfile(str(path)):
            with zipfile.ZipFile(path) as zf:
                return sorted(zf.namelist())
        if tf.is_tarfile(str(path)):
            with tf.open(path) as t:
                return sorted(t.getnames())
    except Exception:
        pass
    return []


# ── duplicate ─────────────────────────────────────────────────────────

def duplicate_path(path: Path) -> Path:
    stem, suffix, parent = path.stem, path.suffix, path.parent
    counter = 1
    while True:
        label = f" (копия)" if counter == 1 else f" (копия {counter})"
        candidate = parent / f"{stem}{label}{suffix}"
        if not candidate.exists():
            break
        counter += 1
    if path.is_dir():
        shutil.copytree(str(path), str(candidate))
    else:
        shutil.copy2(str(path), str(candidate))
    return candidate


# ── image info ────────────────────────────────────────────────────────

def get_image_info(path: Path) -> Optional[dict]:
    if not _HAS_PIL:
        return None
    try:
        with _PILImage.open(path) as img:
            return {
                "width": img.width,
                "height": img.height,
                "mode": img.mode,
                "format": img.format or path.suffix.upper().lstrip("."),
            }
    except Exception:
        return None
