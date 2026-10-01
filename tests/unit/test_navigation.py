"""M7 explicit walkable-graph validation and deterministic routing tests."""

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
    NavigationPath,
    NavigationTransitionType,
)
from amidst.navigation.graph import NavigationError, NavigationFailure, NavigationGraph


def _node(
    node_id: str, position: tuple[float, float, float], floor_id: str = "1F", **updates: Any
) -> NavigationNode:
    payload = dict(node_id=node_id, position=position, floor_id=floor_id)
    payload.update(updates)
    return NavigationNode.model_validate(payload)


def _edge(
    edge_id: str,
    from_node_id: str,
    to_node_id: str,
    polyline: tuple[tuple[float, float, float], ...],
    **updates: Any,
) -> NavigationEdge:
    payload = dict(
        edge_id=edge_id,
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        polyline=polyline,
    )
    payload.update(updates)
    return NavigationEdge.model_validate(payload)


def _config(
    nodes: tuple[NavigationNode, ...],
    edges: tuple[NavigationEdge, ...] = (),
    **updates: Any,
) -> NavigationGraphConfig:
    payload = dict(
        graph_id="synthetic_navigation",
        spatial_context_id="synthetic_context",
        data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
        nodes=nodes,
        edges=edges,
    )
    payload.update(updates)
    return NavigationGraphConfig.model_validate(payload)


def test_bent_polyline_uses_full_3d_walkable_distance() -> None:
    nodes = (_node("A", (0, 0, 0)), _node("B", (3, 4, 0)))
    edge = _edge("A_B", "A", "B", ((0, 0, 0), (0, 4, 0), (3, 4, 0)))
    graph = NavigationGraph(_config(nodes, (edge,)))
    path = graph.minimum_path("A", "B")
    assert path is not None
    assert path.node_ids == ("A", "B")
    assert path.edge_ids == ("A_B",)
    assert path.polyline == edge.polyline
    assert path.distance_m == 7
    assert graph.minimum_path_distance("A", "B") == 7


def test_edges_are_directed_and_reverse_must_be_explicit() -> None:
    nodes = (_node("A", (0, 0, 0)), _node("B", (2, 0, 0)))
    forward = _edge("A_B", "A", "B", ((0, 0, 0), (2, 0, 0)))
    assert NavigationGraph(_config(nodes, (forward,))).minimum_path("B", "A") is None
    reverse = _edge("B_A", "B", "A", tuple(reversed(forward.polyline)))
    path = NavigationGraph(_config(nodes, (forward, reverse))).minimum_path("B", "A")
    assert path is not None and path.edge_ids == ("B_A",)


def test_same_node_disconnected_and_unknown_queries_are_distinct() -> None:
    graph = NavigationGraph(_config((_node("A", (0, 0, 0)), _node("B", (1, 0, 0)))))
    same = graph.minimum_path("A", "A")
    assert same is not None
    assert same.node_ids == ("A",)
    assert same.edge_ids == ()
    assert same.polyline == ((0, 0, 0),)
    assert same.distance_m == 0
    assert graph.minimum_path("A", "B") is None
    with pytest.raises(NavigationError) as captured:
        graph.minimum_path("A", "missing")
    assert captured.value.failure == NavigationFailure.UNKNOWN_NODE


def test_equal_distance_branching_is_stable_across_input_order() -> None:
    nodes = (
        _node("A", (0, 0, 0)),
        _node("B", (2, 0, 0)),
        _node("C", (1, 1, 0)),
        _node("D", (1, -1, 0)),
    )
    edges = (
        _edge("z_ac", "A", "C", ((0, 0, 0), (1, 1, 0))),
        _edge("z_cb", "C", "B", ((1, 1, 0), (2, 0, 0))),
        _edge("a_ad", "A", "D", ((0, 0, 0), (1, -1, 0))),
        _edge("a_db", "D", "B", ((1, -1, 0), (2, 0, 0))),
    )
    expected = ("a_ad", "a_db")
    for node_order in (nodes, tuple(reversed(nodes))):
        for edge_order in (edges, tuple(reversed(edges))):
            path = NavigationGraph(_config(node_order, edge_order)).minimum_path("A", "B")
            assert path is not None and path.edge_ids == expected


def test_parallel_edges_are_preserved_and_tied_by_edge_identity() -> None:
    nodes = (_node("A", (0, 0, 0)), _node("B", (1, 0, 0)))
    edges = (
        _edge("z_corridor", "A", "B", ((0, 0, 0), (1, 0, 0))),
        _edge("a_corridor", "A", "B", ((0, 0, 0), (1, 0, 0))),
    )
    graph = NavigationGraph(_config(nodes, edges))
    assert tuple(edge.edge_id for edge in graph.outgoing_edges("A")) == (
        "a_corridor",
        "z_corridor",
    )
    path = graph.minimum_path("A", "B")
    assert path is not None and path.edge_ids == ("a_corridor",)


