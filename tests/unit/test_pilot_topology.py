"""Configured pilot handoffs retain projected evidence and partial geometry authority."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from amidst.datasets.pilot import PilotInferenceContext, PilotZoneContext
from amidst.datasets.pilot_topology import build_pilot_pipeline
from amidst.domain.camera import Camera
from amidst.domain.common import Provenance, Vec3
from amidst.domain.evidence import GapReason, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.domain.observation import ProjectedPoint
from amidst.domain.stream import ObservationAggregation, OcclusionState, RawProjectedFrameSample
from amidst.domain.topology import CameraTransitionType
from amidst.domain.trajectory import TerminationReason
from amidst.events import reconstruct_gaps
from amidst.observation import aggregate_frames

SOURCE = "a" * 64
CONTEXT = "PILOT:configured-envelope-fixture"


def context_fixture(
    low_x: float = 1145.0,
    high_x: float = 1495.0,
) -> PilotInferenceContext:
    identity = (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    return PilotInferenceContext(
        label="PILOT / SYNTHETIC SAMPLE",
        data_kind="SYNTHETIC",
        site_id="fixture",
        source_id="pilot-source",
        spatial_context_id=CONTEXT,
        source_asset_sha256=SOURCE,
        observations_sha256="b" * 64,
        cameras=tuple(
            Camera(
                camera_id=camera_id,
                camera_to_world=identity,
                fx=100,
                fy=100,
                cx=50,
                cy=50,
                width=100,
                height=100,
                floor_id="1F",
                zone_id=zone,
            )
            for camera_id, zone in (
                ("CAM_FRONT", "AUDITORIUM_FRONT"),
                ("CAM_REAR", "AUDITORIUM_REAR"),
            )
        ),
        plane=Plane(
            plane_id="pilot-landmark",
            point=(0, 0, 75),
            normal=(0, 0, 1),
            floor_id="1F",
            zone_id="AREA_1F_OFFICE",
        ),
        zone=PilotZoneContext(
            floor_id="1F",
            zone_id="AREA_1F_OFFICE",
            walkable_object_id="WALK_1F_OFFICE",
            bounds_min=(low_x, 1710, 15),
            bounds_max=(high_x, 2310, 155),
            authority="ANNOTATION_AABB_ONLY_PROVISIONAL",
        ),
    )


def aggregation_fixture(
    *,
    start: Vec3 = (1400, 2004, 75),
    end: Vec3 = (1400, 2084, 75),
    recovery_camera: str = "CAM_REAR",
    reverse: bool = False,
) -> ObservationAggregation:
    def sample(
        camera_id: str,
        timestamp: float,
        point: Vec3 | None,
    ) -> RawProjectedFrameSample:
        identity = f"{camera_id}:{timestamp}"
        return RawProjectedFrameSample(
            sample_id=identity,
            source_id="pilot-source",
            spatial_context_id=CONTEXT,
            source_asset_sha256=SOURCE,
            target_id="marker",
            camera_id=camera_id,
            timestamp=timestamp,
            frame_id=int(timestamp * 5),
            uv=(25, 25) if point else None,
            visibility=VisibilityStatus.OBSERVED if point else VisibilityStatus.GAP,
            provenance=Provenance.OBSERVED if point else None,
            occlusion_state=OcclusionState.CLEAR if point else OcclusionState.OCCLUDED,
            projected_point=ProjectedPoint(
                point_id=f"projected:{identity}",
                camera_id=camera_id,
                plane_id="pilot-landmark",
                timestamp=timestamp,
                world_position=point,
                floor_id="1F",
                zone_id="AREA_1F_OFFICE",
            )
            if point
            else None,
            gap_reason=None if point else GapReason.OCCLUDED,
            occluder_id=None if point else "unclassified_existing_mesh",
        )

    samples = (
        sample("CAM_FRONT", 4.0, start),
        sample("CAM_FRONT", 4.2, None),
        sample("CAM_REAR", 8.8, None),
        sample(recovery_camera, 9.0, end),
    )
    return aggregate_frames(tuple(reversed(samples)) if reverse else samples)


def test_three_configured_routes_reconstruct_without_truth_or_source_zone_relabeling() -> None:
    aggregation, context = aggregation_fixture(), context_fixture()
    pipeline, evidence = build_pilot_pipeline(aggregation, context)
    events = reconstruct_gaps(
        aggregation, pipeline, dataset_id="PILOT", random_seed=1, clock=lambda: 0.0
    )
    assert len(events) == 1
    event = events[0]
    assert event.event.time_range == (4.0, 9.0)
    assert event.search_result.complete
    assert event.search_result.termination_reason == TerminationReason.COMPLETE
    assert len(event.search_result.candidates) == 3
    assert len({c.candidate_id for c in event.search_result.candidates}) == 3
    assert tuple(c.navmesh_corridor for c in event.search_result.candidates) == (
        ("pilot_route:direct",),
        ("pilot_route:left",),
        ("pilot_route:right",),
    )
    assert all(
        c.polyline[0] == (1400, 2004, 75)
        and c.polyline[-1] == (1400, 2084, 75)
        and c.path_score is None
        for c in event.search_result.candidates
    )
    assert {node.camera_id: node.zone_id for node in pipeline.topology.nodes} == {
        "CAM_FRONT": "AUDITORIUM_FRONT",
        "CAM_REAR": "AUDITORIUM_REAR",
    }
    assert all(
        t.transition_type == CameraTransitionType.ADJACENT for t in pipeline.topology.transitions
    )
    assert all(
        p.provenance != Provenance.GROUND_TRUTH
        for trajectory in event.event.trajectories
        for p in trajectory.timed_points
    )
    assert evidence["status"] == "PARTIAL_PROVISIONAL_CONFIGURED_GRAPH"
    assert evidence["mesh_collision_certified"] is False
    assert evidence["wall_collision_authority"] is False
    assert evidence["scale_authority"] == "UNVERIFIED"
    assert pipeline.navigation.cross_floor_policy == "DISCONNECTED"


def test_raw_input_permutation_preserves_graph_evidence_and_reconstruction_bytes() -> None:
    first, second = aggregation_fixture(), aggregation_fixture(reverse=True)
    context = context_fixture()
    pipeline, evidence = build_pilot_pipeline(first, context)
    repeated, repeated_evidence = build_pilot_pipeline(second, context)
    assert pipeline.model_dump_json() == repeated.model_dump_json()
    assert evidence == repeated_evidence
    events = reconstruct_gaps(first, pipeline, dataset_id="PILOT", random_seed=1, clock=lambda: 0.0)
    rerun = reconstruct_gaps(second, repeated, dataset_id="PILOT", random_seed=1, clock=lambda: 0.0)
    assert tuple(e.model_dump_json() for e in events) == tuple(e.model_dump_json() for e in rerun)


def test_annotation_bounds_reduce_offsets_without_claiming_body_clearance() -> None:
    pipeline, evidence = build_pilot_pipeline(aggregation_fixture(), context_fixture(1395, 1405))
    assert evidence["effective_lateral_offsets_scene_units"] == {
        "direct": 0.0,
        "left": 5.0,
        "right": 5.0,
    }
    assert all(
        1395 <= point[0] <= 1405 for edge in pipeline.navigation.edges for point in edge.polyline
    )
    assert evidence["requested_lateral_offset_scene_units"] == 12.0
    assert "full synthetic marker body" in " ".join(evidence["limitations"])


def test_zero_margin_side_is_reported_and_never_filled_with_a_fake_route() -> None:
    pipeline, evidence = build_pilot_pipeline(
        aggregation_fixture(start=(1395, 2004, 75), end=(1395, 2084, 75)),
        context_fixture(1395, 1405),
    )
    assert evidence["configured_route_count"] == 2
    assert evidence["rejected_routes"] == {
        "left": "NO_POSITIVE_LATERAL_MARGIN_IN_ANNOTATION_AABB",
    }
    assert {edge.edge_id for edge in pipeline.navigation.edges} == {
        "pilot_route:direct",
        "pilot_route:right",
    }


def test_off_network_projected_endpoint_is_rejected_before_graph_generation() -> None:
    with pytest.raises(ValueError, match="outside the provisional annotation bounds"):
        build_pilot_pipeline(aggregation_fixture(start=(1500, 2004, 75)), context_fixture())


def test_source_and_projection_plane_drift_are_rejected() -> None:
    context = context_fixture().model_copy(update={"source_asset_sha256": "c" * 64})
    with pytest.raises(ValueError, match="source/context binding"):
        build_pilot_pipeline(aggregation_fixture(), context)
    with pytest.raises(ValueError, match="plane/floor/zone projection"):
        build_pilot_pipeline(aggregation_fixture(start=(1400, 2004, 74)), context_fixture())


def test_same_camera_moving_gap_is_not_disguised_as_a_camera_self_transition() -> None:
    with pytest.raises(ValueError, match="existing-camera handoff"):
        build_pilot_pipeline(aggregation_fixture(recovery_camera="CAM_FRONT"), context_fixture())


@pytest.mark.parametrize(
    "key,value",
    [
        ("lateral_offset_scene_units", 0),
        ("lateral_offset_scene_units", float("nan")),
        ("lateral_offset_scene_units", True),
        ("max_speed_scene_units_s", float("inf")),
        ("max_candidate_paths", 0),
        ("max_candidate_paths", 4),
        ("max_candidate_paths", True),
    ],
)
def test_invalid_or_unbounded_diagnostic_policy_rejected(key: str, value: float) -> None:
    with pytest.raises(ValueError):
        build_pilot_pipeline(aggregation_fixture(), context_fixture(), **{key: value})  # type: ignore[arg-type]


def test_speed_pruning_and_top_k_budget_use_existing_core_semantics() -> None:
    aggregation, context = aggregation_fixture(), context_fixture()
    slow, _ = build_pilot_pipeline(aggregation, context, max_speed_scene_units_s=10)
    event = reconstruct_gaps(
        aggregation, slow, dataset_id="PILOT", random_seed=1, clock=lambda: 0.0
    )[0]
    assert event.search_result.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    assert event.search_result.candidates == event.event.trajectories == ()
    limited, _ = build_pilot_pipeline(aggregation, context, max_candidate_paths=1)
    event = reconstruct_gaps(
        aggregation, limited, dataset_id="PILOT", random_seed=1, clock=lambda: 0.0
    )[0]
    assert len(event.search_result.candidates) == 1
    assert event.search_result.termination_reason == TerminationReason.MAX_PATHS_REACHED
    assert not event.search_result.complete


def test_truth_file_access_is_poisoned_for_topology_and_graph_consumers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    aggregation, context = aggregation_fixture(), context_fixture()

    def deny(*args: object, **kwargs: object) -> None:
        raise AssertionError("pure topology and graph inference must not open files")

    monkeypatch.setattr(Path, "read_text", deny)
    monkeypatch.setattr(Path, "read_bytes", deny)
    pipeline, evidence = build_pilot_pipeline(aggregation, context)
    events = reconstruct_gaps(
        aggregation, pipeline, dataset_id="PILOT", random_seed=1, clock=lambda: 0.0
    )
    assert events[0].event.trajectories
    assert evidence["ground_truth_used"] is False
    assert evidence["simulation_route_samples_used"] is False


def test_hidden_fields_in_forged_context_and_points_do_not_enter_topology() -> None:
    context = context_fixture()
    object.__setattr__(context, "ground_truth", (999, 999, 999))
    with pytest.raises(ValueError, match="outside its declared contract"):
        build_pilot_pipeline(aggregation_fixture(), context)


def test_topology_module_has_no_simulation_truth_or_evaluation_import() -> None:
    source = Path(__file__).parents[2] / "src/amidst/datasets/pilot_topology.py"
    tree = ast.parse(source.read_text())
    for node in ast.walk(tree):
        modules = (
            [a.name for a in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else []
        )
        assert not any(
            term in module
            for module in modules
            for term in ("ground_truth", "simulation", "evaluation", "visualization")
        )
