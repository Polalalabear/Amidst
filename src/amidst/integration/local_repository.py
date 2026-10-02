"""Mock storage for integration contracts, with no concurrent-writer guarantee."""

from __future__ import annotations

from pathlib import Path

from amidst.experiments.versioning import read_local_bytes
from amidst.integration.repositories import RepositorySnapshot, _merge_snapshots
from amidst.observation.aggregation import validate_stream_model
from amidst.storage.json_files import write_json


class InMemoryRepository:
    """Synthetic mock implementation preserving full canonical record payloads."""

    def __init__(self, initial: RepositorySnapshot | None = None) -> None:
        self._snapshot = validate_stream_model(
            initial if initial is not None else RepositorySnapshot(), RepositorySnapshot,
        )

    def snapshot(self) -> RepositorySnapshot:
        return validate_stream_model(self._snapshot, RepositorySnapshot)

    def add(self, snapshot: RepositorySnapshot) -> None:
        self._snapshot = _merge_snapshots(self._snapshot, snapshot)


class LocalJsonRepository:
    """One validated local mock snapshot file, reopened before every read/merge.

    Publication uses exclusive creation first and atomic replacement only for a
    validated repository file. This is single-writer storage without locking,
    transactions across processes, durability or production concurrency claims.
    """

    def __init__(self, path: Path, initial: RepositorySnapshot | None = None) -> None:
        self.path = path
        if path.suffix.lower() != ".json" or path.resolve().suffix.lower() != ".json":
            raise ValueError("local repository store must be a JSON file")
        incoming = validate_stream_model(
            initial if initial is not None else RepositorySnapshot(), RepositorySnapshot,
        )
        if self.path.exists():
            self.snapshot()
            if initial is not None:
                self.add(incoming)
        else:
            write_json(self.path, incoming.model_dump(mode="json"))

    def snapshot(self) -> RepositorySnapshot:
        return RepositorySnapshot.model_validate_json(read_local_bytes(self.path))

    def add(self, snapshot: RepositorySnapshot) -> None:
        current = self.snapshot()
        merged = _merge_snapshots(current, snapshot)
        if merged != current:
            write_json(self.path, merged.model_dump(mode="json"), overwrite=True)
