"""M8 deterministic, bounded and Ground-Truth-free graph-search tests."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import amidst.graph.engine as engine_module
from amidst.domain.common import Provenance
from amidst.domain.navigation import (
    CrossFloorPolicy,
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
    NavigationTransitionType,
)
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.topology import (
    CameraTopologyConfig,
    CameraTopologyNode,
    CameraTransition,
    CameraTransitionType,
)
from amidst.domain.trajectory import TerminationReason
from amidst.graph.engine import GraphInputError, GraphInputFailure, SpatiotemporalGraphEngine
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph


def _node(
    node_id: str,
    position: tuple[float, float, float],
    floor_id: str = "1F",
) -> NavigationNode:
    return NavigationNode(node_id=node_id, position=position, floor_id=floor_id)


def _edge(
    edge_id: str,
    start: NavigationNode,
    end: NavigationNode,
    *,
    points: tuple[tuple[float, float, float], ...] | None = None,
    transition_type: NavigationTransitionType = NavigationTransitionType.WALK,
    stair_id: str | None = None,
) -> NavigationEdge:
    return NavigationEdge(
        edge_id=edge_id,
        from_node_id=start.node_id,
        to_node_id=end.node_id,
        polyline=points or (start.position, end.position),
        transition_type=transition_type,
        stair_id=stair_id,
    )


def _transition(
    transition_id: str,
    start_camera: str,
    end_camera: str,
    start_node: str,
    end_node: str,
    edge_ids: tuple[str, ...],
    transition_type: CameraTransitionType = CameraTransitionType.ADJACENT,
) -> CameraTransition:
    return CameraTransition(
        transition_id=transition_id,
        from_camera_id=start_camera,
        to_camera_id=end_camera,
        transition_type=transition_type,
        navigation_from_node_id=start_node,
        navigation_to_node_id=end_node,
        navigation_edge_ids=edge_ids,
    )


def _network(
    nodes: tuple[NavigationNode, ...],
    edges: tuple[NavigationEdge, ...],
    cameras: tuple[CameraTopologyNode, ...],
    transitions: tuple[CameraTransition, ...],
    *,
    graph_id: str = "synthetic_graph",
    cross_floor_policy: CrossFloorPolicy = CrossFloorPolicy.DISCONNECTED,
) -> NavigationNetwork:
    navigation = NavigationGraph(
        NavigationGraphConfig(
            graph_id=graph_id,
            spatial_context_id="SYNTHETIC_TEST_FIXTURE",
            data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
            cross_floor_policy=cross_floor_policy,
            nodes=nodes,
            edges=edges,
        )
    )
    topology = CameraTopologyGraph(
        CameraTopologyConfig(
            topology_id=f"{graph_id}_topology",
            navigation_graph_id=graph_id,
            spatial_context_id="SYNTHETIC_TEST_FIXTURE",
            data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
            nodes=cameras,
            transitions=transitions,
        )
    )
    return NavigationNetwork(navigation, topology)


def _point(
    point_id: str,
    camera_id: str,
    timestamp: float,
    position: tuple[float, float, float],
    *,
    floor_id: str | None = "1F",
    observation_id: str | None = None,
) -> ProjectedPoint:
    return ProjectedPoint(
        point_id=point_id,
        camera_id=camera_id,
        plane_id=f"plane_{floor_id or 'missing'}",
        timestamp=timestamp,
        world_position=position,
        floor_id=floor_id,
        observation_id=observation_id,
    )


def _observation(
    observation_id: str,
    camera_id: str,
    points: tuple[ProjectedPoint, ...],
    *,
    target_id: str = "target",
    floor_id: str | None = "1F",
) -> Observation:
    return Observation(
        observation_id=observation_id,
        target_id=target_id,
        camera_id=camera_id,
        start_time=float(points[0].timestamp),
        end_time=float(points[-1].timestamp),
        floor_id=floor_id,
        projected_path=points,
        provenance=Provenance.PROJECTED,
    )


def _endpoints(
    start_position: tuple[float, float, float] = (0, 0, 0),
    end_position: tuple[float, float, float] = (2, 0, 0),
    *,
    start_camera: str = "CAM_A",
    end_camera: str = "CAM_D",
    start_time: float = 1,
    end_time: float = 11,
    start_floor: str | None = "1F",
    end_floor: str | None = "1F",
) -> tuple[Observation, Observation]:
    start = _observation(
        "obs_start",
        start_camera,
        (_point("p_start", start_camera, start_time, start_position, floor_id=start_floor),),
        floor_id=start_floor,
    )
    end = _observation(
        "obs_end",
        end_camera,
        (_point("p_end", end_camera, end_time, end_position, floor_id=end_floor),),
        floor_id=end_floor,
    )
    return start, end


def _branch_network(*, reverse_inputs: bool = False) -> NavigationNetwork:
    start = _node("N0", (0, 0, 0))
    upper = _node("N1", (1, 1, 0))
    lower = _node("N2", (1, -1, 0))
    end = _node("N3", (2, 0, 0))
    nodes = (start, upper, lower, end)
    edges = (
        _edge("m_direct", start, end),
        _edge("z_upper_1", start, upper),
        _edge("z_upper_2", upper, end),
        _edge("a_lower_1", start, lower),
        _edge("a_lower_2", lower, end),
    )
    cameras = (
        CameraTopologyNode(camera_id="CAM_A", floor_id="1F"),
        CameraTopologyNode(camera_id="CAM_D", floor_id="1F"),
    )
    transitions = (
        _transition("route_direct", "CAM_A", "CAM_D", "N0", "N3", ("m_direct",)),
        _transition(
            "route_upper",
            "CAM_A",
            "CAM_D",
            "N0",
            "N3",
            ("z_upper_1", "z_upper_2"),
        ),
        _transition(
            "route_lower",
            "CAM_A",
            "CAM_D",
            "N0",
            "N3",
            ("a_lower_1", "a_lower_2"),
        ),
    )
    if reverse_inputs:
        nodes = tuple(reversed(nodes))
        edges = tuple(reversed(edges))
        cameras = tuple(reversed(cameras))
        transitions = tuple(reversed(transitions))
    return _network(nodes, edges, cameras, transitions, graph_id="branch_graph")


def _engine(
    network: NavigationNetwork,
    *,
    speed: float = 10,
    policy: GraphSearchPolicy | None = None,
    clock: Any = None,
) -> SpatiotemporalGraphEngine:
    kwargs: dict[str, Any] = {}
    if clock is not None:
        kwargs["clock"] = clock
    return SpatiotemporalGraphEngine(
        network,
        MovementConstraints(max_speed_m_s=speed),
        policy,
        **kwargs,
    )


def test_topk_uses_only_explicit_transition_routes() -> None:
    start_node = _node("A", (0, 0, 0))
    end_node = _node("B", (2, 0, 0))
    direct = _edge("forbidden_shortcut", start_node, end_node)
    designated = _edge(
        "designated",
        start_node,
        end_node,
        points=((0, 0, 0), (1, 1, 0), (2, 0, 0)),
    )
    network = _network(
        (start_node, end_node),
        (direct, designated),
        (
            CameraTopologyNode(camera_id="CAM_A", floor_id="1F"),
            CameraTopologyNode(camera_id="CAM_D", floor_id="1F"),
        ),
        (
            _transition(
                "authorized",
                "CAM_A",
                "CAM_D",
                "A",
                "B",
                ("designated",),
            ),
        ),
    )
    start, end = _endpoints()
    result = _engine(
        network,
        policy=GraphSearchPolicy(max_detour_ratio=1),
    ).propose_feasible_trajectories(start, end)
    assert result.termination_reason == TerminationReason.COMPLETE
    assert tuple(candidate.navmesh_corridor for candidate in result.candidates) == (
        ("designated",),
    )
    assert result.candidates[0].path_length == pytest.approx(2 * math.sqrt(2))


def test_topk_order_ids_and_payload_are_input_order_independent() -> None:
    start, end = _endpoints()
    forward = _engine(_branch_network()).propose_feasible_trajectories(start, end, max_paths=3)
    reversed_result = _engine(_branch_network(reverse_inputs=True)).propose_feasible_trajectories(
        start, end, max_paths=3
    )
    expected = (
        ("m_direct",),
        ("a_lower_1", "a_lower_2"),
        ("z_upper_1", "z_upper_2"),
    )
    assert tuple(item.navmesh_corridor for item in forward.candidates) == expected
    assert tuple(item.navmesh_corridor for item in reversed_result.candidates) == expected
    assert tuple(item.candidate_id for item in forward.candidates) == tuple(
        item.candidate_id for item in reversed_result.candidates
    )
    assert forward.termination_reason == TerminationReason.COMPLETE
    direct = forward.candidates[0]
    assert direct.path_length == 2
    assert direct.minimum_travel_time == pytest.approx(0.2)
    assert direct.estimated_travel_time == 10
    assert direct.temporal_cost == pytest.approx(9.8)
    assert direct.provenance == Provenance.INFERRED_GAP
    assert direct.path_score is None
    different_speed = _engine(_branch_network(), speed=20).propose_feasible_trajectories(
        start, end, max_paths=3
    )
    assert different_speed.candidates[0].candidate_id != direct.candidate_id


def test_parallel_routes_are_distinct_and_duplicate_routes_are_deduplicated() -> None:
    start_node = _node("A", (0, 0, 0))
    end_node = _node("B", (2, 0, 0))
    first = _edge("edge_a", start_node, end_node)
    second = _edge("edge_b", start_node, end_node)
    cameras = (
        CameraTopologyNode(camera_id="CAM_A", floor_id="1F"),
        CameraTopologyNode(camera_id="CAM_D", floor_id="1F"),
    )
    transitions = (
        _transition("a", "CAM_A", "CAM_D", "A", "B", ("edge_a",)),
        _transition("b", "CAM_A", "CAM_D", "A", "B", ("edge_b",)),
        _transition("duplicate", "CAM_A", "CAM_D", "A", "B", ("edge_a",)),
    )
    network = _network((start_node, end_node), (first, second), cameras, transitions)
    start, end = _endpoints()
    result = _engine(network).propose_feasible_trajectories(start, end, max_paths=3)
    assert tuple(item.navmesh_corridor for item in result.candidates) == (
        ("edge_a",),
        ("edge_b",),
    )
    assert len({item.candidate_id for item in result.candidates}) == 2
    assert result.termination_reason == TerminationReason.COMPLETE


def test_max_paths_requires_one_additional_feasible_candidate() -> None:
    start, end = _endpoints()
    network = _branch_network()
    truncated = _engine(network).propose_feasible_trajectories(start, end, max_paths=2)
    assert len(truncated.candidates) == 2
    assert truncated.termination_reason == TerminationReason.MAX_PATHS_REACHED
    assert not truncated.complete

    exactly_three_policy = GraphSearchPolicy(max_candidate_paths=3)
    exactly_three = _engine(network, policy=exactly_three_policy).propose_feasible_trajectories(
        start, end, max_paths=3
    )
    assert len(exactly_three.candidates) == 3
    assert exactly_three.termination_reason == TerminationReason.COMPLETE
    assert exactly_three.complete
    assert tuple(item.candidate_id for item in truncated.candidates) == tuple(
        item.candidate_id for item in exactly_three.candidates[:2]
    )

    policy_capped = _engine(
        network,
        policy=GraphSearchPolicy(max_candidate_paths=2),
    ).propose_feasible_trajectories(start, end, max_paths=3)
    assert len(policy_capped.candidates) == 2
    assert policy_capped.termination_reason == TerminationReason.MAX_PATHS_REACHED


def _chain_network(*, discontinuous: bool = False) -> NavigationNetwork:
    n0 = _node("N0", (0, 0, 0))
    n1 = _node("N1", (1, 0, 0))
    n2 = _node("N2", (2, 0, 0))
    n3 = _node("N3", (3, 0, 0))
    edges = (
        _edge("A_B", n0, n1),
        _edge("bridge", n1, n2),
        _edge("B_C", n2 if discontinuous else n1, n3),
    )
    transitions = (
        _transition("A_B", "CAM_A", "CAM_B", "N0", "N1", ("A_B",)),
        _transition(
            "B_C",
            "CAM_B",
            "CAM_C",
            "N2" if discontinuous else "N1",
            "N3",
            ("B_C",),
        ),
    )
    return _network(
        (n0, n1, n2, n3),
        edges,
        tuple(
            CameraTopologyNode(camera_id=name, floor_id="1F")
            for name in ("CAM_A", "CAM_B", "CAM_C")
        ),
        transitions,
        graph_id="chain_graph",
    )


def test_camera_reachability_is_transitive_and_directed() -> None:
    network = _chain_network()
    assert network.topology.minimum_hop_transition_path("CAM_A", "CAM_C") == ("A_B", "B_C")
    assert network.topology.minimum_hop_transition_path("CAM_C", "CAM_A") is None
    start, end = _endpoints(
        end_position=(3, 0, 0),
        start_camera="CAM_A",
        end_camera="CAM_C",
    )
    result = _engine(network).propose_feasible_trajectories(start, end)
    assert result.candidates[0].navmesh_corridor == ("A_B", "B_C")

    reverse_start, reverse_end = _endpoints(
        start_position=(3, 0, 0),
        end_position=(0, 0, 0),
        start_camera="CAM_C",
        end_camera="CAM_A",
    )
    reverse = _engine(network).propose_feasible_trajectories(reverse_start, reverse_end)
    assert reverse.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    assert reverse.rejection_reasons == ("NO_FEASIBLE_AUTHORIZED_ROUTE",)


def test_camera_reachability_tie_is_canonical_across_input_order() -> None:
    cameras = tuple(
        CameraTopologyNode(camera_id=name, floor_id="1F")
        for name in ("CAM_A", "CAM_B", "CAM_C", "CAM_D")
    )
    transitions = (
        _transition("z_ab", "CAM_A", "CAM_B", "A", "B", ("ab",)),
        _transition("z_bd", "CAM_B", "CAM_D", "B", "D", ("bd",)),
        _transition("a_ac", "CAM_A", "CAM_C", "A", "C", ("ac",)),
        _transition("a_cd", "CAM_C", "CAM_D", "C", "D", ("cd",)),
    )
    expected = ("a_ac", "a_cd")
    for camera_order in (cameras, tuple(reversed(cameras))):
        for transition_order in (transitions, tuple(reversed(transitions))):
            topology = CameraTopologyGraph(
                CameraTopologyConfig(
                    topology_id="reachability",
                    navigation_graph_id="unused",
                    spatial_context_id="SYNTHETIC_TEST_FIXTURE",
                    data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
                    nodes=camera_order,
                    transitions=transition_order,
                )
            )
            assert topology.minimum_hop_transition_path("CAM_A", "CAM_D") == expected


def test_transition_sequences_must_be_contiguous_without_silent_bridge() -> None:
    network = _chain_network(discontinuous=True)
    start, end = _endpoints(
        end_position=(3, 0, 0),
        start_camera="CAM_A",
        end_camera="CAM_C",
    )
    result = _engine(network).propose_feasible_trajectories(start, end)
    assert result.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    assert result.rejection_reasons == ("NO_FEASIBLE_AUTHORIZED_ROUTE",)
    assert "bridge" not in tuple(
        edge_id for item in result.candidates for edge_id in item.navmesh_corridor
    )


def test_speed_boundary_and_actual_projected_endpoint_gap() -> None:
    n0 = _node("N0", (0, 0, 0))
    n1 = _node("N1", (4, 0, 0))
    edge = _edge("route", n0, n1)
    network = _network(
        (n0, n1),
        (edge,),
        (
            CameraTopologyNode(camera_id="CAM_A", floor_id="1F"),
            CameraTopologyNode(camera_id="CAM_D", floor_id="1F"),
        ),
        (_transition("route", "CAM_A", "CAM_D", "N0", "N1", ("route",)),),
    )
    exact_start, exact_end = _endpoints(end_position=(4, 0, 0), end_time=3)
    exact = _engine(network, speed=2).propose_feasible_trajectories(exact_start, exact_end)
    assert exact.candidates[0].minimum_travel_time == 2
    assert exact.candidates[0].temporal_cost == 0

    too_fast_start, too_fast_end = _endpoints(end_position=(4, 0, 0), end_time=2.9)
    impossible = _engine(network, speed=2).propose_feasible_trajectories(
        too_fast_start, too_fast_end
    )
    assert impossible.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    assert "PHYSICALLY_IMPOSSIBLE_SPEED" in impossible.rejection_reasons

    start_points = (
        _point("s1", "CAM_A", 1, (0, 0, 0)),
        _point("s2", "CAM_A", 2, (0, 0, 0)),
    )
    end_points = (
        _point("e1", "CAM_D", 8, (4, 0, 0)),
        _point("e2", "CAM_D", 9, (4, 0, 0)),
    )
    endpoints = _engine(network, speed=2).propose_feasible_trajectories(
        _observation("start_multi", "CAM_A", start_points),
        _observation("end_multi", "CAM_D", end_points),
    )
    assert endpoints.candidates[0].estimated_travel_time == 6


def test_non_integer_speed_equality_is_not_pruned_by_rounding() -> None:
    n0 = _node("N0", (0, 0, 0))
    n1 = _node("N1", (0.1, 0, 0))
    network = _network(
        (n0, n1),
        (_edge("route", n0, n1),),
        (
            CameraTopologyNode(camera_id="CAM_A", floor_id="1F"),
            CameraTopologyNode(camera_id="CAM_D", floor_id="1F"),
        ),
        (_transition("route", "CAM_A", "CAM_D", "N0", "N1", ("route",)),),
        graph_id="rounding_boundary",
    )
    speed = math.pi
    start, end = _endpoints(
        end_position=(0.1, 0, 0),
        start_time=0,
        end_time=0.1 / speed,
    )
    result = _engine(network, speed=speed).propose_feasible_trajectories(start, end)
    assert result.termination_reason == TerminationReason.COMPLETE
    assert len(result.candidates) == 1
    assert result.candidates[0].temporal_cost == pytest.approx(0)


def test_close_speed_boundary_is_canonicalized_without_schema_failure() -> None:
    n0 = _node("N0", (0, 0, 0))
    n1 = _node("N1", (math.nextafter(1.0, math.inf), 0, 0))
    network = _network(
        (n0, n1),
        (_edge("route", n0, n1),),
        (
            CameraTopologyNode(camera_id="CAM_A", floor_id="1F"),
            CameraTopologyNode(camera_id="CAM_D", floor_id="1F"),
        ),
        (_transition("route", "CAM_A", "CAM_D", "N0", "N1", ("route",)),),
        graph_id="close_boundary",
    )
    start, end = _endpoints(
        end_position=n1.position,
        start_time=0,
        end_time=1,
    )
    result = _engine(network, speed=1).propose_feasible_trajectories(start, end)
    assert result.termination_reason == TerminationReason.COMPLETE
    assert result.candidates[0].minimum_travel_time == 1
    assert result.candidates[0].temporal_cost == 0


def test_large_magnitude_hard_bound_does_not_gain_relative_tolerance() -> None:
    n0 = _node("N0", (0, 0, 0))
    n1 = _node("N1", (1_000_000_000_000.5, 0, 0))
    network = _network(
        (n0, n1),
        (_edge("route", n0, n1),),
        (
            CameraTopologyNode(camera_id="CAM_A", floor_id="1F"),
            CameraTopologyNode(camera_id="CAM_D", floor_id="1F"),
        ),
        (_transition("route", "CAM_A", "CAM_D", "N0", "N1", ("route",)),),
        graph_id="large_hard_bound",
    )
    start, end = _endpoints(
        end_position=n1.position,
        start_time=0,
        end_time=10,
    )
    result = _engine(
        network,
        speed=1e13,
        policy=GraphSearchPolicy(max_path_length_m=1_000_000_000_000),
    ).propose_feasible_trajectories(start, end)
    assert result.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    assert "MAX_PATH_LENGTH_EXCEEDED" in result.rejection_reasons


def test_invalid_endpoint_inputs_fail_closed() -> None:
    network = _branch_network()
    engine = _engine(network)
    valid_start, valid_end = _endpoints()
    observed_shell = Observation(
        observation_id="observed",
        target_id="target",
        camera_id="CAM_A",
        start_time=0,
        end_time=1,
    )
    with pytest.raises(GraphInputError) as captured:
        engine.propose_feasible_trajectories(observed_shell, valid_end)
    assert captured.value.failure == GraphInputFailure.INVALID_OBSERVATION

    other_target = valid_end.model_copy(update={"target_id": "other"})
    with pytest.raises(GraphInputError) as captured:
        engine.propose_feasible_trajectories(valid_start, other_target)
    assert captured.value.failure == GraphInputFailure.TARGET_MISMATCH

    duplicate = valid_end.model_copy(update={"observation_id": valid_start.observation_id})
    with pytest.raises(GraphInputError) as captured:
        engine.propose_feasible_trajectories(valid_start, duplicate)
    assert captured.value.failure == GraphInputFailure.DUPLICATE_OBSERVATION

    zero_gap_start, zero_gap_end = _endpoints(end_time=1)
    with pytest.raises(GraphInputError) as captured:
        engine.propose_feasible_trajectories(zero_gap_start, zero_gap_end)
    assert captured.value.failure == GraphInputFailure.INVALID_TIME_GAP

    missing_floor_start, missing_floor_end = _endpoints(
        start_floor=None,
        end_floor=None,
    )
    with pytest.raises(GraphInputError) as captured:
        engine.propose_feasible_trajectories(missing_floor_start, missing_floor_end)
    assert captured.value.failure == GraphInputFailure.ENDPOINT_FLOOR_REQUIRED

    off_network_start, off_network_end = _endpoints(start_position=(0.1, 0, 0))
    with pytest.raises(GraphInputError) as captured:
        engine.propose_feasible_trajectories(off_network_start, off_network_end)
    assert captured.value.failure == GraphInputFailure.ENDPOINT_OFF_NETWORK

    unknown_start, unknown_end = _endpoints(start_camera="CAM_UNKNOWN")
    with pytest.raises(GraphInputError) as captured:
        engine.propose_feasible_trajectories(unknown_start, unknown_end)
    assert captured.value.failure == GraphInputFailure.UNKNOWN_CAMERA


def test_same_camera_same_node_yields_stationary_candidate() -> None:
    node = _node("N0", (0, 0, 0))
    network = _network(
        (node,),
        (),
        (CameraTopologyNode(camera_id="CAM_A", floor_id="1F"),),
        (),
        graph_id="stationary",
    )
    start, end = _endpoints(
        end_position=(0, 0, 0),
        start_camera="CAM_A",
        end_camera="CAM_A",
    )
    result = _engine(network).propose_feasible_trajectories(start, end)
    assert result.termination_reason == TerminationReason.COMPLETE
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.navmesh_corridor == ()
    assert candidate.path_length == 0
    assert candidate.minimum_travel_time == 0
    assert candidate.polyline == ((0, 0, 0), (0, 0, 0))


def test_camera_return_cycle_is_allowed_and_bounded_by_path_length() -> None:
    n0 = _node("N0", (0, 0, 0))
    n1 = _node("N1", (1, 0, 0))
    n2 = _node("N2", (2, 0, 0))
    edges = (
        _edge("e_ab", n0, n1),
        _edge("e_ba", n1, n0),
        _edge("e_ac", n0, n2),
    )
    transitions = (
        _transition("A_B", "CAM_A", "CAM_B", "N0", "N1", ("e_ab",)),
        _transition("B_A", "CAM_B", "CAM_A", "N1", "N0", ("e_ba",)),
        _transition("A_C", "CAM_A", "CAM_C", "N0", "N2", ("e_ac",)),
    )
    network = _network(
        (n0, n1, n2),
        edges,
        tuple(
            CameraTopologyNode(camera_id=name, floor_id="1F")
            for name in ("CAM_A", "CAM_B", "CAM_C")
        ),
        transitions,
        graph_id="return_cycle",
    )
    start, end = _endpoints(
        end_position=(2, 0, 0),
        start_camera="CAM_A",
        end_camera="CAM_C",
    )
    result = _engine(
        network,
        policy=GraphSearchPolicy(max_path_length_m=4, max_detour_ratio=2),
    ).propose_feasible_trajectories(start, end, max_paths=3)
    assert tuple(item.navmesh_corridor for item in result.candidates) == (
        ("e_ac",),
        ("e_ab", "e_ba", "e_ac"),
    )
    assert result.termination_reason == TerminationReason.COMPLETE

    same_start, same_end = _endpoints(
        end_position=(0, 0, 0),
        start_camera="CAM_A",
        end_camera="CAM_A",
    )
    same_camera = _engine(
        network,
        policy=GraphSearchPolicy(max_path_length_m=2),
    ).propose_feasible_trajectories(same_start, same_end, max_paths=3)
    assert tuple(item.navmesh_corridor for item in same_camera.candidates) == (
        (),
        ("e_ab", "e_ba"),
    )
    assert same_camera.termination_reason == TerminationReason.COMPLETE


def test_explicit_synthetic_stair_respects_direction() -> None:
    lower = _node("lower", (0, 0, 0), "1F")
    upper = _node("upper", (0, 0, 3), "2F")
    stair = _edge(
        "stair_up",
        lower,
        upper,
        points=((0, 0, 0), (1, 0, 1.5), (0, 0, 3)),
        transition_type=NavigationTransitionType.STAIR_UP,
        stair_id="SYNTHETIC_TEST_FIXTURE_STAIR",
    )
    network = _network(
        (lower, upper),
        (stair,),
        (
            CameraTopologyNode(camera_id="CAM_LOWER", floor_id="1F"),
            CameraTopologyNode(camera_id="CAM_UPPER", floor_id="2F"),
        ),
        (
            _transition(
                "stair_up",
                "CAM_LOWER",
                "CAM_UPPER",
                "lower",
                "upper",
                ("stair_up",),
                CameraTransitionType.STAIR_UP,
            ),
        ),
        graph_id="synthetic_stair",
        cross_floor_policy=CrossFloorPolicy.EXPLICIT_PARAMETERIZED_STAIRS,
    )
    start, end = _endpoints(
        end_position=(0, 0, 3),
        start_camera="CAM_LOWER",
        end_camera="CAM_UPPER",
        start_floor="1F",
        end_floor="2F",
    )
    up = _engine(network).propose_feasible_trajectories(start, end)
    assert up.candidates[0].navmesh_corridor == ("stair_up",)
    reverse_start, reverse_end = _endpoints(
        start_position=(0, 0, 3),
        end_position=(0, 0, 0),
        start_camera="CAM_UPPER",
        end_camera="CAM_LOWER",
        start_floor="2F",
        end_floor="1F",
    )
    down = _engine(network).propose_feasible_trajectories(reverse_start, reverse_end)
    assert down.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    assert down.rejection_reasons == ("NO_FEASIBLE_AUTHORIZED_ROUTE",)


class _ScriptedClock:
    def __init__(self, values: tuple[float, ...]) -> None:
        self._values = iter(values)
        self._last = values[-1]

    def __call__(self) -> float:
        return next(self._values, self._last)


def test_search_limits_report_incomplete_results() -> None:
    start, end = _endpoints()
    network = _branch_network()

    branch = _engine(
        network,
        policy=GraphSearchPolicy(max_branch_factor=2),
    ).propose_feasible_trajectories(start, end)
    assert branch.termination_reason == TerminationReason.MAX_BRANCH_FACTOR
    assert branch.expanded_nodes == 1
    assert not branch.complete

    nodes = _engine(
        network,
        policy=GraphSearchPolicy(max_search_nodes=1),
    ).propose_feasible_trajectories(start, end)
    assert nodes.termination_reason == TerminationReason.MAX_SEARCH_NODES
    assert nodes.expanded_nodes == 1
    assert not nodes.complete

    timeout = _engine(
        network,
        policy=GraphSearchPolicy(max_search_time_s=1),
        clock=_ScriptedClock((0, 2)),
    ).propose_feasible_trajectories(start, end)
    assert timeout.termination_reason == TerminationReason.SEARCH_TIMEOUT
    assert timeout.expanded_nodes == 0
    assert not timeout.complete

    partial = _engine(
        network,
        policy=GraphSearchPolicy(max_search_time_s=1),
        clock=_ScriptedClock((0, 0, 0, 2)),
    ).propose_feasible_trajectories(start, end)
    assert partial.termination_reason == TerminationReason.SEARCH_TIMEOUT
    assert len(partial.candidates) == 1
    assert not partial.complete

    with pytest.raises(GraphInputError) as captured:
        _engine(
            network,
            policy=GraphSearchPolicy(max_search_time_s=1),
            clock=_ScriptedClock((1, 0)),
        ).propose_feasible_trajectories(start, end)
    assert captured.value.failure == GraphInputFailure.NUMERICAL_FAILURE


def test_entry_revalidation_and_numerical_overflow_fail_closed() -> None:
    network = _branch_network()
    start, end = _endpoints()
    mismatched_point = start.projected_path[0].model_copy(update={"camera_id": "CAM_D"})
    invalid = start.model_copy(update={"projected_path": (mismatched_point,)})
    with pytest.raises(GraphInputError) as captured:
        _engine(network).propose_feasible_trajectories(invalid, end)
    assert captured.value.failure == GraphInputFailure.INVALID_OBSERVATION

    huge_start, huge_end = _endpoints(start_time=0, end_time=1e308)
    with pytest.raises(GraphInputError) as captured:
        _engine(network, speed=1e308).propose_feasible_trajectories(huge_start, huge_end)
    assert captured.value.failure == GraphInputFailure.NUMERICAL_FAILURE


def test_path_length_and_detour_are_candidate_space_bounds() -> None:
    start, end = _endpoints()
    network = _branch_network()
    direct_only = _engine(
        network,
        policy=GraphSearchPolicy(max_path_length_m=2, max_detour_ratio=1),
    ).propose_feasible_trajectories(start, end)
    assert tuple(item.navmesh_corridor for item in direct_only.candidates) == (("m_direct",),)
    assert direct_only.termination_reason == TerminationReason.COMPLETE

    none = _engine(
        network,
        policy=GraphSearchPolicy(max_path_length_m=1.99),
    ).propose_feasible_trajectories(start, end)
    assert none.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    assert "MAX_PATH_LENGTH_EXCEEDED" in none.rejection_reasons


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (MovementConstraints, {"max_speed_m_s": 0}),
        (MovementConstraints, {"max_speed_m_s": math.inf}),
        (GraphSearchPolicy, {"max_candidate_paths": 0}),
        (GraphSearchPolicy, {"max_search_nodes": 0}),
        (GraphSearchPolicy, {"max_path_length_m": 0}),
        (GraphSearchPolicy, {"max_search_time_s": math.nan}),
        (GraphSearchPolicy, {"max_branch_factor": 0}),
        (GraphSearchPolicy, {"max_detour_ratio": 0.99}),
    ],
)
def test_search_contracts_reject_invalid_values(model: Any, payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_public_max_paths_and_ground_truth_boundary() -> None:
    start, end = _endpoints()
    engine = _engine(_branch_network())
    with pytest.raises(GraphInputError) as captured:
        engine.propose_feasible_trajectories(start, end, max_paths=0)
    assert captured.value.failure == GraphInputFailure.INVALID_MAX_PATHS

    result = engine.propose_feasible_trajectories(start, end, max_paths=3)
    serialized = result.model_dump_json()
    assert "ground_truth" not in serialized.lower()
    assert "GROUND_TRUTH" not in serialized
    source = Path(engine_module.__file__).read_text(encoding="utf-8")
    assert "amidst.domain.ground_truth" not in source
    assert "amidst.simulation" not in source
