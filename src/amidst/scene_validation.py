"""Read-only semantic diagnostics; never constructs inference navigation or assigns unlabeled roles.

Mesh footprints are geometric diagnostics, not walkability/collision authority. Unsupported
representations retain AABB broad-phase evidence and REVIEW rather than a physical PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from contextvars import ContextVar
from pathlib import Path
from typing import Any

Point = tuple[float, float]
Polygon = list[Point]
KINDS = ("AREA", "WALKABLE", "WALL", "OBSTACLE", "STAIR", "PORTAL", "CAM")
PHYSICAL = {"WALKABLE", "WALL", "OBSTACLE", "STAIR"}
AREA_DECLARATION_FIELDS = (
    "walkable",
    "exclusion_reason",
    "coverage_scope",
    "floor_from",
    "floor_to",
    "stair_id",
    "semantic_review_id",
)
_GEOMETRY_BUDGET: ContextVar[dict[str, int] | None] = ContextVar(
    "scene_validation_budget", default=None
)


class GeometryBudgetExceeded(ValueError):
    """Geometry is too complex for bounded diagnostic processing."""


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "configs/scene_validation_v1.json"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config: dict[str, Any] = json.loads(path.read_text())
    required = json.loads(DEFAULT_CONFIG.read_text())["tolerances"]
    for key in ("maximum_mesh_triangles", "maximum_union_polygons", "maximum_pair_intersections"):
        if (
            not isinstance(config.get("geometry_complexity", {}).get(key), int)
            or config["geometry_complexity"][key] <= 0
        ):
            raise ValueError("geometry complexity budgets must be positive integers")
    values = config.get("tolerances", {})
    if set(required) - set(values):
        raise ValueError("all diagnostic tolerances must be configured")
    for key, value in values.items():
        if key == "minimum_clearance_m" and value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"invalid tolerance {key}")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"tolerance must be finite and nonnegative: {key}")
    if values["numeric_epsilon"] <= 0:
        raise ValueError("numeric epsilon must be positive")
    for key in (
        "coverage_pass_ratio",
        "coverage_partial_ratio",
        "contact_overlap_ratio",
        "conflict_overlap_ratio",
        "portal_orientation_vertical_ratio",
    ):
        if values[key] > 1:
            raise ValueError(f"ratio must be <= 1: {key}")
    if values["coverage_partial_ratio"] > values["coverage_pass_ratio"]:
        raise ValueError("partial coverage cannot exceed pass coverage")
    scale = config.get("meters_per_blender_unit")
    if not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("meters_per_blender_unit must be finite and positive")
    return config


def _class(name: str) -> str | None:
    return next((kind for kind in KINDS if name.startswith(kind + "_")), None)


def _props(row: dict[str, Any]) -> dict[str, Any]:
    custom = row.get("custom_properties", {})
    return dict(custom.get("declared_semantic_fields_unreviewed", custom))


def _finite_vector(value: Any, length: int = 3) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == length
        and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            for v in value
        )
    )


def _safe_json(value: Any) -> Any:
    """Retain anomalous evidence as null rather than writing non-standard JSON numbers."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _safe_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe_json(item) for item in value]
    return value


def _floor(name: str) -> str | None:
    match = re.search(r"(?:^|_)(\d+F|B\d+)(?:_|$)", name)
    return match.group(1) if match else None


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _signed_area(poly: Polygon) -> float:
    return (
        sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1], strict=False)) / 2
    )


def _clip(subject: Polygon, clip: Polygon, eps: float) -> Polygon:
    """Convex clipping; inputs are triangles or explicitly declared convex proxies."""
    result = subject[:]
    direction = 1 if _signed_area(clip) >= 0 else -1
    for a, b in zip(clip, clip[1:] + clip[:1], strict=False):
        previous = result
        result = []
        if not previous:
            break
        for p, q in zip(previous, previous[1:] + previous[:1], strict=False):
            dp, dq = direction * _cross(a, b, p), direction * _cross(a, b, q)
            if dp >= -eps:
                result.append(p)
            if (dp >= -eps) != (dq >= -eps):
                weight = dp / (dp - dq)
                result.append((p[0] + weight * (q[0] - p[0]), p[1] + weight * (q[1] - p[1])))
    return result


def _union_area(polygons: list[Polygon], eps: float) -> float:
    """Exact planar polygon union by a piecewise-linear vertical sweep (no raster approximation)."""
    polygons = [p for p in polygons if len(p) >= 3 and abs(_signed_area(p)) > eps]
    polygons = list({tuple(sorted(poly)): poly for poly in polygons}.values())
    if len(polygons) > (_GEOMETRY_BUDGET.get() or {}).get("maximum_union_polygons", 1024):
        raise GeometryBudgetExceeded("polygon union exceeds configured complexity budget")
    edges = [edge for p in polygons for edge in zip(p, p[1:] + p[:1], strict=False)]
    xs = {p[0] for poly in polygons for p in poly}
    for (a, b), (c, d) in itertools.combinations(edges, 2):
        denominator = (b[0] - a[0]) * (d[1] - c[1]) - (b[1] - a[1]) * (d[0] - c[0])
        if abs(denominator) <= eps:
            continue
        t = ((c[0] - a[0]) * (d[1] - c[1]) - (c[1] - a[1]) * (d[0] - c[0])) / denominator
        u = ((c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])) / denominator
        if 0 < t < 1 and 0 < u < 1:
            xs.add(a[0] + t * (b[0] - a[0]))

    def width(x: float) -> float:
        intervals: list[tuple[float, float]] = []
        for poly in polygons:
            ys = []
            for a, b in zip(poly, poly[1:] + poly[:1], strict=False):
                if min(a[0], b[0]) <= x < max(a[0], b[0]):
                    ys.append(a[1] + (x - a[0]) * (b[1] - a[1]) / (b[0] - a[0]))
            ys.sort()
            intervals.extend(zip(ys[::2], ys[1::2], strict=False))
        total = 0.0
        high: float | None = None
        for low, upper in sorted(intervals):
            if high is None or low > high:
                total += upper - low
                high = upper
            elif upper > high:
                total += upper - high
                high = upper
        return total

    ordered = sorted(xs)
    return sum(
        (right - left)
        * (width(left + (right - left) / 4) + width(left + 3 * (right - left) / 4))
        / 2
        for left, right in zip(ordered, ordered[1:], strict=False)
    )


def _intersections(a: list[Polygon], b: list[Polygon], eps: float) -> list[Polygon]:
    if len(a) * len(b) > (_GEOMETRY_BUDGET.get() or {}).get("maximum_pair_intersections", 8192):
        raise GeometryBudgetExceeded("footprint intersections exceed configured complexity budget")
    return [_clip(left, right, eps) for left in a for right in b]


def _point_segment(p: Point, a: Point, b: Point) -> float:
    length = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    if length == 0:
        return math.dist(p, a)
    t = max(0, min(1, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / length))
    return math.dist(p, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))


def _inside(p: Point, poly: Polygon, eps: float) -> bool:
    # All footprint pieces are convex triangles/proxies.
    signs = [_cross(a, b, p) for a, b in zip(poly, poly[1:] + poly[:1], strict=False)]
    return bool(signs) and (min(signs) >= -eps or max(signs) <= eps)


def _distance(a: list[Polygon], b: list[Polygon], eps: float) -> float:
    if not a or not b:
        return math.inf
    if any(_inside(p, other, eps) for poly in a for p in poly for other in b):
        return 0.0
    if any(_inside(p, other, eps) for poly in b for p in poly for other in a):
        return 0.0
    if _union_area(_intersections(a, b, eps), eps) > eps:
        return 0.0
    return min(
        _point_segment(p, u, v)
        for left, right in itertools.chain(itertools.product(a, b), itertools.product(b, a))
        for p in left
        for u, v in zip(right, right[1:] + right[:1], strict=False)
    )


def _point_distance(p: list[float], row: dict[str, Any], eps: float) -> float:
    xy = (p[0], p[1])
    shapes: list[Polygon] = row["footprints"]
    if any(_inside(xy, poly, eps) for poly in shapes):
        horizontal = 0.0
    else:
        horizontal = min(
            (
                _point_segment(xy, a, b)
                for poly in shapes
                for a, b in zip(poly, poly[1:] + poly[:1], strict=False)
            ),
            default=math.inf,
        )
    return math.hypot(horizontal, abs(p[2] - row["plane_z_m"]))


def _segment_in_footprints(
    a: list[float], b: list[float], polygons: list[Polygon], eps: float
) -> bool:
    """Union of clipped segment intervals catches crossings of mesh holes without sampling."""
    intervals: list[tuple[float, float]] = []
    start, end = (a[0], a[1]), (b[0], b[1])
    for polygon in polygons:
        sign = 1 if _signed_area(polygon) >= 0 else -1
        lower, upper = 0.0, 1.0
        for u, v in zip(polygon, polygon[1:] + polygon[:1], strict=True):
            at_start, at_end = sign * _cross(u, v, start), sign * _cross(u, v, end)
            change = at_end - at_start
            if abs(change) <= eps:
                if at_start < -eps:
                    lower, upper = 1.0, 0.0
                    break
            elif change > 0:
                lower = max(lower, -at_start / change)
            else:
                upper = min(upper, -at_start / change)
        if lower <= upper + eps:
            intervals.append((max(0.0, lower), min(1.0, upper)))
    covered = 0.0
    for lower, upper in sorted(intervals):
        if lower > covered + eps:
            return False
        covered = max(covered, upper)
    return covered >= 1 - eps


