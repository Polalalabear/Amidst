"""Add complete 1F framing, source-camera pointers, and an HR-02 body side view.

This is an unsaved, GT-free display derivative. Existing review files are
immutable; source cutaways and illustrative body poses confer no authority.
"""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import importlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "human_review"
DEFAULT_OUT = REVIEW / "frames/review_clarity"
SOURCE_SHA = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
SCALE = 0.0247
INPUT_RELATIVE = frozenset(
    {
        "human_review/review_template.json",
        "human_review/geometry_evidence.json",
        "human_review/frames/visual_manifest.json",
        "human_review/frames/motion_context/motion_manifest.json",
        "data/scene_audit/school_v3_semantic_audit.json",
        "data/scene_audit/phase1_physical_policy_approval_20261006/floor_support_details.json.gz",
        "data/finalization/local_run/dataset/inference/office/context.json",
        "data/finalization/local_run/diagnostics/office/policy_graph_primary/candidates.json",
    }
)
COLORS = {
    "source": (0.42, 0.47, 0.52, 1),
    "support": (0.10, 0.46, 0.25, 1),
    "office": (1.0, 0.62, 0.08, 1),
    "scope": (0.79, 0.38, 1.0, 1),
    "camera": (0.08, 0.74, 1.0, 1),
    "rear": (0.30, 0.86, 0.75, 1),
    "body": (1.0, 0.60, 0.09, 1),
    "foot": (1.0, 0.93, 0.38, 1),
    "text": (1.0, 1.0, 1.0, 1),
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def public_path(relative: str, repo_root: Path = ROOT) -> Path:
    p = Path(relative)
    root = repo_root.resolve()
    if (
        p.is_absolute()
        or not (root / p).resolve().is_relative_to(root)
        or any(s in relative.lower() for s in ("ground_truth", "evaluation/", "simulation/"))
    ):
        raise ValueError("clarity preview cannot consume GT/evaluation/simulation evidence")
    return root / p


def read_public(path: Path, *, repo_root: Path = ROOT):
    if path.resolve() not in {public_path(p, repo_root).resolve() for p in INPUT_RELATIVE}:
        raise ValueError("clarity preview reads only its explicit public input allowlist")
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _unit(v):
    norm = math.sqrt(_dot(v, v))
    if norm == 0:
        raise ValueError("zero viewing direction")
    return [x / norm for x in v]


def camera_basis(position, target, reference_up=None):
    forward = _unit([target[i] - position[i] for i in range(3)])
    if reference_up is None:
        reference_up = [0, 1, 0] if abs(forward[2]) > 0.999 else [0, 0, 1]
    right = _unit(_cross(forward, reference_up))
    up = _unit(_cross(right, forward))
    return {"right": right, "up": up, "forward": forward}


def project_to_view(point, view):
    difference = [point[i] - view["position_bu"][i] for i in range(3)]
    width, height, scale = view["width"], view["height"], view["ortho_scale_bu"]
    return [
        width * (0.5 + _dot(difference, view["right"]) / scale),
        height * (0.5 - _dot(difference, view["up"]) / (scale * height / width)),
    ]


def fit_view(position, target, points, width=1280, height=800):
    """Fit every source ROI/camera/label anchor below the caption, with explicit margins."""
    basis = camera_basis(position, target)
    xs = [_dot(p, basis["right"]) for p in points]
    ys = [_dot(p, basis["up"]) for p in points]
    bounds = {"x": [0.06, 0.94], "y": [0.22, 0.94]}
    aspect = width / height
    scale = max((max(xs) - min(xs)) / 0.88, (max(ys) - min(ys)) * aspect / 0.72) * 1.015
    mid_x, mid_y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    # Allowed image center is y=.58, so geometry is shifted below the caption.
    wanted_y = mid_y + 0.08 * scale / aspect
    shift = [
        basis["right"][i] * (mid_x - _dot(target, basis["right"]))
        + basis["up"][i] * (wanted_y - _dot(target, basis["up"]))
        for i in range(3)
    ]
    return {
        "position_bu": [position[i] + shift[i] for i in range(3)],
        "target_bu": [target[i] + shift[i] for i in range(3)],
        **basis,
        "ortho_scale_bu": scale,
        "width": width,
        "height": height,
        "fit_points_bu": points,
        "fit_margin": bounds,
    }


def camera_marker_records(cameras, view):
    rows = []
    for camera in cameras:
        position = [camera["camera_to_world"][i][3] for i in range(3)]
        pixel = project_to_view(position, view)
        width, height = view["width"], view["height"]
        anchor = [max(45, min(width - 45, pixel[0])), max(150, min(height - 45, pixel[1]))]
        rows.append(
            {
                "camera_id": camera["camera_id"],
                "source_position_bu": position,
                "uncropped_pixel": pixel,
                "screen_anchor_pixel": anchor,
                "is_offscreen": not (
                    45 <= pixel[0] <= width - 45 and 150 <= pixel[1] <= height - 45
                ),
                "indicator_purpose": "DISPLAY_ONLY_SOURCE_LOCATION_NOT_CAMERA_RELOCATION",
            }
        )
    return rows


def calibrated_camera_geometry(camera):
    matrix = camera["camera_to_world"]
    rays = []
    for u, v in [
        (0, 0),
        (camera["width"], 0),
        (camera["width"], camera["height"]),
        (0, camera["height"]),
    ]:
        local = [(u - camera["cx"]) / camera["fx"], -(v - camera["cy"]) / camera["fy"], -1]
        rays.append(_unit([sum(matrix[i][j] * local[j] for j in range(3)) for i in range(3)]))
    return {
        "camera_id": camera["camera_id"],
        "position_bu": [matrix[i][3] for i in range(3)],
        "optical_axis_world": [-matrix[i][2] for i in range(3)],
        "image_corner_unit_rays_world": rays,
        "corner_pixel_basis": "TOP_LEFT_CONTINUOUS_PUBLIC_INTRINSICS_BLENDER_NEG_Z_UP_Y",
        "authority": "CALIBRATION_GEOMETRY_ONLY_NOT_FOV_OCCLUSION_CERTIFICATION",
    }


def protected_existing(repo_root=ROOT):
    template = read_public(repo_root / "human_review/review_template.json", repo_root=repo_root)
    if template["metadata"]["source_sha256"] != SOURCE_SHA:
        raise ValueError("source-bound review template mismatch")
    rows = template["metadata"]["input_hashes"]
    if len(rows) != 29 or template["metadata"]["gt_used_for_review"] is not False:
        raise ValueError("original frozen GT-free 29-input review required")
    protected = {}
    for row in rows:
        if digest(public_path(row["path"], repo_root)) != row["sha256"]:
            raise ValueError("frozen review input mismatch: " + row["path"])
        protected[row["path"]] = row["sha256"]
    for p in (repo_root / "human_review/frames").rglob("*"):
        if p.is_file() and p.suffix.lower() in {".png", ".gif"}:
            protected[str(p.relative_to(repo_root))] = digest(p)
    for relative in [
        "human_review/review_template.json",
        "human_review/decisions.json",
        "human_review/geometry_evidence.json",
        "human_review/settings_evidence.json",
        "human_review/render_review_evidence.py",
        "human_review/render_spatial_context.py",
        "human_review/render_motion_context.py",
        "human_review/frames/motion_context/motion_manifest.json",
    ]:
        protected[relative] = digest(public_path(relative, repo_root))
    return protected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=25)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--pause-after-map", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    out = args.output.resolve()
    if args.frames != 25 or any(out.glob("*.png")) or (out / "manifest.json").exists():
        raise ValueError("require 25 frames in a fresh additive output directory")
    protected = protected_existing()
    audit = read_public(ROOT / "data/scene_audit/school_v3_semantic_audit.json")
    context = read_public(
        ROOT / "data/finalization/local_run/dataset/inference/office/context.json"
    )
    geometry = read_public(REVIEW / "geometry_evidence.json")
    motion = read_public(REVIEW / "frames/motion_context/motion_manifest.json")
    support = read_public(
        ROOT
        / "data/scene_audit/phase1_physical_policy_approval_20261006/floor_support_details.json.gz"
    )
    candidates = read_public(
        ROOT / "data/finalization/local_run/diagnostics/office/policy_graph_primary/candidates.json"
    )["results"][0]["candidates"]
    if any(
        motion[k] is not False
        for k in ("gt_used", "evaluation_files_read", "simulation_recipe_read")
    ):
        raise ValueError("existing body preview is not isolated from GT")
    body_frame = motion["frames"][20]
    floor_z = geometry["prospective_footpoint_bounds_bu"][0][2]
    landmark_z = context["plane"]["point"][2]
    marker = [body_frame["body_base_bu"][0], body_frame["body_base_bu"][1], landmark_z]
    bpy = importlib.import_module("bpy")
    Vector = importlib.import_module("mathutils").Vector
    np = importlib.import_module("numpy")
    source = Path(bpy.data.filepath).resolve()
    source_before = source.stat()
    if (
        digest(source) != SOURCE_SHA
        or context["source_asset_sha256"] != SOURCE_SHA
        or audit["source_sha256"] != SOURCE_SHA
    ):
        raise ValueError("exact source .blend mismatch")
    scene = bpy.context.scene
    scene.frame_set(audit["scene"]["frame"])
    if scene.name != audit["scene"]["name"]:
        raise ValueError("audited scene mismatch")
    source_native_objects = list(scene.objects)
    for camera in context["cameras"]:
        native = bpy.data.objects.get(camera["camera_id"])
        position = [camera["camera_to_world"][i][3] for i in range(3)]
        if native is None or not np.allclose(list(native.location), position, atol=1e-3):
            raise ValueError("source camera differs from frozen calibration")
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 1280, 800
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.use_border = scene.render.use_crop_to_border = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode, scene.render.image_settings.color_depth = "RGB", "8"
    scene.render.image_settings.compression = 85
    scene.render.film_transparent = False
    scene.render.use_compositing = scene.render.use_sequencer = False
    scene.display.render_aa = "8"
    shading = scene.display.shading
    shading.light, shading.color_type, shading.background_type = "STUDIO", "OBJECT", "WORLD"
    # Match the successful source-context producer: top views need source-wall
    # display shadows because vertical boundary surfaces have zero projected area.
    shading.show_shadows = True
    shading.show_cavity = shading.show_specular_highlight = False
    shading.show_xray = False
    scene.world.color = (0.03, 0.04, 0.05)
    scene.view_settings.view_transform, scene.view_settings.look = "Standard", "None"
    scene.view_settings.exposure, scene.view_settings.gamma = 0, 1
    for obj in source_native_objects:
        obj.hide_render = True
    for col in bpy.data.collections:
        col.hide_render = False
    display = bpy.data.collections.new("REVIEW_CLARITY_UNSAVED_SOURCE_AND_DISPLAY_ONLY")
    scene.collection.children.link(display)
    full_objects, local_objects, camera_objects, local_overlay, labels = [], [], [], [], []

    def mesh_object(name, vertices, faces, color):
        mesh = bpy.data.meshes.new(name + "_MESH")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        display.objects.link(obj)
        obj.color = color
        return obj

    # Fit complete 1F annotation context and both source cameras, not the previous image crop.
    areas = [r for r in audit["objects"] if r["object"].startswith("AREA_1F_")]
    lo = np.min([r["bounding_box"]["minimum"] for r in areas], axis=0)
    hi = np.max([r["bounding_box"]["maximum"] for r in areas], axis=0)
    for camera in context["cameras"]:
        position = np.array([camera["camera_to_world"][i][3] for i in range(3)])
        lo, hi = np.minimum(lo, position), np.maximum(hi, position)
    lo -= [60, 60, 0]
    hi += [140, 100, 0]
    lo[2], hi[2] = -2, 145
    local_lo, local_hi = np.array([1320, 1880, -1]), np.array([1500, 2170, 110])

    def clip_polygon(points, low, high):
        polygon = [np.array(p) for p in points]
        for axis in range(3):
            for threshold, lower in [(low[axis], True), (high[axis], False)]:
                if len(polygon) < 3:
                    return []
                result = []
                for a, b in zip(polygon, polygon[1:] + polygon[:1], strict=True):
                    a_in = a[axis] >= threshold if lower else a[axis] <= threshold
                    b_in = b[axis] >= threshold if lower else b[axis] <= threshold
                    if a_in:
                        result.append(a)
                    if a_in != b_in:
                        fraction = (threshold - a[axis]) / (b[axis] - a[axis])
                        result.append(a + fraction * (b - a))
                polygon = result
        return [p.tolist() for p in polygon]

    source_rows = []
    for row in audit["full_scene_inventory"]["objects"]:
        b = row.get("bounding_box")
        if (
            row["object_type"] == "MESH"
            and b
            and not row["object"].startswith(
                ("AREA_", "WALK_", "PORTAL_", "OBSTACLE_", "WALL_", "STAIR_")
            )
            and all(b["maximum"][i] >= lo[i] and b["minimum"][i] <= hi[i] for i in range(3))
        ):
            source_rows.append(row)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    source_names, triangle_count = [], 0
    for index, row in enumerate(source_rows):
        native = bpy.data.objects.get(row["object"])
        if native is None:
            raise ValueError("missing source object: " + row["object"])
        evaluated = native.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
        try:
            mesh.calc_loop_triangles()
            coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
            mesh.vertices.foreach_get("co", coords)
            matrix = np.asarray(evaluated.matrix_world)
            world = coords.reshape((-1, 3)) @ matrix[:3, :3].T + matrix[:3, 3]
            indices = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
            mesh.loop_triangles.foreach_get("vertices", indices)
            triangles = indices.reshape((-1, 3))
            full_vertices, full_faces, local_vertices, local_faces = [], [], [], []
            for start in range(0, len(triangles), 25000):
                points = world[triangles[start : start + 25000]]
                intersects = np.all(points.max(axis=1) >= lo, axis=1) & np.all(
                    points.min(axis=1) <= hi, axis=1
                )
                fully_inside = np.all(points >= lo, axis=(1, 2)) & np.all(points <= hi, axis=(1, 2))
                interior = points[intersects & fully_inside]
                at = len(full_vertices)
                full_vertices.extend(interior.reshape((-1, 3)).tolist())
                full_faces.extend(
                    [at + 3 * j, at + 3 * j + 1, at + 3 * j + 2] for j in range(len(interior))
                )
                for p in points[intersects & ~fully_inside]:
                    clipped = clip_polygon(p, lo, hi)
                    if len(clipped) < 3:
                        continue
                    at = len(full_vertices)
                    full_vertices.extend(clipped)
                    full_faces.extend([at, at + j, at + j + 1] for j in range(1, len(clipped) - 1))
                local = np.all(points.max(axis=1) >= local_lo, axis=1) & np.all(
                    points.min(axis=1) <= local_hi, axis=1
                )
                local &= np.all(points[:, :, 2] <= local_hi[2], axis=1)
                for p in points[local]:
                    at = len(local_vertices)
                    local_vertices.extend(p.tolist())
                    local_faces.append([at, at + 1, at + 2])
            if full_faces:
                full_objects.append(
                    mesh_object(
                        "SOURCE_1F_DISPLAY_CUT_" + row["object"],
                        full_vertices,
                        full_faces,
                        COLORS["source"],
                    )
                )
                source_names.append(row["object"])
                triangle_count += len(full_faces)
            if local_faces:
                local_objects.append(
                    mesh_object(
                        "SOURCE_HR02_DISPLAY_CUT_" + row["object"],
                        local_vertices,
                        local_faces,
                        COLORS["source"],
                    )
                )
        finally:
            evaluated.to_mesh_clear()
        if index % 200 == 0:
            print("CLARITY source extraction", index, len(source_rows), flush=True)
    del depsgraph, native, evaluated, mesh, world, points, coords, indices, triangles
    for obj in source_native_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    gc.collect()
    print("CLARITY bounded source ready", len(full_objects), triangle_count, flush=True)

    def line(name, points, color, radius=1, cyclic=False):
        curve = bpy.data.curves.new(name + "_CURVE", type="CURVE")
        curve.dimensions, curve.resolution_u = "3D", 1
        curve.bevel_depth, curve.bevel_resolution = radius, 1
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for index, p in enumerate(points):
            spline.points[index].co = (*p, 1)
        spline.use_cyclic_u = cyclic
        obj = bpy.data.objects.new(name, curve)
        display.objects.link(obj)
        obj.color = color
        return obj

    def sphere(name, p, radius, color):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=radius, location=p)
        obj = bpy.context.object
        obj.name, obj.color = name, color
        return obj

    def rectangle(name, low, high, z, color, radius=2):
        return line(
            name,
            [
                [low[0], low[1], z],
                [high[0], low[1], z],
                [high[0], high[1], z],
                [low[0], high[1], z],
            ],
            color,
            radius,
            True,
        )

    office = next(row for row in areas if row["object"] == "AREA_1F_OFFICE")
    office_lo, office_hi = office["bounding_box"]["minimum"], office["bounding_box"]["maximum"]
    office_center = [(office_lo[i] + office_hi[i]) / 2 for i in range(3)]
    rectangle(
        "OFFICE_ANNOTATION_CONTEXT_ONLY", office_lo, office_hi, floor_z + 2, COLORS["office"], 3
    )
    approved_support = next(
        row for row in support["walkable_reviews"] if row["walkable_id"] == "WALK_1F_OFFICE"
    )
    for row in support["support_surfaces"]:
        if row["surface_id"] in approved_support["support_surface_ids"]:
            mesh_object(
                "APPROVED_SOURCE_SUPPORT_ONLY",
                [[p[0], p[1], p[2] + 0.4] for p in row["vertices"]],
                row["triangles"],
                COLORS["support"],
            )
    low, high = geometry["body_envelope_bounds_bu"]
    corners = [
        [x, y, z] for z in (low[2], high[2]) for y in (low[1], high[1]) for x in (low[0], high[0])
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
        line("PENDING_HR01_SCOPE", [corners[a], corners[b]], COLORS["scope"], 0.8)
    for candidate in candidates:
        line(
            "EXISTING_CANDIDATE_NOT_CERTIFIED",
            [[p[0], p[1], floor_z + 1.3] for p in candidate["polyline"]],
            COLORS["body"],
            0.8,
        )
    for row in geometry["findings"]:
        local_overlay.append(
            line(
                "ZERO_AREA_SOURCE_SEAM_" + str(row["source_face_index"]),
                [[p[0], max(1880, min(2170, p[1])), p[2] + 1.4] for p in row["triangle_bu"]],
                COLORS["scope"],
                0.65,
            )
        )
    camera_geometry = [calibrated_camera_geometry(c) for c in context["cameras"]]
    camera_label_anchors = []
    for index, camera in enumerate(camera_geometry):
        p, color = camera["position_bu"], COLORS["camera"] if index == 0 else COLORS["rear"]
        camera_objects.append(sphere("ACTUAL_SOURCE_CAMERA_" + camera["camera_id"], p, 20, color))
        axis_end = [p[i] + 180 * camera["optical_axis_world"][i] for i in range(3)]
        camera_objects.append(line("CALIBRATED_CAMERA_OPTICAL_AXIS", [p, axis_end], color, 3))
        corners = [
            [p[i] + 120 * ray[i] for i in range(3)]
            for ray in camera["image_corner_unit_rays_world"]
        ]
        for corner in corners:
            camera_objects.append(
                line("CALIBRATED_FOV_DIRECTION_WIRE_ONLY", [p, corner], color, 1.2)
            )
        camera_objects.append(line("CALIBRATED_FOV_NEAR_DISPLAY_END", corners, color, 1.2, True))
        camera_objects.append(
            line(
                "SOURCE_CAMERA_OFFICE_LOCATION_LINK_NOT_VISIBILITY",
                [p, [office_center[0], office_center[1], 75]],
                color,
                0.55,
            )
        )
        camera_label_anchors.extend(
            [[p[0] + 40, p[1] - 45, p[2] + 10], [p[0] + 240, p[1] - 45, p[2] + 10]]
        )
    cam_data = bpy.data.cameras.new("CLARITY_REVIEW_CAMERA")
    cam = bpy.data.objects.new("CLARITY_REVIEW_CAMERA_UNSAVED", cam_data)
    scene.collection.objects.link(cam)
    cam_data.type, cam_data.clip_start, cam_data.clip_end = "ORTHO", 0.1, 20000
    scene.camera = cam
    current_view = {}

    def apply_view(view, local=False):
        nonlocal current_view
        cam.location = view["position_bu"]
        # Quaternion is built from the fitted basis, including an unambiguous +X/+Y top view.
        Matrix = importlib.import_module("mathutils").Matrix
        right, up, forward = view["right"], view["up"], view["forward"]
        rotation = Matrix([[right[i], up[i], -forward[i]] for i in range(3)])
        cam.rotation_euler = rotation.to_euler()
        cam_data.ortho_scale = view["ortho_scale_bu"]
        scene.render.resolution_x, scene.render.resolution_y = view["width"], view["height"]
        current_view = {
            **view,
            "position_bu": list(cam.location),
            "right": list(rotation.col[0]),
            "up": list(rotation.col[1]),
            "forward": list(-rotation.col[2]),
        }
        for obj in full_objects:
            obj.hide_render = local
        for obj in local_objects:
            obj.hide_render = not local
        for obj in local_overlay:
            obj.hide_render = not local
        for obj in camera_objects:
            obj.hide_render = local
        for obj in labels:
            bpy.data.objects.remove(obj, do_unlink=True)
        labels.clear()

    def text(name, body, p, size, color=COLORS["text"]):
        curve = bpy.data.curves.new(name + "_TEXT", type="FONT")
        curve.body, curve.size, curve.align_x = body, size, "LEFT"
        obj = bpy.data.objects.new(name, curve)
        display.objects.link(obj)
        obj.location, obj.rotation_euler, obj.color = p, cam.rotation_euler, color
        labels.append(obj)
        return obj

    def title(body, row=0, color=COLORS["text"]):
        scale = current_view["ortho_scale_bu"]
        r, u, f = (Vector(current_view[k]) for k in ("right", "up", "forward"))
        center = cam.location + f * 30
        if row == 0:
            panel = [
                center + f + r * x * scale + u * y * scale
                for x, y in [(-0.497, 0.313), (-0.497, 0.20), (0.497, 0.20), (0.497, 0.313)]
            ]
            labels.append(
                mesh_object(
                    "DISPLAY_CAPTION_BACKGROUND",
                    [list(p) for p in panel],
                    [[0, 1, 2, 3]],
                    (0.012, 0.018, 0.025, 1),
                )
            )
        text(
            "CLARITY_CAPTION",
            body,
            center - r * scale * 0.48 + u * scale * (0.288 - row * 0.030),
            scale * 0.014,
            color,
        )

    def world_camera_labels():
        size = current_view["ortho_scale_bu"] * 0.013
        for index, camera in enumerate(camera_geometry):
            p = camera["position_bu"]
            text(
                "CAMERA_WORLD_LABEL",
                camera["camera_id"].replace("CAM_1F_AUDITORIUM_", ""),
                [p[0] + 40, p[1] - 45, p[2] + 10],
                size,
                COLORS["camera"] if index == 0 else COLORS["rear"],
            )

    def render(name, extra=None):
        path = out / name
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        row = {
            "path": name,
            "sha256": digest(path),
            "bytes": path.stat().st_size,
            "width": current_view["width"],
            "height": current_view["height"],
            "review_camera": current_view.copy(),
            "source_camera_markers": camera_marker_records(context["cameras"], current_view),
        }
        row.update(extra or {})
        return row

    out.mkdir(parents=True, exist_ok=True)
    roi_corners = [
        [x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])
    ]
    fit_points = roi_corners + camera_label_anchors + [c["position_bu"] for c in camera_geometry]
    center = (lo + hi) / 2
    floor_view = fit_view([center[0], center[1], 3500], [center[0], center[1], 20], fit_points)
    apply_view(floor_view)
    title("COMPLETE 1F CONTEXT + BOTH SOURCE CAMERAS | DIAGNOSTIC / NO GT")
    title(
        "Orange: office location. Purple: pending tested body scope. Grey: uncertified context",
        1,
    )
    title(
        "Blue FRONT / teal REAR + calibrated direction wires; no visibility or collision proof", 2
    )
    world_camera_labels()
    floor = render(
        "floor_complete.png", {"fit_points_bu": fit_points, "fit_margin": floor_view["fit_margin"]}
    )
    projected_fit = [project_to_view(p, current_view) for p in fit_points]
    floor["projected_fit_pixels"] = projected_fit
    if not all(
        0.059 <= p[0] / 1280 <= 0.941 and 0.219 <= p[1] / 800 <= 0.941 for p in projected_fit
    ):
        raise ValueError("complete floor/camera/label points escaped required framing margins")
    if args.pause_after_map:
        print("CLARITY_MAP_READY_SEND_CONTINUE: " + str(out / "floor_complete.png"), flush=True)
        if sys.stdin.readline().strip() != "CONTINUE":
            raise ValueError("map review stopped unsaved diagnostic renderer")
    office_view = {
        "position_bu": [1810, 1550, 650],
        "target_bu": [office_center[0], office_center[1], 60],
        "ortho_scale_bu": 780,
        "width": 1280,
        "height": 800,
        **camera_basis([1810, 1550, 650], [office_center[0], office_center[1], 60]),
    }
    apply_view(office_view)
    title("OFFICE CONTEXT | Source-camera positions remain in the complete 1F map")
    title(
        "Offscreen source cameras: page pointers / minimap retain their actual locations",
        1,
    )
    title("Green floor support APPROVED; purple HR01 body scope / orange routes NOT_CERTIFIED", 2)
    office_record = render("office_context.png")
    approach = []
    for frame in range(25):
        fraction = frame / 24
        eased = fraction * fraction * (3 - 2 * fraction)
        position = [
            floor_view["position_bu"][i] * (1 - eased) + office_view["position_bu"][i] * eased
            for i in range(3)
        ]
        target = [
            floor_view["target_bu"][i] * (1 - eased) + office_view["target_bu"][i] * eased
            for i in range(3)
        ]
        view = {
            "position_bu": position,
            "target_bu": target,
            "ortho_scale_bu": floor_view["ortho_scale_bu"] * (1 - eased) + 780 * eased,
            "width": 960,
            "height": 600,
            **camera_basis(position, target, reference_up=[0, 1 - eased, eased]),
        }
        apply_view(view)
        title("CAMERA APPROACH ONLY | Both source-camera locations are tracked by page pointers")
        title(
            "FRONT / REAR directions: frozen calibration. Public visibility: separate timeline",
            1,
        )
        title(
            "1F cutaway Z145 BU: display-only; original geometry / physical authority unchanged",
            2,
        )
        world_camera_labels()
        approach.append(
            render(
                f"approach_{frame:03d}.png",
                {
                    "frame_id": frame,
                    "timestamp": frame / 5,
                    "person_movement_changed": False,
                    "display_only_camera_approach": True,
                },
            )
        )
    # Same illustrative anatomy as the existing motion recording, at its public frame20 endpoint.
    body_root = bpy.data.objects.new("HR02_BODY_DISPLAY_ONLY_PENDING_FLOOR_BINDING", None)
    display.objects.link(body_root)
    body_root.location = body_frame["body_base_bu"]
    body_parts = []
    for name, p, scale in [
        ("HEAD", (0, 0, 62), (4.2, 4.2, 4.2)),
        ("TORSO", (0, 0, 44), (7.5, 4.2, 12)),
        ("PELVIS", (0, 0, 29), (6, 3.8, 5)),
    ]:
        obj = sphere("ILLUSTRATIVE_HR02_" + name, p, 1, COLORS["body"])
        obj.scale, obj.parent = scale, body_root
        body_parts.append(obj)
    for a, b in [
        ((-7, 0, 51), (-7, 0, 33)),
        ((7, 0, 51), (7, 0, 33)),
        ((-4, 0, 28), (-4, 0, 2)),
        ((4, 0, 28), (4, 0, 2)),
    ]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=1, depth=1)
        obj = bpy.context.object
        obj.name, obj.color, obj.parent = "ILLUSTRATIVE_HR02_LIMB", COLORS["body"], body_root
        va, vb = Vector(a), Vector(b)
        obj.location, obj.rotation_euler, obj.scale = (
            (va + vb) / 2,
            (vb - va).to_track_quat("Z", "Y").to_euler(),
            (1.7, 1.7, (vb - va).length),
        )
        body_parts.append(obj)
    for prefix, radius, height, color in [
        ("BODY", 0.30 / SCALE, 1.70 / SCALE, COLORS["body"]),
        ("CLEARANCE", 0.35 / SCALE, 1.75 / SCALE, COLORS["foot"]),
    ]:
        rings = [
            [radius * math.cos(i * math.tau / 24), radius * math.sin(i * math.tau / 24), z]
            for z in (0, height)
            for i in range(24)
        ]
        for off in (0, 24):
            obj = line("HR02_" + prefix + "_RING", rings[off : off + 24], color, 0.3, True)
            obj.parent = body_root
        for i in range(0, 24, 6):
            obj = line("HR02_" + prefix + "_UPRIGHT", [rings[i], rings[i + 24]], color, 0.25)
            obj.parent = body_root
    foot = body_frame["body_base_bu"]
    sphere("HR02_APPROVED_FLOOR_CONTACT_HYPOTHESIS", foot, 2.1, COLORS["foot"])
    sphere("HR02_PUBLIC_MARKER_PLANE_REFERENCE", marker, 2.5, COLORS["camera"])
    line("HR02_PENDING_BINDING_VERTICAL", [foot, marker], COLORS["camera"], 0.5)
    dimension_low = [foot[0], foot[1] + 24, floor_z]
    dimension_high = [foot[0], foot[1] + 24, landmark_z]
    line("HR02_1_36M_DIMENSION", [dimension_low, dimension_high], COLORS["camera"], 0.6)
    for p in (dimension_low, dimension_high):
        line(
            "HR02_DIMENSION_TICK",
            [[p[0], p[1] - 3, p[2]], [p[0], p[1] + 3, p[2]]],
            COLORS["camera"],
            0.6,
        )
    side_points = [
        foot,
        marker,
        [foot[0], foot[1], floor_z + 1.75 / SCALE],
        dimension_low,
        dimension_high,
    ]
    side_view = fit_view(
        [foot[0] + 250, foot[1], floor_z + 40],
        [foot[0], foot[1], floor_z + 40],
        side_points,
        1280,
        800,
    )
    side_view["ortho_scale_bu"] = max(side_view["ortho_scale_bu"], 180)
    apply_view(side_view, True)
    title("HR02 BODY SIDE VIEW | Foot and landmark are different reference points")
    title(
        "Illustrative person + approved body policy; placement and marker identity remain pending",
        1,
    )
    title(
        "1.359735m is vertical landmark-to-foot conversion, not ceiling height or walking distance",
        2,
    )
    text(
        "HR02_FOOT_LABEL",
        "FOOT / approved source floor",
        [foot[0] + 30, foot[1] - 14, floor_z - 5],
        3.4,
        COLORS["foot"],
    )
    text(
        "HR02_MARKER_LABEL",
        "LANDMARK (pending rigid marker semantics)",
        [foot[0] + 30, foot[1] - 35, landmark_z + 5],
        3.4,
        COLORS["camera"],
    )
    text(
        "HR02_HEIGHT_LABEL",
        "1.359735 m",
        [foot[0] + 30, foot[1] + 28, (floor_z + landmark_z) / 2],
        3.6,
        COLORS["camera"],
    )
    hr02 = render(
        "hr02_body_side.png",
        {
            "body_frame_id": 20,
            "footpoint_bu": foot,
            "landmark_position_bu": marker,
            "public_projected_landmark_bu": body_frame["landmark_position_bu"],
            "floor_z_bu": floor_z,
            "landmark_z_bu": landmark_z,
            "offset_bu": landmark_z - floor_z,
            "offset_m": (landmark_z - floor_z) * SCALE,
            "body_policy": {"radius": 0.30, "height": 1.70, "clearance": 0.05},
            "joint_pose_authority": "DISPLAY_ONLY",
            "binding_authority": "PENDING_HR02_NOT_APPROVED",
        },
    )
    if digest(source) != SOURCE_SHA or (source.stat().st_size, source.stat().st_mtime_ns) != (
        source_before.st_size,
        source_before.st_mtime_ns,
    ):
        raise ValueError("original source scene changed")
    for relative, expected in protected.items():
        if digest(public_path(relative)) != expected:
            raise ValueError("original evidence or media changed: " + relative)
    manifest = {
        "schema_version": "phase1-human-review-clarity-v1",
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
        "floor": floor,
        "office": office_record,
        "hr02": hr02,
        "approach_frames": approach,
        "approach_fps": 5,
        "approach_duration_seconds": 5,
        "display_only_camera_approach": True,
        "person_movement_changed": False,
        "new_route_generated": False,
        "joint_pose_authority": "DISPLAY_ONLY",
        "floor_display_bounds_bu": {"minimum": lo.tolist(), "maximum": hi.tolist()},
        "source_bounds_bu": {"minimum": lo.tolist(), "maximum": hi.tolist()},
        "tested_scope_bounds_bu": geometry["body_envelope_bounds_bu"],
        "whole_1f_authority": "ANNOTATION_CONTEXT_ONLY_NOT_CERTIFIED",
        "tested_scope_authority": "PENDING_HR01_NOT_CERTIFIED",
        "camera_calibrations": context["cameras"],
        "calibrated_camera_geometry": camera_geometry,
        "calibration_context_sha256": digest(
            public_path("data/finalization/local_run/dataset/inference/office/context.json")
        ),
        "visibility_timeline": [
            {
                "frame_id": r["frame_id"],
                "timestamp": r["timestamp"],
                "state": r["state"],
                "camera_evidence": r["camera_evidence"],
            }
            for r in motion["frames"]
        ],
        "source_frame": audit["scene"],
        "blender_version": bpy.app.version_string,
        "render_policy": {
            "engine": "BLENDER_WORKBENCH",
            "workbench_shadows_display_only": True,
            "workbench_cavity": False,
            "display_shadows_are_physical_or_visibility_evidence": False,
            "source_snapshot": "FROZEN_EVALUATED_VIEWPORT_MESH",
            "source_objects": source_names,
            "source_triangle_count": triangle_count,
            "source_cutaway_z_bu": 145,
            "hr02_cutaway_z_bu": 110,
            "cutaway_purpose": "DISPLAY_ONLY",
            "native_camera_positions_changed": False,
            "camera_wire_display_length_bu": 120,
            "camera_optical_axis_display_length_bu": 180,
            "visibility_or_collision_proof": False,
            "original_source_objects_removed_in_memory_only": True,
        },
        "shape_legend": {
            "grey": "Evaluated source geometry; display cutaway only, not collider approval",
            "green": "Existing approved source floor support only",
            "purple": "Pending HR01 body guard and zero-area faces1975/2398",
            "amber": "Office annotation/candidate context NOT_CERTIFIED; illustrative body",
            "blue_teal": "Source camera locations/calibrated directions; no visibility proof",
            "cyan_marker": "Public landmark plane; pending HR02 body-floor semantics",
            "yellow_foot": "Proposed foot contact on approved source support",
        },
        "preserved_existing_hashes": protected,
        "inputs": [{"path": p, "sha256": digest(public_path(p))} for p in sorted(INPUT_RELATIVE)],
        "renderer_sha256": digest(Path(__file__).resolve()),
        "limitations": [
            "Complete 1F framing does not establish whole-floor physical authority.",
            "Calibration wires and location pointers do not certify FOV or occlusion.",
            "Public visibility timeline is reused; no GT pair or route selection is performed.",
            "Illustrated HR02 person is not motion capture; marker/floor binding remains pending.",
        ],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {"stills": 3, "approach_frames": 25, "source_preserved": True, "output": str(out)}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
