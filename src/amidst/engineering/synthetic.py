"""Small reproducible engineering-only RGB scene and isolated simulation export.

The procedural scene is an independent configured model, never a derivation of
school geometry.  Generator code alone knows actor recipes.  Its complete GT
sidecar is stored under simulation/export and is not an input to perception.
"""

import json
import math
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw
from pydantic import Field

from amidst.engineering.perception import PixelModel, RGBFrame, frame_manifest_sha256

GENERATOR_VERSION = "procedural-rgb-lab-v1"


class SyntheticCamera(PixelModel):
    camera_id: str
    width: int = 320
    height: int = 240
    ground_to_pixel: tuple[tuple[float, float, float], tuple[float, float, float]]
    plane_z_m: float = 0.0
    camera_group: str = "lab"
    coverage_regions: tuple[str, ...] = ()
    origin: Literal["SYNTHETIC_CONFIGURED"] = "SYNTHETIC_CONFIGURED"
    authority: Literal["ENGINEERING_FIXTURE_ONLY"] = "ENGINEERING_FIXTURE_ONLY"


class SyntheticPackage(PixelModel):
    model_id: str
    revision: str
    run_id: str
    frames: tuple[RGBFrame, ...]
    cameras: tuple[SyntheticCamera, ...]
    source_sha256: str
    model_source_sha256: str
    context_sha256: str
    config_sha256: str
    dataset_sha256: str
    generator_sha256: str
    simulation_export_path: Path
    fps: float = Field(gt=0)
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["ENGINEERING_FIXTURE_ONLY"] = "ENGINEERING_FIXTURE_ONLY"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _project(camera: SyntheticCamera, x: float, y: float) -> tuple[float, float]:
    first, second = camera.ground_to_pixel
    return first[0] * x + first[1] * y + first[2], second[0] * x + second[1] * y + second[2]


def _background(camera: SyntheticCamera) -> Image.Image:
    image = Image.new("RGB", (camera.width, camera.height), (52, 63, 77))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 100, 319, 239), fill=(168, 174, 179))
    draw.rectangle((0, 96, 319, 100), fill=(110, 122, 130))
    for y in range(120, 240, 25):
        draw.line((0, y, 319, y), fill=(149, 155, 160), width=1)
    for x in range(0, 320, 40):
        draw.line((x, 100, x, 239), fill=(149, 155, 160), width=1)
    draw.rectangle((15, 25, 85, 76), fill=(86, 110, 128), outline=(124, 140, 153), width=3)
    draw.rectangle((248, 25, 307, 76), fill=(86, 110, 128), outline=(124, 140, 153), width=3)
    return image


def _draw_target(draw: ImageDraw.ImageDraw, u: float, v: float) -> list[int]:
    x, y = round(u), round(v)
    # RGB-only human-like silhouette; no labels, bbox, IDs or paths drawn.
    draw.ellipse((x - 6, y - 43, x + 6, y - 31), fill=(199, 150, 102))
    draw.rectangle((x - 8, y - 30, x + 8, y - 13), fill=(39, 100, 207))
    draw.rectangle((x - 8, y - 13, x - 1, y), fill=(30, 55, 97))
    draw.rectangle((x + 1, y - 13, x + 8, y), fill=(30, 55, 97))
    draw.line((x - 8, y - 25, x - 11, y - 14), fill=(199, 150, 102), width=3)
    draw.line((x + 8, y - 25, x + 11, y - 14), fill=(199, 150, 102), width=3)
    return [x - 12, y - 43, x + 13, y + 1]


