"""Resolve and fingerprint explicitly versioned local experiment inputs."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from pathlib import Path

from amidst.domain.experiment import (
    ArtifactReference,
    DatasetManifest,
    ExperimentConfig,
    GitRevision,
    InputFingerprint,
)

PIPELINE_VERSION = "phase1-dataset-infrastructure-v1"


def fingerprint(path: Path, logical_id: str) -> InputFingerprint:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return InputFingerprint(logical_id=logical_id, sha256=digest, size_bytes=path.stat().st_size)


def resolve_reference(reference: ArtifactReference, containing_file: Path) -> Path:
    reference = ArtifactReference.model_validate(reference.model_dump(mode="python"))
    path = Path(reference.path)
    return (path if path.is_absolute() else containing_file.parent / path).resolve()


def read_reference(reference: ArtifactReference, containing_file: Path) -> str:
    path = resolve_reference(reference, containing_file)
    contents = path.read_bytes()
    if hashlib.sha256(contents).hexdigest() != reference.sha256:
        raise ValueError(f"input content hash mismatch: {reference.path}")
    return contents.decode("utf-8")


def canonical_config_hash(config: ExperimentConfig) -> str:
    config = ExperimentConfig.model_validate(config.model_dump(mode="python"))
    encoded = json.dumps(config.model_dump(mode="json"), sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_experiment(path: Path) -> tuple[ExperimentConfig, DatasetManifest, Path]:
    config = ExperimentConfig.model_validate_json(path.read_text(encoding="utf-8"))
    if config.pipeline_version != PIPELINE_VERSION:
        raise ValueError("unsupported pipeline version")
    dataset_path = resolve_reference(config.dataset_manifest, path)
    dataset = DatasetManifest.model_validate_json(read_reference(config.dataset_manifest, path))
    fields = (
        "dataset_version", "seed", "scene_version", "camera_config_version", "topology_version",
    )
    if any(getattr(config, name) != getattr(dataset, name) for name in fields):
        raise ValueError("experiment versions/seed must match the dataset manifest")
    return config, dataset, dataset_path


def git_revision(repository: Path) -> GitRevision:
    """Capture dirty state instead of presenting uncommitted code as a clean commit."""
    def git(*arguments: str) -> bytes:
        return subprocess.run(["git", "-C", str(repository), *arguments],
                              check=True, capture_output=True).stdout

    commit = git("rev-parse", "HEAD").decode().strip()
    diff = git("diff", "--binary", "HEAD", "--", "src", "scripts", "pyproject.toml", "uv.lock")
    untracked = git("ls-files", "--others", "--exclude-standard", "-z", "--", "src", "scripts")
    files = sorted(name.decode() for name in untracked.split(b"\x00") if name)
    return GitRevision(
        commit=commit, tracked_dirty=bool(diff),
        tracked_diff_sha256=hashlib.sha256(diff).hexdigest(),
        untracked_source_fingerprints=tuple(fingerprint(repository / name, name) for name in files),
        environment_lock_sha256=fingerprint(repository / "uv.lock", "uv.lock").sha256,
        python_version=platform.python_version(), pipeline_version=PIPELINE_VERSION,
    )
