"""Pixel-derived, hypothesis-scoped synthetic association and geometry composition.

No identity solver or truth channel is imported here. Each pair is an independent
provisional hypothesis. Original pixel IDs and camera-local tracks survive in
explicit maps; no association overwrites a producer record.
"""

from __future__ import annotations

import hashlib
import json
import math
from itertools import pairwise
from typing import Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel
from amidst.domain.observation import Observation
from amidst.domain.stream import BoundGapEvent, StreamBinding
from amidst.domain.trajectory import TerminationReason
from amidst.engineering.association import (
    AssociationHypothesis as LegacyAssociationHypothesis,
)
from amidst.engineering.association import (
    AssociationPolicy as LegacyAssociationPolicy,
)
from amidst.engineering.association import (
    ConfiguredRegion as ConfiguredRegion,
)
from amidst.engineering.association import (
    DerivedRecordMap,
    InferenceScope,
    LocalRecordMap,
    ProjectedMeasurement,
    SyntheticStaticContext,
    _check_declared_contract,
    _derived_observation,
    _graph_input,
    _has_endpoint_projection,
    _local_segments,
    _path_regions,
    _project,
)
from amidst.engineering.association import (
    GroundCalibration as GroundCalibration,
)
from amidst.engineering.local_index import (
    CameraLink,
    CameraRegions,
    IndexRecord,
    RetrievalPolicy,
    RetrievalReceipt,
    ScopedLocalIndex,
    ScopedTopology,
)
from amidst.engineering.perception import PerceptionResult
from amidst.engineering.registry import ResourceScope, opaque_ref, scope_parts
from amidst.integration.repositories import RepositorySnapshot
from amidst.pipeline import reconstruct_input


def content_sha256(value: DomainModel | object) -> str:
    """Canonical strict JSON identity; no filesystem locator is part of this layer."""
    payload = value.model_dump(mode="json") if isinstance(value, DomainModel) else value
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


class AssociationPolicy(LegacyAssociationPolicy):
    retrieval_max_hops: int = Field(default=3, ge=0)
    retrieval_max_cameras: int = Field(default=32, gt=0)
    retrieval_max_records: int = Field(default=128, gt=0)


class AssociationFeatureScores(DomainModel):
    """Uncalibrated synthetic ranking features, independent of Graph ordering."""

    spatial_prior: FiniteFloat = Field(ge=0, le=1)
    time_continuity: FiniteFloat = Field(ge=0, le=1)
    appearance_continuity: FiniteFloat | None = Field(default=None, ge=0, le=1)
    departure_speed_m_s: FiniteFloat | None = Field(default=None, ge=0)
    arrival_speed_m_s: FiniteFloat | None = Field(default=None, ge=0)
    motion_alignment: FiniteFloat | None = Field(default=None, ge=-1, le=1)


class IndexedSegmentMap(DomainModel):
    record_ref: str
    segment_id: str


class AssociationHypothesis(LegacyAssociationHypothesis):
    feature_scores: AssociationFeatureScores | None = None


