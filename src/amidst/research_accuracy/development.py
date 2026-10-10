"""Rebuild the declared DEVELOPMENT-only fixed-pool association selection.

Inference/config/receipt bytes for every option are saved and verified before the
separate evaluation section reads development truth. No historical output is edited.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

from amidst.engineering.access import FreezeReceipt
from amidst.engineering.local_association import InferenceBundle, content_sha256
from amidst.engineering.local_evaluation import ResearchTruth, _inventory, _labels, _link_metrics
from amidst.engineering.local_pilot import _load, frozen_mode
from amidst.research_accuracy.association import (
    AssociationConfig,
    Feature,
    build_appearance_bundle,
    improve_association,
    rank_association_hypotheses,
)

SELECTED = "v2_rgb_space_legacy_time"


def development_options() -> dict[str, AssociationConfig]:
    """A declared comparison set; no test result chooses or mutates these options."""
    return {
        "legacy": AssociationConfig(
            appearance_mode="LEGACY_MEAN_RGB",
            spatial_mode="LEGACY_PROXIMITY",
            time_mode="LEGACY_DIRECTION",
        ),
        "appearance_only_changed": AssociationConfig(
            spatial_mode="LEGACY_PROXIMITY",
            time_mode="LEGACY_DIRECTION",
        ),
        "space_only_changed": AssociationConfig(
            appearance_mode="LEGACY_MEAN_RGB",
            time_mode="LEGACY_DIRECTION",
        ),
        "time_only_changed": AssociationConfig(
            appearance_mode="LEGACY_MEAN_RGB",
            spatial_mode="LEGACY_PROXIMITY",
        ),
        "v2_equal_weights": AssociationConfig(),
        "v2_soft_weights": AssociationConfig(spatial_weight=0.15, time_weight=0.35),
        "v2_without_space_weight": AssociationConfig(spatial_weight=0, time_weight=0.35),
        "v2_appearance_weight_only": AssociationConfig(spatial_weight=0, time_weight=0),
        SELECTED: AssociationConfig(time_mode="LEGACY_DIRECTION"),
        "v2_rgb_time_legacy_space": AssociationConfig(spatial_mode="LEGACY_PROXIMITY"),
    }


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # A rerun uses a new output directory, preserving all frozen bytes.
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _ranking_metrics(
    inference: InferenceBundle,
    config: AssociationConfig,
    labels: dict[str, str | None],
    truth_pairs: set[tuple[str, str]],
) -> dict[str, object]:
    results: dict[str, object] = {}
    comparisons: list[tuple[str, Feature | None, Feature | None]] = [("full", None, None)]
    for feature in ("SPACE", "TIME", "APPEARANCE"):
        comparisons.append(("without_" + feature.lower(), feature, None))
        comparisons.append(("only_" + feature.lower(), None, feature))
    queries = {pair[0] for pair in truth_pairs}
    for name, removed, only in comparisons:
        grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for hypothesis in rank_association_hypotheses(
            inference,
            config=config,
            removed_feature=removed,
            feature_only=only,
        ):
            first, second = hypothesis.segment_ids
            grouped[first].append((first, second))
        top1 = {rows[0] for rows in grouped.values() if rows}
        metrics = _link_metrics(top1, truth_pairs, labels)
        hits = {
            str(k): sum(
                any(pair in truth_pairs for pair in grouped.get(query, ())[:k]) for query in queries
            )
            for k in (1, 3, 5)
        }
        metrics.update(
            {
                "identity_candidate_recall_at_k": {
                    key: count / len(queries) if queries else None for key, count in hits.items()
                },
                "identity_candidate_hit_counts": hits,
                "eligible_query_count": len(queries),
                "candidate_pool_sha256": inference.association_pool_sha256,
                "hard_physics_preserved": True,
                "scores_are_probabilities": False,
                "removed_feature": removed,
                "feature_only": only,
            }
        )
        results[name] = metrics
    return results


def develop_association(
    source: Path, output: Path, receipt_path: Path | None = None
) -> dict[str, object]:
    """Freeze then evaluate the fixed declared options on a validated development run."""
    package, _, _, manifest = _load(source)
    if package.split != "development":
        raise ValueError("association policy selection requires DEVELOPMENT, never test")
    if output.exists():
        raise FileExistsError("development selection output must be a new empty directory")
    if receipt_path is not None and receipt_path.exists():
        raise FileExistsError("curated development receipt must not overwrite history")
    perception, baseline, _, old_receipt = frozen_mode(source, "photos_only", manifest)
    options = development_options()
    output.mkdir(parents=True)
    freezes: dict[str, dict[str, str]] = {}
    for name, config in options.items():
        result = improve_association(perception, baseline, package.frames, config)
        if (
            result.snapshot != baseline.snapshot
            or result.association_pool_sha256 != baseline.association_pool_sha256
        ):
            raise ValueError("development comparison changed the canonical fixed pool or Graph")
        binding = old_receipt.binding.model_copy(update={"config_sha256": content_sha256(config)})
        receipt = FreezeReceipt.create(binding, result, perception.model_dump(mode="json"))
        descriptor = build_appearance_bundle(perception, baseline, package.frames, config)
        _write(output / name / "inference.json", result.model_dump(mode="json"))
        _write(output / name / "config.json", config.model_dump(mode="json"))
        _write(output / name / "freeze.json", receipt.model_dump(mode="json"))
        _write(output / name / "appearance.json", descriptor.model_dump(mode="json"))
        freezes[name] = {
            "inference_sha256": receipt.inference_sha256,
            "receipt_sha256": receipt.receipt_sha256,
            "config_sha256": content_sha256(config),
            "appearance_sha256": content_sha256(descriptor),
        }
    _write(
        output / "freeze_inventory.json",
        {
            "schema_version": "research.association-development-freeze.v2",
            "options": freezes,
            "source_manifest_sha256": sha256((source / "manifest.json").read_bytes()).hexdigest(),
            "baseline_receipt_sha256": old_receipt.receipt_sha256,
            "candidate_pool_sha256": baseline.association_pool_sha256,
        },
    )
    # All saved inference receipts are independently revalidated before truth opens.
    reloaded = {}
    for name, config in options.items():
        result = InferenceBundle.model_validate_json(
            (output / name / "inference.json").read_bytes()
        )
        receipt = FreezeReceipt.model_validate_json((output / name / "freeze.json").read_bytes())
        if not receipt.verify(receipt.binding, result, perception.model_dump(mode="json")) or (
            receipt.binding.config_sha256 != content_sha256(config)
            or content_sha256(result) != freezes[name]["inference_sha256"]
        ):
            raise ValueError("development inference/config receipt mismatch")
        reloaded[name] = result
    # Independent DEVELOPMENT EVALUATION boundary. Runtime association never reads
    # this sidecar; no truth labels are serialized into inference or curated receipts.
    truth_bytes = package.simulation_export_path.read_bytes()
    truth = ResearchTruth.model_validate_json(truth_bytes)
    if (
        truth.split != "development"
        or truth.run_id != package.run_id
        or truth.model_id != package.model_id
        or truth.dataset_sha256 != package.dataset_sha256
        or truth.config_sha256 != package.config_sha256
        or truth.boundary != "EVALUATION_DEBUG_ONLY"
    ):
        raise ValueError("development truth source/config/run binding mismatch")
    _, labels, pixels, _ = _labels(perception, baseline, truth)
    _, pool, _ = _inventory(package, baseline)
    true_pairs = {
        pair for pair in pool if labels[pair[0]] is not None and labels[pair[0]] == labels[pair[1]]
    }
    results = {
        name: _ranking_metrics(reloaded[name], config, labels, true_pairs)
        for name, config in options.items()
    }
    selected = build_appearance_bundle(perception, baseline, package.frames, options[SELECTED])
    summary: dict[str, object] = {
        "schema_version": "research.association-development-selection.v2",
        "status": "DEVELOPMENT_ONLY_POLICY_SELECTION",
        "split": "development",
        "scope": baseline.scope.model_dump(mode="json"),
        "dataset_sha256": perception.input_manifest_sha256,
        "producer_sha256": perception.producer_sha256,
        "candidate_pool_sha256": baseline.association_pool_sha256,
        "baseline_inference_sha256": old_receipt.inference_sha256,
        "baseline_receipt_sha256": old_receipt.receipt_sha256,
        "association_algorithm_sha256": sha256(
            Path(__file__).with_name("association.py").read_bytes()
        ).hexdigest(),
        "selection_algorithm_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "evaluation_truth_sha256": sha256(truth_bytes).hexdigest(),
        "selected_option": SELECTED,
        "selected_config": options[SELECTED].model_dump(mode="json"),
        "selection_reason": "RGB + feasibility-ratio space retained legacy time and equal weights. "
        "Both RGB+space and RGB+time hit all 8 development queries; the selected policy "
        "avoids adding a new temporal scale. The all-new combination and weighted options "
        "were retained as regressions, not used to promise test improvement.",
        "measurement_count": len(perception.measurements),
        "segment_count": len(baseline.local_record_maps),
        "pair_count": baseline.pair_count,
        "pixels_and_local_identity": pixels,
        "freezes": freezes,
        "fixed_pool_comparisons": results,
        "appearance_quality": {
            "unavailable_crop_count": sum(
                row.vector is None for row in selected.measurement_descriptors
            ),
            "uncertain_segment_count": sum(
                row.status == "UNCERTAIN" for row in selected.segment_descriptors
            ),
            "explicit_excluded_crop_count": sum(
                len(row.excluded_observation_ids) for row in selected.segment_descriptors
            ),
        },
        "limitations": [
            "Selection used development evaluation only, before test inference freeze.",
            "Eight queries are conditional on detected and evaluable produced segments.",
            "This fixed-pool comparison does not measure undetected people or global identity.",
            "The test fixture has previously supported integration regression, not sealed holdout.",
            "Synthetic accuracy does not establish cross-place generalization or formal readiness.",
        ],
    }
    _write(output / "evaluation.json", summary)
    if receipt_path is not None:
        _write(receipt_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    result = develop_association(args.source, args.output, args.receipt)
    print(json.dumps({key: result[key] for key in ("status", "selected_option", "pair_count")}))


if __name__ == "__main__":
    main()
