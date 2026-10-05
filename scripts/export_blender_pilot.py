"""Bounded PILOT / SYNTHETIC SAMPLE export in an unsaved Blender process.

Run Blender with school_v3.blend --python this_file -- --plan ... --output ... .
The combined dataset is simulation/evaluation only. observations.json contains
strict 2D evidence, with no truth, axial depths or hidden projected coordinates.
No benchmark, graph, ranking or reconstruction is called by this exporter.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import struct
import sys
import zlib
from itertools import pairwise
from pathlib import Path
from typing import Any

LABEL = "PILOT / SYNTHETIC SAMPLE"
ANNOTATIONS = (
    "Areas", "WALKABLE_AREAS", "OBSTACLE_AREAS", "STAIR_ANNOTATIONS",
    "Stair Reference Surfaces",
)
ANNOTATION_PREFIXES = ("AREA_", "PORTAL_", "WALK_", "OBSTACLE_", "STAIR_")


def fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest(), stat.st_size, stat.st_mtime_ns


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def label_png(path: Path, metadata: dict[str, str]) -> None:
    """Add explicit synthetic provenance without changing rendered PNG pixels.

    The original compressed IDAT chunks stay byte-identical. This is container
    metadata, with no resampling, image annotation or image-model processing.
    """
    content = path.read_bytes()
    if content[:8] != b"\x89PNG\r\n\x1a\n" or content[-12:-4] != b"\x00\x00\x00\x00IEND":
        raise ValueError("render output must be a complete PNG with a final IEND chunk")
    chunks = []
    for key, value in metadata.items():
        payload = key.encode("ascii") + b"\0" + value.encode("ascii")
        chunk = b"tEXt" + payload
        chunks.append(struct.pack(">I", len(payload)) + chunk
                      + struct.pack(">I", zlib.crc32(chunk)))
    path.write_bytes(content[:-12] + b"".join(chunks) + content[-12:])


def project(camera: dict[str, Any], position: list[float], matrix_type: Any) -> dict[str, Any]:
    vector_type = importlib.import_module("mathutils").Vector
    local = matrix_type(camera["camera_to_world"]).inverted() @ vector_type(position)
    depth = float(-local.z)
    pixel = None if depth <= 0 else [
        camera["fx"] * local.x / depth + camera["cx"],
        camera["cy"] - camera["fy"] * local.y / depth,
    ]
    if depth <= 0:
        reason = "BEHIND_CAMERA"
    elif depth < camera["clip_start"]:
        reason = "NEAR_CLIPPED"
    elif depth > camera["clip_end"]:
        reason = "FAR_CLIPPED"
    elif pixel is None or not (0 <= pixel[0] < camera["width"]
                              and 0 <= pixel[1] < camera["height"]):
        reason = "OUTSIDE_FOV"
    else:
        reason = "IN_FRUSTUM"
    return {"pixel": pixel, "axial_depth": depth, "reason": reason}


def configure_render(bpy: Any, width: int, height: int) -> dict[str, Any]:
    """Explicit pilot-only Workbench studio render, independent of missing textures."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1.0
    scene.render.use_border = scene.render.use_crop_to_border = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    scene.display.render_aa = "8"
    shading = scene.display.shading
    shading.light = "STUDIO"
    shading.studiolight_rotate_z = 0.0
    shading.color_type = "OBJECT"
    shading.show_shadows = True
    shading.show_cavity = True
    shading.cavity_type = "BOTH"
    shading.show_specular_highlight = False
    shading.show_xray = False
    shading.background_type = "WORLD"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("PILOT_WORLD")
    scene.world.color = (0.18, 0.18, 0.18)
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    for obj in scene.objects:
        if obj.type == "MESH":
            obj.color = (0.55, 0.55, 0.55, 1)
    # Freeze evaluated VIEWPORT triangles for rendering. Modifier flags alone
    # cannot make Geometry Nodes' Is Viewport or particle render paths agree.
    depsgraph = bpy.context.evaluated_depsgraph_get()
    excluded = []
    for collection_name in ANNOTATIONS:
        collection = bpy.data.collections.get(collection_name)
        if collection:
            for obj in collection.all_objects:
                obj.hide_render = True
                excluded.append(obj)
    excluded.extend(obj for obj in scene.objects if obj.type == "MESH"
                    and obj.name.startswith(ANNOTATION_PREFIXES))
    excluded_pointers = {obj.original.as_pointer() for obj in excluded}
    meshes, instances = {}, []
    for instance in depsgraph.object_instances:
        obj = instance.object
        parent = instance.parent
        if obj.type != "MESH" or not instance.show_self or not len(obj.data.polygons):
            continue
        if obj.original.as_pointer() in excluded_pointers or (
            parent is not None and parent.original.as_pointer() in excluded_pointers
        ):
            continue
        key = (obj.as_pointer(), obj.data.as_pointer())
        if key not in meshes:
            meshes[key] = bpy.data.meshes.new_from_object(
                obj, preserve_all_data_layers=False, depsgraph=depsgraph
            )
        instances.append((key, instance.matrix_world.copy(), obj.original.name))
    for collection in bpy.data.collections:
        collection.hide_render = False
    for obj in scene.objects:
        # Camera objects remain original. All other source renderables are
        # replaced by the static evaluated physical MESH snapshot below.
        obj.hide_render = obj.type != "CAMERA"
    render_collection = bpy.data.collections.new("PILOT_RENDER_MESH_SNAPSHOT")
    scene.collection.children.link(render_collection)
    for index, (key, matrix, source_name) in enumerate(instances):
        snapshot = bpy.data.objects.new(f"PILOT_RENDER_{index:04d}_{source_name}", meshes[key])
        render_collection.objects.link(snapshot)
        snapshot.matrix_world = matrix
        snapshot.color = (0.55, 0.55, 0.55, 1)
        snapshot.hide_viewport = True
        snapshot.hide_render = False
    return {
        "policy_id": "pilot_workbench_opaque_studio_v1",
        "engine": scene.render.engine,
        "width": width, "height": height,
        "color_type": "OBJECT", "lighting": "STUDIO", "antialias_samples": 8,
        "surface_policy": "OPAQUE_GRAY_PHYSICAL_MESH_ORANGE_SYNTHETIC_TARGET",
        "texture_policy": "NOT_USED_BY_WORKBENCH",
        "point_visibility_policy": "EVALUATED_VIEWPORT_FIXED_FRAME_POINT_RAYCAST",
        "geometry_frame": scene.frame_current,
        "geometry_subframe": scene.frame_subframe,
        "excluded_annotation_collections": list(ANNOTATIONS),
        "excluded_annotation_objects": sorted({obj.name for obj in excluded}),
        "source_scene_saved": False,
        "render_mesh_policy": "FROZEN_EVALUATED_VIEWPORT_MESH_INSTANCES_NO_RENDER_MODIFIERS",
        "render_mesh_instance_count": len(instances),
        "render_mesh_datablock_count": len(meshes),
        "non_mesh_source_renderables_excluded": True,
        "formal_render_policy": False,
        "png_label_policy": "SYNTHETIC_PROVENANCE_TEXT_CHUNKS_RENDERED_PIXELS_UNCHANGED",
    }


