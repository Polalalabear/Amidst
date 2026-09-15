#!/usr/bin/env python3
"""Create or verify a portable, checksum-based migration manifest."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
from typing import Any, Iterable


SCHEMA_NAME = "amidst.migration_manifest"
SCHEMA_VERSION = "0.1.0"
CLASSIFICATIONS = {"PUBLIC_ALLOWED", "PRIVATE_ONLY", "REVIEW_REQUIRED"}
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}
EXCLUDED_FILE_NAMES = {".DS_Store"}
EXCLUDED_FILE_SUFFIXES = {".pyc", ".pyo"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(value: str) -> PurePosixPath:
    if "\\" in value:
        raise ValueError(f"Path must use POSIX separators: {value}")
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Path must be repository-relative: {value}")
    if path.parts[0].endswith(":") or ".git" in path.parts:
        raise ValueError(f"Path must not contain a drive or Git metadata: {value}")
    return path


def is_reproducible_local_artifact(path: PurePosixPath) -> bool:
    return (
        bool(EXCLUDED_DIRECTORY_NAMES.intersection(path.parts))
        or path.name in EXCLUDED_FILE_NAMES
        or Path(path.name).suffix.casefold() in EXCLUDED_FILE_SUFFIXES
    )


def parse_entry(value: str) -> dict[str, str]:
    classification, separator, path = value.partition(":")
    if not separator or classification not in CLASSIFICATIONS:
        raise ValueError(
            "--entry must be CLASSIFICATION:repository/relative/path"
        )
    return {"classification": classification, "path": path}


def load_inventory(path: Path | None, command_entries: list[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    if path is not None:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("entries"), list):
            raise ValueError("Inventory must be a JSON object containing entries")
        for entry in value["entries"]:
            if not isinstance(entry, dict):
                raise ValueError("Every inventory entry must be an object")
            entries.append(
                {
                    "classification": str(entry.get("classification", "")),
                    "path": str(entry.get("path", "")),
                }
            )
    entries.extend(parse_entry(value) for value in command_entries)
    if not entries:
        raise ValueError("Provide --inventory or at least one --entry")
    for entry in entries:
        if entry["classification"] not in CLASSIFICATIONS:
            raise ValueError(f"Invalid classification for {entry['path']}")
        portable_path(entry["path"])
    return entries


def find_source(relative: PurePosixPath, roots: list[Path]) -> Path:
    for root in roots:
        candidate = root.joinpath(*relative.parts)
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Migration source is missing: {relative.as_posix()}")


def expand_entries(
    entries: Iterable[dict[str, str]], roots: list[Path]
) -> list[dict[str, Any]]:
    expanded: dict[str, dict[str, Any]] = {}
    for requested in entries:
        relative = portable_path(requested["path"])
        if is_reproducible_local_artifact(relative):
            raise ValueError(f"Cache or local metadata must not be migrated: {relative}")
        source = find_source(relative, roots)
        candidates = [source]
        if source.is_dir():
            candidates = sorted(
                path
                for path in source.rglob("*")
                if path.is_file()
                if not EXCLUDED_DIRECTORY_NAMES.intersection(
                    path.relative_to(source).parts
                )
                if path.name not in EXCLUDED_FILE_NAMES
                if path.suffix.casefold() not in EXCLUDED_FILE_SUFFIXES
            )
        for candidate in candidates:
            if candidate.is_symlink():
                raise ValueError(f"Symlinks are not portable: {candidate}")
            suffix = candidate.relative_to(source)
            logical = relative.joinpath(*suffix.parts) if suffix.parts else relative
            logical_text = logical.as_posix()
            record = {
                "path": logical_text,
                "classification": requested["classification"],
                "size_bytes": candidate.stat().st_size,
                "sha256": sha256_file(candidate),
            }
            previous = expanded.get(logical_text)
            if previous is not None and previous != record:
                raise ValueError(f"Conflicting inventory entries: {logical_text}")
            expanded[logical_text] = record
    return [expanded[path] for path in sorted(expanded)]


def git_record(root: Path) -> dict[str, Any]:
    def git(*arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    status = git("status", "--porcelain=v1", "--untracked-files=all")
    return {
        "branch": git("branch", "--show-current") or "DETACHED",
        "commit": git("rev-parse", "HEAD"),
        "working_tree_dirty": bool(status),
        "porcelain_status_entry_count": len(status.splitlines()) if status else 0,
        "porcelain_status_sha256": hashlib.sha256(status.encode("utf-8")).hexdigest(),
    }


def create_manifest(options: argparse.Namespace) -> int:
    roots = [path.resolve() for path in options.source_root]
    if any(not root.is_dir() for root in roots):
        raise ValueError("Every --source-root must be an existing directory")
    inventory = load_inventory(options.inventory, options.entry)
    records = expand_entries(inventory, roots)
    manifest = {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "repository_classification": "REVIEW_REQUIRED",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "path_contract": {
            "base": "target repository root",
            "separator": "/",
            "absolute_paths_serialized": False,
            "parent_segments_allowed": False,
            "git_metadata_included": False,
        },
        "repository": git_record((options.git_root or roots[0]).resolve()),
        "source_environment": {
            "operating_system": platform.system(),
            "operating_system_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "blender_version": options.blender_version,
            "render_backend": options.render_backend,
            "render_device": options.render_device,
            "driver_version": options.driver_version,
        },
        "entries": records,
    }
    output = options.output.resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite migration manifest: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"status": "CREATED", "entry_count": len(records), "output": str(output)},
            sort_keys=True,
        )
    )
    return 0


def verify_manifest(options: argparse.Namespace) -> int:
    manifest = json.loads(options.manifest.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_name") != SCHEMA_NAME
        or manifest.get("schema_version") != SCHEMA_VERSION
    ):
        raise ValueError("Unsupported migration manifest schema")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Migration manifest entries must be an array")
    targets = [path.resolve() for path in options.target_root]
    if any(not target.is_dir() for target in targets):
        raise ValueError("Every --target-root must be an existing directory")
    failures: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in entries:
        if not isinstance(record, dict):
            raise ValueError("Every migration manifest entry must be an object")
        if record.get("classification") not in CLASSIFICATIONS:
            raise ValueError(f"Invalid classification for {record.get('path')}")
        relative = portable_path(str(record.get("path", "")))
        if relative.as_posix() in seen:
            raise ValueError(f"Duplicate migration manifest path: {relative}")
        seen.add(relative.as_posix())
        try:
            candidate = find_source(relative, targets)
        except FileNotFoundError:
            failures.append({"path": relative.as_posix(), "reason": "missing"})
            continue
        if not candidate.is_file():
            failures.append({"path": relative.as_posix(), "reason": "not_a_file"})
            continue
        if candidate.is_symlink():
            failures.append({"path": relative.as_posix(), "reason": "symlink"})
            continue
        actual_size = candidate.stat().st_size
        actual_sha256 = sha256_file(candidate)
        if actual_size != record.get("size_bytes") or actual_sha256 != record.get("sha256"):
            failures.append(
                {
                    "path": relative.as_posix(),
                    "reason": "content_mismatch",
                    "expected_size_bytes": record.get("size_bytes"),
                    "actual_size_bytes": actual_size,
                    "expected_sha256": record.get("sha256"),
                    "actual_sha256": actual_sha256,
                }
            )
    result = {
        "status": "PASS" if not failures else "FAIL",
        "checked_entry_count": len(entries),
        "failure_count": len(failures),
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create a new immutable manifest")
    create.add_argument("--source-root", type=Path, action="append", required=True)
    create.add_argument("--git-root", type=Path)
    create.add_argument("--inventory", type=Path)
    create.add_argument("--entry", action="append", default=[])
    create.add_argument("--blender-version")
    create.add_argument("--render-backend")
    create.add_argument("--render-device")
    create.add_argument("--driver-version")
    create.add_argument("--output", type=Path, required=True)
    create.set_defaults(handler=create_manifest)

    verify = commands.add_parser("verify", help="Verify files below a new target root")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--target-root", type=Path, action="append", required=True)
    verify.set_defaults(handler=verify_manifest)
    return root


def main() -> int:
    try:
        options = parser().parse_args()
        return options.handler(options)
    except (FileNotFoundError, FileExistsError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Migration manifest error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
