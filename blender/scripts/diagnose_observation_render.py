#!/usr/bin/env python3
"""Render and audit one school_v1 observation without saving the Blender scene."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import time
import traceback
from typing import Any

import bpy
import numpy as np
import OpenImageIO as oiio
from mathutils import Matrix


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from assign_instance_ids import file_sha256  # noqa: E402
from create_texture_agnostic_scene import (  # noqa: E402
    OVERRIDE_MATERIAL,
    scene_invariant_digests,
)
from generate_first_dataset_slice import (  # noqa: E402
    cleanup_aov,
    eligible_task_objects,
    read_aov,
    render,
    setup_aov,
)
from persist_instance_ids import strict_registry  # noqa: E402
from validate_first_slice_readiness import render_config_differences  # noqa: E402


EXPECTED_SCENE_SHA256 = (
    "e349646c27fb343341a372b1e6d97b1a66f304f52c62721400e1833cdcd4d933"
)
CAMERA_INSTANCE_ID = (
    "amidst:school:object:0ab45975-7163-53b4-b83b-5773b35c2bfc"
)
DIAGNOSTIC_VERSION = "amidst.school.observation-render-diagnostic/0.1.0"
NEAR_BLACK_THRESHOLD = 0.02
USABLE_VISIBILITY_THRESHOLD = 0.10
MINIMUM_USABLE_PIXEL_FRACTION = 0.01
MINIMUM_P1_P99_RANGE = 0.05


def script_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scene",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "blender/output/school_v1_first_slice_texture_agnostic_v0_1_0.blend"
        ),
    )
    parser.add_argument(
        "--render-config",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_render_config_v0_1_0.json"
        ),
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=REPOSITORY_ROOT / "data/annotations/instance_registry/school.json",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/render_diagnostics"
            / "school_v1_camera_0ab45975_baseline_v0_1_0"
        ),
    )
    parser.add_argument(
        "--temporary-camera-sun-energy",
        type=float,
        default=0.0,
        help="Add one temporary camera-aligned Sun for a versioned fix candidate.",
    )
    parser.add_argument("--temporary-camera-sun-flipped", action="store_true")
    parser.add_argument(
        "--temporary-principled-weight",
        type=float,
        default=None,
        help="Temporarily correct the neutral Principled BSDF Weight for diagnosis.",
    )
    parser.add_argument("--temporary-diffuse-override", action="store_true")
    parser.add_argument("--repeat-render", action="store_true")
    return parser.parse_args(raw)


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def finite_or_none(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def node_input_value(node: Any, input_name: str) -> Any:
    socket = node.inputs.get(input_name)
    if socket is None:
        return None
    value = socket.default_value
    if hasattr(value, "__len__") and not isinstance(value, str):
        return [finite_or_none(item) for item in value]
    try:
        return finite_or_none(value)
    except (TypeError, ValueError):
        return str(value)


def world_record(scene: Any) -> dict[str, Any] | None:
    world = scene.world
    if world is None:
        return None
    nodes = []
    if world.use_nodes and world.node_tree is not None:
        for node in sorted(world.node_tree.nodes, key=lambda item: item.name):
            record: dict[str, Any] = {
                "name": node.name,
                "type": node.bl_idname,
                "mute": bool(node.mute),
            }
            if node.bl_idname == "ShaderNodeBackground":
                record["color"] = node_input_value(node, "Color")
                record["strength"] = node_input_value(node, "Strength")
            nodes.append(record)
    return {
        "name": world.name,
        "color": [finite_or_none(item) for item in world.color],
        "use_nodes": bool(world.use_nodes),
        "nodes": nodes,
    }


def light_records(scene: Any) -> list[dict[str, Any]]:
    records = []
    for obj in sorted(
        (item for item in scene.objects if item.type == "LIGHT"),
        key=lambda item: item.name,
    ):
        records.append(
            {
                "object_name": obj.name,
                "linked_to_scene": obj.name in scene.objects,
                "hide_render": bool(obj.hide_render),
                "data_name": obj.data.name,
                "light_type": obj.data.type,
                "energy": finite_or_none(obj.data.energy),
                "color": [finite_or_none(item) for item in obj.data.color],
                "matrix_world": [
                    [finite_or_none(value) for value in row] for row in obj.matrix_world
                ],
            }
        )
    return records


def viewport_records() -> list[dict[str, Any]]:
    records = []
    for screen in sorted(bpy.data.screens, key=lambda item: item.name):
        for index, area in enumerate(screen.areas):
            if area.type != "VIEW_3D":
                continue
            shading = area.spaces.active.shading
            records.append(
                {
                    "screen": screen.name,
                    "area_index": index,
                    "shading_type": shading.type,
                    "light": shading.light,
                    "studio_light": shading.studio_light,
                    "use_scene_lights": bool(shading.use_scene_lights),
                    "use_scene_world": bool(shading.use_scene_world),
                    "use_scene_lights_render": bool(shading.use_scene_lights_render),
                    "use_scene_world_render": bool(shading.use_scene_world_render),
                }
            )
    return records


def render_state(scene: Any, camera: Any, config: dict[str, Any]) -> dict[str, Any]:
    view_layer = bpy.context.view_layer
    view = scene.view_settings
    image_settings = scene.render.image_settings
    return {
        "active_scene": scene.name,
        "active_scene_filepath": bpy.data.filepath,
        "active_camera": {
            "object_name": camera.name,
            "instance_id": camera.get("instance_id"),
            "data_name": camera.data.name,
            "type": camera.data.type,
            "lens_mm": finite_or_none(camera.data.lens),
        },
        "active_view_layer": view_layer.name,
        "render_engine": scene.render.engine,
        "resolution": {
            "x": scene.render.resolution_x,
            "y": scene.render.resolution_y,
            "percentage": scene.render.resolution_percentage,
            "pixel_aspect_x": finite_or_none(scene.render.pixel_aspect_x),
            "pixel_aspect_y": finite_or_none(scene.render.pixel_aspect_y),
        },
        "world": world_record(scene),
        "scene_lights": light_records(scene),
        "render_enabled_light_count": sum(
            1 for item in light_records(scene) if not item["hide_render"]
        ),
        "color_management": {
            "display_device": scene.display_settings.display_device,
            "display_emulation": getattr(scene.display_settings, "display_emulation", None),
            "view_transform": getattr(view, "view_transform", None),
            "look": view.look,
            "exposure": finite_or_none(view.exposure),
            "gamma": finite_or_none(view.gamma),
            "use_curve_mapping": bool(view.use_curve_mapping),
            "use_white_balance": bool(view.use_white_balance),
        },
        "film_transparent": bool(scene.render.film_transparent),
        "material_override": (
            view_layer.material_override.name if view_layer.material_override else None
        ),
        "image_output": {
            "file_format": image_settings.file_format,
            "color_mode": image_settings.color_mode,
            "color_depth": image_settings.color_depth,
            "render_result_alpha_mode": bpy.data.images["Render Result"].alpha_mode,
        },
        "compositor": {
            "use_compositing": bool(scene.render.use_compositing),
            "node_group": (
                scene.compositing_node_group.name
                if scene.compositing_node_group is not None
                else None
            ),
        },
        "saved_viewports": viewport_records(),
        "authoritative_render_config": config.get("config_id"),
        "authoritative_config_differences": render_config_differences(scene, config),
    }


def read_rgb(path: Path) -> np.ndarray:
    image = oiio.ImageInput.open(str(path))
    if image is None:
        raise RuntimeError(f"Cannot read rendered image: {path}")
    try:
        pixels = np.asarray(image.read_image(format=oiio.FLOAT))
    finally:
        image.close()
    if pixels.ndim != 3 or pixels.shape[2] < 3:
        raise RuntimeError(f"Unexpected rendered image shape: {pixels.shape}")
    return pixels[..., :3]


def luminance_statistics(path: Path) -> dict[str, Any]:
    rgb = np.clip(read_rgb(path), 0.0, 1.0)
    luminance = (
        0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    )
    return {
        "measurement_space": "saved PNG normalized RGB with Rec.709 coefficients",
        "near_black_threshold": NEAR_BLACK_THRESHOLD,
        "usable_visibility_threshold": USABLE_VISIBILITY_THRESHOLD,
        "minimum_usable_pixel_fraction": MINIMUM_USABLE_PIXEL_FRACTION,
        "minimum_p1_p99_range": MINIMUM_P1_P99_RANGE,
        "mean_luminance": float(np.mean(luminance)),
        "median_luminance": float(np.median(luminance)),
        "percentile_1": float(np.percentile(luminance, 1)),
        "percentile_99": float(np.percentile(luminance, 99)),
        "fraction_below_near_black": float(
            np.mean(luminance < NEAR_BLACK_THRESHOLD)
        ),
        "fraction_above_usable_visibility": float(
            np.mean(luminance > USABLE_VISIBILITY_THRESHOLD)
        ),
    }


def pixel_digest(path: Path) -> str:
    pixels = read_rgb(path)
    return hashlib.sha256(pixels.tobytes(order="C")).hexdigest()


def temporary_camera_sun(
    scene: Any, camera: Any, energy: float, flipped: bool
) -> tuple[Any, Any]:
    if not math.isfinite(energy) or energy <= 0.0:
        raise RuntimeError("Temporary camera Sun energy must be finite and positive")
    data = bpy.data.lights.new("AMIDST_TEMP_DiagnosticCameraSun", type="SUN")
    data.energy = energy
    data.color = (1.0, 1.0, 1.0)
    data.angle = math.radians(10.0)
    obj = bpy.data.objects.new("AMIDST_TEMP_DiagnosticCameraSun", data)
    obj.matrix_world = camera.matrix_world.copy()
    if flipped:
        obj.matrix_world = obj.matrix_world @ Matrix.Rotation(math.pi, 4, "X")
    scene.collection.objects.link(obj)
    return obj, data


def neutral_principled(material: Any) -> Any:
    nodes = [
        node
        for node in material.node_tree.nodes
        if node.bl_idname == "ShaderNodeBsdfPrincipled"
    ]
    if len(nodes) != 1:
        raise RuntimeError(f"Expected one neutral Principled node, found {len(nodes)}")
    return nodes[0]


def socket_by_identifier(node: Any, identifier: str) -> Any:
    matches = [socket for socket in node.inputs if socket.identifier == identifier]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {node.name} input identifier {identifier!r}, found {len(matches)}"
        )
    return matches[0]


def temporary_diffuse_material() -> Any:
    material = bpy.data.materials.new("AMIDST_TEMP_DiagnosticDiffuse")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.inputs["Color"].default_value = (0.18, 0.18, 0.18, 1.0)
    diffuse.inputs["Roughness"].default_value = 0.8
    material.node_tree.links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])
    return material


def palette(index: int) -> tuple[int, int, int]:
    digest = hashlib.sha256(f"amidst-object-index:{index}".encode("utf-8")).digest()
    return tuple(48 + (value % 192) for value in digest[:3])


def write_aov_visualization(indices: np.ndarray, path: Path) -> None:
    maximum = int(indices.max(initial=0))
    table = np.zeros((maximum + 1, 3), dtype=np.uint8)
    for index in range(1, maximum + 1):
        table[index] = palette(index)
    pixels = table[indices]
    specification = oiio.ImageSpec(indices.shape[1], indices.shape[0], 3, oiio.UINT8)
    output = oiio.ImageOutput.create(str(path))
    if output is None or not output.open(str(path), specification):
        raise RuntimeError(f"Cannot open AOV visualization output: {path}")
    try:
        if not output.write_image(pixels):
            raise RuntimeError(f"Cannot write AOV visualization: {path}")
    finally:
        output.close()


def main() -> None:
    args = script_args()
    scene_path = args.scene.resolve()
    if Path(bpy.data.filepath).resolve() != scene_path:
        raise RuntimeError("Loaded scene does not match --scene")
    checksum_before = file_sha256(scene_path)
    if checksum_before != EXPECTED_SCENE_SHA256:
        raise RuntimeError(f"Derived scene SHA-256 mismatch: {checksum_before}")
    output_directory = args.output_directory.resolve()
    if output_directory.exists():
        raise RuntimeError(f"Refusing to overwrite diagnostic evidence: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=False)

    config = json.loads(args.render_config.resolve().read_text(encoding="utf-8"))
    registry = strict_registry(args.registry.resolve())
    registry_ids = {record["instance_id"] for record in registry["records"]}
    scene = bpy.context.scene
    view_layer = bpy.context.view_layer
    cameras = [
        obj
        for obj in scene.objects
        if obj.type == "CAMERA" and obj.get("instance_id") == CAMERA_INSTANCE_ID
    ]
    if len(cameras) != 1:
        raise RuntimeError(f"Expected one diagnostic camera, found {len(cameras)}")
    camera = cameras[0]
    original_material = bpy.data.materials.get(OVERRIDE_MATERIAL)
    if original_material is None or view_layer.material_override != original_material:
        raise RuntimeError("Confirmed neutral view-layer material override is unavailable")
    task_objects = eligible_task_objects(scene, view_layer, registry_ids)
    index_to_object = {index: obj for index, obj in enumerate(task_objects, start=1)}

    previous_camera = scene.camera
    previous_filepath = scene.render.filepath
    previous_compositor = scene.compositing_node_group
    previous_pass_indices = {obj.name: obj.pass_index for obj in task_objects}
    invariants_before = scene_invariant_digests(scene, registry)
    scene.camera = camera
    normal_path = output_directory / "normal_camera_render.png"
    repeat_path = output_directory / "normal_camera_render_repeat.png"
    aov_visualization_path = output_directory / "aov_id_diagnostic.png"
    state_path = output_directory / "render_state.json"
    luminance_path = output_directory / "luminance_statistics.json"
    report_path = output_directory / "comparison_report.md"

    started = datetime.now(timezone.utc)
    aov_state: dict[str, Any] | None = None
    normal_seconds = 0.0
    repeat_seconds = 0.0
    aov_seconds = 0.0
    temporary_light: tuple[Any, Any] | None = None
    temporary_material: Any | None = None
    material = original_material
    principled = neutral_principled(original_material)
    weight_socket = socket_by_identifier(principled, "Weight")
    original_principled_weight = float(weight_socket.default_value)
    try:
        with tempfile.TemporaryDirectory(prefix="amidst_render_diagnostic_") as temporary:
            if args.temporary_principled_weight is not None:
                if (
                    not math.isfinite(args.temporary_principled_weight)
                    or args.temporary_principled_weight < 0.0
                    or args.temporary_principled_weight > 1.0
                ):
                    raise RuntimeError("Temporary Principled Weight must be in [0, 1]")
                weight_socket.default_value = args.temporary_principled_weight
                original_material.node_tree.interface_update(bpy.context)
                original_material.update_tag()
            if args.temporary_diffuse_override:
                temporary_material = temporary_diffuse_material()
                view_layer.material_override = temporary_material
                material = temporary_material
            if args.temporary_camera_sun_energy > 0.0:
                temporary_light = temporary_camera_sun(
                    scene,
                    camera,
                    args.temporary_camera_sun_energy,
                    args.temporary_camera_sun_flipped,
                )
            view_layer.update()
            state = render_state(scene, camera, config)
            scene.render.filepath = str(normal_path)
            normal_seconds = render(scene, write_still=True)
            if args.repeat_render:
                scene.render.filepath = str(repeat_path)
                repeat_seconds = render(scene, write_still=True)
            aov_state = setup_aov(scene, view_layer, material, Path(temporary))
            aov_state["previous_compositor"] = previous_compositor
            for index, obj in index_to_object.items():
                obj.pass_index = index
            original_samples = scene.eevee.taa_render_samples
            original_reprojection = scene.eevee.use_taa_reprojection
            try:
                scene.eevee.taa_render_samples = 1
                scene.eevee.use_taa_reprojection = False
                aov_seconds = render(scene, write_still=False)
            finally:
                scene.eevee.taa_render_samples = original_samples
                scene.eevee.use_taa_reprojection = original_reprojection
            indices = read_aov(
                aov_state["path"],
                scene.render.resolution_x,
                scene.render.resolution_y,
            )
            write_aov_visualization(indices, aov_visualization_path)
    finally:
        if aov_state is not None:
            cleanup_aov(scene, view_layer, material, aov_state)
        for obj in task_objects:
            obj.pass_index = previous_pass_indices[obj.name]
        scene.camera = previous_camera
        scene.render.filepath = previous_filepath
        weight_socket.default_value = original_principled_weight
        if temporary_material is not None:
            view_layer.material_override = original_material
            bpy.data.materials.remove(temporary_material)
        if temporary_light is not None:
            light_object, light_data = temporary_light
            bpy.data.objects.remove(light_object, do_unlink=True)
            bpy.data.lights.remove(light_data)

    invariants_after = scene_invariant_digests(scene, registry)
    checksum_after = file_sha256(scene_path)
    stats = luminance_statistics(normal_path)
    objectively_near_black = stats["percentile_99"] < USABLE_VISIBILITY_THRESHOLD
    insufficient_usable_pixels = (
        stats["fraction_above_usable_visibility"] < MINIMUM_USABLE_PIXEL_FRACTION
    )
    insufficient_dynamic_range = (
        stats["percentile_99"] - stats["percentile_1"] < MINIMUM_P1_P99_RANGE
    )
    observation_invalid = (
        objectively_near_black
        or insufficient_usable_pixels
        or insufficient_dynamic_range
    )
    repeated_pixel_identical = None
    if args.repeat_render:
        repeated_pixel_identical = pixel_digest(normal_path) == pixel_digest(repeat_path)
    state.update(
        {
            "diagnostic_version": DIAGNOSTIC_VERSION,
            "started_at_utc": started.isoformat(),
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "normal_render_seconds": normal_seconds,
            "repeat_render_seconds": repeat_seconds if args.repeat_render else None,
            "aov_render_seconds": aov_seconds,
            "source_scene_sha256_before": checksum_before,
            "source_scene_sha256_after": checksum_after,
            "source_scene_checksum_unchanged": checksum_before == checksum_after,
            "scene_saved": False,
            "scene_invariants_unchanged_after_runtime_cleanup": (
                invariants_before == invariants_after
            ),
            "normal_render_sha256": file_sha256(normal_path),
            "normal_render_pixel_sha256": pixel_digest(normal_path),
            "repeat_render_sha256": (
                file_sha256(repeat_path) if args.repeat_render else None
            ),
            "repeat_render_pixel_sha256": (
                pixel_digest(repeat_path) if args.repeat_render else None
            ),
            "repeat_render_pixel_identical": repeated_pixel_identical,
            "aov_visualization_sha256": file_sha256(aov_visualization_path),
            "temporary_lighting_candidate": (
                {
                    "status": "PROPOSED",
                    "type": "SUN",
                    "alignment": "matrix_world copied from active camera at render time",
                    "flipped_180_degrees_about_camera_local_x": (
                        args.temporary_camera_sun_flipped
                    ),
                    "energy": args.temporary_camera_sun_energy,
                    "color_linear_rgb": [1.0, 1.0, 1.0],
                    "angle_degrees": 10.0,
                    "persisted_to_scene": False,
                }
                if args.temporary_camera_sun_energy > 0.0
                else None
            ),
            "temporary_material_fix_candidate": (
                {
                    "status": "CONFIRMED_CONTRACT_MISMATCH_FIX_CANDIDATE",
                    "material": material.name,
                    "node": principled.name,
                    "input": "Weight",
                    "before": original_principled_weight,
                    "during_render": args.temporary_principled_weight,
                    "after_cleanup": float(
                        weight_socket.default_value
                    ),
                    "persisted_to_scene": False,
                }
                if args.temporary_principled_weight is not None
                else None
            ),
            "temporary_diffuse_override_candidate": (
                {
                    "status": "PROPOSED",
                    "method": "temporary ViewLayer material_override",
                    "shader": "Diffuse BSDF",
                    "color_linear_rgba": [0.18, 0.18, 0.18, 1.0],
                    "roughness": 0.8,
                    "persisted_to_scene": False,
                }
                if args.temporary_diffuse_override
                else None
            ),
        }
    )
    luminance_record = {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "image": normal_path.name,
        "status": (
            "OBSERVATION_RENDER_INVALID" if observation_invalid else "PASS"
        ),
        "objectively_near_black": objectively_near_black,
        "insufficient_usable_pixel_fraction": insufficient_usable_pixels,
        "insufficient_dynamic_range": insufficient_dynamic_range,
        **stats,
    }
    state_path.write_bytes(canonical_json_bytes(state))
    luminance_path.write_bytes(canonical_json_bytes(luminance_record))
    report_lines = [
        "# School v1 Observation Render Diagnostic",
        "",
        f"Status: `{luminance_record['status']}`",
        "",
        f"- Camera: `{CAMERA_INSTANCE_ID}` (`{camera.name}`)",
        f"- Scene checksum unchanged: `{str(checksum_before == checksum_after).lower()}`",
        f"- Runtime scene invariants restored: `{str(invariants_before == invariants_after).lower()}`",
        f"- Render-config differences: `{state['authoritative_config_differences']}`",
        f"- Render-enabled scene lights: {state['render_enabled_light_count']}",
        f"- Mean luminance: {stats['mean_luminance']:.9f}",
        f"- Median luminance: {stats['median_luminance']:.9f}",
        f"- 1st percentile: {stats['percentile_1']:.9f}",
        f"- 99th percentile: {stats['percentile_99']:.9f}",
        f"- Fraction below {NEAR_BLACK_THRESHOLD}: {stats['fraction_below_near_black']:.9f}",
        f"- Fraction above {USABLE_VISIBILITY_THRESHOLD}: {stats['fraction_above_usable_visibility']:.9f}",
        f"- P1-P99 range: {stats['percentile_99'] - stats['percentile_1']:.9f}",
        f"- Repeat render pixel-identical: `{repeated_pixel_identical}`",
        "",
        "The normal image is an actual `bpy.ops.render.render()` EEVEE output. The AOV image",
        "is a separate false-colour visualization of deterministic object-index values and is",
        "not an observation image or authoritative semantic label.",
        "",
        "Saved viewport shading state is recorded in `render_state.json`; a viewport screenshot",
        "cannot be classified conclusively unless the exact viewport state or screenshot is provided.",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": luminance_record["status"], "output": str(output_directory)}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
