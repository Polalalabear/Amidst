"""Source-bound support and exact disk clearance, independent of Blender/GT.

WALKABLE annotations specify semantic permission, never a physical floor. Actual
source triangles are intersected with that permission before they can be approved.
Compatible approved surfaces are unioned before erosion, removing internal seams.
The authoritative erosion is containment plus exact distance to the union boundary;
polygon buffer contours are only display approximations.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from shapely import constrained_delaunay_triangles, normalize, union_all
from shapely.geometry import LineString, Point, Polygon

from amidst.architectural_scale import ArchitecturalScale
from amidst.physical_authority import PhysicalPolicy
from amidst.physical_floor_stair_review import (
    _annotation_faces,
    _digest,
    _Face,
    _floor,
    _props,
    _region_faces,
)
from amidst.scene_geometry import (
    Authority,
    Coordinate,
    FloorAuthority,
    GeometryAuthorityError,
    GeometryRole,
    GeometrySupport,
    GeometrySurface,
)


def _polygons(value: Any) -> list[Any]:
    if value.is_empty:
        return []
    if value.geom_type == "Polygon":
        return [value]
    if value.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [polygon for part in value.geoms for polygon in _polygons(part)]
    return []


def _union(polygons: list[Any]) -> Any:
    # Normalize input as well as output so filesystem/dictionary order cannot
    # select a different coordinate ordering or surface identity.
    result = normalize(union_all(sorted(polygons, key=lambda p: normalize(p).wkb)))
    if not result.is_valid:
        raise ValueError("invalid support union; geometry repair is not authorized")
    return result


def _polygon_report(polygon: Any) -> dict[str, Any]:
    return {
        "exterior_xy_bu": [list(point) for point in polygon.exterior.coords],
        "holes_xy_bu": [
            [list(point) for point in ring.coords] for ring in polygon.interiors
        ],
    }


def _coordinate(value: Coordinate) -> Coordinate:
    if len(value) != 3 or any(
        isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item)
        for item in value
    ):
        raise ValueError("footpoint must contain three finite native coordinates")
    return value


@dataclass(frozen=True, slots=True)
class WalkableClearanceDecision:
    valid: bool
    reason: str
    clearance_bu: float | None
    clearance_m: float | None
    required_clearance_bu: float
    required_clearance_m: float


@dataclass(frozen=True, slots=True)
class WalkableClearanceDomain:
    """A single compatible source-bound floor island; no global free-space claim."""

    source_sha256: str
    floor: FloorAuthority
    scale: ArchitecturalScale
    policy: PhysicalPolicy
    surface_ids: tuple[str, ...]
    union_wkb: bytes
    required_clearance_bu: float
    required_clearance_m: float
    contact_tolerance_bu: float
    support_surfaces: tuple[GeometrySurface, ...]

    @classmethod
    def from_surfaces(
        cls,
        surfaces: tuple[GeometrySurface, ...],
        *,
        floor: FloorAuthority,
        scale: ArchitecturalScale,
        policy: PhysicalPolicy,
        expected_source_sha256: str,
    ) -> WalkableClearanceDomain:
        checked_scale = ArchitecturalScale.model_validate_json(scale.model_dump_json())
        checked_scale.require_source_sha256(expected_source_sha256)
        checked_floor = FloorAuthority.model_validate(floor)
        checked_policy = PhysicalPolicy.model_validate(policy)
        if checked_floor.authority != Authority.APPROVED:
            raise GeometryAuthorityError(("FLOOR_NOT_APPROVED",))
        if checked_floor.normal != (0.0, 0.0, 1.0):
            raise GeometryAuthorityError(("NON_HORIZONTAL_SUPPORT_NEEDS_SEPARATE_DOMAIN",))
        if checked_policy.authority != Authority.APPROVED or checked_policy.pending_fields():
            raise GeometryAuthorityError(("PHYSICAL_POLICY_NOT_APPROVED",))
        if checked_policy.body_model != "UPRIGHT_CYLINDER":
            raise GeometryAuthorityError(("UPRIGHT_CYLINDER_POLICY_REQUIRED",))
        if checked_policy.clearance_comparison != "MINIMUM_INCLUSIVE":
            raise GeometryAuthorityError(("MINIMUM_INCLUSIVE_POLICY_REQUIRED",))
        if not surfaces:
            raise GeometryAuthorityError(("NO_APPROVED_SUPPORT",))
        assert checked_policy.body_radius_m is not None
        assert checked_policy.body_clearance_m is not None
        assert checked_policy.collision_tolerance_m is not None
        radius_m = checked_policy.body_radius_m + checked_policy.body_clearance_m
        radius_bu = checked_scale.to_blender_units(radius_m)
        tolerance_bu = checked_scale.to_blender_units(checked_policy.collision_tolerance_m)
        polygons = []
        identities = []
        approved_surfaces = []
        for item in sorted(surfaces, key=lambda value: value.surface_id):
            surface = GeometrySurface.model_validate(item)
            if (
                surface.role != GeometryRole.WALKABLE
                or surface.support != GeometrySupport.SURFACE
                or surface.semantic_authority != Authority.APPROVED
                or surface.physical_authority != Authority.APPROVED
                or surface.floor_ids != (checked_floor.floor_id,)
                or not surface.source_face_indices
                or f"SOURCE_SHA256:{expected_source_sha256}" not in surface.evidence_ids
            ):
                raise GeometryAuthorityError((f"SUPPORT_NOT_APPROVED:{surface.surface_id}",))
            if surface.surface_id in identities:
                raise ValueError("duplicate support surface identity")
            identities.append(surface.surface_id)
            approved_surfaces.append(surface)
            if any(
                abs(point[2] - checked_floor.point[2]) > tolerance_bu
                for point in surface.vertices
            ):
                raise GeometryAuthorityError((f"INCOMPATIBLE_SUPPORT_HEIGHT:{surface.surface_id}",))
            for triangle in surface.triangles:
                polygon = Polygon([surface.vertices[index][:2] for index in triangle])
                if not polygon.is_valid or polygon.area == 0:
                    raise ValueError("support triangle must have positive valid XY area")
                polygons.append(polygon)
        united = _union(polygons)
        return cls(
            expected_source_sha256, checked_floor, checked_scale, checked_policy,
            tuple(identities), united.wkb, radius_bu, radius_m, tolerance_bu,
            tuple(approved_surfaces),
        )

    def _geometry(self) -> Any:
        from shapely import from_wkb

        return from_wkb(self.union_wkb)

    def _actual_support(self) -> list[tuple[Any, tuple[Coordinate, Coordinate, Coordinate]]]:
        return [
            (Polygon([surface.vertices[index][:2] for index in triangle]), (
                surface.vertices[triangle[0]], surface.vertices[triangle[1]],
                surface.vertices[triangle[2]],
            ))
            for surface in self.support_surfaces for triangle in surface.triangles
        ]

    @staticmethod
    def _source_height(
        x: float, y: float, triangle: tuple[Coordinate, Coordinate, Coordinate],
    ) -> float:
        a, b, c = triangle
        ab, ac = tuple(b[i] - a[i] for i in range(3)), tuple(c[i] - a[i] for i in range(3))
        nx, ny, nz = (
            ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2],
            ab[0] * ac[1] - ab[1] * ac[0],
        )
        if nz == 0:
            raise ValueError("approved support needs actual nonzero XY triangle projection")
        height = a[2] - (nx * (x - a[0]) + ny * (y - a[1])) / nz
        if not math.isfinite(height):
            raise ValueError("actual source support height is outside finite geometry range")
        return height

    @staticmethod
    def _intersection_points(value: Any) -> list[tuple[float, float]]:
        if value.is_empty:
            return []
        if value.geom_type == "Polygon":
            return [(float(x), float(y)) for x, y in value.exterior.coords]
        if value.geom_type in ("Point", "LineString", "LinearRing"):
            return [(float(x), float(y)) for x, y in value.coords]
        return [point for part in value.geoms for point in
                WalkableClearanceDomain._intersection_points(part)]

    def actual_contact_height_band(self, query_xy: Any) -> tuple[float, float] | None:
        """Common foot-Z interval against every actual support fragment in a domain.

        A plane tolerance cannot be added to a second footpoint tolerance. Linear
        source-triangle height extrema occur at the exact clipped polygon vertices.
        Keeping the intersection of these intervals is conservative for all XY
        placements; it never replaces or flattens raw support geometry.
        """
        heights = [
            self._source_height(x, y, triangle)
            for polygon, triangle in self._actual_support()
            for x, y in self._intersection_points(polygon.intersection(query_xy))
        ]
        if not heights:
            return None
        low = max(heights) - self.contact_tolerance_bu
        high = min(heights) + self.contact_tolerance_bu
        return None if low > high else (low, high)

    def _actual_point_contact(self, point: Coordinate) -> bool:
        band = self.actual_contact_height_band(Point(point[:2]))
        return band is not None and band[0] <= point[2] <= band[1]

    def _actual_segment_contact(self, start: Coordinate, end: Coordinate, query: Any) -> bool:
        if start[:2] == end[:2]:
            return self._actual_point_contact(start) and self._actual_point_contact(end)
        dx, dy = end[0] - start[0], end[1] - start[1]
        matched = False
        for polygon, triangle in self._actual_support():
            points = self._intersection_points(polygon.intersection(query))
            for x, y in points:
                matched = True
                parameter = (x - start[0]) / dx if abs(dx) >= abs(dy) else (y - start[1]) / dy
                foot_z = start[2] + parameter * (end[2] - start[2])
                actual_z = self._source_height(x, y, triangle)
                # Along each analytic source-triangle partition, residual height
                # is linear. Endpoint checks prove the entire partition.
                if not actual_z - self.contact_tolerance_bu <= foot_z <= (
                    actual_z + self.contact_tolerance_bu
                ):
                    return False
        return matched

    def _decision(self, query: Any, *, support_height_valid: bool) -> WalkableClearanceDecision:
        geometry = self._geometry()
        if not geometry.covers(query):
            return WalkableClearanceDecision(
                False, "OUTSIDE_APPROVED_WALKABLE", None, None,
                self.required_clearance_bu, self.required_clearance_m,
            )
        if not support_height_valid:
            return WalkableClearanceDecision(
                False, "OFF_SUPPORT_HEIGHT", None, None,
                self.required_clearance_bu, self.required_clearance_m,
            )
        distance = float(geometry.boundary.distance(query))
        # No tolerance subtraction: the approved equality boundary is inclusive
        # and the contact tolerance is a different quantity.
        valid = distance >= self.required_clearance_bu
        return WalkableClearanceDecision(
            valid, "PASS" if valid else "INSUFFICIENT_WALKABLE_CLEARANCE", distance,
            self.scale.to_metres(distance), self.required_clearance_bu,
            self.required_clearance_m,
        )

    def validate_point(self, point_bu: Coordinate) -> WalkableClearanceDecision:
        point = _coordinate(point_bu)
        return self._decision(
            Point(point[:2]),
            support_height_valid=self._actual_point_contact(point),
        )

    def validate_segment(
        self, start_bu: Coordinate, end_bu: Coordinate,
    ) -> WalkableClearanceDecision:
        start, end = _coordinate(start_bu), _coordinate(end_bu)
        query = Point(start[:2]) if start[:2] == end[:2] else LineString((start[:2], end[:2]))
        return self._decision(
            query,
            support_height_valid=self._actual_segment_contact(start, end, query),
        )

    def report(self) -> dict[str, Any]:
        geometry = self._geometry()
        display = normalize(geometry.buffer(-self.required_clearance_bu))
        return {
            "schema_version": "walkable-clearance-domain-v1",
            "source_sha256": self.source_sha256,
            "floor_id": self.floor.floor_id,
            "surface_ids": list(self.surface_ids),
            "union_before_erosion": True,
            "navigation_outside_walkable": "FORBIDDEN",
            "outside_is_wall_or_occluder": False,
            "erosion_authority": "EXACT_UNION_CONTAINMENT_AND_BOUNDARY_DISTANCE",
            "clearance_comparison": "MINIMUM_INCLUSIVE",
            "required_clearance_m": self.required_clearance_m,
            "required_clearance_bu": self.required_clearance_bu,
            "support_area_bu2": float(geometry.area),
            "support_area_m2": self.scale.to_square_metres(float(geometry.area)),
            "support_components": len(_polygons(geometry)),
            "support_holes": sum(len(p.interiors) for p in _polygons(geometry)),
            "union_polygons": [_polygon_report(p) for p in _polygons(geometry)],
            "display_erosion_polygons": [_polygon_report(p) for p in _polygons(display)],
            "display_contour_is_physical_authority": False,
            "contact_reference": "ACTUAL_SOURCE_TRIANGLE_HEIGHT_NOT_NOMINAL_PLANE",
            "segment_height_validation": "ANALYTIC_SOURCE_TRIANGLE_PARTITIONS",
            "source_support_geometry_sha256": _digest([
                surface.model_dump(mode="json") for surface in self.support_surfaces
            ]),
            "union_sha256": hashlib.sha256(self.union_wkb).hexdigest(),
        }


def _derived_surfaces(
    walk_id: str,
    floor_id: str,
    faces: list[_Face],
    permission: Any,
    *,
    source_sha256: str,
    approval_id: str,
    annotation_digest: str,
    numeric_epsilon: float,
) -> tuple[list[GeometrySurface], list[dict[str, Any]], Any]:
    groups: dict[str, dict[tuple[Coordinate, Coordinate, Coordinate], set[int]]] = {}
    clipped_polygons = []
    for face in faces:
        clipped = Polygon(face.footprint).intersection(permission)
        for polygon in _polygons(clipped):
            if polygon.area <= 0:
                continue
            clipped_polygons.append(polygon)
            for part in constrained_delaunay_triangles(polygon).geoms:
                points = []
                for x, y in list(part.exterior.coords)[:-1]:
                    z = WalkableClearanceDomain._source_height(x, y, face.triangle)
                    points.append((float(x), float(y), float(z)))
                if len(points) != 3:
                    raise ValueError("source intersection triangulation must produce triangles")
                ordered = sorted(points)
                canonical = ordered[0], ordered[1], ordered[2]
                groups.setdefault(face.object_id, {}).setdefault(canonical, set()).add(
                    face.source_face_index,
                )
    surfaces, bindings = [], []
    for object_id, triangles in sorted(groups.items()):
        vertices = tuple(sorted({p for triangle in triangles for p in triangle}))
        indices = {point: index for index, point in enumerate(vertices)}
        canonical_triangles = sorted(triangles)
        mesh_triangles = tuple(
            (indices[triangle[0]], indices[triangle[1]], indices[triangle[2]])
            for triangle in canonical_triangles
        )
        source_faces = tuple(sorted({i for values in triangles.values() for i in values}))
        surface_id = "SUPPORT-" + _digest(
            {"walkable": walk_id, "source_object": object_id, "triangles": canonical_triangles},
        )[:20]
        surface = GeometrySurface(
            surface_id=surface_id, source_object_id=object_id, source_face_indices=source_faces,
            role=GeometryRole.WALKABLE, floor_ids=(floor_id,), vertices=vertices,
            triangles=mesh_triangles, semantic_authority=Authority.APPROVED,
            physical_authority=Authority.APPROVED, support=GeometrySupport.SURFACE,
            approval_id=approval_id, evidence_ids=(
                f"SOURCE_SHA256:{source_sha256}", f"ANNOTATION_SHA256:{annotation_digest}",
                f"APPROVED_WALKABLE_PERMISSION:{walk_id}", "EXACT_SOURCE_TRIANGLE_INTERSECTION",
            ),
        )
        surfaces.append(surface)
        bindings.append({
            "surface_id": surface_id, "source_object_id": object_id,
            "source_face_indices": list(source_faces),
            "triangle_source_face_indices": [sorted(triangles[t]) for t in canonical_triangles],
        })
    return surfaces, bindings, _union(clipped_polygons)


def build_source_bound_floor_support(
    audit: Mapping[str, Any],
    survey: Mapping[str, Any],
    *,
    scale: ArchitecturalScale,
    approved_walkable_ids: tuple[str, ...],
    approval_id: str,
    support_heights_bu: Mapping[str, float],
    contact_tolerance_m: float,
    horizontal_normal_abs_z_min: float,
    max_triangles_per_region: int,
    numeric_epsilon: float,
) -> dict[str, Any]:
    """Approve exact proven subdomains, never fill uncovered annotation or holes.

    The caller supplies explicit semantic permission IDs and a review approval.
    Geometry-derived support is tied to source faces, the immutable audit and
    source hash. Off-height source layers remain separate REVIEW evidence.
    """
    source = audit.get("source_sha256")
    if not isinstance(source, str) or survey.get("source_sha256") != source:
        raise ValueError("floor support source SHA binding mismatch")
    scale.require_source_sha256(source)
    if survey.get("audit_content_sha256") != _digest(audit):
        raise ValueError("source survey audit content binding mismatch")
    if survey.get("source_preserved") is not True:
        raise ValueError("source preservation attestation is required")
    if not approval_id.strip():
        raise ValueError("support approval_id must be explicit")
    if len(set(approved_walkable_ids)) != len(approved_walkable_ids):
        raise ValueError("duplicate approved WALKABLE permission identity")
    if (
        isinstance(contact_tolerance_m, bool) or not math.isfinite(contact_tolerance_m)
        or contact_tolerance_m < 0
        or isinstance(horizontal_normal_abs_z_min, bool)
        or not math.isfinite(horizontal_normal_abs_z_min)
        or not 0 < horizontal_normal_abs_z_min <= 1
        or isinstance(max_triangles_per_region, bool)
        or not isinstance(max_triangles_per_region, int) or max_triangles_per_region <= 0
        or isinstance(numeric_epsilon, bool) or not math.isfinite(numeric_epsilon)
        or numeric_epsilon <= 0
    ):
        raise ValueError("invalid source floor support limits")
    tolerance = scale.to_blender_units(contact_tolerance_m)
    regions: dict[str, Mapping[str, Any]] = {}
    for region in survey.get("regions", []):
        if region.get("kind") == "FLOOR_SUPPORT":
            identity = region["region_id"]
            if identity in regions:
                raise ValueError("duplicate floor support source region")
            regions[identity] = region
    raw_rows = [
        row for row in audit.get("objects", [])
        if _props(row).get("semantic_class") == "WALKABLE"
    ]
    rows = {
        row["object"]: row for row in audit.get("objects", [])
        if _props(row).get("semantic_class") == "WALKABLE"
    }
    if len(raw_rows) != len(rows):
        raise ValueError("duplicate WALKABLE annotation identity")
    if not set(approved_walkable_ids) <= set(rows):
        raise ValueError("approved permission identity is not an explicit WALKABLE annotation")
    result_rows: list[dict[str, Any]] = []
    all_surfaces: list[dict[str, Any]] = []
    all_bindings: list[dict[str, Any]] = []
    for walk_id, row in sorted(rows.items()):
        floor_id = _floor(row)
        if floor_id is None or floor_id not in support_heights_bu:
            raise ValueError("WALKABLE requires an explicit source support floor selection")
        height = support_heights_bu[floor_id]
        if isinstance(height, bool) or not math.isfinite(height):
            raise ValueError("source support floor height must be finite")
        annotation = _union([Polygon([(p[0], p[1]) for p in t]) for t in _annotation_faces(row)])
        if annotation.is_empty or annotation.area <= 0:
            raise ValueError("WALKABLE semantic permission must have positive actual area")
        region = regions.get(walk_id)
        if region is not None and region.get("floor_id") != floor_id:
            raise ValueError("source region floor binding differs from its WALKABLE annotation")
        reasons = []
        if walk_id not in approved_walkable_ids:
            reasons.append("WALKABLE_SEMANTIC_PERMISSION_NOT_APPROVED")
        if region is None:
            reasons.append("SOURCE_REGION_MISSING")
        elif region.get("complete") is not True:
            reasons.append("SOURCE_REGION_INCOMPLETE")
        faces = [] if region is None else _region_faces(region, max_triangles_per_region)
        compatible = [
            face for face in faces
            if face.horizontal_normal >= horizontal_normal_abs_z_min
            and all(abs(p[2] - height) <= tolerance for p in face.triangle)
        ]
        compatible_identities = set(compatible)
        off_height = [
            face for face in faces
            if face.horizontal_normal >= horizontal_normal_abs_z_min
            and face not in compatible_identities
        ]
        surfaces, bindings, support = _derived_surfaces(
            walk_id, floor_id, compatible, annotation, source_sha256=source,
            approval_id=approval_id, annotation_digest=_digest(row),
            numeric_epsilon=numeric_epsilon,
        )
        if support.is_empty:
            reasons.append("NO_COMPATIBLE_ACTUAL_SOURCE_SUPPORT")
        uncovered = normalize(annotation.difference(support))
        # Positive residuals are retained even when far below diagnostic epsilon.
        complete = uncovered.is_empty or uncovered.area == 0
        status = "APPROVED" if not reasons else "HUMAN_REVIEW"
        if status == "APPROVED":
            all_surfaces.extend(surface.model_dump(mode="json") for surface in surfaces)
            all_bindings.extend(bindings)
        result_rows.append({
            "walkable_id": walk_id, "floor_id": floor_id, "authority": status,
            "approved_scope": "EXACT_SOURCE_SUPPORTED_SUBDOMAIN_ONLY" if not reasons else None,
            "source_support_height_bu": height, "source_support_height_m": scale.to_metres(height),
            "annotation_z_range_bu": [min(p[2] for t in _annotation_faces(row) for p in t),
                                      max(p[2] for t in _annotation_faces(row) for p in t)],
            "old_plane_offset_reason_resolved": bool(compatible),
            "source_selection_complete": region is not None and region.get("complete") is True,
            "source_triangle_count": len(faces),
            "compatible_source_triangle_count": len(compatible),
            "source_geometry_modified": False, "geometry_flattened": False,
            "annotation_area_bu2": float(annotation.area), "support_area_bu2": float(support.area),
            "support_area_m2": scale.to_square_metres(float(support.area)),
            "uncovered_area_bu2": float(uncovered.area),
            "uncovered_area_m2": scale.to_square_metres(float(uncovered.area)),
            "support_coverage_ratio": min(1.0, float(support.area / annotation.area)),
            "full_annotation_supported": complete,
            "uncovered_authority": "HUMAN_REVIEW" if not complete else "NOT_APPLICABLE",
            "uncovered_polygons": [_polygon_report(p) for p in _polygons(uncovered)],
            "support_components": len(_polygons(support)),
            "support_holes": sum(len(p.interiors) for p in _polygons(support)),
            "support_surface_ids": [s.surface_id for s in surfaces] if not reasons else [],
            "reason_codes": reasons,
            "other_height_source_evidence": [{
                "source_object_id": face.object_id, "source_face_index": face.source_face_index,
                "z_range_bu": list(face.z_range),
                "authority": "HUMAN_REVIEW_NOT_AUTOMATIC_LOCAL_FLOOR_OR_RAMP",
            } for face in off_height],
        })
    approved_floors = []
    for floor_id, height in sorted(support_heights_bu.items()):
        support_ids = tuple(
            row["walkable_id"] for row in result_rows
            if row["floor_id"] == floor_id and row["authority"] == "APPROVED"
        )
        if support_ids:
            approved_floors.append(FloorAuthority(
                floor_id=floor_id, point=(0.0, 0.0, height), normal=(0.0, 0.0, 1.0),
                authority=Authority.APPROVED, approval_id=approval_id,
                evidence_ids=(f"SOURCE_SHA256:{source}", *(
                    f"EXACT_SOURCE_SUPPORTED_WALKABLE:{identity}" for identity in support_ids
                )),
            ).model_dump(mode="json"))
    return {
        "schema_version": "source-bound-floor-support-v1",
        "source_sha256": source, "audit_content_sha256": _digest(audit),
        "survey_content_sha256": _digest(survey), "scale_m_per_bu": scale.metres_per_blender_unit,
        "approval_id": approval_id,
        "authority_scope": "SUPPORTED_PERMISSION_INTERSECTION_NOT_GLOBAL_FLOOR_COMPLETENESS",
        "body_or_ceiling_clearance_approved": False, "source_geometry_modified": False,
        "floor_authorities": approved_floors,
        "walkable_reviews": result_rows, "support_surfaces": all_surfaces,
        "source_bindings": all_bindings,
        "approved_supported_subdomain_count": sum(
            row["authority"] == "APPROVED" for row in result_rows
        ),
        "whole_annotation_supported_count": sum(
            row["full_annotation_supported"] for row in result_rows
        ),
        "review_uncovered_subdomain_count": sum(
            not row["full_annotation_supported"] for row in result_rows
        ),
    }
