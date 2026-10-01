"""Load producer-neutral streams and complete inference before reading references."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, perf_counter
from urllib.parse import quote

from pydantic import Field

from amidst.datasets.loading import load_case_calibration, load_dataset_case
from amidst.domain.calibration import CameraCalibrationCatalog
from amidst.domain.common import DomainModel
from amidst.domain.evaluation import ConstraintConfig
from amidst.domain.experiment import DatasetCase, ExperimentRecord, InputFingerprint
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.metric_config import MetricConfig
from amidst.domain.pipeline import PipelineConfig
from amidst.domain.stream import BoundGapEvent, ObservationAggregation
from amidst.evaluation.configured import (
    ConfiguredEvaluationResult,
    evaluate_configured_trajectories,
)
from amidst.events import reconstruct_gaps
from amidst.experiments.versioning import (
    canonical_config_hash,
    fingerprint,
    git_revision,
    load_experiment,
    read_reference,
    resolve_reference,
)
from amidst.storage.json_files import write_json
from amidst.visualization import RerunDebugVisualizationAdapter


class GapResult(DomainModel):
    gap: BoundGapEvent
    evaluation: ConfiguredEvaluationResult | None = None
    rerun_artifact: str | None = None


class CaseResult(DomainModel):
    case_id: str
    aggregation: ObservationAggregation
    gaps: tuple[GapResult, ...]
    inference_runtime_s: float = Field(ge=0, allow_inf_nan=False)


class BenchmarkResult(DomainModel):
    record: ExperimentRecord
    cases: tuple[CaseResult, ...]
    runtime_s: float = Field(ge=0, allow_inf_nan=False)


@dataclass(frozen=True)
class _InferredCase:
    case: DatasetCase
    pipeline: PipelineConfig
    aggregation: ObservationAggregation
    gaps: tuple[BoundGapEvent, ...]
    calibration: CameraCalibrationCatalog | None
    runtime_s: float


def _component(identity: str) -> str:
    # quote leaves literal dot segments untouched; prefix also protects those IDs.
    return "id-" + quote(identity, safe="")


def _reference_for_gap(
    references: tuple[GroundTruthTrajectory, ...], gap: BoundGapEvent, *, seed: int,
) -> GroundTruthTrajectory | None:
    """Evaluation-only exact boundary slicing, with no extrapolated truth endpoints."""
    if not references:
        return None
    start, end = gap.event.time_range
    matching = tuple(
        truth for truth in references
        if truth.target_id == gap.event.target_id
        and truth.scene_id == gap.binding.spatial_context_id
        and truth.source_asset_sha256 == gap.binding.source_asset_sha256
        and truth.random_seed == seed
        and truth.samples[0].timestamp <= start
        and truth.samples[-1].timestamp >= end
    )
    if len(matching) != 1:
        raise ValueError(
            "each gap must match exactly one evaluation reference by binding/time/seed"
        )
    truth = matching[0]
    samples = tuple(sample for sample in truth.samples if start <= sample.timestamp <= end)
    if len(samples) < 2 or samples[0].timestamp != start or samples[-1].timestamp != end:
        raise ValueError("evaluation reference must sample both exact gap boundaries")
    return GroundTruthTrajectory.model_validate(truth.model_dump() | {"samples": samples})


def _constraints(case: _InferredCase, manifest_path: Path) -> ConstraintConfig:
    pipeline = case.pipeline
    if case.case.constraints is None:
        return ConstraintConfig(
            max_speed_m_s=pipeline.movement.max_speed_m_s,
            navigation_graph=pipeline.navigation,
        )
    constraints = ConstraintConfig.model_validate_json(
        read_reference(case.case.constraints, manifest_path)
    )
    if constraints.max_speed_m_s != pipeline.movement.max_speed_m_s:
        raise ValueError("evaluation speed ceiling must match pipeline movement constraints")
    if constraints.navigation_graph is not None and (
        constraints.navigation_graph != pipeline.navigation
    ):
        raise ValueError("evaluation navigation graph must match the pipeline")
    return ConstraintConfig.model_validate(
        constraints.model_dump() | {"navigation_graph": pipeline.navigation}
    )


def _input_fingerprints(
    config_path: Path, manifest_path: Path, record: ExperimentRecord,
) -> tuple[InputFingerprint, ...]:
    inputs = [fingerprint(config_path, "experiment_config")]
    references = [
        ("dataset_manifest", record.config.dataset_manifest, config_path),
        ("metric_config", record.config.metric_config, config_path),
    ]
    for case in record.dataset.cases:
        for name in ("pipeline", "frames", "camera_calibration", "constraints"):
            reference = getattr(case, name)
            if reference is not None:
                references.append((f"case:{case.case_id}:{name}", reference, manifest_path))
        references.extend(
            (f"case:{case.case_id}:evaluation:{index}", reference, manifest_path)
            for index, reference in enumerate(case.evaluation_references)
        )
    for logical_id, reference, parent in references:
        item = fingerprint(resolve_reference(reference, parent), logical_id)
        if item.sha256 != reference.sha256:
            raise ValueError("input changed during benchmark execution")
        inputs.append(item)
    return tuple(inputs)


def _write_results(result: BenchmarkResult, destination: Path) -> None:
    write_json(destination / "config.json", result.record.config.model_dump(mode="json"))
    write_json(destination / "experiment.json", result.record.model_dump(mode="json"))
    metrics = {
        case.case_id: {
            gap.gap.event.event_id: gap.evaluation.model_dump(mode="json")
            if gap.evaluation is not None else None
            for gap in case.gaps
        } for case in result.cases
    }
    write_json(destination / "metrics.json", metrics)
    write_json(destination / "summary.json", {
        "experiment_id": result.record.config.experiment_id,
        "dataset_version": result.record.config.dataset_version,
        "seed": result.record.config.seed,
        "git_commit": result.record.git.commit,
        "runtime_s": result.runtime_s,
        "cases": [{
            "case_id": case.case_id,
            "visible_segments": len(case.aggregation.observations),
            "gap_count": len(case.gaps),
            "inference_runtime_s": case.inference_runtime_s,
            "gaps": [{
                "event_id": gap.gap.event.event_id,
                "candidates": len(gap.gap.event.candidates),
                "hypotheses": len(gap.gap.event.trajectories),
                "termination_reason": gap.gap.event.termination_reason.value,
                "rerun_artifact": gap.rerun_artifact,
            } for gap in case.gaps],
        } for case in result.cases],
    })
    for case in result.cases:
        directory = destination / "cases" / _component(case.case_id)
        write_json(directory / "observations.json", case.aggregation.model_dump(mode="json"))
        for gap in case.gaps:
            write_json(directory / "gaps" / _component(gap.gap.event.event_id) / "candidates.json",
                       gap.gap.model_dump(mode="json"))


def run_benchmark(
    config_path: Path,
    output_directory: Path,
    *,
    record_rerun: bool | None = None,
    debug_ground_truth: bool | None = None,
    search_clock: Callable[[], float] = monotonic,
    runtime_clock: Callable[[], float] = perf_counter,
) -> BenchmarkResult:
    """Run every case with shared consumers; outputs require a fresh directory.

    Diagnostic wall runtimes/RRD metadata vary between runs. Input versions,
    observations, candidate ordering, Events and metric values are deterministic
    when the configured deterministic search budgets are used.
    """
    started = runtime_clock()
    config_path = config_path.resolve()
    destination = output_directory.resolve()
    if destination.exists():
        raise FileExistsError("benchmark output directory must be new")
    config, dataset, manifest_path = load_experiment(config_path)
    updates = {}
    if record_rerun is not None:
        updates["record_rerun"] = record_rerun
    if debug_ground_truth is not None:
        updates["debug_ground_truth"] = debug_ground_truth
    config = type(config).model_validate(config.model_dump() | updates)
    metric_config = MetricConfig.model_validate_json(
        read_reference(config.metric_config, config_path)
    )
    if metric_config.metric_config_version != config.metric_config_version:
        raise ValueError("metric configuration version must match the experiment")
    # Repository identity comes from installed code location, independent of cwd.
    repository = Path(__file__).resolve().parents[3]
    revision = git_revision(repository)
    inferred: list[_InferredCase] = []
    for case in dataset.cases:
        case_started = runtime_clock()
        provider, pipeline = load_dataset_case(dataset, case, manifest_path)
        aggregation = provider.aggregate(provider.time_range, config.aggregation_policy)
        gaps = reconstruct_gaps(
            aggregation, pipeline, dataset_id=case.case_id, random_seed=config.seed,
            clock=search_clock,
        )
        inferred.append(_InferredCase(
            case, pipeline, aggregation, gaps,
            load_case_calibration(dataset, case, manifest_path),
            runtime_clock() - case_started,
        ))
    # No reference geometry is opened until every case has completed inference.
    destination.mkdir(parents=True, exist_ok=False)
    results: list[CaseResult] = []
    for inferred_case in inferred:
        references = tuple(
            GroundTruthTrajectory.model_validate_json(read_reference(reference, manifest_path))
            for reference in inferred_case.case.evaluation_references
        )
        constraints = _constraints(inferred_case, manifest_path)
        gap_results: list[GapResult] = []
        for gap in inferred_case.gaps:
            truth = _reference_for_gap(references, gap, seed=config.seed)
            evaluation = (
                evaluate_configured_trajectories(
                    gap.event.trajectories, truth, metric_config, constraints=constraints,
                )
                if truth is not None else None
            )
            rerun_artifact = None
            if config.record_rerun:
                relative = Path("cases") / _component(inferred_case.case.case_id) / "gaps" / (
                    _component(gap.event.event_id)
                ) / "debug.rrd"
                adapter = RerunDebugVisualizationAdapter(
                    observations=tuple(
                        bound.observation for bound in inferred_case.aggregation.observations
                    ),
                    navigation_config=inferred_case.pipeline.navigation,
                    topology_config=inferred_case.pipeline.topology,
                    calibration_catalog=inferred_case.calibration,
                    debug_mode=config.debug_ground_truth,
                    application_id="amidst_benchmark",
                )
                try:
                    adapter.save(destination / relative)
                    adapter.log_event(gap.event)
                    if config.debug_ground_truth and truth is not None:
                        adapter.log_debug_ground_truth(truth)
                    if evaluation is not None:
                        adapter.log_metrics(evaluation.model_dump(mode="json"))
                finally:
                    adapter.close()
                rerun_artifact = relative.as_posix()
            gap_results.append(GapResult(gap=gap, evaluation=evaluation,
                                         rerun_artifact=rerun_artifact))
        results.append(CaseResult(
            case_id=inferred_case.case.case_id, aggregation=inferred_case.aggregation,
            gaps=tuple(gap_results), inference_runtime_s=inferred_case.runtime_s,
        ))
    record = ExperimentRecord(
        config=config, dataset=dataset, git=revision,
        config_sha256=canonical_config_hash(config), inputs=(),
    )
    record = record.model_copy(update={
        "inputs": _input_fingerprints(config_path, manifest_path, record),
    })
    result = BenchmarkResult(record=record, cases=tuple(results),
                             runtime_s=runtime_clock() - started)
    _write_results(result, destination)
    return result
