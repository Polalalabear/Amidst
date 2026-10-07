"""Source-only branching proposals, without changing or granting physical authority.

The earlier audit intersected contact with approved WALKABLE annotations. This
discovery instead records original source support faces outside that permission.
Every such face remains HUMAN_REVIEW. Body checks use actual triangles and full
selected components, not obstacle boxes as collision substitutes. No GT, route
ranking, simulation schedule, or formal certificate is produced here.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from itertools import pairwise, product
from typing import Any

import numpy as np
from shapely import union_all
from shapely.geometry import LineString, Polygon, box

from amidst.domain.camera import Camera
from amidst.domain.common import Vec3
from amidst.obstacle_volume_authority import (
    component_geometry,
    component_topology,
    content_sha256,
    region_patches,
    validate_source_evidence,
)
from amidst.physical_collision import (
    CollisionNumerics,
    point_inside_closed_mesh,
    upright_body_triangle_distance,
)
from amidst.physical_policy_contract import PhysicalPolicyContract
from amidst.simulation.virtual_camera import project_world


def _vec(values: Any) -> Vec3:
    return float(values[0]), float(values[1]), float(values[2])


def source_support_patch(
    evidence: Mapping[str, Any], *, source_object_id: str, floor_z_bu: float,
    query_xy: Polygon, contact_tolerance_bu: float,
) -> dict[str, Any]:
    """Locate exact planar contact triangles; permission is always HUMAN_REVIEW.

    A named object is an explicit discovery input, never a semantic inference.
    Actual source triangles are retained, including their original parent faces.
    The query selects a superset; triangles are not flattened or repaired.
    """
    if not math.isfinite(floor_z_bu) or contact_tolerance_bu <= 0 or (
        not math.isfinite(contact_tolerance_bu) or query_xy.is_empty or not query_xy.is_valid
    ):
        raise ValueError("source support needs finite height/tolerance and a valid query")
    meshes = [row for row in evidence["meshes"] if row["source_object_id"] == source_object_id]
    if len(meshes) != 1 or meshes[0].get("full_object_exported") is not True:
        raise ValueError("source support object must have one complete exact mesh")
    mesh = meshes[0]
    vertices = np.asarray(mesh["vertices"], dtype=float)
    triangles = vertices[np.asarray(mesh["triangles"], dtype=int)]
    xmin, ymin, xmax, ymax = query_xy.bounds
    indices = np.flatnonzero(
        (np.max(np.abs(triangles[:, :, 2] - floor_z_bu), axis=1) <= contact_tolerance_bu)
        & (triangles[:, :, 0].max(axis=1) >= xmin)
        & (triangles[:, :, 0].min(axis=1) <= xmax)
        & (triangles[:, :, 1].max(axis=1) >= ymin)
        & (triangles[:, :, 1].min(axis=1) <= ymax)
    )
    rows = []
    polygons = []
    for index in indices:
        triangle = triangles[index]
        polygon = Polygon(triangle[:, :2])
        if polygon.area <= 0 or not polygon.is_valid:
            continue
        polygons.append(polygon)
        rows.append({
            "source_triangle_index": int(index),
            "source_face_index": int(mesh["triangle_source_face_indices"][index]),
            "vertices_bu": triangle.tolist(),
        })
    geometry = union_all(polygons)
    if not geometry.is_valid:
        raise ValueError("invalid raw support union; geometry repair is forbidden")
    heights = [point[2] for row in rows for point in row["vertices_bu"]]
    band = None if not heights else (
        max(heights) - contact_tolerance_bu, min(heights) + contact_tolerance_bu,
    )
    return {
        "source_sha256": evidence["source_sha256"], "source_object_id": source_object_id,
        "source_mesh_id": mesh["mesh_id"], "source_geometry_sha256": mesh["geometry_sha256"],
        "source_face_indices": sorted({row["source_face_index"] for row in rows}),
        "source_face_bindings": [{"source_object_id": source_object_id,
                                  "source_face_index": face}
                                 for face in sorted({row["source_face_index"] for row in rows})],
        "actual_source_triangles": rows, "contact_height_band_bu": band,
        "floor_z_bu": floor_z_bu, "contact_tolerance_bu": contact_tolerance_bu,
        "semantic_authority": "HUMAN_REVIEW", "physical_authority": "HUMAN_REVIEW",
        "geometry_wkb_hex": geometry.wkb_hex,
        "query_guard_bounds_xy_bu": query_xy.bounds,
        "geometry_modified": False, "floor_contact_profile_requires_new_scope_approval": True,
    }


def combine_source_support_patches(patches: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Union explicit raw source patches while retaining every unapproved binding."""
    from shapely import from_wkb

    if not patches or len({row["source_sha256"] for row in patches}) != 1:
        raise ValueError("raw support patches require one exact source identity")
    result = dict(patches[0])
    active = [row for row in patches if row["actual_source_triangles"]]
    union = union_all([from_wkb(bytes.fromhex(row["geometry_wkb_hex"])) for row in active])
    bands = [row["contact_height_band_bu"] for row in active]
    result.update(
        source_patches=patches,
        source_face_bindings=[binding for row in active for binding in row["source_face_bindings"]],
        geometry_wkb_hex=union.wkb_hex,
        contact_height_band_bu=None if not bands else (
            max(row[0] for row in bands), min(row[1] for row in bands)),
    )
    return result


