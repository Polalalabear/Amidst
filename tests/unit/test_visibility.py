from __future__ import annotations

import pytest
from pydantic import ValidationError

from amidst.domain.camera import Camera
from amidst.domain.evidence import GapReason, ObservationFrame, VisibilityStatus
from amidst.simulation.raycast_types import RaycastResult
from amidst.simulation.visibility import observe_point


def camera() -> Camera:
    return Camera(
        camera_id="CAM_FIXTURE",
        width=100,
        height=100,
        fx=50,
        fy=50,
        cx=50,
        cy=50,
        camera_to_world=((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 10), (0, 0, 0, 1)),
    )


def test_visible_evidence_has_pixels_but_no_ground_truth() -> None:
    result = observe_point(
        camera(),
        (0, 0, 0),
        timestamp=0,
        target_id="sim",
        frame_id=0,
        raycaster=lambda origin, target: RaycastResult(False, "CLEAR"),
    )
    assert result.status == VisibilityStatus.OBSERVED
    assert result.point_2d == (50, 50)
    assert "position" not in result.model_dump()
    with pytest.raises(ValidationError):
        ObservationFrame.model_validate({**result.model_dump(), "ground_truth_3d": [0, 0, 0]})


@pytest.mark.parametrize(
    "query,reason",
    [
        (RaycastResult(True, "OCCLUDED", "wall"), GapReason.OCCLUDED),
        (RaycastResult(True, "RAYCAST_LIMIT"), GapReason.RAYCAST_LIMIT),
        (RaycastResult(False, "GEOMETRY_UNCERTAIN"), GapReason.GEOMETRY_UNCERTAIN),
    ],
)
def test_gap_contains_no_projectable_pixels(query: RaycastResult, reason: GapReason) -> None:
    result = observe_point(
        camera(),
        (0, 0, 0),
        timestamp=1,
        target_id="sim",
        frame_id=1,
        raycaster=lambda origin, target: query,
    )
    assert result.status == VisibilityStatus.GAP
    assert result.point_2d is None and result.provenance is None
    assert result.gap_reason == reason


def test_outside_fov_does_not_query_geometry() -> None:
    def forbidden(origin: tuple, target: tuple) -> RaycastResult:
        raise AssertionError("FOV rejection must precede raycast")

    result = observe_point(
        camera(), (100, 0, 0), timestamp=0, target_id="sim", frame_id=0, raycaster=forbidden
    )
    assert result.gap_reason == GapReason.OUTSIDE_FOV
