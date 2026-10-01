from __future__ import annotations

import pytest

from amidst.domain.camera import Camera, ProjectionReason
from amidst.simulation.virtual_camera import project_world


def camera() -> Camera:
    return Camera(
        camera_id="fixture",
        width=100,
        height=100,
        fx=50,
        fy=50,
        cx=50,
        cy=50,
        camera_to_world=((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 10), (0, 0, 0, 1)),
        clip_start=1,
        clip_end=20,
    )


@pytest.mark.parametrize(
    "position,pixel",
    [
        ((0, 0, 0), (50, 50)),
        ((2, 0, 0), (60, 50)),
        ((0, 2, 0), (50, 40)),
        ((-10, 0, 0), (0, 50)),
    ],
)
def test_top_left_pinhole_projection(position: tuple, pixel: tuple) -> None:
    result = project_world(camera(), position)
    assert result.point_2d == pytest.approx(pixel)
    assert result.in_frustum
    assert result.axial_depth == 10


@pytest.mark.parametrize(
    "position,reason",
    [
        ((0, 0, 10), ProjectionReason.BEHIND_CAMERA),
        ((0, 0, 11), ProjectionReason.BEHIND_CAMERA),
        ((0, 0, 9.5), ProjectionReason.NEAR_CLIPPED),
        ((0, 0, -11), ProjectionReason.FAR_CLIPPED),
        ((10, 0, 0), ProjectionReason.OUTSIDE_FOV),
        ((0, -10, 0), ProjectionReason.OUTSIDE_FOV),
    ],
)
def test_clipping_and_half_open_fov(position: tuple, reason: ProjectionReason) -> None:
    result = project_world(camera(), position)
    assert not result.in_frustum
    assert result.reason == reason


def test_axial_clip_is_not_radial_distance() -> None:
    result = project_world(camera(), (19, 0, -10))
    assert result.in_frustum
    assert result.axial_depth == 20


def test_tiny_positive_depth_is_clipped_before_division() -> None:
    origin_camera = camera().model_copy(
        update={"camera_to_world": ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))}
    )
    result = project_world(origin_camera, (1, 0, -1e-320))
    assert result.reason == ProjectionReason.NEAR_CLIPPED
    assert result.point_2d is None


def test_invalid_pose_and_nonfinite_point_fail_closed() -> None:
    reflected = camera().model_copy(
        update={"camera_to_world": ((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 10), (0, 0, 0, 1))}
    )
    with pytest.raises(ValueError, match="rigid"):
        project_world(reflected, (0, 0, 0))
    with pytest.raises(ValueError, match="finite"):
        project_world(camera(), (float("nan"), 0, 0))
