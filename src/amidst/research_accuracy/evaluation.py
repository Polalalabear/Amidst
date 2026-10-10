"""Post-freeze comparison; truth and recipe labels stay in this evaluator only."""

from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.local_association import AssociationHypothesis, InferenceBundle
from amidst.engineering.local_evaluation import (
    ResearchTruth,
    _behavior,
    _inventory,
    _labels,
    _link_metrics,
    evaluate_local_pilot,
)
from amidst.engineering.local_pilot import MODES, _save
from amidst.research_accuracy.association import (
    AssociationConfig,
    RGBDescriptorBundle,
    rank_association_hypotheses,
)
from amidst.research_accuracy.baseline import isolated_package
from amidst.research_accuracy.behavior import event_support_state
from amidst.research_accuracy.run import (
    VARIANTS,
    FrozenVariant,
    association_config,
    frozen,
    load,
)


def _ranking_metrics(
    ranked: tuple[AssociationHypothesis, ...],
    inference: InferenceBundle,
    labels: dict[str, str | None],
    truth_pairs: set[tuple[str, str]],
) -> dict[str, Any]:
    by_source: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in ranked:
        if len(row.segment_ids) == 2:
            by_source[row.segment_ids[0]].append((row.segment_ids[0], row.segment_ids[1]))
    relevant = {a for a, _ in truth_pairs}
    result = _link_metrics({rows[0] for rows in by_source.values() if rows}, truth_pairs, labels)
    result["identity_candidate_recall_at_k"] = {
        str(k): sum(any(p in truth_pairs for p in by_source.get(a, ())[:k]) for a in relevant)
        / len(relevant)
        if relevant
        else None
        for k in (1, 3, 5)
    }
    result.update(
        {
            "eligible_query_count": len(relevant),
            "candidate_pool_sha256": inference.association_pool_sha256,
            "hard_physics_preserved": True,
            "scores_are_probabilities": False,
        }
    )
    return result


def feature_ablations(
    inference: InferenceBundle,
    labels: dict[str, str | None],
    truth_pairs: set[tuple[str, str]],
    config: AssociationConfig,
) -> dict[str, Any]:
    result = {}
    for removed in (None, "SPACE", "TIME", "APPEARANCE"):
        ranked = rank_association_hypotheses(inference, config=config, removed_feature=removed)
        result["full" if removed is None else "without_" + removed.lower()] = _ranking_metrics(
            ranked,
            inference,
            labels,
            truth_pairs,
        )
    for feature in ("SPACE", "TIME", "APPEARANCE"):
        result["only_" + feature.lower()] = _ranking_metrics(
            rank_association_hypotheses(inference, config=config, feature_only=feature),
            inference,
            labels,
            truth_pairs,
        )
    return result


def supported_behavior(
    state: FrozenVariant, truth: ResearchTruth, labels: dict[str, str | None]
) -> dict[str, Any]:
    """Unknown claims stay in prediction count and cannot remove a truth false negative."""
    events = state.events.events
    masked = tuple(
        e.model_copy(update={"local_track_ids": ()}) if event_support_state(e) == "UNKNOWN" else e
        for e in events
    )
    report = _behavior(
        masked, digest([e.model_dump(mode="json") for e in masked]), truth, labels, state.inference
    )
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for event in events:
        counts[event.kind][event_support_state(event)] += 1
    report["candidate_support_population"] = {
        kind: {
            "candidate_count": sum(c.values()),
            "supported": c["SUPPORTED"],
            "unknown": c["UNKNOWN"],
            "gap_alternatives": c["GAP_ALTERNATIVES"],
            "unknown_fraction": c["UNKNOWN"] / sum(c.values()),
        }
        for kind, c in sorted(counts.items())
    }
    visible = [e for e in events if event_support_state(e) != "GAP_ALTERNATIVES"]
    unknown = sum(event_support_state(e) == "UNKNOWN" for e in visible)
    report["visible_candidate_count"] = len(visible)
    report["evidence_unknown_count"] = unknown
    report["evidence_unknown_fraction"] = unknown / len(visible) if visible else None
    report["policy"] = (
        "Evidence UNKNOWN is unresolved; all original truth events remain in FN/recall"
    )
    return report


def pixel_population(
    state: FrozenVariant, measurement_labels: dict[str, str | None]
) -> dict[str, Any]:
    tracks = state.perception.tracks
    multiplicity: Counter[str] = Counter()
    mixed = 0
    singleton = 0
    for track in tracks:
        labels = {
            measurement_labels[oid]
            for oid in track.observation_ids
            if measurement_labels[oid] is not None
        }
        multiplicity.update(labels)  # type: ignore[arg-type]
        mixed += len(labels) > 1
        singleton += len(track.observation_ids) == 1
    return {
        "track_count": len(tracks),
        "fragmented_track_count": sum(t.status == "FRAGMENTED" for t in tracks),
        "single_measurement_track_count": singleton,
        "mixed_known_identity_tracks": mixed,
        "known_actor_produced_track_multiplicity": dict(Counter(multiplicity.values())),
        "condition": "Detected labeled contacts only; not full actor fragmentation/recall",
    }


