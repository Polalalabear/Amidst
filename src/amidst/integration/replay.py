"""Read verified benchmark inference artifacts without running or changing Phase 1."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import ValidationError

from amidst.domain.common import DomainModel
from amidst.domain.experiment import Digest, InputFingerprint
from amidst.domain.stream import BoundGapEvent, BoundObservation, ObservationAggregation
from amidst.integration.repositories import RepositorySnapshot


class BenchmarkImportError(ValueError):
    """An incomplete, changed or ambiguous artifact package cannot be imported."""


class _BenchmarkManifest(DomainModel):
    schema_version: Literal["1.0"]
    status: Literal["COMPLETE"]
    config_sha256: Digest
    files: tuple[InputFingerprint, ...]


def _contained_path(root: Path, logical_id: str) -> Path:
    relative = PurePosixPath(logical_id)
    if (
        relative.is_absolute()
        or relative.as_posix() != logical_id
        or any(part in {"", ".", ".."} for part in logical_id.split("/"))
        or "\\" in logical_id
        or "\x00" in logical_id
        or ":" in logical_id
    ):
        raise BenchmarkImportError("artifact paths must be canonical relative paths")
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise BenchmarkImportError("artifact paths must identify files inside the package root")
    return path


def _verify_file(path: Path, item: InputFingerprint, *, retain: bool) -> bytes | None:
    """Hash all artifacts; retain only inference JSON for atomic deserialization."""
    digest = hashlib.sha256()
    size = 0
    chunks: list[bytes] = []
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
            if retain:
                chunks.append(chunk)
    if size != item.size_bytes or digest.hexdigest() != item.sha256:
        raise BenchmarkImportError(f"artifact digest/size mismatch: {item.logical_id}")
    return b"".join(chunks) if retain else None


def _verified_artifacts(root: Path) -> tuple[Path, dict[str, bytes]]:
    """Finish all integrity and coverage checks before interpreting any evidence."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise BenchmarkImportError("benchmark package root must be a directory")
    manifest_path = _contained_path(root, "artifacts.json")
    manifest = _BenchmarkManifest.model_validate_json(manifest_path.read_bytes(), strict=True)
    listed = {item.logical_id for item in manifest.files}
    if len(listed) != len(manifest.files):
        raise BenchmarkImportError("artifact paths must be unique")
    required = {"experiment.json", "replay/config.json"}
    if not required <= listed:
        raise BenchmarkImportError("experiment.json and replay/config.json must be listed")
    if "artifacts.json" in listed:
        raise BenchmarkImportError("manifest cannot fingerprint itself")

    inference_names = {"observations.json", "candidates.json"}
    on_disk = {
        path.relative_to(root).as_posix()
        for name in sorted(inference_names)
        for path in root.rglob(name)
    }
    if not on_disk <= listed:
        raise BenchmarkImportError("every observation/candidate artifact must be listed")
    if not any(PurePosixPath(name).name == "observations.json" for name in listed):
        raise BenchmarkImportError("benchmark package requires an observation artifact")

    resolved: set[Path] = set()
    inference: dict[str, bytes] = {}
    for item in manifest.files:
        path = _contained_path(root, item.logical_id)
        if path in resolved:
            raise BenchmarkImportError("artifact paths must not alias the same file")
        resolved.add(path)
        retain = PurePosixPath(item.logical_id).name in inference_names
        contents = _verify_file(path, item, retain=retain)
        if contents is not None:
            inference[item.logical_id] = contents
    return root, inference


def load_benchmark_snapshot(root: Path) -> RepositorySnapshot:
    """Import original observations and gaps; evaluation/GT artifacts are hash-only.

    The returned snapshot is constructed only after every listed artifact passes
    digest verification. Cached inference bytes keep deserialization bound to the
    exact verified content. No repository, benchmark output or source is changed.
    """
    try:
        _, inference = _verified_artifacts(root)
        observations: list[BoundObservation] = []
        gaps: list[BoundGapEvent] = []
        for logical_id, contents in sorted(inference.items()):
            if PurePosixPath(logical_id).name == "observations.json":
                aggregation = ObservationAggregation.model_validate_json(contents)
                observations.extend(aggregation.observations)
            else:
                gaps.append(BoundGapEvent.model_validate_json(contents))
        return RepositorySnapshot(observations=tuple(observations), gaps=tuple(gaps))
    except (OSError, ValidationError) as error:
        raise BenchmarkImportError(
            "benchmark package violates its artifact/schema contract"
        ) from error


def load_replay_config(root: Path) -> Path:
    """Return the verified replay locator; never execute replay or load evaluation data.

    This path is a locator verified at lookup time, not a promise that another
    process cannot later modify its contents. Call again to recheck the package.
    """
    try:
        verified_root, _ = _verified_artifacts(root)
        return _contained_path(verified_root, "replay/config.json")
    except (OSError, ValidationError) as error:
        raise BenchmarkImportError(
            "benchmark package violates its artifact/schema contract"
        ) from error
