"""Render the new, GT-free HR02 source-camera audit without saving the scene.

Only this audit's new output directory is writable. Source-camera frames retain
the full allowed evaluated VIEWPORT geometry; cutaway context views are display
derivatives and cannot certify visibility, room ownership, or physical validity.
Run only after inspect_hr02_camera_binding.py has completed its source queries.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "human_review/frames/hr02_camera_audit"
SOURCE_SHA = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
WIDTH, HEIGHT = 1920, 1080
INPUTS = frozenset(
    {
        "human_review/frames/hr02_camera_audit/audit_data.json",
        "human_review/frames/hr02_camera_audit/manifest.json",
        "human_review/review_template.json",
        "data/finalization/local_run/dataset/inference/office/context.json",
        "configs/architectural_scale_school_v3.json",
        "configs/physical_authority_policy_school_v3.json",
    }
)
COLORS = {
    "source": (0.38, 0.43, 0.49, 1),
    "office": (1, 0.69, 0.05, 1),
    "front": (0.10, 0.78, 1, 1),
    "rear": (0.18, 1, 0.64, 1),
    "landmark": (0.96, 0.35, 0.89, 1),
    "body": (0.82, 0.88, 0.95, 1),
    "clearance": (1, 0.89, 0.36, 1),
    "hit": (1, 0.18, 0.13, 1),
    "floor": (0.14, 0.66, 0.31, 1),
    "text": (1, 1, 1, 1),
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_public(relative: str) -> dict[str, Any]:
    if relative not in INPUTS:
        raise ValueError("HR02 renderer reads only the explicit diagnostic input allowlist")
    logical = ROOT / relative
    path = logical.resolve()
    if path != logical or not path.is_relative_to(ROOT.resolve()):
        raise ValueError("diagnostic input must stay on its non-symlink allowlisted path")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("diagnostic renderer input must be a JSON object")
    return document


def verify_data(data: dict[str, Any], context: dict[str, Any]) -> None:
    """Require the existing source cameras and all 50 existing display positions."""
    if context["source_asset_sha256"] != SOURCE_SHA:
        raise ValueError("source-context hash mismatch")
    if data["source_sha256"] != SOURCE_SHA or any(
        data.get(key) is not False
        for key in (
            "gt_used",
            "evaluation_files_read",
            "simulation_recipe_read",
            "physical_authority_changed",
            "formal_execution_enabled",
            "human_decisions_applied",
            "source_saved",
            "source_modified",
        )
    ):
        raise ValueError("source query is not an unchanged GT-free diagnostic")
    if data["source_scene"] != {"name": "Scene", "frame": 220, "subframe": 0}:
        raise ValueError("renderer cannot select a new source animation frame")
    protocol = data["diagnostic_protocol"]
    if protocol["scale_m_per_bu"] != 0.0247:
        raise ValueError("approved architectural scale changed")
    if (
        protocol["sourcegeometryscope"] != "FULL_EVALUATED_VIEWPORT_ALLOWED_MESH"
        or protocol["ray_endpoint_tolerance_bu"] != 0.001
        or protocol["annotation_meshes_excluded"] is not True
        or protocol["hide_render_materials_do_not_remove_blockers"] is not True
    ):
        raise ValueError("renderer cannot select a different source geometry policy")
    binding = data["binding"]
    for name, value in (
        ("floor_z_bu", 20.07884979248047),
        ("landmark_z_bu", 75.12884788513183),
        ("body_height_m", 1.7),
        ("body_radius_m", 0.3),
        ("clearance_m", 0.05),
    ):
        if binding[name] != value:
            raise ValueError("renderer cannot change frozen floor/landmark/body policy")
    if not math.isclose(
        binding["offset_bu"],
        binding["landmark_z_bu"] - binding["floor_z_bu"],
        rel_tol=0,
        abs_tol=1e-10,
    ):
        raise ValueError("pending landmark/floor offset changed")
    cameras = {row["camera_id"]: row for row in context["cameras"]}
    if len(cameras) != 2 or len(data["cameras"]) != 2:
        raise ValueError("HR02 renderer requires the two existing source cameras")
    for row in data["cameras"]:
        if row["calibration"] != cameras[row["camera_id"]]:
            raise ValueError("audit selected a new source-camera calibration")
        if row["position_bu"] != [row["calibration"]["camera_to_world"][i][3] for i in range(3)]:
            raise ValueError("camera position no longer equals frozen calibration")
    if len(data["frames"]) != 50:
        raise ValueError("HR02 diagnostic requires the complete existing 50-frame trace")
    for index, row in enumerate(data["frames"]):
        if row["frame_id"] != index or row["timestamp"] != index / 5:
            raise ValueError("renderer cannot resample or reorder the trace")
        for key in ("landmark_position_bu", "foot_position_bu"):
            point = row[key]
            if len(point) != 3 or not all(math.isfinite(value) for value in point):
                raise ValueError("audit contains an invalid display position")
        if row["foot_position_bu"][2] != binding["floor_z_bu"]:
            raise ValueError("pending body floor position changed")
        if {item["camera_id"] for item in row["cameras"]} != set(cameras):
            raise ValueError("audit camera evidence is incomplete")


def vector_dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def vector_cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def unit(a: list[float]) -> list[float]:
    length = math.hypot(*a)
    if not math.isfinite(length) or length == 0:
        raise ValueError("invalid diagnostic camera direction")
    return [value / length for value in a]


def fit_view(
    position: list[float], target: list[float], points: list[list[float]]
) -> dict[str, Any]:
    """Fit complete camera-to-OFFICE spans below captions; scale is horizontal."""
    forward = unit([target[i] - position[i] for i in range(3)])
    right = unit(vector_cross(forward, [0, 0, 1]))
    up = unit(vector_cross(right, forward))
    xs, ys = [vector_dot(p, right) for p in points], [vector_dot(p, up) for p in points]
    aspect = WIDTH / HEIGHT
    scale = max((max(xs) - min(xs)) / 0.84, (max(ys) - min(ys)) * aspect / 0.72)
    scale = max(scale, 100) * 1.015
    mid_x, mid_y = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    wanted_y = mid_y + 0.08 * scale / aspect
    shift = [
        right[i] * (mid_x - vector_dot(target, right)) + up[i] * (wanted_y - vector_dot(target, up))
        for i in range(3)
    ]
    return {
        "position_bu": [position[i] + shift[i] for i in range(3)],
        "right": right,
        "up": up,
        "forward": forward,
        "ortho_scale_bu": scale,
        "width": WIDTH,
        "height": HEIGHT,
        "fit_points_bu": points,
        "fit_margin": {"x": [0.08, 0.92], "y": [0.22, 0.94]},
    }


def capture_source_geometry(
    raycaster: Any, np: Any, collections: Any
) -> tuple[list[dict[str, Any]], str]:
    """Copy each live instance completely before advancing its RNA iterator.

    Cached evaluated objects and native prototypes cannot reproduce all evaluated
    instances. Only the original raycaster's plain name/matrix inventory is read;
    geometry comes directly from the active VIEWPORT instance iteration, using
    the identical exclusion rules, before any Blender ID creation or mutation.
    """
    snapshots: list[dict[str, Any]] = []
    descriptors = [
        {
            "object_name": str(instance.object_name),
            "matrix": np.array([list(row) for row in instance.matrix], dtype=np.float64, copy=True),
        }
        for instance in raycaster._meshes
    ]

    def original_pointer(obj: Any) -> int:
        return int(obj.original.as_pointer())

    def inventory_key(row: dict[str, Any]) -> tuple[str, tuple[float, ...]]:
        return row["object_name"], tuple(float(value) for value in row["matrix"].ravel())

    excluded = {original_pointer(obj) for obj in raycaster.excluded_objects}
    areas = collections.get("Areas")
    if areas is not None:
        excluded.update(original_pointer(obj) for obj in areas.all_objects)
    for instance in raycaster._depsgraph.object_instances:
        matrix = np.array([list(row) for row in instance.matrix_world], dtype=np.float64, copy=True)
        obj, parent = instance.object, instance.parent
        if obj.type != "MESH" or not instance.show_self:
            continue
        if original_pointer(obj) in excluded or (
            parent is not None and original_pointer(parent) in excluded
        ):
            continue
        mesh = obj.data
        if not len(mesh.polygons):
            continue
        name = str(obj.original.name)
        if not np.isfinite(matrix).all():
            raise ValueError("invalid allowed source instance matrix: " + name)
        mesh.calc_loop_triangles()
        coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", coordinates)
        edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
        mesh.edges.foreach_get("vertices", edges)
        loop_vertices = np.empty(len(mesh.loops), dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", loop_vertices)
        loop_start = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.polygons.foreach_get("loop_start", loop_start)
        loop_total = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.polygons.foreach_get("loop_total", loop_total)
        smooth = np.empty(len(mesh.polygons), dtype=np.bool_)
        mesh.polygons.foreach_get("use_smooth", smooth)
        sharp = np.empty(len(mesh.edges), dtype=np.bool_)
        mesh.edges.foreach_get("use_edge_sharp", sharp)
        triangles = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get("vertices", triangles)
        custom_normals = None
        if mesh.has_custom_normals:
            custom_normals = np.empty(len(mesh.corner_normals) * 3, dtype=np.float64)
            mesh.corner_normals.foreach_get("vector", custom_normals)
            if len(custom_normals) != len(mesh.loops) * 3:
                raise ValueError("source custom corner-normal count differs from loops")
        if not np.isfinite(coordinates).all():
            raise ValueError("non-finite source coordinates: " + name)
        geometry = {
            "coordinates": coordinates.reshape((-1, 3)),
            "edges": edges.reshape((-1, 2)),
            "loop_vertices": loop_vertices,
            "loop_start": loop_start,
            "loop_total": loop_total,
            "smooth": smooth,
            "sharp": sharp,
            "triangles": triangles.reshape((-1, 3)),
            "custom_normals": None if custom_normals is None else custom_normals.reshape((-1, 3)),
        }
        snapshots.append({"object_name": name, "matrix": matrix, "geometry": geometry})
        if len(snapshots) % 100 == 0:
            print("HR02 live-instance geometry captured", len(snapshots), name, flush=True)
    snapshots.sort(key=inventory_key)
    if [inventory_key(row) for row in snapshots] != sorted(
        inventory_key(row) for row in descriptors
    ):
        raise ValueError(
            "live allowed-instance name/matrix inventory differs from source raycaster"
        )
    fingerprint = hashlib.sha256()
    for snapshot in snapshots:
        fingerprint.update(snapshot["object_name"].encode("utf-8") + b"\0")
        fingerprint.update(snapshot["matrix"].tobytes())
        geometry = snapshot["geometry"]
        for key in (
            "coordinates",
            "edges",
            "loop_vertices",
            "loop_start",
            "loop_total",
            "smooth",
            "sharp",
            "triangles",
            "custom_normals",
        ):
            values = geometry[key]
            fingerprint.update(key.encode("ascii") + b"\0")
            fingerprint.update(b"NONE" if values is None else values.tobytes())
    return snapshots, fingerprint.hexdigest()


def main() -> None:
    renderer_path = Path(__file__).resolve()
    renderer_sha = digest(renderer_path)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT,
        help="New image/renderer-receipt directory; canonical audit inputs remain read-only",
    )
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
    out = args.output.absolute()
    if out.resolve() != out:
        raise ValueError("diagnostic output must use a non-symlink absolute directory")
    data = read_public("human_review/frames/hr02_camera_audit/audit_data.json")
    initial_manifest = read_public("human_review/frames/hr02_camera_audit/manifest.json")
    context = read_public("data/finalization/local_run/dataset/inference/office/context.json")
    template = read_public("human_review/review_template.json")
    read_public("configs/architectural_scale_school_v3.json")
    policy = read_public("configs/physical_authority_policy_school_v3.json")
    verify_data(data, context)
    if template["metadata"]["source_sha256"] != SOURCE_SHA or policy["authority"] != "APPROVED":
        raise ValueError("source/approved body policy mismatch")
    data_receipt = initial_manifest["data"]
    if data_receipt["path"] != "audit_data.json" or data_receipt["sha256"] != digest(
        OUT / "audit_data.json"
    ):
        raise ValueError("audit data differs from the source-query receipt")
    outputs = ["wide.png", "side.png", "renderer_manifest.json"] + [
        f"camera_{side}_frame{frame:03d}.png"
        for side in ("FRONT", "REAR")
        for frame in (20, 25, 45)
    ]
    if any((out / name).exists() for name in outputs):
        raise ValueError(
            "renderer preserves all existing artifacts; new audit outputs already exist"
        )
    out.mkdir(parents=True, exist_ok=True)
    before_inputs = {relative: digest(ROOT / relative) for relative in sorted(INPUTS)}
    bpy, mathutils, np = (importlib.import_module(name) for name in ("bpy", "mathutils", "numpy"))
    source = Path(bpy.data.filepath).resolve()
    before_source = source.stat()
    if digest(source) != SOURCE_SHA:
        raise ValueError("exact source school_v3.blend hash mismatch")
    scene = bpy.context.scene
    frozen_scene = data["source_scene"]
    if scene.name != frozen_scene["name"]:
        raise ValueError("source scene differs from source-query receipt")
    scene.frame_set(frozen_scene["frame"], subframe=frozen_scene["subframe"])
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT / "scripts"))
    export_helpers = importlib.import_module("export_blender_pilot")
    raycast_module = importlib.import_module("amidst.simulation.blender_visibility")
    camera_module = importlib.import_module("amidst.simulation.blender_camera")
    raycaster = raycast_module.BlenderMeshRaycaster(
        scene,
        excluded_objects=export_helpers.annotation_objects(bpy, scene),
        endpoint_tolerance_m=0.001,
    )
    if raycaster._uncertain:
        raise ValueError("source evaluated VIEWPORT geometry is uncertain")
    if len(raycaster._meshes) != data["diagnostic_protocol"]["raycast_mesh_instances"]:
        raise ValueError("renderer/source-query allowed physical mesh counts differ")
    # This must precede camera-data copies, new collections, and linked objects.
    # No evaluated object/mesh/matrix RNA reference escapes this read-only phase.
    source_snapshots, snapshot_sha = capture_source_geometry(raycaster, np, bpy.data.collections)
    if len(source_snapshots) != data["diagnostic_protocol"]["raycast_mesh_instances"]:
        raise ValueError("immutable snapshot dropped an allowed physical instance")
    del raycaster
    source_cameras = {}
    for row in data["cameras"]:
        native = bpy.data.objects.get(row["camera_id"])
        if native is None or native.type != "CAMERA":
            raise ValueError("source camera object is missing")
        source_cameras[row["camera_id"]] = {
            "object": native,
            "matrix": [list(matrix_row) for matrix_row in native.matrix_world],
            "camera_data": native.data.copy(),
        }
    native_objects = list(scene.objects)
    display = bpy.data.collections.new("HR02_CAMERA_AUDIT_UNSAVED_SOURCE_DERIVATIVE")
    scene.collection.children.link(display)
    full_objects: list[Any] = []
    cut_objects: list[Any] = []
    office_lo, office_hi = context["zone"]["bounds_min"], context["zone"]["bounds_max"]
    spans = [row["position_bu"] for row in data["cameras"]] + [
        [x, y, z]
        for x in (office_lo[0], office_hi[0])
        for y in (office_lo[1], office_hi[1])
        for z in (office_lo[2], office_hi[2])
    ]
    hit_points = [
        replay["hit"]["position_bu"]
        for frame in data["frames"]
        for camera in frame["cameras"]
        for replay in (camera["landmark_replay"], camera["foot_replay"])
        if replay.get("hit") is not None
    ]
    spans.extend(hit_points)
    crop_lo = np.min(np.asarray(spans), axis=0) - [100, 100, 25]
    crop_hi = np.max(np.asarray(spans), axis=0) + [100, 100, 25]
    cut_lid_z = 145.0
    retained_triangles, source_mesh_count = 0, 0
    source_triangles = 0
    for mesh_index, snapshot in enumerate(source_snapshots):
        geometry, transform = snapshot["geometry"], snapshot["matrix"]
        object_name = snapshot["object_name"]
        matrix = mathutils.Matrix(transform.tolist())
        mesh = bpy.data.meshes.new(f"FULL_ALLOWED_SOURCE_{mesh_index:05d}_MESH")
        faces = [
            geometry["loop_vertices"][start : start + total].tolist()
            for start, total in zip(geometry["loop_start"], geometry["loop_total"], strict=True)
        ]
        mesh.from_pydata(geometry["coordinates"].tolist(), geometry["edges"].tolist(), faces)
        mesh.polygons.foreach_set("use_smooth", geometry["smooth"])
        mesh.edges.foreach_set("use_edge_sharp", geometry["sharp"])
        if geometry["custom_normals"] is not None:
            mesh.normals_split_custom_set(geometry["custom_normals"].tolist())
        mesh.update()
        mesh.calc_loop_triangles()
        copied_triangles = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get("vertices", copied_triangles)
        if (
            len(mesh.vertices) != len(geometry["coordinates"])
            or len(mesh.edges) != len(geometry["edges"])
            or len(mesh.polygons) != len(geometry["loop_start"])
            or len(mesh.loops) != len(geometry["loop_vertices"])
            or not np.array_equal(copied_triangles.reshape((-1, 3)), geometry["triangles"])
        ):
            raise ValueError("owned derivative changed source topology: " + object_name)
        obj = bpy.data.objects.new(f"FULL_ALLOWED_SOURCE_{mesh_index:05d}_{object_name}", mesh)
        display.objects.link(obj)
        obj.matrix_world, obj.color = matrix, COLORS["source"]
        full_objects.append(obj)
        source_mesh_count += 1
        world = geometry["coordinates"] @ transform[:3, :3].T + transform[:3, 3]
        triangles = geometry["triangles"]
        source_triangles += len(triangles)
        points = world[triangles]
        intersects = np.all(points.max(axis=1) >= crop_lo, axis=1) & np.all(
            points.min(axis=1) <= crop_hi, axis=1
        )
        intersects &= np.all(points[:, :, 2] <= cut_lid_z, axis=1)
        selected = triangles[intersects]
        if len(selected):
            indices, inverse = np.unique(selected, return_inverse=True)
            cut_mesh = bpy.data.meshes.new(f"DISPLAY_CUTAWAY_{mesh_index:05d}_MESH")
            cut_mesh.from_pydata(world[indices].tolist(), [], inverse.reshape((-1, 3)).tolist())
            cut_mesh.update()
            cut_obj = bpy.data.objects.new(
                f"DISPLAY_CUTAWAY_{mesh_index:05d}_{object_name}", cut_mesh
            )
            display.objects.link(cut_obj)
            cut_obj.color = COLORS["source"]
            cut_objects.append(cut_obj)
            retained_triangles += len(selected)
        if mesh_index % 100 == 0:
            print("HR02 owned source construction", mesh_index, object_name, flush=True)
    # Keep native source cameras unmodified. Release only native geometry/light
    # objects after constructing the exact unsaved derivative to bound memory.
    del source_snapshots
    for obj in native_objects:
        if obj.type != "CAMERA":
            bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    gc.collect()
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = WIDTH, HEIGHT
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
    if scene.world is None:
        scene.world = bpy.data.worlds.new("HR02_DIAGNOSTIC_WORLD_UNSAVED")
    scene.world.color = (0.025, 0.034, 0.047)
    scene.view_settings.view_transform, scene.view_settings.look = "Standard", "None"
    scene.view_settings.exposure, scene.view_settings.gamma = 0, 1
    overlay: list[Any] = []
    labels: list[Any] = []

    def line(
        name: str,
        points: list[list[float]],
        color: tuple[float, ...],
        radius: float = 1.0,
        cyclic: bool = False,
    ) -> Any:
        curve = bpy.data.curves.new(name + "_CURVE", "CURVE")
        curve.dimensions, curve.resolution_u = "3D", 1
        curve.bevel_depth, curve.bevel_resolution = radius, 1
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for index, point in enumerate(points):
            spline.points[index].co = (*point, 1)
        spline.use_cyclic_u = cyclic
        obj = bpy.data.objects.new(name, curve)
        display.objects.link(obj)
        obj.color = color
        overlay.append(obj)
        return obj

    def sphere(name: str, point: list[float], radius: float, color: tuple[float, ...]) -> Any:
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=16, ring_count=8, radius=radius, location=point
        )
        obj = bpy.context.object
        obj.name, obj.color = name, color
        overlay.append(obj)
        return obj

    def cylinder(
        name: str,
        base: list[float],
        radius: float,
        height: float,
        color: tuple[float, ...],
    ) -> Any:
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=24,
            radius=radius,
            depth=height,
            location=[base[0], base[1], base[2] + height / 2],
        )
        obj = bpy.context.object
        obj.name, obj.color = name, color
        overlay.append(obj)
        return obj

    def clear_overlay() -> None:
        for obj in [*overlay, *labels]:
            bpy.data.objects.remove(obj, do_unlink=True)
        overlay.clear()
        labels.clear()

    def text(
        name: str,
        body: str,
        point: Any,
        camera: Any,
        size: float,
        color: tuple[float, ...] = COLORS["text"],
    ) -> Any:
        curve = bpy.data.curves.new(name + "_FONT", "FONT")
        curve.body, curve.size, curve.align_x = body, size, "LEFT"
        obj = bpy.data.objects.new(name, curve)
        display.objects.link(obj)
        obj.location, obj.rotation_euler, obj.color = point, camera.rotation_euler, color
        labels.append(obj)
        return obj

    def add_body(frame: dict[str, Any], wire: bool = False) -> None:
        scale, binding = 0.0247, data["binding"]
        base = frame["foot_position_bu"]
        height, radius = binding["body_height_m"] / scale, binding["body_radius_m"] / scale
        if not wire:
            cylinder("PENDING_HR02_BODY_NOT_OBSERVED_PIXELS", base, radius, height, COLORS["body"])
            sphere("PENDING_BODY_HEAD", [base[0], base[1], base[2] + height + 5], 5, COLORS["body"])
        for dz in (0, height):
            ring = [
                [
                    base[0] + radius * math.cos(angle * math.tau / 48),
                    base[1] + radius * math.sin(angle * math.tau / 48),
                    base[2] + dz,
                ]
                for angle in range(48)
            ]
            line("APPROVED_BODY_DIMENSIONS_PENDING_PLACEMENT", ring, COLORS["clearance"], 0.6, True)
        for angle in (0, math.pi / 2, math.pi, math.pi * 1.5):
            x = base[0] + radius * math.cos(angle)
            y = base[1] + radius * math.sin(angle)
            line(
                "PENDING_BODY_CYLINDER_VERTICAL",
                [[x, y, base[2]], [x, y, base[2] + height]],
                COLORS["body"],
                0.8,
            )
        outer = radius + binding["clearance_m"] / scale
        ring = [
            [
                base[0] + outer * math.cos(angle * math.tau / 48),
                base[1] + outer * math.sin(angle * math.tau / 48),
                base[2] + 0.2,
            ]
            for angle in range(48)
        ]
        line("BODY_CLEARANCE_DISPLAY_ONLY", ring, COLORS["clearance"], 0.5, True)
        sphere(
            "EXISTING_PUBLIC_OR_CANDIDATE_LANDMARK",
            frame["landmark_position_bu"],
            2.7,
            COLORS["landmark"],
        )
        line(
            "PENDING_VERTICAL_BINDING_OFFSET",
            [base, frame["landmark_position_bu"]],
            COLORS["landmark"],
            0.7,
        )

    def add_context(camera: Any, view: dict[str, Any]) -> list[list[float]]:
        """Static base only; the UI supplies the current-frame body/rays/hits."""
        floor = data["binding"]["floor_z_bu"]
        box = [
            [x, y, floor + 0.5]
            for x, y in (
                (office_lo[0], office_lo[1]),
                (office_hi[0], office_lo[1]),
                (office_hi[0], office_hi[1]),
                (office_lo[0], office_hi[1]),
            )
        ]
        line("OFFICE_ANNOTATION_OUTLINE_NOT_VISIBILITY", box, COLORS["office"], 2.0, True)
        for row in data["cameras"]:
            side = row["camera_id"].split("_")[-1]
            color = COLORS[side.lower()]
            origin, calibration = row["position_bu"], row["calibration"]
            sphere("EXACT_SOURCE_CAMERA_ORIGIN_" + side, origin, 10, color)
            matrix = calibration["camera_to_world"]
            axis = [-matrix[i][2] for i in range(3)]
            line(
                "CAMERA_DIRECTION_" + side,
                [origin, [origin[i] + 100 * axis[i] for i in range(3)]],
                color,
                2.0,
            )
            text(
                "SOURCE_CAMERA_LABEL_" + side,
                side + " / AUDITORIUM label",
                [origin[0] + 12, origin[1], origin[2] + 24],
                camera,
                view["ortho_scale_bu"] * 0.012,
                color,
            )
        return box

    def apply_view(view: dict[str, Any]) -> Any:
        camera_data = bpy.data.cameras.new("HR02_CUTAWAY_CONTEXT_CAMERA_DATA")
        camera_data.type, camera_data.clip_start, camera_data.clip_end = "ORTHO", 0.1, 20000
        camera_data.ortho_scale = view["ortho_scale_bu"]
        camera = bpy.data.objects.new("HR02_CUTAWAY_CONTEXT_CAMERA_UNSAVED", camera_data)
        display.objects.link(camera)
        right, up, forward = view["right"], view["up"], view["forward"]
        camera.matrix_world = mathutils.Matrix(
            [[right[i], up[i], -forward[i], view["position_bu"][i]] for i in range(3)]
            + [[0, 0, 0, 1]]
        )
        scene.camera = camera
        for obj in full_objects:
            obj.hide_render = True
        for obj in cut_objects:
            obj.hide_render = False
        return camera

    def caption(camera: Any, lines: list[str], view: dict[str, Any] | None = None) -> None:
        right, up, forward = (
            camera.matrix_world.to_3x3().col[0],
            camera.matrix_world.to_3x3().col[1],
            -camera.matrix_world.to_3x3().col[2],
        )
        if view is None:
            distance = 3.0
            horizontal = distance * 2 * math.tan(camera.data.angle_x / 2)
            vertical = horizontal * HEIGHT / WIDTH
        else:
            distance, horizontal = 30.0, view["ortho_scale_bu"]
            vertical = horizontal * HEIGHT / WIDTH
        center = camera.location + forward * distance
        for row, body in enumerate(lines):
            p = (
                center
                - right * horizontal * 0.48
                + up * (vertical * 0.465 - row * horizontal * 0.021)
            )
            text("HR02_DISPLAY_CAPTION", body, p, camera, horizontal * 0.015)

    def render(name: str, extra: dict[str, Any]) -> dict[str, Any]:
        path = out / name
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return {
            "path": name,
            "sha256": digest(path),
            "bytes": path.stat().st_size,
            "width": WIDTH,
            "height": HEIGHT,
            **extra,
        }

    midpoint = [
        (min(point[i] for point in spans) + max(point[i] for point in spans)) / 2 for i in range(3)
    ]
    wide_view = fit_view([midpoint[0] + 800, midpoint[1] - 900, 2100], midpoint, spans)
    camera = apply_view(wide_view)
    add_context(camera, wide_view)
    caption(
        camera,
        [
            "HR02 / BOTH ACTUAL SOURCE CAMERAS + OFFICE ANNOTATION / NO GT",
            "CUTAWAY DISPLAY ONLY: source above Z145 BU removed / STATIC CONTEXT BASE",
            "Yellow = OFFICE annotation; cyan/green = cameras / body/rays/hits update in UI",
        ],
        wide_view,
    )
    wide = render(
        "wide.png",
        {
            "view": wide_view,
            "geometry_scope": "DISPLAY_ONLY_CUTAWAY",
            "cutaway_lid_z_bu": cut_lid_z,
            "static_context_only": True,
            "baked_person_or_frame_rays": False,
        },
    )
    clear_overlay()
    # Side view retains both source camera origins plus the complete tested
    # vertical span; the numeric landmark offset is not a ceiling measurement.
    side_view = fit_view(
        [midpoint[0] + 1800, midpoint[1] - 700, midpoint[2] + 150], midpoint, spans
    )
    camera = apply_view(side_view)
    add_context(camera, side_view)
    caption(
        camera,
        [
            "HR02 / SOURCE CAMERA-SPACING + LANDMARK / FLOOR HEIGHT / NO GT",
            "CUTAWAY STATIC CONTEXT BASE / 1.359735 m is landmark-floor offset, NOT ceiling",
            "Floor Z20.078850 BU; landmark Z75.128848 BU / no ownership or visibility approval",
        ],
        side_view,
    )
    side = render(
        "side.png",
        {
            "view": side_view,
            "geometry_scope": "DISPLAY_ONLY_CUTAWAY",
            "cutaway_lid_z_bu": cut_lid_z,
            "static_context_only": True,
            "baked_person_or_frame_rays": False,
        },
    )
    clear_overlay()
    camera_stills = []
    for row in data["cameras"]:
        calibration, camera_id = row["calibration"], row["camera_id"]
        camera_data = source_cameras[camera_id]["camera_data"]
        camera = bpy.data.objects.new(
            "HR02_SOURCE_CALIBRATION_DERIVATIVE_" + camera_id, camera_data
        )
        display.objects.link(camera)
        camera.matrix_world = mathutils.Matrix(calibration["camera_to_world"])
        scene.camera = camera
        extracted = camera_module.extract_camera_dict(scene, camera)
        for key in ("fx", "fy", "cx", "cy"):
            if not math.isclose(extracted[key], calibration[key] * 2, rel_tol=1e-6, abs_tol=1e-3):
                raise ValueError("1920x1080 source-camera derivative changed frozen FOV")
        for obj in full_objects:
            obj.hide_render = False
        for obj in cut_objects:
            obj.hide_render = True
        side_name = camera_id.split("_")[-1]
        for frame_id in (20, 25, 45):
            frame = data["frames"][frame_id]
            item = next(item for item in frame["cameras"] if item["camera_id"] == camera_id)
            add_body(frame, wire=True)
            caption(
                camera,
                [
                    f"HR02 / {side_name} / frame {frame_id} / t={frame['timestamp']:.1f}s"
                    " / FULL SOURCE UNCUT",
                    "Grey = physical mesh; body/marker placement PENDING / NO GT / NO approval",
                ],
            )
            camera_stills.append(
                render(
                    f"camera_{side_name}_frame{frame_id:03d}.png",
                    {
                        "frame_id": frame_id,
                        "timestamp": frame["timestamp"],
                        "camera_id": camera_id,
                        "pixel_scale": 2,
                        "geometry_scope": "FULL_SOURCE_UNCUT_EVALUATED_VIEWPORT_ALLOWED_MESH",
                        "landmark_position_bu": frame["landmark_position_bu"],
                        "foot_position_bu": frame["foot_position_bu"],
                        "landmark_replay": item["landmark_replay"],
                        "foot_replay": item["foot_replay"],
                        "public_record": item["public_record"],
                        "source_calibration": calibration,
                        "scaled_intrinsics": {
                            key: extracted[key] for key in ("fx", "fy", "cx", "cy")
                        },
                        "body_placement_authority": "PENDING_HR02_DISPLAY_ONLY",
                        "rendered_pixel_visibility_certification": False,
                    },
                )
            )
            clear_overlay()
    for camera_id, row in source_cameras.items():
        if [list(matrix_row) for matrix_row in row["object"].matrix_world] != row["matrix"]:
            raise ValueError("native source-camera pose changed: " + camera_id)
    after_inputs = {relative: digest(ROOT / relative) for relative in sorted(INPUTS)}
    if before_inputs != after_inputs:
        raise ValueError("renderer changed existing source-query/review inputs")
    after_source = source.stat()
    if (before_source.st_size, before_source.st_mtime_ns) != (
        after_source.st_size,
        after_source.st_mtime_ns,
    ) or digest(source) != SOURCE_SHA:
        raise ValueError("original .blend changed during unsaved diagnostic rendering")
    receipt = {
        "schema_version": "phase1-hr02-source-camera-renderer-v1",
        "result_type": "DIAGNOSTIC_NOT_CERTIFIED",
        "source_sha256": SOURCE_SHA,
        "source_sha256_after": SOURCE_SHA,
        "source_saved": False,
        "source_modified": False,
        "native_source_camera_poses_changed": False,
        "gt_used": False,
        "evaluation_files_read": False,
        "simulation_recipe_read": False,
        "physical_authority_changed": False,
        "formal_execution_enabled": False,
        "input_hashes": [{"path": path, "sha256": value} for path, value in before_inputs.items()],
        "renderer_sha256": renderer_sha,
        "blender_version": bpy.app.version_string,
        "source_scene": frozen_scene,
        "source_mesh_instances": source_mesh_count,
        "source_full_triangles": source_triangles,
        "source_geometry_snapshot_sha256": snapshot_sha,
        "snapshot_policy": "OWNED_ARRAYS_CAPTURED_BEFORE_ANY_BLENDER_ID_MUTATION",
        "context_cutaway_triangles": retained_triangles,
        "render_policy": {
            "engine": "BLENDER_WORKBENCH",
            "width": WIDTH,
            "height": HEIGHT,
            "source_camera_pixel_scale": 2,
            "grey_geometry_not_cv_pixel_evidence": True,
            "source_camera_geometry": "FULL_ALLOWED_EVALUATED_VIEWPORT_WITHOUT_RENDER_MODIFIERS",
            "hide_render_or_materials_remove_blockers": False,
        },
        "wide": wide,
        "side": side,
        "camera_stills": camera_stills,
    }
    if digest(renderer_path) != renderer_sha:
        raise ValueError("renderer producer changed during diagnostic generation")
    with (out / "renderer_manifest.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print("HR02_CAMERA_AUDIT_RENDER_COMPLETE: " + str(out / "renderer_manifest.json"), flush=True)


if __name__ == "__main__":
    main()
