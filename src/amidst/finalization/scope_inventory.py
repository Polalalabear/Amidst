"""Read-only candidate evidence for a possible future branching-domain review.

An approved solid component is not free-space or camera-landmark authority. This
audit records source bounds/faces and necessary new scope, without issuing any
certificate, inferring object semantics or changing the original review payload.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from itertools import pairwise, product
from pathlib import Path
from typing import Any

import numpy as np

from amidst.domain.camera import Camera
from amidst.domain.common import Vec3
from amidst.local_semantic_review import ReviewedRestrictedLocalPhysicalProvider
from amidst.obstacle_volume_authority import content_sha256, validate_source_evidence
from amidst.simulation.virtual_camera import project_world
from amidst.walkable_clearance import WalkableClearanceDomain


def frustum_separating_plane(
    camera: Camera, low: Vec3, high: Vec3,
) -> dict[str, object] | None:
    """Prove a whole axis-aligned marker box is outside a source pinhole frustum.

    Frustum conditions are linear halfspaces in camera coordinates. If all eight
    box corners are strictly outside one same halfspace, convexity proves that
    every point of the box is outside. Failure to find a plane is UNRESOLVED,
    never a claim that the complete box is visible or free from occlusion.
    """
    if any(low[axis] > high[axis] for axis in range(3)):
        raise ValueError("frustum candidate bounds must be ordered")
    matrix = np.asarray(camera.camera_to_world, dtype=float)
    corners = np.asarray(tuple(product(*(tuple((low[i], high[i])) for i in range(3)))))
    local = np.linalg.solve(matrix, np.column_stack((corners, np.ones(8))).T).T[:, :3]
    depth = -local[:, 2]
    conditions = {
        "NEAR_AXIAL_CLIP": depth - camera.clip_start,
        "FAR_AXIAL_CLIP": camera.clip_end - depth,
        "LEFT_PIXEL_BOUNDARY": camera.fx * local[:, 0] + camera.cx * depth,
        "RIGHT_PIXEL_BOUNDARY": (camera.width - camera.cx) * depth - camera.fx * local[:, 0],
        "TOP_PIXEL_BOUNDARY": camera.cy * depth - camera.fy * local[:, 1],
        "BOTTOM_PIXEL_BOUNDARY": (camera.height - camera.cy) * depth + camera.fy * local[:, 1],
    }
    for name, values in conditions.items():
        maximum = float(values.max())
        epsilon = max(1e-8, 32 * math.ulp(max(abs(maximum), 1)))
        if maximum < -epsilon:
            return {
                "camera_id": camera.camera_id, "status": "WHOLE_BOX_OUTSIDE_SOURCE_FRUSTUM",
                "separating_halfspace": name, "maximum_halfspace_value": maximum,
                "numeric_guard": epsilon, "occlusion_test_required": False,
            }
    return None


def audit_approved_island_candidates(
    provider: ReviewedRestrictedLocalPhysicalProvider,
    obstacle_authority_path: Path, source_evidence_path: Path,
    cameras: tuple[Camera, ...], *, expected_obstacle_authority_file_sha256: str,
    floor_support_z_bu: float, proposed_landmark_offset_bu: float,
) -> dict[str, Any]:
    """Return bounded proposals/automatic exclusions using public source evidence.

    Candidate bounds add one approved body diameter plus clearance on each side
    of each existing solid component. That is a concrete local review candidate,
    not a proof that it is the smallest feasible branching domain. The unchanged
    camera frustum test is only an early necessary visibility check.
    """
    checked = ReviewedRestrictedLocalPhysicalProvider(
        provider.certificate, provider.domain, provider.contract,
        provider.expected_certificate_content_sha256, provider.expected_human_decisions_sha256,
    )
    raw = obstacle_authority_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_obstacle_authority_file_sha256:
        raise ValueError("obstacle authority input hash mismatch")
    obstacles = json.loads(raw)
    source_raw = source_evidence_path.read_bytes()
    source = json.loads(gzip.decompress(source_raw))
    validate_source_evidence(source, expected_source_sha256=checked.domain.source_sha256)
    if content_sha256(source) != checked.certificate.semantic_review.evidence_content_sha256 or (
        obstacles["source_sha256"] != checked.domain.source_sha256
        or obstacles["source_evidence_content_sha256"] != content_sha256(source)
    ):
        raise ValueError("candidate atlas/obstacle authority differs from original reviewed source")
    meshes = {row["mesh_id"]: row for row in source["meshes"]}
    ratio = checked.contract.scale.metres_per_blender_unit
    margin_bu = 2 * checked.contract.footprint_radius_bu
    current_low, current_high = checked.certificate.physical_certificate.footpoint_bounds_bu
    domain_diagonal_m = math.dist(current_low[:2], current_high[:2]) * ratio
    rows = []
    for obstacle in obstacles["obstacles"]:
        if obstacle["floor_id"] != checked.domain.floor.floor_id:
            continue
        for component in obstacle["components"]:
            if component["status"] != "APPROVED":
                continue
            binding = component["source_binding"]
            mesh = meshes[binding["source_mesh_id"]]
            if mesh["geometry_sha256"] != binding["source_geometry_sha256"] or (
                mesh["source_object_id"] != component["source_object_id"]
            ):
                raise ValueError("candidate approved component source geometry binding differs")
            part = next(row for row in mesh["components"]
                        if row["component_id"] == component["component_id"])
            bounds = part["bounds_bu"]
            if bounds != component["bounds_bu"]:
                raise ValueError("candidate component bounds differ from actual source atlas")
            low, high = bounds["minimum"], bounds["maximum"]
            foot_low: Vec3 = (low[0] - margin_bu, low[1] - margin_bu, floor_support_z_bu)
            foot_high: Vec3 = (high[0] + margin_bu, high[1] + margin_bu, floor_support_z_bu)
            marker_low: Vec3 = (foot_low[0], foot_low[1],
                               floor_support_z_bu + proposed_landmark_offset_bu)
            marker_high: Vec3 = (foot_high[0], foot_high[1], marker_low[2])
            visibility = tuple(frustum_separating_plane(camera, marker_low, marker_high)
                               for camera in cameras)
            dx = max(current_low[0] - high[0], low[0] - current_high[0], 0)
            dy = max(current_low[1] - high[1], low[1] - current_high[1], 0)
            distance_m = math.hypot(dx, dy) * ratio
            faces = sorted({mesh["triangle_source_face_indices"][index]
                            for index in part["source_triangle_indices"]})
            rows.append({
                "obstacle_id": obstacle["obstacle_id"],
                "source_object_id": mesh["source_object_id"],
                "source_mesh_id": mesh["mesh_id"],
                "source_geometry_sha256": mesh["geometry_sha256"],
                "source_component_id": component["component_id"],
                "source_face_indices": faces,
                "source_triangle_count": len(part["source_triangle_indices"]),
                "source_bounds_bu": bounds,
                "closed_component_authority": "APPROVED",
                "whole_obstacle_authority": obstacle["whole_obstacle_authority"],
                "candidate_footpoint_bounds_bu": (foot_low, foot_high),
                "proposed_camera_marker_binding_authority": "HUMAN_REVIEW_OUTSIDE_OFFICE",
                "source_camera_frustum_exclusions": visibility,
                "both_local_source_camera_views_impossible": all(row is not None
                                                                 for row in visibility),
                "distance_from_current_scope_lower_bound_m": distance_m,
                "office_to_island_and_return_length_lower_bound_m": 2 * distance_m,
                "maximum_current_domain_direct_detour_budget_m": 2 * domain_diagonal_m,
                "return_to_office_route_within_existing_detour_budget": (
                    2 * distance_m <= 2 * domain_diagonal_m
                ),
                "free_space_certificate": "NOT_CERTIFIED",
                "source_distinct_branches_proven": False,
                "status": "HUMAN_REVIEW_CANDIDATE_AUTOMATIC_VISIBILITY_AND_BUDGET_CHECKS_ONLY",
            })
    return {
        "schema_version": "reviewed-approved-island-scope-audit-v1",
        "status": "NO_EXISTING_AUTHORIZED_BRANCHING_DOMAIN",
        "source_sha256": checked.domain.source_sha256,
        "source_evidence_content_sha256": content_sha256(source),
        "obstacle_authority_file_sha256": expected_obstacle_authority_file_sha256,
        "approved_floor_component_count": len(rows),
        "approved_obstacle_role_count": len({row["obstacle_id"] for row in rows}),
        "candidate_scope_is_proven_minimal": False,
        "geometry_or_camera_authority_granted": False,
        "scope_extended": False,
        "original_decisions_reopened": False,
        "ground_truth_read": False,
        "candidates": rows,
    }


def audit_two_sided_source_candidates(
    candidates: dict[str, Any], domain: WalkableClearanceDomain,
    cameras: tuple[Camera, ...], *, floor_support_z_bu: float,
    proposed_landmark_offset_bu: float,
) -> dict[str, Any]:
    """Check 116 explicit rectangular bypass proposals; never claim global absence.

    Each source component gets two possible travel axes and two sides. Support
    uses the actual approved source contact union and its existing body clearance
    check. Different source cameras must frame departure and recovery. FOV is a
    necessary condition only; no occlusion or full free-space certificate follows.
    """
    if candidates["source_sha256"] != domain.source_sha256:
        raise ValueError("candidate bypass support domain source differs")
    margin = domain.required_clearance_bu + .5
    z, offset = floor_support_z_bu, proposed_landmark_offset_bu
    rows = []
    for candidate in candidates["candidates"]:
        low = candidate["source_bounds_bu"]["minimum"]
        high = candidate["source_bounds_bu"]["maximum"]
        x, y = (low[0] + high[0]) / 2, (low[1] + high[1]) / 2
        for axis in ("y", "x"):
            if axis == "y":
                start, end = (x, low[1] - margin, z), (x, high[1] + margin, z)
                routes = (
                    (start, (low[0] - margin, start[1], z),
                     (low[0] - margin, end[1], z), end),
                    (start, (high[0] + margin, start[1], z),
                     (high[0] + margin, end[1], z), end),
                )
            else:
                start, end = (low[0] - margin, y, z), (high[0] + margin, y, z)
                routes = (
                    (start, (start[0], low[1] - margin, z),
                     (end[0], low[1] - margin, z), end),
                    (start, (start[0], high[1] + margin, z),
                     (end[0], high[1] + margin, z), end),
                )
            support = tuple(domain.validate_segment(first, last)
                            for route in routes for first, last in pairwise(route))
            start_cameras, end_cameras = [], []
            projections = {}
            for camera in cameras:
                if camera.floor_id != domain.floor.floor_id:
                    continue
                first = project_world(camera, (start[0], start[1], start[2] + offset))
                last = project_world(camera, (end[0], end[1], end[2] + offset))
                projections[camera.camera_id] = {
                    "departure": first.model_dump(mode="json"),
                    "recovery": last.model_dump(mode="json"),
                }
                if first.in_frustum:
                    start_cameras.append(camera.camera_id)
                if last.in_frustum:
                    end_cameras.append(camera.camera_id)
            rows.append({
                "component": candidate["source_object_id"] + ":"
                + candidate["source_component_id"],
                "obstacle_id": candidate["obstacle_id"], "axis": axis,
                "start": start, "end": end, "routes": routes,
                "support_all_segments_pass": all(row.valid for row in support),
                "support_fail_reasons": tuple(row.reason for row in support if not row.valid),
                "start_cameras_in_frustum": start_cameras,
                "end_cameras_in_frustum": end_cameras,
                "two_distinct_cameras_match": any(first != last for first in start_cameras
                                                   for last in end_cameras),
                "source_camera_endpoint_projections": projections,
                "source_component": candidate,
                "source_occlusion": "NOT_RUN",
                "full_body_free_space_certificate": "NOT_CERTIFIED",
                "new_camera_landmark_binding": "HUMAN_REVIEW",
            })
    support_count = sum(row["support_all_segments_pass"] for row in rows)
    fov_count = sum(row["two_distinct_cameras_match"] for row in rows)
    combined_count = sum(row["support_all_segments_pass"] and row["two_distinct_cameras_match"]
                         for row in rows)
    return {
        "schema_version": "reviewed-two-sided-source-candidate-audit-v1",
        "status": "PROPOSAL_NOT_AVAILABLE" if combined_count == 0 else "HUMAN_REVIEW_REQUIRED",
        "source_sha256": domain.source_sha256,
        "configured_candidate_count": len(rows),
        "support_pass_count": support_count,
        "source_camera_fov_pair_count": fov_count,
        "combined_support_and_camera_fov_pair_count": combined_count,
        "candidate_family": "TWO_AXES_TWO_RECTANGULAR_BYPASS_SIDES_PER_APPROVED_COMPONENT",
        "global_exhaustive_branch_search": False,
        "source_distinct_feasible_branches_certified": False,
        "human_approval_applied": False,
        "ground_truth_read": False,
        "candidates": rows,
    }
