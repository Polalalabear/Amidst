"""Unsaved source-scene context: school -> 1F cutaway -> office.

Run Blender with --background --factory-startup --disable-autoexec school_v3.blend
--python-exit-code 2 --python human_review/render_spatial_context.py -- --frames 25.
The approach animation moves only the camera. No new person route is generated.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "human_review"
OUT = REVIEW / "frames/spatial_context"
SOURCE_SHA = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
SCALE = 0.0247
AUDIT = ROOT / "data/scene_audit/school_v3_semantic_audit.json"
PUBLIC = ROOT / "data/finalization/local_run/dataset/inference/office/context.json"
CANDIDATES = (
    ROOT / "data/finalization/local_run/diagnostics/office/policy_graph_primary/candidates.json"
)
PROJECTED = (
    ROOT
    / "data/finalization/local_run/diagnostics/office/policy_graph_primary/projected_frames.json"
)
SUPPORT = (
    ROOT / "data/scene_audit/phase1_physical_policy_approval_20261006/floor_support_details.json.gz"
)
INPUTS = frozenset(
    {
        AUDIT,
        PUBLIC,
        CANDIDATES,
        PROJECTED,
        SUPPORT,
        REVIEW / "geometry_evidence.json",
        REVIEW / "review_template.json",
        REVIEW / "frames/visual_manifest.json",
    }
)
COLORS = {
    "source": (0.47, 0.51, 0.55, 1),
    "floor": (0.37, 0.45, 0.52, 1),
    "office": (1, 0.65, 0.05, 1),
    "support": (0.12, 0.55, 0.30, 1),
    "camera": (0.10, 0.70, 1, 1),
    "scope": (0.68, 0.35, 0.95, 1),
    "route": (1, 0.45, 0.04, 1),
    "text": (1, 1, 1, 1),
    "axis": (0.83, 0.87, 0.89, 1),
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_public(path):
    if path not in INPUTS:
        raise ValueError("spatial context reads only explicit public source/review inputs")
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=25)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.frames < 25:
        raise ValueError("spatial approach requires at least25frames")
    bpy = importlib.import_module("bpy")
    Vector = importlib.import_module("mathutils").Vector
    np = importlib.import_module("numpy")
    source = Path(bpy.data.filepath).resolve()
    before = source.stat()
    assert digest(source) == SOURCE_SHA
    audit, context = read_public(AUDIT), read_public(PUBLIC)
    geometry = read_public(REVIEW / "geometry_evidence.json")
    template = read_public(REVIEW / "review_template.json")
    old_manifest = read_public(REVIEW / "frames/visual_manifest.json")
    support = read_public(SUPPORT)
    candidates = read_public(CANDIDATES)["results"][0]["candidates"]
    projected = read_public(PROJECTED)["dataset"]["samples"]
    assert audit["source_sha256"] == context["source_asset_sha256"] == SOURCE_SHA
    protected = {
        row["path"]: digest(ROOT / row["path"]) for row in template["metadata"]["input_hashes"]
    }
    protected["human_review/review_template.json"] = digest(REVIEW / "review_template.json")
    protected["human_review/decisions.json"] = digest(REVIEW / "decisions.json")
    old_images = [
        *old_manifest["frames"],
        *old_manifest["still_frames"],
        *old_manifest["camera_stills"],
        *old_manifest["closeup_frames"],
    ]
    image_hashes = {row["path"]: digest(REVIEW / row["path"]) for row in old_images}
    assert all(image_hashes[row["path"]] == row["sha256"] for row in old_images)
    office = next(row for row in audit["objects"] if row["object"] == "AREA_1F_OFFICE")
    office_lo, office_hi = office["bounding_box"]["minimum"], office["bounding_box"]["maximum"]
    office_center = [(office_lo[i] + office_hi[i]) / 2 for i in range(3)]
    source_floor_z = geometry["prospective_footpoint_bounds_bu"][0][2]
    source_semantics = [
        row
        for row in audit["objects"]
        if row["object"].startswith("AREA_") and row.get("bounding_box")
    ]
    roi_low = np.min([row["bounding_box"]["minimum"] for row in source_semantics], axis=0)
    roi_high = np.max([row["bounding_box"]["maximum"] for row in source_semantics], axis=0)
    roi_low -= [50, 50, 50]
    roi_high += [50, 50, 50]
    roi_low[2], roi_high[2] = -2, 350
    inventory = audit["full_scene_inventory"]["objects"]
    source_rows = []
    for row in inventory:
        if row["object_type"] != "MESH" or row["object"].startswith(
            ("AREA_", "WALK_", "PORTAL_", "OBSTACLE_", "WALL_", "STAIR_")
        ):
            continue
        bounds = row.get("bounding_box")
        if bounds and all(
            bounds["maximum"][i] >= roi_low[i] and bounds["minimum"][i] <= roi_high[i]
            for i in range(3)
        ):
            source_rows.append(row)
    scene = bpy.context.scene
    scene.frame_set(audit["scene"]["frame"])
    assert scene.name == audit["scene"]["name"]
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.use_border = scene.render.use_crop_to_border = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.render.use_compositing = scene.render.use_sequencer = False
    scene.display.render_aa = "8"
    shading = scene.display.shading
    shading.light, shading.color_type = "STUDIO", "OBJECT"
    shading.show_shadows = True
    shading.show_cavity = shading.show_specular_highlight = shading.show_xray = False
    shading.background_type = "WORLD"
    scene.world.color = (0.035, 0.044, 0.052)
    scene.view_settings.view_transform, scene.view_settings.look = "Standard", "None"
    scene.view_settings.exposure, scene.view_settings.gamma = 0, 1
    for obj in list(scene.objects):
        obj.hide_render = True
    for col in bpy.data.collections:
        col.hide_render = False
    full_collection = bpy.data.collections.new("SPATIAL_CONTEXT_EVALUATED_SOURCE")
    cut_collection = bpy.data.collections.new("SPATIAL_CONTEXT_1F_DISPLAY_CUTAWAY")
    overlay = bpy.data.collections.new("SPATIAL_CONTEXT_DISPLAY_OVERLAYS_ONLY")
    for col in (full_collection, cut_collection, overlay):
        scene.collection.children.link(col)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    full_objects, cut_objects, labels, axes, office_marks = [], [], [], [], []
    cut_z = 145.0

    def mesh_object(name, vertices, faces, color, collection=overlay):
        mesh = bpy.data.meshes.new(name + "_MESH")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        obj.color = color
        return obj

    def clip_triangle(points):
        polygon = list(points)
        result = []
        for a, b in zip(polygon, polygon[1:] + polygon[:1], strict=True):
            a_inside, b_inside = a[2] <= cut_z, b[2] <= cut_z
            if a_inside:
                result.append(a.tolist())
            if a_inside != b_inside:
                t = (cut_z - a[2]) / (b[2] - a[2])
                result.append((a + t * (b - a)).tolist())
        return result

    print("SPATIAL source objects in display ROI", len(source_rows), flush=True)
    triangles_kept, triangles_cut = 0, 0
    for index, row in enumerate(source_rows):
        native = bpy.data.objects.get(row["object"])
        if native is None:
            continue
        evaluated = native.evaluated_get(depsgraph)
        if not len(evaluated.data.polygons):
            continue
        mesh = bpy.data.meshes.new_from_object(
            evaluated, preserve_all_data_layers=False, depsgraph=depsgraph
        )
        obj = bpy.data.objects.new("SOURCE_CONTEXT_" + row["object"], mesh)
        full_collection.objects.link(obj)
        obj.matrix_world = evaluated.matrix_world.copy()
        obj.color = COLORS["source"]
        full_objects.append(obj)
        mesh.calc_loop_triangles()
        matrix = np.asarray(obj.matrix_world)
        coords = np.array([tuple(v.co) for v in mesh.vertices])
        world = coords @ matrix[:3, :3].T + matrix[:3, 3]
        vertices, faces = [], []
        for tri in mesh.loop_triangles:
            points = world[list(tri.vertices)]
            if points[:, 2].min() > cut_z:
                continue
            clipped = clip_triangle(points)
            if len(clipped) < 3:
                continue
            start = len(vertices)
            vertices.extend(clipped)
            faces.extend([start, start + i, start + i + 1] for i in range(1, len(clipped) - 1))
            triangles_kept += 1
            triangles_cut += int(points[:, 2].max() > cut_z)
        if faces:
            cut_objects.append(
                mesh_object(
                    "DISPLAY_CUT_" + row["object"], vertices, faces, COLORS["floor"], cut_collection
                )
            )
        if index % 400 == 0:
            print("SPATIAL copied", index, "of", len(source_rows), flush=True)
    print("SPATIAL snapshot ready", len(full_objects), len(cut_objects), flush=True)

    def line(name, points, color, radius=2, cyclic=False):
        curve = bpy.data.curves.new(name + "_CURVE", type="CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 1
        curve.bevel_depth, curve.bevel_resolution = radius, 1
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for i, p in enumerate(points):
            spline.points[i].co = (*p, 1)
        spline.use_cyclic_u = cyclic
        obj = bpy.data.objects.new(name, curve)
        overlay.objects.link(obj)
        obj.color = color
        return obj

    def dot(name, position, radius, color):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=16, ring_count=8, radius=radius, location=position
        )
        obj = bpy.context.object
        obj.name, obj.color = name, color
        return obj

    def rectangle(name, lo, hi, z, color, radius=2):
        return line(
            name,
            [[lo[0], lo[1], z], [hi[0], lo[1], z], [hi[0], hi[1], z], [lo[0], hi[1], z]],
            color,
            radius,
            True,
        )

    # An amber pointer locates the office below the upper floor in the whole-model view.
    roof_pointer = line(
        "1F_OFFICE_LOCATION_DISPLAY_POINTER",
        [
            [office_center[0], office_center[1], source_floor_z],
            [office_center[0], office_center[1], 400],
        ],
        COLORS["office"],
        4,
    )
    roof_dot = dot(
        "1F_OFFICE_BELOW_LOCATION", [office_center[0], office_center[1], 400], 18, COLORS["office"]
    )
    office_marks.extend([roof_pointer, roof_dot])
    rectangle(
        "OFFICE_ANNOTATION_CONTEXT_ONLY",
        office_lo,
        office_hi,
        source_floor_z + 2,
        COLORS["office"],
        3,
    )
    # Green is exact already approved source-supported floor, not body clearance certification.
    office_support = next(
        row for row in support["walkable_reviews"] if row["walkable_id"] == "WALK_1F_OFFICE"
    )
    for row in support["support_surfaces"]:
        if row["surface_id"] not in office_support["support_surface_ids"]:
            continue
        mesh_object(
            "APPROVED_FLOOR_SUPPORT_DISPLAY_ONLY",
            [[p[0], p[1], p[2] + 0.4] for p in row["vertices"]],
            row["triangles"],
            COLORS["support"],
        )
    low, high = geometry["body_envelope_bounds_bu"]
    corners = [
        [x, y, z] for z in [low[2], high[2]] for y in [low[1], high[1]] for x in [low[0], high[0]]
    ]
    for a, b in [
        (0, 1),
        (0, 2),
        (1, 3),
        (2, 3),
        (4, 5),
        (4, 6),
        (5, 7),
        (6, 7),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]:
        line("EXACT_PENDING_HR01_BODY_ENVELOPE", [corners[a], corners[b]], COLORS["scope"], 0.9)
    route = candidates[0]["polyline"]
    line(
        "EXISTING_PUBLIC_DIRECT_GAP_ROUTE",
        [[p[0], p[1], source_floor_z + 2] for p in route],
        COLORS["route"],
        1.5,
    )
    source_points = [
        row["projected_point"]["world_position"]
        for row in projected
        if row.get("projected_point") is not None
    ]
    for p in source_points:
        dot("EXISTING_PUBLIC_PROJECTION", p, 2, COLORS["camera"])
    cameras = []
    for row in context["cameras"]:
        position = [row["camera_to_world"][i][3] for i in range(3)]
        native = bpy.data.objects.get(row["camera_id"])
        assert native is not None and np.allclose(list(native.location), position, atol=1e-3)
        dot("SOURCE_CAMERA_" + row["camera_id"], position, 10, COLORS["camera"])
        line(
            "SOURCE_CAMERA_LOCATION_LINK",
            [position, [office_center[0], office_center[1], 75]],
            COLORS["camera"],
            0.65,
        )
        cameras.append(
            {
                "camera_id": row["camera_id"],
                "position_bu": position,
                "position_m": [v * SCALE for v in position],
                "link": "DISPLAY_LOCATION_GUIDE_NOT_VISIBILITY_PROOF",
            }
        )
    origin = [roi_low[0], roi_low[1], source_floor_z + 4]
    axes.append(
        line("BLENDER_PLUS_X", [origin, [origin[0] + 250, origin[1], origin[2]]], COLORS["axis"], 2)
    )
    axes.append(
        line("BLENDER_PLUS_Y", [origin, [origin[0], origin[1] + 250, origin[2]]], COLORS["axis"], 2)
    )
    camera_data = bpy.data.cameras.new("SPATIAL_CONTEXT_VIEW_CAMERA")
    camera = bpy.data.objects.new("SPATIAL_CONTEXT_VIEW_CAMERA_UNSAVED", camera_data)
    scene.collection.objects.link(camera)
    camera_data.type, camera_data.clip_start, camera_data.clip_end = "ORTHO", 0.1, 20000
    scene.camera = camera

    def position_camera(position, target, scale, cut=False):
        camera.location = position
        camera.rotation_euler = (
            (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()
        )
        camera.data.ortho_scale = scale
        for obj in labels:
            obj.hide_render = True
        for obj in full_objects:
            obj.hide_render = cut
        for obj in cut_objects:
            obj.hide_render = not cut
        for obj in office_marks:
            obj.hide_render = cut

    def text(name, body, position, size, color=None):
        curve = bpy.data.curves.new(name + "_TEXT", type="FONT")
        curve.body, curve.size = body, size
        curve.align_x = "LEFT"
        obj = bpy.data.objects.new(name, curve)
        overlay.objects.link(obj)
        obj.location, obj.rotation_euler = position, camera.rotation_euler
        obj.color = color or COLORS["text"]
        labels.append(obj)
        return obj

    def title(body, row=0, color=None):
        rotation = camera.rotation_euler.to_matrix()
        right, up, front = (rotation @ Vector(v) for v in [(1, 0, 0), (0, 1, 0), (0, 0, -1)])
        scale = camera.data.ortho_scale
        center = camera.location + front * 30
        position = center - right * scale * 0.48 + up * scale * (0.286 - row * 0.033)
        return text("SPATIAL_CONTEXT_LABEL", body, position, scale * 0.018, color)

    def world_labels():
        scale = camera.data.ortho_scale
        text(
            "AXIS_LABEL_X",
            "+X",
            [origin[0] + 250, origin[1], origin[2] + 5],
            scale * 0.018,
            COLORS["axis"],
        )
        text(
            "AXIS_LABEL_Y",
            "+Y",
            [origin[0], origin[1] + 250, origin[2] + 5],
            scale * 0.018,
            COLORS["axis"],
        )
        if scale > 1500:
            text(
                "OFFICE_LOCATION_LABEL",
                "1F OFFICE",
                [office_center[0] + 25, office_center[1], 410],
                scale * 0.021,
                COLORS["office"],
            )
        for row in cameras:
            p = row["position_bu"]
            text(
                "CAMERA_LOCATION_LABEL",
                row["camera_id"].replace("CAM_1F_AUDITORIUM_", ""),
                [p[0] + 14, p[1], p[2] + 15],
                scale * 0.016,
                COLORS["camera"],
            )

    def render(name, caption):
        path = OUT / name
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {
            "path": name,
            "caption": caption,
            "sha256": digest(path),
            "bytes": path.stat().st_size,
        }

    OUT.mkdir(parents=True, exist_ok=True)
    center = (roi_low + roi_high) / 2
    school_position = np.array([3100, 3600, 2700], dtype=float)
    school_target = np.array([center[0], center[1], 100], dtype=float)
    office_position = np.array([1810, 1550, 650], dtype=float)
    office_target = np.array([office_center[0], office_center[1], 60], dtype=float)
    position_camera(school_position, school_target, 2850)
    title("1 / SCHOOL MODEL | Actual evaluated school_v3.blend | DIAGNOSTIC")
    title("Amber pointer locates the 1F OFFICE below the upper floor", 1, COLORS["office"])
    title("Blue FRONT / REAR = the two existing source cameras", 2, COLORS["camera"])
    title("Grey whole-model context is NOT_CERTIFIED. Axes are Blender +X / +Y, not North", 3)
    world_labels()
    overview = render(
        "school_overview.png", "整棟來源模型：先找橘色 1F OFFICE 定位標記；灰色模型僅供位置參考。"
    )
    position_camera([center[0], center[1], 3500], [center[0], center[1], 20], 2600, True)
    title("2 / 1F CUTAWAY MAP | DISPLAY ONLY: upper geometry clipped at Z=145 BU")
    title("Amber = OFFICE annotation context; green = approved source floor support only", 1)
    title(
        "Purple small box = pending HR-01 body envelope. Broad 1F physics remains NOT_CERTIFIED", 2
    )
    title("Blue camera links are location guides, not visibility or camera-binding approval", 3)
    world_labels()
    floor_view = render(
        "floor_1f_overview.png", "1F 剖視定位：橘框是 office 區域參考，紫框才是本次限定人工範圍。"
    )
    position_camera(office_position, office_target, 780, True)
    title("3 / OFFICE CONTEXT | Same source coordinates; display cutaway only")
    title("Green = approved floor support; purple = pending bounded body / enclosure review", 1)
    title("Orange short path is the existing inferred GAP candidate, NOT a new route", 2)
    title("Next: unchanged 10-second local motion, then exact faces1975 /2398 closeup", 3)
    world_labels()
    office_view = render(
        "office_context.png", "Office 中景：看清房間與限定紫框位置，再播放既有局部 10 秒證據。"
    )
    scene.render.resolution_x, scene.render.resolution_y = 1280, 800
    approach = []
    for frame in range(args.frames):
        fraction = frame / (args.frames - 1)
        smooth = fraction * fraction * (3 - 2 * fraction)
        pos = school_position * (1 - smooth) + office_position * smooth
        target = school_target * (1 - smooth) + office_target * smooth
        scale = 2850 * (1 - smooth) + 780 * smooth
        cut = fraction >= 0.36
        position_camera(pos, target, scale, cut)
        title("CAMERA APPROACH ONLY | No new person motion or route | DIAGNOSTIC")
        title("School -> 1F display cutaway -> existing office review scope", 1)
        title("Camera zoom is different from the unchanged 3.87 m local person-motion extent", 2)
        world_labels()
        record = render(f"approach_{frame:03d}.png", "純觀看鏡頭靠近；人物路徑與研究輸入維持不變。")
        approach.append(
            {
                **record,
                "frame_id": frame,
                "timestamp": frame / 5,
                "camera_position_bu": pos.tolist(),
                "camera_target_bu": target.tolist(),
                "ortho_scale_bu": float(scale),
                "display_cutaway": cut,
                "person_movement_changed": False,
            }
        )
    assert digest(source) == SOURCE_SHA
    assert (source.stat().st_size, source.stat().st_mtime_ns) == (
        before.st_size,
        before.st_mtime_ns,
    )
    assert all(digest(ROOT / p) == sha for p, sha in protected.items())
    assert all(digest(REVIEW / p) == sha for p, sha in image_hashes.items())
    public_points = np.asarray(source_points)
    visible_extent = float(
        np.linalg.norm(public_points[:, :2].max(axis=0) - public_points[:, :2].min(axis=0)) * SCALE
    )
    route_length = sum(
        float(np.linalg.norm(np.asarray(b) - np.asarray(a))) * SCALE
        for a, b in zip(route[:-1], route[1:], strict=True)
    )
    offset = (context["plane"]["point"][2] - source_floor_z) * SCALE
    manifest = {
        "schema_version": "phase1-human-review-spatial-context-v1",
        "result_type": "DIAGNOSTIC",
        "source_sha256": SOURCE_SHA,
        "source_sha256_after": digest(source),
        "source_preserved": True,
        "source_saved": False,
        "source_modified": False,
        "gt_used": False,
        "evaluation_files_read": False,
        "simulation_recipe_read": False,
        "physical_authority_changed": False,
        "formal_execution_enabled": False,
        "scope_authority": "PENDING_HUMAN_REVIEW_NOT_APPROVED",
        "whole_school_context_authority": "PROVISIONAL_NOT_CERTIFIED",
        "source_frame": audit["scene"],
        "blender_version": bpy.app.version_string,
        "source_object_count": len(full_objects),
        "cutaway_object_count": len(cut_objects),
        "display_roi_bu": {"minimum": roi_low.tolist(), "maximum": roi_high.tolist()},
        "display_cutaway": {
            "purpose": "DISPLAY_ONLY",
            "clip_z_bu": cut_z,
            "method": "LINEAR_SOURCE_TRIANGLE_PLANE_CLIP",
            "source_or_physical_geometry_changed": False,
            "triangles_retained": triangles_kept,
            "triangles_clipped": triangles_cut,
        },
        "axis_labels": ["+X", "+Y"],
        "geographic_north_assumed": False,
        "office_context": {
            "object": "AREA_1F_OFFICE",
            "bounds_bu": [office_lo, office_hi],
            "authority": "ANNOTATION_CONTEXT_ONLY",
        },
        "review_body_scope_bounds_bu": geometry["body_envelope_bounds_bu"],
        "camera_locations": cameras,
        "overview": overview,
        "floor": floor_view,
        "office": office_view,
        "approach_frames": approach,
        "approach_fps": 5,
        "approach_duration_seconds": len(approach) / 5,
        "display_only_camera_approach": True,
        "person_movement_changed": False,
        "person_motion": {
            "basis": "EXISTING_PUBLIC_PROJECTIONS_AND_INFERRED_CANDIDATE",
            "visible_extent_m": visible_extent,
            "gap_route_length_m": route_length,
            "existing_sequence_time_range_s": [0, 9.8],
            "new_route_generated": False,
        },
        "vertical_coordinate_conversion_m": offset,
        "preserved_original_inputs": protected,
        "preserved_original_images": image_hashes,
        "inputs": [{"path": str(p.relative_to(ROOT)), "sha256": digest(p)} for p in sorted(INPUTS)],
        "renderer_sha256": digest(Path(__file__)),
        "limitations": [
            "Whole school/floor display is spatial context, not physical certification.",
            "Camera location links do not establish visibility or landmark/floor binding.",
            "Camera approach does not extend the existing diagnostic person route.",
            "The 1.36 m value is vertical landmark-to-foot conversion, not travel distance.",
        ],
    }
    (OUT / "spatial_context_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
    )
    print(
        json.dumps(
            {
                "stills": 3,
                "approach_frames": len(approach),
                "source_preserved": True,
                "all_original_review_inputs_preserved": True,
                "output": str(OUT),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
