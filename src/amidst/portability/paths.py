"""Explicit local path resolution and portable JSON references."""

from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath


def resolve_local_path(raw: str | Path, *, base: Path) -> Path:
    """Resolve host-local paths without reinterpreting foreign absolute paths."""
    value = os.fspath(raw)
    windows = PureWindowsPath(value)
    if os.name != "nt" and (windows.drive or value.startswith("\\")):
        raise ValueError("Windows paths cannot be resolved on this platform")
    path = Path(value)
    if os.name == "nt" and path.anchor and not path.is_absolute():
        raise ValueError("Windows paths must be fully absolute or base-relative")
    return (path if path.is_absolute() else base / path).resolve()


def portable_relative_reference(target: Path, base: Path) -> str:
    """Return a POSIX-separator JSON reference; cross-drive paths fail explicitly."""
    try:
        relative = os.path.relpath(target, base)
    except ValueError as error:
        raise ValueError("portable relative references require paths on the same drive") from error
    return relative.replace(os.sep, "/")
