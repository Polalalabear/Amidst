"""Bounded Top-K search over topology-authorized walkable transition paths."""

from __future__ import annotations

import hashlib
import heapq
import json
import math
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, FiniteFloat, ValidationError, model_validator

from amidst.domain.common import DomainModel, Provenance, Vec3
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.trajectory import (
    CandidateTrajectory,
    ReconstructionResult,
    TerminationReason,
)
from amidst.navigation.graph import NavigationError
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import TopologyError


class GraphInputFailure(StrEnum):
    INVALID_OBSERVATION = "INVALID_OBSERVATION"
    DUPLICATE_OBSERVATION = "DUPLICATE_OBSERVATION"
    TARGET_MISMATCH = "TARGET_MISMATCH"
    INVALID_TIME_GAP = "INVALID_TIME_GAP"
    ENDPOINT_FLOOR_REQUIRED = "ENDPOINT_FLOOR_REQUIRED"
    ENDPOINT_FLOOR_MISMATCH = "ENDPOINT_FLOOR_MISMATCH"
    UNKNOWN_CAMERA = "UNKNOWN_CAMERA"
    ENDPOINT_OFF_NETWORK = "ENDPOINT_OFF_NETWORK"
    INVALID_MAX_PATHS = "INVALID_MAX_PATHS"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"


class GraphInputError(ValueError):
    """Caller-inspectable rejection for malformed evidence or search configuration."""

    def __init__(self, failure: GraphInputFailure, message: str) -> None:
        super().__init__(message)
        self.failure = failure


class GraphFactorMask(DomainModel):
    """Additive comparison masks; geometric floor/stair authorization stays intact."""

    travel_time_filter: bool = True
    camera_topology_filter: bool = True


class GeometricRoute(DomainModel):
    """An enumerated route may lack an admissible timing in the observed GAP."""

    candidate_id: str = Field(min_length=1)
    start_observation_id: str = Field(min_length=1)
    end_observation_id: str = Field(min_length=1)
    polyline: tuple[Vec3, ...] = Field(min_length=2)
    navmesh_corridor: tuple[str, ...]
    path_length: FiniteFloat = Field(ge=0)
    minimum_travel_time: FiniteFloat = Field(ge=0)
    observed_gap_duration: FiniteFloat = Field(gt=0)
    timing_status: Literal["FEASIBLE", "UNAVAILABLE"]
    provenance: Literal[Provenance.INFERRED_GAP] = Provenance.INFERRED_GAP

    @model_validator(mode="after")
    def timing_agrees_with_observed_gap(self) -> Self:
        feasible = not _exceeds(self.minimum_travel_time, self.observed_gap_duration)
        if (self.timing_status == "FEASIBLE") != feasible:
            raise ValueError("geometric route timing status must agree with its unchanged GAP")
        return self


class GeometricSearchResult(DomainModel):
    routes: tuple[GeometricRoute, ...] = ()
    termination_reason: TerminationReason
    expanded_nodes: int = Field(default=0, ge=0)
    complete: bool = True
    rejection_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def consistent_search_result(self) -> Self:
        if len({route.candidate_id for route in self.routes}) != len(self.routes):
            raise ValueError("geometric route identities must be unique")
        exhaustive = {TerminationReason.COMPLETE, TerminationReason.NO_FEASIBLE_PATH}
        if self.complete != (self.termination_reason in exhaustive):
            raise ValueError("geometric search completeness must agree with termination")
        if self.termination_reason == TerminationReason.NO_FEASIBLE_PATH and self.routes:
            raise ValueError("NO_FEASIBLE_PATH cannot carry geometric routes")
        return self


class _SearchLimitReached(Exception):
    def __init__(self, reason: TerminationReason) -> None:
        self.reason = reason


def _validated_model[ModelT: DomainModel](
    model: ModelT, model_type: type[ModelT], message: str
) -> ModelT:
    if not isinstance(model, model_type):
        raise GraphInputError(GraphInputFailure.INVALID_CONFIGURATION, message)
    try:
        return model_type.model_validate(model.model_dump(mode="python"))
    except ValidationError as error:
        raise GraphInputError(GraphInputFailure.INVALID_CONFIGURATION, message) from error


def _finite_sum(left: float, right: float, label: str) -> float:
    value = left + right
    if not math.isfinite(value):
        raise GraphInputError(
            GraphInputFailure.NUMERICAL_FAILURE,
            f"{label} must remain finite",
        )
    return value


