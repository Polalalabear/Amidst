"""Portable replay inputs and concise reports; never feed reference data into inference."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from amidst.domain.experiment import ArtifactReference
from amidst.experiments.versioning import (
    fingerprint,
    git_revision,
    read_local_bytes,
    resolve_reference,
)
from amidst.storage.json_files import write_json

if TYPE_CHECKING:
    from amidst.benchmark.runner import BenchmarkResult


def _write_bytes(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(contents)


def _reference(path: Path, root: Path) -> ArtifactReference:
    return ArtifactReference(
        path=path.relative_to(root).as_posix(), sha256=fingerprint(path, "replay").sha256,
    )


def _snapshot_replay(
    result: BenchmarkResult, destination: Path, config_path: Path, manifest_path: Path,
) -> None:
    """Content-bind every consumed JSON and capture uncommitted source changes."""
    replay = destination / "replay"
    expected = {item.logical_id: item for item in result.record.inputs}

    def copy_input(path: Path, logical_id: str) -> Path:
        contents = read_local_bytes(path)
        item = expected[logical_id]
        if len(contents) != item.size_bytes or hashlib.sha256(contents).hexdigest() != item.sha256:
            raise ValueError("input changed before the replay snapshot was saved")
        target = replay / "inputs" / f"{item.sha256}.json"
        if not target.exists():
            _write_bytes(target, contents)
        return target

    copy_input(config_path, "experiment_config")
    copy_input(manifest_path, "dataset_manifest")
    metric_path = copy_input(
        resolve_reference(result.record.config.metric_config, config_path), "metric_config",
    )
    cases = []
    for case in result.record.dataset.cases:
        payload = case.model_dump(mode="json")
        for name in ("pipeline", "frames", "camera_calibration", "constraints"):
            original = getattr(case, name)
            if original is not None:
                target = copy_input(resolve_reference(original, manifest_path),
                                    f"case:{case.case_id}:{name}")
                payload[name] = _reference(target, replay).model_dump(mode="json")
        payload["evaluation_references"] = [
            _reference(copy_input(resolve_reference(original, manifest_path),
                                  f"case:{case.case_id}:evaluation:{index}"), replay).model_dump(
                mode="json"
            ) for index, original in enumerate(case.evaluation_references)
        ]
        cases.append(payload)
    manifest = result.record.dataset.model_dump(mode="json") | {"cases": cases}
    write_json(replay / "dataset.json", manifest)
    config = result.record.config.model_dump(mode="json") | {
        "dataset_manifest": _reference(replay / "dataset.json", replay).model_dump(mode="json"),
        "metric_config": _reference(metric_path, replay).model_dump(mode="json"),
    }
    write_json(replay / "config.json", config)
    repository = Path(__file__).resolve().parents[3]
    if git_revision(repository) != result.record.git:
        raise ValueError("source code or environment lock changed during the benchmark")
    patch = subprocess.run([
        "git", "-C", str(repository), "diff", "--binary", "HEAD", "--",
        "src", "scripts", "pyproject.toml", "uv.lock",
    ], check=True, capture_output=True).stdout
    if hashlib.sha256(patch).hexdigest() != result.record.git.tracked_diff_sha256:
        raise ValueError("source patch changed before snapshot")
    _write_bytes(replay / "source.patch", patch)
    for item in result.record.git.untracked_source_fingerprints:
        relative = Path(item.logical_id)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid source snapshot path")
        contents = read_local_bytes(repository / relative)
        if hashlib.sha256(contents).hexdigest() != item.sha256:
            raise ValueError("untracked source changed before snapshot")
        _write_bytes(replay / "untracked" / relative, contents)
    lock = read_local_bytes(repository / "uv.lock")
    if hashlib.sha256(lock).hexdigest() != result.record.git.environment_lock_sha256:
        raise ValueError("environment lock changed before snapshot")
    _write_bytes(replay / "uv.lock", lock)
    _write_bytes(replay / "README.md", (
        b"Replay uses the Git commit and Python version in ../experiment.json.\n\n"
        b"In a separate checkout at that commit, apply source.patch if nonempty, copy the\n"
        b"contents of untracked/ into that checkout, and restore this uv.lock. Run uv sync\n"
        b"--locked with the recorded Python version, then run:\n\n"
        b"    uv run python -m amidst.benchmark --config /absolute/path/to/replay/config.json "
        b"--output /fresh/output/directory\n\n"
        b"JSON inputs are stored by SHA-256. Runtime and RRD SDK metadata are diagnostic\n"
        b"and may vary; observations, Events, candidate order and metric values replay.\n"
    ))


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def generate_reports(
    result: BenchmarkResult, destination: Path, *, config_path: Path, manifest_path: Path,
) -> None:
    """Add human-readable results and replay artifacts to the runner's core outputs."""
    _snapshot_replay(result, destination, config_path, manifest_path)
    lines = [
        f"Experiment: {_cell(result.record.config.experiment_id)}",
        f"Dataset: {_cell(result.record.config.dataset_version)}; "
        f"seed: {result.record.config.seed}",
        f"Git: {result.record.git.commit}; tracked changes: {result.record.git.tracked_dirty}; "
        f"untracked source files: {len(result.record.git.untracked_source_fingerprints)}",
        "",
        "| Scenario / Event | Candidates / Hypotheses | K | minADE (m) | minFDE (m) | Coverage | "
        "Collision violations | Constraint violations | Termination | Inference runtime (s) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    diagnostics: list[str] = []
    for case in result.cases:
        if not case.gaps:
            lines.append(f"| {_cell(case.case_id)} | 0 / 0 | n/a | n/a | n/a | n/a | n/a | n/a | "
                         f"NO_BOUNDED_GAP | {case.inference_runtime_s:.6f} |")
        for gap in case.gaps:
            diagnostics.extend([
                "", f"Event {_cell(gap.gap.event.event_id)} observed endpoint cameras: "
                f"{_cell(gap.gap.start.observation.camera_id)} → "
                f"{_cell(gap.gap.end.observation.camera_id)}. Evaluation status: "
                + ("EVALUATED." if gap.evaluation is not None else "NO_REFERENCE."),
                "Rejection reasons: " + (
                    ", ".join(_cell(reason) for reason in gap.gap.search_result.rejection_reasons)
                    or "none"
                ) + ".", "",
            ])
            # Configured metrics own K selection; reports never select hypotheses by truth.
            evaluations = gap.evaluation.evaluations if gap.evaluation is not None else (None,)
            for evaluation in evaluations:
                values = (
                    evaluation.config.k_routes, evaluation.min_ade_at_k_m,
                    evaluation.min_fde_at_k_m, evaluation.coverage_at_k,
                    evaluation.collision_segment_count,
                    evaluation.constraint_violation_segment_count,
                ) if evaluation is not None else ("n/a",) * 6
                lines.append(
                    f"| {_cell(case.case_id)} / {_cell(gap.gap.event.event_id)} | "
                    f"{len(gap.gap.event.candidates)} / {len(gap.gap.event.trajectories)} | "
                    + " | ".join(_cell(value) for value in values)
                    + f" | {gap.gap.event.termination_reason.value} | "
                    f"{case.inference_runtime_s:.6f} |"
                )
    lines.extend(diagnostics)
    lines.extend([
        "", f"Total runner runtime: {result.runtime_s:.6f} s.",
        "Inference runtime is per case (shared by its gaps), not an additive per-gap measurement.",
        "Coverage/tolerances are unresolved formal research settings; "
        "this is synthetic regression.",
        "Collision and constraint counts aggregate all timed hypotheses, including dwell segments.",
        "Supplied AABBs/configured graph corridors do not certify Blender mesh walkability.",
        "Runtimes and RRD SDK metadata vary between runs; deterministic metrics/candidates do not.",
    ])
    _write_bytes(destination / "summary.md", ("\n".join(lines) + "\n").encode())
    outputs = tuple(
        fingerprint(path, path.relative_to(destination).as_posix())
        for path in sorted(destination.rglob("*")) if path.is_file()
    )
    write_json(destination / "artifacts.json", {
        "schema_version": "1.0", "status": "COMPLETE",
        "config_sha256": result.record.config_sha256,
        "files": [item.model_dump(mode="json") for item in outputs],
    })
