"""Navigation configuration schemas; routing algorithms live outside domain."""

from __future__ import annotations

import math
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel, PositiveFinite, Vec3

NonNegativeFinite = Annotated[FiniteFloat, Field(ge=0)]


class NavigationDataKind(StrEnum):
    CONFIGURED = "CONFIGURED"
    SYNTHETIC_TEST_FIXTURE = "SYNTHETIC_TEST_FIXTURE"


class CrossFloorPolicy(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    EXPLICIT_PARAMETERIZED_STAIRS = "EXPLICIT_PARAMETERIZED_STAIRS"


class NavigationTransitionType(StrEnum):
    WALK = "WALK"
    STAIR_UP = "STAIR_UP"
    STAIR_DOWN = "STAIR_DOWN"


class NavigationNode(DomainModel):
    node_id: str = Field(min_length=1)
    position: Vec3
    floor_id: str = Field(min_length=1)
    zone_id: str | None = None


class NavigationEdge(DomainModel):
    edge_id: str = Field(min_length=1)
    from_node_id: str = Field(min_length=1)
    to_node_id: str = Field(min_length=1)
    polyline: tuple[Vec3, ...] = Field(min_length=2)
    transition_type: NavigationTransitionType = NavigationTransitionType.WALK
    stair_id: str | None = None
    walkable: Literal[True] = True

    @model_validator(mode="after")
    def consistent_edge(self) -> Self:
        if self.from_node_id == self.to_node_id:
            raise ValueError("navigation self-edges are not allowed")
        if len(set(self.polyline)) != len(self.polyline):
            raise ValueError("navigation edge polyline cannot repeat a point")
        if any(first == second for first, second in pairwise(self.polyline)):
            raise ValueError("navigation edge polyline segments must have positive length")
        if self.transition_type == NavigationTransitionType.WALK:
            if self.stair_id is not None:
                raise ValueError("WALK edge cannot carry a stair_id")
        elif not self.stair_id:
            raise ValueError("stair edge requires a stair_id")
        heights = tuple(float(point[2]) for point in self.polyline)
        if self.transition_type == NavigationTransitionType.STAIR_UP and (
            heights[-1] <= heights[0]
            or any(after < before for before, after in pairwise(heights))
        ):
            raise ValueError("STAIR_UP polyline must be vertically nondecreasing and ascend")
        if self.transition_type == NavigationTransitionType.STAIR_DOWN and (
            heights[-1] >= heights[0]
            or any(after > before for before, after in pairwise(heights))
        ):
            raise ValueError("STAIR_DOWN polyline must be vertically nonincreasing and descend")
        return self


class NavigationGraphConfig(DomainModel):
    graph_id: str = Field(min_length=1)
    spatial_context_id: str = Field(min_length=1)
    data_kind: NavigationDataKind
    source_asset_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    cross_floor_policy: CrossFloorPolicy = CrossFloorPolicy.DISCONNECTED
    node_match_tolerance_m: PositiveFinite = 1e-6
    nodes: tuple[NavigationNode, ...] = Field(min_length=1)
    edges: tuple[NavigationEdge, ...] = ()

    @model_validator(mode="after")
    def consistent_graph(self) -> Self:
        if self.data_kind == NavigationDataKind.CONFIGURED and self.source_asset_sha256 is None:
            raise ValueError("CONFIGURED navigation requires a source asset SHA-256")
        node_ids = [node.node_id for node in self.nodes]
        edge_ids = [edge.edge_id for edge in self.edges]
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("navigation node identities must be unique")
        if len(set(edge_ids)) != len(edge_ids):
            raise ValueError("navigation edge identities must be unique")
        nodes = {node.node_id: node for node in self.nodes}
        for edge in self.edges:
            if edge.from_node_id not in nodes or edge.to_node_id not in nodes:
                raise ValueError("navigation edge endpoint does not exist")
            start, end = nodes[edge.from_node_id], nodes[edge.to_node_id]
            crosses_floor = start.floor_id != end.floor_id
            if edge.transition_type == NavigationTransitionType.WALK and crosses_floor:
                raise ValueError("WALK edge cannot cross floors")
            if edge.transition_type != NavigationTransitionType.WALK and not crosses_floor:
                raise ValueError("stair edge must connect different floors")
            if crosses_floor and self.cross_floor_policy == CrossFloorPolicy.DISCONNECTED:
                raise ValueError("cross-floor edges are disabled by graph policy")
        return self


class NavigationPath(DomainModel):
    node_ids: tuple[str, ...] = Field(min_length=1)
    edge_ids: tuple[str, ...]
    polyline: tuple[Vec3, ...] = Field(min_length=1)
    transition_types: tuple[NavigationTransitionType, ...]
    distance_m: NonNegativeFinite

    @model_validator(mode="after")
    def consistent_path(self) -> Self:
        expected_edges = len(self.node_ids) - 1
        if len(self.edge_ids) != expected_edges:
            raise ValueError("navigation path edge/node counts are inconsistent")
        if len(self.transition_types) != expected_edges:
            raise ValueError("navigation path transition/node counts are inconsistent")
        if expected_edges == 0 and (len(self.polyline) != 1 or self.distance_m != 0):
            raise ValueError("zero-edge path must contain one point and zero distance")
        if expected_edges > 0:
            if len(self.polyline) < 2 or self.distance_m <= 0:
                raise ValueError("nontrivial navigation path requires a positive polyline")
            segment_lengths = tuple(
                math.dist(start, end) for start, end in pairwise(self.polyline)
            )
            if any(not math.isfinite(length) or length <= 0 for length in segment_lengths):
                raise ValueError("navigation path segments must have finite positive length")
            try:
                computed = math.fsum(segment_lengths)
            except OverflowError as error:
                raise ValueError("navigation path distance overflowed") from error
            if not math.isfinite(computed) or not math.isclose(
                float(self.distance_m), computed, rel_tol=1e-12, abs_tol=1e-9
            ):
                raise ValueError("navigation path distance must match its full 3D polyline")
        return self
