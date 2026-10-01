"""Sanitized synthetic evidence flows into M6 without exposing Ground Truth."""

import pytest

from amidst.domain.camera import Camera
from amidst.domain.evidence import VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import (
    InverseProjectionError,
    InverseProjectionFailure,
    InverseProjectionService,
)
from amidst.simulation.raycast_types import RaycastResult
from amidst.simulation.visibility import observe_point


def _camera() -> Camera:
    return Camera(
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


def _plane() -> Plane:
    return Plane(
        plane_id="synthetic_floor",
        point=(0, 0, 0),
        normal=(0, 0, 1),
        floor_id="SYNTHETIC_TEST_FIXTURE",
    )


def test_observed_2d_evidence_recovers_the_synthetic_fixture_point() -> None:
    camera = _camera()
    hidden_simulation_position = (2.0, -1.0, 0.0)
    frame = observe_point(
        camera,
        hidden_simulation_position,
        timestamp=2,
        target_id="target",
        frame_id=3,
        raycaster=lambda _origin, _target: RaycastResult(False, "CLEAR"),
    )
    assert frame.status == VisibilityStatus.OBSERVED
    assert "world_position" not in frame.model_dump()
    projected = InverseProjectionService(camera, _plane()).project_frame(frame)
    assert projected.world_position == pytest.approx(hidden_simulation_position)


def test_occluded_evidence_cannot_enter_inverse_projection() -> None:
    camera = _camera()
    frame = observe_point(
        camera,
        (0, 0, 0),
        timestamp=2,
        target_id="target",
        frame_id=3,
        raycaster=lambda _origin, _target: RaycastResult(True, "OCCLUDED", "wall"),
    )
    assert frame.status == VisibilityStatus.GAP
    with pytest.raises(InverseProjectionError) as captured:
        InverseProjectionService(camera, _plane()).project_frame(frame)
    assert captured.value.failure == InverseProjectionFailure.FRAME_NOT_OBSERVED
