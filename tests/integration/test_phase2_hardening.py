"""Bounded synthetic stress and producer-output compatibility at existing contracts.

These tests reuse Phase 1 inference outputs. They do not define alternate search,
metric, schema, production throughput, or actual pilot-data acceptance behavior.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest
from pydantic import ValidationError

from amidst.benchmark.runner import run_benchmark
from amidst.datasets.providers import BlenderDataset, MockDataset
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evidence import VisibilityStatus
from amidst.domain.stream import BoundGapEvent, ObservationAggregation, RawProjectedFrameSample
from amidst.integration.api import IntegrationApplication, encode_event_key
from amidst.integration.consumer import ConsumerEvent, ReplayFrame
from amidst.integration.contracts import EventPage, ObservationPage, RecordQuery, TrajectoryResponse
from amidst.integration.local_repository import InMemoryRepository, LocalJsonRepository
from amidst.integration.replay import load_benchmark_snapshot, load_replay_config
from amidst.integration.repositories import (
    IntegrationRepository,
    RepositoryConflictError,
    RepositorySnapshot,
)
from amidst.integration.service import MockIntegrationService
from amidst.integration.wiring import build_mock_service, build_replay_service
from amidst.observation.aggregation import AggregationInputError

ROOT = Path(__file__).resolve().parents[2]
SERVICE_CONFIG = ROOT / "configs/integration/mock_v1.json"
BENCHMARK_CONFIG = ROOT / "configs/benchmarks/mock_stream_v1.json"
STRESS_COPIES = 96


def _rename(value: Any, identities: dict[str, str]) -> Any:
    """Rename synthetic fixture identities only, never geometry or inference content."""
    if isinstance(value, dict):
        return {key: _rename(item, identities) for key, item in value.items()}
    if isinstance(value, list):
        return [_rename(item, identities) for item in value]
    if isinstance(value, str):
        return identities.get(value, value)
    return value


def _identities(value: Any) -> set[str]:
    fields = {"sample_id", "point_id", "observation_id", "candidate_id", "event_id",
              "hypothesis_id", "target_id", "source_id"}
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in fields and isinstance(item, str):
                found.add(item)
            if key == "sample_ids":
                found.update(item)
            found.update(_identities(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_identities(item))
    return found


@pytest.fixture(scope="module")
def inference_fixture() -> tuple[ObservationAggregation, BoundGapEvent]:
    service = build_mock_service(SERVICE_CONFIG, search_clock=lambda: 0.0)
    provider = service.observation_provider("branching_top_k")
    assert isinstance(provider, MockDataset)
    aggregation = provider.aggregate(provider.time_range)
    gap = next(item for item in service.repository.snapshot().gaps
               if item.binding.source_id == provider.binding.source_id)
    assert len(gap.event.candidates) > 1
    assert len(gap.event.trajectories) > len(gap.event.candidates)
    return aggregation, gap


def test_repeated_mock_service_builds_preserve_existing_inference_records(
    inference_fixture: tuple[ObservationAggregation, BoundGapEvent],
) -> None:
    _, gap = inference_fixture
    expected = RepositorySnapshot(observations=(gap.start, gap.end), gaps=(gap,))
    for _ in range(3):
        service = build_mock_service(SERVICE_CONFIG, search_clock=lambda: 0.0)
        query = RecordQuery(time_range=(0, 100), source_id=gap.binding.source_id)
        assert service.observations(query).items == expected.observations
        assert service.events(query).items == expected.gaps
        assert service.consumer(gap.event.event_id).gap == gap


def _copy_inference(
    fixture: tuple[ObservationAggregation, BoundGapEvent], index: int,
) -> tuple[ObservationAggregation, BoundGapEvent]:
    aggregation, gap = fixture
    evidence = aggregation.model_dump(mode="json")
    event = gap.model_dump(mode="json")
    identities = {identity: f"SYNTHETIC:stress/{index:04d}/第%/{identity}"
                  for identity in _identities([evidence, event])}
    return (
        ObservationAggregation.model_validate(_rename(evidence, identities)),
        BoundGapEvent.model_validate(_rename(event, identities)),
    )


@pytest.fixture(scope="module")
def large_snapshot(
    inference_fixture: tuple[ObservationAggregation, BoundGapEvent],
) -> RepositorySnapshot:
    copies = [_copy_inference(inference_fixture, index) for index in range(STRESS_COPIES)]
    return RepositorySnapshot(
        observations=tuple(item for aggregation, _ in copies for item in aggregation.observations),
        gaps=tuple(gap for _, gap in copies),
    )


def _event_payloads(service: MockIntegrationService, gap: BoundGapEvent) -> dict[str, str]:
    application = IntegrationApplication(service)
    path = "/v1/events/" + encode_event_key(gap.event.event_id)
    requests = [(path + suffix, "") for suffix in ("", "/trajectories", "/consumer")]
    start, end = gap.event.time_range
    requests.extend((path + "/replay", urlencode({"timestamp": time}))
                    for time in (start, (start + end) / 2, end))
    result = {}
    for route, query in requests:
        status, response = application.handle("GET", route, query)
        assert status == 200
        contents = response.model_dump_json()
        assert "GROUND_TRUTH" not in contents
        result[route + "?" + query] = contents
    return result


@pytest.mark.parametrize("backend", ["memory", "local"])
def test_bounded_repository_api_stress_is_lossless_and_repeated_runs_are_stable(
    backend: str, tmp_path: Path, large_snapshot: RepositorySnapshot,
) -> None:
    store = tmp_path / "nested" / "records.json"
    repository: IntegrationRepository = (
        InMemoryRepository() if backend == "memory" else LocalJsonRepository(store)
    )
    batches = [RepositorySnapshot(observations=(gap.start, gap.end), gaps=(gap,))
               for gap in large_snapshot.gaps]
    # Reversed publication order is deliberately distinct from canonical query order.
    reversed_batches = list(reversed(batches))
    for offset in range(0, len(reversed_batches), 16):
        group = reversed_batches[offset:offset + 16]
        repository.add(RepositorySnapshot(
            observations=tuple(item for batch in group for item in batch.observations),
            gaps=tuple(item for batch in group for item in batch.gaps),
        ))
    service = MockIntegrationService(repository)
    query = RecordQuery(time_range=(0, 100))
    expected_observations = service.observations(query)
    expected_events = service.events(query)
    assert len(expected_observations.items) == 2 * STRESS_COPIES
    assert len(expected_events.items) == STRESS_COPIES
    assert expected_events.items == large_snapshot.gaps
    expected = {gap.event.event_id: _event_payloads(service, gap)
                for gap in (large_snapshot.gaps[0], large_snapshot.gaps[-1])}
    before = store.read_bytes() if backend == "local" else None
    for _ in range(3):
        repository.add(large_snapshot)
        if backend == "local":
            repository = LocalJsonRepository(store)
        service = MockIntegrationService(repository)
        assert service.observations(query) == expected_observations
        assert service.events(query) == expected_events
        for gap in (large_snapshot.gaps[0], large_snapshot.gaps[-1]):
            assert _event_payloads(service, gap) == expected[gap.event.event_id]
        if before is not None:
            assert store.read_bytes() == before
    # Filters remain closed/inclusive and preserve original endpoint records.
    application = IntegrationApplication(service)
    gap = large_snapshot.gaps[STRESS_COPIES // 2]
    query_string = urlencode({"start": gap.event.time_range[0], "end": gap.event.time_range[0],
                              "source_id": gap.binding.source_id})
    status, page = application.handle("GET", "/v1/events", query_string)
    assert status == 200
    assert EventPage.model_validate_json(page.model_dump_json()).items == (gap,)
    status, page = application.handle("GET", "/v1/observations", query_string)
    assert status == 200
    assert ObservationPage.model_validate_json(page.model_dump_json()).items == (gap.start,)
    trajectories = service.trajectories(gap.event.event_id)
    assert TrajectoryResponse.model_validate_json(trajectories.model_dump_json()).hypotheses == (
        gap.event.trajectories
    )
    assert repository.snapshot().gaps == tuple(reversed(large_snapshot.gaps))


@pytest.mark.parametrize("backend", ["memory", "local"])
def test_failed_merge_after_new_record_does_not_partially_publish(
    backend: str, tmp_path: Path, inference_fixture: tuple[ObservationAggregation, BoundGapEvent],
) -> None:
    original = _copy_inference(inference_fixture, 0)[1]
    added = _copy_inference(inference_fixture, 1)[1]
    initial = RepositorySnapshot(observations=(original.start, original.end), gaps=(original,))
    store = tmp_path / "records.json"
    repository: IntegrationRepository = (
        InMemoryRepository(initial) if backend == "memory" else LocalJsonRepository(store, initial)
    )
    changed = original.model_dump(mode="json")
    changed["search_result"]["expanded_nodes"] += 1
    conflict = BoundGapEvent.model_validate(changed)
    incoming = RepositorySnapshot(
        observations=(added.start, added.end, conflict.start, conflict.end), gaps=(added, conflict),
    )
    before = store.read_bytes() if backend == "local" else None
    with pytest.raises(RepositoryConflictError, match="conflicting event"):
        repository.add(incoming)
    assert repository.snapshot() == initial
    if before is not None:
        assert store.read_bytes() == before
        assert LocalJsonRepository(store).snapshot() == initial


@pytest.mark.parametrize(
    "invalid", ["duplicate_observation", "duplicate_event", "missing_endpoint"],
)
def test_missing_or_duplicate_canonical_records_fail_before_storage(
    invalid: str, inference_fixture: tuple[ObservationAggregation, BoundGapEvent],
) -> None:
    _, gap = inference_fixture
    observations = (gap.start, gap.end)
    gaps = (gap,)
    if invalid == "duplicate_observation":
        observations = (*observations, gap.start)
    elif invalid == "duplicate_event":
        gaps = (gap, gap)
    else:
        observations = (gap.start,)
    with pytest.raises(ValidationError):
        RepositorySnapshot(observations=observations, gaps=gaps)


@pytest.fixture(scope="module")
def larger_provider_samples(
    inference_fixture: tuple[ObservationAggregation, BoundGapEvent],
) -> tuple[RawProjectedFrameSample, ...]:
    samples = inference_fixture[0].samples
    copied = []
    for index in range(384):
        payload = [item.model_dump(mode="json") for item in samples]
        identities = {identity: f"SYNTHETIC:provider:{index:04d}:{identity}"
                      for identity in _identities(payload)
                      if identity != samples[0].source_id}
        copied.extend(RawProjectedFrameSample.model_validate(item)
                      for item in _rename(payload, identities))
    assert len(copied) == 1152
    return tuple(copied)


@pytest.mark.parametrize("order", ["forward", "reverse", "interleaved"])
def test_larger_provider_input_order_preserves_every_visible_record(
    order: str, larger_provider_samples: tuple[RawProjectedFrameSample, ...],
) -> None:
    samples = larger_provider_samples
    rearranged = {
        "forward": samples,
        "reverse": tuple(reversed(samples)),
        "interleaved": samples[1::2] + samples[::2],
    }[order]
    binding = samples[0].binding
    expected = MockDataset(FrameSampleDataset(samples=samples), binding).aggregate((0, 100))
    provider = MockDataset(FrameSampleDataset(samples=rearranged), binding)
    actual = provider.aggregate((0, 100))
    assert actual == expected
    assert len(actual.observations) == 768
    visible = {item.sample_id for item in samples if item.visibility == VisibilityStatus.OBSERVED}
    assert {identity for item in actual.observations for identity in item.sample_ids} == visible
    service = MockIntegrationService(InMemoryRepository(
        RepositorySnapshot(observations=actual.observations)
    ))
    assert len(service.observations(RecordQuery(time_range=(0, 100))).items) == 768
    assert service.events(RecordQuery(time_range=(0, 100))).items == ()


@pytest.mark.parametrize("missing", ["one_visible", "all"])
def test_missing_provider_input_never_invents_evidence_or_events(
    missing: str, larger_provider_samples: tuple[RawProjectedFrameSample, ...],
) -> None:
    samples = larger_provider_samples
    removed = next(item for item in samples if item.visibility == VisibilityStatus.OBSERVED)
    remaining = (() if missing == "all" else tuple(
        item for item in samples if item.sample_id != removed.sample_id
    ))
    provider = MockDataset(FrameSampleDataset(samples=remaining), samples[0].binding)
    aggregation = provider.aggregate((0, 100))
    visible = {item.sample_id for item in remaining if item.visibility == VisibilityStatus.OBSERVED}
    assert {identity for item in aggregation.observations
            for identity in item.sample_ids} == visible
    assert removed.sample_id not in visible
    snapshot = RepositorySnapshot(observations=aggregation.observations)
    service = MockIntegrationService(InMemoryRepository(snapshot))
    assert service.events(RecordQuery(time_range=(0, 100))).items == ()


@pytest.mark.parametrize("duplicate", ["identity", "camera_time", "frame_id"])
def test_ambiguous_provider_input_is_rejected_without_silent_deduplication(
    duplicate: str, larger_provider_samples: tuple[RawProjectedFrameSample, ...],
) -> None:
    samples = larger_provider_samples
    original = samples[0]
    payload = original.model_dump(mode="json")
    if duplicate != "identity":
        payload["sample_id"] += ":collision"
        payload["projected_point"]["point_id"] += ":collision"
    if duplicate == "frame_id":
        payload["timestamp"] += 1
        payload["projected_point"]["timestamp"] += 1
    ambiguous = RawProjectedFrameSample.model_validate(payload)
    with pytest.raises(AggregationInputError):
        MockDataset(FrameSampleDataset(samples=(*samples, ambiguous)), samples[0].binding)


def _write_package(root: Path, aggregation: ObservationAggregation, gap: BoundGapEvent) -> None:
    """Existing Phase 1 output JSON, with opaque evaluation artifacts for hash-only proof."""
    files = {
        "cases/SYNTHETIC_pilot_like/observations.json": aggregation.model_dump_json().encode(),
        "cases/SYNTHETIC_pilot_like/gaps/independent/candidates.json": (
            gap.model_dump_json().encode()
        ),
        "experiment.json": b'{"synthetic_test_fixture":true}',
        "replay/config.json": b'{"synthetic_test_fixture":true}',
        "metrics.json": b"OPAQUE_EVALUATION_METRICS_NOT_INFERENCE",
        "evaluation/ground_truth.json": b"OPAQUE_GROUND_TRUTH_NOT_INFERENCE",
    }
    fingerprints = []
    for logical_id, contents in files.items():
        path = root / logical_id
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        fingerprints.append({"logical_id": logical_id,
                             "sha256": hashlib.sha256(contents).hexdigest(),
                             "size_bytes": len(contents)})
    manifest = {"schema_version": "1.0", "status": "COMPLETE",
                "config_sha256": "0" * 64, "files": fingerprints}
    (root / "artifacts.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_producer_neutral_synthetic_pilot_outputs_import_without_evaluation_deserialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    inference_fixture: tuple[ObservationAggregation, BoundGapEvent],
) -> None:
    original_aggregation, original_gap = inference_fixture
    payload = [item.model_dump(mode="json") for item in original_aggregation.samples]
    for sample in payload:
        sample["source_id"] = "SYNTHETIC:pilot_like_projected_export"
        sample["source_asset_sha256"] = "a" * 64
    samples = tuple(RawProjectedFrameSample.model_validate(item) for item in payload)
    provider = BlenderDataset(FrameSampleDataset(samples=samples), samples[0].binding)
    aggregation = provider.aggregate(provider.time_range)
    # Only producer/endpoint identities change; reuse the original inference output.
    identities = {original_gap.binding.source_id: provider.binding.source_id}
    for old, new in zip(original_aggregation.observations, aggregation.observations, strict=True):
        identities[old.observation.observation_id] = new.observation.observation_id
    event = _rename(original_gap.model_dump(mode="json"), identities)
    event["binding"] = provider.binding.model_dump(mode="json")
    event["start"] = aggregation.observations[0].model_dump(mode="json")
    event["end"] = aggregation.observations[1].model_dump(mode="json")
    gap = BoundGapEvent.model_validate(event)
    package = tmp_path / "producer output ü space"
    _write_package(package, aggregation, gap)
    before = {path.relative_to(package).as_posix(): path.read_bytes()
              for path in package.rglob("*") if path.is_file()}
    monkeypatch.chdir(tmp_path)
    imported = build_replay_service(Path(package.name))
    expected = RepositorySnapshot(observations=aggregation.observations, gaps=(gap,))
    assert imported.repository.snapshot() == expected
    assert load_replay_config(Path(package.name)) == package / "replay/config.json"
    _event_payloads(imported, gap)
    assert "OPAQUE_" not in imported.repository.snapshot().model_dump_json()
    assert {path.relative_to(package).as_posix(): path.read_bytes()
            for path in package.rglob("*") if path.is_file()} == before


def test_existing_benchmark_package_relocates_and_imports_outside_repository_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run only after production edits settle: benchmark provenance fingerprints source."""
    generated = tmp_path / "benchmark"
    run_benchmark(BENCHMARK_CONFIG, generated, search_clock=lambda: 0.0,
                  runtime_clock=lambda: 0.0)
    original = load_benchmark_snapshot(generated)
    relocated = tmp_path / "unrelated cwd" / "outputs ü" / "portable package"
    relocated.parent.mkdir(parents=True)
    shutil.copytree(generated, relocated)
    monkeypatch.chdir(relocated.parent)
    assert load_benchmark_snapshot(Path(relocated.name)) == original
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    script = (
        "import sys; from pathlib import Path;"
        "from amidst.integration.replay import load_benchmark_snapshot;"
        "print(load_benchmark_snapshot(Path(sys.argv[1])).model_dump_json())"
    )
    result = subprocess.run([sys.executable, "-c", script, relocated.name],
                            cwd=relocated.parent, env=environment,
                            check=True, capture_output=True, text=True)
    assert RepositorySnapshot.model_validate_json(result.stdout) == original