class InferenceBundle(DomainModel):
    schema_version: Literal["simulation.local-association.v1"] = "simulation.local-association.v1"
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
    association_enumeration_complete: bool = True
    retrieval_receipts: tuple[RetrievalReceipt, ...] = ()
    retrieval_record_maps: tuple[IndexedSegmentMap, ...] = ()
    association_pool_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    limitations: tuple[str, ...] = (
        "Class-agnostic RGB appearance and configured ground-plane projection are uncertain.",
        "Each retrieved pair is independent; no confirmed identity or probability is assigned.",
        "Association completeness covers retrieved pairs only; finite windows omit later arrivals.",
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
        indexed = {item.record_ref: item.segment_id for item in self.retrieval_record_maps}
        if len(indexed) != len(self.retrieval_record_maps) or set(indexed.values()) != set(local):
            raise ValueError("indexed records must preserve exactly the original local segments")
        expected_pairs: set[frozenset[str]] = set()
        anchors: set[str] = set()
        for receipt in self.retrieval_receipts:
            if receipt.scope != resource_scope(self.scope) or receipt.anchor_ref not in indexed:
                raise ValueError("retrieval receipt scope and anchor must retain source lineage")
            if receipt.anchor_ref in anchors or receipt.pairs_considered != len(
                receipt.candidate_refs
            ):
                raise ValueError("retrieval anchors and candidate counts must be unique")
            anchors.add(receipt.anchor_ref)
            for ref in receipt.candidate_refs:
                if ref not in indexed:
                    raise ValueError("retrieval candidates must reference imported local segments")
                pair = frozenset((indexed[receipt.anchor_ref], indexed[ref]))
                if len(pair) != 2 or pair in expected_pairs:
                    raise ValueError("retrieval pairs must be unique before hypothesis formation")
                expected_pairs.add(pair)
        if (
            anchors != set(indexed)
            or unmatched != set(local)
            or paired != expected_pairs
            or (self.pair_count != len(paired))
        ):
            raise ValueError("indexed association pool must retain retrieved pairs and unmatched")
        if self.association_pool_sha256 != content_sha256(candidate_segment_pairs(self)):
            raise ValueError("association candidate pool hash must match retrieval receipts")
        if self.association_enumeration_complete != all(
            receipt.local_inventory_complete for receipt in self.retrieval_receipts
        ):
            raise ValueError("association completeness must describe local retrieval coverage")
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


def resource_scope(scope: InferenceScope) -> ResourceScope:
    return ResourceScope(
        place_id=scope.place_id,
        model_id=scope.model_id,
        model_revision=scope.model_revision,
        run_id=scope.run_id,
        source_id=scope.source_ref,
        source_sha256=scope.source_sha256,
        spatial_context_id=scope.spatial_context_id,
        spatial_context_sha256=scope.context_sha256,
        clock_id=scope.clock_id,
    )


def candidate_segment_pairs(bundle: InferenceBundle) -> tuple[tuple[str, str], ...]:
    indexed = {item.record_ref: item.segment_id for item in bundle.retrieval_record_maps}
    return tuple(
        (indexed[receipt.anchor_ref], indexed[ref])
        for receipt in bundle.retrieval_receipts
        for ref in receipt.candidate_refs
    )


def _association_features(
    first: Observation,
    second: Observation,
    appearance_distance: float | None,
    policy: AssociationPolicy,
) -> AssociationFeatureScores:
    distance = (
        math.dist(first.projected_path[-1].world_position, second.projected_path[0].world_position)
        if first.projected_path and second.projected_path
        else None
    )

    def velocity(observation: Observation, *, departure: bool) -> tuple[float, ...] | None:
        points = observation.projected_path
        if len(points) < 2:
            return None
        a, b = (points[-2], points[-1]) if departure else (points[0], points[1])
        elapsed = b.timestamp - a.timestamp
        if elapsed <= 0:
            return None
        return tuple(
            (v - u) / elapsed for u, v in zip(a.world_position, b.world_position, strict=True)
        )

    departure_velocity = velocity(first, departure=True)
    arrival_velocity = velocity(second, departure=False)
    departure_speed = math.hypot(*departure_velocity) if departure_velocity is not None else None
    arrival_speed = math.hypot(*arrival_velocity) if arrival_velocity is not None else None
    speeds = [
        speed for speed in (departure_speed, arrival_speed) if speed is not None and speed > 0
    ]
    expected_speed = (
        min(policy.max_speed_m_s, math.fsum(speeds) / len(speeds))
        if speeds
        else (policy.max_speed_m_s)
    )
    alignment: float | None = None
    if (
        departure_velocity is not None
        and arrival_velocity is not None
        and (
            departure_speed is not None
            and arrival_speed is not None
            and departure_speed > 0
            and arrival_speed > 0
        )
    ):
        alignment = max(
            -1.0,
            min(
                1.0,
                math.fsum(
                    a * b
                    for a, b in zip(
                        departure_velocity,
                        arrival_velocity,
                        strict=True,
                    )
                )
                / (departure_speed * arrival_speed),
            ),
        )
    gap = max(0.0, second.start_time - first.end_time)
    # Projected velocity comes only from pixel samples. Turns and late arrivals remain
    # feasible; timing / direction affect ranking and never enforce a physical rejection.
    residual = abs(gap - distance / expected_speed) if distance is not None else gap
    direction_prior = 1.0 if alignment is None else (1.0 + alignment) / 2.0
    return AssociationFeatureScores(
        spatial_prior=0.0 if distance is None else 1.0 / (1.0 + distance),
        time_continuity=(0.5 + 0.5 * direction_prior) / (1.0 + residual),
        appearance_continuity=None
        if appearance_distance is None
        else (1.0 / (1.0 + appearance_distance / policy.appearance_max_distance)),
        departure_speed_m_s=departure_speed,
        arrival_speed_m_s=arrival_speed,
        motion_alignment=alignment,
    )


def rank_association_hypotheses(
    bundle: InferenceBundle,
    *,
    removed_feature: Literal["SPACE", "TIME", "APPEARANCE"] | None = None,
) -> tuple[AssociationHypothesis, ...]:
    """Rank the frozen eligible pool; Graph candidates and canonical events stay intact."""

    def score(item: AssociationHypothesis) -> float:
        features = item.feature_scores
        if features is None:
            return 0.0
        return math.fsum(
            (
                features.spatial_prior if removed_feature != "SPACE" else 0.0,
                features.time_continuity if removed_feature != "TIME" else 0.0,
                (features.appearance_continuity or 0.0) if removed_feature != "APPEARANCE" else 0.0,
            )
        )

    return tuple(
        sorted(
            (
                item
                for item in bundle.association_hypotheses
                if item.kind != "UNMATCHED" and item.status != "INCOMPATIBLE"
            ),
            key=lambda item: (-score(item), item.hypothesis_id),
        )
    )


def build_inference(
    perception: PerceptionResult,
    *,
    scope: InferenceScope,
    context: SyntheticStaticContext,
    policy: AssociationPolicy | None = None,
    topology: ScopedTopology | None = None,
    retrieval_policy: RetrievalPolicy | None = None,
) -> InferenceBundle:
    """Freeze all local records, feasible pairs and explicit unresolved alternatives.

    The only dynamic input is the strictly validated RGB producer result. No
    recipes, actor IDs, simulator channels or evaluation sidecars are accepted.
    """
    _check_declared_contract(perception)
    _check_declared_contract(scope)
    _check_declared_contract(context)
    _check_declared_contract(policy)
    _check_declared_contract(topology)
    _check_declared_contract(retrieval_policy)
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
    index_scope = resource_scope(scope)
    if topology is None:
        # Compatibility adapter for the existing explicitly configured E0 lab.
        # Identity clock mapping is bound to this synthetic source and clock ID.
        topology = ScopedTopology(
            scope=index_scope,
            camera_ids=tuple(item.camera_id for item in context.calibrations),
            camera_links=tuple(
                CameraLink(from_camera_id=a, to_camera_id=b)
                for a, b in context.allowed_camera_pairs
            ),
            camera_regions=tuple(
                CameraRegions(
                    camera_id=item.camera_id,
                    region_ids=tuple(region.region_id for region in context.regions),
                )
                for item in context.calibrations
            ),
            topology_complete=True,
            clock_mapping_sha256=content_sha256(
                [scope.source_sha256, scope.clock_id, "SYNTHETIC_CONFIG_IDENTITY_SECONDS"]
            ),
        )
    elif topology.scope != index_scope:
        raise ValueError("retrieval topology must match the exact inference scope")
    rows = tuple(
        IndexRecord(
            scope=index_scope,
            record_ref=opaque_ref("track", *scope_parts(index_scope), mapping.segment_id),
            kind="TRACK",
            camera_id=bound.observation.camera_id,
            start_time=bound.observation.start_time,
            end_time=bound.observation.end_time,
            region_ids=_path_regions(
                tuple(point.world_position for point in bound.observation.projected_path), context
            ),
        )
        for bound, mapping in ordered
    )
    local_index = ScopedLocalIndex(rows, (topology,))
    indexed_sources = {row.record_ref: pair for row, pair in zip(rows, ordered, strict=True)}
    retrieval_policy = retrieval_policy or RetrievalPolicy(
        window_steps_s=(policy.max_association_gap_s,),
        max_hops=policy.retrieval_max_hops,
        max_cameras=policy.retrieval_max_cameras,
        max_records=policy.retrieval_max_records,
    )
    receipts = tuple(
        local_index.retrieve_successors(index_scope, row.record_ref, retrieval_policy)
        for row in rows
    )
    pair_refs = tuple(
        (receipt.anchor_ref, ref) for receipt in receipts for ref in receipt.candidate_refs
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
    for first_ref, second_ref in pair_refs:
        start, first_map = indexed_sources[first_ref]
        end, second_map = indexed_sources[second_ref]
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
        minimum_path_m = local_index.minimum_path_length_m(
            index_scope,
            first.camera_id,
            second.camera_id,
            max_hops=retrieval_policy.max_hops,
        )
        minimum_travel_exceeded = (
            not overlap
            and minimum_path_m is not None
            and (
                minimum_path_m
                > policy.max_speed_m_s
                * (second.start_time - first.end_time + topology.clock_uncertainty_s)
                + 2 * policy.projection_uncertainty_m
            )
        )
        status: Literal["PROVISIONAL", "HOLD", "INCOMPATIBLE"] = "PROVISIONAL"
        reason = "PIXEL_APPEARANCE_FEASIBLE_PROVISIONAL_PAIR"
        if minimum_travel_exceeded:
            status, reason = "INCOMPATIBLE", "SOURCE_BOUND_MINIMUM_TRAVEL_TIME_EXCEEDED"
        elif appearance_distance is None:
            status, reason = "HOLD", "APPEARANCE_MEASUREMENT_MISSING"
        elif overlap and same_camera:
            status, reason = "INCOMPATIBLE", "DISTINCT_SAME_CAMERA_SEGMENTS_OVERLAP"
        elif same_camera:
            status, reason = "HOLD", "SAME_CAMERA_RECOVERY_SOURCE_BOUND_HOLD"
        elif (first.camera_id, second.camera_id) not in context.allowed_camera_pairs:
            status, reason = "HOLD", "CAMERA_PAIR_AUTHORITY_NOT_CONFIGURED"
        elif overlap:
            by_time = {point.timestamp: point for point in second.projected_path}
            common = [
                (point, by_time[point.timestamp])
                for point in first.projected_path
                if point.timestamp in by_time
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
                feature_scores=_association_features(first, second, appearance_distance, policy),
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
        retrieval_receipts=receipts,
        retrieval_record_maps=tuple(
            IndexedSegmentMap(record_ref=row.record_ref, segment_id=mapping.segment_id)
            for row, (_, mapping) in zip(rows, ordered, strict=True)
        ),
        association_pool_sha256=content_sha256(
            tuple(
                (indexed_sources[a][1].segment_id, indexed_sources[b][1].segment_id)
                for a, b in pair_refs
            )
        ),
        association_enumeration_complete=all(row.local_inventory_complete for row in receipts),
    )
