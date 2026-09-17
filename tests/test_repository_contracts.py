"""Tests for repository setup, documentation, and dependency contracts."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_repository_validation_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", "scripts/check.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dev_lock_has_no_third_party_packages(self) -> None:
        lock = (ROOT / "requirements-dev.lock.txt").read_text(encoding="utf-8")
        requirements = [
            line.strip()
            for line in lock.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(requirements, [])

    def test_blender_runtime_lock_records_verified_and_target_profiles(self) -> None:
        lock = json.loads(
            (ROOT / "blender" / "runtime_dependencies.lock.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(lock["schema_name"], "amidst.blender_runtime_dependencies_lock")
        self.assertEqual(lock["schema_version"], "0.1.0")
        self.assertEqual(lock["versions"]["blender"], "5.2.1 LTS")
        self.assertEqual(lock["profiles"]["macos_arm64"]["status"], "CONFIRMED")
        self.assertEqual(lock["profiles"]["linux_x86_64"]["status"], "OPEN")
        self.assertEqual(lock["profiles"]["windows_x86_64"]["status"], "OPEN")

    def test_setup_guide_has_separate_platform_instructions(self) -> None:
        guide = (ROOT / "docs" / "10_Cross_Platform_Setup_and_Testing.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "### macOS",
            "### Windows (PowerShell)",
            "### Linux (Bash)",
            "### macOS 使用方式",
            "### Windows 使用方式（PowerShell）",
            "### Linux 使用方式（Bash）",
            "python3 -B scripts/test.py",
            "py -3 -B scripts/test.py",
            "python3 -B scripts/test.py",
            "$BlenderExe",
            "AMIDST_BLENDER_SOURCE_ROOT",
            "scripts/check_asset_roots.py",
            "amidst.migration_manifest/0.2.0",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, guide)


if __name__ == "__main__":
    unittest.main()
