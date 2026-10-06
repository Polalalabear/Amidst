"""Reproducible physical-authority blocker review; no inference or benchmark execution."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from amidst.architectural_scale import scale_for_scene_config
from amidst.geometry_authority import _reject_truth, digest, value_digest
from amidst.physical_authority import (
    PhysicalAuthorityResolution,
    PhysicalPolicy,
    PhysicalPurpose,
    ReadOnlyPhysicalAuthorityProvider,
    canonical_geometry_sha256,
)
from amidst.physical_floor_stair_review import review_floor_stairs
from amidst.physical_obstacle_resolution import review_obstacle_portal_conflicts
from amidst.scene_geometry import (
    Authority,
    GeometryAuthorityError,
    GeometryRole,
    ReadOnlySceneGeometryProvider,
    SceneGeometrySnapshot,
)


def resolve_physical_authority(
    audit: dict[str, Any],
    baseline: dict[str, Any],
    geometry: SceneGeometrySnapshot,
    survey: dict[str, Any],
    selection_config: dict[str, Any],
    scene_config: dict[str, Any],
    policy_config: dict[str, Any],
    *,
    expected_source_sha256: str,
    expected_geometry_sha256: str,
    checkpoint_commit: str,
    camera_calibration: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], PhysicalAuthorityResolution]:
    """Keep measured conflicts, missing policy and failed formal gates explicit."""
    for document in (audit, baseline, survey, selection_config, scene_config, policy_config):
        _reject_truth(document)
    if camera_calibration is not None:
        _reject_truth(camera_calibration)
    for document in (audit, baseline, survey, selection_config):
        if document.get("source_sha256") != expected_source_sha256:
            raise ValueError("physical resolution source SHA-256 mismatch")
    if survey.get("schema_version") != "physical-source-mesh-evidence-v1" or (
        selection_config.get("schema_version") != "physical-resolution-evidence-config-v1"
    ):
        raise ValueError("unsupported physical source evidence/config version")
    if survey.get("audit_content_sha256") != value_digest(audit) or (
        survey.get("config_content_sha256") != value_digest(selection_config)
    ):
        raise ValueError("physical evidence audit/selection content binding mismatch")
    if (
        survey.get("source_preserved") is not True
        or survey.get("saved") is not False
        or (
            survey.get("rendered") is not False
            or survey.get("policy", {}).get("gt_used") is not False
        )
    ):
        raise ValueError("physical source evidence must be read-only and geometry-only")
    geometry_provider = ReadOnlySceneGeometryProvider(geometry, expected_source_sha256)
    geometry = geometry_provider.snapshot
    if canonical_geometry_sha256(geometry) != expected_geometry_sha256:
        raise ValueError("physical resolution geometry content binding mismatch")
    architectural_scale = scale_for_scene_config(scene_config, expected_source_sha256)
    if (
        geometry.unit_scale_m != scene_config["meters_per_blender_unit"]
        or architectural_scale is not None and (
            geometry.scale_authority != Authority.APPROVED
            or geometry.scale_approval_id != architectural_scale.approval_id
        )
    ):
        raise ValueError("physical resolution scene/geometry scale authority mismatch")
    policy = PhysicalPolicy.model_validate_json(json.dumps(policy_config))
    obstacles = review_obstacle_portal_conflicts(
        audit,
        baseline,
        scene_config,
        expected_source_sha256=expected_source_sha256,
        expected_audit_content_sha256=survey["audit_content_sha256"],
        source_mesh_evidence=survey,
        source_mesh_config=selection_config,
    )
    floor_stair_config = {
        **scene_config,
        "floor_stair_review": selection_config["floor_stair_review"],
    }
    floors_stairs = review_floor_stairs(
        audit,
        survey,
        floor_stair_config,
        camera_calibration=camera_calibration,
    )
    wall_ids = sorted(
        row.surface_id
        for row in geometry.surfaces
        if row.role == GeometryRole.WALL and row.semantic_authority == Authority.HIGH_CONFIDENCE
    )
    obstacle_ids = sorted(
        row.surface_id for row in geometry.surfaces if row.role == GeometryRole.OBSTACLE
    )
    walkable_ids = sorted(
        row.surface_id for row in geometry.surfaces if row.role == GeometryRole.WALKABLE
    )
    blockers = [
        "FLOOR_AUTHORITY_REVIEW",
        "OBSTACLE_VOLUME_REVIEW",
        "PORTAL_PHYSICAL_REVIEW",
        "STAIR_CONNECTIVITY_OPENING_CLEARANCE_REVIEW",
        "WALL_EVIDENCE_PROVISIONAL",
    ]
    if policy.authority != Authority.APPROVED or policy.pending_fields():
        blockers.append("BODY_AND_CLEARANCE_POLICY_REVIEW")
    scopes = []
    for purpose in PhysicalPurpose:
        scopes.append(
            {
                "scope_id": "school-v3-" + purpose.value.lower(),
                "purpose": purpose.value,
                "floor_ids": sorted(row.floor_id for row in geometry.floors),
                "surface_ids": sorted(
                    wall_ids
                    + obstacle_ids
                    + ([] if purpose == PhysicalPurpose.KNOWN_COLLISION_PRUNING else walkable_ids)
                ),
                "portal_ids": sorted(row.portal_id for row in geometry.portals),
                "stair_ids": sorted(row.stair_id for row in geometry.stairs),
                "coverage": "PARTIAL",
                "authority": "HUMAN_REVIEW",
                "unresolved_reasons": sorted(blockers),
                "evidence_ids": ["physical-resolution-review", survey["audit_content_sha256"]],
                "approval_id": None,
            }
        )
    resolution = PhysicalAuthorityResolution.model_validate_json(
        json.dumps(
            {
                "schema_version": "physical-authority-v1",
                "source_sha256": expected_source_sha256,
                "geometry_sha256": expected_geometry_sha256,
                "level": "PROVISIONAL",
                "policy": policy.model_dump(mode="json"),
                "scopes": scopes,
                "evidence_ids": ["physical-resolution-review", value_digest(survey)],
            }
        )
    )
    provider = ReadOnlyPhysicalAuthorityProvider(
        geometry,
        resolution,
        expected_source_sha256,
        expected_geometry_sha256,
    )
    decisions = []
    for scope in provider.get_scopes():
        try:
            provider.require_scope(scope.scope_id, purpose=scope.purpose)
        except GeometryAuthorityError as rejection:
            decisions.append(
                {
                    "scope_id": scope.scope_id,
                    "purpose": scope.purpose.value,
                    "formal_use_allowed": False,
                    "reason_codes": list(rejection.reasons),
                }
            )
        else:
            decisions.append(
                {
                    "scope_id": scope.scope_id,
                    "purpose": scope.purpose.value,
                    "formal_use_allowed": True,
                    "reason_codes": [],
                }
            )
    report = {
        "schema_version": "physical-authority-blocker-report-v1",
        "source_sha256": expected_source_sha256,
        "geometry_sha256": expected_geometry_sha256,
        "checkpoint_commit": checkpoint_commit,
        "physical_authority": resolution.level.value,
        "scope": "PHASE1_BLOCKER_REVIEW_NOT_FORMAL_BENCHMARK",
        "obstacles": obstacles,
        "floors_stairs": floors_stairs,
        "proposed_floor_planes": scene_config["floor_planes"],
        "wall_scope": {
            "high_confidence_surfaces": wall_ids,
            "count": len(wall_ids),
            "authority": "HIGH_CONFIDENCE",
            "doorway_protection_preserved": True,
            "thresholds_lowered": False,
            "ambiguous_patches_promoted": False,
        },
        "physical_policy": {
            "config": policy.model_dump(mode="json"),
            "pending_fields": list(policy.pending_fields()),
        },
        "formal_scope_decisions": decisions,
        "collision_hard_pruning_ready": any(
            row["purpose"] == PhysicalPurpose.KNOWN_COLLISION_PRUNING.value
            and row["formal_use_allowed"]
            for row in decisions
        ),
        "source_selection": survey["summary"],
        "incomplete_source_regions": [
            {"region_id": row["region_id"], "reason_codes": row["unresolved_reasons"]}
            for row in survey["regions"]
            if not row["complete"]
        ],
        "policy": {
            "source_saved": False,
            "scene_geometry_modified": False,
            "gt_used": False,
            "benchmark_run": False,
            "ranking_modified": False,
            "graph_modified": False,
        },
    }
    return report, resolution


def write_report(report: dict[str, Any], path: Path) -> None:
    obstacles, floors = report["obstacles"], report["floors_stairs"]
    volume_count = len(obstacles["obstacle_volume_evidence"])
    wall_count = report["wall_scope"]["count"]
    mesh_binding = report.get("input_bindings", {}).get("survey", {}).get("path")
    mesh_reference = "source_mesh_evidence.json" if mesh_binding is None else Path(os.path.relpath(
        Path(mesh_binding).resolve(), path.parent.resolve(),
    )).as_posix()
    annotation_pairs = sum(
        row["classification"] == "SEMANTIC_ANNOTATION_DEPTH_OVERLAP_CLEAR_DECLARED_CENTER_PLANE"
        for row in obstacles["pairs"]
    )
    lines = [
        "# Physical authority blocker review / 物理權威 blocker 審查",
        "",
        f"Overall authority: **{report['physical_authority']}**。",
        f"Checkpoint `{report['checkpoint_commit']}`；source `{report['source_sha256']}`。",
        f"Architectural scale: **{floors['scale_authority']}**; "
        f"1 BU = {floors['meters_per_blender_unit']} m。原始幾何座標保留 BU。",
        "Annotation consistency 不等於 physical approval。",
        "",
        "## OBSTACLE ↔ PORTAL",
        "",
        "| Floor | AREA | Obstacle | Portal | Overlap | Classification | Physical state |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in obstacles["pairs"]:
        ratio = row.get("portal_overlap_ratio")
        ratio_text = "N/A" if ratio is None else f"{ratio:.2%}"
        lines.append(
            f"| {row.get('floor_id', 'N/A')} | "
            f"{
                ', '.join(
                    a['object_id']
                    for a in row.get('areas', [])
                    if a['floor_id'] == row.get('floor_id')
                )
            } | "
            f"{row['obstacle_id']} | {row['portal_id']} | {ratio_text} | "
            f"{row['classification']} | {row['physical_status']} |"
        )
    lines.extend(
        [
            "",
            f"Scene repairs: **{obstacles['repair_count']}**。",
            "Actual ROI source meshes 是未分類 context；不自動當作 obstacle volume。",
            "無可信 geometry 依據時不縮 footprint、不移 portal；清楚區分 annotation overlap",
            "與尚待核准的實際 aperture／blocker。全部詳情見 [report JSON](resolution.json)。",
            "",
            "## Stair A/B",
            "",
            "| Stair | Actual context triangles | Shared landing evidence | Authority |",
            "| --- | ---: | --- | --- |",
        ]
    )
    bounds_lines = ["", "## Conflict object bounds", ""]
    for row in obstacles["pairs"]:
        bounds_lines.extend(
            [
                f"- `{row['obstacle_id']}` bounds: `{row.get('obstacle_bounds_m')}`",
                f"- `{row['portal_id']}` bounds: `{row.get('portal_bounds_m')}`",
            ]
        )
    for row in floors["stair_reviews"]:
        landing = any(
            x["actual_shared_landing_evidence"] for x in row.get("landing_join_measurements", [])
        )
        lines.append(
            f"| {row['stair_id']} | {row.get('actual_source_triangle_count', 'N/A')} | "
            f"{landing} | {row['status']} |"
        )
    lines.append("")
    for row in floors["stair_reviews"]:
        lines.append(f"- {row['stair_id']} reasons: " + ", ".join(row.get("reason_codes", [])))
    lines.extend(
        [
            "",
            "沒有幾何證據就不填 landing；ROI 中沒有三角面不證明 opening／clearance 合格。",
            "Nearest component gap 與 centerline U-turn gap 是不同測量。",
            "",
            "## Floor authority / Object exceptions",
            "",
            "| WALKABLE object | Floor | Proposed Z | Actual dominant Z | Offset | "
            "State / reason |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for row in floors["floor_reviews"]:
        support = row.get("dominant_support")
        z = support["z_range_units"] if support else "UNMEASURED"
        proposed = row.get("proposed_plane_z_units")
        if proposed is None and row.get("floor_id") in report["proposed_floor_planes"]:
            proposed = (
                report["proposed_floor_planes"][row["floor_id"]]["height_m"]
                / floors["meters_per_blender_unit"]
            )
        lines.append(
            f"| {row['object_id']} | {row.get('floor_id', 'N/A')} | "
            f"{proposed} | {z} | "
            f"{row.get('proposed_minus_actual_z_units', 'N/A')} | "
            f"{row['status']}: {', '.join(row.get('reason_codes', []))} |"
        )
    lines.extend(
        [
            "",
            f"Camera-plane: **{floors['camera_plane_authority']}**; {floors['camera_reason']}",
            "AREA／PORTAL object Z ranges 和個別例外保存於 JSON 的 annotation_floor_context。",
            "不把家具面、annotation plane 或 old-camera hash 當作 floor authority。",
            "",
            "## Obstacle volume / Body / Portal / Contact policy",
            "",
            f"{volume_count} 個原 role approval 與實際 volume approval 分開；"
            "open footprints 不擠出高度。",
            "待決 policy fields: " + ", ".join(report["physical_policy"]["pending_fields"]),
            "數值及 body/reference/comparison 未批准時維持 null／HUMAN_REVIEW；",
            "numeric epsilon 和 export budgets 不代替 body-clearance／collision tolerance。",
            "",
            "## Provider purpose / Scope",
            "",
            "| Purpose | Formal use | Reasons |",
            "| --- | --- | --- |",
        ]
    )
    for row in report["formal_scope_decisions"]:
        lines.append(
            f"| {row['purpose']} | {row['formal_use_allowed']} | "
            f"{', '.join(row['reason_codes'][:6])} |"
        )
    lines.extend(
        [
            "",
            "[Strict provider contract](../../../docs/GEOMETRY_PROVIDER.md)；",
            "[authority sidecar](physical_authority.json)；"
            f"[mesh evidence]({mesh_reference})。",
            f"WALL 保留 {wall_count} HIGH_CONFIDENCE provisional evidence，"
            "原 doorway guard 與閾值不變。",
            f"Collision hard-pruning ready: **{report['collision_hard_pruning_ready']}**。",
            "局部 positive pruning 不認證完整空間無碰撞；complete physical metrics/topology",
            "需要 purpose-specific COMPLETE approved scope。未批准 scope 明確 typed refuse。",
            "",
            "## Remaining HUMAN_REVIEW",
            "",
            f"- {len(obstacles['pairs']) - annotation_pairs} 組 blocker／footprint／portal "
            f"placement 歧義與 {annotation_pairs} 組已解釋 annotation margin，",
            "  仍需 source-bound aperture／obstacle volume；不以 validator pass 取代人工確認。",
            "- Floor support、stair ENTRY／EXIT、landing／opening／body clearance 的 authority。",
            "- Config-driven pedestrian parameters、contact comparison "
            "與 research clearance policy。",
            "- 未分類 source mesh 不能因位於 ROI 就自動獲得 movement／occlusion ownership。",
            "",
            "不執行 Case 1–3、Graph／ranking／benchmark，不讀 GT，不修改 source .blend。",
        ]
    )
    lines.extend(bounds_lines)
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "audit",
        "baseline",
        "geometry",
        "survey",
        "selection-config",
        "scene-config",
        "policy-config",
        "baseline-manifest",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--camera-calibration", type=Path)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--checkpoint-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    outputs = [
        args.output / name
        for name in ("resolution.json", "resolution.md", "physical_authority.json", "manifest.json")
    ]
    if any(path.exists() for path in outputs):
        raise FileExistsError("physical resolution output exists; use a fresh output directory")
    names = (
        "audit",
        "baseline",
        "geometry",
        "survey",
        "selection_config",
        "scene_config",
        "policy_config",
        "baseline_manifest",
    )
    paths = {name: getattr(args, name) for name in names}
    if args.camera_calibration:
        paths["camera_calibration"] = args.camera_calibration
    documents = {name: json.loads(path.read_text()) for name, path in paths.items()}
    checkpoint = documents["baseline_manifest"]
    if checkpoint["source_sha256"] != args.expected_source_sha256 or any(
        digest(paths[name]) != checkpoint["artifacts"][artifact]
        for name, artifact in (("baseline", "authority.json"), ("geometry", "geometry.json"))
    ):
        raise ValueError("baseline artifacts differ from checkpoint manifest")
    geometry = SceneGeometrySnapshot.model_validate_json(paths["geometry"].read_text())
    report, resolution = resolve_physical_authority(
        documents["audit"],
        documents["baseline"],
        geometry,
        documents["survey"],
        documents["selection_config"],
        documents["scene_config"],
        documents["policy_config"],
        expected_source_sha256=args.expected_source_sha256,
        expected_geometry_sha256=canonical_geometry_sha256(geometry),
        checkpoint_commit=args.checkpoint_commit,
        camera_calibration=documents.get("camera_calibration"),
    )
    if documents["scene_config"].get("architectural_scale_config") is not None:
        paths["architectural_scale"] = Path(documents["scene_config"]["architectural_scale_config"])
    report["input_bindings"] = {
        name: {"path": str(path), "sha256": digest(path)} for name, path in paths.items()
    }
    args.output.mkdir(parents=True, exist_ok=True)
    outputs[0].write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    write_report(report, outputs[1])
    outputs[2].write_text(resolution.model_dump_json(indent=2) + "\n")
    code_paths = [
        "src/amidst/physical_resolution.py",
        "src/amidst/architectural_scale.py",
        "src/amidst/physical_authority.py",
        "src/amidst/physical_obstacle_resolution.py",
        "src/amidst/physical_floor_stair_review.py",
        "scripts/export_physical_authority_evidence.py",
    ]
    outputs[3].write_text(
        json.dumps(
            {
                "schema_version": "physical-resolution-manifest-v1",
                "checkpoint_commit": args.checkpoint_commit,
                "source_sha256": args.expected_source_sha256,
                "inputs": report["input_bindings"],
                "artifacts": {path.name: digest(path) for path in outputs[:3]},
                "code_sha256": {name: digest(Path(name)) for name in code_paths},
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "authority": report["physical_authority"],
                "obstacle_pairs": report["obstacles"]["pair_count"],
                "repairs": report["obstacles"]["repair_count"],
                "hard_pruning_ready": report["collision_hard_pruning_ready"],
            }
        )
    )


if __name__ == "__main__":
    main()
