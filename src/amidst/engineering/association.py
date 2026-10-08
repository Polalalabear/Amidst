"""Pixel-derived, hypothesis-scoped synthetic association and geometry composition.

No identity solver or truth channel is imported here. Each pair is an independent
provisional hypothesis. Original pixel IDs and camera-local tracks survive in
explicit maps; no association overwrites a producer record.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from itertools import combinations, pairwise
from typing import Literal, Self

from pydantic import BaseModel, Field, FiniteFloat, model_validator

from amidst.domain.camera import Camera
from amidst.domain.common import DomainModel, PositiveFinite, Provenance, Timestamp, Vec3
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.domain.navigation import (
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
)
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.pipeline import InferenceInput
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.stream import BoundGapEvent, BoundObservation, StreamBinding
from amidst.domain.topology import (
    CameraTopologyConfig,
    CameraTopologyNode,
    CameraTransition,
    CameraTransitionType,
)
from amidst.domain.trajectory import TerminationReason
from amidst.engineering.perception import LocalTrack, Measurement, PerceptionResult
from amidst.geometry.inverse_projection import InverseProjectionError, InverseProjectionService
from amidst.integration.repositories import RepositorySnapshot
from amidst.pipeline import reconstruct_input


def content_sha256(value: DomainModel | object) -> str:
    """Canonical strict JSON identity; no filesystem locator is part of this layer."""
    payload = value.model_dump(mode="json") if isinstance(value, DomainModel) else value
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


class InferenceScope(DomainModel):
    place_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    clock_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    spatial_context_id: str = Field(min_length=1)
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class GroundCalibration(DomainModel):
    """Either calibrated pinhole or the lab renderer's explicit affine floor map."""

    camera_id: str = Field(min_length=1)
    plane: Plane
    pinhole: Camera | None = None
    affine_ground_to_pixel: (
        tuple[
            tuple[FiniteFloat, FiniteFloat, FiniteFloat],
            tuple[FiniteFloat, FiniteFloat, FiniteFloat],
        ]
        | None
    ) = None
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["SYNTHETIC_CONFIG"] = "SYNTHETIC_CONFIG"
    units: Literal["METRES"] = "METRES"

    @model_validator(mode="after")
    def valid_calibration(self) -> Self:
        if (self.pinhole is None) == (self.affine_ground_to_pixel is None):
            raise ValueError("exactly one explicit camera calibration is required")
        if self.pinhole is not None and self.pinhole.camera_id != self.camera_id:
            raise ValueError("camera calibration correspondence must match")
        if self.affine_ground_to_pixel is not None:
            first, second = self.affine_ground_to_pixel
            if abs(first[0] * second[1] - first[1] * second[0]) <= 1e-12:
                raise ValueError("affine floor calibration must be nonsingular")
            if self.plane.normal != (0.0, 0.0, 1.0):
                raise ValueError("affine lab calibration requires the explicit XY ground plane")
        return self


class ConfiguredRegion(DomainModel):
    region_id: str = Field(min_length=1)
    floor_id: str = Field(min_length=1)
    bounds_xy_m: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["SYNTHETIC_CONFIG"] = "SYNTHETIC_CONFIG"

    @model_validator(mode="after")
    def valid_bounds(self) -> Self:
        x0, y0, x1, y1 = self.bounds_xy_m
        if x1 <= x0 or y1 <= y0:
            raise ValueError("region bounds must have positive extent")
        return self


class SyntheticStaticContext(DomainModel):
    """Configured convex lab ground only; never school walkability authority.

    Endpoint nodes are inserted at genuinely inferred pixels. Every connector is
    contained in this static convex domain. Camera transitions are possible only
    for the declared camera pairs, and the finite route grammar is direct or via
    one declared detour waypoint. Exhaustion refers to this grammar alone.
    """

    spatial_context_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ground_plane: Plane
    walkable_bounds_xy_m: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
    calibrations: tuple[GroundCalibration, ...]
    regions: tuple[ConfiguredRegion, ...] = ()
    allowed_camera_pairs: tuple[tuple[str, str], ...] = ()
    detour_waypoints_m: tuple[Vec3, ...] = ()
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["SYNTHETIC_CONFIG"] = "SYNTHETIC_CONFIG"
    route_grammar: Literal["DIRECT_OR_ONE_CONFIGURED_WAYPOINT"] = (
        "DIRECT_OR_ONE_CONFIGURED_WAYPOINT"
    )

    @model_validator(mode="after")
    def source_bound_static_context(self) -> Self:
        x0, y0, x1, y1 = self.walkable_bounds_xy_m
        if x1 <= x0 or y1 <= y0:
            raise ValueError("walkable configured bounds must have positive extent")
        camera_ids = [calibration.camera_id for calibration in self.calibrations]
        if len(set(camera_ids)) != len(camera_ids):
            raise ValueError("calibration camera identities must be unique")
        if any(calibration.plane != self.ground_plane for calibration in self.calibrations):
            raise ValueError("calibrations must reference this exact ground plane")
        if len(set(self.allowed_camera_pairs)) != len(self.allowed_camera_pairs):
            raise ValueError("configured camera pairs must be unique")
        if any(
            a == b or a not in camera_ids or b not in camera_ids
            for a, b in self.allowed_camera_pairs
        ):
            raise ValueError("camera pairs require distinct registered cameras")
        if len({region.region_id for region in self.regions}) != len(self.regions):
            raise ValueError("region identities must be unique")
        if any(region.floor_id != self.ground_plane.floor_id for region in self.regions):
            raise ValueError("lab regions must share the configured ground floor")
        if any(
            not _inside(point, self.walkable_bounds_xy_m)
            or abs(point[2] - self.ground_plane.point[2]) > 1e-9
            for point in self.detour_waypoints_m
        ):
            raise ValueError("detour waypoints must be on this configured walkable plane")
        return self