def support_route_evidence(
    support: Mapping[str, Any], route: tuple[Vec3, ...], clearance_bu: float,
) -> dict[str, Any]:
    """Exact line/union-boundary clearance; no buffer contour is a proof."""
    from shapely import from_wkb

    if len(route) < 2 or not math.isfinite(clearance_bu) or clearance_bu <= 0:
        raise ValueError("source route needs two points and positive finite clearance")
    union = from_wkb(bytes.fromhex(support["geometry_wkb_hex"]))
    line = LineString([point[:2] for point in route])
    band = support["contact_height_band_bu"]
    covered = bool(union.covers(line))
    boundary_distance = float(union.boundary.distance(line)) if covered else None
    contact = band is not None and band[0] <= band[1] and all(
        band[0] <= point[2] <= band[1] for point in route
    )
    supported = covered and contact and boundary_distance is not None and (
        boundary_distance >= clearance_bu
    )
    return {
        "source_support_geometrically_sufficient": supported,
        "centerline_on_actual_source_union": covered, "source_contact_height_valid": contact,
        "minimum_source_support_boundary_distance_bu": boundary_distance,
        "required_footprint_clearance_bu": clearance_bu,
        "authority": "HUMAN_REVIEW", "formal_support_pass": False,
    }


def _enclosure_evidence(
    evidence: Mapping[str, Any], region: Mapping[str, Any], centers: tuple[Vec3, ...],
) -> dict[str, Any]:
    meshes = {row["mesh_id"]: row for row in evidence["meshes"]}
    checked = []
    for selection in region["selections"]:
        mesh = meshes[selection["mesh_id"]]
        for component in mesh["components"]:
            if component["component_id"] not in selection["component_ids"]:
                continue
            low, high = component["bounds_bu"]["minimum"], component["bounds_bu"]["maximum"]
            probes = tuple(center for center in centers if all(
                low[axis] <= center[axis] <= high[axis] for axis in range(3)
            ))
            if not probes:
                continue
            vertices, triangles, _ = component_geometry(mesh, component)
            topology = component_topology(vertices, triangles)
            row = {"source_object_id": mesh["source_object_id"],
                   "source_mesh_id": mesh["mesh_id"],
                   "source_geometry_sha256": mesh["geometry_sha256"],
                   "source_component_id": component["component_id"], "topology": topology}
            faces = sorted({mesh["triangle_source_face_indices"][index]
                            for index in component["source_triangle_indices"]})
            row["source_component_face_count"] = len(faces)
            row["source_component_face_indices_content_sha256"] = content_sha256(faces)
            row["source_component_face_indices_first_16"] = faces[:16]
            source_points = np.asarray(mesh["vertices"])
            zero_by_face: dict[int, list[bool]] = {}
            for triangle_index in component["source_triangle_indices"]:
                triangle = source_points[np.asarray(mesh["triangles"][triangle_index])]
                zero = bool(np.linalg.norm(np.cross(triangle[1] - triangle[0],
                                                    triangle[2] - triangle[0])) == 0)
                face_id = int(mesh["triangle_source_face_indices"][triangle_index])
                zero_by_face.setdefault(face_id, []).append(zero)
            row["exact_zero_area_source_face_indices"] = sorted(
                face for face, decisions in zero_by_face.items() if all(decisions))
            row["zero_area_check_uses_exact_cross_product_zero"] = True
            if topology["boundary_edge_count"] > 0:
                row["state"] = "OPEN_SOURCE_COMPONENT_NOT_CLOSED_VOLUME"
            elif not topology["closed_consistent_nonzero_volume"]:
                row["state"] = "UNRESOLVED_CLOSED_SOURCE_COMPONENT"
            else:
                source_triangles = np.asarray(vertices)[np.asarray(triangles)]
                decisions = [point_inside_closed_mesh(np.asarray(point), source_triangles)
                             for point in probes]
                row["state"] = ("INSIDE_SOURCE_VOLUME" if any(v is True for v in decisions)
                                else "UNRESOLVED_SOURCE_CONTAINMENT"
                                if any(v is None for v in decisions) else "OUTSIDE_SOURCE_VOLUME")
            checked.append(row)
    blockers = [row for row in checked if row["state"] in {
        "INSIDE_SOURCE_VOLUME", "UNRESOLVED_CLOSED_SOURCE_COMPONENT",
        "UNRESOLVED_SOURCE_CONTAINMENT",
    }]
    return {"closed_component_containment_clear": not blockers, "checks": checked,
            "blockers": blockers,
            "proof_basis": "CONTINUOUS_BOUNDARY_SEPARATION_PLUS_ENDPOINT_BODY_CENTER_CONTAINMENT"}


