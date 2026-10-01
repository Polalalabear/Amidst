"""Explicit versions plus content digests, independent of dataset geometry."""

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.domain.experiment import ArtifactReference, DatasetManifest, ExperimentConfig
from amidst.experiments.versioning import (
    PIPELINE_VERSION,
    canonical_config_hash,
    git_revision,
    load_experiment,
    read_reference,
    resolve_reference,
)


def _config(tmp_path: Path) -> tuple[Path, ExperimentConfig]:
    versions = dict(dataset_version="mock-v1", seed=20261001, scene_version="scene-v1",
                    camera_config_version="camera-v1", topology_version="topology-v1")
    reference = ArtifactReference(path="file.json", sha256="0" * 64)
    dataset = DatasetManifest(dataset_id="test", provider_kind="MOCK_JSON", **versions,
                             cases=({"case_id": "one", "source_id": "source",
                                     "spatial_context_id": "space", "pipeline": reference,
                                     "frames": reference},))
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(dataset.model_dump_json(indent=2))
    config = ExperimentConfig(experiment_id="run", **versions,
                              metric_config_version="metrics-v1", pipeline_version=PIPELINE_VERSION,
                              dataset_manifest=ArtifactReference(
                                  path="dataset.json",
                                  sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest()),
                              metric_config=reference)
    path = tmp_path / "config.json"
    path.write_text(config.model_dump_json(indent=2))
    return path, config


def test_config_load_versions_digest_and_stable_identity(tmp_path: Path) -> None:
    path, config = _config(tmp_path)
    loaded, dataset, dataset_path = load_experiment(path)
    assert loaded == config and dataset.seed == 20261001
    assert dataset_path == tmp_path / "dataset.json"
    assert canonical_config_hash(config) == canonical_config_hash(loaded)
    assert resolve_reference(config.dataset_manifest, path) == dataset_path
    assert read_reference(config.dataset_manifest, path) == dataset_path.read_text()
    changed = config.model_copy(update={"experiment_id": "other"})
    assert canonical_config_hash(changed) != canonical_config_hash(config)


@pytest.mark.parametrize("field,value", [
    ("dataset_version", "other"), ("seed", 42), ("scene_version", "other"),
    ("camera_config_version", "other"), ("topology_version", "other"),
    ("pipeline_version", "other"),
])
def test_mismatched_config_versions_fail(tmp_path: Path, field: str, value: str | int) -> None:
    path, config = _config(tmp_path)
    path.write_text(json.dumps(config.model_dump(mode="json") | {field: value}))
    with pytest.raises(ValueError):
        load_experiment(path)


def test_digest_tampering_and_unknown_fields_fail(tmp_path: Path) -> None:
    path, config = _config(tmp_path)
    (tmp_path / "dataset.json").write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_experiment(path)
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(config.model_dump() | {"unversioned_config": "unknown"})


def test_debug_mode_requires_rerun_and_local_artifacts(tmp_path: Path) -> None:
    _, config = _config(tmp_path)
    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(config.model_dump() | {"debug_ground_truth": True})
    with pytest.raises(ValidationError):
        ArtifactReference(path="https://example.com/data", sha256="0" * 64)


def test_real_git_metadata_is_explicit() -> None:
    repository = Path(__file__).resolve().parents[2]
    revision = git_revision(repository)
    assert len(revision.commit) == 40
    assert len(revision.environment_lock_sha256) == 64
    assert revision.pipeline_version == PIPELINE_VERSION
    assert revision == git_revision(repository)
