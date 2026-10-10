"""Freeze tampering and unknown-claim recall accounting across research artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from amidst.engineering.access import FreezeReceipt, RunBinding, digest
from amidst.engineering.local_behavior import BehaviorConfig, compose_local_behaviors
from amidst.engineering.local_evaluation import ResearchTruth
from amidst.engineering.local_pilot import _save
from amidst.research_accuracy.evaluation import supported_behavior
from amidst.research_accuracy.run import FrozenVariant, default_policy, frozen, validate_policy

from .test_association import fixture


def make_frozen(tmp_path: Path):
    pixel, inference, _ = fixture(tmp_path / "pixels")
    behavior = compose_local_behaviors(
        inference,
        BehaviorConfig(scope=inference.scope, config_version="fixture", regions=()),
        tracks=pixel.tracks,
    )
    # A minimal registry binding avoids a second synthetic raw materialization.
    registry = SimpleNamespace(sha256="d" * 64, frames=())
    package = SimpleNamespace(
        run_id=pixel.run_id,
        dataset_sha256=pixel.input_manifest_sha256,
        scope=inference.scope,
        model_id=pixel.model_id,
        revision="1",
        context=SimpleNamespace(),
    )
    # Use a serializable context marker matching this synthetic inference.
    package.context = {"fixture_context": True}
    inference = inference.model_copy(update={"static_context_sha256": digest(package.context)})
    behavior = behavior.model_copy(update={"inference_sha256": digest(inference)})
    manifest = {"experiment_id": "unit-freeze", "config_sha256": "e" * 64, "variants": {}}
    config_hash = digest(
        {
            "run_config": manifest["config_sha256"],
            "experiment_id": manifest["experiment_id"],
            "variant": "baseline",
        }
    )
    scope = inference.scope
    binding = RunBinding(
        place_id=scope.place_id,
        model_id=scope.model_id,
        model_revision=scope.model_revision,
        source_ref=scope.source_ref,
        spatial_context_id=scope.spatial_context_id,
        run_id=scope.run_id,
        clock_id=scope.clock_id,
        observation_mode="photos_only",
        registry_version="local-camera-accuracy-v2",
        dataset_sha256=pixel.input_manifest_sha256,
        config_sha256=config_hash,
        producer_sha256=pixel.producer_sha256,
        registry_sha256=registry.sha256,
        media_sha256=digest([]),
    )
    receipt = FreezeReceipt.create(binding, inference, pixel.model_dump(mode="json"))
    manifest["variants"]["baseline"] = {
        "photos_only": {
            "receipt_sha256": receipt.receipt_sha256,
            "binding_config_sha256": config_hash,
            "base_snapshot_sha256": digest(inference.snapshot),
            "candidate_pool_sha256": inference.association_pool_sha256,
            "events_sha256": digest(behavior),
            "behavior_config_sha256": behavior.config_sha256,
            "appearance_sha256": None,
        }
    }
    root = tmp_path / "baseline/photos_only"
    for name, doc in (
        ("perception", pixel),
        ("inference", inference),
        ("events", behavior),
        ("receipt", receipt),
    ):
        _save(root / (name + ".json"), doc)
    return package, registry, manifest


def test_valid_frozen_variant_and_wrong_experiment_denied(tmp_path: Path) -> None:
    package, registry, manifest = make_frozen(tmp_path)
    state = frozen(tmp_path, "baseline", "photos_only", manifest, package, registry)
    assert state.perception.measurements
    manifest["experiment_id"] = "another-experiment"
    with pytest.raises(ValueError, match="freeze mismatch|candidate pool hash"):
        frozen(tmp_path, "baseline", "photos_only", manifest, package, registry)


@pytest.mark.parametrize(
    "document,field,value",
    [
        ("perception", "producer_version", "wrong-version"),
        ("events", "inference_sha256", "0" * 64),
        ("inference", "association_pool_sha256", "0" * 64),
    ],
)
def test_artifact_tamper_denied(tmp_path: Path, document: str, field: str, value: str) -> None:
    package, registry, manifest = make_frozen(tmp_path)
    path = tmp_path / "baseline/photos_only" / (document + ".json")
    data = json.loads(path.read_text())
    data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="freeze mismatch|candidate pool hash"):
        frozen(tmp_path, "baseline", "photos_only", manifest, package, registry)


@pytest.mark.parametrize("key", ["pixel", "association", "behavior", "variants"])
def test_incomplete_policy_denied(key: str) -> None:
    policy = default_policy()
    policy.pop(key)
    with pytest.raises(ValueError, match="policy schema"):
        validate_policy(policy)


def test_unknown_keeps_candidate_and_full_truth_false_negative(tmp_path: Path) -> None:
    from amidst.engineering.local_association import build_inference
    from amidst.engineering.local_behavior import compose_local_behaviors

    from .test_behavior import perception, setup

    scope, context, config = setup()
    pixel = perception(
        ("DOOR", "door", (0, 0.4, 0.8, 1.2, 1.6), ((4, 2), (5, 2), (6, 2), (7, 2), (8, 2)))
    )
    inference = build_inference(pixel, scope=scope, context=context)
    events = compose_local_behaviors(inference, config, tracks=pixel.tracks)
    event = next(e for e in events.events if e.kind == "ENTER_DOOR")
    events = events.model_copy(
        update={
            "events": (
                event.model_copy(
                    update={"supports": (*event.supports, "V2_EVIDENCE_STATE:UNKNOWN")}
                ),
            )
        }
    )
    truth = ResearchTruth(
        schema_version="local.camera.truth.v1",
        boundary="EVALUATION_DEBUG_ONLY",
        model_id=scope.model_id,
        run_id=scope.run_id,
        split="test",
        dataset_sha256=pixel.input_manifest_sha256,
        config_sha256="f" * 64,
        recipe={},
        ground_truth=(),
        limitations=(),
        behavior_truth=({"kind": "ENTER", "actor_identity": "evaluation-only", "timestamp": 0.8},),
    )
    receipt = SimpleNamespace()
    report = supported_behavior(
        FrozenVariant(pixel, inference, events, receipt),
        truth,
        {row.segment_id: "evaluation-only" for row in inference.local_record_maps},
    )
    metrics = report["groups"]["visible_supported"]["per_kind"]["ENTER"]
    assert metrics["false_negative"] == 1
    assert metrics["recall"] == 0
    assert metrics["unresolved"] == 1
    assert report["visible_candidate_count"] == 1
    assert report["evidence_unknown_fraction"] == 1


def test_completed_output_cannot_be_overwritten(tmp_path: Path) -> None:
    from amidst.research_accuracy.run import build

    output = tmp_path / "existing"
    output.mkdir()
    marker = output / "timings.json"
    marker.write_text("historical telemetry")
    with pytest.raises(ValueError, match="new empty output"):
        build(tmp_path / "source", output, default_policy(), experiment_id="guard")
    assert marker.read_text() == "historical telemetry"


def test_evidence_cannot_replace_existing_png(tmp_path: Path) -> None:
    from amidst.research_accuracy.evidence import export_evidence

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    marker = evidence / "card.png"
    marker.write_bytes(b"historical image")
    with pytest.raises(ValueError, match="new empty evidence"):
        export_evidence(tmp_path)
    assert marker.read_bytes() == b"historical image"


def test_completed_evaluation_is_immutable(tmp_path: Path) -> None:
    from amidst.research_accuracy.evaluation import evaluate

    marker = tmp_path / "comparison.json"
    marker.write_text("historical evaluation")
    with pytest.raises(ValueError, match="completed evaluation is immutable"):
        evaluate(tmp_path)
    assert marker.read_text() == "historical evaluation"


def test_virtual_poisoning_preserves_actual_source(tmp_path: Path) -> None:
    from amidst.research_accuracy.verify import denied_sidecars

    truth = tmp_path / "ground_truth.json"
    rgb = tmp_path / "rgb.png"
    truth.write_bytes(b"immutable truth")
    rgb.write_bytes(b"unannotated rgb")
    with denied_sidecars({truth}, removed=False) as counter:
        assert b"POISON" in truth.read_bytes()
        assert rgb.read_bytes() == b"unannotated rgb"
    assert counter["attempted_reads"] == 1
    with denied_sidecars({truth}, removed=True):
        with pytest.raises(FileNotFoundError):
            truth.read_bytes()
    assert truth.read_bytes() == b"immutable truth"
