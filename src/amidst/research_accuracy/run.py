"""Build/load immutable v2 experiments using one existing RGB materialization."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from amidst.engineering.access import FreezeReceipt, Mode, RunBinding, digest
from amidst.engineering.local_association import AssociationPolicy, InferenceBundle, build_inference
from amidst.engineering.local_behavior import (
    BehaviorConfig,
    LocalBehaviorBundle,
    compose_local_behaviors,
)
from amidst.engineering.local_index import RetrievalPolicy
from amidst.engineering.local_pilot import MODES, _load, _save, algorithm_hashes
from amidst.engineering.perception import PerceptionResult, produce_perception
from amidst.engineering.registry import LocationRegistry
from amidst.engineering.research_scene import ResearchPackage
from amidst.research_accuracy.association import (
    AssociationConfig,
    build_appearance_bundle,
    improve_association,
)
from amidst.research_accuracy.behavior import (
    BehaviorEvidencePolicy,
    behavior_config_sha256,
    compose_behaviors_v2,
)
from amidst.research_accuracy.pixel import PixelContinuityConfig, produce_perception_v2

Variant = Literal[
    "baseline",
    "pixel_only",
    "appearance_only",
    "prior_only",
    "features_full",
    "behavior_only",
    "motion_diagnostic",
    "end_to_end",
]
VARIANTS: tuple[Variant, ...] = (
    "baseline",
    "pixel_only",
    "appearance_only",
    "prior_only",
    "features_full",
    "behavior_only",
    "motion_diagnostic",
    "end_to_end",
)
VERSION = "local-camera-accuracy-v2"


def research_algorithms() -> dict[str, str]:
    names = (
        "pixel.py",
        "association.py",
        "behavior.py",
        "run.py",
        "adapter.py",
        "evaluation.py",
        "evidence.py",
        "appearance_evaluation.py",
    )
    return algorithm_hashes() | {
        "research_accuracy/" + name: sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
        for name in names
    }


def default_policy() -> dict[str, Any]:
    return {
        "schema_version": "accuracy.policy.v2",
        "version": VERSION,
        "pixel": PixelContinuityConfig().model_dump(mode="json"),
        "association": AssociationConfig().model_dump(mode="json"),
        "behavior": BehaviorEvidencePolicy().model_dump(mode="json"),
        "variants": list(VARIANTS),
        "selection": "DEVELOPMENT_ONLY; test is a previously used integration regression set",
    }


def validate_policy(policy: dict[str, Any]) -> None:
    if set(policy) != set(default_policy()) or policy["schema_version"] != "accuracy.policy.v2":
        raise ValueError("accuracy policy schema mismatch")
    if policy["version"] != VERSION or tuple(policy["variants"]) != VARIANTS:
        raise ValueError("accuracy policy/version/variants mismatch")
    PixelContinuityConfig.model_validate(policy["pixel"])
    AssociationConfig.model_validate(policy["association"])
    BehaviorEvidencePolicy.model_validate(policy["behavior"])


def association_config(policy: dict[str, Any], variant: Variant) -> AssociationConfig:
    config = AssociationConfig.model_validate(policy["association"])
    if variant == "appearance_only":
        return config.model_copy(
            update={"spatial_mode": "LEGACY_PROXIMITY", "time_mode": "LEGACY_DIRECTION"}
        )
    if variant == "motion_diagnostic":
        return config.model_copy(update={"time_mode": "SPEED_RESIDUAL"})
    if variant == "prior_only":
        return config.model_copy(update={"appearance_mode": "LEGACY_MEAN_RGB"})
    return config


@dataclass(frozen=True)
class FrozenVariant:
    perception: PerceptionResult
    inference: InferenceBundle
    events: LocalBehaviorBundle
    receipt: FreezeReceipt


def _produce(
    package: ResearchPackage, variant: Variant, policy: dict[str, Any]
) -> PerceptionResult:
    if variant in ("pixel_only", "end_to_end"):
        return produce_perception_v2(
            package.frames,
            model_id=package.model_id,
            run_id=package.run_id,
            config=PixelContinuityConfig.model_validate(policy["pixel"]),
        )
    return produce_perception(package.frames, model_id=package.model_id, run_id=package.run_id)


def build(
    source: Path, output: Path, policy: dict[str, Any], *, experiment_id: str
) -> dict[str, Any]:
    """Never opens simulation/export, GT, recipe or reference annotations."""
    validate_policy(policy)
    if not experiment_id or "/" in experiment_id or ".." in experiment_id:
        raise ValueError("finite experiment identity required")
    source, output = source.resolve(), output.resolve()
    if output == source or (output.exists() and any(output.iterdir())):
        raise ValueError("research build requires a new empty output")
    package, registry, topology, source_manifest = _load(source)
    behavior = BehaviorConfig.model_validate_json((source / "behavior_config.json").read_bytes())
    algorithms = research_algorithms()
    config_sha = digest(
        {
            "policy": policy,
            "algorithms": algorithms,
            "source_config_sha256": source_manifest["config_sha256"],
        }
    )
    _save(output / "policy.json", policy)
    manifest: dict[str, Any] = {
        "schema_version": "accuracy.frozen-run.v2",
        "experiment_id": experiment_id,
        "source_run_id": package.run_id,
        "split": package.split,
        "version": VERSION,
        "source_locator": str(source),
        "source_manifest_sha256": digest(source_manifest),
        "source_package_sha256": digest(package),
        "dataset_sha256": package.dataset_sha256,
        "source_sha256": package.source_sha256,
        "context_sha256": package.context_sha256,
        "clock_id": package.scope.clock_id,
        "unit": "METRES_SYNTHETIC_SECONDS",
        "config_sha256": config_sha,
        "policy_sha256": digest(policy),
        "algorithms": algorithms,
        "variants": {},
        "formal_phase1_acceptance": False,
        "external_model_calls": False,
        "test_is_sealed_holdout": False,
        "raw_copied": False,
        "identity": "New experiment identity; immutable source run/local IDs remain source-bound",
    }
    telemetry = {}
    for variant in VARIANTS:
        manifest["variants"][variant] = {}
        for mode in MODES:
            start = perf_counter()
            # Independently recompute each mode; never read another mode's frozen answer.
            pixel = _produce(package, variant, policy)
            pixel_seconds = perf_counter() - start
            start = perf_counter()
            inference = build_inference(
                pixel,
                scope=package.scope,
                context=package.context,
                policy=AssociationPolicy.model_validate(source_manifest["association_policy"]),
                topology=topology,
                retrieval_policy=RetrievalPolicy.model_validate(
                    source_manifest["retrieval_policy"]
                ),
            )
            base_snapshot_sha = digest(inference.snapshot)
            base_pool_sha = inference.association_pool_sha256
            root = output / variant / mode
            assoc_config = association_config(policy, variant)
            if variant in (
                "appearance_only",
                "prior_only",
                "features_full",
                "motion_diagnostic",
                "end_to_end",
            ):
                appearance = build_appearance_bundle(pixel, inference, package.frames, assoc_config)
                _save(root / "appearance.json", appearance)
                inference = improve_association(pixel, inference, package.frames, assoc_config)
            if digest(inference.snapshot) != base_snapshot_sha or (
                inference.association_pool_sha256 != base_pool_sha
            ):
                raise ValueError("feature experiment changed canonical Graph or candidate pool")
            if variant in ("behavior_only", "end_to_end"):
                behavior_policy = BehaviorEvidencePolicy.model_validate(policy["behavior"])
                events = compose_behaviors_v2(
                    inference,
                    behavior,
                    tracks=pixel.tracks,
                    policy=behavior_policy,
                )
                expected_behavior_sha = behavior_config_sha256(behavior, behavior_policy)
            else:
                events = compose_local_behaviors(inference, behavior, tracks=pixel.tracks)
                expected_behavior_sha = digest(behavior)
            if events.config_sha256 != expected_behavior_sha:
                raise ValueError("behavior config binding mismatch")
            binding = RunBinding(
                place_id=package.scope.place_id,
                model_id=package.model_id,
                model_revision=package.revision,
                source_ref=package.scope.source_ref,
                spatial_context_id=package.scope.spatial_context_id,
                run_id=package.run_id,
                clock_id=package.scope.clock_id,
                observation_mode=mode,
                registry_version=VERSION,
                dataset_sha256=package.dataset_sha256,
                config_sha256=digest(
                    {"run_config": config_sha, "experiment_id": experiment_id, "variant": variant}
                ),
                producer_sha256=pixel.producer_sha256,
                registry_sha256=registry.sha256,
                media_sha256=digest([(f.media_ref, f.sha256) for f in registry.frames]),
            )
            receipt = FreezeReceipt.create(binding, inference, pixel.model_dump(mode="json"))
            for name, document in (
                ("perception", pixel),
                ("inference", inference),
                ("events", events),
                ("receipt", receipt),
            ):
                _save(root / (name + ".json"), document)
            manifest["variants"][variant][mode] = {
                "receipt_sha256": receipt.receipt_sha256,
                "binding_config_sha256": binding.config_sha256,
                "events_sha256": digest(events),
                "behavior_config_sha256": events.config_sha256,
                "base_snapshot_sha256": base_snapshot_sha,
                "candidate_pool_sha256": base_pool_sha,
                "appearance_sha256": digest(appearance)
                if variant
                in (
                    "appearance_only",
                    "prior_only",
                    "features_full",
                    "motion_diagnostic",
                    "end_to_end",
                )
                else None,
            }
            telemetry[variant + "/" + mode] = {
                "pixel_seconds": pixel_seconds,
                "composition_seconds": perf_counter() - start,
                "total_seconds": pixel_seconds + perf_counter() - start,
            }
    # This final immutable manifest is the freeze; evaluation is a separate command.
    _save(output / "manifest.json", manifest)
    (output / "timings.json").write_text(json.dumps(telemetry, indent=2) + "\n")
    return manifest


def load(output: Path) -> tuple[ResearchPackage, LocationRegistry, dict[str, Any], dict[str, Any]]:
    """Validate config and input lineage; reading frozen artifacts never runs inference or GT."""
    manifest = json.loads((output / "manifest.json").read_text())
    policy = json.loads((output / "policy.json").read_text())
    validate_policy(policy)
    if manifest["schema_version"] != "accuracy.frozen-run.v2" or (
        manifest["policy_sha256"] != digest(policy)
        or manifest["algorithms"] != research_algorithms()
    ):
        raise ValueError("research config/algorithm freeze mismatch")
    package, registry, _, original = _load(Path(manifest["source_locator"]))
    expected_config = digest(
        {
            "policy": policy,
            "algorithms": research_algorithms(),
            "source_config_sha256": original["config_sha256"],
        }
    )
    if manifest["config_sha256"] != expected_config or (
        manifest["source_manifest_sha256"] != digest(original)
        or manifest["source_package_sha256"] != digest(package)
        or manifest["source_run_id"] != package.run_id
        or manifest["dataset_sha256"] != package.dataset_sha256
        or manifest["source_sha256"] != package.source_sha256
        or manifest["context_sha256"] != package.context_sha256
        or manifest["clock_id"] != package.scope.clock_id
        or manifest["split"] != package.split
        or set(manifest["variants"]) != set(VARIANTS)
    ):
        raise ValueError("research source/config/scope freeze mismatch")
    return package, registry, manifest, policy


def frozen(
    output: Path,
    variant: Variant,
    mode: Mode,
    manifest: dict[str, Any],
    package: ResearchPackage,
    registry: LocationRegistry,
) -> FrozenVariant:
    if variant not in VARIANTS or mode not in MODES:
        raise ValueError("unknown research variant/mode")
    root = output / variant / mode
    pixel = PerceptionResult.model_validate_json((root / "perception.json").read_bytes())
    inference = InferenceBundle.model_validate_json((root / "inference.json").read_bytes())
    events = LocalBehaviorBundle.model_validate_json((root / "events.json").read_bytes())
    receipt = FreezeReceipt.model_validate_json((root / "receipt.json").read_bytes())
    binding = receipt.binding
    expected = manifest["variants"][variant][mode]
    if not receipt.verify(binding, inference, pixel.model_dump(mode="json")) or (
        receipt.receipt_sha256 != expected["receipt_sha256"]
        or binding.observation_mode != mode
        or binding.run_id != package.run_id
        or binding.registry_version != VERSION
        or binding.config_sha256
        != digest(
            {
                "run_config": manifest["config_sha256"],
                "experiment_id": manifest["experiment_id"],
                "variant": variant,
            }
        )
        or binding.config_sha256 != expected["binding_config_sha256"]
        or binding.dataset_sha256 != package.dataset_sha256
        or binding.registry_sha256 != registry.sha256
        or binding.media_sha256 != digest([(f.media_ref, f.sha256) for f in registry.frames])
        or binding.place_id != package.scope.place_id
        or binding.model_id != package.model_id
        or binding.model_revision != package.revision
        or binding.source_ref != package.scope.source_ref
        or binding.spatial_context_id != package.scope.spatial_context_id
        or binding.clock_id != package.scope.clock_id
        or pixel.model_id != package.model_id
        or inference.static_context_sha256 != digest(package.context)
        or binding.producer_sha256 != pixel.producer_sha256
        or inference.scope != package.scope
        or pixel.run_id != package.run_id
        or pixel.input_manifest_sha256 != package.dataset_sha256
        or inference.input_manifest_sha256 != package.dataset_sha256
        or inference.producer_sha256 != pixel.producer_sha256
        or digest(inference.snapshot) != expected["base_snapshot_sha256"]
        or inference.association_pool_sha256 != expected["candidate_pool_sha256"]
        or digest(events) != expected["events_sha256"]
        or events.inference_sha256 != receipt.inference_sha256
        or events.scope != inference.scope
        or events.producer_sha256 != pixel.producer_sha256
        or events.input_manifest_sha256 != package.dataset_sha256
        or events.config_sha256 != expected["behavior_config_sha256"]
        or events.track_state_sha256 != digest([t.model_dump(mode="json") for t in pixel.tracks])
    ):
        raise ValueError("research same-run variant/mode/event freeze mismatch")
    appearance_path = root / "appearance.json"
    if expected["appearance_sha256"] is not None and (
        digest(json.loads(appearance_path.read_text())) != expected["appearance_sha256"]
    ):
        raise ValueError("research appearance freeze mismatch")
    return FrozenVariant(pixel, inference, events, receipt)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("policy", "build", "evaluate", "evidence", "verify"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--experiment-id")
    args = parser.parse_args()
    if args.command == "policy":
        _save(args.output, default_policy())
        print(json.dumps({"policy_sha256": digest(default_policy())}))
    elif args.command == "build":
        if args.source is None or args.config is None or args.experiment_id is None:
            parser.error("build requires --source --config --experiment-id")
        result = build(
            args.source,
            args.output,
            json.loads(args.config.read_text()),
            experiment_id=args.experiment_id,
        )
        print(
            json.dumps(
                {
                    "experiment_id": result["experiment_id"],
                    "config_sha256": result["config_sha256"],
                    "frozen": True,
                }
            )
        )
    elif args.command == "evaluate":
        from amidst.research_accuracy.evaluation import evaluate

        print(json.dumps(evaluate(args.output)["comparison"]))
    elif args.command == "evidence":
        from amidst.research_accuracy.evidence import export_evidence

        print(json.dumps(export_evidence(args.output)))
    else:
        package, registry, manifest, _ = load(args.output)
        for variant in VARIANTS:
            for mode in MODES:
                frozen(args.output, variant, mode, manifest, package, registry)
        print(json.dumps({"experiment_id": manifest["experiment_id"], "verified": True}))


if __name__ == "__main__":
    main()
