"""Read-only adapters for existing, frozen engineering scene materializations.

Import validates the original source locks and builds scoped indexes once. No
renderer, producer, truth export or original Blender asset is opened by this
module. Human annotations are overlays owned by the separate review store.
"""

from __future__ import annotations

import copy
import json
import math
import re
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Self

from pydantic import RootModel, model_validator

from amidst.engineering.access import digest
from amidst.engineering.association import SyntheticStaticContext
from amidst.engineering.local_behavior import BehaviorConfig
from amidst.engineering.local_index import CameraLink, CameraRegions, ScopedTopology
from amidst.engineering.local_service import LocalPilotService
from amidst.engineering.registry import CameraEntry, MediaFrame, opaque_ref

Json = dict[str, Any]

MAX_EVALUATION_BYTES = 256 * 1024
_MODES = frozenset({"photos_only", "photos_plus_observations"})
_KINDS = frozenset({"ENTER", "EXIT", "CORNER", "DWELL", "POSSIBLE_WANDERING"})
_ASSOCIATION_KINDS = frozenset({
    "CROSS_CAMERA_GAP", "OVERLAPPING_VISIBILITY", "SAME_CAMERA_RECOVERY", "UNMATCHED",
})
_LOOKUP_REASONS = frozenset({
    "FINITE_LOOKUP_WINDOW_EXHAUSTED", "CAMERA_COVERAGE_UNKNOWN", "MAX_HOPS_REACHED",
    "MAX_CAMERAS_REACHED", "TOPOLOGY_INCOMPLETE", "MAX_RECORDS_REACHED",
    "ANCHOR_MISSING", "TOPOLOGY_MISSING", "CLOCK_MAPPING_MISMATCH",
})
_PRIVATE_LOCATOR = re.compile(r"(?:^|[\s\"'=:(])(?:/|[A-Za-z]:[\\/]|file://)|\.\./")

# Canonical content certificates from the published, immutable engineering receipts:
# local_camera_20261008/validation.json hashes.evaluation_sha256 and
# simulation_20261008/evaluation_summary.json. New runs require an explicit server
# certificate; deriving a certificate from the requested summary would bless tampering.
_CERTIFIED_EVALUATIONS = {
    ("synthetic-local-camera-v1", "local-camera-test-v1",
     "76d25ef357fa0876cc4fbe00f994a92773c537a6ef3090014970e50aef1f5c6c",
     "ed843f2916f4c25c5b5f42ff730349ba482356ec278ecd52df81a02264a0a73a"):
        "7d3e3c88a32adb62fae9d7ad31f877637591bfe9a1264e072094727741104283",
    ("synthetic-lab-v1", "simulation-v2",
     "189bbb73e559ac9df8a8c3e3b5b92943fa85e915d45b7bb5998a82336d74de2a",
     "02729186cee74f3bc2f002ee76518557c35d22c5d5c01cdc406e45f00ccf791c"):
        "e24d61ff6f12be7d8eddb0da30a33fb1ce86a56d9cd00541573ba5084aaef126",
}


def _fields(names: str, rule: str) -> dict[str, str]:
    return dict.fromkeys(names.split(), rule)