class AssociationPolicy(DomainModel):
    appearance_max_distance: PositiveFinite = 110.0
    max_speed_m_s: PositiveFinite = 3.0
    max_sample_gap_s: PositiveFinite = 0.6
    max_association_gap_s: PositiveFinite = 12.0
    max_overlap_separation_m: PositiveFinite = 2.0
    projection_uncertainty_m: PositiveFinite = 0.5
    graph_search: GraphSearchPolicy = GraphSearchPolicy(max_candidate_paths=8)


class ProjectedMeasurement(DomainModel):
    observation_id: str
    local_track_id: str
    camera_id: str
    timestamp: Timestamp
    frame_ref: str
    point: ProjectedPoint | None = None
    region_ids: tuple[str, ...] = ()
    status: Literal["PROJECTED", "PROJECTION_MISSING", "OUTSIDE_STATIC_SCOPE"]
    reason: str | None = None
    uncertainty_m: PositiveFinite
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["PIXEL_DERIVED_WITH_SYNTHETIC_CONFIG"] = (
        "PIXEL_DERIVED_WITH_SYNTHETIC_CONFIG"
    )


class LocalRecordMap(DomainModel):
    local_track_id: str
    segment_id: str
    original_pixel_observation_ids: tuple[str, ...]
    canonical_observation_id: str
    frame_refs: tuple[str, ...]


class AssociationHypothesis(DomainModel):
    hypothesis_id: str
    kind: Literal["CROSS_CAMERA_GAP", "OVERLAPPING_VISIBILITY", "SAME_CAMERA_RECOVERY", "UNMATCHED"]
    status: Literal["PROVISIONAL", "HOLD", "INCOMPATIBLE", "UNMATCHED"]
    provisional_binding_id: str | None = None
    source_ref: str
    spatial_context_id: str
    run_id: str
    model_id: str
    local_track_ids: tuple[str, ...]
    segment_ids: tuple[str, ...]
    original_observation_ids: tuple[str, ...]
    pixel_observation_ids: tuple[str, ...]
    derived_observation_ids: tuple[str, ...] = ()
    time_range: tuple[Timestamp, Timestamp]
    camera_ids: tuple[str, ...]
    frame_refs: tuple[str, ...]
    region_ids: tuple[str, ...] = ()
    event_id: str | None = None
    candidate_count: int = Field(default=0, ge=0)
    trajectory_hypothesis_count: int = Field(default=0, ge=0)
    termination_reason: TerminationReason | None = None
    complete: bool | None = None
    appearance_distance: FiniteFloat | None = None
    uncertainty: str
    reason: str
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["PROVISIONAL_PIXEL_ASSOCIATION"] = "PROVISIONAL_PIXEL_ASSOCIATION"


class DerivedRecordMap(DomainModel):
    hypothesis_id: str
    provisional_binding_id: str
    original_observation_ids: tuple[str, ...]
    derived_observation_ids: tuple[str, ...]
    local_track_ids: tuple[str, ...]
    pixel_observation_ids: tuple[str, ...]
    derived_event_id: str | None


