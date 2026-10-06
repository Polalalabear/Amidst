"""Approved SI boundaries preserve native evidence and existing inference decisions."""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.architectural_scale import ArchitecturalScale, load_architectural_scale
from amidst.domain.camera import Camera, ProjectionReason
from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.domain.navigation import NavigationDataKind, NavigationGraphConfig
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.topology import CameraTopologyConfig
from amidst.geometry.inverse_projection import InverseProjectionService
from amidst.graph.engine import SpatiotemporalGraphEngine
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.physical_authority import PhysicalPolicy
from amidst.physical_units import (
    native_camera_to_metres,
    native_movement_to_metres,
    native_navigation_to_metres,
    native_observation_to_metres,
    native_plane_to_metres,
    native_projected_point_to_metres,
    native_quantity_report,
    native_search_policy_to_metres,
    physical_policy_in_blender_units,
)
from amidst.scene_geometry import Authority
from amidst.simulation.virtual_camera import project_world


@pytest.fixture
def scale() -> ArchitecturalScale:
    return load_architectural_scale(
        Path(__file__).resolve().parents[2] / "configs/architectural_scale_school_v3.json"
    )


def _camera() -> Camera:
    return Camera(
        camera_id="CAM_UNIT_BOUNDARY", fx=500, fy=450, cx=320, cy=240,
        width=640, height=480, clip_start=2, clip_end=1000,
        camera_to_world=(
            (0, -1, 0, 120), (1, 0, 0, -40), (0, 0, 1, 300), (0, 0, 0, 1),
        ),
        floor_id="1F", zone_id="unit-boundary",
    )


def _plane() -> Plane:
    return Plane(
        plane_id="native-floor-plane", point=(0, 0, 25), normal=(0, 0, 1),
        floor_id="1F", zone_id="unit-boundary",
    )


def _navigation(scale: ArchitecturalScale) -> NavigationGraphConfig:
    return NavigationGraphConfig.model_validate({
        "graph_id": "unit-graph", "spatial_context_id": "unit-boundary",
        "data_kind": "CONFIGURED", "source_asset_sha256": scale.source_asset_sha256,
        "node_match_tolerance_m": 0.01,
        "nodes": [
            {"node_id": "start", "position": (0, 0, 25), "floor_id": "1F"},
            {"node_id": "end", "position": (30, 40, 25), "floor_id": "1F"},
        ],
        "edges": [{
            "edge_id": "route", "from_node_id": "start", "to_node_id": "end",
            "polyline": [(0, 0, 25), (30, 40, 25)],
        }],
    })


def _topology(scale: ArchitecturalScale) -> CameraTopologyConfig:
    return CameraTopologyConfig.model_validate({
        "topology_id": "unit-topology", "navigation_graph_id": "unit-graph",
        "spatial_context_id": "unit-boundary", "data_kind": "CONFIGURED",
        "source_asset_sha256": scale.source_asset_sha256,
        "nodes": [
            {"camera_id": "start-camera", "floor_id": "1F"},
            {"camera_id": "end-camera", "floor_id": "1F"},
        ],
        "transitions": [{
            "transition_id": "handoff", "from_camera_id": "start-camera",
            "to_camera_id": "end-camera", "transition_type": "ADJACENT",
            "navigation_from_node_id": "start", "navigation_to_node_id": "end",
            "navigation_edge_ids": ["route"],
        }],
    })


def _observation(name: str, timestamp: float) -> Observation:
    camera_id = name + "-camera"
    return Observation(
        observation_id=name + "-observation", camera_id=camera_id,
        target_id="observed-target", start_time=timestamp, end_time=timestamp,
        floor_id="1F", provenance=Provenance.PROJECTED,
        entry_direction=(0, 1, 0),
        projected_path=(ProjectedPoint(
            point_id=name + "-point", camera_id=camera_id, plane_id="native-floor-plane",
            timestamp=timestamp, floor_id="1F",
            world_position=(0, 0, 25) if name == "start" else (30, 40, 25),
        ),),
    )


