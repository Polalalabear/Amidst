"""Exact source-mesh floor and stair diagnostics, without physical certification.

Annotation planes and ramps are compared with independent source triangles.  A
positive local surface measurement does not approve scale, body clearance, slab
openings or a complete navigation scope.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from amidst.architectural_scale import ArchitecturalScale, scale_for_scene_config
from amidst.geometry_physical_review import (
    Triangle,
    Vector,
    _cross,
    _point_triangle_distance,
    _sub,
)
from amidst.scene_validation import (
    _GEOMETRY_BUDGET,
    GeometryBudgetExceeded,
    _intersections,
    _union_area,
)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _dual_unit_measurements(
    document: dict[str, Any], scale: ArchitecturalScale,
) -> dict[str, Any]:
    """Append metre evidence while preserving every original native measurement."""
    def convert(value: Any, *, area: bool = False) -> Any:
        if value is None:
            return None
        if isinstance(value, list):
            return [convert(item, area=area) for item in value]
        return scale.to_square_metres(value) if area else scale.to_metres(value)

    def walk(value: Any) -> Any:
        if isinstance(value, list):
            return [walk(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: walk(item) for key, item in value.items()}
        for key, item in value.items():
            if key.endswith("_units2"):
                result[key.removesuffix("_units2") + "_m2"] = convert(item, area=True)
            elif key.endswith("_units"):
                result[key.removesuffix("_units") + "_m"] = convert(item)
        return result

    return {key: walk(value) for key, value in document.items()}


def _number(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite numeric evidence")
    if value < 0 or (positive and value <= 0):
        raise ValueError(f"{label} must be {'positive' if positive else 'nonnegative'}")
    return float(value)


def _vector(value: Any) -> Vector:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in value
        )
    ):
        raise ValueError("world coordinate must contain three finite numbers")
    return float(value[0]), float(value[1]), float(value[2])


def _plane_height_units(plane: Mapping[str, Any], unit_scale: float) -> float:
    """Prefer retained BU only after checking its metre representation agrees."""
    metres = plane["height_m"]
    if (
        isinstance(metres, bool)
        or not isinstance(metres, (int, float))
        or not math.isfinite(metres)
    ):
        raise ValueError("proposed floor height must be finite")
    native = plane.get("height_bu")
    if native is None:
        return float(metres) / unit_scale
    if (
        isinstance(native, bool)
        or not isinstance(native, (int, float))
        or not math.isfinite(native)
        or not math.isclose(native * unit_scale, metres, abs_tol=1e-12, rel_tol=1e-12)
    ):
        raise ValueError("proposed floor height BU/metre representations disagree")
    return float(native)


@dataclass(frozen=True)
class _Face:
    object_id: str
    source_face_index: int
    triangle: Triangle

    @property
    def footprint(self) -> list[tuple[float, float]]:
        return [(p[0], p[1]) for p in self.triangle]

    @property
    def z_range(self) -> tuple[float, float]:
        return min(p[2] for p in self.triangle), max(p[2] for p in self.triangle)

    @property
    def horizontal_normal(self) -> float:
        normal = _cross(
            _sub(self.triangle[1], self.triangle[0]), _sub(self.triangle[2], self.triangle[0])
        )
        return abs(normal[2]) / math.hypot(*normal)

    @property
    def centre_z(self) -> float:
        return sum(p[2] for p in self.triangle) / 3


def _triangle(indices: Any, points: tuple[Vector, ...]) -> Triangle:
    if (
        not isinstance(indices, (list, tuple))
        or len(indices) != 3
        or any(
            isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= len(points)
            for i in indices
        )
        or len(set(indices)) != 3
    ):
        raise ValueError("source triangle requires three distinct valid indices")
    face = points[indices[0]], points[indices[1]], points[indices[2]]
    normal = _cross(_sub(face[1], face[0]), _sub(face[2], face[0]))
    if not all(math.isfinite(v) for v in normal) or math.hypot(*normal) == 0:
        raise ValueError("source triangle must be finite and nondegenerate")
    return face


def _region_faces(region: Mapping[str, Any], maximum: int) -> list[_Face]:
    patches = region.get("patches")
    if not isinstance(patches, list):
        raise ValueError("source region patches must be an array")
    result: list[_Face] = []
    identities: set[tuple[str, int, tuple[Vector, ...]]] = set()
    for patch in patches:
        if not isinstance(patch, Mapping):
            raise ValueError("source patch must be an object")
        expected = patch.get("geometry_sha256")
        actual = _digest({k: v for k, v in patch.items() if k != "geometry_sha256"})
        if expected != actual:
            raise ValueError("source patch geometry_sha256 differs from actual content")
        object_id = patch.get("source_object_id")
        if not isinstance(object_id, str) or not object_id.strip():
            raise ValueError("source patch object identity is required")
        raw_points, triangles = patch.get("vertices"), patch.get("triangles")
        source_faces, triangle_sources = (
            patch.get("source_face_indices"),
            patch.get("triangle_source_face_indices"),
        )
        if (
            not isinstance(raw_points, list)
            or not isinstance(triangles, list)
            or not (isinstance(source_faces, list) and isinstance(triangle_sources, list))
        ):
            raise ValueError("source vertices, triangles and face identities must be arrays")
        if len(triangles) != len(triangle_sources) or any(
            isinstance(i, bool) or not isinstance(i, int) or i < 0 for i in source_faces
        ):
            raise ValueError("source face identity mapping is invalid")
        points = tuple(_vector(p) for p in raw_points)
        for indices, source_index in zip(triangles, triangle_sources, strict=True):
            if (
                isinstance(source_index, bool)
                or not isinstance(source_index, int)
                or (source_index not in source_faces)
            ):
                raise ValueError("triangle source face must refer to an exported source face")
            face = _triangle(indices, points)
            identity = object_id, source_index, tuple(sorted(face))
            if identity in identities:
                raise ValueError("duplicate source triangle identity in region")
            identities.add(identity)
            result.append(_Face(object_id, source_index, face))
            if len(result) > maximum:
                raise GeometryBudgetExceeded("source region exceeds configured triangle budget")
    return sorted(result, key=lambda f: (f.object_id, f.source_face_index, f.triangle))


def _annotation_faces(row: Mapping[str, Any]) -> list[Triangle]:
    points = tuple(_vector(p) for p in row.get("vertices", []))
    return sorted(
        (_triangle(indices, points) for indices in row.get("triangles", [])),
        key=lambda face: tuple(sorted(face)),
    )


def _props(row: Mapping[str, Any]) -> Mapping[str, Any]:
    properties = row.get("custom_properties", {})
    if not isinstance(properties, Mapping):
        raise ValueError("annotation custom_properties must be an object")
    wrapped = properties.get("declared_semantic_fields_unreviewed", properties)
    if not isinstance(wrapped, Mapping):
        raise ValueError("declared semantic fields must be an object")
    return wrapped


def _floor(row: Mapping[str, Any]) -> str | None:
    declared, explicit = row.get("declared_floor_label"), _props(row).get("floor_id")
    if declared is not None and explicit is not None and declared != explicit:
        raise ValueError("annotation declares conflicting floor identities")
    floor = explicit or declared
    if floor is not None and not isinstance(floor, str):
        raise ValueError("floor identity must be a string")
    return floor


def _layers(faces: list[_Face], normal_minimum: float, tolerance: float) -> list[list[_Face]]:
    horizontal = sorted(
        (f for f in faces if f.horizontal_normal >= normal_minimum),
        key=lambda f: (f.centre_z, f.object_id, f.source_face_index, f.triangle),
    )
    result: list[list[_Face]] = []
    minimum_z: float | None = None
    for face in horizontal:
        if minimum_z is None or face.centre_z - minimum_z > tolerance:
            result.append([])
            minimum_z = face.centre_z
        result[-1].append(face)
    return result


def _ray_height(x: float, y: float, face: Triangle, epsilon: float) -> float | None:
    a, b, c = face
    denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(denominator) <= epsilon:
        return None
    wa = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
    wb = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
    if min(wa, wb, 1 - wa - wb) < -epsilon:
        return None
    return wa * a[2] + wb * b[2] + (1 - wa - wb) * c[2]


def _source_summaries(faces: list[_Face]) -> list[dict[str, Any]]:
    by_object: dict[str, list[_Face]] = {}
    for face in faces:
        by_object.setdefault(face.object_id, []).append(face)
    return [
        {
            "object_id": object_id,
            "source_face_indices": sorted({f.source_face_index for f in rows}),
            "z_range_units": [min(f.z_range[0] for f in rows), max(f.z_range[1] for f in rows)],
        }
        for object_id, rows in sorted(by_object.items())
    ]


def _partial_floor_probes(
    row: Mapping[str, Any],
    faces: list[_Face],
    config: Mapping[str, Any],
    settings: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Retain point evidence when exact area coverage exceeds its budget."""
    epsilon = config["tolerances"]["numeric_epsilon"]
    horizontal = [
        face for face in faces if face.horizontal_normal >= settings["horizontal_normal_abs_z_min"]
    ]
    probes = []
    for triangle in _annotation_faces(row):
        x, y = sum(p[0] for p in triangle) / 3, sum(p[1] for p in triangle) / 3
        hits = [
            {"object_id": face.object_id, "source_face_index": face.source_face_index, "z_units": z}
            for face in horizontal
            if (z := _ray_height(x, y, face.triangle, epsilon)) is not None
        ]
        probes.append(
            {
                "xy_units": [x, y],
                "actual_source_hits": hits,
                "authority": "POINT_SUPPORT_ONLY_NOT_AREA_COVERAGE_CERTIFICATION",
            }
        )
    return probes


