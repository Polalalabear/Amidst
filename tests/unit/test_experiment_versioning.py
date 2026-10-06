"""Explicit versions plus content digests, independent of dataset geometry."""

import errno
import hashlib
import json
import os
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError

import amidst.experiments.versioning as versioning_module
from amidst.domain.experiment import ArtifactReference, DatasetManifest, ExperimentConfig
from amidst.experiments.versioning import (
    PIPELINE_VERSION,
    canonical_config_hash,
    fingerprint,
    git_revision,
    load_experiment,
    read_local_bytes,
    read_reference,
    resolve_reference,
)


def _config(tmp_path: Path) -> tuple[Path, ExperimentConfig]:
    versions = dict(
        dataset_version="mock-v1",
        seed=20261001,
        scene_version="scene-v1",
        camera_config_version="camera-v1",
        topology_version="topology-v1",
    )
    reference = ArtifactReference(path="file.json", sha256="0" * 64)
    dataset = DatasetManifest(
        dataset_id="test",
        provider_kind="MOCK_JSON",
        **versions,
        cases=(
            {
                "case_id": "one",
                "source_id": "source",
                "spatial_context_id": "space",
                "pipeline": reference,
                "frames": reference,
            },
        ),
    )
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(dataset.model_dump_json(indent=2))
    config = ExperimentConfig(
        experiment_id="run",
        **versions,
        metric_config_version="metrics-v1",
        pipeline_version=PIPELINE_VERSION,
        dataset_manifest=ArtifactReference(
            path="dataset.json", sha256=hashlib.sha256(dataset_path.read_bytes()).hexdigest()
        ),
        metric_config=reference,
    )
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


@pytest.mark.parametrize(
    "field,value",
    [
        ("dataset_version", "other"),
        ("seed", 42),
        ("scene_version", "other"),
        ("camera_config_version", "other"),
        ("topology_version", "other"),
        ("pipeline_version", "other"),
    ],
)
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


def test_character_device_inputs_are_rejected_before_reading() -> None:
    device = Path(os.devnull)
    if not device.exists() or not stat.S_ISCHR(device.stat().st_mode):
        pytest.skip("the host does not expose a stat-able null character device")
    reference = ArtifactReference(path=str(device), sha256=hashlib.sha256(b"").hexdigest())
    with pytest.raises(ValueError, match="regular files"):
        read_reference(reference, device.parent / "config.json")
    with pytest.raises(ValueError, match="regular files"):
        fingerprint(device, "device")
    with pytest.raises(ValueError, match="regular files"):
        load_experiment(device)
    with pytest.raises(ValueError, match="regular files"):
        read_local_bytes(device)


def test_fifo_inputs_are_rejected_without_waiting_for_a_writer(tmp_path: Path) -> None:
    fifo = tmp_path / "input.fifo"
    if not hasattr(os, "mkfifo"):
        pytest.skip("the host does not support POSIX FIFO creation")
    try:
        os.mkfifo(fifo)
    except OSError as error:
        if error.errno not in {errno.EPERM, errno.EACCES, errno.ENOSYS, errno.ENOTSUP}:
            raise
        pytest.skip(f"the test filesystem does not support FIFOs: {error}")
    reference = ArtifactReference(path=fifo.name, sha256="0" * 64)
    with pytest.raises(ValueError, match="regular files"):
        read_reference(reference, tmp_path / "config.json")
    with pytest.raises(ValueError, match="regular files"):
        fingerprint(fifo, "fifo")
    with pytest.raises(ValueError, match="regular files"):
        load_experiment(fifo)


def test_regular_symlinks_and_parent_directory_references_remain_supported(tmp_path: Path) -> None:
    parent_file = tmp_path / "input.json"
    parent_file.write_text('{"source": "configured"}')
    nested = tmp_path / "configs"
    nested.mkdir()
    link = nested / "input-link.json"
    try:
        link.symlink_to(parent_file)
    except NotImplementedError:
        pytest.skip("the host does not implement symlinks")
    except OSError as error:
        if error.errno not in {errno.EPERM, errno.EACCES, errno.ENOSYS, errno.ENOTSUP}:
            raise
        pytest.skip(f"the host/test filesystem does not support symlinks: {error}")
    digest = hashlib.sha256(parent_file.read_bytes()).hexdigest()
    for path in ("../input.json", "input-link.json"):
        reference = ArtifactReference(path=path, sha256=digest)
        assert read_reference(reference, nested / "config.json") == parent_file.read_text()
    assert fingerprint(link, "symlink").sha256 == digest


def test_opened_fifo_is_rechecked_if_the_path_changed_after_stat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    regular = tmp_path / "regular.json"
    regular.write_text("{}")
    fifo = tmp_path / "swapped.fifo"
    if not hasattr(os, "mkfifo"):
        pytest.skip("the host does not support POSIX FIFO creation")
    try:
        os.mkfifo(fifo)
    except OSError as error:
        if error.errno not in {errno.EPERM, errno.EACCES, errno.ENOSYS, errno.ENOTSUP}:
            raise
        pytest.skip(f"the test filesystem does not support FIFOs: {error}")
    if not hasattr(os, "O_NONBLOCK"):
        pytest.skip("the host has no nonblocking FIFO open flag")
    original_open = os.open
    descriptors: list[int] = []

    def swapped_open(path: Path, flags: int) -> int:
        assert flags & os.O_NONBLOCK
        descriptor = original_open(fifo, flags)
        descriptors.append(descriptor)
        return descriptor

    monkeypatch.setattr(versioning_module.os, "open", swapped_open)
    with pytest.raises(ValueError, match="regular files"):
        read_local_bytes(regular)
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
