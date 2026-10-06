"""Read-only native-mesh sanity checks of a user-approved architectural scale.

Run in Blender with --background --disable-autoexec and a fresh output directory.
Annotation dimensions and actual source cross-sections are intentionally separate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any


def fingerprint(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    stat = path.stat()
    return {"sha256": sha, "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def validate_config(config: dict[str, Any]) -> float:
    if config["schema_version"] != "school-scale-measurement-config-v1":
        raise ValueError("unsupported scale measurement config")
    scale = config["metres_per_blender_unit"]
    if isinstance(scale, bool) or not isinstance(scale, (int, float)) or (
        not math.isfinite(scale) or scale <= 0
    ):
        raise ValueError("scale must be finite and positive")
    if config["scale_authority"] != "APPROVED":
        raise ValueError("active measurements require user-approved architectural scale")
    record = json.loads(Path(config["architectural_scale_config"]).read_text())
    if record.get("authority") != "APPROVED" or (
        record.get("schema_version") != "architectural-scale-v1"
        or record.get("scope") != "PHASE1_SCHOOL_V3_RESEARCH_MODEL"
        or record.get("measurement_role") != "SANITY_CHECK_EVIDENCE"
        or config.get("measurements_role") != "SANITY_CHECK_EVIDENCE"
        or record.get("approval_basis") != "USER_DEFINED_RESEARCH_MODEL_SETTING"
        or not record.get("approval_id") or not record.get("evidence_ids")
        or record.get("metres_per_blender_unit") != scale
        or record.get("source_asset_sha256") != config["source_sha256"]
        or record.get("source_geometry_scaled") is not False
        or record.get("external_dimensions_required") is not False
    ):
        raise ValueError("measurement config differs from source-bound approved scale")
    if any(config["policy"].values()):
        raise ValueError("read-only measurement policy must deny mutation and formal use")
    for floor, band in config["support_bands_bu"].items():
        if len(band) != 2 or not all(math.isfinite(v) for v in band) or band[0] >= band[1]:
            raise ValueError(f"invalid support band: {floor}")
    for name in ("support_normal_abs_z_min", "side_normal_axis_min"):
        if not 0 < config[name] <= 1:
            raise ValueError(f"invalid normal selection threshold: {name}")
    values = [config["maximum_ray_distance_bu"],
              *config["cross_section_heights_above_support_bu"]]
    if not values or any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError("measurement ray distances/heights must be finite and positive")
    return float(scale)


def measurement_row(
    identity: str, kind: str, object_id: str, floor: str, area: str | None,
    axis: int, first: list[float], second: list[float], scale: float,
) -> dict[str, Any]:
    length = math.dist(first, second)
    return {
        "measurement_id": identity, "kind": kind, "object": object_id,
        "area": area, "portal": object_id if kind == "DOOR" else None,
        "floor": floor, "axis": "XYZ"[axis],
        "annotation_endpoints_bu": [first, second],
        "annotation_length_bu": length, "annotation_length_m": length * scale,
        "source_cross_sections": [], "actual_source_length_bu": None,
        "actual_source_length_m": None,
        "known_real_length_m": None,
        "used_to_derive_scale": False, "measurement_role": "SANITY_CHECK_EVIDENCE",
        "human_confirmation_candidate": False,
        "confidence": "ANNOTATION_ONLY", "ambiguities": [
            "BOUNDARY_OWNERSHIP_UNAPPROVED", "ANNOTATION_IS_NOT_PHYSICAL_CLEAR_BOUNDARY",
        ],
    }


def finish_cross_sections(row: dict[str, Any], scale: float) -> None:
    sections = row["source_cross_sections"]
    complete = [s for s in sections if s["length_bu"] is not None]
    if not complete:
        row["ambiguities"].append("NO_TWO_SIDED_SOURCE_HITS")
        return
    lengths = sorted(s["length_bu"] for s in complete)
    row["actual_source_length_bu"] = statistics.median(lengths)
    row["source_length_aggregation"] = "MEDIAN_OF_AVAILABLE_SAMPLED_CROSS_SECTIONS"
    row["actual_source_length_m"] = row["actual_source_length_bu"] * scale
    row["source_to_annotation_length_ratio"] = (
        row["actual_source_length_bu"] / row["annotation_length_bu"]
        if row["annotation_length_bu"] else None
    )
    row["source_width_range_bu"] = [lengths[0], lengths[-1]]
    row["confidence"] = "SOURCE_GEOMETRY_MEASURED_ROLE_REVIEW"
    row["ambiguities"].append("SOURCE_HIT_ROLES_AND_TRUE_APERTURE_UNAPPROVED")
    if len(complete) != len(sections):
        row["ambiguities"].append("INCOMPLETE_HEIGHT_PROFILE")
    if any(not s["side_orientation_matches"] for s in complete):
        row["ambiguities"].append("SOURCE_BOUNDARY_ORIENTATION_MISMATCH")
    if lengths[-1] - lengths[0] > 0.001:
        row["ambiguities"].append("WIDTH_VARIES_WITH_HEIGHT")
    row["human_confirmation_candidate"] = len(complete) == len(sections) and all(
        s["side_orientation_matches"] for s in complete
    ) and lengths[-1] - lengths[0] <= 0.001


class MeshSurvey:
    """Ray hits cite evaluated source polygons; AABBs only filter query work."""

    def __init__(self, bpy: Any, audit: dict[str, Any], config: dict[str, Any]):
        self.vector = importlib.import_module("mathutils").Vector
        self.bvh = importlib.import_module("mathutils.bvhtree").BVHTree
        self.config = config
        self.objects: list[dict[str, Any]] = []
        self.skipped: list[dict[str, str]] = []
        excluded = {r["object"] for r in audit["objects"]} | set(
            config["excluded_helper_objects"]
        )
        graph = bpy.context.evaluated_depsgraph_get()
        for obj in sorted(bpy.context.scene.objects, key=lambda obj: obj.name):
            if obj.type != "MESH" or obj.name in excluded or obj.get("phase1_annotation_only"):
                continue
            evaluated = obj.evaluated_get(graph)
            matrix = evaluated.matrix_world.copy()
            if abs(matrix.determinant()) < 1e-12:
                self.skipped.append({"object": obj.name, "reason": "SINGULAR_WORLD_MATRIX"})
                continue
            points = [matrix @ self.vector(point) for point in evaluated.bound_box]
            box = [[min(p[i] for p in points) for i in range(3)],
                   [max(p[i] for p in points) for i in range(3)]]
            if not all(math.isfinite(v) for point in box for v in point):
                raise ValueError(f"non-finite source bounds: {obj.name}")
            self.objects.append({
                "object": evaluated, "matrix": matrix, "inverse": matrix.inverted(),
                "bounds": box, "hidden_render": obj.hide_render,
                "hidden_viewport": obj.hide_viewport,
                "tree": None, "vertices": None, "polygons": None,
            })

    def hit(
        self, origin: list[float], axis: int, sign: int, distance: float,
    ) -> dict[str, Any] | None:
        end = origin.copy()
        end[axis] += sign * distance
        nearest: dict[str, Any] | None = None
        for source in self.objects:
            lo, hi = source["bounds"]
            if any(hi[i] < min(origin[i], end[i]) or lo[i] > max(origin[i], end[i])
                   for i in range(3)):
                continue
            inverse, matrix = source["inverse"], source["matrix"]
            local_start = inverse @ self.vector(origin)
            local_end = inverse @ self.vector(end)
            direction = local_end - local_start
            if source["tree"] is None:
                mesh = source["object"].to_mesh()
                try:
                    source["vertices"] = [tuple(v.co) for v in mesh.vertices]
                    source["polygons"] = [tuple(p.vertices) for p in mesh.polygons]
                    source["tree"] = self.bvh.FromPolygons(
                        source["vertices"], source["polygons"], all_triangles=False,
                    )
                finally:
                    source["object"].to_mesh_clear()
            if source["tree"] is None:
                continue
            point, normal, face, _ = source["tree"].ray_cast(
                local_start, direction.normalized(), direction.length,
            )
            if point is None:
                continue
            world_point = matrix @ point
            world_normal = (inverse.transposed().to_3x3() @ normal).normalized()
            length = (world_point - self.vector(origin)).length
            if nearest is not None and length >= nearest["distance_bu"]:
                continue
            evaluated = source["object"]
            polygon_vertices = None
            if 0 <= face < len(source["polygons"]):
                polygon_vertices = [
                    list(matrix @ self.vector(source["vertices"][i]))
                    for i in source["polygons"][face]
                ]
            nearest = {
                "object": evaluated.original.name, "evaluated_polygon_index": face,
                "endpoint_bu": list(world_point), "normal_world": list(world_normal),
                "distance_bu": length, "source_polygon_vertices_bu": polygon_vertices,
                "hidden_render": source["hidden_render"],
                "hidden_viewport": source["hidden_viewport"],
                "semantic_role": "UNASSIGNED_SOURCE_GEOMETRY",
            }
        return nearest

    def support(self, center: list[float], floor: str) -> dict[str, Any] | None:
        band = self.config["support_bands_bu"][floor]
        origin = [center[0], center[1], band[1]]
        hit = self.hit(origin, 2, -1, band[1] - band[0])
        if hit is None or abs(hit["normal_world"][2]) < self.config["support_normal_abs_z_min"]:
            return None
        return hit


def generate_rows(
    audit: dict[str, Any], config: dict[str, Any], survey: MeshSurvey, scale: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    objects = {r["object"]: r for r in audit["objects"]}
    selections = []
    unresolved = []
    for obj in audit["objects"]:
        if obj["custom_properties"].get("semantic_class") != "PORTAL":
            continue
        normal = obj["custom_properties"].get("portal_normal")
        if normal is None or len(normal) != 3 or not all(math.isfinite(v) for v in normal) or (
            normal[2] != 0 or (normal[0] == 0) == (normal[1] == 0)
        ):
            unresolved.append({
                "object": obj["object"], "floor": obj["declared_floor_label"],
                "reason": "PORTAL_NORMAL_NOT_UNIQUELY_DECLARED", "source": "ANNOTATION",
                "bounds_bu": obj["bounding_box"],
                "xy_annotation_extents_bu": [
                    obj["bounding_box"]["maximum"][i] - obj["bounding_box"]["minimum"][i]
                    for i in range(2)
                ],
            })
            continue
        selections.append({"object": obj["object"], "area": None, "kind": "DOOR",
                           "axis": 1 if normal[0] else 0})
    selections += [{**r, "kind": "CORRIDOR"} for r in config["corridors"]]
    selections += [{**r, "kind": "ROOM", "axis": axis}
                   for r in config["rooms"] for axis in (0, 1)]
    rows = []
    for selection in selections:
        obj = objects[selection["object"]]
        area = selection["area"] or obj["custom_properties"].get("source_area_id")
        if area is not None and area not in objects:
            raise ValueError(f"unknown AREA source binding: {area}")
        lo, hi = obj["bounding_box"]["minimum"], obj["bounding_box"]["maximum"]
        center = [(lo[i] + hi[i]) / 2 for i in range(3)]
        floor = obj["custom_properties"].get("floor_id", obj["declared_floor_label"])
        support = survey.support(center, floor)
        axis = selection["axis"]
        first, second = center.copy(), center.copy()
        first[axis], second[axis] = lo[axis], hi[axis]
        row = measurement_row(
            f"{selection['object']}:{'XYZ'[axis]}", selection["kind"], obj["object"],
            floor, area, axis, first, second, scale,
        )
        row["annotation_geometry_sha256"] = obj["geometry_sha256"]
        row["floor_support_hit"] = support
        row["floor_label_authority"] = "DECLARED_NOT_PHYSICAL_APPROVAL"
        if support is None:
            row["ambiguities"].append("NO_HORIZONTAL_SOURCE_SUPPORT")
            rows.append(row)
            continue
        for offset in config["cross_section_heights_above_support_bu"]:
            origin = [center[0], center[1], support["endpoint_bu"][2] + offset]
            hits = [survey.hit(origin, axis, sign, config["maximum_ray_distance_bu"])
                    for sign in (-1, 1)]
            valid_hits = [h for h in hits if h is not None]
            complete = len(valid_hits) == 2
            length = math.dist(
                valid_hits[0]["endpoint_bu"], valid_hits[1]["endpoint_bu"],
            ) if complete else None
            row["source_cross_sections"].append({
                "origin_bu": origin, "height_above_support_bu": offset,
                "height_above_support_m": offset * scale,
                "hits": hits, "length_bu": length,
                "length_m": length * scale if length is not None else None,
                "side_orientation_matches": complete and all(
                    abs(h["normal_world"][axis]) >= config["side_normal_axis_min"]
                    for h in valid_hits
                ),
            })
        finish_cross_sections(row, scale)
        rows.append(row)
    return sorted(rows, key=lambda r: r["measurement_id"]), unresolved


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# School v3 scale-calibration measurements / 尺度量測",
        "", f"Architectural scale: **{report['metres_per_blender_unit']} m/BU — APPROVED**.",
        "Basis: USER_DEFINED_RESEARCH_MODEL_SETTING; measurements: SANITY_CHECK_EVIDENCE.",
        "尺度由使用者明確核准；mesh 只作合理性檢查，不要求外部尺寸重新推導。",
        "不縮放、不修改／儲存模型、不執行 benchmark；幾何邊界仍待各自核准。",
        "Annotation 是標記尺寸；source 是指定高度的最近實體 mesh 兩側截面，",
        "不自動證明牆、門框、全高度淨寬或通行性。完整端點／source polygons 見 JSON。",
        "", "## Measurement table / 自動量測表", "",
        "| Object / axis | Kind | Floor | Annotation BU | Source BU | Source m | Boundary |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in report["measurements"]:
        value = row["actual_source_length_bu"]
        metres = row["actual_source_length_m"]
        lines.append(
            f"| {row['measurement_id']} | {row['kind']} | {row['floor']} | "
            f"{row['annotation_length_bu']:.6f} | "
            + (f"{value:.6f} | {metres:.6f}" if value is not None else "N/A | N/A")
            + " | HUMAN_REVIEW |"
        )
    lines += ["", "## Vertical height / 樓層高差", "",
              "```json",
              json.dumps(report["floor_height"], ensure_ascii=False, indent=2),
              "```",
              "", "## Boundary sanity-check shortlist / 邊界合理性檢查候選", ""]
    lines += ["| Anchor | Source BU / range | m / range | Limitation |",
              "| --- | --- | --- | --- |"]
    for row in report["human_anchor_shortlist"]:
        lines.append(
            f"| {row['measurement_id']} | {row['source_length_bu']} | "
            f"{row['source_length_m']} | {row['reason']} |"
        )
    lines += ["", "若作為正式通行／碰撞資料，仍需確認來源面的角色與室內邊界。",
              "這與已核准的 research architectural scale 是獨立的 authority。",
              "缺法向門洞保留 unresolved；不從 bbox 中挑看起來像門寬的一邊。",
              "", "## Missing portal orientation / 門洞方向待確認", ""]
    lines += [f"- {r['object']}: {r['reason']}" for r in report["unresolved_portals"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.output.exists():
        raise FileExistsError("scale measurement output must be new")
    initial_inputs = {"config": fingerprint(args.config), "script": fingerprint(Path(__file__))}
    config = json.loads(args.config.read_text())
    authority_path = Path(config["architectural_scale_config"])
    initial_inputs["architectural_scale"] = fingerprint(authority_path)
    scale = validate_config(config)
    authority = json.loads(authority_path.read_text())
    audit_path = Path(config["semantic_audit"])
    initial_inputs["audit"] = fingerprint(audit_path)
    audit = json.loads(audit_path.read_text())
    bpy = importlib.import_module("bpy")
    source = Path(bpy.data.filepath).resolve()
    before = fingerprint(source)
    if before["sha256"] != config["source_sha256"] or (
        audit["source_sha256"] != before["sha256"]
    ):
        raise ValueError("scale measurement source SHA-256 mismatch")
    scene = bpy.context.scene
    if audit["scene"] != {"name": scene.name, "frame": scene.frame_current,
                          "subframe": scene.frame_subframe}:
        raise ValueError("scale measurement evaluated context differs from semantic audit")
    survey = MeshSurvey(bpy, audit, config)
    rows, unresolved = generate_rows(audit, config, survey, scale)
    for row in rows:
        row["scale_authority"] = authority["authority"]
        row["metres_per_blender_unit"] = scale
    floors = []
    for floor, identity in sorted(config["floor_anchor_objects"].items()):
        obj = next(row for row in audit["objects"] if row["object"] == identity)
        hit = survey.support(obj["centroid"], floor)
        floors.append({"floor": floor, "object": identity, "source_hit": hit})
    valid = all(r["source_hit"] is not None for r in floors)
    rise = abs(floors[1]["source_hit"]["endpoint_bu"][2]
               - floors[0]["source_hit"]["endpoint_bu"][2]) if valid else None
    candidates = {r["object"]: r for r in rows if r["human_confirmation_candidate"]}
    shortlist = []
    for identity in config["preferred_human_review_objects"]:
        options = [r for r in rows if r["object"] == identity]
        if not options:
            continue
        row = candidates.get(identity, options[0])
        shortlist.append({
            "measurement_id": row["measurement_id"], "object": identity,
            "source_length_bu": row.get("source_width_range_bu"),
            "source_length_m": [v * scale for v in row["source_width_range_bu"]]
            if "source_width_range_bu" in row else None,
            "reason": "Stable sampled cross-section; confirm physical boundary ownership"
            if row["human_confirmation_candidate"] else
            "Variable/incomplete profile; confirm which cited boundaries define actual clear width",
            "source_geometry_measured": row["actual_source_length_bu"] is not None,
            "used_to_derive_scale": False,
        })
    if rise is not None:
        shortlist.append({
            "measurement_id": "FLOOR_1F_TO_2F:Z", "object": config["floor_anchor_objects"],
            "source_length_bu": rise, "source_length_m": rise * scale,
            "reason": "Two horizontal-support candidates; floor authority remains separate",
            "source_geometry_measured": True, "used_to_derive_scale": False,
        })
    after = fingerprint(source)
    if before != after:
        raise RuntimeError("immutable source changed during scale measurement")
    final_inputs = {"config": fingerprint(args.config), "script": fingerprint(Path(__file__)),
                    "audit": fingerprint(audit_path),
                    "architectural_scale": fingerprint(authority_path)}
    if initial_inputs != final_inputs:
        raise RuntimeError("scale measurement inputs changed during execution")
    report = {
        "schema_version": "school-scale-measurement-report-v2",
        "source": {"path": "blender/school_v3.blend", "before": before, "after": after},
        "inputs": {f"{name}_sha256": value["sha256"]
                   for name, value in initial_inputs.items()},
        "blender_version": bpy.app.version_string, "evaluated_scene": audit["scene"],
        "metres_per_blender_unit": scale, "scale_authority": "APPROVED",
        "architectural_scale": authority, "measurement_role": "SANITY_CHECK_EVIDENCE",
        "independent_known_dimensions": [],
        "cross_validation_status": "NOT_REQUIRED_USER_DEFINED_RESEARCH_MODEL_SCALE",
        "measurements": rows, "unresolved_portals": unresolved,
        "floor_height": {"support_candidates": floors, "vertical_height_bu": rise,
                         "vertical_height_m": rise * scale if rise is not None else None,
                         "authority": "HUMAN_REVIEW"},
        "human_anchor_shortlist": shortlist,
        "source_query": {"mesh_count": len(survey.objects), "skipped": survey.skipped,
                         "face_indices": "EXPLICIT_BVH_INPUT_EVALUATED_POLYGON_INDEX"},
        "policy": config["policy"], "elevator": config["elevator"],
        "source_preserved": True, "saved": False, "rendered": False,
        "geometry_modified": False, "gt_used": False, "formal_physical_use_allowed": False,
    }
    args.output.mkdir(parents=True)
    (args.output / "measurements.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
    )
    (args.output / "measurements.md").write_text(render_markdown(report))
    with (args.output / "measurements.csv").open("w", newline="") as stream:
        fields = ["measurement_id", "kind", "object", "area", "portal", "floor", "axis",
                  "scale_authority", "metres_per_blender_unit",
                  "annotation_length_bu", "annotation_length_m",
                  "actual_source_length_bu", "actual_source_length_m",
                  "confidence", "human_confirmation_candidate", "used_to_derive_scale",
                  "measurement_role",
                  "annotation_endpoints_bu", "source_cross_sections", "floor_support_hit",
                  "source_width_range_bu", "source_length_aggregation", "ambiguities"]
        writer = csv.DictWriter(
            stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows({key: json.dumps(value) if isinstance(value, (dict, list)) else value
                          for key, value in row.items()} for row in rows)
    print(f"Scale sanity check: {len(rows)} rows; source preserved; scale APPROVED")


if __name__ == "__main__":
    main()