def _floor_review(
    row: Mapping[str, Any],
    region: Mapping[str, Any],
    faces: list[_Face],
    config: Mapping[str, Any],
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    epsilon = config["tolerances"]["numeric_epsilon"]
    annotation = _annotation_faces(row)
    polygons = [[(p[0], p[1]) for p in face] for face in annotation]
    area = _union_area(polygons, epsilon)
    if area <= epsilon:
        raise ValueError("walkable annotation has no positive XY surface area")
    floor_id = _floor(row)
    proposed = config["floor_planes"].get(floor_id, {}).get("height_m")
    if proposed is None:
        raise ValueError("walkable floor lacks a configured proposed plane")
    proposed_units = _plane_height_units(
        config["floor_planes"][floor_id], config["meters_per_blender_unit"],
    )
    physical_layers: list[dict[str, Any]] = []
    for layer in _layers(
        faces, settings["horizontal_normal_abs_z_min"], settings["horizontal_layer_tolerance_units"]
    ):
        clipped = _intersections(polygons, [f.footprint for f in layer], epsilon)
        overlap = _union_area(clipped, epsilon)
        if overlap <= epsilon:
            continue
        # The exact footprint union is the coverage measurement; a probe is only
        # independent point support evidence and cannot fill a polygon hole.
        probes = []
        for face in annotation:
            x, y = sum(p[0] for p in face) / 3, sum(p[1] for p in face) / 3
            hits = [
                (f, z) for f in layer if (z := _ray_height(x, y, f.triangle, epsilon)) is not None
            ]
            probes.append(
                {
                    "xy_units": [x, y],
                    "hits": [
                        {
                            "object_id": f.object_id,
                            "source_face_index": f.source_face_index,
                            "z_units": z,
                        }
                        for f, z in hits
                    ],
                }
            )
        z_values = [f.centre_z for f in layer]
        physical_layers.append(
            {
                "z_range_units": [
                    min(f.z_range[0] for f in layer),
                    max(f.z_range[1] for f in layer),
                ],
                "representative_z_units": sum(z_values) / len(z_values),
                "coverage_ratio": min(1.0, overlap / area),
                "covered_area_units2": overlap,
                "source_objects": _source_summaries(layer),
                "triangle_centroid_ray_probes": probes,
            }
        )
    # Floating clipping residuals must not prefer a slab underside over its
    # equally covering top face. Preserve every layer and compare equivalent
    # coverage within the existing numeric epsilon before plane proximity.
    maximum_coverage = max((layer["coverage_ratio"] for layer in physical_layers), default=0)
    dominant = max(
        (
            layer
            for layer in physical_layers
            if layer["coverage_ratio"] >= maximum_coverage - epsilon
        ),
        key=lambda layer: -abs(layer["representative_z_units"] - proposed_units),
        default=None,
    )
    reasons = []
    if region.get("complete") is not True:
        reasons.append("SOURCE_REGION_SELECTION_INCOMPLETE")
    if dominant is None:
        reasons.append("NO_ACTUAL_HORIZONTAL_SUPPORT_IN_CONFIGURED_BAND")
    elif dominant["coverage_ratio"] < config["tolerances"]["coverage_pass_ratio"]:
        reasons.append("INCOMPLETE_ACTUAL_WALKABLE_SUPPORT")
    offset = None if dominant is None else proposed_units - dominant["representative_z_units"]
    tolerance_units = config["tolerances"]["floor_height_m"] / config["meters_per_blender_unit"]
    if dominant is not None and any(
        abs(z - proposed_units) > tolerance_units for z in dominant["z_range_units"]
    ):
        reasons.append("PROPOSED_PLANE_DIFFERS_FROM_ACTUAL_MESH_SUPPORT")
    return {
        "object_id": row["object"],
        "floor_id": floor_id,
        "status": "HUMAN_REVIEW" if reasons else "HIGH_CONFIDENCE",
        "proposed_plane_z_units": proposed_units,
        "annotation_z_range_units": [
            min(p[2] for f in annotation for p in f),
            max(p[2] for f in annotation for p in f),
        ],
        "annotation_area_units2": area,
        "physical_support_layers": physical_layers,
        "dominant_support": dominant,
        "proposed_minus_actual_z_units": offset,
        "reason_codes": reasons,
        "physical_floor_approved": False,
    }


def _horizontal_components(faces: list[_Face]) -> list[list[_Face]]:
    # Only a shared full edge joins support. Point contact or a bounding envelope
    # cannot create a stair landing or silently bridge missing geometry.
    edge_faces: dict[tuple[Vector, Vector], list[int]] = {}
    for index, face in enumerate(faces):
        for a, b in zip(face.triangle, (*face.triangle[1:], face.triangle[0]), strict=True):
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(index)
    neighbors: dict[int, set[int]] = {i: set() for i in range(len(faces))}
    for indices in edge_faces.values():
        for i in indices:
            neighbors[i].update(indices)
    unseen = set(neighbors)
    result = []
    while unseen:
        pending = [min(unseen)]
        component: set[int] = set()
        while pending:
            index = pending.pop()
            if index not in component:
                component.add(index)
                pending.extend(sorted(neighbors[index] - component, reverse=True))
        unseen -= component
        result.append([faces[i] for i in sorted(component)])
    return result


def _stair_review(
    stair_id: str,
    rows: list[Mapping[str, Any]],
    region: Mapping[str, Any],
    faces: list[_Face],
    config: Mapping[str, Any],
    settings: Mapping[str, Any],
    *,
    scale_approved: bool = False,
) -> dict[str, Any]:
    roles: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        role = _props(row).get("stair_role")
        if not isinstance(role, str):
            raise ValueError("stair role identity must be explicit")
        if role in roles:
            raise ValueError("duplicate stair role identity")
        roles[role] = row
    missing = [role for role in ("ENTRY", "PATH", "EXIT") if role not in roles]
    if missing:
        return {
            "stair_id": stair_id,
            "status": "HUMAN_REVIEW",
            "reason_codes": [f"MISSING_STAIR_{role}" for role in missing],
            "connectivity_created": False,
            "geometry_repaired": False,
        }
    path = roles["PATH"]
    props = _props(path)
    segments = props.get("path_segment_points_json")
    if not isinstance(segments, str):
        raise ValueError("stair path needs source-bound ordered segment metadata")
    parsed = json.loads(segments)
    if not isinstance(parsed, list) or len(parsed) < 2:
        raise ValueError("stair path needs at least two ordered source segments")
    endpoints: list[tuple[Vector, Vector]] = []
    for points in parsed:
        if not isinstance(points, list) or len(points) != 2:
            raise ValueError("each ordered source stair segment requires two endpoints")
        endpoints.append((_vector(points[0]), _vector(points[1])))
    join_tolerance = (
        config["tolerances"]["stair_join_distance_m"] / (config["meters_per_blender_unit"])
    )
    horizontal = [
        f for f in faces if f.horizontal_normal >= settings["horizontal_normal_abs_z_min"]
    ]
    landing_measurements = []
    for lower, upper in zip(endpoints, endpoints[1:], strict=False):
        start, end = lower[1], upper[0]
        landing = []
        nearest_components = []
        for component in _horizontal_components(horizontal):
            start_distance = min(_point_triangle_distance(start, f.triangle) for f in component)
            end_distance = min(_point_triangle_distance(end, f.triangle) for f in component)
            nearest_components.append(
                {
                    "source_objects": _source_summaries(component),
                    "lower_endpoint_distance_units": start_distance,
                    "upper_endpoint_distance_units": end_distance,
                    "supports_both_proxy_endpoints": max(start_distance, end_distance)
                    <= join_tolerance,
                }
            )
            if min(start_distance, end_distance) <= join_tolerance:
                landing.append(
                    {
                        "source_objects": _source_summaries(component),
                        "lower_endpoint_distance_units": start_distance,
                        "upper_endpoint_distance_units": end_distance,
                        "supports_both_proxy_endpoints": max(start_distance, end_distance)
                        <= join_tolerance,
                    }
                )
        landing_measurements.append(
            {
                "lower_proxy_end": list(start),
                "upper_proxy_start": list(end),
                "proxy_centerline_join_gap_units": math.dist(start, end),
                "actual_landing_components": landing,
                "actual_shared_landing_evidence": any(
                    c["supports_both_proxy_endpoints"] for c in landing
                ),
                "nearest_actual_horizontal_component": min(
                    nearest_components,
                    key=lambda c: max(
                        c["lower_endpoint_distance_units"], c["upper_endpoint_distance_units"]
                    ),
                    default=None,
                ),
            }
        )
    anchors = []
    for role in ("ENTRY", "EXIT"):
        row = roles[role]
        point = _vector(row["centroid"])
        floor_id = _floor(row)
        floor_plane = config["floor_planes"].get(floor_id, {}).get("height_m")
        contacts = sorted(
            ((_point_triangle_distance(point, f.triangle), f) for f in horizontal),
            key=lambda pair: (pair[0], pair[1].object_id, pair[1].source_face_index),
        )
        nearest = contacts[0] if contacts else None
        anchors.append(
            {
                "role": role,
                "object_id": row["object"],
                "floor_id": floor_id,
                "position_units": list(point),
                "proposed_floor_plane_z_units": None
                if floor_plane is None
                else _plane_height_units(
                    config["floor_planes"][floor_id], config["meters_per_blender_unit"],
                ),
                "actual_horizontal_surface_distance_units": None if nearest is None else nearest[0],
                "actual_source_object_id": None if nearest is None else nearest[1].object_id,
                "actual_source_face_index": None
                if nearest is None
                else nearest[1].source_face_index,
            }
        )
    reasons = [
        "BODY_CLEARANCE_POLICY_UNAPPROVED",
        "SLAB_OPENING_AUTHORITY_UNAPPROVED",
        "FLOOR_AUTHORITY_UNAPPROVED" if scale_approved else "FLOOR_AND_SCALE_AUTHORITY_UNAPPROVED",
    ]
    if region.get("complete") is not True:
        reasons.append("SOURCE_REGION_SELECTION_INCOMPLETE")
    if any(not join["actual_shared_landing_evidence"] for join in landing_measurements):
        reasons.append("NO_SHARED_ACTUAL_LANDING_SUPPORT_FOR_PROXY_JOIN")
    if any(
        anchor["actual_horizontal_surface_distance_units"] is None
        or anchor["actual_horizontal_surface_distance_units"] > join_tolerance
        for anchor in anchors
    ):
        reasons.append("PROXY_ANCHOR_DIFFERS_FROM_ACTUAL_HORIZONTAL_SUPPORT")
    return {
        "stair_id": stair_id,
        "status": "HUMAN_REVIEW",
        "floor_from": props.get("floor_from"),
        "floor_to": props.get("floor_to"),
        "ordered_proxy_segment_count": len(endpoints),
        "actual_source_triangle_count": len(faces),
        "actual_horizontal_triangle_count": len(horizontal),
        "actual_source_objects": _source_summaries(faces),
        "landing_join_measurements": landing_measurements,
        "anchors": anchors,
        "source_selection_complete": region.get("complete") is True,
        "opening_status": "HUMAN_REVIEW",
        "clearance_status": "HUMAN_REVIEW",
        "reason_codes": reasons,
        "connectivity_created": False,
        "geometry_repaired": False,
        "physical_stair_approved": False,
    }


def review_floor_stairs(
    audit: Mapping[str, Any],
    survey: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    camera_calibration: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare declared surfaces with independent source triangles, fail closed.

    Units remain native scene units; stored metre conversion is not architectural
    scale approval. Only explicit semantic roles select annotation objects.
    """
    source = audit.get("source_sha256")
    if not isinstance(source, str) or len(source) != 64 or survey.get("source_sha256") != source:
        raise ValueError("floor/stair source SHA binding mismatch")
    if survey.get("source_preserved") is not True:
        raise ValueError("physical source evidence must attest read-only source preservation")
    if survey.get("audit_content_sha256") != _digest(audit):
        raise ValueError("physical source evidence does not bind this annotation audit content")
    settings = config.get("floor_stair_review")
    if not isinstance(settings, Mapping):
        raise ValueError("floor_stair_review diagnostic configuration is required")
    normal_min = _number(
        settings.get("horizontal_normal_abs_z_min"), "horizontal_normal_abs_z_min", positive=True
    )
    if normal_min > 1:
        raise ValueError("horizontal normal threshold must be <= 1")
    _number(
        settings.get("horizontal_layer_tolerance_units"),
        "horizontal_layer_tolerance_units",
        positive=True,
    )
    maximum = settings.get("max_triangles_per_region")
    pair_maximum = settings.get("max_pair_intersections")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise ValueError("floor/stair complexity budgets must be positive integers")
    if isinstance(pair_maximum, bool) or not isinstance(pair_maximum, int) or pair_maximum <= 0:
        raise ValueError("floor/stair complexity budgets must be positive integers")
    _number(config.get("meters_per_blender_unit"), "meters_per_blender_unit", positive=True)
    architectural_scale = scale_for_scene_config(dict(config), source)
    regions = survey.get("regions")
    if not isinstance(regions, list):
        raise ValueError("physical survey regions must be an array")
    by_id: dict[tuple[str, str], Mapping[str, Any]] = {}
    for region in regions:
        if not isinstance(region, Mapping) or not isinstance(region.get("region_id"), str):
            raise ValueError("physical region requires a string identity")
        kind = region.get("kind")
        if not isinstance(kind, str):
            raise ValueError("physical region requires an explicit kind")
        key = kind, region["region_id"]
        if key in by_id:
            raise ValueError("physical survey contains a duplicate region identity")
        by_id[key] = region
    objects = audit.get("objects")
    if not isinstance(objects, list):
        raise ValueError("annotation audit objects must be an array")
    object_ids = [row.get("object") for row in objects]
    if len(set(object_ids)) != len(object_ids):
        raise ValueError("annotation audit contains duplicate object identities")
    walks = sorted(
        (row for row in objects if _props(row).get("semantic_class") == "WALKABLE"),
        key=lambda row: row["object"],
    )
    stair_groups: dict[str, list[Mapping[str, Any]]] = {}
    for row in objects:
        if _props(row).get("semantic_class") == "STAIR":
            stair_groups.setdefault(_props(row)["stair_id"], []).append(row)
    budget = dict(config["geometry_complexity"])
    budget["maximum_pair_intersections"] = pair_maximum
    token = _GEOMETRY_BUDGET.set(budget)
    floor_reviews, stair_reviews = [], []
    try:
        for row in walks:
            region = by_id.get(("FLOOR_SUPPORT", row["object"]))
            if region is None:
                floor_reviews.append(
                    {
                        "object_id": row["object"],
                        "floor_id": _floor(row),
                        "status": "HUMAN_REVIEW",
                        "reason_codes": ["MISSING_SOURCE_REGION"],
                        "physical_floor_approved": False,
                    }
                )
                continue
            faces: list[_Face] | None = None
            try:
                faces = _region_faces(region, maximum)
                result = _floor_review(row, region, faces, config, settings)
            except GeometryBudgetExceeded as error:
                result = {
                    "object_id": row["object"],
                    "floor_id": _floor(row),
                    "status": "HUMAN_REVIEW",
                    "reason_codes": ["GEOMETRY_BUDGET_EXCEEDED"],
                    "error": str(error),
                    "physical_floor_approved": False,
                    "partial_ray_evidence": []
                    if faces is None
                    else _partial_floor_probes(row, faces, config, settings),
                }
            floor_reviews.append(result)
        for stair_id, rows in sorted(stair_groups.items()):
            region = by_id.get(("STAIR_CONTEXT", stair_id))
            if region is None:
                stair_reviews.append(
                    {
                        "stair_id": stair_id,
                        "status": "HUMAN_REVIEW",
                        "reason_codes": ["MISSING_SOURCE_REGION"],
                        "physical_stair_approved": False,
                    }
                )
                continue
            try:
                result = _stair_review(
                    stair_id, rows, region, _region_faces(region, maximum), config, settings,
                    scale_approved=architectural_scale is not None,
                )
            except GeometryBudgetExceeded as error:
                result = {
                    "stair_id": stair_id,
                    "status": "HUMAN_REVIEW",
                    "reason_codes": ["GEOMETRY_BUDGET_EXCEEDED"],
                    "error": str(error),
                    "physical_stair_approved": False,
                }
            stair_reviews.append(result)
    finally:
        _GEOMETRY_BUDGET.reset(token)
    camera_reason = "CAMERA_PLANE_BINDING_UNAPPROVED"
    if camera_calibration is None:
        camera_reason = "NO_CAMERA_CALIBRATION_EVIDENCE"
    elif camera_calibration.get("source_asset_sha256") != source:
        camera_reason = "CAMERA_CALIBRATION_SOURCE_DIFFERS_FROM_SCHOOL_V3"
    annotation_context = []
    for row in sorted(objects, key=lambda row: row["object"]):
        role = _props(row).get("semantic_class")
        if role not in ("AREA", "PORTAL"):
            continue
        vertices = row.get("vertices", [])
        if not vertices:
            continue
        z_values = [_vector(point)[2] for point in vertices]
        annotation_context.append(
            {
                "object_id": row["object"],
                "role": role,
                "floor_id": _floor(row),
                "z_range_units": [min(z_values), max(z_values)],
                "authority": "ANNOTATION_CONTEXT_NOT_PHYSICAL_FLOOR_EVIDENCE",
            }
        )
    report = {
        "schema_version": "physical-floor-stair-review-v1",
        "source_sha256": source,
        "units": "BLENDER_NATIVE_SCENE_UNITS_WITH_EXPLICIT_METRE_CONVERSION",
        "meters_per_blender_unit": config["meters_per_blender_unit"],
        "floor_authority": "HUMAN_REVIEW",
        "stair_authority": "HUMAN_REVIEW",
        "scale_authority": "HUMAN_REVIEW" if architectural_scale is None else "APPROVED",
        "scale_approval_id": (
            None if architectural_scale is None else architectural_scale.approval_id
        ),
        "camera_plane_authority": "HUMAN_REVIEW",
        "camera_reason": camera_reason,
        "floor_reviews": floor_reviews,
        "stair_reviews": stair_reviews,
        "annotation_floor_context": annotation_context,
        "floor_counts": dict(sorted(Counter(row["status"] for row in floor_reviews).items())),
        "geometry_modified": False,
        "connectivity_created": False,
    }
    return report if architectural_scale is None else _dual_unit_measurements(
        report, architectural_scale,
    )
