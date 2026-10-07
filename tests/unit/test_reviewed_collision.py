"""Synthetic engineering gates; these fixtures do not grant school authority."""

import gzip
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_physical_collision import _numerics, _provider, _wall
from test_reviewed_authority import CONFIG, _context, _inference
from test_reviewed_authority import authority as authority

from amidst.domain.navigation import NavigationEdge
from amidst.domain.pipeline import InferenceInput, PipelineConfig
from amidst.finalization.reviewed_authority import (
    ReviewedAuthority,
    reviewed_physical_metrics,
    run_reviewed_baseline,
)
from amidst.finalization.reviewed_collision import (
    ReviewedCollisionBundle,
    collision_bundle_from_provider,
    evaluate_reviewed_known_collisions,
    load_reviewed_collision_bundle,
)
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_authority import (
    PhysicalAuthorityResolution,
    ReadOnlyPhysicalAuthorityProvider,
    canonical_geometry_sha256,
)
from amidst.scene_geometry import GeometryAuthorityError, SceneGeometrySnapshot


def _bound_provider(
    authority: ReviewedAuthority, *, empty: bool = False, review: bool = False,
    purpose: str = "KNOWN_COLLISION_PRUNING", semantic: str = "APPROVED",
) -> ReadOnlyPhysicalAuthorityProvider:
    wall = _wall(5.)
    wall["semantic_authority"] = semantic
    surfaces = [] if empty else [wall]
    if purpose != "KNOWN_COLLISION_PRUNING":
        support = dict(_wall())
        support.update(surface_id="synthetic-walkable", role="WALKABLE",
                       vertices=[[0., 0., 0.], [10., 0., 0.], [10., 10., 0.], [0., 10., 0.]],
                       blocks_movement=False, occludes_visibility=False)
        surfaces.append(support)
    original = _provider(surfaces, review=review)
    geometry_doc = original.geometry.model_dump(mode="json")
    geometry_doc["source_sha256"] = authority.source_sha256
    geometry = SceneGeometrySnapshot.model_validate_json(json.dumps(geometry_doc))
    digest = canonical_geometry_sha256(geometry)
    resolution_doc = original.resolution.model_dump(mode="json")
    resolution_doc.update(source_sha256=authority.source_sha256, geometry_sha256=digest,
                          policy=authority.provider.contract.policy.model_dump(mode="json"))
    resolution_doc["scopes"][0]["purpose"] = purpose
    if purpose != "KNOWN_COLLISION_PRUNING":
        resolution_doc["scopes"][0]["coverage"] = "COMPLETE"
    resolution = PhysicalAuthorityResolution.model_validate_json(json.dumps(resolution_doc))
    return ReadOnlyPhysicalAuthorityProvider(geometry, resolution, authority.source_sha256, digest)


def _bundle(authority: ReviewedAuthority, **changes: Any) -> ReviewedCollisionBundle:
    return collision_bundle_from_provider(
        _bound_provider(authority, **changes), authority.provider.contract, _numerics(),
        floor_ids=("1F",), manifest_sha256="a" * 64,
        local_certificate_content_sha256=authority.certificate_content_sha256,
        semantic_receipt_content_sha256=authority.semantic_review_content_sha256,
    )


def _run(
    authority: ReviewedAuthority, bundle: ReviewedCollisionBundle | None, *,
    ablation: str | None = None, method: str = "spatiotemporal",
    via: tuple[float, float, float] | None = None,
) -> Any:
    context = _context(authority)
    inputs, aggregation, readiness = _inference(authority, context)
    if via is not None:
        payload = inputs.model_dump()
        edge = payload["navigation"]["edges"][0]
        edge["polyline"] = (edge["polyline"][0], via, edge["polyline"][-1])
        inputs = InferenceInput.model_validate(payload)
        readiness["graph_content_sha256"] = content_sha256(PipelineConfig(
            navigation=inputs.navigation, topology=inputs.topology, movement=inputs.movement,
            search_policy=inputs.search_policy, reconstruction_policy=inputs.reconstruction_policy,
        ).model_dump(mode="json"))
    return run_reviewed_baseline(
        inputs, method, authority=authority, context=context, frozen_config_sha256=CONFIG,
        case_readiness_sha256=content_sha256(readiness), case_readiness=readiness,
        aggregation=aggregation, ablation_id=ablation, collision_bundle=bundle, clock=lambda: 0,
    )


