#!/usr/bin/env python3
"""Verify the Blender-embedded runtime against the repository lock."""

from __future__ import annotations

import json
from pathlib import Path
import platform
import sys

import bpy
import mathutils  # noqa: F401 - import is part of the runtime contract
import numpy
import OpenImageIO


ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / "blender" / "runtime_dependencies.lock.json"


def text_value(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def main() -> int:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    expected = lock["versions"]
    actual = {
        "blender": bpy.app.version_string,
        "blender_build_hash": text_value(bpy.app.build_hash),
        "embedded_python": platform.python_version(),
        "numpy": numpy.__version__,
        "openimageio": text_value(OpenImageIO.VERSION_STRING),
    }
    mismatches = {
        name: {"expected": expected[name], "actual": value}
        for name, value in actual.items()
        if expected.get(name) != value
    }
    result = {
        "status": "PASS" if not mismatches else "FAIL",
        "lock": LOCK_PATH.relative_to(ROOT).as_posix(),
        "actual": actual,
        "mismatches": mismatches,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
