"""M6 explicit-plane inverse projection and fail-closed boundary tests."""

from __future__ import annotations

import math
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import GapReason, ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import (
    InverseProjectionError,
    InverseProjectionFailure,
    InverseProjectionService,
)
from amidst.simulation.virtual_camera import project_world


def _camera(**updates: Any) -> Camera:
    payload = dict(
        camera_id="fixture",
        width=100,
        height=100,
        fx=50,
        fy=50,
        cx=50,
        cy=50,
        camera_to_world=(
            (1, 0, 0, 0),
            (0, 1, 0, 0),
            (0, 0, 1, 10),
            (0, 0, 0, 1),
        ),
        clip_start=1,
        clip_end=20,
    )
    payload.update(updates)
    return Camera.model_validate(payload)


def _plane(**updates: Any) -> Plane:
    payload = dict(
        plane_id="floor_1",
        point=(0, 0, 0),
        normal=(0, 0, 1),
        floor_id="1F",
        zone_id="synthetic_fixture",
    )
    payload.update(updates)
    return Plane.model_validate(payload)


def _frame(**updates: Any) -> ObservationFrame:
    payload = dict(
        frame_id=7,
        timestamp=1.5,
        target_id="target",
        camera_id="fixture",
        status=VisibilityStatus.OBSERVED,
        point_2d=(50, 50),
        provenance=Provenance.OBSERVED,
    )
    payload.update(updates)
    return ObservationFrame.model_validate(payload)


def test_plane_contract_roundtrips_and_rejects_unknown_fields() -> None:
    plane = _plane()
    assert Plane.model_validate_json(plane.model_dump_json()) == plane
    with pytest.raises(ValidationError):
        Plane.model_validate(plane.model_dump() | {"ground_truth_3d": (0, 0, 0)})


@pytest.mark.parametrize(
    ("pixel", "expected"),
    [
        ((50, 50), (0, 0, 0)),
        ((60, 50), (2, 0, 0)),
        ((50, 40), (0, 2, 0)),
        ((50, 60), (0, -2, 0)),
        ((0, 50), (-10, 0, 0)),
        ((75, 75), (5, -5, 0)),
    ],
)
def test_inverse_projection_matches_top_left_pinhole_geometry(
    pixel: tuple[float, float], expected: tuple[float, float, float]
) -> None:
    projected = InverseProjectionService(_camera(), _plane()).project_frame(
        _frame(point_2d=pixel)
    )
    assert projected.world_position == pytest.approx(expected)
    assert project_world(_camera(), projected.world_position).point_2d == pytest.approx(pixel)
    assert projected.camera_id == "fixture"
    assert projected.plane_id == "floor_1"
    assert projected.point_id.startswith("projected:")
    assert projected.timestamp == 1.5
    assert projected.floor_id == "1F"
    assert projected.zone_id == "synthetic_fixture"
    assert projected.provenance == Provenance.PROJECTED
    assert 0 < projected.projection_quality <= 1


def test_point_identity_is_deterministic_and_includes_timestamp() -> None:
    service = InverseProjectionService(_camera(), _plane())
    first = service.project_frame(_frame(timestamp=1.5))
    repeated = service.project_frame(_frame(timestamp=1.5))
    later = service.project_frame(_frame(timestamp=1.75))
    assert first.point_id == repeated.point_id
    assert first.point_id != later.point_id


def test_projection_quality_is_ray_plane_incidence() -> None:
    service = InverseProjectionService(_camera(), _plane())
    assert service.project_frame(_frame(point_2d=(50, 50))).projection_quality == 1
    assert service.project_frame(_frame(point_2d=(75, 75))).projection_quality == pytest.approx(
        math.sqrt(2 / 3)
    )


def test_asymmetric_intrinsics_and_explicit_piecewise_planes() -> None:
    camera = _camera(fx=40, fy=80, cx=30, cy=60)
    frame = _frame(point_2d=(50, 20))
    lower = InverseProjectionService(camera, _plane()).project_frame(frame)
    upper = InverseProjectionService(
        camera,
        _plane(plane_id="floor_2", point=(0, 0, 5), floor_id="2F"),
    ).project_frame(frame)
    assert lower.world_position == pytest.approx((5, 5, 0))
    assert upper.world_position == pytest.approx((2.5, 2.5, 5))
    assert upper.floor_id == "2F"
    assert lower.plane_id == "floor_1"
    assert upper.plane_id == "floor_2"
    assert lower.point_id != upper.point_id