@pytest.mark.parametrize("position", [
    (130, -20, 25), (120, -40, 25), (120, -40, 299), (120, -40, -701),
])
def test_camera_conversion_preserves_pixel_fov_and_clip_decisions(
    scale: ArchitecturalScale, position: tuple[float, float, float],
) -> None:
    native = _camera()
    before = native.model_dump(mode="python")
    metric = native_camera_to_metres(native, scale, source_asset_sha256=scale.source_asset_sha256)
    native_projection = project_world(native, position)
    metric_projection = project_world(metric, tuple(scale.to_metres(v) for v in position))
    assert metric_projection.reason == native_projection.reason
    assert metric_projection.in_frustum == native_projection.in_frustum
    if native_projection.point_2d is None:
        assert metric_projection.point_2d is None
    else:
        assert metric_projection.point_2d == pytest.approx(native_projection.point_2d)
    assert metric_projection.axial_depth == pytest.approx(
        scale.to_metres(native_projection.axial_depth)
    )
    assert metric.meters_per_unit == 1
    assert metric.camera_id == native.camera_id
    assert native.model_dump(mode="python") == before


def test_scaled_camera_and_plane_project_back_to_the_same_source_point(
    scale: ArchitecturalScale,
) -> None:
    camera, plane = _camera(), _plane()
    frame = ObservationFrame(
        camera_id=camera.camera_id, target_id="target", frame_id=2, timestamp=1,
        status=VisibilityStatus.OBSERVED, point_2d=(350, 220), provenance=Provenance.OBSERVED,
    )
    native = InverseProjectionService(camera, plane).project_frame(frame)
    metric_camera = native_camera_to_metres(
        camera, scale, source_asset_sha256=scale.source_asset_sha256,
    )
    metric_plane = native_plane_to_metres(
        plane, scale, source_asset_sha256=scale.source_asset_sha256,
    )
    metric = InverseProjectionService(metric_camera, metric_plane).project_frame(frame)
    assert metric.world_position == pytest.approx(tuple(
        scale.to_metres(v) for v in native.world_position
    ))
    assert metric.point_id == native.point_id
    assert metric.provenance == Provenance.PROJECTED
    assert metric.projection_quality == pytest.approx(native.projection_quality)
    assert metric_plane.normal == plane.normal
    assert project_world(metric_camera, metric.world_position).reason == ProjectionReason.IN_FRUSTUM
    assert project_world(metric_camera, metric.world_position).point_2d == pytest.approx(
        frame.point_2d
    )


