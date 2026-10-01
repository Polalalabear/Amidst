"""Export actual CameraCalibration/Pose/frustums; never render or save a .blend."""

from __future__ import annotations

import argparse
from pathlib import Path

from amidst.simulation.camera_calibration import (
    export_camera_calibration_json,
    read_camera_calibration_catalog,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", type=Path, default=Path("blender/school_v2.blend"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--camera-config-version", required=True)
    parser.add_argument("--expected-count", type=int, default=29)
    parser.add_argument("--blender-bin")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".json" or args.output.resolve().suffix.lower() != ".json":
        parser.error("calibration output must be .json; Blender assets are immutable")
    if args.output.resolve() == args.blend.resolve():
        parser.error("camera calibration output must not overwrite the Blender source")
    if args.output.exists():
        parser.error("calibration output already exists; choose a fresh destination")
    if args.expected_count < 1:
        parser.error("expected camera count must be positive")
    catalog = read_camera_calibration_catalog(
        args.blend, camera_config_version=args.camera_config_version,
        blender_binary=args.blender_bin, expected_count=args.expected_count,
    )
    export_camera_calibration_json(catalog, args.output)
    print(f"Exported {len(catalog.cameras)} actual CAM_* calibrations to {args.output}; "
          f"source unchanged; content SHA-256 {catalog.calibration_content_sha256}")


if __name__ == "__main__":
    main()
