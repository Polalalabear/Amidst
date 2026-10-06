"""Bound school-v3 evidence; these checks do not execute formal Cases 1–3.

Committed summaries always run. Marked integration checks require explicit local
materialization; tests never generate or download evidence. Use
``uv run pytest --require-physical-evidence`` to make a missing prerequisite fail.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_authority import (
    PhysicalAuthorityResolution,
    PhysicalPurpose,
    ReadOnlyPhysicalAuthorityProvider,
)
from amidst.physical_policy_validation import read_document, source_fingerprint
from amidst.scene_geometry import GeometryAuthorityError, SceneGeometrySnapshot

CONTEXT = Path("configs/physical_context_school_v3.json")
GENERATED_EVIDENCE = (
    "source_evidence.json.gz",
    "obstacle_collider_details.json.gz",
    "geometry.json.gz",
    "floor_support_details.json.gz",
)
SOURCE = Path(os.environ.get("AMIDST_PHYSICAL_SOURCE_SCENE", "blender/school_v3.blend"))


@pytest.fixture(scope="module")
def bundle() -> tuple[Path, dict[str, Any], dict[str, Any]]:
    context = read_document(CONTEXT)
    manifest_path = Path(context["physical_authority_manifest"])
    return manifest_path.parent, read_document(manifest_path), context


@pytest.fixture(scope="module")
def external_physical_evidence(
    bundle: tuple[Path, dict[str, Any], dict[str, Any]], request: pytest.FixtureRequest,
) -> None:
    directory, _, _ = bundle
    paths = (SOURCE, *(directory / name for name in GENERATED_EVIDENCE))
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        message = (
            "External physical evidence prerequisite is missing: " + ", ".join(missing)
            + ". Explicitly provision the hash-bound local school-v3 source "
            "(or set AMIDST_PHYSICAL_SOURCE_SCENE to its path), then run "
            "`uv run python -m amidst.materialize_physical_evidence` as documented. "
            "These tests do not generate or download evidence."
        )
        if request.config.getoption("--require-physical-evidence"):
            pytest.fail(message, pytrace=False)
        pytest.skip(message)


def test_bound_producer_inputs_and_preserved_source_record(
    bundle: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    directory, manifest, context = bundle
    assert manifest["source_before"] == manifest["source_after"]
    assert manifest["source_preserved"] is True
    assert manifest["source_before"]["sha256"] == context["source_sha256"]
    assert context["scale_authority"] == "APPROVED"
    policy = read_document(Path(context["physical_policy_config"]))
    assert policy["authority"] == "APPROVED"
    resolution = read_document(directory / "physical_authority.json")
    assert resolution["policy"]["authority"] == "APPROVED"
    assert resolution["level"] == "PARTIAL_APPROVED"
    config = read_document(Path(context["physical_policy_validation"]))
    assert content_sha256(config) == manifest["config_content_sha256"]
    for name, digest in manifest["producer_code_sha256"].items():
        assert hashlib.sha256(Path(f"src/amidst/{name}.py").read_bytes()).hexdigest() == digest


@pytest.mark.external_physical_evidence
def test_bound_source_scene_matches_content_and_size(
    bundle: tuple[Path, dict[str, Any], dict[str, Any]], external_physical_evidence: None,
) -> None:
    _, manifest, _ = bundle
    source = source_fingerprint(SOURCE)
    for key in ("sha256", "size"):
        assert source[key] == manifest["source_before"][key] == manifest["source_after"][key]
    # An independently provisioned copy can have a different filesystem mtime.
    # The historical record and the producer's own before/after check stay intact.


def test_committed_reports_match_registered_content(
    bundle: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    directory, manifest, _ = bundle
    for name, digest in manifest["artifact_content_sha256"].items():
        if name not in GENERATED_EVIDENCE:
            assert content_sha256(read_document(directory / name)) == digest, name


@pytest.mark.external_physical_evidence
def test_materialized_reports_match_registered_content(
    bundle: tuple[Path, dict[str, Any], dict[str, Any]], external_physical_evidence: None,
) -> None:
    directory, manifest, _ = bundle
    for name in GENERATED_EVIDENCE:
        document = read_document(directory / name)
        digest = (
            manifest["input_content_sha256"]["source_evidence"]
            if name == "source_evidence.json.gz" else manifest["artifact_content_sha256"][name]
        )
        assert content_sha256(document) == digest, name


def test_floor_support_uses_source_heights_and_retains_uncovered_regions(
    bundle: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    directory, _, _ = bundle
    report = read_document(directory / "floor_authority_map.json")
    assert report["approved_supported_subdomain_count"] == 48
    assert report["whole_annotation_supported_count"] == 45
    assert report["review_uncovered_subdomain_count"] == 3
    assert report["old_offset_exception_count_resolved"] == 38
    floors = {row["floor_id"]: row for row in report["floor_authorities"]}
    assert floors["1F"]["point"][2] == pytest.approx(20.07884979248047)
    assert floors["2F"]["point"][2] == pytest.approx(161.81109619140625)
    assert all(row["authority"] == "APPROVED" for row in floors.values())
    assert report["source_geometry_modified"] is False


def test_component_approval_does_not_certify_whole_obstacles_or_portals(
    bundle: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    directory, _, _ = bundle
    report = read_document(directory / "obstacle_collider_authority.json")
    assert report["approved_component_count"] == 58
    assert report["obstacles_with_approved_components"] == 5
    assert report["obstacle_count"] == 19
    assert all(row["whole_obstacle_authority"] == "HUMAN_REVIEW" for row in report["obstacles"])
    assert report["free_space_certified"] is False
    portals = read_document(directory / "portal_clearance.json")
    assert portals["pair_count"] == portals["human_review_count"] == 8
    assert portals["approved_pair_count"] == 0
    assert all(row["actual_effective_clear_width_m"] is None for row in portals["pairs"])


def test_stair_policy_is_distinct_from_actual_traversability(
    bundle: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    directory, _, _ = bundle
    stairs = read_document(directory / "stair_authority.json")
    assert stairs["direction"] == "BIDIRECTIONAL"
    assert stairs["policy_authority"] == "APPROVED"
    assert stairs["physical_stair_approved_count"] == 0
    assert {row["stair_id"]: row["authority"] for row in stairs["stairs"]} == {
        "A": "HUMAN_REVIEW", "B": "HUMAN_REVIEW",
    }
    assert all(not row["support_chain_approved"] for row in stairs["stairs"])
    assert all(not row["opening_approved"] for row in stairs["stairs"])


def test_local_certificates_and_pruning_retain_explicit_limits(
    bundle: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    directory, manifest, _ = bundle
    local = read_document(directory / "local_physical_scopes.json")
    assert local["approved_scope_count"] <= 3
    assert local["global_building_authority_approved"] is False
    assert local["source_geometry_reclassified"] is False
    for row in local["approved_scopes"]:
        assert content_sha256(row) == manifest["local_certificate_content_sha256"][row["scope_id"]]
        assert row["outside_domain"] == "REFUSE_VALIDATION"
        assert row["formal_case1_3_started"] is False
    pruning = read_document(directory / "collision_pruning_results.json")
    assert pruning["before_count"] == 4
    assert pruning["after_pruning_count"] == pruning["output_count"] == 2
    assert [row["state"] for row in pruning["records"]] == [
        "REJECTED", "RETAINED", "REJECTED", "RETAINED",
    ]
    assert [row["candidate_id"] for row in pruning["output_candidates"]] == [
        "source-component-probe-1", "source-component-probe-3",
    ]
    assert pruning["gt_used"] is pruning["ranking_changed"] is False
    assert pruning["navigation_validity_certified"] is False
    assert pruning["repeat_semantics_identical"] is True


@pytest.mark.external_physical_evidence
def test_building_formal_purposes_remain_fail_closed(
    bundle: tuple[Path, dict[str, Any], dict[str, Any]], external_physical_evidence: None,
) -> None:
    _, manifest, context = bundle
    geometry = SceneGeometrySnapshot.model_validate_json(
        json.dumps(read_document(Path(context["geometry"])))
    )
    resolution = PhysicalAuthorityResolution.model_validate_json(
        Path(context["physical_authority"]).read_bytes()
    )
    provider = ReadOnlyPhysicalAuthorityProvider(
        geometry, resolution, context["source_sha256"], manifest["geometry_model_sha256"],
    )
    assert resolution.level.value == "PARTIAL_APPROVED"
    assert geometry.physical_complete is False
    for scope in resolution.scopes:
        if scope.purpose == PhysicalPurpose.KNOWN_COLLISION_PRUNING:
            assert provider.require_scope(scope.scope_id, purpose=scope.purpose).colliders
        else:
            with pytest.raises(GeometryAuthorityError):
                provider.require_scope(scope.scope_id, purpose=scope.purpose)
