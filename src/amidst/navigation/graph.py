"""Deterministic minimum-distance routing over explicit directed polylines."""

from __future__ import annotations

import heapq
import math
from collections.abc import Mapping
from enum import StrEnum
from itertools import pairwise
from types import MappingProxyType

from pydantic import ValidationError

from amidst.domain.common import Vec3
from amidst.domain.navigation import (
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
    NavigationPath,
)


class NavigationFailure(StrEnum):
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    INVALID_POSITION = "INVALID_POSITION"
    AMBIGUOUS_POSITION = "AMBIGUOUS_POSITION"
    UNKNOWN_NODE = "UNKNOWN_NODE"


class NavigationError(ValueError):
    def __init__(self, failure: NavigationFailure, message: str) -> None:
        super().__init__(message)
        self.failure = failure


def _polyline_length(polyline: tuple[Vec3, ...]) -> float:
    try:
        length = math.fsum(math.dist(start, end) for start, end in pairwise(polyline))
    except OverflowError as error:
        raise NavigationError(
            NavigationFailure.INVALID_CONFIGURATION,
            "navigation polyline length overflowed",
        ) from error
    if not math.isfinite(length) or length <= 0:
        raise NavigationError(
            NavigationFailure.INVALID_CONFIGURATION,
            "navigation edge must have a finite positive 3D length",
        )
    return length