def test_rotated_camera_uses_camera_to_world_rotation() -> None:
    camera = _camera(
        camera_to_world=(
            (0, 0, -1, 0),
            (-1, 0, 0, 0),
            (0, 1, 0, 2),
            (0, 0, 0, 1),
        )
    )
    plane = _plane(point=(10, 0, 0), normal=(1, 0, 0))
    service = InverseProjectionService(camera, plane)
    assert service.project_frame(_frame(point_2d=(50, 50))).world_position == pytest.approx(
        (10, 0, 2)
    )
    assert service.project_frame(_frame(point_2d=(60, 50))).world_position == pytest.approx(
        (10, -2, 2)
    )
    assert service.project_frame(_frame(point_2d=(50, 40))).world_position == pytest.approx(
        (10, 0, 4)
    )


def test_oblique_plane_is_orientation_invariant() -> None:
    component = math.sqrt(0.5)
    positive = _plane(normal=(component, 0, component))
    negative = _plane(normal=(-component, 0, -component))
    frame = _frame(point_2d=(60, 50))
    first = InverseProjectionService(_camera(), positive).project_frame(frame)
    second = InverseProjectionService(_camera(), negative).project_frame(frame)
    assert first.world_position == pytest.approx((2.5, 0, -2.5))
    assert second.world_position == pytest.approx(first.world_position)


@pytest.mark.parametrize(
    ("plane_z", "expected_failure"),
    [
        (9.000001, InverseProjectionFailure.NEAR_CLIPPED),
        (-10.000001, InverseProjectionFailure.FAR_CLIPPED),
        (10, InverseProjectionFailure.INTERSECTION_BEHIND_CAMERA),
        (11, InverseProjectionFailure.INTERSECTION_BEHIND_CAMERA),
    ],
)
def test_plane_intersection_clipping_and_direction_fail_closed(
    plane_z: float, expected_failure: InverseProjectionFailure
) -> None:
    service = InverseProjectionService(_camera(), _plane(point=(0, 0, plane_z)))
    with pytest.raises(InverseProjectionError) as captured:
        service.project_frame(_frame())
    assert captured.value.failure == expected_failure


@pytest.mark.parametrize("plane_z", [9, -10])
def test_clip_endpoints_are_inclusive(plane_z: float) -> None:
    projected = InverseProjectionService(
        _camera(), _plane(point=(0, 0, plane_z))
    ).project_frame(_frame())
    assert projected.world_position[2] == pytest.approx(plane_z)


def test_off_axis_clipping_uses_axial_not_euclidean_depth() -> None:
    projected = InverseProjectionService(
        _camera(), _plane(point=(0, 0, -10))
    ).project_frame(_frame(point_2d=(97.5, 50)))
    assert projected.world_position == pytest.approx((19, 0, -10))


def test_parallel_and_contained_rays_fail_closed() -> None:
    for point in ((1, 0, 0), (0, 0, 0)):
        service = InverseProjectionService(_camera(), _plane(point=point, normal=(1, 0, 0)))
        with pytest.raises(InverseProjectionError) as captured:
            service.project_frame(_frame())
        assert captured.value.failure == InverseProjectionFailure.RAY_PARALLEL_TO_PLANE
    projected = InverseProjectionService(
        _camera(), _plane(point=(1, 0, 0), normal=(1, 0, 0))
    ).project_frame(_frame(point_2d=(60, 50)))
    assert projected.world_position == pytest.approx((1, 0, 5))


@pytest.mark.parametrize("pixel", [(0, 0), (99.999, 99.999)])
def test_pixels_inside_half_open_bounds_are_accepted(pixel: tuple[float, float]) -> None:
    InverseProjectionService(_camera(), _plane()).project_frame(_frame(point_2d=pixel))


