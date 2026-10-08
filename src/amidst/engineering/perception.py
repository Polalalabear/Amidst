"""Deterministic, class-agnostic RGB measurement for the local engineering demo.

This module has no simulator, annotation, segmentation, depth or GT input.  Frame
locators are internal; the Agent facade publishes only their opaque references.
"""

import json
from collections import defaultdict, deque
from collections.abc import Sequence
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

PRODUCER_VERSION = "rgb-temporal-components-v1"


class PixelModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class RGBFrame(PixelModel):
    media_ref: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    timestamp: Annotated[FiniteFloat, Field(ge=0)]
    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class Measurement(PixelModel):
    observation_id: str
    local_track_id: str
    camera_id: str
    run_id: str
    model_id: str
    timestamp: Annotated[FiniteFloat, Field(ge=0)]
    frame_ref: str
    bbox_xyxy: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
    contact_pixel: tuple[FiniteFloat, FiniteFloat]
    appearance: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    uncertainty: Annotated[FiniteFloat, Field(ge=0, le=1)]
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["ENGINEERING_PIXEL_MEASUREMENT"] = "ENGINEERING_PIXEL_MEASUREMENT"
    image_measurement: Literal[True] = True
    measurement_source: Literal["RGB_PIXELS"] = "RGB_PIXELS"
    producer_version: str = PRODUCER_VERSION
    input_sha256: str
    status: Literal["DETECTED", "MERGED_OR_PARTIAL"]
    local_alternative_count: int = Field(ge=0)
    evidence_refs: tuple[str, ...]


class LocalTrack(PixelModel):
    local_track_id: str
    camera_id: str
    run_id: str
    model_id: str
    observation_ids: tuple[str, ...]
    timestamps: tuple[FiniteFloat, ...]
    status: Literal["COMPLETE", "FRAGMENTED"]
    missing_timestamps: tuple[FiniteFloat, ...]
    termination_reason: Literal["SEQUENCE_END", "LOST_OR_LEFT_VIEW"]


class FrameStatus(PixelModel):
    frame_ref: str
    camera_id: str
    timestamp: FiniteFloat
    status: Literal[
        "MEASURED", "NO_DETECTION", "AMBIGUOUS_COMPONENT", "MISSING_IMAGE", "INVALID_IMAGE",
        "HASH_MISMATCH",
    ]
    measurement_count: int = Field(ge=0)
    issue: str | None = None


class PerceptionResult(PixelModel):
    model_id: str
    run_id: str
    measurements: tuple[Measurement, ...]
    tracks: tuple[LocalTrack, ...]
    frame_statuses: tuple[FrameStatus, ...]
    input_manifest_sha256: str
    producer_sha256: str
    producer_version: str = PRODUCER_VERSION
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    image_measurement: Literal[True] = True
    complete: bool


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def frame_manifest_sha256(frames: Sequence[RGBFrame]) -> str:
    """Bind actual pixels and camera/time without persisting private locators."""
    return _digest([
        {"ref": frame.media_ref, "camera": frame.camera_id, "timestamp": frame.timestamp,
         "sha256": frame.sha256, "width": frame.width, "height": frame.height}
        for frame in sorted(frames, key=lambda row: (row.camera_id, row.timestamp, row.media_ref))
    ])


