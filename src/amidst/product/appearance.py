"""Local RGB appearance baseline, quality receipts and bounded retrieval.

Descriptors are handcrafted pixel measurements, not trained ReID or identity
probabilities.  Raw vectors remain inside this module's storage contracts; search
returns only the necessary scoped references, quality and similarity summaries.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Literal, Self

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pydantic import BaseModel, Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel, PositiveFinite, Timestamp
from amidst.engineering.access import digest
from amidst.engineering.perception import PerceptionResult
from amidst.engineering.registry import RegistryStore, ResourceScope, opaque_ref, scope_parts

VERSION: Literal["handcrafted-rgb-appearance-v1"] = "handcrafted-rgb-appearance-v1"
DESCRIPTOR_DIMENSION = 34


class AppearanceError(ValueError):
    """Fixed codes expose no local file paths or rejected caller data."""


class AppearanceConfig(DomainModel):
    schema_version: Literal["product.appearance-config.v1"] = "product.appearance-config.v1"
    max_measurements: int = Field(default=4096, gt=0, le=100_000)
    max_crop_side: int = Field(default=128, ge=8, le=512)
    representative_crops: int = Field(default=3, ge=1, le=8)
    max_candidate_tracks: int = Field(default=128, ge=1, le=4096)
    max_top_k: int = Field(default=32, ge=1, le=128)
    max_query_span_s: PositiveFinite = 3600.0
    descriptor_version: Literal["handcrafted-rgb-appearance-v1"] = VERSION


class CropQuality(DomainModel):
    crop_pixels: int = Field(ge=0)
    clipping_fraction: FiniteFloat = Field(ge=0, le=1)
    brightness: FiniteFloat = Field(ge=0, le=1)
    contrast: FiniteFloat = Field(ge=0, le=1)
    edge_strength: FiniteFloat = Field(ge=0, le=1)
    merged_or_partial: bool
    local_alternative_count: int = Field(ge=0)
    quality: FiniteFloat = Field(ge=0, le=1)
    interpretation: Literal["UNCALIBRATED_PIXEL_QUALITY"] = "UNCALIBRATED_PIXEL_QUALITY"


DescriptorStatus = Literal[
    "READY",
    "PARTIAL_OR_MERGED",
    "MISSING_REFERENCE",
    "MISSING_MEDIA",
    "HASH_MISMATCH",
    "INVALID_RGB",
    "INVALID_CROP",
]


class MeasurementDescriptor(DomainModel):
    descriptor_ref: str
    local_track_id: str
    observation_id: str
    camera_id: str
    timestamp: Timestamp
    media_ref: str | None
    input_sha256: str
    status: DescriptorStatus
    vector: tuple[FiniteFloat, ...] | None = None
    quality: CropQuality | None = None

    @model_validator(mode="after")
    def complete_descriptor(self) -> Self:
        available = self.status in {"READY", "PARTIAL_OR_MERGED"}
        if available != (self.vector is not None and self.quality is not None):
            raise ValueError("appearance availability must preserve vector and quality")
        if self.vector is not None and (
            len(self.vector) != DESCRIPTOR_DIMENSION
            or any(value < 0 or value > 1 for value in self.vector)
        ):
            raise ValueError("appearance vectors must use the declared bounded dimension")
        return self


class TrackDescriptor(DomainModel):
    track_ref: str
    local_track_id: str
    camera_id: str
    time_range: tuple[Timestamp, Timestamp]
    original_observation_ids: tuple[str, ...]
    descriptor_refs: tuple[str, ...]
    representative_descriptor_refs: tuple[str, ...]
    representative_media_refs: tuple[str, ...]
    vector: tuple[FiniteFloat, ...] | None
    quality: FiniteFloat = Field(ge=0, le=1)
    usable_measurements: int = Field(ge=0)
    status: Literal["READY", "UNCERTAIN", "UNAVAILABLE"]

    @model_validator(mode="after")
    def valid_profile(self) -> Self:
        if self.vector is not None and (
            len(self.vector) != DESCRIPTOR_DIMENSION
            or any(value < 0 or value > 1 for value in self.vector)
        ):
            raise ValueError("track appearance vectors require the declared bounded dimension")
        if (self.status == "UNAVAILABLE") != (self.vector is None or self.usable_measurements == 0):
            raise ValueError("track appearance availability must agree with its usable samples")
        return self


class DescriptorBundle(DomainModel):
    schema_version: Literal["product.appearance.v1"] = "product.appearance.v1"
    scope: ResourceScope
    dataset_sha256: str
    perception_sha256: str
    producer_sha256: str
    registry_sha256: str
    media_sha256: str
    input_config_sha256: str
    config: AppearanceConfig
    config_sha256: str
    algorithm_sha256: str
    camera_ids: tuple[str, ...] = ()
    measurement_descriptors: tuple[MeasurementDescriptor, ...]
    track_descriptors: tuple[TrackDescriptor, ...]
    complete: bool
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["HANDCRAFTED_PIXEL_APPEARANCE_ONLY"] = "HANDCRAFTED_PIXEL_APPEARANCE_ONLY"
    trained_reid: Literal[False] = False
    scores_are_probabilities: Literal[False] = False

    @model_validator(mode="after")
    def bound_descriptors(self) -> Self:
        if digest(self.config) != self.config_sha256:
            raise ValueError("appearance config hash mismatch")
        if any(
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
            for value in (
                self.dataset_sha256,
                self.perception_sha256,
                self.producer_sha256,
                self.registry_sha256,
                self.media_sha256,
                self.input_config_sha256,
                self.config_sha256,
                self.algorithm_sha256,
            )
        ):
            raise ValueError("appearance bindings require SHA-256")
        samples = {row.descriptor_ref: row for row in self.measurement_descriptors}
        if (
            len(samples) != len(self.measurement_descriptors)
            or len({row.track_ref for row in self.track_descriptors}) != len(self.track_descriptors)
            or len({row.local_track_id for row in self.track_descriptors})
            != len(self.track_descriptors)
        ):
            raise ValueError("appearance references must be unique")
        for track in self.track_descriptors:
            if track.track_ref != opaque_ref(
                "track", *scope_parts(self.scope), track.local_track_id
            ):
                raise ValueError("appearance track reference scope mismatch")
            selected = [samples.get(ref) for ref in track.descriptor_refs]
            if any(
                row is None
                or row.local_track_id != track.local_track_id
                or row.camera_id != track.camera_id
                for row in selected
            ):
                raise ValueError("appearance track must preserve its measurement descriptors")
            if tuple(row.observation_id for row in selected if row is not None) != (
                track.original_observation_ids
            ):
                raise ValueError("appearance track must preserve original observation IDs")
            if not set(track.representative_descriptor_refs).issubset(track.descriptor_refs):
                raise ValueError("representative appearance references must belong to their track")
            if track.time_range[1] < track.time_range[0]:
                raise ValueError("appearance track time range must be ordered")
        covered = [ref for track in self.track_descriptors for ref in track.descriptor_refs]
        if len(covered) != len(set(covered)) or set(covered) != set(samples):
            raise ValueError("each appearance descriptor must belong to exactly one local track")
        if any(
            row.descriptor_ref
            != opaque_ref(
                "appearance",
                *scope_parts(self.scope),
                self.config_sha256,
                row.observation_id,
                row.input_sha256,
            )
            for row in samples.values()
        ):
            raise ValueError("appearance descriptor reference binding mismatch")
        return self


def _declared(value: object) -> None:
    if isinstance(value, BaseModel):
        if set(value.__dict__) - set(type(value).model_fields) or value.model_extra:
            raise AppearanceError("UNDECLARED_INPUT")
        for name in type(value).model_fields:
            _declared(getattr(value, name))
    elif isinstance(value, (tuple, list)):
        for item in value:
            _declared(item)


def _descriptor(
    rgb: NDArray[np.uint8], *, clipping: float, partial: bool, alternatives: int, max_side: int
) -> tuple[tuple[float, ...], CropQuality]:
    original_pixels = rgb.shape[0] * rgb.shape[1]
    if max(rgb.shape[:2]) > max_side:
        scale = max_side / max(rgb.shape[:2])
        resized = Image.fromarray(rgb).resize(
            (max(3, round(rgb.shape[1] * scale)), max(3, round(rgb.shape[0] * scale)))
        )
        rgb = np.asarray(resized, dtype=np.uint8)
    hsv = np.asarray(Image.fromarray(rgb).convert("HSV"), dtype=np.uint8)
    histograms = [
        np.histogram(hsv[:, :, channel], bins=count, range=(0, 256))[0]
        / hsv.shape[0]
        / hsv.shape[1]
        for channel, count in ((0, 8), (1, 4), (2, 4))
    ]
    color = rgb.astype(np.float64) / 255.0
    gray = color.mean(axis=2)
    dy, dx = np.gradient(gray)
    magnitude = np.hypot(dx, dy)
    angle = np.mod(np.arctan2(dy, dx), 2 * np.pi)
    orientation = np.histogram(angle, bins=8, range=(0, 2 * np.pi), weights=magnitude)[0].astype(
        np.float64
    )
    orientation = orientation / max(float(orientation.sum()), 1e-12)
    split = max(1, color.shape[0] // 2)
    bands = np.concatenate((color[:split].mean(axis=(0, 1)), color[split:].mean(axis=(0, 1))))
    aspect = min(1.0, color.shape[1] / color.shape[0] / 2.0)
    vector = np.concatenate((*histograms, orientation, color.mean(axis=(0, 1)), bands, [aspect]))
    edge = min(1.0, float(magnitude.mean()) * 8)
    contrast = min(1.0, float(gray.std()) * 4)
    quality = min(1.0, math.sqrt(original_pixels / 1024)) * (1 - clipping)
    quality *= (0.5 + 0.25 * edge + 0.25 * contrast) / (1 + 0.25 * alternatives)
    if partial:
        quality *= 0.5
    return tuple(float(min(1, max(0, value))) for value in vector), CropQuality(
        crop_pixels=original_pixels,
        clipping_fraction=clipping,
        brightness=float(gray.mean()),
        contrast=contrast,
        edge_strength=edge,
        merged_or_partial=partial,
        local_alternative_count=alternatives,
        quality=quality,
    )


def build_appearance_bundle(
    perception: PerceptionResult,
    store: RegistryStore,
    scope: ResourceScope,
    frame_links: Mapping[str, str],
    *,
    input_config_sha256: str,
    config: AppearanceConfig | None = None,
) -> DescriptorBundle:
    """Import actual verified RGB crops; annotations and filesystem locators are not inputs."""
    config = config or AppearanceConfig()
    _declared(perception)
    perception = PerceptionResult.model_validate(perception.model_dump())
    if perception.model_id != scope.model_id or perception.run_id != scope.run_id:
        raise AppearanceError("SCOPE_BINDING_MISMATCH")
    if len(perception.measurements) > config.max_measurements:
        raise AppearanceError("MEASUREMENT_BUDGET_EXCEEDED")
    frames = {frame.media_ref: frame for frame in store.registry.frames if frame.scope == scope}
    if scope not in {model.scope for model in store.registry.models}:
        raise AppearanceError("SCOPE_UNAVAILABLE")
    by_id = {row.observation_id: row for row in perception.measurements}
    if len(by_id) != len(perception.measurements):
        raise AppearanceError("DUPLICATE_MEASUREMENT")
    images: dict[str, NDArray[np.uint8] | DescriptorStatus] = {}
    samples: list[MeasurementDescriptor] = []
    by_track: dict[str, list[MeasurementDescriptor]] = defaultdict(list)
    config_hash = digest(config)
    for measurement in perception.measurements:
        if (measurement.model_id, measurement.run_id) != (scope.model_id, scope.run_id):
            raise AppearanceError("SCOPE_BINDING_MISMATCH")
        ref = frame_links.get(measurement.frame_ref)
        status: DescriptorStatus = "READY"
        vector, quality = None, None
        if ref is None:
            status = "MISSING_REFERENCE"
        else:
            frame = frames.get(ref)
            if frame is None or (frame.camera_id, frame.timestamp, frame.sha256) != (
                measurement.camera_id,
                measurement.timestamp,
                measurement.input_sha256,
            ):
                raise AppearanceError("FRAME_BINDING_MISMATCH")
            if ref not in images:
                try:
                    payload = store.media_bytes(scope, ref)
                    with Image.open(BytesIO(payload)) as image:
                        if image.mode != "RGB" or image.size != (frame.width, frame.height):
                            raise OSError("expected RGB dimensions")
                        images[ref] = np.asarray(image, dtype=np.uint8).copy()
                except (KeyError, FileNotFoundError):
                    images[ref] = "MISSING_MEDIA"
                except ValueError as error:
                    images[ref] = "HASH_MISMATCH" if "integrity" in str(error) else "MISSING_MEDIA"
                except OSError:
                    images[ref] = "INVALID_RGB"
            image_data = images[ref]
            if isinstance(image_data, str):
                status = image_data
            else:
                left, top, right, bottom = measurement.bbox_xyxy
                x0, y0, x1, y1 = (
                    math.floor(left),
                    math.floor(top),
                    math.ceil(right),
                    math.ceil(bottom),
                )
                expected_area = max(0, x1 - x0) * max(0, y1 - y0)
                x0, y0, x1, y1 = max(0, x0), max(0, y0), min(frame.width, x1), min(frame.height, y1)
                if x1 - x0 < 3 or y1 - y0 < 3 or expected_area <= 0:
                    status = "INVALID_CROP"
                else:
                    clipping = 1 - (x1 - x0) * (y1 - y0) / expected_area
                    partial = measurement.status == "MERGED_OR_PARTIAL" or clipping > 0
                    vector, quality = _descriptor(
                        image_data[y0:y1, x0:x1],
                        clipping=clipping,
                        partial=partial,
                        alternatives=measurement.local_alternative_count,
                        max_side=config.max_crop_side,
                    )
                    status = "PARTIAL_OR_MERGED" if partial else "READY"
        sample = MeasurementDescriptor(
            descriptor_ref=opaque_ref(
                "appearance",
                *scope_parts(scope),
                config_hash,
                measurement.observation_id,
                measurement.input_sha256,
            ),
            local_track_id=measurement.local_track_id,
            observation_id=measurement.observation_id,
            camera_id=measurement.camera_id,
            timestamp=measurement.timestamp,
            media_ref=ref,
            input_sha256=measurement.input_sha256,
            status=status,
            vector=vector,
            quality=quality,
        )
        samples.append(sample)
        by_track[measurement.local_track_id].append(sample)
    profiles = []
    covered: set[str] = set()
    for track in perception.tracks:
        selected = by_track.get(track.local_track_id, [])
        if (
            (track.model_id, track.run_id) != (scope.model_id, scope.run_id)
            or not track.observation_ids
            or set(track.observation_ids) & covered
            or tuple(row.observation_id for row in selected) != track.observation_ids
            or tuple(row.timestamp for row in selected) != track.timestamps
            or any(row.camera_id != track.camera_id for row in selected)
        ):
            raise AppearanceError("TRACK_BINDING_MISMATCH")
        covered.update(track.observation_ids)
        usable = [row for row in selected if row.vector is not None and row.quality is not None]
        weights = [max(0.001, row.quality.quality) for row in usable if row.quality is not None]
        vectors = [row.vector for row in usable]
        averaged = (
            tuple(
                float(value)
                for value in np.average(
                    np.asarray(vectors),
                    axis=0,
                    weights=weights,
                )
            )
            if usable
            else None
        )
        representatives = sorted(
            usable,
            key=lambda row: (
                -(row.quality.quality if row.quality is not None else 0),
                row.timestamp,
                row.descriptor_ref,
            ),
        )[: config.representative_crops]
        profiles.append(
            TrackDescriptor(
                track_ref=opaque_ref("track", *scope_parts(scope), track.local_track_id),
                local_track_id=track.local_track_id,
                camera_id=track.camera_id,
                time_range=(track.timestamps[0], track.timestamps[-1]),
                original_observation_ids=track.observation_ids,
                descriptor_refs=tuple(row.descriptor_ref for row in selected),
                representative_descriptor_refs=tuple(row.descriptor_ref for row in representatives),
                representative_media_refs=tuple(
                    dict.fromkeys(
                        row.media_ref for row in representatives if row.media_ref is not None
                    )
                ),
                vector=averaged,
                quality=math.fsum(weights) / len(weights) if weights else 0,
                usable_measurements=len(usable),
                status=(
                    "UNAVAILABLE"
                    if not usable
                    else "UNCERTAIN"
                    if any(row.status != "READY" for row in selected)
                    else "READY"
                ),
            )
        )
    if covered != set(by_id):
        raise AppearanceError("TRACK_BINDING_MISMATCH")
    return DescriptorBundle(
        scope=scope,
        dataset_sha256=perception.input_manifest_sha256,
        perception_sha256=digest(perception.model_dump(mode="json")),
        producer_sha256=perception.producer_sha256,
        registry_sha256=store.registry.sha256,
        media_sha256=digest([(frame.media_ref, frame.sha256) for frame in frames.values()]),
        input_config_sha256=input_config_sha256,
        config=config,
        config_sha256=config_hash,
        algorithm_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        camera_ids=tuple(camera.camera_id for camera in store.list_cameras(scope)),
        measurement_descriptors=tuple(samples),
        track_descriptors=tuple(profiles),
        complete=all(row.vector is not None for row in samples),
    )


def descriptor_distance(first: TrackDescriptor, second: TrackDescriptor) -> float | None:
    if first.vector is None or second.vector is None:
        return None
    return math.dist(first.vector, second.vector) / math.sqrt(DESCRIPTOR_DIMENSION)


class AppearanceHit(DomainModel):
    track_ref: str
    camera_id: str
    time_range: tuple[Timestamp, Timestamp]
    similarity: FiniteFloat = Field(ge=0, le=1)
    distance: FiniteFloat = Field(ge=0)
    quality: FiniteFloat = Field(ge=0, le=1)
    status: Literal["READY", "UNCERTAIN", "UNAVAILABLE"]
    descriptor_refs: tuple[str, ...]
    representative_media_refs: tuple[str, ...]


class AppearanceSearchResult(DomainModel):
    scope: ResourceScope
    query_track_ref: str
    hits: tuple[AppearanceHit, ...]
    requested_top_k: int
    candidate_tracks_read: int
    eligible_tracks: int
    unavailable_track_refs: tuple[str, ...]
    cutoff_tie_extension: int
    truncated: bool
    complete: bool
    source_inputs_complete: bool
    coverage: Literal["CALLER_ALLOWED_LOCAL_POOL_AND_WINDOW"] = (
        "CALLER_ALLOWED_LOCAL_POOL_AND_WINDOW"
    )
    score_meaning: Literal["HANDCRAFTED_SIMILARITY_NOT_IDENTITY_PROBABILITY"] = (
        "HANDCRAFTED_SIMILARITY_NOT_IDENTITY_PROBABILITY"
    )


class AppearanceIndex:
    """Import once; each query reads only explicitly allowed local track references."""

    def __init__(self, bundle: DescriptorBundle) -> None:
        _declared(bundle)
        self.bundle = DescriptorBundle.model_validate(bundle.model_dump())
        self._tracks = {row.track_ref: row for row in self.bundle.track_descriptors}
        self._cameras = set(self.bundle.camera_ids)

    def search(
        self,
        query_track_ref: str,
        *,
        scope: ResourceScope,
        allowed_track_refs: Sequence[str],
        camera_id: str | None,
        time_range: tuple[float, float],
        top_k: int = 5,
    ) -> AppearanceSearchResult:
        if scope != self.bundle.scope:
            raise AppearanceError("SCOPE_DENIED")
        config = self.bundle.config
        if (
            len(time_range) != 2
            or any(
                isinstance(t, bool)
                or not isinstance(t, (int, float))
                or not math.isfinite(t)
                or t < 0
                for t in time_range
            )
            or time_range[1] < time_range[0]
            or time_range[1] - time_range[0] > config.max_query_span_s
            or isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or not 1 <= top_k <= config.max_top_k
        ):
            raise AppearanceError("INVALID_QUERY")
        if (
            isinstance(allowed_track_refs, str)
            or len(allowed_track_refs) > config.max_candidate_tracks
        ):
            raise AppearanceError("CANDIDATE_BUDGET_EXCEEDED")
        refs = tuple(dict.fromkeys(allowed_track_refs))
        if camera_id is not None and camera_id not in self._cameras:
            raise AppearanceError("CAMERA_UNAVAILABLE")
        query = self._tracks.get(query_track_ref)
        if query is None or query.vector is None:
            raise AppearanceError("QUERY_APPEARANCE_UNAVAILABLE")
        if any(ref not in self._tracks for ref in refs):
            raise AppearanceError("CANDIDATE_SCOPE_DENIED")
        candidates = [self._tracks[ref] for ref in refs if ref != query_track_ref]
        candidates = [
            row
            for row in candidates
            if (camera_id is None or row.camera_id == camera_id)
            and row.time_range[0] <= time_range[1]
            and time_range[0] <= row.time_range[1]
        ]
        available = [row for row in candidates if row.vector is not None]
        ranked = sorted(
            ((descriptor_distance(query, row), row) for row in available),
            key=lambda item: (float(item[0] or 0), item[1].track_ref),
        )
        retained = ranked[:top_k]
        if retained:
            cutoff = float(retained[-1][0] or 0)
            retained.extend(
                item
                for item in ranked[top_k:]
                if math.isclose(float(item[0] or 0), cutoff, abs_tol=1e-12, rel_tol=0)
            )
        unavailable = tuple(row.track_ref for row in candidates if row.vector is None)
        truncated = len(retained) < len(ranked)
        return AppearanceSearchResult(
            scope=scope,
            query_track_ref=query_track_ref,
            hits=tuple(
                AppearanceHit(
                    track_ref=row.track_ref,
                    camera_id=row.camera_id,
                    time_range=row.time_range,
                    similarity=1 / (1 + float(distance or 0)),
                    distance=float(distance or 0),
                    quality=row.quality,
                    status=row.status,
                    descriptor_refs=row.representative_descriptor_refs,
                    representative_media_refs=row.representative_media_refs,
                )
                for distance, row in retained
            ),
            requested_top_k=top_k,
            candidate_tracks_read=len(refs),
            eligible_tracks=len(ranked),
            unavailable_track_refs=unavailable,
            cutoff_tie_extension=max(0, len(retained) - top_k),
            truncated=truncated,
            complete=not truncated,
            source_inputs_complete=not unavailable,
        )