def body_cell_evidence(
    evidence: Mapping[str, Any], region_id: str, cell_xy: Polygon,
    contact_band_bu: tuple[float, float], support: Mapping[str, Any],
    contract: PhysicalPolicyContract, numerics: CollisionNumerics,
    *, obstruction_object_ids: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Screen a complete narrow rectangular tube with continuous full-body distance.

    Source floor contacts are explicit proposed exceptions, never automatically
    approved. Complete original region coverage and enclosure selection remain
    necessary. Uncertain/degenerate triangles are reported without being removed.
    """
    regions = [row for row in evidence["regions"] if row["region_id"] == region_id]
    if len(regions) != 1:
        raise ValueError("body source region missing/duplicated")
    region = regions[0]
    xmin, ymin, xmax, ymax = cell_xy.bounds
    low_z, high_z = contact_band_bu
    if cell_xy.is_empty or not cell_xy.equals(box(xmin, ymin, xmax, ymax)) or low_z > high_z:
        raise ValueError("body cell must be an ordered nonempty rectangle/contact band")
    ratio = contract.scale.metres_per_blender_unit
    radius = contract.footprint_radius_bu
    clearance = contract.parameter("body_clearance_m")
    extra = clearance / ratio
    envelope_low = np.array([xmin - radius, ymin - radius, low_z - extra])
    envelope_high = np.array([xmax + radius, ymax + radius,
                              high_z + (contract.parameter("body_height_m") + clearance) / ratio])
    region_low, region_high = region["bounds_bu"]["minimum"], region["bounds_bu"]["maximum"]
    covered = bool(np.all(envelope_low >= region_low) and np.all(envelope_high <= region_high))
    result: dict[str, Any] = {
        "source_body_region_id": region_id, "source_body_region_selection_complete": (
            region["kind"] == "FULL_BODY_CONTEXT" and region["selection_complete"] is True
            and evidence["policy"].get("component_enclosure_candidates_included") is True
        ), "source_region_covers_entire_body_guard": covered,
        "footpoint_cell_bounds_xy_bu": cell_xy.bounds, "footpoint_contact_band_bu": contact_band_bu,
        "body_guard_bounds_bu": {"minimum": envelope_low.tolist(),
                                  "maximum": envelope_high.tolist()},
        "legal_support_contacts_require_approval": True, "formal_certificate": "NOT_CERTIFIED",
        "semantic_authority": "HUMAN_REVIEW", "blockers": [],
    }
    if not covered or not result["source_body_region_selection_complete"]:
        result.update(source_body_geometry_clear=False,
                      blockers=["FRESH_EXHAUSTIVE_BODY_SOURCE_SELECTION_REQUIRED"])
        return result
    feet = tuple(_vec((x * ratio, y * ratio, z * ratio))
                 for x, y in list(cell_xy.exterior.coords)[:-1]
                 for z in sorted({low_z, high_z}))
    support_faces = {(row["source_object_id"], row["source_face_index"])
                     for row in support["source_face_bindings"]}
    queries = legal = screened = 0
    minimum: float | None = None
    failures: list[dict[str, Any]] = []
    guard_bindings: dict[tuple[str, str], set[int]] = {}
    for patch in region_patches(evidence, region_id):
        triangles = np.asarray(patch["vertices"])[np.asarray(patch["triangles"])]
        screened += len(triangles)
        selected = np.flatnonzero((triangles.max(axis=1) >= envelope_low).all(axis=1)
                                  & (triangles.min(axis=1) <= envelope_high).all(axis=1))
        for index in selected:
            triangle = triangles[index]
            face = int(patch["triangle_source_face_indices"][index])
            binding = {"source_object_id": patch["source_object_id"], "source_face_index": face,
                       "source_mesh_id": patch["mesh_id"],
                       "source_geometry_sha256": patch["source_geometry_sha256"]}
            guard_key = (patch["source_object_id"], patch["mesh_id"])
            guard_bindings.setdefault(guard_key, set()).add(face)
            normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
            if float(np.linalg.norm(normal)) == 0:
                failures.append({**binding, "reason": "DEGENERATE_SOURCE_TRIANGLE_REQUIRES_REVIEW"})
                continue
            if (patch["source_object_id"], face) in support_faces and (
                low_z >= float(triangle[:, 2].max())
                - support["contact_tolerance_bu"] and high_z <= float(triangle[:, 2].min())
                + support["contact_tolerance_bu"]
            ):
                legal += 1
                continue
            queries += 1
            if queries > numerics.maximum_triangles_per_segment:
                failures.append({"reason": "EXACT_BODY_QUERY_BUDGET_EXCEEDED"})
                break
            distance = upright_body_triangle_distance(
                feet, tuple(_vec(point * ratio) for point in triangle),  # type: ignore[arg-type]
                radius_m=contract.parameter("body_radius_m"),
                height_m=contract.parameter("body_height_m"), numerics=numerics,
            )
            minimum = distance.lower_m if minimum is None else min(minimum, distance.lower_m)
            if distance.lower_m < clearance - 16 * math.ulp(max(clearance, 1.0)):
                failures.append({**binding, "reason": "SOURCE_BODY_CLEARANCE_OR_DISTANCE_UNCERTAIN",
                                 "distance_lower_m": distance.lower_m,
                                 "distance_upper_m": distance.upper_m,
                                 "actual_source_triangle_bu": triangle.tolist()})
                if patch["source_object_id"] in obstruction_object_ids and (
                    distance.upper_m <= contract.parameter("collision_tolerance_m")
                ):
                    result.update(source_body_geometry_clear=False,
                                  exact_distance_queries=queries,
                                  source_triangle_failures=failures,
                                  actual_source_obstruction_witness_found=True,
                                  remaining_distance_queries="NOT_REQUIRED_FOR_OBSTRUCTION_WITNESS")
                    return result
    centers = tuple((float(x), float(y), (low_z + high_z) / 2
                     + contract.parameter("body_height_m") / ratio / 2)
                    for x, y in cell_xy.exterior.coords)
    enclosure = _enclosure_evidence(evidence, region, centers)
    if enclosure["blockers"]:
        failures.append({"reason": "SOURCE_ENCLOSURE_NOT_CLEAR"})
    result.update(source_body_geometry_clear=not failures,
                  continuous_body_triangle_sweep_clear=not any(
                      row["reason"] != "SOURCE_ENCLOSURE_NOT_CLEAR" for row in failures),
                  exact_distance_queries=queries,
                  source_triangles_screened=screened, proposed_legal_support_triangles=legal,
                  minimum_other_geometry_distance_lower_m=minimum,
                  source_triangle_failures=failures, enclosure=enclosure,
                  source_faces_intersecting_body_guard=[{
                      "source_object_id": obj, "source_mesh_id": mesh_id,
                      "source_face_indices": sorted(faces),
                  } for (obj, mesh_id), faces in sorted(guard_bindings.items())],
                  blockers=sorted({row["reason"] for row in failures}))
    return result


def propose_source_island(
    evidence: Mapping[str, Any], obstacles: Mapping[str, Any],
    contract: PhysicalPolicyContract, numerics: CollisionNumerics, cameras: tuple[Camera, ...],
    *, obstacle_id: str, support_source_object_id: str, floor_z_bu: float,
    source_body_region_id: str, landmark_offset_bu: float, placement_margin_bu: float = .5,
    tube_half_width_bu: float = .1,
    additional_source_object_ids: tuple[str, ...] = (), endpoint_extension_bu: float = 0.,
    additional_support_source_object_ids: tuple[str, ...] = (),
    same_side_endpoint_x_bu: tuple[float, float] | None = None,
    east_return_endpoints_xy_bu: tuple[float, float, float, float] | None = None,
    east_return_turn_x_bu: float | None = None,
) -> dict[str, Any]:
    """Build a small source-supported two-sided proposal around one whole island.

    Rectangular connectors are discovery recipes only. Actual triangles establish
    direct obstruction and continuous body-tube clearance. Original permission is
    never widened and every new domain/binding requires explicit human approval.
    """
    validate_source_evidence(evidence, expected_source_sha256=contract.scale.source_asset_sha256)
    if obstacles["source_sha256"] != evidence["source_sha256"] or (
        obstacles["source_evidence_content_sha256"] != content_sha256(evidence)
    ):
        raise ValueError("obstacle/source evidence binding differs")
    if any(not math.isfinite(v) or v <= 0 for v in (
        placement_margin_bu, tube_half_width_bu, landmark_offset_bu,
    )) or tube_half_width_bu >= placement_margin_bu or (
        not math.isfinite(endpoint_extension_bu) or endpoint_extension_bu < 0
    ):
        raise ValueError("finite tube width must be smaller than the placement margin")
    role = next(row for row in obstacles["obstacles"] if row["obstacle_id"] == obstacle_id)
    approved = [row for row in role["components"] if row["status"] == "APPROVED"]
    if not approved:
        raise ValueError("discovery island requires an existing source-bound closed component")
    by_mesh_id = {row["mesh_id"]: row for row in evidence["meshes"]}
    for component in approved:
        binding = component["source_binding"]
        mesh = by_mesh_id[binding["source_mesh_id"]]
        parts = [row for row in mesh["components"]
                 if row["component_id"] == component["component_id"]]
        if mesh["source_object_id"] != component["source_object_id"] or (
            mesh["geometry_sha256"] != binding["source_geometry_sha256"] or len(parts) != 1
            or parts[0]["bounds_bu"] != component["bounds_bu"]
        ):
            raise ValueError("approved source component geometry binding differs")
    object_ids = {row["source_object_id"] for row in approved}
    object_ids.update(additional_source_object_ids)
    meshes = [row for row in evidence["meshes"] if row["source_object_id"] in object_ids]
    if {row["source_object_id"] for row in meshes} != object_ids:
        raise ValueError("explicit additional island source object is absent from original atlas")
    ratio = contract.scale.metres_per_blender_unit
    top = floor_z_bu + contract.parameter("body_height_m") / ratio
    source_points = []
    mesh_bindings = []
    for mesh in meshes:
        triangles = np.asarray(mesh["vertices"])[np.asarray(mesh["triangles"])]
        indices = np.flatnonzero((triangles.max(axis=1)[:, 2] > floor_z_bu)
                                 & (triangles.min(axis=1)[:, 2] < top))
        if len(indices):
            source_points.extend(triangles[indices].reshape(-1, 3).tolist())
            mesh_bindings.append({
                "source_object_id": mesh["source_object_id"], "source_mesh_id": mesh["mesh_id"],
                "source_geometry_sha256": mesh["geometry_sha256"],
                "source_face_indices": sorted({mesh["triangle_source_face_indices"][i]
                                                for i in indices}),
                "whole_object_authority": "HUMAN_REVIEW",
            })
    if not source_points:
        raise ValueError("source island does not overlap the proposed full body height")
    low, high = np.min(source_points, axis=0), np.max(source_points, axis=0)
    margin = contract.footprint_radius_bu + placement_margin_bu
    x0, x1 = float(low[0] - margin), float(high[0] + margin)
    y0, y1 = float(low[1] - margin), float(high[1] + margin)
    ymid = float((low[1] + high[1]) / 2)
    start = (x0 - endpoint_extension_bu, ymid, floor_z_bu)
    end = (x1 + endpoint_extension_bu, ymid, floor_z_bu)
    routes: tuple[tuple[Vec3, ...], ...] = (
        (start, (start[0], y0, floor_z_bu), (end[0], y0, floor_z_bu), end),
        (start, (start[0], y1, floor_z_bu), (end[0], y1, floor_z_bu), end),
    )
    if same_side_endpoint_x_bu is not None:
        departure_x, recovery_x = same_side_endpoint_x_bu
        if not all(math.isfinite(v) for v in same_side_endpoint_x_bu) or (
            not x1 < departure_x < recovery_x
        ):
            raise ValueError("same-side source endpoints must be strictly east of the whole island")
        start, end = (departure_x, y1, floor_z_bu), (recovery_x, y1, floor_z_bu)
        routes = ((start, end), (start, (x0, y1, floor_z_bu), (x0, y0, floor_z_bu),
                                (recovery_x, y0, floor_z_bu), end))
    if east_return_endpoints_xy_bu is not None:
        if same_side_endpoint_x_bu is not None or east_return_turn_x_bu is None:
            raise ValueError("source return proposal needs one explicit endpoint design and turn")
        sx, sy, ex, ey = east_return_endpoints_xy_bu
        turn = east_return_turn_x_bu
        if not all(math.isfinite(v) for v in (*east_return_endpoints_xy_bu, turn)) or (
            not x1 < turn < sx < ex or not sy < y0 < ey < float(low[1])
        ):
            raise ValueError(
                "source return endpoints must give a disjoint south approach/east exit",
            )
        start, end = (sx, sy, floor_z_bu), (ex, ey, floor_z_bu)
        routes = ((start, end), (start, (x0, sy, floor_z_bu), (x0, y1, floor_z_bu),
                                (turn, y1, floor_z_bu), (turn, ey, floor_z_bu), end))
    all_points = [point for route in routes for point in route]
    guard = box(min(point[0] for point in all_points) - margin,
                min(point[1] for point in all_points) - margin,
                max(point[0] for point in all_points) + margin,
                max(point[1] for point in all_points) + margin)
    support = combine_source_support_patches(tuple(source_support_patch(
        evidence, source_object_id=identity, floor_z_bu=floor_z_bu,
        query_xy=guard, contact_tolerance_bu=contract.parameter("collision_tolerance_m") / ratio,
    ) for identity in (support_source_object_id, *additional_support_source_object_ids)))
    band = support["contact_height_band_bu"]
    if band is None or band[0] > band[1]:
        raise ValueError("no common actual source floor contact band")
    cells = []
    for route in routes:
        for first, last in pairwise(route):
            rectangle = box(min(first[0], last[0]) - tube_half_width_bu,
                            min(first[1], last[1]) - tube_half_width_bu,
                            max(first[0], last[0]) + tube_half_width_bu,
                            max(first[1], last[1]) + tube_half_width_bu)
            cells.append(body_cell_evidence(evidence, source_body_region_id, rectangle,
                                            band, support, contract, numerics))
    direct = body_cell_evidence(
        evidence, source_body_region_id,
            box(x0, ymid - tube_half_width_bu, x1, ymid + tube_half_width_bu),
        (floor_z_bu, floor_z_bu), support, contract, numerics,
        obstruction_object_ids=frozenset(object_ids),
    )
    occupied = [row for row in direct.get("source_triangle_failures", [])
                if row.get("source_object_id") in object_ids
                and row.get("distance_upper_m", math.inf)
                <= contract.parameter("collision_tolerance_m")]
    support_checks = [support_route_evidence(support, route, contract.footprint_radius_bu)
                      for route in routes]
    endpoint_projections: list[dict[str, Any]] = []
    for camera in sorted(cameras, key=lambda value: value.camera_id):
        if camera.floor_id != role["floor_id"]:
            continue
        departure_projection = project_world(
            camera, (start[0], start[1], start[2] + landmark_offset_bu),
        )
        recovery_projection = project_world(camera, (end[0], end[1], end[2] + landmark_offset_bu))
        endpoint_projections.append({"camera_id": camera.camera_id,
                                     "actual_source_camera": camera.model_dump(mode="json"),
                                     "departure": departure_projection.model_dump(mode="json"),
                                     "recovery": recovery_projection.model_dump(mode="json")})
    pairs = [(a["camera_id"], b["camera_id"]) for a, b in product(endpoint_projections, repeat=2)
             if a["camera_id"] != b["camera_id"] and a["departure"]["in_frustum"]
             and b["recovery"]["in_frustum"]]
    physical = all(row["source_support_geometrically_sufficient"] for row in support_checks)
    physical = physical and all(row["source_body_geometry_clear"] for row in cells) and bool(
        occupied
    )
    # A proposal can expose the exact sole unresolved source-surface semantics.
    # It cannot erase the enclosure blocker or become a physical/formal PASS.
    profile_pending = all(
        row.get("continuous_body_triangle_sweep_clear") is True and all(
            item["state"] == "UNRESOLVED_CLOSED_SOURCE_COMPONENT"
            for item in row.get("enclosure", {}).get("blockers", [])
        ) for row in cells
    )
    reviewable = (physical or profile_pending) and bool(occupied) and all(
        row["source_support_geometrically_sufficient"] for row in support_checks)
    winding = None
    if occupied:
        witness = np.mean(occupied[0]["actual_source_triangle_bu"], axis=0)
        loop = [*routes[0], *reversed(routes[1][:-1])]
        angles = []
        for first, last in pairwise(loop):
            ax, ay = first[0] - witness[0], first[1] - witness[1]
            bx, by = last[0] - witness[0], last[1] - witness[1]
            angles.append(math.atan2(ax * by - ay * bx, ax * bx + ay * by))
        number = sum(angles) / (2 * math.pi)
        winding = {"source_triangle_contact_witness": occupied[0],
                   "witness_xy_bu": witness[:2].tolist(), "combined_loop_winding_number": number,
                   "two_routes_wind_differently_around_actual_body_obstruction": abs(number) > .5,
                   "fixed_contact_height_band_bu": band, "semantic_authority": "HUMAN_REVIEW"}
        reviewable = reviewable and abs(number) > .5
    pending_profiles: dict[tuple[str, str], dict[str, Any]] = {}
    for cell_index, cell in enumerate(cells):
        for blocker in cell.get("enclosure", {}).get("blockers", []):
            key = (blocker["source_mesh_id"], blocker["source_component_id"])
            profile = pending_profiles.setdefault(key, {**blocker, "cell_guards": [],
                                                        "authority": "HUMAN_REVIEW"})
            in_guard = [row for row in cell["source_faces_intersecting_body_guard"]
                        if row["source_mesh_id"] == key[0]]
            profile["cell_guards"].append({"cell_index": cell_index,
                                           "body_guard_bounds_bu": cell["body_guard_bounds_bu"],
                                           "actual_source_faces_intersecting_guard": in_guard})
    return {
        "schema_version": "source-supported-branch-proposal-v1",
        "status": "PROPOSED" if reviewable and pairs else "DISCOVERY_BLOCKED",
        "source_sha256": evidence["source_sha256"],
        "source_evidence_content_sha256": content_sha256(evidence),
        "source_body_region_id": source_body_region_id, "obstacle_id": obstacle_id,
        "floor_id_proposed": role["floor_id"], "support_source_faces": support,
        "source_island_bindings": mesh_bindings, "existing_approved_closed_components": approved,
        "source_body_height_island_bounds_bu": {"minimum": low.tolist(), "maximum": high.tolist()},
        "common_endpoints_bu": (start, end), "two_sided_routes_bu": routes,
        "route_lengths_m": [sum(math.dist(a, b) for a, b in pairwise(route)) * ratio
                            for route in routes],
        "proposed_footpoint_cells": cells, "raw_support_route_checks": support_checks,
        "direct_connector_actual_source_body_contacts": occupied,
        "direct_connector_body_evidence": direct,
        "actual_source_obstruction_probe_endpoints_bu": (
            (x0, ymid, floor_z_bu), (x1, ymid, floor_z_bu)),
        "obstruction_probe_is_common_endpoint_connector": (
            same_side_endpoint_x_bu is None and east_return_endpoints_xy_bu is None),
        "direct_endpoint_distance_m": math.dist(start, end) * ratio,
        "source_route_lengths_over_endpoint_distance": [
            sum(math.dist(a, b) for a, b in pairwise(route)) / math.dist(start, end)
            for route in routes],
        "source_camera_endpoint_projections": endpoint_projections,
        "distinct_source_camera_fov_pairs": pairs,
        "proposed_landmark_offset_bu": landmark_offset_bu,
        "proposed_landmark_offset_m": landmark_offset_bu * ratio,
        "source_physical_candidate_geometry_sufficient": physical,
        "source_geometric_proposal_conditions_satisfied": reviewable,
        "source_route_winding_witness": winding,
        "placement_margin_bu": placement_margin_bu, "tube_half_width_bu": tube_half_width_bu,
        "additional_clearance_after_tube_width_m": (
            placement_margin_bu - tube_half_width_bu) * ratio,
        "unresolved_enclosure_profiles_requiring_new_approval": list(pending_profiles.values()),
        "bounded_surface_only_enclosure_profile_requires_new_approval": profile_pending
        and not physical,
        "proposed_source_surface_only_guard_profile": {
            "source_object_id": support_source_object_id,
            "source_mesh_id": support["source_mesh_id"],
            "source_geometry_sha256": support["source_geometry_sha256"],
            "source_face_indices": support["source_face_indices"],
            "cell_body_guards": [row["body_guard_bounds_bu"] for row in cells],
            "requested_semantics": "SOURCE_SUPPORT_SURFACES_ONLY_WITHIN_EXACT_GUARDS",
            "authority": "HUMAN_REVIEW", "whole_object_excluded": False,
        },
        "source_occlusion": "NOT_RUN", "visible_gap_visible": "NOT_PROVEN",
        "new_scope_semantics": "HUMAN_REVIEW", "camera_landmark_binding": "HUMAN_REVIEW",
        "new_floor_surface_only_profile": "HUMAN_REVIEW", "formal_readiness": False,
        "formal_certificate": "NOT_CERTIFIED", "authority_applied": False,
        "existing_office_scope_changed": False, "ground_truth_read": False,
        "candidate_is_proven_globally_minimal": False,
        "physical_policy": contract.policy.model_dump(mode="json"),
        "collision_numerics": numerics.model_dump(mode="json"),
    }
