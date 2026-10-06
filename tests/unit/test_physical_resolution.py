"""Real-evidence binding and fail-closed report regressions."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.architectural_scale import load_architectural_scale
from amidst.geometry_authority import digest
from amidst.physical_authority import (
    PhysicalAuthorityResolution,
    PhysicalPolicy,
    ReadOnlyPhysicalAuthorityProvider,
    canonical_geometry_sha256,
)
from amidst.physical_resolution import resolve_physical_authority, write_report
from amidst.scene_geometry import GeometryAuthorityError, SceneGeometrySnapshot

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "data/scene_audit/phase1_physical_authority_20261006"
BASELINE = ROOT / "data/scene_audit/phase1_geometry_authority_20261006"
SOURCE = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
HISTORICAL_CONFIGS = ROOT / "tests/fixtures/physical_resolution_history_cdeee3e"


def document(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def arguments() -> dict[str, Any]:
    geometry = SceneGeometrySnapshot.model_validate_json((BASELINE / "geometry.json").read_text())
    # The immutable historical geometry uses its original 1:1 diagnostic config.
    scene_config = document(ROOT / "configs/scene_validation_v1.json")
    scene_config["floor_planes"] = document(FOLDER / "resolution.json")["proposed_floor_planes"]
    return {
        "audit": document(ROOT / "data/scene_audit/school_v3_semantic_audit.json"),
        "baseline": document(BASELINE / "authority.json"),
        "geometry": geometry,
        "survey": document(FOLDER / "source_mesh_evidence.json"),
        "selection_config": document(ROOT / "configs/physical_authority_resolution_school_v3.json"),
        "scene_config": scene_config,
        "policy_config": document(FOLDER / "resolution.json")["physical_policy"]["config"],
        "expected_source_sha256": SOURCE,
        "expected_geometry_sha256": canonical_geometry_sha256(geometry),
        "checkpoint_commit": "bb66bb74a4a76430f6fa8f79672345385a79e3f0",
    }


def test_changed_selection_config_cannot_reuse_source_evidence(arguments: dict[str, Any]) -> None:
    args = {**arguments, "selection_config": copy.deepcopy(arguments["selection_config"])}
    args["selection_config"]["floor_stair_review"]["horizontal_normal_abs_z_min"] = 0.5
    with pytest.raises(ValueError, match="selection content binding"):
        resolve_physical_authority(**args)


def test_gt_poison_cannot_enter_physical_resolution(arguments: dict[str, Any]) -> None:
    args = {
        **arguments,
        "policy_config": {**arguments["policy_config"], "ground_truth": [[1.0, 2.0, 3.0]]},
    }
    with pytest.raises(ValueError, match="Ground Truth fields are forbidden"):
        resolve_physical_authority(**args)


def test_modified_or_rendered_source_evidence_rejected(arguments: dict[str, Any]) -> None:
    args = {**arguments, "survey": {**arguments["survey"], "saved": True}}
    with pytest.raises(ValueError, match="read-only and geometry-only"):
        resolve_physical_authority(**args)


def test_independent_geometry_digest_is_required(arguments: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="geometry content binding"):
        resolve_physical_authority(**{**arguments, "expected_geometry_sha256": "a" * 64})


def test_active_scale_cannot_consume_immutable_legacy_geometry(arguments: dict[str, Any]) -> None:
    active = document(ROOT / "configs/scene_validation_school_v3.json")
    with pytest.raises(ValueError, match="scene/geometry scale authority mismatch"):
        resolve_physical_authority(**{**arguments, "scene_config": active})


def test_policy_config_preserves_unapproved_research_parameters() -> None:
    policy = PhysicalPolicy.model_validate_json(
        json.dumps(document(FOLDER / "resolution.json")["physical_policy"]["config"])
    )
    assert len(policy.pending_fields()) == 10
    assert policy.approval_id is None
    assert policy.authority.value == "HUMAN_REVIEW"


def test_real_resolution_artifact_refuses_all_formal_purposes(arguments: dict[str, Any]) -> None:
    sidecar = PhysicalAuthorityResolution.model_validate_json(
        (FOLDER / "physical_authority.json").read_text()
    )
    provider = ReadOnlyPhysicalAuthorityProvider(
        arguments["geometry"], sidecar, SOURCE, arguments["expected_geometry_sha256"]
    )
    assert sidecar.level.value == "PROVISIONAL"
    assert len(provider.get_scopes()) == 4
    for scope in provider.get_scopes():
        with pytest.raises(GeometryAuthorityError) as rejection:
            provider.require_scope(scope.scope_id, purpose=scope.purpose)
        assert any(reason.startswith("POLICY_NOT_APPROVED:") for reason in rejection.value.reasons)


def test_scale_approval_removes_only_scale_gate_and_requires_new_geometry_binding(
    arguments: dict[str, Any],
) -> None:
    scale = load_architectural_scale("configs/architectural_scale_school_v3.json", SOURCE)
    raw = arguments["geometry"].model_dump(mode="json")
    raw.update(
        unit_scale_m=scale.metres_per_blender_unit,
        scale_authority="APPROVED",
        scale_approval_id=scale.approval_id,
        portal_protection_tolerance_m=raw["portal_protection_tolerance_m"]
        * scale.metres_per_blender_unit,
    )
    geometry = SceneGeometrySnapshot.model_validate_json(json.dumps(raw))
    geometry_sha = canonical_geometry_sha256(geometry)
    original = PhysicalAuthorityResolution.model_validate_json(
        (FOLDER / "physical_authority.json").read_text()
    )
    with pytest.raises(ValueError, match="geometry"):
        ReadOnlyPhysicalAuthorityProvider(geometry, original, SOURCE, geometry_sha)
    updated = original.model_dump(mode="json")
    updated["geometry_sha256"] = geometry_sha
    resolution = PhysicalAuthorityResolution.model_validate_json(json.dumps(updated))
    provider = ReadOnlyPhysicalAuthorityProvider(geometry, resolution, SOURCE, geometry_sha)
    for scope in provider.get_scopes():
        with pytest.raises(GeometryAuthorityError) as rejection:
            provider.require_scope(scope.scope_id, purpose=scope.purpose)
        assert "SCALE_NOT_APPROVED" not in rejection.value.reasons
        assert any(reason.startswith("POLICY_NOT_APPROVED:") for reason in rejection.value.reasons)
        assert any(reason.startswith("FLOOR_NOT_APPROVED:") for reason in rejection.value.reasons)
    assert resolution.level.value == "PROVISIONAL"


def test_actual_report_never_certifies_annotation_overlap_or_partial_rays() -> None:
    report = document(FOLDER / "resolution.json")
    assert report["physical_authority"] == "PROVISIONAL"
    assert report["obstacles"]["pair_count"] == 8
    assert report["obstacles"]["repair_count"] == 0
    assert (
        sum(
            row["classification"] == "SEMANTIC_ANNOTATION_DEPTH_OVERLAP_CLEAR_DECLARED_CENTER_PLANE"
            for row in report["obstacles"]["pairs"]
        )
        == 2
    )
    assert all(row["physical_status"] == "HUMAN_REVIEW" for row in report["obstacles"]["pairs"])
    assert all(
        not row["physical_floor_approved"] for row in report["floors_stairs"]["floor_reviews"]
    )
    assert all(row["status"] == "HUMAN_REVIEW" for row in report["floors_stairs"]["stair_reviews"])
    assert report["wall_scope"]["count"] == 73
    assert report["wall_scope"]["ambiguous_patches_promoted"] is False
    assert report["collision_hard_pruning_ready"] is False
    assert all(not row["formal_use_allowed"] for row in report["formal_scope_decisions"])
    assert report["policy"]["gt_used"] is False


def test_manifest_preserves_checkpoint_input_and_artifact_hashes() -> None:
    manifest = document(FOLDER / "manifest.json")
    assert manifest["checkpoint_commit"] == "bb66bb74a4a76430f6fa8f79672345385a79e3f0"
    for name, binding in manifest["inputs"].items():
        if name == "camera_calibration":
            # This historical local artifact is independently checked below.
            continue
        # Exact committed copies of the original configs bind the historical
        # checkpoint even when active configs evolve or Git history is shallow.
        root = (
            HISTORICAL_CONFIGS if name in {"selection_config", "scene_config", "policy_config"}
            else ROOT
        )
        assert digest(root / binding["path"]) == binding["sha256"], name
    for name, expected in manifest["artifacts"].items():
        assert digest(FOLDER / name) == expected


def test_optional_historical_camera_calibration_matches_original_manifest() -> None:
    binding = document(FOLDER / "manifest.json")["inputs"]["camera_calibration"]
    calibration = ROOT / binding["path"]
    if not calibration.is_file():
        pytest.skip(
            f"Optional historical school-v2 calibration prerequisite is missing: {calibration}. "
            "Provision the original local artifact matching manifest SHA-256 "
            f"{binding['sha256']} to run this provenance check. "
            "This prerequisite is independent of school-v3 physical evidence; "
            "tests never generate or download calibration."
        )
    assert digest(calibration) == binding["sha256"]


def test_report_keeps_stair_table_and_known_proposals_for_unmeasured_floors(tmp_path: Path) -> None:
    report = document(FOLDER / "resolution.json")
    output = tmp_path / "resolution.md"
    write_report(report, output)
    rendered = output.read_text()
    stair_table = rendered.split("| Stair |", 1)[1].split("\n\n", 1)[0]
    assert "| A |" in stair_table and "| B |" in stair_table
    assert "Reasons:" not in stair_table
    floor_table = rendered.split("## Floor authority", 1)[1]
    for row in report["floors_stairs"]["floor_reviews"]:
        if row.get("dominant_support") is None:
            plane = report["proposed_floor_planes"][row["floor_id"]]["height_m"]
            assert (
                f"| {row['object_id']} | {row['floor_id']} | {float(plane)} | UNMEASURED"
                in floor_table
            )
    first_floor_mensroom = next(
        line for line in rendered.splitlines() if line.startswith("| 1F | AREA_1F_MENSROOM")
    )
    assert "AREA_2F_MENSROOM" not in first_floor_mensroom
    reference = rendered.split("[mesh evidence](", 1)[1].split(")", 1)[0]
    assert (output.parent / reference).resolve() == (FOLDER / "source_mesh_evidence.json").resolve()