# Every nested object has a declared field contract. Categorical maps have finite
# key sets below; there is no arbitrary metadata, identity or diagnostic map.
_CONTRACTS: dict[str, dict[str, str]] = {
    "stats": {**_fields("maximum mean rms", "metric"), "samples": "count"},
    "diagnostic": {
        **_fields("run_id model_id status", "text"),
        **_fields("dataset_sha256 config_sha256", "hash"),
    },
    "association": {
        **_fields("global_false_merge_count global_false_split_count", "na"),
        **_fields("pair_level_false_merge_count pair_level_missed_link_count predicted_link_count "
                  "resolved_link_count true_link_count true_positive unresolved_link_count",
                  "count"),
        **_fields("same_identity_eligible_pair_precision same_identity_eligible_pair_recall",
                  "ratio"),
        "is_true_next_continuation_metric": "false", "metric_family": "text",
    },
    "behavior_metric": {
        **_fields("false_negative false_positive true_positive unresolved", "metric"),
        **_fields("precision recall", "ratio_or_na"),
    },
    "visible_behavior": {
        "confusion": "confusion", "direction_error": "na", "per_kind": "behavior_kinds",
        "prediction_count": "count", "trigger_midpoint_error_s": "stats",
    },
    "gap_behavior": {
        **_fields("canonical_candidate_count canonical_gap_event_count "
                  "canonical_timing_hypothesis_count hypothesis_event_count", "count"),
        **_fields("confusion direction_error trigger_error_s", "na"),
        **_fields("status uncertainty", "text"), "per_kind": "behavior_kinds",
    },
    "behavior": {
        "expected_all_recipe_events": "count", "groups": "behavior_groups",
        **_fields("note status", "text"), "time_tolerance_s": "number",
    },
    "policy": {
        **_fields("ambiguous_assignment_score_margin minimum_bbox_iou "
                  "segment_known_identity_purity", "ratio"),
        **_fields("behavior_time_tolerance_s contact_tolerance_px "
                  "reference_retrieval_window_s", "number"),
        **_fields("minimum_visible_pixels reference_retrieval_max_hops", "count"),
        **_fields("global_identity_metrics schema_version true_next_reference", "text"),
        "true_next_uses_retrieval_window_hop_or_budget": "false",
    },
    "pixels": {
        **_fields("IDF1 assignment segment_assignment", "text"),
        **_fields("bounded_detection_precision one_to_one_visible_contact_recall", "ratio"),
        **_fields("bounded_labeled_measurements eligible_visible_actor_contacts "
                  "impure_segment_count measurement_count unresolved_segment_count "
                  "within_local_track_id_switches", "count"),
        **_fields("ground_contact_error_m pixel_contact_error_px", "stats"),
    },
    "geometry": {
        **_fields("candidate_count hard_speed_violation_count outside_configured_region_count",
                  "count"),
        "formal_route_Coverage_at_K": "na", "projection_authority": "text",
    },
    "retrieval": {
        **_fields("bytes_read crops_read expansions frames_read "
                  "full_global_pair_count_for_comparison_only "
                  "independent_complete_scope_candidate_count "
                  "index_entries_touched pairs_considered "
                  "records_read reference_retrieval_max_hops retrieved_pair_count "
                  "retrieved_same_identity_eligible_pair_count "
                  "retrieved_true_next_successor_pair_count same_identity_eligible_pair_count "
                  "same_identity_eligible_pair_miss_count true_next_successor_miss_count "
                  "true_next_successor_pair_count", "count"),
        **_fields("complete_scope_pair_coverage same_identity_eligible_pair_retrieval_recall "
                  "true_next_successor_retrieval_recall", "ratio"),
        **_fields("inventory true_next_reference_condition", "text"),
        **_fields("query_latency_ms undetected_full_actor_trajectory_recall", "na"),
        **_fields("scope_completeness_is_formal_graph_proof "
                  "true_next_reference_has_window_hop_or_record_budget", "false"),
        "reference_retrieval_window_s": "number", "touched_camera_count_per_query": "counts",
        **_fields("stop_reasons truncation_reasons", "lookup_counts"),
    },
    "e1": {
        **_fields("config_sha256 dataset_sha256 evaluation_truth_sha256 "
                  "evaluator_policy_sha256 evaluator_sha256 freeze_sha256 inference_sha256",
                  "hash"),
        **_fields("model_id origin run_id schema_version split status", "text"),
        **_fields("external_model_calls formal_phase1_acceptance", "false"),
        "behavior_bundle_binding_verified": "bool", "limitations": "texts",
        "association_all_provisional_hypotheses": "association",
        "association_by_kind": "association_kinds", "behavior": "behavior",
        "evaluator_policy": "policy", "fixed_pool_feature_ablations": "ablations",
        "geometry": "geometry", "pixels_and_local_identity": "pixels", "retrieval": "retrieval",
    },
    "eligibility": _fields("bbox contact error_matching "
                           "merged_partial_measurements recall_matching", "text"),
    "e0_mode": {
        **_fields("association_identity_precision association_identity_recall detection_precision "
                  "formal_research_metrics", "na"),
        **_fields("candidate_count canonical_gap_count eligible_actor_contacts frame_count "
                  "local_track_count measurement_count one_to_one_contact_matches_24px", "count"),
        "eligible_detection_recall_24px": "ratio",
        **_fields("best_unoccluded_bbox_iou nearest_eligible_pixel_contact_error_px "
                  "same_nearest_contact_ground_error_m", "stats"),
        "association_kind_counts": "association_counts", "association_status_counts": "statuses",
        "frame_status_counts": "frame_counts", "measurement_status_counts": "measurement_counts",
        "projection_status_counts": "projection_counts",
    },
    "e0": {
        **_fields("config_sha256 dataset_sha256 evaluation_truth_sha256 registry_sha256", "hash"),
        **_fields("authority model_id origin run_id schema_version status", "text"),
        **_fields("external_model_calls formal_phase1_acceptance", "false"),
        "eligibility": "eligibility", "freeze_receipt_sha256": "hashes", "limitations": "texts",
        "modes": "e0_modes",
    },
}
_CONTRACTS["ablation"] = {
    **_CONTRACTS["association"], "candidate_pool_sha256": "hash", "eligible_query_count": "count",
    "hard_physics_preserved": "true", "identity_candidate_recall_at_k": "recall_k",
    "removed_feature": "removed_feature", "scores_are_probabilities": "false",
}


def _evaluation_map(value: object, keys: frozenset[str], rule: str,
                    *, complete: bool = False) -> None:
    if not isinstance(value, dict) or not set(value) <= keys or complete and set(value) != keys:
        raise ValueError("INVALID_AGGREGATE_FIELDS")
    for child in value.values():
        _evaluation_field(child, rule)


