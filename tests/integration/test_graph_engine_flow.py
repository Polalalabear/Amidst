"""Sanitized 2D evidence flows through M6-M8 without Ground Truth input."""

import pytest

from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.geometry import Plane
from amidst.domain.navigation import (
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
)
from amidst.domain.observation import Observation
from amidst.domain.search import MovementConstraints
from amidst.domain.topology import (
    CameraTopologyConfig,
    CameraTopologyNode,
    CameraTransition,
    CameraTransitionType,
)
from amidst.domain.trajectory import TerminationReason
from amidst.geometry.inverse_projection import InverseProjectionService
from amidst.graph.engine import SpatiotemporalGraphEngine
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.simulation.raycast_types import RaycastResult
from amidst.simulation.visibility import observe_point


def _camera(camera_id: str) -> Camera:
    return Camera(
        camera_id=camera_id,
        width=100,
        height=100,
        fx=50,
        fy=50,
        cx=50,
        cy=50,
        camera_to_world=(
            (1, 0, 0, 0),
            (0, 1, 0, 0),
            (0, 0, 1, 10),
            (0, 0, 0, 1),
        ),
        clip_start=1,
        clip_end=20,
        floor_id="SYNTHETIC_TEST_FIXTURE",
    )


def test_sanitized_frame_to_projected_observation_to_topk_candidate() -> None:
    camera_a = _camera("CAM_A")
    camera_b = _camera("CAM_B")
    plane = Plane(
        plane_id="synthetic_floor",
        point=(0, 0, 0),
        normal=(0, 0, 1),
        floor_id="SYNTHETIC_TEST_FIXTURE",
    )
    def clear(
        _origin: tuple[float, float, float], _target: tuple[float, float, float]
    ) -> RaycastResult:
        return RaycastResult(False, "CLEAR")

    start_frame = observe_point(
        camera_a,
        (0, 0, 0),
        timestamp=1,
        target_id="target",
        frame_id=1,
        raycaster=clear,
    )
    end_frame = observe_point(
        camera_b,
        (2, 0, 0),
        timestamp=3,
        target_id="target",
        frame_id=2,
        raycaster=clear,
    )
    assert "world_position" not in start_frame.model_dump()
    assert "world_position" not in end_frame.model_dump()

    start_point = InverseProjectionService(camera_a, plane).project_frame(start_frame)
    end_point = InverseProjectionService(camera_b, plane).project_frame(end_frame)
    start = Observation(
        observation_id="obs_start",
        target_id="target",
        camera_id="CAM_A",
        start_time=1,
        end_time=1,
        floor_id=plane.floor_id,
        frames=(start_frame,),
        projected_path=(start_point.model_copy(update={"observation_id": "obs_start"}),),
        provenance=Provenance.PROJECTED,
    )
    end = Observation(
        observation_id="obs_end",
        target_id="target",
        camera_id="CAM_B",
        start_time=3,
        end_time=3,
        floor_id=plane.floor_id,
        frames=(end_frame,),
        projected_path=(end_point.model_copy(update={"observation_id": "obs_end"}),),
        provenance=Provenance.PROJECTED,
    )

    node_a = NavigationNode(
        node_id="node_a",
        position=(0, 0, 0),
        floor_id=plane.floor_id,
    )
    node_b = NavigationNode(
        node_id="node_b",
        position=(2, 0, 0),
        floor_id=plane.floor_id,
    )
    edge = NavigationEdge(
        edge_id="authorized_corridor",
        from_node_id="node_a",
        to_node_id="node_b",
        polyline=(node_a.position, node_b.position),
    )
    navigation = NavigationGraph(
        NavigationGraphConfig(
            graph_id="synthetic_flow",
            spatial_context_id="SYNTHETIC_TEST_FIXTURE",
            data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
            nodes=(node_a, node_b),
            edges=(edge,),
        )
    )
    topology = CameraTopologyGraph(
        CameraTopologyConfig(
            topology_id="synthetic_flow_topology",
            navigation_graph_id="synthetic_flow",
            spatial_context_id="SYNTHETIC_TEST_FIXTURE",
            data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
            nodes=(
                CameraTopologyNode(camera_id="CAM_A", floor_id=plane.floor_id),
                CameraTopologyNode(camera_id="CAM_B", floor_id=plane.floor_id),
            ),
            transitions=(
                CameraTransition(
                    transition_id="CAM_A_TO_CAM_B",
                    from_camera_id="CAM_A",
                    to_camera_id="CAM_B",
                    transition_type=CameraTransitionType.ADJACENT,
                    navigation_from_node_id="node_a",
                    navigation_to_node_id="node_b",
                    navigation_edge_ids=("authorized_corridor",),
                ),
            ),
        )
    )
    engine = SpatiotemporalGraphEngine(
        NavigationNetwork(navigation, topology),
        MovementConstraints(max_speed_m_s=1),
    )
    result = engine.propose_feasible_trajectories(start, end)

    assert start_point.world_position == pytest.approx(node_a.position)
    assert end_point.world_position == pytest.approx(node_b.position)
    assert result.termination_reason == TerminationReason.COMPLETE
    assert result.complete
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.navmesh_corridor == ("authorized_corridor",)
    assert candidate.path_length == 2
    assert candidate.minimum_travel_time == 2
    assert candidate.estimated_travel_time == 2
    assert candidate.provenance == Provenance.INFERRED_GAP
    assert "ground_truth" not in result.model_dump_json().lower()
