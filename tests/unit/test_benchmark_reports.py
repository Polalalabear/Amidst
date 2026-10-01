"""Reports bind portable inputs and source state instead of claiming a hash alone replays."""

import hashlib
import json
from pathlib import Path

import pytest

from amidst.benchmark.reporting import generate_reports
from amidst.benchmark.runner import run_benchmark
from amidst.domain.experiment import ArtifactReference, ExperimentConfig
from amidst.experiments.versioning import resolve_reference
from amidst.storage.json_files import write_json

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/benchmarks/mock_stream_v1.json"


def _local_config(directory: Path) -> Path:
    config = ExperimentConfig.model_validate_json(CONFIG.read_text())
    payload = config.model_dump(mode="json")
    for name in ("dataset_manifest", "metric_config"):
        reference = getattr(config, name)
        payload[name] = ArtifactReference(
            path=str(resolve_reference(reference, CONFIG)), sha256=reference.sha256,
        ).model_dump(mode="json")
    path = directory / "input.json"
    write_json(path, payload)
    return path


def test_report_snapshots_all_inputs_source_state_and_output_hashes(tmp_path: Path) -> None:
    config = _local_config(tmp_path)
    destination = tmp_path / "run"
    result = run_benchmark(config, destination, search_clock=lambda: 0.0,
                           runtime_clock=lambda: 0.0)
    artifacts = json.loads((destination / "artifacts.json").read_text())
    assert artifacts["status"] == "COMPLETE"
    assert artifacts["config_sha256"] == result.record.config_sha256
    for item in artifacts["files"]:
        path = destination / item["logical_id"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        assert path.stat().st_size == item["size_bytes"]
    for item in result.record.inputs:
        path = destination / "replay/inputs" / f"{item.sha256}.json"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item.sha256
    replay = destination / "replay"
    assert hashlib.sha256((replay / "source.patch").read_bytes()).hexdigest() == (
        result.record.git.tracked_diff_sha256
    )
    assert hashlib.sha256((replay / "uv.lock").read_bytes()).hexdigest() == (
        result.record.git.environment_lock_sha256
    )
    for item in result.record.git.untracked_source_fingerprints:
        contents = (replay / "untracked" / item.logical_id).read_bytes()
        assert hashlib.sha256(contents).hexdigest() == item.sha256
    markdown = (destination / "summary.md").read_text()
    for case in result.cases:
        assert case.case_id in markdown
    assert "minADE" in markdown and "minFDE" in markdown and "Coverage" in markdown
    assert "Collision violations" in markdown and "Constraint violations" in markdown
    assert "COMPLETE" in markdown and "runtime" in markdown
    for path in destination.glob("cases/*/gaps/*/candidates.json"):
        assert "GROUND_TRUTH" not in path.read_text()


def test_relocated_replay_uses_identical_observations_events_and_metrics(tmp_path: Path) -> None:
    config = _local_config(tmp_path)
    original = tmp_path / "original"
    first = run_benchmark(config, original, search_clock=lambda: 0.0,
                          runtime_clock=lambda: 0.0)
    relocated = tmp_path / "relocated"
    original.rename(relocated)
    second = run_benchmark(relocated / "replay/config.json", tmp_path / "replayed",
                           search_clock=lambda: 0.0, runtime_clock=lambda: 0.0)
    assert first.cases == second.cases
    assert (relocated / "metrics.json").read_bytes() == (
        tmp_path / "replayed/metrics.json"
    ).read_bytes()


def test_report_rejects_input_change_instead_of_publishing_completion(tmp_path: Path) -> None:
    config = _local_config(tmp_path)
    destination = tmp_path / "run"
    result = run_benchmark(config, destination, search_clock=lambda: 0.0)
    config.write_text(config.read_text() + " ")
    failed_report = tmp_path / "failed_report"
    with pytest.raises(ValueError, match="input changed"):
        generate_reports(result, failed_report, config_path=config,
                         manifest_path=ROOT / "data/mock/stream_v1/dataset.json")
    assert not (failed_report / "artifacts.json").exists()


def test_report_refuses_existing_snapshot_outputs(tmp_path: Path) -> None:
    config = _local_config(tmp_path)
    destination = tmp_path / "run"
    result = run_benchmark(config, destination, search_clock=lambda: 0.0)
    with pytest.raises(FileExistsError):
        generate_reports(result, destination, config_path=config,
                         manifest_path=ROOT / "data/mock/stream_v1/dataset.json")
