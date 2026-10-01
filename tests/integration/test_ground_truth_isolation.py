"""Structural and metamorphic proof that inference never consumes hidden truth."""

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.domain.common import Provenance
from amidst.domain.evaluation import ConstraintConfig, EvaluationConfig
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.observation import Observation
from amidst.domain.pipeline import InferenceInput
from amidst.evaluation import evaluate_trajectories
from amidst.graph.engine import GraphInputError
from amidst.pipeline import generate_candidates, load_inference_input, reconstruct_input
from amidst.reconstruction.blind_gap import BlindGapReconstructor, ReconstructionInputError

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "mock"


def test_inference_imports_exclude_truth_and_benchmark_consumers() -> None:
    source = ROOT / "src" / "amidst"
    paths = [source / "pipeline.py", source / "domain" / "pipeline.py"]
    for folder in ("graph", "geometry", "navigation", "reconstruction"):
        paths.extend((source / folder).rglob("*.py"))
    forbidden = ("ground_truth", ".simulation", ".evaluation", ".visualization")
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            assert not any(word in module for word in forbidden for module in modules), path


@pytest.mark.parametrize("name", [
    "single_path", "branching_top_k", "temporal_slack", "simplified_stair",
])
def test_inference_works_when_truth_file_access_is_poisoned(
    name: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.read_text

    def read(path: Path, *args: object, **kwargs: object) -> str:
        if "ground_truth" in str(path):
            raise AssertionError("inference attempted to read truth")
        return original(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", read)
    inputs = load_inference_input(FIXTURES / name / "inference.json")
    result, event = reconstruct_input(inputs, clock=lambda: 0.0)
    assert result.candidates and event.trajectories
    assert "GROUND_TRUTH" not in event.model_dump_json()


def test_changed_truth_changes_metrics_but_never_candidates_or_reconstruction() -> None:
    folder = FIXTURES / "branching_top_k"
    inputs = load_inference_input(folder / "inference.json")
    before_result, before_event = reconstruct_input(inputs, clock=lambda: 0.0)
    truth = GroundTruthTrajectory.model_validate_json((folder / "ground_truth.json").read_text())
    changed = truth.model_dump(mode="python")
    for sample in changed["samples"]:
        sample["position"] = (sample["position"][0], sample["position"][1] + 100, 0)
    changed_truth = GroundTruthTrajectory.model_validate(changed)
    constraints = ConstraintConfig(
        max_speed_m_s=inputs.movement.max_speed_m_s, navigation_graph=inputs.navigation,
    )
    first = evaluate_trajectories(
        before_event.trajectories, truth, EvaluationConfig(), constraints=constraints,
    )
    altered = evaluate_trajectories(
        before_event.trajectories, changed_truth, EvaluationConfig(), constraints=constraints,
    )
    after_result, after_event = reconstruct_input(inputs, clock=lambda: 0.0)
    assert first.coverage_at_k and not altered.coverage_at_k
    assert before_result.model_dump_json() == after_result.model_dump_json()
    assert before_event.model_dump_json() == after_event.model_dump_json()
    assert all(candidate.path_score is None for candidate in after_result.candidates)


@pytest.mark.parametrize("field", ["ground_truth_3d", "ground_truth", "future_position"])
def test_json_truth_injection_is_rejected_at_inference_boundary(field: str) -> None:
    payload = json.loads((FIXTURES / "single_path" / "inference.json").read_text())
    payload[field] = [999, 999, 999]
    with pytest.raises(ValidationError):
        InferenceInput.model_validate(payload)
    del payload[field]
    payload["start_observation"][field] = [999, 999, 999]
    with pytest.raises(ValidationError):
        InferenceInput.model_validate(payload)


@pytest.mark.parametrize("construction", ["copy", "construct"])
def test_forged_projected_truth_provenance_cannot_enter_graph_or_reconstruction(
    construction: str,
) -> None:
    inputs = load_inference_input(FIXTURES / "single_path" / "inference.json")
    result = generate_candidates(inputs, clock=lambda: 0.0)
    start = inputs.start_observation
    point = start.projected_path[0].model_copy(update={"provenance": Provenance.GROUND_TRUTH})
    updates = {"projected_path": (point,)}
    forged = (start.model_copy(update=updates) if construction == "copy" else
              Observation.model_construct(**(start.model_dump() | updates)))
    with pytest.raises(GraphInputError):
        # Exercise Graph's object-input guard separately from InferenceInput validation.
        from amidst.graph.engine import SpatiotemporalGraphEngine
        SpatiotemporalGraphEngine._validated_observation(forged)
    with pytest.raises(ReconstructionInputError):
        BlindGapReconstructor().reconstruct_gap(forged, inputs.end_observation, result)


def test_candidate_truth_and_probability_injection_is_rejected() -> None:
    inputs = load_inference_input(FIXTURES / "single_path" / "inference.json")
    result = generate_candidates(inputs, clock=lambda: 0.0)
    for updates in ({"provenance": Provenance.GROUND_TRUTH},
                    {"ground_truth_3d": (999, 999, 999)}, {"behavior_probability": 0.8}):
        candidate = result.candidates[0].model_copy(update=updates)
        forged = result.model_copy(update={"candidates": (candidate,)})
        with pytest.raises(ReconstructionInputError):
            BlindGapReconstructor().reconstruct_gap(
                inputs.start_observation, inputs.end_observation, forged,
            )