def _components(mask: NDArray[np.bool_]) -> list[tuple[int, int, int, int, NDArray[np.int64]]]:
    remaining = mask.copy()
    height, width = remaining.shape
    components: list[tuple[int, int, int, int, NDArray[np.int64]]] = []
    for raw_y, raw_x in zip(*np.nonzero(mask), strict=True):
        x, y = int(raw_x), int(raw_y)
        if not remaining[y, x]:
            continue
        remaining[y, x] = False
        queue = deque([(y, x)])
        pixels: list[tuple[int, int]] = []
        while queue:
            py, px = queue.popleft()
            pixels.append((py, px))
            for ny, nx in ((py - 1, px), (py + 1, px), (py, px - 1), (py, px + 1)):
                if 0 <= ny < height and 0 <= nx < width and remaining[ny, nx]:
                    remaining[ny, nx] = False
                    queue.append((ny, nx))
        if len(pixels) < 28:
            continue
        coordinates = np.asarray(pixels, dtype=np.int64)
        ymin, xmin = coordinates.min(axis=0)
        ymax, xmax = coordinates.max(axis=0)
        components.append((int(xmin), int(ymin), int(xmax) + 1, int(ymax) + 1, coordinates))
    return sorted(components, key=lambda item: (item[0], item[1]))