@pytest.mark.parametrize("pixel", [(-1e-9, 50), (100, 50), (50, -1e-9), (50, 100)])
def test_pixels_outside_half_open_bounds_are_rejected(pixel: tuple[float, float]) -> None:
    with pytest.raises(InverseProjectionError) as captured:
        InverseProjectionService(_camera(), _plane()).project_frame(_frame(point_2d=pixel))
    assert captured.value.failure == InverseProjectionFailure.PIXEL_OUTSIDE_IMAGE


def test_gap_and_camera_mismatch_fail_closed() -> None:
    service = InverseProjectionService(_camera(), _plane())
    gap = _frame(
        status=VisibilityStatus.GAP,
        point_2d=None,
        provenance=None,
        gap_reason=GapReason.OCCLUDED,
    )
    with pytest.raises(InverseProjectionError) as captured:
        service.project_frame(gap)
    assert captured.value.failure == InverseProjectionFailure.FRAME_NOT_OBSERVED
    with pytest.raises(InverseProjectionError) as captured:
        service.project_frame(_frame(camera_id="other"))
    assert captured.value.failure == InverseProjectionFailure.CAMERA_MISMATCH


@pytest.mark.parametrize(
    "updates",
    [
        {"normal": (0, 0, 0)},
        {"normal": (0, 0, 2)},
        {"normal": (float("nan"), 0, 1)},
        {"normal": (1e308, 0, 0)},
        {"floor_id": ""},
    ],
)
def test_plane_requires_a_floor_and_finite_unit_normal(updates: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _plane(**updates)


@pytest.mark.parametrize(
    "pose",
    [
        ((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 10), (0, 0, 0, 1)),
        ((2, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 10), (0, 0, 0, 1)),
        ((1, 1, 0, 0), (0, 1, 0, 0), (0, 0, 1, 10), (0, 0, 0, 1)),
        ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 10), (0, 0, 0, 2)),
    ],
)
def test_invalid_camera_pose_fails_when_service_is_configured(pose: tuple) -> None:
    camera = _camera().model_copy(update={"camera_to_world": pose})
    with pytest.raises(InverseProjectionError) as captured:
        InverseProjectionService(camera, _plane())
    assert captured.value.failure == InverseProjectionFailure.INVALID_CAMERA_POSE


def test_nonfinite_pose_bypassing_model_validation_still_fails_closed() -> None:
    pose = ((1, 0, 0, float("nan")), (0, 1, 0, 0), (0, 0, 1, 10), (0, 0, 0, 1))
    camera = _camera().model_copy(update={"camera_to_world": pose})
    with pytest.raises(InverseProjectionError) as captured:
        InverseProjectionService(camera, _plane())
    assert captured.value.failure == InverseProjectionFailure.INVALID_CAMERA_POSE


@pytest.mark.parametrize("normal", [(0, 0, 2), (1e308, 0, 0)])
def test_invalid_plane_bypassing_model_validation_still_fails_closed(
    normal: tuple[float, float, float]
) -> None:
    plane = _plane().model_copy(update={"normal": normal})
    with pytest.raises(InverseProjectionError) as captured:
        InverseProjectionService(_camera(), plane)
    assert captured.value.failure == InverseProjectionFailure.INVALID_PLANE


@pytest.mark.parametrize("construction", ["copy", "construct"])
@pytest.mark.parametrize("updates", [
    {"provenance": Provenance.GROUND_TRUTH},
    {"provenance": Provenance.INFERRED_GAP},
    {"timestamp": -1.0},
    {"point_2d": (float("nan"), 50.0)},
])
def test_frame_schema_bypass_is_rejected_before_projection(
    construction: str, updates: dict[str, Any],
) -> None:
    original = _frame()
    if construction == "copy":
        frame = original.model_copy(update=updates)
    else:
        frame = ObservationFrame.model_construct(**(original.model_dump() | updates))
    with pytest.raises(InverseProjectionError) as captured:
        InverseProjectionService(_camera(), _plane()).project_frame(frame)
    assert captured.value.failure == InverseProjectionFailure.INVALID_FRAME