def test_typescript_consumer_stress_preserves_every_alternative_and_replay_order(
    tmp_path: Path, large_snapshot: RepositorySnapshot, node_with_typescript: str,
) -> None:
    node = node_with_typescript
    payloads = []
    for gap in large_snapshot.gaps:
        # Validate all records using bounded isolated views, avoiding quadratic scans.
        snapshot = RepositorySnapshot(observations=(gap.start, gap.end), gaps=(gap,))
        service = MockIntegrationService(InMemoryRepository(snapshot))
        consumer = service.consumer(gap.event.event_id)
        frames: list[ReplayFrame] = []
        # Call the API contract for start/midpoint/end, preserving all alternatives.
        application = IntegrationApplication(service)
        path = "/v1/events/" + encode_event_key(gap.event.event_id)
        for timestamp in (gap.event.time_range[0], sum(gap.event.time_range) / 2,
                          gap.event.time_range[1]):
            status, response = application.handle("GET", path + "/replay",
                                                  urlencode({"timestamp": timestamp}))
            assert status == 200
            frames.append(ReplayFrame.model_validate_json(response.model_dump_json()))
        assert ConsumerEvent.model_validate_json(consumer.model_dump_json()).gap == gap
        payloads.append({"consumer": consumer.model_dump(mode="json"),
                         "frames": [frame.model_dump(mode="json") for frame in frames],
                         "path": path})
    fixture = tmp_path / "consumer-responses.json"
    fixture.write_text(json.dumps(payloads), encoding="utf-8")
    script = (
        "import {readFileSync} from 'node:fs';"
        "import {strict as assert} from 'node:assert';"
        "import {eventPath,validateConsumerEvent,validateReplayFrame,WORLD_UP} from "
        + json.dumps((ROOT / "frontend/phase2/consumer.ts").as_uri()) + ";"
        "let eventCount=0,frameCount=0;"
        "for (const item of JSON.parse(readFileSync(process.argv[1],'utf8'))) {"
        "const before=JSON.stringify(item); const event=validateConsumerEvent(item.consumer);"
        "assert.equal(event,item.consumer); assert.equal(eventPath(event.gap.event.event_id),"
        "item.path); for (const frame of item.frames) {"
        "assert.equal(validateReplayFrame(frame,event),frame);"
        "assert.deepEqual(frame.markers.map(x=>x.hypothesis_id),"
        "event.gap.event.trajectories.map(x=>x.hypothesis_id)); frameCount++; }"
        "assert.equal(JSON.stringify(item),before); eventCount++; }"
        "assert.deepEqual(WORLD_UP,[0,0,1]);"
        "console.log(JSON.stringify({eventCount,frameCount}));"
    )
    result = subprocess.run([node, "--input-type=module", "-e", script, str(fixture)],
                            check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == {"eventCount": STRESS_COPIES,
                                       "frameCount": 3 * STRESS_COPIES}
    assert len(payloads) == STRESS_COPIES
    assert service.repository.snapshot().gaps == (large_snapshot.gaps[-1],)
