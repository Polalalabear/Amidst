"""Replay v1 bytes and evaluate only into a new isolated evidence directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.local_association import build_inference
from amidst.engineering.local_behavior import compose_local_behaviors
from amidst.engineering.local_evaluation import evaluate_local_pilot
from amidst.engineering.local_index import RetrievalPolicy
from amidst.engineering.local_pilot import MODES, _load, _save, frozen_mode
from amidst.engineering.perception import produce_perception
from amidst.engineering.research_scene import ResearchPackage


def isolated_package(package: ResearchPackage, output: Path) -> ResearchPackage:
    """Evaluator-only symlink: share truth bytes, never copy or rewrite source raw."""
    path = output.resolve() / "simulation/export/ground_truth.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    source = package.simulation_export_path.resolve()
    if path.is_symlink():
        if path.resolve() != source:
            raise ValueError("evaluation truth locator conflict")
    elif path.exists():
        raise ValueError("evaluation input must be an immutable source symlink")
    else:
        path.symlink_to(source)
    return package.model_copy(update={"simulation_export_path": path})


def reproduce_baseline(source: Path, output: Path) -> dict[str, Any]:
    package, _, topology, manifest = _load(source)
    policy = manifest["association_policy"]
    from amidst.engineering.local_association import AssociationPolicy
    from amidst.engineering.local_behavior import BehaviorConfig

    behavior = BehaviorConfig.model_validate_json((source / "behavior_config.json").read_bytes())
    perception = produce_perception(
        package.frames, model_id=package.model_id, run_id=package.run_id,
    )
    inference = build_inference(
        perception, scope=package.scope, context=package.context,
        policy=AssociationPolicy.model_validate(policy), topology=topology,
        retrieval_policy=RetrievalPolicy.model_validate(manifest["retrieval_policy"]),
    )
    events = compose_local_behaviors(inference, behavior, tracks=perception.tracks)
    result: dict[str, Any] = {
        "schema_version": "accuracy.baseline-replay.v1", "run_id": package.run_id,
        "split": package.split, "source_manifest_sha256": digest(manifest),
        "dataset_sha256": package.dataset_sha256, "modes": {},
        "formal_phase1_acceptance": False, "raw_copied": False,
    }
    for mode in MODES:
        old_pixel, old_inference, old_events, receipt = frozen_mode(source, mode, manifest)
        checks = {
            "pixel": digest(perception) == digest(old_pixel),
            "inference": digest(inference) == digest(old_inference),
            "events": digest(events) == digest(old_events),
        }
        if not all(checks.values()):
            raise ValueError(f"v1 replay mismatch: {checks}")
        for name, document in (("perception", perception), ("inference", inference),
                               ("events", events)):
            path = output / f"{name}_{mode}.json"
            _save(path, document)
            checks[name + "_bytes"] = path.read_bytes() == (
                source / f"{name}_{mode}.json").read_bytes()
        if not all(checks.values()):
            raise ValueError(f"v1 frozen byte replay mismatch: {checks}")
        evaluation = evaluate_local_pilot(
            isolated_package(package, output / mode), perception, inference, receipt=receipt,
            events=events.events, events_sha256=digest([e.model_dump(mode="json")
                                                       for e in events.events]),
            behavior_bundle=events,
        )
        _save(output / f"evaluation_{mode}.json", evaluation)
        result["modes"][mode] = {
            "byte_content_reproduction": checks,
            "pixel_sha256": digest(perception), "inference_sha256": digest(inference),
            "events_sha256": digest(events), "evaluation_sha256": digest(evaluation),
            "pixels": evaluation["pixels_and_local_identity"],
            "association": evaluation["association_all_provisional_hypotheses"],
            "ablations": evaluation["fixed_pool_feature_ablations"],
            "retrieval": evaluation["retrieval"], "behavior": evaluation["behavior"],
        }
    _save(output / "baseline_receipt.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = reproduce_baseline(args.source.resolve(), args.output.resolve())
    print(json.dumps({"run_id": result["run_id"], "replayed": True,
                      "receipt": str(args.output / "baseline_receipt.json")}))


if __name__ == "__main__":
    main()
