"""Platform-neutral Blender CLI discovery, usable by Blender-side stdlib scripts."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def resolve_blender_executable(explicit: str | None = None) -> str:
    """Resolve explicit argument, BLENDER_BIN, then PATH without platform guesses.

    A configured executable must exist and be executable on the running platform;
    a broken explicit/environment setting never silently selects another Blender.
    Absolute results remain valid if the caller changes its working directory.
    """
    configured = explicit or os.environ.get("BLENDER_BIN")
    candidate = configured or "blender"
    executable = shutil.which(candidate)
    if executable is None:
        if configured:
            origin = "explicit argument" if explicit else "BLENDER_BIN"
            raise FileNotFoundError(
                f"Blender CLI configured by {origin} is missing or not executable: {configured}"
            )
        raise FileNotFoundError(
            "Blender CLI unavailable; provide --blender-bin/--blender, BLENDER_BIN, "
            "or a blender executable on PATH"
        )
    return str(Path(executable).resolve())
