#!/usr/bin/env python3
"""Protect immutable Blender sources and task-scoped output directories."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid

from asset_paths import AssetPathError, resolve_below_root, validate_task_id


LOCK_NAME = ".amidst-task.lock"


class SourceMutationError(RuntimeError):
    """An immutable source changed during a guarded operation."""


class OutputLockError(RuntimeError):
    """A task output directory is already locked or its lock is invalid."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SourceSnapshot:
    logical_uri: str
    size_bytes: int
    sha256: str


def snapshot_source(path: Path, logical_uri: str) -> SourceSnapshot:
    if not path.is_file():
        raise FileNotFoundError(f"Immutable source is unavailable: {logical_uri}")
    return SourceSnapshot(
        logical_uri=logical_uri,
        size_bytes=path.stat().st_size,
        sha256=sha256_file(path),
    )


def verify_source_unchanged(path: Path, before: SourceSnapshot) -> SourceSnapshot:
    after = snapshot_source(path, before.logical_uri)
    if after != before:
        raise SourceMutationError(f"Immutable source changed: {before.logical_uri}")
    return after


def source_root_is_writable(path: Path) -> bool:
    return os.access(path, os.W_OK)


class TaskOutputLock:
    """Atomic file lock scoped to one validated task output directory."""

    def __init__(self, output_root: Path, task_id: str):
        self.output_root = output_root.resolve(strict=False)
        self.task_id = validate_task_id(task_id)
        self.task_directory = resolve_below_root(self.output_root, self.task_id)
        self.lock_path = self.task_directory / LOCK_NAME
        self.run_id = str(uuid.uuid4())
        self._acquired = False

    def acquire(self) -> "TaskOutputLock":
        self.task_directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "lock_schema": "amidst.task_output_lock/0.1.0",
            "process_id": os.getpid(),
            "run_id": self.run_id,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "ACTIVE",
            "task_id": self.task_id,
        }
        try:
            descriptor = os.open(
                self.lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as error:
            raise OutputLockError(f"Task output is already locked: {self.task_id}") from error
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            self.lock_path.unlink(missing_ok=True)
            raise
        self._acquired = True
        return self

    def release(self) -> None:
        if not self._acquired:
            return
        try:
            record = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as error:
            raise OutputLockError(f"Task lock is missing or invalid: {self.task_id}") from error
        if record.get("run_id") != self.run_id:
            raise OutputLockError(f"Task lock ownership changed: {self.task_id}")
        self.lock_path.unlink()
        self._acquired = False

    def __enter__(self) -> "TaskOutputLock":
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()

    def record(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "acquired": self._acquired,
            "source_snapshots": [],
        }


def snapshot_record(snapshot: SourceSnapshot) -> dict[str, object]:
    return asdict(snapshot)
