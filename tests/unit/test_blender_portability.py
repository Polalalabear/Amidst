"""Blender discovery and diagnostic publication without platform-specific installs."""

from __future__ import annotations

import errno
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from amidst.portability import blender

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("explicit", "environment", "expected"),
    [("cli-tool", "env-tool", "cli-tool"), (None, "env-tool", "env-tool"),
     (None, None, "blender")],
)
def test_discovery_precedence_and_absolute_result(
    monkeypatch: pytest.MonkeyPatch, explicit: str | None, environment: str | None,
    expected: str,
) -> None:
    if environment is None:
        monkeypatch.delenv("BLENDER_BIN", raising=False)
    else:
        monkeypatch.setenv("BLENDER_BIN", environment)
    calls: list[str] = []

    def which(candidate: str) -> str:
        calls.append(candidate)
        return sys.executable

    monkeypatch.setattr(blender.shutil, "which", which)
    assert blender.resolve_blender_executable(explicit) == str(Path(sys.executable).resolve())
    assert calls == [expected]


@pytest.mark.parametrize("origin", ["explicit", "environment", "PATH"])
def test_discovery_reports_missing_executable_without_guessing_an_install(
    monkeypatch: pytest.MonkeyPatch, origin: str,
) -> None:
    monkeypatch.delenv("BLENDER_BIN", raising=False)
    calls: list[str] = []
    if origin == "environment":
        monkeypatch.setenv("BLENDER_BIN", "missing-configured-tool")

    def which(candidate: str) -> None:
        calls.append(candidate)
        return None

    monkeypatch.setattr(blender.shutil, "which", which)
    explicit = "missing-configured-tool" if origin == "explicit" else None
    with pytest.raises(FileNotFoundError, match="Blender CLI"):
        blender.resolve_blender_executable(explicit)
    assert calls == ["blender" if origin == "PATH" else "missing-configured-tool"]


def test_explicit_directory_is_not_an_executable(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not executable"):
        blender.resolve_blender_executable(str(tmp_path))


def _load_audit_script(name: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("kind", ["scene", "geometry"])
@pytest.mark.parametrize("publication_fails", [False, True])
def test_audit_staging_uses_destination_filesystem_and_cleans_up_on_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, publication_fails: bool,
) -> None:
    """Inject EXDEV for any cross-filesystem staging; failure preserves old bytes."""
    script = _load_audit_script(f"run_{kind}_audit", monkeypatch)
    source = tmp_path / "synthetic read-only source.blend"
    source.write_bytes(b"SYNTHETIC TEST_FIXTURE; never loaded by Blender")
    output_dir = tmp_path / "destination volume"
    output_dir.mkdir()
    filename = f"school_v2_{kind}_audit.json"
    output = output_dir / filename
    previous = b"previous complete diagnostic"
    output.write_bytes(previous)
    if kind == "scene":
        (output_dir / "README.md").write_text("previous summary", encoding="utf-8")
        monkeypatch.setattr(script, "render_summary", lambda report: "synthetic summary\n")
    foreign_cwd = tmp_path / "unrelated caller"
    foreign_cwd.mkdir()
    monkeypatch.chdir(foreign_cwd)
    option = "--output-dir" if kind == "scene" else "--output"
    destination = output_dir if kind == "scene" else output
    monkeypatch.setattr(sys, "argv", [
        str(ROOT / "scripts" / f"run_{kind}_audit.py"), "--blend", str(source),
        "--blender", sys.executable, option, str(destination),
    ])
    source_bytes = source.read_bytes()
    calls: list[list[str]] = []
    staged_paths: list[Path] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert command[0] == str(Path(sys.executable).resolve())
        assert str(source) in command
        assert Path(kwargs["cwd"]) == ROOT
        stage_option = "--json-output" if kind == "scene" else "--output"
        stage = Path(command[command.index(stage_option) + 1])
        staged_paths.append(stage)
        report = {"source": {}, "read_only_contract": {}} if kind == "scene" else {}
        stage.write_text(json.dumps(report), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(script.subprocess, "run", run)
    real_replace = os.replace
    published: list[Path] = []

    def replace(staged: Path, final: Path) -> None:
        # The old global-temp staging would hit this EXDEV boundary.
        if staged.parent.parent != final.parent:
            raise OSError(errno.EXDEV, "synthetic cross-filesystem replace")
        if publication_fails:
            raise OSError(errno.EXDEV, "synthetic filesystem publication failure")
        real_replace(staged, final)
        published.append(final)

    monkeypatch.setattr(script.os, "replace", replace)
    if publication_fails:
        with pytest.raises(OSError) as raised:
            script.main()
        assert raised.value.errno == errno.EXDEV
        assert output.read_bytes() == previous
        assert not published
    else:
        script.main()
        report = json.loads(output.read_text(encoding="utf-8"))
        assert report["source"]["sha256_before"] == report["source"]["sha256_after"]
        assert output in published
    assert source.read_bytes() == source_bytes
    assert len(calls) == 1 and len(staged_paths) == 1
    assert staged_paths[0].parent.parent == output_dir
    assert not staged_paths[0].parent.exists()
    assert {path.name for path in output_dir.iterdir()} == (
        {filename, "README.md"} if kind == "scene" else {filename}
    )


@pytest.mark.parametrize("script", ["export_cameras", "run_scene_audit", "run_geometry_audit"])
def test_blender_wrapper_cli_help_is_cwd_independent(tmp_path: Path, script: str) -> None:
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    environment.pop("PYTHONPATH", None)
    command = [sys.executable]
    if script == "export_cameras":
        # Camera schema validation already requires the installed Python dependencies.
        environment["PYTHONPATH"] = str(ROOT / "src")
    else:
        # Standalone diagnostics need only stdlib, even without site-packages/PYTHONPATH.
        command.append("-S")
    command.extend([str(ROOT / "scripts" / f"{script}.py"), "--help"])
    result = subprocess.run(
        command,
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--blend" in result.stdout
