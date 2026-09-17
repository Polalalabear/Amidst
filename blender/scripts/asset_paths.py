#!/usr/bin/env python3
"""Resolve machine-local Blender roots without serializing physical paths."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
from typing import Mapping


CONFIG_SCHEMA = "amidst.local_asset_roots"
CONFIG_VERSION = "0.1.0"
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class AssetPathError(ValueError):
    """A configured or logical asset path violates the local path contract."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RootDefinition:
    environment_variable: str
    repository_fallback: str
    access: str


ROOT_DEFINITIONS = {
    "blender-source": RootDefinition(
        "AMIDST_BLENDER_SOURCE_ROOT", "blender/source", "read_only"
    ),
    "blender-textures": RootDefinition(
        "AMIDST_BLENDER_TEXTURE_ROOT", "blender/textures", "read_only"
    ),
    "blender-working": RootDefinition(
        "AMIDST_BLENDER_WORK_ROOT", "blender/working", "task_scoped_write"
    ),
    "blender-output": RootDefinition(
        "AMIDST_BLENDER_OUTPUT_ROOT", "blender/output", "task_scoped_write"
    ),
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def portable_relative_path(value: str) -> PurePosixPath:
    if not value or "\\" in value:
        raise AssetPathError("INVALID_LOGICAL_PATH", "Use a non-empty POSIX path")
    relative = PurePosixPath(value)
    if (
        not relative.parts
        or relative.as_posix() == "."
        or relative.is_absolute()
        or ".." in relative.parts
        or ".git" in relative.parts
    ):
        raise AssetPathError(
            "PATH_ESCAPE_REJECTED", f"Logical path is not portable: {value}"
        )
    if relative.parts[0].endswith(":"):
        raise AssetPathError(
            "INVALID_LOGICAL_PATH", f"Logical path contains a drive: {value}"
        )
    return relative


def validate_task_id(task_id: str) -> str:
    if not TASK_ID_RE.fullmatch(task_id):
        raise AssetPathError("INVALID_TASK_ID", f"Invalid task ID: {task_id!r}")
    return task_id


def load_root_config(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssetPathError("INVALID_CONFIG", "Asset-root config must be an object")
    if value.get("schema_name") != CONFIG_SCHEMA or value.get("schema_version") != CONFIG_VERSION:
        raise AssetPathError("INVALID_CONFIG", "Unsupported asset-root config schema")
    roots = value.get("roots")
    if not isinstance(roots, dict):
        raise AssetPathError("INVALID_CONFIG", "Asset-root config requires roots")
    result: dict[str, dict[str, str]] = {}
    for name, record in roots.items():
        if name not in ROOT_DEFINITIONS or not isinstance(record, dict):
            raise AssetPathError("INVALID_CONFIG", f"Unsupported asset root: {name}")
        configured_path = record.get("path")
        access = record.get("access")
        if not isinstance(configured_path, str) or not configured_path:
            raise AssetPathError("INVALID_CONFIG", f"Root {name} requires path")
        if access != ROOT_DEFINITIONS[name].access:
            raise AssetPathError(
                "ROOT_ACCESS_MISMATCH", f"Root {name} must use {ROOT_DEFINITIONS[name].access}"
            )
        result[name] = {"path": configured_path, "access": access}
    return result


def configured_root(
    name: str,
    *,
    repo_root: Path | None = None,
    config_path: Path | None = None,
    environment: Mapping[str, str] | None = None,
    require_exists: bool = False,
) -> Path:
    if name not in ROOT_DEFINITIONS:
        raise AssetPathError("UNKNOWN_ROOT", f"Unknown asset root: {name}")
    repo = (repo_root or repository_root()).resolve()
    definition = ROOT_DEFINITIONS[name]
    env = os.environ if environment is None else environment
    raw_path = env.get(definition.environment_variable)
    if raw_path:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            raise AssetPathError(
                "INVALID_CONFIG", f"{definition.environment_variable} must be absolute"
            )
    else:
        local_config = config_path or repo / "local" / "asset_roots.json"
        configured = load_root_config(local_config)
        if name in configured:
            candidate = Path(configured[name]["path"]).expanduser()
            if not candidate.is_absolute():
                raise AssetPathError(
                    "INVALID_CONFIG", f"Configured root {name} must be absolute"
                )
        else:
            fallback = portable_relative_path(definition.repository_fallback)
            candidate = repo.joinpath(*fallback.parts)
    resolved = candidate.resolve(strict=False)
    if require_exists and not resolved.is_dir():
        raise AssetPathError("ROOT_NOT_FOUND", f"Configured root is unavailable: {name}")
    return resolved


def resolve_below_root(
    root: Path, relative: str | PurePosixPath, *, must_exist: bool = False
) -> Path:
    portable = portable_relative_path(str(relative))
    resolved_root = root.resolve(strict=False)
    candidate = resolved_root.joinpath(*portable.parts).resolve(strict=False)
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise AssetPathError(
            "PATH_ESCAPE_REJECTED", f"Logical path escapes configured root: {portable}"
        )
    if must_exist and not candidate.exists():
        raise AssetPathError("ASSET_NOT_FOUND", f"Asset is unavailable: {portable}")
    return candidate


def root_path(
    name: str,
    relative: str = ".",
    *,
    repo_root: Path | None = None,
    config_path: Path | None = None,
    environment: Mapping[str, str] | None = None,
    must_exist: bool = False,
) -> Path:
    root = configured_root(
        name,
        repo_root=repo_root,
        config_path=config_path,
        environment=environment,
        require_exists=False,
    )
    if relative == ".":
        if must_exist and not root.exists():
            raise AssetPathError("ROOT_NOT_FOUND", f"Configured root is unavailable: {name}")
        return root
    return resolve_below_root(root, relative, must_exist=must_exist)


def parse_logical_uri(uri: str) -> tuple[str, PurePosixPath]:
    if uri.startswith("asset://"):
        payload = uri.removeprefix("asset://")
        root_name, separator, relative = payload.partition("/")
        if not separator or root_name not in ROOT_DEFINITIONS:
            raise AssetPathError("INVALID_LOGICAL_URI", f"Invalid asset URI: {uri}")
        return root_name, portable_relative_path(relative)
    if uri.startswith("output://"):
        payload = uri.removeprefix("output://")
        task_id, separator, relative = payload.partition("/")
        validate_task_id(task_id)
        if not separator:
            relative = "."
        combined = PurePosixPath(task_id)
        if relative != ".":
            combined = combined.joinpath(portable_relative_path(relative))
        return "blender-output", portable_relative_path(combined.as_posix())
    raise AssetPathError("INVALID_LOGICAL_URI", f"Unsupported logical URI: {uri}")


def resolve_logical_uri(
    uri: str,
    *,
    repo_root: Path | None = None,
    config_path: Path | None = None,
    environment: Mapping[str, str] | None = None,
    must_exist: bool = False,
) -> Path:
    root_name, relative = parse_logical_uri(uri)
    return root_path(
        root_name,
        relative.as_posix(),
        repo_root=repo_root,
        config_path=config_path,
        environment=environment,
        must_exist=must_exist,
    )


def logical_uri(root_name: str, relative: str | PurePosixPath) -> str:
    if root_name not in ROOT_DEFINITIONS:
        raise AssetPathError("UNKNOWN_ROOT", f"Unknown asset root: {root_name}")
    portable = portable_relative_path(str(relative))
    return f"asset://{root_name}/{portable.as_posix()}"


def logical_uri_for_path(
    root_name: str,
    path: Path,
    *,
    repo_root: Path | None = None,
    config_path: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> str:
    root = configured_root(
        root_name,
        repo_root=repo_root,
        config_path=config_path,
        environment=environment,
    )
    resolved = path.resolve(strict=False)
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise AssetPathError(
            "PATH_ESCAPE_REJECTED", f"Path is outside configured root: {root_name}"
        ) from error
    if not relative.parts:
        raise AssetPathError("INVALID_LOGICAL_PATH", "A logical asset must name a path")
    return logical_uri(root_name, PurePosixPath(*relative.parts))


def portable_repository_reference(path: Path, *, repo_root: Path | None = None) -> str:
    repo = (repo_root or repository_root()).resolve()
    resolved = path.resolve(strict=False)
    try:
        relative = resolved.relative_to(repo)
    except ValueError as error:
        raise AssetPathError(
            "PATH_ESCAPE_REJECTED", "Repository record path is outside the repository"
        ) from error
    return portable_relative_path(PurePosixPath(*relative.parts).as_posix()).as_posix()


def task_output_root(task_id: str, **kwargs: object) -> Path:
    validate_task_id(task_id)
    return root_path("blender-output", task_id, **kwargs)
