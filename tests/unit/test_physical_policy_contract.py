"""Approved policy behavior and unit boundaries, independent of scene approval."""

import json
import math
from pathlib import Path
from typing import Any

import pytest

from amidst.architectural_scale import load_architectural_scale
from amidst.physical_authority import PhysicalPolicy
from amidst.physical_policy_contract import PhysicalPolicyContract, PhysicalPolicyRuntime
from amidst.scene_geometry import Authority, GeometrySurface

SOURCE = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"


@pytest.fixture
def contract() -> PhysicalPolicyContract:
    runtime = PhysicalPolicyRuntime.model_validate_json(json.dumps({
        "source_asset_sha256": SOURCE,
        "authority": "APPROVED", "approval_id": "explicit-user-policy",
        "policy_config": "configs/physical_authority_policy_school_v3.json",
        "architectural_scale_config": "configs/architectural_scale_school_v3.json",
        "legal_support_contact": "APPROVED_SUPPORT_ONLY",
        "portal_clearance_combination": "MAXIMUM", "stair_direction": "BIDIRECTIONAL",
        "navigation_allowed_roles": ["WALKABLE", "STAIR"],
        "navigation_outside_approved_support": "FORBIDDEN",
        "walkable_representation": "RAW_SUPPORT_SURFACE",
        "footprint_preprocess": "UNION_THEN_EROSION",
    }))
    policy = PhysicalPolicy.model_validate_json(Path(runtime.policy_config).read_bytes())
    scale = load_architectural_scale(runtime.architectural_scale_config, SOURCE)
    return PhysicalPolicyContract(policy, scale, runtime)


def test_approved_policy_has_exact_si_and_native_units(contract: PhysicalPolicyContract) -> None:
    assert contract.policy.authority == "APPROVED"
    assert contract.policy.pending_fields() == ()
    assert contract.policy.body_model == "UPRIGHT_CYLINDER"
    assert contract.policy.trajectory_reference == "FLOOR_CONTACT_POINT"
    report = contract.report()
    values = report["lengths_blender_units"]
    assert isinstance(values, dict)
    assert values["body_radius_bu"] == pytest.approx(12.145748987854251)
    assert values["body_height_bu"] == pytest.approx(68.82591093117409)
    assert values["body_clearance_bu"] == pytest.approx(2.0242914979757085)
    assert values["collision_tolerance_bu"] == pytest.approx(0.04048582995951417)
    assert report["geometry_authority_upgraded"] is False
    assert report["physical_authority_upgraded"] is False


def test_portal_clearance_uses_maximum_without_double_add(contract: PhysicalPolicyContract) -> None:
    assert contract.footprint_radius_m == pytest.approx(0.35)
    assert contract.portal_min_width_m == pytest.approx(0.70)
    assert contract.portal_min_height_m == pytest.approx(1.80)
    updated = contract.policy.model_dump(mode="python")
    updated["body_clearance_m"] = 0.20
    wider = PhysicalPolicyContract(PhysicalPolicy.model_validate(updated), contract.scale,
                                   contract.runtime)
    assert wider.portal_min_width_m == pytest.approx(1.00)
    assert wider.portal_min_height_m == pytest.approx(1.90)


@pytest.mark.parametrize("distance, expected", [(0.04999999, False), (0.05, True), (0.05001, True)])
def test_clearance_equality_is_pass(
    contract: PhysicalPolicyContract, distance: float, expected: bool,
) -> None:
    assert contract.clearance_pass(distance) is expected


@pytest.mark.parametrize(
    "gap, expected", [(-0.1, True), (0.0, True), (0.001, True), (0.00101, False)],
)
def test_obstacle_contact_is_collision(
    contract: PhysicalPolicyContract, gap: float, expected: bool,
) -> None:
    assert contract.is_obstacle_contact(gap) is expected
    assert contract.clearance_pass(0.001) is False


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, True])
def test_nonfinite_or_boolean_contact_clearance_rejected(
    contract: PhysicalPolicyContract, value: Any,
) -> None:
    with pytest.raises(ValueError, match="finite"):
        contract.clearance_pass(value)
    with pytest.raises(ValueError, match="finite"):
        contract.is_obstacle_contact(value)


@pytest.mark.parametrize(
    "role, authority, expected",
    [("WALKABLE", "APPROVED", True), ("STAIR", "APPROVED", True),
     ("WALL", "APPROVED", False), ("OBSTACLE", "APPROVED", False),
     ("WALKABLE", "HUMAN_REVIEW", False)],
)
def test_only_approved_support_allows_legal_contact(
    contract: PhysicalPolicyContract, role: str, authority: str, expected: bool,
) -> None:
    surface = GeometrySurface.model_validate_json(json.dumps({
        "surface_id": "support", "source_object_id": "bound-source", "role": role,
        "floor_ids": ["1F"], "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        "triangles": [[0, 1, 2]], "semantic_authority": authority,
        "physical_authority": authority, "support": "SURFACE",
        "approval_id": "source-bound-support", "evidence_ids": ["face-0"],
    }))
    assert contract.approved_support_contact_allowed(surface) is expected


@pytest.mark.parametrize(
    "change",
    [{"authority": Authority.HUMAN_REVIEW}, {"body_radius_m": None},
     {"body_model": "UPRIGHT_CAPSULE"}, {"collision_comparison": "CONTACT_EXCLUSIVE"}],
)
def test_copied_policy_cannot_bypass_runtime_contract(
    contract: PhysicalPolicyContract, change: dict[str, Any],
) -> None:
    with pytest.raises(ValueError):
        PhysicalPolicyContract(contract.policy.model_copy(update=change), contract.scale,
                               contract.runtime)


def test_runtime_source_and_semantics_cannot_be_forged(contract: PhysicalPolicyContract) -> None:
    with pytest.raises(ValueError, match="source SHA-256"):
        PhysicalPolicyContract(
            contract.policy, contract.scale,
            contract.runtime.model_copy(update={"source_asset_sha256": "a" * 64}),
        )
    with pytest.raises(ValueError):
        PhysicalPolicyContract(contract.policy, contract.scale,
                               contract.runtime.model_copy(update={"stair_direction": "UP"}))
