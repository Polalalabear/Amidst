"""Encode the new diagnostic body-motion PNGs as a ten-second local GIF."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import PIL
from PIL import Image, ImageSequence

HERE = Path(__file__).resolve().parent
FRAMES = HERE / "frames/motion_context"


def main() -> None:
    manifest_path = FRAMES / "motion_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest["gt_used"] is not False
        or manifest["result_type"] != "DIAGNOSTIC"
        or manifest["sampling_hz"] != 5
        or manifest["duration_seconds"] != 10
        or len(manifest["frames"]) != 50
    ):
        raise ValueError("GIF requires the locked ten-second diagnostic sequence")
    paths = []
    for index, row in enumerate(manifest["frames"]):
        relative = row["path"]
        if not isinstance(relative, str) or not re.fullmatch(r"motion_\d{3}\.png", relative):
            raise ValueError("motion images must be local generated PNG filenames")
        if row["frame_id"] != index or abs(row["timestamp"] - index / 5) > 1e-9:
            raise ValueError("motion frame order/timing changed")
        paths.append(FRAMES / relative)
    if any(path.is_symlink() or path.resolve().parent != FRAMES.resolve() for path in paths):
        raise ValueError("motion image paths cannot redirect outside the local render directory")
    for path, row in zip(paths, manifest["frames"], strict=True):
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("motion PNG hash changed: " + path.name)
    output = FRAMES / "motion_preview.gif"
    receipt = FRAMES / "gif_manifest.json"
    if output.exists() or receipt.exists():
        raise ValueError("GIF output must be fresh; preserve the existing preview")
    images: list[Image.Image] = []
    # Retain indexed previews instead of floating-point caches for all 50 frames.
    for path in paths:
        with Image.open(path) as rendered:
            preview = rendered.resize((800, 500), Image.Resampling.LANCZOS).convert("RGB")
            images.append(
                preview.quantize(
                    colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
                )
            )
    images[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=200,
        loop=0,
        disposal=2,
        optimize=True,
    )
    for image in images:
        image.close()
    with Image.open(output) as encoded:
        delays = [
            int(frame.info.get("duration", 0)) // 10 for frame in ImageSequence.Iterator(encoded)
        ]
    if sum(delays) != 1000:
        raise ValueError("encoded GIF must have exactly ten seconds per loop")
    document = {
        "schema_version": "phase1-human-review-motion-gif-v1",
        "result_type": "DIAGNOSTIC",
        "gt_used": False,
        "physical_authority_changed": False,
        "position_or_timing_changed": False,
        "source_motion_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "source_frame_count": 50,
        "source_sampling_hz": 5,
        "encoded_duration_seconds": sum(delays) / 100,
        "encoded_frame_delays_centiseconds": delays,
        "display_size": [800, 500],
        "lossy_palette_preview": True,
        "full_resolution_source": "player.html",
        "encoder_version": "Pillow " + PIL.__version__,
        "encoder_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "command_argv": ["uv", "run", "python", "human_review/make_motion_gif.py"],
        "artifact": {
            "path": output.name,
            "bytes": output.stat().st_size,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        },
    }
    receipt.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(document["artifact"]))


if __name__ == "__main__":
    main()
