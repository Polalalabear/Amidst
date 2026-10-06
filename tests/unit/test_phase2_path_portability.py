"""Phase 2 readers retain path identity and reject platform-specific ambiguity."""

import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

import pytest

import amidst.integration.replay as replay_module
from amidst.domain.stream import ObservationAggregation
from amidst.integration.local_repository import LocalJsonRepository
from amidst.integration.replay import BenchmarkImportError, load_benchmark_snapshot
from amidst.integration.repositories import RepositorySnapshot
from amidst.integration.wiring import build_mock_service

ROOT = Path(__file__).resolve().parents[2]


def _empty_package(root: Path) -> None:
    files = {
        "experiment.json": b"{}",
        "replay/config.json": b"{}",
        "cases/SYNTHETIC/observations.json": ObservationAggregation(
            samples=(), observations=(),
        ).model_dump_json().encode(),
    }
    records = []
    for logical_id, data in files.items():
        path = root / logical_id
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        records.append({"logical_id": logical_id, "sha256": hashlib.sha256(data).hexdigest(),
                        "size_bytes": len(data)})
    (root / "artifacts.json").write_text(json.dumps({
        "schema_version": "1.0", "status": "COMPLETE", "config_sha256": "0" * 64,
        "files": records,
    }), encoding="utf-8")


def test_local_repository_keeps_its_construction_directory_after_cwd_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    working = tmp_path / "first ü space"
    elsewhere = tmp_path / "second"
    working.mkdir()
    elsewhere.mkdir()
    monkeypatch.chdir(working)
    repository = LocalJsonRepository(Path("state/snapshot.json"))
    original = (working / "state/snapshot.json").read_bytes()
    monkeypatch.chdir(elsewhere)
    assert repository.snapshot() == RepositorySnapshot()
    repository.add(RepositorySnapshot())
    assert (working / "state/snapshot.json").read_bytes() == original
    assert not (elsewhere / "state").exists()


def test_service_store_path_is_relative_to_config_even_from_foreign_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = json.loads((ROOT / "configs/integration/mock_v1.json").read_text())
    config["dataset_manifest"]["path"] = str(ROOT / "data/mock/stream_v1/dataset.json")
    config.update(repository_kind="LOCAL_JSON", repository_path="stores/local.json")
    config_directory = tmp_path / "configuration ü space"
    config_directory.mkdir()
    path = config_directory / "service.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    service = build_mock_service(path, search_clock=lambda: 0.0)
    monkeypatch.chdir(config_directory)
    assert len(service.repository.snapshot().gaps) == 4
    assert (config_directory / "stores/local.json").is_file()
    assert not (tmp_path / "stores").exists()


@pytest.mark.parametrize("logical_id", [r"C:\data\one.json", "C:/data/one.json",
                                       r"\\server\share\one.json", "C:one.json"])
def test_windows_manifest_paths_never_escape_or_depend_on_host_flavor(
    tmp_path: Path, logical_id: str,
) -> None:
    _empty_package(tmp_path)
    path = tmp_path / "artifacts.json"
    manifest = json.loads(path.read_text())
    manifest["files"].append({"logical_id": logical_id, "sha256": "0" * 64, "size_bytes": 0})
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BenchmarkImportError, match="canonical relative"):
        load_benchmark_snapshot(tmp_path)


@pytest.mark.parametrize("changed", ["artifacts.json", "cases/SYNTHETIC/observations.json"])
def test_replay_regular_file_failure_is_structured_before_deserialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str,
) -> None:
    _empty_package(tmp_path)
    reader = replay_module.open_regular_file

    @contextmanager
    def changed_file(path: Path):
        if path.relative_to(tmp_path).as_posix() == changed:
            raise ValueError("injected special-file replacement after path validation")
        with reader(path) as stream:
            yield stream

    monkeypatch.setattr(replay_module, "open_regular_file", changed_file)
    with pytest.raises(BenchmarkImportError, match="artifact/schema"):
        load_benchmark_snapshot(tmp_path)


def test_relative_replay_import_survives_relocation_without_a_repository_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "not a git checkout ü" / "portable package"
    _empty_package(package)
    monkeypatch.chdir(package.parent)
    assert load_benchmark_snapshot(Path(package.name)) == RepositorySnapshot()
