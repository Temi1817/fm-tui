import shutil
import tempfile
from pathlib import Path

import pytest

from fm.operations import (
    copy_path,
    delete_path,
    format_size,
    get_disk_usage,
    get_file_info,
    get_preview_text,
    make_dir,
    move_path,
    rename_path,
)


@pytest.fixture
def tmp(tmp_path: Path) -> Path:
    return tmp_path


def test_format_size():
    assert format_size(0) == "0 B"
    assert format_size(1023) == "1023 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(1024 ** 3) == "1.0 GB"


def test_get_file_info_file(tmp: Path):
    f = tmp / "hello.txt"
    f.write_text("hello world")
    info = get_file_info(f)
    assert info["size"] == 11
    assert info["is_dir"] is False
    assert info["modified"] != "?"


def test_get_file_info_dir(tmp: Path):
    info = get_file_info(tmp)
    assert info["is_dir"] is True


def test_get_file_info_missing(tmp: Path):
    info = get_file_info(tmp / "ghost.txt")
    assert info["size"] == 0


def test_get_disk_usage(tmp: Path):
    result = get_disk_usage(tmp)
    assert "Free" in result


def test_copy_file(tmp: Path):
    src = tmp / "src.txt"
    src.write_text("data")
    dst = tmp / "dst.txt"
    copy_path(src, dst)
    assert dst.read_text() == "data"
    assert src.exists()


def test_copy_dir(tmp: Path):
    src = tmp / "srcdir"
    src.mkdir()
    (src / "file.txt").write_text("x")
    dst = tmp / "dstdir"
    copy_path(src, dst)
    assert (dst / "file.txt").exists()


def test_move_file(tmp: Path):
    src = tmp / "a.txt"
    src.write_text("move me")
    dst = tmp / "b.txt"
    move_path(src, dst)
    assert not src.exists()
    assert dst.read_text() == "move me"


def test_rename_path(tmp: Path):
    f = tmp / "old.txt"
    f.write_text("rename")
    new = rename_path(f, "new.txt")
    assert new.name == "new.txt"
    assert new.exists()
    assert not f.exists()


def test_make_dir(tmp: Path):
    new_dir = make_dir(tmp, "subdir")
    assert new_dir.is_dir()


def test_make_dir_duplicate(tmp: Path):
    make_dir(tmp, "sub")
    with pytest.raises(FileExistsError):
        make_dir(tmp, "sub")


def test_delete_path_file(tmp: Path):
    f = tmp / "del.txt"
    f.write_text("bye")
    delete_path(f, use_trash=False)
    assert not f.exists()


def test_delete_path_dir(tmp: Path):
    d = tmp / "deldir"
    d.mkdir()
    (d / "x").write_text("x")
    delete_path(d, use_trash=False)
    assert not d.exists()


def test_preview_text(tmp: Path):
    f = tmp / "sample.py"
    f.write_text("print('hello')")
    text = get_preview_text(f)
    assert text is not None
    assert "hello" in text


def test_preview_binary(tmp: Path):
    f = tmp / "binary.bin"
    f.write_bytes(b"\x00\x01\x02\x03")
    assert get_preview_text(f) is None


def test_preview_missing(tmp: Path):
    assert get_preview_text(tmp / "nope.txt") is None