@pytest.mark.parametrize("gap_seconds,expected_count", [(1.0, 0), (2.0, 1), (20.0, 1)])
def test_graph_speed_rejection_and_minimum_time_are_unit_invariant(
    scale: ArchitecturalScale, gap_seconds: float, expected_count: int,
) -> None:
    native_graph = _navigation(scale)
    native_movement = MovementConstraints(max_speed_m_s=25)
    native_policy = GraphSearchPolicy(max_path_length_m=75, max_search_time_s=10)
    native_observations = (_observation("start", 0), _observation("end", gap_seconds))
    native_result = SpatiotemporalGraphEngine(
        NavigationNetwork(NavigationGraph(native_graph), CameraTopologyGraph(_topology(scale))),
        native_movement, native_policy,
    ).propose_feasible_trajectories(*native_observations)
    metric_graph = native_navigation_to_metres(native_graph, scale)
    metric_movement = native_movement_to_metres(
        native_movement, scale, source_asset_sha256=scale.source_asset_sha256,
    )
    metric_policy = native_search_policy_to_metres(
        native_policy, scale, source_asset_sha256=scale.source_asset_sha256,
    )
    metric_observations = tuple(native_observation_to_metres(
        observation, scale, source_asset_sha256=scale.source_asset_sha256,
    ) for observation in native_observations)
    metric_result = SpatiotemporalGraphEngine(
        NavigationNetwork(NavigationGraph(metric_graph), CameraTopologyGraph(_topology(scale))),
        metric_movement, metric_policy,
    ).propose_feasible_trajectories(*metric_observations)
    assert len(metric_result.candidates) == len(native_result.candidates) == expected_count
    assert metric_result.termination_reason == native_result.termination_reason
    assert metric_result.rejection_reasons == native_result.rejection_reasons
    assert metric_graph.graph_id == native_graph.graph_id
    assert metric_graph.edges[0].edge_id == native_graph.edges[0].edge_id
    assert metric_policy.max_search_time_s == native_policy.max_search_time_s
    assert metric_policy.max_detour_ratio == native_policy.max_detour_ratio
    for native_observation, metric_observation in zip(
        native_observations, metric_observations, strict=True,
    ):
        assert metric_observation.observation_id == native_observation.observation_id
        assert metric_observation.entry_direction == native_observation.entry_direction
        assert metric_observation.end_time == native_observation.end_time
    if expected_count:
        native_candidate = native_result.candidates[0]
        metric_candidate = metric_result.candidates[0]
        assert metric_candidate.path_length == pytest.approx(
            scale.to_metres(native_candidate.path_length)
        )
        assert metric_candidate.minimum_travel_time == pytest.approx(2)
        assert metric_candidate.minimum_travel_time == pytest.approx(
            native_candidate.minimum_travel_time
        )
    assert native_graph.nodes[1].position == (30, 40, 25)
    assert native_movement.max_speed_m_s == 25


def test_policy_stays_si_and_pending_authority_is_not_upgraded(scale: ArchitecturalScale) -> None:
    policy = PhysicalPolicy(
        policy_id="pending-body", config_version="unit-policy-v1", body_radius_m=0.30,
        body_height_m=1.70, body_clearance_m=0.05, collision_tolerance_m=0,
    )
    before = policy.model_dump(mode="json")
    report = physical_policy_in_blender_units(
        policy, scale, source_asset_sha256=scale.source_asset_sha256,
    )
    assert report["policy_metres"] == before
    assert report["lengths_blender_units"] == {
        "body_radius_bu": pytest.approx(0.30 / 0.0247),
        "body_height_bu": pytest.approx(1.70 / 0.0247),
        "body_clearance_bu": pytest.approx(0.05 / 0.0247),
        "portal_horizontal_clearance_bu": None,
        "portal_vertical_clearance_bu": None,
        "collision_tolerance_bu": 0,
    }
    assert report["physical_authority_upgraded"] is False
    assert before["authority"] == "HUMAN_REVIEW"
    assert policy.model_dump(mode="json") == before


def test_metric_report_preserves_bu_and_unavailable_results(scale: ArchitecturalScale) -> None:
    lengths = {"ADE": 1.25, "FDE": 0.5, "minADE@K": None, "path_length": 141.732246}
    speeds = {"maximum_speed": 32.0, "stationary": 0.0}
    before = lengths.copy(), speeds.copy()
    report = native_quantity_report(
        scale, source_asset_sha256=scale.source_asset_sha256,
        lengths_bu=lengths, speeds_bu_per_s=speeds,
    )
    assert report["lengths"] == {
        "ADE": {"bu": 1.25, "m": pytest.approx(0.030875)},
        "FDE": {"bu": 0.5, "m": pytest.approx(0.01235)},
        "minADE@K": {"bu": None, "m": None},
        "path_length": {"bu": 141.732246, "m": pytest.approx(3.5007864762)},
    }
    assert report["speeds"] == {
        "maximum_speed": {"bu_per_s": 32, "m_per_s": pytest.approx(0.7904)},
        "stationary": {"bu_per_s": 0, "m_per_s": 0},
    }
    assert report["coverage_recomputed"] is False
    assert report["inference_outputs_modified"] is False
    assert (lengths, speeds) == before


