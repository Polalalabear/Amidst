"""V3 orchestration integrity using tiny synthetic authorities and actual inference.

Only source hydration, pixel projection and case inventory construction are
substituted. The reviewed run wrapper, collision consumers, domain guard and
freeze/verification orchestration execute unchanged. No school geometry is read.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_reviewed_authority import _dataset, _inference
from test_reviewed_authority import authority as authority
from test_reviewed_collision import _bundle

from amidst.datasets.pilot import PilotInferenceContext
from amidst.domain.pipeline import PipelineConfig
from amidst.domain.stream import AggregationPolicy
from amidst.finalization import reviewed_authority as authority_module
from amidst.finalization import reviewed_collision as collision_module
from amidst.finalization import reviewed_collision_lock as lock_module
from amidst.finalization import reviewed_pipeline as pipeline_module
from amidst.finalization import route_inventory as inventory_module
from amidst.finalization.reviewed_authority import ReviewedAuthority, build_reviewed_context
from amidst.finalization.reviewed_collision_lock import ReviewedKnownCollisionBinding
from amidst.obstacle_volume_authority import content_sha256


@pytest.fixture
def harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, authority: ReviewedAuthority,
) -> SimpleNamespace:
    """Hydrate a tiny independently approved wall instead of the large scene."""
    dataset, application = tmp_path / "dataset", tmp_path / "application"
    config_path = tmp_path / "v3.json"
    bundle = _bundle(authority)
    binding = ReviewedKnownCollisionBinding(
        context_path="configs/synthetic-explicit-collision.json",
        physical_manifest_file_sha256=bundle.manifest_sha256,
        source_sha256=authority.source_sha256, scope_ids=bundle.scope_ids,
    )
    config = {
        "export_config_file_sha256": "1" * 64,
        "aggregation_max_visible_sample_gap_s": .200001,
        "inference_seed": 42, "cases": [{"case_id": "case1"}],
    }
    typed = SimpleNamespace(
        export_config_file_sha256=config["export_config_file_sha256"],
        aggregation_max_visible_sample_gap_s=config["aggregation_max_visible_sample_gap_s"],
        model_dump=lambda **kwargs: config,
    )
    document = {
        "schema_version": "phase1-reviewed-case-inference-lock-v3",
        "known_collision": binding.model_dump(mode="json"), "base_config": config,
    }
    pipeline_module.write_json(config_path, document)
    pipeline_module.write_json(application / "manifest.json", {"synthetic": True})
    observations = {
        "label": "PILOT / SYNTHETIC SAMPLE", "data_kind": "SYNTHETIC",
        "source_asset_sha256": authority.source_sha256,
        "site_id": authority.historical_context.site_id,
        "frames": [{
            "frame_id": int(timestamp * 5), "timestamp": timestamp,
            "target_id": "marker", "camera_id": camera, "status": status,
            "point_2d": None if status == "GAP" else [0., 0.],
            "provenance": None if status == "GAP" else "OBSERVED",
            "gap_reason": "OCCLUDED" if status == "GAP" else None,
        } for camera, timestamp, status in (
            ("CAM_FRONT", 0., "OBSERVED"), ("CAM_FRONT", 5., "GAP"),
            ("CAM_REAR", 10., "OBSERVED"),
        )],
    }
    observation_path = dataset / "inference/case1/observations.json"
    pipeline_module.write_json(observation_path, observations)
    native = authority.historical_context.model_dump(mode="json")
    native.update(source_id="fresh-source", spatial_context_id="fresh-context",
                  observations_sha256=pipeline_module.digest(observation_path))
    pipeline_module.write_json(dataset / "inference/case1/context.json", native)
    pipeline_module.write_json(dataset / "evaluation/case1/ground_truth.json", {
        "samples": [{"position": [3., 5., 0.]}],
    })
    pipeline_module.write_json(dataset / "simulation/case1/recipe.json", {
        "waypoints": [{"position": [3., 5., 0.]}],
    })
    pipeline_module.write_json(dataset / "evaluation/case1/reference_movement_annotations.json", {
        "segments": [{"kind": "MOVING", "duration_s": 10}],
    })
    pipeline_module.write_json(dataset / "manifest.json", {
        "schema_version": "phase1-reviewed-dataset-v1", "dataset_version": "synthetic-v3",
        "config_sha256": typed.export_config_file_sha256,
        "source_sha256": authority.source_sha256,
        "human_decisions_sha256": authority.human_decisions_sha256,
        "application_manifest_sha256": pipeline_module.digest(application / "manifest.json"),
        "inference_seed": 42,
        "artifacts": {str(path.relative_to(dataset)): pipeline_module.digest(path)
                      for path in dataset.rglob("*.json")},
    })
    state: dict[str, Any] = {"outside": False}

    def project(context: PilotInferenceContext, export: Any) -> dict[str, Any]:
        reviewed = build_reviewed_context(
            authority, context, observations_sha256=context.observations_sha256,
            fresh_export_config_sha256=typed.export_config_file_sha256,
        )
        state["context"] = reviewed
        return _dataset(reviewed)[1]

    def pipeline(*args: Any) -> PipelineConfig:
        inputs, _, readiness = _inference(authority, state["context"])
        payload = PipelineConfig(
            navigation=inputs.navigation, topology=inputs.topology, movement=inputs.movement,
            search_policy=inputs.search_policy, reconstruction_policy=inputs.reconstruction_policy,
        ).model_dump()
        if state["outside"]:
            edge = payload["navigation"]["edges"][0]
            edge["polyline"] = (edge["polyline"][0], (5., 8.01, 0.), edge["polyline"][-1])
        result = PipelineConfig.model_validate(payload)
        readiness.update(
            graph_content_sha256=content_sha256(result.model_dump(mode="json")),
            case_config_content_sha256=content_sha256(config),
            aggregation_policy=AggregationPolicy(max_visible_sample_gap_s=.200001).model_dump(
                mode="json",
            ),
        )
        readiness["aggregation_policy_content_sha256"] = content_sha256(
            readiness["aggregation_policy"],
        )
        state["readiness"] = readiness
        return result

    def collision_loader(*args: Any, **kwargs: Any) -> Any:
        assert kwargs["expected_source_sha256"] == authority.source_sha256
        assert kwargs["expected_manifest_sha256"] == binding.physical_manifest_file_sha256
        assert kwargs["scope_ids"] == binding.scope_ids
        bundle.validate_bindings(
            source_sha256=kwargs["expected_source_sha256"], contract=kwargs["contract"],
            floor_ids=kwargs["floor_ids"],
            local_certificate_content_sha256=kwargs["local_certificate_content_sha256"],
            semantic_receipt_content_sha256=kwargs["semantic_receipt_content_sha256"],
        )
        return bundle

    monkeypatch.setattr(authority_module, "load_reviewed_authority", lambda *a, **kw: authority)
    monkeypatch.setattr(lock_module, "load_reviewed_collision_lock", lambda *a, **kw:
                        SimpleNamespace(base_inference_lock=SimpleNamespace(
                            base_inference_config=typed), known_collision=binding,
                            model_dump=lambda **kwargs: document))
    monkeypatch.setattr(collision_module, "load_reviewed_collision_bundle", collision_loader)
    monkeypatch.setattr(pipeline_module, "_module", lambda *args: SimpleNamespace(
        project_export=project,
        project_policy_frames=lambda *args: _dataset(state["context"])[0],
    ))
    monkeypatch.setattr(inventory_module, "build_reviewed_case_pipeline", pipeline)
    monkeypatch.setattr(inventory_module, "reviewed_case_readiness", lambda *args:
                        dict(state["readiness"]))
    return SimpleNamespace(dataset=dataset, application=application, config_path=config_path,
                           bundle=bundle, authority=authority, state=state, repo_root=tmp_path)


def _infer(harness: SimpleNamespace, output: Path, dataset: Path | None = None) -> dict[str, Any]:
    return pipeline_module.infer_dataset(
        dataset or harness.dataset, harness.application, harness.config_path, output,
        repo_root=harness.repo_root,
    )


def test_v3_pipeline_freezes_exact_config_and_real_bundle_receipt(
    tmp_path: Path, harness: SimpleNamespace,
) -> None:
    output = tmp_path / "inference"
    freeze = _infer(harness, output)
    collision = pipeline_module.read_json(output / "collision_authority.json")
    assert collision["inference_lock_file_sha256"] == pipeline_module.digest(harness.config_path)
    assert collision["inference_lock_content_sha256"] == content_sha256(
        pipeline_module.read_json(harness.config_path),
    )
    assert content_sha256(collision["consumer"]) == content_sha256(harness.bundle.receipt())
    assert "collision_authority.json" in freeze["artifacts"]
    full = pipeline_module.read_json(output / "case1/spatiotemporal.json")
    removed = pipeline_module.read_json(output / "case1/remove_collision.json")
    assert full["collision_filter_enabled"] is True
    assert removed["collision_filter_enabled"] is False
    assert full["collision_consumer_receipt"] == removed["collision_consumer_receipt"]
    assert full["geometric_result"]["routes"] == []
    assert len(removed["geometric_result"]["routes"]) == 1


def test_v3_inference_remains_identical_when_only_gt_and_annotations_are_poisoned(
    tmp_path: Path, harness: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    poisoned = tmp_path / "poisoned"
    pipeline_module.create_gt_poison_dataset(harness.dataset, poisoned)
    original_open = Path.open

    def guarded(path: Path, *args: Any, **kwargs: Any) -> Any:
        if {"evaluation", "simulation"} & set(path.parts):
            raise AssertionError("V3 inference consumed a GT/reference partition")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    first, second = tmp_path / "first", tmp_path / "second"
    _infer(harness, first)
    _infer(harness, second, poisoned)
    assert pipeline_module.compare_frozen_runs(first, second)["status"] == "PASS"


def test_remove_collision_pipeline_retains_original_complete_provider_guard(
    tmp_path: Path, harness: SimpleNamespace,
) -> None:
    harness.state["outside"] = True
    output = tmp_path / "inference"
    _infer(harness, output)
    removed = pipeline_module.read_json(output / "case1/remove_collision.json")
    assert removed["result_type"] == "FORMAL"
    assert removed["collision_filter_enabled"] is False
    assert removed["geometric_result"]["routes"] == []
    assert any("OUTSIDE_APPROVED_LOCAL" in reason for record in removed["physical_records"]
               for reason in record["reasons"])
    assert removed["physical_scope_id"] == (
        harness.authority.certificate.physical_certificate.scope_id
    )


@pytest.mark.parametrize("mutation", ["after_freeze", "config_binding", "bundle_receipt"])
def test_evaluation_rejects_changed_frozen_collision_lineage_before_metrics(
    tmp_path: Path, harness: SimpleNamespace, mutation: str,
) -> None:
    output = tmp_path / "inference"
    _infer(harness, output)
    path = output / "collision_authority.json"
    document = pipeline_module.read_json(path)
    if mutation == "bundle_receipt":
        document["consumer"]["semantic_receipt_content_sha256"] = "f" * 64
        expected = "collision authority differs from frozen inference"
    else:
        document["inference_lock_file_sha256"] = "f" * 64
        expected = "changed after freeze" if mutation == "after_freeze" else (
            "collision binding differs from.*frozen config"
        )
    path.write_text(json.dumps(document))
    if mutation != "after_freeze":
        # An independent synthetic freeze with internally hash-consistent artifacts
        # must still fail the external config/approved bundle binding checks.
        old = pipeline_module.read_json(output / "inference_freeze.json")
        (output / "inference_freeze.json").unlink()
        pipeline_module.freeze_inference(
            output, dataset_manifest_sha256=old["dataset_manifest_sha256"],
            config_sha256=old["config_sha256"],
        )
    with pytest.raises(ValueError, match=expected):
        pipeline_module.evaluate_dataset(
            harness.dataset, output, harness.application, tmp_path / "evaluation-output",
            repo_root=harness.repo_root, demos=False,
        )
    assert not (tmp_path / "evaluation-output/metric_authority.json").exists()