def test_join_points_are_not_duplicated_in_path_polyline() -> None:
    nodes = (
        _node("A", (0, 0, 0)),
        _node("B", (2, 0, 0)),
        _node("C", (4, 0, 0)),
    )
    edges = (
        _edge("A_B", "A", "B", ((0, 0, 0), (1, 1, 0), (2, 0, 0))),
        _edge("B_C", "B", "C", ((2, 0, 0), (3, 1, 0), (4, 0, 0))),
    )
    path = NavigationGraph(_config(nodes, edges)).minimum_path("A", "C")
    assert path is not None
    assert path.polyline == ((0, 0, 0), (1, 1, 0), (2, 0, 0), (3, 1, 0), (4, 0, 0))
    assert path.polyline.count((2, 0, 0)) == 1


def test_schema_roundtrip_and_ground_truth_fields_are_rejected() -> None:
    config = _config((_node("A", (0, 0, 0)),))
    assert NavigationGraphConfig.model_validate_json(config.model_dump_json()) == config
    with pytest.raises(ValidationError):
        NavigationNode.model_validate(
            {"node_id": "A", "position": (0, 0, 0), "floor_id": "1F", "ground_truth": True}
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"distance_m": 2},
        {"polyline": ((0, 0, 0), (0, 0, 0)), "distance_m": 0},
        {"polyline": ((0, 0, 0),), "distance_m": 1},
        {"polyline": ((0, 0, 0), (9e307, 0, 0), (0, 1, 0)), "distance_m": 1},
    ],
)
def test_navigation_path_rejects_forged_or_degenerate_distance(updates: dict[str, Any]) -> None:
    payload = dict(
        node_ids=("A", "B"),
        edge_ids=("A_B",),
        polyline=((0, 0, 0), (1, 0, 0)),
        transition_types=(NavigationTransitionType.WALK,),
        distance_m=1,
    )
    with pytest.raises(ValidationError):
        NavigationPath.model_validate(payload | updates)


@pytest.mark.parametrize(
    "builder",
    [
        lambda: _config((_node("A", (0, 0, 0)), _node("A", (1, 0, 0)))),
        lambda: _config(
            (_node("A", (0, 0, 0)),),
            (_edge("missing", "A", "B", ((0, 0, 0), (1, 0, 0))),),
        ),
        lambda: _edge("self", "A", "A", ((0, 0, 0), (1, 0, 0))),
        lambda: _edge("repeat", "A", "B", ((0, 0, 0), (1, 0, 0), (0, 0, 0))),
    ],
)
def test_structurally_invalid_graph_contracts_are_rejected(builder: Any) -> None:
    with pytest.raises(ValidationError):
        builder()


def test_polyline_endpoints_must_match_nodes() -> None:
    nodes = (_node("A", (0, 0, 0)), _node("B", (1, 0, 0)))
    edge = _edge("bad", "A", "B", ((0, 0, 0), (2, 0, 0)))
    with pytest.raises(NavigationError) as captured:
        NavigationGraph(_config(nodes, (edge,)))
    assert captured.value.failure == NavigationFailure.INVALID_CONFIGURATION


def test_overflowing_walkable_length_fails_closed() -> None:
    nodes = (_node("A", (-1e308, 0, 0)), _node("B", (1e308, 0, 0)))
    edge = _edge("overflow", "A", "B", (nodes[0].position, nodes[1].position))
    with pytest.raises(NavigationError) as captured:
        NavigationGraph(_config(nodes, (edge,)))
    assert captured.value.failure == NavigationFailure.INVALID_CONFIGURATION


def test_composite_route_distance_overflow_fails_closed() -> None:
    nodes = (
        _node("A", (0, 0, 0)),
        _node("B", (9e307, 0, 0)),
        _node("C", (0, 1, 0)),
    )
    edges = (
        _edge("A_B", "A", "B", (nodes[0].position, nodes[1].position)),
        _edge("B_C", "B", "C", (nodes[1].position, nodes[2].position)),
    )
    graph = NavigationGraph(_config(nodes, edges))
    with pytest.raises(NavigationError) as captured:
        graph.minimum_path("A", "C")
    assert captured.value.failure == NavigationFailure.INVALID_CONFIGURATION


def test_configured_navigation_requires_a_valid_source_digest() -> None:
    node = _node("A", (0, 0, 0))
    with pytest.raises(ValidationError):
        _config((node,), data_kind=NavigationDataKind.CONFIGURED)
    with pytest.raises(ValidationError):
        _config(
            (node,),
            data_kind=NavigationDataKind.CONFIGURED,
            source_asset_sha256="not-a-digest",
        )


