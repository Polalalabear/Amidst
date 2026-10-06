"""Add a moving diagnostic body in actual bounded school source geometry.

Blender --background --factory-startup --disable-autoexec school_v3.blend
--python-exit-code 2 --python human_review/render_motion_context.py -- --frames 50.
Existing visual-manifest positions are copied exactly. Limb motion is an
illustration, not measured motion capture; pending floor binding stays pending.
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
OUT = REVIEW / "frames/motion_context"
SOURCE_SHA = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
SCALE = 0.0247
INPUT_RELATIVE = frozenset(
    {
        "human_review/review_template.json",
        "human_review/geometry_evidence.json",
        "human_review/frames/visual_manifest.json",
        "human_review/frames/spatial_context/spatial_context_manifest.json",
        "data/scene_audit/school_v3_semantic_audit.json",
        "data/scene_audit/phase1_physical_policy_approval_20261006/floor_support_details.json.gz",
        "data/finalization/local_run/dataset/inference/office/context.json",
        "data/finalization/local_run/diagnostics/office/policy_graph_primary/projected_frames.json",
        "data/finalization/local_run/diagnostics/office/policy_graph_primary/candidates.json",
    }
)
COLORS = {
    "source": (0.40, 0.46, 0.51, 1),
    "support": (0.12, 0.42, 0.23, 1),
    "observed": (0.07, 0.76, 1, 1),
    "gap": (1, 0.53, 0.06, 1),
    "scope": (0.80, 0.45, 1, 1),
    "clearance": (1, 0.96, 0.57, 1),
    "portal": (0.13, 0.61, 0.92, 1),
    "obstacle": (0.79, 0.26, 0.22, 1),
    "text": (1, 1, 1, 1),
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def public_path(relative: str, repo_root: Path = ROOT) -> Path:
    path = Path(relative)
    root = repo_root.resolve()
    if (
        path.is_absolute()
        or not (root / path).resolve().is_relative_to(root)
        or any(s in relative.lower() for s in ("ground_truth", "evaluation/", "simulation/"))
    ):
        raise ValueError("motion preview cannot read private GT/evaluation/simulation evidence")
    return root / path


def read_public(path: Path, *, repo_root: Path = ROOT):
    root = repo_root.resolve()
    allowlist = {public_path(name, root).resolve() for name in INPUT_RELATIVE}
    if path.resolve() not in allowlist:
        raise ValueError("motion context reads only explicit public source/review inputs")
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def verified_inputs(repo_root: Path = ROOT) -> dict[str, str]:
    """Check frozen expected hashes before reading observations or evaluating Blender."""
    template = read_public(repo_root / "human_review/review_template.json", repo_root=repo_root)
    metadata = template["metadata"]
    if metadata["source_sha256"] != SOURCE_SHA or metadata["gt_used_for_review"] is not False:
        raise ValueError("review source/GT lineage mismatch")
    rows = metadata["input_hashes"]
    if len(rows) != 29 or len({row["path"] for row in rows}) != 29:
        raise ValueError("motion preview requires the original 29 frozen inputs")
    protected = {}
    for row in rows:
        actual = digest(public_path(row["path"], repo_root))
        if actual != row["sha256"]:
            raise ValueError("frozen review input SHA-256 mismatch: " + row["path"])
        protected[row["path"]] = actual
    old = read_public(repo_root / "human_review/frames/visual_manifest.json", repo_root=repo_root)
    spatial = read_public(
        repo_root / "human_review/frames/spatial_context/spatial_context_manifest.json",
        repo_root=repo_root,
    )
    old_rows = [
        *old["frames"],
        *old["still_frames"],
        *old["camera_stills"],
        *old["closeup_frames"],
    ]
    image_rows = [("human_review/" + row["path"], row) for row in old_rows]
    image_rows.extend(
        ("human_review/frames/spatial_context/" + row["path"], row)
        for row in [
            spatial["overview"],
            spatial["floor"],
            spatial["office"],
            *spatial["approach_frames"],
        ]
    )
    if len(image_rows) != 85:
        raise ValueError("expected all 85 pre-existing PNGs")
    for relative, row in image_rows:
        actual = digest(public_path(relative, repo_root))
        if actual != row["sha256"]:
            raise ValueError("existing PNG hash mismatch: " + relative)
        protected[relative] = actual
    for relative in [
        "human_review/review_template.json",
        "human_review/decisions.json",
        "human_review/README.md",
        "human_review/index.html",
        "human_review/frames/player.html",
        "human_review/frames/spatial_context/guide.html",
        "human_review/frames/spatial_context/spatial_context_manifest.json",
    ]:
        protected[relative] = digest(public_path(relative, repo_root))
    return protected


def load_motion_trace(repo_root: Path = ROOT) -> dict:
    """Copy the existing public/inferred trace; do not invent or re-float positions."""
    old = read_public(repo_root / "human_review/frames/visual_manifest.json", repo_root=repo_root)
    frames = old["frames"]
    if (
        old["gt_used"] is not False
        or old["evaluation_files_read"] is not False
        or old["simulation_recipe_read"] is not False
        or old["source_asset_sha256"] != SOURCE_SHA
        or len(frames) != 50
        or old["sequence_fps"] != 5
    ):
        raise ValueError("existing motion trace is not the frozen GT-free 50-frame sequence")
    projected = read_public(
        repo_root
        / "data/finalization/local_run/diagnostics/office/policy_graph_primary"
        / "projected_frames.json",
        repo_root=repo_root,
    )["dataset"]["samples"]
    public_by_frame = {}
    for sample in projected:
        public_by_frame.setdefault(sample["frame_id"], []).append(sample)
    for index, row in enumerate(frames):
        if row["frame_id"] != index or row["timestamp"] != index / 5:
            raise ValueError("existing public frame order or sampling mismatch")
        samples = public_by_frame[index]
        visible = sorted(
            [s for s in samples if s["projected_point"] is not None],
            key=lambda s: s["camera_id"],
        )
        if visible and any(
            abs(a - b) > 0.001
            for a, b in zip(
                row["landmark_position_bu"],
                visible[0]["projected_point"]["world_position"],
                strict=True,
            )
        ):
            raise ValueError("existing body trace differs from public projected evidence")
        if (
            any(row["body_base_bu"][i] != row["landmark_position_bu"][i] for i in (0, 1))
            or row["body_base_bu"][2] != old["approved_support_z_bu"]
        ):
            raise ValueError("pending floor binding changed")
    distance = (
        sum(
            math.dist(a["body_base_bu"], b["body_base_bu"])
            for a, b in zip(frames[:-1], frames[1:], strict=True)
        )
        * SCALE
    )
    return {
        "frames": frames,
        "fps": 5,
        "duration_seconds": 10,
        "trajectory_time_range_seconds": [0, 9.8],
        "total_body_distance_m": distance,
        "visible_extent_m": math.dist(frames[0]["body_base_bu"], frames[-1]["body_base_bu"])
        * SCALE,
        "vertical_coordinate_conversion_m": old["proposed_exact_landmark_offset_m"],
        "trajectory_basis": "EXISTING_PUBLIC_PROJECTIONS_AND_INFERRED_CANDIDATE",
        "joint_pose_authority": "DISPLAY_ONLY",
        "foot_binding_authority": "PENDING_HR02_NOT_APPROVED",
        "new_route_generated": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=50)
    parser.add_argument("--width", type=int, default=960, choices=[720, 960])
    parser.add_argument("--pause-after-first", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.frames != 50:
        raise ValueError("the additive preview must copy all 50 original frames")
    if any(OUT.glob("motion_*.png")) or (OUT / "motion_manifest.json").exists():
        raise ValueError("motion preview output already exists; choose an isolated fresh checkout")
    protected = verified_inputs()
    trace = load_motion_trace()
    audit = read_public(ROOT / "data/scene_audit/school_v3_semantic_audit.json")
    geometry = read_public(REVIEW / "geometry_evidence.json")
    context = read_public(
        ROOT / "data/finalization/local_run/dataset/inference/office/context.json"
    )
    support = read_public(
        ROOT
        / "data/scene_audit/phase1_physical_policy_approval_20261006/floor_support_details.json.gz"
    )
    candidates = read_public(
        ROOT / "data/finalization/local_run/diagnostics/office/policy_graph_primary/candidates.json"
    )["results"][0]["candidates"]
    bpy = importlib.import_module("bpy")
    Vector = importlib.import_module("mathutils").Vector
    np = importlib.import_module("numpy")
    source = Path(bpy.data.filepath).resolve()
    before = source.stat()
    if digest(source) != SOURCE_SHA or audit["source_sha256"] != SOURCE_SHA:
        raise ValueError("exact source school_v3.blend SHA-256 mismatch")
    scene = bpy.context.scene
    scene.frame_set(audit["scene"]["frame"])
    if scene.name != audit["scene"]["name"]:
        raise ValueError("audited source scene mismatch")
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = args.width, args.width * 5 // 8
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.use_border = scene.render.use_crop_to_border = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode, scene.render.image_settings.color_depth = "RGB", "8"
    scene.render.image_settings.compression = 90
    scene.render.film_transparent = False
    scene.render.use_compositing = scene.render.use_sequencer = False
    scene.display.render_aa = "8"
    shading = scene.display.shading
    shading.light, shading.color_type = "STUDIO", "OBJECT"
    shading.show_shadows = shading.show_cavity = shading.show_specular_highlight = False
    shading.show_xray = False
    shading.background_type = "WORLD"
    scene.world.color = (0.030, 0.041, 0.050)
    scene.view_settings.view_transform, scene.view_settings.look = "Standard", "None"
    scene.view_settings.exposure, scene.view_settings.gamma = 0, 1
    source_native_objects = list(scene.objects)
    source_cameras = []
    for row in context["cameras"]:
        native = bpy.data.objects.get(row["camera_id"])
        position = [row["camera_to_world"][i][3] for i in range(3)]
        if native is None or not np.allclose(list(native.location), position, atol=1e-3):
            raise ValueError("source camera location differs from frozen public calibration")
        source_cameras.append({"camera_id": row["camera_id"], "position_bu": position})
    for obj in list(scene.objects):
        obj.hide_render = True
    for col in bpy.data.collections:
        col.hide_render = False
    display = bpy.data.collections.new("MOTION_CONTEXT_SOURCE_AND_ILLUSTRATION_UNSAVED")
    scene.collection.children.link(display)

    def mesh_object(name, vertices, faces, color):
        mesh = bpy.data.meshes.new(name + "_MESH")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        display.objects.link(obj)
        obj.color = color
        return obj

    # Tight display crop only; no geometric certificate or source-asset modification.
    lo = np.array([1320.0, 1880.0, -1.0])
    hi = np.array([1500.0, 2170.0, 110.0])
    source_rows = []
    for row in audit["full_scene_inventory"]["objects"]:
        bounds = row.get("bounding_box")
        if (
            row["object_type"] == "MESH"
            and not row["object"].startswith(
                ("AREA_", "WALK_", "PORTAL_", "OBSTACLE_", "WALL_", "STAIR_")
            )
            and bounds
            and all(
                bounds["maximum"][i] >= lo[i] and bounds["minimum"][i] <= hi[i] for i in range(3)
            )
        ):
            source_rows.append(row)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    source_objects, retained_triangles = [], 0
    for row in source_rows:
        native = bpy.data.objects.get(row["object"])
        if native is None:
            raise ValueError("audited source object is missing: " + row["object"])
        evaluated = native.evaluated_get(depsgraph)
        # One temporary evaluated mesh at a time: do not duplicate whole school meshes.
        mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
        try:
            mesh.calc_loop_triangles()
            coords = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
            mesh.vertices.foreach_get("co", coords)
            matrix = np.asarray(evaluated.matrix_world)
            world = coords.reshape((-1, 3)) @ matrix[:3, :3].T + matrix[:3, 3]
            triangles = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
            mesh.loop_triangles.foreach_get("vertices", triangles)
            triangles = triangles.reshape((-1, 3))
            points = world[triangles]
            intersects = np.all(points.max(axis=1) >= lo, axis=1) & np.all(
                points.min(axis=1) <= hi, axis=1
            )
            # Display cutaway drops faces crossing the lid, retaining exact remaining vertices.
            intersects &= np.all(points[:, :, 2] <= hi[2], axis=1)
            selected = triangles[intersects]
            if not len(selected):
                continue
            indices, inverse = np.unique(selected, return_inverse=True)
            mesh_object(
                "DISPLAY_LOCAL_SOURCE_" + row["object"],
                world[indices].tolist(),
                inverse.reshape((-1, 3)).tolist(),
                COLORS["source"],
            )
            retained_triangles += len(selected)
            source_objects.append(row["object"])
        finally:
            evaluated.to_mesh_clear()
        print("MOTION bounded source", len(source_objects), row["object"], flush=True)
    # Remove only in-memory native objects after the bounded evaluated display copy.
    # The original .blend and every filesystem artifact remain unchanged.
    del depsgraph, mesh, evaluated, native, world, points, triangles, coords
    for obj in source_native_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    del source_native_objects
    gc.collect()
    print("MOTION original in-memory scene meshes released", flush=True)

    def line(name, points, color, radius=0.55, cyclic=False):
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

    def sphere(name, position, radius, color):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=12, ring_count=6, radius=radius, location=position
        )
        obj = bpy.context.object
        obj.name, obj.color = name, color
        return obj

    floor_z = geometry["prospective_footpoint_bounds_bu"][0][2]
    office_support = next(
        row for row in support["walkable_reviews"] if row["walkable_id"] == "WALK_1F_OFFICE"
    )
    for row in support["support_surfaces"]:
        if row["surface_id"] in office_support["support_surface_ids"]:
            mesh_object(
                "APPROVED_SUPPORT_DISPLAY_OFFSET_ONLY",
                [[p[0], p[1], p[2] + 0.4] for p in row["vertices"]],
                row["triangles"],
                COLORS["support"],
            )
    objects = {row["object"]: row for row in audit["objects"]}
    for name in ("OBSTACLE_1F_OFFICE_01", "OBSTACLE_1F_OFFICE_02"):
        row = objects[name]
        # Annotation outline, not an approved source collider.
        bounds = row["bounding_box"]
        low, high = bounds["minimum"], bounds["maximum"]
        line(
            "SEMANTIC_OBSTACLE_NO_SOLID_APPROVAL_" + name,
            [
                [low[0], low[1], floor_z + 1],
                [high[0], low[1], floor_z + 1],
                [high[0], high[1], floor_z + 1],
                [low[0], high[1], floor_z + 1],
            ],
            COLORS["obstacle"],
            cyclic=True,
        )
    for candidate in candidates:
        color = COLORS["obstacle"] if "left" in candidate["navmesh_corridor"][0] else COLORS["gap"]
        line(
            "EXISTING_INFERRED_CANDIDATE_" + candidate["navmesh_corridor"][0],
            [[p[0], p[1], floor_z + 1.3] for p in candidate["polyline"]],
            color,
            radius=0.7,
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
        line("PENDING_HR01_BODY_GUARD", [corners[a], corners[b]], COLORS["scope"], radius=0.35)
    for finding in geometry["findings"]:
        points = [[p[0], max(lo[1], min(hi[1], p[1])), p[2] + 1.4] for p in finding["triangle_bu"]]
        line(
            "EXACT_ZERO_AREA_SEAM_DISPLAY_" + str(finding["source_face_index"]),
            points,
            COLORS["scope"],
            radius=0.8,
        )
    projected_points = []
    for row in trace["frames"]:
        if row["role"].startswith("OBSERVED"):
            p = row["landmark_position_bu"]
            if p not in projected_points:
                sphere("EXISTING_PUBLIC_PROJECTED_POINT", p, 0.8, COLORS["observed"])
                projected_points.append(p)
    body_root = bpy.data.objects.new("MOVING_PENDING_BODY_BINDING", None)
    display.objects.link(body_root)
    avatar_parts, envelope_parts = [], []

    def parent_sphere(name, position, scale):
        obj = sphere(name, position, 1, COLORS["observed"])
        obj.scale, obj.parent = scale, body_root
        avatar_parts.append(obj)
        return obj

    parent_sphere("ILLUSTRATIVE_HEAD_NOT_MOCAP", (0, 0, 62), (4.2, 4.2, 4.2))
    parent_sphere("ILLUSTRATIVE_TORSO_NOT_MOCAP", (0, 0, 44), (7.5, 4.2, 12))
    parent_sphere("ILLUSTRATIVE_PELVIS_NOT_MOCAP", (0, 0, 29), (6, 3.8, 5))
    limbs = []
    for name in ("ARM_L", "ARM_R", "LEG_L", "LEG_R"):
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=1, depth=1)
        obj = bpy.context.object
        obj.name = "ILLUSTRATIVE_LIMB_" + name
        obj.parent = body_root
        avatar_parts.append(obj)
        limbs.append(obj)
    body_radius, body_height = 0.30 / SCALE, 1.70 / SCALE
    for prefix, radius, height, color in [
        ("BODY_POLICY", body_radius, body_height, COLORS["observed"]),
        ("CLEARANCE_POLICY", 0.35 / SCALE, 1.75 / SCALE, COLORS["clearance"]),
    ]:
        rings = [
            [radius * math.cos(i * math.tau / 24), radius * math.sin(i * math.tau / 24), z]
            for z in (0, height)
            for i in range(24)
        ]
        for offset in (0, 24):
            obj = line(
                prefix + "_RING", rings[offset : offset + 24], color, radius=0.35, cyclic=True
            )
            obj.parent = body_root
            envelope_parts.append(obj)
        for i in range(0, 24, 6):
            obj = line(prefix + "_UPRIGHT", [rings[i], rings[i + 24]], color, radius=0.25)
            obj.parent = body_root
            envelope_parts.append(obj)
    active_landmark = sphere(
        "ACTIVE_PUBLIC_OR_INFERRED_PROJECTION", (0, 0, 0), 2, COLORS["observed"]
    )
    binding_link = line(
        "PENDING_HR02_LANDMARK_FLOOR_BINDING",
        [[0, 0, 0], [0, 0, 1]],
        COLORS["observed"],
        radius=0.45,
    )
    camera_links = {}
    for row in source_cameras:
        camera_links[row["camera_id"]] = line(
            "PUBLIC_OBSERVATION_CAMERA_LINK_" + row["camera_id"],
            [row["position_bu"], [0, 0, 0]],
            COLORS["observed"],
            radius=0.25,
        )
    camera_data = bpy.data.cameras.new("DIAGNOSTIC_MOTION_REVIEW_CAMERA")
    camera = bpy.data.objects.new("DIAGNOSTIC_MOTION_REVIEW_CAMERA_UNSAVED", camera_data)
    scene.collection.objects.link(camera)
    camera_data.type, camera_data.clip_start, camera_data.clip_end = "ORTHO", 0.1, 10000
    camera.location = (1600, 1770, 330)
    target = Vector((1405, 2018, 48))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.ortho_scale = 330
    scene.camera = camera
    rotation = camera.rotation_euler.to_matrix()
    right, up, front = (rotation @ Vector(v) for v in [(1, 0, 0), (0, 1, 0), (0, 0, -1)])
    camera.location += up * 22
    label_center = camera.location + front * 30
    panel_vertices = [
        label_center + front + right * x * 330 + up * y * 330
        for x, y in [(-0.495, 0.312), (-0.495, 0.168), (0.495, 0.168), (0.495, 0.312)]
    ]
    mesh_object(
        "DISPLAY_ONLY_CAPTION_PANEL",
        [list(p) for p in panel_vertices],
        [[0, 1, 2, 3]],
        (0.014, 0.018, 0.023, 1),
    )
    label_objects = []
    for row in range(4):
        curve = bpy.data.curves.new("MOTION_LABEL_TEXT", type="FONT")
        curve.align_x, curve.size = "LEFT", 5.1
        obj = bpy.data.objects.new("MOTION_DISPLAY_CAPTION", curve)
        display.objects.link(obj)
        obj.location = label_center - right * 157 + up * (96 - row * 12)
        obj.rotation_euler, obj.color = camera.rotation_euler, COLORS["text"]
        label_objects.append(obj)
    record_frames = []
    OUT.mkdir(parents=True, exist_ok=True)
    elapsed_distance = 0.0
    for index, row in enumerate(trace["frames"]):
        if index:
            elapsed_distance += (
                math.dist(trace["frames"][index - 1]["body_base_bu"], row["body_base_bu"]) * SCALE
            )
        state = "OBSERVED" if row["role"].startswith("OBSERVED") else "INFERRED_GAP"
        color = COLORS["observed"] if state == "OBSERVED" else COLORS["gap"]
        body_root.location = row["body_base_bu"]
        active_landmark.location, active_landmark.color = row["landmark_position_bu"], color
        binding_link.color = color
        binding_link.data.splines[0].points[0].co = (*row["body_base_bu"], 1)
        binding_link.data.splines[0].points[1].co = (*row["landmark_position_bu"], 1)
        for observation in row["camera_evidence"]:
            link = camera_links[observation["camera_id"]]
            link.hide_render = observation["visibility"] != "OBSERVED"
            link.data.splines[0].points[1].co = (*row["landmark_position_bu"], 1)
        for obj in avatar_parts:
            obj.color = color
        for obj in envelope_parts[:6]:
            obj.color = color
        previous = trace["frames"][max(0, index - 1)]["body_base_bu"]
        following = trace["frames"][min(49, index + 1)]["body_base_bu"]
        dx, dy = following[0] - previous[0], following[1] - previous[1]
        body_root.rotation_euler.z = math.atan2(-dx, dy)
        swing = 5 * math.sin(elapsed_distance * math.tau / 0.65)
        endpoints = [
            ((-7, 0, 51), (-7, swing, 33)),
            ((7, 0, 51), (7, -swing, 33)),
            ((-4, 0, 28), (-4, -swing, 2)),
            ((4, 0, 28), (4, swing, 2)),
        ]
        for limb, (a, b) in zip(limbs, endpoints, strict=True):
            va, vb = Vector(a), Vector(b)
            limb.location = (va + vb) / 2
            limb.rotation_euler = (vb - va).to_track_quat("Z", "Y").to_euler()
            limb.scale = (1.7, 1.7, (vb - va).length)
        status = " / ".join(
            s["camera_id"].replace("CAM_1F_AUDITORIUM_", "") + ":" + s["visibility"]
            for s in row["camera_evidence"]
        )
        captions = [
            f"10s BODY MOTION | t={row['timestamp']:04.1f}s | {state} | DIAGNOSTIC / NO GT",
            "Actual local source model; joints are DISPLAY-ONLY illustration, not motion capture",
            "Body r0.30m h1.70m / clearance0.05m | floor binding HR02 / scope HR01 PENDING",
            status + " | purple seams: group_0 faces1975/2398",
        ]
        for obj, caption in zip(label_objects, captions, strict=True):
            obj.data.body = caption
        path = OUT / f"motion_{index:03d}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        record_frames.append(
            {
                "path": path.name,
                "sha256": digest(path),
                "bytes": path.stat().st_size,
                "frame_id": row["frame_id"],
                "timestamp": row["timestamp"],
                "state": state,
                "body_base_bu": row["body_base_bu"],
                "landmark_position_bu": row["landmark_position_bu"],
                "role": row["role"],
                "camera_evidence": row["camera_evidence"],
                "projection_method": row["projection_method"],
                "confidence_state": row["confidence_state"],
                "uncertainty": row["uncertainty"],
                "body_pose_display_only": True,
                "joint_pose_authority": "DISPLAY_ONLY",
            }
        )
        if index == 0 and args.pause_after_first:
            print("MOTION_FIRST_FRAME_READY_SEND_CONTINUE: " + str(path), flush=True)
            if sys.stdin.readline().strip() != "CONTINUE":
                raise ValueError("first-frame review stopped the unsaved diagnostic process")
    source_after = digest(source)
    if source_after != SOURCE_SHA or (source.stat().st_size, source.stat().st_mtime_ns) != (
        before.st_size,
        before.st_mtime_ns,
    ):
        raise ValueError("source scene changed during diagnostic render")
    for relative, expected in protected.items():
        if digest(public_path(relative)) != expected:
            raise ValueError("protected old input/preview changed: " + relative)
    manifest = {
        "schema_version": "phase1-human-review-body-motion-v1",
        "result_type": "DIAGNOSTIC",
        "source_sha256": SOURCE_SHA,
        "source_sha256_after": source_after,
        "source_preserved": True,
        "source_saved": False,
        "source_modified": False,
        "gt_used": False,
        "evaluation_files_read": False,
        "simulation_recipe_read": False,
        "physical_authority_changed": False,
        "formal_execution_enabled": False,
        "fps": 5,
        "sampling_hz": 5,
        "duration_seconds": 10,
        "trajectory_time_range_seconds": [0, 9.8],
        "frames": record_frames,
        "trajectory_basis": trace["trajectory_basis"],
        "joint_pose_authority": "DISPLAY_ONLY",
        "body_pose_display_only": True,
        "new_route_generated": False,
        "display_only_camera_approach": False,
        "body_motion_changed": False,
        "body_motion_reused_exactly": True,
        "fixed_review_camera": True,
        "total_body_distance_m": trace["total_body_distance_m"],
        "visible_extent_m": trace["visible_extent_m"],
        "vertical_coordinate_conversion_m": trace["vertical_coordinate_conversion_m"],
        "foot_binding_authority": "PENDING_HR02_NOT_APPROVED",
        "scope_authority": "PENDING_HR01_NOT_CERTIFIED",
        "render_policy": {
            "engine": "BLENDER_WORKBENCH",
            "width": args.width,
            "height": args.width * 5 // 8,
            "source_evaluation": "FROZEN_EVALUATED_VIEWPORT_LOCAL_TRIANGLES",
            "source_frame": audit["scene"],
            "source_objects": source_objects,
            "retained_source_triangles": retained_triangles,
            "display_crop_bu": {"minimum": lo.tolist(), "maximum": hi.tolist()},
            "display_cutaway": "DROP_SOURCE_FACES_CROSSING_Z110_BU_DISPLAY_ONLY_NO_SOURCE_EDIT",
            "whole_scene_occlusion_proof": False,
        },
        "original_scene_objects_removed_in_memory_only": True,
        "source_camera_locations": source_cameras,
        "review_camera": {
            "position_bu": list(camera.location),
            "rotation_euler_radians": list(camera.rotation_euler),
            "ortho_scale_bu": 330,
        },
        "approved_body_dimensions_m": {"radius": 0.30, "height": 1.70, "clearance": 0.05},
        "source_issue_faces": [1975, 2398],
        "source_issue_authority": "SOURCE_CONTEXT_ONLY_NOT_APPROVED_COLLIDER",
        "display_offsets_bu": {"floor_support": 0.4, "seam": 1.4, "candidate_floor_trace": 1.3},
        "preserved_inputs_and_85_old_images": protected,
        "inputs": [
            {"path": name, "sha256": digest(public_path(name))} for name in sorted(INPUT_RELATIVE)
        ],
        "renderer_sha256": digest(Path(__file__).resolve()),
        "blender_version": bpy.app.version_string,
        "limitations": [
            "OBSERVED means public projected evidence, not measured 3D ground truth.",
            "GAP movement follows the existing inferred direct candidate; "
            "it is not actual hidden motion.",
            "Avatar joint swing is illustrative only; "
            "body placement copies the existing pending binding.",
            "Grey source context and purple reviewed interior are not approved source colliders.",
        ],
    }
    (OUT / "motion_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "frames_rendered": 50,
                "duration_seconds": 10,
                "source_preserved": True,
                "old_images_preserved": 85,
                "gt_used": False,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
