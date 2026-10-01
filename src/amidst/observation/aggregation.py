"""Deterministic visible segments; no stitching, semantics or hidden trajectory access."""

from __future__ import annotations

import hashlib
import json
from itertools import groupby

from pydantic import ValidationError

from amidst.domain.common import DomainModel, Provenance
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.stream import (
    AggregationPolicy,
    BoundObservation,
    ObservationAggregation,
    RawProjectedFrameSample,
)


class AggregationInputError(ValueError):
    """Ambiguous identities or evidence outside the declared producer contract."""


def _check_contract(value: object) -> None:
    if isinstance(value, DomainModel):
        if DomainModel not in type(value).__bases__:
            raise AggregationInputError("nested models must use exact declared domain contracts")
        fields = set(type(value).model_fields)
        if set(value.__dict__) - fields or value.model_extra:
            raise AggregationInputError("model contains fields outside its declared contract")
        for field in fields:
            _check_contract(getattr(value, field))
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_contract(item)


def validate_stream_model[ModelT: DomainModel](model: ModelT, expected: type[ModelT]) -> ModelT:
    """Recheck unchecked model_copy/model_construct inputs, including nested models."""
    if type(model) is not expected:
        raise AggregationInputError(f"input must be an exact {expected.__name__} model")
    try:
        _check_contract(model)
        return expected.model_validate(model.model_dump(mode="python"))
    except (ValidationError, AttributeError, TypeError, OverflowError) as error:
        raise AggregationInputError(f"input violates the {expected.__name__} contract") from error


def _identity(samples: tuple[RawProjectedFrameSample, ...]) -> str:
    payload = json.dumps(
        {
            "binding": samples[0].binding.model_dump(mode="json"),
            "target_id": samples[0].target_id,
            "camera_id": samples[0].camera_id,
            "samples": [sample.model_dump(mode="json") for sample in samples],
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return f"obs_{hashlib.sha256(payload).hexdigest()[:24]}"


def _same_segment(first: RawProjectedFrameSample, second: RawProjectedFrameSample) -> bool:
    first_point, second_point = first.projected_point, second.projected_point
    return (
        first.binding == second.binding
        and first.target_id == second.target_id
        and first.camera_id == second.camera_id
        and first.provenance == second.provenance
        and (first.uv is None) == (second.uv is None)
        and (first_point is None) == (second_point is None)
        and (
            first_point is None
            or second_point is None
            or (
                first_point.floor_id == second_point.floor_id
                and first_point.zone_id == second_point.zone_id
                and first_point.plane_id == second_point.plane_id
            )
        )
    )


def _observation(samples: tuple[RawProjectedFrameSample, ...]) -> BoundObservation:
    first, last = samples[0], samples[-1]
    identity = _identity(samples)
    projected = tuple(
        ProjectedPoint.model_validate(
            sample.projected_point.model_dump()
            | {
                "observation_id": identity,
            }
        )
        for sample in samples
        if sample.projected_point is not None
    )
    observation = Observation(
        observation_id=identity,
        target_id=first.target_id,
        camera_id=first.camera_id,
        start_time=first.timestamp,
        end_time=last.timestamp,
        floor_id=projected[0].floor_id if projected else None,
        zone_id=projected[0].zone_id if projected else None,
        frames=tuple(
            ObservationFrame(
                frame_id=sample.frame_id,
                timestamp=sample.timestamp,
                camera_id=sample.camera_id,
                target_id=sample.target_id,
                status=VisibilityStatus.OBSERVED,
                point_2d=sample.uv,
                provenance=Provenance.OBSERVED,
                data_kind=sample.data_kind,
            )
            for sample in samples
            if sample.uv is not None
        ),
        projected_path=projected,
        provenance=Provenance.PROJECTED if projected else Provenance.OBSERVED,
    )
    return BoundObservation(
        binding=first.binding,
        observation=observation,
        sample_ids=tuple(sample.sample_id for sample in samples),
    )


def aggregate_frames(
    samples: tuple[RawProjectedFrameSample, ...],
    policy: AggregationPolicy | None = None,
) -> ObservationAggregation:
    """Split on explicit GAPs, camera handoffs, binding/floor/projection changes.

    Input order has no meaning. Ties are sorted by stable identity; duplicate
    target/camera timestamps or source/target/camera frame IDs are ambiguous and
    rejected. A GAP from another camera never erases visible evidence. Multiple
    cameras visible simultaneously are retained for Event inference to reject as
    ambiguous rather than silently choosing a camera.
    """
    policy = validate_stream_model(policy or AggregationPolicy(), AggregationPolicy)
    validated = tuple(validate_stream_model(sample, RawProjectedFrameSample) for sample in samples)
    sample_ids: set[str] = set()
    timestamp_keys: set[tuple[str, str, float]] = set()
    frame_keys: set[tuple[str, str, str, int]] = set()
    for sample in validated:
        timestamp_key = (sample.target_id, sample.camera_id, float(sample.timestamp))
        frame_key = (sample.source_id, sample.target_id, sample.camera_id, sample.frame_id)
        if (
            sample.sample_id in sample_ids
            or timestamp_key in timestamp_keys
            or frame_key in frame_keys
        ):
            raise AggregationInputError(
                "duplicate sample, camera timestamp or source frame identity"
            )
        sample_ids.add(sample.sample_id)
        timestamp_keys.add(timestamp_key)
        frame_keys.add(frame_key)
    canonical = tuple(
        sorted(
            validated,
            key=lambda sample: (
                sample.timestamp,
                sample.target_id,
                sample.camera_id,
                sample.source_id,
                sample.sample_id,
            ),
        )
    )
    by_target = sorted(
        canonical,
        key=lambda sample: (sample.target_id, sample.timestamp, sample.camera_id, sample.sample_id),
    )
    observations: list[BoundObservation] = []
    for _, target_samples in groupby(by_target, key=lambda sample: sample.target_id):
        active: dict[str, list[RawProjectedFrameSample]] = {}

        def close(
            camera_id: str,
            active_cameras: dict[str, list[RawProjectedFrameSample]] = active,
        ) -> None:
            group = active_cameras.pop(camera_id, [])
            if group:
                observations.append(_observation(tuple(group)))

        for _, time_samples in groupby(target_samples, key=lambda sample: sample.timestamp):
            simultaneous = tuple(time_samples)
            visible_cameras = {
                sample.camera_id
                for sample in simultaneous
                if sample.visibility == VisibilityStatus.OBSERVED
            }
            if visible_cameras:
                for camera_id in sorted(set(active) - visible_cameras):
                    close(camera_id)
            for sample in simultaneous:
                if sample.visibility == VisibilityStatus.GAP:
                    close(sample.camera_id)
                    continue
                group = active.get(sample.camera_id)
                if group and (
                    not _same_segment(group[-1], sample)
                    or (
                        policy.max_visible_sample_gap_s is not None
                        and sample.timestamp - group[-1].timestamp > policy.max_visible_sample_gap_s
                    )
                ):
                    close(sample.camera_id)
                active.setdefault(sample.camera_id, []).append(sample)
        for camera_id in sorted(active):
            close(camera_id)
    ordered = tuple(
        sorted(
            observations,
            key=lambda item: (
                item.observation.start_time,
                item.observation.target_id,
                item.observation.camera_id,
                item.observation.observation_id,
            ),
        )
    )
    return ObservationAggregation(samples=canonical, observations=ordered)
