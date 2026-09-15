"""Tests for portable migration-manifest creation and verification."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts import migration_manifest


class PortablePathTests(unittest.TestCase):
    def test_accepts_repository_relative_posix_path(self) -> None:
        value = migration_manifest.portable_path("docs/00_Project_Map.md")
        self.assertEqual(value.as_posix(), "docs/00_Project_Map.md")

    def test_rejects_nonportable_paths(self) -> None:
        invalid = (
            "/Users/example/project/file.json",
            "C:/Users/example/project/file.json",
            "docs\\file.md",
            "../outside.txt",
            ".git/config",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                migration_manifest.portable_path(value)


class EntryExpansionTests(unittest.TestCase):
    def test_directory_expansion_excludes_reproducible_local_artifacts(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "payload"
            (source / "nested").mkdir(parents=True)
            (source / "nested" / "kept.txt").write_text("kept", encoding="utf-8")
            (source / "__pycache__").mkdir()
            (source / "__pycache__" / "ignored.pyc").write_bytes(b"cache")
            (source / ".DS_Store").write_bytes(b"metadata")

            records = migration_manifest.expand_entries(
                [{"classification": "PUBLIC_ALLOWED", "path": "payload"}],
                [root],
            )

            self.assertEqual([record["path"] for record in records], ["payload/nested/kept.txt"])

    def test_uses_first_source_root_containing_each_file(self) -> None:
        with TemporaryDirectory() as first_temporary, TemporaryDirectory() as second_temporary:
            first = Path(first_temporary)
            second = Path(second_temporary)
            (second / "private").mkdir()
            (second / "private" / "asset.bin").write_bytes(b"asset")

            records = migration_manifest.expand_entries(
                [{"classification": "PRIVATE_ONLY", "path": "private/asset.bin"}],
                [first, second],
            )

            self.assertEqual(records[0]["path"], "private/asset.bin")
            self.assertEqual(records[0]["classification"], "PRIVATE_ONLY")


class ManifestVerificationTests(unittest.TestCase):
    def _write_manifest(self, path: Path, target: Path) -> None:
        relative = migration_manifest.portable_path("payload/file.txt")
        source = target.joinpath(*relative.parts)
        manifest = {
            "schema_name": migration_manifest.SCHEMA_NAME,
            "schema_version": migration_manifest.SCHEMA_VERSION,
            "entries": [
                {
                    "path": relative.as_posix(),
                    "classification": "PUBLIC_ALLOWED",
                    "size_bytes": source.stat().st_size,
                    "sha256": migration_manifest.sha256_file(source),
                }
            ],
        }
        path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_verify_passes_then_reports_content_mismatch(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            (target / "payload").mkdir(parents=True)
            payload = target / "payload" / "file.txt"
            payload.write_text("original", encoding="utf-8")
            manifest = root / "manifest.json"
            self._write_manifest(manifest, target)
            options = argparse.Namespace(manifest=manifest, target_root=[target])

            with redirect_stdout(io.StringIO()):
                self.assertEqual(migration_manifest.verify_manifest(options), 0)

            payload.write_text("changed", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(migration_manifest.verify_manifest(options), 1)
            self.assertIn("content_mismatch", output.getvalue())


if __name__ == "__main__":
    unittest.main()