def _bounds(row: dict[str, Any], scale: float) -> tuple[list[float], list[float]] | None:
    box = row.get("bounding_box")
    if box is None and row.get("vertices"):
        try:
            if any(
                len(p) != 3
                or not all(
                    isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                    for v in p
                )
                for p in row["vertices"]
            ):
                return None
        except TypeError:
            return None
        box = {
            "minimum": [min(p[i] for p in row["vertices"]) for i in range(3)],
            "maximum": [max(p[i] for p in row["vertices"]) for i in range(3)],
        }
    if not isinstance(box, dict):
        return None
    try:
        if any(isinstance(v, bool) for v in box["minimum"] + box["maximum"]):
            return None
        lower = [float(v) * scale for v in box["minimum"]]
        upper = [float(v) * scale for v in box["maximum"]]
    except (TypeError, KeyError, ValueError):
        return None
    if len(lower) != 3 or len(upper) != 3 or not all(math.isfinite(v) for v in lower + upper):
        return None
    if any(a > b for a, b in zip(lower, upper, strict=False)):
        return None
    return lower, upper


def _footprints(row: dict[str, Any], scale: float, eps: float) -> tuple[list[Polygon], str]:
    if row.get("vertices") is not None and row.get("triangles") is not None:
        try:
            if any(
                not isinstance(p, (list, tuple))
                or len(p) != 3
                or any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in p)
                for p in row["vertices"]
            ):
                return [], "INVALID_MESH"
            if len(row["triangles"]) > (_GEOMETRY_BUDGET.get() or {}).get(
                "maximum_mesh_triangles", 256
            ):
                return [], "UNSUPPORTED_COMPLEX_MESH"
            vertices = [[float(v) * scale for v in p] for p in row["vertices"]]
            if any(
                not isinstance(face, (list, tuple))
                or len(face) != 3
                or any(
                    not isinstance(i, int) or isinstance(i, bool) or i < 0 or i >= len(vertices)
                    for i in face
                )
                for face in row["triangles"]
            ):
                return [], "INVALID_MESH"
            if any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in vertices):
                return [], "INVALID_MESH"
            triangles = [
                [(vertices[i][0], vertices[i][1]) for i in face] for face in row["triangles"]
            ]
            if any(len(poly) != 3 for poly in triangles):
                return [], "INVALID_MESH"
            return [p for p in triangles if abs(_signed_area(p)) > eps], "EVALUATED_MESH_XY"
        except (IndexError, TypeError, ValueError):
            return [], "INVALID_MESH"
    if "footprint" in row:
        if not isinstance(row["footprint"], list) or any(
            not isinstance(p, (list, tuple))
            or len(p) != 2
            or any(
                not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
                for v in p
            )
            for p in row["footprint"]
        ):
            return [], "INVALID_PROXY"
        poly = [(float(p[0]) * scale, float(p[1]) * scale) for p in row["footprint"]]
        turns = [
            _cross(a, b, c)
            for a, b, c in zip(poly, poly[1:] + poly[:1], poly[2:] + poly[:2], strict=False)
        ]
        if len(poly) < 3 or not all(math.isfinite(v) for p in poly for v in p):
            return [], "INVALID_PROXY"
        if turns and min(turns) < -eps < max(turns):
            return [], "UNSUPPORTED_NONCONVEX_PROXY"
        return [poly], "EXPLICIT_CONVEX_PROXY"
    box = _bounds(row, scale)
    if box:
        lo, hi = box
        return [[(lo[0], lo[1]), (hi[0], lo[1]), (hi[0], hi[1]), (lo[0], hi[1])]], "AABB_PROXY_ONLY"
    return [], "INVALID_BOUNDS"


def _source_hash(scene: dict[str, Any]) -> str | None:
    value = scene.get("source_sha256") or scene.get("source", {}).get("sha256_before")
    return value if isinstance(value, str) else None


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_area_declaration(props: dict[str, Any]) -> bool:
    return any(key in props for key in ("walkable", "exclusion_reason", "coverage_scope"))


def _declared_area_evidence(scene: dict[str, Any]) -> list[dict[str, Any]]:
    """Preserve new declarations even if bounded geometry processing cannot finish."""
    collections = {r.get("collection", r.get("name")): r for r in scene.get("collections", [])}
    result = []
    for raw in scene.get("objects", []):
        name = raw.get("object", raw.get("name", ""))
        props = _props(raw)
        area_role = _class(name) == "AREA" or props.get("semantic_class") == "AREA"
        area_role |= any(
            _class(c) == "AREA" or _props(collections.get(c, {})).get("semantic_class") == "AREA"
            for c in raw.get("collections", [])
        )
        if area_role and _has_area_declaration(props):
            result.append(
                {
                    "object_id": name,
                    "declared_fields": _safe_json(
                        {key: props[key] for key in AREA_DECLARATION_FIELDS if key in props}
                    ),
                    "source_sha256": _source_hash(scene),
                }
            )
    return result


def _area_declaration(
    name: str, props: dict[str, Any], config: dict[str, Any], issue: Any
) -> dict[str, Any]:
    """Review identity records semantic intent, never floor or traversal approval."""
    if not _has_area_declaration(props):
        return {}
    errors = []
    walkable = props.get("walkable")
    scope = props.get("coverage_scope")
    mode = "STANDARD"
    if "walkable" in props and not isinstance(walkable, bool):
        errors.append("walkable must be a boolean")
    if "coverage_scope" in props and scope != "CROSS_FLOOR":
        errors.append("coverage_scope must be CROSS_FLOOR when provided")
    if scope == "CROSS_FLOOR":
        mode = "CROSS_FLOOR"
        if walkable is False or "exclusion_reason" in props:
            errors.append("cross-floor coverage and nonwalkable exclusion cannot be combined")
        floor_from, floor_to = props.get("floor_from"), props.get("floor_to")
        if not _nonempty_string(floor_from) or floor_from not in config["allowed_floors"]:
            errors.append("floor_from must name a configured floor")
        if not _nonempty_string(floor_to) or floor_to not in config["allowed_floors"]:
            errors.append("floor_to must name a configured floor")
        if floor_from == floor_to:
            errors.append("cross-floor AREA must name two distinct floors")
        if not _nonempty_string(props.get("stair_id")):
            errors.append("cross-floor AREA requires a nonempty stair_id")
        if not _nonempty_string(props.get("semantic_review_id")):
            errors.append("cross-floor AREA requires a nonempty semantic_review_id")
    elif walkable is False or "exclusion_reason" in props:
        mode = "EXCLUDED"
        if walkable is not False:
            errors.append("nonwalkable exclusion requires explicit walkable=false")
        if not _nonempty_string(props.get("exclusion_reason")):
            errors.append("nonwalkable exclusion requires a nonempty exclusion_reason")
        if not _nonempty_string(props.get("semantic_review_id")):
            errors.append("nonwalkable exclusion requires a nonempty semantic_review_id")
    evidence = _safe_json({key: props[key] for key in AREA_DECLARATION_FIELDS if key in props})
    if errors:
        issue(
            "AREA_COVERAGE_DECLARATION_INVALID",
            [name],
            "HIGH",
            "Incomplete or malformed AREA intent does not exempt ordinary coverage checks.",
            errors=errors,
            declared_fields=evidence,
        )
        mode = "INVALID"
    return {"mode": mode, "declared_fields": evidence}


