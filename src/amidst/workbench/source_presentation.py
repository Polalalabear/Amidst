"""Interactive, bounded source-mesh presentation over immutable public evidence.

This is the historical school Office diagnostic, not RGB perception or a new
research run. Meshes come from the original evaluated-source archive; body
positions come from public projections and the original inferred candidate.
No Blender, renderer, GT, simulation recipe or external provider is opened.
The research workbench owns authorization; this module is not an Agent tool.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from amidst.engineering.registry import content_hash, opaque_ref, safe_relative_path

Json = dict[str, Any]
SOURCE_SHA256 = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
METRES_PER_BU = 0.0247
CHECKPOINT = "883204af854bed301506b39d63ccb33312b79ff2"
_MOTION = "human_review/frames/motion_context/motion_manifest.json"
_VISUAL = "human_review/frames/visual_manifest.json"
_GEOMETRY = "data/scene_audit/phase1_physical_policy_approval_20261006/source_evidence.json.gz"
_SUPPORT = "data/scene_audit/phase1_physical_policy_approval_20261006/floor_support_details.json.gz"
_CONTEXT = "data/finalization/local_run/dataset/inference/office/context.json"
_PROJECTION = (
    "data/finalization/local_run/diagnostics/office/policy_graph_primary/projected_frames.json"
)
_CANDIDATES = "data/finalization/local_run/diagnostics/office/policy_graph_primary/candidates.json"
_SCALE = "configs/architectural_scale_school_v3.json"
_PINS = {
    _MOTION: "e77628c145fceb42ae086a76f4de60741147ea525eb12d46e7f23d7ba83d7b69",
    _VISUAL: "f6c4c9fef9dc80fd1717b6a751762b1a09d686b014c1394409b61cb0c9b22d0c",
    _GEOMETRY: "6d30e591d6210707f2b6175bf96dc2fe2395fe0202b24bd0a6df7ee87a5d997c",
    _SUPPORT: "6a37b041a368e3e576da4c3f3894708462c0504956f82ad599082acd816b23d0",
    _CONTEXT: "56a131626b7c9382f260cb0d088abf6d38ff13127f76d3b5233dd2abdf87dc70",
    _PROJECTION: "0ebdb3762fe181c44ea25456b4525204aaa19dbe957a923c360f2bffdf5d6e48",
    _CANDIDATES: "0212756864986ee5044313058144c7e3fcb56c72e68ebd30b7062e508b9c9b02",
    _SCALE: "7e3615a3b0b4485585da9c0f7beefb96955517f7a321910fc008c041f99a3eaf",
}


class SourcePresentationError(ValueError):
    """Fixed public errors; locators and rejected data are never echoed."""


def _path(repo: Path, relative: str) -> Path:
    path = repo.joinpath(*safe_relative_path(relative).parts)
    if path.is_symlink() or not path.resolve().is_relative_to(repo):
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    return path


def _hash(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _read(repo: Path, relative: str) -> Json:
    if relative not in _PINS:
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    raw = _path(repo, relative).read_bytes()
    if hashlib.sha256(raw).hexdigest() != _PINS[relative]:
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    value = json.loads(gzip.decompress(raw) if relative.endswith(".gz") else raw)
    if not isinstance(value, dict):
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    return value


def _vector(value: Any) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3 or any(
        type(v) not in (int, float) or not math.isfinite(v) for v in value
    ):
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    return [float(v) for v in value]


def _metres(value: Any) -> list[float]:
    return [v * METRES_PER_BU for v in _vector(value)]


def _no_truth(value: Json) -> None:
    if any(value.get(key) is not False for key in (
        "gt_used", "evaluation_files_read", "simulation_recipe_read",
    )):
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")


def _mesh(row: Json, low: list[float], high: list[float]) -> Json | None:
    vertices = [_vector(v) for v in row["vertices"]]
    chosen = []
    source_indices = []
    for index, triangle in enumerate(row["triangles"]):
        if len(triangle) != 3 or any(type(i) is not int or not 0 <= i < len(vertices)
                                    for i in triangle):
            raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
        points = [vertices[i] for i in triangle]
        # Exactly the historical display cutaway: retain original vertices,
        # intersect the crop AABB, and drop source faces crossing its Z lid.
        if all(max(p[a] for p in points) >= low[a] and
               min(p[a] for p in points) <= high[a] for a in range(3)) and all(
            p[2] <= high[2] for p in points
        ):
            chosen.append(triangle)
            source_indices.append(index)
    if not chosen:
        return None
    retained = sorted({i for triangle in chosen for i in triangle})
    index_map = {original: compact for compact, original in enumerate(retained)}
    return {
        "mesh_ref": opaque_ref("mesh", _PINS[_GEOMETRY], row["geometry_sha256"],
                               content_hash(source_indices)),
        "vertices": [_metres(vertices[i]) for i in retained],
        "triangles": [[index_map[i] for i in triangle] for triangle in chosen],
        "source_geometry_sha256": row["geometry_sha256"],
        "selection_sha256": content_hash(source_indices),
        "origin": "SOURCE_EVALUATED_GEOMETRY", "authority": "DISPLAY_CONTEXT_ONLY",
        "color": "#727b84", "source_vertices_unchanged": True,
    }


def _clip_polygon(
    polygon: list[list[float]], axis: int, boundary: float, keep_above: bool,
) -> list[list[float]]:
    """Clip a source face to one plane; emit no new closing faces or caps."""
    result: list[list[float]] = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        start_inside = start[axis] >= boundary if keep_above else start[axis] <= boundary
        end_inside = end[axis] >= boundary if keep_above else end[axis] <= boundary
        if start_inside:
            result.append(start)
        if start_inside != end_inside:
            fraction = (boundary - start[axis]) / (end[axis] - start[axis])
            point = [start[a] + fraction * (end[a] - start[a]) for a in range(3)]
            point[axis] = boundary
            result.append(point)
    # A source corner exactly on a clip plane may have been emitted twice.
    compact: list[list[float]] = []
    for point in result:
        if not compact or math.dist(compact[-1], point) > 1e-9:
            compact.append(point)
    if len(compact) > 1 and math.dist(compact[0], compact[-1]) <= 1e-9:
        compact.pop()
    return compact


def _clipped_mesh(
    row: Json, low: list[float], high: list[float], algorithm_sha256: str,
) -> Json | None:
    """A new bounded display derivation of the same historical source objects."""
    source_vertices = [_vector(v) for v in row["vertices"]]
    vertices: list[list[float]] = []
    triangles: list[list[int]] = []
    vertex_indices: dict[tuple[float, ...], int] = {}
    source_indices: list[int] = []
    non_horizontal = 0
    for index, triangle in enumerate(row["triangles"]):
        if len(triangle) != 3 or any(type(i) is not int or not 0 <= i < len(source_vertices)
                                    for i in triangle):
            raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
        polygon = [source_vertices[i] for i in triangle]
        for axis in range(3):
            polygon = _clip_polygon(polygon, axis, low[axis], True)
            if not polygon:
                break
            polygon = _clip_polygon(polygon, axis, high[axis], False)
            if not polygon:
                break
        for fan in range(1, len(polygon) - 1):
            points = [polygon[0], polygon[fan], polygon[fan + 1]]
            u = [points[1][a] - points[0][a] for a in range(3)]
            v = [points[2][a] - points[0][a] for a in range(3)]
            normal = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                      u[0] * v[1] - u[1] * v[0]]
            area_twice = math.hypot(*normal)
            if area_twice < 1e-8:
                continue
            indices = []
            for point in points:
                key = tuple(point)
                if key not in vertex_indices:
                    vertex_indices[key] = len(vertices)
                    vertices.append(_metres(point))
                indices.append(vertex_indices[key])
            triangles.append(indices)
            source_indices.append(index)
            non_horizontal += abs(normal[2]) / area_twice < 0.999999
    if not triangles:
        return None
    derivation = {
        "method": "SOURCE_TRIANGLE_SIX_PLANE_CLIP_NO_CAPS_V1",
        "parent_source_sha256": SOURCE_SHA256,
        "parent_revision": "EVALUATED_SCENE_FRAME_220_SUBFRAME_0",
        "parent_archive_sha256": _PINS[_GEOMETRY],
        "parent_geometry_sha256": row["geometry_sha256"],
        "parent_motion_manifest_sha256": _PINS[_MOTION],
        "source_triangle_indices_sha256": content_hash(source_indices),
        "source_triangle_count": len(set(source_indices)),
        "crop_native_bu": [low, high], "crop_metres": [_metres(low), _metres(high)],
        "metres_per_unit": METRES_PER_BU, "algorithm_sha256": algorithm_sha256,
        "native_world_to_metres": [
            [METRES_PER_BU, 0.0, 0.0, 0.0], [0.0, METRES_PER_BU, 0.0, 0.0],
            [0.0, 0.0, METRES_PER_BU, 0.0], [0.0, 0.0, 0.0, 1.0],
        ],
        "geometry_sha256": content_hash({"vertices": vertices, "triangles": triangles}),
        "new_caps_created": False, "physical_authority_changed": False,
        "semantic_classification_performed": False,
    }
    derivation_sha256 = content_hash(derivation)
    return {
        "mesh_ref": opaque_ref("mesh", derivation_sha256),
        "vertices": vertices, "triangles": triangles,
        "source_geometry_sha256": row["geometry_sha256"],
        "derivation": derivation, "derivation_sha256": derivation_sha256,
        "origin": "SOURCE_EVALUATED_GEOMETRY", "authority": "DISPLAY_CONTEXT_ONLY",
        "color": "#727b84", "source_vertices_unchanged": False,
        "non_horizontal_triangle_count": non_horizontal,
        "horizontal_triangle_count": len(triangles) - non_horizontal,
    }


@lru_cache(maxsize=2)
def _assemble(repo_string: str, pins_sha256: str, algorithm_sha256: str) -> Json:
    repo = Path(repo_string)
    motion, visual = _read(repo, _MOTION), _read(repo, _VISUAL)
    _no_truth(motion)
    _no_truth(visual)
    if motion["source_sha256"] != SOURCE_SHA256 or (
        visual["source_asset_sha256"] != SOURCE_SHA256
        or motion["fps"] != 5 or visual["sequence_fps"] != 5
        or motion["new_route_generated"] is not False
        or motion["joint_pose_authority"] != "DISPLAY_ONLY"
        or len(motion["frames"]) != 50 or len(visual["frames"]) != 50
    ):
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    for entry in motion["inputs"]:
        if entry["path"] in _PINS and entry["sha256"] != _PINS[entry["path"]]:
            raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    archive = _read(repo, _GEOMETRY)
    scale = _read(repo, _SCALE)
    if archive["source_sha256"] != SOURCE_SHA256 or (
        archive["evaluated_scene"] != motion["render_policy"]["source_frame"]
        or archive["policy"]["gt_used"] is not False
        or archive["geometry_modified"] is not False or archive["saved"] is not False
        or archive["architectural_scale"]["metres_per_blender_unit"] != METRES_PER_BU
        or scale["metres_per_blender_unit"] != METRES_PER_BU
        or scale["source_asset_sha256"] != SOURCE_SHA256
        or scale["authority"] != "APPROVED"
    ):
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    crop = motion["render_policy"]["display_crop_bu"]
    low, high = _vector(crop["minimum"]), _vector(crop["maximum"])
    if any(a >= b for a, b in zip(low, high, strict=True)):
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    selected_objects = motion["render_policy"]["source_objects"]
    matched = [row for row in archive["meshes"] if row["source_object_id"] in selected_objects]
    if len(matched) != len(selected_objects) or any(r["full_object_exported"] is not True
                                                   for r in matched):
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    historical_meshes = [result for row in matched if (result := _mesh(row, low, high)) is not None]
    if sum(len(row["triangles"]) for row in historical_meshes) != motion["render_policy"][
        "retained_source_triangles"
    ]:
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    meshes = [result for row in matched
              if (result := _clipped_mesh(row, low, high, algorithm_sha256)) is not None]
    projection = _read(repo, _PROJECTION)["dataset"]["samples"]
    samples: dict[int, list[Json]] = {}
    for sample in projection:
        samples.setdefault(sample["frame_id"], []).append(sample)
    frames = []
    elapsed = 0.0
    for index, (frame, old) in enumerate(zip(motion["frames"], visual["frames"], strict=True)):
        if type(frame["frame_id"]) is not int or frame["frame_id"] != index or (
            type(frame["timestamp"]) not in (int, float)
            or frame["timestamp"] != index / 5
            or type(old["frame_id"]) is not int or old["frame_id"] != index
            or type(old["timestamp"]) not in (int, float) or old["timestamp"] != index / 5
        ) or (
            frame["body_base_bu"] != old["body_base_bu"]
            or frame["landmark_position_bu"] != old["landmark_position_bu"]
            or frame["joint_pose_authority"] != "DISPLAY_ONLY"
            or frame["body_pose_display_only"] is not True
        ):
            raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
        visible = sorted((s for s in samples[index] if s["projected_point"] is not None),
                         key=lambda s: s["camera_id"])
        observed = frame["state"] == "OBSERVED"
        if observed != bool(visible) or frame["state"] not in ("OBSERVED", "INFERRED_GAP"):
            raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
        if observed and math.dist(_vector(frame["landmark_position_bu"]),
                                  _vector(visible[0]["projected_point"]["world_position"])) > 0.001:
            raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
        position = _metres(frame["body_base_bu"])
        previous = _metres(motion["frames"][max(0, index - 1)]["body_base_bu"])
        following = _metres(motion["frames"][min(49, index + 1)]["body_base_bu"])
        elapsed += math.dist(previous, position)
        frames.append({
            "frame_ref": opaque_ref("frame", _PINS[_MOTION], str(index)),
            "timestamp": float(frame["timestamp"]), "world_position": position,
            "landmark_position": _metres(frame["landmark_position_bu"]),
            "evidence_state": "PROJECTED" if observed else "INFERRED_GAP",
            "source_state": frame["state"], "source_role": frame["role"],
            "origin": "SYNTHETIC", "image_measurement": False,
            "authority": "EXISTING_PUBLIC_PROJECTIONS_AND_INFERRED_CANDIDATE",
            "display_only": True, "joint_pose_authority": "DISPLAY_ONLY",
            "yaw_radians": math.atan2(following[1] - previous[1], following[0] - previous[0]),
            "walk_phase_radians": elapsed * 2 * math.pi / 1.2,
            "media_ref": opaque_ref("media", _PINS[_MOTION], frame["sha256"], str(index)),
        })
    result = _read(repo, _CANDIDATES)["results"][0]
    routes = [{"candidate_ref": opaque_ref("candidate", _PINS[_CANDIDATES], c["candidate_id"]),
               "points": [_metres(p) for p in c["polyline"]], "original_order": index,
               "origin": "SYNTHETIC", "image_measurement": False,
               "authority": "ORIGINAL_FROZEN_INFERRED_CANDIDATE"}
              for index, c in enumerate(result["candidates"])]
    context = _read(repo, _CONTEXT)
    cameras = [{"camera_id": c["camera_id"],
                "camera_ref": opaque_ref("camera", _PINS[_CONTEXT], c["camera_id"]),
                "position": _metres([c["camera_to_world"][a][3] for a in range(3)]),
                "authority": "ORIGINAL_FROZEN_SOURCE_CALIBRATION"} for c in context["cameras"]]
    points = [p for mesh in meshes for p in mesh["vertices"]]
    points.extend(f["world_position"] for f in frames)
    if not points:
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    retained_bounds = [[min(p[a] for p in points) for a in range(3)],
                       [max(p[a] for p in points) for a in range(3)]]
    bounds = [_metres(low), _metres(high)]
    units = {"native_units": "NATIVE_BU", "normalized_units": "METRES",
             "metres_per_unit": METRES_PER_BU, "normalization": "SCALE_TO_METRES",
             "coordinate_frame": "RIGHT_HANDED_XYZ_Z_UP", "authority": "APPROVED_SCHOOL_V3_SCALE"}
    source_binding_ref = opaque_ref("binding", SOURCE_SHA256, pins_sha256, content_hash(units))
    for row in [*meshes, *historical_meshes, *frames, *routes]:
        row["source_binding_ref"] = source_binding_ref
        row["normalization_sha256"] = content_hash(units)
    dimensions = {key: motion["approved_body_dimensions_m"][key]
                  for key in ("radius", "height", "clearance")}
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
           for v in dimensions.values()):
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
    return {
        "schema_version": "workbench.source-presentation.v1",
        "presentation_ref": opaque_ref("presentation", SOURCE_SHA256, pins_sha256,
                                       algorithm_sha256, content_hash(units)),
        "label": "原校園模型・Office 行走診斷",
        "description": "來源 evaluated mesh、公開投影與全部原 GAP 路徑；人物姿態僅供呈現。",
        "origin": "SYNTHETIC", "image_measurement": False,
        "authority": "SOURCE_BOUND_DIAGNOSTIC_PRESENTATION", "gt_used": False,
        "formal_execution_enabled": False, "physical_authority_changed": False,
        "frame_step_s": 0.2, "time_range": [0.0, 9.8], "bounds": bounds,
        "binding": {"binding_ref": source_binding_ref,
                    "source_ref": opaque_ref("source", SOURCE_SHA256),
                    "source_sha256": SOURCE_SHA256, "checkpoint": CHECKPOINT,
                    "model_revision": "historical-office-diagnostic-v1",
                    "run_ref": opaque_ref("run", CHECKPOINT, _PINS[_MOTION]),
                    "clock": "HISTORICAL_CONFIGURED_SYNTHETIC_SECONDS",
                    "units": units, "normalization_sha256": content_hash(units),
                    "producer_sha256": algorithm_sha256,
                    "inputs": [{"resource_ref": opaque_ref("source", ref, sha), "sha256": sha}
                               for ref, sha in sorted(_PINS.items())]},
        "snapshot": {"bounds": bounds, "cameras": cameras, "objects": [],
                     "source_evaluation": archive["evaluated_scene"],
                     "retained_geometry_bounds": retained_bounds,
                     "display_crop_metres": [_metres(low), _metres(high)],
                     "whole_scene_occlusion_proof": False},
        "meshes": meshes, "historical_meshes": historical_meshes,
        "frames": frames, "routes": routes,
        "geometry_presentation": {
            "method": "SOURCE_TRIANGLE_SIX_PLANE_CLIP_NO_CAPS_V1",
            "derivation_sha256": content_hash([m["derivation_sha256"] for m in meshes]),
            "historical_triangle_count": sum(len(m["triangles"]) for m in historical_meshes),
            "display_triangle_count": sum(len(m["triangles"]) for m in meshes),
            "non_horizontal_triangle_count": sum(
                m["non_horizontal_triangle_count"] for m in meshes
            ),
            "historical_manifest_unchanged": True,
            "physical_authority_changed": False, "semantic_classification_performed": False,
        },
        "termination_reason": result.get("termination_reason"), "complete": result.get("complete"),
        "humanoid": {**dimensions, "joint_pose_authority": "DISPLAY_ONLY",
                     "historical_foot_binding_authority": motion["foot_binding_authority"],
                     "historical_scope_authority": motion["scope_authority"]},
    }


def load_source_presentation(repo: Path) -> Json:
    """Verify pinned bytes, then return a mutable copy of the cached bounded DTO."""
    try:
        repo = repo.resolve()
        for ref, sha in _PINS.items():
            if _hash(_path(repo, ref)) != sha:
                raise SourcePresentationError("SOURCE_PRESENTATION_INVALID")
        pins_hash = content_hash(_PINS)
        algorithm_hash = _hash(Path(__file__))
        return copy.deepcopy(_assemble(str(repo), pins_hash, algorithm_hash))
    except (OSError, ValueError, KeyError, TypeError, IndexError, OverflowError):
        raise SourcePresentationError("SOURCE_PRESENTATION_INVALID") from None


def source_presentation_summary(repo: Path) -> Json:
    asset = load_source_presentation(repo)
    return {key: asset[key] for key in (
        "presentation_ref", "label", "description", "origin", "image_measurement", "authority",
        "gt_used", "formal_execution_enabled", "frame_step_s", "time_range", "binding",
        "geometry_presentation",
    )} | {"mesh_count": len(asset["meshes"]), "frame_count": len(asset["frames"]),
          "candidate_count": len(asset["routes"]), "status": "AVAILABLE_INTERACTIVE"}


def source_presentation_media(repo: Path, media_ref: str) -> tuple[str, bytes]:
    """Only the fifty original diagnostic PNGs, never arbitrary source paths."""
    try:
        repo = repo.resolve()
        motion = _read(repo, _MOTION)
        _no_truth(motion)
        for index, row in enumerate(motion["frames"]):
            if opaque_ref("media", _PINS[_MOTION], row["sha256"], str(index)) != media_ref:
                continue
            relative = "human_review/frames/motion_context/" + row["path"]
            raw = _path(repo, relative).read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["sha256"] or len(raw) != row["bytes"]:
                raise SourcePresentationError("SOURCE_PRESENTATION_MEDIA_UNAVAILABLE")
            return "image/png", raw
    except (OSError, ValueError, KeyError, TypeError):
        raise SourcePresentationError("SOURCE_PRESENTATION_MEDIA_UNAVAILABLE") from None
    raise SourcePresentationError("SOURCE_PRESENTATION_MEDIA_UNAVAILABLE")
