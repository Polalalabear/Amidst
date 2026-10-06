"""Geometry authority and aperture safety regressions, independent of Blender."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.scene_geometry import (
    Authority,
    GeometryAuthorityError,
    GeometrySurface,
    ReadOnlySceneGeometryProvider,
    SceneGeometrySnapshot,
    clip_triangle_to_box,
    promoted_wall_portal_conflicts,
    triangle_distance,
)

SOURCE = "a" * 64


def surface(identity: str = "walkable", role: str = "WALKABLE") -> dict[str, Any]:
    return {
        "surface_id": identity, "source_object_id": "source", "role": role,
        "floor_ids": ["1F"], "vertices": [[0., 0., 0.], [4., 0., 0.], [0., 4., 0.]],
        "triangles": [[0, 1, 2]], "semantic_authority": "HIGH_CONFIDENCE",
        "physical_authority": "HUMAN_REVIEW", "support": "SURFACE",
        "evidence_ids": ["source-exact-triangles"],
    }


def portal_surface() -> dict[str, Any]:
    result = surface("aperture", "PORTAL")
    result["support"] = "ANNOTATION"
    result["vertices"] = [[1., 1., 0.], [2., 1., 0.], [2., 2., 2.], [1., 2., 2.]]
    result["triangles"] = [[0, 1, 2], [0, 2, 3]]
    return result


def payload() -> dict[str, Any]:
    return {
        "schema_version": "scene-geometry-v1", "source_sha256": SOURCE,
        "scene_id": "tiny-scene", "unit_scale_m": 1., "floors": [{
            "floor_id": "1F", "point": [0., 0., 0.], "normal": [0., 0., 1.],
            "authority": "HUMAN_REVIEW",
        }], "surfaces": [surface()],
    }


def snapshot(data: dict[str, Any]) -> SceneGeometrySnapshot:
    return SceneGeometrySnapshot.model_validate_json(json.dumps(data))


def with_portal() -> dict[str, Any]:
    data = payload()
    data["surfaces"].append(portal_surface())
    data["portals"] = [{
        "portal_id": "door", "floor_id": "1F", "surface_id": "aperture",
        "adjacent_walkable_ids": ["walkable"], "authority": "HUMAN_REVIEW",
    }]
    return data


def wall(vertices: list[list[float]]) -> dict[str, Any]:
    result = surface("wall", "WALL")
    result["vertices"] = vertices
    result["blocks_movement"] = True
    return result


def test_source_binding_requires_independent_expected_hash(tmp_path: Path) -> None:
    path = tmp_path / "geometry.json"
    path.write_text(json.dumps(payload()))
    provider = ReadOnlySceneGeometryProvider.from_json(path, expected_source_sha256=SOURCE)
    assert provider.snapshot.source_sha256 == SOURCE
    with pytest.raises(ValueError, match="caller expectation"):
        ReadOnlySceneGeometryProvider.from_json(path, expected_source_sha256="b" * 64)
    with pytest.raises(TypeError, match="expected_source_sha256"):
        ReadOnlySceneGeometryProvider.from_json(path)  # type: ignore[call-arg]


@pytest.mark.parametrize("field", ["ground_truth", "ground_truth_path", "provenance", "bpy"])
def test_evaluation_and_platform_fields_cannot_enter_geometry(field: str) -> None:
    data = payload()
    data[field] = "forged"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        snapshot(data)


def test_nested_unknown_and_false_protection_claim_fail_closed() -> None:
    data = payload()
    data["surfaces"][0]["portal_protection_passed"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        snapshot(data)


@pytest.mark.parametrize("coordinate", [float("nan"), float("inf"), -float("inf"), True])
def test_nonfinite_and_boolean_geometry_rejected(coordinate: float | bool) -> None:
    data = payload()
    data["surfaces"][0]["vertices"][0][0] = coordinate
    with pytest.raises(ValidationError):
        snapshot(data)


@pytest.mark.parametrize("triangle", [[0, 1, 5], [0, 1, -1], [0, 0, 1], [0, 1, True]])
def test_invalid_triangle_indices_rejected(triangle: list[int | bool]) -> None:
    data = payload()
    data["surfaces"][0]["triangles"] = [triangle]
    with pytest.raises(ValidationError):
        snapshot(data)


def test_degenerate_triangle_rejected() -> None:
    data = payload()
    data["surfaces"][0]["vertices"] = [[0., 0., 0.], [1., 0., 0.], [2., 0., 0.]]
    with pytest.raises(ValidationError, match="degenerate"):
        snapshot(data)


def test_role_approved_footprint_stays_review_and_is_not_a_collider() -> None:
    data = payload()
    obstacle = surface("obstacle", "OBSTACLE")
    obstacle.update({"semantic_authority": "APPROVED", "support": "FOOTPRINT",
                     "approval_id": "human-obstacle-policy", "blocks_movement": True,
                     "occludes_visibility": True})
    data["surfaces"].append(obstacle)
    provider = ReadOnlySceneGeometryProvider(snapshot(data), SOURCE)
    assert provider.get_obstacles()[0].semantic_authority == Authority.APPROVED
    assert provider.get_obstacles()[0].physical_authority == Authority.HUMAN_REVIEW
    assert provider.get_colliders("1F") == ()
    with pytest.raises(GeometryAuthorityError) as refusal:
        provider.require_approved_physics("1F")
    assert "COLLIDER_NOT_APPROVED:obstacle" in refusal.value.reasons
    obstacle["physical_authority"] = "HIGH_CONFIDENCE"
    with pytest.raises(ValidationError, match="footprint/annotation"):
        snapshot(data)


def test_human_approval_requires_explicit_identity() -> None:
    data = payload()
    data["surfaces"][0]["semantic_authority"] = "APPROVED"
    with pytest.raises(ValidationError, match="approval_id"):
        snapshot(data)


def test_proposed_floor_and_scale_cannot_approve_physical_surface() -> None:
    data = payload()
    data["surfaces"][0].update({"physical_authority": "APPROVED", "approval_id": "human"})
    with pytest.raises(ValidationError, match="floor and scale"):
        snapshot(data)
    data["floors"][0].update({"authority": "APPROVED", "approval_id": "human-floor",
                              "evidence_ids": ["approved-floor-plane"]})
    with pytest.raises(ValidationError, match="floor and scale"):
        snapshot(data)
    data.update({"scale_authority": "APPROVED", "scale_approval_id": "human-scale"})
    assert snapshot(data).surfaces[0].physical_authority == Authority.APPROVED


def test_physical_complete_false_until_all_authorities_resolved() -> None:
    data = payload()
    data["physical_complete"] = True
    with pytest.raises(ValidationError, match="physical_complete"):
        snapshot(data)


def test_inspection_empty_colliders_never_certifies_provisional_space_clear() -> None:
    data = payload()
    candidate = wall([[0., 0., 0.], [0., 0., 2.], [0., 2., 0.]])
    candidate["physical_authority"] = "HIGH_CONFIDENCE"
    data["surfaces"].append(candidate)
    provider = ReadOnlySceneGeometryProvider(snapshot(data), SOURCE)
    assert provider.get_colliders("1F") == ()
    assert len(provider.get_colliders("1F", authority=Authority.HIGH_CONFIDENCE)) == 1
    with pytest.raises(GeometryAuthorityError) as refusal:
        provider.require_approved_physics("1F")
    assert refusal.value.reasons == (
        "PHYSICAL_AUTHORITY_INCOMPLETE", "FLOOR_NOT_APPROVED:1F", "SCALE_NOT_APPROVED",
        "WALKABLE_SCOPE_NOT_APPROVED:1F", "WALKABLE_NOT_APPROVED:walkable",
        "COLLIDER_NOT_APPROVED:wall",
    )


def test_physics_guard_returns_typed_missing_floor_refusal() -> None:
    provider = ReadOnlySceneGeometryProvider(snapshot(payload()), SOURCE)
    with pytest.raises(GeometryAuthorityError) as refusal:
        provider.require_approved_physics("unknown")
    assert "FLOOR_AUTHORITY_MISSING:unknown" in refusal.value.reasons


def approved_closed_scope() -> dict[str, Any]:
    data = payload()
    data.update({"scale_authority": "APPROVED", "scale_approval_id": "human-scale",
                 "physical_complete": True})
    data["floors"][0].update({"authority": "APPROVED", "approval_id": "human-floor",
                              "evidence_ids": ["approved-plane"]})
    data["surfaces"][0].update({"semantic_authority": "APPROVED",
                               "physical_authority": "APPROVED", "approval_id": "human-floor"})
    obstacle = surface("closed-obstacle", "OBSTACLE")
    obstacle.update({
        "vertices": [[1., 1., 0.], [2., 1., 0.], [1., 2., 0.], [1., 1., 1.]],
        "triangles": [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]],
        "support": "VOLUME", "semantic_authority": "APPROVED",
        "physical_authority": "APPROVED", "approval_id": "human-closed-volume",
        "blocks_movement": True, "occludes_visibility": True,
    })
    data["surfaces"].append(obstacle)
    return data


def test_physics_guard_accepts_explicitly_approved_complete_closed_scope() -> None:
    provider = ReadOnlySceneGeometryProvider(snapshot(approved_closed_scope()), SOURCE)
    colliders = provider.require_approved_physics("1F")
    assert tuple(surface.surface_id for surface in colliders) == ("closed-obstacle",)
    assert colliders[0].triangles == ((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3))


def test_approved_subset_cannot_bypass_global_physical_incompleteness() -> None:
    data = approved_closed_scope()
    data["physical_complete"] = False
    provider = ReadOnlySceneGeometryProvider(snapshot(data), SOURCE)
    assert len(provider.get_colliders("1F")) == 1
    with pytest.raises(GeometryAuthorityError) as refusal:
        provider.require_approved_physics("1F")
    assert refusal.value.reasons == ("PHYSICAL_AUTHORITY_INCOMPLETE",)


def test_empty_approved_floor_cannot_vacuously_claim_complete_physics() -> None:
    data = approved_closed_scope()
    data["surfaces"] = []
    with pytest.raises(ValidationError, match="physical_complete"):
        snapshot(data)
    data["physical_complete"] = False
    provider = ReadOnlySceneGeometryProvider(snapshot(data), SOURCE)
    assert provider.get_colliders("1F") == ()
    with pytest.raises(GeometryAuthorityError) as refusal:
        provider.require_approved_physics("1F")
    assert refusal.value.reasons == (
        "PHYSICAL_AUTHORITY_INCOMPLETE", "WALKABLE_AUTHORITY_MISSING:1F",
    )


def test_complete_snapshot_requires_walkable_support_on_every_floor() -> None:
    data = approved_closed_scope()
    data["floors"].append({"floor_id": "2F", "point": [0., 0., 10.],
                          "normal": [0., 0., 1.], "authority": "APPROVED",
                          "approval_id": "human-upper-floor", "evidence_ids": ["approved-plane"]})
    with pytest.raises(ValidationError, match="physical_complete"):
        snapshot(data)


def test_exact_hole_triangles_preserved_without_envelope(tmp_path: Path) -> None:
    data = payload()
    data["surfaces"][0]["vertices"] = [
        [0., 0., 0.], [1., 0., 0.], [0., 1., 0.],
        [3., 0., 0.], [4., 0., 0.], [4., 1., 0.],
    ]
    data["surfaces"][0]["triangles"] = [[0, 1, 2], [3, 4, 5]]
    path = tmp_path / "geometry.json"
    path.write_text(json.dumps(data))
    triangles = ReadOnlySceneGeometryProvider.from_json(
        path, expected_source_sha256=SOURCE,
    ).get_walkable()[0].triangles
    assert triangles == ((0, 1, 2), (3, 4, 5))


@pytest.mark.parametrize("vertices", [
    [[1.2, 1.2, .5], [1.8, 1.2, .5], [1.2, 1.8, .5]],  # Entirely inside aperture.
    [[0., 0., 1.], [4., 0., 1.], [0., 4., 1.]],  # Large transverse triangle.
    [[2., 1., .5], [3., 1., .5], [2., 2., .5]],  # Boundary contact.
])
def test_promoted_wall_cannot_seal_any_part_of_protected_portal(
    vertices: list[list[float]],
) -> None:
    data = with_portal()
    data["surfaces"].append(wall(vertices))
    with pytest.raises(ValidationError, match="violates protected portals"):
        snapshot(data)


def test_portal_padding_boundary_and_unit_conversion() -> None:
    data = with_portal()
    data["unit_scale_m"] = 2.
    data["portal_protection_tolerance_m"] = .5
    candidate = wall([[2.25, 1., .5], [3., 1., .5], [2.25, 2., .5]])
    data["surfaces"].append(candidate)
    with pytest.raises(ValidationError, match="protected portals"):
        snapshot(data)
    candidate["vertices"] = [[2.25001, 1., .5], [3., 1., .5], [2.25001, 2., .5]]
    assert len(snapshot(data).surfaces) == 3


def test_review_wall_is_retained_without_silent_promotion() -> None:
    data = with_portal()
    candidate = wall([[1.2, 1.2, .5], [1.8, 1.2, .5], [1.2, 1.8, .5]])
    candidate["semantic_authority"] = "HUMAN_REVIEW"
    data["surfaces"].append(candidate)
    provider = ReadOnlySceneGeometryProvider(snapshot(data), SOURCE)
    assert provider.get_walls()[0].semantic_authority == Authority.HUMAN_REVIEW
    assert provider.get_colliders("1F", authority=Authority.HIGH_CONFIDENCE) == ()


def test_portal_guard_is_floor_aware_and_unknown_floor_cannot_bypass() -> None:
    data = with_portal()
    data["floors"].append({"floor_id": "2F", "point": [0., 0., 10.],
                          "normal": [0., 0., 1.], "authority": "HUMAN_REVIEW"})
    candidate = wall([[1.2, 1.2, .5], [1.8, 1.2, .5], [1.2, 1.8, .5]])
    candidate["floor_ids"] = ["2F"]
    data["surfaces"].append(candidate)
    with pytest.raises(ValidationError, match="protected portals"):
        snapshot(data)  # Wrong floor label cannot excuse actual doorway contact.
    candidate["vertices"] = [[1.2, 1.2, 10.5], [1.8, 1.2, 10.5], [1.2, 1.8, 10.5]]
    assert len(snapshot(data).surfaces) == 3
    candidate["floor_ids"] = ["unknown"]
    with pytest.raises(ValidationError, match="unknown floor"):
        snapshot(data)
    candidate["floor_ids"] = []
    with pytest.raises(ValidationError, match="promoted wall requires floor"):
        snapshot(data)


def test_portal_protection_preserves_opening_in_actual_wall_triangles() -> None:
    data = with_portal()
    candidate = wall([[0., 0., 1.], [0., 4., 1.], [.5, 0., 1.],
                      [3., 0., 1.], [4., 0., 1.], [4., 4., 1.]])
    candidate["triangles"] = [[0, 1, 2], [3, 4, 5]]
    data["surfaces"].append(candidate)
    assert len(snapshot(data).surfaces) == 3  # Collider AABB would seal this opening.


def test_provider_is_immutable_and_queries_have_stable_order() -> None:
    data = payload()
    data["surfaces"] = [surface("z"), surface("a")]
    provider = ReadOnlySceneGeometryProvider(snapshot(data), SOURCE)
    assert tuple(item.surface_id for item in provider.get_walkable()) == ("a", "z")
    with pytest.raises(FrozenInstanceError):
        provider.snapshot = snapshot(payload())  # type: ignore[misc]
    with pytest.raises(ValidationError, match="frozen"):
        provider.get_walkable()[0].surface_id = "forged"
    with pytest.raises(KeyError, match="unknown floor"):
        provider.get_obstacles("nonexistent")


def test_model_construct_does_not_bypass_provider_validation() -> None:
    valid = snapshot(payload())
    forged = SceneGeometrySnapshot.model_construct(**{
        **valid.model_dump(), "source_sha256": "not-a-digest",
    })
    with pytest.raises(ValidationError):
        ReadOnlySceneGeometryProvider(forged, "not-a-digest")


def test_nested_model_copy_does_not_bypass_geometry_guards() -> None:
    valid = snapshot(payload())
    forged_surface = valid.surfaces[0].model_copy(update={"triangles": ((0, 0, 0),)})
    forged_snapshot = valid.model_copy(update={"surfaces": (forged_surface,)})
    with pytest.raises(ValidationError, match="distinct vertices"):
        ReadOnlySceneGeometryProvider(forged_snapshot, SOURCE)


def test_accepted_authority_without_evidence_rejected() -> None:
    data = payload()
    data["surfaces"][0]["evidence_ids"] = []
    with pytest.raises(ValidationError, match="traceable evidence"):
        snapshot(data)


@pytest.mark.parametrize("kind", ["surface", "floor", "portal"])
def test_duplicate_identities_fail(kind: str) -> None:
    data = with_portal()
    key = {"surface": "surfaces", "floor": "floors", "portal": "portals"}[kind]
    data[key].append(data[key][0].copy())
    with pytest.raises(ValidationError, match="duplicate"):
        snapshot(data)


def test_volume_support_rejects_planar_or_open_claim() -> None:
    data = payload()
    data["surfaces"][0]["support"] = "VOLUME"
    with pytest.raises(ValidationError, match="closed two-manifold"):
        snapshot(data)
    data["surfaces"][0]["triangles"] = [[0, 1, 2], [2, 1, 0]]
    with pytest.raises(ValidationError, match="zero enclosed"):
        snapshot(data)


def test_annotation_points_do_not_certify_collider() -> None:
    data = payload()
    data["surfaces"][0].update({"support": "ANNOTATION", "vertices": [[0., 0., 0.]],
                               "triangles": []})
    assert snapshot(data).surfaces[0].triangles == ()
    data["surfaces"][0]["physical_authority"] = "HIGH_CONFIDENCE"
    with pytest.raises(ValidationError, match="annotation"):
        snapshot(data)


def test_stair_roles_preserve_review_for_disconnected_path() -> None:
    data = payload()
    data["floors"].append({"floor_id": "2F", "point": [0., 0., 10.],
                          "normal": [0., 0., 1.], "authority": "HUMAN_REVIEW"})
    data["surfaces"].append(surface("stairpath", "STAIR"))
    data["stairs"] = [{
        "stair_id": "A", "floor_from": "1F", "floor_to": "2F",
        "entry_point": [0., 0., 0.], "exit_point": [0., 0., 10.],
        "path_surface_ids": ["stairpath"], "connectivity_authority": "HUMAN_REVIEW",
        "opening_authority": "HUMAN_REVIEW", "clearance_authority": "HUMAN_REVIEW",
    }]
    provider = ReadOnlySceneGeometryProvider(snapshot(data), SOURCE)
    assert provider.get_stairs()[0].connectivity_authority == Authority.HUMAN_REVIEW
    data["stairs"][0]["path_surface_ids"] = ["walkable"]
    with pytest.raises(ValidationError, match="actual STAIR"):
        snapshot(data)


def test_triangle_distance_transverse_coplanar_and_disjoint() -> None:
    first = ((0., 0., 0.), (4., 0., 0.), (0., 4., 0.))
    transverse = ((1., 1., -2.), (1., 1., 2.), (2., 1., 2.))
    inside = ((1., 1., 0.), (2., 1., 0.), (1., 2., 0.))
    above = ((0., 0., 3.), (4., 0., 3.), (0., 4., 3.))
    assert triangle_distance(first, transverse) == 0
    assert triangle_distance(first, inside) == 0
    assert triangle_distance(first, above) == pytest.approx(3.)


def test_clipping_catches_contained_surface_and_line_contact() -> None:
    contained = ((.2, .2, .5), (.8, .2, .5), (.2, .8, .5))
    assert clip_triangle_to_box(contained, (0., 0., 0.), (1., 1., 1.)) == contained
    boundary = ((1., 0., .5), (2., 0., .5), (1., 1., .5))
    assert clip_triangle_to_box(boundary, (0., 0., 0.), (1., 1., 1.))


def test_unknown_floor_direct_guard_remains_conservative() -> None:
    candidate = wall([[1.2, 1.2, .5], [1.8, 1.2, .5], [1.2, 1.8, .5]])
    candidate["floor_ids"] = []
    geometry = GeometrySurface.model_validate_json(json.dumps(candidate))
    aperture = GeometrySurface.model_validate_json(json.dumps(portal_surface()))
    assert promoted_wall_portal_conflicts(
        geometry, (aperture,), tolerance_m=0., unit_scale_m=1.,
    ) == ("aperture",)
