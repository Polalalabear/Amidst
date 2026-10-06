"""Publish a source-hash-verified read-only Blender geometry diagnostic report."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# The bundled Blender audit scripts remain source-checkout tools.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from run_scene_audit import sha256  # noqa: E402

from amidst.portability.blender import resolve_blender_executable  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path, default=Path("blender/school_v2.blend"))
    parser.add_argument("--blender", help="Blender CLI path; otherwise BLENDER_BIN/PATH")
    parser.add_argument("--scope", choices=("structural", "all"), default="structural")
    parser.add_argument(
        "--output", type=Path, default=Path("data/scene_audit/school_v2_geometry_audit.json")
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    blend = (repo_root / args.blend).resolve()
    output = (repo_root / args.output).resolve()
    if not blend.is_file():
        raise FileNotFoundError(blend)
    if output.suffix != ".json" or output == blend:
        raise ValueError("output must be a separate JSON report, never the source asset")
    before_hash = sha256(blend)
    before_stat = blend.stat()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".amidst-geometry-audit-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / "geometry.json"
        command = [
            resolve_blender_executable(args.blender),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "-noaudio",
            str(blend),
            "--python-exit-code",
            "2",
            "--python",
            str(Path(__file__).with_name("audit_blender_geometry.py")),
            "--",
            "--output",
            str(staged),
            "--scope",
            args.scope,
        ]
        try:
            result = subprocess.run(
                command, cwd=repo_root, capture_output=True, text=True, timeout=600
            )
        finally:
            after_hash = sha256(blend)
            after_stat = blend.stat()
            if (
                before_hash != after_hash
                or before_stat.st_size != after_stat.st_size
                or before_stat.st_mtime_ns != after_stat.st_mtime_ns
            ):
                raise RuntimeError("source asset changed during the read-only diagnostic")
        if result.returncode:
            raise RuntimeError(f"Blender diagnostic failed:\n{result.stderr[-2000:]}")
        report = json.loads(staged.read_text(encoding="utf-8"))
        report.update(
            {
                "schema_version": "1.0.0",
                "audit_kind": "READ_ONLY_GEOMETRY_DIAGNOSTIC",
                "source": {
                    "filename": blend.name,
                    "sha256_before": before_hash,
                    "sha256_after": after_hash,
                    "size_bytes": before_stat.st_size,
                },
                "read_only_contract": {
                    "source_hash_unchanged": True,
                    "source_size_unchanged": True,
                    "source_mtime_unchanged": True,
                    "save_operation_performed": False,
                    "render_operation_performed": False,
                },
                "interpretation_boundary": {
                    "navigation_geometry_approved": False,
                    "raw_coverage_is_walkability": False,
                    "annotation_boxes_are_collision_surfaces": False,
                    "stair_absence_globally_proven": False,
                },
            }
        )
        staged.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )
        os.replace(staged, output)
    print(f"geometry diagnostic: {output}")
    print(f"source SHA-256 unchanged: {before_hash}")


if __name__ == "__main__":
    main()
