"""Purpose scopes cannot turn provisional geometry into physical certification."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.physical_authority import (
    PhysicalAuthorityLevel,
    PhysicalAuthorityResolution,
    PhysicalPolicy,
    PhysicalPurpose,
    ReadOnlyPhysicalAuthorityProvider,
    canonical_geometry_sha256,
)
from amidst.scene_geometry import (
    Authority,
    GeometryAuthorityError,
    SceneGeometrySnapshot,
)

SOURCE = "a" * 64


def geometry_payload() -> dict[str, Any]:
    return {
        "source_sha256": SOURCE,
        "scene_id": "authority-test",
        "unit_scale_m": 1.0,
        "scale_authority": "APPROVED",
        "scale_approval_id": "human-scale",
        "floors": [
            {
                "floor_id": "1F",
                "point": [0.0, 0.0, 0.0],
                "normal": [0.0, 0.0, 1.0],
                "authority": "APPROVED",
                "approval_id": "human-floor",
                "evidence_ids": ["floor-evidence"],
            }
        ],
        "surfaces": [
            {
                "surface_id": "walk",
                "source_object_id": "floor-mesh",
                "role": "WALKABLE",
                "floor_ids": ["1F"],
                "vertices": [[0.0, 0.0, 0.0], [4.0, 0.0, 0.0], [0.0, 4.0, 0.0]],
                "triangles": [[0, 1, 2]],
                "semantic_authority": "APPROVED",
                "physical_authority": "APPROVED",
                "support": "SURFACE",
                "approval_id": "human-walk",
                "evidence_ids": ["source-floor-face"],
            },
            {
                "surface_id": "solid",
                "source_object_id": "actual-solid",
                "role": "OBSTACLE",
                "floor_ids": ["1F"],
                "vertices": [[1.0, 1.0, 0.0], [2.0, 1.0, 0.0], [1.0, 2.0, 0.0], [1.0, 1.0, 1.0]],
                "triangles": [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]],
                "semantic_authority": "APPROVED",
                "physical_authority": "APPROVED",
                "support": "VOLUME",
                "approval_id": "human-volume",
                "evidence_ids": ["source-solid-faces"],
                "blocks_movement": True,
                "occludes_visibility": True,
            },
        ],
    }


def geometry(data: dict[str, Any] | None = None) -> SceneGeometrySnapshot:
    return SceneGeometrySnapshot.model_validate_json(json.dumps(data or geometry_payload()))


def policy_payload(approved: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {"policy_id": "body-policy", "config_version": "test-v1"}
    if approved:
        data.update(
            {
                "authority": "APPROVED",
                "body_model": "UPRIGHT_CAPSULE",
                "trajectory_reference": "FLOOR_CONTACT_POINT",
                "body_radius_m": 0.25,
                "body_height_m": 1.8,
                "body_clearance_m": 0.02,
                "portal_horizontal_clearance_m": 0.1,
                "portal_vertical_clearance_m": 0.1,
                "collision_tolerance_m": 0.001,
                "clearance_comparison": "MINIMUM_INCLUSIVE",
                "collision_comparison": "CONTACT_INCLUSIVE",
                "approval_id": "test-human-policy",
                "evidence_ids": ["test-policy-review"],
            }
        )
    return data


def scope_payload(
    identity: str = "positive",
    *,
    purpose: str = "KNOWN_COLLISION_PRUNING",
    approved: bool = True,
    complete: bool = False,
) -> dict[str, Any]:
    data = {
        "scope_id": identity,
        "purpose": purpose,
        "floor_ids": ["1F"],
        "surface_ids": ["solid", "walk"] if complete else ["solid"],
        "coverage": "COMPLETE" if complete else "PARTIAL",
        "authority": "APPROVED" if approved else "HUMAN_REVIEW",
    }
    if approved:
        data.update({"approval_id": "test-human-scope", "evidence_ids": ["source-scope-review"]})
    return data


def resolution_payload(
    snapshot: SceneGeometrySnapshot,
    *,
    approved: bool = True,
) -> dict[str, Any]:
    return {
        "source_sha256": SOURCE,
        "geometry_sha256": canonical_geometry_sha256(snapshot),
        "level": "PARTIAL_APPROVED" if approved else "PROVISIONAL",
        "policy": policy_payload(approved),
        "scopes": [scope_payload(approved=approved)],
    }


def provider(
    snapshot: SceneGeometrySnapshot,
    data: dict[str, Any],
) -> ReadOnlyPhysicalAuthorityProvider:
    return ReadOnlyPhysicalAuthorityProvider(
        snapshot,
        PhysicalAuthorityResolution.model_validate_json(json.dumps(data)),
        SOURCE,
        canonical_geometry_sha256(snapshot),
    )


def test_pending_policy_is_explicit_and_formal_use_refuses() -> None:
    snapshot = geometry()
    result = provider(snapshot, resolution_payload(snapshot, approved=False))
    assert result.resolution.level == PhysicalAuthorityLevel.PROVISIONAL
    assert result.resolution.policy.body_clearance_m is None
    with pytest.raises(GeometryAuthorityError) as refusal:
        result.require_scope("positive", purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING)
    assert "POLICY_PENDING:body_clearance_m" in refusal.value.reasons
    assert "POLICY_PENDING:portal_vertical_clearance_m" in refusal.value.reasons
    assert "POLICY_PENDING:collision_tolerance_m" in refusal.value.reasons
    assert "SCOPE_NOT_APPROVED:positive" in refusal.value.reasons


def test_partial_positive_rejection_does_not_certify_free_space_or_topology() -> None:
    snapshot = geometry()
    result = provider(snapshot, resolution_payload(snapshot))
    inputs = result.require_scope("positive", purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING)
    assert inputs.scope.coverage == "PARTIAL"
    assert [item.surface_id for item in inputs.colliders] == ["solid"]
    assert result.geometry.physical_complete is False
    for purpose in (
        PhysicalPurpose.COLLISION_FREE_VALIDATION,
        PhysicalPurpose.TOPOLOGY_VALIDATION,
        PhysicalPurpose.PHYSICAL_VALIDITY_METRICS,
    ):
        with pytest.raises(GeometryAuthorityError, match="PHYSICAL_PURPOSE_MISMATCH"):
            result.require_scope("positive", purpose=purpose)


def test_high_wall_remains_provisional_even_when_policy_is_approved() -> None:
    data = geometry_payload()
    wall = dict(data["surfaces"][0])
    wall.update(
        {
            "surface_id": "high-wall",
            "role": "WALL",
            "semantic_authority": "HIGH_CONFIDENCE",
            "physical_authority": "HIGH_CONFIDENCE",
            "vertices": [[4.0, 0.0, 0.0], [4.0, 4.0, 0.0], [4.0, 0.0, 2.0]],
            "blocks_movement": True,
        }
    )
    data["surfaces"].append(wall)
    snapshot = geometry(data)
    resolution = resolution_payload(snapshot, approved=False)
    resolution["policy"] = policy_payload()
    resolution["scopes"][0]["surface_ids"] = ["high-wall"]
    result = provider(snapshot, resolution)
    with pytest.raises(GeometryAuthorityError) as refusal:
        result.require_scope("positive", purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING)
    assert "SURFACE_NOT_APPROVED:high-wall" in refusal.value.reasons
    assert result.geometry.surfaces[-1].physical_authority == Authority.HIGH_CONFIDENCE
    resolution["scopes"][0].update(
        {"authority": "APPROVED", "approval_id": "forged", "evidence_ids": ["unsupported"]}
    )
    resolution["level"] = "PARTIAL_APPROVED"
    with pytest.raises(GeometryAuthorityError, match="SURFACE_NOT_APPROVED"):
        provider(snapshot, resolution)


def test_role_approval_cannot_certify_obstacle_footprint() -> None:
    data = geometry_payload()
    data["surfaces"][1].update(
        {
            "support": "FOOTPRINT",
            "physical_authority": "HUMAN_REVIEW",
            "vertices": [[1.0, 1.0, 0.0], [2.0, 1.0, 0.0], [1.0, 2.0, 0.0]],
            "triangles": [[0, 1, 2]],
        }
    )
    snapshot = geometry(data)
    result = provider(snapshot, resolution_payload(snapshot, approved=False))
    with pytest.raises(GeometryAuthorityError) as refusal:
        result.require_scope("positive", purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING)
    assert "OBSTACLE_VOLUME_NOT_APPROVED:solid" in refusal.value.reasons
    assert result.geometry.surfaces[1].blocks_movement is True


@pytest.mark.parametrize(
    "field",
    [
        "body_model",
        "trajectory_reference",
        "body_radius_m",
        "body_height_m",
        "body_clearance_m",
        "portal_horizontal_clearance_m",
        "portal_vertical_clearance_m",
        "collision_tolerance_m",
        "clearance_comparison",
        "collision_comparison",
    ],
)
def test_approved_policy_cannot_hide_pending_parameter(field: str) -> None:
    data = policy_payload()
    data[field] = None
    with pytest.raises(ValidationError, match="pending fields"):
        PhysicalPolicy.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("value", [-0.001, float("nan"), float("inf"), True])
@pytest.mark.parametrize("field", ["body_clearance_m", "collision_tolerance_m"])
def test_invalid_clearance_or_tolerance_fails_fast(field: str, value: float | bool) -> None:
    data = policy_payload()
    data[field] = value
    with pytest.raises(ValidationError):
        PhysicalPolicy.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("field", ["body_radius_m", "body_height_m"])
def test_zero_body_dimension_rejected(field: str) -> None:
    data = policy_payload()
    data[field] = 0.0
    with pytest.raises(ValidationError):
        PhysicalPolicy.model_validate_json(json.dumps(data))


def test_capsule_height_includes_both_hemispheres() -> None:
    data = policy_payload()
    data["body_height_m"] = 0.4
    with pytest.raises(ValidationError, match="hemispheres"):
        PhysicalPolicy.model_validate_json(json.dumps(data))


@pytest.mark.parametrize("field", ["approval_id", "evidence_ids"])
def test_approved_policy_requires_traceable_review(field: str) -> None:
    data = policy_payload()
    del data[field]
    with pytest.raises(ValidationError, match="approval_id and evidence_ids"):
        PhysicalPolicy.model_validate_json(json.dumps(data))


def test_blank_approval_identity_cannot_certify_policy_or_scope() -> None:
    policy = policy_payload()
    policy["approval_id"] = "   "
    with pytest.raises(ValidationError, match="approval_id and evidence_ids"):
        PhysicalPolicy.model_validate_json(json.dumps(policy))
    snapshot = geometry()
    resolution = resolution_payload(snapshot)
    resolution["scopes"][0]["approval_id"] = "   "
    with pytest.raises(ValidationError, match="approval_id and evidence_ids"):
        provider(snapshot, resolution)


def test_clearance_zero_is_explicit_policy_not_missing_or_numerical_epsilon() -> None:
    data = policy_payload()
    for field in (
        "body_clearance_m",
        "portal_horizontal_clearance_m",
        "portal_vertical_clearance_m",
        "collision_tolerance_m",
    ):
        data[field] = 0.0
    approved = PhysicalPolicy.model_validate_json(json.dumps(data))
    assert approved.pending_fields() == ()
    assert approved.collision_tolerance_m == 0.0
    data["numeric_epsilon"] = 1e-9
    with pytest.raises(ValidationError, match="Extra inputs"):
        PhysicalPolicy.model_validate_json(json.dumps(data))


@pytest.mark.parametrize(
    "purpose",
    [
        "COLLISION_FREE_VALIDATION",
        "TOPOLOGY_VALIDATION",
        "PHYSICAL_VALIDITY_METRICS",
    ],
)
def test_partial_scope_cannot_claim_formal_non_pruning_purpose(purpose: str) -> None:
    snapshot = geometry()
    data = resolution_payload(snapshot)
    data["scopes"][0]["purpose"] = purpose
    with pytest.raises(ValidationError, match="COMPLETE coverage"):
        provider(snapshot, data)


def test_complete_scope_cannot_omit_known_geometry() -> None:
    snapshot = geometry()
    data = resolution_payload(snapshot)
    data["scopes"][0]["coverage"] = "COMPLETE"
    with pytest.raises(GeometryAuthorityError) as refusal:
        provider(snapshot, data)
    assert "SURFACE_SCOPE_OMITTED:walk" in refusal.value.reasons
    assert "WALKABLE_SCOPE_NOT_APPROVED:1F" in refusal.value.reasons


def test_known_high_wall_cannot_be_omitted_from_complete_physics() -> None:
    data = geometry_payload()
    wall = dict(data["surfaces"][0])
    wall.update(
        {
            "surface_id": "unresolved-wall",
            "role": "WALL",
            "semantic_authority": "HIGH_CONFIDENCE",
            "physical_authority": "HIGH_CONFIDENCE",
            "vertices": [[4.0, 0.0, 0.0], [4.0, 4.0, 0.0], [4.0, 0.0, 2.0]],
            "blocks_movement": True,
        }
    )
    data["surfaces"].append(wall)
    snapshot = geometry(data)
    resolution = resolution_payload(snapshot)
    resolution["scopes"][0] = scope_payload(complete=True)
    with pytest.raises(GeometryAuthorityError, match="SURFACE_SCOPE_OMITTED:unresolved-wall"):
        provider(snapshot, resolution)


def test_proposed_floor_and_scale_still_refuse_with_review_sidecar() -> None:
    data = geometry_payload()
    data["scale_authority"] = "HUMAN_REVIEW"
    data["scale_approval_id"] = None
    data["floors"][0]["authority"] = "HUMAN_REVIEW"
    for surface in data["surfaces"]:
        surface["physical_authority"] = "HUMAN_REVIEW"
    snapshot = geometry(data)
    result = provider(snapshot, resolution_payload(snapshot, approved=False))
    with pytest.raises(GeometryAuthorityError) as refusal:
        result.require_scope("positive", purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING)
    assert "FLOOR_NOT_APPROVED:1F" in refusal.value.reasons
    assert "SCALE_NOT_APPROVED" in refusal.value.reasons


def test_complete_scope_must_include_and_approve_portal() -> None:
    data = geometry_payload()
    aperture = dict(data["surfaces"][0])
    aperture.update(
        {
            "surface_id": "aperture",
            "source_object_id": "actual-doorway",
            "role": "PORTAL",
            "vertices": [[3.0, 0.0, 0.0], [3.0, 1.0, 0.0], [3.0, 0.0, 2.0]],
            "support": "ANNOTATION",
            "physical_authority": "HUMAN_REVIEW",
        }
    )
    data["surfaces"].append(aperture)
    data["portals"] = [
        {
            "portal_id": "door",
            "floor_id": "1F",
            "surface_id": "aperture",
            "adjacent_walkable_ids": ["walk"],
            "authority": "HUMAN_REVIEW",
        }
    ]
    snapshot = geometry(data)
    resolution = resolution_payload(snapshot)
    resolution["scopes"][0] = scope_payload(complete=True)
    with pytest.raises(GeometryAuthorityError, match="PORTAL_SCOPE_OMITTED:door"):
        provider(snapshot, resolution)
    resolution["scopes"][0]["portal_ids"] = ["door"]
    with pytest.raises(GeometryAuthorityError, match="PORTAL_NOT_APPROVED:door"):
        provider(snapshot, resolution)


def test_stair_opening_or_clearance_review_blocks_complete_topology_scope() -> None:
    data = geometry_payload()
    upper_floor = dict(data["floors"][0])
    upper_floor.update({"floor_id": "2F", "point": [0.0, 0.0, 3.0]})
    data["floors"].append(upper_floor)
    upper_walk = dict(data["surfaces"][0])
    upper_walk.update(
        {
            "surface_id": "upper-walk",
            "floor_ids": ["2F"],
            "vertices": [[0.0, 0.0, 3.0], [4.0, 0.0, 3.0], [0.0, 4.0, 3.0]],
        }
    )
    data["surfaces"].append(upper_walk)
    stair_path = dict(data["surfaces"][0])
    stair_path.update(
        {
            "surface_id": "actual-stair",
            "role": "STAIR",
            "floor_ids": ["1F", "2F"],
            "physical_authority": "HUMAN_REVIEW",
            "vertices": [[0.0, 0.0, 0.0], [0.0, 3.0, 3.0], [1.0, 3.0, 3.0]],
        }
    )
    data["surfaces"].append(stair_path)
    data["stairs"] = [
        {
            "stair_id": "A",
            "floor_from": "1F",
            "floor_to": "2F",
            "entry_point": [0.0, 0.0, 0.0],
            "exit_point": [0.0, 3.0, 3.0],
            "path_surface_ids": ["actual-stair"],
            "connectivity_authority": "APPROVED",
            "opening_authority": "HUMAN_REVIEW",
            "clearance_authority": "HUMAN_REVIEW",
            "approval_id": "connectivity-only-review",
            "evidence_ids": ["actual-connected-path"],
        }
    ]
    snapshot = geometry(data)
    resolution = resolution_payload(snapshot)
    resolution["scopes"][0] = scope_payload(
        purpose="TOPOLOGY_VALIDATION",
        complete=True,
    )
    resolution["scopes"][0].update(
        {
            "floor_ids": ["1F", "2F"],
            "surface_ids": ["walk", "upper-walk", "solid"],
            "stair_ids": ["A"],
        }
    )
    with pytest.raises(GeometryAuthorityError) as refusal:
        provider(snapshot, resolution)
    assert "STAIR_NOT_APPROVED:A:opening_authority" in refusal.value.reasons
    assert "STAIR_NOT_APPROVED:A:clearance_authority" in refusal.value.reasons


def test_partial_positive_scope_cannot_claim_floor_without_collider() -> None:
    data = geometry_payload()
    upper_floor = dict(data["floors"][0])
    upper_floor.update({"floor_id": "2F", "point": [0.0, 0.0, 3.0]})
    data["floors"].append(upper_floor)
    snapshot = geometry(data)
    resolution = resolution_payload(snapshot)
    resolution["scopes"][0]["floor_ids"] = ["1F", "2F"]
    with pytest.raises(GeometryAuthorityError, match="MOVEMENT_COLLIDER_MISSING:2F"):
        provider(snapshot, resolution)


def test_all_purposes_and_floors_required_for_overall_approved() -> None:
    source = geometry_payload()
    source["physical_complete"] = True
    snapshot = geometry(source)
    data = resolution_payload(snapshot)
    data["level"] = "APPROVED"
    with pytest.raises(ValueError, match="level does not match"):
        provider(snapshot, data)
    data["scopes"] = [
        scope_payload(purpose.value, purpose=purpose.value, complete=True)
        for purpose in PhysicalPurpose
    ]
    approved = provider(snapshot, data)
    assert approved.resolution.level == PhysicalAuthorityLevel.APPROVED
    inputs = approved.require_scope(
        "PHYSICAL_VALIDITY_METRICS",
        purpose=PhysicalPurpose.PHYSICAL_VALIDITY_METRICS,
    )
    assert [item.surface_id for item in inputs.surfaces] == ["solid", "walk"]


def test_sidecar_cannot_overwrite_snapshot_global_incompleteness() -> None:
    snapshot = geometry()
    data = resolution_payload(snapshot)
    data["scopes"] = [
        scope_payload(purpose.value, purpose=purpose.value, complete=True)
        for purpose in PhysicalPurpose
    ]
    partial = provider(snapshot, data)
    assert partial.resolution.level == PhysicalAuthorityLevel.PARTIAL_APPROVED
    data["level"] = "APPROVED"
    with pytest.raises(ValueError, match="level does not match"):
        provider(snapshot, data)


def test_source_and_exact_geometry_mismatch_cannot_rebind_approval() -> None:
    snapshot = geometry()
    data = resolution_payload(snapshot)
    data["source_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="source SHA-256"):
        provider(snapshot, data)
    data = resolution_payload(snapshot)
    data["geometry_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="geometry SHA-256"):
        provider(snapshot, data)
    modified = geometry_payload()
    modified["surfaces"][1]["vertices"][1][0] = 3.0
    with pytest.raises(ValueError, match="geometry SHA-256"):
        ReadOnlyPhysicalAuthorityProvider(
            geometry(modified),
            PhysicalAuthorityResolution.model_validate_json(
                json.dumps(
                    resolution_payload(snapshot),
                )
            ),
            SOURCE,
            canonical_geometry_sha256(snapshot),
        )


@pytest.mark.parametrize("where", ["root", "policy", "scope"])
@pytest.mark.parametrize("field", ["ground_truth", "gt_path", "bpy"])
def test_gt_or_platform_objects_cannot_enter_authority(where: str, field: str) -> None:
    snapshot = geometry()
    data = resolution_payload(snapshot)
    target = data if where == "root" else data["policy"] if where == "policy" else data["scopes"][0]
    target[field] = "forged"
    with pytest.raises(ValidationError, match="Extra inputs"):
        provider(snapshot, data)


def test_unchecked_nested_policy_copy_is_revalidated_at_provider_boundary() -> None:
    snapshot = geometry()
    valid = PhysicalAuthorityResolution.model_validate_json(
        json.dumps(resolution_payload(snapshot))
    )
    forged = valid.model_copy(
        update={
            "policy": valid.policy.model_copy(
                update={
                    "body_radius_m": -5.0,
                }
            )
        }
    )
    with pytest.raises(ValidationError):
        ReadOnlyPhysicalAuthorityProvider(
            snapshot, forged, SOURCE, canonical_geometry_sha256(snapshot)
        )


def test_unchecked_scope_copy_cannot_upgrade_high_wall() -> None:
    data = geometry_payload()
    data["surfaces"][1]["physical_authority"] = "HIGH_CONFIDENCE"
    snapshot = geometry(data)
    resolution = resolution_payload(snapshot, approved=False)
    resolution["policy"] = policy_payload()
    valid = PhysicalAuthorityResolution.model_validate_json(json.dumps(resolution))
    forged_scope = valid.scopes[0].model_copy(
        update={
            "authority": Authority.APPROVED,
            "approval_id": "forged",
            "evidence_ids": ("forged",),
        }
    )
    forged = valid.model_copy(
        update={"scopes": (forged_scope,), "level": PhysicalAuthorityLevel.PARTIAL_APPROVED}
    )
    with pytest.raises(GeometryAuthorityError, match="SURFACE_NOT_APPROVED"):
        ReadOnlyPhysicalAuthorityProvider(
            snapshot, forged, SOURCE, canonical_geometry_sha256(snapshot)
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("surface_ids", ["missing"]),
        ("portal_ids", ["missing"]),
        ("stair_ids", ["missing"]),
        ("floor_ids", ["3F"]),
    ],
)
def test_invalid_geometry_references_fail_fast(field: str, value: list[str]) -> None:
    snapshot = geometry()
    data = resolution_payload(snapshot, approved=False)
    data["scopes"][0][field] = value
    with pytest.raises(ValueError, match="reference"):
        provider(snapshot, data)


def test_scope_with_unresolved_conflict_cannot_claim_approved() -> None:
    snapshot = geometry()
    data = resolution_payload(snapshot)
    data["scopes"][0]["unresolved_reasons"] = ["OBSTACLE_PORTAL_CONFLICT"]
    with pytest.raises(ValidationError, match="unresolved reasons"):
        provider(snapshot, data)


def test_purpose_required_and_missing_scope_refusal_is_structured() -> None:
    snapshot = geometry()
    result = provider(snapshot, resolution_payload(snapshot))
    with pytest.raises(GeometryAuthorityError) as refusal:
        result.require_scope("missing", purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING)
    assert refusal.value.reasons == ("PHYSICAL_SCOPE_MISSING:missing",)
    with pytest.raises(TypeError, match="explicit PhysicalPurpose"):
        result.require_scope("positive", purpose="KNOWN_COLLISION_PRUNING")  # type: ignore[arg-type]


def test_read_only_inputs_and_provider_are_immutable() -> None:
    snapshot = geometry()
    result = provider(snapshot, resolution_payload(snapshot))
    inputs = result.require_scope("positive", purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING)
    with pytest.raises(FrozenInstanceError):
        inputs.source_sha256 = "b" * 64  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.geometry = geometry()  # type: ignore[misc]
    with pytest.raises(ValidationError):
        inputs.policy.body_radius_m = 2.0  # type: ignore[misc]


def test_json_roundtrip_ignores_whitespace_and_output_directory(tmp_path: Path) -> None:
    snapshot = geometry()
    data = resolution_payload(snapshot)
    outputs = []
    for directory, indent in (("first", None), ("second", 2)):
        destination = tmp_path / directory
        destination.mkdir()
        geometry_path = destination / "geometry.json"
        resolution_path = destination / "physical.json"
        geometry_path.write_text(json.dumps(snapshot.model_dump(mode="json"), indent=indent))
        resolution_path.write_text(json.dumps(data, indent=indent))
        loaded = ReadOnlyPhysicalAuthorityProvider.from_json(
            geometry_path,
            resolution_path,
            expected_source_sha256=SOURCE,
            expected_geometry_sha256=canonical_geometry_sha256(snapshot),
        )
        outputs.append(
            loaded.require_scope(
                "positive",
                purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING,
            )
        )
    assert outputs[0] == outputs[1]


def test_missing_floor_query_and_duplicate_scope_id_fail_explicitly() -> None:
    snapshot = geometry()
    data = resolution_payload(snapshot)
    result = provider(snapshot, data)
    with pytest.raises(KeyError, match="unknown floor"):
        result.get_scopes(floor_id="3F")
    data["scopes"].append(dict(data["scopes"][0]))
    with pytest.raises(ValidationError, match="unique"):
        provider(snapshot, data)
