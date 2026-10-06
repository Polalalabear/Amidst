"""Existing mock providers and portable replay traverse the entire Phase 2 boundary."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import amidst.datasets.loading as dataset_loading
import amidst.integration.wiring as wiring
from amidst.benchmark.runner import BenchmarkResult, run_benchmark
from amidst.datasets.providers import MockDataset
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.experiment import ArtifactReference
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.stream import BoundGapEvent, RawProjectedFrameSample
from amidst.domain.trajectory import TerminationReason
from amidst.events import reconstruct_gaps
from amidst.experiments.versioning import load_experiment
from amidst.integration.api import IntegrationApplication, encode_event_key
from amidst.integration.consumer import ConsumerEvent, ReplayFrame
from amidst.integration.contracts import EventPage, RecordQuery, TrajectoryResponse
from amidst.integration.local_repository import InMemoryRepository, LocalJsonRepository
from amidst.integration.replay import (
    BenchmarkImportError,
    load_benchmark_snapshot,
    load_replay_config,
)
from amidst.integration.repositories import IntegrationRepository, RepositorySnapshot
from amidst.integration.service import MockIntegrationService
from amidst.integration.wiring import build_mock_service, build_replay_service

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_CONFIG = ROOT / "configs/benchmarks/mock_stream_v1.json"
SERVICE_CONFIG = ROOT / "configs/integration/mock_v1.json"
CASES = ("single_path", "branching_top_k", "temporal_slack", "simplified_stair")


@pytest.fixture(scope="module")
def benchmark_package(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, BenchmarkResult]:
    output = tmp_path_factory.mktemp("phase2_benchmark") / "output"
    result = run_benchmark(BENCHMARK_CONFIG, output, search_clock=lambda: 0.0,
                           runtime_clock=lambda: 0.0)
    return output, result


@pytest.mark.parametrize("case_id", CASES)
def test_provider_repository_api_consumer_and_replay_match_existing_benchmark(
    case_id: str, benchmark_package: tuple[Path, BenchmarkResult],
) -> None:
    output, benchmark = benchmark_package
    original = next(case for case in benchmark.cases if case.case_id == case_id)
    direct = build_mock_service(SERVICE_CONFIG, search_clock=lambda: 0.0)
    imported = build_replay_service(output)
    query = RecordQuery(
        time_range=(0, max(
            item.observation.end_time for item in original.aggregation.observations
        )),
        source_id=f"mock:{case_id}",
    )
    for service in (direct, imported):
        assert service.observations(query).items == original.aggregation.observations
        assert service.events(query).items == tuple(result.gap for result in original.gaps)
        for result in original.gaps:
            gap = result.gap
            original_json = gap.model_dump_json()
            application = IntegrationApplication(service)
            path = "/v1/events/" + encode_event_key(gap.event.event_id)
            status, response = application.handle("GET", path + "/consumer")
            assert status == 200
            consumer = ConsumerEvent.model_validate_json(response.model_dump_json())
            assert consumer.gap == gap
            status, response = application.handle("GET", path + "/trajectories")
            assert status == 200
            trajectories = TrajectoryResponse.model_validate_json(response.model_dump_json())
            assert trajectories.candidates == gap.event.candidates
            assert trajectories.hypotheses == gap.event.trajectories
            assert trajectories.complete == gap.search_result.complete
            assert all(candidate.path_score is None for candidate in trajectories.candidates)
            midpoint = sum(gap.event.time_range) / 2
            status, response = application.handle("GET", path + "/replay",
                                                   f"timestamp={midpoint}")
            assert status == 200
            frame = ReplayFrame.model_validate_json(response.model_dump_json())
            assert tuple(marker.hypothesis_id for marker in frame.markers) == tuple(
                hypothesis.hypothesis_id for hypothesis in gap.event.trajectories
            )
            assert "GROUND_TRUTH" not in response.model_dump_json()
            assert gap.model_dump_json() == original_json
    assert load_replay_config(output) == output / "replay/config.json"


def test_existing_portable_replay_relocates_and_preserves_metrics_and_api_outputs(
    tmp_path: Path, benchmark_package: tuple[Path, BenchmarkResult],
) -> None:
    output, first = benchmark_package
    relocated = tmp_path / "relocated"
    shutil.copytree(output, relocated)
    replayed = tmp_path / "replayed"
    second = run_benchmark(load_replay_config(relocated), replayed,
                           search_clock=lambda: 0.0, runtime_clock=lambda: 0.0)
    assert second.cases == first.cases
    assert (relocated / "metrics.json").read_bytes() == (replayed / "metrics.json").read_bytes()
    original_service = build_replay_service(relocated)
    replay_service = build_replay_service(replayed)
    query = RecordQuery(time_range=(0, max(
        item.observation.end_time for item in original_service.repository.snapshot().observations
    )))
    assert original_service.events(query).model_dump_json() == (
        replay_service.events(query).model_dump_json()
    )
    assert original_service.observations(query) == replay_service.observations(query)


@pytest.mark.parametrize("backend", ["memory", "local"])
def test_storage_adapter_swap_is_lossless_and_idempotent(
    backend: str, tmp_path: Path, benchmark_package: tuple[Path, BenchmarkResult],
) -> None:
    snapshot = load_benchmark_snapshot(benchmark_package[0])
    repository: IntegrationRepository = (
        InMemoryRepository() if backend == "memory"
        else LocalJsonRepository(tmp_path / "store.json")
    )
    repository.add(snapshot)
    repository.add(snapshot)
    assert repository.snapshot() == snapshot
    service = MockIntegrationService(repository)
    assert all(service.event(gap.event.event_id).gap == gap for gap in snapshot.gaps)


def test_narrow_provider_queries_remain_distinct_from_stored_canonical_event_endpoints() -> None:
    config, dataset, manifest = load_experiment(BENCHMARK_CONFIG)
    case = next(case for case in dataset.cases if case.case_id == "single_path")
    provider, pipeline = dataset_loading.load_dataset_case(dataset, case, manifest)
    samples = provider.get_frame_samples(None, provider.time_range)
    first = samples[0]
    assert first.projected_point is not None
    earlier = first.model_dump(mode="json")
    earlier.update(sample_id="SYNTHETIC:extra-visible-sample", timestamp=9, frame_id=100)
    earlier["projected_point"].update(timestamp=9, point_id="SYNTHETIC:extra-projected-point")
    augmented = MockDataset(
        FrameSampleDataset(samples=(RawProjectedFrameSample.model_validate(earlier), *samples)),
        provider.binding,
    )
    aggregation = augmented.aggregate(augmented.time_range, config.aggregation_policy)
    gaps = reconstruct_gaps(aggregation, pipeline, dataset_id=case.case_id,
                            random_seed=config.seed, clock=lambda: 0.0)
    snapshot = RepositorySnapshot(observations=aggregation.observations, gaps=gaps)
    service = MockIntegrationService(InMemoryRepository(snapshot), {case.case_id: augmented})
    start = gaps[0].start
    clipped = service.provider_observations(case.case_id, start.observation.camera_id, (10, 10))
    assert clipped[0].observation_id != start.observation.observation_id
    page = service.observations(RecordQuery(
        time_range=(10, 10), camera_id=start.observation.camera_id,
    ))
    assert page.items == (start,)
    assert page.items[0].observation.start_time == 9
    assert service.event(gaps[0].event.event_id).gap.start == start


def test_service_and_importer_do_not_deserialize_evaluation_ground_truth(
    monkeypatch: pytest.MonkeyPatch, benchmark_package: tuple[Path, BenchmarkResult],
) -> None:
    original_read = dataset_loading.read_reference
    reads: list[str] = []

    def inference_read(reference: ArtifactReference, parent: Path) -> str:
        path = reference.path
        reads.append(path)
        assert "ground_truth" not in path
        return original_read(reference, parent)

    def reject_truth(*args: object, **kwargs: object) -> None:
        raise AssertionError("Phase 2 service must not deserialize evaluation truth")

    monkeypatch.setattr(dataset_loading, "read_reference", inference_read)
    monkeypatch.setattr(wiring, "read_reference", inference_read)
    monkeypatch.setattr(GroundTruthTrajectory, "model_validate_json", reject_truth)
    direct = build_mock_service(SERVICE_CONFIG, search_clock=lambda: 0.0)
    imported = build_replay_service(benchmark_package[0])
    query = RecordQuery(time_range=(0, max(
        item.observation.end_time for item in direct.repository.snapshot().observations
    )))
    assert direct.events(query) == imported.events(query)
    assert reads and all("ground_truth" not in path for path in reads)


@pytest.mark.parametrize("reason", [
    TerminationReason.MAX_SEARCH_NODES, TerminationReason.NO_FEASIBLE_PATH,
])
def test_api_preserves_incomplete_and_empty_search_without_inventing_success(
    reason: TerminationReason, benchmark_package: tuple[Path, BenchmarkResult],
) -> None:
    original = benchmark_package[1].cases[0].gaps[0].gap
    payload = original.model_dump(mode="json")
    complete = reason == TerminationReason.NO_FEASIBLE_PATH
    payload["search_result"].update(termination_reason=reason, complete=complete)
    payload["event"]["termination_reason"] = reason
    if complete:
        payload["search_result"]["candidates"] = []
        payload["event"].update(candidates=[], trajectories=[])
    gap = BoundGapEvent.model_validate(payload)
    snapshot = RepositorySnapshot(observations=(gap.start, gap.end), gaps=(gap,))
    application = IntegrationApplication(MockIntegrationService(InMemoryRepository(snapshot)))
    path = "/v1/events/" + encode_event_key(gap.event.event_id)
    status, response = application.handle("GET", path + "/consumer")
    assert status == 200
    assert ConsumerEvent.model_validate_json(response.model_dump_json()).gap == gap
    status, response = application.handle("GET", path + "/trajectories")
    assert status == 200
    assert TrajectoryResponse.model_validate_json(response.model_dump_json()).complete == complete
    for time in (gap.event.time_range[0] - 1, gap.event.time_range[1] + 1):
        assert application.handle("GET", path + "/replay", f"timestamp={time}")[0] == 400


def test_tampered_benchmark_is_rejected_before_repository_mutation(
    tmp_path: Path, benchmark_package: tuple[Path, BenchmarkResult],
) -> None:
    altered = tmp_path / "altered"
    shutil.copytree(benchmark_package[0], altered)
    candidate = next(altered.glob("cases/*/gaps/*/candidates.json"))
    candidate.write_bytes(candidate.read_bytes() + b" ")
    repository = InMemoryRepository()
    with pytest.raises(BenchmarkImportError, match="digest/size"):
        repository.add(load_benchmark_snapshot(altered))
    assert repository.snapshot() == RepositorySnapshot()


def test_cli_emits_current_json_contract_and_mock_events() -> None:
    command = [sys.executable, "-m", "amidst.integration", "--config", str(SERVICE_CONFIG)]
    schema = subprocess.run([*command, "--contract"], check=True, capture_output=True, text=True)
    contract = json.loads(schema.stdout)
    assert len(contract["endpoints"]) == 7
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    assert len(EventPage.model_validate_json(result.stdout).items) == 4


def test_typescript_consumes_serialized_backend_consumer_and_replay_responses(
    tmp_path: Path, benchmark_package: tuple[Path, BenchmarkResult],
    node_with_typescript: str,
) -> None:
    node = node_with_typescript
    application = IntegrationApplication(build_replay_service(benchmark_package[0]))
    payloads = []
    for gap in application.service.repository.snapshot().gaps:
        path = "/v1/events/" + encode_event_key(gap.event.event_id)
        consumer_status, consumer = application.handle("GET", path + "/consumer")
        frame_status, frame = application.handle("GET", path + "/replay",
                                                 f"timestamp={sum(gap.event.time_range) / 2}")
        assert consumer_status == frame_status == 200
        payloads.append({"consumer": json.loads(consumer.model_dump_json()),
                         "frame": json.loads(frame.model_dump_json()), "path": path})
    fixture = tmp_path / "api-responses.json"
    fixture.write_text(json.dumps(payloads))
    script = (
        "import {readFileSync} from 'node:fs';"
        "import {strict as assert} from 'node:assert';"
        "import {eventPath,validateConsumerEvent,validateReplayFrame} from "
        + json.dumps((ROOT / "frontend/phase2/consumer.ts").as_uri()) + ";"
        "for (const item of JSON.parse(readFileSync(process.argv[1], 'utf8'))) {"
        "const event=validateConsumerEvent(item.consumer);"
        "validateReplayFrame(item.frame,event);"
        "assert.equal(eventPath(event.gap.event.event_id),item.path);"
        "}"
    )
    subprocess.run([node, "--input-type=module", "-e", script, str(fixture)],
                   check=True, capture_output=True, text=True)
