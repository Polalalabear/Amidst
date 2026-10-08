"""Independent E1 perspective RGB research scene; recipes/GT stay generator-only.

This software renderer projects 3D faceted people and static geometry through
the same pinhole Camera used for inverse projection. It is a synthetic fixture,
not a school derivation or a general person detector benchmark. No source scene
is loaded or edited. The returned package has no actor identity or path fields.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

import numpy as np
from PIL import Image, ImageDraw

from amidst.domain.camera import Camera
from amidst.domain.geometry import Plane
from amidst.engineering.association import (
    ConfiguredRegion,
    GroundCalibration,
    InferenceScope,
    SyntheticStaticContext,
    content_sha256,
)
from amidst.engineering.perception import PixelModel, RGBFrame, frame_manifest_sha256

GENERATOR_VERSION = "pinhole-local-research-v1"
DEFAULT_CONFIG = Path(__file__).resolve().parents[3] / "configs/engineering/local_camera_v1.json"


class ResearchPackage(PixelModel):
    model_id: str
    revision: str
    run_id: str
    split: Literal["development", "test"]
    frames: tuple[RGBFrame, ...]
    cameras: tuple[Camera, ...]
    context: SyntheticStaticContext
    scope: InferenceScope
    adjacency: tuple[tuple[str, str], ...]
    source_sha256: str
    model_source_sha256: str
    context_sha256: str
    config_sha256: str
    dataset_sha256: str
    generator_sha256: str
    simulation_export_path: Path
    fps: float
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["SYNTHETIC_CONFIG"] = "SYNTHETIC_CONFIG"
    evidence_level: Literal["E1_CONFIGURED_PINHOLE_RGB"] = "E1_CONFIGURED_PINHOLE_RGB"


def _bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _write_immutable(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != payload:
        raise ValueError("existing research input differs; choose a new output/run")
    if not path.exists():
        path.write_bytes(payload)


def _camera(row: dict[str, Any], width: int, height: int, focal: float) -> Camera:
    origin = np.asarray(row["position"], dtype=float)
    target = np.asarray(row["target"], dtype=float)
    forward = target - origin
    forward /= np.linalg.norm(forward)
    right = np.cross(forward, np.asarray((0.0, 0.0, 1.0)))
    right /= np.linalg.norm(right)
    up = np.cross(right, forward)
    rotation = np.column_stack((right, up, -forward))
    pose = np.eye(4)
    pose[:3, :3] = rotation
    pose[:3, 3] = origin
    return Camera.model_validate({
        "camera_id": row["camera_id"], "camera_to_world": pose.tolist(),
        "fx": focal, "fy": focal, "cx": width / 2, "cy": height / 2,
        "width": width, "height": height, "clip_start": 0.1, "clip_end": 100,
        "floor_id": "local-floor",
    })


def project_world(camera: Camera, point: Sequence[float]) -> tuple[float, float, float] | None:
    """Exact public configured-camera projection, also useful in geometry tests."""
    pose = np.asarray(camera.camera_to_world)
    local = pose[:3, :3].T @ (np.asarray(point) - pose[:3, 3])
    depth = -float(local[2])
    if depth <= camera.clip_start or depth >= camera.clip_end:
        return None
    return (camera.cx + camera.fx * float(local[0]) / depth,
            camera.cy - camera.fy * float(local[1]) / depth, depth)


def _position(actor: dict[str, Any], timestamp: float) -> tuple[float, float] | None:
    waypoints = actor["waypoints"]
    if timestamp < waypoints[0][0] or timestamp > waypoints[-1][0]:
        return None
    for first, last in zip(waypoints, waypoints[1:], strict=False):
        if first[0] <= timestamp <= last[0]:
            alpha = (timestamp - first[0]) / (last[0] - first[0])
            return (float(first[1] + alpha * (last[1] - first[1])),
                    float(first[2] + alpha * (last[2] - first[2])))
    return float(waypoints[-1][1]), float(waypoints[-1][2])


def _box_faces(
    minimum: tuple[float, float, float], maximum: tuple[float, float, float],
    color: tuple[int, int, int], actor_label: int = 0,
) -> list[tuple[list[tuple[float, float, float]], tuple[int, int, int], int]]:
    x0, y0, z0 = minimum
    x1, y1, z1 = maximum
    vertices = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    result = []
    for indices, shade in (((0, 1, 5, 4), 1.0), ((1, 2, 6, 5), 0.82),
                           ((2, 3, 7, 6), 0.73), ((3, 0, 4, 7), 0.91),
                           ((4, 5, 6, 7), 1.08)):
        red, green, blue = (min(255, round(component * shade)) for component in color)
        result.append(([vertices[index] for index in indices],
                       (red, green, blue), actor_label))
    return result


def _person_faces(
    x: float, y: float, timestamp: float, shirt: tuple[int, int, int], label: int,
) -> list[tuple[list[tuple[float, float, float]], tuple[int, int, int], int]]:
    result = []
    # 3D head, torso, arms, separated trousers and shoes have independent facets.
    pieces = [
        ((-0.13, -0.13, 1.43), (0.13, 0.13, 1.72), (199, 152, 110)),
        ((-0.21, -0.14, 0.78), (0.21, 0.14, 1.42), shirt),
        ((-0.30, -0.10, 0.83), (-0.21, 0.10, 1.32), (184, 132, 96)),
        ((0.21, -0.10, 0.83), (0.30, 0.10, 1.32), (184, 132, 96)),
    ]
    swing = 0.06 * math.sin(timestamp * 7)
    for a, b, shift in ((-0.18, -0.025, swing), (0.025, 0.18, -swing)):
        pieces.append(((a, -0.11 + shift, 0.08), (b, 0.11 + shift, 0.80), (31, 43, 60)))
        pieces.append(((a - 0.02, -0.19 + shift, 0.0),
                       (b + 0.02, 0.11 + shift, 0.10), (22, 24, 28)))
    for low, high, color in pieces:
        result.extend(_box_faces((x + low[0], y + low[1], low[2]),
                                 (x + high[0], y + high[1], high[2]), color, label))
    return result


def _render(
    camera: Camera, row: dict[str, Any], config: dict[str, Any],
    actors: list[dict[str, Any]], timestamp: float,
) -> tuple[bytes, list[dict[str, object]]]:
    image = Image.new("RGB", (camera.width, camera.height), (58, 67, 76))
    draw = ImageDraw.Draw(image)
    floor = [project_world(camera, point) for point in
             ((0, 0, 0), (16, 0, 0), (16, 8, 0), (0, 8, 0))]
    if all(point is not None for point in floor):
        draw.polygon([(point[0], point[1]) for point in floor if point is not None],
                     fill=(169, 171, 167))
    for grid_x in range(17):
        a = project_world(camera, (grid_x, 0, 0))
        b = project_world(camera, (grid_x, 8, 0))
        if a and b:
            draw.line((a[0], a[1], b[0], b[1]), fill=(153, 157, 153))
    for grid_y in range(9):
        a = project_world(camera, (0, grid_y, 0))
        b = project_world(camera, (16, grid_y, 0))
        if a and b:
            draw.line((a[0], a[1], b[0], b[1]), fill=(153, 157, 153))
    # Portal is visible architectural geometry; coverage walls are configured masks.
    faces = _box_faces((5.9, 3.5, 0), (6.1, 4.0, 2.7), (116, 124, 125))
    faces.extend(_box_faces((5.9, 0.0, 0), (6.1, 0.5, 2.7), (116, 124, 125)))
    faces.extend(_box_faces((5.9, 0.5, 2.5), (6.1, 3.5, 2.7), (124, 132, 130)))
    pillar = config["static_pillar"]
    faces.extend(_box_faces(tuple(pillar["min_xyz"]), tuple(pillar["max_xyz"]),
                            (89, 96, 101)))
    annotations: list[dict[str, object]] = []
    x0, y0, x1, y1 = row["coverage"]
    for label, actor in enumerate(actors, start=1):
        position = _position(actor, timestamp)
        if position is None:
            continue
        x, y = position
        contact = project_world(camera, (x, y, 0.0))
        coverage = x0 <= x <= x1 and y0 <= y <= y1
        projected_faces = _person_faces(x, y, timestamp, tuple(actor["shirt_rgb"]), label)
        vertices = [project_world(camera, point)
                    for face, _, _ in projected_faces for point in face]
        pixels = [point for point in vertices if point is not None]
        bbox = [min(p[0] for p in pixels), min(p[1] for p in pixels),
                max(p[0] for p in pixels), max(p[1] for p in pixels)] if pixels else None
        if coverage:
            faces.extend(projected_faces)
        annotations.append({
            "actor_identity": actor["actor_identity"], "position_xyz_m": [x, y, 0.0],
            "contact_uv": list(contact[:2]) if contact else None,
            "unoccluded_bbox_xyxy": bbox, "in_configured_coverage": coverage,
            "contact_inside_frame": bool(contact and 0 <= contact[0] < camera.width
                                         and 0 <= contact[1] < camera.height),
            "actor_label": label,
        })
    label_image = Image.new("I", image.size, 0)
    label_draw = ImageDraw.Draw(label_image)
    projected = []
    for points, color, label in faces:
        face_pixels = [project_world(camera, point) for point in points]
        if any(point is None for point in face_pixels):
            continue
        good = [point for point in face_pixels if point is not None]
        projected.append((sum(point[2] for point in good) / len(good),
                          [(point[0], point[1]) for point in good], color, label))
    for _, polygon, color, label in sorted(projected, key=lambda item: -item[0]):
        light = row["light"]
        draw.polygon(polygon, fill=tuple(min(255, round(c * light)) for c in color))
        label_draw.polygon(polygon, fill=label)
    labels = np.asarray(label_image)
    for annotation in annotations:
        ys, xs = np.nonzero(labels == annotation["actor_label"])
        annotation["visible_pixel_count"] = int(len(xs))
        annotation["visible_bbox_xyxy"] = (
            [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
            if len(xs) else None)
        del annotation["actor_label"]
    stream = BytesIO()
    image.save(stream, format="PNG", compress_level=6)
    return stream.getvalue(), annotations


def generate_research_sequence(
    output_dir: Path, *, split: Literal["development", "test"] = "test",
    run_id: str | None = None, config_path: Path | None = None,
) -> ResearchPackage:
    """Materialize a new immutable split; export GT only under simulation/export.

    Split selection chooses whole distinct actor trajectories. Policies are
    already fixed in the versioned config; this function never examines test GT
    to adjust them. Frames show neither labels nor simulator overlays.
    """
    config = json.loads((config_path or DEFAULT_CONFIG).read_text())
    if config.get("generator_version") != GENERATOR_VERSION or not config.get(
        "policy_frozen_before_test"
    ):
        raise ValueError("research config version and pre-test policy freeze required")
    if split not in {"development", "test"}:
        raise ValueError("whole-trajectory development/test split required")
    run_id = run_id or f"local-camera-{split}-v1"
    if not run_id:
        raise ValueError("run namespace is required")
    output_dir = output_dir.resolve()
    width, height = config["image_size"]
    cameras = tuple(_camera(row, width, height, config["focal_px"])
                    for row in config["cameras"])
    generator_hash = sha256(Path(__file__).read_bytes()).hexdigest()
    config_hash = content_sha256(config)
    # Only non-recipe static data binds the context; actors are absent at inference.
    static = {key: value for key, value in config.items() if key != "splits"}
    model_hash = content_sha256(static)
    source_hash = content_sha256({"model": model_hash, "generator": generator_hash})
    context_hash = content_sha256({"static": static, "cameras": [
        camera.model_dump(mode="json") for camera in cameras]})
    plane = Plane(plane_id="local-ground", point=(0, 0, 0), normal=(0, 0, 1),
                  floor_id="local-floor")
    adjacency = tuple((str(a), str(b)) for a, b in config["directed_camera_edges"])
    context = SyntheticStaticContext(
        spatial_context_id="context:synthetic-local-camera-v1",
        source_sha256=source_hash, context_sha256=context_hash, ground_plane=plane,
        walkable_bounds_xy_m=(0, 0, 16, 8),
        calibrations=tuple(GroundCalibration(camera_id=camera.camera_id, plane=plane,
                                             pinhole=camera) for camera in cameras),
        regions=tuple(ConfiguredRegion(region_id=row["region_id"], floor_id="local-floor",
                                       bounds_xy_m=tuple(row["bounds_xy_m"]))
                      for row in config["regions"]),
        allowed_camera_pairs=adjacency, detour_waypoints_m=((8.5, 1.0, 0.0), (8.5, 3.8, 0.0)),
    )
    scope = InferenceScope(
        place_id="synthetic-local-camera", model_id=config["model_id"],
        model_revision=config["revision"], run_id=run_id, clock_id="synthetic-seconds-v1",
        source_ref=f"source:{source_hash}", source_sha256=source_hash,
        spatial_context_id=context.spatial_context_id, context_sha256=context_hash,
    )
    fps = float(config["fps"])
    actors = config["splits"][split]["actors"]
    frames = []
    truth = []
    for index in range(round(float(config["duration_s"]) * fps) + 1):
        timestamp = round(index / fps, 9)
        for camera, row in zip(cameras, config["cameras"], strict=True):
            payload, annotations = _render(camera, row, config, actors, timestamp)
            media_ref = f"media:{config['model_id']}:{run_id}:{camera.camera_id}:{index:04d}"
            path = output_dir / "rgb" / camera.camera_id / f"frame-{index:04d}.png"
            _write_immutable(path, payload)
            frames.append(RGBFrame(media_ref=media_ref, camera_id=camera.camera_id,
                                   timestamp=timestamp, path=path,
                                   sha256=sha256(payload).hexdigest(), width=width, height=height))
            truth.append({"frame_ref": media_ref, "camera_id": camera.camera_id,
                          "timestamp": timestamp, "render_annotations": annotations})
    dataset_hash = frame_manifest_sha256(frames)
    export_path = output_dir / "simulation/export/ground_truth.json"
    _write_immutable(export_path, _bytes({
        "schema_version": "local.camera.truth.v1", "boundary": "EVALUATION_DEBUG_ONLY",
        "model_id": scope.model_id, "run_id": run_id, "split": split,
        "dataset_sha256": dataset_hash, "config_sha256": config_hash,
        "recipe": config["splits"][split], "ground_truth": truth,
        "behavior_truth": _behavior_truth(actors),
        "limitations": ["Configured camera coverage walls are fixture visibility masks.",
                        "Fast-negative trajectory is deliberately physically invalid.",
                        "No real camera, school source or appearance generalization claim."],
    }))
    return ResearchPackage(
        model_id=scope.model_id, revision=scope.model_revision, run_id=run_id, split=split,
        frames=tuple(frames), cameras=cameras, context=context, scope=scope,
        adjacency=adjacency, source_sha256=source_hash, model_source_sha256=model_hash,
        context_sha256=context_hash, config_sha256=config_hash, dataset_sha256=dataset_hash,
        generator_sha256=generator_hash, simulation_export_path=export_path, fps=fps,
    )


def _behavior_truth(actors: list[dict[str, Any]]) -> list[dict[str, object]]:
    """Generator-only analytic labels; inference never calls this helper."""
    events: list[dict[str, object]] = []
    for actor in actors:
        waypoints = actor["waypoints"]
        for first, last in zip(waypoints, waypoints[1:], strict=False):
            t0, x0, y0 = first
            t1, x1, y1 = last
            if (x0 < 6 <= x1) or (x1 < 6 <= x0):
                alpha = (6 - x0) / (x1 - x0)
                y = y0 + alpha * (y1 - y0)
                if 0.5 <= y <= 3.5:
                    events.append({"actor_identity": actor["actor_identity"],
                                   "kind": "ENTER" if x1 > x0 else "EXIT",
                                   "timestamp": t0 + alpha * (t1 - t0),
                                   "direction": "west-to-east" if x1 > x0 else "east-to-west"})
            if math.dist((x0, y0), (x1, y1)) < 0.05 and t1 - t0 >= 2:
                events.append({"actor_identity": actor["actor_identity"], "kind": "DWELL",
                               "timestamp": t0, "end_time": t1, "direction": None})
        if actor["scenario"] == "enter_exit_corner_revisit_dwell":
            corner = next(row for row in waypoints if row[1] >= 9.9 and row[2] < 2.1)
            events.append({"actor_identity": actor["actor_identity"], "kind": "CORNER",
                           "timestamp": corner[0], "direction": "east-to-north"})
            events.append({"actor_identity": actor["actor_identity"],
                           "kind": "POSSIBLE_WANDERING", "timestamp": waypoints[-2][0],
                           "direction": None})
    return events
