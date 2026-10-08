"""Camera-local provisional tracklet compositions, without canonical rewrites.

No Graph self-transition, simulator identity or interpolated observation is
created.  Every inspected pair and unmatched alternative retains original track
and pixel IDs, including rejected overlap and uncertain recovery evidence.
"""

from __future__ import annotations

import math
from collections import defaultdict
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel, PositiveFinite, Timestamp
from amidst.engineering.access import digest
from amidst.engineering.perception import PerceptionResult
from amidst.engineering.registry import ResourceScope, opaque_ref, scope_parts
from amidst.product.appearance import DescriptorBundle, _declared, descriptor_distance


class StitchError(ValueError):
    pass


class StitchConfig(DomainModel):
    schema_version: Literal["product.stitch-config.v1"] = "product.stitch-config.v1"
    max_gap_s: PositiveFinite = 2.0
    max_contact_gap_px: PositiveFinite = 160.0
    max_pixel_speed_px_s: PositiveFinite = 200.0
    max_descriptor_distance: PositiveFinite = 0.25
    minimum_quality: FiniteFloat = Field(default=0.1, ge=0, le=1)
    max_tracks: int = Field(default=256, ge=1, le=4096)
    max_pairs: int = Field(default=4096, ge=1, le=100_000)


class OriginalTrackMap(DomainModel):
    track_ref: str
    original_track_id: str
    camera_id: str
    original_observation_ids: tuple[str, ...]
    timestamps: tuple[Timestamp, ...]
    missing_sample_timestamps: tuple[Timestamp, ...]


class StitchHypothesis(DomainModel):
    hypothesis_ref: str
    kind: Literal["SHORT_GAP_RECOVERY", "OVERLAPPING_TRACKLETS", "UNMATCHED"]
    status: Literal["PROVISIONAL", "HOLD", "INCOMPATIBLE", "UNMATCHED"]
    track_refs: tuple[str, ...]
    original_track_ids: tuple[str, ...]
    original_observation_ids: tuple[str, ...]
    camera_id: str
    time_range: tuple[Timestamp, Timestamp]
    observed_intervals: tuple[tuple[Timestamp, Timestamp], ...]
    missing_intervals: tuple[tuple[Timestamp, Timestamp], ...]
    missing_sample_timestamps: tuple[Timestamp, ...] = ()
    gap_s: FiniteFloat | None = None
    contact_distance_px: FiniteFloat | None = None
    appearance_distance: FiniteFloat | None = None
    alternatives: tuple[str, ...] = ()
    reason: str
    authority: Literal["PROVISIONAL_PIXEL_STITCH_ONLY"] = "PROVISIONAL_PIXEL_STITCH_ONLY"
    confirmed_identity: Literal[False] = False
    creates_observed_gap_samples: Literal[False] = False


class StitchBundle(DomainModel):
    schema_version: Literal["product.stitch.v1"] = "product.stitch.v1"
    scope: ResourceScope
    dataset_sha256: str
    perception_sha256: str
    appearance_sha256: str
    producer_sha256: str
    config: StitchConfig
    config_sha256: str
    algorithm_sha256: str
    original_tracks: tuple[OriginalTrackMap, ...]
    hypotheses: tuple[StitchHypothesis, ...]
    pairs_inspected: int = Field(ge=0)
    excluded_beyond_gap_window: int = Field(ge=0)
    truncated: bool
    complete: bool
    source_inputs_complete: bool
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    physical_authority_expanded: Literal[False] = False
    canonical_records_rewritten: Literal[False] = False

    @model_validator(mode="after")
    def original_lineage(self) -> Self:
        if digest(self.config) != self.config_sha256 or self.complete != (not self.truncated):
            raise ValueError("stitch config and search completion binding mismatch")
        for value in (
            self.dataset_sha256,
            self.perception_sha256,
            self.appearance_sha256,
            self.producer_sha256,
            self.config_sha256,
            self.algorithm_sha256,
        ):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("stitch inputs require SHA-256")
        tracks = {track.track_ref: track for track in self.original_tracks}
        if len(tracks) != len(self.original_tracks):
            raise ValueError("stitch original tracks must be unique")
        for track in tracks.values():
            if (
                track.track_ref
                != opaque_ref("track", *scope_parts(self.scope), track.original_track_id)
                or not track.timestamps
                or len(track.timestamps) != len(track.original_observation_ids)
                or any(b <= a for a, b in zip(track.timestamps, track.timestamps[1:], strict=False))
            ):
                raise ValueError("stitch original track lineage mismatch")
        refs = [row.hypothesis_ref for row in self.hypotheses]
        if len(refs) != len(set(refs)):
            raise ValueError("stitch hypothesis references must be unique")
        unmatched: list[str] = []
        for row in self.hypotheses:
            selected = [tracks.get(ref) for ref in row.track_refs]
            if (
                not selected
                or any(track is None or track.camera_id != row.camera_id for track in selected)
                or tuple(track.original_track_id for track in selected if track is not None)
                != row.original_track_ids
                or tuple(
                    identity
                    for track in selected
                    if track is not None
                    for identity in track.original_observation_ids
                )
                != row.original_observation_ids
                or any(ref not in refs or ref == row.hypothesis_ref for ref in row.alternatives)
            ):
                raise ValueError("stitch hypothesis must preserve its original pixel mappings")
            if row.kind == "UNMATCHED":
                if len(selected) != 1 or row.status != "UNMATCHED":
                    raise ValueError("unmatched stitch hypotheses require one unchanged track")
                unmatched.extend(row.track_refs)
            elif len(selected) != 2:
                raise ValueError("pair stitch hypotheses require two original tracks")
        if (
            set(unmatched) != set(tracks)
            or len(unmatched) != len(tracks)
            or self.pairs_inspected != len(self.hypotheses) - len(unmatched)
        ):
            raise ValueError("stitch pairs and unmatched alternatives must remain complete")
        return self


