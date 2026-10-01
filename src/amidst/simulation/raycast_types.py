"""Blender-compatible standard-library-only physical ray query interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from amidst.domain.common import Vec3


@dataclass(frozen=True)
class RaycastResult:
    occluded: bool
    reason: Literal["CLEAR", "OCCLUDED", "GEOMETRY_UNCERTAIN", "RAYCAST_LIMIT"]
    occluder_id: str | None = None


class Raycaster(Protocol):
    def __call__(self, origin: Vec3, target: Vec3) -> RaycastResult: ...
