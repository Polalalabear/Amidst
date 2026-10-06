"""Evaluate saved robustness cases without changing inference or metric semantics.

Successful cases delegate to evaluate_pilot_downstream.evaluate_saved_pilot.
Missing/unsupported/empty predictions receive NOT_COMPUTABLE metrics, with null
ADE/FDE/minima/Coverage rather than artificial zeros or inferred endpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

from amidst.datasets.pilot import PILOT_LABEL


def _load_evaluator() -> Any:
    spec = importlib.util.spec_from_file_location(
        "robustness_existing_pilot_evaluator",
        Path(__file__).with_name("evaluate_pilot_downstream.py"),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("existing bounded pilot evaluator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


downstream = _load_evaluator()
INFERENCE_FILES = (
    *downstream.INFERENCE_FILES,
    "inference_report.md",
    "digests.json",
    "robustness_report.md",
    "untrusted_binding.json",
)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def frozen_digests(root: Path, status_path: Path) -> dict[str, Any]:
    return {
        "robustness_status_sha256": digest(status_path),
        "inference_artifact_sha256": {
            name: digest(root / name) for name in INFERENCE_FILES if (root / name).is_file()
        },
    }


def load_status(path: Path) -> dict[str, Any]:
    status = json.loads(path.read_text())
    if not isinstance(status, dict) or status.get("label") != PILOT_LABEL:
        raise ValueError("robustness status must carry PILOT / SYNTHETIC SAMPLE label")
    if not isinstance(status.get("scenario_id"), str) or not status["scenario_id"].strip():
        raise ValueError("robustness status must identify its scenario")
    if not isinstance(status.get("evaluation_eligible"), bool):
        raise ValueError("robustness evaluation eligibility must be explicit boolean")
    return status


def saved_prediction_check(root: Path, status: dict[str, Any]) -> tuple[bool, str | None]:
    """Check saved predictions before any truth access, even if status claims eligibility."""
    if not status["evaluation_eligible"]:
        return False, "EMPTY_RECONSTRUCTION" if search_result_available(status) else (
            "INFERENCE_NOT_AVAILABLE"
        )
    path = root / "gap_events.json"
    if not path.is_file():
        return False, "ELIGIBILITY_HAS_NO_SAVED_GAP"
    payload = downstream.load_labeled(path)
    gaps = payload.get("gaps")
    if not isinstance(gaps, list) or len(gaps) != 1:
        return False, "ELIGIBILITY_HAS_NO_SINGLE_BOUNDED_GAP"
    event = gaps[0].get("event", {})
    trajectories, candidates = event.get("trajectories"), event.get("candidates")
    if not isinstance(trajectories, list) or not trajectories:
        return False, "ELIGIBILITY_HAS_NO_TIMED_PREDICTION"
    if not isinstance(candidates, list) or not candidates:
        return False, "ELIGIBILITY_HAS_NO_CANDIDATE_ROUTE"
    if status.get("candidate_count") != len(candidates) or status.get("hypothesis_count") != len(
        trajectories
    ):
        raise ValueError("robustness status prediction counts differ from saved inference")
    return True, None


def search_result_available(status: dict[str, Any]) -> bool:
    return status.get("termination_reason") not in (None, "NOT_RUN")


def _physical_validity() -> dict[str, Any]:
    return {
        "status": "PARTIAL_PROVISIONAL",
        "mesh_collision_certified": False,
        "wall_authority_complete": False,
        "blender_mesh_collision_rate": None,
        "assessment": "No Blender mesh/body clearance or physical-scale certification.",
    }


def _not_computable(
    status: dict[str, Any],
    reason_code: str,
    snapshot: dict[str, Any],
    coverage_epsilon: float,
) -> dict[str, Any]:
    returned_search = search_result_available(status)
    detail = status.get("reason") or (
        "Saved inference has no timed prediction to evaluate."
        if returned_search
        else "Inference did not provide a bounded search result."
    )
    return {
        "label": PILOT_LABEL,
        "scope": "PILOT_ROBUSTNESS_EVALUATION_ONLY_NOT_FORMAL_CASES_1_3",
        "scenario_id": status["scenario_id"],
        "status": "NOT_COMPUTABLE",
        "reason_code": reason_code,
        "reason": detail,
        "inference_outcome": status.get("outcome"),
        "failed_stage": status.get("failed_stage"),
        "stage_states": status.get("stage_states"),
        "termination_reason": status.get("termination_reason"),
        "saved_search_result_available": returned_search,
        "candidate_count": status.get("candidate_count"),
        "candidate_count_state": status.get("candidate_count_state"),
        "hypothesis_count": status.get("hypothesis_count"),
        "saved_evaluation_eligible": status["evaluation_eligible"],
        "coordinate_units": "BLENDER_SCENE_UNITS",
        "physical_scale_authority": "UNVERIFIED",
        "coverage_epsilon_scene_units": coverage_epsilon,
        "coverage_comparison": "STRICTLY_LESS_THAN_ADE",
        "ground_truth_read": False,
        "ground_truth_sha256": None,
        "configured_evaluation": None,
        "physical_validity": _physical_validity(),
        "inference_artifacts_unchanged_after_evaluation": True,
        "frozen_inference": snapshot,
        "formal_benchmark_executed": False,
        "formal_benchmark_semantics_modified": False,
        "summaries": [
            {
                "k": k,
                "ade_first_primary_scene_units": None,
                "fde_first_primary_scene_units": None,
                "min_ade_at_k_scene_units": None,
                "min_fde_at_k_scene_units": None,
                "coverage_at_k": None,
                "selected_route_count": None,
                "selected_hypothesis_ids": None,
            }
            for k in (1, 2, 3)
        ],
    }


def evaluate_saved_robustness(
    root: Path,
    truth_path: Path,
    context_path: Path,
    *,
    coverage_epsilon: float = 0.02,
    status_path: Path | None = None,
) -> dict[str, Any]:
    """Evaluate completed predictions or honestly record why evaluation is unavailable."""
    if (
        not isinstance(coverage_epsilon, int | float)
        or isinstance(coverage_epsilon, bool)
        or not math.isfinite(coverage_epsilon)
        or coverage_epsilon <= 0
    ):
        raise ValueError("coverage epsilon must be an explicit positive diagnostic setting")
    if not root.is_dir():
        raise ValueError("saved robustness run directory is unavailable")
    for name in ("metrics.json", "metrics.md"):
        if (root / name).exists():
            raise FileExistsError(root / name)
    status_path = status_path or root / "robustness_status.json"
    status = load_status(status_path)
    before = frozen_digests(root, status_path)
    eligible, reason = saved_prediction_check(root, status)
    if eligible:
        # Delegate unchanged: it validates saved domain inputs before opening GT,
        # then uses the existing exact-extent, interpolation and Top-K policies.
        report = downstream.evaluate_saved_pilot(
            root,
            truth_path,
            context_path,
            coverage_epsilon=coverage_epsilon,
        )
        report.update(
            status="COMPUTED",
            scenario_id=status["scenario_id"],
            robustness_inference_outcome=status.get("outcome"),
            saved_evaluation_eligible=True,
            ground_truth_read=True,
            formal_benchmark_executed=False,
            formal_benchmark_semantics_modified=False,
            frozen_inference=before,
        )
    else:
        assert reason is not None
        report = _not_computable(status, reason, before, coverage_epsilon)
    if frozen_digests(root, status_path) != before:
        raise RuntimeError("robustness evaluation changed saved inference/status evidence")
    report["inference_artifacts_unchanged_after_evaluation"] = True
    (root / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    if eligible:
        existing = (root / "metrics.md").read_text()
        (root / "metrics.md").write_text(
            existing + f"\nRobustness scenario: `{status['scenario_id']}`; status **COMPUTED**.\n"
            "Existing metric semantics and all inference artifacts were preserved.\n"
        )
    else:
        lines = [
            f"# {PILOT_LABEL} — robustness evaluation",
            "",
            f"Scenario: `{status['scenario_id']}`; status **NOT_COMPUTABLE**.",
            f"Reason: `{reason}` — {report['reason']}",
            f"Inference outcome: `{status.get('outcome')}`; failed stage: "
            f"`{status.get('failed_stage')}`; termination: `{status.get('termination_reason')}`.",
            f"Saved search result available: `{report['saved_search_result_available']}`.",
            "No GT was read and no prediction or metric value was fabricated.",
            "",
            "| K | ADE | FDE | minADE@K | minFDE@K | Coverage@K |",
            "| --- | --- | --- | --- | --- | --- |",
            "| 1 | N/A | N/A | N/A | N/A | N/A |",
            "| 2 | N/A | N/A | N/A | N/A | N/A |",
            "| 3 | N/A | N/A | N/A | N/A | N/A |",
            "",
            "Physical validity remains PARTIAL / PROVISIONAL; Blender mesh collision rate N/A.",
            "Native scene units have unverified physical scale. No formal Case 1–3 execution.",
            "",
        ]
        (root / "metrics.md").write_text("\n".join(lines))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--status", type=Path)
    parser.add_argument("--coverage-epsilon-scene-units", type=float, default=0.02)
    args = parser.parse_args()
    report = evaluate_saved_robustness(
        args.run,
        args.ground_truth,
        args.context,
        coverage_epsilon=args.coverage_epsilon_scene_units,
        status_path=args.status,
    )
    print(
        json.dumps(
            {
                "label": PILOT_LABEL,
                "scenario_id": report["scenario_id"],
                "status": report["status"],
                "summaries": report["summaries"],
            }
        )
    )


if __name__ == "__main__":
    main()