def validate_scene(scene: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Bounded validation; excessive geometry is explicitly incomplete and queued for review."""
    token = _GEOMETRY_BUDGET.set(config["geometry_complexity"])
    try:
        report = _validate_scene(scene, config)
    except GeometryBudgetExceeded as error:
        finding = {
            "review_id": "SV-00001",
            "code": "GEOMETRY_COMPLEXITY_REVIEW",
            "objects": [],
            "priority": "HIGH",
            "status": "REVIEW",
            "detail": str(error),
            "evidence": {},
        }
        report = {
            "schema_version": "scene-validation-v1",
            "status": "INCOMPLETE_REVIEW_REQUIRED",
            "source": scene.get("source", {}),
            "source_sha256": _source_hash(scene),
            "config": config,
            "semantic_counts": {
                kind: sum(
                    _class(r.get("object", r.get("name", ""))) == kind
                    for r in scene.get("objects", [])
                )
                for kind in KINDS
            },
            "floor_summary": [],
            "area_coverage": [],
            "walkable_connectivity": {"status": "NOT_COMPLETED"},
            "floor_consistency": {},
            "portal_validation": [],
            "stair_validation": {"status": "NOT_COMPLETED"},
            "cross_semantic_conflicts": [],
            "geometry_objects": [],
            "findings": [finding],
            "review_queue": {"HIGH": [finding], "MEDIUM": [], "LOW": []},
            "review_counts": {"HIGH": 1},
            "limits": [
                "Configured complexity budget exceeded; no absent metric is replaced by zero."
            ],
        }
    finally:
        _GEOMETRY_BUDGET.reset(token)
    declarations = _declared_area_evidence(scene)
    if declarations:
        report["area_semantic_declarations"] = declarations
    return report


def _validate_scene(scene: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Validate a portable snapshot. Returns diagnostics and review queue, never navmesh edges."""
    tol = config["tolerances"]
    eps = tol["numeric_epsilon"]
    scale = config["meters_per_blender_unit"]
    findings: list[dict[str, Any]] = []

    def issue(
        code: str,
        objects: list[str],
        priority: str,
        detail: str,
        status: str = "REVIEW",
        **evidence: Any,
    ) -> None:
        findings.append(
            {
                "code": code,
                "objects": objects,
                "priority": priority,
                "status": status,
                "detail": detail,
                "evidence": _safe_json(evidence),
            }
        )

    collections = {r.get("collection", r.get("name")): r for r in scene.get("collections", [])}
    rows: list[dict[str, Any]] = []
    for raw in scene.get("objects", []):
        name = raw.get("object", raw.get("name", ""))
        props = _props(raw)
        labels: set[str] = set()
        object_class = _class(name)
        if object_class:
            labels.add(object_class)
        declared = props.get("semantic_class", raw.get("semantic_class"))
        if declared in KINDS:
            labels.add(declared)
        memberships = raw.get("collections", [])
        for collection in memberships:
            kind = _class(collection)
            if kind:
                labels.add(kind)
            collection_props = _props(collections.get(collection, {}))
            if collection_props.get("semantic_class") in KINDS:
                labels.add(collection_props["semantic_class"])
        if not labels:
            continue  # No interpretation of unlabeled group_*/Cube.*.
        kind = _class(name) or sorted(labels)[0]
        declaration = _area_declaration(name, props, config, issue) if kind == "AREA" else {}
        cross_floor = declaration.get("mode") == "CROSS_FLOOR"
        floor_labels = {
            _floor(name),
            raw.get("declared_floor_label"),
            props.get("floor_id"),
            raw.get("floor_id"),
        } - {None, ""}
        floor_labels.update(_floor(c) for c in memberships if _floor(c))
        if len(labels) > 1:
            issue(
                "INCOMPATIBLE_SEMANTIC_OWNERSHIP",
                [name],
                "HIGH",
                "Object has incompatible explicit object/property/collection roles.",
                "ERROR",
                roles=sorted(labels),
                collections=memberships,
            )
        if len(floor_labels) > 1:
            issue(
                "CONFLICTING_FLOOR_LABELS",
                [name],
                "HIGH",
                "Explicit floor labels disagree; no label was selected as authority.",
                "ERROR",
                floors=sorted(floor_labels),
            )
        floor = next(iter(floor_labels)) if len(floor_labels) == 1 else None
        if floor and floor not in config["allowed_floors"]:
            issue(
                "INVALID_FLOOR_PREFIX",
                [name],
                "HIGH",
                "Floor label is outside configured floors.",
                "ERROR",
                floor=floor,
            )
        if floor is None and kind != "STAIR" and not cross_floor:
            issue("MISSING_FLOOR_LABEL", [name], "LOW", "No unambiguous explicit floor label.")
        reviewed_walk_alias = (
            kind == "WALKABLE"
            and name.startswith("WALK_")
            and _nonempty_string(props.get("semantic_review_id"))
        )
        if _class(name) is None and not reviewed_walk_alias:
            issue(
                "NAMING_INCONSISTENCY",
                [name],
                "LOW",
                "Explicit collection/property role exists without matching object prefix.",
            )
        tokens = name.split("_")
        conflicting = sorted({token for token in tokens if token in KINDS} - {kind})
        if cross_floor:
            conflicting = [role for role in conflicting if role != "STAIR"]
        if conflicting:
            issue(
                "CONFLICTING_NAME_PREFIX",
                [name],
                "HIGH",
                "Name contains conflicting semantic tokens.",
                "ERROR",
                roles=conflicting,
            )
        expected = config.get("expected_collections", {}).get(kind)
        if expected and not any(c in expected for c in memberships):
            issue(
                "WRONG_COLLECTION",
                [name],
                "LOW",
                "Object is outside configured semantic collections.",
                expected_collections=expected,
                actual_collections=memberships,
            )
        for collection in memberships:
            if collection in collections:
                cp = _props(collections[collection])
                if cp.get("semantic_class") in KINDS and cp["semantic_class"] != kind:
                    issue(
                        "INCOMPATIBLE_COLLECTION_OWNERSHIP",
                        [name],
                        "HIGH",
                        "Collection property and object semantic role conflict.",
                        "ERROR",
                        collection=collection,
                        collection_role=cp["semantic_class"],
                    )
        box = _bounds(raw, scale)
        if box is None:
            issue(
                "INVALID_BOUNDS_OR_NONFINITE",
                [name],
                "MEDIUM",
                "Bounds are missing, inverted, malformed or non-finite.",
                "ERROR",
            )
            lo = hi = [0.0, 0.0, 0.0]
        else:
            lo, hi = box
        footprints, representation = _footprints(raw, scale, eps)
        if representation.startswith(("INVALID", "UNSUPPORTED")):
            issue(
                "INVALID_OR_UNSUPPORTED_GEOMETRY",
                [name],
                "MEDIUM",
                "Geometry cannot be evaluated safely.",
                representation=representation,
            )
        area = _union_area(footprints, eps)
        centroid = raw.get("centroid", [(a + b) / 2 / scale for a, b in zip(lo, hi, strict=False)])
        if (
            not isinstance(centroid, (list, tuple))
            or len(centroid) != 3
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in centroid)
        ):
            issue(
                "NONFINITE_CENTROID",
                [name],
                "MEDIUM",
                "Centroid is not a finite 3D point.",
                "ERROR",
            )
            centroid = [(a + b) / 2 / scale for a, b in zip(lo, hi, strict=False)]
        center = [float(v) * scale for v in centroid]
        row = {
            "id": name,
            "semantic_id": props.get("semantic_id", re.sub(r"\.\d+$", "", name)),
            "kind": kind,
            "floor": floor,
            "roles": sorted(labels),
            "props": props,
            "raw": raw,
            "bounds": [lo, hi],
            "centroid_m": center,
            "footprints": footprints,
            "representation": representation,
            "area_m2": area,
            "plane_z_m": (lo[2] + hi[2]) / 2,
            "valid_geometry": box is not None and bool(footprints) and area > eps,
            "coverage_declaration": declaration,
        }
        rows.append(row)
        _geometry_checks(row, tol, issue)

    duplicates: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        duplicates[row["semantic_id"]].append(row["id"])
    for semantic_id, ids in duplicates.items():
        if len(ids) > 1:
            issue(
                "DUPLICATE_SEMANTIC_ID",
                ids,
                "LOW",
                "Duplicate semantic ID; no rename performed.",
                "ERROR",
                semantic_id=semantic_id,
            )
    fingerprints: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        digest = row["raw"].get("geometry_sha256")
        if digest:
            fingerprints[digest].append(row["id"])
    for digest, ids in fingerprints.items():
        if len(ids) > 1:
            issue(
                "DUPLICATED_GEOMETRY",
                ids,
                "MEDIUM",
                "Identical evaluated world geometry.",
                geometry_sha256=digest,
            )

    floor_checks = _floor_checks(rows, scene, config, issue)
    by_kind = {kind: [r for r in rows if r["kind"] == kind] for kind in KINDS}
    walkables = [r for r in by_kind["WALKABLE"] if r["valid_geometry"]]
    coverage = _coverage(
        by_kind["AREA"], walkables, floor_checks, tol, issue, source_sha256=_source_hash(scene)
    )
    graph = _connectivity(walkables, scene.get("endpoints", []), tol, issue)
    portals = _portals(by_kind["PORTAL"], walkables, floor_checks, tol, issue)
    stairs = _stairs(by_kind["STAIR"], walkables, config, issue)
    stair_groups = {group["stair_id"]: group for group in stairs["groups"]}
    for item in coverage:
        if item["coverage_status"] != "NOT_APPLICABLE":
            continue
        group = stair_groups.get(item["semantic_declaration"]["declared_fields"]["stair_id"])
        item["stair_diagnostic_status"] = "MISSING" if group is None else group["status"]
        if group is None:
            issue(
                "AREA_CROSS_FLOOR_STAIR_UNRESOLVED",
                [item["area_id"]],
                "HIGH",
                "Declared cross-floor AREA has no matching explicit stair diagnostic group.",
                stair_id=item["semantic_declaration"]["declared_fields"]["stair_id"],
            )
    conflicts = _conflicts(by_kind, tol, issue)
    for kind in PHYSICAL:
        if not by_kind[kind]:
            issue(
                "MISSING_" + kind + "_LABELS",
                [],
                "HIGH",
                f"No explicit {kind}_* objects or semantic collection members.",
                "MISSING",
            )
    if not any(r["approved"] for r in floor_checks.values()):
        issue(
            "FLOOR_PLANE_AUTHORITY_UNRESOLVED",
            [],
            "HIGH",
            "No source-bound approved floor-plane configuration; floor results remain HEURISTIC.",
        )
    for setting in config.get("unresolved_settings", []):
        issue("UNRESOLVED_SETTING", [], "MEDIUM", setting)
    if not config.get("expected_collections"):
        issue(
            "COLLECTION_POLICY_UNRESOLVED",
            [],
            "LOW",
            "No approved expected-collection mapping; explicit incompatible ownership is checked.",
        )

    priorities = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    findings.sort(key=lambda f: (priorities[f["priority"]], f["code"], f["objects"]))
    for index, finding in enumerate(findings, 1):
        finding["review_id"] = f"SV-{index:05d}"
    floors = sorted(set(config["allowed_floors"]) | {r["floor"] or "UNASSIGNED" for r in rows})
    summary = []
    for floor in floors:
        floor_ids = {r["id"] for r in rows if (r["floor"] or "UNASSIGNED") == floor}
        same = [r for r in rows if r["id"] in floor_ids]
        item = {
            "floor": floor,
            **{kind.lower() + "_count": sum(r["kind"] == kind for r in same) for kind in KINDS},
        }
        item.update(
            connected_components=sum(any(i in floor_ids for i in c) for c in graph["components"]),
            isolated_walkables=sum(i in floor_ids for i in graph["isolated_walkables"]),
            uncovered_areas=sum(
                c["area_id"] in floor_ids
                and c["coverage_status"] not in {"PASS", "EXCLUDED", "NOT_APPLICABLE"}
                for c in coverage
            ),
            suspicious_portals=sum(
                p["portal_id"] in floor_ids and p["status"] != "PASS" for p in portals
            ),
            semantic_conflicts=sum(
                any(i in floor_ids for i in f["objects"])
                and f["status"] == "ERROR"
                and f["code"]
                in {
                    "INCOMPATIBLE_SEMANTIC_OWNERSHIP",
                    "INCOMPATIBLE_COLLECTION_OWNERSHIP",
                    "CONFLICTING_FLOOR_LABELS",
                    "CONFLICTING_NAME_PREFIX",
                    "WALKABLE_COLLIDER_OVERLAP",
                    "AREA_NONWALKABLE_OVERLAP",
                }
                for f in findings
            ),
            geometry_warnings=sum(
                any(i in floor_ids for i in f["objects"]) and f["code"] in GEOMETRY_CODES
                for f in findings
            ),
        )
        summary.append(item)
    return {
        "schema_version": "scene-validation-v1",
        "benchmark_type": scene.get("benchmark_type", "SCENE_DIAGNOSTIC"),
        "status": "REVIEW_REQUIRED" if findings else "PASS_DIAGNOSTICS_ONLY",
        "source": scene.get("source", {}),
        "source_sha256": _source_hash(scene),
        "config": config,
        "limits": [
            "Diagnostic graph never creates or approves inference topology, "
            "stair edges or floor authority.",
            "XY mesh footprints preserve holes but cannot certify swept-body "
            "clearance or 3D collision.",
            "AABB-only representations are broad-phase evidence and require human review.",
            "All thresholds are diagnostic heuristics until adopted by explicit research review.",
        ],
        "semantic_counts": {kind: len(by_kind[kind]) for kind in KINDS},
        "floor_summary": summary,
        "floor_consistency": floor_checks,
        "area_coverage": coverage,
        "walkable_connectivity": graph,
        "portal_validation": portals,
        "stair_validation": stairs,
        "cross_semantic_conflicts": conflicts,
        "geometry_objects": [
            {
                k: r[k]
                for k in (
                    "id",
                    "kind",
                    "floor",
                    "representation",
                    "area_m2",
                    "bounds",
                    "centroid_m",
                )
            }
            for r in rows
        ],
        "review_queue": {p: [f for f in findings if f["priority"] == p] for p in priorities},
        "review_counts": dict(Counter(f["priority"] for f in findings)),
        "findings": findings,
    }