def evaluate(output: Path) -> dict[str, Any]:
    if (output / "comparison.json").exists():
        raise ValueError("completed evaluation is immutable; rebuild into a new output")
    package, registry, manifest, policy = load(output)
    # Validate every variant/mode first; no GT is opened until this completes.
    states = {
        (v, m): frozen(output, v, m, manifest, package, registry) for v in VARIANTS for m in MODES
    }
    result: dict[str, Any] = {
        "schema_version": "accuracy.comparison.v2",
        "experiment_id": manifest["experiment_id"],
        "source_run_id": package.run_id,
        "split": package.split,
        "manifest_sha256": digest(manifest),
        "config_sha256": manifest["config_sha256"],
        "dataset_sha256": package.dataset_sha256,
        "evaluator_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "evaluator_policy": {
            "legacy_contact_and_truth_population": "UNCHANGED",
            "unknown_behavior": "UNRESOLVED_WITH_FULL_TRUTH_FN_DENOMINATOR",
            "rank_ties": "Legacy stable hypothesis ref ordering; RGB appearance keeps cutoff ties",
            "global_IDF1": "N/A; no global identity assignment",
        },
        "formal_phase1_acceptance": False,
        "test_is_sealed_holdout": False,
        "variants": {},
        "comparison": {},
    }
    for variant in VARIANTS:
        result["variants"][variant] = {}
        for mode in MODES:
            state = states[variant, mode]
            summary = evaluate_local_pilot(
                isolated_package(package, output / "evaluation_inputs" / variant / mode),
                state.perception,
                state.inference,
                receipt=state.receipt,
                events=state.events.events,
                events_sha256=digest([e.model_dump(mode="json") for e in state.events.events]),
                behavior_bundle=state.events,
            )
            truth = ResearchTruth.model_validate_json(package.simulation_export_path.read_bytes())
            measurement_labels, labels, _, detail = _labels(
                state.perception, state.inference, truth
            )
            _, physics_pool, _ = _inventory(package, state.inference)
            truth_pairs = {
                p for p in physics_pool if labels[p[0]] is not None and labels[p[0]] == labels[p[1]]
            }
            # Keep the original candidate-diagnostic confusion beside supported-claim evaluation.
            summary["behavior_unmasked_candidate_diagnostic"] = summary["behavior"]
            summary["behavior"] = supported_behavior(state, truth, labels)
            summary["weighted_fixed_pool_feature_ablations"] = feature_ablations(
                state.inference,
                labels,
                truth_pairs,
                association_config(policy, variant),
            )
            summary["pixel_population"] = pixel_population(state, measurement_labels)
            root = output / variant / mode
            if (root / "appearance.json").exists():
                from amidst.research_accuracy.appearance_evaluation import evaluate_appearance

                appearance = RGBDescriptorBundle.model_validate_json(
                    (root / "appearance.json").read_bytes()
                )
                import json

                source_manifest = json.loads(
                    (Path(manifest["source_locator"]) / "manifest.json").read_text()
                )
                appearance_report, appearance_detail = evaluate_appearance(
                    package,
                    state.perception,
                    state.inference,
                    appearance,
                    measurement_labels,
                    registry,
                    source_manifest,
                )
                summary["pure_track_appearance_comparison"] = appearance_report
                _save(
                    output / "evaluation" / variant / mode / "appearance_debug.json",
                    appearance_detail,
                )
            summary["experiment_id"] = manifest["experiment_id"]
            summary["runtime_config_sha256"] = manifest["config_sha256"]
            summary["variant"] = variant
            summary["mode"] = mode
            _save(output / "evaluation" / variant / mode / "summary.json", summary)
            _save(output / "evaluation" / variant / mode / "pixel_debug.json", detail)
            result["variants"][variant][mode] = summary
        selected = result["variants"][variant]["photos_only"]
        baseline = result["variants"]["baseline"]["photos_only"]
        result["comparison"][variant] = {
            "ID_switches": selected["pixels_and_local_identity"]["within_local_track_id_switches"],
            "contact_recall": selected["pixels_and_local_identity"][
                "one_to_one_visible_contact_recall"
            ],
            "ground_RMS_m": selected["pixels_and_local_identity"]["ground_contact_error_m"]["rms"],
            "tracks": selected["pixel_population"]["track_count"],
            "pairs": selected["retrieval"]["retrieved_pair_count"],
            "eligible_pair_positives": selected["retrieval"]["same_identity_eligible_pair_count"],
            "candidate_pool_sha256": selected["weighted_fixed_pool_feature_ablations"]["full"][
                "candidate_pool_sha256"
            ],
            "same_baseline_pool": selected["weighted_fixed_pool_feature_ablations"]["full"][
                "candidate_pool_sha256"
            ]
            == baseline["weighted_fixed_pool_feature_ablations"]["full"]["candidate_pool_sha256"],
            "pair_precision": selected["association_all_provisional_hypotheses"][
                "same_identity_eligible_pair_precision"
            ],
            "pair_recall": selected["association_all_provisional_hypotheses"][
                "same_identity_eligible_pair_recall"
            ],
            "rank_recall_at_k": selected["weighted_fixed_pool_feature_ablations"]["full"][
                "identity_candidate_recall_at_k"
            ],
            "visible_behavior": selected["behavior"]["groups"]["visible_supported"]["per_kind"],
            "unknown_count": selected["behavior"]["evidence_unknown_count"],
            "visible_candidate_count": selected["behavior"]["visible_candidate_count"],
        }
    _save(output / "comparison.json", result)
    return result
