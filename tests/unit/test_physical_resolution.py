"""Real-evidence binding and fail-closed report regressions."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

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


def document(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def arguments() -> dict[str, Any]:
    geometry = SceneGeometrySnapshot.model_validate_json((BASELINE / "geometry.json").read_text())
    return {
        "audit": document(ROOT / "data/scene_audit/school_v3_semantic_audit.json"),
        "baseline": document(BASELINE / "authority.json"),
        "geometry": geometry,
        "survey": document(FOLDER / "source_mesh_evidence.json"),
        "selection_config": document(ROOT / "configs/physical_authority_resolution_school_v3.json"),
        "scene_config": document(ROOT / "configs/scene_validation_school_v3.json"),
        "policy_config": document(ROOT / "configs/physical_authority_policy_school_v3.json"),
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


def test_policy_config_preserves_unapproved_research_parameters() -> None:
    policy = PhysicalPolicy.model_validate_json(
        (ROOT / "configs/physical_authority_policy_school_v3.json").read_text()
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
    for binding in manifest["inputs"].values():
        assert digest(ROOT / binding["path"]) == binding["sha256"]
    for name, expected in manifest["artifacts"].items():
        assert digest(FOLDER / name) == expected


def test_report_keeps_stair_table_and_known_proposals_for_unmeasured_floors(tmp_path: Path) -> None:
    report = document(FOLDER / "resolution.json")
    report["proposed_floor_planes"] = document(ROOT / "configs/scene_validation_school_v3.json")[
        "floor_planes"
    ]
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