GEOMETRY_CODES = {
    "INVALID_BOUNDS_OR_NONFINITE",
    "INVALID_OR_UNSUPPORTED_GEOMETRY",
    "NONFINITE_CENTROID",
    "EMPTY_MESH",
    "ZERO_SURFACE_AREA",
    "EXTREME_SCALE",
    "TINY_GEOMETRY",
    "GIANT_GEOMETRY",
    "HIDDEN_DISABLED_OBJECT",
    "NON_MANIFOLD",
    "DUPLICATED_GEOMETRY",
    "DECORATIVE_GEOMETRY_SUSPECT",
}


def _geometry_checks(row: dict[str, Any], tol: dict[str, Any], issue: Any) -> None:
    raw, name, kind = row["raw"], row["id"], row["kind"]
    stats = raw.get("mesh_statistics") or {}
    if raw.get("object_type", "MESH") == "MESH":
        count = stats.get("evaluated_vertices", len(raw.get("vertices", [])))
        if (
            count == 0
            and raw.get("geometry_status") == "EMPTY_EVALUATED_MESH"
            or ("vertices" in raw and not raw["vertices"])
        ):
            issue("EMPTY_MESH", [name], "MEDIUM", "Evaluated mesh has no vertices.", "ERROR")
        surface_area = raw.get("surface_area_m2", raw.get("surface_area_units2"))
        if surface_area is not None and surface_area <= tol["numeric_epsilon"]:
            issue(
                "ZERO_SURFACE_AREA",
                [name],
                "MEDIUM",
                "Evaluated mesh has zero surface area.",
                "ERROR",
            )
        elif kind in {"AREA", "WALKABLE"} and row["area_m2"] <= tol["numeric_epsilon"]:
            issue(
                "ZERO_SURFACE_AREA", [name], "MEDIUM", "No nonzero XY surface footprint.", "ERROR"
            )
    if kind == "CAM" and raw.get("object_type") != "CAMERA":
        issue(
            "CAM_PREFIX_WRONG_OBJECT_TYPE",
            [name],
            "LOW",
            "CAM_* must label a camera object.",
            "ERROR",
        )
    if (
        kind == "WALKABLE"
        and row["bounds"][1][2] - row["bounds"][0][2] > tol["walkable_plane_extent_m"]
    ):
        issue(
            "WALKABLE_NONPLANAR_EXTENT",
            [name],
            "MEDIUM",
            "Walkable vertical extent exceeds diagnostic plane tolerance; "
            "ramps need explicit review.",
        )
    extent = max(b - a for a, b in zip(*row["bounds"], strict=False))
    if extent > tol["huge_extent_m"]:
        issue(
            "GIANT_GEOMETRY",
            [name],
            "MEDIUM",
            "Object exceeds configured maximum diagnostic extent.",
            extent_m=extent,
        )
    if kind in {"AREA", "WALKABLE", "OBSTACLE"} and row["area_m2"] < tol["tiny_area_m2"]:
        issue(
            "TINY_GEOMETRY",
            [name],
            "MEDIUM",
            "Object has a suspiciously tiny projected footprint.",
            projected_area_m2=row["area_m2"],
        )
    if kind in {"WALL", "OBSTACLE"} and row["area_m2"] <= tol["numeric_epsilon"]:
        issue(
            "COLLIDER_FOOTPRINT_DEGENERATE_REVIEW",
            [name],
            "MEDIUM",
            "Thin vertical collider has no XY area; overlap ratios cannot certify passage.",
        )
    if raw.get("nonfinite_geometry"):
        issue(
            "INVALID_OR_UNSUPPORTED_GEOMETRY",
            [name],
            "MEDIUM",
            "Mesh contains non-finite coordinates.",
            "ERROR",
        )
    if raw.get("representation_unsupported"):
        issue(
            "GEOMETRY_COMPLEXITY_REVIEW",
            [name],
            "MEDIUM",
            "Mesh exceeds configured geometry budget; AABB evidence only.",
        )
    scales = raw.get("scale")
    if scales is None and raw.get("matrix_world"):
        matrix = raw["matrix_world"]
        if (
            isinstance(matrix, list)
            and len(matrix) == 4
            and all(_finite_vector(row_values, 4) for row_values in matrix)
        ):
            scales = [math.sqrt(sum(float(matrix[j][i]) ** 2 for j in range(3))) for i in range(3)]
        else:
            issue("EXTREME_SCALE", [name], "MEDIUM", "World transform is malformed/non-finite.")
    if scales is not None and (
        not _finite_vector(scales)
        or any(
            abs(s) < tol["extreme_scale_min"] or abs(s) > tol["extreme_scale_max"] for s in scales
        )
    ):
        issue(
            "EXTREME_SCALE",
            [name],
            "MEDIUM",
            "Scale is non-finite or outside configured diagnostic range.",
            scale=scales,
        )
    if (
        raw.get("hidden")
        or raw.get("hide_viewport")
        or raw.get("hide_render")
        or raw.get("disabled")
        or raw.get("in_active_scene") is False
        or raw.get("collection_disabled")
    ):
        issue("HIDDEN_DISABLED_OBJECT", [name], "MEDIUM", "Semantic object is hidden or disabled.")
    nonmanifold = raw.get("non_manifold_edges")
    if nonmanifold:
        issue(
            "NON_MANIFOLD",
            [name],
            "LOW",
            "Non-manifold edges reported; this does not invalidate a surface.",
            edge_count=nonmanifold,
        )
    if kind in {"WALL", "OBSTACLE"} and raw.get("object_type", "MESH") not in {
        "MESH",
        "CURVE",
        "SURFACE",
    }:
        issue(
            "DECORATIVE_GEOMETRY_SUSPECT",
            [name],
            "MEDIUM",
            "Explicit collider label refers to a helper/decorative object "
            "type; review its ownership.",
        )


