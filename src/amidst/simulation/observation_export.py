"""Sanitized synthetic observation production, separate from truth artifacts."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from amidst.domain.camera import Camera
from amidst.domain.common import Vec3
from amidst.domain.evidence import ObservationFrame
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.portability.blender import resolve_blender_executable
from amidst.simulation.raycast_types import Raycaster, RaycastResult
from amidst.simulation.visibility import observe_point

GEOMETRY_POLICY = "EVALUATED_VIEWPORT_FIXED_FRAME_POINT_RAYCAST"


def observe_trajectory(
    trajectory: GroundTruthTrajectory,
    cameras: tuple[Camera, ...],
    raycaster: Raycaster,
    *,
    max_frames: int = 100000,
) -> tuple[ObservationFrame, ...]:
    """Simulation is the only producer reading hidden motion; output is 2D-only."""
    if not cameras or max_frames < 1 or len(trajectory.samples) * len(cameras) > max_frames:
        raise ValueError("observation export requires cameras and a bounded frame count")
    if len({camera.camera_id for camera in cameras}) != len(cameras):
        raise ValueError("camera IDs must be unique")
    return tuple(
        observe_point(
            camera,
            sample.position,
            timestamp=sample.timestamp,
            target_id=trajectory.target_id,
            frame_id=frame_id,
            raycaster=raycaster,
        )
        for frame_id, sample in enumerate(trajectory.samples)
        for camera in sorted(cameras, key=lambda item: item.camera_id)
    )


def _fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return digest, stat.st_size, stat.st_mtime_ns


def blender_ray_queries(
    queries: tuple[tuple[Vec3, Vec3], ...],
    *,
    blend_path: Path | None = None,
    blender_binary: str | None = None,
    max_candidates: int = 10000,
) -> tuple[RaycastResult, ...]:
    """Query the loaded scene's fixed evaluated frame, without saving or rendering."""
    if not queries:
        return ()
    if len(queries) > 100000 or max_candidates < 1:
        raise ValueError("ray query batch/collider budget is invalid")
    executable = resolve_blender_executable(blender_binary)
    if blend_path is not None and (
        not blend_path.is_file() or blend_path.suffix.lower() != ".blend"
    ):
        raise ValueError("scene must be an existing read-only .blend")
    fingerprint = _fingerprint(blend_path) if blend_path is not None else None
    with tempfile.TemporaryDirectory(prefix="amidst-visibility-") as temporary:
        inputs, outputs = Path(temporary) / "queries.json", Path(temporary) / "results.json"
        inputs.write_text(json.dumps(queries, allow_nan=False), encoding="utf-8")
        source_dir = Path(__file__).resolve().parents[2]
        code = f"""
import sys,json
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,{str(source_dir)!r})
import bpy
from amidst.simulation.blender_visibility import BlenderMeshRaycaster
caster=BlenderMeshRaycaster(bpy.context.scene,max_candidates={max_candidates!r})
queries=json.loads(Path({str(inputs)!r}).read_text())
rows=[asdict(caster(tuple(origin),tuple(target))) for origin,target in queries]
Path({str(outputs)!r}).write_text(json.dumps(rows,allow_nan=False))
print('BLENDER_VISIBILITY_EXPORT_OK')
"""
        command = [
            executable,
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "-noaudio",
        ]
        if blend_path is not None:
            command.append(str(blend_path.resolve()))
        command += ["--python-exit-code", "2", "--python-expr", code]
        try:
            result = subprocess.run(
                command, check=True, capture_output=True, text=True, timeout=120
            )
        finally:
            if blend_path is not None and _fingerprint(blend_path) != fingerprint:
                raise RuntimeError("source changed during read-only visibility export")
        if "BLENDER_VISIBILITY_EXPORT_OK" not in result.stdout:
            raise RuntimeError("Blender did not confirm visibility export")
        raw = json.loads(outputs.read_text())
    if len(raw) != len(queries):
        raise ValueError("raycast batch result count mismatch")
    results = tuple(RaycastResult(**row) for row in raw)
    if any(
        row.reason not in {"CLEAR", "OCCLUDED", "GEOMETRY_UNCERTAIN", "RAYCAST_LIMIT"}
        or type(row.occluded) is not bool
        for row in results
    ):
        raise ValueError("invalid physical raycast response")
    return results
