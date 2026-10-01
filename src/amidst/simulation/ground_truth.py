"""Deterministic synthetic paths, restricted to simulation/export and evaluation.

Sample times include the rate grid anchored at the first keyframe and every
keyframe endpoint. Interior metadata is the explicitly configured left keyframe
metadata; it never guesses floors/zones from position. Velocity is right-handed
at a corner, except the final sample uses the preceding segment velocity.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import tempfile
from bisect import bisect_right
from fractions import Fraction
from pathlib import Path

from amidst.domain.ground_truth import GroundTruthSample, GroundTruthTrajectory, TrajectoryConfig
from amidst.simulation.blender_target import MAX_BLENDER_FRAME


def _asset_fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return digest, stat.st_size, stat.st_mtime_ns


def sample_trajectory(
    config: TrajectoryConfig, *, max_samples: int = 1_000_000
) -> GroundTruthTrajectory:
    """Sample a configured piecewise-linear path without consuming random state."""
    if max_samples < 2:
        raise ValueError("max_samples must be at least two")
    times = tuple(Fraction(str(keyframe.timestamp)) for keyframe in config.keyframes)
    first, last = times[0], times[-1]
    grid_intervals = int((last - first) * config.sample_rate_hz)
    if grid_intervals + 1 > max_samples or len(times) > max_samples:
        raise ValueError("trajectory exceeds max_samples")
    sample_times = {first + Fraction(i, config.sample_rate_hz) for i in range(grid_intervals + 1)}
    sample_times.update(times)
    if len(sample_times) > max_samples:
        raise ValueError("trajectory exceeds max_samples after including keyframe endpoints")

    samples: list[GroundTruthSample] = []
    for timestamp in sorted(sample_times):
        keyframe_index = bisect_right(times, timestamp) - 1
        segment_index = min(keyframe_index, len(times) - 2)
        start, end = config.keyframes[segment_index : segment_index + 2]
        duration = float(times[segment_index + 1] - times[segment_index])
        alpha = float(
            (timestamp - times[segment_index]) / (times[segment_index + 1] - times[segment_index])
        )
        position = tuple(
            a + alpha * (b - a) for a, b in zip(start.position, end.position, strict=True)
        )
        velocity = tuple(
            (b - a) / duration for a, b in zip(start.position, end.position, strict=True)
        )
        if not all(math.isfinite(value) for value in (*position, *velocity)):
            raise ValueError("trajectory interpolation produced a non-finite coordinate/velocity")
        metadata = config.keyframes[keyframe_index]
        samples.append(
            GroundTruthSample(
                timestamp=float(timestamp),
                position=(position[0], position[1], position[2]),
                velocity=(velocity[0], velocity[1], velocity[2]),
                floor_id=metadata.floor_id,
                zone_id=metadata.zone_id,
                semantic_region=metadata.semantic_region,
            )
        )
    return GroundTruthTrajectory(
        trajectory_id=config.trajectory_id,
        target_id=config.target_id,
        scene_id=config.scene_id,
        random_seed=config.random_seed,
        sample_rate_hz=config.sample_rate_hz,
        samples=tuple(samples),
    )


def blender_evaluated_trajectory(
    config: TrajectoryConfig,
    *,
    blender_binary: str | None = None,
    blend_path: Path | None = None,
    frame_rate_hz: float = 30.0,
    max_samples: int = 1_000_000,
    position_tolerance_m: float = 1e-3,
) -> GroundTruthTrajectory:
    """Export actual Blender evaluated world positions, never render or save.

    Timestamps/metadata and the piecewise-linear derivative velocity originate
    from the configured path. Positions originate from Blender's evaluated
    matrix_world and therefore retain Blender's numerical precision. A supplied
    scene is loaded read-only; otherwise a fresh factory scene is used. This does
    not assert that a configured path is walkable in any school building.
    """
    if not math.isfinite(frame_rate_hz) or frame_rate_hz <= 0:
        raise ValueError("frame_rate_hz must be finite and positive")
    if not math.isfinite(position_tolerance_m) or position_tolerance_m <= 0:
        raise ValueError("position_tolerance_m must be finite and positive")
    analytic = sample_trajectory(config, max_samples=max_samples)
    final_frame = 1.0 + analytic.samples[-1].timestamp * frame_rate_hz
    if not math.isfinite(final_frame) or final_frame > MAX_BLENDER_FRAME:
        raise ValueError("trajectory exceeds Blender's supported frame domain")
    executable = blender_binary or os.environ.get("BLENDER_BIN") or shutil.which("blender")
    if executable is None:
        installed = Path("/Applications/Blender.app/Contents/MacOS/blender")
        executable = str(installed) if installed.is_file() else None
    if executable is None:
        raise FileNotFoundError("Blender CLI unavailable; set BLENDER_BIN or --blender-bin")
    if blend_path is not None:
        blend_path = blend_path.resolve()
        if blend_path.suffix.lower() != ".blend":
            raise ValueError("read-only scene must be a .blend file")
        if not blend_path.is_file():
            raise FileNotFoundError(blend_path)
    source_dir = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="amidst-ground-truth-") as temporary_dir:
        input_path = Path(temporary_dir) / "configured_samples.json"
        output_path = Path(temporary_dir) / "evaluated_positions.json"
        input_path.write_text(analytic.model_dump_json(), encoding="utf-8")
        code = f"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, {str(source_dir)!r})
import bpy
from amidst.simulation.blender_target import animated_target_proxy, evaluated_proxy_positions
data = json.loads(Path({str(input_path)!r}).read_text(encoding='utf-8'))
trajectory = SimpleNamespace(samples=[SimpleNamespace(**sample) for sample in data['samples']])
with animated_target_proxy(bpy.context.scene, trajectory, frame_rate_hz={frame_rate_hz!r}) as proxy:
    positions = evaluated_proxy_positions(bpy.context.scene, proxy,
        [sample.timestamp for sample in trajectory.samples], frame_rate_hz={frame_rate_hz!r})
Path({str(output_path)!r}).write_text(json.dumps(positions, allow_nan=False), encoding='utf-8')
print('BLENDER_GROUND_TRUTH_EXPORT_OK')
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
        command.extend(["--python-exit-code", "2", "--python-expr", code])
        source_fingerprint = _asset_fingerprint(blend_path) if blend_path is not None else None
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=120, check=True
            )
        finally:
            if blend_path is not None and _asset_fingerprint(blend_path) != source_fingerprint:
                raise RuntimeError("read-only Blender source changed during ground-truth export")
        if "BLENDER_GROUND_TRUTH_EXPORT_OK" not in result.stdout:
            raise RuntimeError("Blender did not confirm ground-truth export")
        positions = json.loads(output_path.read_text(encoding="utf-8"))
    if len(positions) != len(analytic.samples):
        raise ValueError("Blender returned an inconsistent sample count")
    payload = analytic.model_dump(mode="json")
    for sample_payload, position in zip(payload["samples"], positions, strict=True):
        if len(position) != 3 or not all(math.isfinite(value) for value in position):
            raise ValueError("Blender returned a non-finite or invalid world position")
        if math.dist(sample_payload["position"], position) > position_tolerance_m:
            raise ValueError(
                "Blender evaluated path diverges from the configuration beyond tolerance"
            )
        sample_payload["position"] = position
    payload["sample_source"] = "BLENDER_EVALUATED"
    if blend_path is not None:
        assert source_fingerprint is not None
        payload["source_asset_name"] = blend_path.name
        payload["source_asset_sha256"] = source_fingerprint[0]
    return GroundTruthTrajectory.model_validate(payload)


def _publish_text(path: Path, contents: str, *, overwrite: bool) -> Path:
    """Publish a complete file atomically, refusing existing paths by default."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, path)
        else:
            # A hard link atomically enforces exclusive creation, including races.
            os.link(temporary, path)
        return path
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export_ground_truth_json(
    trajectory: GroundTruthTrajectory, path: Path, *, overwrite: bool = False
) -> Path:
    """Export the simulation-only schema, including explicit SYNTHETIC provenance."""
    if path.suffix.lower() != ".json" or path.resolve().suffix.lower() != ".json":
        raise ValueError("ground-truth JSON output must use a .json destination")
    return _publish_text(path, trajectory.model_dump_json(indent=2) + "\n", overwrite=overwrite)


