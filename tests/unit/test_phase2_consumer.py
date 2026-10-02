"""Lossless presentation and real TypeScript consumption of existing mock contracts."""

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.datasets.loading import load_dataset_case
from amidst.domain.common import Provenance
from amidst.domain.stream import BoundGapEvent
from amidst.domain.trajectory import HypothesisKind, TerminationReason
from amidst.events import reconstruct_gaps
from amidst.experiments.versioning import load_experiment
from amidst.integration.consumer import (
    ConsumerContractError,
    ConsumerEvent,
    ReplayFrame,
    ReplaySeek,
    replay_frame,
    to_consumer_event,
)
from amidst.observation.aggregation import AggregationInputError

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "benchmarks" / "mock_stream_v1.json"
CASES = ("single_path", "branching_top_k", "temporal_slack", "simplified_stair")
NODE = shutil.which("node")


def _gap(case_id: str = "single_path") -> BoundGapEvent:
    config, dataset, manifest = load_experiment(CONFIG)
    case = next(case for case in dataset.cases if case.case_id == case_id)
    provider, pipeline = load_dataset_case(dataset, case, manifest)
    aggregation = provider.aggregate(provider.time_range, config.aggregation_policy)
    return reconstruct_gaps(
        aggregation, pipeline, dataset_id=case.case_id, random_seed=config.seed, clock=lambda: 0.0,
    )[0]


@pytest.mark.parametrize("case_id", CASES)
def test_consumer_roundtrip_preserves_every_phase1_record(case_id: str) -> None:
    gap = _gap(case_id)
    original = gap.model_dump_json()
    consumer = to_consumer_event(gap)
    assert ConsumerEvent.model_validate_json(consumer.model_dump_json()) == consumer
    assert consumer.gap == gap
    assert consumer.gap.model_dump_json() == original
    assert consumer.time_basis == "CONFIGURED_SECONDS"
    assert consumer.coordinate_system == "BLENDER_RIGHT_HANDED_Z_UP"
    assert "GROUND_TRUTH" not in consumer.model_dump_json()


@pytest.mark.parametrize("case_id", CASES)
def test_replay_exact_keyframes_keep_provenance_and_alternative_order(case_id: str) -> None:
    gap = _gap(case_id)
    original = gap.model_dump_json()
    for timestamp in gap.event.time_range:
        frame = replay_frame(gap, timestamp)
        assert ReplayFrame.model_validate_json(frame.model_dump_json()) == frame
        assert tuple(marker.hypothesis_id for marker in frame.markers) == tuple(
            hypothesis.hypothesis_id for hypothesis in gap.event.trajectories
        )
        for marker, hypothesis in zip(frame.markers, gap.event.trajectories, strict=True):
            point = next(point for point in hypothesis.timed_points if point.timestamp == timestamp)
            assert marker.world_position == point.world_position
            assert marker.provenance == point.provenance
            assert not marker.interpolated
    assert gap.model_dump_json() == original


def test_replay_midpoint_interpolates_all_xyz_without_mutating_event() -> None:
    gap = _gap("simplified_stair")
    hypothesis = gap.event.trajectories[0]
    before, after = hypothesis.timed_points[:2]
    timestamp = (before.timestamp + after.timestamp) / 2
    original = gap.model_dump_json()
    marker = replay_frame(gap, timestamp).markers[0]
    assert marker.world_position == pytest.approx(tuple(
        (a + b) / 2 for a, b in zip(before.world_position, after.world_position, strict=True)
    ))
    assert marker.provenance == Provenance.INFERRED_GAP and marker.interpolated
    assert gap.model_dump_json() == original