class InferenceBundle(DomainModel):
    schema_version: Literal["simulation.association.v1"] = "simulation.association.v1"
    scope: InferenceScope
    policy: AssociationPolicy
    input_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    static_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    projected_measurements: tuple[ProjectedMeasurement, ...]
    local_record_maps: tuple[LocalRecordMap, ...]
    association_hypotheses: tuple[AssociationHypothesis, ...]
    derived_record_maps: tuple[DerivedRecordMap, ...]
    snapshot: RepositorySnapshot
    pair_count: int = Field(ge=0)
    association_enumeration_complete: Literal[True] = True
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    limitations: tuple[str, ...] = (
        "Class-agnostic RGB appearance and configured ground-plane projection are uncertain.",
        "Each pair is independent; no globally confirmed identity or probability is assigned.",
        "Graph completeness covers the configured lab route grammar only.",
        "Same-camera recovery is source-bound HOLD; overlapping visibility is not a blind gap.",
    )

    @model_validator(mode="after")
    def preserve_complete_lineage(self) -> Self:
        observations = {
            item.observation.observation_id: item for item in self.snapshot.observations
        }
        pixels = {item.observation_id: item for item in self.projected_measurements}
        local = {item.segment_id: item for item in self.local_record_maps}
        hypotheses = {item.hypothesis_id: item for item in self.association_hypotheses}
        if (
            len(pixels) != len(self.projected_measurements)
            or len(local) != len(self.local_record_maps)
            or len(hypotheses) != len(self.association_hypotheses)
        ):
            raise ValueError("inference identities must be unique")
        expected_binding = StreamBinding(
            source_id=self.scope.source_ref,
            spatial_context_id=self.scope.spatial_context_id,
            source_asset_sha256=self.scope.source_sha256,
        )
        if any(item.binding != expected_binding for item in self.snapshot.observations):
            raise ValueError("canonical records must retain the inference source/context binding")
        covered_pixels: set[str] = set()
        for mapping in self.local_record_maps:
            observation = observations.get(mapping.canonical_observation_id)
            if (
                observation is None
                or observation.sample_ids != mapping.original_pixel_observation_ids
            ):
                raise ValueError("local maps must preserve their exact original pixel samples")
            if observation.observation.target_id != mapping.local_track_id:
                raise ValueError("original observations must retain camera-local track identities")
            for identity in mapping.original_pixel_observation_ids:
                if (
                    identity not in pixels
                    or identity in covered_pixels
                    or (pixels[identity].local_track_id != mapping.local_track_id)
                ):
                    raise ValueError("each projection must map to exactly one local segment")
                covered_pixels.add(identity)
        if covered_pixels != set(pixels):
            raise ValueError("local segments must cover all pixel measurements")
        unmatched: set[str] = set()
        paired: set[frozenset[str]] = set()
        for hypothesis in self.association_hypotheses:
            if (
                hypothesis.source_ref,
                hypothesis.spatial_context_id,
                hypothesis.run_id,
                hypothesis.model_id,
            ) != (
                self.scope.source_ref,
                self.scope.spatial_context_id,
                self.scope.run_id,
                self.scope.model_id,
            ):
                raise ValueError("association hypotheses cannot cross source/context/model/run")
            if any(identity not in local for identity in hypothesis.segment_ids):
                raise ValueError("association hypotheses require original local segments")
            maps = [local[identity] for identity in hypothesis.segment_ids]
            if (
                tuple(item.canonical_observation_id for item in maps)
                != (hypothesis.original_observation_ids)
                or tuple(item.local_track_id for item in maps) != hypothesis.local_track_ids
            ):
                raise ValueError("association hypotheses must retain the original local maps")
            if tuple(
                identity for item in maps for identity in item.original_pixel_observation_ids
            ) != (hypothesis.pixel_observation_ids):
                raise ValueError("association hypotheses must retain original pixel identities")
            if hypothesis.kind == "UNMATCHED":
                if len(hypothesis.segment_ids) != 1 or hypothesis.segment_ids[0] in unmatched:
                    raise ValueError("every local segment requires one unmatched alternative")
                unmatched.add(hypothesis.segment_ids[0])
            else:
                pair = frozenset(hypothesis.segment_ids)
                if len(pair) != 2 or pair in paired:
                    raise ValueError("each independent segment pair must be represented once")
                paired.add(pair)
        expected_pairs = {frozenset(pair) for pair in combinations(local, 2)}
        if unmatched != set(local) or paired != expected_pairs or self.pair_count != len(paired):
            raise ValueError("complete association enumeration must retain all pairs and unmatched")
        gaps = {gap.event.event_id: gap for gap in self.snapshot.gaps}
        mapped_events: set[str] = set()
        expected_observations = {item.canonical_observation_id for item in self.local_record_maps}
        for derived_map in self.derived_record_maps:
            bound_hypothesis = hypotheses.get(derived_map.hypothesis_id)
            if bound_hypothesis is None or (
                derived_map.provisional_binding_id != bound_hypothesis.provisional_binding_id
                or derived_map.original_observation_ids != bound_hypothesis.original_observation_ids
                or derived_map.derived_observation_ids != bound_hypothesis.derived_observation_ids
                or derived_map.local_track_ids != bound_hypothesis.local_track_ids
                or derived_map.pixel_observation_ids != bound_hypothesis.pixel_observation_ids
                or derived_map.derived_event_id != bound_hypothesis.event_id
            ):
                raise ValueError("derived records must preserve their independent hypothesis map")
            if derived_map.derived_event_id is None or derived_map.derived_event_id not in gaps:
                raise ValueError("derived graph records require their canonical event")
            if derived_map.derived_event_id in mapped_events:
                raise ValueError("derived graph events must map exactly once")
            mapped_events.add(derived_map.derived_event_id)
            gap = gaps[derived_map.derived_event_id]
            if gap.event.observation_ids != derived_map.derived_observation_ids or (
                gap.event.target_id != derived_map.provisional_binding_id
                or gap.event.termination_reason != bound_hypothesis.termination_reason
                or gap.search_result.complete != bound_hypothesis.complete
                or len(gap.event.candidates) != bound_hypothesis.candidate_count
                or len(gap.event.trajectories) != bound_hypothesis.trajectory_hypothesis_count
            ):
                raise ValueError("association summaries must preserve canonical graph status")
            expected_observations.update(derived_map.derived_observation_ids)
        if mapped_events != set(gaps) or expected_observations != set(observations):
            raise ValueError("all canonical graph records require complete original lineage")
        if {item.event_id for item in self.association_hypotheses if item.event_id is not None} != (
            mapped_events
        ):
            raise ValueError(
                "association event references must equal their mapped canonical events"
            )
        return self


