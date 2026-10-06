"""Source-bound regressions for real school mesh evidence and authority forgery."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.geometry_authority import classify_walls, review_authority, write_report

ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = ROOT / "data" / "scene_audit"
AUTHORITY_DIR = AUDIT_DIR / "phase1_geometry_authority_20261006"
Document = dict[str, Any]
Evidence = tuple[Document, Document, Document, Document]


@pytest.fixture(scope="module")
def evidence() -> Evidence:
    paths = (
        AUDIT_DIR / "phase1_wall_candidates_20261005.json",
        AUTHORITY_DIR / "wall_meshes.json",
        AUDIT_DIR / "school_v3_semantic_audit.json",
        ROOT / "configs" / "scene_validation_school_v3.json",
    )
    candidates, meshes, audit, config = (
        json.loads(path.read_text(encoding="utf-8")) for path in paths
    )
    return candidates, meshes, audit, config


@pytest.fixture(scope="module")
def unauthorised_report(evidence: Evidence) -> Document:
    """One complete geometry review, shared by the real-evidence assertions."""
    candidates, meshes, audit, config = evidence
    report, _ = review_authority(
        candidates,
        meshes,
        audit,
        config,
        expected_source_sha256=candidates["source"]["sha256"],
    )
    return report


def selected_evidence(evidence: Evidence, identity: str) -> tuple[Document, Document, Document]:
    """Retain a real patch and its transitive legacy parallel-support references."""
    candidates, meshes, audit, _ = evidence
    indexed = {row["candidate_id"]: row for row in candidates["candidates"]}
    selected: set[str] = set()
    pending = [identity]
    while pending:
        current = pending.pop()
        if current in selected:
            continue
        selected.add(current)
        pending.extend(row["paired_patch"] for row in indexed[current]["thickness_evidence"])
    document = copy.deepcopy(
        {key: value for key, value in candidates.items() if key != "candidates"}
    )
    document["candidates"] = [
        copy.deepcopy(row) for row in candidates["candidates"] if row["candidate_id"] in selected
    ]
    exact = copy.deepcopy({key: value for key, value in meshes.items() if key != "patches"})
    exact["patches"] = [
        copy.deepcopy(row) for row in meshes["patches"] if row["candidate_id"] in selected
    ]
    return document, exact, audit


def patch(document: Document, identity: str) -> Document:
    return next(row for row in document["candidates"] if row["candidate_id"] == identity)


def test_authentic_mesh_classification_matches_independent_exact_review(
    unauthorised_report: Document,
) -> None:
    wall = unauthorised_report["wall_summary"]
    assert wall["baseline_seeds"] == 81
    assert wall["baseline_human_review"] == 1491
    assert wall["final"] == {
        "APPROVED": 0,
        "HIGH_CONFIDENCE": 73,
        "HUMAN_REVIEW": 1422,
        "REJECTED": 77,
    }
    assert set(wall["seed_downgrades"]) == {
        "WALL-PATCH-00214", "WALL-PATCH-00215", "WALL-PATCH-00228",
        "WALL-PATCH-00229", "WALL-PATCH-00232", "WALL-PATCH-00280",
        "WALL-PATCH-00284", "WALL-PATCH-00587", "WALL-PATCH-00591",
        "WALL-PATCH-00720", "WALL-PATCH-00828",
    }
    assert set(wall["new_promotions"]) == {
        "WALL-PATCH-00311", "WALL-PATCH-00421", "WALL-PATCH-00447",
    }
    assert unauthorised_report["physical_authority"] == "PROVISIONAL"
    assert unauthorised_report["provider"]["physical_complete"] is False
    assert unauthorised_report["provider"]["default_approved_colliders"] == 0


def test_cross_floor_doorway_intersection_is_hard_rejected(
    unauthorised_report: Document,
) -> None:
    row = next(
        row for row in unauthorised_report["walls"] if row["candidate_id"] == "WALL-PATCH-00734"
    )
    assert row["floor"] == "2F"
    assert row["status"] == "REJECTED"
    assert "PORTAL_1F_SIDE_ENTRANCE" in row["protected_portal_conflicts"]
    assert unauthorised_report["doorway_protection"]["protected_portals"] == 28
    assert unauthorised_report["doorway_protection"]["accepted_wall_contacts"] == 0


def test_forged_legacy_seed_does_not_relax_original_width_gate(evidence: Evidence) -> None:
    document, meshes, audit = selected_evidence(evidence, "WALL-PATCH-00168")
    candidate = patch(document, "WALL-PATCH-00168")
    candidate["status"] = "AUTO_CONFIRMED_WALL"
    assert candidate["extent"] < document["parameters"]["auto_min_extent"]
    rows = classify_walls(document, meshes, audit)
    row = next(row for row in rows if row["candidate_id"] == candidate["candidate_id"])
    assert row["status"] == "HUMAN_REVIEW"
    assert "NARROW_DOOR_PANEL_COLUMN_OR_DECOR_REVIEW" in row["reasons"]


@pytest.mark.parametrize("minimum", [0.0, True, float("nan"), float("inf")])
def test_claimed_seed_cannot_change_fixed_extraction_policy(
    evidence: Evidence, minimum: float | bool,
) -> None:
    document, meshes, audit = selected_evidence(evidence, "WALL-PATCH-00168")
    patch(document, "WALL-PATCH-00168")["status"] = "AUTO_CONFIRMED_WALL"
    document["parameters"]["auto_min_extent"] = minimum
    with pytest.raises(ValueError, match="threshold policy"):
        classify_walls(document, meshes, audit)


def test_forged_nearby_metadata_cannot_hide_continuous_walkable_intrusion(
    evidence: Evidence,
) -> None:
    document, meshes, audit = selected_evidence(evidence, "WALL-PATCH-00280")
    patch(document, "WALL-PATCH-00280")["walkable_relation"]["nearby"] = [
        "WALK_1F_CORRIDOR_02"
    ]
    row = next(
        row for row in classify_walls(document, meshes, audit)
        if row["candidate_id"] == "WALL-PATCH-00280"
    )
    assert row["status"] == "HUMAN_REVIEW"
    assert "CONTINUOUS_WALKABLE_INTERIOR_INTRUSION" in row["reasons"]
    assert "WALK_1F_OFFICE" in row["actual_nearby_walkables"]
    intrusion = next(
        item for item in row["continuous_walkable_intrusions"]
        if item["walkable_id"] == "WALK_1F_OFFICE"
    )
    assert intrusion["continuous_intrusion_length"] == pytest.approx(2.523101806640625)


@pytest.mark.parametrize("changed", ["candidate", "audit"])
def test_public_review_api_rejects_stale_content_bindings(
    evidence: Evidence, changed: str,
) -> None:
    candidates, meshes, audit, config = evidence
    if changed == "candidate":
        candidates = copy.deepcopy(candidates)
        patch(candidates, "WALL-PATCH-00280")["walkable_relation"]["nearby"] = []
        message = "candidate content"
    else:
        audit = copy.deepcopy(audit)
        audit["objects"][0]["vertices"][0][0] += 1.0
        message = "semantic audit content"
    with pytest.raises(ValueError, match=message):
        review_authority(
            candidates,
            meshes,
            audit,
            config,
            expected_source_sha256=candidates["source"]["sha256"],
        )


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("floor_contact_offset", "floor/offset/section"),
        ("bounds", "bounds differ"),
        ("tangent", "canonical horizontal tangent"),
        ("tangent_interval", "tangent interval differs"),
    ],
)
def test_stale_candidate_spatial_metadata_is_rejected(
    evidence: Evidence, field: str, message: str,
) -> None:
    document, meshes, audit = selected_evidence(evidence, "WALL-PATCH-00280")
    candidate = patch(document, "WALL-PATCH-00280")
    if field == "floor_contact_offset":
        candidate[field] = 0.0
    elif field == "bounds":
        candidate[field]["minimum"][0] -= 1.0
    else:
        candidate[field][0] += 1.0
    with pytest.raises(ValueError, match=message):
        classify_walls(document, meshes, audit)


def test_changed_actual_geometry_cannot_reuse_recorded_content_hash(evidence: Evidence) -> None:
    document, meshes, audit = selected_evidence(evidence, "WALL-PATCH-00280")
    raw = next(row for row in meshes["patches"] if row["candidate_id"] == "WALL-PATCH-00280")
    raw["vertices"][0][0] += 0.25
    with pytest.raises(ValueError, match="exact geometry content hash"):
        classify_walls(document, meshes, audit)


def test_mismatched_source_faces_fail_before_geometry_classification(evidence: Evidence) -> None:
    document, meshes, audit = selected_evidence(evidence, "WALL-PATCH-00280")
    raw = next(row for row in meshes["patches"] if row["candidate_id"] == "WALL-PATCH-00280")
    raw["source_face_indices"][0] += 1
    with pytest.raises(ValueError, match="source face identity differs"):
        classify_walls(document, meshes, audit)


def test_report_without_role_authorization_does_not_claim_obstacle_approval(
    unauthorised_report: Document, tmp_path: Path,
) -> None:
    reviews = unauthorised_report["physical_review"]["obstacle_reviews"]
    assert len(reviews) == 19
    assert all(row["semantic_role_status"] == "HUMAN_REVIEW" for row in reviews)
    output = tmp_path / "authority.md"
    write_report(unauthorised_report, output)
    text = output.read_text(encoding="utf-8")
    assert "19 個 OBSTACLE；其中 0 個 semantic roles APPROVED。" in text
    assert "19 個已確認 semantic roles APPROVED" not in text


def test_report_counts_follow_measured_subset(tmp_path: Path) -> None:
    """A smaller reviewed scope must not inherit the school-wide narrative counts."""
    stored = json.loads((AUTHORITY_DIR / "authority.json").read_text(encoding="utf-8"))
    stored["physical_review"]["obstacle_reviews"] = [
        {
            "object_id": "reviewed-obstacle",
            "semantic_role_status": "HUMAN_REVIEW",
            "physical_geometry_status": "HUMAN_REVIEW",
            "conflicts": {"walkable": ["walkable"], "portal": ["one", "two"]},
        }
    ]
    stored["walls"] = []
    stored["wall_summary"]["seed_downgrades"] = []
    stored["wall_summary"]["new_promotions"] = []
    output = tmp_path / "subset.md"
    write_report(stored, output)
    text = output.read_text(encoding="utf-8")
    assert "1 個 OBSTACLE；其中 0 個 semantic roles APPROVED。" in text
    assert "WALKABLE 超過配置 contact ratio：1 pairs；PORTAL：2 pairs。" in text
    assert "0 個 seeds 降級" in text