def test_true_continuous_cylinder_collision_is_pruned(authority: ReviewedAuthority) -> None:
    bundle = _bundle(authority)
    decision = bundle.validate(((3., 5., 0.), (7., 5., 0.)))
    assert decision.state == "REJECTED"
    assert decision.tested_triangles > 0
    assert decision.complete_physical_validation is False
    run = _run(authority, bundle)
    assert run.collision_filter_enabled is True
    assert run.collision_filter_status == "AVAILABLE"
    assert not run.geometric_result.routes
    assert any(record.state == "REJECTED" for record in run.physical_records)
    assert run.collision_consumer_receipt == bundle.receipt()


def test_clear_alternative_survives_collision_before_top_k(authority: ReviewedAuthority) -> None:
    bundle = _bundle(authority)
    context = _context(authority)
    inputs, aggregation, readiness = _inference(authority, context)
    payload = inputs.model_dump()
    a, b = inputs.navigation.nodes[0].position, inputs.navigation.nodes[1].position
    detour = NavigationEdge(edge_id="detour", from_node_id="a", to_node_id="b",
                           polyline=(a, (3., 6., 0.), (7., 6., 0.), b))
    payload["navigation"]["edges"] = (*payload["navigation"]["edges"], detour.model_dump())
    transition = dict(payload["topology"]["transitions"][0])
    transition.update(transition_id="detour-handoff", navigation_edge_ids=("detour",))
    payload["topology"]["transitions"] = (*payload["topology"]["transitions"], transition)
    inputs = InferenceInput.model_validate(payload)
    readiness["graph_content_sha256"] = content_sha256(PipelineConfig(
        navigation=inputs.navigation, topology=inputs.topology, movement=inputs.movement,
        search_policy=inputs.search_policy, reconstruction_policy=inputs.reconstruction_policy,
    ).model_dump(mode="json"))
    run = run_reviewed_baseline(
        inputs, "spatiotemporal", authority=authority, context=context,
        frozen_config_sha256=CONFIG, case_readiness_sha256=content_sha256(readiness),
        case_readiness=readiness, aggregation=aggregation, collision_bundle=bundle, clock=lambda: 0,
    )
    assert len(run.geometric_result.routes) == 1
    assert run.geometric_result.routes[0].polyline == detour.polyline
    assert run.requested_k == 3


def test_ablation_keeps_domain_guard_and_both_independent_evaluators(
    authority: ReviewedAuthority,
) -> None:
    bundle = _bundle(authority)
    removed = _run(authority, bundle, ablation="remove_collision")
    assert removed.collision_filter_enabled is False
    assert removed.collision_filter_status == "AVAILABLE"
    assert len(removed.geometric_result.routes) == 1
    known = evaluate_reviewed_known_collisions(removed.event, bundle)
    assert known["known_collision_segment_count"] > 0
    assert known["known_collision_rate"] > 0
    assert known["tested_triangles"] > 0
    assert known["inference_ablation_affects_evaluator"] is False
    physical = reviewed_physical_metrics(removed.event, authority)
    assert physical["segment_count"] > 0
    assert physical["scope_id"] == authority.certificate.physical_certificate.scope_id
    outside = _run(authority, bundle, ablation="remove_collision", via=(5., 8.01, 0.))
    assert not outside.geometric_result.routes
    assert any("OUTSIDE_APPROVED_LOCAL" in reason for record in outside.physical_records
               for reason in record.reasons)


@pytest.mark.parametrize("method", ["shortest_path", "geometry", "spatiotemporal"])
def test_required_collision_mask_is_applied_to_abc(
    authority: ReviewedAuthority, method: str,
) -> None:
    run = _run(authority, _bundle(authority), method=method)
    assert run.collision_filter_enabled is True
    assert not run.geometric_result.routes