def _check_declared_contract(value: object) -> None:
    """Reject unchecked model_copy/model_construct extras before serializers drop them."""
    if isinstance(value, BaseModel):
        declared = set(type(value).model_fields)
        if set(value.__dict__) - declared or value.model_extra:
            raise ValueError("inference inputs must not contain undeclared or truth fields")
        for name in declared:
            _check_declared_contract(getattr(value, name))
    elif isinstance(value, (tuple, list)):
        for item in value:
            _check_declared_contract(item)


def _inside(point: Vec3, bounds: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = bounds
    return x0 <= point[0] <= x1 and y0 <= point[1] <= y1


def _region_ids(point: Vec3, context: SyntheticStaticContext) -> tuple[str, ...]:
    return tuple(
        region.region_id for region in context.regions if _inside(point, region.bounds_xy_m)
    )


def _segment_intersects_region(a: Vec3, b: Vec3, region: ConfiguredRegion) -> bool:
    low, high = 0.0, 1.0
    x0, y0, x1, y1 = region.bounds_xy_m
    for origin, delta, minimum, maximum in (
        (a[0], b[0] - a[0], x0, x1),
        (a[1], b[1] - a[1], y0, y1),
    ):
        if delta == 0:
            if origin < minimum or origin > maximum:
                return False
        else:
            first, second = (minimum - origin) / delta, (maximum - origin) / delta
            low, high = max(low, min(first, second)), min(high, max(first, second))
            if high < low:
                return False
    return True


def _path_regions(path: Sequence[Vec3], context: SyntheticStaticContext) -> tuple[str, ...]:
    return tuple(
        region.region_id
        for region in context.regions
        if any(_inside(point, region.bounds_xy_m) for point in path)
        or any(_segment_intersects_region(a, b, region) for a, b in pairwise(path))
    )


def _project(
    measurement: Measurement,
    frame_id: int,
    calibration: GroundCalibration,
    context: SyntheticStaticContext,
    policy: AssociationPolicy,
) -> ProjectedMeasurement:
    frame = ObservationFrame(
        frame_id=frame_id,
        timestamp=measurement.timestamp,
        target_id=measurement.local_track_id,
        camera_id=measurement.camera_id,
        status=VisibilityStatus.OBSERVED,
        point_2d=measurement.contact_pixel,
        provenance=Provenance.OBSERVED,
    )
    point: ProjectedPoint | None = None
    reason: str | None = None
    status: Literal["PROJECTED", "PROJECTION_MISSING", "OUTSIDE_STATIC_SCOPE"] = "PROJECTED"
    if calibration.pinhole is not None:
        try:
            point = InverseProjectionService(calibration.pinhole, calibration.plane).project_frame(
                frame,
            )
        except InverseProjectionError as error:
            reason, status = error.failure.value, "PROJECTION_MISSING"
    else:
        assert calibration.affine_ground_to_pixel is not None
        first, second = calibration.affine_ground_to_pixel
        u, v = measurement.contact_pixel
        determinant = first[0] * second[1] - first[1] * second[0]
        position: Vec3 = (
            ((u - first[2]) * second[1] - first[1] * (v - second[2])) / determinant,
            (first[0] * (v - second[2]) - (u - first[2]) * second[0]) / determinant,
            calibration.plane.point[2],
        )
        point_hash = content_sha256(
            [
                measurement.observation_id,
                calibration.model_dump(mode="json"),
            ]
        )
        point = ProjectedPoint(
            point_id=f"pixel-projection:{point_hash}",
            camera_id=measurement.camera_id,
            plane_id=calibration.plane.plane_id,
            timestamp=measurement.timestamp,
            world_position=position,
            floor_id=calibration.plane.floor_id,
            projection_quality=max(0.0, 1.0 - measurement.uncertainty),
        )
    if point is not None and not _inside(point.world_position, context.walkable_bounds_xy_m):
        point, reason, status = (
            None,
            "PIXEL_PROJECTION_OUTSIDE_CONFIGURED_GROUND",
            "OUTSIDE_STATIC_SCOPE",
        )
    regions = _region_ids(point.world_position, context) if point is not None else ()
    if point is not None and len(regions) == 1:
        point = ProjectedPoint.model_validate(point.model_dump() | {"zone_id": regions[0]})
    return ProjectedMeasurement(
        observation_id=measurement.observation_id,
        local_track_id=measurement.local_track_id,
        camera_id=measurement.camera_id,
        timestamp=measurement.timestamp,
        frame_ref=measurement.frame_ref,
        point=point,
        region_ids=regions,
        status=status,
        reason=reason,
        uncertainty_m=policy.projection_uncertainty_m * (1 + measurement.uncertainty),
    )


def _local_segments(
    tracks: tuple[LocalTrack, ...],
    measurements: tuple[Measurement, ...],
    projected: tuple[ProjectedMeasurement, ...],
    scope: InferenceScope,
    policy: AssociationPolicy,
) -> tuple[tuple[BoundObservation, ...], tuple[LocalRecordMap, ...]]:
    by_id = {item.observation_id: item for item in measurements}
    projections = {item.observation_id: item for item in projected}
    frame_keys = sorted({(item.camera_id, item.timestamp, item.frame_ref) for item in measurements})
    frame_numbers = {key: index for index, key in enumerate(frame_keys)}
    binding = StreamBinding(
        source_id=scope.source_ref,
        spatial_context_id=scope.spatial_context_id,
        source_asset_sha256=scope.source_sha256,
    )
    observations: list[BoundObservation] = []
    maps: list[LocalRecordMap] = []
    for track in sorted(tracks, key=lambda item: item.local_track_id):
        selected = [by_id[identity] for identity in track.observation_ids]
        pieces: list[list[Measurement]] = []
        for item in selected:
            if not pieces or item.timestamp - pieces[-1][-1].timestamp > policy.max_sample_gap_s:
                pieces.append([])
            pieces[-1].append(item)
        for piece in pieces:
            identities = tuple(item.observation_id for item in piece)
            identity_hash = content_sha256(
                [scope.model_dump(mode="json"), track.local_track_id, identities]
            )
            segment_id = f"local-segment:{identity_hash}"
            observation_id = f"local-observation:{identity_hash}"
            frames = tuple(
                ObservationFrame(
                    frame_id=frame_numbers[(item.camera_id, item.timestamp, item.frame_ref)],
                    timestamp=item.timestamp,
                    target_id=track.local_track_id,
                    camera_id=track.camera_id,
                    status=VisibilityStatus.OBSERVED,
                    point_2d=item.contact_pixel,
                    provenance=Provenance.OBSERVED,
                )
                for item in piece
            )
            points = tuple(
                ProjectedPoint.model_validate(
                    point.model_dump()
                    | {
                        "observation_id": observation_id,
                    }
                )
                for item in piece
                if (point := projections[item.observation_id].point) is not None
            )
            zones = {point.zone_id for point in points}
            mean_appearance = tuple(
                math.fsum(item.appearance[index] for item in piece) / len(piece)
                for index in range(3)
            )
            observation = Observation(
                observation_id=observation_id,
                target_id=track.local_track_id,
                camera_id=track.camera_id,
                start_time=piece[0].timestamp,
                end_time=piece[-1].timestamp,
                floor_id=points[0].floor_id if points else None,
                zone_id=next(iter(zones)) if len(zones) == 1 else None,
                frames=frames,
                projected_path=points,
                provenance=Provenance.PROJECTED if points else Provenance.OBSERVED,
                track_ids=(track.local_track_id,),
                appearance_embedding=mean_appearance,
                appearance_quality=max(0.0, 1.0 - max(item.uncertainty for item in piece)),
                tracking_quality=None,
                source_video_reference=None,
                projection_quality=min(point.projection_quality for point in points)
                if points
                else None,
            )
            observations.append(
                BoundObservation(binding=binding, observation=observation, sample_ids=identities)
            )
            maps.append(
                LocalRecordMap(
                    local_track_id=track.local_track_id,
                    segment_id=segment_id,
                    original_pixel_observation_ids=identities,
                    canonical_observation_id=observation_id,
                    frame_refs=tuple(dict.fromkeys(item.frame_ref for item in piece)),
                )
            )
    return tuple(observations), tuple(maps)


def _derived_observation(
    original: BoundObservation, hypothesis_id: str, provisional_id: str
) -> BoundObservation:
    identity_hash = content_sha256([hypothesis_id, original.observation.observation_id])
    identity = f"association-observation:{identity_hash}"
    record = original.observation.model_dump(mode="python") | {
        "observation_id": identity,
        "target_id": provisional_id,
        "frames": [
            frame.model_dump() | {"target_id": provisional_id}
            for frame in original.observation.frames
        ],
        "projected_path": [
            point.model_dump() | {"observation_id": identity}
            for point in original.observation.projected_path
        ],
    }
    return BoundObservation(
        binding=original.binding,
        observation=Observation.model_validate(record),
        sample_ids=original.sample_ids,
    )


def _graph_input(
    start: BoundObservation,
    end: BoundObservation,
    context: SyntheticStaticContext,
    policy: AssociationPolicy,
    hypothesis_id: str,
) -> InferenceInput:
    first, last = start.observation.projected_path[-1], end.observation.projected_path[0]
    floor = context.ground_plane.floor_id
    nodes = [
        NavigationNode(node_id="departure", position=first.world_position, floor_id=floor),
        NavigationNode(node_id="arrival", position=last.world_position, floor_id=floor),
    ]
    edges = [
        NavigationEdge(
            edge_id="direct",
            from_node_id="departure",
            to_node_id="arrival",
            polyline=(first.world_position, last.world_position),
        )
    ]
    transition_routes: list[tuple[str, tuple[str, ...]]] = [("direct", ("direct",))]
    for index, waypoint in enumerate(context.detour_waypoints_m):
        if waypoint in (first.world_position, last.world_position):
            continue
        node_id = f"configured-waypoint-{index}"
        nodes.append(NavigationNode(node_id=node_id, position=waypoint, floor_id=floor))
        edge_a, edge_b = f"detour-{index}-a", f"detour-{index}-b"
        edges.extend(
            (
                NavigationEdge(
                    edge_id=edge_a,
                    from_node_id="departure",
                    to_node_id=node_id,
                    polyline=(first.world_position, waypoint),
                ),
                NavigationEdge(
                    edge_id=edge_b,
                    from_node_id=node_id,
                    to_node_id="arrival",
                    polyline=(waypoint, last.world_position),
                ),
            )
        )
        transition_routes.append((f"configured-detour-{index}", (edge_a, edge_b)))
    navigation = NavigationGraphConfig(
        graph_id=f"lab-navigation:{hypothesis_id}",
        spatial_context_id=context.spatial_context_id,
        data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
        source_asset_sha256=context.source_sha256,
        nodes=tuple(nodes),
        edges=tuple(edges),
    )
    topology = CameraTopologyConfig(
        topology_id=f"lab-topology:{hypothesis_id}",
        navigation_graph_id=navigation.graph_id,
        spatial_context_id=context.spatial_context_id,
        data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
        source_asset_sha256=context.source_sha256,
        nodes=(
            CameraTopologyNode(camera_id=start.observation.camera_id, floor_id=floor),
            CameraTopologyNode(camera_id=end.observation.camera_id, floor_id=floor),
        ),
        transitions=tuple(
            CameraTransition(
                transition_id=identity,
                from_camera_id=start.observation.camera_id,
                to_camera_id=end.observation.camera_id,
                transition_type=CameraTransitionType.ADJACENT,
                navigation_from_node_id="departure",
                navigation_to_node_id="arrival",
                navigation_edge_ids=edge_ids,
            )
            for identity, edge_ids in transition_routes
        ),
    )
    return InferenceInput(
        dataset_id=hypothesis_id,
        random_seed=0,
        start_observation=start.observation,
        end_observation=end.observation,
        navigation=navigation,
        topology=topology,
        movement=MovementConstraints(max_speed_m_s=policy.max_speed_m_s),
        search_policy=policy.graph_search,
    )


def _has_endpoint_projection(observation: Observation, *, first: bool) -> bool:
    if not observation.projected_path:
        return False
    point = observation.projected_path[0] if first else observation.projected_path[-1]
    return point.timestamp == (observation.start_time if first else observation.end_time)


def build_inference(
    perception: PerceptionResult,
    *,
    scope: InferenceScope,
    context: SyntheticStaticContext,
    policy: AssociationPolicy | None = None,
) -> InferenceBundle:
    """Freeze all local records, feasible pairs and explicit unresolved alternatives.

    The only dynamic input is the strictly validated RGB producer result. No
    recipes, actor IDs, simulator channels or evaluation sidecars are accepted.
    """
    _check_declared_contract(perception)
    _check_declared_contract(scope)
    _check_declared_contract(context)
    _check_declared_contract(policy)
    perception = PerceptionResult.model_validate(perception.model_dump(mode="python"))
    scope = InferenceScope.model_validate(scope.model_dump(mode="python"))
    context = SyntheticStaticContext.model_validate(context.model_dump(mode="python"))
    policy = AssociationPolicy.model_validate((policy or AssociationPolicy()).model_dump())
    if perception.model_id != scope.model_id or perception.run_id != scope.run_id:
        raise ValueError("perception model/run must match inference scope")
    if (
        context.source_sha256 != scope.source_sha256
        or (context.spatial_context_id != scope.spatial_context_id)
        or context.context_sha256 != scope.context_sha256
    ):
        raise ValueError("static context must match source/context scope")
    by_id = {item.observation_id: item for item in perception.measurements}
    if len(by_id) != len(perception.measurements):
        raise ValueError("pixel observation IDs must be unique")
    tracks_by_id = {track.local_track_id: track for track in perception.tracks}
    if len(tracks_by_id) != len(perception.tracks):
        raise ValueError("local track IDs must be unique")
    covered: set[str] = set()
    for track in perception.tracks:
        if track.model_id != scope.model_id or track.run_id != scope.run_id:
            raise ValueError("local tracks cannot cross model/run scope")
        if len(track.timestamps) != len(track.observation_ids) or not track.observation_ids:
            raise ValueError("track times must preserve its pixel observations")
        if any(b <= a for a, b in pairwise(track.timestamps)):
            raise ValueError("local track timestamps must be strictly increasing")
        for identity, timestamp in zip(track.observation_ids, track.timestamps, strict=True):
            if identity not in by_id or identity in covered:
                raise ValueError("each pixel observation must occur in exactly one track")
            item = by_id[identity]
            if (
                item.local_track_id,
                item.camera_id,
                item.model_id,
                item.run_id,
                item.timestamp,
            ) != (
                track.local_track_id,
                track.camera_id,
                scope.model_id,
                scope.run_id,
                timestamp,
            ):
                raise ValueError("pixel measurement and track bindings must match")
            covered.add(identity)
    if covered != set(by_id):
        raise ValueError("all pixel measurements require a source-bound local track")
    calibrations = {item.camera_id: item for item in context.calibrations}
    projected: list[ProjectedMeasurement] = []
    for index, item in enumerate(perception.measurements):
        calibration = calibrations.get(item.camera_id)
        if calibration is None:
            projected.append(
                ProjectedMeasurement(
                    observation_id=item.observation_id,
                    local_track_id=item.local_track_id,
                    camera_id=item.camera_id,
                    timestamp=item.timestamp,
                    frame_ref=item.frame_ref,
                    status="PROJECTION_MISSING",
                    reason="CALIBRATION_NOT_REGISTERED",
                    uncertainty_m=policy.projection_uncertainty_m,
                )
            )
        else:
            projected.append(_project(item, index, calibration, context, policy))
    originals, local_maps = _local_segments(
        perception.tracks, perception.measurements, tuple(projected), scope, policy
    )
    ordered = sorted(
        zip(originals, local_maps, strict=True),
        key=lambda pair: (
            pair[0].observation.start_time,
            pair[0].observation.end_time,
            pair[1].segment_id,
        ),
    )
    all_observations = list(originals)
    gaps: list[BoundGapEvent] = []
    hypotheses: list[AssociationHypothesis] = []
    derived_maps: list[DerivedRecordMap] = []
    for original, mapping in ordered:
        observation = original.observation
        hypotheses.append(
            AssociationHypothesis(
                hypothesis_id=f"unmatched:{content_sha256([scope.run_id, mapping.segment_id])}",
                kind="UNMATCHED",
                status="UNMATCHED",
                source_ref=scope.source_ref,
                spatial_context_id=scope.spatial_context_id,
                run_id=scope.run_id,
                model_id=scope.model_id,
                local_track_ids=(mapping.local_track_id,),
                segment_ids=(mapping.segment_id,),
                original_observation_ids=(observation.observation_id,),
                pixel_observation_ids=mapping.original_pixel_observation_ids,
                time_range=(observation.start_time, observation.end_time),
                camera_ids=(observation.camera_id,),
                frame_refs=mapping.frame_refs,
                region_ids=_path_regions(
                    tuple(point.world_position for point in observation.projected_path), context
                ),
                uncertainty="This local segment may remain unrelated to every other "
                "camera segment.",
                reason="UNMATCHED_ALTERNATIVE_RETAINED",
            )
        )
    pair_count = 0
    for (start, first_map), (end, second_map) in combinations(ordered, 2):
        pair_count += 1
        first, second = start.observation, end.observation
        pair_hash = content_sha256(
            [
                scope.model_dump(mode="json"),
                first_map.segment_id,
                second_map.segment_id,
            ]
        )
        hypothesis_id = f"association:{pair_hash}"
        provisional_id = f"provisional:{hypothesis_id}"
        overlap = first.end_time >= second.start_time
        same_camera = first.camera_id == second.camera_id
        kind: Literal["CROSS_CAMERA_GAP", "OVERLAPPING_VISIBILITY", "SAME_CAMERA_RECOVERY"] = (
            "OVERLAPPING_VISIBILITY"
            if overlap
            else "SAME_CAMERA_RECOVERY"
            if same_camera
            else "CROSS_CAMERA_GAP"
        )
        first_appearance, second_appearance = (
            first.appearance_embedding,
            second.appearance_embedding,
        )
        appearance_distance = (
            math.dist(first_appearance, second_appearance)
            if (first_appearance is not None and second_appearance is not None)
            else None
        )
        status: Literal["PROVISIONAL", "HOLD", "INCOMPATIBLE"] = "PROVISIONAL"
        reason = "PIXEL_APPEARANCE_FEASIBLE_PROVISIONAL_PAIR"
        if appearance_distance is None:
            status, reason = "HOLD", "APPEARANCE_MEASUREMENT_MISSING"
        elif appearance_distance > policy.appearance_max_distance:
            status, reason = "INCOMPATIBLE", "RGB_APPEARANCE_THRESHOLD_EXCEEDED"
        elif overlap and same_camera:
            status, reason = "INCOMPATIBLE", "DISTINCT_SAME_CAMERA_SEGMENTS_OVERLAP"
        elif same_camera:
            status, reason = "HOLD", "SAME_CAMERA_RECOVERY_SOURCE_BOUND_HOLD"
        elif not overlap and (second.start_time - first.end_time) > policy.max_association_gap_s:
            status, reason = "INCOMPATIBLE", "ASSOCIATION_GAP_EXCEEDS_CONFIGURED_WINDOW"
        elif (first.camera_id, second.camera_id) not in context.allowed_camera_pairs:
            status, reason = "HOLD", "CAMERA_PAIR_AUTHORITY_NOT_CONFIGURED"
        elif overlap:
            common = [
                (a, b)
                for a in first.projected_path
                for b in second.projected_path
                if a.timestamp == b.timestamp
            ]
            if not common:
                status, reason = "HOLD", "OVERLAP_WITHOUT_SYNCHRONOUS_PROJECTED_EVIDENCE"
            elif min(math.dist(a.world_position, b.world_position) for a, b in common) > (
                policy.max_overlap_separation_m
            ):
                status, reason = "INCOMPATIBLE", "SIMULTANEOUS_PROJECTED_SEPARATION_EXCEEDED"
            else:
                reason = "OVERLAP_ASSOCIATION_NO_BLIND_GAP_OR_CAMERA_HANDOFF"
        elif not _has_endpoint_projection(first, first=False) or not _has_endpoint_projection(
            second,
            first=True,
        ):
            status, reason = "HOLD", "ENDPOINT_PROJECTION_MISSING"
        elif first.projected_path[-1].world_position == second.projected_path[0].world_position:
            status, reason = "HOLD", "ZERO_DISTANCE_CROSS_CAMERA_ROUTE_NOT_REPRESENTABLE"
        derived_ids: tuple[str, ...] = ()
        event_id: str | None = None
        termination: TerminationReason | None = None
        complete: bool | None = None
        candidate_count, trajectory_count = 0, 0
        regions = tuple(
            dict.fromkeys(
                (
                    *_path_regions(
                        tuple(point.world_position for point in first.projected_path), context
                    ),
                    *_path_regions(
                        tuple(point.world_position for point in second.projected_path), context
                    ),
                )
            )
        )
        if status == "PROVISIONAL" and not overlap:
            bound_start = _derived_observation(start, hypothesis_id, provisional_id)
            bound_end = _derived_observation(end, hypothesis_id, provisional_id)
            inputs = _graph_input(bound_start, bound_end, context, policy, hypothesis_id)
            search, event = reconstruct_input(inputs, clock=lambda: 0.0)
            # Region annotations come from configured static rectangles, never recipes.
            candidates = tuple(
                type(candidate).model_validate(
                    candidate.model_dump()
                    | {
                        "semantic_regions": _path_regions(candidate.polyline, context),
                    }
                )
                for candidate in search.candidates
            )
            search = type(search).model_validate(search.model_dump() | {"candidates": candidates})
            event = type(event).model_validate(event.model_dump() | {"candidates": candidates})
            gap = BoundGapEvent(
                binding=start.binding,
                start=bound_start,
                end=bound_end,
                search_result=search,
                event=event,
            )
            gaps.append(gap)
            all_observations.extend((bound_start, bound_end))
            event_id = event.event_id
            derived_ids = (
                bound_start.observation.observation_id,
                bound_end.observation.observation_id,
            )
            candidate_count, trajectory_count = len(event.candidates), len(event.trajectories)
            termination, complete = search.termination_reason, search.complete
            regions = tuple(
                dict.fromkeys(
                    (
                        *regions,
                        *(
                            region
                            for candidate in candidates
                            for region in candidate.semantic_regions
                        ),
                    )
                )
            )
            if not candidates:
                status, reason = "INCOMPATIBLE", "NO_FEASIBLE_CONFIGURED_GRAPH_ROUTE"
            derived_maps.append(
                DerivedRecordMap(
                    hypothesis_id=hypothesis_id,
                    provisional_binding_id=provisional_id,
                    original_observation_ids=(first.observation_id, second.observation_id),
                    derived_observation_ids=derived_ids,
                    local_track_ids=(first_map.local_track_id, second_map.local_track_id),
                    pixel_observation_ids=(
                        *first_map.original_pixel_observation_ids,
                        *second_map.original_pixel_observation_ids,
                    ),
                    derived_event_id=event_id,
                )
            )
        hypotheses.append(
            AssociationHypothesis(
                hypothesis_id=hypothesis_id,
                kind=kind,
                status=status,
                provisional_binding_id=provisional_id
                if status != "INCOMPATIBLE" or event_id
                else None,
                source_ref=scope.source_ref,
                spatial_context_id=scope.spatial_context_id,
                run_id=scope.run_id,
                model_id=scope.model_id,
                local_track_ids=(first_map.local_track_id, second_map.local_track_id),
                segment_ids=(first_map.segment_id, second_map.segment_id),
                original_observation_ids=(first.observation_id, second.observation_id),
                pixel_observation_ids=(
                    *first_map.original_pixel_observation_ids,
                    *second_map.original_pixel_observation_ids,
                ),
                derived_observation_ids=derived_ids,
                time_range=(
                    max(first.start_time, second.start_time),
                    min(first.end_time, second.end_time),
                )
                if overlap
                else (first.end_time, second.start_time),
                camera_ids=(first.camera_id, second.camera_id),
                frame_refs=tuple(dict.fromkeys((*first_map.frame_refs, *second_map.frame_refs))),
                region_ids=regions,
                event_id=event_id,
                candidate_count=candidate_count,
                trajectory_hypothesis_count=trajectory_count,
                termination_reason=termination,
                complete=complete,
                appearance_distance=appearance_distance,
                reason=reason,
                uncertainty="RGB appearance can merge or swap local identities. This is an "
                "independent pair hypothesis, with all unmatched and competing pairs retained; "
                "no probability is "
                "calibrated. Projection assumes the explicitly configured synthetic ground plane.",
            )
        )
    return InferenceBundle(
        scope=scope,
        policy=policy,
        input_manifest_sha256=perception.input_manifest_sha256,
        producer_sha256=perception.producer_sha256,
        static_context_sha256=content_sha256(context),
        projected_measurements=tuple(projected),
        local_record_maps=local_maps,
        association_hypotheses=tuple(hypotheses),
        derived_record_maps=tuple(derived_maps),
        snapshot=RepositorySnapshot(observations=tuple(all_observations), gaps=tuple(gaps)),
        pair_count=pair_count,
    )
