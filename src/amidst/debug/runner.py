"""Run replaceable inference data, then evaluate and record optional debug truth."""

from pathlib import Path

from amidst.domain.evaluation import ConstraintConfig, EvaluationConfig, EvaluationResult
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.trajectory import Event, ReconstructionResult
from amidst.evaluation import evaluate_trajectories
from amidst.pipeline import load_inference_input, reconstruct_input
from amidst.storage.json_files import write_json
from amidst.visualization import RerunDebugVisualizationAdapter


def run_experiment(
    input_path: Path,
    output_directory: Path,
    *,
    ground_truth_path: Path | None = None,
    evaluation_config: EvaluationConfig | None = None,
    constraints: ConstraintConfig | None = None,
    record_rerun: bool = True,
) -> tuple[ReconstructionResult, Event, EvaluationResult | None]:
    """Truth is first loaded only after candidate generation and reconstruction.

    Outputs are exclusive and never replace existing directories or inputs.
    The Graph Engine uses its normal operational clock; fixtures finish well
    within their configured budget. RRD SDK metadata is not byte deterministic.
    """
    inputs = load_inference_input(input_path)
    result, event = reconstruct_input(inputs)
    used_evaluation_config = evaluation_config or EvaluationConfig()
    used_constraints = constraints or ConstraintConfig(
        max_speed_m_s=inputs.movement.max_speed_m_s,
    )
    if used_constraints.navigation_graph is None:
        used_constraints = ConstraintConfig.model_validate(
            used_constraints.model_dump(mode="python") | {"navigation_graph": inputs.navigation},
        )
    truth = None
    metrics = None
    if ground_truth_path is not None:
        truth = GroundTruthTrajectory.model_validate_json(
            ground_truth_path.read_text(encoding="utf-8"),
        )
        if truth.target_id != event.target_id:
            raise ValueError("evaluation truth target must match reconstructed event")
        if truth.scene_id != inputs.navigation.spatial_context_id:
            raise ValueError("evaluation truth must match the inference spatial context")
        if truth.source_asset_sha256 != inputs.navigation.source_asset_sha256:
            raise ValueError("evaluation truth and inference source bindings must match")
        metrics = evaluate_trajectories(
            event.trajectories, truth, used_evaluation_config,
            constraints=used_constraints,
        )
    output_directory.mkdir(parents=True, exist_ok=False)
    protected = (input_path,) if ground_truth_path is None else (input_path, ground_truth_path)
    write_json(output_directory / "candidates.json", result.model_dump(mode="json"),
               protected_inputs=protected)
    write_json(output_directory / "event.json", event.model_dump(mode="json"),
               protected_inputs=protected)
    if metrics is not None:
        write_json(output_directory / "metrics.json", metrics.model_dump(mode="json"),
                   protected_inputs=protected)
    write_json(output_directory / "run_config.json", {
        "dataset_id": inputs.dataset_id, "data_kind": inputs.data_kind,
        "random_seed": inputs.random_seed, "movement": inputs.movement.model_dump(mode="json"),
        "search_policy": inputs.search_policy.model_dump(mode="json"),
        "reconstruction_policy": inputs.reconstruction_policy.model_dump(mode="json"),
        "evaluation_config": used_evaluation_config.model_dump(mode="json") if truth else None,
        "constraint_config": used_constraints.model_dump(mode="json") if truth else None,
        "ground_truth_consumers": ["evaluation", "debug_visualization"] if truth else [],
        "rerun_recorded": record_rerun,
    }, protected_inputs=protected)
    if record_rerun:
        adapter = RerunDebugVisualizationAdapter(
            observations=(inputs.start_observation, inputs.end_observation),
            navigation_config=inputs.navigation, topology_config=inputs.topology,
            debug_mode=truth is not None,
        )
        try:
            adapter.save(output_directory / "debug.rrd")
            adapter.log_event(event)
            if truth is not None:
                adapter.log_debug_ground_truth(truth)
            if metrics is not None:
                adapter.log_metrics(metrics.model_dump(mode="json"))
        finally:
            adapter.close()
    return result, event, metrics
