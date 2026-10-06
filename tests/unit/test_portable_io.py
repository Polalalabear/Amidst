"""Local platform adapters preserve byte identity and explicit path ownership."""

import errno
import os
from pathlib import Path

import pytest

import amidst.experiments.versioning as versioning_module
import amidst.portability.paths as paths_module
import amidst.storage.json_files as json_module
from amidst.domain.experiment import ArtifactReference
from amidst.experiments.versioning import fingerprint, read_local_bytes, resolve_reference
from amidst.portability.paths import portable_relative_reference, resolve_local_path
from amidst.storage.json_files import write_json


def test_local_references_ignore_current_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "inputs" / "data.json"
    source.parent.mkdir()
    source.write_bytes(b'{"id": "configured"}\r\n')
    config = tmp_path / "config" / "run.json"
    config.parent.mkdir()
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    reference = ArtifactReference(path="../inputs/data.json", sha256="0" * 64)
    expected = resolve_reference(reference, config)
    monkeypatch.chdir(unrelated)
    assert resolve_reference(reference, config) == expected == source.resolve()
    assert resolve_local_path(source, base=unrelated) == source.resolve()


@pytest.mark.skipif(os.name == "nt", reason="foreign Windows path rejection is POSIX-specific")
@pytest.mark.parametrize(
    "raw", [r"C:\data\snapshot.json", "C:/data/snapshot.json", r"\\server\share\data.json",
            r"\data\snapshot.json", r"C:data.json"],
)
def test_foreign_windows_paths_are_never_interpreted_relative_to_the_cwd(
    tmp_path: Path, raw: str,
) -> None:
    with pytest.raises(ValueError, match="Windows paths"):
        resolve_local_path(raw, base=tmp_path)
    reference = ArtifactReference(path=raw, sha256="0" * 64)
    with pytest.raises(ValueError, match="Windows paths"):
        resolve_reference(reference, tmp_path / "config.json")


def test_windows_style_json_separators_are_normalized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulate the native Windows relpath result without requiring a Windows FS.
    monkeypatch.setattr(paths_module.os.path, "relpath", lambda target, base: r"..\data\one.json")
    monkeypatch.setattr(paths_module.os, "sep", "\\")
    assert portable_relative_reference(tmp_path / "one.json", tmp_path) == "../data/one.json"


def test_cross_drive_relative_reference_fails_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def cross_drive(target: Path, base: Path) -> str:
        raise ValueError("path is on mount D:, start on mount C:")

    monkeypatch.setattr(paths_module.os.path, "relpath", cross_drive)
    with pytest.raises(ValueError, match="same drive"):
        portable_relative_reference(tmp_path / "one.json", tmp_path)


def test_regular_file_reader_without_optional_platform_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "exact.json"
    original = b'{"line": "one"}\r\n\x1a'
    path.write_bytes(original)
    monkeypatch.delattr(versioning_module.os, "O_NONBLOCK", raising=False)
    monkeypatch.delattr(versioning_module.os, "O_BINARY", raising=False)
    assert read_local_bytes(path) == original
    assert fingerprint(path, "exact").size_bytes == len(original)


def test_windows_binary_mode_flag_is_used_when_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "exact.json"
    original = b'{"line": "one"}\r\n\x1a'
    path.write_bytes(original)
    host_open = os.open
    binary_flag = getattr(os, "O_BINARY", 1 << 29)
    seen: list[int] = []

    def platform_open(target: Path, flags: int) -> int:
        seen.append(flags)
        # A simulated flag is removed before the real POSIX syscall.
        return host_open(target, flags if hasattr(os, "O_BINARY") and os.name == "nt"
                         else flags & ~binary_flag)

    monkeypatch.setattr(versioning_module.os, "O_BINARY", binary_flag, raising=False)
    monkeypatch.setattr(versioning_module.os, "open", platform_open)
    assert read_local_bytes(path) == original
    assert len(seen) == 1 and seen[0] & binary_flag


def test_atomic_overwrite_stages_on_destination_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "nested" / "snapshot.json"
    write_json(target, {"generation": 1})
    real_replace = os.replace
    calls: list[tuple[Path, Path]] = []

    def same_filesystem_replace(source: Path, destination: Path) -> None:
        assert source.parent.resolve() == destination.parent.resolve()
        calls.append((source, destination))
        real_replace(source, destination)

    monkeypatch.setattr(json_module.os, "replace", same_filesystem_replace)
    write_json(target, {"generation": 2}, overwrite=True)
    assert len(calls) == 1
    assert '"generation": 2' in target.read_text()
    assert list(target.parent.iterdir()) == [target]


def test_replace_failure_never_falls_back_to_nonatomic_cross_filesystem_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "snapshot.json"
    write_json(target, {"generation": 1})
    original = target.read_bytes()

    def cross_filesystem(source: Path, destination: Path) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(json_module.os, "replace", cross_filesystem)
    with pytest.raises(OSError) as raised:
        write_json(target, {"generation": 2}, overwrite=True)
    assert raised.value.errno == errno.EXDEV
    assert target.read_bytes() == original
    assert list(tmp_path.iterdir()) == [target]