def generate_sequence(
    output_dir: Path, *, run_id: str = "simulation-demo-v1", model_id: str = "synthetic-lab-v1",
    frame_count: int = 51, fps: float = 5.0,
) -> SyntheticPackage:
    """Materialize a two-camera sequence and a complete separate GT package.

    Repeating exactly the same configuration reproduces PNG byte hashes.  An
    existing differing file is never overwritten, so a run cannot silently
    change its immutable inputs.  The returned RGB index contains no GT fields.
    """
    if not run_id or not model_id or frame_count < 5 or not math.isfinite(fps) or fps <= 0:
        raise ValueError("valid namespaces, >=5 frames and finite positive fps required")
    if not output_dir.is_absolute():
        output_dir = output_dir.resolve()
    cameras = (
        SyntheticCamera(camera_id="CAM_A", ground_to_pixel=((38.0, 0.0, 16.0),
                                                          (0.0, -8.0, 218.0))),
        SyntheticCamera(camera_id="CAM_B", ground_to_pixel=((38.0, 0.0, -136.0),
                                                          (0.0, 8.0, 188.0))),
    )
    recipe: dict[str, object] = {
        "generator_version": GENERATOR_VERSION, "model_id": model_id, "revision": "1",
        "run_id": run_id, "frame_count": frame_count, "fps": fps,
        "cameras": [camera.model_dump(mode="json") for camera in cameras],
        "actors": ["blue-person-a", "blue-person-b"],
        "paths": "A:x=0.8+t,y=2+0.05sin(t);B:x=1.7+0.82t,y=2.1+0.05cos(t)",
        "occlusion": "CAM_A static pillar x=[138,214] y=[105,239]",
        "coordinate_frame": "RIGHT_HANDED_XYZ_Z_UP", "units": "METRES",
        "authority": "ENGINEERING_FIXTURE_ONLY", "scene_is_school_derivation": False,
    }
    generator_hash = sha256(Path(__file__).read_bytes()).hexdigest()
    config_hash = sha256(_canonical_bytes(recipe)).hexdigest()
    model_source = {key: value for key, value in recipe.items()
                    if key not in {"run_id", "frame_count", "fps"}}
    model_source_hash = sha256(_canonical_bytes(model_source)).hexdigest()
    source_hash = sha256(_canonical_bytes({"generator": generator_hash,
                                          "model_sha256": model_source_hash})).hexdigest()
    context_hash = sha256(_canonical_bytes({"frame": "RIGHT_HANDED_XYZ_Z_UP",
                                           "units": "METRES", "floor_z": 0.0,
                                           "extent": [0.0, 12.0, 0.0, 4.0],
                                           "authority": "ENGINEERING_FIXTURE_ONLY"})).hexdigest()
    frames: list[RGBFrame] = []
    truth: list[dict[str, object]] = []
    for frame_index in range(frame_count):
        timestamp = round(frame_index / fps, 9)
        actors = (
            ("blue-person-a", 0.8 + timestamp, 2.0 + 0.05 * math.sin(timestamp)),
            ("blue-person-b", 1.7 + 0.82 * timestamp, 2.1 + 0.05 * math.cos(timestamp)),
        )
        truth.append({"timestamp": timestamp, "actors": [
            {"actor_identity": identity, "position_xyz_m": [x, y, 0.0]}
            for identity, x, y in actors
        ]})
        for camera in cameras:
            image = _background(camera)
            draw = ImageDraw.Draw(image)
            camera_truth: list[dict[str, object]] = []
            for identity, x, y in actors:
                u, v = _project(camera, x, y)
                bbox = _draw_target(draw, u, v)
                camera_truth.append({"actor_identity": identity, "contact_uv": [u, v],
                                     "unoccluded_bbox_xyxy": bbox,
                                     "contact_inside_frame": 0 <= u < 320 and 0 <= v < 240})
            if camera.camera_id == "CAM_A":
                draw.rectangle((138, 105, 214, 239), fill=(94, 99, 108))
                draw.rectangle((138, 105, 142, 239), fill=(124, 128, 135))
            relative = Path("rgb") / camera.camera_id / f"frame-{frame_index:04d}.png"
            path = output_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            # Encode first, then reject conflicting existing materialization.
            stream = BytesIO()
            image.save(stream, format="PNG", compress_level=6)
            payload = stream.getvalue()
            if path.exists() and path.read_bytes() != payload:
                raise ValueError("existing run image differs; choose a new run output")
            if not path.exists():
                path.write_bytes(payload)
            media_ref = f"media:{model_id}:{run_id}:{camera.camera_id}:{frame_index:04d}"
            frames.append(RGBFrame(
                media_ref=media_ref, camera_id=camera.camera_id, timestamp=timestamp, path=path,
                sha256=sha256(payload).hexdigest(), width=camera.width, height=camera.height,
            ))
            truth.append({"timestamp": timestamp, "camera_id": camera.camera_id,
                          "render_annotations": camera_truth})
    dataset_hash = frame_manifest_sha256(frames)
    gt_path = output_dir / "simulation" / "export" / "ground_truth.json"
    gt_path.parent.mkdir(parents=True, exist_ok=True)
    gt_payload = _canonical_bytes({"schema_version": "simulation.export.v1",
                                   "boundary": "EVALUATION_DEBUG_ONLY", "recipe": recipe,
                                   "dataset_sha256": dataset_hash, "ground_truth": truth})
    if gt_path.exists() and gt_path.read_bytes() != gt_payload:
        raise ValueError("existing run GT differs; choose a new run output")
    if not gt_path.exists():
        gt_path.write_bytes(gt_payload)
    return SyntheticPackage(
        model_id=model_id, revision="1", run_id=run_id, frames=tuple(frames), cameras=cameras,
        source_sha256=source_hash, model_source_sha256=model_source_hash,
        context_sha256=context_hash, config_sha256=config_hash,
        dataset_sha256=dataset_hash, generator_sha256=generator_hash,
        simulation_export_path=gt_path, fps=fps,
    )