def _evaluation_field(value: object, rule: str) -> None:
    if rule in _CONTRACTS:
        fields = _CONTRACTS[rule]
        optional = {"true_positive", "unresolved"} if rule == "behavior_metric" else set()
        if not isinstance(value, dict) or not set(value) <= fields.keys() or (
            not fields.keys() - optional <= value.keys()
        ):
            raise ValueError("INVALID_AGGREGATE_FIELDS")
        for name, child in value.items():
            _evaluation_field(child, fields[name])
        return
    categorical = {
        "association_kinds": (_ASSOCIATION_KINDS - {"UNMATCHED"}, "association", True),
        "association_counts": (_ASSOCIATION_KINDS, "count", False),
        "behavior_kinds": (_KINDS, "behavior_metric", True),
        "statuses": (frozenset({"HOLD", "INCOMPATIBLE", "PROVISIONAL", "UNMATCHED"}),
                     "count", False),
        "frame_counts": (frozenset({"MEASURED", "NO_DETECTION", "AMBIGUOUS_COMPONENT",
                                    "MISSING_IMAGE", "INVALID_IMAGE", "HASH_MISMATCH"}),
                         "count", False),
        "measurement_counts": (frozenset({"DETECTED", "MERGED_OR_PARTIAL"}), "count", False),
        "projection_counts": (frozenset({"PROJECTED", "OUTSIDE_STATIC_SCOPE", "UNCALIBRATED",
                                         "INVALID_CONTACT", "NO_SURFACE_INTERSECTION"}),
                              "count", False),
        "lookup_counts": (_LOOKUP_REASONS, "count", False),
        "recall_k": (frozenset({"1", "3", "5"}), "ratio", True),
        "e0_modes": (_MODES, "e0_mode", True),
        "ablations": (frozenset({"full", "without_appearance", "without_space", "without_time"}),
                      "ablation", True),
        "confusion": (frozenset(f"{a}->{b}" for a in _KINDS | {"NONE"}
                               for b in _KINDS | {"NONE"}), "count", False),
    }
    if rule in categorical:
        keys, child_rule, complete = categorical[rule]
        _evaluation_map(value, keys, child_rule, complete=complete)
        return
    if rule == "behavior_groups":
        if not isinstance(value, dict) or set(value) != {"visible_supported", "inferred_gap"}:
            raise ValueError("INVALID_AGGREGATE_FIELDS")
        _evaluation_field(value["visible_supported"], "visible_behavior")
        _evaluation_field(value["inferred_gap"], "gap_behavior")
        return
    if rule in {"texts", "counts", "hashes"}:
        if not isinstance(value, list) or len(value) > 128:
            raise ValueError("INVALID_AGGREGATE_ARRAY")
        for child in value:
            _evaluation_field(child, {"texts": "text", "counts": "count", "hashes": "hash"}[rule])
        return
    if rule == "removed_feature":
        if value not in (None, "SPACE", "TIME", "APPEARANCE"):
            raise ValueError("INVALID_AGGREGATE_VALUE")
        return
    if rule in {"true", "false", "bool"}:
        if type(value) is not bool or rule != "bool" and value != (rule == "true"):
            raise ValueError("INVALID_AGGREGATE_VALUE")
        return
    if rule == "hash":
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("INVALID_AGGREGATE_HASH")
        return
    if rule in {"text", "na"} or rule in {"metric", "ratio_or_na"} and isinstance(value, str):
        if not isinstance(value, str) or not value or len(value) > 1024 or (
            _PRIVATE_LOCATOR.search(value) or any(ord(char) < 32 for char in value)
        ) or rule != "text" and not (value == "N/A" or value.startswith("N/A:")):
            raise ValueError("INVALID_AGGREGATE_TEXT")
        return
    if rule in {"metric", "ratio", "ratio_or_na"} and value is None:
        return
    if rule == "count":
        if type(value) is not int or not 0 <= value <= 10**15:
            raise ValueError("INVALID_AGGREGATE_COUNT")
        return
    if rule in {"number", "metric", "ratio", "ratio_or_na"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or (
            not math.isfinite(value) or value < 0
        ) or (
            rule in {"ratio", "ratio_or_na"} and value > 1
        ):
            raise ValueError("INVALID_AGGREGATE_NUMBER")
        return
    raise ValueError("UNKNOWN_AGGREGATE_CONTRACT")


class AggregateEvaluationDTO(RootModel[Json]):
    """Exact E0/E1 aggregate contracts, preserving metrics and excluding raw labels."""

    @model_validator(mode="after")
    def aggregate_only(self) -> Self:
        nodes = 0

        def bounded(value: object, depth: int = 0) -> None:
            nonlocal nodes
            nodes += 1
            if depth > 12 or nodes > 4096:
                raise ValueError("AGGREGATE_COMPLEXITY_LIMIT")
            if isinstance(value, dict):
                if len(value) > 128:
                    raise ValueError("AGGREGATE_COMPLEXITY_LIMIT")
                for key, child in value.items():
                    if not isinstance(key, str) or len(key) > 128:
                        raise ValueError("INVALID_AGGREGATE_FIELDS")
                    bounded(child, depth + 1)
            elif isinstance(value, list):
                if len(value) > 128:
                    raise ValueError("AGGREGATE_COMPLEXITY_LIMIT")
                for child in value:
                    bounded(child, depth + 1)

        bounded(self.root)
        if self.root.get("status") == "SYNTHETIC_DIAGNOSTIC":
            # Compatibility for metric-free legacy diagnostics; never accepts data maps.
            _evaluation_field(self.root, "diagnostic")
        elif self.root.get("schema_version") == "simulation.evaluation.v1":
            _evaluation_field(self.root, "e0")
            if self.root["status"] != "SYNTHETIC_ENGINEERING_MEASURED" or (
                self.root["origin"] != "SYNTHETIC"
                or self.root["authority"] != "ENGINEERING_FIXTURE_ONLY"
                or len(self.root["freeze_receipt_sha256"]) != 2
                or len(set(self.root["freeze_receipt_sha256"])) != 2
            ):
                raise ValueError("INVALID_AGGREGATE_SCHEMA")
        else:
            _evaluation_map(self.root, _MODES, "e1", complete=True)
            for row in self.root.values():
                if row["schema_version"] != "local.camera.evaluation.v1" or (
                    row["status"] != "E1_SYNTHETIC_PILOT_MEASURED"
                    or row["origin"] != "SYNTHETIC"
                    or row["split"] not in {"development", "test"}
                ):
                    raise ValueError("INVALID_AGGREGATE_SCHEMA")
        return self


def _evaluation_pairs(pairs: list[tuple[str, Any]]) -> Json:
    result: Json = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_AGGREGATE_FIELD")
        result[key] = value
    return result


def _invalid_evaluation_constant(_: str) -> None:
    raise ValueError("NONFINITE_AGGREGATE_VALUE")


def _polygon(bounds: Sequence[float], z: float = 0.0) -> Json:
    x0, y0, x1, y1 = bounds
    return {"type": "polygon", "points": [[x0, y0, z], [x1, y0, z],
                                           [x1, y1, z], [x0, y1, z]]}


def _camera(camera: CameraEntry) -> Json:
    """Affine-only sources have no recoverable physical camera pose."""
    calibration = camera.calibration
    if calibration is not None:
        matrix = calibration.camera_to_world
        position: list[float] | None = [matrix[i][3] for i in range(3)]
        props = {"calibration_kind": "PINHOLE", "position": position,
                 "camera_to_world": [list(row) for row in matrix],
                 "fx": calibration.fx, "fy": calibration.fy,
                 "cx": calibration.cx, "cy": calibration.cy,
                 "width": calibration.width, "height": calibration.height,
                 "convention": calibration.convention}
    elif camera.affine_calibration is not None:
        affine = camera.affine_calibration
        position = None
        props = {"calibration_kind": affine.calibration_kind, "position": None,
                 "ground_to_pixel": [list(row) for row in affine.ground_to_pixel],
                 "plane_z_m": affine.plane_z_m, "width": affine.width,
                 "height": affine.height, "physical_pose_status": "UNKNOWN"}
    else:
        position = None
        props = {"calibration_kind": "UNAVAILABLE", "position": None,
                 "physical_pose_status": "UNKNOWN"}
    return {"camera_id": camera.camera_id, "camera_ref": camera.camera_ref,
            "label": camera.camera_id, "position": position,
            "coverage_status": camera.coverage_status,
            "region_ids": list(camera.region_ids), "authority": camera.authority,
            "calibration_sha256": camera.calibration_sha256, "properties": props}


def baseline_objects(context: SyntheticStaticContext, cameras: Sequence[CameraEntry],
                     behavior: BehaviorConfig | None = None) -> list[Json]:
    """Selectable geometry is drawn only from validated static source authority."""
    z = context.ground_plane.point[2]
    objects: list[Json] = [{
        "object_id": "walkable:" + context.ground_plane.plane_id, "kind": "WALKABLE",
        "label": "Configured walkable plane", "semantic": "WALKABLE",
        "geometry": _polygon(context.walkable_bounds_xy_m, z),
        "properties": {"floor_id": context.ground_plane.floor_id, "plane_z_m": z},
        "editable_fields": ["label", "semantic", "geometry", "properties"],
        "authority": "SYNTHETIC_CONFIG",
    }]
    for region in context.regions:
        objects.append({
            "object_id": "region:" + region.region_id, "kind": "REGION",
            "label": region.region_id, "semantic": "REGION",
            "geometry": _polygon(region.bounds_xy_m, z),
            "properties": {"region_id": region.region_id, "floor_id": region.floor_id},
            "editable_fields": ["label", "semantic", "geometry", "properties"],
            "authority": "SYNTHETIC_CONFIG",
        })
    if behavior is not None:
        for portal in behavior.portals:
            objects.append({
                "object_id": "portal:" + portal.portal_id, "kind": "PORTAL",
                "label": portal.portal_id, "semantic": "DOOR",
                "geometry": {"type": "line", "points": [[x, y, z]
                             for x, y in portal.line_xy_m]},
                "properties": {"inside_region_id": portal.inside_region_id,
                               "outside_region_id": portal.outside_region_id,
                               "enter_normal_xy": list(portal.enter_normal_xy)},
                "editable_fields": ["label", "semantic", "geometry", "properties"],
                "authority": behavior.authority,
            })
    for entry in cameras:
        camera = _camera(entry)
        objects.append({
            "object_id": "camera:" + entry.camera_id, "kind": "CAMERA",
            "label": entry.camera_id, "semantic": "CAMERA",
            "geometry": {"type": "point", "points": [] if camera["position"] is None
                         else [camera["position"]]},
            "properties": camera["properties"],
            "editable_fields": ["label", "properties"] if camera["position"] is None
                               else ["label", "geometry", "properties"],
            "authority": entry.authority,
        })
    return objects


class SceneAdapter:
    """A common desktop view over one immutable model/run with indexed access."""

    def __init__(self, *, scene_id: str, label: str, description: str,
                 service: LocalPilotService, context: SyntheticStaticContext,
                 evidence_level: str, evaluation_path: Path | None = None,
                 behavior: BehaviorConfig | None = None,
                 evaluation_config_hash: str | None = None,
                 evaluation_freeze_hashes: Mapping[str, str] | None = None,
                 evaluation_content_sha256: str | None = None) -> None:
        if (context.source_sha256 != service.scope.source_sha256
                or context.context_sha256 != service.scope.spatial_context_sha256):
            raise ValueError("SCENE_SOURCE_MISMATCH")
        self.scene_id, self.label, self.description = scene_id, label, description
        self.source_hash = service.scope.source_sha256
        self.model_revision = service.scope.model_revision
        self.run_id = service.scope.run_id
        self.service = service
        self._evaluation_path = evaluation_path
        self._evaluation_config_hash = evaluation_config_hash or service.guard.binding.config_sha256
        self._evaluation_freeze_hashes = dict(evaluation_freeze_hashes or {})
        if evaluation_content_sha256 is not None and re.fullmatch(
            r"[0-9a-f]{64}", evaluation_content_sha256
        ) is None:
            raise ValueError("INVALID_EVALUATION_CONTENT_CERTIFICATE")
        binding = service.guard.binding
        self._evaluation_content_sha256 = evaluation_content_sha256 or _CERTIFIED_EVALUATIONS.get(
            (binding.model_id, self.run_id, binding.dataset_sha256, self._evaluation_config_hash)
        )
        self._cameras = {camera.camera_id: camera for camera in service.cameras.values()}
        self._frame_buckets: dict[str, tuple[MediaFrame, ...]] = {}
        self._frame_times: dict[str, tuple[float, ...]] = {}
        self._frame_steps: dict[str, float] = {}
        for camera_id in self._cameras:
            frames = tuple(sorted((f for f in service.frames.values()
                                   if f.camera_id == camera_id), key=lambda f: f.timestamp))
            self._frame_buckets[camera_id] = frames
            self._frame_times[camera_id] = tuple(f.timestamp for f in frames)
            differences = [b.timestamp - a.timestamp
                           for a, b in zip(frames, frames[1:], strict=False)
                           if b.timestamp > a.timestamp]
            self._frame_steps[camera_id] = min(differences, default=0.0)
        times = [f.timestamp for f in service.frames.values()]
        model = next(m for m in service.store.registry.models if m.scope == service.scope)
        self._snapshot: Json = {
            "scene_id": scene_id, "label": label, "description": description,
            "model_id": service.scope.model_id, "model_revision": self.model_revision,
            "run_id": self.run_id, "source_hash": self.source_hash,
            "source_ref": service.guard.binding.source_ref,
            "config_sha256": service.guard.binding.config_sha256,
            "registry_sha256": service.store.registry.sha256,
            "freeze_ref": service.context().get("freeze_ref"),
            "clock": model.clock.model_dump(mode="json"),
            "coordinates": model.coordinates.model_dump(mode="json"),
            "evidence_level": evidence_level, "origin": "SYNTHETIC",
            "authority": "CONFIGURED_ENGINEERING_ONLY", "formal_phase1_acceptance": False,
            "capabilities": {
                "images": bool(times), "video": False, "local_3d": True,
                "camera_pose": all(c.calibration is not None for c in self._cameras.values()),
                "events": bool(service.events), "scene_review": True, "result_review": True,
                "evaluation": evaluation_path is not None and evaluation_path.is_file(),
                "inference_execution": False,
            },
            "bounds": list(context.walkable_bounds_xy_m),
            "time_range": [min(times), max(times)] if times else [0, 0],
            "cameras": [_camera(c) for c in self._cameras.values()],
            "objects": baseline_objects(context, tuple(self._cameras.values()), behavior),
            "counts": {"cameras": len(self._cameras), "frames": len(times),
                       "observations": len(service.observations), "events": len(service.events)},
            "limitations": ["Synthetic configured scene; provisional identities and events.",
                            "Reviewed annotations are versioned overlays; frozen outputs retain "
                            "their original config and require an explicit rerun after edits."],
        }

    def summary(self) -> Json:
        return copy.deepcopy({key: value for key, value in self._snapshot.items()
                              if key not in {"objects", "cameras"}})

    def with_display_identity(self, scene_id: str, label: str, description: str) -> SceneAdapter:
        """Server catalog aliases change display metadata, never the frozen source scope."""
        scene = copy.copy(self)
        scene.scene_id, scene.label, scene.description = scene_id, label, description
        scene._snapshot = copy.deepcopy(self._snapshot)
        scene._snapshot.update({"scene_id": scene_id, "label": label, "description": description})
        return scene

    def snapshot(self) -> Json:
        return copy.deepcopy(self._snapshot)

    def query(self, camera_id: str, start: float, end: float) -> Json:
        camera = self._cameras.get(camera_id)
        if camera is None:
            raise ValueError("CAMERA_SCOPE_DENIED")
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
            raise ValueError("INVALID_TIME_RANGE")
        request = {"session_ref": self.service.guard.session_ref,
                   "camera_ref": camera.camera_ref, "time_range": [start, end]}
        events = self.service.call("query_events", request)
        observations = self.service.call("query_observations", request)
        receipts = [events["retrieval"], observations["retrieval"]]
        totals = {key: sum(receipt[key] for receipt in receipts)
                  for key in ("records_read", "index_entries_touched", "frames_read", "bytes_read")}
        return copy.deepcopy({
            "events": events["items"], "observations": observations["items"],
            "retrieval": {**totals, "events": events["retrieval"],
                          "observations": observations["retrieval"],
                          "truncated": any(receipt["truncated"] for receipt in receipts),
                          "time_range": [start, end], "import_built_index": True,
                          "global_scan": False}})

    def event(self, ref: str) -> Json:
        return copy.deepcopy(self.service.call("get_event_detail", {
            "session_ref": self.service.guard.session_ref, "event_ref": ref}))

    def media(self, ref: str) -> tuple[str, bytes]:
        frame = self.service.frames.get(ref)
        if frame is None:
            raise ValueError("MEDIA_SCOPE_DENIED")
        return frame.media_type, self.service.store.media_bytes(self.service.scope, ref)

    def frames(self, camera_ids: Sequence[str], timestamp: float) -> Json:
        if not math.isfinite(timestamp) or timestamp < 0 or len(camera_ids) > 8:
            raise ValueError("INVALID_FRAME_WINDOW")
        if len(set(camera_ids)) != len(camera_ids) or any(c not in self._cameras
                                                         for c in camera_ids):
            raise ValueError("CAMERA_SCOPE_DENIED")
        result = []
        for camera_id in camera_ids:
            times = self._frame_times[camera_id]
            selected: MediaFrame | None = None
            if times and times[0] <= timestamp <= times[-1]:
                i = bisect_left(times, timestamp)
                nearby = [j for j in (i - 1, i) if 0 <= j < len(times)]
                best = min(nearby, key=lambda j: (abs(times[j] - timestamp), times[j]))
                if abs(times[best] - timestamp) <= self._frame_steps[camera_id] * 0.51:
                    selected = self._frame_buckets[camera_id][best]
            result.append({"camera_id": camera_id, "requested_timestamp": timestamp,
                           "timestamp": None if selected is None else selected.timestamp,
                           "media_ref": None if selected is None else selected.media_ref,
                           "status": "MISSING" if selected is None else
                           "EXACT" if selected.timestamp == timestamp else "NEAREST_AVAILABLE",
                           "time_offset_s": None if selected is None else
                           selected.timestamp - timestamp})
        return {"frames": result, "retrieval": {"camera_lookups": len(camera_ids),
                                                "frames_read": 0, "bytes_read": 0}}

    def evaluation(self) -> Json:
        """Return only certified, bounded aggregates; never truth or free-form metadata."""
        try:
            if self._evaluation_path is None or not self._evaluation_path.is_file():
                return {"status": "UNAVAILABLE", "reason": "NO_PREEXISTING_EVALUATION"}
            if self._evaluation_path.is_symlink() or (
                self._evaluation_path.name == "ground_truth.json"
            ):
                return {"status": "UNAVAILABLE", "reason": "EVALUATION_REFERENCE_DENIED"}
        except OSError:
            return {"status": "UNAVAILABLE", "reason": "INVALID_EVALUATION_SUMMARY"}
        try:
            # Bound the read itself, not only the already allocated parsed result.
            with self._evaluation_path.open("rb") as stream:
                payload = stream.read(MAX_EVALUATION_BYTES + 1)
            if len(payload) > MAX_EVALUATION_BYTES:
                return {"status": "UNAVAILABLE", "reason": "EVALUATION_PAYLOAD_TOO_LARGE"}
            parsed = json.loads(payload, object_pairs_hook=_evaluation_pairs,
                                parse_constant=_invalid_evaluation_constant)
            value = AggregateEvaluationDTO.model_validate(parsed).root
        except (OSError, ValueError, RecursionError):
            return {"status": "UNAVAILABLE", "reason": "INVALID_EVALUATION_SUMMARY"}
        rows = {"aggregate": value} if "run_id" in value else value
        binding = self.service.guard.binding
        valid = bool(rows)
        if self._evaluation_freeze_hashes and "aggregate" not in rows:
            if set(rows) != set(self._evaluation_freeze_hashes):
                return {"status": "STALE", "reason": "EVALUATION_BINDING_MISMATCH"}
        for mode, row in rows.items():
            if not isinstance(row, dict) or row.get("run_id") != self.run_id or (
                row.get("model_id") != binding.model_id
                or row.get("config_sha256") != self._evaluation_config_hash
                or row.get("dataset_sha256") != binding.dataset_sha256
            ):
                valid = False
                break
            if self._evaluation_freeze_hashes:
                if mode == "aggregate":
                    hashes = row.get("freeze_receipt_sha256")
                    valid = False
                    if isinstance(hashes, list) and all(isinstance(h, str) for h in hashes):
                        valid = set(hashes) == set(self._evaluation_freeze_hashes.values())
                else:
                    valid = row.get("freeze_sha256") == self._evaluation_freeze_hashes.get(mode)
                if not valid:
                    break
        if not valid:
            return {"status": "STALE", "reason": "EVALUATION_BINDING_MISMATCH"}
        if self._evaluation_content_sha256 is None:
            if value.get("status") != "SYNTHETIC_DIAGNOSTIC":
                return {"status": "UNAVAILABLE",
                        "reason": "EVALUATION_CONTENT_CERTIFICATE_MISSING"}
        elif digest(value) != self._evaluation_content_sha256:
            return {"status": "STALE", "reason": "EVALUATION_CONTENT_HASH_MISMATCH"}
        return value


def load_local_camera(root: Path) -> SceneAdapter:
    """Reuse the verified E1 checkpoint; opening the scene never generates data."""
    from amidst.engineering.local_pilot import _load, load_services

    services = load_services(root)
    service = next(s for s in services
                   if s.guard.binding.observation_mode == "photos_plus_observations")
    package, _, _, _ = _load(root)
    behavior = BehaviorConfig.model_validate_json((root / "behavior_config.json").read_bytes())
    return SceneAdapter(scene_id="local-camera", label="局部多鏡頭研究場景",
                        description="E1 · 四鏡頭透視 RGB、門口與轉角事件研究",
                        service=service, context=package.context,
                        evidence_level="E1_CONFIGURED_PINHOLE_RGB", behavior=behavior,
                        evaluation_path=root / "evaluation.json",
                        evaluation_config_hash=package.config_sha256,
                        evaluation_freeze_hashes={
                            s.guard.binding.observation_mode:
                            str(s.context()["freeze_ref"]).removeprefix("freeze-")
                            for s in services})


def load_local_camera_accuracy_v2(root: Path) -> SceneAdapter:
    """A distinct frozen experiment over original E1 RGB/static context, never GT."""
    from amidst.research_accuracy.adapter import load_service
    from amidst.research_accuracy.run import VERSION as accuracy_version
    from amidst.research_accuracy.run import load

    package, registry, manifest, _ = load(root)
    service = load_service(root, variant="end_to_end", mode="photos_plus_observations",
                           input_stage=False)
    # This locator is owned by the verified server-side manifest, not a request.
    source = Path(manifest["source_locator"]).resolve()
    original = json.loads((source / "manifest.json").read_bytes())
    behavior = BehaviorConfig.model_validate_json((source / "behavior_config.json").read_bytes())
    model = next(m for m in registry.models if m.scope == service.scope)
    support_states = ("SUPPORTED", "UNKNOWN", "GAP_ALTERNATIVES")
    if (
        manifest["version"] != accuracy_version
        or manifest["unit"] != "METRES_SYNTHETIC_SECONDS"
        or not isinstance(manifest["experiment_id"], str)
        or re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", manifest["experiment_id"]) is None
        or digest(original) != manifest["source_manifest_sha256"]
        or digest(behavior) != original["behavior_config_sha256"]
        or service.store.registry.sha256 != registry.sha256
        or service.guard.stage != "RESULTS"
        or service.guard.binding.registry_version != accuracy_version
        or service.guard.binding.observation_mode != "photos_plus_observations"
        or model.coordinates.native_units != "METRES"
        or model.coordinates.metres_per_unit != 1
        or model.coordinates.normalization_policy != "IDENTITY"
        or any(c.calibration is None or c.scope != service.scope
               for c in service.cameras.values())
        or any(e.get("support_state") not in support_states for e in service.events.values())
    ):
        raise ValueError("ACCURACY_SCENE_BINDING_MISMATCH")
    scene = SceneAdapter(
        scene_id="local-camera-accuracy-v2", label="局部鏡頭精度研究 v2",
        description="E1 同源 RGB · accuracy v2 end_to_end；SUPPORTED／UNKNOWN／盲區替代分列",
        service=service, context=package.context, evidence_level="E1_FROZEN_ACCURACY_V2_RGB",
        behavior=behavior,
    )
    # No E1 content certificate is reused for the new aggregate schema. Human
    # evaluation stays unavailable until it has an independent DTO/certificate.
    scene._snapshot.update({
        "experiment_id": manifest["experiment_id"], "experiment_version": accuracy_version,
        "experiment_namespace": opaque_ref("experiment", manifest["experiment_id"],
                                           "end_to_end", "photos_plus_observations",
                                           service.guard.binding.config_sha256),
        "source_run_id": manifest["source_run_id"], "variant": "end_to_end",
        "observation_mode": "photos_plus_observations", "decision_stage": "RESULTS",
        "research_manifest_sha256": digest(manifest),
        "experiment_config_sha256": manifest["config_sha256"],
        "explicit_support_states": list(support_states),
        "support_state_counts": {state: sum(e["support_state"] == state
                                           for e in service.events.values())
                                 for state in support_states},
        "evaluation_status": "UNAVAILABLE_UNCERTIFIED_ACCURACY_V2_AGGREGATE",
        "limitations": [
            "Same E1 synthetic RGB/static context; source run ID is retained.",
            "Experiment/variant/config/freeze and event/track refs are separately bound.",
            "UNKNOWN is not supported evidence; all GAP alternatives are retained.",
            "Changed v2 tracking population is not the original fixed v1 population.",
            "No formal school, real-camera or sealed-holdout acceptance.",
        ],
    })
    return scene


def load_synthetic_lab(root: Path) -> SceneAdapter:
    """Normalize E0 frozen results once; subsequent queries use the same interval index."""
    from amidst.engineering.run import load_facades

    facades = load_facades(root)
    facade = next(f for f in facades
                  if f.guard.binding.observation_mode == "photos_plus_observations")
    context = SyntheticStaticContext.model_validate_json(
        (root / "static_context.json").read_bytes())
    observations = []
    for original in facade.observations:
        row = original.model_dump(mode="json")
        row["camera_ids"] = [row.pop("camera_id")]
        row["camera_refs"] = [row.pop("camera_ref")]
        row["projected_path"] = row.pop("projected_positions")
        observations.append(row)
    by_observation = {o["observation_ref"]: o for o in observations}
    gaps = {g.event.event_id: g.event for g in facade.snapshot.gaps}
    frames = {f.media_ref: f for f in facade.frames}
    events = []
    for original_event in facade.events:
        row = original_event.model_dump(mode="json")
        row["camera_ids"] = list(dict.fromkeys(row["camera_ids"]))
        row["camera_refs"] = list(dict.fromkeys(row["camera_refs"]))
        gap = gaps.get(original_event.canonical_event_id or "")
        row["evidence_state"] = "INFERRED_GAP" if gap else "PROJECTED"
        row["candidates"] = [] if gap is None else [c.model_dump(mode="json")
                                                   for c in gap.candidates]
        row["trajectories"] = [] if gap is None else [t.model_dump(mode="json")
                                                     for t in gap.trajectories]
        row["projected_path"] = [p for ref in original_event.observation_refs
                                 for p in by_observation[ref]["projected_path"]]
        # Keep the registered source order; the UI can request a small evidence subset.
        row["source_frames"] = [{"frame_ref": ref, "camera_id": frames[ref].camera_id,
                                 "timestamp": frames[ref].timestamp}
                                for ref in original_event.media_refs]
        row["status"] = original_event.termination_reason
        row["support"] = []
        row["conflicts"] = []
        row["alternatives"] = [original_event.uncertainty]
        events.append(row)
    model = next(m for m in facade.store.registry.models if m.scope == facade.scope)
    topology = ScopedTopology(
        scope=facade.scope, camera_ids=tuple(c.camera_id for c in facade.cameras),
        camera_links=tuple(CameraLink(from_camera_id=a, to_camera_id=b)
                           for a, b in context.allowed_camera_pairs),
        camera_regions=tuple(CameraRegions(camera_id=c.camera_id, region_ids=c.region_ids)
                             for c in facade.cameras),
        topology_complete=False, clock_mapping_sha256=model.clock.mapping_sha256,
    )
    service = LocalPilotService(facade.store, facade.scope, facade.guard,
                                tuple(observations), tuple(events), topology)
    return SceneAdapter(scene_id="synthetic-lab", label="雙鏡頭基礎實驗室",
                        description="E0 · 仿射地面投影與盲區候選診斷；無實體鏡頭姿態",
                        service=service, context=context, evidence_level="E0_AFFINE_RGB_FIXTURE",
                        evaluation_path=root / "evaluation" / "summary.json",
                        evaluation_freeze_hashes={
                            f.guard.binding.observation_mode:
                            str(f.context()["freeze_ref"]).removeprefix("freeze-")
                            for f in facades})


def load_catalog(repo: Path, overrides: Mapping[str, Path] | None = None,
                 *, manifest_path: Path | None = None
                 ) -> dict[str, SceneAdapter]:
    """Resolve a fixed local manifest allowlist. Missing assets stay unavailable.

    Explicit overrides are server configuration, never browser-supplied paths.
    Invalid existing freezes fail closed; no fallback or automatic regeneration.
    """
    repo = repo.resolve()
    default_path = repo / "configs/engineering/workbench_v1.json"
    selected_path = manifest_path if manifest_path is not None else default_path
    if not selected_path.is_absolute():
        selected_path = repo / selected_path
    if selected_path.is_file():
        try:
            manifest = json.loads(selected_path.read_text())
        except (OSError, ValueError) as error:
            raise ValueError("INVALID_SCENE_CATALOG") from error
    elif manifest_path is not None:
        raise ValueError("SCENE_CATALOG_UNAVAILABLE")
    else:
        # A repository without a local manifest still has the two documented defaults.
        manifest = {"schema_version": "workbench.catalog.v1", "scenes": [
            {"scene_id": "local-camera", "adapter": "local_camera",
             "checkpoint": "data/engineering/local_run/local_camera_v1/test/checkpoints/final",
             "label": "局部多鏡頭研究場景",
             "description": "E1 · 四鏡頭透視 RGB、門口與轉角事件研究"},
            {"scene_id": "synthetic-lab", "adapter": "synthetic_lab",
             "checkpoint": "data/engineering/local_run/simulation_v2",
             "label": "雙鏡頭基礎實驗室", "description": "E0 · 仿射地面投影與盲區候選診斷"},
        ]}
    entries = _catalog_entries(repo, manifest)
    if overrides is not None:
        if not set(overrides) <= {entry["scene_id"] for entry in entries}:
            raise ValueError("UNKNOWN_SCENE_ADAPTER")
    loaders = {"local_camera": load_local_camera, "synthetic_lab": load_synthetic_lab,
               "local_camera_accuracy_v2": load_local_camera_accuracy_v2}
    catalog = {}
    for entry in entries:
        scene_id = entry["scene_id"]
        root = (overrides or {}).get(scene_id, repo / entry["checkpoint"])
        if not root.exists():
            continue
        try:
            scene = loaders[entry["adapter"]](root.resolve())
            catalog[scene_id] = scene.with_display_identity(
                scene_id, entry["label"], entry["description"])
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
            raise ValueError("SCENE_SOURCE_UNAVAILABLE:" + scene_id) from error
    return catalog


def _catalog_entries(repo: Path, manifest: object) -> list[dict[str, str]]:
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "scenes"}:
        raise ValueError("INVALID_SCENE_CATALOG")
    if manifest["schema_version"] != "workbench.catalog.v1" or not isinstance(
        manifest["scenes"], list
    ):
        raise ValueError("INVALID_SCENE_CATALOG")
    entries: list[dict[str, str]] = []
    known: set[str] = set()
    for row in manifest["scenes"]:
        if not isinstance(row, dict) or set(row) != {
            "scene_id", "adapter", "checkpoint", "label", "description"
        } or any(not isinstance(value, str) or not value.strip() for value in row.values()):
            raise ValueError("INVALID_SCENE_CATALOG")
        scene_id = row["scene_id"]
        if not scene_id.isascii() or not all(c.isalnum() or c in "-_" for c in scene_id):
            raise ValueError("INVALID_SCENE_ID")
        if scene_id in known:
            raise ValueError("DUPLICATE_SCENE_ID")
        known.add(scene_id)
        if row["adapter"] not in {"local_camera", "synthetic_lab", "local_camera_accuracy_v2"}:
            raise ValueError("UNKNOWN_SCENE_ADAPTER")
        checkpoint = PurePosixPath(row["checkpoint"])
        if checkpoint.is_absolute() or ".." in checkpoint.parts or "\\" in row["checkpoint"]:
            raise ValueError("INVALID_SCENE_CHECKPOINT")
        try:
            (repo / row["checkpoint"]).resolve().relative_to(repo)
        except (ValueError, OSError) as error:
            raise ValueError("INVALID_SCENE_CHECKPOINT") from error
        entries.append(dict(row))
    return entries