def test_replay_dwell_stays_stationary_and_boundary_keeps_declared_provenance() -> None:
    gap = _gap("temporal_slack")
    dwell = next(h for h in gap.event.trajectories if h.kind == HypothesisKind.DWELL)
    segment = next(segment for segment in dwell.segments if segment.kind == "DWELL")
    timestamp = math.fsum(segment.time_range) / 2
    marker = next(marker for marker in replay_frame(gap, timestamp).markers
                  if marker.hypothesis_id == dwell.hypothesis_id)
    first = next(point for point in dwell.timed_points if point.timestamp == segment.time_range[0])
    assert marker.world_position == first.world_position
    assert marker.provenance == Provenance.INFERRED_GAP and marker.interpolated
    boundary = next(marker for marker in replay_frame(gap, segment.time_range[1]).markers
                    if marker.hypothesis_id == dwell.hypothesis_id)
    assert not boundary.interpolated
    assert boundary.provenance == next(
        point.provenance for point in dwell.timed_points if point.timestamp == segment.time_range[1]
    )


def test_incomplete_and_empty_search_contracts_remain_explicit() -> None:
    gap = _gap()
    payload = gap.model_dump(mode="json")
    payload["search_result"].update(
        termination_reason=TerminationReason.MAX_PATHS_REACHED, complete=False,
    )
    payload["event"]["termination_reason"] = TerminationReason.MAX_PATHS_REACHED
    incomplete = BoundGapEvent.model_validate(payload)
    assert not to_consumer_event(incomplete).gap.search_result.complete
    assert len(replay_frame(incomplete, 20).markers) == len(incomplete.event.trajectories)
    payload["search_result"].update(
        termination_reason=TerminationReason.NO_FEASIBLE_PATH, complete=True, candidates=[],
    )
    payload["event"].update(
        termination_reason=TerminationReason.NO_FEASIBLE_PATH, candidates=[], trajectories=[],
    )
    empty = BoundGapEvent.model_validate(payload)
    assert (
        to_consumer_event(empty).gap.event.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    )
    assert replay_frame(empty, 20).markers == ()


@pytest.mark.parametrize("timestamp", [-1, 9, 31, float("nan"), float("inf"), True, "20"])
def test_replay_rejects_invalid_or_outside_configured_time(timestamp: object) -> None:
    with pytest.raises((ValidationError, ConsumerContractError)):
        replay_frame(_gap(), timestamp)  # type: ignore[arg-type]


def test_replay_does_not_extrapolate_narrow_hypothesis() -> None:
    payload = _gap("temporal_slack").model_dump(mode="json")
    hypothesis = next(h for h in payload["event"]["trajectories"]
                      if h["kind"] != "DWELL" and h["temporal_slack"] >= 1)
    for point in hypothesis["timed_points"]:
        point["timestamp"] += 1
    hypothesis["timed_points"][-1]["timestamp"] -= 1
    for segment in hypothesis["segments"]:
        segment["time_range"][0] += 1
    hypothesis["temporal_slack"] -= 1
    hypothesis["movement_duration"] -= 1
    narrowed = BoundGapEvent.model_validate(payload)
    with pytest.raises(ConsumerContractError, match="hypothesis"):
        replay_frame(narrowed, narrowed.event.time_range[0])


@pytest.mark.parametrize("surface", ["binding", "frame"])
def test_consumer_rejects_real_cv_at_every_evidence_boundary(surface: str) -> None:
    payload = _gap().model_dump(mode="json")
    if surface == "binding":
        for binding in (payload["binding"], payload["start"]["binding"], payload["end"]["binding"]):
            binding["data_kind"] = "REAL_CV"
    else:
        observation = payload["start"]["observation"]
        observation["frames"] = [{
            "frame_id": 0, "timestamp": observation["start_time"],
            "target_id": observation["target_id"], "camera_id": observation["camera_id"],
            "status": "OBSERVED", "point_2d": [1, 2], "provenance": "OBSERVED",
            "gap_reason": None, "occluder_id": None, "data_kind": "REAL_CV",
        }]
    gap = BoundGapEvent.model_validate(payload)
    with pytest.raises(ConsumerContractError, match="SYNTHETIC"):
        to_consumer_event(gap)
    with pytest.raises(ConsumerContractError, match="SYNTHETIC"):
        replay_frame(gap, 20)
    with pytest.raises(ValidationError, match="SYNTHETIC"):
        ConsumerEvent.model_validate({"gap": payload})


