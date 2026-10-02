"""Freeze regressions for evaluation isolation and read-only integration consumers."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import rerun as rr

import amidst.integration.wiring as wiring
from amidst.benchmark.runner import run_benchmark
from amidst.datasets.providers import MockDataset
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.integration.api import IntegrationApplication, encode_event_key
from amidst.integration.local_repository import InMemoryRepository, LocalJsonRepository
from amidst.integration.replay import load_benchmark_snapshot
from amidst.integration.repositories import IntegrationRepository
from amidst.integration.service import MockIntegrationService
from amidst.integration.wiring import build_mock_service, build_replay_service
from amidst.visualization import RerunDebugVisualizationAdapter

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_CONFIG = ROOT / "configs/benchmarks/mock_stream_v1.json"
SERVICE_CONFIG = ROOT / "configs/integration/mock_v1.json"


@pytest.fixture(scope="module")
def freeze_benchmark(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("phase2_freeze_benchmark") / "output"
    run_benchmark(BENCHMARK_CONFIG, output, search_clock=lambda: 0.0,
                  runtime_clock=lambda: 0.0)
    return output


def _rewrite_json(path: Path, payload: object) -> str:
    contents = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    path.write_bytes(contents)
    return hashlib.sha256(contents).hexdigest()


def _api_payloads(service: MockIntegrationService) -> dict[str, str]:
    """Capture every advertised GET route, including all replay alternatives."""
    application = IntegrationApplication(service)
    snapshot = service.repository.snapshot()
    end = max(item.observation.end_time for item in snapshot.observations)
    requests = [
        ("/v1/contract", ""),
        ("/v1/observations", f"start=0&end={end}"),
        ("/v1/events", f"start=0&end={end}"),
    ]
    for gap in snapshot.gaps:
        path = "/v1/events/" + encode_event_key(gap.event.event_id)
        requests.extend((path + suffix, "") for suffix in ("", "/trajectories", "/consumer"))
        start, finish = gap.event.time_range
        requests.extend((path + "/replay", f"timestamp={timestamp}")
                        for timestamp in (start, (start + finish) / 2, finish))
    payloads = {}
    for path, query in requests:
        status, response = application.handle("GET", path, query)
        assert status == 200
        payloads[path + "?" + query] = response.model_dump_json()
    return payloads


@pytest.mark.parametrize("changed_input", ["ground_truth", "metric_config"])
def test_changed_evaluation_inputs_and_metrics_preserve_all_api_inference_records(
    changed_input: str, tmp_path: Path, freeze_benchmark: Path,
) -> None:
    """Re-evaluate temporary replay inputs; source fixtures and contracts stay fixed."""
    replay = tmp_path / "replay"
    shutil.copytree(freeze_benchmark / "replay", replay)
    config_path = replay / "config.json"
    config = json.loads(config_path.read_text())
    dataset_path = replay / config["dataset_manifest"]["path"]
    dataset = json.loads(dataset_path.read_text())
    if changed_input == "ground_truth":
        case = next(case for case in dataset["cases"] if case["case_id"] == "branching_top_k")
        reference = case["evaluation_references"][0]
        truth_path = replay / reference["path"]
        truth = json.loads(truth_path.read_text())
        for sample in truth["samples"]:
            sample["position"][1] += 100
        reference["sha256"] = _rewrite_json(truth_path, truth)
        config["dataset_manifest"]["sha256"] = _rewrite_json(dataset_path, dataset)
    else:
        reference = config["metric_config"]
        metric_path = replay / reference["path"]
        metrics = json.loads(metric_path.read_text())
        metrics["k_values"] = [1]
        reference["sha256"] = _rewrite_json(metric_path, metrics)
    _rewrite_json(config_path, config)
    changed_output = tmp_path / "changed_output"
    run_benchmark(config_path, changed_output, search_clock=lambda: 0.0,
                  runtime_clock=lambda: 0.0)
    assert (freeze_benchmark / "metrics.json").read_bytes() != (
        changed_output / "metrics.json"
    ).read_bytes()
    original = build_replay_service(freeze_benchmark)
    changed = build_replay_service(changed_output)
    assert original.repository.snapshot() == changed.repository.snapshot()
    assert _api_payloads(original) == _api_payloads(changed)


def test_repeated_api_reads_do_not_rerun_inference_or_reload_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = build_mock_service(SERVICE_CONFIG, search_clock=lambda: 0.0)
    original_snapshot = service.repository.snapshot().model_dump_json()
    expected = _api_payloads(service)

    def reject_inference(*args: object, **kwargs: object) -> None:
        raise AssertionError("a read-only API request reran inference or loaded input data")

    monkeypatch.setattr(wiring, "reconstruct_gaps", reject_inference)
    monkeypatch.setattr(wiring, "load_dataset_case", reject_inference)
    monkeypatch.setattr(wiring, "load_benchmark_snapshot", reject_inference)
    monkeypatch.setattr(MockDataset, "aggregate", reject_inference)
    monkeypatch.setattr(MockDataset, "get_observations", reject_inference)
    for _ in range(3):
        assert _api_payloads(service) == expected
        assert service.repository.snapshot().model_dump_json() == original_snapshot


class _DebugSink:
    """Inject the existing visualization boundary without files or viewer processes."""

    def __init__(self) -> None:
        self.paths: list[str] = []

    def log(self, entity_path: str, entity: rr.AsComponents, *, static: bool = False) -> None:
        self.paths.append(entity_path)

    def set_time(self, timeline: str, *, duration: float) -> None:
        pass

    def save(self, path: str | Path) -> None:
        pass

    def flush(self) -> None:
        pass

    def disconnect(self) -> None:
        pass


@pytest.mark.parametrize("backend", ["memory", "local"])
def test_replay_and_debug_overlays_leave_stored_events_and_local_bytes_unchanged(
    backend: str, tmp_path: Path, freeze_benchmark: Path,
) -> None:
    snapshot = load_benchmark_snapshot(freeze_benchmark)
    store = tmp_path / "store.json"
    repository: IntegrationRepository = (
        InMemoryRepository(snapshot) if backend == "memory"
        else LocalJsonRepository(store, snapshot)
    )
    service = MockIntegrationService(repository)
    original_snapshot = repository.snapshot().model_dump_json()
    original_disk = store.read_bytes() if store.exists() else None
    original_api = _api_payloads(service)
    gap = next(gap for gap in snapshot.gaps if gap.binding.source_id == "mock:branching_top_k")
    original_gap = gap.model_dump_json()
    truth = GroundTruthTrajectory.model_validate_json(
        (ROOT / "data/mock/branching_top_k/ground_truth.json").read_text()
    )
    payload = truth.model_dump(mode="json")
    for sample in payload["samples"]:
        sample["position"][1] += 100
    altered_truth = GroundTruthTrajectory.model_validate(payload)
    sink = _DebugSink()
    adapter = RerunDebugVisualizationAdapter(
        observations=(gap.start.observation, gap.end.observation),
        recording=sink, debug_mode=True,
    )
    try:
        adapter.log_event(gap.event)
        adapter.log_debug_ground_truth(altered_truth)
        adapter.log_metrics({"changed_evaluation_metric": 100.0})
    finally:
        adapter.close()
    assert any(path.startswith("world/debug_ground_truth/") for path in sink.paths)
    assert "debug/evaluation_metrics" in sink.paths
    assert gap.model_dump_json() == original_gap
    assert repository.snapshot().model_dump_json() == original_snapshot
    assert _api_payloads(service) == original_api
    if original_disk is not None:
        assert store.read_bytes() == original_disk
