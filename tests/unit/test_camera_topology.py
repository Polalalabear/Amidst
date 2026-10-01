"""M7 camera-topology separation and navigation cross-validation tests."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from amidst.domain.navigation import (
    CrossFloorPolicy,
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
    NavigationTransitionType,
)
from amidst.domain.topology import (
    CameraTopologyConfig,
    CameraTopologyNode,
    CameraTransition,
    CameraTransitionType,
)
from amidst.navigation.graph import NavigationError, NavigationFailure, NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph, TopologyError, TopologyFailure


def _camera(camera_id: str, floor_id: str = "1F", zone_id: str | None = None) -> CameraTopologyNode:
    return CameraTopologyNode(camera_id=camera_id, floor_id=floor_id, zone_id=zone_id)


def _transition(
    transition_id: str,
    from_camera_id: str,
    to_camera_id: str,
    nav_from: str,
    nav_to: str,
    transition_type: CameraTransitionType = CameraTransitionType.ADJACENT,
    navigation_edge_ids: tuple[str, ...] | None = None,
) -> CameraTransition:
    return CameraTransition(
        transition_id=transition_id,
        from_camera_id=from_camera_id,
        to_camera_id=to_camera_id,
        transition_type=transition_type,
        navigation_from_node_id=nav_from,
        navigation_to_node_id=nav_to,
        navigation_edge_ids=navigation_edge_ids or (transition_id,),
    )


def _topology(
    nodes: tuple[CameraTopologyNode, ...],
    transitions: tuple[CameraTransition, ...] = (),
    **updates: Any,
) -> CameraTopologyConfig:
    payload = dict(
        topology_id="synthetic_topology",
        navigation_graph_id="same_floor",
        spatial_context_id="synthetic_context",
        data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
        nodes=nodes,
        transitions=transitions,
    )
    payload.update(updates)
    return CameraTopologyConfig.model_validate(payload)


def _same_floor_navigation() -> NavigationGraph:
    nodes = (
        NavigationNode(node_id="nav_a", position=(0, 0, 0), floor_id="1F"),
        NavigationNode(node_id="nav_b", position=(2, 0, 0), floor_id="1F"),
        NavigationNode(node_id="nav_c", position=(4, 0, 0), floor_id="1F"),
    )
    edges = (
        NavigationEdge(
            edge_id="A_B",
            from_node_id="nav_a",
            to_node_id="nav_b",
            polyline=((0, 0, 0), (2, 0, 0)),
        ),
        NavigationEdge(
            edge_id="B_C",
            from_node_id="nav_b",
            to_node_id="nav_c",
            polyline=((2, 0, 0), (4, 0, 0)),
        ),
    )
    return NavigationGraph(
        NavigationGraphConfig(
            graph_id="same_floor",
            spatial_context_id="synthetic_context",
            data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
            nodes=nodes,
            edges=edges,
        )
    )


def test_directed_topology_exposes_stable_outgoing_transitions_only() -> None:
    nodes = (_camera("CAM_A"), _camera("CAM_B"), _camera("CAM_C"))
    transitions = (
        _transition("z_ab", "CAM_A", "CAM_B", "nav_a", "nav_b"),
        _transition("a_ab", "CAM_A", "CAM_B", "nav_a", "nav_b"),
        _transition("b_bc", "CAM_B", "CAM_C", "nav_b", "nav_c"),
    )
    graph = CameraTopologyGraph(_topology(nodes, tuple(reversed(transitions))))
    assert tuple(item.transition_id for item in graph.outgoing_transitions("CAM_A")) == (
        "a_ab",
        "z_ab",
    )
    assert tuple(item.transition_id for item in graph.outgoing_transitions("CAM_B")) == ("b_bc",)
    assert graph.outgoing_transitions("CAM_C") == ()
    with pytest.raises(TopologyError) as captured:
        graph.outgoing_transitions("missing")
    assert captured.value.failure == TopologyFailure.UNKNOWN_CAMERA


def test_return_trip_is_not_a_fixed_camera_transition_type() -> None:
    assert "RETURN_TRIP" not in {item.value for item in CameraTransitionType}
    with pytest.raises(ValidationError):
        CameraTransition.model_validate(
            {
                "transition_id": "return",
                "from_camera_id": "CAM_A",
                "to_camera_id": "CAM_B",
                "transition_type": "RETURN_TRIP",
                "navigation_from_node_id": "A",
                "navigation_to_node_id": "B",
                "navigation_edge_ids": ("A_B",),
            }
        )


@pytest.mark.parametrize(
    "builder",
    [
        lambda: _topology((_camera("CAM_A"), _camera("CAM_A"))),
        lambda: _topology(
            (_camera("CAM_A"),),
            (_transition("bad", "CAM_A", "missing", "A", "B"),),
        ),
        lambda: _transition("self", "CAM_A", "CAM_A", "A", "A"),
        lambda: _topology(
            (_camera("CAM_A", zone_id="z1"), _camera("CAM_B", zone_id="z2")),
            (
                _transition(
                    "zone",
                    "CAM_A",
                    "CAM_B",
                    "A",
                    "B",
                    CameraTransitionType.SAME_ZONE,
                ),
            ),
        ),
        lambda: _topology(
            (_camera("CAM_A", "1F"), _camera("CAM_B", "2F")),
            (_transition("cross", "CAM_A", "CAM_B", "A", "B"),),
        ),
    ],
)
def test_invalid_topology_contracts_are_rejected(builder: Any) -> None:
    with pytest.raises(ValidationError):
        builder()


def test_same_floor_network_cross_validates_walkable_anchors() -> None:
    navigation = _same_floor_navigation()
    topology = CameraTopologyGraph(
        _topology(
            (_camera("CAM_A"), _camera("CAM_B"), _camera("CAM_C")),
            (
                _transition("A_B", "CAM_A", "CAM_B", "nav_a", "nav_b"),
                _transition("B_C", "CAM_B", "CAM_C", "nav_b", "nav_c"),
            ),
        )
    )
    network = NavigationNetwork(navigation, topology)
    assert network.navigation.minimum_path_distance("nav_a", "nav_c") == 4
    assert network.topology.outgoing_transitions("CAM_C") == ()


def _stair_navigation(include_down: bool = False) -> NavigationGraph:
    lower = NavigationNode(node_id="lower", position=(0, 0, 0), floor_id="1F")
    upper = NavigationNode(node_id="upper", position=(0, 0, 3), floor_id="2F")
    up = NavigationEdge(
        edge_id="stair_up",
        from_node_id="lower",
        to_node_id="upper",
        polyline=((0, 0, 0), (1, 0, 1.5), (0, 0, 3)),
        transition_type=NavigationTransitionType.STAIR_UP,
        stair_id="SYNTHETIC_TEST_FIXTURE_STAIR",
    )
    edges = [up]
    if include_down:
        edges.append(
            NavigationEdge(
                edge_id="stair_down",
                from_node_id="upper",
                to_node_id="lower",
                polyline=tuple(reversed(up.polyline)),
                transition_type=NavigationTransitionType.STAIR_DOWN,
                stair_id="SYNTHETIC_TEST_FIXTURE_STAIR",
            )
        )
    return NavigationGraph(
        NavigationGraphConfig(
            graph_id="synthetic_stair",
            spatial_context_id="synthetic_context",
            data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
            cross_floor_policy=CrossFloorPolicy.EXPLICIT_PARAMETERIZED_STAIRS,
            nodes=(lower, upper),
            edges=tuple(edges),
        )
    )


def test_explicit_synthetic_stair_camera_transition_is_cross_validated() -> None:
    topology = CameraTopologyGraph(
        _topology(
            (_camera("CAM_1F", "1F"), _camera("CAM_2F", "2F")),
            (
                _transition(
                    "camera_stair_up",
                    "CAM_1F",
                    "CAM_2F",
                    "lower",
                    "upper",
                    CameraTransitionType.STAIR_UP,
                    ("stair_up",),
                ),
            ),
            navigation_graph_id="synthetic_stair",
        )
    )
    network = NavigationNetwork(_stair_navigation(), topology)
    assert tuple(
        item.transition_id for item in network.topology.outgoing_transitions("CAM_1F")
    ) == ("camera_stair_up",)
    assert network.topology.outgoing_transitions("CAM_2F") == ()


def test_cross_floor_camera_transition_requires_a_matching_stair_route() -> None:
    bad_transition = _transition(
        "camera_stair_down",
        "CAM_2F",
        "CAM_1F",
        "upper",
        "lower",
        CameraTransitionType.STAIR_DOWN,
        ("stair_down",),
    )
    topology = CameraTopologyGraph(
        _topology(
            (_camera("CAM_1F", "1F"), _camera("CAM_2F", "2F")),
            (bad_transition,),
            navigation_graph_id="synthetic_stair",
        )
    )
    with pytest.raises(NavigationError) as captured:
        NavigationNetwork(_stair_navigation(include_down=False), topology)
    assert captured.value.failure == NavigationFailure.INVALID_CONFIGURATION


def test_network_rejects_mixed_authority_and_anchor_floor_mismatch() -> None:
    topology = CameraTopologyGraph(
        _topology(
            (_camera("CAM_A", "2F"), _camera("CAM_B", "1F")),
            (
                _transition(
                    "stair_down",
                    "CAM_A",
                    "CAM_B",
                    "upper",
                    "lower",
                    CameraTransitionType.STAIR_DOWN,
                    ("stair_down",),
                ),
            ),
            navigation_graph_id="synthetic_stair",
        )
    )
    configured_navigation = NavigationGraph(
        _stair_navigation(include_down=True).config.model_copy(
            update={
                "data_kind": NavigationDataKind.CONFIGURED,
                "source_asset_sha256": "a" * 64,
            }
        )
    )
    with pytest.raises(NavigationError) as captured:
        NavigationNetwork(configured_navigation, topology)
    assert captured.value.failure == NavigationFailure.INVALID_CONFIGURATION

    wrong_floor_topology = CameraTopologyGraph(
        _topology(
            (_camera("CAM_A", "1F"), _camera("CAM_B", "1F")),
            (_transition("adjacent", "CAM_A", "CAM_B", "upper", "lower"),),
            navigation_graph_id="synthetic_stair",
        )
    )
    with pytest.raises(NavigationError) as captured:
        NavigationNetwork(_stair_navigation(include_down=True), wrong_floor_topology)
    assert captured.value.failure == NavigationFailure.INVALID_CONFIGURATION


def test_network_rejects_same_kind_but_different_navigation_graph() -> None:
    topology = CameraTopologyGraph(
        _topology(
            (_camera("CAM_A"), _camera("CAM_B")),
            (_transition("A_B", "CAM_A", "CAM_B", "nav_a", "nav_b"),),
            navigation_graph_id="different_graph",
        )
    )
    with pytest.raises(NavigationError) as captured:
        NavigationNetwork(_same_floor_navigation(), topology)
    assert captured.value.failure == NavigationFailure.INVALID_CONFIGURATION


def test_network_rejects_context_and_source_binding_mismatches() -> None:
    context_mismatch = CameraTopologyGraph(
        _topology(
            (_camera("CAM_A"), _camera("CAM_B")),
            (_transition("A_B", "CAM_A", "CAM_B", "nav_a", "nav_b"),),
            spatial_context_id="other_context",
        )
    )
    with pytest.raises(NavigationError) as captured:
        NavigationNetwork(_same_floor_navigation(), context_mismatch)
    assert captured.value.failure == NavigationFailure.INVALID_CONFIGURATION

    navigation = NavigationGraph(
        _same_floor_navigation().config.model_copy(
            update={
                "data_kind": NavigationDataKind.CONFIGURED,
                "source_asset_sha256": "a" * 64,
            }
        )
    )
    topology = CameraTopologyGraph(
        _topology(
            (_camera("CAM_A"), _camera("CAM_B")),
            (_transition("A_B", "CAM_A", "CAM_B", "nav_a", "nav_b"),),
            data_kind=NavigationDataKind.CONFIGURED,
            source_asset_sha256="b" * 64,
        )
    )
    with pytest.raises(NavigationError) as captured:
        NavigationNetwork(navigation, topology)
    assert captured.value.failure == NavigationFailure.INVALID_CONFIGURATION


def test_transition_uses_its_explicit_walkable_edge_sequence() -> None:
    nodes = (
        NavigationNode(node_id="nav_a", position=(0, 0, 0), floor_id="1F"),
        NavigationNode(node_id="nav_b", position=(2, 0, 0), floor_id="1F"),
    )
    direct = NavigationEdge(
        edge_id="direct",
        from_node_id="nav_a",
        to_node_id="nav_b",
        polyline=((0, 0, 0), (2, 0, 0)),
    )
    designated = NavigationEdge(
        edge_id="designated",
        from_node_id="nav_a",
        to_node_id="nav_b",
        polyline=((0, 0, 0), (1, 1, 0), (2, 0, 0)),
    )
    navigation = NavigationGraph(
        NavigationGraphConfig(
            graph_id="explicit_path",
            spatial_context_id="synthetic_context",
            data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
            nodes=nodes,
            edges=(direct, designated),
        )
    )
    topology = CameraTopologyGraph(
        _topology(
            (_camera("CAM_A"), _camera("CAM_B")),
            (
                _transition(
                    "camera_path",
                    "CAM_A",
                    "CAM_B",
                    "nav_a",
                    "nav_b",
                    navigation_edge_ids=("designated",),
                ),
            ),
            navigation_graph_id="explicit_path",
        )
    )
    network = NavigationNetwork(navigation, topology)
    assert network.navigation.minimum_path("nav_a", "nav_b") is not None
    designated_path = network.navigation.path_from_edge_ids("nav_a", ("designated",))
    assert designated_path.distance_m > 2
