"""Render bounded review evidence in an unsaved, GT-free Blender process.

Blender --background --factory-startup --disable-autoexec school_v3.blend
--python-exit-code 2 --python human_review/render_review_evidence.py -- --frames 50.
All moving placements are public projections or existing inferred candidates.
Source geometry is evaluated at the audited viewport frame and never saved.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "human_review" / "frames"
SCALE = 0.0247
SOURCE_HASH = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
PUBLIC = ROOT / "data/finalization/local_run/dataset/inference/office"
DIAGNOSTIC = ROOT / "data/finalization/local_run/diagnostics/office"
AUTHORITY = ROOT / "data/scene_audit/phase1_physical_policy_approval_20261006"
PALETTE = {
    "source": (0.34, 0.38, 0.42, 1),
    "walk": (0.12, 0.40, 0.25, 1),
    "portal": (0.24, 0.65, 0.97, 1),
    "obstacle": (0.76, 0.34, 0.30, 1),
    "observed": (0.06, 0.71, 1, 1),
    "gap": (1, 0.52, 0.06, 1),
    "left": (0.72, 0.30, 0.98, 1),
    "right": (0.97, 0.81, 0.12, 1),
    "witness": (1, 0.05, 0.25, 1),
    "clearance": (0.98, 0.97, 0.75, 1),
    "text": (0.99, 0.99, 0.99, 1),
}


def read(path):
    return json.loads(path.read_text())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=50)
    parser.add_argument("--closeup-only", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    bpy = importlib.import_module("bpy")
    Vector = importlib.import_module("mathutils").Vector
    np = importlib.import_module("numpy")
    sys.path.insert(0, str(ROOT / "scripts"))
    source = Path(bpy.data.filepath).resolve()
    stat_before = source.stat()
    assert digest(source) == SOURCE_HASH
    audit_path = ROOT / "data/scene_audit/school_v3_semantic_audit.json"
    audit = read(audit_path)
    context = read(PUBLIC / "context.json")
    observations = read(PUBLIC / "observations.json")
    projected_path = DIAGNOSTIC / "policy_graph_primary/projected_frames.json"
    projected = read(projected_path)["dataset"]["samples"]
    public_index = {(r["camera_id"], r["frame_id"]): r for r in observations["frames"]}
    assert all(
        s["uv"] == public_index[(s["camera_id"], s["frame_id"])]["point_2d"]
        and s["visibility"] == public_index[(s["camera_id"], s["frame_id"])]["status"]
        for s in projected
    )
    policy_path = DIAGNOSTIC / "primary.json"
    policy_rows = {r["frame_id"]: r for r in read(policy_path)["rows"]}
    assert all(
        r["ground_truth_read"] is False and r["selection_uses_ground_truth"] is False
        for r in policy_rows.values()
    )
    candidates_path = DIAGNOSTIC / "policy_graph_primary/candidates.json"
    candidates = read(candidates_path)["results"][0]["candidates"]
    local_path = AUTHORITY / "local_physical_scopes.json"
    local = read(local_path)
    floor_path = AUTHORITY / "floor_authority_map.json"
    floor = next(
        row
        for row in read(floor_path)["walkable_reviews"]
        if row["walkable_id"] == "WALK_1F_OFFICE"
    )
    obstacle_path = AUTHORITY / "obstacle_collider_authority.json"
    obstacle_authority = read(obstacle_path)
    assert context["source_asset_sha256"] == audit["source_sha256"] == SOURCE_HASH
    scene = bpy.context.scene
    scene.frame_set(audit["scene"]["frame"])
    assert scene.name == audit["scene"]["name"]
    # Same evaluated-viewport snapshot policy as export_blender_pilot.configure_render,
    # bounded to audit AABB intersections before copying meshes (97 instead of 2873 objects).
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
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
    shading.show_shadows = shading.show_cavity = shading.show_specular_highlight = False
    shading.show_xray = False
    shading.background_type = "WORLD"
    scene.world.color = (0.035, 0.045, 0.055)
    scene.view_settings.view_transform, scene.view_settings.look = "Standard", "None"
    scene.view_settings.exposure, scene.view_settings.gamma = 0, 1
    crop_lo, crop_hi = np.array([1130, 1680, -1]), np.array([1525, 2330, 155])
    inventory = audit["full_scene_inventory"]["objects"]
    wanted = []
    for row in inventory:
        if row["object_type"] != "MESH" or row["object"].startswith(
            ("AREA_", "PORTAL_", "WALK_", "OBSTACLE_", "WALL_", "STAIR_")
        ):
            continue
        bounds = row.get("bounding_box")
        if bounds and all(
            bounds["maximum"][i] >= crop_lo[i] and bounds["minimum"][i] <= crop_hi[i]
            for i in range(3)
        ):
            wanted.append(row["object"])
    print("REVIEW bounded snapshot objects", len(wanted), flush=True)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    snapshot_collection = bpy.data.collections.new("REVIEW_EVALUATED_VIEWPORT_SNAPSHOT")
    scene.collection.children.link(snapshot_collection)
    originals = []
    for name in wanted:
        source_obj = bpy.data.objects.get(name)
        if source_obj is None:
            continue
        evaluated = source_obj.evaluated_get(depsgraph)
        if not len(evaluated.data.polygons):
            continue
        mesh = bpy.data.meshes.new_from_object(
            evaluated, preserve_all_data_layers=False, depsgraph=depsgraph
        )
        snapshot = bpy.data.objects.new("REVIEW_SOURCE_" + name, mesh)
        snapshot_collection.objects.link(snapshot)
        snapshot.matrix_world = evaluated.matrix_world.copy()
        snapshot.color = PALETTE["source"]
        originals.append(snapshot)
    for obj in list(scene.objects):
        obj.hide_render = obj.type != "CAMERA"
    for col in bpy.data.collections:
        col.hide_render = False
    policy = {
        "engine": "BLENDER_WORKBENCH",
        "width": 960,
        "height": 540,
        "render_mesh_policy": "FROZEN_EVALUATED_VIEWPORT_MESH_NO_RENDER_MODIFIERS",
        "snapshot_scope": "AUDIT_AABB_INTERSECTION_BOUNDED_LOCAL_REVIEW",
        "snapshot_source_object_count": len(originals),
        "source_saved": False,
        "reference_helper": "scripts/export_blender_pilot.py:configure_render",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    print("REVIEW snapshot ready", len(originals), flush=True)
    collection = bpy.data.collections.new("DIAGNOSTIC_REVIEW_OVERLAYS_UNSAVED")
    scene.collection.children.link(collection)
    dynamic = []
    labels = []
    frame_records = []
    face_records = []

    def mesh_object(name, vertices, faces, color):
        mesh = bpy.data.meshes.new(name + "_MESH")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        obj.color = color
        return obj

    def line(name, points, color, radius=0.75, cyclic=False):
        curve = bpy.data.curves.new(name + "_CURVE", type="CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 1
        curve.bevel_depth = radius
        curve.bevel_resolution = 1
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for i, point in enumerate(points):
            spline.points[i].co = (*point, 1)
        spline.use_cyclic_u = cyclic
        obj = bpy.data.objects.new(name, curve)
        collection.objects.link(obj)
        obj.color = color
        return obj

    def dot(name, position, radius, color):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=12, ring_count=6, radius=radius, location=position
        )
        obj = bpy.context.object
        obj.name = name
        obj.color = color
        return obj

    def wire_cylinder(name, base, radius, height, color):
        vertices = [
            [radius * math.cos(2 * math.pi * i / 24), radius * math.sin(2 * math.pi * i / 24), z]
            for z in [0, height]
            for i in range(24)
        ]
        curves = []
        for offset in [0, 24]:
            curves.append(
                line(
                    name + str(offset),
                    vertices[offset : offset + 24],
                    color,
                    radius=0.50,
                    cyclic=True,
                )
            )
        for i in range(0, 24, 4):
            curves.append(
                line(name + "upright" + str(i), [vertices[i], vertices[i + 24]], color, radius=0.50)
            )
        for obj in curves:
            obj.location = base
        return curves

    def text(name, body, position, camera, size=7, color=None):
        curve = bpy.data.curves.new(name + "_TEXT", type="FONT")
        curve.body = body
        curve.size = size
        curve.align_x = "LEFT"
        obj = bpy.data.objects.new(name, curve)
        collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = camera.rotation_euler
        obj.color = color or PALETTE["text"]
        labels.append(obj)
        return obj

    # Local wireframe is copied from the frozen evaluated viewport snapshot.
    # No source coordinates are changed, and upper floors remain outside this display crop.
    for snapshot in originals:
        mesh = snapshot.data
        mesh.calc_loop_triangles()
        matrix = np.asarray(snapshot.matrix_world)
        coords = np.array([tuple(v.co) for v in mesh.vertices])
        world = coords @ matrix[:3, :3].T + matrix[:3, 3]
        selected = []
        for tri in mesh.loop_triangles:
            pts = world[list(tri.vertices)]
            if np.any(pts.max(axis=0) < crop_lo) or np.any(pts.min(axis=0) > crop_hi):
                continue
            if pts.max(axis=0)[2] > 155.01:
                continue
            selected.append(list(tri.vertices))
        if not selected:
            continue
        original_indices = sorted({i for face in selected for i in face})
        remap = {old: new for new, old in enumerate(original_indices)}
        derived = mesh_object(
            "LOCAL_SOURCE_" + snapshot.name,
            world[original_indices].tolist(),
            [[remap[i] for i in tri] for tri in selected],
            PALETTE["source"],
        )
        modifier = derived.modifiers.new("DIAGNOSTIC_WIREFRAME_DISPLAY_ONLY", "WIREFRAME")
        modifier.thickness = 0.28
        modifier.use_replace = True
        derived["diagnostic_display_only"] = True

    objects = {row["object"]: row for row in audit["objects"]}
    for name in [
        "WALK_1F_OFFICE",
        "WALK_1F_OFFICE_THRESHOLD",
        "WALK_1F_AUDITORIUM_OFFICE_THRESHOLD",
    ]:
        row = objects[name]
        # Annotation is lifted only for display; it is not a physical support surface.
        vertices = [[p[0], p[1], floor["source_support_height_bu"] + 0.6] for p in row["vertices"]]
        mesh_object("ANNOTATION_DISPLAY_" + name, vertices, row["triangles"], PALETTE["walk"])
    for name in ["OBSTACLE_1F_OFFICE_01", "OBSTACLE_1F_OFFICE_02"]:
        row = objects[name]
        vertices = [[p[0], p[1], floor["source_support_height_bu"] + 0.8] for p in row["vertices"]]
        mesh_object(
            "SEMANTIC_FOOTPRINT_NO_APPROVED_SOLID_" + name,
            vertices,
            row["triangles"],
            PALETTE["obstacle"],
        )
    for name in ["PORTAL_1F_OFFICE", "PORTAL_1F_AUDITORIUM_OFFICE"]:
        row = objects[name]
        lo, hi = row["bounding_box"]["minimum"], row["bounding_box"]["maximum"]
        z = floor["source_support_height_bu"] + 1.2
        line(
            "CONTEXT_ONLY_" + name,
            [[lo[0], lo[1], z], [hi[0], lo[1], z], [hi[0], hi[1], z], [lo[0], hi[1], z]],
            PALETTE["portal"],
            cyclic=True,
        )
    region = next(r for r in local["regions"] if r["walkable_id"] == "WALK_1F_OFFICE")
    for witness in region["review_witnesses"]:
        if "triangle_bu" not in witness:
            continue
        face_id = witness["source_face_index"]
        points = witness["triangle_bu"]
        line(
            "REAL_WITNESS_group_0_FACE_" + str(face_id),
            points,
            PALETTE["witness"],
            radius=1.1,
            cyclic=True,
        )
        face_records.append(
            {
                "object": witness["source_object_id"],
                "face_id": face_id,
                "reason": witness["reason"],
                "triangle_bu": points,
                "triangle_m": [[v * SCALE for v in p] for p in points],
            }
        )

    landmark_z = context["plane"]["point"][2]
    exact_offset = landmark_z - floor["source_support_height_bu"]
    base_z = landmark_z - exact_offset
    for index, candidate in enumerate(candidates):
        points = [[p[0], p[1], base_z + 2] for p in candidate["polyline"]]
        color = [PALETTE["gap"], PALETTE["witness"], PALETTE["gap"]][index]
        line(
            "INFERRED_NOT_CERTIFIED_" + candidate["navmesh_corridor"][0], points, color, radius=0.95
        )
    public_projections = [s for s in projected if s["projected_point"] is not None]
    for sample in public_projections:
        dot(
            "PUBLIC_PROJECTED_" + str(sample["frame_id"]),
            sample["projected_point"]["world_position"],
            1.7,
            PALETTE["observed"],
        )
    camera_objects = {}
    for row in context["cameras"]:
        obj = bpy.data.objects.get(row["camera_id"])
        assert obj is not None
        camera_objects[row["camera_id"]] = obj
    camera_data = bpy.data.cameras.new("REVIEW_ORTHOGRAPHIC")
    review_cam = bpy.data.objects.new("REVIEW_ORTHOGRAPHIC_UNSAVED", camera_data)
    scene.collection.objects.link(review_cam)
    camera_data.type = "ORTHO"
    camera_data.clip_start = 0.1
    camera_data.clip_end = 10000
    scene.camera = review_cam

    def position_camera(position, target, scale):
        review_cam.location = position
        direction = Vector(target) - review_cam.location
        review_cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        review_cam.data.ortho_scale = scale
        for obj in labels:
            obj.hide_render = True

    def title(body, line_number=0, color=None):
        rotation = review_cam.rotation_euler.to_matrix()
        right = rotation @ Vector((1, 0, 0))
        up = rotation @ Vector((0, 1, 0))
        front = rotation @ Vector((0, 0, -1))
        width = review_cam.data.ortho_scale
        center = review_cam.location + front * 30
        origin = center - right * width * 0.48 + up * width * (0.265 - 0.032 * line_number)
        return text("REVIEW_LABEL", body, origin, review_cam, size=width * 0.018, color=color)

    def render(name):
        path = OUT / name
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {"path": "frames/" + name, "sha256": digest(path), "bytes": path.stat().st_size}

    if args.closeup_only:
        # Add targeted stills without changing the completed sequence or its source bindings.
        manifest_path = OUT / "visual_manifest.json"
        manifest = read(manifest_path)
        preserved = [*manifest["frames"], *manifest["still_frames"], *manifest["camera_stills"]]
        assert all(
            digest(ROOT / "human_review" / row["path"]) == row["sha256"] for row in preserved
        )
        geometry_path = ROOT / "human_review/geometry_evidence.json"
        geometry = read(geometry_path)
        assert geometry["source_sha256"] == SOURCE_HASH and geometry["gt_used"] is False
        assert geometry["certificate_generated"] is False
        low, high = geometry["body_envelope_bounds_bu"]
        foot_low, foot_high = geometry["prospective_footpoint_bounds_bu"]
        close_lo = np.array([low[0] - 25, low[1] - 15, -1])
        close_hi = np.array([high[0] + 25, high[1] + 15, high[2] + 5])
        for obj in collection.objects:
            if obj.name.startswith(
                ("REAL_WITNESS_", "CONTEXT_ONLY_PORTAL_", "LOCAL_SOURCE_", "SEMANTIC_FOOTPRINT_")
            ):
                obj.hide_render = True
        # Existing broad source context is replaced visually by a tighter display crop.
        # Evaluated source vertices remain exact; this is not a new physical collider.
        for snapshot in originals:
            mesh = snapshot.data
            mesh.calc_loop_triangles()
            matrix = np.asarray(snapshot.matrix_world)
            coords = np.array([tuple(v.co) for v in mesh.vertices])
            world = coords @ matrix[:3, :3].T + matrix[:3, 3]
            selected = []
            for tri in mesh.loop_triangles:
                pts = world[list(tri.vertices)]
                if (
                    np.any(pts.max(axis=0) < close_lo)
                    or np.any(pts.min(axis=0) > close_hi)
                    or pts.max(axis=0)[2] > close_hi[2]
                ):
                    continue
                selected.append(list(tri.vertices))
            if not selected:
                continue
            original_indices = sorted({i for face in selected for i in face})
            remap = {old: new for new, old in enumerate(original_indices)}
            derived = mesh_object(
                "CLOSEUP_EXACT_SOURCE_" + snapshot.name,
                world[original_indices].tolist(),
                [[remap[i] for i in tri] for tri in selected],
                PALETTE["source"],
            )
            modifier = derived.modifiers.new("DIAGNOSTIC_CLOSEUP_WIREFRAME", "WIREFRAME")
            modifier.thickness, modifier.use_replace = 0.16, True
            derived["diagnostic_display_only"] = True
        corners = [
            [x, y, z]
            for z in [low[2], high[2]]
            for y in [low[1], high[1]]
            for x in [low[0], high[0]]
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
            line(
                "PENDING_EXACT_BODY_GUARD", [corners[a], corners[b]], PALETTE["portal"], radius=0.4
            )
        line(
            "PENDING_FOOTPOINT_DOMAIN",
            [
                [foot_low[0], foot_low[1], base_z + 1],
                [foot_high[0], foot_low[1], base_z + 1],
                [foot_high[0], foot_high[1], base_z + 1],
                [foot_low[0], foot_high[1], base_z + 1],
            ],
            PALETTE["clearance"],
            radius=0.5,
            cyclic=True,
        )
        exact_faces = geometry["findings"]
        assert {(row["source_object_id"], row["source_face_index"]) for row in exact_faces} == {
            ("group_0", 1975),
            ("group_0", 2398),
        }
        # Both triangles are the same exact zero-area seam with reversed winding.
        seam_display_lift_bu = 1.4
        seam_display_points = [
            [p[0], p[1], p[2] + seam_display_lift_bu] for p in exact_faces[0]["triangle_bu"]
        ]
        line(
            "EXACT_DUPLICATE_SOURCE_FACES_1975_2398",
            seam_display_points,
            PALETTE["left"],
            radius=0.7,
            cyclic=True,
        )
        centroid = exact_faces[0]["centroid_bu"]
        dot(
            "EXACT_SEAM_CENTROID_1975_2398",
            [centroid[0], centroid[1], centroid[2] + seam_display_lift_bu],
            1.2,
            PALETTE["left"],
        )
        body_base = [
            candidates[0]["polyline"][0][0],
            sum(p[1] for p in candidates[0]["polyline"]) / 2,
            base_z,
        ]
        wire_cylinder(
            "PROSPECTIVE_BODY_BINDING_PENDING",
            body_base,
            0.30 / SCALE,
            1.70 / SCALE,
            PALETTE["gap"],
        )
        wire_cylinder(
            "APPROVED_DIMENSIONS_CLEARANCE_PENDING_SCOPE",
            body_base,
            0.35 / SCALE,
            1.75 / SCALE,
            PALETTE["clearance"],
        )
        scene.render.resolution_x, scene.render.resolution_y = 1440, 900
        target = [(foot_low[0] + foot_high[0]) / 2, (foot_low[1] + foot_high[1]) / 2, 50]
        position_camera((1515, 1875, 210), target, 300)
        title("HR-01 ONLY | 1F OFFICE BOUNDED GEOMETRY SEMANTICS | NO GT")
        title("Cyan = body guard; white = permitted footpoint domain; decision PENDING", 1)
        title("group_0 faces1975 / 2398: SAME zero-area floor seam (purple)", 2)
        title("Left candidate AUTO-REJECT: floor clearance0.1896m <0.3500m", 3)
        title("Amber direct/right: support PASS; full local body certificate still REVIEW", 4)
        title("East wall face7356 is OUTSIDE this guard: context only, not a decision", 5)
        title("Body r0.30m h1.70m +clearance0.05m; no office source collider approved", 6)
        closeup = render("office_scope_closeup.png")
        position_camera((target[0], target[1], 450), (target[0], target[1], 20), 215)
        review_cam.rotation_euler.rotate_axis("Z", math.pi / 2)
        title("HR-01 TOP | Exact1975/2398 seam + proposed body guard | NO GT")
        title("Purple seam is zero-area floor evidence (display lift1.4BU /0.0346m)", 1)
        title("Red left route: AUTO-REJECT floor clearance; amber direct/right: hypotheses", 2)
        title("Cyan = pending body volume; white = proposed footpoint domain", 3)
        closeup_top = render("office_scope_top_closeup.png")
        assert digest(source) == SOURCE_HASH
        assert (source.stat().st_size, source.stat().st_mtime_ns) == (
            stat_before.st_size,
            stat_before.st_mtime_ns,
        )
        assert all(
            digest(ROOT / "human_review" / row["path"]) == row["sha256"] for row in preserved
        )
        manifest["closeup_frames"] = [closeup, closeup_top]
        manifest["closeup_input_geometry_sha256"] = digest(geometry_path)
        manifest["closeup_seam_display_offset"] = {
            "bu": seam_display_lift_bu,
            "m": seam_display_lift_bu * SCALE,
            "reason": "DISPLAY_ONLY_OVERLAY_VISIBILITY_ABOVE_WALKABLE_ANNOTATION",
            "actual_source_coordinates_preserved": True,
            "physical_geometry_or_policy_changed": False,
        }
        manifest["closeup_renderer_sha256"] = digest(Path(__file__))
        manifest["closeup_render_policy"] = {
            **policy,
            "width": 1440,
            "height": 900,
            "display_crop_bu": {"minimum": close_lo.tolist(), "maximum": close_hi.tolist()},
            "body_guard_bu": {"minimum": low, "maximum": high},
            "source_saved": False,
            "gt_used": False,
            "existing_sequence_preserved": True,
        }
        manifest["closeup_overlay_legend"] = {
            "cyan_box": "PENDING_EXACT_REVIEW_BODY_ENVELOPE_NOT_A_NAVIGATION_DOMAIN",
            "white_rectangle": "EXACT_PROSPECTIVE_FOOTPOINT_DOMAIN",
            "purple_line": "EXACT_DUPLICATE_ZERO_AREA_SOURCE_FACES_1975_2398_DISPLAY_LIFT_ONLY",
            "red_route": "AUTOMATIC_APPROVED_FLOOR_CLEARANCE_REJECTION",
            "amber_routes": "SUPPORT_ELIGIBLE_PUBLIC_HYPOTHESES_NOT_CERTIFIED",
        }
        manifest["review_scope_source_faces"] = exact_faces
        manifest["context_warnings"] = [
            "Existing broad office/sequence frames also highlight group_0 face7356. "
            "It is outside the narrow prospective body guard and is CONTEXT ONLY, "
            "not an HR-01 blocker.",
            "Use office_scope_closeup.png / office_scope_top_closeup.png for the exact "
            "two-seam and bounded-interior decision. No full component approval is requested.",
        ]
        for row in manifest["source_face_witnesses"]:
            row["review_role"] = (
                "CONTEXT_ONLY_OUTSIDE_CURRENT_BODY_GUARD"
                if row["face_id"] == 7356
                else "BLOCKING_EXACT_LOCAL_SEAM"
                if row["face_id"] == 1975
                else "CONTEXT_ONLY"
            )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
        print(
            json.dumps(
                {
                    "closeups_rendered": 2,
                    "preserved_sequence_frames": len(manifest["frames"]),
                    "source_preserved": True,
                    "gt_used": False,
                }
            ),
            flush=True,
        )
        return

    position_camera((1760, 1750, 410), (1415, 2020, 54), 350)
    title("DIAGNOSTIC | PUBLIC PROJECTIONS + INFERRED CANDIDATES | NO GT")
    title("1F OFFICE: source wireframe; WALK green; semantic OBSTACLE red", 1)
    title("Amber direct/right: NOT_CERTIFIED; red left: AUTO-REJECT clearance", 2)
    title("Red source witness: group_0 face1975 floor / face7356 east wall", 3)
    still_oblique = render("office_oblique.png")

    position_camera((1320, 2010, 800), (1320, 2010, 20), 710)
    review_cam.rotation_euler.rotate_axis("Z", math.pi / 2)
    title("1F OFFICE TOP VIEW | FULL LOCAL CONTEXT | NO GT")
    title("Cyan portal footprints are CONTEXT ONLY; this route stays inside OFFICE", 1)
    title("OBSTACLE semantics APPROVED; 0 office source solids APPROVED", 2)
    still_top = render("office_top.png")

    position_camera((1760, 2020, 75), (1415, 2020, 75), 380)
    title("1F OFFICE SIDE VIEW | +X LOOKING WEST | NO GT")
    title("Floor support APPROVED; whole local body scope NOT_CERTIFIED", 1)
    title("Cyan dots = landmark projection; base = proposed landmark Z - 55.0499981 BU", 2)
    still_side = render("office_side.png")

    def point_on_candidate(candidate, fraction):
        points = [Vector(p) for p in candidate["polyline"]]
        lengths = [(b - a).length for a, b in zip(points[:-1], points[1:], strict=True)]
        distance = sum(lengths) * min(1, max(0, fraction))
        for a, b, length in zip(points[:-1], points[1:], lengths, strict=True):
            if distance <= length:
                return a.lerp(b, distance / length)
            distance -= length
        return points[-1]

    grouped = {}
    for sample in projected:
        grouped.setdefault(sample["frame_id"], []).append(sample)
    ordered_frames = sorted(grouped)
    assert len(ordered_frames) == 50
    for frame_id in ordered_frames[: args.frames]:
        for obj in dynamic:
            bpy.data.objects.remove(obj, do_unlink=True)
        dynamic.clear()
        samples = grouped[frame_id]
        timestamp = samples[0]["timestamp"]
        visible = [s for s in samples if s["projected_point"] is not None]
        if visible:
            selected = sorted(visible, key=lambda s: s["camera_id"])[0]
            position = Vector(selected["projected_point"]["world_position"])
            role, color = "OBSERVED / PUBLIC PROJECTED", PALETTE["observed"]
        else:
            position = point_on_candidate(candidates[0], (timestamp - 4) / 5)
            role, color = "GAP / INFERRED DIRECT CANDIDATE", PALETTE["gap"]
        base = (position.x, position.y, base_z)
        dynamic.extend(
            wire_cylinder(
                "BODY_APPROVED_DIMENSIONS_PENDING_BINDING", base, 0.30 / SCALE, 1.70 / SCALE, color
            )
        )
        dynamic.extend(
            wire_cylinder(
                "CLEARANCE_ENVELOPE", base, 0.35 / SCALE, 1.75 / SCALE, PALETTE["clearance"]
            )
        )
        dynamic.append(dot("ACTIVE_PUBLIC_OR_INFERRED_LANDMARK", position, 3, color))
        dynamic.append(
            line("PENDING_LANDMARK_TO_FLOOR_BINDING", [base, position], color, radius=0.6)
        )
        for sample in visible:
            cam = camera_objects[sample["camera_id"]]
            dynamic.append(
                line(
                    "VISIBLE_CAMERA_PUBLIC_EVIDENCE",
                    [cam.location, position],
                    PALETTE["observed"],
                    radius=0.35,
                )
            )
        position_camera((1760, 1750, 410), (1415, 2020, 54), 350)
        title("DIAGNOSTIC / NO GT / NOT A FORMAL TRAJECTORY", 0)
        title(f"t={timestamp:04.1f}s | {role}", 1, color)
        title("PROPOSED FLOOR-CONTACT MODEL / NOT GT | r0.30m h1.70m +0.05m", 2)
        title("Source grey / WALK green / semantic obstacle red / witnesses bright red", 3)
        cam_status = "; ".join(
            s["camera_id"].replace("CAM_1F_AUDITORIUM_", "") + ":" + s["visibility"]
            for s in samples
        )
        title(cam_status, 4)
        record = render(f"sequence_{frame_id:03d}.png")
        frame_records.append(
            {
                **record,
                "frame_id": frame_id,
                "timestamp": timestamp,
                "role": role,
                "projection_method": policy_rows[frame_id]["method"],
                "confidence_state": policy_rows[frame_id]["state"],
                "uncertainty": policy_rows[frame_id]["uncertainty"],
                "landmark_position_bu": list(position),
                "body_base_bu": list(base),
                "camera_evidence": [
                    {
                        "camera_id": s["camera_id"],
                        "visibility": s["visibility"],
                        "uv": s["uv"],
                        "gap_reason": s["gap_reason"],
                        "occluder_id": s["occluder_id"],
                    }
                    for s in samples
                ],
            }
        )
    # Camera stills contain only a body inferred from the public visible endpoint.
    camera_stills = []
    for cam_name, frame_id in [("CAM_1F_AUDITORIUM_FRONT", 20), ("CAM_1F_AUDITORIUM_REAR", 46)]:
        for obj in dynamic:
            bpy.data.objects.remove(obj, do_unlink=True)
        dynamic.clear()
        for obj in collection.objects:
            obj.hide_render = True
        for obj in originals:
            obj.hide_render = False
        sample = next(s for s in grouped[frame_id] if s["camera_id"] == cam_name)
        position = sample["projected_point"]["world_position"]
        body_base = (position[0], position[1], base_z)
        dynamic.extend(
            wire_cylinder(
                "DIAGNOSTIC_PUBLIC_ENDPOINT_BODY",
                body_base,
                0.30 / SCALE,
                1.70 / SCALE,
                PALETTE["observed"],
            )
        )
        dynamic.append(dot("OBSERVED_PROJECTED_LANDMARK", position, 3, PALETTE["observed"]))
        scene.camera = camera_objects[cam_name]
        row = render(f"camera_{cam_name.lower()}_frame{frame_id}.png")
        camera_stills.append(
            {
                **row,
                "camera_id": cam_name,
                "frame_id": frame_id,
                "timestamp": sample["timestamp"],
                "public_uv": sample["uv"],
                "body_placement": "PUBLIC_PROJECTION_MINUS_SOURCE_BOUND_PENDING_LANDMARK_OFFSET",
            }
        )
        for obj in originals:
            obj.hide_render = True
    source_after = digest(source)
    assert source_after == SOURCE_HASH
    assert (source.stat().st_size, source.stat().st_mtime_ns) == (
        stat_before.st_size,
        stat_before.st_mtime_ns,
    )
    office_obstacles = [
        r
        for r in obstacle_authority["obstacles"]
        if r["obstacle_id"] in ["OBSTACLE_1F_OFFICE_01", "OBSTACLE_1F_OFFICE_02"]
    ]
    input_paths = [
        audit_path,
        PUBLIC / "context.json",
        PUBLIC / "observations.json",
        projected_path,
        candidates_path,
        policy_path,
        local_path,
        floor_path,
        obstacle_path,
    ]
    manifest = {
        "schema_version": "phase1-human-review-visuals-v1",
        "result_type": "DIAGNOSTIC",
        "gt_used": False,
        "evaluation_files_read": False,
        "simulation_recipe_read": False,
        "source_asset_sha256": SOURCE_HASH,
        "source_sha256_after": source_after,
        "source_modified": False,
        "source_saved": False,
        "blender_version": bpy.app.version_string,
        "evaluated_frame": audit["scene"],
        "render_policy": policy,
        "display_policy": "ACTUAL_EVALUATED_SOURCE_LOCAL_WIREFRAME_AND_ANNOTATION_OVERLAYS",
        "camera_still_warning": "BOUNDED_SOURCE_SNAPSHOT_NOT_FULL_SCENE_OCCLUSION_PROOF",
        "display_crop_bu": {"minimum": crop_lo.tolist(), "maximum": crop_hi.tolist()},
        "landmark_z_bu": landmark_z,
        "proposed_exact_landmark_offset_bu": exact_offset,
        "proposed_exact_landmark_offset_m": exact_offset * SCALE,
        "proposed_base_z_bu": base_z,
        "approved_support_z_bu": floor["source_support_height_bu"],
        "proposed_base_minus_approved_support_m": (base_z - floor["source_support_height_bu"])
        * SCALE,
        "approved_body_dimensions_m": {"radius": 0.30, "height": 1.70, "clearance": 0.05},
        "all_route_candidates_not_certified": True,
        "portal_footprints": "CONTEXT_ONLY_NOT_CROSSED_BY_EXISTING_ROUTE",
        "office_obstacle_authority": [
            {
                "id": r["obstacle_id"],
                "semantics": r["semantic_authority"],
                "approved_component_count": r["approved_component_count"],
                "solid_volume": r["whole_obstacle_authority"],
            }
            for r in office_obstacles
        ],
        "source_face_witnesses": face_records,
        "sequence_fps": 5,
        "sequence_duration_seconds": len(frame_records) / 5,
        "trajectory_time_range_seconds": [0, 9.8],
        "still_frames": [still_oblique, still_top, still_side],
        "camera_stills": camera_stills,
        "frames": frame_records,
        "inputs": [{"path": str(p.relative_to(ROOT)), "sha256": digest(p)} for p in input_paths],
    }
    (OUT / "visual_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "rendered_sequence_frames": len(frame_records),
                "source_preserved": True,
                "output": str(OUT),
                "gt_used": False,
            }
        )
    )


if __name__ == "__main__":
    main()
