"""Inspect only source authority and inference evidence; print a review snapshot.

This tool does not open GT, evaluation, simulation plans or trajectory recipes.
It never edits configs, authority, decisions or source assets. Redirect stdout to
settings_evidence.json only when intentionally rebuilding this review evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SITES = ("corridor", "office", "auditorium")
SCENE_SHA = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
FORBIDDEN_KEYS = {"ground_truth", "evaluation", "waypoints", "trajectory_plan", "recipe"}
REVIEW_FILES = (
    "configs/benchmarks/protocol_v1.json",
    "configs/architectural_scale_school_v3.json",
    "configs/physical_authority_policy_school_v3.json",
    "configs/physical_policy_runtime_school_v3.json",
    "configs/physical_collision_numerics_v1.json",
    "src/amidst/domain/metric_config.py",
    "src/amidst/domain/search.py",
    "src/amidst/domain/reconstruction.py",
    "src/amidst/datasets/pilot.py",
    "src/amidst/datasets/pilot_topology.py",
    "src/amidst/benchmark/baselines.py",
    "scripts/phase1_projection_policy.py",
    "data/scene_audit/phase1_physical_policy_approval_20261006/floor_authority_map.json",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def reject_truth(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"review evidence includes a forbidden field: {key}")
            reject_truth(item)
    elif isinstance(value, list):
        for item in value:
            reject_truth(item)
    elif value == "GROUND_TRUTH":
        raise ValueError("review evidence includes GROUND_TRUTH provenance")


def read_inference(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("inference review evidence must be a JSON object")
    reject_truth(value)
    if value.get("source_asset_sha256") != SCENE_SHA:
        raise ValueError("inference evidence is not bound to the pinned school scene")
    return value


def endpoint(frame: dict[str, Any]) -> dict[str, Any]:
    return {key: frame[key] for key in (
        "camera_id", "frame_id", "timestamp", "target_id", "point_2d", "provenance",
    )}


def camera_runs(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for frame in frames:
        if not runs or runs[-1]["status"] != frame["status"]:
            runs.append({
                "status": frame["status"], "first_frame_id": frame["frame_id"],
                "last_frame_id": frame["frame_id"], "first_timestamp": frame["timestamp"],
                "last_timestamp": frame["timestamp"], "sample_count": 0,
            })
        runs[-1]["last_frame_id"] = frame["frame_id"]
        runs[-1]["last_timestamp"] = frame["timestamp"]
        runs[-1]["sample_count"] += 1
    return runs


def inspect(repo: Path, inference_root: Path, source_asset: Path | None) -> dict[str, Any]:
    inputs = [{"path": name, "sha256": digest(repo / name)} for name in REVIEW_FILES]
    scale = json.loads((repo / REVIEW_FILES[1]).read_text())
    metres_per_bu = float(scale["metres_per_blender_unit"])
    if metres_per_bu != 0.0247:
        raise ValueError("approved architectural scale changed")
    floor_map = json.loads((repo / REVIEW_FILES[-1]).read_text())
    floors = {item["floor_id"]: item for item in floor_map["floor_authorities"]}
    support = {item["walkable_id"]: item for item in floor_map["walkable_reviews"]}
    streams = []
    for site in SITES:
        context_path = inference_root / site / "context.json"
        observation_path = inference_root / site / "observations.json"
        context = read_inference(context_path)
        observations = read_inference(observation_path)
        if digest(observation_path) != context["observations_sha256"]:
            raise ValueError("observations SHA does not match its inference context")
        if context["site_id"] != site or observations["site_id"] != site:
            raise ValueError("inference site binding differs from requested source")
        frames = sorted(observations["frames"], key=lambda row: (
            row["timestamp"], row["target_id"], row["frame_id"], row["camera_id"],
        ))
        stamps = sorted({float(item["timestamp"]) for item in frames})
        steps = [b - a for a, b in zip(stamps, stamps[1:], strict=False)]
        if not steps or any(not math.isclose(step, 0.2, abs_tol=1e-9) for step in steps):
            raise ValueError("existing inference timestamp grid is no longer exactly 5 Hz")
        floor = floors[context["zone"]["floor_id"]]
        walkable = support[context["zone"]["walkable_object_id"]]
        if floor["authority"] != "APPROVED" or walkable["authority"] != "APPROVED":
            raise ValueError("existing floor support lacks approved authority")
        floor_z = float(walkable["source_support_height_bu"])
        offset = float(context["plane"]["point"][2]) - floor_z
        cameras = []
        for camera in sorted(context["cameras"], key=lambda row: row["camera_id"]):
            camera_frames = [item for item in frames if item["camera_id"] == camera["camera_id"]]
            visible = [item for item in camera_frames if item["status"] == "OBSERVED"]
            cameras.append({
                "camera_id": camera["camera_id"], "source_calibration": camera,
                "source_calibration_canonical_sha256": hashlib.sha256(json.dumps(
                    camera, sort_keys=True, separators=(",", ":"), allow_nan=False,
                ).encode()).hexdigest(),
                "position_bu": [camera["camera_to_world"][axis][3] for axis in range(3)],
                "position_m": [camera["camera_to_world"][axis][3] * metres_per_bu
                               for axis in range(3)],
                "observed_sample_count": len(visible),
                "gap_sample_count": len(camera_frames) - len(visible),
                "first_observed_endpoint": endpoint(visible[0]) if visible else None,
                "last_observed_endpoint": endpoint(visible[-1]) if visible else None,
                "observed_frame_ids": [item["frame_id"] for item in visible],
                "visibility_runs": camera_runs(camera_frames),
            })
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for frame in frames:
            groups.setdefault((frame["target_id"], frame["timestamp"], frame["frame_id"]),
                              []).append(frame)
        streams.append({
            "site_id": site,
            "evidence_status": "DIAGNOSTIC_INFERENCE_ONLY_NOT_FORMAL_CASE_ROUTE",
            "context_path": str(context_path.relative_to(repo)) if context_path.is_relative_to(repo)
            else str(context_path),
            "context_sha256": digest(context_path),
            "observations_path": str(observation_path.relative_to(repo))
            if observation_path.is_relative_to(repo) else str(observation_path),
            "observations_sha256": digest(observation_path),
            "zone": context["zone"], "landmark_plane": context["plane"],
            "approved_floor_plane": floor, "approved_walkable_id": walkable["walkable_id"],
            "floor_support_z_bu": floor_z, "floor_support_z_m": floor_z * metres_per_bu,
            "landmark_z_bu": context["plane"]["point"][2],
            "landmark_z_m": context["plane"]["point"][2] * metres_per_bu,
            "rigid_landmark_to_floor_offset_bu": offset,
            "rigid_landmark_to_floor_offset_m": offset * metres_per_bu,
            "offset_basis": "INFERENCE_PLANE_MINUS_APPROVED_SOURCE_SUPPORT_NO_GT",
            "offset_semantic_authority": "HUMAN_REVIEW",
            "sampling_hz": 5, "timestamp_first": stamps[0], "timestamp_last": stamps[-1],
            "timestamp_count": len(stamps),
            "exact_time_multiple_observed_views_count": sum(
                sum(item["status"] == "OBSERVED" for item in group) >= 2
                for group in groups.values()
            ),
            "cameras": cameras,
        })
    source = {"source_asset_path": "blender/school_v3.blend", "pinned_sha256": SCENE_SHA,
              "source_immutable": True, "source_size_bytes": 468300506}
    if source_asset is not None:
        source["verified_sha256"] = digest(source_asset)
        source["verified_size_bytes"] = source_asset.stat().st_size
        if source["verified_sha256"] != SCENE_SHA or source["verified_size_bytes"] != 468300506:
            raise ValueError("source asset differs from the pinned physical/projection checkpoints")
    return {
        "schema_version": "phase1-human-review-settings-evidence-v1",
        "status": "HUMAN_REVIEW_PENDING_NO_FORMAL_EXECUTION",
        "checkpoint_sha": "85f5e6b055e75d286c1519e6c5ba2f2efc416347",
        "source": source, "input_hashes": inputs, "streams": streams,
        "ground_truth_or_evaluation_opened": False, "simulation_recipe_opened": False,
        "automatic_settings": {
            "metres_per_blender_unit": metres_per_bu, "k_values": [1, 2, 3],
            "distance_metric": "ADE", "coverage_comparison": "STRICTLY_LESS_THAN",
            "sampling_hz": 5, "sampling_extent": "SOURCE_ENDPOINTS_INCLUSIVE_NO_REJECTION",
            "temporal_alignment_policy": "ALL_GROUND_TRUTH_TIMESTAMPS_EXACT_EXTENT",
            "interpolation_policy": "PIECEWISE_LINEAR",
            "top_k_policy": "FIRST_HYPOTHESIS_PER_DISTINCT_CANDIDATE_IN_INPUT_ORDER",
            "aggregation_max_visible_sample_gap_s": None,
            "projection_policy": "EXACT_TIME_MULTIVIEW_THEN_SINGLE_VIEW_FIXED_PLANE",
            "pixel_sigma_px": None, "unavailable_uncertainty": "RETAIN_AND_MARK_LOW_CONFIDENCE",
            "physical_policy": json.loads((repo / REVIEW_FILES[2]).read_text()),
            "baseline_protocol": "EXISTING_A_B_C_FACTOR_MASKS_AND_SUPPORTED_ABLATIONS",
            "cross_case_aggregation": "NONE", "case4": "DEFERRED", "phase2": "FROZEN",
        },
        "review_decisions": [
            {
                "id": "HR-02", "category": "PROJECTION_BINDING", "blocks": [1, 2, 3],
                "title": "可見 landmark 如何對應核准地板上的人物落點",
                "approved_binding_candidate_site": "office",
                "approved_binding_candidate_cameras": [
                    "CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR",
                ],
                "approved_binding_candidate_floor": "1F",
                "approved_binding_candidate_area": "AREA_1F_OFFICE",
                "approved_binding_candidate_walkable": "WALK_1F_OFFICE",
                "other_streams_role": "HISTORICAL_LIMITATION_EVIDENCE_NOT_BINDING_APPROVAL",
                "recommended_option": "SOURCE_BOUND_RIGID_LANDMARK_OFFSET",
                "approve_options": [
                    {"id": "SOURCE_BOUND_RIGID_LANDMARK_OFFSET",
                     "landmark_reference": "RIGID_UPRIGHT_SOURCE_BOUND_MARKER",
                     "offset": "PER_CONTEXT_PLANE_MINUS_APPROVED_SOURCE_SUPPORT",
                     "inference_reference": "FLOOR_CONTACT_POINT",
                     "conversion": "SUBTRACT_SOURCE_BOUND_Z_OFFSET_KEEP_XY",
                     "single_view_fallback": "ALLOWED_WITH_METHOD_CONFIDENCE_PROVENANCE",
                     "scope": "GEOMETRY_DECISION_APPROVED_LOCAL_DOMAIN_WITHIN_WALK_1F_OFFICE",
                     "fresh_observations_required": True},
                    {"id": "FLOOR_CONTACT_MARKER",
                     "landmark_reference": "VISIBLE_FLOOR_CONTACT_POINT",
                     "offset_bu": 0.0, "offset_m": 0.0,
                     "inference_reference": "FLOOR_CONTACT_POINT",
                     "single_view_fallback": "ALLOWED_WITH_METHOD_CONFIDENCE_PROVENANCE",
                     "scope": "GEOMETRY_DECISION_APPROVED_LOCAL_DOMAIN_WITHIN_WALK_1F_OFFICE",
                     "fresh_observations_required": True},
                ],
                "decision": None,
            },
            {
                "id": "HR-03", "category": "FORMAL_SETTING", "blocks": [1, 2, 3],
                "title": "Coverage 的正式 ADE 容差",
                "recommended_option": "ADE_EPSILON_0_50_M",
                "approve_options": [
                    {"id": "ADE_EPSILON_0_50_M", "distance_metric": "ADE",
                     "epsilon_m": 0.5, "comparison": "STRICTLY_LESS_THAN"},
                    {"id": "ADE_EPSILON_1_00_M", "distance_metric": "ADE",
                     "epsilon_m": 1.0, "comparison": "STRICTLY_LESS_THAN"},
                ],
                "scale_basis": "EXISTING_PROTOCOL_INITIAL_TARGETS_NOT_APPROVED_COVERAGE",
                "decision": None,
            },
            {
                "id": "HR-04", "category": "FORMAL_SETTING", "blocks": [1, 2, 3],
                "title": "固定現有速度上限與長 GAP 的 timing 假設",
                "recommended_option": "EXISTING_SPEED_WITH_SUPPORTED_DWELL",
                "approve_options": [
                    {"id": "EXISTING_SPEED_WITH_SUPPORTED_DWELL",
                     "max_speed_bu_s": 32.0, "max_speed_m_s": 0.7904,
                     "direct_path_slack_tolerance_s": 1.0,
                     "include_dwell_hypotheses": True,
                     "dwell_location": "DEPARTURE_WAYPOINT_ONLY",
                     "timing_primary": "UNIFORM_CONTINUOUS_FIRST"},
                    {"id": "EXISTING_SPEED_UNIFORM_ONLY",
                     "max_speed_bu_s": 32.0, "max_speed_m_s": 0.7904,
                     "direct_path_slack_tolerance_s": 1.0,
                     "include_dwell_hypotheses": False,
                     "dwell_location": None,
                     "timing_primary": "UNIFORM_CONTINUOUS_FIRST"},
                ],
                "speed_authority": "PROPOSED_FORMAL_RESEARCH_CEILING_NOT_MEASURED_PERSON_SPEED",
                "decision": None,
            },
        ],
        "automatic_readiness_requirements": [
            "Apply source-bound geometry decisions then calculate complete local certificates.",
            "Prove Case1 uniqueness, Case2 distinct feasible branches, Case3 timing feasibility.",
            "Verify camera FOV, occlusion, calibration and GAP endpoint domain without GT.",
            "Add source-bound landmark-to-footpoint and multiview endpoint authority adapters.",
            "Wrap diagnostic-only context/MetricConfig contracts with formal approval evidence.",
            "Create frozen source/config hashes, fresh formal dataset and independent inventory.",
        ],
        "automatic_readiness_owner": "AGENT_AFTER_EXPLICIT_DECISIONS",
        "case3_instance_status": {
            "exact_gap_duration_fixed_by_protocol": False,
            "illustrative_prd_gap_s": [20, 180],
            "illustrative_values_are_existing_school_dataset": False,
            "instance_owner": "AGENT_PRE_DATASET_AUTOMATIC_CASE_PREFLIGHT",
            "required_proof": [
                "AUTHORIZED_LOCAL_ROUTE_AND_SOURCE_CAMERA_VISIBILITY",
                "GAP_EXCEEDS_MINIMUM_TRAVEL_TIME_WITH_LEGAL_TEMPORAL_SLACK",
                "SHARED_ENDPOINT_TIMES_FOR_ALL_METHODS",
                "SOURCE_BOUND_SCHEDULE_DECLARED_AND_HASH_LOCKED_BEFORE_METRICS",
                "NO_GAP_EVIDENCE_FABRICATED_OR_GT_SELECTED_TIMING",
            ],
            "unique_duration_formula_declared": False,
            "extra_human_duration_decision_required_by_protocol": False,
            "current_preview_is_formal_long_gap_evidence": False,
        },
        "all_approve_means_existing_artifacts_immediately_formal": False,
        "choices": ["APPROVE", "REJECT", "FIX_GEOMETRY", "KEEP_REVIEW"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--inference-root", type=Path,
                        help="Only the sanitized inference directory; no evaluation/recipes.")
    parser.add_argument("--source-asset", type=Path, help="Read-only pinned .blend hash check.")
    args = parser.parse_args()
    repo = args.repo.resolve()
    inference_root = (args.inference_root.resolve() if args.inference_root is not None
                      else repo / "data/finalization/local_run/dataset/inference")
    print(json.dumps(inspect(repo, inference_root, args.source_asset), sort_keys=True,
                     indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
