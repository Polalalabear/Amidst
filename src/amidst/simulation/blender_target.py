"""Temporary foot-anchored target proxies; never save or render a Blender asset.

This adapter only imports Blender at execution time and needs no third-party
packages in Blender's bundled Python. A frame is ``1 + timestamp * frame_rate``.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from amidst.domain.common import Vec3
    from amidst.domain.ground_truth import GroundTruthTrajectory

MAX_BLENDER_FRAME = 1_048_574


def _frame_at(timestamp: float, frame_rate_hz: float) -> float:
    if not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError("timestamps must be finite and non-negative")
    frame = 1.0 + timestamp * frame_rate_hz
    if not math.isfinite(frame) or frame > MAX_BLENDER_FRAME:
        raise ValueError("trajectory exceeds Blender's supported frame domain")
    return frame


def _linear_interpolation(action: Any) -> None:
    if hasattr(action, "fcurves"):
        curves = action.fcurves
    else:
        curves = [
            curve
            for layer in action.layers
            for strip in layer.strips
            for channelbag in strip.channelbags
            for curve in channelbag.fcurves
        ]
    for curve in curves:
        for keyframe in curve.keyframe_points:
            keyframe.interpolation = "LINEAR"


@contextmanager
def animated_target_proxy(
    scene: Any,
    trajectory: GroundTruthTrajectory,
    *,
    frame_rate_hz: float = 30.0,
    radius_m: float = 0.2,
    height_m: float = 1.7,
) -> Iterator[Any]:
    """Create a disposable box whose origin is its ground-contact point.

    All owned object/mesh/action data is removed even after an exception. Original
    objects and the scene's timing/render settings remain untouched.
    """
    import bpy  # type: ignore[import-not-found]

    if any(not math.isfinite(value) or value <= 0 for value in (frame_rate_hz, radius_m, height_m)):
        raise ValueError("frame rate, proxy radius and height must be finite and positive")
    mesh = bpy.data.meshes.new("AMIDST_SYNTHETIC_TARGET_MESH")
    proxy = bpy.data.objects.new("AMIDST_SYNTHETIC_TARGET_PROXY", mesh)
    action = None
    try:
        vertices = [
            (x, y, z)
            for z in (0.0, height_m)
            for x, y in (
                (-radius_m, -radius_m),
                (radius_m, -radius_m),
                (radius_m, radius_m),
                (-radius_m, radius_m),
            )
        ]
        faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        scene.collection.objects.link(proxy)
        for sample in trajectory.samples:
            proxy.location = sample.position
            frame = _frame_at(sample.timestamp, frame_rate_hz)
            proxy.keyframe_insert(data_path="location", frame=frame)
        action = proxy.animation_data.action
        _linear_interpolation(action)
        yield proxy
    finally:
        # keyframe insertion may fail after allocating the Action.
        if action is None and proxy.animation_data is not None:
            action = proxy.animation_data.action
        bpy.data.objects.remove(proxy, do_unlink=True)
        bpy.data.meshes.remove(mesh)
        if action is not None and action.users == 0:
            bpy.data.actions.remove(action)


def evaluated_proxy_positions(
    scene: Any,
    proxy: Any,
    timestamps: Sequence[float],
    *,
    frame_rate_hz: float = 30.0,
) -> tuple[Vec3, ...]:
    """Evaluate world-space contact positions, then restore the current frame."""
    import bpy

    if not math.isfinite(frame_rate_hz) or frame_rate_hz <= 0:
        raise ValueError("frame_rate_hz must be finite and positive")
    frame_before, subframe_before = scene.frame_current, scene.frame_subframe
    positions = []
    try:
        for timestamp in timestamps:
            frame = _frame_at(timestamp, frame_rate_hz)
            integral_frame = math.floor(frame)
            scene.frame_set(integral_frame, subframe=frame - integral_frame)
            evaluated = proxy.evaluated_get(bpy.context.evaluated_depsgraph_get())
            translation = evaluated.matrix_world.translation
            positions.append((float(translation.x), float(translation.y), float(translation.z)))
        return tuple(positions)
    finally:
        scene.frame_set(frame_before, subframe=subframe_before)
