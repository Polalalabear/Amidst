"""Saved pilot results remain unchanged while all candidates and debug GT are shown."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest
from rerun.chunk import RrdReader

from amidst.domain.navigation import NavigationGraphConfig
from amidst.domain.observation import ProjectedPoint
from amidst.domain.pipeline import PipelineConfig
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.stream import BoundGapEvent, RawProjectedFrameSample
from amidst.domain.topology import CameraTopologyConfig
from amidst.domain.trajectory import (
    CandidateTrajectory,
    Event,
    ReconstructionResult,
    TimedTrajectoryPoint,
    TrajectoryHypothesis,
    TrajectorySegment,
)
from amidst.observation.aggregation import aggregate_frames

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "visualize_pilot_downstream.py"
SPEC = importlib.util.spec_from_file_location("pilot_downstream_visualization", SCRIPT)
assert SPEC and SPEC.loader
visualization = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(visualization)
SOURCE_SHA = "a" * 64


@pytest.fixture
def inputs() -> tuple:
    samples = []
    for timestamp in range(6):
        visible = timestamp not in (2, 3)
        point = (
            ProjectedPoint(
                point_id=f"p{timestamp}",
                camera_id="CAM_TEST",
                plane_id="pilot_plane",
                timestamp=timestamp,
                world_position=(timestamp * 2, 0, 0),
                floor_id="1F",
            )
            if visible
            else None
        )
        samples.append(
            RawProjectedFrameSample(
                sample_id=f"s{timestamp}",
                source_id="PILOT_TEST",
                spatial_context_id="pilot_context",
                source_asset_sha256=SOURCE_SHA,
                target_id="pilot_target",
                camera_id="CAM_TEST",
                timestamp=timestamp,
                frame_id=timestamp,
                uv=(10, 20) if visible else None,
                visibility="OBSERVED" if visible else "GAP",
                occlusion_state="CLEAR" if visible else "OCCLUDED",
                provenance="OBSERVED" if visible else None,
                projected_point=point,
                gap_reason=None if visible else "OCCLUDED",
                occluder_id=None if visible else "wall",
            )
        )
    aggregation = aggregate_frames(tuple(samples))
    start, end = aggregation.observations
    navigation = NavigationGraphConfig.model_validate(
        {
            "graph_id": "pilot_graph",
            "spatial_context_id": "pilot_context",
            "data_kind": "CONFIGURED",
            "source_asset_sha256": SOURCE_SHA,
            "nodes": [
                {"node_id": "S", "position": [2, 0, 0], "floor_id": "1F"},
                {"node_id": "M", "position": [5, 2, 0], "floor_id": "1F"},
                {"node_id": "T", "position": [8, 0, 0], "floor_id": "1F"},
            ],
            "edges": [
                {
                    "edge_id": "ST",
                    "from_node_id": "S",
                    "to_node_id": "T",
                    "polyline": [[2, 0, 0], [8, 0, 0]],
                },
                {
                    "edge_id": "SM",
                    "from_node_id": "S",
                    "to_node_id": "M",
                    "polyline": [[2, 0, 0], [5, 2, 0]],
                },
                {
                    "edge_id": "MT",
                    "from_node_id": "M",
                    "to_node_id": "T",
                    "polyline": [[5, 2, 0], [8, 0, 0]],
                },
            ],
        }
    )
    topology = CameraTopologyConfig(
        topology_id="pilot_topology",
        navigation_graph_id=navigation.graph_id,
        spatial_context_id=navigation.spatial_context_id,
        data_kind="CONFIGURED",
        source_asset_sha256=SOURCE_SHA,
        nodes=({"camera_id": "CAM_TEST", "floor_id": "1F"},),
    )
    pipeline = PipelineConfig(
        navigation=navigation,
        topology=topology,
        movement=MovementConstraints(max_speed_m_s=10),
        search_policy=GraphSearchPolicy(),
    )
    candidates, hypotheses = [], []
    for index, positions in enumerate(([(2, 0, 0), (8, 0, 0)], [(2, 0, 0), (5, 2, 0), (8, 0, 0)])):
        length = sum(math.dist(a, b) for a, b in zip(positions[:-1], positions[1:], strict=True))
        candidate = CandidateTrajectory(
            candidate_id=f"route_{index}",
            start_observation_id=start.observation.observation_id,
            end_observation_id=end.observation.observation_id,
            polyline=tuple(positions),
            path_length=length,
            minimum_travel_time=length / 10,
            estimated_travel_time=3,
        )
        candidates.append(candidate)
        hypotheses.append(
            TrajectoryHypothesis(
                hypothesis_id=f"hypothesis_{index}",
                candidate_id=candidate.candidate_id,
                kind="SLOWER_MOVEMENT",
                timed_points=tuple(
                    TimedTrajectoryPoint(
                        timestamp=1 + point_index * 3 / (len(positions) - 1),
                        world_position=position,
                    )
                    for point_index, position in enumerate(positions)
                ),
                segments=(TrajectorySegment(time_range=(1, 4), kind="MOVEMENT"),),
                minimum_travel_time=length / 10,
                temporal_slack=3 - length / 10,
                movement_duration=3,
                uncertainty="PILOT timing remains underdetermined",
            )
        )
    result = ReconstructionResult(candidates=tuple(candidates), termination_reason="COMPLETE")
    event = Event(
        event_id="pilot_event",
        target_id="pilot_target",
        time_range=(1, 4),
        observation_ids=(start.observation.observation_id, end.observation.observation_id),
        candidates=tuple(candidates),
        trajectories=tuple(hypotheses),
        termination_reason="COMPLETE",
    )
    gap = BoundGapEvent(
        binding=start.binding, start=start, end=end, search_result=result, event=event
    )
    return aggregation, pipeline, (gap,)


def write_gt(path: Path, *, shift: float = 0, source_sha: str = SOURCE_SHA) -> None:
    path.write_text(
        json.dumps(
            {
                "label": visualization.LABEL,
                "source_asset_sha256": source_sha,
                "target_id": "pilot_target",
                "trajectory_id": "truth_debug",
                "samples": [
                    {"timestamp": index, "position": [index * 2, shift, 0], "floor_id": "1F"}
                    for index in range(6)
                ],
            }
        )
    )


def test_core_preserves_all_routes_order_and_does_not_accept_truth(inputs: tuple) -> None:
    before = [value.model_dump_json() for value in (*inputs[:2], *inputs[2])]
    payload = visualization.build_presentation(*inputs)
    assert payload["label"] == visualization.LABEL
    assert [item["candidate_id"] for item in payload["events"][0]["candidates"]] == [
        "route_0",
        "route_1",
    ]
    assert len({tuple(item["color"]) for item in payload["events"][0]["candidates"]}) == 2
    assert "debug_ground_truth" not in payload
    assert not payload["inference_executed_by_visualizer"]
    assert before == [value.model_dump_json() for value in (*inputs[:2], *inputs[2])]


def test_gt_overlay_changes_neither_candidates_nor_observations(
    inputs: tuple, tmp_path: Path
) -> None:
    payload = visualization.build_presentation(*inputs)
    before = json.dumps(payload, sort_keys=True)
    path = tmp_path / "evaluation_gt.json"
    write_gt(path)
    first = visualization.load_gt_overlay(path, payload)
    write_gt(path, shift=100)
    second = visualization.load_gt_overlay(path, payload)
    assert first != second
    assert json.dumps(payload, sort_keys=True) == before
    write_gt(path, source_sha="b" * 64)
    with pytest.raises(ValueError, match="source and target"):
        visualization.load_gt_overlay(path, payload)


def test_mismatched_source_or_forged_gt_candidate_is_rejected(inputs: tuple) -> None:
    aggregation, pipeline, (gap,) = inputs
    other = pipeline.model_copy(
        update={
            "navigation": pipeline.navigation.model_copy(update={"source_asset_sha256": "b" * 64}),
        }
    )
    with pytest.raises(ValueError, match="source/context"):
        visualization.build_presentation(aggregation, other, (gap,))
    forged = gap.event.candidates[0].model_copy(update={"provenance": "GROUND_TRUTH"})
    unsafe = gap.model_copy(
        update={"event": gap.event.model_copy(update={"candidates": (forged,)})}
    )
    with pytest.raises(ValueError):
        visualization.build_presentation(aggregation, pipeline, (unsafe,))


def test_actual_rrd_contains_all_routes_markers_and_separate_gt(
    inputs: tuple, tmp_path: Path
) -> None:
    payload = visualization.build_presentation(*inputs)
    truth_path = tmp_path / "evaluation_gt.json"
    write_gt(truth_path)
    overlay = visualization.load_gt_overlay(truth_path, payload)
    output = tmp_path / "debug.rrd"
    counts = visualization.log_recording(payload, output, overlay)
    assert counts == {"candidates": 2, "hypotheses": 2, "projected_samples": 4, "gt_samples": 6}
    paths = {chunk.entity_path for chunk in RrdReader(output).stream()}
    assert "/world/inferred/pilot_event/candidates/route_0" in paths
    assert "/world/inferred/pilot_event/candidates/route_1" in paths
    assert "/world/debug_ground_truth/truth_debug/marker" in paths
    assert "/world/observed_markers/CAM_TEST" in paths
    with pytest.raises(FileExistsError):
        visualization.log_recording(payload, output, overlay)


def test_standalone_html_has_layers_and_escapes_script_injection(
    inputs: tuple, tmp_path: Path
) -> None:
    payload = visualization.build_presentation(*inputs)
    payload["target_id"] = "</script><script>alert('test')</script>"
    output = tmp_path / "review_3d.html"
    visualization.write_html(payload, output)
    content = output.read_text()
    assert "<script src" not in content
    assert content.count("</script>") == 1
    assert "\\u003c/script>" in content
    assert "GT · debug/evaluation only" in content


def test_display_interpolation_is_only_presentation_and_preserves_endpoints(inputs: tuple) -> None:
    points = inputs[2][0].event.trajectories[0].model_dump(mode="json")["timed_points"]
    before = json.dumps(points)
    samples = visualization.display_samples(points)
    assert samples[0]["world_position"] == points[0]["world_position"]
    assert samples[-1]["world_position"] == points[-1]["world_position"]
    assert len(samples) == 16
    assert json.dumps(points) == before
