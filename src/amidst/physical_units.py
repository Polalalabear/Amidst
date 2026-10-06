"""Explicit source-bound BU to SI adapters, outside inference/domain contracts.

Native Blender exports remain immutable. Callers must identify a native input and
bind it to the approved architectural scale before supplying metric coordinates
to the existing core. These adapters do not approve geometry, policy or floors.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from amidst.architectural_scale import ArchitecturalScale
from amidst.domain.camera import Camera
from amidst.domain.common import Vec3
from amidst.domain.geometry import Plane
from amidst.domain.navigation import NavigationGraphConfig
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.physical_authority import PhysicalPolicy


def _bound_scale(scale: ArchitecturalScale, source_asset_sha256: str) -> ArchitecturalScale:
    """Revalidate even unchecked model copies; authority is never inferred from size."""
    approved = ArchitecturalScale.model_validate(scale.model_dump(mode="python"))
    if approved.authority != "APPROVED":
        raise ValueError("native physical conversion requires APPROVED architectural scale")
    approved.require_source_sha256(source_asset_sha256)
    return approved


def _metric_point(point: Vec3, scale: ArchitecturalScale) -> Vec3:
    return (
        scale.to_metres(float(point[0])),
        scale.to_metres(float(point[1])),
        scale.to_metres(float(point[2])),
    )


def native_camera_to_metres(
    camera: Camera, scale: ArchitecturalScale, *, source_asset_sha256: str,
) -> Camera:
    """Convert native translation/clips; rigid rotation, identity and pixels stay fixed.

    ``Camera.meters_per_unit`` remains one because the returned coordinates really
    are metres. This does not change or relabel the original calibration export.
    """
    scale = _bound_scale(scale, source_asset_sha256)
    camera = Camera.model_validate(camera.model_dump(mode="python"))
    payload = camera.model_dump(mode="python")
    payload["camera_to_world"] = tuple(
        tuple(
            scale.to_metres(float(value)) if column == 3 and row < 3 else value
            for column, value in enumerate(values)
        )
        for row, values in enumerate(camera.camera_to_world)
    )
    payload["clip_start"] = scale.to_metres(float(camera.clip_start))
    payload["clip_end"] = scale.to_metres(float(camera.clip_end))
    return Camera.model_validate(payload)


def native_plane_to_metres(
    plane: Plane, scale: ArchitecturalScale, *, source_asset_sha256: str,
) -> Plane:
    """Convert a source-bound native plane point; its unit normal is dimensionless."""
    scale = _bound_scale(scale, source_asset_sha256)
    plane = Plane.model_validate(plane.model_dump(mode="python"))
    payload = plane.model_dump(mode="python")
    payload["point"] = _metric_point(plane.point, scale)
    return Plane.model_validate(payload)


def native_projected_point_to_metres(
    point: ProjectedPoint, scale: ArchitecturalScale, *, source_asset_sha256: str,
) -> ProjectedPoint:
    """Convert projected coordinates only, preserving evidence identity and provenance."""
    scale = _bound_scale(scale, source_asset_sha256)
    point = ProjectedPoint.model_validate(point.model_dump(mode="python"))
    payload = point.model_dump(mode="python")
    payload["world_position"] = _metric_point(point.world_position, scale)
    return ProjectedPoint.model_validate(payload)


def native_observation_to_metres(
    observation: Observation, scale: ArchitecturalScale, *, source_asset_sha256: str,
) -> Observation:
    """Normalize legacy projected paths; 2D frames, times and direction vectors stay fixed."""
    scale = _bound_scale(scale, source_asset_sha256)
    observation = Observation.model_validate(observation.model_dump(mode="python"))
    payload = observation.model_dump(mode="python")
    payload["projected_path"] = tuple(
        native_projected_point_to_metres(
            point, scale, source_asset_sha256=source_asset_sha256,
        ).model_dump(mode="python")
        for point in observation.projected_path
    )
    return Observation.model_validate(payload)


def native_navigation_to_metres(
    navigation: NavigationGraphConfig, scale: ArchitecturalScale,
) -> NavigationGraphConfig:
    """Normalize an explicitly source-bound native graph without changing connectivity."""
    navigation = NavigationGraphConfig.model_validate(navigation.model_dump(mode="python"))
    if navigation.source_asset_sha256 is None:
        raise ValueError("native navigation conversion requires an explicit source asset SHA-256")
    scale = _bound_scale(scale, navigation.source_asset_sha256)
    payload = navigation.model_dump(mode="python")
    payload["nodes"] = tuple(
        {**node.model_dump(mode="python"), "position": _metric_point(node.position, scale)}
        for node in navigation.nodes
    )
    payload["edges"] = tuple(
        {
            **edge.model_dump(mode="python"),
            "polyline": tuple(_metric_point(point, scale) for point in edge.polyline),
        }
        for edge in navigation.edges
    )
    payload["node_match_tolerance_m"] = scale.to_metres(
        float(navigation.node_match_tolerance_m)
    )
    return NavigationGraphConfig.model_validate(payload)


def native_movement_to_metres(
    movement: MovementConstraints, scale: ArchitecturalScale, *, source_asset_sha256: str,
) -> MovementConstraints:
    """Convert an explicitly native BU/s constraint; never rescale an existing SI policy."""
    scale = _bound_scale(scale, source_asset_sha256)
    movement = MovementConstraints.model_validate(movement.model_dump(mode="python"))
    return MovementConstraints(
        max_speed_m_s=scale.speed_to_metres_per_second(float(movement.max_speed_m_s))
    )


def native_search_policy_to_metres(
    policy: GraphSearchPolicy, scale: ArchitecturalScale, *, source_asset_sha256: str,
) -> GraphSearchPolicy:
    """Convert only a native distance bound; path counts, time and ratios are unchanged."""
    scale = _bound_scale(scale, source_asset_sha256)
    policy = GraphSearchPolicy.model_validate(policy.model_dump(mode="python"))
    payload = policy.model_dump(mode="python")
    payload["max_path_length_m"] = scale.to_metres(float(policy.max_path_length_m))
    return GraphSearchPolicy.model_validate(payload)


def physical_policy_in_blender_units(
    policy: PhysicalPolicy, scale: ArchitecturalScale, *, source_asset_sha256: str,
) -> dict[str, object]:
    """Report SI policy lengths in native units without filling or approving pending fields."""
    scale = _bound_scale(scale, source_asset_sha256)
    policy = PhysicalPolicy.model_validate(policy.model_dump(mode="python"))
    names = (
        "body_radius_m", "body_height_m", "body_clearance_m",
        "portal_horizontal_clearance_m", "portal_vertical_clearance_m",
        "collision_tolerance_m",
    )
    native = {}
    for name in names:
        value = getattr(policy, name)
        native[name.removesuffix("_m") + "_bu"] = (
            None if value is None else scale.to_blender_units(float(value))
        )
    return {
        "source_asset_sha256": source_asset_sha256,
        "scale_authority": str(scale.authority),
        "scale_approval_id": scale.approval_id,
        "metres_per_blender_unit": scale.metres_per_blender_unit,
        "policy_metres": policy.model_dump(mode="json"),
        "lengths_blender_units": native,
        "physical_authority_upgraded": False,
    }


def _scalar(value: float | None, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (
        not math.isfinite(value) or value < 0
    ):
        raise ValueError(f"native {label} must be a finite nonnegative scalar or unavailable")
    return float(value)


def native_quantity_report(
    scale: ArchitecturalScale, *, source_asset_sha256: str,
    lengths_bu: Mapping[str, float | None] | None = None,
    speeds_bu_per_s: Mapping[str, float | None] | None = None,
) -> dict[str, object]:
    """Add meter reports for already computed lengths/errors/speeds; preserve native values.

    No trajectory, truth, Coverage decision, epsilon or dimensionless metric is
    accepted. Missing evaluation results stay unavailable, rather than becoming zero.
    """
    scale = _bound_scale(scale, source_asset_sha256)
    lengths: dict[str, dict[str, float | None]] = {}
    speeds: dict[str, dict[str, float | None]] = {}
    for identity, value in (lengths_bu or {}).items():
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("native length report requires nonempty quantity identities")
        native = _scalar(value, f"length {identity}")
        lengths[identity] = {
            "bu": native, "m": None if native is None else scale.to_metres(native),
        }
    for identity, value in (speeds_bu_per_s or {}).items():
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("native speed report requires nonempty quantity identities")
        native = _scalar(value, f"speed {identity}")
        speeds[identity] = {
            "bu_per_s": native,
            "m_per_s": None if native is None else scale.speed_to_metres_per_second(native),
        }
    return {
        "source_asset_sha256": source_asset_sha256,
        "scale_authority": str(scale.authority),
        "scale_approval_id": scale.approval_id,
        "metres_per_blender_unit": scale.metres_per_blender_unit,
        "lengths": lengths,
        "speeds": speeds,
        "coverage_recomputed": False,
        "inference_outputs_modified": False,
    }