@pytest.mark.parametrize("value", [-1, True, math.nan, math.inf])
@pytest.mark.parametrize("kind", ["lengths_bu", "speeds_bu_per_s"])
def test_report_refuses_invalid_physical_scalars(
    scale: ArchitecturalScale, value: float, kind: str,
) -> None:
    with pytest.raises(ValueError, match="finite nonnegative"):
        native_quantity_report(
            scale, source_asset_sha256=scale.source_asset_sha256, **{kind: {"bad": value}},
        )


def test_all_explicit_source_adapters_refuse_source_mismatch(scale: ArchitecturalScale) -> None:
    mismatched = "0" * 64
    calls = (
        lambda: native_camera_to_metres(_camera(), scale, source_asset_sha256=mismatched),
        lambda: native_plane_to_metres(_plane(), scale, source_asset_sha256=mismatched),
        lambda: native_observation_to_metres(
            _observation("start", 0), scale, source_asset_sha256=mismatched,
        ),
        lambda: native_movement_to_metres(
            MovementConstraints(max_speed_m_s=25), scale, source_asset_sha256=mismatched,
        ),
        lambda: native_search_policy_to_metres(
            GraphSearchPolicy(), scale, source_asset_sha256=mismatched,
        ),
        lambda: native_quantity_report(scale, source_asset_sha256=mismatched),
        lambda: physical_policy_in_blender_units(
            PhysicalPolicy(policy_id="pending", config_version="v1"), scale,
            source_asset_sha256=mismatched,
        ),
    )
    for call in calls:
        with pytest.raises(ValueError, match="source SHA-256 mismatch"):
            call()


def test_navigation_requires_matching_explicit_source(scale: ArchitecturalScale) -> None:
    wrong_source = _navigation(scale).model_copy(update={"source_asset_sha256": "0" * 64})
    with pytest.raises(ValueError, match="source SHA-256 mismatch"):
        native_navigation_to_metres(wrong_source, scale)
    unbound = _navigation(scale).model_copy(update={
        "data_kind": NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
        "source_asset_sha256": None,
    })
    with pytest.raises(ValueError, match="explicit source asset SHA-256"):
        native_navigation_to_metres(unbound, scale)


def test_projection_adapter_does_not_accept_forged_truth_provenance(
    scale: ArchitecturalScale,
) -> None:
    point = _observation("start", 0).projected_path[0].model_copy(
        update={"provenance": Provenance.GROUND_TRUTH}
    )
    with pytest.raises(ValidationError):
        native_projected_point_to_metres(
            point, scale, source_asset_sha256=scale.source_asset_sha256,
        )


def test_adapters_revalidate_forged_scale_and_nested_models(scale: ArchitecturalScale) -> None:
    forged = scale.model_copy(update={"authority": Authority.HUMAN_REVIEW})
    with pytest.raises(ValidationError, match="APPROVED"):
        native_camera_to_metres(_camera(), forged, source_asset_sha256=scale.source_asset_sha256)
    invalid_plane = _plane().model_copy(update={"point": (math.nan, 0, 0)})
    with pytest.raises(ValidationError):
        native_plane_to_metres(invalid_plane, scale, source_asset_sha256=scale.source_asset_sha256)
    invalid_point = _observation("start", 0).projected_path[0].model_copy(
        update={"world_position": (math.inf, 0, 0)}
    )
    invalid_observation = _observation("start", 0).model_copy(
        update={"projected_path": (invalid_point,)}
    )
    with pytest.raises(ValidationError):
        native_observation_to_metres(
            invalid_observation, scale, source_asset_sha256=scale.source_asset_sha256,
        )


def test_reports_require_nonempty_quantity_identity(scale: ArchitecturalScale) -> None:
    with pytest.raises(ValueError, match="quantity identities"):
        native_quantity_report(
            scale, source_asset_sha256=scale.source_asset_sha256, lengths_bu={" ": 1},
        )
