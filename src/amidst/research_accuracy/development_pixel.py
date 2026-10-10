"""Freeze/replay fixed-detector pixel ablations on DEVELOPMENT only.

Build never opens GT. Evaluation loads and verifies every saved receipt before
reading the one independently bound development truth sidecar. Defaults and
single-feature removals are declared in code; this tool never selects parameters.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from amidst.engineering import perception as detector
from amidst.engineering.access import FreezeReceipt, RunBinding, digest
from amidst.engineering.local_association import AssociationPolicy, InferenceBundle, build_inference
from amidst.engineering.local_evaluation import ResearchTruth, _labels, evaluator_policy
from amidst.engineering.local_index import RetrievalPolicy, ScopedTopology
from amidst.engineering.local_pilot import _load, _save, algorithm_hashes, frozen_mode
from amidst.engineering.perception import PerceptionResult
from amidst.engineering.registry import LocationRegistry
from amidst.engineering.research_scene import ResearchPackage
from amidst.research_accuracy import pixel

VERSION = "development-fixed-detector-pixel-ablations-v2"


def ablation_configs() -> dict[str, pixel.PixelContinuityConfig]:
    return {
        "full": pixel.PixelContinuityConfig(),
        "greedy": pixel.PixelContinuityConfig(assignment="greedy"),
        "no_velocity": pixel.PixelContinuityConfig(use_velocity=False),
        "no_appearance": pixel.PixelContinuityConfig(appearance_weight=0),
        "no_shape": pixel.PixelContinuityConfig(shape_weight=0),
        "no_quarantine": pixel.PixelContinuityConfig(merge_quarantine=False),
    }


def _algorithms() -> dict[str, str]:
    return algorithm_hashes() | {
        "research_accuracy/pixel.py": sha256(Path(pixel.__file__).read_bytes()).hexdigest(),
        "research_accuracy/development_pixel.py": sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def _development_source(
    source: Path,
) -> tuple[ResearchPackage, LocationRegistry, ScopedTopology, dict[str, Any]]:
    # Reject test before loading its media, frozen results or any sidecar.
    header = json.loads((source / "package.json").read_bytes())
    if header.get("split") != "development":
        raise ValueError("pixel ablations require DEVELOPMENT; test sources are forbidden")
    package, registry, topology, manifest = _load(source)
    if package.split != "development" or manifest["split"] != "development":
        raise ValueError("development source split binding mismatch")
    return package, registry, topology, manifest


def _contacts(perception: PerceptionResult) -> str:
    """Ignore changed IDs/assignment uncertainty; bind every original detected pixel."""
    return digest(sorted([
        (row.camera_id, row.timestamp, row.frame_ref, row.input_sha256,
         row.bbox_xyxy, row.contact_pixel, row.appearance)
        for row in perception.measurements
    ]))


def _binding(
    package: ResearchPackage, registry: LocationRegistry, producer: str, config_sha: str,
) -> RunBinding:
    return RunBinding(
        place_id=package.scope.place_id, model_id=package.model_id, model_revision=package.revision,
        source_ref=package.scope.source_ref, spatial_context_id=package.scope.spatial_context_id,
        run_id=package.run_id, clock_id=package.scope.clock_id, observation_mode="photos_only",
        registry_version=VERSION, dataset_sha256=package.dataset_sha256, config_sha256=config_sha,
        producer_sha256=producer, registry_sha256=registry.sha256,
        media_sha256=digest([(row.media_ref, row.sha256) for row in registry.frames]),
    )


def build(source: Path, output: Path) -> dict[str, Any]:
    """Freeze all policies, detector contacts, inferences and receipts without GT."""
    source, output = source.resolve(), output.resolve()
    package, registry, topology, original = _development_source(source)
    baseline = detector.produce_perception(
        package.frames, model_id=package.model_id, run_id=package.run_id,
    )
    old, _, _, _ = frozen_mode(source, "photos_only", original)
    if digest(baseline) != digest(old):
        raise ValueError("development v1 detector replay differs from its source freeze")
    configs = {name: config.model_dump(mode="json") for name, config in ablation_configs().items()}
    algorithms = _algorithms()
    config_sha = digest({"version": VERSION, "configs": configs, "algorithms": algorithms,
                         "source_config_sha256": original["config_sha256"]})
    _save(output / "configs.json", configs)
    states = {"v1": baseline} | {
        name: pixel.reassociate_perception_v2(baseline, config=config)
        for name, config in ablation_configs().items()
    }
    contacts = _contacts(baseline)
    manifest: dict[str, Any] = {
        "schema_version": "accuracy.pixel-development-freeze.v2", "version": VERSION,
        "source_locator": str(source), "source_manifest_sha256": digest(original),
        "source_package_sha256": digest(package), "split": "development",
        "run_id": package.run_id, "dataset_sha256": package.dataset_sha256,
        "source_sha256": package.source_sha256, "context_sha256": package.context_sha256,
        "clock_id": package.scope.clock_id, "units": "METRES_SYNTHETIC_SECONDS",
        "algorithms": algorithms, "config_sha256": config_sha, "configs_sha256": digest(configs),
        "detector_contact_population_sha256": contacts,
        "source_frozen_v1_perception_sha256": digest(old),
        "frame_count": len(package.frames), "measurement_count": len(baseline.measurements),
        "observation_mode": "photos_only", "raw_copied": False,
        "gt_opened_during_build": False, "parameter_selection": "UNCHANGED_GENERIC_DEFAULTS",
        "variants": {},
    }
    for name, perception in states.items():
        if _contacts(perception) != contacts:
            raise ValueError("pixel ablation changed the fixed detector contact population")
        inference = build_inference(
            perception, scope=package.scope, context=package.context,
            policy=AssociationPolicy.model_validate(original["association_policy"]),
            topology=topology,
            retrieval_policy=RetrievalPolicy.model_validate(original["retrieval_policy"]),
        )
        receipt = FreezeReceipt.create(
            _binding(package, registry, perception.producer_sha256, config_sha),
            inference, perception.model_dump(mode="json"),
        )
        for filename, document in (("perception", perception), ("inference", inference),
                                   ("receipt", receipt)):
            _save(output / name / (filename + ".json"), document)
        manifest["variants"][name] = {
            "perception_sha256": digest(perception), "inference_sha256": digest(inference),
            "receipt_sha256": receipt.receipt_sha256, "producer_sha256": perception.producer_sha256,
            "producer_version": perception.producer_version,
            "candidate_pool_sha256": inference.association_pool_sha256,
        }
    # This final manifest certifies that every ablation completed before evaluation.
    _save(output / "manifest.json", manifest)
    return manifest


def _load_frozen(
    output: Path,
) -> tuple[ResearchPackage, dict[str, Any], dict[str, tuple[PerceptionResult, InferenceBundle]]]:
    manifest = json.loads((output / "manifest.json").read_bytes())
    if (manifest["schema_version"] != "accuracy.pixel-development-freeze.v2"
            or manifest["version"] != VERSION or manifest["split"] != "development"
            or manifest["algorithms"] != _algorithms()):
        raise ValueError("development pixel freeze/source version mismatch")
    package, registry, _, original = _development_source(Path(manifest["source_locator"]))
    configs = json.loads((output / "configs.json").read_bytes())
    expected_configs = {name: config.model_dump(mode="json")
                        for name, config in ablation_configs().items()}
    expected_config_sha = digest({"version": VERSION, "configs": configs,
                                  "algorithms": _algorithms(),
                                  "source_config_sha256": original["config_sha256"]})
    if (configs != expected_configs or digest(configs) != manifest["configs_sha256"]
            or manifest["config_sha256"] != expected_config_sha
            or manifest["source_manifest_sha256"] != digest(original)
            or manifest["source_package_sha256"] != digest(package)
            or manifest["dataset_sha256"] != package.dataset_sha256
            or manifest["run_id"] != package.run_id
            or manifest["source_sha256"] != package.source_sha256
            or manifest["context_sha256"] != package.context_sha256
            or manifest["clock_id"] != package.scope.clock_id
            or set(manifest["variants"]) != {"v1", *expected_configs}):
        raise ValueError("development pixel config/source freeze mismatch")
    states = {}
    for name, hashes in manifest["variants"].items():
        root = output / name
        perception = PerceptionResult.model_validate_json((root / "perception.json").read_bytes())
        inference = InferenceBundle.model_validate_json((root / "inference.json").read_bytes())
        receipt = FreezeReceipt.model_validate_json((root / "receipt.json").read_bytes())
        producer = (sha256(Path(detector.__file__).read_bytes()).hexdigest() if name == "v1"
                    else pixel.producer_sha256(ablation_configs()[name]))
        expected_binding = _binding(package, registry, perception.producer_sha256,
                                    manifest["config_sha256"])
        if (not receipt.verify(expected_binding, inference, perception.model_dump(mode="json"))
                or digest(perception) != hashes["perception_sha256"]
                or digest(inference) != hashes["inference_sha256"]
                or receipt.receipt_sha256 != hashes["receipt_sha256"]
                or perception.producer_sha256 != hashes["producer_sha256"]
                or perception.producer_sha256 != producer
                or perception.producer_version != hashes["producer_version"]
                or perception.model_id != package.model_id or perception.run_id != package.run_id
                or perception.input_manifest_sha256 != package.dataset_sha256
                or inference.producer_sha256 != perception.producer_sha256
                or inference.association_pool_sha256 != hashes["candidate_pool_sha256"]
                or inference.input_manifest_sha256 != package.dataset_sha256
                or inference.scope != package.scope
                or inference.static_context_sha256 != digest(package.context)
                or _contacts(perception) != manifest["detector_contact_population_sha256"]):
            raise ValueError("development pixel receipt/input mismatch before truth")
        states[name] = (perception, inference)
    if digest(states["v1"][0]) != manifest["source_frozen_v1_perception_sha256"]:
        raise ValueError("development pixel original detector freeze mismatch")
    return package, manifest, states


def evaluate(output: Path, *, curated: Path | None = None) -> dict[str, Any]:
    """Verify all saved inferences first; then open DEVELOPMENT truth and save evidence."""
    output = output.resolve()
    package, manifest, states = _load_frozen(output)
    truth_bytes = package.simulation_export_path.read_bytes()
    truth = ResearchTruth.model_validate_json(truth_bytes)
    expected_frames = {row.media_ref: (row.camera_id, row.timestamp) for row in package.frames}
    if (truth.schema_version != "local.camera.truth.v1" or truth.boundary != "EVALUATION_DEBUG_ONLY"
            or truth.split != "development" or truth.dataset_sha256 != package.dataset_sha256
            or truth.config_sha256 != package.config_sha256 or truth.run_id != package.run_id
            or truth.model_id != package.model_id or len(truth.ground_truth) != len(expected_frames)
            or {row.frame_ref: (row.camera_id, row.timestamp) for row in truth.ground_truth}
            != expected_frames
            or any(len({a.actor_identity for a in row.render_annotations})
                   != len(row.render_annotations) for row in truth.ground_truth)):
        raise ValueError("development pixel truth dataset/config/clock inventory mismatch")
    result: dict[str, Any] = {
        "schema_version": "accuracy.development-pixel-ablations.v2", "version": VERSION,
        "artifact_policy": "PUBLIC_ALLOWED_AGGREGATE_RECEIPT", "split": "development",
        "run_id": package.run_id, "dataset_sha256": package.dataset_sha256,
        "source_sha256": package.source_sha256, "context_sha256": package.context_sha256,
        "clock_id": package.scope.clock_id, "units": "METRES_SYNTHETIC_SECONDS",
        "source_manifest_sha256": manifest["source_manifest_sha256"],
        "freeze_manifest_sha256": digest(manifest), "config_sha256": manifest["config_sha256"],
        "configs_sha256": manifest["configs_sha256"], "algorithms": manifest["algorithms"],
        "evaluation_truth_sha256": sha256(truth_bytes).hexdigest(),
        "evaluator_policy": evaluator_policy(), "all_receipts_verified_before_gt": True,
        "same_detector_contacts": True, "detector_contact_population_sha256":
        manifest["detector_contact_population_sha256"],
        "frame_count": manifest["frame_count"], "measurement_count": manifest["measurement_count"],
        "source_versions": {"detector": detector.PRODUCER_VERSION,
                            "continuity": pixel.PRODUCER_VERSION},
        "configs": {name: config.model_dump(mode="json")
                    for name, config in ablation_configs().items()},
        "parameter_selection": "UNCHANGED_GENERIC_DEFAULTS; no test truth read or tuning",
        "formal_phase1_acceptance": False, "full_actor_recall": "N/A", "variants": {},
    }
    for name, (perception, inference) in states.items():
        labels, _, metrics, details = _labels(perception, inference, truth)
        multiplicity: Counter[str] = Counter()
        mixed = 0
        for track in perception.tracks:
            known = {labels[ref] for ref in track.observation_ids if labels[ref] is not None}
            multiplicity.update(value for value in known if value is not None)
            mixed += len(known) > 1
        result["variants"][name] = manifest["variants"][name] | {
            "pixels_and_local_identity": metrics,
            "track_count": len(perception.tracks),
            "fragmented_track_count": sum(row.status == "FRAGMENTED" for row in perception.tracks),
            "single_measurement_track_count": sum(len(row.timestamps) == 1
                                                  for row in perception.tracks),
            "merged_or_partial_measurement_count": sum(row.status == "MERGED_OR_PARTIAL"
                                                       for row in perception.measurements),
            "mixed_known_identity_track_count": mixed,
            "known_actor_produced_track_multiplicity": dict(Counter(multiplicity.values())),
            "association_pair_count": inference.pair_count,
            "changed_candidate_pool": inference.association_pool_sha256
            != states["v1"][1].association_pool_sha256,
        }
        _save(output / "evaluation/debug" / (name + ".json"), {
            "boundary": "LOCAL_EVALUATION_DEBUG_ONLY", "pixel_identity_assignment": details,
        })
    _save(output / "pixel_ablations.json", result)
    if curated is not None:
        _save(curated, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "evaluate"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--curated", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        if args.source is None:
            parser.error("build requires --source")
        result = build(args.source, args.output)
        print(json.dumps({"frozen": True, "manifest_sha256": digest(result)}))
    else:
        result = evaluate(args.output, curated=args.curated)
        print(json.dumps({name: {"switches": row["pixels_and_local_identity"][
            "within_local_track_id_switches"], "tracks": row["track_count"]}
            for name, row in result["variants"].items()}))


if __name__ == "__main__":
    main()