def make_target(bpy: Any, plan: dict[str, Any]) -> list[Any]:
    """A visible synthetic capsule marker; scale is scene units, not a human claim."""
    target = plan.get("target", {})
    height = float(target.get("height_scene_units", 110))
    radius = float(target.get("radius_scene_units", 8))
    probe = float(plan.get("probe_height_units", height / 2))
    actual_height = 2 * probe + 1.5 * radius
    if not math.isclose(height, actual_height, abs_tol=1e-6):
        raise ValueError("plan clearance envelope must include full cylinder/head render target")
    objects = []
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=radius, depth=2 * probe)
    body = bpy.context.object
    body.name = "PILOT_SYNTHETIC_TARGET_BODY"
    objects.append(body)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, radius=radius)
    head = bpy.context.object
    head.name = "PILOT_SYNTHETIC_TARGET_HEAD"
    objects.append(head)
    for obj in objects:
        obj.color = (1.0, 0.18, 0.015, 1)
    plan["render_target"] = {
        "height_scene_units": height, "radius_scene_units": radius,
        "probe_height_scene_units": probe,
        "body_center_above_foot": probe,
        "head_center_above_foot": 2 * probe + radius * 0.5,
        "kind": "SYNTHETIC_CAPSULE_MARKER_NOT_PHYSICALLY_CALIBRATED_PERSON",
    }
    return objects


