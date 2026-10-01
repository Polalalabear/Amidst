"""Project and ray-test synthetic targets, publishing only sanitized 2D evidence."""

from __future__ import annotations

from typing import TypedDict

from amidst.domain.camera import Camera
from amidst.domain.common import Provenance, Vec3
from amidst.domain.evidence import GapReason, ObservationFrame, VisibilityStatus
from amidst.simulation.raycast_types import Raycaster
from amidst.simulation.virtual_camera import project_world


class _FrameBase(TypedDict):
    frame_id: int
    timestamp: float
    target_id: str
    camera_id: str


def observe_point(
    camera: Camera,
    position: Vec3,
    *,
    timestamp: float,
    target_id: str,
    frame_id: int,
    raycaster: Raycaster,
) -> ObservationFrame:
    """Use hidden positions only inside simulation; no 3D truth enters the result."""
    projection = project_world(camera, position)
    base: _FrameBase = dict(
        frame_id=frame_id, timestamp=timestamp, target_id=target_id, camera_id=camera.camera_id
    )
    if not projection.in_frustum:
        return ObservationFrame(
            **base,
            status=VisibilityStatus.GAP,
            point_2d=None,
            provenance=None,
            gap_reason=GapReason(projection.reason.value),
        )
    matrix = camera.camera_to_world
    origin = (matrix[0][3], matrix[1][3], matrix[2][3])
    result = raycaster(origin, position)
    if result.occluded or result.reason != "CLEAR":
        reason = "GEOMETRY_UNCERTAIN" if result.reason == "CLEAR" else result.reason
        return ObservationFrame(
            **base,
            status=VisibilityStatus.GAP,
            point_2d=None,
            provenance=None,
            gap_reason=GapReason(reason),
            occluder_id=result.occluder_id,
        )
    return ObservationFrame(
        **base,
        status=VisibilityStatus.OBSERVED,
        point_2d=projection.point_2d,
        provenance=Provenance.OBSERVED,
    )