def produce_perception(
    frames: Sequence[RGBFrame], *, model_id: str, run_id: str,
) -> PerceptionResult:
    """Recompute measurements from RGB bytes, using a per-camera temporal median.

    This deliberately modest offline algorithm may merge objects, swap local
    identities and fragment tracks.  It reports those limits without filling
    missing measurements with projected or simulator answers.
    """
    if not model_id or not run_id:
        raise ValueError("model and run namespaces are required")
    identities = [(frame.camera_id, frame.timestamp) for frame in frames]
    refs = [frame.media_ref for frame in frames]
    if len(set(identities)) != len(identities) or len(set(refs)) != len(refs):
        raise ValueError("duplicate frame camera/time or reference")
    by_camera: dict[str, list[RGBFrame]] = defaultdict(list)
    images: dict[str, NDArray[np.uint8]] = {}
    statuses: dict[str, FrameStatus] = {}
    for frame in sorted(frames, key=lambda row: (row.camera_id, row.timestamp)):
        by_camera[frame.camera_id].append(frame)
        try:
            payload = frame.path.read_bytes()
        except FileNotFoundError:
            statuses[frame.media_ref] = FrameStatus(
                frame_ref=frame.media_ref, camera_id=frame.camera_id, timestamp=frame.timestamp,
                status="MISSING_IMAGE", measurement_count=0, issue="referenced RGB image missing",
            )
            continue
        if sha256(payload).hexdigest() != frame.sha256:
            statuses[frame.media_ref] = FrameStatus(
                frame_ref=frame.media_ref, camera_id=frame.camera_id, timestamp=frame.timestamp,
                status="HASH_MISMATCH", measurement_count=0, issue="RGB input hash mismatch",
            )
            continue
        try:
            with Image.open(BytesIO(payload)) as image:
                if image.mode != "RGB" or image.size != (frame.width, frame.height):
                    raise ValueError("expected configured RGB dimensions")
                images[frame.media_ref] = np.asarray(image, dtype=np.uint8).copy()
        except (OSError, ValueError):
            statuses[frame.media_ref] = FrameStatus(
                frame_ref=frame.media_ref, camera_id=frame.camera_id, timestamp=frame.timestamp,
                status="INVALID_IMAGE", measurement_count=0, issue="invalid RGB image",
            )

    measurements: list[Measurement] = []
    tracks: list[LocalTrack] = []
    for camera_id, camera_frames in sorted(by_camera.items()):
        valid_images = [images[row.media_ref] for row in camera_frames if row.media_ref in images]
        if not valid_images:
            continue
        shapes = {array.shape for array in valid_images}
        if len(shapes) != 1:
            raise ValueError("camera RGB dimensions changed within sequence")
        background = np.median(np.stack(valid_images), axis=0).astype(np.int16)
        # Only previous pixel measurements are used for local tracking.
        histories: dict[str, list[Measurement]] = {}
        for frame_index, frame in enumerate(camera_frames):
            if frame.media_ref not in images:
                continue
            rgb = images[frame.media_ref]
            difference = np.max(np.abs(rgb.astype(np.int16) - background), axis=2)
            components = _components(difference > 30)
            used_tracks: set[str] = set()
            ambiguous_frame = False
            for component_index, (xmin, ymin, xmax, ymax, coordinates) in enumerate(components):
                contact = ((xmin + xmax - 1) / 2.0, float(ymax - 1))
                possibilities: list[tuple[float, str]] = []
                for track_id, history in histories.items():
                    prior = history[-1]
                    dt = frame.timestamp - prior.timestamp
                    if track_id in used_tracks or not 0 < dt <= 0.61:
                        continue
                    distance = float(np.hypot(
                        contact[0] - prior.contact_pixel[0], contact[1] - prior.contact_pixel[1],
                    ))
                    if distance <= 28.0 * max(1.0, dt / 0.2):
                        possibilities.append((distance, track_id))
                possibilities.sort()
                if possibilities:
                    track_id = possibilities[0][1]
                else:
                    track_id = f"track:{model_id}:{run_id}:{camera_id}:{len(histories):04d}"
                    histories[track_id] = []
                used_tracks.add(track_id)
                ys, xs = coordinates[:, 0], coordinates[:, 1]
                color = rgb[ys, xs].mean(axis=0)
                merged = xmax - xmin > 32 or ymax - ymin < 20
                ambiguous_frame |= merged
                measurement = Measurement(
                    observation_id=(
                        f"pixel:{model_id}:{run_id}:{camera_id}:{frame_index:04d}:"
                        f"{component_index:02d}"
                    ),
                    local_track_id=track_id, camera_id=camera_id, run_id=run_id, model_id=model_id,
                    timestamp=frame.timestamp, frame_ref=frame.media_ref,
                    bbox_xyxy=(float(xmin), float(ymin), float(xmax), float(ymax)),
                    contact_pixel=contact,
                    appearance=(float(color[0]), float(color[1]), float(color[2])),
                    uncertainty=min(1.0, 0.25 + 0.35 * merged + 0.15 * (len(possibilities) > 1)),
                    input_sha256=frame.sha256,
                    status="MERGED_OR_PARTIAL" if merged else "DETECTED",
                    local_alternative_count=max(0, len(possibilities) - 1),
                    evidence_refs=(frame.media_ref,),
                )
                histories[track_id].append(measurement)
                measurements.append(measurement)
            statuses[frame.media_ref] = FrameStatus(
                frame_ref=frame.media_ref, camera_id=camera_id, timestamp=frame.timestamp,
                status=("AMBIGUOUS_COMPONENT" if ambiguous_frame else
                        "MEASURED" if components else "NO_DETECTION"),
                measurement_count=len(components),
                issue=("component may contain merged or partial objects"
                       if ambiguous_frame else None),
            )
        for track_id, history in histories.items():
            timestamps = tuple(row.timestamp for row in history)
            missing = tuple(row.timestamp for row in camera_frames
                            if timestamps[0] < row.timestamp < timestamps[-1]
                            and row.timestamp not in timestamps)
            tracks.append(LocalTrack(
                local_track_id=track_id, camera_id=camera_id, run_id=run_id, model_id=model_id,
                observation_ids=tuple(row.observation_id for row in history), timestamps=timestamps,
                status="FRAGMENTED" if missing else "COMPLETE", missing_timestamps=missing,
                termination_reason=("SEQUENCE_END" if timestamps[-1] == camera_frames[-1].timestamp
                                    else "LOST_OR_LEFT_VIEW"),
            ))
    ordered_statuses = tuple(statuses[row.media_ref] for row in sorted(
        frames, key=lambda row: (row.camera_id, row.timestamp),
    ))
    return PerceptionResult(
        model_id=model_id, run_id=run_id, measurements=tuple(measurements), tracks=tuple(tracks),
        frame_statuses=ordered_statuses, input_manifest_sha256=frame_manifest_sha256(frames),
        producer_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        complete=all(row.status not in {"MISSING_IMAGE", "HASH_MISMATCH", "INVALID_IMAGE"}
                     for row in ordered_statuses),
    )