def image_diagnostics(bpy: Any, path: Path, projected: list[float] | None) -> dict[str, Any]:
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        np = importlib.import_module("numpy")
        pixels = np.asarray(image.pixels[:], dtype=np.float32).reshape(
            image.size[1], image.size[0], 4
        )
        rgb = pixels[:, :, :3]
        luminance = rgb.mean(axis=2)
        # All physical meshes are grayscale. This mask is only a render QA diagnostic.
        orange = (rgb[:, :, 0] > rgb[:, :, 1] * 1.35) & (
            rgb[:, :, 0] > rgb[:, :, 2] * 1.8
        ) & (rgb[:, :, 0] > 0.15)
        nearby = None
        if projected and 0 <= projected[0] < image.size[0] and 0 <= projected[1] < image.size[1]:
            u, v = round(projected[0]), round(image.size[1] - projected[1])
            nearby = bool(orange[max(0, v-2):v+3, max(0, u-2):u+3].any())
        return {
            "width": image.size[0], "height": image.size[1],
            "luminance_mean": float(luminance.mean()),
            "luminance_std": float(luminance.std()),
            "luminance_p01": float(np.percentile(luminance, 1)),
            "luminance_p99": float(np.percentile(luminance, 99)),
            "orange_target_pixels": int(orange.sum()),
            "orange_near_projected_landmark": nearby,
            "interpretation": "POINT_VISIBILITY_AND_PARTIAL_BODY_VISIBILITY_ARE_DISTINCT",
        }
    finally:
        bpy.data.images.remove(image)


