"""Provisional, endpoint-conditioned pilot graph from projected evidence only.

The configured direct/left/right polylines demonstrate the existing downstream
interfaces. An annotation AABB bounds this local scaffold; it does not establish
school navigation, mesh clearance, WALL collision or metric-scale authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from amidst.datasets.pilot import PilotInferenceContext
from amidst.domain.common import Provenance, Vec3
from amidst.domain.navigation import (
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
)
from amidst.domain.observation import Observation
from amidst.domain.pipeline import PipelineConfig
from amidst.domain.reconstruction import ReconstructionPolicy
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.stream import ObservationAggregation
from amidst.domain.topology import (
    CameraTopologyConfig,
    CameraTopologyNode,
    CameraTransition,
    CameraTransitionType,
)
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.observation.aggregation import aggregate_frames, validate_stream_model


def _positive(value: float, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} must be a finite positive configured number")
    return float(value)


def _inside(point: Vec3, context: PilotInferenceContext) -> bool:
    return all(
        low <= value <= high
        for value, low, high in zip(
            point, context.zone.bounds_min, context.zone.bounds_max, strict=True
        )
    )


def _offset_limit(
    start: Vec3,
    end: Vec3,
    direction: tuple[float, float],
    context: PilotInferenceContext,
) -> float:
    limit = math.inf
    for axis, component in enumerate(direction):
        if component > 0:
            available = context.zone.bounds_max[axis] - max(start[axis], end[axis])
            limit = min(limit, available / component)
        elif component < 0:
            available = min(start[axis], end[axis]) - context.zone.bounds_min[axis]
            limit = min(limit, available / -component)
    return max(0.0, limit)


def _endpoints(aggregation: ObservationAggregation) -> tuple[Observation, Observation]:
    if len(aggregation.observations) != 2:
        raise ValueError("pilot topology requires exactly two visible segments and one bounded gap")
    ordered = sorted(
        aggregation.observations,
        key=lambda item: (
            item.observation.start_time,
            item.observation.end_time,
            item.observation.observation_id,
        ),
    )
    start, end = (item.observation for item in ordered)
    if (
        start.target_id != end.target_id
        or start.provenance != Provenance.PROJECTED
        or end.provenance != Provenance.PROJECTED
        or not start.projected_path
        or not end.projected_path
        or start.end_time >= end.start_time
    ):
        raise ValueError(
            "pilot gap endpoints require one target and nonoverlapping PROJECTED evidence"
        )
    if start.camera_id == end.camera_id:
        raise ValueError("this configured pilot topology requires an existing-camera handoff")
    return start, end


def build_pilot_pipeline(
    aggregation: ObservationAggregation,
    context: PilotInferenceContext,
    *,
    lateral_offset_scene_units: float = 12.0,
    max_speed_scene_units_s: float = 32.0,
    max_candidate_paths: int = 3,
) -> tuple[PipelineConfig, dict[str, Any]]:
    """Build a local configured graph without files, simulation routes or truth input.

    Endpoint anchors are the actual projection results, with no snapping. Lateral
    offsets are explicit configuration, reduced only to fit the supplied annotation
    bounds. The native-unit speed ceiling is a diagnostic setting, not a measured
    person speed. ADJACENT transitions authorize this one provisional connector;
    source camera zones are preserved and no school-wide adjacency is asserted.
    """
    aggregation = validate_stream_model(aggregation, ObservationAggregation)
    context = validate_stream_model(context, PilotInferenceContext)
    if aggregate_frames(aggregation.samples, aggregation.policy) != aggregation:
        raise ValueError("pilot topology requires the canonical visible-evidence partition")
    offset = _positive(lateral_offset_scene_units, "lateral offset")
    speed = _positive(max_speed_scene_units_s, "maximum speed")
    if (
        not isinstance(max_candidate_paths, int)
        or isinstance(max_candidate_paths, bool)
        or not 1 <= max_candidate_paths <= 3
    ):
        raise ValueError("pilot candidate path budget must be an integer from 1 through 3")
    if any(
        sample.source_id != context.source_id
        or sample.spatial_context_id != context.spatial_context_id
        or sample.source_asset_sha256 != context.source_asset_sha256
        or sample.data_kind != "SYNTHETIC"
        for sample in aggregation.samples
    ):
        raise ValueError("pilot topology source/context binding differs from projected evidence")
    start, end = _endpoints(aggregation)
    first, last = start.projected_path[-1], end.projected_path[0]
    cameras = {camera.camera_id: camera for camera in context.cameras}
    if start.camera_id not in cameras or end.camera_id not in cameras:
        raise ValueError("pilot endpoint camera is absent from source calibration")
    if any(
        cameras[observation.camera_id].floor_id != context.zone.floor_id
        for observation in (start, end)
    ):
        raise ValueError("source camera floor does not match the configured local zone")
    if (
        context.plane.floor_id != context.zone.floor_id
        or context.plane.zone_id != context.zone.zone_id
        or abs(context.plane.normal[0]) > 1e-9
        or abs(context.plane.normal[1]) > 1e-9
        or context.plane.normal[2] < 1 - 1e-9
    ):
        raise ValueError("pilot topology requires the configured horizontal local projection plane")
    for point in (first, last):
        if (
            point.provenance != Provenance.PROJECTED
            or point.plane_id != context.plane.plane_id
            or point.floor_id != context.zone.floor_id
            or point.zone_id != context.zone.zone_id
            or abs(point.world_position[2] - context.plane.point[2]) > 1e-6
        ):
            raise ValueError(
                "pilot endpoint does not preserve configured plane/floor/zone projection"
            )
        if not _inside(point.world_position, context):
            raise ValueError("projected endpoint lies outside the provisional annotation bounds")
    a, b = first.world_position, last.world_position
    delta = (b[0] - a[0], b[1] - a[1])
    distance_xy = math.hypot(*delta)
    if not math.isfinite(distance_xy) or distance_xy <= 1e-6:
        raise ValueError("moving pilot graph requires distinct projected XY endpoints")
    perpendicular = (-delta[1] / distance_xy, delta[0] / distance_xy)
    routes: dict[str, tuple[Vec3, ...]] = {"direct": (a, b)}
    route_offsets = {"direct": 0.0}
    rejected: dict[str, str] = {}
    for name, sign in (("left", 1.0), ("right", -1.0)):
        direction = (sign * perpendicular[0], sign * perpendicular[1])
        effective = min(offset, _offset_limit(a, b, direction, context))
        if effective <= 1e-6:
            rejected[name] = "NO_POSITIVE_LATERAL_MARGIN_IN_ANNOTATION_AABB"
            continue
        left: Vec3 = (a[0] + direction[0] * effective, a[1] + direction[1] * effective, a[2])
        right: Vec3 = (b[0] + direction[0] * effective, b[1] + direction[1] * effective, b[2])
        polyline = (a, left, right, b)
        if not all(_inside(point, context) for point in polyline):
            rejected[name] = "LATERAL_ROUTE_EXCEEDS_ANNOTATION_AABB_AT_FLOAT_PRECISION"
            continue
        routes[name] = polyline
        route_offsets[name] = effective
    identity = {
        "source_id": context.source_id,
        "context_id": context.spatial_context_id,
        "source_sha256": context.source_asset_sha256,
        "observations_sha256": context.observations_sha256,
        "endpoint_point_ids": (first.point_id, last.point_id),
        "polylines": routes,
    }
    token = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()[:24]
    graph_id = f"pilot_configured_graph:{token}"
    navigation = NavigationGraphConfig(
        graph_id=graph_id,
        spatial_context_id=context.spatial_context_id,
        data_kind=NavigationDataKind.CONFIGURED,
        source_asset_sha256=context.source_asset_sha256,
        nodes=(
            NavigationNode(
                node_id="projected_departure",
                position=a,
                floor_id=context.zone.floor_id,
                zone_id=context.zone.zone_id,
            ),
            NavigationNode(
                node_id="projected_recovery",
                position=b,
                floor_id=context.zone.floor_id,
                zone_id=context.zone.zone_id,
            ),
        ),
        edges=tuple(
            NavigationEdge(
                edge_id=f"pilot_route:{name}",
                from_node_id="projected_departure",
                to_node_id="projected_recovery",
                polyline=polyline,
            )
            for name, polyline in sorted(routes.items())
        ),
    )
    topology = CameraTopologyConfig(
        topology_id=f"pilot_configured_topology:{token}",
        navigation_graph_id=graph_id,
        spatial_context_id=context.spatial_context_id,
        data_kind=NavigationDataKind.CONFIGURED,
        source_asset_sha256=context.source_asset_sha256,
        nodes=tuple(
            CameraTopologyNode(
                camera_id=camera_id,
                floor_id=context.zone.floor_id,
                zone_id=cameras[camera_id].zone_id,
            )
            for camera_id in sorted((start.camera_id, end.camera_id))
        ),
        transitions=tuple(
            CameraTransition(
                transition_id=f"pilot_handoff:{name}",
                from_camera_id=start.camera_id,
                to_camera_id=end.camera_id,
                transition_type=CameraTransitionType.ADJACENT,
                navigation_from_node_id="projected_departure",
                navigation_to_node_id="projected_recovery",
                navigation_edge_ids=(f"pilot_route:{name}",),
            )
            for name in sorted(routes)
        ),
    )
    # Exercise the existing cross-validation; no core graph behavior is changed.
    NavigationNetwork(NavigationGraph(navigation), CameraTopologyGraph(topology))
    pipeline = PipelineConfig(
        navigation=navigation,
        topology=topology,
        movement=MovementConstraints(max_speed_m_s=speed),
        search_policy=GraphSearchPolicy(
            max_candidate_paths=max_candidate_paths,
            max_search_nodes=1000,
            max_path_length_m=1000.0,
            max_search_time_s=10.0,
            max_branch_factor=3,
            max_detour_ratio=2.0,
        ),
        reconstruction_policy=ReconstructionPolicy(),
    )
    evidence: dict[str, Any] = {
        "schema_version": "pilot-configured-topology-evidence-v1",
        "label": context.label,
        "status": "PARTIAL_PROVISIONAL_CONFIGURED_GRAPH",
        "authority": "PROJECTED_ENDPOINTS_AND_EXPLICIT_OFFSET_WITHIN_ANNOTATION_AABB",
        "source_asset_sha256": context.source_asset_sha256,
        "observations_sha256": context.observations_sha256,
        "coordinate_units": context.coordinate_units,
        "scale_authority": context.scale_authority,
        "context_zone": context.zone.model_dump(mode="json"),
        "plane_authority": context.plane_authority,
        "endpoint_basis": "OBSERVED_2D_THROUGH_EXISTING_INVERSE_PROJECTION",
        "endpoint_provenance": (first.provenance.value, last.provenance.value),
        "endpoint_point_ids": (first.point_id, last.point_id),
        "endpoint_observation_ids": (start.observation_id, end.observation_id),
        "gap_time_range": (first.timestamp, last.timestamp),
        "source_camera_zones_preserved": {node.camera_id: node.zone_id for node in topology.nodes},
        "transition_type": "ADJACENT",
        "transition_authority": "EXPLICIT_GAP_SPECIFIC_CONFIGURED_CONNECTOR",
        "requested_lateral_offset_scene_units": offset,
        "effective_lateral_offsets_scene_units": route_offsets,
        "configured_routes": tuple(sorted(routes)),
        "rejected_routes": rejected,
        "configured_route_count": len(routes),
        "max_candidate_paths": max_candidate_paths,
        "max_speed_scene_units_s": speed,
        "speed_authority": "EXPLICIT_PILOT_DIAGNOSTIC_SETTING_NOT_MEASURED_PERSON_SPEED",
        "ordering": "EXISTING_ENGINE_DISTANCE_THEN_STABLE_EDGE_AND_TRANSITION_IDS",
        "path_score": None,
        "ground_truth_used": False,
        "simulation_route_samples_used": False,
        "wall_collision_authority": False,
        "mesh_collision_certified": False,
        "formal_benchmark_executed": False,
        "selection_reason": (
            "One bounded existing-camera handoff is represented by direct and explicit lateral "
            "configured polylines anchored at the exact inverse-projected observations."
        ),
        "limitations": (
            "This is an endpoint-conditioned configured graph, not extracted school topology.",
            "Annotation AABB containment does not check WALKABLE holes, WALLs or physical meshes.",
            "Point-center paths do not establish clearance of the full synthetic marker body.",
            "Native-unit speed, distance and offsets do not certify real metres or person speed.",
            "ADJACENT applies only to this configured gap connector, not school-wide adjacency.",
            "Configured walkable flags describe this scaffold only; physical authority is partial.",
        ),
    }
    return pipeline, evidence