@pytest.mark.parametrize(
    "config_builder",
    [
        lambda: _config(
            (_node("A", (0, 0, 0), "1F"), _node("B", (1, 0, 0), "2F")),
            (_edge("walk", "A", "B", ((0, 0, 0), (1, 0, 0))),),
        ),
        lambda: _config(
            (_node("A", (0, 0, 0), "1F"), _node("B", (0, 0, 1), "1F")),
            (
                _edge(
                    "stair",
                    "A",
                    "B",
                    ((0, 0, 0), (0, 0, 1)),
                    transition_type=NavigationTransitionType.STAIR_UP,
                    stair_id="fixture_stair",
                ),
            ),
            cross_floor_policy=CrossFloorPolicy.EXPLICIT_PARAMETERIZED_STAIRS,
        ),
        lambda: _config(
            (_node("A", (0, 0, 0), "1F"), _node("B", (0, 0, 1), "2F")),
            (
                _edge(
                    "stair",
                    "A",
                    "B",
                    ((0, 0, 0), (0, 0, 1)),
                    transition_type=NavigationTransitionType.STAIR_UP,
                    stair_id="fixture_stair",
                ),
            ),
        ),
    ],
)
def test_floor_and_cross_floor_policy_violations_are_rejected(config_builder: Any) -> None:
    with pytest.raises(ValidationError):
        config_builder()


@pytest.mark.parametrize(
    ("transition_type", "polyline"),
    [
        (NavigationTransitionType.STAIR_UP, ((0, 0, 0), (0, 0, -1))),
        (NavigationTransitionType.STAIR_UP, ((0, 0, 0), (0, 0, 1), (0, 0, 0.5))),
        (NavigationTransitionType.STAIR_DOWN, ((0, 0, 1), (0, 0, 2))),
        (NavigationTransitionType.STAIR_DOWN, ((0, 0, 1), (0, 0, 0), (0, 0, 0.5))),
    ],
)
def test_wrong_direction_and_nonmonotonic_stairs_are_rejected(
    transition_type: NavigationTransitionType,
    polyline: tuple[tuple[float, float, float], ...],
) -> None:
    with pytest.raises(ValidationError):
        _edge(
            "stair",
            "A",
            "B",
            polyline,
            transition_type=transition_type,
            stair_id="fixture_stair",
        )


def test_explicit_synthetic_stairs_preserve_3d_path_and_direction() -> None:
    nodes = (_node("lower", (0, 0, 0), "1F"), _node("upper", (3, 0, 4), "2F"))
    up = _edge(
        "stair_up",
        "lower",
        "upper",
        ((0, 0, 0), (1.5, 0, 2), (3, 0, 4)),
        transition_type=NavigationTransitionType.STAIR_UP,
        stair_id="SYNTHETIC_TEST_FIXTURE_STAIR",
    )
    config = _config(
        nodes,
        (up,),
        cross_floor_policy=CrossFloorPolicy.EXPLICIT_PARAMETERIZED_STAIRS,
    )
    graph = NavigationGraph(config)
    path = graph.minimum_path("lower", "upper")
    assert path is not None
    assert path.distance_m == pytest.approx(5)
    assert path.transition_types == (NavigationTransitionType.STAIR_UP,)
    assert graph.minimum_path("upper", "lower") is None

    down = _edge(
        "stair_down",
        "upper",
        "lower",
        tuple(reversed(up.polyline)),
        transition_type=NavigationTransitionType.STAIR_DOWN,
        stair_id="SYNTHETIC_TEST_FIXTURE_STAIR",
    )
    reverse = NavigationGraph(config.model_copy(update={"edges": (up, down)}))
    down_path = reverse.minimum_path("upper", "lower")
    assert down_path is not None
    assert down_path.transition_types == (NavigationTransitionType.STAIR_DOWN,)


def test_school_like_floors_remain_disconnected_without_an_explicit_stair() -> None:
    graph = NavigationGraph(
        _config((_node("school_1f", (0, 0, 20), "1F"), _node("school_2f", (0, 0, 162), "2F")))
    )
    assert graph.config.cross_floor_policy == CrossFloorPolicy.DISCONNECTED
    assert graph.minimum_path("school_1f", "school_2f") is None


def test_locate_node_requires_floor_exactness_and_rejects_ambiguity() -> None:
    graph = NavigationGraph(
        _config((_node("A", (1, 2, 0), "1F"), _node("B", (1, 2, 0), "2F")))
    )
    assert graph.locate_node((1, 2, 0), "1F") == "A"
    assert graph.locate_node((1 + 5e-7, 2, 0), "1F") == "A"
    assert graph.locate_node((1 + 2e-6, 2, 0), "1F") is None
    assert graph.locate_node((1, 2, 0), "missing") is None

    ambiguous = NavigationGraph(
        _config((_node("A", (1, 2, 0), "1F"), _node("C", (1, 2, 0), "1F")))
    )
    with pytest.raises(NavigationError) as captured:
        ambiguous.locate_node((1, 2, 0), "1F")
    assert captured.value.failure == NavigationFailure.AMBIGUOUS_POSITION
