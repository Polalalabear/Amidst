"""Pilot planning preserves both original and derived asset identity."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "plan_blender_pilot_sites.py"
SPEC = importlib.util.spec_from_file_location("pilot_planning_source", SCRIPT)
assert SPEC and SPEC.loader
planning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(planning)


def identity(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def test_unchanged_original_and_derived_assets_pass(tmp_path: Path) -> None:
    for name in ("original.blend", "derived.blend"):
        path = tmp_path / name
        path.write_bytes(name.encode())
        planning.verify_immutable_source(path, *identity(path))


def test_content_change_is_rejected_even_with_original_size_and_mtime(tmp_path: Path) -> None:
    path = tmp_path / "original.blend"
    path.write_bytes(b"original")
    before = identity(path)
    stat = path.stat()
    path.write_bytes(b"modified")
    os.utime(path, ns=(stat.st_atime_ns, before[2]))
    assert path.stat().st_size == before[1]
    assert path.stat().st_mtime_ns == before[2]
    with pytest.raises(RuntimeError, match="Immutable Blender source changed"):
        planning.verify_immutable_source(path, *before)


def test_timestamp_change_is_rejected_without_content_change(tmp_path: Path) -> None:
    path = tmp_path / "original.blend"
    path.write_bytes(b"original")
    before = identity(path)
    os.utime(path, ns=(before[2], before[2] + 1_000_000_000))
    with pytest.raises(RuntimeError, match="Immutable Blender source changed"):
        planning.verify_immutable_source(path, *before)
