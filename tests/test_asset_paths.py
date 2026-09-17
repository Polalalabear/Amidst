"""Tests for external Blender roots, immutable sources, and output locks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from blender.scripts import asset_paths

BLENDER_SCRIPTS = Path(__file__).resolve().parents[1] / "blender" / "scripts"
if str(BLENDER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(BLENDER_SCRIPTS))

from asset_guards import (  # noqa: E402
    OutputLockError,
    SourceMutationError,
    TaskOutputLock,
    snapshot_source,
    verify_source_unchanged,
)


class AssetRootTests(unittest.TestCase):
    def _config(self, path: Path, roots: dict[str, Path]) -> Path:
        value = {
            "schema_name": asset_paths.CONFIG_SCHEMA,
            "schema_version": asset_paths.CONFIG_VERSION,
            "roots": {
                name: {
                    "path": str(root),
                    "access": asset_paths.ROOT_DEFINITIONS[name].access,
                }
                for name, root in roots.items()
            },
        }
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_environment_overrides_local_config_and_repository_fallback(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            configured = base / "configured"
            environment_root = base / "environment"
            configured.mkdir()
            environment_root.mkdir()
            config = self._config(
                base / "asset_roots.json", {"blender-source": configured}
            )
            resolved = asset_paths.configured_root(
                "blender-source",
                repo_root=base,
                config_path=config,
                environment={"AMIDST_BLENDER_SOURCE_ROOT": str(environment_root)},
                require_exists=True,
            )
            self.assertEqual(resolved, environment_root.resolve())

    def test_logical_uri_is_independent_of_physical_root(self) -> None:
        uri = asset_paths.logical_uri("blender-source", "school/school_v1.blend")
        self.assertEqual(uri, "asset://blender-source/school/school_v1.blend")
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            first_path = Path(first) / "school" / "school_v1.blend"
            second_path = Path(second) / "school" / "school_v1.blend"
            first_path.parent.mkdir()
            second_path.parent.mkdir()
            first_path.write_bytes(b"scene")
            second_path.write_bytes(b"scene")
            one = asset_paths.resolve_logical_uri(
                uri,
                repo_root=Path(first),
                environment={"AMIDST_BLENDER_SOURCE_ROOT": first},
                must_exist=True,
            )
            two = asset_paths.resolve_logical_uri(
                uri,
                repo_root=Path(second),
                environment={"AMIDST_BLENDER_SOURCE_ROOT": second},
                must_exist=True,
            )
            self.assertNotEqual(one, two)
            self.assertEqual(one.read_bytes(), two.read_bytes())

    def test_path_serialization_uses_logical_or_repository_reference(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            repository = base / "repo"
            external = base / "external-source"
            repository.mkdir()
            external.mkdir()
            project_file = repository / "data" / "schema.json"
            project_file.parent.mkdir()
            project_file.write_text("{}", encoding="utf-8")
            source = external / "scene.blend"
            source.write_bytes(b"scene")
            environment = {"AMIDST_BLENDER_SOURCE_ROOT": str(external)}

            self.assertEqual(
                asset_paths.portable_repository_reference(
                    project_file, repo_root=repository
                ),
                "data/schema.json",
            )
            self.assertEqual(
                asset_paths.logical_uri_for_path(
                    "blender-source",
                    source,
                    repo_root=repository,
                    environment=environment,
                ),
                "asset://blender-source/scene.blend",
            )

    def test_rejects_escape_and_invalid_task_id(self) -> None:
        with TemporaryDirectory() as temporary:
            for invalid in (".", "../outside"):
                with self.subTest(invalid=invalid), self.assertRaises(
                    asset_paths.AssetPathError
                ):
                    asset_paths.resolve_below_root(Path(temporary), invalid)
            with self.assertRaises(asset_paths.AssetPathError):
                asset_paths.validate_task_id("../same-output")

    def test_blender_scripts_do_not_hardcode_worktree_asset_roots(self) -> None:
        scripts = BLENDER_SCRIPTS
        forbidden = (
            'REPOSITORY_ROOT / "blender/source',
            'REPOSITORY_ROOT / "blender/working',
            'REPOSITORY_ROOT / "blender/output',
            'root / "blender/source',
            '"blender/working" not in',
        )
        failures: list[str] = []
        for path in sorted(scripts.glob("*.py")):
            if path.name == "asset_paths.py":
                continue
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                if marker in text:
                    failures.append(f"{path.name}: {marker}")
        self.assertEqual(failures, [])

        validation_script = (scripts / "validate_scene.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('"source_path": str(source_path)', validation_script)

    @unittest.skipIf(os.name == "nt", "POSIX symlink behavior is tested here")
    def test_allows_symlink_root_but_rejects_nested_escape(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            physical = base / "physical"
            external = base / "external"
            physical.mkdir()
            external.mkdir()
            root_link = base / "root-link"
            root_link.symlink_to(physical, target_is_directory=True)
            outside = external / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            (physical / "nested-link").symlink_to(outside)
            self.assertEqual(
                asset_paths.resolve_below_root(root_link, "inside.txt"),
                (physical / "inside.txt").resolve(strict=False),
            )
            with self.assertRaises(asset_paths.AssetPathError):
                asset_paths.resolve_below_root(root_link, "nested-link")


class GuardTests(unittest.TestCase):
    def test_source_snapshot_detects_mutation(self) -> None:
        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.blend"
            source.write_bytes(b"before")
            before = snapshot_source(
                source, "asset://blender-source/source.blend"
            )
            verify_source_unchanged(source, before)
            source.write_bytes(b"after")
            with self.assertRaises(SourceMutationError):
                verify_source_unchanged(source, before)

    def test_task_lock_is_exclusive_and_releasable(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = TaskOutputLock(root, "observation-macos-0001")
            second = TaskOutputLock(root, "observation-macos-0001")
            first.acquire()
            try:
                with self.assertRaises(OutputLockError):
                    second.acquire()
            finally:
                first.release()
            second.acquire()
            second.release()

    def test_health_check_probes_output_without_printing_physical_roots(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            roots = {
                name: base / name for name in asset_paths.ROOT_DEFINITIONS
            }
            for root in roots.values():
                root.mkdir()
            config = base / "asset_roots.json"
            config.write_text(
                json.dumps(
                    {
                        "schema_name": asset_paths.CONFIG_SCHEMA,
                        "schema_version": asset_paths.CONFIG_VERSION,
                        "roots": {
                            name: {
                                "path": str(root),
                                "access": asset_paths.ROOT_DEFINITIONS[name].access,
                            }
                            for name, root in roots.items()
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "scripts/check_asset_roots.py",
                    "--config",
                    str(config),
                    "--probe-output",
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn(str(base), result.stdout)
            self.assertFalse(
                (roots["blender-output"] / "asset-root-health-check" / ".amidst-task.lock").exists()
            )


if __name__ == "__main__":
    unittest.main()
