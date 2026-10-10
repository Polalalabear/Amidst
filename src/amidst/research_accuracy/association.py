"""Versioned crop appearance and soft ranking over an unchanged local pair pool.

Only verified RGB, producer measurements and frozen projected observations enter
this module. Descriptors and scores are handcrafted, uncalibrated evidence; they
do not assign identity, change hard statuses or modify canonical Graph records.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Literal, Self

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel
from amidst.domain.observation import Observation
from amidst.engineering.association import InferenceScope, _check_declared_contract
from amidst.engineering.local_association import (
    AssociationFeatureScores,
    AssociationHypothesis,
    InferenceBundle,
    content_sha256,
)
from amidst.engineering.perception import (
    Measurement,
    PerceptionResult,
    RGBFrame,
    frame_manifest_sha256,
)

VERSION: Literal["robust-chromatic-crop-v2"] = "robust-chromatic-crop-v2"
DIMENSION = 32
Feature = Literal["SPACE", "TIME", "APPEARANCE"]
DescriptorStatus = Literal[
    "READY",
    "UNCERTAIN",
    "MISSING_REFERENCE",
    "MISSING_MEDIA",
    "HASH_MISMATCH",
    "INVALID_RGB",
    "INVALID_CROP",
]


class AssociationConfig(DomainModel):
    schema_version: Literal["research.accuracy-association-config.v2"] = (
        "research.accuracy-association-config.v2"
    )
    descriptor_version: Literal["robust-chromatic-crop-v2"] = VERSION
    appearance_mode: Literal["LEGACY_MEAN_RGB", "ROBUST_CROP"] = "ROBUST_CROP"
    spatial_mode: Literal["LEGACY_PROXIMITY", "FEASIBILITY_RATIO"] = "FEASIBILITY_RATIO"
    time_mode: Literal["LEGACY_DIRECTION", "SPEED_RESIDUAL"] = "SPEED_RESIDUAL"
    spatial_weight: FiniteFloat = Field(default=1.0, ge=0, le=1)
    time_weight: FiniteFloat = Field(default=1.0, ge=0, le=1)
    appearance_weight: FiniteFloat = Field(default=1.0, ge=0, le=1)
    appearance_distance_scale: FiniteFloat = Field(default=0.15, gt=0, le=1)
    time_speed_scale_m_s: FiniteFloat = Field(default=1.5, gt=0)
    crop_inset_fraction: FiniteFloat = Field(default=0.08, ge=0, le=0.25)
    foreground_chroma_distance: FiniteFloat = Field(default=0.10, ge=0, le=1)
    foreground_saturation: FiniteFloat = Field(default=0.15, ge=0, le=1)
    outlier_distance: FiniteFloat = Field(default=0.22, gt=0, le=1)
    max_crop_side: int = Field(default=128, ge=8, le=512)
    max_measurements: int = Field(default=4096, ge=1, le=100_000)
    representative_crops: int = Field(default=3, ge=1, le=8)
    scores_are_probabilities: Literal[False] = False


class CropDescriptor(DomainModel):
    observation_id: str
    local_track_id: str
    frame_ref: str
    camera_id: str
    timestamp: FiniteFloat
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: DescriptorStatus
    vector: tuple[FiniteFloat, ...] | None = None
    quality: FiniteFloat = Field(default=0, ge=0, le=1)
    crop_pixels: int = Field(default=0, ge=0)
    foreground_fraction: FiniteFloat = Field(default=0, ge=0, le=1)
    clipping_fraction: FiniteFloat = Field(default=0, ge=0, le=1)
    merged_or_partial: bool = False
    local_alternative_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def bounded_descriptor(self) -> Self:
        if (self.status in {"READY", "UNCERTAIN"}) != (self.vector is not None):
            raise ValueError("crop availability must agree with RGB descriptor")
        if self.vector is not None and (
            len(self.vector) != DIMENSION or any(value < 0 or value > 1 for value in self.vector)
        ):
            raise ValueError("crop descriptor must preserve its bounded declared dimension")
        return self


class SegmentDescriptor(DomainModel):
    segment_id: str
    local_track_id: str
    observation_ids: tuple[str, ...]
    representative_observation_ids: tuple[str, ...]
    usable_measurements: int = Field(ge=0)
    retained_measurements: int = Field(ge=0)
    excluded_observation_ids: tuple[str, ...]
    vector: tuple[FiniteFloat, ...] | None = None
    quality: FiniteFloat = Field(ge=0, le=1)
    dispersion: FiniteFloat | None = Field(default=None, ge=0, le=1)
    status: Literal["READY", "UNCERTAIN", "UNAVAILABLE"]

    @model_validator(mode="after")
    def original_sample_binding(self) -> Self:
        if (self.status != "UNAVAILABLE") != (self.vector is not None):
            raise ValueError("segment availability must agree with its descriptor")
        if self.vector is not None and len(self.vector) != DIMENSION:
            raise ValueError("segment descriptor dimension mismatch")
        if not set(self.representative_observation_ids + self.excluded_observation_ids) <= set(
            self.observation_ids
        ) or not 0 <= self.retained_measurements <= self.usable_measurements <= len(
            self.observation_ids
        ):
            raise ValueError("segment descriptor must retain its original samples")
        return self


class RGBDescriptorBundle(DomainModel):
    schema_version: Literal["research.accuracy-appearance.v2"] = "research.accuracy-appearance.v2"
    scope: InferenceScope
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    perception_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_inference_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_pool_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    config: AssociationConfig
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    algorithm_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    measurement_descriptors: tuple[CropDescriptor, ...]
    segment_descriptors: tuple[SegmentDescriptor, ...]
    complete: bool
    trained_reid: Literal[False] = False
    scores_are_probabilities: Literal[False] = False
    limitations: tuple[str, ...] = (
        "Handcrafted chromaticity is sensitive to similar clothes, occlusion and viewpoint.",
        "Quality and dispersion describe pixels; neither certifies identity purity.",
        "Excluded crop outliers remain explicit evidence, never deleted producer samples.",
        "No trained ReID, global identity or cross-place generalization is established.",
    )

    @model_validator(mode="after")
    def verify_lineage(self) -> Self:
        if self.config_sha256 != content_sha256(self.config):
            raise ValueError("appearance config hash mismatch")
        samples = {row.observation_id: row for row in self.measurement_descriptors}
        segments = {row.segment_id: row for row in self.segment_descriptors}
        if len(samples) != len(self.measurement_descriptors) or len(segments) != len(
            self.segment_descriptors
        ):
            raise ValueError("appearance identities must remain unique")
        identities = [
            identity for row in self.segment_descriptors for identity in row.observation_ids
        ]
        if len(identities) != len(set(identities)) or set(identities) != set(samples):
            raise ValueError("appearance segments must cover every original sample exactly once")
        for row in self.segment_descriptors:
            if any(
                samples[identity].local_track_id != row.local_track_id
                for identity in row.observation_ids
            ):
                raise ValueError("appearance cannot replace camera-local identities")
        if self.complete != all(row.vector is not None for row in self.measurement_descriptors):
            raise ValueError("appearance completeness must describe missing crops")
        return self


def descriptor_distance(first: Sequence[float], second: Sequence[float]) -> float:
    """Bounded chromatic distance, excluding geometric and absolute brightness cues."""
    if len(first) != DIMENSION or len(second) != DIMENSION:
        raise ValueError("descriptor dimension mismatch")
    a, b = np.asarray(first, dtype=np.float64), np.asarray(second, dtype=np.float64)
    if not np.isfinite(a).all() or not np.isfinite(b).all() or min(a.min(), b.min()) < 0:
        raise ValueError("invalid descriptor values")
    hue = float(np.linalg.norm(np.sqrt(a[:12]) - np.sqrt(b[:12])) / math.sqrt(2))
    saturation = float(np.linalg.norm(np.sqrt(a[12:16]) - np.sqrt(b[12:16])) / math.sqrt(2))
    bands = float(np.abs(a[16:] - b[16:]).reshape(4, 4)[:, :3].sum(axis=1).mean() / 2)
    return min(1.0, max(0.0, 0.35 * hue + 0.10 * saturation + 0.55 * bands))


def _normalize_vector(vector: NDArray[np.float64]) -> tuple[float, ...]:
    vector = vector.copy()
    for lower, upper in ((0, 12), (12, 16)):
        vector[lower:upper] /= max(float(vector[lower:upper].sum()), 1e-12)
    for lower in range(16, DIMENSION, 4):
        vector[lower : lower + 3] /= max(float(vector[lower : lower + 3].sum()), 1e-12)
    return tuple(float(min(1, max(0, value))) for value in vector)


def _rgb_descriptor(
    rgb: NDArray[np.uint8],
    config: AssociationConfig,
) -> tuple[tuple[float, ...], float]:
    if max(rgb.shape[:2]) > config.max_crop_side:
        factor = config.max_crop_side / max(rgb.shape[:2])
        rgb = np.asarray(
            Image.fromarray(rgb).resize(
                (max(3, round(rgb.shape[1] * factor)), max(4, round(rgb.shape[0] * factor)))
            ),
            dtype=np.uint8,
        )
    color = rgb.astype(np.float64) / 255
    chroma = color / np.maximum(color.sum(axis=2, keepdims=True), 1e-8)
    hsv = np.asarray(Image.fromarray(rgb).convert("HSV"), dtype=np.float64) / 255
    border = np.concatenate((chroma[0], chroma[-1], chroma[:, 0], chroma[:, -1]))
    background_chroma = np.median(border, axis=0)
    foreground = (hsv[:, :, 1] >= config.foreground_saturation) | (
        np.linalg.norm(chroma - background_chroma, axis=2) >= config.foreground_chroma_distance
    )
    # Uniform/desaturated clothing has no reliable background-color boundary. Keep
    # the inset crop rather than inventing a segmentation or discarding the sample.
    if np.count_nonzero(foreground) < max(3, foreground.size * 0.08):
        foreground[:] = True
    selected_hsv = hsv[foreground]
    hue_weights = selected_hsv[:, 1]
    hue = np.histogram(selected_hsv[:, 0], bins=12, range=(0, 1), weights=hue_weights)[0]
    if float(hue.sum()) <= 1e-12:
        hue = np.ones(12, dtype=np.float64)
    hue = 0.70 * hue + 0.15 * np.roll(hue, 1) + 0.15 * np.roll(hue, -1)
    saturation = np.histogram(selected_hsv[:, 1], bins=4, range=(0, 1))[0]
    parts: list[NDArray[np.float64]] = [hue.astype(np.float64), saturation.astype(np.float64)]
    for band in range(4):
        lower = band * color.shape[0] // 4
        upper = max(lower + 1, (band + 1) * color.shape[0] // 4)
        mask = foreground[lower:upper]
        pixels = chroma[lower:upper][mask]
        band_hsv = hsv[lower:upper][mask]
        if pixels.size == 0:
            pixels, band_hsv = chroma[lower:upper].reshape(-1, 3), hsv[lower:upper].reshape(-1, 3)
        parts.append(np.asarray([*np.median(pixels, axis=0), float(np.median(band_hsv[:, 1]))]))
    return _normalize_vector(np.concatenate(parts)), float(foreground.mean())


def _crop(
    row: Measurement,
    image: NDArray[np.uint8] | DescriptorStatus,
    config: AssociationConfig,
) -> CropDescriptor:
    common = dict(
        observation_id=row.observation_id,
        local_track_id=row.local_track_id,
        frame_ref=row.frame_ref,
        camera_id=row.camera_id,
        timestamp=row.timestamp,
        input_sha256=row.input_sha256,
        merged_or_partial=row.status == "MERGED_OR_PARTIAL",
        local_alternative_count=row.local_alternative_count,
    )
    if isinstance(image, str):
        return CropDescriptor.model_validate(common | {"status": image})
    left, top, right, bottom = row.bbox_xyxy
    x0, y0, x1, y1 = math.floor(left), math.floor(top), math.ceil(right), math.ceil(bottom)
    area = max(0, x1 - x0) * max(0, y1 - y0)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(image.shape[1], x1), min(image.shape[0], y1)
    if area <= 0 or x1 - x0 < 3 or y1 - y0 < 4:
        return CropDescriptor.model_validate(common | {"status": "INVALID_CROP"})
    pixels = (x1 - x0) * (y1 - y0)
    clipping = 1 - pixels / area
    inset_x = min((x1 - x0 - 3) // 2, int((x1 - x0) * config.crop_inset_fraction))
    inset_y = min((y1 - y0 - 4) // 2, int((y1 - y0) * config.crop_inset_fraction))
    vector, foreground = _rgb_descriptor(
        image[y0 + inset_y : y1 - inset_y, x0 + inset_x : x1 - inset_x], config
    )
    quality = min(1.0, math.sqrt(pixels / 512)) * (1 - clipping) * (1 - 0.5 * row.uncertainty)
    quality /= 1 + 0.25 * row.local_alternative_count
    partial = row.status == "MERGED_OR_PARTIAL"
    if partial:
        quality *= 0.20
    return CropDescriptor.model_validate(
        common
        | {
            "status": "UNCERTAIN" if partial or clipping > 0 else "READY",
            "vector": vector,
            "quality": quality,
            "crop_pixels": pixels,
            "foreground_fraction": foreground,
            "clipping_fraction": clipping,
        }
    )


def _profile(
    segment_id: str,
    local_track_id: str,
    rows: Sequence[CropDescriptor],
    config: AssociationConfig,
) -> SegmentDescriptor:
    usable = [row for row in rows if row.vector is not None]
    retained = usable
    dispersion = None
    if usable:
        # A quality-weighted medoid and bounded rejection resist intermittent merged
        # crops. This does not repair or certify a mixed-identity producer track.
        medoid = min(
            usable,
            key=lambda a: (
                math.fsum(
                    descriptor_distance(a.vector or (), b.vector or ()) * b.quality for b in usable
                ),
                -a.quality,
                a.timestamp,
                a.observation_id,
            ),
        )
        distances = {
            row.observation_id: descriptor_distance(medoid.vector or (), row.vector or ())
            for row in usable
        }
        retained = [
            row for row in usable if distances[row.observation_id] <= config.outlier_distance
        ]
        dispersion = math.fsum(distances.values()) / len(distances)
    vector = None
    if retained:
        vector = _normalize_vector(
            np.average(
                np.asarray([row.vector for row in retained], dtype=np.float64),
                axis=0,
                weights=[max(0.001, row.quality) for row in retained],
            )
        )
    representatives = sorted(
        retained,
        key=lambda row: (
            -row.quality,
            row.timestamp,
            row.observation_id,
        ),
    )[: config.representative_crops]
    excluded = tuple(row.observation_id for row in rows if row not in retained)
    uncertain = bool(excluded) or any(row.status != "READY" for row in rows)
    return SegmentDescriptor(
        segment_id=segment_id,
        local_track_id=local_track_id,
        observation_ids=tuple(row.observation_id for row in rows),
        representative_observation_ids=tuple(row.observation_id for row in representatives),
        usable_measurements=len(usable),
        retained_measurements=len(retained),
        excluded_observation_ids=excluded,
        vector=vector,
        quality=math.fsum(row.quality for row in retained) / len(retained) if retained else 0,
        dispersion=dispersion,
        status="UNAVAILABLE" if vector is None else "UNCERTAIN" if uncertain else "READY",
    )


def build_appearance_bundle(
    perception: PerceptionResult,
    inference: InferenceBundle,
    frames: Sequence[RGBFrame],
    config: AssociationConfig | None = None,
) -> RGBDescriptorBundle:
    """Read only explicit SHA-bound RGB referenced by this producer's measurements."""
    config = config or AssociationConfig()
    for value in (perception, inference, tuple(frames), config):
        _check_declared_contract(value)
    perception = PerceptionResult.model_validate(perception.model_dump())
    inference = InferenceBundle.model_validate(inference.model_dump())
    config = AssociationConfig.model_validate(config.model_dump())
    if (perception.model_id, perception.run_id) != (
        inference.scope.model_id,
        inference.scope.run_id,
    ) or (
        perception.input_manifest_sha256 != inference.input_manifest_sha256
        or perception.producer_sha256 != inference.producer_sha256
        or frame_manifest_sha256(frames) != perception.input_manifest_sha256
    ):
        raise ValueError("appearance source/run/dataset/producer binding mismatch")
    if len(perception.measurements) > config.max_measurements:
        raise ValueError("appearance measurement budget exceeded")
    by_frame = {row.media_ref: row for row in frames}
    by_id = {row.observation_id: row for row in perception.measurements}
    if len(by_frame) != len(frames) or len(by_id) != len(perception.measurements):
        raise ValueError("appearance inputs require unique media and measurement references")
    images: dict[str, NDArray[np.uint8] | DescriptorStatus] = {}
    samples = []
    for measurement in perception.measurements:
        frame = by_frame.get(measurement.frame_ref)
        if frame is None:
            image: NDArray[np.uint8] | DescriptorStatus = "MISSING_REFERENCE"
        else:
            if (measurement.camera_id, measurement.timestamp, measurement.input_sha256) != (
                frame.camera_id,
                frame.timestamp,
                frame.sha256,
            ) or (measurement.model_id, measurement.run_id) != (
                perception.model_id,
                perception.run_id,
            ):
                raise ValueError("appearance frame camera/time/hash binding mismatch")
            if frame.media_ref not in images:
                try:
                    payload = frame.path.read_bytes()
                    if sha256(payload).hexdigest() != frame.sha256:
                        images[frame.media_ref] = "HASH_MISMATCH"
                    else:
                        with Image.open(BytesIO(payload)) as actual:
                            if actual.mode != "RGB" or actual.size != (frame.width, frame.height):
                                raise OSError("RGB dimensions mismatch")
                            images[frame.media_ref] = np.asarray(actual, dtype=np.uint8).copy()
                except FileNotFoundError:
                    images[frame.media_ref] = "MISSING_MEDIA"
                except OSError:
                    images[frame.media_ref] = "INVALID_RGB"
            image = images[frame.media_ref]
        samples.append(_crop(measurement, image, config))
    by_sample = {row.observation_id: row for row in samples}
    profiles = tuple(
        _profile(
            row.segment_id,
            row.local_track_id,
            [by_sample[identity] for identity in row.original_pixel_observation_ids],
            config,
        )
        for row in inference.local_record_maps
    )
    return RGBDescriptorBundle(
        scope=inference.scope,
        dataset_sha256=perception.input_manifest_sha256,
        perception_sha256=content_sha256(perception.model_dump(mode="json")),
        producer_sha256=perception.producer_sha256,
        input_inference_sha256=content_sha256(inference),
        candidate_pool_sha256=inference.association_pool_sha256,
        config=config,
        config_sha256=content_sha256(config),
        algorithm_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        measurement_descriptors=tuple(samples),
        segment_descriptors=profiles,
        complete=all(row.vector is not None for row in samples),
    )


