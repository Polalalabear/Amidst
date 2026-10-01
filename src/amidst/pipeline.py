"""Generic inference orchestration: producer-independent input, no truth access."""

from collections.abc import Callable
from pathlib import Path
from time import monotonic

from amidst.domain.pipeline import InferenceInput
from amidst.domain.trajectory import Event, ReconstructionResult
from amidst.graph.engine import SpatiotemporalGraphEngine
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.reconstruction.blind_gap import BlindGapReconstructor


def load_inference_input(path: Path) -> InferenceInput:
    return InferenceInput.model_validate_json(path.read_text(encoding="utf-8"))


def generate_candidates(
    inputs: InferenceInput, *, max_paths: int | None = None,
    clock: Callable[[], float] = monotonic,
) -> ReconstructionResult:
    """Use the same configured engine for fixtures and Blender-derived inputs."""
    inputs = InferenceInput.model_validate(inputs.model_dump(mode="python"))
    network = NavigationNetwork(
        NavigationGraph(inputs.navigation), CameraTopologyGraph(inputs.topology),
    )
    engine = SpatiotemporalGraphEngine(
        network, inputs.movement, inputs.search_policy, clock=clock,
    )
    return engine.propose_feasible_trajectories(
        inputs.start_observation, inputs.end_observation,
        inputs.search_policy.max_candidate_paths if max_paths is None else max_paths,
    )


def reconstruct_input(
    inputs: InferenceInput, *, max_paths: int | None = None,
    clock: Callable[[], float] = monotonic,
) -> tuple[ReconstructionResult, Event]:
    """Return graph evidence and its timed alternatives before any evaluation."""
    inputs = InferenceInput.model_validate(inputs.model_dump(mode="python"))
    result = generate_candidates(inputs, max_paths=max_paths, clock=clock)
    event = BlindGapReconstructor().reconstruct_gap(
        inputs.start_observation, inputs.end_observation, result,
    )
    return result, event
