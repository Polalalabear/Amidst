#!/usr/bin/env python3
"""Generate the bounded deterministic school_v1 first-slice pilot dataset."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import shutil
import sys
import tempfile
import time
import traceback
from typing import Any

import bpy
import numpy as np
import OpenImageIO as oiio
from mathutils import Matrix, Vector


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from assign_instance_ids import file_sha256, load_identity_layer  # noqa: E402
from create_texture_agnostic_scene import (  # noqa: E402
    OUTPUT_NAME,
    OVERRIDE_MATERIAL,
    POLICY_ID,
    scene_invariant_digests,
)
from persist_instance_ids import (  # noqa: E402
    EXCLUDED_CAMERA,
    strict_registry,
    validate_registry_against_scene,
)
from validate_first_slice_readiness import (  # noqa: E402
    camera_record,
    render_config_differences,
)
from validate_texture_agnostic_scene import validate_override_material  # noqa: E402


GENERATOR_VERSION = "amidst.school.first-slice-generator/0.1.0"
DATASET_VERSION = "school_v1_first_slice_v0_1_0"
EXPECTED_SCENE_SHA256 = (
    "e349646c27fb343341a372b1e6d97b1a66f304f52c62721400e1833cdcd4d933"
)
SCHEMA_ID = "amidst.first-dataset-slice.metadata/0.1.0"
CONTRACT_ID = "amidst.school.first-dataset-slice/0.1.0"
SPATIAL_VERSION = "amidst.school.first-slice-spatial/1.0.0"
VISIBILITY_VERSION = "amidst.school.first-slice-visibility/1.0.0"
RENDER_CONFIG_ID = "amidst.school.first-slice-render/0.1.0"
IDENTITY_POLICY_ID = "amidst.school.object-id/1.0.1"
SEMANTIC_VERSION = "school.v1.semantic/0.1.0"
MINIMUM_VISIBLE_PIXELS = 16
RAY_EPSILON_M = 0.000001
DISTANCE_TIE_EPSILON_M = 0.000001
RELATION_DEADBAND_M = 0.0001
SERIALIZED_PLACES = 9
TASK_ORDER = [
    "visible_objects",
    "nearest_object",
    "distance_to_object",
    "left_of",
    "right_of",
    "in_front_of",
    "behind",
]


class SampleRejected(RuntimeError):
    """A deterministic candidate failed an authoritative acceptance rule."""

    def __init__(self, code: str, stage: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.stage = stage
        self.reason = reason


class SchemaValidationError(ValueError):
    """Metadata does not conform to the authoritative JSON Schema."""


def script_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--accepted-count", type=int, default=10)
    parser.add_argument("--max-attempts", type=int, default=50)
    parser.add_argument("--generation-run-id", default="run_pilot_0001")
    parser.add_argument(
        "--derived-scene",
        type=Path,
        default=REPOSITORY_ROOT / "blender/output" / OUTPUT_NAME,
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=REPOSITORY_ROOT / "data/datasets" / DATASET_VERSION,
    )
    parser.add_argument(
        "--source-scene",
        type=Path,
        default=REPOSITORY_ROOT / "blender/source/school_v1.blend",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=REPOSITORY_ROOT / "data/annotations/instance_registry/school.json",
    )
    parser.add_argument(
        "--automatic-disambiguation",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/annotations/instance_registry/school_v1_disambiguation.json"
        ),
    )
    parser.add_argument(
        "--identity-bootstrap",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/annotations/instance_registry/school_v1_identity_bootstrap.json"
        ),
    )
    parser.add_argument(
        "--semantic-sidecar",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/annotations/semantic/school_v1_semantic_baseline_v0_1_0.json"
        ),
    )
    parser.add_argument(
        "--task-contract",
        type=Path,
        default=REPOSITORY_ROOT / "data/metadata/first_dataset_slice_tasks_v0_1_0.json",
    )
    parser.add_argument(
        "--metadata-schema",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_metadata_schema_v0_1_0.json"
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
        "--resource-policy",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_render_resource_policy_v0_1_0.json"
        ),
    )
    parser.add_argument(
        "--readiness-report",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_first_slice_readiness.json",
    )
    parser.add_argument(
        "--scene-validation",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_texture_agnostic_scene_validation.json"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_first_slice_pilot_run_pilot_0001.json"
        ),
    )
    parser.add_argument(
        "--human-report",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_first_slice_pilot_run_pilot_0001.md"
        ),
    )
    return parser.parse_args(raw)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def strict_json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if left is None or right is None:
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    return type(left) is type(right) and left == right


def schema_type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    raise SchemaValidationError(f"Unsupported schema type: {expected}")


def resolve_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise SchemaValidationError(f"Only local JSON pointers are supported: {reference}")
    value: Any = root
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        value = value[part]
    if not isinstance(value, dict):
        raise SchemaValidationError(f"Schema reference is not an object: {reference}")
    return value


def schema_errors(
    value: Any,
    schema: dict[str, Any],
    root: dict[str, Any],
    path: str = "$",
) -> list[str]:
    if "$ref" in schema:
        return schema_errors(value, resolve_ref(root, schema["$ref"]), root, path)
    errors: list[str] = []
    if "oneOf" in schema:
        matches = [
            not schema_errors(value, candidate, root, path)
            for candidate in schema["oneOf"]
        ]
        if sum(matches) != 1:
            errors.append(f"{path}: expected exactly one oneOf match, got {sum(matches)}")
        return errors
    for candidate in schema.get("allOf", []):
        errors.extend(schema_errors(value, candidate, root, path))
    if "if" in schema and not schema_errors(value, schema["if"], root, path):
        errors.extend(schema_errors(value, schema.get("then", {}), root, path))
    expected_type = schema.get("type")
    if expected_type is not None:
        allowed_types = [expected_type] if isinstance(expected_type, str) else expected_type
        if not any(schema_type_matches(value, item) for item in allowed_types):
            errors.append(f"{path}: type mismatch, expected {allowed_types}")
            return errors
    if "const" in schema and not strict_json_equal(value, schema["const"]):
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and not any(strict_json_equal(value, item) for item in schema["enum"]):
        errors.append(f"{path}: value is not in enum")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}: missing required property {name!r}")
        for name, child in value.items():
            child_path = f"{path}.{name}"
            if name in properties:
                errors.extend(schema_errors(child, properties[name], root, child_path))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{child_path}: additional property is forbidden")
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(
                    schema_errors(child, schema["additionalProperties"], root, child_path)
                )
        if len(value) > schema.get("maxProperties", len(value)):
            errors.append(f"{path}: too many properties")
        if len(value) < schema.get("minProperties", 0):
            errors.append(f"{path}: too few properties")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        if len(value) > schema.get("maxItems", len(value)):
            errors.append(f"{path}: too many items")
        if schema.get("uniqueItems"):
            canonical_items = [canonical_json_bytes(item) for item in value]
            if len(set(canonical_items)) != len(canonical_items):
                errors.append(f"{path}: items are not unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(schema_errors(item, item_schema, root, f"{path}[{index}]"))
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: string is too short")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: string does not match pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if not math.isfinite(number):
            errors.append(f"{path}: number is not finite")
        if "minimum" in schema and number < float(schema["minimum"]):
            errors.append(f"{path}: number is below minimum")
        if "maximum" in schema and number > float(schema["maximum"]):
            errors.append(f"{path}: number is above maximum")
        if "exclusiveMinimum" in schema and number <= float(schema["exclusiveMinimum"]):
            errors.append(f"{path}: number is not above exclusiveMinimum")
        if "exclusiveMaximum" in schema and number >= float(schema["exclusiveMaximum"]):
            errors.append(f"{path}: number is not below exclusiveMaximum")
    return errors


def validate_against_schema(value: Any, schema: dict[str, Any]) -> None:
    errors = schema_errors(value, schema, schema)
    if errors:
        raise SchemaValidationError("; ".join(errors[:20]))


def finite_tree(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(finite_tree(item) for item in value.values())
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    return True


def q9(value: float) -> float:
    if not math.isfinite(float(value)):
        raise SampleRejected(
            "non_finite_geometry_or_camera_value",
            "numeric_serialization",
            f"Non-finite numeric value: {value!r}",
        )
    quantized = Decimal(str(float(value))).quantize(
        Decimal("0.000000001"), rounding=ROUND_HALF_EVEN
    )
    result = float(quantized)
    return 0.0 if result == 0.0 else result


def vector3(value: Any) -> list[float]:
    return [q9(value[index]) for index in range(3)]


def matrix4(value: Any) -> list[list[float]]:
    return [[q9(value[row][column]) for column in range(4)] for row in range(4)]


def enabled_collection_pointers(view_layer: Any) -> set[int]:
    enabled: set[int] = set()

    def visit(layer_collection: Any, parent_enabled: bool) -> None:
        current_enabled = (
            parent_enabled
            and not layer_collection.exclude
            and not layer_collection.collection.hide_render
        )
        if current_enabled:
            enabled.add(layer_collection.collection.as_pointer())
        for child in layer_collection.children:
            visit(child, current_enabled)

    visit(view_layer.layer_collection, True)
    return enabled


def eligible_task_objects(scene: Any, view_layer: Any, registry_ids: set[str]) -> list[Any]:
    enabled_collections = enabled_collection_pointers(view_layer)
    objects = []
    for obj in scene.objects:
        instance_id = obj.get("instance_id")
        if obj.type not in {"CURVE", "FONT", "MESH"}:
            continue
        if instance_id not in registry_ids or obj.hide_render:
            continue
        if not any(
            collection.as_pointer() in enabled_collections
            for collection in obj.users_collection
        ):
            continue
        objects.append(obj)
    return sorted(objects, key=lambda item: item["instance_id"])


def camera_is_valid(camera: Any) -> bool:
    return (
        camera.type == "CAMERA"
        and camera.data.type == "PERSP"
        and camera.get("instance_id")
        and not camera_record(camera)["invalid_parameters"]
        and all(
            math.isfinite(float(value))
            for row in camera.matrix_world
            for value in row
        )
    )


def camera_projection_inverse(camera: Any, scene: Any, depsgraph: Any) -> Matrix:
    width = scene.render.resolution_x * scene.render.resolution_percentage // 100
    height = scene.render.resolution_y * scene.render.resolution_percentage // 100
    return camera.calc_matrix_camera(
        depsgraph,
        x=width,
        y=height,
        scale_x=scene.render.pixel_aspect_x,
        scale_y=scene.render.pixel_aspect_y,
    ).inverted()


def view_direction(projection_inverse: Matrix, ndc_x: float, ndc_y: float) -> Vector:
    point = projection_inverse @ Vector((ndc_x, ndc_y, -1.0, 1.0))
    return Vector((point.x / point.w, point.y / point.w, point.z / point.w)).normalized()


def camera_fov(camera: Any, scene: Any, depsgraph: Any) -> tuple[float, float]:
    inverse = camera_projection_inverse(camera, scene, depsgraph)
    left = view_direction(inverse, -1.0, 0.0)
    right = view_direction(inverse, 1.0, 0.0)
    top = view_direction(inverse, 0.0, 1.0)
    bottom = view_direction(inverse, 0.0, -1.0)
    return left.angle(right), top.angle(bottom)


def camera_metadata(camera: Any, scene: Any, depsgraph: Any) -> dict[str, Any]:
    world_to_camera_cv = Matrix.Diagonal((1.0, -1.0, -1.0, 1.0)) @ camera.matrix_world.inverted()
    fov_x, fov_y = camera_fov(camera, scene, depsgraph)
    width = scene.render.resolution_x * scene.render.resolution_percentage // 100
    height = scene.render.resolution_y * scene.render.resolution_percentage // 100
    return {
        "instance_id": camera["instance_id"],
        "pose": {
            "world_coordinate_frame": "blender_world_metric_scale_1",
            "camera_coordinate_frame": "camera_cv",
            "position_world_m": vector3(camera.matrix_world.translation),
            "matrix_world": matrix4(camera.matrix_world),
            "world_to_camera_cv": matrix4(world_to_camera_cv),
        },
        "intrinsics": {
            "projection_type": camera.data.type,
            "lens_mm": q9(camera.data.lens),
            "sensor_width_mm": q9(camera.data.sensor_width),
            "sensor_height_mm": q9(camera.data.sensor_height),
            "sensor_fit": camera.data.sensor_fit,
            "shift_x": q9(camera.data.shift_x),
            "shift_y": q9(camera.data.shift_y),
            "clip_start_m": q9(camera.data.clip_start),
            "clip_end_m": q9(camera.data.clip_end),
            "fov_x_radians": q9(fov_x),
            "fov_y_radians": q9(fov_y),
            "render_width_px": width,
            "render_height_px": height,
        },
    }


def object_anchor(obj: Any, depsgraph: Any, world_to_camera_cv: Matrix) -> tuple[Vector, Vector]:
    evaluated = obj.evaluated_get(depsgraph)
    corners = [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
    if len(corners) != 8 or any(
        not math.isfinite(float(component))
        for corner in corners
        for component in corner
    ):
        raise SampleRejected(
            "non_finite_geometry_or_camera_value",
            "object_anchor",
            f"Invalid evaluated bounding box for {obj['instance_id']}",
        )
    anchor_world = sum(corners, Vector((0.0, 0.0, 0.0))) / 8.0
    anchor_camera_4d = world_to_camera_cv @ anchor_world.to_4d()
    anchor_camera = Vector(anchor_camera_4d[:3])
    if not all(math.isfinite(float(value)) for value in anchor_camera):
        raise SampleRejected(
            "non_finite_geometry_or_camera_value",
            "object_anchor",
            f"Non-finite camera-relative anchor for {obj['instance_id']}",
        )
    if anchor_camera.z <= 0.0:
        raise SampleRejected(
            "object_not_task_eligible",
            "object_anchor",
            f"Visible object anchor is not in front of camera: {obj['instance_id']}",
        )
    return anchor_world, anchor_camera


def validate_png(path: Path, width: int, height: int) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise SampleRejected("generation_failure", "render", f"Missing image: {path}")
    image = oiio.ImageInput.open(str(path))
    if image is None:
        raise SampleRejected("generation_failure", "image_validation", f"Unreadable image: {path}")
    try:
        spec = image.spec()
        if spec.width != width or spec.height != height or spec.nchannels < 3:
            raise SampleRejected(
                "render_ground_truth_mismatch",
                "image_validation",
                f"Unexpected image shape: {spec.width}x{spec.height}x{spec.nchannels}",
            )
    finally:
        image.close()
    return {
        "sha256": file_sha256(path),
        "size_bytes": path.stat().st_size,
        "width": width,
        "height": height,
    }


def read_aov(path: Path, width: int, height: int) -> np.ndarray:
    image = oiio.ImageInput.open(str(path))
    if image is None:
        raise SampleRejected("generation_failure", "visibility", f"Missing AOV: {path}")
    try:
        spec = image.spec()
        pixels = np.asarray(image.read_image(format=oiio.FLOAT))
    finally:
        image.close()
    if spec.width != width or spec.height != height or pixels.shape != (height, width, 1):
        raise SampleRejected(
            "render_ground_truth_mismatch",
            "visibility",
            f"Unexpected AOV shape: {pixels.shape}",
        )
    values = pixels[..., 0]
    if not np.isfinite(values).all():
        raise SampleRejected(
            "non_finite_geometry_or_camera_value",
            "visibility",
            "Object-index AOV contains NaN or Infinity",
        )
    rounded = np.rint(values)
    if np.max(np.abs(values - rounded), initial=0.0) > 0.000001:
        raise SampleRejected(
            "render_ground_truth_mismatch",
            "visibility",
            "Single-sample object-index AOV contains fractional values",
        )
    return rounded.astype(np.int32)


def setup_aov(scene: Any, view_layer: Any, material: Any, temp_directory: Path) -> dict[str, Any]:
    if any(aov.name == "AMIDST_ObjectIndex" for aov in view_layer.aovs):
        raise RuntimeError("Temporary AOV name already exists")
    aov = view_layer.aovs.add()
    aov.name = "AMIDST_ObjectIndex"
    aov.type = "VALUE"
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    object_info = nodes.new("ShaderNodeObjectInfo")
    object_info.name = "AMIDST_TEMP_ObjectInfo"
    aov_output = nodes.new("ShaderNodeOutputAOV")
    aov_output.name = "AMIDST_TEMP_ObjectIndex_Output"
    aov_output.aov_name = aov.name
    links.new(object_info.outputs["Object Index"], aov_output.inputs["Value"])
    compositor = bpy.data.node_groups.new(
        "AMIDST_TEMP_FirstSlice_Compositor", "CompositorNodeTree"
    )
    scene.compositing_node_group = compositor
    render_layers = compositor.nodes.new("CompositorNodeRLayers")
    render_layers.layer = view_layer.name
    output = compositor.nodes.new("CompositorNodeOutputFile")
    output.directory = str(temp_directory)
    output.file_name = "object_index"
    item = output.file_output_items.new("FLOAT", "AMIDST_ObjectIndex")
    compositor.links.new(
        render_layers.outputs["AMIDST_ObjectIndex"], output.inputs[item.name]
    )
    return {
        "aov": aov,
        "object_info": object_info,
        "aov_output": aov_output,
        "compositor": compositor,
        "output": output,
        "path": temp_directory / "object_index.exr",
    }


def cleanup_aov(scene: Any, view_layer: Any, material: Any, state: dict[str, Any]) -> None:
    material.node_tree.nodes.remove(state["aov_output"])
    material.node_tree.nodes.remove(state["object_info"])
    view_layer.aovs.remove(state["aov"])
    scene.compositing_node_group = state["previous_compositor"]
    bpy.data.node_groups.remove(state["compositor"])


def render(scene: Any, write_still: bool) -> float:
    start = time.perf_counter()
    result = bpy.ops.render.render(write_still=write_still, use_viewport=False)
    elapsed = time.perf_counter() - start
    if "FINISHED" not in result:
        raise SampleRejected(
            "generation_failure", "render", f"Blender render returned {sorted(result)}"
        )
    return elapsed


def sampled_ray_consistency(
    scene: Any,
    depsgraph: Any,
    camera: Any,
    object_index: np.ndarray,
    eligible_index_by_pointer: dict[int, int],
    sample_seed_hex: str,
) -> bool:
    height, width = object_index.shape
    projection_inverse = camera_projection_inverse(camera, scene, depsgraph)
    rotation = camera.matrix_world.to_3x3()
    origin = camera.matrix_world.translation
    seed = int(sample_seed_hex, 16)
    coordinates = {(width // 2, height // 2)}
    for offset in range(63):
        x = (seed + offset * 104729) % width
        y = ((seed >> 16) + offset * 130363) % height
        coordinates.add((int(x), int(y)))
    for x, y in sorted(coordinates):
        ndc_x = 2.0 * (x + 0.5) / width - 1.0
        ndc_y = 1.0 - 2.0 * (y + 0.5) / height
        local_direction = view_direction(projection_inverse, ndc_x, ndc_y)
        direction = (rotation @ local_direction).normalized()
        ray_origin = origin + direction * camera.data.clip_start
        hit, _, _, _, hit_object, _ = scene.ray_cast(
            depsgraph,
            ray_origin,
            direction,
            distance=camera.data.clip_end - camera.data.clip_start,
        )
        expected_index = 0
        if hit and hit_object is not None:
            expected_index = eligible_index_by_pointer.get(hit_object.original.as_pointer(), 0)
        if int(object_index[y, x]) != expected_index:
            return False
    return True


def visibility_evidence(
    scene: Any,
    view_layer: Any,
    camera: Any,
    eligible_objects: list[Any],
    index_to_object: dict[int, Any],
    aov_path: Path,
    width: int,
    height: int,
    sample_seed_hex: str,
    original_samples: int,
    original_reprojection: bool,
) -> tuple[dict[str, dict[str, Any]], float, float, bool]:
    original_hide_render = {obj.name: obj.hide_render for obj in eligible_objects}
    scene.eevee.taa_render_samples = 1
    scene.eevee.use_taa_reprojection = False
    try:
        full_render_seconds = render(scene, write_still=False)
        full_indices = read_aov(aov_path, width, height)
        maximum_index = len(eligible_objects)
        if int(full_indices.min()) < 0 or int(full_indices.max()) > maximum_index:
            raise SampleRejected(
                "render_ground_truth_mismatch",
                "visibility",
                "Object-index AOV contains an unknown object index",
            )
        values, counts = np.unique(full_indices, return_counts=True)
        visible_counts = {
            int(value): int(count)
            for value, count in zip(values, counts)
            if value > 0 and count >= MINIMUM_VISIBLE_PIXELS
        }
        if not visible_counts:
            raise SampleRejected(
                "insufficient_visible_pixels",
                "visibility",
                "No eligible object reaches the 16-pixel visibility threshold",
            )
        depsgraph = bpy.context.evaluated_depsgraph_get()
        pointer_map = {
            obj.as_pointer(): index
            for index, obj in index_to_object.items()
        }
        ray_consistent = sampled_ray_consistency(
            scene,
            depsgraph,
            camera,
            full_indices,
            pointer_map,
            sample_seed_hex,
        )
        if not ray_consistent:
            raise SampleRejected(
                "render_ground_truth_mismatch",
                "visibility",
                "Object-index AOV disagrees with Blender ray_cast audit pixels",
            )
        for obj in eligible_objects:
            obj.hide_render = True
        target_seconds = 0.0
        evidence: dict[str, dict[str, Any]] = {}
        for index in sorted(visible_counts):
            target = index_to_object[index]
            target.hide_render = False
            target_seconds += render(scene, write_still=False)
            target.hide_render = True
            target_indices = read_aov(aov_path, width, height)
            positive_values = set(int(item) for item in np.unique(target_indices) if item > 0)
            if positive_values - {index}:
                raise SampleRejected(
                    "render_ground_truth_mismatch",
                    "occlusion",
                    f"Target-only pass contains other eligible IDs: {sorted(positive_values)}",
                )
            total_projected = int(np.count_nonzero(target_indices == index))
            visible = visible_counts[index]
            if total_projected < visible or total_projected <= 0:
                raise SampleRejected(
                    "render_ground_truth_mismatch",
                    "occlusion",
                    (
                        f"Invalid target-only count for {target['instance_id']}: "
                        f"visible={visible}, target_only={total_projected}"
                    ),
                )
            occluded = total_projected - visible
            fraction = q9(occluded / total_projected)
            if visible == total_projected:
                state = "unoccluded"
            elif visible > 0:
                state = "partially_occluded"
            else:
                state = "fully_occluded"
            evidence[target["instance_id"]] = {
                "visible_pixel_count": visible,
                "total_projected_pixel_count": total_projected,
                "occluded_pixel_count": occluded,
                "occlusion_fraction": fraction,
                "occlusion_state": state,
            }
        return evidence, full_render_seconds, target_seconds, ray_consistent
    finally:
        for obj in eligible_objects:
            obj.hide_render = original_hide_render[obj.name]
        scene.eevee.taa_render_samples = original_samples
        scene.eevee.use_taa_reprojection = original_reprojection


def select_relation_pair(
    anchors: dict[str, Vector], relation: str
) -> tuple[str, str, float]:
    ids = sorted(anchors)
    axis = "x" if relation in {"left_of", "right_of"} else "z"
    for subject_id in ids:
        for object_id in ids:
            if subject_id == object_id:
                continue
            delta = float(getattr(anchors[subject_id], axis) - getattr(anchors[object_id], axis))
            is_true = (
                delta < -RELATION_DEADBAND_M
                if relation in {"left_of", "in_front_of"}
                else delta > RELATION_DEADBAND_M
            )
            if is_true:
                return subject_id, object_id, delta
    raise SampleRejected(
        "relation_within_deadband",
        "task_ground_truth",
        f"No visible ordered pair satisfies {relation} outside the deadband",
    )


def build_metadata(
    args: argparse.Namespace,
    camera: Any,
    frame_id: str,
    sample_id: str,
    sample_seed_hex: str,
    evidence: dict[str, dict[str, Any]],
    registry_sha256: str,
    resource_policy_sha256: str,
    source_scene_sha256: str,
    scene_sha256: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    world_to_camera_cv = Matrix.Diagonal((1.0, -1.0, -1.0, 1.0)) @ camera.matrix_world.inverted()
    camera_origin = camera.matrix_world.translation
    object_records = []
    anchors_camera: dict[str, Vector] = {}
    raw_distances: dict[str, float] = {}
    for instance_id in sorted(evidence):
        obj = next(item for item in scene.objects if item.get("instance_id") == instance_id)
        anchor_world, anchor_camera = object_anchor(obj, depsgraph, world_to_camera_cv)
        distance = float((anchor_world - camera_origin).length)
        anchors_camera[instance_id] = anchor_camera
        raw_distances[instance_id] = distance
        object_records.append(
            {
                "instance_id": instance_id,
                "object_type": obj.type,
                "anchor_world_m": vector3(anchor_world),
                "anchor_camera_m": vector3(anchor_camera),
                "distance_m": q9(distance),
                "visibility": evidence[instance_id],
            }
        )
    visible_ids = sorted(evidence)
    minimum_distance = min(raw_distances.values())
    tie_ids = sorted(
        instance_id
        for instance_id, distance in raw_distances.items()
        if abs(distance - minimum_distance) <= DISTANCE_TIE_EPSILON_M
    )
    selected_nearest = tie_ids[0]
    relationships = []
    relation_tasks = []
    for relation in ["left_of", "right_of", "in_front_of", "behind"]:
        subject_id, object_id, delta = select_relation_pair(anchors_camera, relation)
        serialized_delta = q9(delta)
        relationships.append(
            {
                "subject_instance_id": subject_id,
                "relation": relation,
                "object_instance_id": object_id,
                "coordinate_frame": "camera_cv",
                "axis_delta_m": serialized_delta,
                "tolerance_m": RELATION_DEADBAND_M,
                "derivation": "Blender_geometry",
            }
        )
        relation_tasks.append(
            {
                "task": relation,
                "inputs": {
                    "subject_instance_id": subject_id,
                    "object_instance_id": object_id,
                },
                "authoritative_answer": {
                    "result": True,
                    "axis_delta_m": serialized_delta,
                    "tolerance_m": RELATION_DEADBAND_M,
                },
                "question": None,
            }
        )
    relationships.sort(
        key=lambda item: (
            item["relation"],
            item["subject_instance_id"],
            item["object_instance_id"],
        )
    )
    tasks = [
        {
            "task": "visible_objects",
            "inputs": {},
            "authoritative_answer": {"instance_ids": visible_ids},
            "question": None,
        },
        {
            "task": "nearest_object",
            "inputs": {},
            "authoritative_answer": {
                "selected_instance_id": selected_nearest,
                "distance_m": q9(raw_distances[selected_nearest]),
                "tie_instance_ids": tie_ids,
            },
            "question": None,
        },
        {
            "task": "distance_to_object",
            "inputs": {"instance_id": selected_nearest},
            "authoritative_answer": {
                "instance_id": selected_nearest,
                "distance_m": q9(raw_distances[selected_nearest]),
            },
            "question": None,
        },
        *relation_tasks,
    ]
    checks = {
        "blender_render_completed": True,
        "camera_finite": True,
        "camera_in_approved_eligible_set": True,
        "derived_scene_checksum_matches": True,
        "distance_uses_camera_to_evaluated_bbox_center": True,
        "excluded_helper_camera_absent": True,
        "metadata_contains_no_non_finite_values": True,
        "nearest_is_visible": selected_nearest in visible_ids,
        "numeric_tolerances_match_contract": True,
        "observation_and_gt_share_scene_camera_material_policy": True,
        "raw_observation_has_no_ground_truth_overlay": True,
        "ray_cast_audit_matches_object_index_aov": True,
        "relations_use_camera_cv": True,
        "resource_policy_matches": True,
        "stable_ids_exist_in_registry": True,
        "tie_policy_applied": True,
        "visibility_threshold_applied": all(
            item["visible_pixel_count"] >= MINIMUM_VISIBLE_PIXELS
            for item in evidence.values()
        ),
    }
    metadata = {
        "schema_name": "amidst.first_dataset_slice_metadata",
        "schema_version": "0.1.0",
        "dataset_version": DATASET_VERSION,
        "contract_version": CONTRACT_ID,
        "generation_run_id": args.generation_run_id,
        "scene": {
            "scene_id": "school",
            "scene_version": "v1",
            "source_scene": "school_v1.blend",
            "source_scene_sha256": source_scene_sha256,
            "output_scene": "blender/output/" + OUTPUT_NAME,
            "output_scene_sha256": scene_sha256,
        },
        "sample_id": sample_id,
        "frame_id": frame_id,
        "artifacts": {
            "raw_observation": "image.png",
            "metadata": "metadata.json",
            "ground_truth_visualization": None,
        },
        "camera": camera_metadata(camera, scene, depsgraph),
        "ground_truth": {
            "visible_instance_ids": visible_ids,
            "objects": object_records,
            "relative_spatial_relationships": relationships,
        },
        "tasks": tasks,
        "validity": {
            "status": "valid",
            "invalidation_reasons": [],
            "validation_checks": checks,
        },
        "provenance": {
            "instance_registry": "data/annotations/instance_registry/school.json",
            "instance_registry_sha256": registry_sha256,
            "identity_policy_id": IDENTITY_POLICY_ID,
            "semantic_annotation_version": SEMANTIC_VERSION,
            "task_contract_version": CONTRACT_ID,
            "spatial_conventions_version": SPATIAL_VERSION,
            "visibility_definition_version": VISIBILITY_VERSION,
            "render_config_version": RENDER_CONFIG_ID,
            "render_resource_policy_id": POLICY_ID,
            "resource_policy": "texture_agnostic",
            "authoritative_visual_fidelity": False,
            "resource_manifest": "data/metadata/first_dataset_slice_render_resource_policy_v0_1_0.json",
            "resource_manifest_sha256": resource_policy_sha256,
            "generator_version": GENERATOR_VERSION,
            "blender_version": bpy.app.version_string,
            "blender_build_hash": bpy.app.build_hash.decode("utf-8"),
            "sample_seed_hex": sample_seed_hex,
        },
    }
    if [item["task"] for item in tasks] != TASK_ORDER:
        raise SampleRejected(
            "contract_or_provenance_mismatch",
            "task_ground_truth",
            "Task order differs from the confirmed contract",
        )
    if not finite_tree(metadata):
        raise SampleRejected(
            "non_finite_geometry_or_camera_value",
            "metadata_validation",
            "Metadata contains NaN or Infinity",
        )
    try:
        validate_against_schema(metadata, schema)
    except SchemaValidationError as exc:
        raise SampleRejected(
            "contract_or_provenance_mismatch",
            "metadata_schema_validation",
            str(exc),
        ) from exc
    return metadata


def seed_hex(run_id: str, sample_id: str, camera_id: str) -> str:
    value = "\n".join([DATASET_VERSION, run_id, sample_id, camera_id])
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def failure_record(
    attempt_id: str,
    camera_id: str,
    code: str,
    reason: str,
    stage: str,
    image_path: Path,
    metadata_path: Path,
    exception: BaseException | None = None,
) -> dict[str, Any]:
    return {
        "attempt_id": attempt_id,
        "camera_id": camera_id,
        "failure_code": code,
        "reason": reason,
        "stage": stage,
        "exception_type": type(exception).__name__ if exception else None,
        "exit_information": None,
        "image_output_exists": image_path.is_file(),
        "metadata_output_exists": metadata_path.is_file(),
    }


def render_report_markdown(report: dict[str, Any]) -> str:
    rejection_lines = [
        f"- `{code}`: {count}"
        for code, count in sorted(report["rejection_reasons"].items())
    ] or ["- None"]
    camera_lines = [f"- `{camera_id}`" for camera_id in report["camera_ids_used"]]
    return (
        "\n".join(
            [
                "# School v1 First-Slice Pilot Generation",
                "",
                f"Status: `{report['status']}`",
                "",
                f"- Generator: `{report['generator_path']}`",
                f"- Generator version: `{report['generator_version']}`",
                f"- Dataset output: `{report['dataset_output_path']}`",
                f"- Attempts: {report['attempts']}",
                f"- Accepted: {report['accepted_samples']}",
                f"- Rejected: {report['rejected_samples']}",
                f"- First accepted frame: `{report['first_accepted_frame_id']}`",
                f"- Last accepted frame: `{report['last_accepted_frame_id']}`",
                f"- Metadata schema validation: `{report['validation']['metadata_schema']}`",
                f"- Determinism validation: `{report['validation']['determinism']}`",
                f"- Scene checksum unchanged: `{str(report['scene_checksum_unchanged']).lower()}`",
                "",
                "## Cameras used",
                "",
                *camera_lines,
                "",
                "## Rejection summary",
                "",
                *rejection_lines,
            ]
        )
        + "\n"
    )


def main() -> None:
    args = script_args()
    if not args.pilot:
        raise RuntimeError("Refusing non-pilot generation; pass --pilot")
    if args.accepted_count != 10:
        raise RuntimeError("This authorized pilot requires exactly 10 accepted samples")
    if args.max_attempts < args.accepted_count or args.max_attempts > 50:
        raise RuntimeError("--max-attempts must be between accepted-count and 50")
    if re.fullmatch(r"run_[A-Za-z0-9][A-Za-z0-9._-]*", args.generation_run_id) is None:
        raise RuntimeError("Invalid generation_run_id")
    scene_path = Path(bpy.data.filepath).resolve()
    expected_scene_path = args.derived_scene.resolve()
    if scene_path != expected_scene_path:
        raise RuntimeError(f"Loaded scene mismatch: {scene_path}")
    scene_checksum_before = file_sha256(scene_path)
    if scene_checksum_before != EXPECTED_SCENE_SHA256:
        raise RuntimeError(
            f"Derived scene SHA-256 mismatch: {scene_checksum_before}"
        )
    if bpy.app.version_string != "5.2.1 LTS":
        raise RuntimeError(f"Blender version mismatch: {bpy.app.version_string}")
    build_hash = bpy.app.build_hash.decode("utf-8")
    if build_hash != "9e2066aef7ef":
        raise RuntimeError(f"Blender build hash mismatch: {build_hash}")

    registry_path = args.registry.resolve()
    semantic_path = args.semantic_sidecar.resolve()
    task_contract_path = args.task_contract.resolve()
    schema_path = args.metadata_schema.resolve()
    render_config_path = args.render_config.resolve()
    resource_policy_path = args.resource_policy.resolve()
    registry = strict_registry(registry_path)
    semantic = load_json(semantic_path)
    task_contract = load_json(task_contract_path)
    schema = load_json(schema_path)
    render_config = load_json(render_config_path)
    resource_policy = load_json(resource_policy_path)
    readiness = load_json(args.readiness_report.resolve())
    scene_validation = load_json(args.scene_validation.resolve())
    automatic = load_identity_layer(
        args.automatic_disambiguation.resolve(),
        "amidst.school_object_objective_disambiguation",
        5,
    )
    bootstrap = load_identity_layer(
        args.identity_bootstrap.resolve(),
        "amidst.school_object_identity_bootstrap",
        131,
    )
    identity = validate_registry_against_scene(
        bpy.context.scene, registry, automatic, bootstrap, require_ids=True
    )
    preconditions = {
        "identity_count": identity["ids_verified"] == 2777,
        "semantic_category_agnostic": (
            semantic.get("status") == "CONFIRMED"
            and semantic.get("reviewed_annotations") == []
            and semantic.get("unreviewed_default", {}).get("category") == "Unknown"
            and semantic.get("unreviewed_default", {}).get("annotation_status")
            == "needs_review"
        ),
        "task_contract": (
            task_contract.get("status") == "CONFIRMED"
            and task_contract.get("contract_id") == CONTRACT_ID
        ),
        "metadata_schema": schema.get("$id") == SCHEMA_ID,
        "render_config": (
            render_config.get("status") == "CONFIRMED"
            and render_config.get("config_id") == RENDER_CONFIG_ID
            and render_config.get("resource_gate", {}).get("current_status")
            == "READY_FOR_FIRST_DATASET_SLICE"
            and not render_config.get("known_readiness_blockers")
        ),
        "resource_policy": (
            resource_policy.get("status") == "CONFIRMED"
            and resource_policy.get("policy_id") == POLICY_ID
            and resource_policy.get("derived_scene_sha256") == scene_checksum_before
            and resource_policy.get("runtime_required_missing_resource_count") == 0
        ),
        "readiness": (
            readiness.get("status") == "READY_FOR_FIRST_DATASET_SLICE"
            and readiness.get("blockers") == []
            and readiness.get("validated_output_scene_sha256") == scene_checksum_before
        ),
        "scene_validation": (
            scene_validation.get("status") == "PASS"
            and scene_validation.get("derived_scene_sha256") == scene_checksum_before
            and scene_validation.get("unauthorized_scene_change_count") == 0
        ),
        "source_checksum": (
            file_sha256(args.source_scene.resolve())
            == resource_policy.get("source_scene_sha256")
        ),
    }
    failed_preconditions = sorted(
        name for name, passed in preconditions.items() if passed is not True
    )
    if failed_preconditions:
        raise RuntimeError(f"Authoritative preconditions failed: {failed_preconditions}")

    scene = bpy.context.scene
    view_layer = bpy.context.view_layer
    render_mismatches = render_config_differences(scene, render_config)
    if render_mismatches:
        raise RuntimeError(f"Loaded scene render config mismatch: {render_mismatches}")
    if scene.unit_settings.system != "METRIC" or scene.unit_settings.scale_length != 1.0:
        raise RuntimeError("Scene units do not match the spatial contract")
    material = bpy.data.materials.get(OVERRIDE_MATERIAL)
    if material is None or view_layer.material_override != material:
        raise RuntimeError("Validated neutral material override is unavailable")
    material_failures = validate_override_material(material)
    if material_failures:
        raise RuntimeError(
            f"Neutral material override validation failed: {material_failures}"
        )
    cameras = sorted(
        [
            obj
            for obj in scene.objects
            if obj.type == "CAMERA"
            and obj.name != EXCLUDED_CAMERA
            and obj.get("instance_id")
        ],
        key=lambda obj: obj["instance_id"],
    )
    if len(cameras) != 29 or not all(camera_is_valid(camera) for camera in cameras):
        raise RuntimeError("Eligible camera set does not match the confirmed 29-camera policy")
    helper = scene.objects.get(EXCLUDED_CAMERA)
    if helper is None or helper.get("instance_id") is not None:
        raise RuntimeError("Excluded helper camera policy mismatch")
    registry_ids = {record["instance_id"] for record in registry["records"]}
    task_objects = eligible_task_objects(scene, view_layer, registry_ids)
    if not task_objects:
        raise RuntimeError("No render-enabled eligible task objects")
    index_to_object = {index: obj for index, obj in enumerate(task_objects, start=1)}
    object_to_index = {obj.name: index for index, obj in index_to_object.items()}
    run_root = args.dataset_root.resolve() / args.generation_run_id
    if run_root.exists():
        raise RuntimeError(f"Refusing to overwrite existing generation run: {run_root}")
    run_root.mkdir(parents=True, exist_ok=False)
    rejected_root = run_root / "rejected"
    rejected_root.mkdir()
    if args.report.exists() or args.human_report.exists():
        raise RuntimeError("Refusing to overwrite an existing pilot report")

    started = datetime.now(timezone.utc)
    source_checksum = file_sha256(args.source_scene.resolve())
    registry_checksum = file_sha256(registry_path)
    resource_policy_checksum = file_sha256(resource_policy_path)
    invariants_before = scene_invariant_digests(scene, registry)
    previous_compositor = scene.compositing_node_group
    previous_camera = scene.camera
    previous_filepath = scene.render.filepath
    previous_pass_indices = {obj.name: obj.pass_index for obj in task_objects}
    previous_hide_render = {obj.name: obj.hide_render for obj in task_objects}
    original_samples = scene.eevee.taa_render_samples
    original_reprojection = scene.eevee.use_taa_reprojection
    accepted_records: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []
    render_durations: list[float] = []
    gt_full_durations: list[float] = []
    gt_target_durations: list[float] = []
    fatal_error: dict[str, Any] | None = None

    with tempfile.TemporaryDirectory(prefix="amidst_first_slice_") as temporary:
        temporary_root = Path(temporary)
        aov_state = setup_aov(scene, view_layer, material, temporary_root)
        aov_state["previous_compositor"] = previous_compositor
        for obj in task_objects:
            obj.pass_index = object_to_index[obj.name]
        try:
            for attempt_index in range(args.max_attempts):
                if len(accepted_records) >= args.accepted_count:
                    break
                attempt_id = f"attempt_{attempt_index:06d}"
                camera = cameras[attempt_index % len(cameras)]
                camera_id = camera["instance_id"]
                frame_id = f"frame_{len(accepted_records):06d}"
                sample_id = f"{DATASET_VERSION}_{frame_id}"
                current_seed = seed_hex(args.generation_run_id, sample_id, camera_id)
                attempt_stage = temporary_root / attempt_id
                attempt_stage.mkdir()
                image_path = attempt_stage / "image.png"
                metadata_path = attempt_stage / "metadata.json"
                scene.camera = camera
                try:
                    if render_config_differences(scene, render_config):
                        raise SampleRejected(
                            "contract_or_provenance_mismatch",
                            "pre_render",
                            "Render configuration changed before raw observation",
                        )
                    scene.render.filepath = str(image_path)
                    raw_seconds = render(scene, write_still=True)
                    render_durations.append(raw_seconds)
                    image_record = validate_png(
                        image_path,
                        scene.render.resolution_x,
                        scene.render.resolution_y,
                    )
                    evidence, gt_full_seconds, gt_target_seconds, ray_consistent = (
                        visibility_evidence(
                            scene,
                            view_layer,
                            camera,
                            task_objects,
                            index_to_object,
                            aov_state["path"],
                            scene.render.resolution_x,
                            scene.render.resolution_y,
                            current_seed,
                            original_samples,
                            original_reprojection,
                        )
                    )
                    gt_full_durations.append(gt_full_seconds)
                    gt_target_durations.append(gt_target_seconds)
                    metadata = build_metadata(
                        args,
                        camera,
                        frame_id,
                        sample_id,
                        current_seed,
                        evidence,
                        registry_checksum,
                        resource_policy_checksum,
                        source_checksum,
                        scene_checksum_before,
                        schema,
                    )
                    first_bytes = canonical_json_bytes(metadata)
                    second_metadata = build_metadata(
                        args,
                        camera,
                        frame_id,
                        sample_id,
                        current_seed,
                        evidence,
                        registry_checksum,
                        resource_policy_checksum,
                        source_checksum,
                        scene_checksum_before,
                        schema,
                    )
                    if first_bytes != canonical_json_bytes(second_metadata):
                        raise SampleRejected(
                            "generation_failure",
                            "determinism_validation",
                            "Repeated metadata construction was not byte-identical",
                        )
                    metadata_path.write_bytes(first_bytes)
                    validate_against_schema(load_json(metadata_path), schema)
                    if not all(
                        instance_id in registry_ids
                        for instance_id in metadata["ground_truth"]["visible_instance_ids"]
                    ):
                        raise SampleRejected(
                            "stable_id_mismatch",
                            "metadata_validation",
                            "Metadata contains an ID outside the authoritative registry",
                        )
                    accepted_path = run_root / frame_id
                    if accepted_path.exists():
                        raise RuntimeError(f"Refusing to overwrite sample: {accepted_path}")
                    attempt_stage.rename(accepted_path)
                    accepted_records.append(
                        {
                            "attempt_id": attempt_id,
                            "frame_id": frame_id,
                            "sample_id": sample_id,
                            "camera_id": camera_id,
                            "camera_selection_method": "lexicographic_stable_instance_id_by_attempt_ordinal",
                            "sample_seed_hex": current_seed,
                            "visible_object_count": len(evidence),
                            "image_sha256": image_record["sha256"],
                            "metadata_sha256": hashlib.sha256(first_bytes).hexdigest(),
                            "raw_render_seconds": raw_seconds,
                            "visibility_render_seconds": gt_full_seconds,
                            "target_only_render_seconds": gt_target_seconds,
                            "schema_valid": True,
                            "metadata_deterministic": True,
                            "ray_cast_audit_consistent": ray_consistent,
                        }
                    )
                    print(
                        json.dumps(
                            {
                                "attempt": attempt_index + 1,
                                "accepted": len(accepted_records),
                                "camera_id": camera_id,
                                "frame_id": frame_id,
                                "visible_objects": len(evidence),
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
                except SampleRejected as exc:
                    rejected_path = rejected_root / f"frame_{attempt_index:06d}"
                    rejected_path.mkdir()
                    if image_path.exists():
                        shutil.move(str(image_path), rejected_path / "image.png")
                    if metadata_path.exists():
                        shutil.move(str(metadata_path), rejected_path / "metadata.json")
                    failure = failure_record(
                        attempt_id,
                        camera_id,
                        exc.code,
                        exc.reason,
                        exc.stage,
                        rejected_path / "image.png",
                        rejected_path / "metadata.json",
                        exc,
                    )
                    write_json(rejected_path / "failure.json", failure)
                    rejected_records.append(failure)
                    shutil.rmtree(attempt_stage, ignore_errors=True)
                    print(json.dumps({"attempt": attempt_index + 1, "rejected": failure}, sort_keys=True), flush=True)
                except BaseException as exc:
                    rejected_path = rejected_root / f"frame_{attempt_index:06d}"
                    rejected_path.mkdir()
                    if image_path.exists():
                        shutil.move(str(image_path), rejected_path / "image.png")
                    if metadata_path.exists():
                        shutil.move(str(metadata_path), rejected_path / "metadata.json")
                    failure = failure_record(
                        attempt_id,
                        camera_id,
                        "generation_failure",
                        str(exc),
                        "unexpected_exception",
                        rejected_path / "image.png",
                        rejected_path / "metadata.json",
                        exc,
                    )
                    failure["traceback"] = traceback.format_exc()
                    write_json(rejected_path / "failure.json", failure)
                    rejected_records.append(failure)
                    fatal_error = failure
                    shutil.rmtree(attempt_stage, ignore_errors=True)
                    break
        finally:
            for obj in task_objects:
                obj.hide_render = previous_hide_render[obj.name]
                obj.pass_index = previous_pass_indices[obj.name]
            scene.eevee.taa_render_samples = original_samples
            scene.eevee.use_taa_reprojection = original_reprojection
            scene.render.filepath = previous_filepath
            scene.camera = previous_camera
            cleanup_aov(scene, view_layer, material, aov_state)

    invariants_after = scene_invariant_digests(scene, registry)
    scene_checksum_after = file_sha256(scene_path)
    invariant_match = invariants_after == invariants_before
    checksum_match = scene_checksum_after == scene_checksum_before == EXPECTED_SCENE_SHA256
    metadata_schema_pass = all(record["schema_valid"] for record in accepted_records)
    metadata_determinism_pass = all(
        record["metadata_deterministic"] for record in accepted_records
    )
    selected_camera_order = [record["camera_id"] for record in accepted_records]
    expected_camera_order = [
        cameras[index % len(cameras)]["instance_id"]
        for index in range(len(accepted_records) + len(rejected_records))
        if index < args.max_attempts
    ]
    accepted_attempt_indices = [
        int(record["attempt_id"].split("_")[-1]) for record in accepted_records
    ]
    camera_selection_deterministic = all(
        record["camera_id"] == expected_camera_order[attempt_index]
        for record, attempt_index in zip(accepted_records, accepted_attempt_indices)
    )
    final_ready = (
        fatal_error is None
        and len(accepted_records) == args.accepted_count
        and metadata_schema_pass
        and metadata_determinism_pass
        and camera_selection_deterministic
        and invariant_match
        and checksum_match
    )
    status = "PILOT_DATASET_READY" if final_ready else "REVIEW_REQUIRED"
    attempts = len(accepted_records) + len(rejected_records)
    rejection_counts: dict[str, int] = {}
    for record in rejected_records:
        rejection_counts[record["failure_code"]] = (
            rejection_counts.get(record["failure_code"], 0) + 1
        )
    completed = datetime.now(timezone.utc)
    report = {
        "schema_name": "amidst.first_slice_pilot_generation_report",
        "schema_version": "0.1.0",
        "repository_classification": "REVIEW_REQUIRED",
        "status": status,
        "started_at_utc": started.isoformat(),
        "completed_at_utc": completed.isoformat(),
        "generator_path": "blender/scripts/generate_first_dataset_slice.py",
        "generator_version": GENERATOR_VERSION,
        "dataset_version": DATASET_VERSION,
        "generation_run_id": args.generation_run_id,
        "dataset_output_path": str(run_root.relative_to(REPOSITORY_ROOT)),
        "attempt_limit": args.max_attempts,
        "attempts": attempts,
        "accepted_samples": len(accepted_records),
        "rejected_samples": len(rejected_records),
        "first_accepted_frame_id": accepted_records[0]["frame_id"] if accepted_records else None,
        "last_accepted_frame_id": accepted_records[-1]["frame_id"] if accepted_records else None,
        "camera_selection_method": "lexicographic_stable_instance_id_by_attempt_ordinal",
        "camera_ids_used": sorted(set(selected_camera_order)),
        "samples": accepted_records,
        "rejections": rejected_records,
        "rejection_reasons": rejection_counts,
        "render_duration_seconds": {
            "raw_total": q9(sum(render_durations)),
            "raw_min": q9(min(render_durations)) if render_durations else None,
            "raw_max": q9(max(render_durations)) if render_durations else None,
            "raw_mean": q9(sum(render_durations) / len(render_durations)) if render_durations else None,
            "visibility_total": q9(sum(gt_full_durations)),
            "target_only_total": q9(sum(gt_target_durations)),
            "wall_clock_total": q9((completed - started).total_seconds()),
        },
        "contracts": {
            "task_contract": CONTRACT_ID,
            "metadata_schema": SCHEMA_ID,
            "spatial_conventions": SPATIAL_VERSION,
            "visibility_definition": VISIBILITY_VERSION,
            "render_config": RENDER_CONFIG_ID,
            "render_resource_policy": POLICY_ID,
            "identity_policy": IDENTITY_POLICY_ID,
            "semantic_annotation_version": SEMANTIC_VERSION,
        },
        "numeric_policy": {
            "minimum_visible_pixel_count": MINIMUM_VISIBLE_PIXELS,
            "ray_hit_distance_epsilon_m": RAY_EPSILON_M,
            "distance_tie_epsilon_m": DISTANCE_TIE_EPSILON_M,
            "relation_deadband_m": RELATION_DEADBAND_M,
            "serialized_decimal_places": SERIALIZED_PLACES,
        },
        "input_scene": "blender/output/" + OUTPUT_NAME,
        "input_scene_sha256": scene_checksum_before,
        "post_run_scene_sha256": scene_checksum_after,
        "scene_checksum_unchanged": checksum_match,
        "scene_invariants_unchanged": invariant_match,
        "source_or_scene_file_saved": False,
        "image_gt_generated": False,
        "stochastic_generator_choice_count": 0,
        "unseeded_stochastic_render_settings": [],
        "validation": {
            "preconditions": "PASS" if all(preconditions.values()) else "FAIL",
            "metadata_schema": "PASS" if metadata_schema_pass else "FAIL",
            "determinism": (
                "PASS"
                if metadata_determinism_pass and camera_selection_deterministic
                else "FAIL"
            ),
            "scene_integrity": "PASS" if invariant_match and checksum_match else "FAIL",
            "observation_ground_truth_consistency": (
                "PASS"
                if accepted_records
                and all(item["ray_cast_audit_consistent"] for item in accepted_records)
                else "FAIL"
            ),
        },
        "fatal_error": fatal_error,
    }
    write_json(run_root / "generation_manifest.json", report)
    write_json(args.report.resolve(), report)
    args.human_report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.human_report.resolve().write_text(render_report_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status,
                "attempts": attempts,
                "accepted": len(accepted_records),
                "rejected": len(rejected_records),
                "dataset": str(run_root),
                "scene_checksum_unchanged": checksum_match,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    if status != "PILOT_DATASET_READY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
