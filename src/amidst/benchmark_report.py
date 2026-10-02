"""Evaluation-only benchmark comparisons from persisted metrics, without truth-based ordering.

Native runner directories and ``benchmark-comparison/v1`` manifests are supported.
Normalized runs contain case_id, method_id, run_id, status, metrics (canonical keys),
coverage_at_k (positive integer keys), termination_reason and explicit provenance.
Missing measurements stay null; this module does not infer new research metrics.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import tempfile
import textwrap
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any

# Keep plots usable in a sandbox without changing user cache directories.
_plot_cache = Path(tempfile.gettempdir()) / "amidst-matplotlib-cache"
_plot_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_plot_cache))
os.environ.setdefault("XDG_CACHE_HOME", str(_plot_cache))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SCHEMA = "benchmark-comparison/v1"
METHOD_LABELS = {
    "shortest_path": "Shortest Path",
    "geometry": "Geometry Graph",
    "spatiotemporal": "Spatiotemporal Graph",
    "semantic": "Graph + Semantic Information",
    "agent": "Graph + Agent Semantic Ranking",
    "deterministic_graph": "Configured Deterministic Graph",
}
# Canonical key -> (axis title, unit, filename). All are existing inputs or future exports.
METRICS = {
    "projection_error_m": ("Projection Error", "m", "projection_error.png"),
    "ade_m": ("ADE", "m", "accuracy_ade.png"),
    "fde_m": ("FDE", "m", "accuracy_fde.png"),
    "min_ade_at_k_m": ("minADE@K", "m", "accuracy_minade_at_k.png"),
    "min_fde_at_k_m": ("minFDE@K", "m", "accuracy_minfde_at_k.png"),
    "feasible_candidate_recall": ("Feasible Candidate Recall", "ratio", "feasible_recall.png"),
    "collision_rate": ("Collision Rate", "ratio", "collision_rate.png"),
    "constraint_violation_rate": ("Constraint Violation Rate", "ratio", "constraint_rate.png"),
    "impossible_transition_rate": (
        "Impossible Transition Rate", "ratio", "impossible_transition_rate.png",
    ),
    "path_length_error_m": ("Path Length Error", "m", "path_length_error.png"),
    "travel_time_error_s": ("Travel-time Error", "s", "travel_time_error.png"),
    "runtime_s": ("Inference Runtime", "s", "runtime.png"),
    "candidate_count": ("Candidate Count", "count", "candidate_count.png"),
    "search_nodes": ("Expanded Search States", "count", "search_nodes.png"),
}
ACCEPTANCE_CATEGORIES = {
    "GEOMETRIC_ACCURACY": (
        "projection_error_m", "ade_m", "fde_m", "min_ade_at_k_m", "min_fde_at_k_m",
        "path_length_error_m",
    ),
    "PHYSICAL_VALIDITY": (
        "collision_rate", "constraint_violation_rate", "impossible_transition_rate",
    ),
    "TOP_K_COVERAGE": ("coverage_at_k",),
    "TEMPORAL_VALIDITY": ("travel_time_error_s",),
    "SEARCH_BEHAVIOR": (
        "candidate_count", "feasible_candidate_recall", "search_nodes", "termination_reason",
    ),
    "SYSTEM_RUNTIME": ("runtime_s",),
}
PROVENANCE_LABELS = {
    "SYNTHETIC_TEST_FIXTURE": "SYNTHETIC REGRESSION",
    "SYNTHETIC_REGRESSION": "SYNTHETIC REGRESSION",
    "MOCK_VALIDATION": "MOCK VALIDATION",
}


@dataclass
class ReportRun:
    """One independent case/method/run; native gaps are averaged within this unit."""

    case_id: str
    method_id: str
    run_id: str
    source: str
    status: str
    benchmark_label: str
    metrics: dict[str, float | None] = field(default_factory=dict)
    coverage_at_k: dict[int, float | None] = field(default_factory=dict)
    selected_k: int | None = None
    terminations: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    physical_counts: dict[str, tuple[float, float]] = field(default_factory=dict)
    gap_availability: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadedComparison:
    runs: tuple[ReportRun, ...]
    declared_cases: tuple[str, ...] = ()
    declared_methods: tuple[str, ...] = ()


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _number(value: object, *, allow_bool: bool = False) -> float | None:
    if isinstance(value, bool):
        return float(value) if allow_bool else None
    if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
        return float(value)
    return None


def _positive_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _average(values: Sequence[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return mean(present) if present else None


def _provenance_label(value: Mapping[str, Any]) -> str:
    kind = value.get("benchmark_kind")
    if isinstance(kind, str) and kind in PROVENANCE_LABELS:
        return PROVENANCE_LABELS[kind]
    if kind == "BLENDER_RESEARCH_RESULT":
        if (
            value.get("formal_benchmark_status") == "APPROVED"
            and re.fullmatch(r"[0-9a-fA-F]{64}", str(value.get("scene_sha256", "")))
            and value.get("dataset_id")
            and value.get("protocol_version")
        ):
            return "BLENDER RESEARCH RESULT (SUPPLIED PROVENANCE)"
    return "UNVERIFIED INPUT"


def _metric_values(value: Mapping[str, Any], warnings: list[str]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for key in METRICS:
        raw = value.get(key)
        parsed = _number(raw)
        if parsed is not None and METRICS[key][1] == "ratio" and parsed > 1:
            parsed = None
        if raw is not None and parsed is None:
            warnings.append(f"{key}: invalid measurement reported as N/A")
        result[key] = parsed
    return result


def _normalized(path: Path, payload: Mapping[str, Any]) -> LoadedComparison:
    default_provenance = _mapping(payload.get("provenance"))
    runs: list[ReportRun] = []
    identities: set[tuple[str, str, str]] = set()
    for index, value in enumerate(_items(payload.get("runs"))):
        record = _mapping(value)
        case_id = str(record.get("case_id", "")).strip()
        method_id = str(record.get("method_id", "")).strip()
        run_id = str(record.get("run_id", index + 1)).strip()
        if not case_id or not method_id or not run_id:
            raise ValueError("normalized runs require nonempty case_id, method_id and run_id")
        identity = (case_id, method_id, run_id)
        if identity in identities:
            raise ValueError(f"duplicate case/method/run identity: {identity}")
        identities.add(identity)
        provenance = default_provenance | _mapping(record.get("provenance"))
        if "benchmark_kind" in record:
            provenance["benchmark_kind"] = record["benchmark_kind"]
        warnings: list[str] = []
        coverage: dict[int, float | None] = {}
        for key, raw in _mapping(record.get("coverage_at_k")).items():
            if not str(key).isdigit() or int(key) <= 0:
                warnings.append(f"Coverage key {key!r} is not a positive K; ignored")
                continue
            parsed = _number(raw, allow_bool=True)
            coverage[int(key)] = parsed if parsed is not None and parsed <= 1 else None
            if raw is not None and coverage[int(key)] is None:
                warnings.append(f"Coverage@{key}: invalid measurement reported as N/A")
        label = _provenance_label(provenance)
        if label == "UNVERIFIED INPUT":
            warnings.append("Benchmark provenance is missing or lacks formal approval evidence")
        termination = record.get("termination_reason")
        termination_counts = {str(termination): 1} if termination else {}
        counts: dict[str, tuple[float, float]] = {}
        for key, raw_count in _mapping(record.get("physical_counts")).items():
            count = _mapping(raw_count)
            numerator = _number(count.get("numerator"))
            denominator = _number(count.get("denominator"))
            if (key in {"collision_rate", "constraint_violation_rate"}
                    and numerator is not None and denominator is not None
                    and denominator > 0 and numerator <= denominator):
                counts[key] = (numerator, denominator)
        runs.append(ReportRun(
            case_id=case_id, method_id=method_id, run_id=run_id, source=str(path),
            status=str(record.get("status", "UNKNOWN")), benchmark_label=label,
            metrics=_metric_values(_mapping(record.get("metrics")), warnings),
            coverage_at_k=coverage, selected_k=_positive_int(record.get("selected_k")),
            terminations=termination_counts, warnings=warnings,
            settings=_mapping(payload.get("comparison_settings"))
            | _mapping(record.get("comparison_settings")), physical_counts=counts,
        ))
    cases = tuple(str(value) for value in _items(payload.get("cases")))
    methods = tuple(str(value) for value in _items(payload.get("methods")))
    return LoadedComparison(tuple(runs), cases, methods)


def _evaluation_metrics(
    raw: object,
) -> tuple[dict[str, float | None], dict[int, float | None], int | None, dict[str, Any], str]:
    """Read the highest exported K; Top-1 identity stays in original caller order."""
    payload = _mapping(raw)
    evaluations = [_mapping(value) for value in _items(payload.get("evaluations"))]
    if not evaluations and "config" in payload:
        evaluations = [payload]  # legacy unconfigured EvaluationResult
    by_k = {
        k: value for value in evaluations
        if (k := _positive_int(_mapping(value.get("config")).get("k_routes"))) is not None
    }
    coverage = {k: _number(value.get("coverage_at_k"), allow_bool=True)
                for k, value in by_k.items()}
    selected_k = max(by_k) if by_k else None
    selected = by_k[selected_k] if selected_k is not None else {}
    identities = _items(selected.get("top_k_hypothesis_ids"))
    top_one = next((
        _mapping(value) for value in _items(selected.get("trajectory_metrics"))
        if identities and _mapping(value).get("hypothesis_id") == identities[0]
    ), {})
    values = {
        "ade_m": _number(top_one.get("ade_m")),
        "fde_m": _number(top_one.get("fde_m")),
        "min_ade_at_k_m": _number(selected.get("min_ade_at_k_m")),
        "min_fde_at_k_m": _number(selected.get("min_fde_at_k_m")),
        "collision_rate": _number(selected.get("collision_rate")),
        "constraint_violation_rate": _number(selected.get("constraint_violation_rate")),
    }
    settings = _mapping(payload.get("metric_config"))
    label = _provenance_label(_mapping(selected.get("config")))
    return values, coverage, selected_k, settings, label


def _native(path: Path, method_id: str, run_id: str) -> LoadedComparison:
    directory = path if path.is_dir() else path.parent
    metrics_path = directory / "metrics.json"
    metrics = _read(metrics_path) if metrics_path.exists() else {}
    summary_path = directory / "summary.json"
    summary = _read(summary_path) if summary_path.exists() else {}
    config_path = directory / "config.json"
    config = _read(config_path) if config_path.exists() else {}
    # This is schema provenance from the existing runner, never a filename inference.
    experiment_path = directory / "experiment.json"
    experiment = _read(experiment_path) if experiment_path.exists() else {}
    dataset = _mapping(experiment.get("dataset"))
    default_label = "UNVERIFIED INPUT"
    if dataset.get("data_kind") == "SYNTHETIC":
        default_label = "SYNTHETIC REGRESSION"
    if "config" in metrics and "trajectory_metrics" in metrics:
        # Earlier fake regression exporter persisted one EvaluationResult per directory.
        legacy = metrics
        case_id = str(summary.get("case_id", directory.name))
        metrics = {case_id: {"legacy_gap": legacy}}
        event_path = directory / "event.json"
        event = _read(event_path) if event_path.exists() else {}
        summary = {"cases": [{"case_id": case_id, "gaps": [{
            "event_id": "legacy_gap",
            "candidates": len(event["candidates"]) if "candidates" in event else None,
            "termination_reason": event.get("termination_reason"),
        }]}]}
    summary_cases = {
        str(_mapping(case).get("case_id")): _mapping(case)
        for case in _items(summary.get("cases"))
    }
    case_ids = list(summary_cases)
    for case_id, raw in metrics.items():
        if isinstance(raw, dict) and case_id not in case_ids:
            case_ids.append(case_id)
    runs: list[ReportRun] = []
    for case_id in case_ids:
        case = summary_cases.get(case_id, {})
        gap_metrics = _mapping(metrics.get(case_id))
        summary_gaps = {
            str(_mapping(gap).get("event_id")): _mapping(gap)
            for gap in _items(case.get("gaps"))
        }
        event_ids = list(dict.fromkeys([*summary_gaps, *gap_metrics]))
        gap_values: list[dict[str, float | None]] = []
        gap_coverage: list[dict[int, float | None]] = []
        k_values: set[int] = set()
        labels: set[str] = set()
        settings: dict[str, Any] = {}
        gap_settings: list[dict[str, Any]] = []
        incompatible_gap_settings = False
        termination: Counter[str] = Counter()
        evaluation_statuses: Counter[str] = Counter()
        warnings: list[str] = []
        physical_counts: dict[str, tuple[float, float]] = {}
        counted_gaps: Counter[str] = Counter()
        for event_id in event_ids:
            gap = summary_gaps.get(event_id, {})
            raw = gap_metrics.get(event_id)
            values, coverage, selected_k, metric_settings, label = _evaluation_metrics(raw)
            values.update({
                "candidate_count": _number(gap.get("candidates")),
                "search_nodes": _number(gap.get("expanded_nodes")),
            })
            evaluations = _items(_mapping(raw).get("evaluations"))
            selected = next((
                _mapping(value) for value in evaluations
                if _mapping(_mapping(value).get("config")).get("k_routes") == selected_k
            ), _mapping(raw) if not evaluations else {})
            denominator = _number(selected.get("total_segment_count"))
            for key, count_key in (
                ("collision_rate", "collision_segment_count"),
                ("constraint_violation_rate", "constraint_violation_segment_count"),
            ):
                numerator = _number(selected.get(count_key))
                if (numerator is not None and denominator is not None and denominator > 0
                        and numerator <= denominator):
                    counted_gaps[key] += 1
                    previous = physical_counts.get(key, (0.0, 0.0))
                    physical_counts[key] = (previous[0] + numerator, previous[1] + denominator)
            gap_values.append(values)
            gap_coverage.append(coverage)
            if selected_k is not None:
                k_values.add(selected_k)
                labels.add(label)
            if settings and metric_settings and settings != metric_settings:
                incompatible_gap_settings = True
                warnings.append("Metric settings differ between gaps; compare separately")
            if metric_settings and metric_settings not in gap_settings:
                gap_settings.append(metric_settings)
            settings.update(metric_settings)
            if gap.get("termination_reason"):
                termination[str(gap["termination_reason"])] += 1
            evaluation_statuses[str(gap.get(
                "evaluation_status", "NO_REFERENCE" if raw is None else "EVALUATED",
            ))] += 1
        if len(k_values) > 1:
            # ADE remains readable, but a mixed-K minimum is not a valid comparison.
            warnings.append("Selected K differs between gaps: minADE/minFDE reported as N/A")
        values = {
            key: _average([gap.get(key) for gap in gap_values]) for key in METRICS
        }
        for key in ("search_nodes",):
            measured = [gap.get(key) for gap in gap_values]
            values[key] = (sum(float(v) for v in measured if v is not None)
                           if measured and all(v is not None for v in measured) else None)
        for key, (numerator, denominator) in list(physical_counts.items()):
            if counted_gaps[key] == sum(gap.get(key) is not None for gap in gap_values):
                values[key] = numerator / denominator
            else:
                physical_counts.pop(key)
                warnings.append(f"{key}: incomplete counts; using MEAN_OF_REPORTED_RATES")
        values["runtime_s"] = _number(case.get("inference_runtime_s"))
        if len(k_values) > 1:
            values["min_ade_at_k_m"] = values["min_fde_at_k_m"] = None
        coverage = {
            k: _average([gap.get(k) for gap in gap_coverage])
            for k in sorted({k for gap in gap_coverage for k in gap})
        }
        if incompatible_gap_settings:
            values = {key: None for key in METRICS}
            coverage = {k: None for k in coverage}
            settings = {"incompatible_gap_metric_configs": gap_settings}
            warnings.append("Incompatible gap metric settings: aggregate measurements "
                            "suppressed to N/A")
        default_status = ("COMPLETE" if len(termination) and sum(termination.values())
                          == len(event_ids) else "UNKNOWN")
        if not event_ids and "gaps" in case:
            default_status = "NO_BOUNDED_GAP"
        status = str(summary.get("status", default_status))
        if evaluation_statuses and set(evaluation_statuses) == {"NO_REFERENCE"}:
            status = "NO_REFERENCE"
        elif "NO_FEASIBLE_PATH" in termination:
            status = "NO_FEASIBLE_PATH"
        elif any(value != "COMPLETE" for value in termination):
            status = "PARTIAL_SEARCH"
        if evaluation_statuses.get("NO_REFERENCE"):
            warnings.append(f"{evaluation_statuses['NO_REFERENCE']} gap(s) have NO_REFERENCE")
        if len(gap_values) > 1:
            warnings.append("Native accuracy/coverage use equal-gap means; physical rates pool "
                            "segments; candidates average gaps; search sums gaps; "
                            "runtime is once per case")
        label = next(iter(labels)) if len(labels) == 1 else default_label
        runs.append(ReportRun(
            case_id, method_id, run_id, str(directory), status, label, values, coverage,
            next(iter(k_values)) if len(k_values) == 1 else None, dict(termination), warnings,
            {
                "dataset_version": config.get("dataset_version", summary.get("dataset_version")),
                "seed": config.get("seed", summary.get("seed")),
                "metric_config": settings,
            }, physical_counts, {
                key: {"available_gaps": sum(gap.get(key) is not None for gap in gap_values),
                      "total_gaps": len(gap_values)} for key in METRICS if key != "runtime_s"
            },
        ))
    return LoadedComparison(tuple(runs))


def load_comparison(input_path: Path) -> LoadedComparison:
    """Read a manifest, one runner directory, or a case/method[/run] output tree."""
    path = input_path.resolve()
    if path.is_file():
        payload = _read(path)
        if payload.get("schema_version") == SCHEMA:
            return _normalized(path, payload)
        if path.name not in {"metrics.json", "summary.json"}:
            raise ValueError("JSON input must be a comparison manifest or native metrics/summary")
        return _native(path, "deterministic_graph", path.parent.name)
    if not path.is_dir():
        raise FileNotFoundError(path)
    manifest = path / "comparison.json"
    if manifest.exists():
        return _normalized(manifest, _read(manifest))
    if (path / "metrics.json").exists() or (path / "summary.json").exists():
        return _native(path, "deterministic_graph", path.name)
    roots = sorted({p.parent for p in path.rglob("metrics.json")} | {
        p.parent for p in path.rglob("summary.json")
    })
    runs: list[ReportRun] = []
    for directory in roots:
        if "replay" in directory.relative_to(path).parts:
            continue
        parts = directory.relative_to(path).parts
        # The interface is root/case/method[/run]; native case IDs remain authoritative.
        method_id = parts[1] if len(parts) >= 2 else "deterministic_graph"
        run_id = "/".join(parts[2:]) if len(parts) >= 3 else directory.name
        runs.extend(_native(directory, method_id, run_id).runs)
    if not runs:
        raise ValueError(f"no benchmark runs found under {path}")
    return LoadedComparison(tuple(runs))


def _aggregate(values: Sequence[float | None]) -> dict[str, Any]:
    present = [value for value in values if value is not None]
    return {
        "mean": mean(present) if present else None,
        "available_runs": len(present), "total_runs": len(values),
    }


def summarize(comparison: LoadedComparison) -> dict[str, Any]:
    """Equal independent-run means, with visible denominators and failed/missing rows."""
    cases = list(dict.fromkeys([*comparison.declared_cases, *(r.case_id for r in comparison.runs)]))
    methods = list(dict.fromkeys([
        *comparison.declared_methods, *(r.method_id for r in comparison.runs),
    ]))
    labels = list(dict.fromkeys(run.benchmark_label for run in comparison.runs))
    label = (labels[0] if len(labels) == 1 else "MIXED INPUT — " + "; ".join(labels)
             if labels else "UNVERIFIED INPUT")
    rows: list[dict[str, Any]] = []
    for case_id in cases:
        for method_id in methods:
            runs = [r for r in comparison.runs if (r.case_id, r.method_id) == (case_id, method_id)]
            selected_ks = {r.selected_k for r in runs if r.selected_k is not None}
            warnings = list(dict.fromkeys(message for r in runs for message in r.warnings))
            settings = {json.dumps(r.settings, sort_keys=True) for r in runs if r.settings}
            if len(settings) > 1:
                warnings.append("Comparison settings differ across runs; "
                                "protocol compatibility REVIEW")
            metrics = {key: _aggregate([r.metrics.get(key) for r in runs]) for key in METRICS}
            for key in ("collision_rate", "constraint_violation_rate"):
                measured = [r for r in runs if r.metrics.get(key) is not None]
                if measured and all(key in r.physical_counts for r in measured):
                    numerator = sum(r.physical_counts[key][0] for r in measured)
                    denominator = sum(r.physical_counts[key][1] for r in measured)
                    metrics[key].update(mean=numerator / denominator,
                                        numerator=numerator, denominator=denominator,
                                        aggregation="POOLED_SEGMENT_RATE")
                else:
                    metrics[key]["aggregation"] = "MEAN_OF_REPORTED_RATES"
            if len(selected_ks) > 1:
                warnings.append("Selected K differs across runs: minADE/minFDE reported as N/A")
                for key in ("min_ade_at_k_m", "min_fde_at_k_m"):
                    metrics[key] = _aggregate([None for _ in runs])
            k_values = sorted({k for r in runs for k in r.coverage_at_k})
            coverage = {
                str(k): _aggregate([r.coverage_at_k.get(k) for r in runs]) for k in k_values
            }
            if len(settings) > 1:
                warnings.append("Incompatible invariant settings: aggregate measurements "
                                "suppressed to N/A")
                metrics = {key: _aggregate([None for _ in runs]) for key in METRICS}
                coverage = {str(k): _aggregate([None for _ in runs]) for k in k_values}
            terminations = dict(sum((Counter(r.terminations) for r in runs), Counter()))
            categories: dict[str, Any] = {}
            for category, required in ACCEPTANCE_CATEGORIES.items():
                available = []
                for key in required:
                    if key == "coverage_at_k":
                        has_metric = any(value["mean"] is not None
                                         for value in coverage.values())
                    elif key == "termination_reason":
                        has_metric = bool(terminations)
                    else:
                        has_metric = metrics[key]["mean"] is not None
                    if has_metric:
                        available.append(key)
                categories[category] = {
                    "acceptance": "NOT_ASSESSED",
                    "criteria_status": "UNRESOLVED_RESEARCH_SETTING",
                    "measurement_status": ("MEASUREMENTS_AVAILABLE"
                                           if len(available) == len(required)
                                           else "PARTIAL_MEASUREMENTS" if available
                                           else "NO_MEASUREMENTS"),
                    "available_metrics": available,
                    "missing_metrics": [key for key in required if key not in available],
                }
            rows.append({
                "case_id": case_id, "method_id": method_id,
                "method_label": METHOD_LABELS.get(method_id, method_id),
                "run_count": len(runs), "run_ids": [r.run_id for r in runs],
                "sources": [r.source for r in runs],
                "benchmark_labels": list(dict.fromkeys(r.benchmark_label for r in runs)),
                "status_counts": dict(Counter(r.status for r in runs)) or {"MISSING_RUN": 1},
                "termination_counts": terminations, "acceptance_categories": categories,
                "selected_k": next(iter(selected_ks)) if len(selected_ks) == 1 else None,
                "metrics": metrics, "coverage_at_k": coverage, "warnings": warnings,
                "gap_availability": {r.run_id: r.gap_availability for r in runs},
            })
    comparison_warnings: list[str] = []
    selected_ks = {row["selected_k"] for row in rows if row["selected_k"] is not None}
    if len(selected_ks) > 1:
        comparison_warnings.append("K varies across rows; minimum errors require matched K")
    all_settings = {json.dumps(r.settings, sort_keys=True) for r in comparison.runs if r.settings}
    if len(all_settings) > 1:
        comparison_warnings.append("Dataset/seed/metric comparison settings differ; "
                                   "protocol compatibility REVIEW")
    return {
        "schema_version": SCHEMA, "benchmark_label": label or "UNVERIFIED INPUT",
        "comparison_warnings": comparison_warnings,
        "aggregation": "ARITHMETIC_MEAN_OF_AVAILABLE_INDEPENDENT_RUNS",
        "missing_policy": "NULL_AND_N/A; never zero-filled; availability counts retained",
        "ordering": "DECLARED_OR_DISCOVERY_IDENTITY_ORDER; never Ground Truth metric order",
        "native_gap_aggregation": "ACCURACY/COVERAGE=EQUAL_GAP_MEAN; "
        "PHYSICAL=POOLED_SEGMENT_RATE; CANDIDATE=MEAN; SEARCH=SUM; RUNTIME=ONCE_PER_CASE",
        "cases": cases, "methods": methods, "rows": rows,
    }


def _row_label(row: Mapping[str, Any]) -> str:
    statuses = row["status_counts"]
    status = "" if set(statuses) == {"COMPLETE"} else "\n" + "/".join(statuses)
    return f"{row['case_id']}\n{row['method_label']}{status}"


def _save(fig: Any, path: Path, *, footer_fraction: float = 0.0) -> None:
    fig.tight_layout(rect=(0, footer_fraction, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _bar_chart(summary: Mapping[str, Any], key: str, output: Path) -> bool:
    rows = summary["rows"]
    title, unit, filename = METRICS[key]
    values = [row["metrics"][key]["mean"] for row in rows]
    if all(value is None for value in values):
        return False
    fig, axis = plt.subplots(figsize=(max(7, min(24, len(rows) * 1.15)), 5.5))
    for index, (row, value) in enumerate(zip(rows, values, strict=True)):
        if value is None:
            axis.text(index, 0.02, "N/A", transform=axis.get_xaxis_transform(), ha="center")
        else:
            axis.bar(index, value)
            count = row["metrics"][key]
            axis.annotate(f"{value:.3g}\n{count['available_runs']}/{count['total_runs']}",
                          (index, value), xytext=(0, 4), textcoords="offset points", ha="center")
    tick_labels = [_row_label(row) + (f"\nK={row['selected_k'] or 'N/A'}"
                                    if "at_k" in key else "") for row in rows]
    axis.set_xticks(range(len(rows)), tick_labels, rotation=25, ha="right")
    axis.set_xlim(-0.6, len(rows) - 0.4)
    axis.set_ylim(bottom=0)
    axis.margins(y=0.2)
    if unit == "ratio":
        axis.set_ylim(0, 1.16)
    axis.set_ylabel(f"{title} ({unit})")
    axis.set_xlabel("Case / Method (annotations: available / total runs)")
    suffix = " — exported K shown in summary" if "at_k" in key else ""
    axis.set_title(f"{summary['benchmark_label']}\n{title}{suffix}")
    _save(fig, output / filename)
    return True


def _coverage_chart(summary: Mapping[str, Any], output: Path) -> bool:
    rows = summary["rows"]
    ks = sorted({int(k) for row in rows for k in row["coverage_at_k"]})
    if not ks:
        return False
    fig, axis = plt.subplots(figsize=(9, 6))
    any_present = False
    missing: list[str] = []
    for row in rows:
        values = [row["coverage_at_k"].get(str(k), {}).get("mean") for k in ks]
        label = f"{row['case_id']} / {row['method_label']}"
        if any(value is not None for value in values):
            any_present = True
            axis.plot(ks, [value if value is not None else math.nan for value in values],
                      marker="o", label=label)
        else:
            missing.append(f"{label}: N/A")
        for k, value in zip(ks, values, strict=True):
            if value is None and any(v is not None for v in values):
                missing.append(f"{label} @K={k}: N/A")
    if not any_present:
        plt.close(fig)
        return False
    axis.set_xticks(ks)
    axis.set_ylim(0, 1.08)
    axis.set_xlabel("K (distinct candidate routes, exported order)")
    axis.set_ylabel("Mean measured Coverage@K (fraction)")
    axis.set_title(f"{summary['benchmark_label']}\nTop-K Coverage")
    axis.legend(loc="best", fontsize="small")
    footer_fraction = 0.0
    if missing:
        footer_lines = textwrap.wrap("Missing: " + "; ".join(missing), width=115,
                                     break_long_words=False, break_on_hyphens=False)
        footer_height = 0.16 * len(footer_lines) + 0.15
        figure_height = 6 + footer_height
        fig.set_size_inches(9, figure_height)
        footer_fraction = footer_height / figure_height
        fig.text(0.01, 0.015, "\n".join(footer_lines), fontsize=8, va="bottom")
    _save(fig, output / "coverage_at_k.png", footer_fraction=footer_fraction)
    return True


def _physical_chart(summary: Mapping[str, Any], output: Path) -> bool:
    keys = ("collision_rate", "constraint_violation_rate", "impossible_transition_rate")
    rows = summary["rows"]
    if all(row["metrics"][key]["mean"] is None for row in rows for key in keys):
        return False
    fig, axis = plt.subplots(figsize=(max(8, min(24, len(rows) * 1.25)), 6))
    for metric_index, key in enumerate(keys):
        positions = [index + (metric_index - 1) * 0.25 for index in range(len(rows))]
        values = [row["metrics"][key]["mean"] for row in rows]
        axis.bar(positions, [value if value is not None else math.nan for value in values],
                 width=0.23, label=METRICS[key][0])
        for x, value in zip(positions, values, strict=True):
            if value is None:
                axis.text(x, 0.02, "N/A", transform=axis.get_xaxis_transform(),
                          ha="center", rotation=90, fontsize=7)
    axis.set_xticks(range(len(rows)), [_row_label(row) for row in rows], rotation=25, ha="right")
    axis.set_ylim(0, 1.12)
    axis.set_xlim(-0.6, len(rows) - 0.4)
    axis.set_ylabel("Violation Rate (fraction; denominators in summary)")
    axis.set_xlabel("Case / Method")
    axis.set_title(f"{summary['benchmark_label']}\nPhysical Validity")
    axis.legend(fontsize="small")
    _save(fig, output / "physical_validity.png")
    return True


def _termination_chart(summary: Mapping[str, Any], output: Path) -> bool:
    rows = summary["rows"]
    categories = list(dict.fromkeys(key for row in rows for key in row["termination_counts"]))
    if not categories:
        return False
    fig, axis = plt.subplots(figsize=(max(8, min(24, len(rows) * 1.15)), 6))
    bottoms = [0] * len(rows)
    for category in categories:
        counts = [row["termination_counts"].get(category, 0) for row in rows]
        axis.bar(range(len(rows)), counts, bottom=bottoms, label=category)
        bottoms = [a + b for a, b in zip(bottoms, counts, strict=True)]
    for index, row in enumerate(rows):
        if not row["termination_counts"]:
            axis.text(index, 0.02, "N/A", transform=axis.get_xaxis_transform(), ha="center")
    axis.set_xticks(range(len(rows)), [_row_label(row) for row in rows], rotation=25, ha="right")
    axis.set_ylabel("Exported Terminations (count; native unit: gap)")
    axis.set_xlabel("Case / Method")
    axis.set_title(f"{summary['benchmark_label']}\nTermination Categories")
    axis.legend(fontsize="small")
    _save(fig, output / "termination_categories.png")
    return True


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _format(value: object) -> str:
    return "N/A" if value is None else f"{float(str(value)):.6g}"


def _markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        f"# {_cell(summary['benchmark_label'])} — Benchmark Comparison", "",
        "Equal-run means use only measured values. Every value has available/total run counts "
        "in JSON; missing values remain N/A. Failed and missing cases stay visible. "
        "Method order follows input identities and never Ground Truth accuracy.", "",
        "| Case | Method | Status | Runs | K | ADE (m) | FDE (m) | minADE@K (m) | "
        "minFDE@K (m) | Coverage@K | Collision | Constraint | Runtime (s) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary["rows"]:
        metrics = row["metrics"]
        k = row["selected_k"]
        coverage = row["coverage_at_k"].get(str(k), {}).get("mean")
        cells: list[object] = [
            row["case_id"], row["method_label"],
            ", ".join(f"{key}:{count}" for key, count in row["status_counts"].items()),
            row["run_count"], k if k is not None else "N/A",
            *(_format(metrics[key]["mean"]) for key in (
                "ade_m", "fde_m", "min_ade_at_k_m", "min_fde_at_k_m",
            )),
            _format(coverage), _format(metrics["collision_rate"]["mean"]),
            _format(metrics["constraint_violation_rate"]["mean"]),
            _format(metrics["runtime_s"]["mean"]),
        ]
        lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    lines.extend(["", "## Acceptance categories", "",
                  "| Category | Available rows | Partial rows | Missing rows | Acceptance |",
                  "| --- | --- | --- | --- | --- |"])
    for category in ACCEPTANCE_CATEGORIES:
        statuses = Counter(row["acceptance_categories"][category]["measurement_status"]
                           for row in summary["rows"])
        lines.append(f"| {category} | {statuses['MEASUREMENTS_AVAILABLE']} | "
                     f"{statuses['PARTIAL_MEASUREMENTS']} | {statuses['NO_MEASUREMENTS']} | "
                     "NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |")
    lines.extend(["", "## Availability and review", ""])
    lines.extend(f"- REVIEW: {_cell(message)}"
                 for message in summary["comparison_warnings"])
    for row in summary["rows"]:
        counts = ", ".join(
            f"{key}={value['available_runs']}/{value['total_runs']}"
            for key, value in row["metrics"].items()
        )
        coverage_counts = ", ".join(
            f"Coverage@{key}={value['available_runs']}/{value['total_runs']}"
            for key, value in row["coverage_at_k"].items()
        )
        lines.append(f"- {_cell(row['case_id'])} / {_cell(row['method_label'])}: {counts}"
                     + (f"; {coverage_counts}" if coverage_counts else ""))
        lines.extend(f"  - REVIEW: {_cell(message)}" for message in row["warnings"])
    lines.extend(["", "## Chart artifacts", ""])
    lines.extend(f"- [{filename}]({filename})" for filename in summary["generated_charts"])
    lines.extend(["", "## Skipped charts", ""])
    lines.extend(f"- {_cell(name)}: {_cell(reason)}"
                 for name, reason in summary["skipped_charts"].items())
    lines.extend([
        "", "Native metrics reflect configured synthetic AABB/corridor checks; they do not "
        "certify Blender mesh physics. Missing Projection Error, impossible transitions, "
        "feasible recall, path/time errors are never inferred from other measurements.",
        "Formal Coverage distance/epsilon, clearance and contact semantics require an "
        "approved protocol. A supplied provenance label is not independent certification.",
    ])
    return "\n".join(lines) + "\n"


def generate_comparison(input_path: Path, output_path: Path) -> dict[str, Any]:
    """Generate separate PNG charts, a machine-readable summary and a Markdown table."""
    comparison = load_comparison(input_path)
    summary = summarize(comparison)
    output = output_path.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("comparison output directory must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []
    skipped: dict[str, str] = {}
    for key, (_, _, filename) in METRICS.items():
        if _bar_chart(summary, key, output):
            generated.append(filename)
        else:
            skipped[filename] = f"{key}: no measured values; all rows are N/A"
    for filename, plot in (
        ("coverage_at_k.png", _coverage_chart),
        ("physical_validity.png", _physical_chart),
        ("termination_categories.png", _termination_chart),
    ):
        if plot(summary, output):
            generated.append(filename)
        else:
            skipped[filename] = "No exported measurements; all rows are N/A"
    summary["generated_charts"] = generated
    summary["skipped_charts"] = skipped
    (output / "benchmark_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (output / "benchmark_summary.md").write_text(_markdown(summary), encoding="utf-8")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        summary = generate_comparison(args.input, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"{summary['benchmark_label']}: {len(summary['rows'])} case/method rows, "
          f"{len(summary['generated_charts'])} charts → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