@pytest.mark.parametrize("field", [
    "local_certificate_content_sha256", "semantic_receipt_content_sha256",
])
def test_run_refuses_different_local_approval_receipts(
    authority: ReviewedAuthority, field: str,
) -> None:
    changes: dict[str, Any] = {field: "f" * 64}
    with pytest.raises(ValueError, match="receipt mismatch"):
        _run(authority, replace(_bundle(authority), **changes))


def test_source_mismatch_refused_even_when_scope_and_names_match(
    authority: ReviewedAuthority,
) -> None:
    other = _provider([_wall(5.)])
    with pytest.raises((ValueError, GeometryAuthorityError), match="[Ss]ource"):
        collision_bundle_from_provider(
            other, authority.provider.contract, _numerics(), floor_ids=("1F",),
            local_certificate_content_sha256=authority.certificate_content_sha256,
            semantic_receipt_content_sha256=authority.semantic_review_content_sha256,
            manifest_sha256="a" * 64,
        )


@pytest.mark.parametrize("change", [{"empty": True}, {"review": True},
                                    {"purpose": "COLLISION_FREE_VALIDATION"},
                                    {"semantic": "HUMAN_REVIEW"}])
def test_empty_review_or_wrong_purpose_cannot_enable_ablation(
    authority: ReviewedAuthority, change: dict[str, Any],
) -> None:
    with pytest.raises((ValueError, GeometryAuthorityError)):
        _bundle(authority, **change)


def test_explicit_scope_from_another_valid_purpose_is_rejected(
    authority: ReviewedAuthority,
) -> None:
    provider = _bound_provider(authority, purpose="COLLISION_FREE_VALIDATION")
    with pytest.raises(GeometryAuthorityError, match="PURPOSE"):
        collision_bundle_from_provider(
            provider, authority.provider.contract, _numerics(), floor_ids=("1F",),
            local_certificate_content_sha256=authority.certificate_content_sha256,
            semantic_receipt_content_sha256=authority.semantic_review_content_sha256,
            manifest_sha256="a" * 64, scope_ids=("synthetic-known-colliders",),
        )


def test_missing_authority_reports_na_without_collision_mask(authority: ReviewedAuthority) -> None:
    run = _run(authority, None)
    assert run.collision_filter_status == "N/A_NO_APPROVED_COLLIDER_AUTHORITY"
    assert run.collision_filter_enabled is False
    with pytest.raises(ValueError, match="supplied approved collision consumer"):
        _run(authority, None, ablation="remove_collision")


def test_operation_snapshot_is_detached_and_next_boundary_refuses_geometry_mutation(
    authority: ReviewedAuthority,
) -> None:
    bundle = _bundle(authority)
    prepared = bundle.prepare()
    path = ((3., 5., 0.), (7., 5., 0.))
    assert prepared.validate(path).state == "REJECTED"
    snapshot_receipt = prepared.receipt()
    snapshot_receipt["source_sha256"] = "f" * 64
    assert prepared.receipt()["source_sha256"] == authority.source_sha256
    changed = bundle.provider.geometry.model_dump(mode="json")
    for point in changed["surfaces"][0]["vertices"]:
        point[0] = 0.
    geometry = SceneGeometrySnapshot.model_validate_json(json.dumps(changed))
    # Simulate unsupported mutation after one operation took its snapshot. Its
    # detached source triangles remain unchanged; every subsequent boundary fails.
    object.__setattr__(bundle.provider, "geometry", geometry)
    assert prepared.validate(path).state == "REJECTED"
    with pytest.raises(ValueError, match="geometry SHA-256"):
        bundle.prepare()
    with pytest.raises(ValueError, match="geometry SHA-256"):
        bundle.receipt()


