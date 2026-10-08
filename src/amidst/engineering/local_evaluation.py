"""Post-freeze, offline E1 pilot evaluation; this module alone reads local GT.

The inventory is independently enumerated here, never supplied to inference.
Identity labels are evaluation-only bounded pixel matches, including explicit
unresolved/impure segments. Metrics describe hypotheses, not confirmed identities.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict, deque
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any

from amidst.domain.common import DomainModel
from amidst.engineering.access import FreezeReceipt, digest
from amidst.engineering.local_association import InferenceBundle
from amidst.engineering.local_behavior import LocalBehaviorBundle, LocalBehaviorEvent
from amidst.engineering.perception import PerceptionResult, PixelModel
from amidst.engineering.research_scene import ResearchPackage

CONTACT_TOLERANCE_PX = 24.0
SEGMENT_PURITY = 0.70
BEHAVIOR_TIME_TOLERANCE_S = 1.2
# Frozen reference eligibility is independent of any runtime receipt/budget.
REFERENCE_RETRIEVAL_WINDOW_S = 12.0
REFERENCE_RETRIEVAL_MAX_HOPS = 3


def evaluator_policy() -> dict[str, object]:
    """The declared pre-test evaluation rules; no GT-dependent tuning state."""
    return {
        "schema_version": "local.camera.evaluator-policy.v1",
        "contact_tolerance_px": CONTACT_TOLERANCE_PX,
        "minimum_visible_pixels": 28,
        "minimum_bbox_iou": 0.10,
        "ambiguous_assignment_score_margin": 0.08,
        "segment_known_identity_purity": SEGMENT_PURITY,
        "behavior_time_tolerance_s": BEHAVIOR_TIME_TOLERANCE_S,
        "reference_retrieval_window_s": REFERENCE_RETRIEVAL_WINDOW_S,
        "reference_retrieval_max_hops": REFERENCE_RETRIEVAL_MAX_HOPS,
        "true_next_reference": "Conditional on GT-labeled produced segments; earliest later "
        "nonoverlap physically feasible same-actor segments; retain all earliest-start ties",
        "true_next_uses_retrieval_window_hop_or_budget": False,
        "global_identity_metrics": "N/A: no global identity solver",
    }


def _verify_behavior_inputs(
    events: Sequence[DomainModel], events_sha256: str | None, inference: InferenceBundle,
    perception: PerceptionResult, bundle: LocalBehaviorBundle | None,
) -> tuple[LocalBehaviorEvent, ...]:
    """Validate same-run behavior lineage before the evaluator opens any truth."""
    validated = tuple(LocalBehaviorEvent.model_validate(event.model_dump()) for event in events)
    if events and not events_sha256:
        raise ValueError("behavior freeze hash is required for supplied events")
    if events_sha256 and digest([event.model_dump(mode="json") for event in validated]) != (
        events_sha256
    ):
        raise ValueError("behavior freeze mismatch")
    if bundle is not None:
        bundle = LocalBehaviorBundle.model_validate(bundle.model_dump())
        if (bundle.scope != inference.scope or bundle.events != validated
                or bundle.inference_sha256 != digest(inference)
                or bundle.input_manifest_sha256 != inference.input_manifest_sha256
                or bundle.producer_sha256 != perception.producer_sha256
                or bundle.track_state_sha256 != digest([
                    track.model_dump(mode="json") for track in perception.tracks])):
            raise ValueError("behavior bundle inference/run binding mismatch")
    mappings = {row.segment_id: row for row in inference.local_record_maps}
    projected = {row.observation_id: row for row in inference.projected_measurements}
    associations = {row.hypothesis_id: row for row in inference.association_hypotheses}
    gaps = {row.event.event_id: row for row in inference.snapshot.gaps}
    configs = {(event.config_version, event.config_sha256, event.rule_version)
               for event in validated}
    if len(configs) > 1:
        raise ValueError("behavior event rule/config binding mismatch")
    for event in validated:
        if event.scope != inference.scope:
            raise ValueError("behavior event scope/run mismatch")
        if (not event.segment_ids or any(identity not in mappings for identity in event.segment_ids)
                or tuple(mappings[identity].local_track_id for identity in event.segment_ids)
                != event.local_track_ids
                or bundle is not None and event.config_sha256 != bundle.config_sha256):
            raise ValueError("behavior event segment/track/config membership mismatch")
        pixels = {identity for segment_id in event.segment_ids
                  for identity in mappings[segment_id].original_pixel_observation_ids}
        for state in event.association_states:
            hypothesis = associations.get(state.hypothesis_id)
            if (hypothesis is None or not set(hypothesis.segment_ids) & set(event.segment_ids)
                    or (state.kind, state.status, state.reason) != (
                        hypothesis.kind, hypothesis.status, hypothesis.reason)):
                raise ValueError("behavior association membership/state mismatch")
        for frame in event.source_frames:
            original = projected.get(frame.observation_id)
            if (original is None or frame.observation_id not in pixels or original.point is None
                    or original.status != "PROJECTED" or (
                        frame.frame_ref, frame.camera_id, frame.timestamp) != (
                            original.frame_ref, original.camera_id, original.timestamp)):
                raise ValueError("behavior source frame membership mismatch")
        for point in event.projected_path:
            original = projected.get(point.observation_id)
            if (original is None or point.observation_id not in pixels or original.point is None
                    or (point.local_track_id, point.camera_id, point.timestamp,
                        point.world_position, point.uncertainty_m) != (
                        original.local_track_id, original.camera_id, original.timestamp,
                        original.point.world_position, original.uncertainty_m)):
                raise ValueError("behavior projected evidence membership mismatch")
        if event.canonical_event_id is not None:
            gap = gaps.get(event.canonical_event_id)
            if (gap is None or event.candidates != gap.event.candidates
                    or event.trajectories != gap.event.trajectories
                    or event.time_range != gap.event.time_range
                    or event.termination_reason != str(gap.event.termination_reason)
                    or event.complete != gap.search_result.complete
                    or not any(associations[identity].event_id == event.canonical_event_id
                               and associations[identity].segment_ids == event.segment_ids
                               for identity in event.association_refs)):
                raise ValueError("behavior canonical gap binding mismatch")
    return validated


class ResearchAnnotation(PixelModel):
    actor_identity: str
    position_xyz_m: tuple[float, float, float]
    contact_uv: tuple[float, float] | None
    unoccluded_bbox_xyxy: tuple[float, float, float, float] | None
    visible_bbox_xyxy: tuple[int, int, int, int] | None
    in_configured_coverage: bool
    contact_inside_frame: bool
    visible_pixel_count: int


class ResearchTruthFrame(PixelModel):
    frame_ref: str
    camera_id: str
    timestamp: float
    render_annotations: tuple[ResearchAnnotation, ...]


class ResearchTruth(PixelModel):
    schema_version: str
    boundary: str
    model_id: str
    run_id: str
    split: str
    dataset_sha256: str
    config_sha256: str
    recipe: dict[str, Any]
    ground_truth: tuple[ResearchTruthFrame, ...]
    behavior_truth: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...]


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _iou(first: Sequence[float], second: Sequence[float]) -> float:
    x0, y0, x1, y1 = first
    a0, b0, a1, b1 = second
    intersection = max(0, min(x1, a1) - max(x0, a0)) * max(0, min(y1, b1) - max(y0, b0))
    union = (x1 - x0) * (y1 - y0) + (a1 - a0) * (b1 - b0) - intersection
    return intersection / union if union > 0 else 0.0


def _stats(values: Sequence[float]) -> dict[str, float | int | None]:
    return {"samples": len(values), "mean": math.fsum(values) / len(values) if values else None,
            "rms": math.sqrt(math.fsum(value * value for value in values) / len(values))
            if values else None, "maximum": max(values) if values else None}


def _labels(
    perception: PerceptionResult, inference: InferenceBundle, truth: ResearchTruth,
) -> tuple[
    dict[str, str | None], dict[str, str | None], dict[str, object], list[dict[str, object]],
]:
    frames = {row.frame_ref: row for row in truth.ground_truth}
    projections = {row.observation_id: row for row in inference.projected_measurements}
    measurement_labels: dict[str, str | None] = {}
    eligible_count = sum(annotation.visible_pixel_count >= 28
                         and annotation.contact_inside_frame
                         and annotation.in_configured_coverage
                         for frame in truth.ground_truth for annotation in frame.render_annotations)
    used_truth: set[tuple[str, str]] = set()
    contact_errors: list[float] = []
    ground_errors: list[float] = []
    details: list[dict[str, object]] = []
    for measurement in perception.measurements:
        frame = frames[measurement.frame_ref]
        candidates = []
        for annotation in frame.render_annotations:
            if not (annotation.visible_pixel_count >= 28 and annotation.in_configured_coverage
                    and annotation.contact_inside_frame and annotation.contact_uv
                    and annotation.visible_bbox_xyxy):
                continue
            distance = math.dist(measurement.contact_pixel, annotation.contact_uv)
            overlap = _iou(measurement.bbox_xyxy, annotation.visible_bbox_xyxy)
            if distance <= CONTACT_TOLERANCE_PX and overlap >= 0.10:
                candidates.append((overlap - distance / 240, distance, annotation))
        candidates.sort(key=lambda item: (-item[0], item[1], item[2].actor_identity))
        best = candidates[0] if candidates else None
        ambiguous = len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.08
        label = best[2].actor_identity if best and not ambiguous else None
        measurement_labels[measurement.observation_id] = label
        if best is not None and label is not None:
            annotation = best[2]
            used_truth.add((measurement.frame_ref, label))
            contact_errors.append(best[1])
            projection = projections.get(measurement.observation_id)
            if projection and projection.point:
                ground_errors.append(math.dist(projection.point.world_position,
                                              annotation.position_xyz_m))
        details.append({"observation_id": measurement.observation_id,
                        "evaluation_only_actor": label, "ambiguous": ambiguous,
                        "candidate_actor_count": len(candidates)})
    segment_labels: dict[str, str | None] = {}
    impure_segments = 0
    unresolved_segments = 0
    for mapping in inference.local_record_maps:
        counts = Counter(measurement_labels[identity]
                         for identity in mapping.original_pixel_observation_ids
                         if measurement_labels[identity] is not None)
        known = sum(counts.values())
        winner, count = counts.most_common(1)[0] if counts else (None, 0)
        label = winner if known and count / known >= SEGMENT_PURITY else None
        segment_labels[mapping.segment_id] = label
        impure_segments += len(counts) > 1
        unresolved_segments += label is None
    switches = 0
    for track in perception.tracks:
        identities = [measurement_labels[identity] for identity in track.observation_ids
                      if measurement_labels[identity] is not None]
        switches += sum(first != last for first, last in
                        zip(identities, identities[1:], strict=False))
    labeled_count = sum(label is not None for label in measurement_labels.values())
    return measurement_labels, segment_labels, {
        "measurement_count": len(perception.measurements),
        "eligible_visible_actor_contacts": eligible_count,
        "bounded_labeled_measurements": labeled_count,
        "bounded_detection_precision": _ratio(len(used_truth), len(perception.measurements)),
        "one_to_one_visible_contact_recall": _ratio(len(used_truth), eligible_count),
        "unresolved_segment_count": unresolved_segments,
        "impure_segment_count": impure_segments,
        "within_local_track_id_switches": switches,
        "pixel_contact_error_px": _stats(contact_errors),
        "ground_contact_error_m": _stats(ground_errors),
        "assignment": "Evaluation-only IoU>=0.10 and contact<=24px; close alternatives unresolved",
        "segment_assignment": "Dominant known pixel identity purity>=0.70; unresolved retained",
        "IDF1": "N/A: no global identity trajectory assignment is produced",
    }, details


def _reachable(package: ResearchPackage, camera: str, hops: int) -> set[str]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for first, last in package.adjacency:
        adjacency[first].append(last)
    reached = {camera}
    queue = deque([(camera, 0)])
    while queue:
        current, depth = queue.popleft()
        if depth >= hops:
            continue
        for neighbor in adjacency[current]:
            if neighbor not in reached:
                reached.add(neighbor)
                queue.append((neighbor, depth + 1))
    return reached


def _inventory(
    package: ResearchPackage, inference: InferenceBundle,
) -> tuple[set[tuple[str, str]], set[tuple[str, str]], dict[str, str]]:
    """Full scope enumeration is deliberate evaluator-only reference work."""
    observations = {row.observation.observation_id: row.observation
                    for row in inference.snapshot.observations}
    mappings = {row.segment_id: row for row in inference.local_record_maps}
    record_maps = {row.segment_id: row.record_ref for row in inference.retrieval_record_maps}
    ordered = sorted(mappings, key=lambda identity: (
        observations[mappings[identity].canonical_observation_id].start_time,
        observations[mappings[identity].canonical_observation_id].end_time,
        record_maps[identity],
    ))
    complete_pool: set[tuple[str, str]] = set()
    physics_pool: set[tuple[str, str]] = set()
    kinds: dict[str, str] = {}
    for index, source in enumerate(ordered):
        first = observations[mappings[source].canonical_observation_id]
        reachable = _reachable(package, first.camera_id, REFERENCE_RETRIEVAL_MAX_HOPS)
        for target in ordered[index + 1:]:
            last = observations[mappings[target].canonical_observation_id]
            if last.camera_id not in reachable or last.start_time > (
                first.end_time + REFERENCE_RETRIEVAL_WINDOW_S
            ):
                continue
            pair = source, target
            complete_pool.add(pair)
            overlap = last.start_time <= first.end_time
            kind = "OVERLAPPING_VISIBILITY" if overlap else (
                "SAME_CAMERA_RECOVERY" if first.camera_id == last.camera_id else "CROSS_CAMERA_GAP")
            kinds["|".join(pair)] = kind
            if overlap:
                if first.camera_id == last.camera_id:
                    continue
                common = [(a, b) for a in first.projected_path for b in last.projected_path
                          if a.timestamp == b.timestamp]
                minimum = min((math.dist(a.world_position, b.world_position)
                               for a, b in common), default=math.inf)
                if minimum <= (
                    inference.policy.max_overlap_separation_m
                ):
                    physics_pool.add(pair)
            elif first.projected_path and last.projected_path:
                dt = last.start_time - first.end_time
                distance = math.dist(first.projected_path[-1].world_position,
                                     last.projected_path[0].world_position)
                if distance <= dt * inference.policy.max_speed_m_s + (
                    2 * inference.policy.projection_uncertainty_m
                ):
                    physics_pool.add(pair)
    return complete_pool, physics_pool, kinds


def _next_successors(
    package: ResearchPackage, inference: InferenceBundle, labels: dict[str, str | None],
) -> set[tuple[str, str]]:
    """Conditional true next produced-segment reference, with no retrieval limits.

    Unobserved actors and unresolved/impure segments are not represented here.
    Reachability uses the entire declared scoped topology; speed uses projected
    endpoints with the same explicit uncertainty bound. All earliest-start ties
    are retained. Window/hop/record budgets never remove reference successors.
    """
    observations = {row.observation.observation_id: row.observation
                    for row in inference.snapshot.observations}
    segments = {row.segment_id: observations[row.canonical_observation_id]
                for row in inference.local_record_maps}
    result: set[tuple[str, str]] = set()
    for source, first in segments.items():
        if labels[source] is None or not first.projected_path:
            continue
        reachable = _reachable(package, first.camera_id, len(package.cameras))
        candidates: list[tuple[float, str]] = []
        for target, last in segments.items():
            if (target == source or labels[target] != labels[source]
                    or last.camera_id not in reachable or not last.projected_path
                    or last.start_time <= first.start_time or last.start_time < first.end_time):
                continue
            duration = last.start_time - first.end_time
            distance = math.dist(first.projected_path[-1].world_position,
                                 last.projected_path[0].world_position)
            if distance <= duration * inference.policy.max_speed_m_s + (
                2 * inference.policy.projection_uncertainty_m
            ):
                candidates.append((last.start_time, target))
        if candidates:
            earliest = min(timestamp for timestamp, _ in candidates)
            result.update((source, target) for timestamp, target in candidates
                          if timestamp == earliest)
    return result


def _link_metrics(
    predicted: set[tuple[str, str]], truth: set[tuple[str, str]],
    labels: dict[str, str | None],
) -> dict[str, object]:
    resolved = {pair for pair in predicted
                if all(labels[identity] is not None for identity in pair)}
    correct = resolved & truth
    wrong_identity = {pair for pair in resolved if labels[pair[0]] != labels[pair[1]]}
    return {"predicted_link_count": len(predicted), "resolved_link_count": len(resolved),
            "true_link_count": len(truth), "true_positive": len(correct),
            "same_identity_eligible_pair_precision": _ratio(len(correct), len(resolved)),
            "same_identity_eligible_pair_recall": _ratio(len(correct), len(truth)),
            "pair_level_false_merge_count": len(wrong_identity),
            "pair_level_missed_link_count": len(truth - resolved),
            "global_false_merge_count": "N/A: no global identity solver",
            "global_false_split_count": "N/A: no global identity solver",
            "unresolved_link_count": len(predicted - resolved),
            "metric_family": "SAME_IDENTITY_PHYSICALLY_ELIGIBLE_PRODUCED_SEGMENT_PAIRS",
            "is_true_next_continuation_metric": False}


def _fixed_pool_ablations(
    inference: InferenceBundle, labels: dict[str, str | None],
    truth_pairs: set[tuple[str, str]],
) -> dict[str, object]:
    from amidst.engineering.local_association import rank_association_hypotheses

    results: dict[str, object] = {}
    for removed in (None, "SPACE", "TIME", "APPEARANCE"):
        # Ranking is pure and never changes the canonical Graph candidate order.
        ranked = rank_association_hypotheses(inference, removed_feature=removed)
        by_source: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for hypothesis in ranked:
            if len(hypothesis.segment_ids) != 2 or hypothesis.status == "INCOMPATIBLE":
                continue
            by_source[hypothesis.segment_ids[0]].append(tuple(hypothesis.segment_ids))  # type: ignore[arg-type]
        top1 = {pairs[0] for pairs in by_source.values() if pairs}
        metric = _link_metrics(top1, truth_pairs, labels)
        relevant_sources = {pair[0] for pair in truth_pairs}
        recall_at_k: dict[str, float | None] = {}
        for k in (1, 3, 5):
            hit = sum(any(pair in truth_pairs for pair in by_source.get(source, ())[:k])
                      for source in relevant_sources)
            recall_at_k[str(k)] = _ratio(hit, len(relevant_sources))
        metric["identity_candidate_recall_at_k"] = recall_at_k
        metric["eligible_query_count"] = len(relevant_sources)
        metric["candidate_pool_sha256"] = inference.association_pool_sha256
        metric["hard_physics_preserved"] = True
        metric["removed_feature"] = removed
        metric["scores_are_probabilities"] = False
        results["full" if removed is None else "without_" + removed.lower()] = metric
    return results


def _behavior(
    events: Sequence[DomainModel], events_sha256: str | None,
    truth: ResearchTruth, labels: dict[str, str | None], inference: InferenceBundle,
) -> dict[str, object]:
    if not events_sha256:
        return {"status": "N/A", "reason": "Behavior event freeze hash is unavailable"}
    if digest([event.model_dump(mode="json") for event in events]) != events_sha256:
        raise ValueError("behavior freeze mismatch")
    track_labels: dict[str, set[str]] = defaultdict(set)
    for mapping in inference.local_record_maps:
        if labels[mapping.segment_id] is not None:
            track_labels[mapping.local_track_id].add(str(labels[mapping.segment_id]))
    canonical = {"ENTER_DOOR": "ENTER", "EXIT_DOOR": "EXIT", "TURN_CORNER": "CORNER",
                 "POSSIBLE_LOITERING": "POSSIBLE_WANDERING",
                 "POSSIBLE_WANDERING": "POSSIBLE_WANDERING", "LOCAL_REVISIT": "POSSIBLE_WANDERING",
                 "ENTER": "ENTER", "EXIT": "EXIT", "CORNER": "CORNER", "DWELL": "DWELL"}
    expected = list(truth.behavior_truth)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        row = event.model_dump(mode="json")
        if row.get("evidence_state") == "INFERRED_GAP":
            groups["inferred_gap"].append(row)
            continue
        kind = canonical.get(row.get("kind", row.get("event_kind", "")))
        if kind is None:
            continue
        tracks = row.get("local_track_ids", ())
        identities = {identity for track in tracks for identity in track_labels.get(track, ())}
        row["evaluation_actor"] = next(iter(identities)) if len(identities) == 1 else None
        row["evaluation_kind"] = kind
        groups["visible_supported"].append(row)
    reports: dict[str, object] = {}
    for category in ("visible_supported",):
        predictions = groups[category]
        matches: set[int] = set()
        by_kind: dict[str, Counter[str]] = defaultdict(Counter)
        confusion: Counter[str] = Counter()
        errors: list[float] = []
        for row in predictions:
            kind = row["evaluation_kind"]
            interval = row.get("time_range", (0.0, 0.0))
            actor = row["evaluation_actor"]
            if actor is None:
                by_kind[kind]["unresolved"] += 1
                continue
            candidates = [(index, annotation) for index, annotation in enumerate(expected)
                          if annotation["actor_identity"] == actor and index not in matches
                          and interval[0] - BEHAVIOR_TIME_TOLERANCE_S <= annotation["timestamp"]
                          <= interval[1] + BEHAVIOR_TIME_TOLERANCE_S]
            exact = [(index, annotation) for index, annotation in candidates
                     if annotation["kind"] == kind]
            if exact:
                index, annotation = min(exact, key=lambda pair: abs(
                    pair[1]["timestamp"] - (interval[0] + interval[1]) / 2))
                matches.add(index)
                by_kind[kind]["true_positive"] += 1
                errors.append(abs(annotation["timestamp"] - (interval[0] + interval[1]) / 2))
                confusion[f"{annotation['kind']}->{kind}"] += 1
            else:
                by_kind[kind]["false_positive"] += 1
                other = candidates[0][1]["kind"] if candidates else "NONE"
                confusion[f"{other}->{kind}"] += 1
        all_kinds = {row["kind"] for row in expected} | set(by_kind)
        metrics = {}
        for kind in sorted(all_kinds):
            counts = by_kind[kind]
            gt_count = sum(row["kind"] == kind for row in expected)
            tp, fp = counts["true_positive"], counts["false_positive"]
            metrics[kind] = {"true_positive": tp, "false_positive": fp,
                             "false_negative": gt_count - tp, "unresolved": counts["unresolved"],
                             "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, gt_count)}
        reports[category] = {"per_kind": metrics, "confusion": dict(confusion),
                             "trigger_midpoint_error_s": _stats(errors),
                             "direction_error": "N/A: no calibrated direction-error reference",
                             "prediction_count": len(predictions)}
    # Canonical route/timing alternatives have no independently labeled blind
    # behavior population. Visible recipe events are not their false negatives.
    gap_events = groups["inferred_gap"]
    reports["inferred_gap"] = {
        "status": "N/A_UNLABELED_GAP_BEHAVIOR_ALTERNATIVES",
        "hypothesis_event_count": len(gap_events),
        "canonical_gap_event_count": len({row["canonical_event_id"] for row in gap_events}),
        "canonical_candidate_count": sum(len(row.get("candidates", ())) for row in gap_events),
        "canonical_timing_hypothesis_count": sum(len(row.get("trajectories", ()))
                                                for row in gap_events),
        "per_kind": {kind: {"precision": "N/A", "recall": "N/A",
                            "false_positive": "N/A", "false_negative": "N/A"}
                     for kind in sorted({row["kind"] for row in expected})},
        "confusion": "N/A: no independently labeled blind-gap behavior population",
        "trigger_error_s": "N/A",
        "direction_error": "N/A",
        "uncertainty": "Canonical route/timing alternatives preserve ambiguity; "
        "they do not constitute visible event detections or independently labeled gap behavior.",
    }
    return {"status": "POST_FREEZE_SYNTHETIC_MEASURED", "groups": reports,
            "time_tolerance_s": BEHAVIOR_TIME_TOLERANCE_S,
            "expected_all_recipe_events": len(expected),
            "note": "Recipe labels operationalize movement; possible wandering is not intent."}


def evaluate_local_pilot(
    package: ResearchPackage, perception: PerceptionResult, inference: InferenceBundle, *,
    receipt: FreezeReceipt, events: Sequence[DomainModel] = (), events_sha256: str | None = None,
    behavior_bundle: LocalBehaviorBundle | None = None,
) -> dict[str, object]:
    """Verify RGB/config/run/inference freeze first, then and only then read test GT."""
    binding = receipt.binding
    if not receipt.verify(binding, inference, perception.model_dump(mode="json")) or (
        binding.model_id != package.model_id or binding.run_id != package.run_id
        or binding.place_id != package.scope.place_id
        or binding.model_revision != package.scope.model_revision
        or binding.clock_id != package.scope.clock_id
        or binding.source_ref != package.scope.source_ref
        or binding.spatial_context_id != package.scope.spatial_context_id
        or binding.producer_sha256 != perception.producer_sha256
        or binding.dataset_sha256 != package.dataset_sha256
        or perception.input_manifest_sha256 != package.dataset_sha256
        or inference.input_manifest_sha256 != package.dataset_sha256
        or inference.scope != package.scope
        or inference.static_context_sha256 != digest(package.context)
    ):
        raise ValueError("local evaluation freeze/package mismatch")
    validated_events = _verify_behavior_inputs(events, events_sha256, inference, perception,
                                               behavior_bundle)
    truth_bytes = package.simulation_export_path.read_bytes()
    truth = ResearchTruth.model_validate_json(truth_bytes)
    expected_frames = {frame.media_ref: (frame.camera_id, frame.timestamp)
                       for frame in package.frames}
    if (truth.schema_version != "local.camera.truth.v1" or truth.boundary != "EVALUATION_DEBUG_ONLY"
            or truth.dataset_sha256 != package.dataset_sha256
            or truth.config_sha256 != package.config_sha256 or truth.run_id != package.run_id
            or truth.model_id != package.model_id or truth.split != package.split
            or len(truth.ground_truth) != len(expected_frames)
            or {row.frame_ref: (row.camera_id, row.timestamp) for row in truth.ground_truth}
            != expected_frames
            or any(len({annotation.actor_identity for annotation in row.render_annotations})
                   != len(row.render_annotations) for row in truth.ground_truth)):
        raise ValueError("local truth binding/inventory mismatch")
    _, labels, pixel_metrics, details = _labels(perception, inference, truth)
    complete_pool, physics_pool, kinds = _inventory(package, inference)
    truth_pairs = {pair for pair in physics_pool
                   if labels[pair[0]] is not None and labels[pair[0]] == labels[pair[1]]}
    true_next = _next_successors(package, inference, labels)
    from amidst.engineering.local_association import candidate_segment_pairs

    retrieved_pool = set(candidate_segment_pairs(inference))
    proposed = {tuple(row.segment_ids) for row in inference.association_hypotheses
                if len(row.segment_ids) == 2 and row.status == "PROVISIONAL"}
    all_hypothesis_metrics = _link_metrics(proposed, truth_pairs, labels)  # type: ignore[arg-type]
    grouped = {}
    for kind in ("SAME_CAMERA_RECOVERY", "CROSS_CAMERA_GAP", "OVERLAPPING_VISIBILITY"):
        relevant = {pair for pair in truth_pairs if kinds.get("|".join(pair)) == kind}
        predictions = {pair for pair in proposed if kinds.get("|".join(pair)) == kind}
        grouped[kind] = _link_metrics(predictions, relevant, labels)  # type: ignore[arg-type]
    receipts = inference.retrieval_receipts
    read_count = sum(row.records_read for row in receipts)
    all_pairs = len(labels) * (len(labels) - 1) // 2
    retrieval = {
        "independent_complete_scope_candidate_count": len(complete_pool),
        "retrieved_pair_count": len(retrieved_pool),
        "complete_scope_pair_coverage": _ratio(len(retrieved_pool & complete_pool),
                                             len(complete_pool)),
        "same_identity_eligible_pair_count": len(truth_pairs),
        "retrieved_same_identity_eligible_pair_count": len(truth_pairs & retrieved_pool),
        "same_identity_eligible_pair_retrieval_recall": _ratio(len(truth_pairs & retrieved_pool),
                                                             len(truth_pairs)),
        "same_identity_eligible_pair_miss_count": len(truth_pairs - retrieved_pool),
        "true_next_successor_pair_count": len(true_next),
        "retrieved_true_next_successor_pair_count": len(true_next & retrieved_pool),
        "true_next_successor_retrieval_recall": _ratio(len(true_next & retrieved_pool),
                                                     len(true_next)),
        "true_next_successor_miss_count": len(true_next - retrieved_pool),
        "true_next_reference_condition": "Detected, GT-labeled produced segments only; "
        "earliest later nonoverlap physically feasible same-actor segment(s), all start-time ties",
        "true_next_reference_has_window_hop_or_record_budget": False,
        "undetected_full_actor_trajectory_recall":
        "N/A: reference is conditional on produced segments",
        "reference_retrieval_window_s": REFERENCE_RETRIEVAL_WINDOW_S,
        "reference_retrieval_max_hops": REFERENCE_RETRIEVAL_MAX_HOPS,
        "full_global_pair_count_for_comparison_only": all_pairs,
        "pairs_considered": inference.pair_count,
        "records_read": read_count,
        "index_entries_touched": sum(row.index_entries_touched for row in receipts),
        "frames_read": sum(row.frames_read for row in receipts),
        "crops_read": sum(row.crops_read for row in receipts),
        "bytes_read": sum(row.bytes_read for row in receipts),
        "touched_camera_count_per_query": [len(row.touched_camera_ids) for row in receipts],
        "expansions": sum(row.expansions for row in receipts),
        "stop_reasons": dict(Counter(reason for row in receipts for reason in row.stop_reasons)),
        "truncation_reasons": dict(Counter(reason for row in receipts
                                          for reason in row.truncation_reasons)),
        "query_latency_ms": "N/A: measured external telemetry must be supplied by runner",
        "inventory": "Independent evaluator full scope/time/reachability inventory; no runtime GT",
        "scope_completeness_is_formal_graph_proof": False,
    }
    speed_violations = 0
    region_violations = 0
    candidate_count = 0
    for gap in inference.snapshot.gaps:
        duration = gap.event.time_range[1] - gap.event.time_range[0]
        for candidate in gap.event.candidates:
            candidate_count += 1
            speed_violations += candidate.path_length > (
                duration * inference.policy.max_speed_m_s + 1e-8)
            x0, y0, x1, y1 = package.context.walkable_bounds_xy_m
            region_violations += any(not (x0 <= point[0] <= x1 and y0 <= point[1] <= y1)
                                     for point in candidate.polyline)
    summary: dict[str, object] = {
        "schema_version": "local.camera.evaluation.v1", "origin": "SYNTHETIC",
        "status": "E1_SYNTHETIC_PILOT_MEASURED", "split": package.split,
        "run_id": package.run_id, "model_id": package.model_id,
        "dataset_sha256": package.dataset_sha256, "config_sha256": package.config_sha256,
        "inference_sha256": receipt.inference_sha256, "freeze_sha256": receipt.receipt_sha256,
        "evaluation_truth_sha256": sha256(truth_bytes).hexdigest(),
        "evaluator_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "evaluator_policy": evaluator_policy(),
        "evaluator_policy_sha256": digest(evaluator_policy()),
        "behavior_bundle_binding_verified": behavior_bundle is not None,
        "pixels_and_local_identity": pixel_metrics,
        "association_all_provisional_hypotheses": all_hypothesis_metrics,
        "association_by_kind": grouped,
        "fixed_pool_feature_ablations": _fixed_pool_ablations(inference, labels, truth_pairs),
        "behavior": _behavior(validated_events, events_sha256, truth, labels, inference),
        "retrieval": retrieval,
        "geometry": {"candidate_count": candidate_count,
                     "hard_speed_violation_count": speed_violations,
                     "outside_configured_region_count": region_violations,
                     "projection_authority": "SYNTHETIC_CONFIG",
                     "formal_route_Coverage_at_K": "N/A: separate formal gates remain blocked"},
        "formal_phase1_acceptance": False, "external_model_calls": False,
        "limitations": [
            "Metrics use bounded evaluation-only pixel labels; unresolved identities are retained.",
            "Every provisional association is a hypothesis; no global identity is certified.",
            "No actor/appearance or camera/place generalization is claimed.",
            "Candidate identity recall is distinct from formal route Coverage@K.",
            "Missing reference metrics stay N/A; original formal gates remain effective.",
        ],
    }
    output = package.simulation_export_path.parents[2] / "evaluation"
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    debug = {"boundary": "LOCAL_EVALUATION_DEBUG_ONLY", "pixel_identity_assignment": details}
    (output / "debug").mkdir(exist_ok=True)
    (output / "debug/identity_labels.json").write_text(json.dumps(debug, indent=2) + "\n")
    return summary
