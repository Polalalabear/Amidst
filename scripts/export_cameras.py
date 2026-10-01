"""Export the 29 research cameras read-only; do not render or save any .blend."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from amidst.domain.camera import Camera

REPO_ROOT = Path(__file__).resolve().parents[1]


def _fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return digest, stat.st_size, stat.st_mtime_ns


def _write_catalog(path: Path, catalog: dict[str, Any], *, overwrite: bool) -> None:
    temporary = None
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(catalog, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--blend", type=Path, default=REPO_ROOT / "blender/working/school_v2_research.blend"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, default=29)
    parser.add_argument("--blender-bin", help="Blender CLI path; otherwise BLENDER_BIN/PATH")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    source, output = args.blend.resolve(), args.output
    if source.suffix.lower() != ".blend" or not source.is_file():
        parser.error("--blend must be an existing read-only .blend asset")
    if output.suffix.lower() != ".json" or output.resolve().suffix.lower() != ".json":
        parser.error("camera output must use a .json destination; Blender assets are immutable")
    if output.resolve() == source:
        parser.error("output must not overwrite the input asset")
    if output.exists() and not args.overwrite:
        parser.error("output already exists; choose a new destination or --overwrite")
    if args.expected_count < 1:
        parser.error("--expected-count must be positive")
    executable = args.blender_bin or os.environ.get("BLENDER_BIN") or shutil.which("blender")
    if executable is None:
        installed = Path("/Applications/Blender.app/Contents/MacOS/blender")
        executable = str(installed) if installed.is_file() else None
    if executable is None:
        parser.error("Blender unavailable; provide --blender-bin or BLENDER_BIN")
    fingerprint = _fingerprint(source)
    with tempfile.TemporaryDirectory(prefix="amidst-camera-export-") as temporary_dir:
        raw_output = Path(temporary_dir) / "raw_cameras.json"
        code = f"""
import json
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "src")!r})
import bpy
from amidst.simulation.blender_camera import extract_camera_catalog
cameras = extract_camera_catalog(bpy.context.scene, expected_count={args.expected_count!r})
Path({str(raw_output)!r}).write_text(json.dumps(cameras, allow_nan=False), encoding='utf-8')
print('BLENDER_CAMERA_EXPORT_OK')
"""
        command = [
            executable,
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "-noaudio",
            str(source),
            "--python-exit-code",
            "2",
            "--python-expr",
            code,
        ]
        try:
            completed = subprocess.run(
                command, check=True, capture_output=True, text=True, timeout=120
            )
        finally:
            if _fingerprint(source) != fingerprint:
                raise RuntimeError("read-only Blender asset changed during camera extraction")
        if "BLENDER_CAMERA_EXPORT_OK" not in completed.stdout:
            raise RuntimeError("Blender did not confirm camera extraction")
        raw_cameras = json.loads(raw_output.read_text(encoding="utf-8"))
    cameras = [Camera.model_validate(raw) for raw in raw_cameras]
    if len(cameras) != args.expected_count or len({camera.camera_id for camera in cameras}) != len(
        cameras
    ):
        raise ValueError("camera catalog count/identity validation failed")
    _write_catalog(
        output,
        {
            "data_kind": "SYNTHETIC",
            "source_asset_name": source.name,
            "source_asset_sha256": fingerprint[0],
            "camera_count": len(cameras),
            "cameras": [camera.model_dump(mode="json") for camera in cameras],
        },
        overwrite=args.overwrite,
    )
    print(f"Exported {len(cameras)} CAM_* cameras to {output}; source asset unchanged")


if __name__ == "__main__":
    main()