def export_ground_truth_csv(
    trajectory: GroundTruthTrajectory, path: Path, *, overwrite: bool = False
) -> Path:
    """Export all coordinates, velocities, metadata and source labels to CSV."""
    if path.suffix.lower() != ".csv" or path.resolve().suffix.lower() != ".csv":
        raise ValueError("ground-truth CSV output must use a .csv destination")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "trajectory_id",
            "target_id",
            "scene_id",
            "data_kind",
            "sample_source",
            "source_asset_name",
            "source_asset_sha256",
            "random_seed",
            "sample_rate_hz",
            "timestamp",
            "X",
            "Y",
            "Z",
            "VX",
            "VY",
            "VZ",
            "floor_id",
            "zone_id",
            "semantic_region",
            "provenance",
        ]
    )
    for sample in trajectory.samples:
        writer.writerow(
            [
                trajectory.trajectory_id,
                trajectory.target_id,
                trajectory.scene_id,
                trajectory.data_kind,
                trajectory.sample_source,
                trajectory.source_asset_name,
                trajectory.source_asset_sha256,
                trajectory.random_seed,
                trajectory.sample_rate_hz,
                sample.timestamp,
                *sample.position,
                *sample.velocity,
                sample.floor_id,
                sample.zone_id,
                sample.semantic_region,
                sample.provenance.value,
            ]
        )
    return _publish_text(path, buffer.getvalue(), overwrite=overwrite)
