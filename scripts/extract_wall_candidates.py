"""Read-only, source-bound evaluated-mesh WALL patch extraction for PILOT review.

Run with Blender --background --disable-autoexec SOURCE --python this_file --
--output data/scene_audit/school_v3_wall_candidates.json --expected-source-sha256 SHA.
Annotations select existing evaluated faces only; no faces, colliders, topology or
elevator transitions are added, and the Blender source is never saved.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bounds(points: list[list[float]]) -> dict[str, list[float]]:
    return {
        "minimum": [min(p[i] for p in points) for i in range(3)],
        "maximum": [max(p[i] for p in points) for i in range(3)],
    }


def box_distance(a: dict[str, Any], b: dict[str, Any], dimensions: int = 2) -> float:
    return math.sqrt(
        sum(
            max(a["minimum"][i] - b["maximum"][i], b["minimum"][i] - a["maximum"][i], 0) ** 2
            for i in range(dimensions)
        )
    )


def polygon_area(points: list[list[float]]) -> float:
    # Magnitude of the oriented planar polygon area vector; valid for concave faces too.
    value = [0.0, 0.0, 0.0]
    for a, b in zip(points, points[1:] + points[:1], strict=True):
        value[0] += a[1] * b[2] - a[2] * b[1]
        value[1] += a[2] * b[0] - a[0] * b[2]
        value[2] += a[0] * b[1] - a[1] * b[0]
    return 0.5 * math.sqrt(sum(x * x for x in value))


def clip_polygon_box(
    points: list[list[float]], box: dict[str, Any], padding: float = 0.0
) -> list[list[float]]:
    """Exact convex half-space clipping; AABB overlap alone never fills a doorway."""
    clipped = points
    for axis in range(3):
        for sign, level in (
            (1, box["minimum"][axis] - padding),
            (-1, box["maximum"][axis] + padding),
        ):
            result = []
            if not clipped:
                return []
            for a, b in zip(clipped, clipped[1:] + clipped[:1], strict=True):
                da, db = sign * (a[axis] - level), sign * (b[axis] - level)
                if da >= 0:
                    result.append(a)
                if (da >= 0) != (db >= 0):
                    ratio = da / (da - db)
                    result.append([a[i] + ratio * (b[i] - a[i]) for i in range(3)])
            clipped = result
    return clipped


def point_in_triangle_xy(point: list[float], triangle: list[list[float]]) -> bool:
    a, b, c = triangle
    denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(denominator) < 1e-9:
        return False
    u = ((b[1] - c[1]) * (point[0] - c[0]) + (c[0] - b[0]) * (point[1] - c[1])) / denominator
    v = ((c[1] - a[1]) * (point[0] - c[0]) + (a[0] - c[0]) * (point[1] - c[1])) / denominator
    return u >= -1e-8 and v >= -1e-8 and u + v <= 1 + 1e-8


def horizontal_sections(
    polygons: list[list[list[float]]], z: float, tangent: list[float]
) -> list[list[float]]:
    intervals = []
    for points in polygons:
        ts = []
        for a, b in zip(points, points[1:] + points[:1], strict=True):
            if (a[2] <= z < b[2]) or (b[2] <= z < a[2]):
                ratio = (z - a[2]) / (b[2] - a[2])
                ts.append(sum((a[i] + ratio * (b[i] - a[i])) * tangent[i] for i in range(3)))
        if len(ts) >= 2:
            intervals.append([min(ts), max(ts)])
    merged: list[list[float]] = []
    for low, high in sorted(intervals):
        if merged and low <= merged[-1][1] + 1e-3:
            merged[-1][1] = max(high, merged[-1][1])
        else:
            merged.append([low, high])
    return merged


def material_flags(material: Any) -> list[str]:
    if material is None:
        return ["MATERIAL_ABSENT"]
    flags = []
    if material.diffuse_color[3] < 0.99:
        flags.append("MATERIAL_ALPHA")
    if re.search(r"glass|glaz|window|door|curtain|decor", material.name, re.I):
        flags.append("AMBIGUOUS_WINDOW_DOOR_DECOR_MATERIAL_NAME")
    if material.use_nodes and material.node_tree:
        for node in material.node_tree.nodes:
            if node.type in {"BSDF_TRANSPARENT", "BSDF_GLASS", "BSDF_REFRACTION"}:
                flags.append("TRANSMISSIVE_SHADER")
            if node.type == "BSDF_PRINCIPLED":
                for name in ("Alpha", "Transmission Weight"):
                    socket = node.inputs.get(name)
                    if socket and (
                        socket.is_linked
                        or (
                            float(socket.default_value) < 0.99
                            if name == "Alpha"
                            else float(socket.default_value) > 0.01
                        )
                    ):
                        flags.append("POSSIBLE_ALPHA_OR_TRANSMISSION")
    return sorted(set(flags))


def extract_patches(obj: Any, depsgraph: Any, params: dict[str, float]) -> list[dict[str, Any]]:
    """Merge only edge-connected, coplanar actual faces, including duplicated backfaces."""
    np = importlib.import_module("numpy")
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        if not mesh.vertices or not mesh.polygons:
            return []
        coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", coordinates)
        matrix = np.asarray(evaluated.matrix_world, dtype=np.float64)
        world = coordinates.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
        normals = np.empty(len(mesh.polygons) * 3, dtype=np.float64)
        mesh.polygons.foreach_get("normal", normals)
        normals = normals.reshape(-1, 3) @ np.linalg.inv(matrix[:3, :3])
        lengths = np.linalg.norm(normals, axis=1)
        normals /= np.maximum(lengths[:, None], 1e-20)
        selected = np.flatnonzero(
            (np.abs(normals[:, 2]) <= params["vertical_max_abs_nz"]) & (lengths > 1e-12)
        )
        # World-coordinate weld joins SketchUp's duplicated front/back vertices.
        weld = params["weld_epsilon"]
        faces: list[dict[str, Any]] = []
        edge_faces: dict[Any, list[int]] = defaultdict(list)
        for index in selected:
            p = mesh.polygons[int(index)]
            points = world[list(p.vertices)].tolist()
            area = polygon_area(points)
            if area <= weld * weld:
                continue
            normal = normals[index].tolist()
            if normal[0] < -1e-8 or (abs(normal[0]) <= 1e-8 and normal[1] < 0):
                normal = [-x for x in normal]
            keys = [tuple(round(x / weld) for x in point) for point in points]
            fi = len(faces)
            faces.append(
                {
                    "index": int(index),
                    "points": points,
                    "normal": normal,
                    "plane": sum(a * b for a, b in zip(normal, points[0], strict=True)),
                    "area": area,
                    "material": p.material_index,
                    "geometry_key": tuple(sorted(keys)),
                }
            )
            for a, b in zip(keys, keys[1:] + keys[:1], strict=True):
                edge_faces[tuple(sorted((a, b)))].append(fi)
        parent = list(range(len(faces)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for linked in edge_faces.values():
            for offset, i in enumerate(linked):
                for j in linked[offset + 1 :]:
                    a, b = faces[i], faces[j]
                    if (
                        sum(x * y for x, y in zip(a["normal"], b["normal"], strict=True))
                        >= params["continuity_min_normal_dot"]
                        and abs(a["plane"] - b["plane"]) <= params["plane_epsilon"]
                    ):
                        parent[find(j)] = find(i)
        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for index, face in enumerate(faces):
            groups[find(index)].append(face)
        result = []
        for group in groups.values():
            unique = {face["geometry_key"]: face for face in group}
            points = [point for face in unique.values() for point in face["points"]]
            box = bounds(points)
            height = box["maximum"][2] - box["minimum"][2]
            normal = group[0]["normal"]
            horizontal_length = math.hypot(normal[0], normal[1])
            tangent = [-normal[1] / horizontal_length, normal[0] / horizontal_length, 0.0]
            ts = [sum(x * y for x, y in zip(point, tangent, strict=True)) for point in points]
            extent = max(ts) - min(ts)
            if height < params["candidate_min_height"] or extent < params["candidate_min_extent"]:
                continue
            materials = sorted({face["material"] for face in group})
            flags, names = [], []
            for index in materials:
                material = mesh.materials[index] if index < len(mesh.materials) else None
                names.append(material.name if material else "NONE")
                flags.extend(material_flags(material))
            area = sum(face["area"] for face in unique.values())
            result.append(
                {
                    "object": obj.name,
                    "collections": sorted(c.name for c in obj.users_collection),
                    "evaluated_mesh_polygons": len(mesh.polygons),
                    "evaluated_face_indices": sorted(face["index"] for face in group),
                    "bounds": box,
                    "normal": normal,
                    "plane": group[0]["plane"],
                    "tangent": tangent,
                    "tangent_interval": [min(ts), max(ts)],
                    "height": height,
                    "extent": extent,
                    "unique_surface_area": area,
                    "rectangular_fill_ratio": min(1.0, area / (height * extent)),
                    "duplicate_backface_count": len(group) - len(unique),
                    "surface_continuity": "WELDED_EDGE_CONNECTED_COPLANAR_EVALUATED_FACES",
                    "materials": sorted(set(names)),
                    "material_review_flags": sorted(set(flags)),
                    "hidden_render": bool(obj.hide_render),
                    "hidden_viewport": bool(obj.hide_get()),
                    "polygons": [face["points"] for face in unique.values()],
                }
            )
        return result
    finally:
        evaluated.to_mesh_clear()


def semantics(bpy: Any, depsgraph: Any) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obj in sorted(bpy.context.scene.objects, key=lambda x: x.name):
        role = obj.get("semantic_class")
        if role is None:
            role = next(
                (
                    semantic
                    for prefix, semantic in (
                        ("AREA_", "AREA"),
                        ("PORTAL_", "PORTAL"),
                        ("WALK_", "WALKABLE"),
                        ("WALKABLE_", "WALKABLE"),
                    )
                    if obj.name.startswith(prefix)
                ),
                None,
            )
        if role not in {"AREA", "WALKABLE", "PORTAL"} or obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            world = [list(evaluated.matrix_world @ v.co) for v in mesh.vertices]
            if not world:
                continue
            match = re.search(r"(?:^|_)(\d+F)(?:_|$)", obj.name)
            floor = obj.get("floor_id") or (match.group(1) if match else None)
            row = {"object": obj.name, "floor": floor, "bounds": bounds(world)}
            if role == "WALKABLE":
                mesh.calc_loop_triangles()
                row["triangles"] = [[world[i] for i in t.vertices] for t in mesh.loop_triangles]
                row["height"] = sum(p[2] for p in world) / len(world)
            result[str(role)].append(row)
        finally:
            evaluated.to_mesh_clear()
    return result


def classify(
    patch: dict[str, Any],
    peers: list[dict[str, Any]],
    semantic: dict[str, Any],
    floors: dict[str, float],
    params: dict[str, float],
) -> None:
    box, normal, tangent = patch["bounds"], patch["normal"], patch["tangent"]
    floor = min(floors, key=lambda f: abs(box["minimum"][2] - floors[f]))
    floor_height = floors[floor]
    patch["floor"] = floor
    patch["floor_basis"] = "NEAREST_EXISTING_WALKABLE_PLANE_GEOMETRY_NOT_METRE_CERTIFICATION"
    patch["floor_contact_offset"] = abs(box["minimum"][2] - floor_height)
    patch["nearby_area"] = [
        {"object": row["object"], "xy_bounds_distance": box_distance(box, row["bounds"])}
        for row in semantic["AREA"]
        if row["floor"] == floor and box_distance(box, row["bounds"]) <= params["near_distance"]
    ]
    patch["nearby_portal"] = []
    portal_conflicts = []
    for row in semantic["PORTAL"]:
        if row["floor"] != floor or box_distance(box, row["bounds"], 3) > params["near_distance"]:
            continue
        actual_area = sum(
            polygon_area(clip_polygon_box(p, row["bounds"], params["portal_padding"]))
            for p in patch["polygons"]
        )
        patch["nearby_portal"].append(
            {
                "object": row["object"],
                "bounds_distance": box_distance(box, row["bounds"], 3),
                "actual_surface_intersection_area": actual_area,
                "protected_aperture": True,
            }
        )
        if actual_area > params["weld_epsilon"] ** 2:
            portal_conflicts.append(row["object"])
    section_z = floor_height + params["section_above_floor"]
    sections = horizontal_sections(patch["polygons"], section_z, tangent)
    horizontal_normal_squared = normal[0] ** 2 + normal[1] ** 2
    offset_at_z = patch["plane"] - normal[2] * section_z
    origin = [normal[i] * offset_at_z / horizontal_normal_squared for i in range(2)]
    samples = [
        [
            origin[0] + tangent[0] * (low + (high - low) * (i + 0.5) / 17),
            origin[1] + tangent[1] * (low + (high - low) * (i + 0.5) / 17),
        ]
        for low, high in sections
        for i in range(17)
    ]
    related_walk = [
        row
        for row in semantic["WALKABLE"]
        if row["floor"] == floor and box_distance(box, row["bounds"]) <= params["near_distance"]
    ]
    intruded_walk = []
    # Both side probes must be interior to a WALKABLE triangle union. A boundary
    # contact or thin wall in the unwalkable strip between annotations is not intrusion.
    for row in related_walk:
        hits = 0
        for point in samples:
            left = [point[i] + normal[i] * params["walk_probe_offset"] for i in range(2)]
            right = [point[i] - normal[i] * params["walk_probe_offset"] for i in range(2)]
            if all(
                any(point_in_triangle_xy(p, tri) for tri in row["triangles"]) for p in (left, right)
            ):
                hits += 1
        if hits:
            intruded_walk.append({"object": row["object"], "interior_sample_count": hits})
    patch["walkable_relation"] = {
        "nearby": [row["object"] for row in related_walk],
        "section_z": section_z,
        "actual_horizontal_sections": sections,
        "test": "17_INTERIOR_SECTION_SAMPLES_PER_INTERVAL_BOTH_SIDE_PROBES_IN_TRIANGLE_UNION",
        "sample_count": len(samples),
        "interior_conflicts": intruded_walk,
    }
    thickness = []
    for other in peers:
        if other is patch or other["object"] != patch["object"]:
            continue
        if sum(a * b for a, b in zip(normal, other["normal"], strict=True)) < 0.9999:
            continue
        separation = abs(patch["plane"] - other["plane"])
        if not params["thickness_min"] <= separation <= params["thickness_max"]:
            continue
        a, b = patch["tangent_interval"], other["tangent_interval"]
        xy_overlap = max(0.0, min(a[1], b[1]) - max(a[0], b[0])) / patch["extent"]
        z_overlap = (
            max(
                0.0,
                min(box["maximum"][2], other["bounds"]["maximum"][2])
                - max(box["minimum"][2], other["bounds"]["minimum"][2]),
            )
            / patch["height"]
        )
        if xy_overlap >= 0.7 and z_overlap >= 0.9:
            thickness.append(
                {
                    "paired_patch": other["candidate_id"],
                    "separation": separation,
                    "extent_overlap_ratio": xy_overlap,
                    "height_overlap_ratio": z_overlap,
                    "basis": "SAME_SOURCE_OBJECT_PARALLEL_SURFACE_SUPPORT_NOT_VOLUME_PROOF",
                }
            )
    patch["thickness_evidence"] = sorted(thickness, key=lambda row: row["separation"])
    reasons = []
    if patch["height"] < params["auto_min_height"]:
        reasons.append("INSUFFICIENT_FULL_STOREY_HEIGHT_WINDOW_PANEL_DECOR_OR_FURNITURE_REVIEW")
    if patch["height"] > params["auto_max_height"]:
        reasons.append("MULTI_STOREY_OR_UNASSIGNED_FLOOR_EXTENT_REVIEW")
    if patch["extent"] < params["auto_min_extent"]:
        reasons.append("NARROW_DOOR_PANEL_COLUMN_OR_DECOR_REVIEW")
    if patch["floor_contact_offset"] > params["floor_contact_tolerance"]:
        reasons.append("DOES_NOT_CONTACT_EXISTING_FLOOR_WINDOW_LINTEL_OR_DECOR_REVIEW")
    if not patch["nearby_area"] or not related_walk:
        reasons.append("NO_NEARBY_SAME_FLOOR_AREA_AND_WALKABLE_SUPPORT")
    if not sections:
        reasons.append("NO_ACTUAL_SURFACE_AT_LOWER_WALL_SECTION")
    if intruded_walk:
        reasons.append("ACTUAL_SURFACE_INSIDE_EXISTING_WALKABLE_REVIEW")
    if portal_conflicts:
        reasons.append("PROTECTED_PORTAL_APERTURE_INTERSECTION_REQUIRES_HUMAN_REVIEW")
    if patch["material_review_flags"]:
        reasons.extend(patch["material_review_flags"])
    if patch["hidden_render"] or patch["hidden_viewport"]:
        reasons.append("HIDDEN_GEOMETRY_REVIEW")
    if not thickness and (
        patch["extent"] < params["broad_sheet_min_extent"] or patch["rectangular_fill_ratio"] < 0.9
    ):
        reasons.append("NO_THICKNESS_SUPPORT_THIN_PANEL_OR_DECOR_REVIEW")
    patch["protected_portal_conflicts"] = portal_conflicts
    patch["status"] = "HUMAN_REVIEW" if reasons else "AUTO_CONFIRMED_WALL"
    patch["semantic_class"] = "WALL" if not reasons else "WALL_CANDIDATE"
    patch["reasons"] = reasons or [
        "VERTICAL_CONTINUOUS_OPAQUE_FULL_HEIGHT_SURFACE_WITH_FLOOR_CONTACT",
        "SUBSTANTIAL_EXTENT_AND_PARALLEL_SURFACE_SUPPORT"
        if thickness
        else "BROAD_CONTINUOUS_SHEET_WITH_SUBSTANTIAL_ARCHITECTURAL_EXTENT",
        "SAME_FLOOR_AREA_WALKABLE_ADJACENCY_WITHOUT_TESTED_INTERIOR_INTRUSION",
        "NO_ACTUAL_SURFACE_INTERSECTION_WITH_PROTECTED_PORTAL_BOXES",
    ]
    patch["annotation"] = {
        "applied_to_source": False,
        "kind": "SOURCE_BOUND_EVALUATED_FACE_SELECTION_SIDECAR",
        "evaluated_face_indices": patch["evaluated_face_indices"] if not reasons else [],
        "create_or_fill_geometry": False,
        "movement_collider_installed": False,
        "portal_exclusion_policy": "ANY_ACTUAL_FACE_INTERSECTION_PREVENTS_AUTO_CONFIRMATION",
    }
    del patch["polygons"]


def write_report(result: dict[str, Any], output: Path) -> None:
    counts, source = result["summary"], result["source"]
    lines = [
        "# PILOT / SYNTHETIC SAMPLE — WALL candidate report",
        "",
        "本報告唯讀提取既有 evaluated mesh；不儲存或修改來源 .blend。",
        "計數單位是 **同一 object 內 edge-connected coplanar surface patch**；",
        "相反面的重複三角形去重，牆的兩個不同實體表面仍分開計數。",
        "完整 object 不因局部牆面被重新分類；自動標記位於來源 SHA 綁定的 JSON sidecar。",
        "",
        f"- Source: `{source['path']}`; SHA-256 `{source['sha256']}`",
        f"- AUTO_CONFIRMED_WALL: **{counts['auto_confirmed_wall_patches']}** patches / "
        f"{counts['auto_confirmed_source_objects']} source objects",
        f"- HUMAN_REVIEW: **{counts['human_review_patches']}** patches / "
        f"{counts['human_review_source_objects']} source objects",
        "- Source object totals can overlap when one mesh contains both clear walls and",
        "  ambiguous surfaces; these are patch annotations, never whole-object labels。",
        f"- Scanned architectural meshes: {counts['architectural_meshes']}; "
        f"source polygons: {counts['architectural_source_polygons']}",
        f"- Protected PORTAL annotations: {counts['protected_portals']}; "
        "auto-confirmed surface/aperture conflicts: **0**",
        "",
        "所有 bounds、height、extent、separation 均為 **Blender native scene units**。",
        "Scene 宣告 METRIC / scale_length=1；既有 WALKABLE planes Z=25 / 165，",
        "140-unit storey separation 的實際米制尺度尚未人工認證。本報告不修正尺度。",
        "Floor 依既有 WALKABLE 幾何分配，並不核准樓層平面、導航或碰撞 authority。",
        "`AREA_*_ELEVATOR` 僅保留歷史名稱；沒有 elevator，也不建立 transition。",
        "GT 不參與此提取；沒有 Graph、ranking、reconstruction 或 Case 1–3 benchmark。",
        "",
        "## Extraction policy",
        "",
        "- World-space polygon normal verticality、edge-welded coplanar connectivity、",
        "  actual unique surface area、height、extent、same-object parallel thickness evidence。",
        "- AREA proximity uses existing same-floor AABB; WALKABLE tests actual horizontal",
        "  face sections with two-sided points in the existing triangulated surface union。",
        "  WALKABLE intrusion check is sampled evidence, not a complete collision proof。",
        "- Portal protection clips every actual face against the protected PORTAL AABB",
        "  (with padding); any nonzero surface intersection forces HUMAN_REVIEW。",
        "  No wall rectangle, AABB collider, aperture infill or source geometry is created。",
        "- Alpha/transmission/window/door/decor material hints, short/narrow/floating",
        "  surfaces, weak extent/thickness, hidden geometry and spatial conflicts",
        "  remain HUMAN_REVIEW。",
        "- Candidate minima intentionally exclude tiny trim, edges and small props.",
        "  The numbers are extraction candidates above stated thresholds, not all scene surfaces。",
        "",
        "## Thresholds (native scene units)",
        "",
        "```json",
        json.dumps(result["parameters"], indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    review = [row for row in result["candidates"] if row["status"] == "HUMAN_REVIEW"]
    reason_counts = Counter(reason for row in review for reason in row["reasons"])
    reason_ids = {
        reason: f"R{index + 1:02d}" for index, (reason, _) in enumerate(reason_counts.most_common())
    }
    lines.extend(
        [
            "## HUMAN_REVIEW reason breakdown",
            "",
            "一個 patch 可以有多個原因，所以下表原因數量不應相加成 patch 總數。",
            "Short codes are used in the object/floor index below;",
            "detailed patches retain full reasons。",
            "",
            "| Code | Reason | Patches |",
            "| --- | --- | ---: |",
        ]
    )
    for reason, count in reason_counts.most_common():
        lines.append(f"| {reason_ids[reason]} | `{reason}` | {count} |")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in review:
        groups[(row["object"], row["floor"])].append(row)
    lines.extend(
        [
            "",
            "## HUMAN_REVIEW object / floor index",
            "",
            "按 review patch 數排序；原因列最多三個主要原因及其 patch 數，",
            "完整 bounds、AREA／PORTAL、理由和 source face references 在後面的逐 patch 詳列。",
            "",
            "| Object | Floor | Review patches | Leading reasons | First patch |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for (obj, floor), rows in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
        reasons = Counter(reason for row in rows for reason in row["reasons"])
        leading = ", ".join(
            f"{reason_ids[reason]} ({count})" for reason, count in reasons.most_common(3)
        )
        lines.append(
            f"| {obj.replace('|', ' ')} | {floor} | {len(rows)} | "
            f"{leading} | {rows[0]['candidate_id']} |"
        )
    lines.append("")
    for status in ("AUTO_CONFIRMED_WALL", "HUMAN_REVIEW"):
        lines.extend([f"## {status}", ""])
        for row in result["candidates"]:
            if row["status"] != status:
                continue
            area = ", ".join(x["object"] for x in row["nearby_area"]) or "NONE"
            portals = ", ".join(x["object"] for x in row["nearby_portal"]) or "NONE"
            lines.extend(
                [
                    f"### {row['candidate_id']} — {row['object']} / {row['floor']}",
                    "",
                    f"- Bounds: `{row['bounds']['minimum']}` → `{row['bounds']['maximum']}`",
                    f"- Height {row['height']:.4f}; extent {row['extent']:.4f}; "
                    f"unique area {row['unique_surface_area']:.4f}; "
                    f"fill {row['rectangular_fill_ratio']:.4f}",
                    f"- Vertical normal: `{row['normal']}`; "
                    f"floor offset {row['floor_contact_offset']:.4f}",
                    f"- Surface continuity: {row['surface_continuity']}; "
                    f"faces {len(row['evaluated_face_indices'])}; "
                    f"duplicate backfaces {row['duplicate_backface_count']}",
                    f"- Thickness/parallel support: `{row['thickness_evidence']}`",
                    f"- AREA: {area}",
                    f"- WALKABLE: {', '.join(row['walkable_relation']['nearby']) or 'NONE'}",
                    f"- PORTAL: {portals}",
                    "- Portal surface conflicts: "
                    f"{', '.join(row['protected_portal_conflicts']) or 'NONE'}",
                    f"- Materials: {', '.join(row['materials'])}",
                    f"- Reasons: {'; '.join(row['reasons'])}",
                    "",
                ]
            )
    output.with_suffix(".md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    bpy = importlib.import_module("bpy")
    vector = importlib.import_module("mathutils").Vector
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    source = Path(bpy.data.filepath).resolve()
    initial = source.stat()
    source_digest = digest(source)
    if source_digest != args.expected_source_sha256:
        raise ValueError("source SHA-256 does not match the explicitly requested scene")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    semantic = semantics(bpy, depsgraph)
    plane_samples: dict[str, list[float]] = defaultdict(list)
    for row in semantic["WALKABLE"]:
        if row["floor"]:
            plane_samples[row["floor"]].append(row["height"])
    floors = {floor: sorted(samples)[len(samples) // 2] for floor, samples in plane_samples.items()}
    levels = sorted(floors.values())
    if len(levels) < 2 or any(b - a <= 0 for a, b in zip(levels, levels[1:], strict=False)):
        raise ValueError("two distinct existing WALKABLE floor levels required for relative scale")
    spacing = min(b - a for a, b in zip(levels, levels[1:], strict=False))
    params = {
        "storey_spacing": spacing,
        "vertical_max_abs_nz": math.sin(math.radians(5)),
        "continuity_min_normal_dot": math.cos(math.radians(1)),
        "weld_epsilon": spacing * 1e-5,
        "plane_epsilon": spacing * 1e-4,
        "candidate_min_height": spacing * 0.2,
        "candidate_min_extent": spacing * 0.12,
        "auto_min_height": spacing * 0.75,
        "auto_max_height": spacing * 1.15,
        "auto_min_extent": spacing * 0.75,
        "broad_sheet_min_extent": spacing * 2.0,
        "floor_contact_tolerance": spacing * 0.07,
        "near_distance": spacing * 0.25,
        "thickness_min": spacing * 0.015,
        "thickness_max": spacing * 0.2,
        "section_above_floor": spacing * 0.15,
        "walk_probe_offset": spacing * 0.005,
        "portal_padding": spacing * 0.002,
    }
    candidates = []
    inventory: Counter[str] = Counter()
    for obj in sorted(bpy.context.scene.objects, key=lambda x: x.name):
        if (
            obj.type != "MESH"
            or obj.get("annotation_only") is True
            or obj.get("semantic_class")
            in {
                "AREA",
                "WALKABLE",
                "PORTAL",
                "OBSTACLE",
                "STAIR",
                "WALL",
            }
            or obj.name.startswith(
                ("AREA_", "PORTAL_", "WALK_", "WALKABLE_", "OBSTACLE_", "STAIR_", "WALL_")
            )
        ):
            continue
        inventory["architectural_meshes"] += 1
        inventory["architectural_source_polygons"] += len(obj.data.polygons)
        # Evaluated AABB prefilter is only used to reject meshes too small to contain
        # a candidate; face geometry determines every extracted and confirmed patch.
        evaluated = obj.evaluated_get(depsgraph)
        box = bounds([list(evaluated.matrix_world @ vector(v)) for v in evaluated.bound_box])
        dimensions = [box["maximum"][i] - box["minimum"][i] for i in range(3)]
        if (
            dimensions[2] < params["candidate_min_height"]
            or math.hypot(*dimensions[:2]) < params["candidate_min_extent"]
        ):
            inventory["aabb_too_small_meshes"] += 1
            continue
        inventory["evaluated_candidate_size_meshes"] += 1
        candidates.extend(extract_patches(obj, depsgraph, params))
    for index, row in enumerate(candidates):
        row["candidate_id"] = f"WALL-PATCH-{index + 1:05d}"
    # Keep actual polygons until every peer's metrics are used; classify deletes only
    # its own polygon payload after the portal/section checks.
    for row in candidates:
        classify(row, candidates, semantic, floors, params)
    confirmed = [row for row in candidates if row["status"] == "AUTO_CONFIRMED_WALL"]
    review = [row for row in candidates if row["status"] == "HUMAN_REVIEW"]
    if any(row["protected_portal_conflicts"] for row in confirmed):
        raise RuntimeError("protected aperture invariant failed")
    final = source.stat()
    if (initial.st_size, initial.st_mtime_ns, source_digest) != (
        final.st_size,
        final.st_mtime_ns,
        digest(source),
    ):
        raise RuntimeError("source changed during read-only extraction")
    result = {
        "schema_version": "source-bound-wall-candidates-pilot-v1",
        "label": "PILOT / SYNTHETIC SAMPLE",
        "authority": "GEOMETRY_DERIVED_PATCH_SIDECAR",
        "source": {
            "path": str(source),
            "sha256": source_digest,
            "size": initial.st_size,
            "mtime_ns": initial.st_mtime_ns,
            "preserved": True,
        },
        "blender_version": bpy.app.version_string,
        "evaluated_scene": {
            "name": bpy.context.scene.name,
            "frame": bpy.context.scene.frame_current,
            "subframe": bpy.context.scene.frame_subframe,
            "view_layer": bpy.context.view_layer.name,
        },
        "units": {
            "bounds": "BLENDER_NATIVE_SCENE_UNITS",
            "declared_system": bpy.context.scene.unit_settings.system,
            "declared_scale_length": bpy.context.scene.unit_settings.scale_length,
            "physical_metres_certified": False,
        },
        "floor_planes": floors,
        "parameters": params,
        "policy": {
            "source_saved": False,
            "new_geometry_created": False,
            "whole_objects_reclassified": False,
            "gt_used": False,
            "graph_ranking_reconstruction_called": False,
            "benchmark_run": False,
            "elevator_exists": False,
            "elevator_transition_created": False,
            "historical_elevator_area_names_preserved": True,
        },
        "summary": {
            **inventory,
            "candidate_patches": len(candidates),
            "count_unit": "OBJECT_EDGE_CONNECTED_COPLANAR_SURFACE_PATCH",
            "auto_confirmed_wall_patches": len(confirmed),
            "human_review_patches": len(review),
            "auto_confirmed_source_objects": len({row["object"] for row in confirmed}),
            "human_review_source_objects": len({row["object"] for row in review}),
            "source_objects_with_both_statuses": sorted(
                {row["object"] for row in confirmed} & {row["object"] for row in review}
            ),
            "protected_portals": len(semantic["PORTAL"]),
            "auto_confirmed_portal_intersections": 0,
            "by_status_and_floor": dict(
                Counter(f"{row['status']}/{row['floor']}" for row in candidates)
            ),
        },
        "candidates": candidates,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    write_report(result, args.output)
    print("WALL_EXTRACTION_DONE", json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