class NavigationGraph:
    """Validated multiedge graph with input-order-independent Dijkstra routing."""

    def __init__(self, config: NavigationGraphConfig) -> None:
        try:
            validated = NavigationGraphConfig.model_validate(config.model_dump(mode="python"))
        except ValidationError as error:
            raise NavigationError(
                NavigationFailure.INVALID_CONFIGURATION,
                "navigation graph does not satisfy its domain contract",
            ) from error

        nodes = {node.node_id: node for node in validated.nodes}
        edges = {edge.edge_id: edge for edge in validated.edges}
        lengths: dict[str, float] = {}
        outgoing: dict[str, list[NavigationEdge]] = {node_id: [] for node_id in nodes}
        for edge in validated.edges:
            start, end = nodes[edge.from_node_id], nodes[edge.to_node_id]
            if edge.polyline[0] != start.position or edge.polyline[-1] != end.position:
                raise NavigationError(
                    NavigationFailure.INVALID_CONFIGURATION,
                    "navigation edge polyline endpoints must match referenced nodes",
                )
            lengths[edge.edge_id] = _polyline_length(edge.polyline)
            outgoing[edge.from_node_id].append(edge)

        self.config = validated
        self._nodes: Mapping[str, NavigationNode] = MappingProxyType(nodes)
        self._edges: Mapping[str, NavigationEdge] = MappingProxyType(edges)
        self._lengths: Mapping[str, float] = MappingProxyType(lengths)
        self._outgoing: Mapping[str, tuple[NavigationEdge, ...]] = MappingProxyType(
            {
                node_id: tuple(sorted(node_edges, key=lambda edge: edge.edge_id))
                for node_id, node_edges in outgoing.items()
            }
        )

    def node(self, node_id: str) -> NavigationNode:
        try:
            return self._nodes[node_id]
        except KeyError as error:
            raise NavigationError(
                NavigationFailure.UNKNOWN_NODE, f"unknown navigation node: {node_id}"
            ) from error

    def outgoing_edges(self, node_id: str) -> tuple[NavigationEdge, ...]:
        self.node(node_id)
        return self._outgoing[node_id]

    def edge(self, edge_id: str) -> NavigationEdge:
        try:
            return self._edges[edge_id]
        except KeyError as error:
            raise NavigationError(
                NavigationFailure.INVALID_CONFIGURATION,
                f"unknown navigation edge: {edge_id}",
            ) from error

    def edge_length(self, edge_id: str) -> float:
        self.edge(edge_id)
        return self._lengths[edge_id]

    def locate_node(self, position: Vec3, floor_id: str) -> str | None:
        if len(position) != 3 or not all(math.isfinite(float(value)) for value in position):
            raise NavigationError(
                NavigationFailure.INVALID_POSITION,
                "navigation lookup requires three finite coordinates",
            )
        matches = tuple(
            sorted(
                node.node_id
                for node in self._nodes.values()
                if node.floor_id == floor_id
                and math.dist(node.position, position)
                <= float(self.config.node_match_tolerance_m)
            )
        )
        if len(matches) > 1:
            raise NavigationError(
                NavigationFailure.AMBIGUOUS_POSITION,
                "position matches more than one configured navigation node",
            )
        return matches[0] if matches else None

    def path_from_edge_ids(
        self, start_node_id: str, edge_ids: tuple[str, ...]
    ) -> NavigationPath:
        start = self.node(start_node_id)
        current = start_node_id
        node_ids = [start_node_id]
        edges: list[NavigationEdge] = []
        for edge_id in edge_ids:
            edge = self.edge(edge_id)
            if edge.from_node_id != current:
                raise NavigationError(
                    NavigationFailure.INVALID_CONFIGURATION,
                    "navigation edge sequence is not contiguous",
                )
            edges.append(edge)
            current = edge.to_node_id
            node_ids.append(current)
        if not edges:
            return NavigationPath(
                node_ids=(start_node_id,),
                edge_ids=(),
                polyline=(start.position,),
                transition_types=(),
                distance_m=0,
            )
        polyline = list(edges[0].polyline)
        for edge in edges[1:]:
            polyline.extend(edge.polyline[1:])
        try:
            distance = math.fsum(self._lengths[edge.edge_id] for edge in edges)
        except OverflowError as error:
            raise NavigationError(
                NavigationFailure.INVALID_CONFIGURATION,
                "navigation path distance overflowed",
            ) from error
        if not math.isfinite(distance):
            raise NavigationError(
                NavigationFailure.INVALID_CONFIGURATION,
                "navigation path distance must remain finite",
            )
        return NavigationPath(
            node_ids=tuple(node_ids),
            edge_ids=edge_ids,
            polyline=tuple(polyline),
            transition_types=tuple(edge.transition_type for edge in edges),
            distance_m=distance,
        )

    def minimum_path(self, start_node_id: str, end_node_id: str) -> NavigationPath | None:
        self.node(start_node_id)
        self.node(end_node_id)
        if start_node_id == end_node_id:
            return self.path_from_edge_ids(start_node_id, ())

        queue: list[tuple[float, tuple[str, ...], tuple[str, ...], str]] = [
            (0.0, (), (start_node_id,), start_node_id)
        ]
        best: dict[str, tuple[float, tuple[str, ...]]] = {start_node_id: (0.0, ())}
        while queue:
            distance, edge_ids, node_ids, current = heapq.heappop(queue)
            if best.get(current) != (distance, edge_ids):
                continue
            if current == end_node_id:
                return self.path_from_edge_ids(start_node_id, edge_ids)
            for edge in self._outgoing[current]:
                new_edge_ids = (*edge_ids, edge.edge_id)
                new_distance = distance + self._lengths[edge.edge_id]
                if not math.isfinite(new_distance):
                    raise NavigationError(
                        NavigationFailure.INVALID_CONFIGURATION,
                        "navigation route accumulation overflowed",
                    )
                key = (new_distance, new_edge_ids)
                if edge.to_node_id not in best or key < best[edge.to_node_id]:
                    best[edge.to_node_id] = key
                    heapq.heappush(
                        queue,
                        (new_distance, new_edge_ids, (*node_ids, edge.to_node_id), edge.to_node_id),
                    )
        return None

    def minimum_path_distance(self, start_node_id: str, end_node_id: str) -> float | None:
        path = self.minimum_path(start_node_id, end_node_id)
        return None if path is None else float(path.distance_m)
