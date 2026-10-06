"""Small committed-contract fixtures; no Blender, source assets, or downloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import amidst.materialize_physical_evidence as materializer
from amidst.materialize_physical_evidence import (
    POLICY_OUTPUTS,
    RAW_FILENAMES,
    MaterializationError,
    file_sha256,
    load_manifest,
    materialize,
    research_results,
    verify_artifact,
    verify_bindings,
)
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_policy_validation import write_document


@pytest.fixture
def contract_repo(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    """A tiny contract exercises the same bindings without school evidence."""
    root = tmp_path
    bundle = root / "data/policy"
    bundle.mkdir(parents=True)
    source = root / "blender/school_v3.blend"
    source.parent.mkdir()
    source.write_bytes(b"synthetic source bytes, never a Blender scene")
    (root / "uv.lock").write_text("synthetic-lock")
    producer = root / "src/amidst/producer.py"
    producer.parent.mkdir(parents=True)
    producer.write_text("# synthetic immutable producer\n")
    config = root / "configs/validation.json"
    config.parent.mkdir()
    write_document(config, {"synthetic_config": True})
    documents: dict[str, dict[str, Any]] = {
        name: {"synthetic_fixture": True} for name in POLICY_OUTPUTS | {"source_evidence.json.gz"}
    }
    documents.update(
        {
            "body_clearance_policy.json": {
                "scale_authority": "APPROVED",
                "policy_metres": {"authority": "APPROVED"},
            },
            "floor_authority_map.json": {"approved_supported_subdomain_count": 48},
            "obstacle_collider_authority.json": {
                "approved_component_count": 58,
                "obstacles_with_approved_components": 5,
                "obstacle_count": 19,
            },
            "portal_clearance.json": {
                "human_review_count": 8,
                "actual_aperture_authority": "HUMAN_REVIEW",
            },
            "stair_authority.json": {
                "stairs": [{"stair_id": name, "authority": "HUMAN_REVIEW"} for name in ("A", "B")],
            },
            "physical_authority.json": {"level": "PARTIAL_APPROVED"},
            "collision_pruning_results.json": {
                "before_count": 4,
                "after_pruning_count": 2,
                "runtime_seconds": 0.2,
            },
        }
    )
    artifacts = []
    for name, document in sorted(documents.items()):
        path = bundle / name
        write_document(path, document)
        record = {
            "filename": str(path.relative_to(root)),
            "sha256": file_sha256(path),
            "content_sha256": content_sha256(document),
            "source_scene_sha256": file_sha256(source),
            "generating_command": "explicit synthetic fixture",
            "config": str(config.relative_to(root)),
            "producer_commit": "historical-synthetic-commit",
            "semantic_role": "SYNTHETIC_UNIT_FIXTURE",
            "tracked": name not in RAW_FILENAMES,
        }
        if name == "collision_pruning_results.json":
            record["semantic_sha256"] = content_sha256(
                {key: value for key, value in document.items() if key != "runtime_seconds"}
            )
        artifacts.append(record)
    historical = bundle / "manifest.json"
    write_document(historical, {"historical_synthetic_manifest": True})
    contract = {
        "schema_version": "physical-evidence-materialization-v1",
        "full_evidence_commit": "historical-synthetic-commit",
        "historical_manifest": str(historical.relative_to(root)),
        "historical_manifest_sha256": file_sha256(historical),
        "validation_config": str(config.relative_to(root)),
        "source_scene": {
            "filename": str(source.relative_to(root)),
            "sha256": file_sha256(source),
            "size": source.stat().st_size,
            "original_mtime_ns": 123456789,
        },
        "producer": {
            "commit": "historical-synthetic-commit",
            "blender_version": "fixture-version",
            "blender_build_hash": "fixture-build",
            "file_sha256": {
                str(producer.relative_to(root)): file_sha256(producer),
            },
            "dependency_lock_sha256": file_sha256(root / "uv.lock"),
        },
        "input_content_sha256": {},
        "config_content_sha256": {
            str(config.relative_to(root)): content_sha256({"synthetic_config": True})
        },
        "artifacts": artifacts,
        "expected_research_results": research_results(bundle),
    }
    path = bundle / "artifact_manifest.json"
    write_document(path, contract)
    return root, path, contract


def test_verify_only_is_read_only_and_never_runs_producers(
    contract_repo: tuple[Path, Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, manifest, contract = contract_repo
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("verify-only invoked a producer or subprocess")

    monkeypatch.setattr(materializer.subprocess, "run", forbidden)
    result = materialize(root, manifest, verify_only=True)
    assert result["research_results"] == contract["expected_research_results"]
    assert result["source_observed"]["mtime_ns"] != contract["source_scene"]["original_mtime_ns"]
    assert before == {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }


def test_missing_external_source_has_explicit_prerequisite_error(
    contract_repo: tuple[Path, Path, dict[str, Any]],
) -> None:
    root, manifest, _ = contract_repo
    with pytest.raises(MaterializationError, match="missing external source scene prerequisite"):
        materialize(root, manifest, source_scene=root / "absent.blend", verify_only=True)


def test_missing_raw_evidence_cannot_implicitly_generate(
    contract_repo: tuple[Path, Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, manifest, _ = contract_repo
    missing = root / "data/policy/geometry.json.gz"
    missing.unlink()

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("missing fixture implicitly invoked a producer")

    monkeypatch.setattr(materializer.subprocess, "run", forbidden)
    with pytest.raises(
        MaterializationError, match="missing prerequisite physical evidence artifact"
    ):
        materialize(root, manifest, verify_only=True)
    assert not missing.exists()


@pytest.mark.parametrize(
    "target", ["uv.lock", "src/amidst/producer.py", "data/policy/manifest.json"]
)
def test_producer_lock_and_historical_provenance_tampering_fail_closed(
    contract_repo: tuple[Path, Path, dict[str, Any]],
    target: str,
) -> None:
    root, _, contract = contract_repo
    (root / target).write_bytes(b"tampered")
    with pytest.raises(MaterializationError, match="SHA-256 mismatch"):
        verify_bindings(root, contract)


def test_config_tampering_fails_before_generation(
    contract_repo: tuple[Path, Path, dict[str, Any]],
) -> None:
    root, _, contract = contract_repo
    write_document(root / "configs/validation.json", {"synthetic_config": False})
    with pytest.raises(MaterializationError, match="config_content_sha256 mismatch"):
        verify_bindings(root, contract)


def test_source_bytes_must_match_even_when_filename_matches(
    contract_repo: tuple[Path, Path, dict[str, Any]],
) -> None:
    root, manifest, _ = contract_repo
    (root / "blender/school_v3.blend").write_bytes(b"different source")
    with pytest.raises(MaterializationError, match="external source scene SHA-256 or size"):
        materialize(root, manifest, verify_only=True)


def test_collision_semantic_comparison_excludes_runtime_only(
    contract_repo: tuple[Path, Path, dict[str, Any]],
) -> None:
    root, _, contract = contract_repo
    record = next(
        row
        for row in contract["artifacts"]
        if Path(row["filename"]).name == "collision_pruning_results.json"
    )
    path = root / record["filename"]
    write_document(path, {"before_count": 4, "after_pruning_count": 2, "runtime_seconds": 42.0})
    verify_artifact(path, record, semantic=True)
    with pytest.raises(MaterializationError, match="byte SHA-256 mismatch"):
        verify_artifact(path, record)
    write_document(path, {"before_count": 4, "after_pruning_count": 3, "runtime_seconds": 42.0})
    with pytest.raises(MaterializationError, match="content SHA-256 mismatch"):
        verify_artifact(path, record, semantic=True)


def test_raw_artifacts_are_bound_by_bytes_and_json_content(
    contract_repo: tuple[Path, Path, dict[str, Any]],
) -> None:
    root, _, contract = contract_repo
    record = next(
        row for row in contract["artifacts"] if row["filename"].endswith("geometry.json.gz")
    )
    path = root / record["filename"]
    record = {**record, "content_sha256": "0" * 64}
    with pytest.raises(MaterializationError, match="content SHA-256 mismatch"):
        verify_artifact(path, record)
    path.write_bytes(path.read_bytes() + b"\0")  # Valid gzip padding, different transport bytes.
    with pytest.raises(MaterializationError, match="byte SHA-256 mismatch"):
        verify_artifact(path, record)


@pytest.mark.parametrize(
    "change", ["traversal", "tracked_raw", "missing_field", "missing_artifact"]
)
def test_malformed_or_unsafe_manifest_has_clear_error(
    contract_repo: tuple[Path, Path, dict[str, Any]],
    change: str,
) -> None:
    root, manifest, contract = contract_repo
    if change == "traversal":
        contract["artifacts"][0]["filename"] = "../outside.json"
    elif change == "tracked_raw":
        next(row for row in contract["artifacts"] if not row["tracked"])["tracked"] = True
    elif change == "missing_field":
        del contract["source_scene"]["sha256"]
    else:
        contract["artifacts"].pop()
    write_document(manifest, contract)
    with pytest.raises(MaterializationError):
        load_manifest(manifest, root)


def test_invalid_json_is_reported_as_invalid_prerequisite(tmp_path: Path) -> None:
    path = tmp_path / "artifact_manifest.json"
    path.write_text("{invalid json")
    with pytest.raises(MaterializationError, match="invalid canonical artifact manifest"):
        load_manifest(path, tmp_path)


def test_materialization_requires_explicit_blender_or_atlas(
    contract_repo: tuple[Path, Path, dict[str, Any]],
) -> None:
    root, manifest, _ = contract_repo
    with pytest.raises(MaterializationError, match="missing Blender prerequisite"):
        materialize(root, manifest)


def test_blender_build_binding_prevents_unmatched_producer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer = {"blender_version": "5.2.1 LTS", "blender_build_hash": "historical-build"}
    monkeypatch.setattr(
        materializer.subprocess,
        "run",
        lambda *args, **kwargs: materializer.subprocess.CompletedProcess(
            args[0], 0, stdout="Blender 5.2.1 LTS\n build hash: different-build\n"
        ),
    )
    with pytest.raises(MaterializationError, match="Blender version/build"):
        materializer._check_blender(tmp_path / "blender", producer)


def test_cli_missing_manifest_does_not_expose_file_not_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(materializer.sys, "argv", ["materialize", "--repo-root", str(tmp_path)])
    with pytest.raises(SystemExit) as result:
        materializer.main()
    assert result.value.code == 2
    error = capsys.readouterr().err
    assert "missing prerequisite canonical artifact manifest" in error
    assert "FileNotFoundError" not in error
