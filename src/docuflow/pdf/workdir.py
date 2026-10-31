"""Temporary work directories with guaranteed cleanup."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def work_directory(prefix: str = "docuflow-", parent: str | Path | None = None) -> Iterator[Path]:
    base = Path(parent) if parent else None
    if base is not None:
        base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=str(base) if base else None))
    try:
        os.chmod(path, stat.S_IRWXU)
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def paths_collide(left: Path | str, right: Path | str) -> bool:
    """True when two paths name the same file after expand, resolve, and symlink follow."""
    return Path(left).expanduser().resolve() == Path(right).expanduser().resolve()


def safe_output_path(work_dir: Path, name: str) -> Path:
    candidate = Path(name)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("Output name must be a basename without path separators.")
    target = (work_dir / candidate.name).resolve()
    if not str(target).startswith(str(work_dir.resolve())):
        raise ValueError("Refusing to write outside the work directory.")
    return target