def main() -> None:
    bpy = importlib.import_module("bpy")
    mathutils = importlib.import_module("mathutils")
    native_project = importlib.import_module("bpy_extras.object_utils").world_to_camera_view
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from amidst.simulation.blender_camera import extract_camera_dict
    from amidst.simulation.blender_visibility import BlenderMeshRaycaster

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--limit", type=int, default=50, help="Only lower for diagnostic previews")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    plan = json.loads(args.plan.read_text())
    source = Path(bpy.data.filepath).resolve()
    before = fingerprint(source)
    if plan["source_asset_sha256"] != before[0]:
        raise ValueError("trajectory plan and current source hash differ")
    samples = plan["samples"]
    if len(samples) != 50 or not 1 <= args.limit <= 50 or not 2 <= len(plan["camera_ids"]) <= 3:
        raise ValueError("pilot is bounded at 50 timestamps and 2–3 source cameras")
    if not isinstance(plan.get("probe_height_units"), int | float):
        raise ValueError("source-bound landmark height must be explicit in the pilot plan")
    if args.width <= 0 or args.height <= 0 or args.output.resolve() == source.parent:
        raise ValueError("invalid render output configuration")
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "dataset.json").exists() or (args.output / "frames").exists():
        raise ValueError("pilot outputs already exist; use a fresh destination")
    scene = bpy.context.scene
    scene.frame_set(scene.frame_current)
    policy = configure_render(bpy, args.width, args.height)
    targets = make_target(bpy, plan)
    excluded = targets.copy()
    for collection_name in ANNOTATIONS:
        collection = bpy.data.collections.get(collection_name)
        if collection:
            excluded.extend(collection.all_objects)
    excluded.extend(obj for obj in scene.objects if obj.type == "MESH"
                    and obj.name.startswith(ANNOTATION_PREFIXES))
    raycaster = BlenderMeshRaycaster(scene, excluded_objects=excluded)
    camera_objects = [bpy.data.objects[name] for name in plan["camera_ids"]]
    cameras = [extract_camera_dict(scene, obj) for obj in camera_objects]
    for camera in cameras:
        (args.output / "frames" / camera["camera_id"]).mkdir(parents=True)
    frames, timestamps = [], []
    trajectory_id = plan.get("trajectory_id", "school_v3_pilot_trajectory_001")
    target_id = "pilot_synthetic_target_001"
    try:
        for index, sample in enumerate(samples[:args.limit]):
            foot = sample.get("foot_position", sample.get("position"))
            position = sample.get("probe_position") or [
                foot[0], foot[1], foot[2] + plan["probe_height_units"]
            ]
            target_meta = plan["render_target"]
            targets[0].location = [
                foot[0], foot[1], foot[2] + target_meta["body_center_above_foot"]
            ]
            targets[1].location = [
                foot[0], foot[1], foot[2] + target_meta["head_center_above_foot"]
            ]
            bpy.context.view_layer.update()
            raycaster.refresh()
            per_camera = []
            for camera, obj in zip(cameras, camera_objects, strict=True):
                projected = project(camera, position, mathutils.Matrix)
                reason, occluder = projected["reason"], None
                if reason == "IN_FRUSTUM":
                    matrix = camera["camera_to_world"]
                    ray = raycaster(tuple(matrix[i][3] for i in range(3)), tuple(position))
                    reason = ray.reason
                    occluder = ray.occluder_id
                visible = reason == "CLEAR"
                visibility = "visible" if visible else (
                    "occluded" if reason in {"OCCLUDED", "GEOMETRY_UNCERTAIN", "RAYCAST_LIMIT"}
                    else "out_of_FOV"
                )
                observation = {
                    "frame_id": index, "timestamp": sample["timestamp"],
                    "target_id": target_id, "camera_id": camera["camera_id"],
                    "status": "OBSERVED" if visible else "GAP",
                    "point_2d": projected["pixel"] if visible else None,
                    "provenance": "OBSERVED" if visible else None,
                    "gap_reason": None if visible else reason,
                    "occluder_id": occluder, "data_kind": "SYNTHETIC",
                }
                ndc = native_project(scene, obj, mathutils.Vector(position))
                native_pixel = None if ndc.z <= 0 else [
                    float(ndc.x * args.width), float((1-ndc.y) * args.height)
                ]
                relative = Path("frames") / camera["camera_id"] / f"frame_{index:03d}.png"
                path = args.output / relative
                scene.camera = obj
                scene.render.filepath = str(path.resolve())
                bpy.ops.render.render(write_still=True)
                label_png(path, {
                    "DatasetLabel": LABEL, "DataKind": "SYNTHETIC",
                    "SourceAssetSHA256": before[0],
                    "SimulationTimestampSeconds": str(sample["timestamp"]),
                    "TrajectoryID": trajectory_id,
                    "SiteID": plan.get("site_id", "corridor_reference"),
                    "VisibilityPolicy": policy["point_visibility_policy"],
                })
                qa = image_diagnostics(bpy, path, native_pixel)
                per_camera.append({
                    "camera_id": camera["camera_id"], "visibility": visibility,
                    "pixel": observation["point_2d"], "depth": projected["axial_depth"],
                    "reason": reason, "occluder_id": occluder,
                    "gap_state": observation["status"], "observation": observation,
                    "observation_provenance": {
                        "producer": "BLENDER_SIMULATION_POINT_RAYCAST",
                        "data_kind": "SYNTHETIC", "label": LABEL,
                        "source_asset_sha256": before[0],
                        "render_policy_id": policy["policy_id"],
                        "image_measurement": False,
                        "site_id": plan.get("site_id", "corridor_reference"),
                    },
                    "blender_projection": {
                        "pixel": native_pixel, "axial_depth": float(ndc.z),
                    },
                    "render": {"path": relative.as_posix(), "sha256": fingerprint(path)[0]},
                    "image_diagnostics": qa,
                })
                frames.append(observation)
            timestamps.append({
                "index": index, "timestamp": sample["timestamp"],
                "ground_truth": {
                    "position": list(position), "foot_position": list(foot),
                    "floor_id": sample.get("floor_id", plan.get("floor_id")),
                    "trajectory_id": trajectory_id, "provenance": "GROUND_TRUTH",
                    "landmark": "SYNTHETIC_TARGET_BODY_CENTER",
                },
                "per_camera": per_camera,
                "gap_state": "OBSERVED" if any(
                    row["visibility"] == "visible" for row in per_camera
                ) else "GAP",
            })
            print(f"PILOT_TIMESTAMP_OK {index + 1}/{args.limit}", flush=True)
    finally:
        after = fingerprint(source)
        if after != before:
            raise RuntimeError("pilot export changed source Blender asset")
    positions = [row["ground_truth"]["position"] for row in timestamps]
    length = sum(math.dist(a, b) for a, b in pairwise(positions))
    source_info = {
        "path": str(source), "sha256_before": before[0], "sha256_after": after[0],
        "size_before": before[1], "size_after": after[1],
        "mtime_ns_before": before[2], "mtime_ns_after": after[2],
    }
    dataset = {
        "schema_version": "blender-pilot-sample-v1", "label": LABEL,
        "data_kind": "SYNTHETIC", "purpose": "SIMULATION_EXPORT_EVALUATION_AND_HUMAN_REVIEW_ONLY",
        "site_id": plan.get("site_id", "corridor_reference"),
        "site_label": plan.get("site_label", "1F corridor reference"),
        "sample_role": plan.get("sample_role", "VISIBLE_GAP_VISIBLE"),
        "duration_seconds": 10, "sampling_fps": 5,
        "sampling_interval": "[0,10) seconds: 0.0 through 9.8, endpoint excluded",
        "requested_timestamps": 50, "successful_timestamps": len(timestamps),
        "source_scene": source_info, "cameras": cameras,
        "blender_version": bpy.app.version_string, "render_policy": policy,
        "trajectory": {
            "trajectory_id": trajectory_id, "target_id": target_id,
            "floor_id": plan.get("floor_id"), "length_scene_units": length,
            "configured_length_scene_units": plan["trajectory_length_scene_units"],
            "observation_plane_z": plan["observation_plane_z"],
            "projection_plane_basis": plan["projection_plane_basis"],
            "scale_authority": "UNVERIFIED", "meters_per_unit_contract": 1.0,
            "target": plan["render_target"], "plan_path": str(args.plan.resolve()),
        },
        "ground_truth_policy": {
            "allowed": ["simulation", "export", "evaluation", "debug_visualization"],
            "forbidden": ["projection_inference_input", "graph", "ranking", "reconstruction"],
            "sanitized_observations": "observations.json",
            "benchmark_executed": False, "elevator_transitions": [],
        },
        "timestamps": timestamps,
    }
    write_json(args.output / "dataset.json", dataset)
    write_json(args.output / "observations.json", {
        "data_kind": "SYNTHETIC", "label": LABEL,
        "source_asset_sha256": before[0], "frames": frames,
        "site_id": plan.get("site_id", "corridor_reference"),
    })
    write_json(args.output / "ground_truth.json", {
        "label": LABEL, "provenance": "GROUND_TRUTH", "source_asset_sha256": before[0],
        "trajectory_id": trajectory_id,
        "site_id": plan.get("site_id", "corridor_reference"),
        "samples": [{"timestamp": row["timestamp"], **row["ground_truth"]} for row in timestamps],
    })
    print(f"PILOT_EXPORT_OK {len(timestamps)} timestamps; source unchanged", flush=True)


if __name__ == "__main__":
    main()