def build_stitch_bundle(
    perception: PerceptionResult,
    appearance_bundle: DescriptorBundle,
    *,
    scope: ResourceScope,
    config: StitchConfig | None = None,
) -> StitchBundle:
    config = config or StitchConfig()
    _declared(perception)
    _declared(appearance_bundle)
    perception = PerceptionResult.model_validate(perception.model_dump())
    appearance_bundle = DescriptorBundle.model_validate(appearance_bundle.model_dump())
    if (
        (perception.model_id, perception.run_id) != (scope.model_id, scope.run_id)
        or appearance_bundle.scope != scope
        or appearance_bundle.perception_sha256 != digest(perception.model_dump(mode="json"))
        or appearance_bundle.dataset_sha256 != perception.input_manifest_sha256
        or appearance_bundle.producer_sha256 != perception.producer_sha256
    ):
        raise StitchError("STITCH_INPUT_BINDING_MISMATCH")
    if len(perception.tracks) > config.max_tracks:
        raise StitchError("STITCH_TRACK_BUDGET_EXCEEDED")
    profiles = {row.local_track_id: row for row in appearance_bundle.track_descriptors}
    measurements = {row.observation_id: row for row in perception.measurements}
    samples = {row.observation_id: row for row in appearance_bundle.measurement_descriptors}
    if set(profiles) != {row.local_track_id for row in perception.tracks}:
        raise StitchError("STITCH_TRACK_BINDING_MISMATCH")
    originals, grouped = [], defaultdict(list)
    for track in perception.tracks:
        profile = profiles[track.local_track_id]
        if profile.original_observation_ids != track.observation_ids:
            raise StitchError("STITCH_TRACK_BINDING_MISMATCH")
        originals.append(
            OriginalTrackMap(
                track_ref=profile.track_ref,
                original_track_id=track.local_track_id,
                camera_id=track.camera_id,
                original_observation_ids=track.observation_ids,
                timestamps=track.timestamps,
                missing_sample_timestamps=track.missing_timestamps,
            )
        )
        grouped[track.camera_id].append(track)
    config_hash = digest(config)
    hypotheses: list[StitchHypothesis] = []
    inspected, excluded = 0, 0
    truncated = False
    for camera_id, tracks in sorted(grouped.items()):
        ordered = sorted(
            tracks, key=lambda row: (row.timestamps[0], row.timestamps[-1], row.local_track_id)
        )
        for first, second in combinations(ordered, 2):
            overlap = second.timestamps[0] <= first.timestamps[-1]
            gap = second.timestamps[0] - first.timestamps[-1]
            if not overlap and gap > config.max_gap_s:
                excluded += 1
                continue
            if inspected >= config.max_pairs:
                truncated = True
                continue
            inspected += 1
            source, target = profiles[first.local_track_id], profiles[second.local_track_id]
            endpoint_a = measurements[first.observation_ids[-1]]
            endpoint_b = measurements[second.observation_ids[0]]
            distance = math.dist(endpoint_a.contact_pixel, endpoint_b.contact_pixel)
            appearance = descriptor_distance(source, target)
            status: Literal["PROVISIONAL", "HOLD", "INCOMPATIBLE", "UNMATCHED"] = "PROVISIONAL"
            reason = "SHORT_GAP_PIXEL_AND_APPEARANCE_COMPATIBLE_PROVISIONAL"
            if overlap:
                status, reason = "INCOMPATIBLE", "OVERLAPPING_VISIBLE_TRACKLETS_NOT_STITCHED"
            elif (
                samples[endpoint_a.observation_id].vector is None
                or samples[endpoint_b.observation_id].vector is None
            ):
                status, reason = "HOLD", "ENDPOINT_APPEARANCE_UNAVAILABLE"
            elif appearance is None:
                status, reason = "HOLD", "APPEARANCE_UNAVAILABLE"
            elif min(source.quality, target.quality) < config.minimum_quality:
                status, reason = "HOLD", "APPEARANCE_QUALITY_INSUFFICIENT"
            elif (
                endpoint_a.status != "DETECTED"
                or endpoint_b.status != "DETECTED"
                or endpoint_a.local_alternative_count
                or endpoint_b.local_alternative_count
            ):
                status, reason = "HOLD", "ENDPOINT_MERGE_PARTIAL_OR_LOCAL_AMBIGUITY"
            elif appearance > config.max_descriptor_distance:
                status, reason = "INCOMPATIBLE", "APPEARANCE_DISTANCE_EXCEEDED"
            elif (
                distance > config.max_contact_gap_px or distance / gap > config.max_pixel_speed_px_s
            ):
                status, reason = "INCOMPATIBLE", "PIXEL_DISPLACEMENT_BOUND_EXCEEDED"
            ref = opaque_ref(
                "stitch",
                *scope_parts(scope),
                config_hash,
                first.local_track_id,
                second.local_track_id,
            )
            hypotheses.append(
                StitchHypothesis(
                    hypothesis_ref=ref,
                    kind="OVERLAPPING_TRACKLETS" if overlap else "SHORT_GAP_RECOVERY",
                    status=status,
                    track_refs=(source.track_ref, target.track_ref),
                    original_track_ids=(first.local_track_id, second.local_track_id),
                    original_observation_ids=(*first.observation_ids, *second.observation_ids),
                    camera_id=camera_id,
                    time_range=(
                        first.timestamps[0],
                        max(first.timestamps[-1], second.timestamps[-1]),
                    ),
                    observed_intervals=(
                        (first.timestamps[0], first.timestamps[-1]),
                        (second.timestamps[0], second.timestamps[-1]),
                    ),
                    missing_intervals=()
                    if overlap
                    else ((first.timestamps[-1], second.timestamps[0]),),
                    missing_sample_timestamps=(
                        *first.missing_timestamps,
                        *second.missing_timestamps,
                    ),
                    gap_s=max(0, gap),
                    contact_distance_px=distance,
                    appearance_distance=appearance,
                    reason=reason,
                )
            )
    for original in originals:
        hypotheses.append(
            StitchHypothesis(
                hypothesis_ref=opaque_ref(
                    "stitch",
                    *scope_parts(scope),
                    config_hash,
                    original.original_track_id,
                    "unmatched",
                ),
                kind="UNMATCHED",
                status="UNMATCHED",
                track_refs=(original.track_ref,),
                original_track_ids=(original.original_track_id,),
                original_observation_ids=original.original_observation_ids,
                camera_id=original.camera_id,
                time_range=(original.timestamps[0], original.timestamps[-1]),
                observed_intervals=((original.timestamps[0], original.timestamps[-1]),),
                missing_intervals=(),
                missing_sample_timestamps=original.missing_sample_timestamps,
                reason="ORIGINAL_TRACK_RETAINED_WITHOUT_IDENTITY_CONFIRMATION",
            )
        )
    updated = tuple(
        row.model_copy(
            update={
                "alternatives": tuple(
                    other.hypothesis_ref
                    for other in hypotheses
                    if other.hypothesis_ref != row.hypothesis_ref
                    and row.track_refs[0] in other.track_refs
                )
            }
        )
        for row in hypotheses
    )
    return StitchBundle(
        scope=scope,
        dataset_sha256=perception.input_manifest_sha256,
        perception_sha256=digest(perception.model_dump(mode="json")),
        appearance_sha256=digest(appearance_bundle),
        producer_sha256=perception.producer_sha256,
        config=config,
        config_sha256=config_hash,
        algorithm_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        original_tracks=tuple(originals),
        hypotheses=updated,
        pairs_inspected=inspected,
        excluded_beyond_gap_window=excluded,
        truncated=truncated,
        complete=not truncated,
        source_inputs_complete=appearance_bundle.complete,
    )
