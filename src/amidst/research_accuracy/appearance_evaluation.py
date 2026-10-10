"""Evaluator-only P8-compatible fixed-pool comparison of handcrafted RGB evidence.

Caller supplies post-freeze measurement labels.  Labels decide only evaluation
eligibility and positives; crop aggregation and distances never consume them.
This module reads no truth, recipes or reference sidecars and is not imported by
the runtime producer, association, Graph or product tools.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any

from amidst.engineering.access import FreezeReceipt, digest
from amidst.engineering.local_association import InferenceBundle, resource_scope
from amidst.engineering.perception import PerceptionResult
from amidst.engineering.registry import (
    LocationRegistry,
    RegistryStore,
    opaque_ref,
    safe_relative_path,
    scope_parts,
)
from amidst.engineering.research_scene import ResearchPackage
from amidst.product import appearance as p8
from amidst.product import evaluation as p8_evaluation
from amidst.research_accuracy import association as robust
from amidst.research_accuracy.association import RGBDescriptorBundle, SegmentDescriptor

K_VALUES = (1, 3, 5)


def _pool_manifest(
    package: ResearchPackage, rows: Sequence[p8.TrackDescriptor], labels: Mapping[str, str | None],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    """Exactly the P8 query/pool/positive population, independent of crop quality."""
    manifest: list[dict[str, Any]] = []
    excluded: Counter[str] = Counter()
    for query in rows:
        label = labels[query.local_track_id]
        if label is None:
            excluded["UNRESOLVED_OR_IMPURE_QUERY"] += 1
            continue
        reached = p8_evaluation._reachable(package, query.camera_id)
        window = (query.time_range[0], query.time_range[1] + 12)
        allowed = tuple(row.track_ref for row in rows
                        if row.track_ref != query.track_ref and row.camera_id in reached
                        and row.time_range[0] <= window[1] and window[0] <= row.time_range[1])
        relevant = tuple(row.track_ref for row in rows
                         if row.track_ref in allowed and labels[row.local_track_id] is not None
                         and labels[row.local_track_id] == label)
        manifest.append({"query_ref": query.track_ref, "pool": allowed,
                         "positive_count": len(relevant), "positive_refs": relevant})
        if not relevant:
            excluded["NO_ELIGIBLE_SAME_IDENTITY_PRODUCED_TARGET"] += 1
    return manifest, excluded


def _p8_pool_digest(manifest: Sequence[Mapping[str, Any]]) -> str:
    return digest([{"query_ref": row["query_ref"], "pool": row["pool"],
                    "positive_count": row["positive_count"]} for row in manifest])


def _cutoff_refs(ranked: Sequence[tuple[float, str]], k: int) -> set[str]:
    selected = list(ranked[:k])
    if selected:
        cutoff = selected[-1][0]
        selected.extend(row for row in ranked[k:]
                        if math.isclose(row[0], cutoff, abs_tol=1e-12, rel_tol=0))
    return {ref for _, ref in selected}


def _counter_report(counter: Counter[str]) -> dict[str, Any]:
    count = counter["queries"]
    return {
        "eligible_queries": count,
        "tie_aware_recall_at_k": {
            str(k): counter[f"hits_{k}"] / count if count else None for k in K_VALUES
        },
        "true_positive_queries_at_k": {str(k): counter[f"hits_{k}"] for k in K_VALUES},
        "false_negative_queries_at_k": {str(k): count - counter[f"hits_{k}"] for k in K_VALUES},
        "missing_query_descriptor_count": counter["missing_query_descriptor"],
        "missing_candidate_descriptor_reads": counter["missing_candidate_descriptors"],
        "mean_returned_hits_at_k": {
            str(k): counter[f"returned_{k}"] / count if count else None for k in K_VALUES
        },
        "cutoff_tie_extensions_at_k": {str(k): counter[f"ties_{k}"] for k in K_VALUES},
    }


def _retrieval(
    manifest: Sequence[Mapping[str, Any]], vectors: Mapping[str, tuple[float, ...] | None],
    quality: Mapping[str, float], distance: Callable[[Sequence[float], Sequence[float]], float],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """An unavailable query or positive target remains a conditional retrieval FN."""
    totals: Counter[str] = Counter()
    strata: dict[str, Counter[str]] = {name: Counter() for name in ("LOW", "MEDIUM", "HIGH")}
    details: list[dict[str, Any]] = []
    for row in manifest:
        positives = set(row["positive_refs"])
        if not positives:
            continue
        query = row["query_ref"]
        query_vector = vectors.get(query)
        value = quality.get(query, 0)
        stratum = "LOW" if value < 0.25 else "MEDIUM" if value < 0.5 else "HIGH"
        counters = (totals, strata[stratum])
        missing_targets = sum(vectors.get(ref) is None for ref in row["pool"])
        for counter in counters:
            counter["queries"] += 1
            counter["missing_query_descriptor"] += query_vector is None
            counter["missing_candidate_descriptors"] += missing_targets
        ranked = []
        if query_vector is not None:
            for ref in row["pool"]:
                target = vectors.get(ref)
                if target is not None:
                    ranked.append((distance(query_vector, target), ref))
            ranked.sort()
        per_k = {}
        for k in K_VALUES:
            returned = _cutoff_refs(ranked, k)
            for counter in counters:
                counter[f"hits_{k}"] += bool(returned & positives)
                counter[f"returned_{k}"] += len(returned)
                counter[f"ties_{k}"] += max(0, len(returned) - k)
            per_k[str(k)] = {"returned_refs": sorted(returned),
                             "hit": bool(returned & positives)}
        details.append({"query_ref": query, "quality_stratum": stratum,
                        "eligible_positive_count": len(positives),
                        "missing_query_descriptor": query_vector is None,
                        "missing_candidate_descriptors": missing_targets, "at_k": per_k})
    return _counter_report(totals) | {
        "by_query_quality": {name: _counter_report(counter) for name, counter in strata.items()},
        "quality_strata": "LOW<0.25; MEDIUM<0.5; HIGH>=0.5; uncalibrated crop quality",
    }, details


def _track_profiles(
    perception: PerceptionResult, bundle: RGBDescriptorBundle,
) -> dict[str, SegmentDescriptor]:
    """Reuse the RGB-only robust policy on every original crop in each local track."""
    samples = {row.observation_id: row for row in bundle.measurement_descriptors}
    if set(samples) != {row.observation_id for row in perception.measurements}:
        raise ValueError("appearance evaluation crop population mismatch")
    for measurement in perception.measurements:
        sample = samples[measurement.observation_id]
        if (sample.local_track_id, sample.frame_ref, sample.camera_id,
                sample.timestamp, sample.input_sha256) != (
            measurement.local_track_id, measurement.frame_ref, measurement.camera_id,
            measurement.timestamp, measurement.input_sha256,
        ):
            raise ValueError("appearance evaluation crop measurement binding mismatch")
    return {
        track.local_track_id: robust._profile(
            "evaluation-track:" + track.local_track_id, track.local_track_id,
            [samples[identity] for identity in track.observation_ids], bundle.config,
        ) for track in perception.tracks
    }


def _registry_store(
    package: ResearchPackage, registry: LocationRegistry, frame_links: Mapping[str, str],
) -> RegistryStore:
    """Derive one contained RGB root from explicit verified package/registry records."""
    registered = {row.media_ref: row for row in registry.frames}
    roots: set[Path] = set()
    for frame in package.frames:
        entry = registered.get(frame_links.get(frame.media_ref, ""))
        if entry is None or (entry.scope, entry.camera_id, entry.timestamp, entry.sha256,
                             entry.width, entry.height) != (
            resource_scope(package.scope), frame.camera_id, frame.timestamp, frame.sha256,
            frame.width, frame.height,
        ):
            raise ValueError("appearance evaluation registry RGB binding mismatch")
        relative = safe_relative_path(entry.relative_path)
        path = frame.path.resolve()
        if len(relative.parts) > len(path.parents):
            raise ValueError("appearance evaluation RGB containment mismatch")
        root = path.parents[len(relative.parts) - 1]
        if root.joinpath(relative).resolve() != path:
            raise ValueError("appearance evaluation RGB containment mismatch")
        roots.add(root)
    if len(roots) != 1:
        raise ValueError("appearance evaluation requires one explicit RGB materialization")
    return RegistryStore(registry, next(iter(roots)))


def evaluate_appearance(
    package: ResearchPackage, perception: PerceptionResult, inference: InferenceBundle,
    descriptors: RGBDescriptorBundle, measurement_labels: dict[str, str | None],
    registry: LocationRegistry, source_manifest: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compare robust crops/P8/mean RGB using the identical P8 produced-track pool.

    Run only after the caller verifies the freeze and creates independent labels.
    P8 is recomputed from the same RGB; no historical product output is overwritten.
    A v2 producer population is explicitly a separate experiment from frozen v1.
    """
    descriptors = RGBDescriptorBundle.model_validate(descriptors.model_dump())
    if (descriptors.scope != inference.scope or inference.scope != package.scope
            or descriptors.dataset_sha256 != package.dataset_sha256
            or descriptors.perception_sha256 != digest(perception.model_dump(mode="json"))
            or descriptors.producer_sha256 != perception.producer_sha256
            or inference.producer_sha256 != perception.producer_sha256
            or inference.input_manifest_sha256 != package.dataset_sha256
            or descriptors.candidate_pool_sha256 != inference.association_pool_sha256
            or perception.input_manifest_sha256 != package.dataset_sha256
            or source_manifest["run_id"] != package.run_id
            or source_manifest["registry_sha256"] != registry.sha256
            or {row.segment_id: (row.local_track_id, row.observation_ids)
                for row in descriptors.segment_descriptors} != {
                    row.segment_id: (row.local_track_id, row.original_pixel_observation_ids)
                    for row in inference.local_record_maps}
            or set(measurement_labels) != {row.observation_id for row in perception.measurements}):
        raise ValueError("appearance evaluation source/producer/pool binding mismatch")
    scope = resource_scope(package.scope)
    profiles = _track_profiles(perception, descriptors)
    # Descriptor aggregation is completed before labels are examined.
    store = _registry_store(package, registry, source_manifest["frame_links"])
    p8_bundle = p8.build_appearance_bundle(
        perception, store, scope, source_manifest["frame_links"],
        input_config_sha256=source_manifest["config_sha256"],
    )
    labels, population, _ = p8_evaluation._track_labels(perception, measurement_labels)
    p8_summary, p8_details = p8_evaluation._appearance(package, perception, p8_bundle, labels)
    manifest, excluded = _pool_manifest(package, p8_bundle.track_descriptors, labels)
    pool_hash = _p8_pool_digest(manifest)
    if pool_hash != p8_summary["same_pool_sha256"]:
        raise ValueError("appearance evaluation differs from the P8 fixed pool")
    track_refs = {track_id: opaque_ref("track", *scope_parts(scope), track_id)
                  for track_id in profiles}
    vectors = {track_refs[identity]: profile.vector for identity, profile in profiles.items()}
    quality = {track_refs[identity]: profile.quality for identity, profile in profiles.items()}
    result, details = _retrieval(manifest, vectors, quality, robust.descriptor_distance)
    eligible = sum(bool(row["positive_refs"]) for row in manifest)
    reference_methods = [p8_summary[name] for name in
                         ("handcrafted", "component_mean_rgb_same_pool_baseline")]
    if eligible != result["eligible_queries"] or any(
        not isinstance(method, dict) or eligible != method["eligible_queries"]
        for method in reference_methods
    ):
        raise ValueError("appearance evaluation conditional denominator differs from P8")
    receipts = [FreezeReceipt.model_validate(row)
                for row in source_manifest["receipts"].values()]
    same_original_producer = any(
        receipt.measurement_sha256 == digest(perception.model_dump(mode="json"))
        and receipt.binding.producer_sha256 == perception.producer_sha256
        and receipt.binding.dataset_sha256 == package.dataset_sha256 for receipt in receipts
    )
    reference_details = {str(row["query_ref"]): row for row in p8_details}
    details = [row | {"p8_reference": reference_details[row["query_ref"]]} for row in details]
    return {
        "schema_version": "research.appearance-evaluation.v2",
        "status": "CONDITIONAL_PRODUCED_PURE_TRACK_RETRIEVAL",
        "population_relation_to_frozen_v1": (
            "EXACT_FROZEN_V1_PRODUCER_TRACK_POOL" if same_original_producer
            else "CHANGED_PRODUCER_TRACK_POOL_SEPARATE_EXPERIMENT"
        ),
        "source_perception_sha256": digest(perception.model_dump(mode="json")),
        "source_dataset_sha256": package.dataset_sha256,
        "producer_sha256": perception.producer_sha256,
        "descriptor_input_inference_sha256": descriptors.input_inference_sha256,
        "ranked_inference_sha256": digest(inference),
        "association_candidate_pool_sha256": inference.association_pool_sha256,
        "rgb_descriptor_bundle_sha256": digest(descriptors),
        "rgb_descriptor_algorithm_sha256": descriptors.algorithm_sha256,
        "p8_descriptor_bundle_sha256": digest(p8_bundle),
        "p8_descriptor_algorithm_sha256": p8_bundle.algorithm_sha256,
        "evaluator_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "population": population,
        "same_pool_sha256": pool_hash,
        "p8_same_pool_sha256": p8_summary["same_pool_sha256"],
        "pool_equality_proven": True,
        "pool_query_count": len(manifest),
        "eligible_queries": eligible,
        "pool_candidate_reads": sum(len(row["pool"]) for row in manifest),
        "query_exclusion_counts": dict(excluded),
        "robust_crop": result,
        "p8_reference_same_tracks_and_pool": p8_summary,
        "track_aggregation": "RGB-only quality-weighted medoid/outlier policy over all "
        "original measurement crops; independent of segment count and evaluator labels",
        "aggregation_counts": {
            "tracks": len(profiles),
            "unavailable_tracks": sum(row.vector is None for row in profiles.values()),
            "usable_measurements": sum(row.usable_measurements for row in profiles.values()),
            "retained_measurements": sum(row.retained_measurements for row in profiles.values()),
            "excluded_measurements": sum(len(row.excluded_observation_ids)
                                         for row in profiles.values()),
        },
        "missing_descriptor_policy": "Eligible missing queries remain false negatives; "
        "unavailable positive targets remain in the reference denominator",
        "tie_interpretation": "Every distance tie at K is retained; more than K can be returned",
        "scores_are_probabilities": False,
        "trained_reid_accuracy": "N/A",
        "full_actor_or_undetected_person_recall": "N/A",
        "cross_place_generalization": "UNVERIFIED",
    }, details
