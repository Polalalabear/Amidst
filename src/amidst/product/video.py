"""Explicit local presentation encoding of registered RGB; original pixels remain inputs."""

from __future__ import annotations

import hashlib
import json
import subprocess
from bisect import bisect_left
from io import BytesIO
from pathlib import Path
from typing import Literal, cast

from PIL import Image
from pydantic import Field

from amidst.domain.common import DomainModel
from amidst.engineering.access import digest
from amidst.engineering.registry import RegistryStore, ResourceScope, opaque_ref, scope_parts


class VideoArtifact(DomainModel):
    video_ref: str
    camera_ref: str
    camera_id: str
    relative_path: str
    sha256: str
    byte_count: int
    input_frames_sha256: str
    source_frame_refs: tuple[str, ...]
    start_time: float
    end_time: float
    frame_count: int
    fps: float
    width: int
    height: int
    sampling: Literal["NEAREST_REGISTERED_RGB_FRAME_HOLD"] = "NEAREST_REGISTERED_RGB_FRAME_HOLD"
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    annotations: Literal["NONE"] = "NONE"
    codec: Literal["H264_YUV420P_PRESENTATION_ONLY"] = "H264_YUV420P_PRESENTATION_ONLY"


class VideoManifest(DomainModel):
    schema_version: Literal["product.video.v1"] = "product.video.v1"
    scope: ResourceScope
    registry_sha256: str
    encoder_sha256: str
    encoder_version: str
    fps: float = Field(gt=0)
    artifacts: tuple[VideoArtifact, ...]


def encode_videos(store: RegistryStore, scope: ResourceScope, output: Path, *,
                  fps: float = 15.0) -> VideoManifest:
    from imageio_ffmpeg import get_ffmpeg_exe, get_ffmpeg_version  # type: ignore[import-untyped]

    encoder = Path(cast(str, get_ffmpeg_exe()))
    encoder_hash = hashlib.sha256(encoder.read_bytes()).hexdigest()
    implementation_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for camera in store.list_cameras(scope):
        frames = sorted((f for f in store.query_frames(scope) if f.camera_id == camera.camera_id),
                        key=lambda frame: frame.timestamp)
        if not frames:
            continue
        if any(f.annotations != "NONE" or f.purpose != "RGB_SEQUENCE" for f in frames):
            raise ValueError("VIDEO_SOURCE_DENIED")
        input_hash = digest([(f.media_ref, f.timestamp, f.sha256) for f in frames])
        ref = opaque_ref("video", *scope_parts(scope), camera.camera_ref, input_hash, str(fps),
                         encoder_hash, implementation_hash)
        destination = output / (ref.replace(":", "-") + ".mp4")
        cache_receipt = destination.with_suffix(".json")
        frame_count = round((frames[-1].timestamp - frames[0].timestamp) * fps) + 1
        with Image.open(BytesIO(store.media_bytes(scope, frames[0].media_ref))) as decoded:
            width, height = decoded.size
        if destination.exists():
            if destination.is_symlink() or not cache_receipt.is_file():
                raise ValueError("VIDEO_CACHE_UNCERTIFIED")
            saved = VideoArtifact.model_validate_json(cache_receipt.read_bytes())
            if (saved.video_ref != ref or saved.input_frames_sha256 != input_hash
                or saved.source_frame_refs != tuple(f.media_ref for f in frames)
                or saved.sha256 != hashlib.sha256(destination.read_bytes()).hexdigest()):
                raise ValueError("VIDEO_CACHE_MISMATCH")
        if not destination.exists():
            command = [str(encoder), "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                       "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0", "-an",
                       "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-threads", "1",
                       "-fflags", "+bitexact", "-flags:v", "+bitexact", "-map_metadata", "-1",
                       "-movflags", "+faststart", str(destination)]
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.PIPE)
            assert process.stdin is not None and process.stderr is not None
            times = [f.timestamp for f in frames]
            previous_ref, pixel_bytes = "", b""
            try:
                for index in range(frame_count):
                    time = frames[0].timestamp + index / fps
                    insertion = bisect_left(times, time)
                    options = frames[max(0, insertion - 1):min(len(frames), insertion + 1)]
                    nearest = min(options, key=lambda f: (abs(f.timestamp - time), f.timestamp))
                    if previous_ref != nearest.media_ref:
                        source_bytes = store.media_bytes(scope, nearest.media_ref)
                        with Image.open(BytesIO(source_bytes)) as image:
                            if image.size != (width, height):
                                raise ValueError("VIDEO_SOURCE_RESOLUTION_MISMATCH")
                            pixel_bytes = image.convert("RGB").tobytes()
                        previous_ref = nearest.media_ref
                    process.stdin.write(pixel_bytes)
                process.stdin.close()
                process.stderr.read()
                if process.wait() != 0:
                    raise ValueError("VIDEO_ENCODING_FAILED")
            except (OSError, ValueError):
                process.kill()
                process.wait()
                raise ValueError("VIDEO_ENCODING_FAILED") from None
            finally:
                process.stderr.close()
        artifact = VideoArtifact(
            video_ref=ref, camera_ref=camera.camera_ref, camera_id=camera.camera_id,
            relative_path=destination.name,
            sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
            byte_count=destination.stat().st_size, input_frames_sha256=input_hash,
            source_frame_refs=tuple(f.media_ref for f in frames), start_time=frames[0].timestamp,
            end_time=frames[-1].timestamp, frame_count=frame_count, fps=fps,
            width=width, height=height,
        )
        if not cache_receipt.exists():
            cache_receipt.write_text(json.dumps(artifact.model_dump(mode="json"),
                                               indent=2, sort_keys=True) + "\n")
        artifacts.append(artifact)
    return VideoManifest(scope=scope, registry_sha256=store.registry.sha256,
                         encoder_sha256=encoder_hash,
                         encoder_version=cast(str, get_ffmpeg_version()), fps=fps,
                         artifacts=tuple(artifacts))