def test_next_run_rechecks_mutated_resolution_even_after_prior_ablation(
    authority: ReviewedAuthority,
) -> None:
    bundle = _bundle(authority)
    first = _run(authority, bundle, ablation="remove_collision")
    assert len(first.geometric_result.routes) == 1
    changed = bundle.provider.resolution.model_dump(mode="json")
    changed["scopes"][0]["approval_id"] = "OTHER_SYNTHETIC_APPROVAL"
    resolution = PhysicalAuthorityResolution.model_validate_json(json.dumps(changed))
    object.__setattr__(bundle.provider, "resolution", resolution)
    with pytest.raises(ValueError, match="resolution content hash"):
        _run(authority, bundle, ablation="remove_collision")
    with pytest.raises(ValueError, match="resolution content hash"):
        evaluate_reviewed_known_collisions(first.event, bundle)


def _loader_inputs(tmp_path: Path, authority: ReviewedAuthority) -> tuple[Path, str]:
    provider = _bound_provider(authority)
    paths = {"geometry.json.gz": provider.geometry.model_dump(mode="json"),
             "physical_authority.json": provider.resolution.model_dump(mode="json")}
    for name, value in paths.items():
        raw = json.dumps(value).encode()
        (tmp_path / name).write_bytes(gzip.compress(raw) if name.endswith(".gz") else raw)
    (tmp_path / "configs").mkdir()
    numerics = _numerics().model_dump(mode="json")
    (tmp_path / "configs/physical_collision_numerics_v1.json").write_text(json.dumps(numerics))
    source = {"sha256": authority.source_sha256}
    manifest = {
        "schema_version": "physical-policy-review-manifest-v1",
        "source_preserved": True, "source_before": source, "source_after": source,
        "summary": {"gt_used": False},
        "geometry_model_sha256": canonical_geometry_sha256(provider.geometry),
        "artifact_content_sha256": {name: content_sha256(value) for name, value in paths.items()},
        "input_content_sha256": {"collision_numerics_config": content_sha256(numerics)},
    }
    raw = json.dumps(manifest).encode()
    (tmp_path / "manifest.json").write_bytes(raw)
    context = {"schema_version": "school-physical-context-v1",
               "source_sha256": authority.source_sha256,
               "geometry": "geometry.json.gz", "physical_authority": "physical_authority.json",
               "physical_authority_manifest": "manifest.json"}
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context))
    return context_path, hashlib.sha256(raw).hexdigest()


def test_loader_verifies_exact_source_manifest_and_artifacts(
    tmp_path: Path, authority: ReviewedAuthority,
) -> None:
    context, manifest = _loader_inputs(tmp_path, authority)
    arguments: dict[str, Any] = dict(
        repo_root=tmp_path, expected_manifest_sha256=manifest,
        expected_source_sha256=authority.source_sha256, contract=authority.provider.contract,
        floor_ids=("1F",), local_certificate_content_sha256=authority.certificate_content_sha256,
        semantic_receipt_content_sha256=authority.semantic_review_content_sha256,
        scope_ids=("synthetic-known-colliders",),
    )
    bundle = load_reviewed_collision_bundle(context, **arguments)
    assert bundle.receipt()["nonempty_approved_collider_count"] == 1
    (tmp_path / "physical_authority.json").write_text("{}")
    with pytest.raises(ValueError, match="artifact content hash"):
        load_reviewed_collision_bundle(context, **arguments)


@pytest.mark.parametrize("relative", ["../escape.json", "ground_truth/authority.json"])
def test_loader_never_follows_gt_or_escaping_paths(
    tmp_path: Path, authority: ReviewedAuthority, relative: str,
) -> None:
    context, manifest = _loader_inputs(tmp_path, authority)
    value = json.loads(context.read_bytes())
    value["physical_authority"] = relative
    context.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="public source-bound"):
        load_reviewed_collision_bundle(
            context, repo_root=tmp_path, expected_manifest_sha256=manifest,
            expected_source_sha256=authority.source_sha256, contract=authority.provider.contract,
            floor_ids=("1F",),
            local_certificate_content_sha256=authority.certificate_content_sha256,
            semantic_receipt_content_sha256=authority.semantic_review_content_sha256,
        )
