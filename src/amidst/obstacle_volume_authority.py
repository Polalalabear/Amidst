"""Source-bound component collider review; no Blender, GT or inference dependencies.

Full source components may certify positive collision evidence. Their approval never
certifies an entire annotation, an aperture, or an absence of unclassified geometry.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from shapely import STRtree, get_coordinates
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from amidst.architectural_scale import ArchitecturalScale
from amidst.physical_authority import PhysicalPolicy
from amidst.scene_geometry import (
    Authority,
    Coordinate,
    FloorAuthority,
    GeometryRole,
    GeometrySupport,
    GeometrySurface,
    triangle_distance,
)


def content_sha256(document: Any) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _finite(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def validate_source_evidence(
    evidence: Mapping[str, Any], *, expected_source_sha256: str,
    expected_audit_content_sha256: str | None = None,
    expected_config_content_sha256: str | None = None,
) -> None:
    """Validate immutable full-object bindings before inspecting authority evidence."""
    if (
        re.fullmatch(r"[0-9a-f]{64}", expected_source_sha256) is None
        or evidence.get("schema_version") != "physical-policy-source-evidence-v1"
        or evidence.get("source_sha256") != expected_source_sha256
        or evidence.get("source_preserved") is not True
        or any(evidence.get(key) is not False for key in ("saved", "rendered", "geometry_modified"))
    ):
        raise ValueError("policy source evidence requires unchanged source SHA-256 bindings")
    for field, expected in (
        ("audit_content_sha256", expected_audit_content_sha256),
        ("config_content_sha256", expected_config_content_sha256),
    ):
        if expected is not None and evidence.get(field) != expected:
            raise ValueError(f"policy source evidence {field} differs from expected binding")
    policy = evidence.get("policy", {})
    required = {
        "gt_used": False, "roles_inferred_from_names": False, "bounds_are_colliders": False,
        "hidden_geometry_included": True, "missing_triangles_certify_clearance": False,
        "source_object_geometry_complete": True,
        "component_enclosure_candidates_included": True,
        "region_complete_means_exhaustive_selection_only": True,
    }
    if any(policy.get(key) is not value for key, value in required.items()):
        raise ValueError("policy source evidence cannot infer roles, hide geometry or invent space")
    authority = ArchitecturalScale.model_validate_json(json.dumps(evidence["architectural_scale"]))
    authority.require_source_sha256(expected_source_sha256)
    if evidence.get("architectural_scale_content_sha256") != content_sha256(
        evidence["architectural_scale"]
    ):
        raise ValueError("architectural scale content binding differs")
    identities = set()
    for mesh in evidence["meshes"]:
        identity = mesh.get("mesh_id")
        if identity in identities or not isinstance(identity, str):
            raise ValueError("source mesh identities must be unique")
        identities.add(identity)
        if (
            mesh.get("semantic_role") != "UNCLASSIFIED_SOURCE_MESH_CONTEXT_ONLY"
            or mesh.get("full_object_exported") is not True
            or mesh.get("geometry_sha256") != content_sha256(
                {key: value for key, value in mesh.items() if key != "geometry_sha256"}
            )
            or identity != content_sha256({
                key: mesh[key] for key in
                ("source_object_id", "vertices", "triangles", "triangle_source_face_indices")
            })
        ):
            raise ValueError("source mesh geometry or complete-object bindings differ")
        vertices, triangles = mesh["vertices"], mesh["triangles"]
        faces = mesh["triangle_source_face_indices"]
        if (
            len(vertices) != mesh["evaluated_vertex_count"]
            or len(triangles) != mesh["evaluated_triangle_count"]
            or len(faces) != len(triangles)
            or any(len(point) != 3 or not all(_finite(value) for value in point)
                   for point in vertices)
            or any(len(triangle) != 3 or any(
                isinstance(index, bool) or not isinstance(index, int)
                or not 0 <= index < len(vertices) for index in triangle
            ) for triangle in triangles)
            or any(isinstance(index, bool) or not isinstance(index, int)
                   or not 0 <= index < mesh["evaluated_polygon_count"] for index in faces)
            or sorted(set(faces)) != mesh["source_face_indices"]
        ):
            raise ValueError("source mesh has invalid original vertex/triangle/face references")
        covered = []
        component_ids = set()
        for component in mesh["components"]:
            indices = component["source_triangle_indices"]
            if (
                component["component_id"] in component_ids
                or component.get("full_component_exported") is not True
                or indices != sorted(set(indices))
                or any(isinstance(index, bool) or not isinstance(index, int)
                       or not 0 <= index < len(triangles) for index in indices)
                or len(indices) != component["triangle_count"]
                or component["source_vertex_indices"] != sorted({
                    vertex for index in indices for vertex in triangles[index]
                })
            ):
                raise ValueError("source component must retain complete original triangle indices")
            component_ids.add(component["component_id"])
            covered.extend(indices)
        if sorted(covered) != list(range(len(triangles))):
            raise ValueError("source components must partition the complete source object")
    regions = set()
    by_id = {mesh["mesh_id"]: mesh for mesh in evidence["meshes"]}
    for region in evidence["regions"]:
        if region["region_id"] in regions or not isinstance(region["selection_complete"], bool):
            raise ValueError("source region identities/completeness must be explicit")
        regions.add(region["region_id"])
        for selection in region["selections"]:
            if selection["mesh_id"] not in by_id:
                raise ValueError("source region references absent original geometry")
            mesh = by_id[selection["mesh_id"]]
            indices = selection["source_triangle_indices"]
            if (
                indices != sorted(set(indices))
                or any(isinstance(index, bool) or not isinstance(index, int)
                       or not 0 <= index < len(mesh["triangles"]) for index in indices)
                or selection["source_object_id"] != mesh["source_object_id"]
                or not set(selection["component_ids"]).issubset({
                    component["component_id"] for component in mesh["components"]
                })
            ):
                raise ValueError("source region selections differ from original geometry")


def region_patches(evidence: Mapping[str, Any], region_id: str) -> list[dict[str, Any]]:
    """Return exact survey-compatible patches from a previously validated atlas.

    Consumers must call validate_source_evidence once with independent expected
    source bindings. The helper does not substitute an empty region on failure.
    """
    matches = [region for region in evidence["regions"] if region["region_id"] == region_id]
    if len(matches) != 1:
        raise ValueError(f"unknown or duplicate source region: {region_id}")
    meshes = {mesh["mesh_id"]: mesh for mesh in evidence["meshes"]}
    result = []
    for selection in matches[0]["selections"]:
        mesh = meshes[selection["mesh_id"]]
        indices = selection["source_triangle_indices"]
        if not indices:
            # The component IDs still carry enclosing-volume evidence. Source
            # consumers must inspect those complete components independently.
            continue
        originals = sorted({vertex for index in indices for vertex in mesh["triangles"][index]})
        remap = {index: offset for offset, index in enumerate(originals)}
        patch = {
            "source_object_id": mesh["source_object_id"],
            "mesh_id": mesh["mesh_id"],
            "source_geometry_sha256": mesh["geometry_sha256"],
            "vertices": [mesh["vertices"][index] for index in originals],
            "triangles": [[remap[vertex] for vertex in mesh["triangles"][index]]
                          for index in indices],
            "source_vertex_indices": originals,
            "source_triangle_indices": indices,
            "triangle_source_face_indices": [mesh["triangle_source_face_indices"][index]
                                             for index in indices],
            "source_face_indices": sorted({mesh["triangle_source_face_indices"][index]
                                           for index in indices}),
            "semantic_role": mesh["semantic_role"],
            "hidden_render": mesh["hidden_render"],
            "hidden_viewport": mesh["hidden_viewport"],
            "viewport_disabled": mesh["viewport_disabled"],
            "collection_disabled": mesh["collection_disabled"],
        }
        patch["geometry_sha256"] = content_sha256(patch)
        result.append(patch)
    return result


def component_geometry(
    mesh: Mapping[str, Any], component: Mapping[str, Any]
) -> tuple[tuple[Coordinate, ...], tuple[tuple[int, int, int], ...], dict[str, Any]]:
    """Exact-coordinate reindex only; each resulting triangle retains original parents."""
    indices = component["source_triangle_indices"]
    originals = sorted({vertex for index in indices for vertex in mesh["triangles"][index]})
    keys = sorted({tuple(mesh["vertices"][index]) for index in originals})
    remap = {point: offset for offset, point in enumerate(keys)}
    vertices: tuple[Coordinate, ...] = tuple((point[0], point[1], point[2]) for point in keys)
    triangles = tuple(tuple(remap[tuple(mesh["vertices"][vertex])]
                            for vertex in mesh["triangles"][index]) for index in indices)
    provenance = {
        "source_mesh_id": mesh["mesh_id"],
        "source_geometry_sha256": mesh["geometry_sha256"],
        "source_component_id": component["component_id"],
        "source_vertex_indices": originals,
        "source_triangle_indices": indices,
        "triangle_source_face_indices": [mesh["triangle_source_face_indices"][index]
                                         for index in indices],
        "coincident_vertex_reindexing": "EXACT_COORDINATES_NO_ROUNDING_NO_COORDINATE_CHANGE",
        "source_component_complete": component["full_component_exported"],
    }
    return vertices, triangles, provenance  # type: ignore[return-value]


def component_topology(
    vertices: Sequence[Coordinate], triangles: Sequence[tuple[int, int, int]]
) -> dict[str, Any]:
    edges: Counter[tuple[int, int]] = Counter()
    orientations: Counter[tuple[int, int]] = Counter()
    coordinates = np.asarray(vertices, dtype=np.float64)
    indices = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    points = coordinates[indices]
    # Batch arithmetic retains source triangle order and the same local origin.
    # No rounding/welding/threshold change is applied to original coordinates.
    normals = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
    duplicated = ((indices[:, 0] == indices[:, 1]) | (indices[:, 1] == indices[:, 2])
                  | (indices[:, 0] == indices[:, 2]))
    degenerate = int(np.count_nonzero(duplicated | ~(np.linalg.norm(normals, axis=1) > 0)))
    for triangle in triangles:
        for a, b in zip(triangle, (*triangle[1:], triangle[0]), strict=True):
            key = (min(a, b), max(a, b))
            edges[key] += 1
            orientations[key] += 1 if a < b else -1
    shifted = points - coordinates[0]
    products = np.einsum(
        "ij,ij->i", shifted[:, 0], np.cross(shifted[:, 1], shifted[:, 2]),
    )
    signed_volume = math.fsum(float(value) / 6 for value in products)
    return {
        "triangle_count": len(triangles),
        "boundary_edge_count": sum(count == 1 for count in edges.values()),
        "nonmanifold_edge_count": sum(count > 2 for count in edges.values()),
        "inconsistent_winding_edge_count": sum(value != 0 for value in orientations.values()),
        "degenerate_triangle_count": degenerate,
        "signed_volume_bu3": signed_volume,
        "enclosed_volume_bu3": abs(signed_volume),
        "closed_consistent_nonzero_volume": bool(triangles) and not degenerate
        and all(count == 2 for count in edges.values())
        and all(value == 0 for value in orientations.values())
        and math.isfinite(signed_volume) and signed_volume != 0,
    }


def _shared_feature_intersection(
    first: tuple[Coordinate, Coordinate, Coordinate],
    second: tuple[Coordinate, Coordinate, Coordinate],
    shared: tuple[Coordinate, ...], numerical_epsilon: float,
) -> str:
    """Allow only the common vertex/edge, including coplanar and folded fans."""
    points_a, points_b = np.asarray(first), np.asarray(second)
    normal_a = np.cross(points_a[1] - points_a[0], points_a[2] - points_a[0])
    normal_b = np.cross(points_b[1] - points_b[0], points_b[2] - points_b[0])
    length_a, length_b = float(np.linalg.norm(normal_a)), float(np.linalg.norm(normal_b))
    if length_a == 0 or length_b == 0:
        return "HUMAN_REVIEW"
    normal_a, normal_b = normal_a / length_a, normal_b / length_b
    distances_a = (points_a - points_b[0]) @ normal_b
    distances_b = (points_b - points_a[0]) @ normal_a
    coplanar = bool(np.max(np.abs(distances_a)) <= numerical_epsilon
                    and np.max(np.abs(distances_b)) <= numerical_epsilon)
    if coplanar:
        omitted = int(np.argmax(np.abs(normal_a)))
        axes = [axis for axis in range(3) if axis != omitted]
        polygon_a = Polygon([(point[axes[0]], point[axes[1]]) for point in first])
        polygon_b = Polygon([(point[axes[0]], point[axes[1]]) for point in second])
        intersection = polygon_a.intersection(polygon_b)
        if intersection.area > 0:
            return "REJECTED"
        coordinates = [(point[axes[0]], point[axes[1]]) for point in shared]
        allowed = Point(coordinates[0]) if len(coordinates) == 1 else LineString(coordinates)
        if any(Point(point).distance(allowed) > numerical_epsilon
               for point in get_coordinates(intersection)):
            return "REJECTED"
        return "PASS"
    if len(shared) == 2:
        # Two distinct noncoplanar triangle planes intersect on their exact
        # shared edge. Each nondegenerate triangle's intersection is that edge.
        return "PASS"
    if len(shared) != 1:
        return "REJECTED"
    direction = np.cross(normal_a, normal_b)
    length = float(np.linalg.norm(direction))
    if length <= np.finfo(float).eps * 16:
        return "HUMAN_REVIEW"
    direction /= length
    origin = np.asarray(shared[0])

    def interval(points: Any, distances: Any) -> tuple[float, float] | None:
        cuts = [point for point, distance in zip(points, distances, strict=True)
                if abs(float(distance)) <= numerical_epsilon]
        for index in range(3):
            following = (index + 1) % 3
            first_distance, second_distance = float(distances[index]), float(distances[following])
            if (first_distance < -numerical_epsilon and second_distance > numerical_epsilon
                    or first_distance > numerical_epsilon
                    and second_distance < -numerical_epsilon):
                parameter = first_distance / (first_distance - second_distance)
                cuts.append(points[index] + parameter * (points[following] - points[index]))
        if not cuts:
            return None
        positions = [float(np.dot(point - origin, direction)) for point in cuts]
        return min(positions), max(positions)

    interval_a, interval_b = interval(points_a, distances_a), interval(points_b, distances_b)
    if interval_a is None or interval_b is None:
        return "HUMAN_REVIEW"  # Shared vertex must be present; do not certify inconsistent math.
    lower, upper = max(interval_a[0], interval_b[0]), min(interval_a[1], interval_b[1])
    if lower > upper + numerical_epsilon:
        return "HUMAN_REVIEW"
    if lower < -numerical_epsilon or upper > numerical_epsilon:
        return "REJECTED"
    return "PASS"


def component_self_intersection(
    vertices: Sequence[Coordinate], triangles: Sequence[tuple[int, int, int]],
    *, maximum_pair_checks: int = 250000, numerical_epsilon_bu: float = 1e-9,
) -> dict[str, Any]:
    """Exhaustive triangle checks, allowing only exact shared topological features.

    Closed/winding consistency does not certify adjacent geometry. Shared-feature
    pairs are checked explicitly for coplanar fold or remote vertex intersections.
    No tolerance-expanded collider is manufactured. Budget exhaustion means REVIEW.
    """
    if maximum_pair_checks <= 0 or numerical_epsilon_bu < 0:
        raise ValueError("self-intersection guard requires positive budget and valid epsilon")
    points = np.asarray([[vertices[index] for index in triangle] for triangle in triangles])
    minima, maxima = points.min(axis=1), points.max(axis=1)
    extents = np.ptp(np.asarray(vertices), axis=0)
    axes = sorted(range(3), key=lambda axis: (-float(extents[axis]), axis))[:2]
    rectangles = [box(minima[i, axes[0]], minima[i, axes[1]],
                      maxima[i, axes[0]], maxima[i, axes[1]]) for i in range(len(triangles))]
    tree = STRtree(rectangles)
    checked = adjacent = 0
    for first, rectangle in enumerate(rectangles):
        for raw_second in sorted(tree.query(rectangle).tolist()):
            second = int(raw_second)
            if second <= first or any(minima[first, axis] > maxima[second, axis]
                                      or minima[second, axis] > maxima[first, axis]
                                      for axis in range(3)):
                continue
            if checked >= maximum_pair_checks:
                return {"status": "HUMAN_REVIEW", "reason": "SELF_INTERSECTION_GUARD_BUDGET",
                        "pair_checks": checked, "shared_feature_pairs_checked": adjacent}
            checked += 1
            common = set(triangles[first]) & set(triangles[second])
            if common:
                adjacent += 1
                status = _shared_feature_intersection(
                    tuple(vertices[index] for index in triangles[first]),  # type: ignore[arg-type]
                    tuple(vertices[index] for index in triangles[second]),  # type: ignore[arg-type]
                    tuple(vertices[index] for index in sorted(common)), numerical_epsilon_bu,
                )
                if status != "PASS":
                    return {
                        "status": status,
                        "reason": "SHARED_FEATURE_SELF_INTERSECTION" if status == "REJECTED"
                        else "SHARED_FEATURE_INTERSECTION_NUMERIC_REVIEW",
                        "triangle_indices": [first, second], "pair_checks": checked,
                        "shared_feature_pairs_checked": adjacent,
                    }
                continue
            if triangle_distance(
                tuple(vertices[index] for index in triangles[first]),  # type: ignore[arg-type]
                tuple(vertices[index] for index in triangles[second]),  # type: ignore[arg-type]
                numerical_epsilon=numerical_epsilon_bu,
            ) <= numerical_epsilon_bu:
                return {"status": "REJECTED", "reason": "NONADJACENT_SELF_INTERSECTION",
                        "triangle_indices": [first, second], "pair_checks": checked,
                        "shared_feature_pairs_checked": adjacent}
    return {"status": "PASS", "pair_checks": checked, "shared_feature_pairs_checked": adjacent,
            "basis": "EXHAUSTIVE_TRIANGLE_CHECK_WITH_SHARED_FEATURE_INTERSECTION_GUARD"}


def _footprint(row: Mapping[str, Any]) -> Any:
    vertices = row["vertices"]
    polygons = [Polygon([(vertices[index][0], vertices[index][1]) for index in triangle])
                for triangle in row["triangles"]]
    return unary_union([polygon for polygon in polygons if polygon.area > 0])


def _contained(vertices: Sequence[Coordinate], triangles: Sequence[tuple[int, int, int]],
               footprint: Any) -> bool:
    if not all(footprint.covers(Point(point[0], point[1])) for point in vertices):
        return False
    for triangle in triangles:
        polygon = Polygon([(vertices[index][0], vertices[index][1]) for index in triangle])
        if polygon.area > 0 and not footprint.covers(polygon):
            return False
    return True


def review_obstacle_volumes(
    evidence: Mapping[str, Any], audit: Mapping[str, Any], role_authorization: Mapping[str, Any],
    *, scale: ArchitecturalScale, policy: PhysicalPolicy,
    floors: Sequence[FloorAuthority] = (), maximum_self_intersection_pairs: int = 250000,
) -> dict[str, Any]:
    """Approve only exact source components; unresolved outer pieces retain REVIEW."""
    scale = ArchitecturalScale.model_validate(scale)
    policy = PhysicalPolicy.model_validate(policy)
    source_hash = scale.source_asset_sha256
    validate_source_evidence(evidence, expected_source_sha256=source_hash,
                             expected_audit_content_sha256=content_sha256(audit))
    if (
        audit.get("source_sha256") != source_hash
        or role_authorization.get("schema_version") != "geometry-role-authorization-v1"
        or role_authorization.get("source_sha256") != source_hash
        or role_authorization.get("authority_scope") != "SEMANTIC_ROLE_ONLY"
        or not role_authorization.get("approval_id")
    ):
        raise ValueError("obstacle roles require independent source-bound semantic authorization")
    if policy.authority != Authority.APPROVED:
        raise ValueError("component collider approval requires approved body/clearance policy")
    approved_roles = set(role_authorization["approved_obstacle_ids"])
    floor_map = {floor.floor_id: FloorAuthority.model_validate(floor) for floor in floors}
    meshes = {mesh["mesh_id"]: mesh for mesh in evidence["meshes"]}
    rows = {row["object"]: row for row in audit["objects"]}
    obstacles = []
    approved_surfaces = []
    for region in evidence["regions"]:
        if region["kind"] != "OBSTACLE_COMPONENT_SELECTION":
            continue
        identity = region["annotation_object_id"]
        row = rows[identity]
        props = row["custom_properties"]
        if props.get("semantic_class") != "OBSTACLE" or identity not in approved_roles:
            raise ValueError("source obstacle selection lacks approved explicit semantic binding")
        floor_id = props["floor_id"]
        floor = floor_map.get(floor_id)
        footprint = _footprint(row)
        if footprint.is_empty or not footprint.is_valid:
            raise ValueError("approved obstacle footprint is empty or malformed")
        components = []
        for selection in region["selections"]:
            mesh = meshes[selection["mesh_id"]]
            for component in mesh["components"]:
                if component["component_id"] not in selection["component_ids"]:
                    continue
                vertices, triangles, provenance = component_geometry(mesh, component)
                topology = component_topology(vertices, triangles)
                contained = _contained(vertices, triangles, footprint)
                floor_overlap = None
                if floor is not None:
                    height = (float(policy.body_height_m or 0)
                              + float(policy.body_clearance_m or 0)) / scale.metres_per_blender_unit
                    floor_overlap = (max(point[2] for point in vertices) >= floor.point[2]
                                     and min(point[2] for point in vertices)
                                     <= floor.point[2] + height)
                safety = {"status": "NOT_RUN_INVALID_TOPOLOGY_OR_OWNERSHIP"}
                if contained and topology["closed_consistent_nonzero_volume"]:
                    safety = component_self_intersection(
                        vertices, triangles, maximum_pair_checks=maximum_self_intersection_pairs
                    )
                reasons = []
                if not contained:
                    reasons.append("SOURCE_COMPONENT_NOT_ENTIRELY_IN_APPROVED_FOOTPRINT")
                if not topology["closed_consistent_nonzero_volume"]:
                    reasons.append("SOURCE_COMPONENT_NOT_CLOSED_CONSISTENT_VOLUME")
                if safety["status"] != "PASS":
                    reasons.append(str(safety.get("reason", "SELF_INTERSECTION_NOT_CERTIFIED")))
                if floor is None or floor.authority != Authority.APPROVED:
                    reasons.append("SOURCE_FLOOR_AUTHORITY_PENDING")
                elif not floor_overlap:
                    reasons.append("SOURCE_COMPONENT_OUTSIDE_FLOOR_BODY_ENVELOPE")
                record = {
                    "component_id": component["component_id"],
                    "source_object_id": mesh["source_object_id"],
                    "source_geometry_sha256": mesh["geometry_sha256"],
                    "bounds_bu": component["bounds_bu"],
                    "bounds_m": {key: [scale.to_metres(value) for value in values]
                                 for key, values in component["bounds_bu"].items()},
                    "footprint_contained": contained,
                    "topology": {
                        **topology,
                        "signed_volume_m3": scale.to_cubic_metres(topology["signed_volume_bu3"]),
                        "enclosed_volume_m3": scale.to_cubic_metres(
                            topology["enclosed_volume_bu3"]
                        ),
                    },
                    "self_intersection": safety,
                    "floor_id": floor_id,
                    "floor_body_envelope_overlap": floor_overlap,
                    "status": "APPROVED" if not reasons else "HUMAN_REVIEW",
                    "unresolved_reasons": reasons,
                    "provenance": provenance,
                    "hidden_render": mesh["hidden_render"],
                    "hidden_viewport": mesh["hidden_viewport"],
                    "visibility_ownership": "APPROVED_OBSTACLE_ROLE_SOURCE_COMPONENT",
                }
                if not reasons:
                    surface = GeometrySurface(
                        surface_id=f"{identity}:source:{mesh['mesh_id'][:12]}:"
                        f"{component['component_id']}",
                        source_object_id=mesh["source_object_id"],
                        source_face_indices=tuple(sorted(set(provenance[
                            "triangle_source_face_indices"]))),
                        role=GeometryRole.OBSTACLE, floor_ids=(floor_id,),
                        vertices=vertices, triangles=triangles,
                        semantic_authority=Authority.APPROVED,
                        physical_authority=Authority.APPROVED, support=GeometrySupport.VOLUME,
                        evidence_ids=(f"source:{source_hash}", f"mesh:{mesh['geometry_sha256']}",
                                      f"semantic-role:{role_authorization['approval_id']}",
                                      "USER_PHYSICAL_POLICY_APPROVAL_2026_10_06"),
                        approval_id="SOURCE_BOUND_CLOSED_COMPONENT_PHYSICAL_APPROVAL_20261006",
                        blocks_movement=True, occludes_visibility=True,
                    )
                    record["surface_id"] = surface.surface_id
                    approved_surfaces.append(surface.model_dump(mode="json"))
                components.append(record)
        count = sum(component["status"] == "APPROVED" for component in components)
        obstacles.append({
            "obstacle_id": identity, "floor_id": floor_id,
            "semantic_authority": "APPROVED", "source_selection_complete":
            region["selection_complete"], "whole_obstacle_authority": "HUMAN_REVIEW",
            "known_component_authority": "PARTIAL_APPROVED" if count else "HUMAN_REVIEW",
            "approved_component_count": count,
            "components": components,
            "unresolved_reasons": ["ANNOTATION_DOES_NOT_CERTIFY_COMPLETE_OBSTACLE_VOLUME"]
            + ([] if region["selection_complete"] else ["SOURCE_REGION_SELECTION_INCOMPLETE"]),
        })
    return {
        "schema_version": "obstacle-volume-authority-v1", "source_sha256": source_hash,
        "architectural_scale": scale.model_dump(mode="json"),
        "policy_id": policy.policy_id, "policy_content_sha256": content_sha256(
            policy.model_dump(mode="json")),
        "source_evidence_content_sha256": content_sha256(evidence),
        "audit_content_sha256": content_sha256(audit),
        "role_authorization_content_sha256": content_sha256(role_authorization),
        "obstacle_count": len(obstacles),
        "approved_component_count": len(approved_surfaces),
        "obstacles_with_approved_components": sum(row["approved_component_count"] > 0
                                                 for row in obstacles),
        "obstacles": obstacles, "approved_surfaces": approved_surfaces,
        "scope": "KNOWN_SOURCE_COMPONENT_COLLISION_EVIDENCE_ONLY",
        "free_space_certified": False, "whole_obstacle_volume_certified": False,
        "source_geometry_modified": False, "gt_used": False,
    }


def approved_obstacle_surfaces(report: Mapping[str, Any]) -> tuple[GeometrySurface, ...]:
    """Load exact components for a provider; a caller still needs physical scope gates."""
    if report.get("schema_version") != "obstacle-volume-authority-v1":
        raise ValueError("unsupported obstacle volume authority report")
    result = tuple(GeometrySurface.model_validate_json(json.dumps(surface)) for surface in
                   report["approved_surfaces"])
    if any(surface.physical_authority != Authority.APPROVED
           or surface.support != GeometrySupport.VOLUME for surface in result):
        raise ValueError("approved component report contains unapproved/open collider")
    return tuple(sorted(result, key=lambda surface: surface.surface_id))


def review_portal_clearance(
    evidence: Mapping[str, Any], audit: Mapping[str, Any], *, scale: ArchitecturalScale,
    policy: PhysicalPolicy,
) -> dict[str, Any]:
    """Report annotation conflicts separately from unresolved actual source apertures."""
    scale = ArchitecturalScale.model_validate(scale)
    policy = PhysicalPolicy.model_validate(policy)
    validate_source_evidence(evidence, expected_source_sha256=scale.source_asset_sha256,
                             expected_audit_content_sha256=content_sha256(audit))
    if policy.authority != Authority.APPROVED:
        raise ValueError("portal clearance review requires approved physical policy")
    radius = float(policy.body_radius_m or 0)
    horizontal = max(float(policy.body_clearance_m or 0),
                     float(policy.portal_horizontal_clearance_m or 0))
    vertical = max(float(policy.body_clearance_m or 0),
                   float(policy.portal_vertical_clearance_m or 0))
    required_width = 2 * (radius + horizontal)
    required_height = float(policy.body_height_m or 0) + vertical
    obstacles = {row["object"]: row for row in audit["objects"]
                 if row["custom_properties"].get("semantic_class") == "OBSTACLE"}
    portals = {row["object"]: row for row in audit["objects"]
               if row["custom_properties"].get("semantic_class") == "PORTAL"}
    footprints = {identity: _footprint(row) for identity, row in obstacles.items()}
    regions = {region["region_id"]: region for region in evidence["regions"]}
    meshes = {mesh["mesh_id"]: mesh for mesh in evidence["meshes"]}
    records = []
    for portal_id, portal in sorted(portals.items()):
        footprint = _footprint(portal)
        pv = portal["vertices"]
        pb = {"minimum": [min(point[axis] for point in pv) for axis in range(3)],
              "maximum": [max(point[axis] for point in pv) for axis in range(3)]}
        conflicts = []
        for obstacle_id, obstacle in sorted(obstacles.items()):
            ov = obstacle["vertices"]
            if (max(point[2] for point in ov) < pb["minimum"][2]
                    or min(point[2] for point in ov) > pb["maximum"][2]):
                continue
            intersection = footprint.intersection(footprints[obstacle_id])
            if intersection.area > 0:
                conflicts.append((obstacle_id, intersection.area))
        if not conflicts:
            continue
        normal = portal["custom_properties"].get("portal_normal")
        reasons = ["ACTUAL_APERTURE_OWNERSHIP_AND_HEIGHT_UNAPPROVED"]
        measurement: dict[str, Any] = {"status": "UNMEASURED"}
        if normal is None:
            reasons.append("PORTAL_NORMAL_NOT_DECLARED")
        elif (not isinstance(normal, (list, tuple)) or len(normal) != 3
              or not all(_finite(value) for value in normal)
              or normal[2] != 0 or math.hypot(normal[0], normal[1]) == 0):
            reasons.append("PORTAL_NORMAL_INVALID")
        else:
            norm = math.hypot(normal[0], normal[1])
            tangent = (-normal[1] / norm, normal[0] / norm)
            center = [(pb["minimum"][axis] + pb["maximum"][axis]) / 2 for axis in range(3)]
            offsets = [sum((point[axis] - center[axis]) * tangent[axis] for axis in range(2))
                       for point in pv]
            ends = [[center[axis] + offset * tangent[axis] for axis in range(2)]
                    for offset in (min(offsets), max(offsets))]
            section = LineString(ends).intersection(footprint)
            blocked = section.intersection(unary_union([footprints[identity]
                                                       for identity, _ in conflicts]))
            free = section.difference(blocked)
            pieces = list(free.geoms) if hasattr(free, "geoms") else [free]
            clear = max((piece.length for piece in pieces), default=0)
            width = scale.to_metres(section.length)
            height = scale.to_metres(pb["maximum"][2] - pb["minimum"][2])
            measurement = {
                "status": "ANNOTATION_CENTER_SECTION_ONLY", "center_bu": center,
                "center_m": [scale.to_metres(value) for value in center],
                "normal_declared": normal, "width_bu": section.length, "width_m": width,
                "height_bu": pb["maximum"][2] - pb["minimum"][2], "height_m": height,
                "blocked_width_bu": blocked.length,
                "blocked_width_m": scale.to_metres(blocked.length),
                "effective_max_contiguous_width_bu": clear,
                "effective_max_contiguous_width_m": scale.to_metres(clear),
                "annotation_body_feasibility": "PASS" if (
                    scale.to_metres(clear) >= required_width and height >= required_height
                ) else "FAIL",
            }
            if width < required_width:
                reasons.append("ANNOTATION_WIDTH_BELOW_APPROVED_BODY_REQUIREMENT")
        for obstacle_id, area in conflicts:
            selections = regions.get(obstacle_id, {}).get("selections", [])
            source_review = []
            for selection in selections:
                mesh = meshes[selection["mesh_id"]]
                # These are precise viewport review references, not inferred roles
                # or an aperture collider. Keep only actual source triangle bounds
                # overlapping this declared portal, including contact boundaries.
                local_indices = []
                for index in selection["source_triangle_indices"]:
                    points = [mesh["vertices"][vertex] for vertex in mesh["triangles"][index]]
                    if all(min(point[axis] for point in points) <= pb["maximum"][axis]
                           and max(point[axis] for point in points) >= pb["minimum"][axis]
                           for axis in range(3)):
                        local_indices.append(index)
                if not local_indices:
                    continue
                source_review.append({
                    "source_object_id": mesh["source_object_id"],
                    "source_mesh_id": mesh["mesh_id"],
                    "source_face_indices": sorted({mesh["triangle_source_face_indices"][index]
                                                   for index in local_indices}),
                    "source_triangle_indices": local_indices,
                    "semantic_role": "UNCLASSIFIED_SOURCE_CONTEXT_NOT_APERTURE_APPROVAL",
                })
            records.append({
                "portal_id": portal_id, "obstacle_id": obstacle_id,
                "floor_id": portal["custom_properties"]["floor_id"],
                "status": "HUMAN_REVIEW", "repair_applied": False,
                "annotation_overlap_bu2": area,
                "annotation_overlap_m2": scale.to_square_metres(area),
                "annotation_center_section": measurement,
                "actual_source_bound_opening": None,
                "actual_effective_clear_width_m": None, "actual_clear_height_m": None,
                "physical_body_feasibility": "UNDETERMINED_REVIEW",
                "required_width_m": required_width, "required_height_m": required_height,
                "bounds_bu": pb,
                "bounds_m": {key: [scale.to_metres(value) for value in values]
                             for key, values in pb.items()},
                "source_face_review": source_review,
                "remaining_decisions": reasons,
                "screenshot_ready": {
                    "select_annotation_objects": [portal_id, obstacle_id],
                    "focus_bu": [(pb["minimum"][axis] + pb["maximum"][axis]) / 2
                                 for axis in range(3)],
                    "declared_normal": normal,
                    "show_source_faces": source_review,
                },
            })
    return {
        "schema_version": "portal-body-clearance-review-v1",
        "source_sha256": scale.source_asset_sha256,
        "required_width_m": required_width, "required_height_m": required_height,
        "clearance_combination": "MAX_BODY_PORTAL_EXTRAS_NOT_SUM",
        "pairs": records, "pair_count": len(records),
        "approved_pair_count": 0, "human_review_count": len(records),
        "actual_aperture_authority": "HUMAN_REVIEW", "scene_geometry_modified": False,
        "gt_used": False,
    }
