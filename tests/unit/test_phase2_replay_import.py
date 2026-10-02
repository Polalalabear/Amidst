"""Hash-bound additive imports reject incomplete, escaping and ambiguous packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.domain.stream import BoundGapEvent, ObservationAggregation, RawProjectedFrameSample
from amidst.domain.trajectory import (
    CandidateTrajectory,
    Event,
    HypothesisKind,
    ReconstructionResult,
    SegmentKind,
    TerminationReason,
    TimedTrajectoryPoint,
    TrajectoryHypothesis,
    TrajectorySegment,
)
from amidst.integration.replay import (
    BenchmarkImportError,
    load_benchmark_snapshot,
    load_replay_config,
)
from amidst.observation.aggregation import aggregate_frames

ROOT = Path(__file__).resolve().parents[2]
OBSERVATIONS = "cases/single_path/observations.json"
CANDIDATES = "cases/single_path/gaps/mock_gap/candidates.json"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _manifest(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "artifacts.json":
            contents = path.read_bytes()
            files.append({
                "logical_id": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(contents).hexdigest(),
                "size_bytes": len(contents),
            })
    value = {
        "schema_version": "1.0", "status": "COMPLETE", "config_sha256": "0" * 64,
        "files": files,
    }
    _write_json(root / "artifacts.json", value)
    return value


@pytest.fixture
def package(tmp_path: Path) -> tuple[Path, ObservationAggregation, BoundGapEvent]:
    """Reuse raw mock evidence with an explicit output fixture, without running inference."""
    frames = json.loads((ROOT / "data/mock/stream_v1/single_path/frames.json").read_text())
    aggregation = aggregate_frames(tuple(
        RawProjectedFrameSample.model_validate(item) for item in frames["samples"]
    ))
    start, end = aggregation.observations
    route = CandidateTrajectory(
        candidate_id="mock_route", start_observation_id=start.observation.observation_id,
        end_observation_id=end.observation.observation_id,
        polyline=((0, 0, 0), (20, 0, 0)), path_length=20,
        minimum_travel_time=20, estimated_travel_time=20,
    )
    hypothesis = TrajectoryHypothesis(
        hypothesis_id="mock_timing", candidate_id=route.candidate_id,
        kind=HypothesisKind.DIRECT_PATH,
        timed_points=(
            TimedTrajectoryPoint(timestamp=10, world_position=(0, 0, 0)),
            TimedTrajectoryPoint(timestamp=30, world_position=(20, 0, 0)),
        ),
        segments=(TrajectorySegment(time_range=(10, 30), kind=SegmentKind.MOVEMENT),),
        minimum_travel_time=20, temporal_slack=0, movement_duration=20,
        uncertainty="Mock output fixture; no behavioral probability",
    )
    gap = BoundGapEvent(
        binding=start.binding, start=start, end=end,
        search_result=ReconstructionResult(
            candidates=(route,), termination_reason=TerminationReason.COMPLETE,
        ),
        event=Event(
            event_id="mock_gap", target_id=start.observation.target_id, time_range=(10, 30),
            observation_ids=(start.observation.observation_id, end.observation.observation_id),
            candidates=(route,), trajectories=(hypothesis,),
            termination_reason=TerminationReason.COMPLETE,
        ),
    )
    root = tmp_path / "package"
    _write_json(root / OBSERVATIONS, aggregation.model_dump(mode="json"))
    _write_json(root / CANDIDATES, gap.model_dump(mode="json"))
    _write_json(root / "experiment.json", {"mock_record": True})
    _write_json(root / "replay/config.json", {"mock_replay_locator": True})
    # Opaque non-JSON content proves these artifacts are hashed without deserialization.
    (root / "metrics.json").write_bytes(b"opaque evaluation artifact")
    (root / "ground_truth.json").write_bytes(b"opaque GT artifact")
    _manifest(root)
    return root, aggregation, gap


def test_import_preserves_exact_bound_evidence_routes_timings_and_source_files(
    package: tuple[Path, ObservationAggregation, BoundGapEvent],
) -> None:
    root, aggregation, gap = package
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    snapshot = load_benchmark_snapshot(root)
    assert snapshot.schema_version == "phase2.integration.v1"
    assert snapshot.observations == aggregation.observations
    assert snapshot.gaps == (gap,)
    assert snapshot.gaps[0].event.candidates[0].polyline == ((0, 0, 0), (20, 0, 0))
    assert snapshot.gaps[0].event.trajectories[0].timed_points[-1].timestamp == 30
    assert load_replay_config(root) == root / "replay/config.json"
    assert {path: path.read_bytes() for path in root.rglob("*") if path.is_file()} == before
    assert "GROUND_TRUTH" not in snapshot.model_dump_json()
    assert "opaque" not in snapshot.model_dump_json()


@pytest.mark.parametrize("changes", [{"status": "INCOMPLETE"}, {"schema_version": "2.0"}])
def test_import_requires_complete_supported_manifest(
    package: tuple[Path, ObservationAggregation, BoundGapEvent], changes: dict[str, str],
) -> None:
    root, _, _ = package
    manifest = _manifest(root) | changes
    _write_json(root / "artifacts.json", manifest)
    with pytest.raises(BenchmarkImportError, match="artifact/schema"):
        load_benchmark_snapshot(root)


@pytest.mark.parametrize("required", ["experiment.json", "replay/config.json"])
def test_required_replay_identity_files_must_be_listed(
    package: tuple[Path, ObservationAggregation, BoundGapEvent], required: str,
) -> None:
    root, _, _ = package
    manifest = _manifest(root)
    manifest["files"] = [item for item in manifest["files"] if item["logical_id"] != required]
    _write_json(root / "artifacts.json", manifest)
    with pytest.raises(BenchmarkImportError, match="must be listed"):
        load_benchmark_snapshot(root)


@pytest.mark.parametrize("name", ["observations.json", "candidates.json"])
def test_unlisted_inference_files_cannot_silently_disappear(
    package: tuple[Path, ObservationAggregation, BoundGapEvent], name: str,
) -> None:
    root, _, _ = package
    _write_json(root / "additional_case" / name, {})
    with pytest.raises(BenchmarkImportError, match="every observation/candidate"):
        load_benchmark_snapshot(root)


@pytest.mark.parametrize(
    "artifact", [OBSERVATIONS, CANDIDATES, "metrics.json", "ground_truth.json"],
)
def test_any_artifact_tamper_aborts_the_import(
    package: tuple[Path, ObservationAggregation, BoundGapEvent], artifact: str,
) -> None:
    root, _, _ = package
    path = root / artifact
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(BenchmarkImportError, match="digest/size mismatch"):
        load_benchmark_snapshot(root)
    with pytest.raises(BenchmarkImportError, match="digest/size mismatch"):
        load_replay_config(root)


def test_verifies_all_hashes_before_deserializing_inference(
    package: tuple[Path, ObservationAggregation, BoundGapEvent],
) -> None:
    root, _, _ = package
    (root / OBSERVATIONS).write_bytes(b"invalid observation JSON")
    _manifest(root)
    (root / "metrics.json").write_bytes(b"changed evaluation data")
    with pytest.raises(BenchmarkImportError, match="digest/size mismatch: metrics.json"):
        load_benchmark_snapshot(root)


@pytest.mark.parametrize("size", [False, "1", -1])
def test_manifest_size_is_a_strict_nonnegative_integer(
    package: tuple[Path, ObservationAggregation, BoundGapEvent], size: object,
) -> None:
    root, _, _ = package
    manifest = _manifest(root)
    manifest["files"][0]["size_bytes"] = size
    _write_json(root / "artifacts.json", manifest)
    with pytest.raises(BenchmarkImportError, match="artifact/schema"):
        load_benchmark_snapshot(root)


@pytest.mark.parametrize("logical_id", ["../escape", "/escape", "./escape", "a/../escape", "a\\b"])
def test_manifest_paths_cannot_escape_or_use_noncanonical_spellings(
    package: tuple[Path, ObservationAggregation, BoundGapEvent], logical_id: str,
) -> None:
    root, _, _ = package
    manifest = _manifest(root)
    manifest["files"].append({
        "logical_id": logical_id, "sha256": "0" * 64, "size_bytes": 0,
    })
    _write_json(root / "artifacts.json", manifest)
    with pytest.raises(BenchmarkImportError, match="canonical relative"):
        load_benchmark_snapshot(root)


def test_symlink_escape_is_rejected_even_with_matching_hash(
    package: tuple[Path, ObservationAggregation, BoundGapEvent],
) -> None:
    root, _, _ = package
    outside = root.parent / "outside.json"
    outside.write_bytes((root / OBSERVATIONS).read_bytes())
    (root / OBSERVATIONS).unlink()
    (root / OBSERVATIONS).symlink_to(outside)
    with pytest.raises(BenchmarkImportError, match="inside the package root"):
        load_benchmark_snapshot(root)


def test_duplicate_manifest_paths_and_internal_aliases_are_rejected(
    package: tuple[Path, ObservationAggregation, BoundGapEvent],
) -> None:
    root, _, _ = package
    manifest = _manifest(root)
    manifest["files"].append(manifest["files"][0])
    _write_json(root / "artifacts.json", manifest)
    with pytest.raises(BenchmarkImportError, match="must be unique"):
        load_benchmark_snapshot(root)
    (root / "alias.json").symlink_to(root / "experiment.json")
    _manifest(root)
    with pytest.raises(BenchmarkImportError, match="alias the same file"):
        load_benchmark_snapshot(root)


@pytest.mark.parametrize("artifact", [OBSERVATIONS, CANDIDATES])
def test_duplicate_domain_identities_across_case_files_are_rejected(
    package: tuple[Path, ObservationAggregation, BoundGapEvent], artifact: str,
) -> None:
    root, _, _ = package
    duplicate = root / "cases/duplicate" / Path(artifact).name
    duplicate.parent.mkdir(parents=True)
    duplicate.write_bytes((root / artifact).read_bytes())
    _manifest(root)
    with pytest.raises(BenchmarkImportError, match="artifact/schema"):
        load_benchmark_snapshot(root)


def test_gap_endpoints_must_exactly_match_imported_observations(
    package: tuple[Path, ObservationAggregation, BoundGapEvent],
) -> None:
    root, _, gap = package
    value = gap.model_dump(mode="json")
    value["start"]["sample_ids"] = ["different-but-valid-sample-id"]
    _write_json(root / CANDIDATES, value)
    _manifest(root)
    with pytest.raises(BenchmarkImportError, match="artifact/schema"):
        load_benchmark_snapshot(root)


def test_hidden_fields_in_inference_schema_are_rejected(
    package: tuple[Path, ObservationAggregation, BoundGapEvent],
) -> None:
    root, _, aggregation = package
    value = aggregation.model_dump(mode="json") | {"ground_truth": {"hidden_path": []}}
    _write_json(root / OBSERVATIONS, value)
    _manifest(root)
    with pytest.raises(BenchmarkImportError, match="artifact/schema"):
        load_benchmark_snapshot(root)


def test_missing_listed_artifact_is_rejected(
    package: tuple[Path, ObservationAggregation, BoundGapEvent],
) -> None:
    root, _, _ = package
    (root / CANDIDATES).unlink()
    with pytest.raises(BenchmarkImportError, match="artifact/schema"):
        load_benchmark_snapshot(root)