def _finite_product(left: float, right: float, label: str) -> float:
    value = left * right
    if not math.isfinite(value):
        raise GraphInputError(
            GraphInputFailure.NUMERICAL_FAILURE,
            f"{label} must remain finite",
        )
    return value


def _exceeds(value: float, limit: float) -> bool:
    tolerance = max(1e-12, 4 * max(math.ulp(value), math.ulp(limit)))
    return value > limit and value - limit > tolerance


def _detour_limit(shortest_distance: float, policy: GraphSearchPolicy) -> float:
    if shortest_distance == 0:
        return float(policy.max_path_length_m)
    return _finite_product(
        shortest_distance,
        float(policy.max_detour_ratio),
        "maximum detour distance",
    )


def _endpoint_floor(observation: Observation, point: ProjectedPoint) -> str:
    if observation.floor_id is not None and point.floor_id is not None:
        if observation.floor_id != point.floor_id:
            raise GraphInputError(
                GraphInputFailure.ENDPOINT_FLOOR_MISMATCH,
                "observation and projected endpoint floor identities differ",
            )
    floor_id = point.floor_id or observation.floor_id
    if floor_id is None:
        raise GraphInputError(
            GraphInputFailure.ENDPOINT_FLOOR_REQUIRED,
            "graph search requires an explicit endpoint floor identity",
        )
    return floor_id


