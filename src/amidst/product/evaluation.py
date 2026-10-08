"""Post-freeze product diagnostics; truth never enters product tools or records.

Recall is conditional on produced, sufficiently labeled, pure local tracks.  It
is not recall of undetected actors or trained ReID.  Source behavior metrics are
quoted from an independently hashed, receipt-bound existing evaluation only.
"""

from __future__ import annotations

import json
import math
from collections import Counter, deque
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.local_evaluation import ResearchTruth, _labels, evaluator_policy
from amidst.engineering.perception import PerceptionResult
from amidst.engineering.research_scene import DEFAULT_CONFIG, ResearchPackage
from amidst.product.appearance import (
    AppearanceError,
    AppearanceIndex,
    AppearanceSearchResult,
    DescriptorBundle,
)
from amidst.product.stitching import StitchBundle


class ProductEvaluationError(ValueError):
    """Fixed safe errors; private source locators are not external diagnostics."""


def product_evaluator_policy() -> dict[str, object]:
    return {
        "schema_version": "product.evaluation-policy.v1",
        "pixel_labeling": evaluator_policy(),
        "track_known_coverage_minimum": 0.7,
        "mixed_known_identities_are_eligible": False,
        "appearance_reference_window_s": 12.0,
        "appearance_reference_max_hops": 3,
        "appearance_recall_k": [1, 3, 5],
        "appearance_ties": "Retain every equal distance at each K cutoff; report returned counts",
        "quality_strata": {"LOW": [0.0, 0.25], "MEDIUM": [0.25, 0.5], "HIGH": [0.5, 1.0]},
        "stitch_positive_reference": "Pure produced same-identity tracks in one camera, positive "
        "short gap and declared pixel displacement/speed bounds; no appearance/quality filtering",
        "global_identity_metrics": "N/A: independent hypotheses do not assign global identities",
        "existing_behavior_reference": "Quote only matching source dataset/recipe config, "
        "inference/freeze and truth hashes; an unbound optional reference is N/A",
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _track_labels(
    perception: PerceptionResult, labels: dict[str, str | None]
) -> tuple[dict[str, str | None], dict[str, object], list[dict[str, object]]]:
    result: dict[str, str | None] = {}
    details: list[dict[str, object]] = []
    reasons: Counter[str] = Counter()
    for track in perception.tracks:
        known = Counter(
            labels[identity] for identity in track.observation_ids if labels[identity] is not None
        )
        coverage = sum(known.values()) / len(track.observation_ids)
        reason = (
            "UNRESOLVED"
            if not known
            else "MIXED_KNOWN_IDENTITIES"
            if len(known) > 1
            else "INSUFFICIENT_KNOWN_COVERAGE"
            if coverage < 0.7
            else "PURE_SUFFICIENTLY_LABELED"
        )
        result[track.local_track_id] = (
            next(iter(known)) if reason == "PURE_SUFFICIENTLY_LABELED" else None
        )
        reasons[reason] += 1
        details.append(
            {
                "local_track_id": track.local_track_id,
                "evaluation_only_actor": result[track.local_track_id],
                "known_measurements": sum(known.values()),
                "measurement_count": len(track.observation_ids),
                "known_coverage": coverage,
                "known_identity_count": len(known),
                "reason": reason,
            }
        )
    return (
        result,
        {
            "produced_local_tracks": len(perception.tracks),
            "track_label_status_counts": dict(reasons),
            "conditional_track_identity_population": True,
            "undetected_full_actor_recall": "N/A",
        },
        details,
    )


def _reachable(package: ResearchPackage, camera: str) -> set[str]:
    result, queue = {camera}, deque([(camera, 0)])
    while queue:
        current, depth = queue.popleft()
        if depth == 3:
            continue
        for source, target in package.adjacency:
            if source == current and target not in result:
                result.add(target)
                queue.append((target, depth + 1))
    return result


def _appearance(
    package: ResearchPackage,
    perception: PerceptionResult,
    bundle: DescriptorBundle,
    track_labels: dict[str, str | None],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    index = AppearanceIndex(bundle)
    rows = bundle.track_descriptors
    labels = {row.track_ref: track_labels[row.local_track_id] for row in rows}
    pixels = {row.observation_id: row for row in perception.measurements}
    mean_rgb = {
        row.track_ref: tuple(
            math.fsum(
                pixels[identity].appearance[channel] / 255
                for identity in row.original_observation_ids
            )
            / len(row.original_observation_ids)
            for channel in range(3)
        )
        for row in rows
    }
    totals: dict[str, Counter[str]] = {"handcrafted": Counter(), "component_mean_rgb": Counter()}
    strata: dict[str, Counter[str]] = {name: Counter() for name in ("LOW", "MEDIUM", "HIGH")}
    details: list[dict[str, object]] = []
    pool_manifest: list[dict[str, object]] = []
    excluded: Counter[str] = Counter()
    for query in rows:
        if labels[query.track_ref] is None:
            excluded["UNRESOLVED_OR_IMPURE_QUERY"] += 1
            continue
        reached = _reachable(package, query.camera_id)
        window = (query.time_range[0], query.time_range[1] + 12)
        allowed = tuple(
            row.track_ref
            for row in rows
            if row.track_ref != query.track_ref
            and row.camera_id in reached
            and row.time_range[0] <= window[1]
            and window[0] <= row.time_range[1]
        )
        relevant = {
            ref
            for ref in allowed
            if labels[ref] is not None and labels[ref] == labels[query.track_ref]
        }
        pool_manifest.append(
            {"query_ref": query.track_ref, "pool": allowed, "positive_count": len(relevant)}
        )
        if not relevant:
            excluded["NO_ELIGIBLE_SAME_IDENTITY_PRODUCED_TARGET"] += 1
            continue
        stratum = "LOW" if query.quality < 0.25 else "MEDIUM" if query.quality < 0.5 else "HIGH"
        searches: dict[int, AppearanceSearchResult | None] = {}
        for k in (1, 3, 5):
            try:
                searches[k] = index.search(
                    query.track_ref,
                    scope=bundle.scope,
                    allowed_track_refs=allowed,
                    camera_id=None,
                    time_range=window,
                    top_k=k,
                )
            except AppearanceError:
                # An eligible query that cannot execute is a retrieval failure,
                # never removed from the conditional reference denominator.
                searches[k] = None
                excluded[f"RUNTIME_QUERY_OR_APPEARANCE_FAILURE_AT_{k}"] += 1
        baseline = sorted(
            (math.dist(mean_rgb[query.track_ref], mean_rgb[ref]) / math.sqrt(3), ref)
            for ref in allowed
        )
        for counters in (*totals.values(), strata[stratum]):
            counters["queries"] += 1
        per_query: dict[str, object] = {
            "query_ref": query.track_ref,
            "quality_stratum": stratum,
            "eligible_positive_count": len(relevant),
            "methods": {},
        }
        methods: dict[str, object] = {}
        for k, search in searches.items():
            current = {hit.track_ref for hit in search.hits} if search is not None else set()
            selected = baseline[:k]
            if selected:
                selected.extend(
                    item
                    for item in baseline[k:]
                    if math.isclose(item[0], selected[-1][0], abs_tol=1e-12, rel_tol=0)
                )
            baseline_refs = {ref for _, ref in selected}
            for name, returned in (("handcrafted", current), ("component_mean_rgb", baseline_refs)):
                hit = bool(returned & relevant)
                totals[name][f"hits_{k}"] += hit
                totals[name][f"returned_{k}"] += len(returned)
                totals[name][f"ties_{k}"] += max(0, len(returned) - k)
                if name == "handcrafted":
                    strata[stratum][f"hits_{k}"] += hit
                    strata[stratum][f"returned_{k}"] += len(returned)
            methods[str(k)] = {
                "handcrafted_refs": sorted(current),
                "mean_rgb_refs": sorted(baseline_refs),
                "evaluation_only_positive_refs": sorted(relevant),
            }
        per_query["methods"] = methods
        details.append(per_query)

    def report(counter: Counter[str]) -> dict[str, object]:
        count = counter["queries"]
        return {
            "eligible_queries": count,
            "tie_aware_recall_at_k": {
                str(k): _ratio(counter[f"hits_{k}"], count) for k in (1, 3, 5)
            },
            "mean_returned_hits_at_k": {
                str(k): _ratio(counter[f"returned_{k}"], count) for k in (1, 3, 5)
            },
            "cutoff_tie_extensions_at_k": {str(k): counter[f"ties_{k}"] for k in (1, 3, 5)},
        }

    return {
        "status": "CONDITIONAL_PRODUCED_PURE_TRACK_RETRIEVAL",
        "receiver": "FROZEN_APPEARANCE_INDEX_REACHABLE_CAMERA_LOCAL_POOL",
        "same_pool_sha256": digest(pool_manifest),
        "pool_query_count": len(pool_manifest),
        "query_exclusion_counts": dict(excluded),
        "handcrafted": report(totals["handcrafted"]),
        "component_mean_rgb_same_pool_baseline": report(totals["component_mean_rgb"]),
        "handcrafted_by_query_quality": {name: report(counter) for name, counter in strata.items()},
        "full_actor_or_undetected_person_recall": "N/A",
        "trained_reid_accuracy": "N/A",
        "scores_are_probabilities": False,
        "tie_interpretation": "Equal-distance alternatives can yield more than K cutoff hits",
        "condition": "Produced pure tracks only; unknown and impure targets remain in the pool "
        "without being counted as known positives",
    }, details


def _stitches(
    perception: PerceptionResult, bundle: StitchBundle, labels: dict[str, str | None]
) -> tuple[dict[str, object], list[dict[str, object]]]:
    pixels = {row.observation_id: row for row in perception.measurements}
    ordered = sorted(
        perception.tracks,
        key=lambda row: (row.timestamps[0], row.timestamps[-1], row.local_track_id),
    )
    eligible: set[tuple[str, str]] = set()
    true_pairs: set[tuple[str, str]] = set()
    for first, second in combinations(ordered, 2):
        gap = second.timestamps[0] - first.timestamps[-1]
        if first.camera_id != second.camera_id or not 0 < gap <= bundle.config.max_gap_s:
            continue
        distance = math.dist(
            pixels[first.observation_ids[-1]].contact_pixel,
            pixels[second.observation_ids[0]].contact_pixel,
        )
        if (
            distance > bundle.config.max_contact_gap_px
            or distance / gap > bundle.config.max_pixel_speed_px_s
        ):
            continue
        if labels[first.local_track_id] is None or labels[second.local_track_id] is None:
            continue
        pair = first.local_track_id, second.local_track_id
        eligible.add(pair)
        if labels[first.local_track_id] == labels[second.local_track_id]:
            true_pairs.add(pair)
    proposed = {
        tuple(row.original_track_ids)
        for row in bundle.hypotheses
        if row.kind == "SHORT_GAP_RECOVERY" and row.status == "PROVISIONAL"
    }
    known_proposed = {
        pair for pair in proposed if labels[pair[0]] is not None and labels[pair[1]] is not None
    }
    tp = len(known_proposed & true_pairs)
    details: list[dict[str, object]] = [
        {
            "hypothesis_ref": row.hypothesis_ref,
            "status": row.status,
            "reason": row.reason,
            "original_track_ids": row.original_track_ids,
            "evaluation_only_same_identity": (
                None
                if any(labels[identity] is None for identity in row.original_track_ids)
                else len({labels[identity] for identity in row.original_track_ids}) == 1
            ),
            "reference_eligible": tuple(row.original_track_ids) in eligible,
        }
        for row in bundle.hypotheses
        if row.kind != "UNMATCHED"
    ]
    return {
        "positive_reference_count": len(true_pairs),
        "known_pixel_eligible_pair_count": len(eligible),
        "provisional_pair_count": len(proposed),
        "resolved_provisional_pair_count": len(known_proposed),
        "unresolved_provisional_pair_count": len(proposed - known_proposed),
        "true_positive": tp,
        "false_positive": len(known_proposed - true_pairs),
        "false_negative": len(true_pairs - known_proposed),
        "pair_precision": _ratio(tp, len(known_proposed)),
        "pair_recall": _ratio(tp, len(true_pairs)),
        "hypothesis_status_counts": dict(Counter(row.status for row in bundle.hypotheses)),
        "hypothesis_kind_counts": dict(Counter(row.kind for row in bundle.hypotheses)),
        "enumeration_complete": bundle.complete,
        "source_inputs_complete": bundle.source_inputs_complete,
        "IDF1": "N/A",
        "global_false_merge_count": "N/A",
        "global_false_split_count": "N/A",
        "identity_assignment": "Independent provisional pairs; no global assignment",
        "reference": "Pure tracks, same camera, short gap and pixel bounds; "
        "no reference filtering by appearance or quality",
    }, details


def _behavior_reference(
    baseline: object, *, dataset: str, config: str, inference: str, freeze: str, truth: str
) -> dict[str, object]:
    if not isinstance(baseline, dict):
        return {"status": "N/A", "reason": "Existing frozen source evaluation unavailable"}
    expected = {
        "dataset_sha256": dataset,
        "config_sha256": config,
        "inference_sha256": inference,
        "freeze_sha256": freeze,
        "evaluation_truth_sha256": truth,
    }
    if any(baseline.get(name) != value for name, value in expected.items()):
        return {
            "status": "N/A",
            "reason": "SOURCE_EVALUATION_BINDING_MISMATCH",
            "source_evaluation_sha256": digest(baseline),
        }
    behavior = baseline.get("behavior")
    if not isinstance(behavior, dict) or not isinstance(behavior.get("groups"), dict):
        return {"status": "N/A", "reason": "Source behavior metric population unavailable"}
    groups = behavior["groups"]
    visible = groups.get("visible_supported", {})
    per_kind = visible.get("per_kind", {}) if isinstance(visible, dict) else {}
    safe = {}
    for kind in ("ENTER", "EXIT", "CORNER", "DWELL", "POSSIBLE_WANDERING"):
        metrics = per_kind.get(kind) if isinstance(per_kind, dict) else None
        if not isinstance(metrics, dict):
            continue
        safe[kind] = {
            name: value
            for name, value in metrics.items()
            if name
            in {
                "true_positive",
                "false_positive",
                "false_negative",
                "unresolved",
                "precision",
                "recall",
                "support",
                "expected",
            }
            and (
                value is None
                or isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                or isinstance(value, str)
                and value == "N/A"
            )
        }
    return {
        "status": "QUOTED_EXISTING_POST_FREEZE_SOURCE_EVALUATION",
        "source_evaluation_sha256": digest(baseline),
        "visible_supported_per_kind": safe,
        "inferred_gap_behavior_metrics": "N/A",
        "new_winner_or_behavior_inference_run": False,
    }


def _immutable_json(path: Path, value: object) -> None:
    payload = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ProductEvaluationError("EVALUATION_RECEIPT_CONFLICT")
        return
    path.write_bytes(payload)


def evaluate_product(output: Path) -> dict[str, object]:
    """Load and verify the entire product first; only then open independent truth."""
    from amidst.engineering.local_pilot import _load, frozen_mode
    from amidst.product.run import load_product

    output = output.resolve()
    try:
        runtime = load_product(output)
    except (OSError, ValueError, KeyError) as error:
        raise ProductEvaluationError("PRODUCT_FREEZE_REQUIRED_OR_MISMATCH") from error
    try:
        package, _, _, source_manifest = _load(runtime.source)
        # This is evaluation reference certification, never an inference config import.
        source_config = json.loads(DEFAULT_CONFIG.read_bytes())
        if digest(source_config) != package.config_sha256:
            raise ProductEvaluationError("EVALUATION_SOURCE_CONFIG_UNAVAILABLE")
        truth_bytes = package.simulation_export_path.read_bytes()
        truth = ResearchTruth.model_validate_json(truth_bytes)
        expected_frames = {
            frame.media_ref: (frame.camera_id, frame.timestamp) for frame in package.frames
        }
        if (
            truth.schema_version != "local.camera.truth.v1"
            or truth.boundary != "EVALUATION_DEBUG_ONLY"
            or truth.dataset_sha256 != package.dataset_sha256
            or truth.config_sha256 != package.config_sha256
            or truth.model_id != package.model_id
            or truth.run_id != package.run_id
            or truth.split != package.split
            or truth.recipe != source_config["splits"][package.split]
            or len(truth.ground_truth) != len(expected_frames)
            or {row.frame_ref: (row.camera_id, row.timestamp) for row in truth.ground_truth}
            != expected_frames
        ):
            raise ProductEvaluationError("EVALUATION_TRUTH_BINDING_MISMATCH")
        recipe_actors = source_config["splits"][package.split]["actors"]
        for frame in truth.ground_truth:
            expected_identities = {
                actor["actor_identity"]
                for actor in recipe_actors
                if actor["waypoints"][0][0] <= frame.timestamp <= actor["waypoints"][-1][0]
            }
            if (
                len({annotation.actor_identity for annotation in frame.render_annotations})
                != len(frame.render_annotations)
                or {annotation.actor_identity for annotation in frame.render_annotations}
                != expected_identities
                or any(
                    not all(math.isfinite(value) for value in annotation.position_xyz_m)
                    or annotation.contact_uv is not None
                    and not all(math.isfinite(value) for value in annotation.contact_uv)
                    for annotation in frame.render_annotations
                )
            ):
                raise ProductEvaluationError("EVALUATION_TRUTH_INVENTORY_INVALID")
        truth_hash = sha256(truth_bytes).hexdigest()
        old_receipt = output / "evaluation" / "receipt.json"
        if (
            old_receipt.exists()
            and json.loads(old_receipt.read_bytes()).get("evaluation_truth_sha256") != truth_hash
        ):
            raise ProductEvaluationError("EVALUATION_TRUTH_CHANGED")
        baseline_path = runtime.source / "evaluation.json"
        baseline: dict[str, Any] = (
            json.loads(baseline_path.read_bytes()) if baseline_path.exists() else {}
        )
        modes: dict[str, object] = {}
        debug: dict[str, object] = {}
        for mode_receipt, service in zip(runtime.manifest.modes, runtime.services, strict=True):
            mode = mode_receipt.observation_mode
            perception, inference, _, receipt = frozen_mode(runtime.source, mode, source_manifest)
            descriptors = service.descriptors
            if descriptors is None:
                raise ProductEvaluationError("APPEARANCE_FREEZE_UNAVAILABLE")
            stitches = StitchBundle.model_validate(service.stitches)
            measurement_labels, _, pixels, pixel_details = _labels(perception, inference, truth)
            labels, population, label_details = _track_labels(perception, measurement_labels)
            appearance, retrieval_details = _appearance(package, perception, descriptors, labels)
            stitch_summary, stitch_details = _stitches(perception, stitches, labels)
            behavior = _behavior_reference(
                baseline.get(mode),
                dataset=package.dataset_sha256,
                # E1 evaluation binds the recipe/dataset configuration.  The
                # separately checked freeze receipt binds effective inference
                # configuration; these are distinct hash domains.
                config=package.config_sha256,
                inference=receipt.inference_sha256,
                freeze=receipt.receipt_sha256,
                truth=truth_hash,
            )
            modes[mode] = {
                "population": population,
                "source_pixel_measurement_diagnostics": pixels,
                "appearance": appearance,
                "stitching": stitch_summary,
                "existing_behavior_reference": behavior,
                "product_freeze_ref": mode_receipt.product_freeze_ref,
                "appearance_sha256": mode_receipt.appearance_sha256,
                "stitch_sha256": mode_receipt.stitch_sha256,
            }
            debug[mode] = {
                "pixel_labels": pixel_details,
                "track_labels": label_details,
                "appearance_queries": retrieval_details,
                "stitch_hypotheses": stitch_details,
            }
        policy = product_evaluator_policy()
        result: dict[str, object] = {
            "schema_version": "product.evaluation.v1",
            "status": "LOCAL_SYNTHETIC_PRODUCT_MEASURED",
            "run_id": package.run_id,
            "model_id": package.model_id,
            "split": package.split,
            "origin": "SYNTHETIC",
            "authority": "CONFIGURED_ENGINEERING_DIAGNOSTIC_ONLY",
            "dataset_sha256": package.dataset_sha256,
            "product_manifest_sha256": runtime.manifest.manifest_sha256,
            "source_manifest_sha256": runtime.manifest.source_manifest_sha256,
            "product_config_sha256": runtime.manifest.product_config_sha256,
            "evaluation_truth_sha256": truth_hash,
            "evaluator_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "pixel_labeling_code_sha256": sha256(
                Path(__file__)
                .parents[1]
                .joinpath("engineering", "local_evaluation.py")
                .read_bytes()
            ).hexdigest(),
            "evaluator_policy": policy,
            "evaluator_policy_sha256": digest(policy),
            "modes": modes,
            "formal_phase1_acceptance": False,
            "external_model_calls": False,
            "limitations": [
                "Conditional produced pure-track population, not undetected full actor recall.",
                "Cutoff ties are all retained; more than K returned references is explicit.",
                "No trained ReID, global identity assignment or appearance/place generalization.",
                "Existing behavior metrics are quoted, not regenerated or changed.",
            ],
        }
        receipt_summary = {
            name: result[name]
            for name in (
                "dataset_sha256",
                "product_manifest_sha256",
                "source_manifest_sha256",
                "product_config_sha256",
                "evaluation_truth_sha256",
                "evaluator_sha256",
                "pixel_labeling_code_sha256",
                "evaluator_policy_sha256",
            )
        }
        receipt_summary["summary_sha256"] = digest(result)
        receipt_summary["product_freeze_refs"] = {
            receipt.observation_mode: receipt.product_freeze_ref
            for receipt in runtime.manifest.modes
        }
        _immutable_json(
            output / "evaluation" / "debug" / "identity_mappings.json",
            {"boundary": "LOCAL_EVALUATION_DEBUG_ONLY", "modes": debug},
        )
        _immutable_json(output / "evaluation" / "summary.json", result)
        _immutable_json(output / "evaluation" / "receipt.json", receipt_summary)
        return result
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, ProductEvaluationError):
            raise
        raise ProductEvaluationError("EVALUATION_REFERENCE_UNAVAILABLE_OR_INVALID") from error
    finally:
        runtime.close()