def _endpoint_speed(observation: Observation, *, departure: bool) -> float | None:
    points = observation.projected_path[-4:] if departure else observation.projected_path[:4]
    speeds = [
        math.dist(a.world_position, b.world_position) / (b.timestamp - a.timestamp)
        for a, b in zip(points, points[1:], strict=False)
        if b.timestamp > a.timestamp
    ]
    return float(np.median(speeds)) if speeds else None


def improve_association(
    perception: PerceptionResult,
    inference: InferenceBundle,
    frames: Sequence[RGBFrame],
    config: AssociationConfig | None = None,
) -> InferenceBundle:
    """Replace only pair feature scores/distances; preserve all canonical bytes and IDs."""
    config = config or AssociationConfig()
    appearance = build_appearance_bundle(perception, inference, frames, config)
    descriptors = {row.segment_id: row for row in appearance.segment_descriptors}
    local = {row.segment_id: row for row in inference.local_record_maps}
    observed = {
        row.observation.observation_id: row.observation for row in inference.snapshot.observations
    }
    hypotheses = []
    for row in inference.association_hypotheses:
        old = row.feature_scores
        if old is None or len(row.segment_ids) != 2:
            hypotheses.append(row)
            continue
        first_id, second_id = row.segment_ids
        first = observed[local[first_id].canonical_observation_id]
        second = observed[local[second_id].canonical_observation_id]
        a, b = descriptors[first_id], descriptors[second_id]
        distance, continuity = row.appearance_distance, old.appearance_continuity
        if config.appearance_mode == "ROBUST_CROP":
            distance = (
                descriptor_distance(a.vector, b.vector)
                if a.vector is not None and (b.vector is not None)
                else None
            )
            # Unreliable evidence moves toward neutral; no missing feature is made a
            # positive identity match and the hard HOLD/rejection remains untouched.
            quality = math.sqrt(a.quality * b.quality)
            continuity = (
                None
                if distance is None
                else 0.5 + quality * (1 / (1 + distance / config.appearance_distance_scale) - 0.5)
            )
        spatial, temporal = old.spatial_prior, old.time_continuity
        departure, arrival = old.departure_speed_m_s, old.arrival_speed_m_s
        if first.projected_path and second.projected_path:
            distance_m = math.dist(
                first.projected_path[-1].world_position, second.projected_path[0].world_position
            )
            gap = max(0, second.start_time - first.end_time)
            if config.spatial_mode == "FEASIBILITY_RATIO":
                envelope = (
                    inference.policy.max_speed_m_s * gap
                    + 2 * inference.policy.projection_uncertainty_m
                )
                spatial = 1 / (1 + distance_m / max(envelope, 1e-8))
            if config.time_mode == "SPEED_RESIDUAL":
                departure, arrival = (
                    _endpoint_speed(first, departure=True),
                    _endpoint_speed(second, departure=False),
                )
                speeds = [speed for speed in (departure, arrival) if speed is not None]
                # Overlap is not a travel interval. No invented velocity or gap is
                # required when samples are insufficient; the legacy score survives.
                if speeds and gap > 0:
                    expected = min(inference.policy.max_speed_m_s, float(np.median(speeds)))
                    temporal = 1 / (
                        1 + abs(distance_m / gap - expected) / config.time_speed_scale_m_s
                    )
        features = AssociationFeatureScores(
            spatial_prior=spatial,
            time_continuity=temporal,
            appearance_continuity=continuity,
            departure_speed_m_s=departure,
            arrival_speed_m_s=arrival,
            motion_alignment=old.motion_alignment,
        )
        hypotheses.append(
            row.model_copy(update={"feature_scores": features, "appearance_distance": distance})
        )
    result = inference.model_copy(update={"association_hypotheses": tuple(hypotheses)})
    return InferenceBundle.model_validate(result.model_dump())