def _floor_checks(
    rows: list[dict[str, Any]], scene: dict[str, Any], config: dict[str, Any], issue: Any
) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    planes = config.get("floor_planes", {})
    for floor in config["allowed_floors"]:
        plane = planes.get(floor, {})
        height = plane.get("height_m")
        normal = plane.get("normal")
        normal_supported = (
            isinstance(normal, list)
            and len(normal) == 3
            and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for v in normal
            )
            and abs(normal[0]) <= config["tolerances"]["numeric_epsilon"]
            and abs(normal[1]) <= config["tolerances"]["numeric_epsilon"]
            and abs(abs(normal[2]) - 1) <= config["tolerances"]["numeric_epsilon"]
        )
        height_supported = (
            isinstance(height, (int, float))
            and not isinstance(height, bool)
            and math.isfinite(height)
        )
        approved = (
            height_supported
            and normal_supported
            and plane.get("status") == "APPROVED"
            and bool(plane.get("review_id"))
            and bool(_source_hash(scene))
            and plane.get("source_sha256") == _source_hash(scene)
        )
        synthetic = (
            height_supported
            and normal_supported
            and plane.get("status") == "SYNTHETIC_FIXTURE"
            and scene.get("benchmark_type") == "SYNTHETIC REGRESSION"
        )
        if plane.get("status") in {"APPROVED", "SYNTHETIC_FIXTURE"} and not normal_supported:
            issue(
                "FLOOR_PLANE_REPRESENTATION_REVIEW",
                [],
                "HIGH",
                "Floor configuration requires finite height and supported unit "
                "horizontal normal; tilted planes remain REVIEW.",
                floor=floor,
            )
        if plane.get("status") == "APPROVED" and not approved:
            issue(
                "FLOOR_AUTHORITY_SOURCE_MISMATCH",
                [],
                "HIGH",
                "Approved floor authority lacks matching source hash/review identity.",
                floor=floor,
            )
        height = plane.get("height_m")
        if height is not None and (
            not isinstance(height, (int, float)) or not math.isfinite(height)
        ):
            raise ValueError("configured floor height must be finite")
        checks[floor] = {
            "authority": "APPROVED"
            if approved
            else "SYNTHETIC_FIXTURE"
            if synthetic
            else "HEURISTIC",
            "approved": approved or synthetic,
            "height_m": height,
            "objects": [],
        }
    tol = config["tolerances"]
    for row in rows:
        floor = row["floor"]
        if floor not in checks:
            continue
        check = checks[floor]
        lo, hi = row["bounds"]
        height = check["height_m"]
        offset = None if height is None else max(lo[2] - height, height - hi[2], 0)
        status = "REVIEW"
        if height is not None:
            if row["kind"] == "WALKABLE":
                offset = max(abs(lo[2] - height), abs(hi[2] - height))
            if offset is not None and offset > tol["floor_height_m"] and row["kind"] != "CAM":
                issue(
                    "FLOOR_GEOMETRY_OFFSET",
                    [row["id"]],
                    "HIGH",
                    "Declared floor and geometry differ beyond configured height tolerance.",
                    "ERROR" if check["approved"] else "REVIEW",
                    floor=floor,
                    authority=check["authority"],
                    offset_m=offset,
                )
                status = "ERROR" if check["approved"] else "REVIEW"
            elif check["approved"] and row["kind"] != "CAM":
                status = "PASS"
            if row["kind"] == "CAM":
                status = "REVIEW"
                issue(
                    "CAMERA_PLANE_BINDING_REVIEW",
                    [row["id"]],
                    "MEDIUM",
                    "Floor label and camera position do not approve camera-to-plane binding.",
                )
        check["objects"].append(
            {
                "object_id": row["id"],
                "semantic_floor_label": floor,
                "centroid_z_m": row["centroid_m"][2],
                "vertical_extent_m": hi[2] - lo[2],
                "floor_geometry_offset_m": offset,
                "status": status,
            }
        )
    return checks


def _same_floor(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a["floor"] is not None and a["floor"] == b["floor"]


def _coverage(
    areas: list[dict[str, Any]],
    walkables: list[dict[str, Any]],
    floors: dict[str, Any],
    tol: dict[str, Any],
    issue: Any,
    source_sha256: str | None = None,
) -> list[dict[str, Any]]:
    result = []
    eps = tol["numeric_epsilon"]
    for area in areas:
        declaration = area["coverage_declaration"]
        mode = declaration.get("mode")
        declared_evidence = {**declaration, "source_sha256": source_sha256} if declaration else None
        if mode == "CROSS_FLOOR":
            result.append(
                {
                    "area_id": area["id"],
                    "floor": area["floor"],
                    "status": "REVIEW",
                    "coverage_status": "NOT_APPLICABLE",
                    "walkable_overlap_ratio": None,
                    "uncovered_ratio": None,
                    "overlapping_walkables": [],
                    "nearest_walkable": None,
                    "nearest_distance_m": None,
                    "floor_consistency": "REVIEW",
                    "geometry_offset_m": None,
                    "geometry_basis": area["representation"],
                    "authority": "DECLARED_CROSS_FLOOR_AREA_NOT_TOPOLOGY",
                    "semantic_declaration": declared_evidence,
                }
            )
            issue(
                "AREA_CROSS_FLOOR_REVIEW",
                [area["id"]],
                "MEDIUM",
                "Cross-floor AREA defers traversal to explicit stair diagnostics; "
                "semantic intent does not approve floor or stair connectivity.",
                declared_fields=declaration["declared_fields"],
                source_sha256=source_sha256,
            )
            continue
        # A nonwalkable volume must not hide overlapping surfaces behind a floor-label mismatch.
        same = walkables if mode == "EXCLUDED" else [w for w in walkables if _same_floor(area, w)]
        if mode == "EXCLUDED":
            # Sloped WALKABLE can enter the volume although its midpoint lies outside it.
            eligible = [
                w
                for w in same
                if max(
                    area["bounds"][0][2] - w["bounds"][1][2],
                    w["bounds"][0][2] - area["bounds"][1][2],
                    0,
                )
                <= tol["floor_height_m"]
            ]
        else:
            eligible = [
                w
                for w in same
                if max(
                    area["bounds"][0][2] - w["plane_z_m"],
                    w["plane_z_m"] - area["bounds"][1][2],
                    0,
                )
                <= tol["floor_height_m"]
            ]
        pieces = [
            p for w in eligible for p in _intersections(area["footprints"], w["footprints"], eps)
        ]
        denominator = area["area_m2"]
        overlap_area = _union_area(pieces, eps) if denominator > eps or mode == "EXCLUDED" else 0.0
        ratio = min(1.0, overlap_area / denominator) if denominator > eps else None
        if ratio is None:
            geometric = "REVIEW"
        elif ratio >= tol["coverage_pass_ratio"]:
            geometric = "PASS"
        elif ratio >= tol["coverage_partial_ratio"]:
            geometric = "PARTIAL"
        else:
            geometric = "MISSING"
        reliable = (
            area["valid_geometry"]
            and area["representation"] != "AABB_PROXY_ONLY"
            and all(w["representation"] != "AABB_PROXY_ONLY" for w in eligible)
        )
        if mode == "EXCLUDED" and any(
            w["bounds"][1][2] - w["bounds"][0][2] > tol["walkable_plane_extent_m"]
            and _union_area(_intersections(area["footprints"], w["footprints"], eps), eps) > eps
            for w in eligible
        ):
            reliable = False  # XY projection plus Z extents is conservative for nonplanar surfaces.
        approved_floor = floors.get(area["floor"], {}).get("approved", False)
        status = geometric if reliable and approved_floor or geometric == "MISSING" else "REVIEW"
        if mode == "INVALID":
            status = "REVIEW"
        if mode == "EXCLUDED":
            geometric = "EXCLUDED"
            status = "EXCLUDED" if reliable and area["floor"] in floors else "REVIEW"
            if overlap_area > eps:
                status = "ERROR" if reliable else "REVIEW"
        nearest = min(
            walkables if area["valid_geometry"] else [],
            key=lambda w: math.hypot(
                _distance(area["footprints"], w["footprints"], eps),
                max(
                    area["bounds"][0][2] - w["plane_z_m"], w["plane_z_m"] - area["bounds"][1][2], 0
                ),
            ),
            default=None,
        )
        offset = (
            None
            if nearest is None
            else max(
                area["bounds"][0][2] - nearest["plane_z_m"],
                nearest["plane_z_m"] - area["bounds"][1][2],
                0,
            )
        )
        item = {
            "area_id": area["id"],
            "floor": area["floor"],
            "status": status,
            "coverage_status": geometric,
            "walkable_overlap_ratio": ratio,
            "uncovered_ratio": None if ratio is None or mode == "EXCLUDED" else 1 - ratio,
            "overlapping_walkables": [
                w["id"]
                for w in eligible
                if _union_area(_intersections(area["footprints"], w["footprints"], eps), eps) > eps
            ],
            "nearest_walkable": None if nearest is None else nearest["id"],
            "nearest_distance_m": None
            if nearest is None
            else math.hypot(_distance(area["footprints"], nearest["footprints"], eps), offset or 0),
            "floor_consistency": "REVIEW"
            if not approved_floor or nearest is None
            else "PASS"
            if _same_floor(area, nearest)
            else "ERROR",
            "geometry_offset_m": offset,
            "geometry_basis": area["representation"],
            "authority": floors.get(area["floor"], {}).get("authority", "HEURISTIC"),
        }
        if declaration:
            item["semantic_declaration"] = declared_evidence
        result.append(item)
        if mode == "EXCLUDED":
            if item["overlapping_walkables"]:
                issue(
                    "AREA_NONWALKABLE_OVERLAP",
                    [area["id"], *item["overlapping_walkables"]],
                    "HIGH",
                    "Projected WALKABLE overlap with intersecting or nearby Z extents "
                    "contradicts nonwalkable intent; bounds do not certify 3D collision.",
                    "ERROR" if reliable else "REVIEW",
                    overlap_ratio=ratio,
                    declared_fields=declaration["declared_fields"],
                    source_sha256=source_sha256,
                    overlap_basis="XY_FOOTPRINTS_WITH_Z_INTERVAL_BROAD_PHASE",
                )
            if not reliable or area["floor"] not in floors:
                issue(
                    "AREA_EXCLUSION_GEOMETRY_REVIEW",
                    [area["id"]],
                    "HIGH",
                    "Nonwalkable intent does not certify unsupported/nonplanar geometry "
                    "or an unresolved floor label as free of WALKABLE overlap.",
                )
            continue
        if geometric == "MISSING":
            issue(
                "AREA_MISSING_WALKABLE",
                [area["id"]],
                "HIGH",
                "Area has no sufficient same-floor walkable overlap.",
                "MISSING",
                overlap_ratio=ratio,
            )
        elif geometric == "PARTIAL":
            issue(
                "AREA_PARTIAL_COVERAGE",
                [area["id"]],
                "MEDIUM",
                "Area coverage is below diagnostic pass threshold.",
                overlap_ratio=ratio,
            )
        elif status == "REVIEW":
            issue(
                "AREA_COVERAGE_AUTHORITY_REVIEW",
                [area["id"]],
                "MEDIUM",
                "Coverage evidence requires approved floor authority or a "
                "supported geometry representation.",
                geometry_status=geometric,
            )
    return result


def _connectivity(
    walkables: list[dict[str, Any]],
    endpoints: list[dict[str, Any]],
    tol: dict[str, Any],
    issue: Any,
) -> dict[str, Any]:
    adjacency: dict[str, set[str]] = {w["id"]: set() for w in walkables}
    edges = []
    for a, b in itertools.combinations(walkables, 2):
        distance = _distance(a["footprints"], b["footprints"], tol["numeric_epsilon"])
        if (
            _same_floor(a, b)
            and distance <= tol["connectivity_distance_m"]
            and abs(a["plane_z_m"] - b["plane_z_m"]) <= tol["connectivity_z_m"]
        ):
            adjacency[a["id"]].add(b["id"])
            adjacency[b["id"]].add(a["id"])
            edges.append(
                {
                    "from": a["id"],
                    "to": b["id"],
                    "distance_m": distance,
                    "authority": "DIAGNOSTIC_ONLY_NOT_INFERENCE_EDGE",
                }
            )
    components: list[list[str]] = []
    remaining = set(adjacency)
    while remaining:
        stack = [min(remaining)]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)
        remaining -= component
        components.append(sorted(component))
    isolated = sorted(i for i, neighbors in adjacency.items() if not neighbors)
    for name in isolated:
        issue(
            "ISOLATED_WALKABLE",
            [name],
            "MEDIUM",
            "Walkable has no same-floor geometric neighbor; isolation can be intentional.",
        )
    by_id = {w["id"]: w for w in walkables}
    component_details = []
    for group in components:
        floor = by_id[group[0]]["floor"]
        area = _union_area(
            [p for i in group for p in by_id[i]["footprints"]], tol["numeric_epsilon"]
        )
        component_details.append({"objects": group, "floor": floor, "area_m2": area})
        if area < tol["small_island_area_m2"]:
            issue(
                "SMALL_WALKABLE_ISLAND",
                group,
                "MEDIUM",
                "Small component warrants human review.",
                area_m2=area,
            )
    for floor in sorted({w["floor"] for w in walkables if w["floor"]}):
        large = [
            c
            for c in component_details
            if c["floor"] == floor and c["area_m2"] >= tol["large_component_area_m2"]
        ]
        if len(large) > 1:
            issue(
                "LARGE_SAME_FLOOR_DISCONNECTION",
                [i for c in large for i in c["objects"]],
                "MEDIUM",
                "Large same-floor components are disconnected; not automatically an error.",
                floor=floor,
            )
    access = []
    for endpoint in endpoints:
        point = endpoint["position_m"]
        if not _finite_vector(point):
            issue(
                "ENDPOINT_GEOMETRY_INVALID",
                [endpoint["id"]],
                "HIGH",
                "Declared endpoint is malformed/non-finite; no accessibility is inferred.",
            )
            access.append(
                {
                    "endpoint_id": endpoint["id"],
                    "status": "REVIEW",
                    "nearest_walkable": None,
                    "distance_m": None,
                }
            )
            continue
        candidates = [w for w in walkables if w["floor"] == endpoint.get("floor_id")]
        nearest = min(
            candidates,
            key=lambda w: _point_distance(point, w, tol["numeric_epsilon"]),
            default=None,
        )
        endpoint_distance = (
            None if nearest is None else _point_distance(point, nearest, tol["numeric_epsilon"])
        )
        status = (
            "PASS_DIAGNOSTIC"
            if endpoint_distance is not None and endpoint_distance <= tol["endpoint_distance_m"]
            else "REVIEW"
        )
        access.append(
            {
                "endpoint_id": endpoint["id"],
                "status": status,
                "nearest_walkable": None if nearest is None else nearest["id"],
                "distance_m": endpoint_distance,
            }
        )
        if status == "REVIEW":
            issue(
                "ENDPOINT_INACCESSIBLE",
                [endpoint["id"]],
                "HIGH",
                "Declared endpoint is not near a same-floor walkable; never snap it.",
            )
    if not endpoints:
        issue(
            "ENDPOINT_ACCESSIBILITY_UNRESOLVED",
            [],
            "MEDIUM",
            "No explicit navigation endpoint declarations.",
        )
    return {
        "authority": "HEURISTIC_DIAGNOSTIC_ONLY",
        "connected_component_count": len(components),
        "components": components,
        "component_details": component_details,
        "isolated_walkables": isolated,
        "edges": edges,
        "endpoint_accessibility": access,
        "stair_edges_created": False,
        "portal_edges_created": False,
    }


