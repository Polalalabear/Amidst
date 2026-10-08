"""Product/source freeze precedes GT; evaluation never changes tools or plans."""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from amidst.engineering.access import digest
from amidst.engineering.local_pilot import _load, build_run, frozen_mode
from amidst.product.evaluation import ProductEvaluationError, _behavior_reference, evaluate_product
from amidst.product.investigation import (
    SUPPORTED_TOOLS,
    InMemoryPlanStore,
    InvestigationBinding,
    InvestigationIntent,
    InvestigationPolicy,
    build_report,
    compile_intent,
    execute_plan,
)
from amidst.product.run import build_product, load_product


@pytest.fixture(scope="module")
def product(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("product-evaluation")
    source, output = root / "source", root / "product"
    build_run(source, split="test", run_id="product-evaluation-test-v1")
    build_product(source, output, video_pool=root / "video", encode_video=False)
    return source, output


def _operations(output: Path) -> dict[str, object]:
    with load_product(output) as runtime:
        service = runtime.services[0]
        context = service.context()
        session = {"session_ref": context.context.session_ref}
        cameras = service.call("list_cameras", session)
        camera_ref = cameras["items"][0]["camera_ref"]
        observations = service.call(
            "query_observations",
            session
            | {
                "camera_ref": camera_ref,
                "time_range": [0, 24],
                "limit": 128,
            },
        )
        seeds = tuple(row["observation_ref"] for row in observations["items"][:2])
        assert len(seeds) == 2
        policy = InvestigationPolicy()
        binding = InvestigationBinding(
            session_ref=context.context.session_ref,
            place_id=context.context.place_id,
            model_id=context.context.model_id,
            run_id=context.context.run_id,
            clock_id=context.context.clock_id,
            observation_mode=context.context.observation_mode,
            decision_stage="RESULTS",
            freeze_ref=context.product_freeze_ref,
            config_sha256=service.base.guard.binding.config_sha256,
            policy_sha256=digest(policy),
            allowed_tools=tuple(tool for tool in SUPPORTED_TOOLS if tool in context.allowed_tools),
        )
        compiled = compile_intent(
            InvestigationIntent(
                task="MULTI_TARGET", camera_ref=camera_ref, time_range=(0, 24), seed_refs=seeds
            ),
            binding,
            policy,
        )
        assert compiled.plan is not None
        plans = InMemoryPlanStore()
        plans.put_plan(compiled.plan)
        case = execute_plan(compiled.plan.plan_ref, plans, service.call)
        report = build_report(case)
        return {
            "manifest_sha256": runtime.manifest.manifest_sha256,
            "cameras": cameras,
            "observations": observations,
            "plan_sha256": compiled.plan.plan_sha256,
            "report_sha256": report.report_sha256,
        }


def test_actual_product_metrics_and_source_bytes_preserved(product: tuple[Path, Path]) -> None:
    source, output = product
    original = {path.name: path.read_bytes() for path in source.glob("*.json")}
    result = evaluate_product(output)
    assert result["status"] == "LOCAL_SYNTHETIC_PRODUCT_MEASURED"
    assert not result["formal_phase1_acceptance"] and not result["external_model_calls"]
    for mode in result["modes"].values():
        appearance = mode["appearance"]
        assert appearance["handcrafted"]["eligible_queries"] > 0
        assert (
            appearance["handcrafted"]["eligible_queries"]
            == (appearance["component_mean_rgb_same_pool_baseline"]["eligible_queries"])
        )
        assert (
            sum(
                row["eligible_queries"]
                for row in appearance["handcrafted_by_query_quality"].values()
            )
            == (appearance["handcrafted"]["eligible_queries"])
        )
        assert mode["population"]["track_label_status_counts"].get("MIXED_KNOWN_IDENTITIES", 0) > 0
        assert mode["stitching"]["IDF1"] == "N/A"
        assert mode["existing_behavior_reference"]["status"] == "N/A"
    encoded = json.dumps(result)
    assert "test-blue-main" not in encoded and str(source) not in encoded
    assert "position_xyz" not in encoded and "world_position" not in encoded
    assert {path.name: path.read_bytes() for path in source.glob("*.json")} == original
    debug = output / "evaluation" / "debug" / "identity_mappings.json"
    assert "test-blue-main" in debug.read_text()
    assert result == evaluate_product(output)


def test_poisoned_gt_changes_no_product_tool_plan_or_report(product: tuple[Path, Path]) -> None:
    source, output = product
    evaluate_product(output)
    before = _operations(output)
    gt_path = source / "simulation" / "export" / "ground_truth.json"
    original = gt_path.read_bytes()
    truth = json.loads(original)
    truth["ground_truth"][0]["render_annotations"][0]["position_xyz_m"][0] += 99
    try:
        gt_path.write_text(json.dumps(truth))
        assert _operations(output) == before
        with pytest.raises(ProductEvaluationError, match="EVALUATION_TRUTH_CHANGED"):
            evaluate_product(output)
        truth["recipe"] = {"hidden_actor_answer": "polluted"}
        gt_path.write_text(json.dumps(truth))
        assert _operations(output) == before
        with pytest.raises(ProductEvaluationError, match="EVALUATION_TRUTH_BINDING_MISMATCH"):
            evaluate_product(output)
    finally:
        gt_path.write_bytes(original)


def test_wrong_product_scope_refuses_before_gt(
    product: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, output = product
    path = output / "product_manifest.json"
    original = path.read_bytes()
    value = json.loads(original)
    value["modes"][0]["scope"]["resource_scope"]["run_id"] = "foreign-run"
    touched = []
    read_bytes = Path.read_bytes

    def record(path: Path) -> bytes:
        if path.name == "ground_truth.json":
            touched.append(path)
        return read_bytes(path)

    try:
        path.write_text(json.dumps(value))
        monkeypatch.setattr(Path, "read_bytes", record)
        with pytest.raises(ProductEvaluationError, match="PRODUCT_FREEZE_REQUIRED_OR_MISMATCH"):
            evaluate_product(output)
        assert not touched
    finally:
        path.write_bytes(original)


def test_unfrozen_product_refuses_before_gt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    touched = []
    read_bytes = Path.read_bytes

    def record(path: Path) -> bytes:
        if path.name == "ground_truth.json":
            touched.append(path)
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", record)
    with pytest.raises(ProductEvaluationError, match="PRODUCT_FREEZE_REQUIRED_OR_MISMATCH"):
        evaluate_product(tmp_path)
    assert not touched


def test_existing_behavior_reference_is_bound_and_allowlisted() -> None:
    headers = {
        "dataset_sha256": "a" * 64,
        "config_sha256": "b" * 64,
        "inference_sha256": "c" * 64,
        "freeze_sha256": "d" * 64,
        "evaluation_truth_sha256": "e" * 64,
    }
    baseline = headers | {
        "behavior": {
            "groups": {
                "visible_supported": {
                    "per_kind": {
                        "CORNER": {
                            "precision": 0.0,
                            "recall": 0.0,
                            "false_positive": 5,
                            "actor_identity": "hidden-person",
                            "private_path": "/private/location",
                        },
                        "hidden-person": {"precision": 1.0},
                    }
                }
            }
        }
    }
    result = _behavior_reference(
        baseline,
        dataset="a" * 64,
        config="b" * 64,
        inference="c" * 64,
        freeze="d" * 64,
        truth="e" * 64,
    )
    assert result["visible_supported_per_kind"]["CORNER"]["false_positive"] == 5
    assert "hidden-person" not in json.dumps(result) and "/private/location" not in json.dumps(
        result
    )
    assert not result["new_winner_or_behavior_inference_run"]
    unavailable = _behavior_reference(
        baseline,
        dataset="f" * 64,
        config="b" * 64,
        inference="c" * 64,
        freeze="d" * 64,
        truth="e" * 64,
    )
    assert unavailable["status"] == "N/A"
    assert unavailable["reason"] == "SOURCE_EVALUATION_BINDING_MISMATCH"
    assert "visible_supported_per_kind" not in unavailable


def test_actual_source_recipe_config_reference_is_distinct_from_inference_config(
    product: tuple[Path, Path], tmp_path: Path
) -> None:
    source, _ = product
    package, _, _, manifest = _load(source)
    baseline = {}
    for mode in ("photos_only", "photos_plus_observations"):
        _, _, _, receipt = frozen_mode(source, mode, manifest)
        assert package.config_sha256 != receipt.binding.config_sha256
        baseline[mode] = {
            "dataset_sha256": package.dataset_sha256,
            "config_sha256": package.config_sha256,
            "inference_sha256": receipt.inference_sha256,
            "freeze_sha256": receipt.receipt_sha256,
            "evaluation_truth_sha256": sha256(
                package.simulation_export_path.read_bytes()
            ).hexdigest(),
            "behavior": {
                "groups": {
                    "visible_supported": {"per_kind": {"CORNER": {"false_positive": 5}}}
                }
            },
        }
    path = source / "evaluation.json"
    original = path.read_bytes() if path.exists() else None
    try:
        path.write_text(json.dumps(baseline))
        output = tmp_path / "with-source-reference"
        build_product(source, output, video_pool=tmp_path / "video", encode_video=False)
        result = evaluate_product(output)
        for mode in result["modes"].values():
            reference = mode["existing_behavior_reference"]
            assert reference["status"] == "QUOTED_EXISTING_POST_FREEZE_SOURCE_EVALUATION"
            assert reference["visible_supported_per_kind"]["CORNER"]["false_positive"] == 5
    finally:
        if original is None:
            path.unlink()
        else:
            path.write_bytes(original)
