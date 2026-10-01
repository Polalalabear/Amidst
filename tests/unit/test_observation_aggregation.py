"""Raw producer contract, deterministic segmentation and hidden-data rejection."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.domain.common import Provenance, Vec3
from amidst.domain.evidence import GapReason, VisibilityStatus
from amidst.domain.interfaces import ObservationProvider
from amidst.domain.observation import ProjectedPoint
from amidst.domain.stream import (
    AggregationPolicy,
    ObservationAggregation,
    OcclusionState,
    RawFrameProvider,
    RawProjectedFrameSample,
)
from amidst.observation import (
    AggregatingObservationProvider,
    AggregationInputError,
    InMemoryRawFrameProvider,
    aggregate_frames,
)


def _sample(
    timestamp: float,
    *,
    camera_id: str = "CAM_A",
    target_id: str = "target",
    source_id: str = "source",
    spatial_context_id: str = "context",
    source_asset_sha256: str | None = None,
    frame_id: int | None = None,
    visible: bool = True,
    projected: bool = True,
    pixels: bool = True,
    floor_id: str = "1F",
    position: Vec3 = (0, 0, 0),
    data_kind: str = "SYNTHETIC",
) -> RawProjectedFrameSample:
    identity = f"{source_id}:{target_id}:{camera_id}:{timestamp}:{floor_id}"
    return RawProjectedFrameSample.model_validate(
        {
            "sample_id": identity,
            "source_id": source_id,
            "spatial_context_id": spatial_context_id,
            "source_asset_sha256": source_asset_sha256,
            "target_id": target_id,
            "camera_id": camera_id,
            "timestamp": timestamp,
            "frame_id": int(timestamp * 10) if frame_id is None else frame_id,
            "uv": (0.25, 0.75) if visible and pixels else None,
            "visibility": VisibilityStatus.OBSERVED if visible else VisibilityStatus.GAP,
            "occlusion_state": OcclusionState.CLEAR if visible else OcclusionState.OCCLUDED,
            "provenance": (Provenance.OBSERVED if pixels else Provenance.PROJECTED)
            if visible
            else None,
            "projected_point": ProjectedPoint(
                point_id=f"{identity}:point",
                camera_id=camera_id,
                plane_id=f"plane:{floor_id}",
                timestamp=timestamp,
                world_position=position,
                floor_id=floor_id,
            ).model_dump()
            if visible and projected
            else None,
            "gap_reason": None if visible else GapReason.OCCLUDED,
            "occluder_id": None if visible else "wall_01",
            "data_kind": data_kind,
        }
    )


def test_visible_frames_aggregate_with_source_binding_and_exact_evidence() -> None:
    samples = (_sample(0, position=(0, 0, 0)), _sample(1, position=(1, 0, 0)))
    result = aggregate_frames(samples)
    assert len(result.observations) == 1
    bound = result.observations[0]
    observation = bound.observation
    assert bound.binding.source_id == "source"
    assert bound.binding.spatial_context_id == "context"
    assert bound.sample_ids == tuple(sample.sample_id for sample in samples)
    assert observation.provenance == Provenance.PROJECTED
    assert observation.start_time == 0 and observation.end_time == 1
    assert tuple(point.world_position for point in observation.projected_path) == (
        (0, 0, 0),
        (1, 0, 0),
    )
    assert tuple(frame.point_2d for frame in observation.frames) == ((0.25, 0.75),) * 2
    assert all(
        point.observation_id == observation.observation_id for point in observation.projected_path
    )
    assert observation.observation_quality is None
    assert all(sample.confidence is None for sample in result.samples)


def test_explicit_gaps_and_single_frame_recovery_are_never_stitched() -> None:
    samples = tuple(_sample(time, visible=time in {0, 1, 3, 5}) for time in range(6))
    observations = aggregate_frames(samples).observations
    assert tuple(
        (item.observation.start_time, item.observation.end_time) for item in observations
    ) == (
        (0, 1),
        (3, 3),
        (5, 5),
    )
    assert all(
        frame.status == VisibilityStatus.OBSERVED
        for item in observations
        for frame in item.observation.frames
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"camera_id": "CAM_B"},
        {"source_id": "other"},
        {"spatial_context_id": "other"},
        {"source_asset_sha256": "f" * 64},
        {"floor_id": "2F"},
        {"pixels": False},
        {"projected": False},
        {"data_kind": "REAL_CV"},
    ],
)
def test_identity_projection_mode_and_floor_changes_split_segments(changes: dict[str, Any]) -> None:
    result = aggregate_frames((_sample(0), _sample(1, **changes)))
    assert len(result.observations) == 2


def test_sorting_is_deterministic_for_out_of_order_sources_and_targets() -> None:
    samples = (
        _sample(0),
        _sample(1),
        _sample(2, visible=False),
        _sample(3),
        _sample(0, target_id="other"),
        _sample(1, target_id="other"),
    )
    forward = aggregate_frames(samples)
    assert aggregate_frames(tuple(reversed(samples))).model_dump_json() == forward.model_dump_json()
    assert len(forward.observations) == 3
    changed = samples[0].model_copy(update={"confidence": 0.5})
    assert aggregate_frames((changed,)).observations[0].observation.observation_id != (
        aggregate_frames((samples[0],)).observations[0].observation.observation_id
    )


def test_projected_only_visible_samples_do_not_invent_camera_pixels() -> None:
    result = aggregate_frames((_sample(0, pixels=False), _sample(1, pixels=False)))
    observation = result.observations[0].observation
    assert observation.frames == ()
    assert observation.provenance == Provenance.PROJECTED
    assert len(observation.projected_path) == 2
    assert all(sample.uv is None for sample in result.samples)


def test_future_unprojected_real_cv_samples_preserve_kind_without_implementation() -> None:
    result = aggregate_frames((_sample(0, projected=False, data_kind="REAL_CV"),))
    bound = result.observations[0]
    assert bound.binding.data_kind == "REAL_CV"
    assert bound.observation.provenance == Provenance.OBSERVED
    assert bound.observation.projected_path == ()
    assert bound.observation.frames[0].data_kind == "REAL_CV"


def test_gap_in_another_camera_does_not_remove_visible_evidence() -> None:
    samples = (_sample(0), _sample(1, camera_id="CAM_B", visible=False), _sample(2))
    result = aggregate_frames(samples)
    assert len(result.observations) == 1
    assert result.observations[0].observation.end_time == 2


def test_camera_handoff_and_return_do_not_merge_disjoint_camera_segments() -> None:
    result = aggregate_frames((_sample(0), _sample(1, camera_id="CAM_B"), _sample(2)))
    assert tuple(item.observation.camera_id for item in result.observations) == (
        "CAM_A",
        "CAM_B",
        "CAM_A",
    )


def test_simultaneous_different_camera_visibility_is_preserved_as_ambiguity() -> None:
    result = aggregate_frames((_sample(0), _sample(0, camera_id="CAM_B")))
    assert len(result.observations) == 2
    assert all(item.observation.start_time == 0 for item in result.observations)


@pytest.mark.parametrize(
    "duplicate",
    [
        _sample(0),
        _sample(0).model_copy(update={"sample_id": "different"}),
        _sample(1, frame_id=0),
    ],
)
def test_duplicate_sample_timestamp_or_source_frame_identity_is_rejected(
    duplicate: RawProjectedFrameSample,
) -> None:
    with pytest.raises(AggregationInputError, match="duplicate"):
        aggregate_frames((_sample(0), duplicate))


def test_equal_frame_ids_in_different_cameras_or_targets_are_unambiguous() -> None:
    samples = (_sample(0), _sample(0, camera_id="CAM_B"), _sample(0, target_id="other"))
    assert len(aggregate_frames(samples).observations) == 3


def test_optional_sampling_gap_policy_is_explicit_and_preserves_short_recovery() -> None:
    samples = (_sample(0), _sample(5))
    assert len(aggregate_frames(samples).observations) == 1
    assert (
        len(aggregate_frames(samples, AggregationPolicy(max_visible_sample_gap_s=2)).observations)
        == 2
    )
    invalid = AggregationPolicy().model_copy(update={"max_visible_sample_gap_s": 0})
    with pytest.raises(AggregationInputError):
        aggregate_frames(samples, invalid)


@pytest.mark.parametrize(
    "changes",
    [
        {"uv": None},
        {"occlusion_state": OcclusionState.OCCLUDED},
        {"provenance": Provenance.GROUND_TRUTH},
        {"confidence": -1},
        {"confidence": 2},
        {"timestamp": float("nan")},
        {"frame_id": True},
        {"ground_truth_3d": [999, 999, 999]},
    ],
)
def test_raw_evidence_contract_rejects_invalid_or_hidden_fields(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RawProjectedFrameSample.model_validate(_sample(0).model_dump() | changes)


def test_gap_metadata_and_projection_identity_are_validated() -> None:
    gap = _sample(1, visible=False)
    for change in (
        {"uv": (1, 1)},
        {"projected_point": _sample(1).projected_point},
        {"occlusion_state": OcclusionState.UNKNOWN},
        {"gap_reason": None},
    ):
        with pytest.raises(ValidationError):
            RawProjectedFrameSample.model_validate(gap.model_dump() | change)
    point = _sample(0).projected_point
    assert point is not None
    with pytest.raises(ValidationError, match="camera/time"):
        RawProjectedFrameSample.model_validate(
            _sample(0).model_dump()
            | {
                "projected_point": point.model_copy(update={"camera_id": "wrong"}).model_dump(),
            }
        )


def test_construct_and_copy_bypasses_including_nested_truth_are_rejected() -> None:
    sample = _sample(0)
    assert sample.projected_point is not None
    forged_point = sample.projected_point.model_copy(update={"provenance": Provenance.GROUND_TRUTH})
    bad = sample.model_copy(update={"projected_point": forged_point})
    with pytest.raises(AggregationInputError):
        aggregate_frames((bad,))
    constructed = RawProjectedFrameSample.model_construct(**(sample.__dict__ | {"timestamp": -1}))
    with pytest.raises(AggregationInputError):
        aggregate_frames((constructed,))
    injected = sample.model_copy(update={"ground_truth_3d": object()})
    with pytest.raises(AggregationInputError, match="outside its declared"):
        aggregate_frames((injected,))


def test_aggregation_cannot_forge_time_geometry_source_or_drop_visible_samples() -> None:
    result = aggregate_frames((_sample(0), _sample(1)))
    payload = result.model_dump()
    payload["observations"][0]["observation"]["projected_path"][0]["world_position"] = [999, 0, 0]
    with pytest.raises(ValidationError, match="raw source evidence"):
        ObservationAggregation.model_validate(payload)
    payload = result.model_dump()
    payload["observations"] = []
    with pytest.raises(ValidationError, match="every visible sample"):
        ObservationAggregation.model_validate(payload)
    payload = result.model_dump()
    payload["observations"][0]["binding"]["source_id"] = "wrong"
    with pytest.raises(ValidationError, match="source/context"):
        ObservationAggregation.model_validate(payload)


def test_raw_provider_adapter_satisfies_existing_observation_provider_contract() -> None:
    samples = (_sample(0), _sample(1), _sample(2, visible=False), _sample(3, camera_id="CAM_B"))
    raw = InMemoryRawFrameProvider(samples)
    assert isinstance(raw, RawFrameProvider)
    provider: ObservationProvider = AggregatingObservationProvider(raw)
    observations = provider.get_observations("CAM_A", (0, 3))
    assert len(observations) == 1 and len(observations[0].frames) == 2
    assert provider.get_observations("missing", (0, 3)) == ()
    assert len(raw.get_frame_samples("CAM_A", (0, 1))) == 2
    assert len(raw.get_frame_samples("CAM_A", (1, 1))) == 1


@pytest.mark.parametrize("query", [(-1, 1), (2, 1), (float("nan"), 2), (0, float("inf"))])
def test_provider_rejects_invalid_time_ranges(query: tuple[float, float]) -> None:
    with pytest.raises(AggregationInputError):
        AggregatingObservationProvider(InMemoryRawFrameProvider((_sample(0),))).aggregate(query)


def test_empty_and_gap_only_streams_create_no_fake_observation() -> None:
    assert aggregate_frames(()).observations == ()
    assert aggregate_frames((_sample(0, visible=False),)).observations == ()


def test_misbehaving_provider_cannot_return_frames_outside_requested_window() -> None:
    class OutOfRangeProvider:
        def get_frame_samples(
            self,
            camera_id: str | None,
            time_range: tuple[float, float],
        ) -> tuple[RawProjectedFrameSample, ...]:
            return (_sample(5),)

    with pytest.raises(AggregationInputError, match="outside the requested range"):
        AggregatingObservationProvider(OutOfRangeProvider()).aggregate((0, 1))


def test_aggregation_import_boundary_has_no_hidden_trajectory_or_consumer_access() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "amidst"
    paths = [root / "domain" / "stream.py", *(root / "observation").rglob("*.py")]
    for path in paths:
        modules = []
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                modules.append(node.module or "")
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
        assert not any(
            word in module
            for word in ("ground_truth", ".simulation", ".evaluation", ".visualization")
            for module in modules
        ), path