def _portals(
    portals: list[dict[str, Any]],
    walkables: list[dict[str, Any]],
    floors: dict[str, Any],
    tol: dict[str, Any],
    issue: Any,
) -> list[dict[str, Any]]:
    result = []
    for portal in portals:
        same = [w for w in walkables if _same_floor(portal, w)]
        near = [
            w
            for w in same
            if _distance(portal["footprints"], w["footprints"], tol["numeric_epsilon"])
            <= tol["portal_near_distance_m"]
            and max(
                portal["bounds"][0][2] - w["plane_z_m"], w["plane_z_m"] - portal["bounds"][1][2], 0
            )
            <= tol["floor_height_m"]
        ]
        sides: dict[str, list[str]] = {"negative": [], "positive": []}
        normal = portal["props"].get("portal_normal")
        orientation = "REVIEW"
        status = "MISSING" if not near else "REVIEW"
        if normal is not None:
            if (
                not _finite_vector(normal)
                or math.sqrt(sum(v * v for v in normal)) <= tol["numeric_epsilon"]
            ):
                issue(
                    "PORTAL_INVALID_ORIENTATION",
                    [portal["id"]],
                    "MEDIUM",
                    "Portal normal is not finite/nonzero.",
                )
            else:
                length = math.sqrt(sum(v * v for v in normal))
                orientation = (
                    "PASS"
                    if abs(normal[2]) / length <= tol["portal_orientation_vertical_ratio"]
                    else "REVIEW"
                )
                if orientation == "REVIEW":
                    issue(
                        "PORTAL_ORIENTATION_ANOMALY",
                        [portal["id"]],
                        "MEDIUM",
                        "Explicit portal normal is unusually vertical.",
                    )
                for label, sign in (("negative", -1), ("positive", 1)):
                    point = [
                        portal["centroid_m"][i]
                        + sign * normal[i] / length * tol["portal_side_probe_m"]
                        for i in range(3)
                    ]
                    if near:
                        point[2] = min(near, key=lambda w: abs(w["plane_z_m"] - point[2]))[
                            "plane_z_m"
                        ]
                    sides[label] = [
                        w["id"]
                        for w in near
                        if _point_distance(point, w, tol["numeric_epsilon"])
                        <= tol["connectivity_distance_m"]
                    ]
                if sides["negative"] and sides["positive"]:
                    # Both sides may touch one object; this creates no new graph edge.
                    status = (
                        "PASS"
                        if orientation == "PASS"
                        and floors.get(portal["floor"], {}).get("approved")
                        and portal["representation"] != "AABB_PROXY_ONLY"
                        else "REVIEW"
                    )
                elif sides["negative"] or sides["positive"]:
                    status = "PARTIAL"
                    issue(
                        "PORTAL_ONE_SIDED",
                        [portal["id"]],
                        "HIGH",
                        "Only one explicit portal side touches walkable.",
                    )
                elif near:
                    issue(
                        "PORTAL_IN_NONWALKABLE_REGION",
                        [portal["id"]],
                        "HIGH",
                        "Portal is near walkable but its explicit side probes are inaccessible.",
                    )
        elif near:
            issue(
                "PORTAL_ORIENTATION_UNRESOLVED",
                [portal["id"]],
                "MEDIUM",
                "No explicit world-space portal normal; geometry thin axis is not "
                "treated as authority.",
            )
        if not near:
            issue(
                "PORTAL_DISCONNECTED",
                [portal["id"]],
                "HIGH",
                "No nearby same-floor walkable.",
                "MISSING",
            )
        result.append(
            {
                "portal_id": portal["id"],
                "floor": portal["floor"],
                "status": status,
                "nearby_walkables": [w["id"] for w in near],
                "side_accessibility": sides,
                "orientation": orientation,
                "floor_consistency": floors.get(portal["floor"], {}).get("authority", "HEURISTIC"),
                "connectivity_created": False,
            }
        )
    return result


