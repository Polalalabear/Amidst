"""Verify SDK data, Top-K/timing/provenance, opt-in GT, and actual RRD saving."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import rerun as rr
from pydantic import ValidationError
from rerun.chunk import RrdReader

from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.ground_truth import GroundTruthSample, GroundTruthTrajectory
from amidst.domain.navigation import (
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
)
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.topology import (
    CameraTopologyConfig,
    CameraTopologyNode,
    CameraTransition,
    CameraTransitionType,
)
from amidst.domain.trajectory import (
    CandidateTrajectory,
    Event,
    HypothesisKind,
    SegmentKind,
    TerminationReason,
    TimedTrajectoryPoint,
    TrajectoryHypothesis,
    TrajectorySegment,
)
from amidst.visualization import RerunDebugVisualizationAdapter
from amidst.visualization.rerun_adapter import EVENT_TIMELINE, PROVENANCE_COLORS


@dataclass
class Logged:
    path: str
    entity: rr.AsComponents
    static: bool
    timestamp: float | None


@dataclass
class Sink:
    logs: list[Logged] = field(default_factory=list)
    times: list[tuple[str, float]] = field(default_factory=list)
    timestamp: float | None = None
    saved_paths: list[Path] = field(default_factory=list)
    flush_count: int = 0
    closed: bool = False

    def log(self, entity_path: str, entity: rr.AsComponents, *, static: bool = False) -> None:
        self.logs.append(Logged(entity_path, entity, static, None if static else self.timestamp))

    def set_time(self, timeline: str, *, duration: float) -> None:
        self.times.append((timeline, duration))
        self.timestamp = duration

    def save(self, path: str | Path) -> None:
        self.saved_paths.append(Path(path))

    def flush(self) -> None:
        self.flush_count += 1

    def disconnect(self) -> None:
        self.closed = True


def _event() -> Event:
    candidates: list[CandidateTrajectory] = []
    hypotheses: list[TrajectoryHypothesis] = []
    for rank in range(1, 4):
        middle = (1.0, float(rank - 1), 0.0)
        polyline = ((0.0, 0.0, 0.0), middle, (2.0, 0.0, 0.0))
        length = 2 * math.dist(polyline[0], middle)
        candidates.append(CandidateTrajectory(
            candidate_id=f"candidate_{rank}",
            start_observation_id="obs_a", end_observation_id="obs_b",
            polyline=polyline, path_length=length,
            minimum_travel_time=length / 2, estimated_travel_time=10,
        ))
        hypotheses.append(TrajectoryHypothesis(
            hypothesis_id=f"hypothesis_{rank}", candidate_id=f"candidate_{rank}",
            kind=HypothesisKind.SLOWER_MOVEMENT,
            timed_points=(
                TimedTrajectoryPoint(
                    timestamp=0, world_position=polyline[0], provenance=Provenance.PROJECTED,
                ),
                TimedTrajectoryPoint(timestamp=5, world_position=middle),
                TimedTrajectoryPoint(
                    timestamp=10, world_position=polyline[-1], provenance=Provenance.PROJECTED,
                ),
            ),
            segments=(TrajectorySegment(time_range=(0, 10), kind=SegmentKind.MOVEMENT),),
            minimum_travel_time=length / 2, temporal_slack=10 - length / 2,
            movement_duration=10, uncertainty="timing underdetermined",
        ))
    hypotheses.append(TrajectoryHypothesis(
        hypothesis_id="dwell_1", candidate_id="candidate_1", kind=HypothesisKind.DWELL,
        timed_points=(
            TimedTrajectoryPoint(
                timestamp=0, world_position=(0, 0, 0), provenance=Provenance.PROJECTED,
            ),
            TimedTrajectoryPoint(timestamp=9, world_position=(0, 0, 0)),
            TimedTrajectoryPoint(
                timestamp=10, world_position=(2, 0, 0), provenance=Provenance.PROJECTED,
            ),
        ),
        segments=(
            TrajectorySegment(time_range=(0, 9), kind=SegmentKind.DWELL),
            TrajectorySegment(time_range=(9, 10), kind=SegmentKind.MOVEMENT),
        ),
        minimum_travel_time=1, temporal_slack=9, movement_duration=1, dwell_duration=9,
        uncertainty="dwell location underdetermined; no behavioral probability",
    ))
    return Event(
        event_id="synthetic/test", target_id="synthetic_target", time_range=(0, 10),
        observation_ids=("obs_a", "obs_b"), candidates=tuple(candidates),
        termination_reason=TerminationReason.COMPLETE, trajectories=tuple(hypotheses),
    )


def _observations() -> tuple[Observation, ...]:
    result: list[Observation] = []
    for name, camera, timestamp, position in (
        ("obs_a", "camera_a", 0.0, (0.0, 0.0, 0.0)),
        ("obs_b", "camera_b", 10.0, (2.0, 0.0, 0.0)),
    ):
        result.append(Observation(
            observation_id=name, target_id="synthetic_target", camera_id=camera,
            start_time=timestamp, end_time=timestamp, provenance=Provenance.PROJECTED,
            frames=(ObservationFrame(
                frame_id=int(timestamp), timestamp=timestamp, target_id="synthetic_target",
                camera_id=camera, status=VisibilityStatus.OBSERVED, point_2d=(10, 20),
                provenance=Provenance.OBSERVED,
            ),),
            projected_path=(ProjectedPoint(
                point_id=f"point_{name}", observation_id=name, camera_id=camera,
                plane_id="1F", timestamp=timestamp, world_position=position,
            ),),
        ))
    return tuple(result)


def _navigation() -> NavigationGraphConfig:
    return NavigationGraphConfig(
        graph_id="waypoints", spatial_context_id="synthetic",
        data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
        nodes=(
            NavigationNode(node_id="A", position=(0, 0, 0), floor_id="1F"),
            NavigationNode(node_id="B", position=(2, 0, 0), floor_id="1F"),
        ),
        edges=(NavigationEdge(
            edge_id="AB", from_node_id="A", to_node_id="B", polyline=((0, 0, 0), (2, 0, 0)),
        ),),
    )


def _topology() -> CameraTopologyConfig:
    return CameraTopologyConfig(
        topology_id="cameras", navigation_graph_id="waypoints", spatial_context_id="synthetic",
        data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
        nodes=(
            CameraTopologyNode(camera_id="camera_a", floor_id="1F"),
            CameraTopologyNode(camera_id="camera_b", floor_id="1F"),
        ),
        transitions=(CameraTransition(
            transition_id="camera_AB", from_camera_id="camera_a", to_camera_id="camera_b",
            transition_type=CameraTransitionType.ADJACENT, navigation_from_node_id="A",
            navigation_to_node_id="B", navigation_edge_ids=("AB",),
        ),),
    )


def _ground_truth() -> GroundTruthTrajectory:
    return GroundTruthTrajectory(
        trajectory_id="truth", target_id="synthetic_target", scene_id="SYNTHETIC_TEST_FIXTURE",
        random_seed=47, sample_rate_hz=1,
        samples=tuple(GroundTruthSample(
            timestamp=timestamp, position=(timestamp / 5, 0, 0), velocity=(0.2, 0, 0),
        ) for timestamp in (0.0, 5.0, 10.0)),
    )


def _text(log: Logged) -> str:
    assert isinstance(log.entity, rr.TextDocument)
    assert log.entity.text is not None
    result: str = log.entity.text.as_arrow_array().to_pylist()[0]
    return result


def test_adapter_logs_all_top_k_hypotheses_with_times_labels_and_provenance() -> None:
    sink = Sink()
    event = _event()
    before = event.model_dump_json()
    adapter = RerunDebugVisualizationAdapter(
        recording=sink, observations=_observations(), navigation_config=_navigation(),
        topology_config=_topology(),
    )
    adapter.log_event(event)
    paths = {log.path for log in sink.logs}
    root = "world/events/synthetic%2Ftest"
    assert {f"{root}/candidates/{item.candidate_id}" for item in event.candidates} <= paths
    assert {f"{root}/hypotheses/{item.hypothesis_id}/path" for item in event.trajectories} <= paths
    for hypothesis in event.trajectories:
        markers = [
            log for log in sink.logs
            if log.path == f"{root}/hypotheses/{hypothesis.hypothesis_id}/marker"
        ]
        assert [log.timestamp for log in markers] == list(range(11))
        declared = {point.timestamp: point for point in hypothesis.timed_points}
        for log in markers:
            assert isinstance(log.entity, rr.Points3D)
            assert log.entity.positions is not None and log.entity.labels is not None
            labels = log.entity.labels.as_arrow_array().to_pylist()
            if log.timestamp in declared:
                point = declared[log.timestamp]
                assert log.entity.positions.as_arrow_array().to_pylist() == [
                    list(point.world_position)
                ]
                assert f"sample={point.provenance.value}" in labels[0]
            else:
                assert "sample=INFERRED_GAP" in labels[0]
            assert hypothesis.kind.value in labels[0]
    assert all(timeline == EVENT_TIMELINE for timeline, _ in sink.times)
    assert not any("debug_ground_truth" in path for path in paths)
    assert event.model_dump_json() == before
    metadata = json.loads(_text(next(
        log for log in sink.logs if log.path == "debug/events/synthetic%2Ftest"
    )))
    assert metadata["termination_reason"] == "COMPLETE"
    assert metadata["candidate_order"] == [item.candidate_id for item in event.candidates]
    assert metadata["hypothesis_count"] == 4
    assert metadata["marker_sample_count"] == 44
    assert metadata["display_sample_rate_hz"] == 1.0


def _two_point_event() -> Event:
    candidate = CandidateTrajectory(
        candidate_id="route_20s", start_observation_id="obs_a", end_observation_id="obs_b",
        polyline=((0, 0, 0), (20, 0, 0)), path_length=20,
        minimum_travel_time=20, estimated_travel_time=20,
    )
    hypothesis = TrajectoryHypothesis(
        hypothesis_id="direct_20s", candidate_id="route_20s", kind=HypothesisKind.DIRECT_PATH,
        timed_points=(
            TimedTrajectoryPoint(
                timestamp=0, world_position=(0, 0, 0), provenance=Provenance.PROJECTED,
            ),
            TimedTrajectoryPoint(
                timestamp=20, world_position=(20, 0, 0), provenance=Provenance.PROJECTED,
            ),
        ),
        segments=(TrajectorySegment(time_range=(0, 20), kind=SegmentKind.MOVEMENT),),
        minimum_travel_time=20, temporal_slack=0, movement_duration=20,
        uncertainty="no temporal slack",
    )
    return Event(
        event_id="playback", target_id="synthetic_target", time_range=(0, 20),
        observation_ids=("obs_a", "obs_b"), candidates=(candidate,),
        termination_reason=TerminationReason.COMPLETE, trajectories=(hypothesis,),
    )


def test_two_point_route_has_deterministic_midpoint_playback_without_changing_event() -> None:
    event = _two_point_event()
    snapshot = event.model_dump_json()
    sinks = [Sink(), Sink()]
    for sink in sinks:
        RerunDebugVisualizationAdapter(recording=sink).log_event(event)
    markers = [log for log in sinks[0].logs if log.path.endswith("/direct_20s/marker")]
    assert [log.timestamp for log in markers] == list(range(21))
    midpoint = markers[10]
    assert isinstance(midpoint.entity, rr.Points3D)
    assert midpoint.entity.positions is not None and midpoint.entity.labels is not None
    assert midpoint.entity.positions.as_arrow_array().to_pylist() == [[10, 0, 0]]
    assert "sample=INFERRED_GAP" in midpoint.entity.labels.as_arrow_array().to_pylist()[0]
    for endpoint in (markers[0], markers[-1]):
        assert isinstance(endpoint.entity, rr.Points3D)
        assert endpoint.entity.labels is not None
        assert "sample=PROJECTED" in endpoint.entity.labels.as_arrow_array().to_pylist()[0]
    second_markers = [log for log in sinks[1].logs if log.path.endswith("/direct_20s/marker")]
    assert [log.timestamp for log in second_markers] == [log.timestamp for log in markers]
    assert event.model_dump_json() == snapshot


def test_display_sampling_includes_off_grid_declared_samples_and_original_provenance() -> None:
    event = _event()
    first = event.trajectories[0]
    keyframe = TimedTrajectoryPoint(
        timestamp=5.5, world_position=(1, 0, 0), provenance=Provenance.PROJECTED,
    )
    adjusted = first.model_copy(update={
        "timed_points": (first.timed_points[0], keyframe, first.timed_points[-1]),
    })
    event = event.model_copy(update={"trajectories": (adjusted,)})
    sink = Sink()
    RerunDebugVisualizationAdapter(recording=sink, display_sample_rate_hz=0.5).log_event(event)
    markers = [log for log in sink.logs if log.path.endswith("/hypothesis_1/marker")]
    assert [log.timestamp for log in markers] == [0, 2, 4, 5.5, 6, 8, 10]
    declared = next(log for log in markers if log.timestamp == 5.5)
    assert isinstance(declared.entity, rr.Points3D)
    assert declared.entity.labels is not None and declared.entity.positions is not None
    assert "sample=PROJECTED" in declared.entity.labels.as_arrow_array().to_pylist()[0]
    assert declared.entity.positions.as_arrow_array().to_pylist() == [[1, 0, 0]]


@pytest.mark.parametrize("rate_hz", [0.0, -1.0, math.inf, math.nan])
def test_display_sampling_rejects_invalid_rate(rate_hz: float) -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        RerunDebugVisualizationAdapter(recording=Sink(), display_sample_rate_hz=rate_hz)


def test_display_sampling_budget_rejects_excessive_work_before_any_event_logging() -> None:
    sink = Sink()
    adapter = RerunDebugVisualizationAdapter(recording=sink, max_marker_samples=20)
    with pytest.raises(ValueError, match="sample budget exceeded"):
        adapter.log_event(_two_point_event())
    assert not sink.logs
    # The limit is shared by all hypotheses, including dwell alternatives.
    adapter = RerunDebugVisualizationAdapter(recording=sink, max_marker_samples=43)
    with pytest.raises(ValueError, match="sample budget exceeded"):
        adapter.log_event(_event())
    assert not sink.logs


def test_static_context_projected_endpoints_and_observed_pixels_are_separate() -> None:
    sink = Sink()
    adapter = RerunDebugVisualizationAdapter(
        recording=sink, observations=_observations(), navigation_config=_navigation(),
        topology_config=_topology(),
    )
    adapter.log_event(_event())
    paths = {log.path for log in sink.logs}
    assert "world/navigation/nodes" in paths
    assert "world/navigation/edges/AB" in paths
    assert "world/camera_anchors/camera_a" in paths
    assert "world/camera_anchors/camera_b" in paths
    observed = [log for log in sink.logs if "/observed/" in log.path]
    projected = [log for log in sink.logs if log.path.startswith("world/projected/")]
    assert [log.timestamp for log in observed] == [0, 10]
    assert [log.timestamp for log in projected] == [0, 10]
    for logs, cls, provenance in (
        (observed, rr.Points2D, Provenance.OBSERVED),
        (projected, rr.Points3D, Provenance.PROJECTED),
    ):
        for log in logs:
            assert isinstance(log.entity, cls)
            assert log.entity.colors is not None
            expected = rr.Points3D([(0, 0, 0)], colors=PROVENANCE_COLORS[provenance])
            assert expected.colors is not None
            assert log.entity.colors.as_arrow_array() == expected.colors.as_arrow_array()
    legend = _text(next(log for log in sink.logs if log.path == "debug/provenance_legend"))
    assert "not calibrated camera poses/FOV" in legend
    assert "not Blender mesh walkability certification" in legend


def test_ground_truth_requires_opt_in_and_cannot_mutate_logged_event() -> None:
    sink = Sink()
    disabled = RerunDebugVisualizationAdapter(recording=sink)
    with pytest.raises(PermissionError, match="explicit debug mode"):
        disabled.log_debug_ground_truth(_ground_truth())
    assert not sink.logs
    enabled = RerunDebugVisualizationAdapter(recording=sink, debug_mode=True)
    event = _event()
    snapshot = event.model_dump_json()
    enabled.log_event(event)
    event_logs = tuple(sink.logs)
    enabled.log_debug_ground_truth(_ground_truth())
    assert tuple(sink.logs[:len(event_logs)]) == event_logs
    assert event.model_dump_json() == snapshot
    markers = [log for log in sink.logs if log.path == "world/debug_ground_truth/truth/marker"]
    assert [log.timestamp for log in markers] == [0, 5, 10]
    assert any(log.path == "world/debug_ground_truth/truth/dotted_path" for log in sink.logs)


def test_adapter_revalidates_schema_bypassing_ground_truth_candidate() -> None:
    sink = Sink()
    event = _event()
    candidate = event.candidates[0].model_copy(update={"provenance": Provenance.GROUND_TRUTH})
    unsafe = event.model_copy(update={"candidates": (candidate, *event.candidates[1:])})
    adapter = RerunDebugVisualizationAdapter(recording=sink)
    with pytest.raises(ValidationError):
        adapter.log_event(unsafe)
    assert not sink.logs


def test_metrics_log_numeric_series_and_complete_nested_debug_document() -> None:
    sink = Sink()
    adapter = RerunDebugVisualizationAdapter(recording=sink)
    adapter.log_event(_event())
    metrics = {
        "min_ade_at_k_m": 0.25, "min_fde_at_k_m": 0.0, "coverage_at_k": 1,
        "collision_rate": None,
        "trajectory_metrics": [{"hypothesis_id": "h1", "constraint_violation_rate": 0}],
    }
    adapter.log_metrics(metrics)
    document = next(log for log in sink.logs if log.path == "debug/evaluation_metrics")
    assert json.loads(_text(document)) == metrics
    series = [log for log in sink.logs if isinstance(log.entity, rr.Scalars)]
    assert {log.path for log in series} == {
        "metrics/min_ade_at_k_m", "metrics/min_fde_at_k_m", "metrics/coverage_at_k",
    }
    assert all(log.timestamp == 10 for log in series)


def test_inferred_paths_use_actual_dashed_geometry() -> None:
    sink = Sink()
    RerunDebugVisualizationAdapter(recording=sink).log_event(_event())
    path = next(log for log in sink.logs if log.path.endswith("/candidates/candidate_1"))
    assert isinstance(path.entity, rr.LineStrips3D)
    assert path.entity.strips is not None
    strips = path.entity.strips.as_arrow_array().to_pylist()
    assert len(strips) > 1
    assert math.dist(strips[0][-1], strips[1][0]) > 0


@pytest.mark.parametrize("name", ["scene.blend", "report.json", "recording"])
def test_save_rejects_non_rrd_suffix_without_creating_file(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    with pytest.raises(ValueError, match=".rrd"):
        RerunDebugVisualizationAdapter(recording=Sink()).save(path)
    assert not path.exists()


def test_save_refuses_overwrite_and_save_after_logging(tmp_path: Path) -> None:
    path = tmp_path / "existing.rrd"
    path.write_bytes(b"preserved recording")
    adapter = RerunDebugVisualizationAdapter(recording=Sink())
    with pytest.raises(FileExistsError):
        adapter.save(path)
    assert path.read_bytes() == b"preserved recording"
    adapter.log_event(_event())
    later = tmp_path / "later.rrd"
    with pytest.raises(RuntimeError, match="before logging"):
        adapter.save(later)
    assert not later.exists()


def test_real_sdk_saves_nonempty_rrd_with_event_truth_and_metrics(tmp_path: Path) -> None:
    path = tmp_path / "smoke.rrd"
    adapter = RerunDebugVisualizationAdapter(
        observations=_observations(), navigation_config=_navigation(), topology_config=_topology(),
        debug_mode=True,
    )
    adapter.save(path)
    adapter.log_event(_event())
    adapter.log_event(_two_point_event())
    adapter.log_debug_ground_truth(_ground_truth())
    adapter.log_metrics({"min_ade_at_k_m": 0.0, "min_fde_at_k_m": 0.0, "coverage_at_k": 1.0})
    adapter.close()
    assert path.stat().st_size > 1024
    assert path.read_bytes()[:3] == b"RRF"
    reader = RrdReader(path)
    assert len(reader.recordings()) == 1
    # Opening the lazy store also proves close emitted the readable footer/manifest.
    assert len(reader.store()) > 0
    chunks = list(reader.stream())
    paths = {chunk.entity_path.lstrip("/").replace("\\", "") for chunk in chunks}
    assert "world/navigation/nodes" in paths
    assert "world/camera_anchors/camera_a" in paths
    assert "world/projected/obs_a" in paths
    assert "cameras/camera_a/observed/obs_a" in paths
    for candidate in _event().candidates:
        assert f"world/events/synthetic%2Ftest/candidates/{candidate.candidate_id}" in paths
    for hypothesis in _event().trajectories:
        markers = [
            chunk for chunk in chunks
            if chunk.entity_path.endswith(f"/hypotheses/{hypothesis.hypothesis_id}/marker")
        ]
        seconds: list[float] = []
        for chunk in markers:
            batch = chunk.to_record_batch()
            seconds.extend(
                value.total_seconds() for value in batch.column(EVENT_TIMELINE).to_pylist()
            )
            assert "Points3D:positions" in batch.column_names
            assert "Points3D:colors" in batch.column_names
            assert "Points3D:labels" in batch.column_names
        assert seconds == list(range(11))
    playback_rows = [
        row for chunk in chunks
        if chunk.entity_path == "/world/events/playback/hypotheses/direct_20s/marker"
        for row in chunk.to_record_batch().to_pylist()
    ]
    assert len(playback_rows) == 21
    midpoint = next(row for row in playback_rows if row[EVENT_TIMELINE].total_seconds() == 10)
    assert midpoint["Points3D:positions"] == [[10, 0, 0]]
    assert "sample=INFERRED_GAP" in midpoint["Points3D:labels"][0]
    assert midpoint["Points3D:colors"] == [4119931135]
    truth_markers = [
        chunk for chunk in chunks if chunk.entity_path == "/world/debug_ground_truth/truth/marker"
    ]
    assert sum(chunk.num_rows for chunk in truth_markers) == len(_ground_truth().samples)
    assert "world/debug_ground_truth/truth/dotted_path" in paths
    truth_rows = [
        row for chunk in truth_markers for row in chunk.to_record_batch().to_pylist()
    ]
    assert all("GROUND_TRUTH" in row["Points3D:labels"][0] for row in truth_rows)
    assert all(row["Points3D:colors"] == [2526451455] for row in truth_rows)
    metadata = next(chunk for chunk in chunks if chunk.entity_path.endswith(
        "/debug/events/synthetic\\%2Ftest"
    ))
    data = json.loads(metadata.to_record_batch().to_pylist()[0]["TextDocument:text"][0])
    assert data["termination_reason"] == "COMPLETE"
    assert data["candidate_count"] == 3
    assert {f"metrics/{name}" for name in (
        "min_ade_at_k_m", "min_fde_at_k_m", "coverage_at_k",
    )} <= paths
    with pytest.raises(RuntimeError, match="closed"):
        adapter.log_event(_event())