def rank_association_hypotheses(
    bundle: InferenceBundle,
    *,
    config: AssociationConfig | None = None,
    removed_feature: Feature | None = None,
    feature_only: Feature | None = None,
) -> tuple[AssociationHypothesis, ...]:
    """Use one frozen pool and explicit weights for full/removal/feature-only comparisons."""
    config = config or AssociationConfig()
    _check_declared_contract(bundle)
    _check_declared_contract(config)
    if removed_feature is not None and feature_only is not None:
        raise ValueError("choose one removal or one feature-only comparison")

    def score(row: AssociationHypothesis) -> float:
        if row.feature_scores is None:
            return 0
        features = row.feature_scores
        return math.fsum(
            weight * value
            for name, weight, value in (
                ("SPACE", config.spatial_weight, features.spatial_prior),
                ("TIME", config.time_weight, features.time_continuity),
                ("APPEARANCE", config.appearance_weight, features.appearance_continuity or 0),
            )
            if name != removed_feature and (feature_only is None or name == feature_only)
        )

    return tuple(
        sorted(
            (
                row
                for row in bundle.association_hypotheses
                if row.kind != "UNMATCHED" and row.status != "INCOMPATIBLE"
            ),
            key=lambda row: (-score(row), row.hypothesis_id),
        )
    )
