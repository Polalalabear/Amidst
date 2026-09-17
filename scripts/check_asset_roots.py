#!/usr/bin/env python3
"""Validate local Blender roots without emitting their physical paths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BLENDER_SCRIPTS = ROOT / "blender" / "scripts"
if str(BLENDER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(BLENDER_SCRIPTS))

from asset_guards import TaskOutputLock, source_root_is_writable  # noqa: E402
from asset_paths import (  # noqa: E402
    AssetPathError,
    ROOT_DEFINITIONS,
    configured_root,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--require-read-only-source", action="store_true")
    parser.add_argument("--probe-output", action="store_true")
    parser.add_argument("--probe-task-id", default="asset-root-health-check")
    return parser.parse_args()


def main() -> int:
    args = arguments()
    records: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    roots: dict[str, Path] = {}
    for name, definition in ROOT_DEFINITIONS.items():
        try:
            path = configured_root(
                name,
                repo_root=ROOT,
                config_path=args.config,
                require_exists=True,
            )
        except AssetPathError as error:
            failures.append({"root": name, "reason": error.code})
            continue
        roots[name] = path
        writable = source_root_is_writable(path)
        records.append(
            {
                "access": definition.access,
                "exists": True,
                "root": name,
                "writable": writable,
            }
        )
        if (
            args.require_read_only_source
            and definition.access == "read_only"
            and writable
        ):
            failures.append({"root": name, "reason": "SOURCE_ROOT_WRITABLE"})
    if args.probe_output and "blender-output" in roots:
        try:
            with TaskOutputLock(roots["blender-output"], args.probe_task_id) as lock:
                probe = lock.task_directory / ".write-probe"
                probe.write_bytes(b"amidst-output-probe")
                probe.unlink()
        except (OSError, RuntimeError, AssetPathError) as error:
            failures.append(
                {"root": "blender-output", "reason": type(error).__name__}
            )
    result = {
        "failure_count": len(failures),
        "failures": failures,
        "physical_paths_serialized": False,
        "roots": records,
        "status": "PASS" if not failures else "FAIL",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
