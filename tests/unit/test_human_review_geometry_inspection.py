"""Guard the review evidence boundary and bounded prospective scope."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "human_review/geometry_inspection.py"
SPEC = importlib.util.spec_from_file_location("geometry_inspection", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize(
    "relative",
    [
        "data/finalization/local_run/dataset/evaluation/office/ground_truth.json",
        "data/finalization/local_run/dataset/simulation/office/recipe.json",
        "data/finalization/local_run/diagnostics/office/projection_evaluation.json",
    ],
)
def test_forbidden_files_are_rejected_before_any_read(
    relative: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_read(_path: Path) -> bytes:
        raise AssertionError("forbidden evidence was opened")

    monkeypatch.setattr(Path, "read_bytes", fail_if_read)
    with pytest.raises(ValueError, match="allowlisted public evidence"):
        MODULE.read_allowed(MODULE.ROOT / relative)


def test_scope_keeps_machine_invalid_left_candidate_outside_approved_proposal() -> None:
    value = json.loads(SCRIPT.with_name("geometry_evidence.json").read_text())
    by_route = {row["route"][0]: row for row in value["paths"]}
    left = by_route["pilot_route:left"]
    assert left["support_eligible_for_prospective_scope"] is False
    assert all(
        check["reason"] == "INSUFFICIENT_WALKABLE_CLEARANCE" for check in left["support_checks"]
    )
    low, high = np.asarray(value["prospective_footpoint_bounds_bu"])
    for name in ("pilot_route:direct", "pilot_route:right"):
        route = by_route[name]
        assert route["support_eligible_for_prospective_scope"] is True
        points = np.asarray(route["prospective_foot_polyline_bu"])
        assert np.all(points >= low) and np.all(points <= high)
    assert min(p[0] for p in left["prospective_foot_polyline_bu"]) < low[0]
    assert value["certificate_generated"] is False


def test_only_exact_source_seams_are_requested_for_local_semantic_decision() -> None:
    value = json.loads(SCRIPT.with_name("geometry_evidence.json").read_text())
    assert value["gt_used"] is False
    assert value["portal"] is None
    assert value["enclosure"]["full_component_approval_requested"] is False
    assert {(row["source_object_id"], row["source_face_index"]) for row in value["findings"]} == {
        ("group_0", 1975),
        ("group_0", 2398),
    }
    for row in value["findings"]:
        points = np.asarray(row["triangle_bu"])
        assert np.linalg.norm(np.cross(points[1] - points[0], points[2] - points[0])) == 0
        assert np.all(points[:, 2] == value["prospective_footpoint_bounds_bu"][0][2])
    assert value["legal_actual_support_triangles"] == 10
    assert value["source_triangles_selected_by_envelope"] == 12