def _stairs(
    stairs: list[dict[str, Any]],
    walkables: list[dict[str, Any]],
    config: dict[str, Any],
    issue: Any,
) -> dict[str, Any]:
    if not stairs:
        return {"status": "MISSING", "stair_count": 0, "groups": [], "connectivity_created": False}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in stairs:
        role = row["props"].get("stair_role")
        if role is None:
            role = next((r for r in ("ENTRY", "PATH", "EXIT") if r in row["id"].split("_")), None)
        stair_id = row["props"].get("stair_id")
        if not stair_id or role not in {"ENTRY", "PATH", "EXIT"}:
            issue(
                "STAIR_GROUP_OR_ROLE_UNRESOLVED",
                [row["id"]],
                "HIGH",
                "Explicit stair_id and ENTRY/PATH/EXIT role are required; no "
                "pairing inferred from proximity.",
            )
            grouped["UNRESOLVED:" + row["id"]].append({**row, "stair_role": role})
        else:
            grouped[stair_id].append({**row, "stair_role": role})
    tol = config["tolerances"]
    result = []
    for stair_id, members in sorted(grouped.items()):
        roles = {
            role: [r for r in members if r["stair_role"] == role]
            for role in ("ENTRY", "PATH", "EXIT")
        }
        ids = [r["id"] for r in members]
        checks: dict[str, Any] = {}
        for role, items in roles.items():
            checks[role.lower()] = (
                "PASS" if len(items) == 1 else "MISSING" if not items else "REVIEW"
            )
            if not items:
                issue(
                    "STAIR_MISSING_" + role,
                    ids,
                    "HIGH",
                    f"Stair group lacks explicit {role}.",
                    "MISSING",
                )
            elif len(items) > 1:
                issue(
                    "STAIR_DUPLICATE_ROLE",
                    [r["id"] for r in items],
                    "MEDIUM",
                    f"Multiple {role} objects in stair group.",
                )
        entry = roles["ENTRY"][0] if len(roles["ENTRY"]) == 1 else None
        exit_ = roles["EXIT"][0] if len(roles["EXIT"]) == 1 else None
        path = roles["PATH"][0] if len(roles["PATH"]) == 1 else None
        floor_from = path["props"].get("floor_from") if path else None
        floor_to = path["props"].get("floor_to") if path else None
        if entry and not floor_from:
            floor_from = entry["floor"]
        if exit_ and not floor_to:
            floor_to = exit_["floor"]
        checks["floor_transition"] = "REVIEW"
        if floor_from is None or floor_to is None:
            issue(
                "STAIR_FLOOR_TRANSITION_UNRESOLVED",
                ids,
                "HIGH",
                "Stair floor_from/floor_to unavailable.",
            )
        elif (
            floor_from == floor_to
            or floor_from not in config["allowed_floors"]
            or floor_to not in config["allowed_floors"]
        ):
            checks["floor_transition"] = "ERROR"
            issue(
                "STAIR_WRONG_FLOOR",
                ids,
                "HIGH",
                "Stair must join two distinct configured floors.",
                "ERROR",
                floor_from=floor_from,
                floor_to=floor_to,
            )
        elif entry and exit_ and (entry["floor"] != floor_from or exit_["floor"] != floor_to):
            checks["floor_transition"] = "ERROR"
            issue(
                "STAIR_WRONG_FLOOR",
                ids,
                "HIGH",
                "Entry/exit floor labels conflict with declared transition.",
                "ERROR",
            )
        else:
            checks["floor_transition"] = "PASS_DIAGNOSTIC"
        accessibility: list[str] = []
        for label, endpoint, floor in (("entry", entry, floor_from), ("exit", exit_, floor_to)):
            if endpoint is None:
                checks[label + "_walkable"] = "MISSING"
                continue
            near = [
                w
                for w in walkables
                if w["floor"] == floor
                and _point_distance(endpoint["centroid_m"], w, tol["numeric_epsilon"])
                <= tol["stair_join_distance_m"]
            ]
            checks[label + "_walkable"] = "PASS_DIAGNOSTIC" if near else "MISSING"
            accessibility.extend(w["id"] for w in near)
            if not near:
                issue(
                    "STAIR_" + label.upper() + "_DISCONNECTED",
                    [endpoint["id"]],
                    "HIGH",
                    "Stair endpoint does not touch declared-floor walkable.",
                    "MISSING",
                )
        if not accessibility:
            issue(
                "ISOLATED_STAIR", ids, "HIGH", "No stair endpoint touches any same-floor walkable."
            )
        points = path["props"].get("path_points_m") if path else None
        checks["path_continuity"] = "REVIEW"
        checks["z_direction"] = "REVIEW"
        valid_points = (
            isinstance(points, list)
            and len(points) >= 2
            and all(
                isinstance(p, list)
                and len(p) == 3
                and all(
                    isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                    for v in p
                )
                for p in points
            )
        )
        if points is not None and not valid_points:
            issue(
                "STAIR_INVALID_PATH",
                ids,
                "HIGH",
                "Explicit ordered path is malformed or non-finite.",
                "ERROR",
            )
        elif valid_points and isinstance(points, list):
            checks["path_continuity"] = "PASS_DIAGNOSTIC"
            if entry and math.dist(points[0], entry["centroid_m"]) > tol["stair_join_distance_m"]:
                checks["path_continuity"] = "ERROR"
            if exit_ and math.dist(points[-1], exit_["centroid_m"]) > tol["stair_join_distance_m"]:
                checks["path_continuity"] = "ERROR"
            if checks["path_continuity"] == "ERROR":
                issue(
                    "STAIR_PATH_DISCONTINUITY",
                    ids,
                    "HIGH",
                    "Ordered path does not join entry/exit anchors.",
                    "ERROR",
                )
            checks["path_geometry_alignment"] = "REVIEW"
            if path and path["valid_geometry"] and path["representation"] != "AABB_PROXY_ONLY":
                contained = all(
                    _segment_in_footprints(a, b, path["footprints"], tol["numeric_epsilon"])
                    for a, b in zip(points, points[1:], strict=False)
                )
                contained &= all(
                    path["bounds"][0][2] - tol["stair_join_distance_m"]
                    <= p[2]
                    <= path["bounds"][1][2] + tol["stair_join_distance_m"]
                    for p in points
                )
                checks["path_geometry_alignment"] = "PASS_DIAGNOSTIC" if contained else "ERROR"
                if not contained:
                    issue(
                        "STAIR_PATH_GEOMETRY_MISMATCH",
                        ids,
                        "HIGH",
                        "Ordered path crosses a projected mesh hole "
                        "or leaves path geometry bounds.",
                        "ERROR",
                    )
            else:
                issue(
                    "STAIR_PATH_GEOMETRY_ALIGNMENT_REVIEW",
                    ids,
                    "MEDIUM",
                    "Stair path geometry cannot support a containment check.",
                )
            rise = points[-1][2] - points[0][2]
            checks["z_direction"] = "PASS_DIAGNOSTIC"
            direction = path["props"].get("direction") if path else None
            changes = [b[2] - a[2] for a, b in zip(points, points[1:], strict=False)]
            if (
                abs(rise) < tol["stair_min_rise_m"]
                or direction == "UP"
                and any(d < -tol["stair_direction_tolerance_m"] for d in changes)
                or direction == "DOWN"
                and any(d > tol["stair_direction_tolerance_m"] for d in changes)
            ):
                checks["z_direction"] = "ERROR"
                issue(
                    "STAIR_Z_DIRECTION",
                    ids,
                    "HIGH",
                    "Stair rise or explicit direction contradicts path Z.",
                    "ERROR",
                )
            if direction not in {"UP", "DOWN"}:
                checks["z_direction"] = "REVIEW"
                issue(
                    "STAIR_DIRECTION_UNRESOLVED",
                    ids,
                    "MEDIUM",
                    "No explicit UP/DOWN path direction.",
                )
            if any(
                math.dist(a, b) <= tol["numeric_epsilon"]
                for a, b in zip(points, points[1:], strict=False)
            ):
                issue(
                    "STAIR_DUPLICATED_PATH_POINT",
                    ids,
                    "MEDIUM",
                    "Ordered path contains zero-length segment.",
                )
        else:
            issue(
                "STAIR_PATH_CONTINUITY_UNRESOLVED",
                ids,
                "HIGH",
                "Mesh/AABB alone does not declare ordered stair traversal; "
                "explicit path_points_m required.",
            )
        # Measured clearance/slab evidence is diagnostic input, never an implicit certification.
        clearance = path["props"].get("measured_clearance_m") if path else None
        minimum = tol["minimum_clearance_m"]
        checks["clearance"] = "REVIEW"
        if minimum is not None and isinstance(clearance, (int, float)) and math.isfinite(clearance):
            checks["clearance"] = "PASS_DECLARED_MEASUREMENT" if clearance >= minimum else "ERROR"
            if clearance < minimum:
                issue(
                    "STAIR_INSUFFICIENT_CLEARANCE",
                    ids,
                    "HIGH",
                    "Declared measured clearance is below configured threshold.",
                    "ERROR",
                )
        else:
            issue(
                "STAIR_CLEARANCE_UNRESOLVED",
                ids,
                "MEDIUM",
                "Physical clearance policy/measurement is missing; no mesh-derived "
                "clearance claimed.",
            )
        opening = path["props"].get("slab_opening_review") if path else None
        checks["slab_opening"] = (
            "PASS_HUMAN_REVIEW" if opening == "PASS" else "ERROR" if opening == "FAIL" else "REVIEW"
        )
        if opening != "PASS":
            issue(
                "STAIR_SLAB_OPENING_REVIEW",
                ids,
                "HIGH",
                "Slab opening needs explicit human PASS/FAIL review.",
                "ERROR" if opening == "FAIL" else "REVIEW",
            )
        status = (
            "ERROR"
            if "ERROR" in checks.values()
            else "MISSING"
            if "MISSING" in checks.values()
            else "REVIEW"
        )
        result.append(
            {
                "stair_id": stair_id,
                "objects": ids,
                "floor_from": floor_from,
                "floor_to": floor_to,
                "status": status,
                "checks": checks,
                "connectivity_created": False,
            }
        )
    return {
        "status": "REVIEW",
        "stair_count": len(stairs),
        "groups": result,
        "connectivity_created": False,
    }