def _candidate_id(
    network: NavigationNetwork,
    start: Observation,
    end: Observation,
    start_point: ProjectedPoint,
    end_point: ProjectedPoint,
    transition_ids: tuple[str, ...],
    edge_ids: tuple[str, ...],
    polyline: tuple[Vec3, ...],
    distance: float,
    minimum_time: float,
    actual_gap: float,
    max_speed_m_s: float,
) -> str:
    def point_identity(point: ProjectedPoint) -> dict[str, object]:
        return {
            "point_id": point.point_id,
            "observation_id": point.observation_id,
            "camera_id": point.camera_id,
            "plane_id": point.plane_id,
            "floor_id": point.floor_id,
            "timestamp": float(point.timestamp).hex(),
            "world_position": [float(value).hex() for value in point.world_position],
        }

    payload = {
        "identity_version": "amidst_candidate_v1",
        "spatial_context_id": network.navigation.config.spatial_context_id,
        "navigation_graph_id": network.navigation.config.graph_id,
        "topology_id": network.topology.config.topology_id,
        "source_asset_sha256": network.navigation.config.source_asset_sha256,
        "max_speed_m_s": max_speed_m_s.hex(),
        "target_id": start.target_id,
        "start_camera_id": start.camera_id,
        "end_camera_id": end.camera_id,
        "start_floor_id": start.floor_id,
        "end_floor_id": end.floor_id,
        "start_observation_id": start.observation_id,
        "end_observation_id": end.observation_id,
        "start_point": point_identity(start_point),
        "end_point": point_identity(end_point),
        "transition_ids": transition_ids,
        "navigation_edge_ids": edge_ids,
        "polyline": [
            [float(coordinate).hex() for coordinate in point] for point in polyline
        ],
        "path_length": distance.hex(),
        "minimum_travel_time": minimum_time.hex(),
        "estimated_travel_time": actual_gap.hex(),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"candidate:{hashlib.sha256(encoded.encode()).hexdigest()}"


class SpatiotemporalGraphEngine:
    """Generate physically feasible candidates without Ground Truth or semantic ranking."""

    def __init__(
        self,
        network: NavigationNetwork,
        movement: MovementConstraints,
        policy: GraphSearchPolicy | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        factors: GraphFactorMask | None = None,
        route_filter: Callable[[tuple[Vec3, ...]], bool] | None = None,
    ) -> None:
        if not isinstance(network, NavigationNetwork):
            raise GraphInputError(
                GraphInputFailure.INVALID_CONFIGURATION,
                "graph engine requires a validated NavigationNetwork",
            )
        self.network = network
        self.movement = _validated_model(
            movement,
            MovementConstraints,
            "movement constraints do not satisfy their domain contract",
        )
        self.policy = _validated_model(
            policy or GraphSearchPolicy(),
            GraphSearchPolicy,
            "search policy does not satisfy its domain contract",
        )
        if not callable(clock):
            raise GraphInputError(
                GraphInputFailure.INVALID_CONFIGURATION,
                "search clock must be callable",
            )
        self._clock = clock
        self.factors = _validated_model(
            factors or GraphFactorMask(), GraphFactorMask, "invalid graph factor mask",
        )
        if route_filter is not None and not callable(route_filter):
            raise GraphInputError(
                GraphInputFailure.INVALID_CONFIGURATION, "route filter must be callable",
            )
        self._route_filter = route_filter

    def _now(self) -> float:
        value = float(self._clock())
        if not math.isfinite(value):
            raise GraphInputError(
                GraphInputFailure.NUMERICAL_FAILURE,
                "search clock must return a finite value",
            )
        return value

    @staticmethod
    def _validated_observation(observation: Observation) -> Observation:
        if not isinstance(observation, Observation):
            raise GraphInputError(
                GraphInputFailure.INVALID_OBSERVATION,
                "graph endpoints must be Observation instances",
            )
        try:
            validated = Observation.model_validate(observation.model_dump(mode="python"))
        except ValidationError as error:
            raise GraphInputError(
                GraphInputFailure.INVALID_OBSERVATION,
                "graph endpoint does not satisfy the Observation contract",
            ) from error
        if validated.provenance != Provenance.PROJECTED or not validated.projected_path:
            raise GraphInputError(
                GraphInputFailure.INVALID_OBSERVATION,
                "graph endpoints require non-empty PROJECTED evidence",
            )
        return validated

    def _located_endpoint(
        self, observation: Observation, point: ProjectedPoint
    ) -> tuple[str, str]:
        floor_id = _endpoint_floor(observation, point)
        try:
            topology_node = self.network.topology.node(observation.camera_id)
        except TopologyError as error:
            raise GraphInputError(
                GraphInputFailure.UNKNOWN_CAMERA,
                "observation camera is absent from configured topology",
            ) from error
        if topology_node.floor_id != floor_id:
            raise GraphInputError(
                GraphInputFailure.ENDPOINT_FLOOR_MISMATCH,
                "projected endpoint floor does not match camera topology",
            )
        try:
            node_id = self.network.navigation.locate_node(point.world_position, floor_id)
        except NavigationError as error:
            raise GraphInputError(
                GraphInputFailure.ENDPOINT_OFF_NETWORK,
                "projected endpoint cannot be matched to one navigation node",
            ) from error
        if node_id is None:
            raise GraphInputError(
                GraphInputFailure.ENDPOINT_OFF_NETWORK,
                "projected endpoint is outside the configured navigation-node tolerance",
            )
        return node_id, floor_id

    def _geometric_route(
        self,
        start: Observation,
        end: Observation,
        start_point: ProjectedPoint,
        end_point: ProjectedPoint,
        transition_ids: tuple[str, ...],
        edge_ids: tuple[str, ...],
        start_node_id: str,
        actual_gap: float,
    ) -> GeometricRoute:
        try:
            path = self.network.navigation.path_from_edge_ids(start_node_id, edge_ids)
        except NavigationError as error:
            raise GraphInputError(
                GraphInputFailure.INVALID_CONFIGURATION,
                "topology-authorized navigation sequence became invalid",
            ) from error
        distance = float(path.distance_m)
        minimum_time = distance / float(self.movement.max_speed_m_s)
        if not math.isfinite(minimum_time):
            raise GraphInputError(
                GraphInputFailure.NUMERICAL_FAILURE,
                "minimum travel time must remain finite",
            )
        feasible_timing = not _exceeds(minimum_time, actual_gap)
        if not feasible_timing and self.factors.travel_time_filter:
            raise GraphInputError(
                GraphInputFailure.NUMERICAL_FAILURE,
                "candidate minimum travel time exceeds its available gap",
            )
        if feasible_timing and minimum_time > actual_gap:
            minimum_time = actual_gap
        polyline = (
            path.polyline
            if len(path.polyline) >= 2
            else (path.polyline[0], path.polyline[0])
        )
        return GeometricRoute(
            candidate_id=_candidate_id(
                self.network,
                start,
                end,
                start_point,
                end_point,
                transition_ids,
                edge_ids,
                polyline,
                distance,
                minimum_time,
                actual_gap,
                float(self.movement.max_speed_m_s),
            ),
            start_observation_id=start.observation_id,
            end_observation_id=end.observation_id,
            polyline=polyline,
            navmesh_corridor=edge_ids,
            path_length=distance,
            minimum_travel_time=minimum_time,
            observed_gap_duration=actual_gap,
            timing_status="FEASIBLE" if feasible_timing else "UNAVAILABLE",
        )

    def timed_candidate(self, route: GeometricRoute) -> CandidateTrajectory | None:
        """Keep timing-infeasible routes untimed; never change speed or endpoint times."""
        route = _validated_model(route, GeometricRoute, "invalid geometric route")
        if route.timing_status == "UNAVAILABLE":
            return None
        flags = (
            ("CAMERA_REACHABLE", "TOPOLOGY_AUTHORIZED")
            if self.factors.camera_topology_filter else ("CAMERA_TOPOLOGY_FILTER_DISABLED",)
        )
        return CandidateTrajectory(
            candidate_id=route.candidate_id,
            start_observation_id=route.start_observation_id,
            end_observation_id=route.end_observation_id,
            polyline=route.polyline, navmesh_corridor=route.navmesh_corridor,
            path_length=route.path_length, minimum_travel_time=route.minimum_travel_time,
            estimated_travel_time=route.observed_gap_duration,
            spatial_cost=route.path_length,
            temporal_cost=max(0.0, route.observed_gap_duration - route.minimum_travel_time),
            feasibility_flags=(*flags, "WALKABLE", "WITHIN_MAX_SPEED"), path_score=None,
        )

    def propose_feasible_trajectories(
        self, start: Observation, end: Observation, max_paths: int = 3
    ) -> ReconstructionResult:
        if not self.factors.travel_time_filter:
            raise GraphInputError(
                GraphInputFailure.INVALID_CONFIGURATION,
                "disabled time filtering requires propose_geometric_routes and untimed N/A records",
            )
        geometry = self.propose_geometric_routes(start, end, max_paths)
        candidates = tuple(
            candidate for route in geometry.routes
            if (candidate := self.timed_candidate(route)) is not None
        )
        return ReconstructionResult(
            candidates=candidates, termination_reason=geometry.termination_reason,
            expanded_nodes=geometry.expanded_nodes, complete=geometry.complete,
            rejection_reasons=geometry.rejection_reasons,
        )

    def propose_geometric_routes(
        self, start: Observation, end: Observation, max_paths: int = 3,
    ) -> GeometricSearchResult:
        """Use the same bounded traversal for masked comparisons and default C."""
        started_at = self._now()
        last_clock_value = started_at

        def checked_now() -> float:
            nonlocal last_clock_value
            value = self._now()
            if value < last_clock_value:
                raise GraphInputError(
                    GraphInputFailure.NUMERICAL_FAILURE,
                    "search clock must be monotonic and cannot move backwards",
                )
            last_clock_value = value
            return value

        if isinstance(max_paths, bool) or not isinstance(max_paths, int) or max_paths <= 0:
            raise GraphInputError(
                GraphInputFailure.INVALID_MAX_PATHS,
                "max_paths must be a positive integer",
            )
        deadline = _finite_sum(
            started_at,
            float(self.policy.max_search_time_s),
            "search deadline",
        )
        start = self._validated_observation(start)
        end = self._validated_observation(end)
        if start.target_id != end.target_id:
            raise GraphInputError(
                GraphInputFailure.TARGET_MISMATCH,
                "graph endpoints must describe the same target",
            )
        if start.observation_id == end.observation_id:
            raise GraphInputError(
                GraphInputFailure.DUPLICATE_OBSERVATION,
                "graph endpoints must be distinct observations",
            )
        start_point = start.projected_path[-1]
        end_point = end.projected_path[0]
        actual_gap = float(end_point.timestamp) - float(start_point.timestamp)
        if not math.isfinite(actual_gap) or actual_gap <= 0:
            raise GraphInputError(
                GraphInputFailure.INVALID_TIME_GAP,
                "end evidence must occur strictly after start evidence",
            )
        start_node_id, _ = self._located_endpoint(start, start_point)
        end_node_id, _ = self._located_endpoint(end, end_point)

        allowed_by_speed = (
            _finite_product(actual_gap, float(self.movement.max_speed_m_s),
                            "maximum traversable distance")
            if self.factors.travel_time_filter else None
        )
        effective_max_paths = min(max_paths, self.policy.max_candidate_paths)

        queue: list[
            tuple[float, tuple[str, ...], tuple[str, ...], str, str]
        ] = [(0.0, (), (), start.camera_id, start_node_id)]
        seen_states: set[tuple[str, str, tuple[str, ...]]] = {
            (start.camera_id, start_node_id, ())
        }
        seen_corridors: set[tuple[str, ...]] = set()
        candidates: list[GeometricRoute] = []
        shortest_distance: float | None = None
        expanded_nodes = 0
        pruned_for_speed = False
        pruned_for_length = False
        pruned_for_route_filter = False

        try:
            while queue:
                if checked_now() >= deadline:
                    raise _SearchLimitReached(TerminationReason.SEARCH_TIMEOUT)
                if expanded_nodes >= self.policy.max_search_nodes:
                    raise _SearchLimitReached(TerminationReason.MAX_SEARCH_NODES)
                distance, edge_ids, transition_ids, camera_id, nav_node_id = heapq.heappop(
                    queue
                )
                expanded_nodes += 1

                if shortest_distance is not None:
                    detour_limit = _detour_limit(shortest_distance, self.policy)
                    if _exceeds(distance, detour_limit):
                        break

                if nav_node_id == end_node_id and (
                    not self.factors.camera_topology_filter or camera_id == end.camera_id
                ):
                    if edge_ids not in seen_corridors:
                        candidate = self._geometric_route(
                            start,
                            end,
                            start_point,
                            end_point,
                            transition_ids,
                            edge_ids,
                            start_node_id,
                            actual_gap,
                        )
                        seen_corridors.add(edge_ids)
                        if self._route_filter is not None and not self._route_filter(
                            candidate.polyline,
                        ):
                            pruned_for_route_filter = True
                            continue
                        if shortest_distance is None:
                            shortest_distance = float(candidate.path_length)
                        candidates.append(candidate)
                        if len(candidates) > effective_max_paths:
                            return GeometricSearchResult(
                                routes=tuple(candidates[:effective_max_paths]),
                                termination_reason=TerminationReason.MAX_PATHS_REACHED,
                                expanded_nodes=expanded_nodes,
                                complete=False,
                            )

                eligible = (
                    tuple(
                        (transition.to_camera_id, transition.navigation_to_node_id,
                         transition.navigation_edge_ids, transition.transition_id)
                        for transition in self.network.topology.outgoing_transitions(camera_id)
                        if transition.navigation_from_node_id == nav_node_id
                    )
                    if self.factors.camera_topology_filter else
                    tuple(
                        (camera_id, edge.to_node_id, (edge.edge_id,), None)
                        for edge in self.network.navigation.outgoing_edges(nav_node_id)
                    )
                )
                if len(eligible) > self.policy.max_branch_factor:
                    raise _SearchLimitReached(TerminationReason.MAX_BRANCH_FACTOR)
                for next_camera, next_node, step_edges, transition_id in eligible:
                    next_edge_ids = (*edge_ids, *step_edges)
                    try:
                        combined_path = self.network.navigation.path_from_edge_ids(
                            start_node_id, next_edge_ids
                        )
                    except NavigationError as error:
                        raise GraphInputError(
                            GraphInputFailure.INVALID_CONFIGURATION,
                            "topology transition sequence is no longer a valid walkable path",
                        ) from error
                    next_distance = float(combined_path.distance_m)
                    if _exceeds(next_distance, float(self.policy.max_path_length_m)):
                        pruned_for_length = True
                        continue
                    if allowed_by_speed is not None and _exceeds(next_distance, allowed_by_speed):
                        pruned_for_speed = True
                        continue
                    if shortest_distance is not None:
                        detour_limit = _detour_limit(shortest_distance, self.policy)
                        if _exceeds(next_distance, detour_limit):
                            continue
                    next_transition_ids = (
                        transition_ids if transition_id is None
                        else (*transition_ids, transition_id)
                    )
                    state_identity = (
                        next_camera,
                        next_node,
                        next_edge_ids,
                    )
                    if state_identity in seen_states:
                        continue
                    seen_states.add(state_identity)
                    heapq.heappush(
                        queue,
                        (
                            next_distance,
                            next_edge_ids,
                            next_transition_ids,
                            next_camera,
                            next_node,
                        ),
                    )
        except _SearchLimitReached as limit:
            return GeometricSearchResult(
                routes=tuple(candidates),
                termination_reason=limit.reason,
                expanded_nodes=expanded_nodes,
                complete=False,
            )

        if candidates:
            return GeometricSearchResult(
                routes=tuple(candidates),
                termination_reason=TerminationReason.COMPLETE,
                expanded_nodes=expanded_nodes,
                complete=True,
            )
        rejections = ["NO_FEASIBLE_AUTHORIZED_ROUTE"]
        if pruned_for_speed:
            rejections.append("PHYSICALLY_IMPOSSIBLE_SPEED")
        if pruned_for_length:
            rejections.append("MAX_PATH_LENGTH_EXCEEDED")
        if pruned_for_route_filter:
            rejections.append("CONFIGURED_ROUTE_FILTER_REJECTED_OR_UNVALIDATED")
        return GeometricSearchResult(
            termination_reason=TerminationReason.NO_FEASIBLE_PATH,
            expanded_nodes=expanded_nodes,
            complete=True,
            rejection_reasons=tuple(rejections),
        )
