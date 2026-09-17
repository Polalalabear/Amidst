#!/usr/bin/env python3
"""Deterministically propose school object IDs without modifying Blender data.

This policy-v1 tool intentionally supports dry-run output only. It writes a
canonical sidecar registry and audit reports, but never writes custom
properties and never saves the open .blend file.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import unicodedata
import uuid
from typing import Any

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from asset_paths import logical_uri_for_path, root_path  # noqa: E402


POLICY_ID = "amidst.school.object-id/1.0.1"
POLICY_VERSION = "1.0.1"
BASE_FINGERPRINT_POLICY_ID = "amidst.school.object-id/1.0.0"
NAMESPACE_UUID = uuid.UUID("1601a7c1-19ac-555d-9962-05e4503ac6bd")
SOURCE_SHA256 = "cbfef8c84295253323890be5d9ffae186c46481f9dde8a6509ce897c49a34fa1"
SUPPORTED_TYPES = frozenset({"MESH", "ARMATURE", "CURVE", "EMPTY", "CAMERA", "FONT"})
AUTOMATIC_METHOD = "approved_objective_disambiguation"
BOOTSTRAP_METHOD = "human_reviewed_bootstrap"
BOOTSTRAP_RE = re.compile(r"^bootstrap:[0-9]{3}$")
INSTANCE_ID_RE = re.compile(
    r"^amidst:school:object:"
    r"[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class DeterminismError(RuntimeError):
    """An object cannot be represented by the approved deterministic policy."""


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def canonical_value(value: Any) -> Any:
    """Convert values to the exact policy-v1 canonical JSON value domain."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DeterminismError(f"Non-finite float is not canonical: {value!r}")
        return value.hex().lower()
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = normalize_text(str(raw_key))
            if key in result:
                raise DeterminismError(f"Duplicate key after Unicode normalization: {key!r}")
            result[key] = canonical_value(raw_value)
        return result
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    if hasattr(value, "to_list"):
        return canonical_value(value.to_list())
    try:
        return canonical_value(list(value))
    except TypeError as exc:
        raise DeterminismError(f"Unsupported canonical value: {type(value).__name__}") from exc


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_record(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_canonical(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def normalized_blender_path(value: str) -> str:
    return normalize_text(value.replace("\\", "/"))


class SignatureBuilder:
    def __init__(self, scene: Any, scene_id: str, scene_version: str, source_sha256: str):
        self.scene = scene
        self.scene_id = scene_id
        self.scene_version = scene_version
        self.source_sha256 = source_sha256
        self._file_hashes: dict[str, str] = {}
        self._image_signatures: dict[int, str] = {}
        self._node_tree_signatures: dict[int, str] = {}
        self._material_signatures: dict[int, str] = {}
        self._data_signatures: dict[tuple[str, int], str] = {}
        self._object_fingerprints: dict[int, tuple[str, dict[str, Any]]] = {}
        self._object_stack: set[int] = set()
        self.collection_paths = self._collection_paths()

    def _cached_file_hash(self, path: Path) -> str:
        key = str(path.resolve())
        if key not in self._file_hashes:
            self._file_hashes[key] = file_sha256(path)
        return self._file_hashes[key]

    def _collection_paths(self) -> dict[int, list[list[str]]]:
        paths: dict[int, list[list[str]]] = defaultdict(list)

        def walk(collection: Any, parent_path: list[str], ancestors: set[int]) -> None:
            pointer = collection.as_pointer()
            if pointer in ancestors:
                raise DeterminismError("Collection hierarchy cycle detected")
            current_path = parent_path + [normalize_text(collection.name)]
            paths[pointer].append(current_path)
            next_ancestors = ancestors | {pointer}
            children = sorted(
                collection.children,
                key=lambda item: normalize_text(item.name).encode("utf-8"),
            )
            for child in children:
                walk(child, current_path, next_ancestors)

        walk(self.scene.collection, [], set())
        for collection_paths in paths.values():
            collection_paths.sort(key=canonical_bytes)
        return dict(paths)

    def object_collection_paths(self, obj: Any) -> list[list[str]]:
        result: list[list[str]] = []
        for collection in obj.users_collection:
            result.extend(self.collection_paths.get(collection.as_pointer(), []))
        if not result:
            raise DeterminismError("Object has no collection path in the current scene")
        unique = {canonical_bytes(path): path for path in result}
        return [unique[key] for key in sorted(unique)]

    def image_signature(self, image: Any) -> str:
        pointer = image.as_pointer()
        if pointer in self._image_signatures:
            return self._image_signatures[pointer]

        packed_entries = []
        for packed in getattr(image, "packed_files", ()):
            packed_entries.append(
                {
                    "path": normalized_blender_path(getattr(packed, "filepath", "")),
                    "sha256": hashlib.sha256(bytes(packed.packed_file.data)).hexdigest(),
                }
            )
        if not packed_entries and getattr(image, "packed_file", None):
            packed = image.packed_file
            packed_entries.append(
                {
                    "path": normalized_blender_path(image.filepath),
                    "sha256": hashlib.sha256(bytes(packed.data)).hexdigest(),
                }
            )
        packed_entries.sort(key=canonical_bytes)

        raw_path = normalized_blender_path(image.filepath)
        resolved = Path(bpy.path.abspath(image.filepath)).resolve() if image.filepath else None
        external = None
        if resolved is not None:
            external = {
                "blender_path": raw_path,
                "exists": resolved.is_file(),
                "sha256": self._cached_file_hash(resolved) if resolved.is_file() else None,
            }

        record = {
            "source": image.source,
            "packed": packed_entries,
            "external": external,
            "generated": (
                {
                    "width": image.generated_width,
                    "height": image.generated_height,
                    "type": image.generated_type,
                    "color": list(image.generated_color),
                }
                if image.source == "GENERATED"
                else None
            ),
            "colorspace": getattr(image.colorspace_settings, "name", None),
            "alpha_mode": image.alpha_mode,
        }
        signature = digest_record(record)
        self._image_signatures[pointer] = signature
        return signature

    @staticmethod
    def _rna_scalar_properties(data_block: Any, excluded: set[str]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for prop in data_block.bl_rna.properties:
            identifier = prop.identifier
            if identifier in excluded or prop.type not in {"BOOLEAN", "INT", "FLOAT", "STRING", "ENUM"}:
                continue
            try:
                value = getattr(data_block, identifier)
                if getattr(prop, "is_array", False):
                    value = list(value)
                values[identifier] = value
            except (AttributeError, RuntimeError, TypeError):
                continue
        return values

    @staticmethod
    def _socket_record(socket: Any, index: int) -> dict[str, Any]:
        default = None
        if hasattr(socket, "default_value"):
            try:
                value = socket.default_value
                default = list(value) if hasattr(value, "__len__") and not isinstance(value, str) else value
            except (AttributeError, RuntimeError, TypeError):
                default = None
        return {
            "index": index,
            "identifier": getattr(socket, "identifier", ""),
            "socket_type": socket.bl_idname,
            "enabled": socket.enabled,
            "default": default,
        }

    def node_tree_signature(self, node_tree: Any, stack: set[int] | None = None) -> str:
        pointer = node_tree.as_pointer()
        if pointer in self._node_tree_signatures:
            return self._node_tree_signatures[pointer]
        stack = stack or set()
        if pointer in stack:
            raise DeterminismError("Recursive node-group cycle is unsupported by policy v1")
        stack = stack | {pointer}

        node_hashes: dict[int, str] = {}
        node_records: list[dict[str, Any]] = []
        excluded = {
            "rna_type", "name", "label", "location", "width", "width_hidden",
            "height", "dimensions", "select", "parent", "show_options",
            "show_preview", "show_texture", "color", "use_custom_color",
        }
        for node in node_tree.nodes:
            record = {
                "node_type": node.bl_idname,
                "properties": self._rna_scalar_properties(node, excluded),
                "inputs": [self._socket_record(socket, index) for index, socket in enumerate(node.inputs)],
                "outputs": [self._socket_record(socket, index) for index, socket in enumerate(node.outputs)],
                "image_signature": (
                    self.image_signature(node.image) if getattr(node, "image", None) else None
                ),
                "group_signature": (
                    self.node_tree_signature(node.node_tree, stack)
                    if getattr(node, "node_tree", None)
                    else None
                ),
            }
            node_hash = digest_record(record)
            node_hashes[node.as_pointer()] = node_hash
            node_records.append(record)

        links: list[dict[str, Any]] = []
        for link in node_tree.links:
            from_outputs = list(link.from_node.outputs)
            to_inputs = list(link.to_node.inputs)
            links.append(
                {
                    "from_node": node_hashes[link.from_node.as_pointer()],
                    "from_socket_index": from_outputs.index(link.from_socket),
                    "to_node": node_hashes[link.to_node.as_pointer()],
                    "to_socket_index": to_inputs.index(link.to_socket),
                    "is_muted": link.is_muted,
                }
            )

        node_records.sort(key=canonical_bytes)
        links.sort(key=canonical_bytes)
        signature = digest_record({"nodes": node_records, "links": links})
        self._node_tree_signatures[pointer] = signature
        return signature

    def material_signature(self, material: Any) -> str:
        pointer = material.as_pointer()
        if pointer in self._material_signatures:
            return self._material_signatures[pointer]
        record = {
            "diffuse_color": list(material.diffuse_color),
            "metallic": material.metallic,
            "roughness": material.roughness,
            "specular_ior_level": getattr(material, "specular_ior_level", None),
            "use_nodes": material.use_nodes,
            "surface_render_method": getattr(material, "surface_render_method", None),
            "node_tree_signature": (
                self.node_tree_signature(material.node_tree) if material.use_nodes and material.node_tree else None
            ),
        }
        signature = digest_record(record)
        self._material_signatures[pointer] = signature
        return signature

    @staticmethod
    def _matrix(matrix: Any) -> list[list[float]]:
        return [[float(value) for value in row] for row in matrix]

    def mesh_signature(self, mesh: Any) -> str:
        return digest_record(
            {
                "vertex_count": len(mesh.vertices),
                "edge_count": len(mesh.edges),
                "polygon_count": len(mesh.polygons),
                "vertices": [list(vertex.co) for vertex in mesh.vertices],
                "edges": [list(edge.vertices) for edge in mesh.edges],
                "polygons": [
                    {
                        "vertices": list(polygon.vertices),
                        "material_index": polygon.material_index,
                    }
                    for polygon in mesh.polygons
                ],
            }
        )

    def armature_signature(self, armature: Any) -> str:
        memo: dict[int, str] = {}
        stack: set[int] = set()

        def bone_fingerprint(bone: Any) -> str:
            pointer = bone.as_pointer()
            if pointer in memo:
                return memo[pointer]
            if pointer in stack:
                raise DeterminismError("Bone hierarchy cycle detected")
            stack.add(pointer)
            record = {
                "parent": bone_fingerprint(bone.parent) if bone.parent else None,
                "head_local": list(bone.head_local),
                "tail_local": list(bone.tail_local),
                "roll_orientation_matrix": self._matrix(bone.matrix_local),
                "use_connect": bone.use_connect,
                "use_deform": bone.use_deform,
                "inherit_scale": bone.inherit_scale,
            }
            result = digest_record(record)
            memo[pointer] = result
            stack.remove(pointer)
            return result

        bones = sorted((bone_fingerprint(bone) for bone in armature.bones))
        return digest_record({"bone_count": len(bones), "bone_signatures": bones})

    @staticmethod
    def _curve_common(curve: Any) -> dict[str, Any]:
        names = (
            "dimensions", "resolution_u", "render_resolution_u", "resolution_v",
            "render_resolution_v", "twist_smooth", "bevel_depth", "bevel_resolution",
            "extrude", "offset", "fill_mode", "resolution_u",
        )
        return {name: getattr(curve, name, None) for name in names}

    def curve_signature(self, curve: Any) -> str:
        splines = []
        for spline in curve.splines:
            spline_record: dict[str, Any] = {
                "type": spline.type,
                "use_cyclic_u": spline.use_cyclic_u,
                "use_cyclic_v": spline.use_cyclic_v,
                "resolution_u": spline.resolution_u,
                "resolution_v": spline.resolution_v,
                "order_u": spline.order_u,
                "order_v": spline.order_v,
                "use_endpoint_u": spline.use_endpoint_u,
                "use_endpoint_v": spline.use_endpoint_v,
            }
            if spline.type == "BEZIER":
                spline_record["bezier_points"] = [
                    {
                        "co": list(point.co),
                        "handle_left": list(point.handle_left),
                        "handle_right": list(point.handle_right),
                        "handle_left_type": point.handle_left_type,
                        "handle_right_type": point.handle_right_type,
                        "tilt": point.tilt,
                        "radius": point.radius,
                        "weight_softbody": point.weight_softbody,
                    }
                    for point in spline.bezier_points
                ]
            else:
                spline_record["points"] = [
                    {
                        "co": list(point.co),
                        "tilt": point.tilt,
                        "radius": point.radius,
                        "weight": point.weight,
                        "weight_softbody": point.weight_softbody,
                    }
                    for point in spline.points
                ]
            splines.append(spline_record)
        return digest_record({"settings": self._curve_common(curve), "splines": splines})

    def font_signature(self, font: Any) -> str:
        settings = self._curve_common(font)
        for name in (
            "align_x", "align_y", "size", "shear", "space_character",
            "space_word", "space_line", "offset_x", "follow_curve",
            "overflow", "small_caps_scale",
        ):
            value = getattr(font, name, None)
            if name == "follow_curve":
                value = None if value is None else digest_record({"type": value.type, "matrix": self._matrix(value.matrix_world)})
            settings[name] = value
        settings["text_boxes"] = [
            {"x": box.x, "y": box.y, "width": box.width, "height": box.height}
            for box in font.text_boxes
        ]
        return digest_record({"body": font.body, "settings": settings})

    def empty_signature(self, obj: Any) -> str:
        referenced = None
        if obj.data is not None:
            if isinstance(obj.data, bpy.types.Image):
                referenced = {"kind": "image", "signature": self.image_signature(obj.data)}
            else:
                raise DeterminismError(f"Unsupported EMPTY data type: {type(obj.data).__name__}")
        if obj.instance_collection is not None:
            raise DeterminismError("EMPTY collection instances are not supported by policy v1")
        return digest_record(
            {
                "display_type": obj.empty_display_type,
                "display_size": obj.empty_display_size,
                "image_depth": getattr(obj, "empty_image_depth", None),
                "image_side": getattr(obj, "empty_image_side", None),
                "color": list(obj.color),
                "instance_type": obj.instance_type,
                "referenced_data": referenced,
            }
        )

    def camera_signature(self, camera: Any) -> str:
        common_fields = (
            "type", "lens", "lens_unit", "sensor_fit", "sensor_width",
            "sensor_height", "shift_x", "shift_y", "clip_start", "clip_end",
        )
        record = {name: getattr(camera, name, None) for name in common_fields}
        if camera.type == "ORTHO":
            record["ortho_scale"] = camera.ortho_scale
        elif camera.type == "PANO":
            for name in (
                "panorama_type", "fisheye_fov", "fisheye_lens", "latitude_min",
                "latitude_max", "longitude_min", "longitude_max",
            ):
                record[name] = getattr(camera, name, None)
        return digest_record(record)

    def data_signature(self, obj: Any) -> str:
        if obj.type == "EMPTY":
            return self.empty_signature(obj)
        if obj.data is None:
            raise DeterminismError(f"{obj.type} object has no data block")
        cache_key = (obj.type, obj.data.as_pointer())
        if cache_key in self._data_signatures:
            return self._data_signatures[cache_key]
        if obj.type == "MESH":
            result = self.mesh_signature(obj.data)
        elif obj.type == "ARMATURE":
            result = self.armature_signature(obj.data)
        elif obj.type == "CURVE":
            result = self.curve_signature(obj.data)
        elif obj.type == "FONT":
            result = self.font_signature(obj.data)
        elif obj.type == "CAMERA":
            result = self.camera_signature(obj.data)
        else:
            raise DeterminismError(f"Unsupported object type: {obj.type}")
        self._data_signatures[cache_key] = result
        return result

    def object_fingerprint(self, obj: Any) -> tuple[str, dict[str, Any]]:
        pointer = obj.as_pointer()
        if pointer in self._object_fingerprints:
            return self._object_fingerprints[pointer]
        if pointer in self._object_stack:
            raise DeterminismError("Object parent hierarchy cycle detected")
        if obj.type not in SUPPORTED_TYPES:
            raise DeterminismError(f"Unsupported object type: {obj.type}")
        self._object_stack.add(pointer)
        try:
            if obj.parent is not None:
                if obj.parent.name not in self.scene.objects:
                    raise DeterminismError("Parent is not in the current scene")
                parent_fingerprint, _ = self.object_fingerprint(obj.parent)
            else:
                parent_fingerprint = None
            material_signatures = [
                self.material_signature(slot.material) if slot.material else None
                for slot in obj.material_slots
            ]
            identity_signals = {
                "policy_id": BASE_FINGERPRINT_POLICY_ID,
                "scene_id": self.scene_id,
                "first_seen_scene_version": self.scene_version,
                "first_seen_source_sha256": self.source_sha256,
                "object_type": obj.type,
                "collection_paths": self.object_collection_paths(obj),
                "parent_identity_fingerprint": parent_fingerprint,
                "data_signature": self.data_signature(obj),
                "matrix_world": self._matrix(obj.matrix_world),
                "dimensions": list(obj.dimensions),
                "material_signatures": material_signatures,
            }
            fingerprint = digest_record(identity_signals)
            result = (fingerprint, canonical_value(identity_signals))
            self._object_fingerprints[pointer] = result
            return result
        finally:
            self._object_stack.remove(pointer)


def custom_property_snapshot(scene: Any) -> str:
    rows = []
    for obj in sorted(scene.objects, key=lambda item: normalize_text(item.name).encode("utf-8")):
        properties = {}
        for key, value in obj.items():
            if key == "_RNA_UI":
                continue
            try:
                properties[str(key)] = canonical_value(value)
            except DeterminismError:
                properties[str(key)] = str(value)
        rows.append({"object_name": obj.name, "properties": properties})
    return digest_record(rows)


def scene_state_snapshot(scene: Any, builder: SignatureBuilder) -> str:
    rows = []
    for obj in sorted(scene.objects, key=lambda item: normalize_text(item.name).encode("utf-8")):
        rows.append(
            {
                "object_name": obj.name,
                "object_type": obj.type,
                "parent_name": obj.parent.name if obj.parent else None,
                "collections": sorted(normalize_text(collection.name) for collection in obj.users_collection),
                "matrix_world": builder._matrix(obj.matrix_world),
                "dimensions": list(obj.dimensions),
                "custom_properties": {str(key): str(value) for key, value in obj.items() if key != "_RNA_UI"},
            }
        )
    return digest_record(rows)


def valid_instance_id(value: Any) -> bool:
    if not isinstance(value, str) or not INSTANCE_ID_RE.fullmatch(value):
        return False
    try:
        return uuid.UUID(value.rsplit(":", 1)[1]).version == 5
    except ValueError:
        return False


def load_existing_registry(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("policy_id") not in {POLICY_ID, BASE_FINGERPRINT_POLICY_ID}:
        raise DeterminismError("Existing registry policy does not match")
    if data.get("namespace_uuid") != str(NAMESPACE_UUID):
        raise DeterminismError("Existing registry policy or namespace does not match")
    if data.get("source_sha256") != SOURCE_SHA256:
        raise DeterminismError("Existing registry source checksum does not match")
    return data


def load_identity_layer(path: Path, schema_name: str, record_count: int) -> dict[str, Any]:
    if not path.is_file():
        raise DeterminismError(f"Required identity layer is missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_name") != schema_name or data.get("schema_version") != "1.0.0":
        raise DeterminismError(f"Identity-layer schema mismatch: {path}")
    if data.get("status") != "CONFIRMED":
        raise DeterminismError(f"Identity layer is not confirmed: {path}")
    if data.get("effective_policy_id") != POLICY_ID:
        raise DeterminismError(f"Identity-layer effective policy mismatch: {path}")
    if data.get("base_fingerprint_policy_id") != BASE_FINGERPRINT_POLICY_ID:
        raise DeterminismError(f"Identity-layer base policy mismatch: {path}")
    if data.get("namespace_uuid") != str(NAMESPACE_UUID):
        raise DeterminismError(f"Identity-layer namespace mismatch: {path}")
    if data.get("source_sha256") != SOURCE_SHA256:
        raise DeterminismError(f"Identity-layer source checksum mismatch: {path}")
    if data.get("record_count") != record_count or len(data.get("records", [])) != record_count:
        raise DeterminismError(f"Identity-layer record count mismatch: {path}")
    return data


def layer_record_name(record: dict[str, Any]) -> str:
    locator = record.get("current_blender_object_locator", {})
    if locator.get("participates_in_fingerprint_or_uuid_input") is not False:
        raise DeterminismError("Identity-layer locator role is invalid")
    name = locator.get("blender_object_name")
    if not isinstance(name, str) or not name:
        raise DeterminismError("Identity-layer object locator is invalid")
    return normalize_text(name)


def index_layer_records(layer: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in layer["records"]:
        name = layer_record_name(record)
        if name in result:
            raise DeterminismError(f"Duplicate identity-layer locator: {name}")
        result[name] = record
    return result


def resolved_identity(
    base_fingerprint: str, method: str, token: str
) -> tuple[str, str]:
    resolved_fingerprint = digest_record(
        {
            "base_fingerprint": base_fingerprint,
            "disambiguation_method": method,
            "disambiguation_token": token,
        }
    )
    object_uuid = uuid.uuid5(
        NAMESPACE_UUID, f"{BASE_FINGERPRINT_POLICY_ID}:{resolved_fingerprint}"
    )
    return resolved_fingerprint, f"amidst:school:object:{object_uuid}"


def arguments() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    root = REPOSITORY_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--scene-id", default="school")
    parser.add_argument("--scene-version", default="v1")
    parser.add_argument(
        "--source-scene",
        type=Path,
        default=root_path("blender-source", "school_v1.blend", repo_root=root),
    )
    parser.add_argument("--expected-source-sha256", default=SOURCE_SHA256)
    parser.add_argument("--registry", type=Path, default=root / "data/annotations/instance_registry/school.json")
    parser.add_argument("--existing-registry", type=Path)
    parser.add_argument(
        "--automatic-disambiguation",
        type=Path,
        default=(root / "data/annotations/instance_registry/school_v1_disambiguation.json"),
    )
    parser.add_argument(
        "--identity-bootstrap",
        type=Path,
        default=(root / "data/annotations/instance_registry/school_v1_identity_bootstrap.json"),
    )
    parser.add_argument("--report", type=Path, default=root / "data/reports/school_v1_id_assignment.json")
    parser.add_argument("--collision-report", type=Path, default=root / "data/reports/school_v1_id_collisions.json")
    parser.add_argument("--human-report", type=Path, default=root / "data/reports/school_v1_id_assignment.md")
    return parser.parse_args(raw)


def human_report(report: dict[str, Any]) -> str:
    counts = report["counts"]
    checks = report["validation"]
    lines = [
        "# School v1 Stable-ID Dry-Run Report",
        "",
        f"Status: `{report['status']}`",
        "",
        "Repository classification: `REVIEW_REQUIRED`",
        "",
        "No Blender custom property was written and the scene was not saved.",
        "",
        "## Counts",
        "",
        "| Measure | Value |",
        "| --- | ---: |",
        f"| Total Blender objects | {counts['total_objects']} |",
        f"| Excluded objects | {counts['excluded_objects']} |",
        f"| Eligible objects | {counts['eligible_objects']} |",
        f"| Proposed IDs | {counts['proposed_ids']} |",
        f"| Normally assigned IDs | {counts['normally_assigned_ids']} |",
        f"| Automatically disambiguated IDs | {counts['automatically_disambiguated_ids']} |",
        f"| Human-bootstrap IDs | {counts['human_bootstrap_ids']} |",
        f"| Observed base duplicate groups | {counts['observed_base_duplicate_fingerprint_groups']} |",
        f"| Duplicate fingerprint blockers | {counts['duplicate_fingerprint_blockers']} |",
        f"| Duplicate proposed ID groups | {counts['duplicate_id_groups']} |",
        f"| Unresolved ambiguous objects | {counts['unresolved_ambiguous_objects']} |",
        f"| Assignment failures | {counts['assignment_failures']} |",
        f"| Manual-review objects | {counts['manual_review_objects']} |",
        f"| Unsupported objects | {counts['unsupported_objects']} |",
        f"| Registry rows | {counts['registry_rows']} |",
        "",
        "## Integrity",
        "",
        f"- Source SHA-256: `{report['source_sha256']}`",
        f"- Working SHA-256 before/after: `{report['working_sha256_before']}` / `{report['working_sha256_after']}`",
        f"- Working checksum unchanged: `{str(checks['working_checksum_unchanged']).lower()}`",
        f"- Custom properties unchanged in memory: `{str(checks['custom_properties_unchanged']).lower()}`",
        f"- Scene state unchanged in memory: `{str(checks['scene_state_unchanged']).lower()}`",
        "- Registry: `data/annotations/instance_registry/school.json`",
        "",
        "## Decision",
        "",
        (
            "All dry-run invariants passed. Persistent custom-property assignment may be reviewed as the next task."
            if report["status"] == "READY_FOR_PERSISTENT_ID_ASSIGNMENT"
            else "Blocking findings remain. Do not persist IDs; review the machine and collision reports."
        ),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = arguments()
    if not args.dry_run:
        raise RuntimeError("Policy v1 tool only supports --dry-run; persistent writing is prohibited")
    if not bpy.data.filepath:
        raise RuntimeError("No saved Blender working scene is open")

    working_path = Path(bpy.data.filepath).resolve()
    source_path = args.source_scene.resolve()
    if source_path == working_path or source_path.parent == working_path.parent:
        raise RuntimeError("Dry run must load a working scene, not the immutable source scene")
    working_root = root_path("blender-working", repo_root=REPOSITORY_ROOT)
    if working_path != working_root and working_root not in working_path.parents:
        raise RuntimeError("Loaded scene is outside the configured working root")
    source_hash = file_sha256(source_path)
    if source_hash != args.expected_source_sha256 or source_hash != SOURCE_SHA256:
        raise RuntimeError(f"Immutable source checksum mismatch: {source_hash}")
    working_hash_before = file_sha256(working_path)
    if working_hash_before != source_hash:
        raise RuntimeError("Initial working scene is not byte-identical to the immutable source")

    scene = bpy.context.scene
    builder = SignatureBuilder(scene, args.scene_id, args.scene_version, source_hash)
    custom_before = custom_property_snapshot(scene)
    state_before = scene_state_snapshot(scene, builder)
    dirty_before = bpy.data.is_dirty

    automatic_layer = load_identity_layer(
        args.automatic_disambiguation,
        "amidst.school_object_objective_disambiguation",
        5,
    )
    bootstrap_layer = load_identity_layer(
        args.identity_bootstrap,
        "amidst.school_object_identity_bootstrap",
        131,
    )
    automatic_by_name = index_layer_records(automatic_layer)
    bootstrap_by_name = index_layer_records(bootstrap_layer)
    if set(automatic_by_name) & set(bootstrap_by_name):
        raise DeterminismError("Automatic and bootstrap identity layers overlap")

    exclusion_records = bootstrap_layer.get("eligibility_exclusions", [])
    if len(exclusion_records) != 1:
        raise DeterminismError("Expected exactly one confirmed eligibility exclusion")
    excluded_names: set[str] = set()
    excluded_objects: list[dict[str, Any]] = []
    for exclusion in exclusion_records:
        if exclusion.get("reviewer_status") != "CONFIRMED":
            raise DeterminismError("Eligibility exclusion is not confirmed")
        name = layer_record_name(exclusion)
        obj = scene.objects.get(name)
        if obj is None or obj.type != exclusion.get("object_type"):
            raise DeterminismError(f"Eligibility exclusion target mismatch: {name}")
        excluded_names.add(name)
        excluded_objects.append(
            {
                "object_name": name,
                "object_type": obj.type,
                "reason": exclusion["reason"],
                "policy_version": exclusion["policy_version"],
            }
        )

    unsupported = sorted(
        (
            {"object_name": obj.name, "object_type": obj.type}
            for obj in scene.objects
            if obj.name not in excluded_names and obj.type not in SUPPORTED_TYPES
        ),
        key=lambda item: (item["object_type"], normalize_text(item["object_name"])),
    )
    eligible = [
        obj
        for obj in scene.objects
        if obj.name not in excluded_names and obj.type in SUPPORTED_TYPES
    ]
    failures: list[dict[str, str]] = []
    assignments: list[dict[str, Any]] = []
    by_fingerprint: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for obj in eligible:
        try:
            fingerprint, signals = builder.object_fingerprint(obj)
            object_uuid = uuid.uuid5(
                NAMESPACE_UUID, f"{BASE_FINGERPRINT_POLICY_ID}:{fingerprint}"
            )
            proposed_id = f"amidst:school:object:{object_uuid}"
            row = {
                "object_name": obj.name,
                "object_type": obj.type,
                "canonical_fingerprint": fingerprint,
                "generated_instance_id": proposed_id,
                "identity_signals": signals,
                "existing_blender_instance_id": obj.get("instance_id"),
            }
            assignments.append(row)
            by_fingerprint[fingerprint].append(row)
        except (DeterminismError, ValueError, TypeError, AttributeError) as exc:
            failures.append({"object_name": obj.name, "object_type": obj.type, "reason": str(exc)})

    base_duplicate_fingerprints = [
        {
            "canonical_fingerprint": fingerprint,
            "object_names": sorted(row["object_name"] for row in rows),
            "generated_instance_id": rows[0]["generated_instance_id"],
        }
        for fingerprint, rows in sorted(by_fingerprint.items())
        if len(rows) > 1
    ]
    base_ambiguous_names = {
        name for group in base_duplicate_fingerprints for name in group["object_names"]
    }
    expected_override_names = set(automatic_by_name) | set(bootstrap_by_name)
    if expected_override_names != base_ambiguous_names:
        missing = sorted(base_ambiguous_names - expected_override_names)
        extra = sorted(expected_override_names - base_ambiguous_names)
        raise DeterminismError(
            f"Identity-layer collision coverage mismatch; missing={missing!r}, extra={extra!r}"
        )

    existing_path = args.existing_registry or args.registry
    existing_registry = load_existing_registry(existing_path)
    existing_by_fingerprint: dict[str, list[dict[str, Any]]] = defaultdict(list)
    existing_by_resolved_fingerprint: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if existing_registry:
        for record in existing_registry.get("records", []):
            resolved = record.get("resolved_identity_fingerprint")
            method = record.get("assignment_method")
            if resolved and method in {AUTOMATIC_METHOD, BOOTSTRAP_METHOD}:
                existing_by_resolved_fingerprint[resolved].append(record)
            else:
                existing_by_fingerprint[record["canonical_fingerprint"]].append(record)

    id_rows: list[dict[str, Any]] = []
    id_to_names: dict[str, list[str]] = defaultdict(list)
    registry_conflicts: list[dict[str, Any]] = []
    unresolved_names: set[str] = set()
    for assignment in assignments:
        name = assignment["object_name"]
        fingerprint = assignment["canonical_fingerprint"]
        method = "canonical_fingerprint"
        token = None
        resolved_fingerprint = fingerprint
        generated_id = assignment["generated_instance_id"]

        override_record = automatic_by_name.get(name) or bootstrap_by_name.get(name)
        if name in base_ambiguous_names:
            try:
                if override_record is None:
                    raise DeterminismError("Missing approved identity override")
                if override_record.get("scene_id") != args.scene_id:
                    raise DeterminismError("Override scene_id mismatch")
                if override_record.get("scene_version") != args.scene_version:
                    raise DeterminismError("Override scene_version mismatch")
                if override_record.get("policy_version") != POLICY_VERSION:
                    raise DeterminismError("Override policy version mismatch")
                if override_record.get("reviewer_status") != "CONFIRMED":
                    raise DeterminismError("Override is not confirmed")
                if override_record.get("original_canonical_fingerprint") != fingerprint:
                    raise DeterminismError("Override base fingerprint mismatch")
                expected_group_id = (
                    f"{args.scene_id}:{args.scene_version}:duplicate-fingerprint:{fingerprint}"
                )
                if override_record.get("collision_group_id") != expected_group_id:
                    raise DeterminismError("Override collision group mismatch")

                method = override_record.get("assignment_method")
                if name in automatic_by_name:
                    if method != AUTOMATIC_METHOD:
                        raise DeterminismError("Automatic override method mismatch")
                    discriminator = override_record.get("objective_discriminator", {})
                    if discriminator.get("field") != "hierarchy.child_fingerprints":
                        raise DeterminismError("Automatic discriminator field mismatch")
                    child_fingerprints = sorted(
                        builder.object_fingerprint(child)[0] for child in scene.objects[name].children
                    )
                    if discriminator.get("value") != child_fingerprints:
                        raise DeterminismError("Automatic child-fingerprint evidence mismatch")
                    token = override_record.get("disambiguation_token")
                else:
                    if method != BOOTSTRAP_METHOD:
                        raise DeterminismError("Bootstrap override method mismatch")
                    token = override_record.get("bootstrap_discriminator")
                    if not isinstance(token, str) or not BOOTSTRAP_RE.fullmatch(token):
                        raise DeterminismError("Bootstrap discriminator format mismatch")

                if not isinstance(token, str) or not token:
                    raise DeterminismError("Override token is missing")
                resolved_fingerprint, generated_id = resolved_identity(
                    fingerprint, method, token
                )
                if override_record.get("resolved_identity_fingerprint") != resolved_fingerprint:
                    raise DeterminismError("Override resolved fingerprint mismatch")
                if override_record.get("final_proposed_instance_id") != generated_id:
                    raise DeterminismError("Override proposed instance_id mismatch")
            except (DeterminismError, ValueError, TypeError, KeyError) as exc:
                failures.append({"object_name": name, "object_type": assignment["object_type"], "reason": str(exc)})
                assignment["instance_id"] = None
                assignment["assignment_status"] = "override_failure"
                unresolved_names.add(name)
                continue
        elif override_record is not None:
            failures.append(
                {
                    "object_name": name,
                    "object_type": assignment["object_type"],
                    "reason": "Override supplied for a non-colliding object",
                }
            )
            assignment["instance_id"] = None
            assignment["assignment_status"] = "override_failure"
            unresolved_names.add(name)
            continue

        assignment["assignment_method"] = method
        assignment["disambiguation_token"] = token
        assignment["resolved_identity_fingerprint"] = resolved_fingerprint
        assignment["generated_instance_id"] = generated_id
        existing_records = (
            existing_by_resolved_fingerprint.get(resolved_fingerprint, [])
            if method in {AUTOMATIC_METHOD, BOOTSTRAP_METHOD}
            else existing_by_fingerprint.get(fingerprint, [])
        )
        if len(existing_records) > 1:
            registry_conflicts.append(
                {
                    "object_name": name,
                    "reason": "duplicate_registry_identity_key",
                    "fingerprint": resolved_fingerprint,
                }
            )
            assignment["instance_id"] = None
            assignment["assignment_status"] = "registry_conflict"
            continue
        instance_id = existing_records[0]["instance_id"] if existing_records else generated_id
        if existing_records and instance_id != generated_id:
            registry_conflicts.append(
                {
                    "object_name": name,
                    "reason": "registry_instance_id_derivation_mismatch",
                    "registry_instance_id": instance_id,
                    "generated_instance_id": generated_id,
                }
            )
            assignment["instance_id"] = None
            assignment["assignment_status"] = "registry_conflict"
            unresolved_names.add(name)
            continue
        if not valid_instance_id(instance_id):
            registry_conflicts.append(
                {"object_name": name, "reason": "invalid_registry_instance_id", "instance_id": instance_id}
            )
            assignment["instance_id"] = None
            assignment["assignment_status"] = "registry_conflict"
            unresolved_names.add(name)
            continue

        blender_id = assignment["existing_blender_instance_id"]
        if blender_id is not None and (not valid_instance_id(blender_id) or blender_id != instance_id):
            registry_conflicts.append(
                {
                    "object_name": name,
                    "reason": "blender_mirror_conflict",
                    "blender_instance_id": blender_id,
                    "registry_or_generated_instance_id": instance_id,
                }
            )
            assignment["instance_id"] = None
            assignment["assignment_status"] = "registry_conflict"
            unresolved_names.add(name)
            continue

        assignment["instance_id"] = instance_id
        assignment["assignment_status"] = "preserved" if existing_records else "proposed"
        id_to_names[instance_id].append(name)
        id_rows.append(assignment)

    duplicate_ids = [
        {"instance_id": instance_id, "object_names": sorted(names)}
        for instance_id, names in sorted(id_to_names.items())
        if len(names) > 1
    ]

    duplicate_fingerprint_blockers = []
    handled_duplicate_fingerprints = []
    for group in base_duplicate_fingerprints:
        group_rows = [
            assignment
            for assignment in assignments
            if assignment["canonical_fingerprint"] == group["canonical_fingerprint"]
        ]
        group_ids = [row.get("instance_id") for row in group_rows]
        if None in group_ids or len(group_ids) != len(set(group_ids)):
            duplicate_fingerprint_blockers.append(group)
        else:
            handled_duplicate_fingerprints.append(
                {
                    "canonical_fingerprint": group["canonical_fingerprint"],
                    "object_names": group["object_names"],
                    "assignment_methods": sorted(
                        {row["assignment_method"] for row in group_rows}
                    ),
                }
            )

    registry_records = [
        {
            "instance_id": row["instance_id"],
            "scene_id": args.scene_id,
            "first_seen_version": args.scene_version,
            "last_seen_version": args.scene_version,
            "status": "active",
            "object_name": row["object_name"],
            "canonical_fingerprint": row["canonical_fingerprint"],
            "resolved_identity_fingerprint": row["resolved_identity_fingerprint"],
            "assignment_method": row["assignment_method"],
            "disambiguation_token": row["disambiguation_token"],
            "identity_signals": row["identity_signals"],
            "category": "Unknown",
            "annotation_status": "needs_review",
        }
        for row in id_rows
    ]
    registry_records.sort(key=lambda row: row["instance_id"])

    custom_after = custom_property_snapshot(scene)
    state_after = scene_state_snapshot(scene, builder)
    working_hash_after = file_sha256(working_path)
    dirty_after = bpy.data.is_dirty
    validation = {
        "source_checksum_matches_expected": source_hash == SOURCE_SHA256,
        "working_checksum_unchanged": working_hash_before == working_hash_after,
        "custom_properties_unchanged": custom_before == custom_after,
        "scene_state_unchanged": state_before == state_after,
        "blender_dirty_flag_unchanged": dirty_before == dirty_after,
        "all_eligible_objects_assigned": len(registry_records) == len(eligible),
        "all_instance_ids_unique": not duplicate_ids,
        "no_duplicate_fingerprint_blockers": not duplicate_fingerprint_blockers,
        "no_unresolved_ambiguous_eligible_objects": not unresolved_names,
        "approved_automatic_layer_fully_represented": sum(
            row.get("assignment_method") == AUTOMATIC_METHOD for row in id_rows
        ) == 5,
        "approved_bootstrap_layer_fully_represented": sum(
            row.get("assignment_method") == BOOTSTRAP_METHOD for row in id_rows
        ) == 131,
        "approved_camera_exclusion_applied": len(excluded_objects) == 1,
        "no_unsupported_objects": not unsupported,
        "no_assignment_failures": not failures,
        "no_registry_conflicts": not registry_conflicts,
        "semantic_labels_inferred": False,
        "blend_saved": False,
    }
    ready = all(value for key, value in validation.items() if key not in {"semantic_labels_inferred", "blend_saved"})
    ready = ready and not validation["semantic_labels_inferred"] and not validation["blend_saved"]
    status = "READY_FOR_PERSISTENT_ID_ASSIGNMENT" if ready else "REVIEW_REQUIRED"

    manual_review_names = {
        *unresolved_names,
        *(item["object_name"] for item in unsupported),
        *(item["object_name"] for item in failures),
        *(item["object_name"] for item in registry_conflicts),
    }
    counts = {
        "total_objects": len(scene.objects),
        "excluded_objects": len(excluded_objects),
        "eligible_objects": len(eligible),
        "proposed_ids": len(registry_records),
        "normally_assigned_ids": sum(
            row.get("assignment_method") == "canonical_fingerprint" for row in id_rows
        ),
        "automatically_disambiguated_ids": sum(
            row.get("assignment_method") == AUTOMATIC_METHOD for row in id_rows
        ),
        "human_bootstrap_ids": sum(
            row.get("assignment_method") == BOOTSTRAP_METHOD for row in id_rows
        ),
        "observed_base_duplicate_fingerprint_groups": len(base_duplicate_fingerprints),
        "duplicate_fingerprint_blockers": len(duplicate_fingerprint_blockers),
        "duplicate_id_groups": len(duplicate_ids),
        "unresolved_ambiguous_objects": len(unresolved_names),
        "manual_review_objects": len(manual_review_names),
        "unsupported_objects": len(unsupported),
        "assignment_failures": len(failures),
        "registry_conflicts": len(registry_conflicts),
        "intentionally_excluded_objects": len(excluded_objects),
        "registry_rows": len(registry_records),
    }

    registry = {
        "schema_name": "amidst.instance_registry",
        "schema_version": "1.1.0",
        "repository_classification": "REVIEW_REQUIRED",
        "authority": "sidecar",
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "base_fingerprint_policy_id": BASE_FINGERPRINT_POLICY_ID,
        "namespace_uuid": str(NAMESPACE_UUID),
        "instance_id_format": "amidst:school:object:<uuid-v5>",
        "scene_id": args.scene_id,
        "scene_version": args.scene_version,
        "source_scene": source_path.name,
        "source_sha256": source_hash,
        "working_scene": working_path.name,
        "semantic_default": {"category": "Unknown", "annotation_status": "needs_review"},
        "identity_layers": {
            "automatic_disambiguation": args.automatic_disambiguation.name,
            "human_bootstrap": args.identity_bootstrap.name,
        },
        "eligibility_exclusions": excluded_objects,
        "records": registry_records,
    }
    collision_report = {
        "schema_name": "amidst.instance_id_collision_report",
        "schema_version": "1.1.0",
        "policy_id": POLICY_ID,
        "base_fingerprint_policy_id": BASE_FINGERPRINT_POLICY_ID,
        "scene_id": args.scene_id,
        "scene_version": args.scene_version,
        "base_duplicate_fingerprints": base_duplicate_fingerprints,
        "handled_duplicate_fingerprints": handled_duplicate_fingerprints,
        "duplicate_fingerprints": duplicate_fingerprint_blockers,
        "duplicate_instance_ids": duplicate_ids,
        "unsupported_objects": unsupported,
        "assignment_failures": failures,
        "registry_conflicts": registry_conflicts,
        "eligibility_exclusions": excluded_objects,
    }
    report = {
        "schema_name": "amidst.instance_id_dry_run",
        "schema_version": "1.1.0",
        "repository_classification": "REVIEW_REQUIRED",
        "status": status,
        "dry_run": True,
        "policy_id": POLICY_ID,
        "base_fingerprint_policy_id": BASE_FINGERPRINT_POLICY_ID,
        "namespace_uuid": str(NAMESPACE_UUID),
        "scene_id": args.scene_id,
        "scene_version": args.scene_version,
        "source_scene": logical_uri_for_path(
            "blender-source", source_path, repo_root=REPOSITORY_ROOT
        ),
        "source_sha256": source_hash,
        "working_scene": logical_uri_for_path(
            "blender-working", working_path, repo_root=REPOSITORY_ROOT
        ),
        "working_sha256_before": working_hash_before,
        "working_sha256_after": working_hash_after,
        "counts": counts,
        "validation": validation,
        "excluded_objects": excluded_objects,
        "object_assignments": sorted(
            (
                {
                    "object_name": row["object_name"],
                    "object_type": row["object_type"],
                    "canonical_fingerprint": row["canonical_fingerprint"],
                    "resolved_identity_fingerprint": row.get("resolved_identity_fingerprint"),
                    "instance_id": row.get("instance_id"),
                    "assignment_method": row.get("assignment_method"),
                    "assignment_status": row.get("assignment_status"),
                }
                for row in assignments
            ),
            key=lambda row: normalize_text(row["object_name"]).encode("utf-8"),
        ),
    }

    write_canonical(args.registry, registry)
    write_canonical(args.collision_report, collision_report)
    write_canonical(args.report, report)
    args.human_report.parent.mkdir(parents=True, exist_ok=True)
    args.human_report.write_text(human_report(report), encoding="utf-8")
    print(json.dumps({"status": status, "counts": counts}, sort_keys=True))


if __name__ == "__main__":
    main()
