"""Recipe isolation and bounded-route guards; synthetic proof fixtures only."""

from __future__ import annotations

import ast
import importlib.util
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.finalization.route_inventory import (
    CASE2_BLOCKER,
    ReviewedCaseInferenceConfig,
    ReviewedCaseInventoryConfig,
    load_reviewed_case_inference_config,
    load_reviewed_case_inventory,
    reviewed_rectangle_inventory,
    validate_inference_authority,
)
from amidst.local_semantic_review import ReviewedRestrictedLocalPhysicalProvider
from amidst.obstacle_volume_authority import content_sha256

ROOT = Path(__file__).resolve().parents[2]
EXPORT = ROOT / "configs/finalization/reviewed_case_inventory_v1.json"
INFERENCE = ROOT / "configs/finalization/reviewed_case_inference_lock_v1.json"


def _synthetic_provider() -> ReviewedRestrictedLocalPhysicalProvider:
    spec = importlib.util.spec_from_file_location(
        "reviewed_synthetic_fixture", Path(__file__).with_name("test_local_semantic_review.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt, evidence, domain, contract = module._proof_inputs()
    certificate, result = module._reviewed_proof(receipt, evidence, domain, contract)
    assert certificate is not None, result
    return ReviewedRestrictedLocalPhysicalProvider(
        certificate, domain, contract, content_sha256(certificate.model_dump(mode="json")),
        module.HUMAN,
    )


def test_complete_convex_synthetic_domain_has_one_major_route_class() -> None:
    provider = _synthetic_provider()
    proof = reviewed_rectangle_inventory(provider)
    assert proof["status"] == "PASS_SINGLE_MAJOR_ROUTE_CLASS"
    assert proof["source_distinct_route_classes"] == 1
    assert proof["branch_count"] == 0
    assert proof["parallel_offsets_are_distinct_branches"] is False
    assert proof["timing_hypotheses_are_distinct_routes"] is False
    assert proof["all_geometric_curves_enumerated"] is False
    assert proof["case2_blockers"] == (CASE2_BLOCKER,)
    assert proof["ground_truth_read"] is False


def test_synthetic_inventory_preserves_semantic_receipt_hash_validation() -> None:
    provider = _synthetic_provider()
    with pytest.raises(ValueError, match="certificate/human decisions hash"):
        replace(provider, expected_human_decisions_sha256="e" * 64)
    with pytest.raises(ValueError, match="reviewed provider"):
        reviewed_rectangle_inventory(object())  # type: ignore[arg-type]


def test_frozen_export_schedule_stays_inside_reviewed_scope_and_keeps_case2_blocked() -> None:
    config = load_reviewed_case_inventory(EXPORT)
    assert config.case("case2").waypoints == ()
    assert config.case("case2").blockers == (CASE2_BLOCKER,)
    assert config.case("case1").waypoints[-1].timestamp == 9.8
    stress = config.case("case3")
    assert stress.waypoints[2].timestamp - stress.waypoints[1].timestamp == 180
    assert int(stress.waypoints[-1].timestamp * config.sampling_fps) + 1 == 925
    assert config.search_policy.max_path_length_m == 1000 * .0247
    assert config.overall_exit_gate_enabled is False


@pytest.mark.parametrize("mutation", ["branch", "out_of_scope", "too_fast", "budget"])
def test_export_lock_refuses_fake_branch_or_unapproved_scope_speed_budget(mutation: str) -> None:
    config: dict[str, Any] = json.loads(EXPORT.read_bytes())
    if mutation == "branch":
        config["cases"][1]["status"] = "FROZEN_PENDING_FRESH_VISIBILITY"
        config["cases"][1]["blockers"] = []
        config["cases"][1]["waypoints"] = deepcopy(config["cases"][0]["waypoints"])
    elif mutation == "out_of_scope":
        config["cases"][0]["waypoints"][0]["position"][0] = 1500
    elif mutation == "too_fast":
        config["cases"][0]["waypoints"][-1]["timestamp"] = .2
    else:
        config["search_policy"]["max_search_nodes"] = 10000
    with pytest.raises(ValidationError):
        ReviewedCaseInventoryConfig.model_validate(config)


def test_inference_lock_contains_no_recipe_and_records_export_hash_lineage() -> None:
    config = load_reviewed_case_inference_config(INFERENCE)
    data = config.model_dump(mode="json")
    assert data["export_config_content_sha256"] == content_sha256(
        load_reviewed_case_inventory(EXPORT).model_dump(mode="json"),
    )
    assert not any("waypoints" in case or "trajectory_id" in case for case in data["cases"])
    assert config.ground_truth_available_to_inference is False
    assert config.simulation_recipe_positions_available_to_inference is False
    with pytest.raises(ValueError, match="file SHA-256 mismatch"):
        load_reviewed_case_inference_config(INFERENCE, expected_sha256="f" * 64)


@pytest.mark.parametrize("field", ["waypoints", "ground_truth", "simulation_recipe"])
def test_inference_config_rejects_recipe_or_reference_fields(field: str) -> None:
    config = json.loads(INFERENCE.read_bytes())
    config["cases"][0][field] = [{"timestamp": 0, "position": [1400, 1940, 20]}]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ReviewedCaseInferenceConfig.model_validate(config)


def test_export_recipe_object_is_refused_at_inference_authority_boundary() -> None:
    with pytest.raises(ValueError, match="never simulation recipes"):
        validate_inference_authority(
            load_reviewed_case_inventory(EXPORT),  # type: ignore[arg-type]
            _synthetic_provider(),
        )


def test_graph_and_readiness_do_not_call_recipe_validation_or_open_files() -> None:
    tree = ast.parse((ROOT / "src/amidst/finalization/route_inventory.py").read_text())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for name in ("validate_inference_authority", "build_reviewed_case_pipeline",
                 "reviewed_case_readiness"):
        calls = [node for node in ast.walk(functions[name]) if isinstance(node, ast.Call)]
        assert not any(isinstance(node.func, ast.Name) and node.func.id in (
            "open", "load_reviewed_case_inventory", "validate_inventory_authority",
        ) for node in calls)
        assert not any(isinstance(node, ast.Attribute) and node.attr == "waypoints"
                       for node in ast.walk(functions[name]))
