"""Compare a complete fresh reviewed delivery, retaining failure and N/A content."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from amidst.finalization.reviewed_pipeline import compare_frozen_runs, verify_dataset

RUNTIME_FIELDS = frozenset({"runtime_s", "inference_runtime_s", "runtime_seconds"})
COUNT_FIELDS = frozenset({
    "count", "run_count", "gap_count", "sample_count", "missing_count", "failed_count",
    "available_count", "value_count", "measured_count",
    "available_runs", "total_runs", "missing_runs", "failed_runs",
})
RUNTIME_CHARTS = frozenset({"runtime_s.png", "runtime.png"})


def _canonical(value: Any, root: Path, *, runtime: bool = False) -> Any:
    if isinstance(value, dict):
        return {key: _canonical(item, root, runtime=(
            key in RUNTIME_FIELDS or runtime and key not in COUNT_FIELDS
        )) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical(item, root, runtime=runtime) for item in value]
    if isinstance(value, (int, float)) and not isinstance(value, bool) and runtime:
        return "<MEASURED_RUNTIME>"
    if isinstance(value, str):
        prefix = str(root.resolve()) + "/"
        if value.startswith(prefix):
            return "<EVALUATION>/" + value[len(prefix):]
    return value


def _markdown(path: Path, root: Path) -> list[str]:
    rows: list[str] = []
    runtime_columns: set[int] = set()
    for line in path.read_text().splitlines():
        if not line.startswith("|"):
            runtime_columns = set()
            rows.append(line.replace(str(root.resolve()), "<EVALUATION>"))
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if any(cell in {"Runtime (s)", "inference_runtime_s", "runtime_s"} for cell in cells):
            runtime_columns = {index for index, cell in enumerate(cells)
                               if cell in {"Runtime (s)", "inference_runtime_s", "runtime_s"}}
        elif runtime_columns and not all(set(cell) <= {"-", ":"} for cell in cells):
            for index in runtime_columns:
                if cells[index] not in {"N/A", "None", "null", ""}:
                    cells[index] = "<MEASURED_RUNTIME>"
        rows.append("|".join(cells))
    return rows


def _files(root: Path) -> dict[str, Path]:
    return {str(path.relative_to(root)): path for path in root.rglob("*")
            if path.is_file() and path.suffix in {".json", ".png", ".md", ".csv", ".rrd"}}


def compare_reviewed_deliveries(
    *, local_dataset: Path, fresh_dataset: Path, local_inference: Path,
    fresh_inference: Path, local_evaluation: Path, fresh_evaluation: Path,
) -> dict[str, Any]:
    """Compare dataset bytes, every frozen inference artifact and reports/demos.

    Runtime measurements remain available but their numeric values and runtime
    PNG pixels differ. RRD container bytes differ; their existence, verified-reader
    receipt and full canonical presentation (including ordering) remain required.
    """
    first_dataset = verify_dataset(local_dataset, inference_only=False)
    second_dataset = verify_dataset(fresh_dataset, inference_only=False)
    dataset_equal = first_dataset == second_dataset
    inference = compare_frozen_runs(local_inference, fresh_inference)
    first_files, second_files = _files(local_evaluation), _files(fresh_evaluation)
    differences: list[str] = []
    excluded: list[str] = []
    counts = {"json": 0, "markdown": 0, "csv": 0, "png": 0, "rrd": 0}
    for relative in sorted(set(first_files) | set(second_files)):
        if relative not in first_files or relative not in second_files:
            differences.append(relative + ": missing artifact")
            continue
        first, second = first_files[relative], second_files[relative]
        if first.suffix == ".rrd":
            if not first.stat().st_size or not second.stat().st_size:
                differences.append(relative + ": empty recording")
            presentation = first.parent / "presentation.json"
            other_presentation = second.parent / "presentation.json"
            if not presentation.is_file() or not other_presentation.is_file() or any(
                json.loads(path.read_bytes()).get("rrd_reader_verified") is not True
                for path in (presentation, other_presentation)
            ):
                differences.append(relative + ": missing verified reader receipt")
            excluded.append(relative + ": container metadata bytes only")
            counts["rrd"] += 1
        elif first.suffix == ".png" and first.name in RUNTIME_CHARTS:
            excluded.append(relative + ": measured runtime plot pixels only")
        elif first.suffix == ".json":
            equal = _canonical(json.loads(first.read_bytes()), local_evaluation) == (
                _canonical(json.loads(second.read_bytes()), fresh_evaluation)
            )
            if not equal:
                differences.append(relative + ": canonical JSON differs")
            counts["json"] += 1
        elif first.suffix == ".md":
            if _markdown(first, local_evaluation) != _markdown(second, fresh_evaluation):
                differences.append(relative + ": canonical Markdown differs")
            counts["markdown"] += 1
        elif first.suffix == ".csv":
            def read_csv(path: Path, root: Path) -> list[dict[str, Any]]:
                with path.open(newline="") as stream:
                    return [_canonical({key: (
                        "<MEASURED_RUNTIME>" if key in RUNTIME_FIELDS and value else value
                    ) for key, value in row.items()}, root) for row in csv.DictReader(stream)]
            if read_csv(first, local_evaluation) != read_csv(second, fresh_evaluation):
                differences.append(relative + ": canonical CSV differs")
            counts["csv"] += 1
        else:
            if hashlib.sha256(first.read_bytes()).digest() != (
                hashlib.sha256(second.read_bytes()).digest()
            ):
                differences.append(relative + ": byte SHA-256 differs")
            counts["png"] += 1
    complete = dataset_equal and inference["status"] == "PASS" and not differences
    # An empty report cannot silently establish delivery reproducibility.
    required = {"verification.json", "benchmark_table.json", "benchmark_table.csv",
                "benchmark_table.md", "charts/benchmark_summary.json"}
    if "verification.json" in first_files:
        execution = json.loads(first_files["verification.json"].read_bytes()).get(
            "formal_case_execution", {}
        )
        if set(execution) != {"case1", "case2", "case3"}:
            differences.append("verification.json: missing original case execution statuses")
        for case_id, executed in execution.items():
            if executed is True:
                required.update(f"demos/{case_id}/{name}" for name in (
                    "presentation.json", "preview.png", "reviewed.rrd", "README.md",
                ))
    missing = sorted(required - set(first_files))
    complete = complete and not missing and not differences
    return {
        "schema_version": "phase1-reviewed-fresh-delivery-comparison-v1",
        "status": "PASS" if complete else "FAIL",
        "dataset_manifest_and_all_artifacts_equal": dataset_equal,
        "inference": inference,
        "report_and_demo_comparison_counts": counts,
        "differences": differences, "missing_required_reports": missing,
        "explicit_nondeterministic_exclusions": excluded,
        "case_failure_na_and_candidate_order_preserved": True,
        "overall_exit_gate_or_freeze_granted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("local_dataset", "fresh_dataset", "local_inference", "fresh_inference",
                 "local_evaluation", "fresh_evaluation"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = vars(parser.parse_args())
    output = args.pop("output")
    result = compare_reviewed_deliveries(**args)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "differences": result["differences"]}))


if __name__ == "__main__":
    main()
