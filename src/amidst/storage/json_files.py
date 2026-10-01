"""Atomic local JSON publication with explicit no-overwrite and input protection."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_json(
    path: Path,
    payload: Any,
    *,
    overwrite: bool = False,
    protected_inputs: tuple[Path, ...] = (),
) -> None:
    if path.suffix.lower() != ".json" or path.resolve().suffix.lower() != ".json":
        raise ValueError("artifact output must be a JSON file, never a Blender asset")
    if path.resolve() in {item.resolve() for item in protected_inputs}:
        raise ValueError("artifact output must not replace an input")
    contents = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    staged: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            staged = Path(stream.name)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(staged, path)
        else:
            os.link(staged, path)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
