"""Reproduce source-bound physical policy reviews without Blender or Ground Truth.

The source atlas is generated separately by the read-only Blender exporter. This
command verifies its independent content binding and retains native geometry.
It never invokes a benchmark, Graph, ranking, or an observation producer.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from amidst.domain.trajectory import CandidateTrajectory
from amidst.local_physical_scopes import discover_local_scopes
from amidst.obstacle_volume_authority import (
    approved_obstacle_surfaces,
    content_sha256,
    review_obstacle_volumes,
    review_portal_clearance,
    validate_source_evidence,
)
from amidst.physical_authority import (
    PhysicalAuthorityResolution,
    ReadOnlyPhysicalAuthorityProvider,
    canonical_geometry_sha256,
)
from amidst.physical_collision import (
    CollisionNumerics,
    CylinderCollisionConsumer,
    load_collision_numerics,
    prune_before_top_k,
)
from amidst.physical_policy_contract import PhysicalPolicyContract, load_physical_policy_contract
from amidst.scene_geometry import FloorAuthority, GeometrySurface, SceneGeometrySnapshot
from amidst.stair_physical_authority import review_stair_physical_authority
from amidst.walkable_clearance import (
    WalkableClearanceDomain,
    build_source_bound_floor_support,
)

PRODUCER_MODULES = (
    "physical_policy_validation", "physical_policy_contract", "physical_collision",
    "walkable_clearance", "local_physical_scopes", "obstacle_volume_authority",
    "stair_physical_authority", "physical_authority", "scene_geometry",
)


def _producer_digests() -> dict[str, str]:
    return {name: hashlib.sha256(Path(__file__).with_name(name + ".py").read_bytes()).hexdigest()
            for name in PRODUCER_MODULES}


def read_document(path: Path) -> dict[str, Any]:
    data = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_document(path: Path, value: Any) -> None:
    # Stable gzip header; reproducibility is assessed on JSON semantics/digests.
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode() + b"\n"
    path.write_bytes(gzip.compress(data, mtime=0) if path.suffix == ".gz" else data)


def source_fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return {"sha256": digest.hexdigest(), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _models(rows: list[dict[str, Any]], cls: Any) -> tuple[Any, ...]:
    return tuple(cls.model_validate_json(json.dumps(row, allow_nan=False)) for row in rows)


def _geometry(
    previous: dict[str, Any], support: dict[str, Any], obstacles: dict[str, Any],
) -> tuple[SceneGeometrySnapshot, PhysicalAuthorityResolution]:
    geometry = dict(previous)
    geometry["floors"] = support["floor_authorities"]
    geometry["surfaces"] = [*previous["surfaces"], *support["support_surfaces"],
                            *obstacles["approved_surfaces"]]
    geometry["physical_complete"] = False
    snapshot = SceneGeometrySnapshot.model_validate_json(json.dumps(geometry, allow_nan=False))
    digest = canonical_geometry_sha256(snapshot)
    colliders = approved_obstacle_surfaces(obstacles)
    scopes = []
    for identity in sorted({surface.source_object_id for surface in colliders}):
        selected = tuple(surface for surface in colliders if surface.source_object_id == identity)
        floors = sorted({f for surface in selected for f in surface.floor_ids})
        scopes.append({
            "scope_id": "school-v3:known-components:" + content_sha256(identity)[:16],
            "purpose": "KNOWN_COLLISION_PRUNING", "floor_ids": floors,
            "surface_ids": [surface.surface_id for surface in selected],
            "coverage": "PARTIAL", "authority": "APPROVED",
            "approval_id": "SOURCE_BOUND_COMPONENT_POLICY_APPROVAL_20261006",
            "evidence_ids": ["source:" + snapshot.source_sha256,
                             "obstacle-review:" + content_sha256(obstacles)],
        })
    for purpose in ("COLLISION_FREE_VALIDATION", "TOPOLOGY_VALIDATION",
                    "PHYSICAL_VALIDITY_METRICS"):
        scopes.append({
            "scope_id": "school-v3:building:" + purpose.lower(), "purpose": purpose,
            "floor_ids": [floor.floor_id for floor in snapshot.floors],
            "surface_ids": [], "coverage": "PARTIAL", "authority": "HUMAN_REVIEW",
            "unresolved_reasons": ["BUILDING_COLLIDER_COVERAGE_INCOMPLETE",
                                   "PORTAL_AND_STAIR_PHYSICAL_AUTHORITY_PENDING"],
        })
    resolution = PhysicalAuthorityResolution.model_validate_json(json.dumps({
        "source_sha256": snapshot.source_sha256, "geometry_sha256": digest,
        "level": "PARTIAL_APPROVED" if colliders else "PROVISIONAL",
        "policy": obstacles["policy"], "scopes": scopes,
        "evidence_ids": ["source-support:" + content_sha256(support)],
    }))
    ReadOnlyPhysicalAuthorityProvider(snapshot, resolution, snapshot.source_sha256, digest)
    return snapshot, resolution


def collision_pruning_prototype(
    snapshot: SceneGeometrySnapshot, resolution: PhysicalAuthorityResolution,
    contract: PhysicalPolicyContract, numerics: CollisionNumerics,
) -> dict[str, Any]:
    """Positive source-component probes, restricted to explicit PARTIAL scopes.

    This is a geometry-consumer experiment, not inference or a formal school
    candidate set. A retained probe certifies only absence of *known* collision.
    Navigation, camera binding, complete free space and benchmark approval are
    explicitly unavailable. Every rejected probe intersects an approved collider.
    """
    started = time.perf_counter()
    provider = ReadOnlyPhysicalAuthorityProvider(
        snapshot, resolution, snapshot.source_sha256, canonical_geometry_sha256(snapshot),
    )
    surface_map = {surface.surface_id: surface for surface in snapshot.surfaces}
    approved = [scope for scope in resolution.scopes if str(scope.authority) == "APPROVED"]
    if not approved:
        return {"status": "NOT_ENABLED", "reason": "NO_APPROVED_KNOWN_COLLIDER_SCOPE"}
    scope = min(approved, key=lambda row: (
        sum(len(surface_map[x].triangles) for x in row.surface_ids), row.scope_id,
    ))
    consumer = CylinderCollisionConsumer.from_provider(provider, scope.scope_id, contract, numerics)
    surface = min(consumer.inputs.colliders, key=lambda row: (len(row.triangles), row.surface_id))
    ratio = contract.scale.metres_per_blender_unit
    floor = next(f for f in consumer.inputs.floors if f.floor_id in surface.floor_ids)
    z_m = floor.point[2] * ratio
    vertices = np.asarray(surface.vertices) * ratio
    triangles = vertices[np.asarray(surface.triangles)]
    body_height = contract.parameter("body_height_m")
    centers = [t.mean(axis=0) for t in triangles if z_m <= t.mean(axis=0)[2] <= z_m + body_height]
    if not centers:
        raise ValueError("approved collider has no positive body-envelope triangle probe")
    center = centers[0]
    offset = contract.parameter("body_radius_m") / 2
    collision = ((float(center[0] - offset), float(center[1]), z_m),
                 (float(center[0] + offset), float(center[1]), z_m))
    # Probe points are deliberately outside every selected collider bounding box;
    # boxes select probes, and the actual cylinder/triangle consumer decides them.
    maximum = max(float(np.asarray(s.vertices)[:, 0].max()) * ratio
                  for s in consumer.inputs.colliders)
    clear = ((maximum + 1., float(center[1]), z_m),
             (maximum + 2., float(center[1]), z_m))
    polylines = (collision, clear, tuple(reversed(collision)), tuple(reversed(clear)))
    candidates = tuple(CandidateTrajectory(
        candidate_id=f"source-component-probe-{index}",
        start_observation_id="GEOMETRY_DIAGNOSTIC_NO_OBSERVATION",
        end_observation_id="GEOMETRY_DIAGNOSTIC_NO_OBSERVATION",
        polyline=points, path_length=float(np.linalg.norm(np.asarray(points[1])-points[0])),
        minimum_travel_time=0., estimated_travel_time=0., path_score=float(4-index),
    ) for index, points in enumerate(polylines))
    output, report = prune_before_top_k(candidates, consumer, top_k=2)
    if report["after_pruning_count"] != 2 or len(output) != 2:
        raise ValueError("source-component positive/negative collision probes did not validate")
    repeat, repeat_report = prune_before_top_k(candidates, consumer, top_k=2)
    if repeat != output or repeat_report != report:
        raise ValueError("collision filtering is not deterministic")
    return {
        **report, "status": "ENABLED_APPROVED_KNOWN_COMPONENTS_ONLY",
        "experiment": "COLLISION_PRUNING_PROTOTYPE_NOT_FORMAL_CASE",
        "candidate_coordinates": "METRES", "geometry_coordinates": "BLENDER_NATIVE_UNITS",
        "candidate_pool": [row.model_dump(mode="json") for row in candidates],
        "output_candidates": [row.model_dump(mode="json") for row in output],
        "candidate_native_polylines_bu": {
            row.candidate_id: [
                [contract.scale.to_blender_units(v) for v in p] for p in row.polyline
            ]
            for row in candidates
        },
        "approved_source_surface_id": surface.surface_id,
        "navigation_validity_certified": False, "complete_collision_free_certified": False,
        "formal_case1_3_started": False, "graph_core_modified": False,
        "ids_scores_relative_order_preserved": True, "repeat_semantics_identical": True,
        "runtime_seconds": time.perf_counter() - started,
    }


def validate_policy(config_path: Path, output: Path) -> dict[str, Any]:
    started = time.perf_counter()
    producer_digests = _producer_digests()
    config = read_document(config_path)
    if config.get("schema_version") != "physical-policy-validation-config-v1":
        raise ValueError("unsupported physical policy validation config")
    contract = load_physical_policy_contract(Path(config["runtime_config"]))
    source_path = Path(config["source_blend"])
    before = source_fingerprint(source_path)
    contract.scale.require_source_sha256(before["sha256"])
    paths = {name: Path(config[name]) for name in (
        "audit", "floor_survey", "source_evidence", "source_selection_config",
        "role_authorization", "previous_geometry", "collision_numerics_config",
        "stair_review_config",
        "historical_resolution",
    )}
    documents = {name: read_document(path) for name, path in paths.items()}
    evidence = documents["source_evidence"]
    if content_sha256(evidence) != config["source_evidence_content_sha256"]:
        raise ValueError("source atlas content differs from independently recorded binding")
    validate_source_evidence(
        evidence, expected_source_sha256=before["sha256"],
        expected_audit_content_sha256=content_sha256(documents["audit"]),
        expected_config_content_sha256=content_sha256(documents["source_selection_config"]),
    )
    if evidence["exporter_code_sha256"] != hashlib.sha256(
        Path(config["source_exporter"]).read_bytes()
    ).hexdigest():
        raise ValueError("source exporter code differs from source evidence producer")
    audit = documents["audit"]
    walkable_ids = tuple(sorted(row["object"] for row in audit["objects"] if
                               row.get("custom_properties", {}).get("semantic_class") == "WALKABLE"
                               and row["custom_properties"].get("semantic_review_id")))
    settings = config["floor_support"]
    support = build_source_bound_floor_support(
        audit, documents["floor_survey"], scale=contract.scale,
        approved_walkable_ids=walkable_ids,
        approval_id="SOURCE_BOUND_GEOMETRY_REVIEW_PHYSICAL_POLICY_2026_10_06",
        support_heights_bu=settings["support_heights_bu"],
        contact_tolerance_m=contract.parameter("collision_tolerance_m"),
        horizontal_normal_abs_z_min=settings["horizontal_normal_abs_z_min"],
        max_triangles_per_region=settings["maximum_triangles_per_region"],
        numeric_epsilon=settings["numeric_epsilon_bu"],
    )
    floors = _models(support["floor_authorities"], FloorAuthority)
    surfaces = _models(support["support_surfaces"], GeometrySurface)
    typed_floors = {floor.floor_id: floor for floor in floors}
    typed_surfaces = {surface.surface_id: surface for surface in surfaces}
    domains = {}
    for row in support["walkable_reviews"]:
        if row["support_surface_ids"]:
            domains[row["walkable_id"]] = WalkableClearanceDomain.from_surfaces(
                tuple(typed_surfaces[x] for x in row["support_surface_ids"]),
                floor=typed_floors[row["floor_id"]], scale=contract.scale,
                policy=contract.policy, expected_source_sha256=before["sha256"],
            )
    floor_domains = {floor.floor_id: WalkableClearanceDomain.from_surfaces(
        tuple(surface for surface in surfaces if floor.floor_id in surface.floor_ids),
        floor=floor, scale=contract.scale, policy=contract.policy,
        expected_source_sha256=before["sha256"],
    ) for floor in floors}
    obstacle_started = time.perf_counter()
    obstacles = review_obstacle_volumes(
        evidence, audit, documents["role_authorization"], scale=contract.scale,
        policy=contract.policy, floors=floors,
        maximum_self_intersection_pairs=config["maximum_self_intersection_pairs"],
    )
    obstacles["policy"] = contract.policy.model_dump(mode="json")
    runtimes = {"obstacle_review_seconds": time.perf_counter() - obstacle_started}
    portals = review_portal_clearance(
        evidence, audit, scale=contract.scale, policy=contract.policy,
    )
    stairs = review_stair_physical_authority(
        evidence, audit, contract, floor_points_bu={f.floor_id: f.point for f in floors},
        settings=documents["stair_review_config"]["floor_stair_review"],
    )
    scope_started = time.perf_counter()
    faces = {f: frozenset((surface.source_object_id, face) for surface in surfaces
                         if f in surface.floor_ids for face in surface.source_face_indices)
             for f in typed_floors}
    search = config["local_scope_search"]
    scopes = discover_local_scopes(
        domains, evidence, contract, load_collision_numerics(paths["collision_numerics_config"]),
        support_source_faces=faces, half_extent_m=tuple(search["half_extent_m"]),
        maximum_centers=search["maximum_centers"], maximum_approved=search["maximum_approved"],
        maximum_enclosure_pair_checks=search["maximum_enclosure_pair_checks"],
        self_intersection_numeric_epsilon_bu=search["self_intersection_numeric_epsilon_bu"],
    )
    runtimes["local_scope_search_seconds"] = time.perf_counter() - scope_started
    snapshot, resolution = _geometry(documents["previous_geometry"], support, obstacles)
    pruning = collision_pruning_prototype(
        snapshot, resolution, contract, load_collision_numerics(paths["collision_numerics_config"]),
    )
    floor_summary = {k: v for k, v in support.items() if k not in (
        "support_surfaces", "source_bindings", "walkable_reviews",
    )}
    floor_summary["walkable_reviews"] = [{k: v for k, v in row.items() if k not in (
        "other_height_source_evidence", "uncovered_polygons",
    )} for row in support["walkable_reviews"]]
    historical = documents["historical_resolution"]
    if historical["source_sha256"] != before["sha256"]:
        raise ValueError("historical diagnostic comparison belongs to a different source")
    now = {row["walkable_id"]: row for row in support["walkable_reviews"]}
    old_rows = historical["floors_stairs"]["floor_reviews"]
    floor_summary["old_offset_exception_count_resolved"] = sum(
        "PROPOSED_PLANE_DIFFERS_FROM_ACTUAL_MESH_SUPPORT" in row["reason_codes"]
        and now[row["object_id"]]["old_plane_offset_reason_resolved"] for row in old_rows
    )
    floor_summary["old_budget_limited_regions_with_source_support"] = sum(
        "GEOMETRY_BUDGET_EXCEEDED" in row["reason_codes"]
        and bool(now[row["object_id"]]["support_surface_ids"]) for row in old_rows
    )
    floor_summary["current_proxy_height_offsets_explained"] = sum(
        row["old_plane_offset_reason_resolved"] for row in support["walkable_reviews"]
    )
    obstacle_summary = {k: v for k, v in obstacles.items() if k not in (
        "obstacles", "approved_surfaces",
    )}
    obstacle_summary["obstacles"] = [{
        **{k: v for k, v in row.items() if k != "components"},
        "components": [{
            **{k: v for k, v in component.items() if k != "provenance"},
            "source_binding": {k: component["provenance"][k] for k in (
                "source_mesh_id", "source_geometry_sha256", "source_component_id",
            )},
        } for component in row["components"]],
    } for row in obstacles["obstacles"]]
    after = source_fingerprint(source_path)
    if before != after:
        raise ValueError("source integrity changed during physical policy validation")
    if producer_digests != _producer_digests():
        raise ValueError("producer code changed during validation; rerun before recording authority"
                         )
    pruning.update(
        diagnostic_positive_component_probe_only=True,
        temporal_validity_certified=False,
        formal_inference_pruning_enabled=False,
        complete_local_scope_collision_pruning_enabled=bool(scopes["approved_scope_count"]),
    )
    output = output.resolve()
    protected = {path.resolve() for path in paths.values()} | {
        source_path.resolve(), config_path.resolve(), Path(config["runtime_config"]).resolve(),
    }
    artifacts = {
        "body_clearance_policy.json": contract.report(),
        "floor_authority_map.json": floor_summary,
        "floor_support_details.json.gz": support,
        "obstacle_collider_authority.json": obstacle_summary,
        "obstacle_collider_details.json.gz": obstacles,
        "portal_clearance.json": portals, "stair_authority.json": stairs,
        "local_physical_scopes.json": scopes,
        "geometry.json.gz": snapshot.model_dump(mode="json"),
        "physical_authority.json": resolution.model_dump(mode="json"),
        "collision_pruning_results.json": pruning,
        **{f"walkable_clearance_{f}.json": domain.report()
           for f, domain in floor_domains.items()},
    }
    if any((output / name).resolve() in protected for name in (*artifacts, "manifest.json")):
        raise ValueError("report cannot overwrite source/config/evidence input")
    output.mkdir(parents=True, exist_ok=True)
    for name, document in artifacts.items():
        write_document(output / name, document)
    summary = {
        "overall_physical_authority": str(resolution.level),
        "approved_source_component_count": obstacles["approved_component_count"],
        "obstacles_with_approved_components": obstacles["obstacles_with_approved_components"],
        "whole_obstacle_volumes_approved": 0,
        "approved_restricted_local_islands": scopes["approved_scope_count"],
        "floor_supported_subdomains": support["approved_supported_subdomain_count"],
        "floor_uncovered_subdomains": support["review_uncovered_subdomain_count"],
        "wall_status_counts": dict(Counter(str(s.semantic_authority)
                                             for s in snapshot.surfaces if str(s.role) == "WALL")),
        "building_physical_complete": False, "formal_cases_started": False, "gt_used": False,
    }
    manifest = {
        "schema_version": "physical-policy-review-manifest-v1", "source_before": before,
        "source_after": after, "source_preserved": True,
        "architectural_scale_m_per_bu": contract.scale.metres_per_blender_unit,
        "checkpoint_commit": config["checkpoint_commit"],
        "execution_parent_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
        ).stdout.strip(),
        "producer_code_sha256": producer_digests,
        "input_content_sha256": {name: content_sha256(value)
                                 for name, value in documents.items()},
        "config_content_sha256": content_sha256(config),
        "artifact_content_sha256": {name: content_sha256(value)
                                    for name, value in artifacts.items()},
        "geometry_model_sha256": canonical_geometry_sha256(snapshot),
        "local_certificate_content_sha256": {
            row["scope_id"]: content_sha256(row) for row in scopes["approved_scopes"]
        },
        "summary": summary, "runtime": {**runtimes, "total_seconds": time.perf_counter() - started},
    }
    write_document(output / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = validate_policy(args.config, args.output)
    print(json.dumps(manifest["summary"], sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
