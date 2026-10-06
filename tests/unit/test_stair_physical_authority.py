"""Source stair diagnostics must not turn an annotation or point probe into authority."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.architectural_scale import ArchitecturalScale
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_authority import PhysicalPolicy
from amidst.physical_policy_contract import PhysicalPolicyContract, PhysicalPolicyRuntime
from amidst.stair_physical_authority import review_stair_physical_authority

SOURCE = "0" * 64
SETTINGS = {"horizontal_normal_abs_z_min": 0.984807753012208,
            "horizontal_layer_tolerance_units": 0.25}


def fixture() -> tuple[dict[str, Any], dict[str, Any], PhysicalPolicyContract]:
    runtime = json.loads(Path("configs/physical_policy_runtime_school_v3.json").read_text())
    runtime.update(source_asset_sha256=SOURCE, approval_id="synthetic-runtime-approval")
    scale = ArchitecturalScale.model_validate_json(json.dumps({
        "source_asset_sha256": SOURCE, "metres_per_blender_unit": .0247,
        "authority": "APPROVED", "approval_id": "synthetic-scale",
        "evidence_ids": ["synthetic-scale"],
    }))
    policy = PhysicalPolicy.model_validate_json(
        Path("configs/physical_authority_policy_school_v3.json").read_bytes()
    )
    contract = PhysicalPolicyContract(policy, scale,
                                      PhysicalPolicyRuntime.model_validate_json(json.dumps(runtime)))
    audit = {"source_sha256": SOURCE, "objects": [{
        "object": "STAIR_A_PATH", "custom_properties": {
            "semantic_class": "STAIR", "stair_id": "A", "stair_role": "PATH",
            "floor_from": "1F", "floor_to": "2F", "direction": "UP",
            "geometry_authority": "ANNOTATION_PROXY_NOT_PHYSICAL_CERTIFICATION",
            "source_objects": ["opaque-annotation-helper"],
        },
    }]}
    mesh = {
        "source_object_id": "group_opaque", "vertices": [[0., 0., 12.], [40., 0., 12.],
                                                          [40., 40., 12.], [0., 40., 12.]],
        "triangles": [[0, 1, 2], [0, 2, 3]], "triangle_source_face_indices": [0, 0],
        "source_face_indices": [0], "evaluated_vertex_count": 4,
        "evaluated_triangle_count": 2, "evaluated_polygon_count": 1,
        "full_object_exported": True, "components": [{
            "component_id": "component-0", "source_triangle_indices": [0, 1],
            "source_vertex_indices": [0, 1, 2, 3], "triangle_count": 2,
            "full_component_exported": True,
        }], "hidden_render": False, "hidden_viewport": False, "viewport_disabled": False,
        "collection_disabled": False, "semantic_role": "UNCLASSIFIED_SOURCE_MESH_CONTEXT_ONLY",
    }
    _hash_mesh(mesh)
    approval = scale.model_dump(mode="json")
    evidence = {
        "schema_version": "physical-policy-source-evidence-v1", "source_sha256": SOURCE,
        "source_preserved": True, "saved": False, "rendered": False,
        "geometry_modified": False, "audit_content_sha256": content_sha256(audit),
        "architectural_scale": approval, "architectural_scale_content_sha256": content_sha256(
            approval
        ), "policy": {
            "gt_used": False, "roles_inferred_from_names": False, "bounds_are_colliders": False,
            "hidden_geometry_included": True, "missing_triangles_certify_clearance": False,
            "source_object_geometry_complete": True,
            "component_enclosure_candidates_included": True,
            "region_complete_means_exhaustive_selection_only": True,
        }, "meshes": [mesh], "regions": [{
            "region_id": "STAIR_A", "kind": "STAIR_CONTEXT", "selection_complete": True,
            "bounds_bu": {"minimum": [-10., -10., 0.], "maximum": [50., 50., 100.]},
            "selections": [{"mesh_id": mesh["mesh_id"],
                            "source_object_id": mesh["source_object_id"],
                            "source_triangle_indices": [0, 1], "component_ids": ["component-0"]}],
        }],
    }
    return evidence, audit, contract


def _hash_mesh(mesh: dict[str, Any]) -> None:
    mesh["mesh_id"] = content_sha256({key: mesh[key] for key in (
        "source_object_id", "vertices", "triangles", "triangle_source_face_indices",
    )})
    mesh["geometry_sha256"] = content_sha256({
        key: value for key, value in mesh.items() if key != "geometry_sha256"
    })


def run(evidence: dict[str, Any], audit: dict[str, Any], contract: PhysicalPolicyContract) -> dict:
    return review_stair_physical_authority(
        evidence, audit, contract, floor_points_bu={"1F": (0., 0., 0.), "2F": (0., 0., 100.)},
        settings=SETTINGS,
    )


def test_real_horizontal_surface_census_does_not_certify_staircase() -> None:
    evidence, audit, contract = fixture()
    before = copy.deepcopy(evidence)
    report = run(evidence, audit, contract)
    assert evidence == before
    row = report["stairs"][0]
    assert row["direction"] == "BIDIRECTIONAL"
    assert row["authority"] == "HUMAN_REVIEW"
    assert row["horizontal_support_layers"][0]["body_sized_disk_fits"] is True
    assert row["horizontal_support_layers"][0]["support_area_m2"] == pytest.approx(1600*.0247**2)
    assert row["horizontal_support_layers"][0]["point_headroom_m"] is None
    assert row["support_chain_approved"] is False
    assert row["opening_approved"] is False and row["body_clearance_approved"] is False
    assert "SOURCE_SUPPORT_CHAIN_NOT_PROVEN" in row["reason_codes"]
    assert report["physical_stair_approved_count"] == 0


def test_explicit_annotation_helper_is_excluded_without_name_guessing() -> None:
    evidence, audit, contract = fixture()
    audit["objects"][0]["custom_properties"]["source_objects"] = ["group_opaque"]
    evidence["audit_content_sha256"] = content_sha256(audit)
    row = run(evidence, audit, contract)["stairs"][0]
    assert row["source_triangles_inspected"] == 0
    assert row["horizontal_support_layers"] == []
    assert row["excluded_annotation_helper_ids"] == ["group_opaque"]
    assert row["authority"] == "HUMAN_REVIEW"


def test_degenerate_source_triangle_is_structured_review() -> None:
    evidence, audit, contract = fixture()
    mesh = evidence["meshes"][0]
    mesh["vertices"][2] = [20., 0., 12.]
    _hash_mesh(mesh)
    evidence["regions"][0]["selections"][0]["mesh_id"] = mesh["mesh_id"]
    row = run(evidence, audit, contract)["stairs"][0]
    assert len(row["invalid_source_faces"]) == 1
    assert row["invalid_source_faces"][0]["source_triangle_index"] == 0
    assert "INVALID_SOURCE_FACE_GEOMETRY_REPORTED" in row["reason_codes"]
    assert row["support_chain_approved"] is False


def test_incomplete_selection_and_missing_floor_do_not_approve() -> None:
    evidence, audit, contract = fixture()
    evidence["regions"][0]["selection_complete"] = False
    row = review_stair_physical_authority(evidence, audit, contract, settings=SETTINGS)["stairs"][0]
    assert "SOURCE_REGION_SELECTION_INCOMPLETE" in row["reason_codes"]
    assert "SOURCE_FLOOR_REFERENCES_UNAVAILABLE" in row["reason_codes"]
    assert row["authority"] == "HUMAN_REVIEW"


def test_known_low_headroom_cannot_turn_slab_underside_into_landing() -> None:
    evidence, audit, contract = fixture()
    mesh = evidence["meshes"][0]
    mesh["vertices"].extend([[0., 0., 13.], [40., 0., 13.], [40., 40., 13.], [0., 40., 13.]])
    mesh["triangles"].extend([[4, 5, 6], [4, 6, 7]])
    mesh["triangle_source_face_indices"] = [0, 0, 1, 1]
    mesh["source_face_indices"] = [0, 1]
    mesh.update(evaluated_vertex_count=8, evaluated_triangle_count=4, evaluated_polygon_count=2)
    mesh["components"] = [{
        "component_id": "component-0", "source_triangle_indices": [0, 1, 2, 3],
        "source_vertex_indices": list(range(8)), "triangle_count": 4,
        "full_component_exported": True,
    }]
    _hash_mesh(mesh)
    selected = evidence["regions"][0]["selections"][0]
    selected.update(mesh_id=mesh["mesh_id"], source_triangle_indices=[0, 1, 2, 3])
    row = run(evidence, audit, contract)["stairs"][0]
    underside = row["horizontal_support_layers"][0]
    assert underside["body_sized_disk_fits"] is True
    assert underside["point_headroom_m"] == pytest.approx(.0247)
    assert underside["point_headroom_policy_check"] == "FAIL_KNOWN_SOURCE_INTERSECTION"
    assert underside not in row["intermediate_landing_candidates"]
    assert row["body_clearance_approved"] is False


def test_source_or_audit_forgery_fail_fast() -> None:
    evidence, audit, contract = fixture()
    evidence["source_sha256"] = "a" * 64
    with pytest.raises(ValueError, match="source SHA"):
        run(evidence, audit, contract)
    evidence["source_sha256"] = SOURCE
    audit["objects"][0]["custom_properties"]["direction"] = "DOWN"
    with pytest.raises(ValueError, match="audit_content_sha256"):
        run(evidence, audit, contract)


def test_repeated_source_inspection_is_deterministic() -> None:
    evidence, audit, contract = fixture()
    assert run(evidence, audit, contract) == run(
        copy.deepcopy(evidence), copy.deepcopy(audit), contract,
    )