def test_consumer_revalidates_unchecked_models_and_version() -> None:
    gap = _gap()
    invalid = gap.model_copy(update={"extra_truth": [1, 2, 3]})
    with pytest.raises(AggregationInputError, match="contract"):
        to_consumer_event(invalid)
    payload = to_consumer_event(gap).model_dump(mode="json")
    payload["contract_version"] = "phase2.integration.v99"
    with pytest.raises(ValidationError):
        ConsumerEvent.model_validate(payload)
    with pytest.raises(ValidationError):
        ReplaySeek(event_id="", timestamp=20)


@pytest.mark.skipif(
    NODE is None, reason="Node is required for TypeScript runtime contract coverage",
)
def test_typescript_validates_actual_python_payloads_and_rejects_corruption(tmp_path: Path) -> None:
    fixtures = []
    for case in CASES:
        gap = _gap(case)
        timestamp = math.fsum(gap.event.time_range) / 2
        fixtures.append({
            "consumer": to_consumer_event(gap).model_dump(mode="json"),
            "frame": replay_frame(gap, timestamp).model_dump(mode="json"),
            "endpoint": replay_frame(gap, gap.event.time_range[0]).model_dump(mode="json"),
        })
    fixture = tmp_path / "consumer-fixtures.json"
    fixture.write_text(json.dumps(fixtures))
    source = ROOT / "frontend" / "phase2" / "consumer.ts"
    script = f"""
import {{ readFileSync }} from 'node:fs';
import {{ strict as assert }} from 'node:assert';
import {{ validateConsumerEvent, validateReplayFrame, WORLD_UP }}
  from {json.dumps(source.as_uri())};
const fixtures = JSON.parse(readFileSync(process.argv[1], 'utf8'));
assert.deepEqual(WORLD_UP, [0, 0, 1]);
for (const fixture of fixtures) {{
  const before = JSON.stringify(fixture);
  assert.equal(validateConsumerEvent(fixture.consumer), fixture.consumer);
  assert.equal(validateReplayFrame(fixture.frame, fixture.consumer), fixture.frame);
  assert.equal(validateReplayFrame(fixture.endpoint, fixture.consumer), fixture.endpoint);
  assert.equal(JSON.stringify(fixture), before);
}}
function badConsumer(mutate) {{
  const value = structuredClone(fixtures[0].consumer); mutate(value);
  assert.throws(() => validateConsumerEvent(value), TypeError);
}}
badConsumer(v => v.contract_version = 'phase2.integration.v99');
badConsumer(v => v.gap.event.candidates[0].polyline[0][2] = Infinity);
badConsumer(v => v.gap.event.trajectories[0].timed_points[1].timestamp = 0);
badConsumer(v => v.gap.event.trajectories[0].candidate_id = 'missing');
badConsumer(v => v.gap.event.trajectories[0].timed_points[0].provenance = 'GROUND_TRUTH');
badConsumer(v => v.gap.binding.data_kind = 'REAL_CV');
badConsumer(v => v.gap.search_result.complete = false);
badConsumer(v => v.gap.start.observation.extra_truth = [1, 2, 3]);
badConsumer(v => v.gap.event.time_range[0] = 0);
for (const mutate of [
  v => v.event_id = 'missing',
  v => v.timestamp = 99,
  v => v.markers[0].candidate_id = 'missing',
  v => v.markers[0].provenance = 'OBSERVED',
  v => v.markers[0].world_position[2] = 99,
  v => v.markers = [],
]) {{
  const frame = structuredClone(fixtures[0].frame); mutate(frame);
  assert.throws(() => validateReplayFrame(frame, fixtures[0].consumer), TypeError);
}}
console.log('TypeScript consumer: 4 mock cases accepted; corrupt contracts rejected');
"""
    result = subprocess.run(
        [str(NODE), "--input-type=module", "-e", script, str(fixture)],
        check=True, capture_output=True, text=True,
    )
    assert "4 mock cases accepted" in result.stdout
