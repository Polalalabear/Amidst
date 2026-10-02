"""Content-bind small adversarial mutations without modifying original fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from amidst.benchmark.runner import BenchmarkResult
from amidst.domain.pipeline import PipelineConfig
from amidst.experiments.versioning import load_experiment, resolve_reference

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data/mock"
BOUNDARY = FIXTURES / "boundary"
CONFIG = ROOT / "configs/benchmarks/mock_stream_v1.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def reference(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def custom_config(
    directory: Path,
    *,
    base_case: str = "single_path",
    frames: dict[str, Any] | None = None,
    pipeline: dict[str, Any] | None = None,
    truth: dict[str, Any] | None = None,
    no_truth: bool = False,
) -> Path:
    config, dataset, manifest_path = load_experiment(CONFIG)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = dataset.model_dump(mode="json")
    case = next(case for case in manifest["cases"] if case["case_id"] == base_case)
    manifest["cases"] = [case]
    for name in ("frames", "pipeline", "constraints", "camera_calibration"):
        if case[name] is not None:
            case[name]["path"] = str((manifest_path.parent / case[name]["path"]).resolve())
    for item in case["evaluation_references"]:
        item["path"] = str((manifest_path.parent / item["path"]).resolve())
    for name, payload in (("frames", frames), ("pipeline", pipeline), ("truth", truth)):
        if payload is not None:
            path = directory / f"{name}.json"
            path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
            if name == "truth":
                case["evaluation_references"] = [reference(path)]
            else:
                case[name] = reference(path)
    if no_truth:
        case["evaluation_references"] = []
    if pipeline is not None:
        case["spatial_context_id"] = pipeline["navigation"]["spatial_context_id"]
        case["source_asset_sha256"] = pipeline["navigation"].get("source_asset_sha256")
        constraints_path = directory / "constraints.json"
        constraints_path.write_text(json.dumps({
            "max_speed_m_s": pipeline["movement"]["max_speed_m_s"],
        }) + "\n")
        case["constraints"] = reference(constraints_path)
    manifest_file = directory / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    payload = config.model_dump(mode="json")
    payload["dataset_manifest"] = reference(manifest_file)
    payload["metric_config"]["path"] = str(resolve_reference(config.metric_config, CONFIG))
    path = directory / "experiment.json"
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    return path


def graph_benchmark_config(directory: Path, case_id: str) -> Path:
    from .graph_cases import load_graph_case

    inputs = load_graph_case(case_id)
    pipeline = PipelineConfig.model_validate(inputs.model_dump(include={
        "navigation", "topology", "movement", "search_policy", "reconstruction_policy",
    })).model_dump(mode="json")
    # Benchmark currently requests K=3; expose that same bound in the policy.
    pipeline["search_policy"]["max_candidate_paths"] = 3
    samples = []
    truth_samples = []
    endpoints = (inputs.start_observation, inputs.end_observation)
    for index, observation in enumerate(endpoints):
        point = observation.projected_path[0].model_dump(mode="json")
        samples.append({
            "sample_id": point["point_id"], "source_id": "mock:single_path",
            "spatial_context_id": inputs.navigation.spatial_context_id,
            "source_asset_sha256": inputs.navigation.source_asset_sha256,
            "target_id": observation.target_id, "camera_id": observation.camera_id,
            "timestamp": point["timestamp"], "frame_id": index, "uv": None,
            "visibility": "OBSERVED", "provenance": "PROJECTED", "projected_point": point,
        })
        truth_samples.append({
            "timestamp": point["timestamp"], "position": point["world_position"],
            "velocity": [0, 0, 0], "floor_id": point["floor_id"],
        })
    truth = {
        "trajectory_id": f"boundary:{case_id}:evaluation",
        "target_id": endpoints[0].target_id,
        "scene_id": inputs.navigation.spatial_context_id,
        "random_seed": 20261001, "sample_rate_hz": 1, "samples": truth_samples,
    }
    return custom_config(directory, pipeline=pipeline,
                         frames={"samples": samples}, truth=truth)


def inference_semantics(result: BenchmarkResult) -> list[dict[str, Any]]:
    return [
        {
            "case_id": case.case_id,
            "aggregation": case.aggregation.model_dump(mode="json"),
            "gaps": [gap.gap.model_dump(mode="json") for gap in case.gaps],
        }
        for case in result.cases
    ]


def report_semantics(output: Path) -> dict[str, Any]:
    payload = read_json(output / "summary.json")
    for name in ("runtime_s", "git_commit"):
        payload.pop(name)
    for case in payload["cases"]:
        case.pop("inference_runtime_s")
    return payload