def _conflicts(
    by_kind: dict[str, list[dict[str, Any]]], tol: dict[str, Any], issue: Any
) -> list[dict[str, Any]]:
    result = []
    for kind in ("WALL", "OBSTACLE"):
        for collider in by_kind[kind]:
            near_navigation = False
            for walkable in by_kind["WALKABLE"]:
                if not _same_floor(collider, walkable):
                    continue
                distance = _distance(
                    collider["footprints"], walkable["footprints"], tol["numeric_epsilon"]
                )
                near_navigation |= distance <= tol["navigation_near_distance_m"]
                lo, hi = collider["bounds"]
                if (
                    walkable["plane_z_m"] < lo[2] - tol["conflict_vertical_contact_m"]
                    or walkable["plane_z_m"] > hi[2] + tol["conflict_vertical_contact_m"]
                ):
                    continue
                overlap = _union_area(
                    _intersections(
                        collider["footprints"], walkable["footprints"], tol["numeric_epsilon"]
                    ),
                    tol["numeric_epsilon"],
                )
                # Fraction of the walkable surface, not of a zero-area vertical wall.
                ratio = (
                    overlap / walkable["area_m2"]
                    if walkable["area_m2"] > tol["numeric_epsilon"]
                    else None
                )
                if ratio is None or ratio <= tol["contact_overlap_ratio"]:
                    continue
                strong = ratio >= tol["conflict_overlap_ratio"]
                reliable = (
                    collider["representation"] != "AABB_PROXY_ONLY"
                    and walkable["representation"] != "AABB_PROXY_ONLY"
                )
                status = "ERROR" if strong and reliable else "REVIEW"
                item = {
                    "walkable": walkable["id"],
                    "collider": collider["id"],
                    "kind": kind,
                    "projected_overlap_m2": overlap,
                    "walkable_overlap_ratio": ratio,
                    "status": status,
                    "authority": "GEOMETRIC_DIAGNOSTIC_NOT_COLLISION_CERTIFICATION",
                }
                result.append(item)
                issue(
                    "WALKABLE_COLLIDER_OVERLAP",
                    [walkable["id"], collider["id"]],
                    "HIGH" if strong else "MEDIUM",
                    "Projected walkable/collider overlap exceeds configured contact tolerance.",
                    status,
                    overlap_ratio=ratio,
                    collider_kind=kind,
                )
            if kind == "OBSTACLE" and not near_navigation:
                issue(
                    "OBSTACLE_UNRELATED_TO_NAVIGATION",
                    [collider["id"]],
                    "MEDIUM",
                    "No same-floor nearby walkable navigation area; review obstacle ownership.",
                )
            if collider["props"].get("collision_role") not in {"MOVEMENT", "OCCLUSION", "BOTH"}:
                issue(
                    "COLLIDER_OWNERSHIP_UNRESOLVED",
                    [collider["id"]],
                    "MEDIUM",
                    "Movement versus occlusion ownership is not explicitly declared.",
                )
            for portal in by_kind["PORTAL"]:
                if not _same_floor(collider, portal):
                    continue
                overlap = _union_area(
                    _intersections(
                        collider["footprints"], portal["footprints"], tol["numeric_epsilon"]
                    ),
                    tol["numeric_epsilon"],
                )
                if (
                    portal["area_m2"] > tol["numeric_epsilon"]
                    and overlap / portal["area_m2"] > tol["contact_overlap_ratio"]
                ):
                    issue(
                        "COLLIDER_CROSSES_PORTAL",
                        [collider["id"], portal["id"]],
                        "HIGH",
                        "Projected collider overlap crosses portal; review 3D "
                        "aperture/contact semantics.",
                        projected_overlap_m2=overlap,
                    )
    return result


def _fingerprint(path: Path) -> tuple[str, int, int]:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    stat = path.stat()
    return digest, stat.st_size, stat.st_mtime_ns


def extract_blend(
    source: Path, blender: str | None = None, max_triangles: int = 256
) -> dict[str, Any]:
    """Extract a fresh snapshot using Blender; source immutability is checked even on failure."""
    before = _fingerprint(source)
    binary = blender or shutil.which("blender")
    fallback = Path("/Applications/Blender.app/Contents/MacOS/blender")
    if binary is None and fallback.is_file():
        binary = str(fallback)
    if binary is None:
        raise FileNotFoundError(
            "Blender executable unavailable; provide --blender or --input snapshot.json"
        )
    extractor = Path(__file__).with_name("scene_validation_blender.py")
    with tempfile.TemporaryDirectory(prefix="amidst-scene-validation-") as directory:
        output = Path(directory) / "snapshot.json"
        command = [
            binary,
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "-noaudio",
            str(source.resolve()),
            "--python-exit-code",
            "2",
            "--python",
            str(extractor),
            "--",
            "--output",
            str(output),
            "--source-sha256",
            before[0],
            "--max-triangles",
            str(max_triangles),
        ]
        try:
            subprocess.run(command, check=True)
        finally:
            after = _fingerprint(source)
            if before != after:
                raise RuntimeError("immutable Blender source changed during validation extraction")
        snapshot: dict[str, Any] = json.loads(output.read_text())
    snapshot["source"] = {
        "path": str(source),
        "sha256_before": before[0],
        "sha256_after": after[0],
        "size_bytes": before[1],
        "mtime_ns_before": before[2],
        "mtime_ns_after": after[2],
    }
    snapshot["read_only_contract"] = {
        "source_unchanged": True,
        "saved": False,
        "rendered": False,
        "autoexec_disabled": True,
        "unlabeled_objects_interpreted": False,
    }
    return snapshot


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Semantic completeness diagnostics / 場景語意完整度診斷",
        "",
        f"Status: **{report['status']}**. "
        "Authority: **HEURISTIC / REVIEW** until source-bound approval.",
        "",
        "原始場景不修改；不建立 Graph／stair connectivity、不猜測未標記幾何。",
        "Source is preserved; no inferred physical roles or inference topology are created.",
        "",
        "## Floor summary / 每層摘要",
        "",
        "| Floor | AREA | WALKABLE | WALL | OBSTACLE | STAIR | PORTAL | "
        "Components | Isolated | Uncovered | Suspicious portals | "
        "Conflicts | Geometry warnings |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | ---: | ---: |",
    ]
    keys = (
        "floor",
        "area_count",
        "walkable_count",
        "wall_count",
        "obstacle_count",
        "stair_count",
        "portal_count",
        "connected_components",
        "isolated_walkables",
        "uncovered_areas",
        "suspicious_portals",
        "semantic_conflicts",
        "geometry_warnings",
    )
    lines.extend(
        "| " + " | ".join(str(row[k]) for k in keys) + " |" for row in report["floor_summary"]
    )
    lines.extend(
        [
            "",
            "## AREA coverage / 區域覆蓋",
            "",
            "| AREA | Status | Geometric coverage | Overlap ratio | Uncovered "
            "| Nearest WALKABLE | Offset m |",
            "| --- | --- | --- | ---: | ---: | --- | ---: |",
        ]
    )
    for row in report["area_coverage"]:
        values = [
            row.get(k)
            for k in (
                "area_id",
                "status",
                "coverage_status",
                "walkable_overlap_ratio",
                "uncovered_ratio",
                "nearest_walkable",
                "geometry_offset_m",
            )
        ]
        lines.append(
            "| "
            + " | ".join(
                "N/A" if v is None else f"{v:.6g}" if isinstance(v, float) else str(v)
                for v in values
            )
            + " |"
        )
    lines.extend(["", "## Human review queue / 人工審查佇列", ""])
    for priority, items in report["review_queue"].items():
        lines.extend([f"### {priority} ({len(items)})", ""])
        lines.extend(
            f"- **{f['review_id']} {f['code']}** [{f['status']}] "
            f"{', '.join(f['objects']) or 'Scene'} — {f['detail']}"
            for f in items
        )
        lines.append("")
    lines.extend(["## Limits / 診斷限制", ""] + ["- " + line for line in report["limits"]])
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output: Path) -> tuple[Path, Path]:
    """Replace only the selected generated JSON/Markdown pair for repeat validation."""
    stem = output.with_suffix("") if output.suffix in {".json", ".md"} else output
    paths = stem.with_suffix(".json"), stem.with_suffix(".md")
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    paths[0].write_text(
        json.dumps(_safe_json(report), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    paths[1].write_text(_markdown(report))
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--blend", type=Path)
    source.add_argument("--input", type=Path, help="Portable synthetic/live scene snapshot JSON")
    parser.add_argument("--blender", help="Blender binary; auto-detects PATH and macOS app")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--audit", type=Path, default=Path("data/scene_audit/school_v2_semantic_audit.json")
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="JSON/Markdown output stem (repeatable)"
    )
    args = parser.parse_args()
    stem = args.output.with_suffix("") if args.output.suffix in {".json", ".md"} else args.output
    outputs = [stem.with_suffix(".json").resolve(), stem.with_suffix(".md").resolve()]
    for protected in (args.blend, args.input, args.config, args.audit):
        if protected is not None and protected.resolve() in outputs:
            parser.error("report output must not overwrite an input, configuration or scene audit")
    config = load_config(args.config)
    snapshot = (
        extract_blend(
            args.blend, args.blender, config["geometry_complexity"]["maximum_mesh_triangles"]
        )
        if args.blend
        else json.loads(args.input.read_text())
    )
    if args.audit.is_file():
        audit = json.loads(args.audit.read_text())
        snapshot["audit_binding"] = {
            "path": str(args.audit),
            "sha256": _fingerprint(args.audit)[0],
            "source_matches": _source_hash(audit) == _source_hash(snapshot),
            "floor_separation": audit.get("floor_separation", {}),
        }
        # The existing audit can supply reviewed source-bound planes only. Name-derived AREA bounds
        # and unreviewed floor-surface candidates are never imported as floor authority.
        for plane in audit.get("floor_separation", {}).get("trusted_floor_surfaces", []):
            if (
                _source_hash(audit) == _source_hash(snapshot)
                and isinstance(plane, dict)
                and plane.get("status") == "APPROVED"
                and plane.get("floor_id")
            ):
                config["floor_planes"].setdefault(plane["floor_id"], plane)
    report = validate_scene(snapshot, config)
    report["read_only_contract"] = snapshot.get("read_only_contract", {})
    report["audit_binding"] = snapshot.get("audit_binding")
    paths = write_report(report, args.output)
    print(
        json.dumps(
            {
                "outputs": [str(p) for p in paths],
                "status": report["status"],
                "semantic_counts": report["semantic_counts"],
                "review_counts": report["review_counts"],
            }
        )
    )


if __name__ == "__main__":
    main()
