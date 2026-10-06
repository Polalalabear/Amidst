"""Replay fresh Phase 1 inputs as diagnostics; never promote them to formal cases.

Only strict observations/context enter projection or the legacy Graph consumer.
GT is opened after inference has been frozen, solely by evaluation/debug code.
The additive selected points are not supplied to the unchanged Graph contract.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from amidst.datasets.pilot import (
    PilotInferenceContext,
    PilotObservationExport,
    run_pilot_downstream,
)
from amidst.storage.json_files import write_json

ROOT = Path(__file__).resolve().parents[1]
INFERENCE_FILES = (
    "projected_frames.json", "aggregation.json", "pipeline_config.json", "gap_events.json",
    "candidates.json", "events.json", "topology_evidence.json", "inference_report.json",
    "inference_report.md", "digests.json",
)


def module(name: str) -> Any:
    path = ROOT / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location("finalization_replay_" + name, path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_dataset(root: Path, *, inference_only: bool = True) -> dict[str, Any]:
    manifest = json.loads((root / "manifest.json").read_bytes())
    for relative, expected in manifest["artifacts"].items():
        if inference_only and not relative.startswith("inference/"):
            continue
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path) != expected:
            raise ValueError("dataset artifact differs from its frozen manifest: " + relative)
    return manifest


def projection_error(sidecar: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    """Post-freeze evaluation, with no threshold, epsilon, filtering or ranking."""
    if (
        truth.get("provenance") != "GROUND_TRUTH"
        or truth.get("source_asset_sha256") != sidecar["source_asset_sha256"]
        or any(row["site_id"] != truth.get("site_id") for row in sidecar["rows"])
    ):
        raise ValueError("evaluation truth must match source and GT provenance")
    samples = truth["samples"]
    if len({row["timestamp"] for row in samples}) != len(samples):
        raise ValueError("evaluation reference timestamps must be unique")
    by_time = {row["timestamp"]: row["position"] for row in samples}
    errors = [
        math.dist(row["selected_world_position"], by_time[row["timestamp"]])
        for row in sidecar["rows"] if row["selected_world_position"] is not None
    ]
    return {
        "status": "DIAGNOSTIC", "formal_cases_executed": False,
        "evaluated_visible_timestamp_count": len(errors),
        "mean_error_bu": sum(errors) / len(errors) if errors else None,
        "rms_error_bu": math.sqrt(sum(value**2 for value in errors) / len(errors))
        if errors else None,
        "mean_error_m": sum(errors) / len(errors) * .0247 if errors else None,
        "metres_per_bu": .0247, "scale_authority": "APPROVED",
        "selection_uses_gt": False, "gt_loaded_after_inference": True,
        "metric_is_full_trajectory_ade": False,
    }


def run_cli(script: str, arguments: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *arguments],
        check=False, capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def inference_hashes(root: Path) -> dict[str, str]:
    return {name: digest(root / name) for name in INFERENCE_FILES}


def write_demo(
    context: PilotInferenceContext, sidecar: dict[str, Any], truth: dict[str, Any],
    events: list[dict[str, Any]], output: Path,
) -> dict[str, Any]:
    """Display frozen inference; GT has an independent, initially hidden layer."""
    import matplotlib
    import rerun as rr
    import rerun.blueprint as rrb

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output.mkdir(parents=True, exist_ok=False)
    presentation = {
        "status": "DIAGNOSTIC", "source_asset_sha256": context.source_asset_sha256,
        "cameras": [camera.model_dump(mode="json") for camera in context.cameras],
        "projection_rows": sidecar["rows"], "existing_graph_events": events,
        "scope": context.zone.model_dump(mode="json"),
        "authority": "PROVISIONAL_NOT_CERTIFIED", "gt_debug_default_visible": False,
        "gt_debug": truth, "full_school_mesh_displayed": False,
        "collision_pruned_candidate": "N/A / NO_APPROVED_SCOPE_ATTACHED_TO_DIAGNOSTIC_GRAPH",
        "multiview_points_consumed_by_demo_graph": False,
        "optional_policy_projector_available": True,
    }
    write_json(output / "presentation.json", presentation)
    recording = rr.RecordingStream("amidst_phase1_finalization_diagnostic")
    recording.save(output / "diagnostic.rrd")
    recording.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
    recording.log("debug/authority", rr.TextDocument(json.dumps({
        key: presentation[key] for key in (
            "status", "authority", "collision_pruned_candidate", "full_school_mesh_displayed",
            "multiview_points_consumed_by_demo_graph", "optional_policy_projector_available",
        )
    }, indent=2)), static=True)
    origins = [[camera.camera_to_world[i][3] for i in range(3)] for camera in context.cameras]
    recording.log("world/cameras", rr.Points3D(
        origins, labels=[camera.camera_id for camera in context.cameras],
        colors=(60, 150, 240), radii=rr.Radius.ui_points(6),
    ), static=True)
    low, high = context.zone.bounds_min, context.zone.bounds_max
    z = context.plane.point[2]
    scope = [[low[0], low[1], z], [high[0], low[1], z], [high[0], high[1], z],
             [low[0], high[1], z], [low[0], low[1], z]]
    recording.log("world/provisional_scope", rr.LineStrips3D(
        [scope], colors=(150, 150, 150), labels=["Annotation bounds / NOT_CERTIFIED"],
    ), static=True)
    for row in sidecar["rows"]:
        recording.set_time("event_time", duration=row["timestamp"])
        recording.log("debug/projection", rr.TextDocument(json.dumps({
            "method": row["method"], "state": row["state"],
            "observed_count": row["observed_count"], "uncertainty": row["uncertainty"],
            "visibility": [frame["status"] for frame in row["input_evidence"]],
        }, indent=2)))
        if row["selected_world_position"] is None:
            recording.log("world/projected", rr.Clear(recursive=True))
        else:
            recording.log("world/projected", rr.Points3D(
                [row["selected_world_position"]], colors=(40, 190, 80),
                radii=rr.Radius.ui_points(5), labels=[row["method"] + " / " + row["state"]],
            ))
    for event in events:
        for index, candidate in enumerate(event["candidates"]):
            recording.log(f"world/legacy_candidates/{index}", rr.LineStrips3D(
                [candidate["polyline"]], labels=[f"Top-{index + 1} legacy fixed-plane diagnostic"],
                colors=(240, 100 + index * 40, 80),
            ), static=True)
        for index, hypothesis in enumerate(event["trajectories"]):
            recording.log(f"debug/timing/{index}", rr.TextDocument(
                json.dumps(hypothesis, indent=2),
            ), static=True)
    recording.log("world/debug_ground_truth", rr.Points3D(
        [row["position"] for row in truth["samples"]], colors=(170, 170, 170),
        radii=rr.Radius.ui_points(2),
    ), static=True)
    recording.send_blueprint(rrb.Blueprint(rrb.Horizontal(
        rrb.Spatial3DView(origin="/world", name="DIAGNOSTIC / NOT CERTIFIED",
                          contents=["+ /world/**", "- /world/debug_ground_truth/**"]),
        rrb.TextDocumentView(origin="/debug/projection", name="Projection method / confidence"),
    ), auto_views=False, auto_layout=False))
    recording.flush()
    recording.disconnect()
    reader = subprocess.run([
        str(Path(sys.executable).with_name("rerun")), "rrd", "verify",
        str(output / "diagnostic.rrd"),
    ], check=False, capture_output=True, text=True)
    if reader.returncode:
        raise RuntimeError("Rerun reader verification failed: " + reader.stderr)
    figure = plt.figure(figsize=(10, 7), dpi=140)
    axis = figure.add_subplot(projection="3d")
    axis.plot(*np.asarray(scope).T, color="grey", alpha=.5, label="Provisional scope")
    points = [row["selected_world_position"] for row in sidecar["rows"]
              if row["selected_world_position"] is not None]
    if points:
        axis.scatter(*np.asarray(points).T, s=12, color="#28be50", label="Projected evidence")
    for event in events:
        for index, candidate in enumerate(event["candidates"]):
            axis.plot(*np.asarray(candidate["polyline"]).T, linestyle="--",
                      label=f"Top-{index + 1} legacy fixed plane")
    # Display geometry at a fixed native-unit vertical scale; do not magnify the
    # tiny export/triangulation residuals through Matplotlib's automatic limits.
    axis.set_zlim(z - 5, z + 5)
    axis.ticklabel_format(axis="z", style="plain", useOffset=False)
    axis.set(xlabel="X (BU)", ylabel="Y (BU)", zlabel="Z (BU)")
    axis.set_title(context.site_id + " / DIAGNOSTIC / NOT CERTIFIED")
    axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(output / "preview.png")
    plt.close(figure)
    (output / "README.md").write_text(
        "# Diagnostic replay\n\nOpen `diagnostic.rrd` with `uv run rerun diagnostic.rrd`.\n"
        "The event_time timeline shows observed/GAP evidence, projection method and confidence.\n"
        "Toggle `/world/debug_ground_truth` in view contents to show evaluation/debug GT.\n"
        "The GT layer is excluded by default. The optional policy projector runs through\n"
        "the unchanged Graph contract where supported. These candidates use fixed-plane\n"
        "fallback; multi-view endpoints remain gated by existing topology checks. Scope\n"
        "is an annotation\n"
        "envelope, not a certified floor or full school mesh. No collision-pruned example\n"
        "or formal Case 1–3 result is claimed.\n", encoding="utf-8",
    )
    return {"rrd_saved": True, "rrd_reader_verified": True,
            "preview_saved": True, "gt_default_visible": False,
            "candidate_count": sum(len(event["candidates"]) for event in events)}


def infer_site(dataset: Path, output: Path, site: str) -> dict[str, Any]:
    """Inference boundary: reads strict inference files only, never GT or recipes."""
    observations_path = dataset / "inference" / site / "observations.json"
    context_path = dataset / "inference" / site / "context.json"
    observation_bytes = observations_path.read_bytes()
    context = PilotInferenceContext.model_validate_json(context_path.read_bytes())
    if hashlib.sha256(observation_bytes).hexdigest() != context.observations_sha256:
        raise ValueError("observations content differs from context binding")
    evidence = PilotObservationExport.model_validate_json(observation_bytes)
    composer = module("phase1_projection_policy")
    output.mkdir(parents=True, exist_ok=False)
    reversed_context = PilotInferenceContext.model_validate(context.model_dump() | {
        "cameras": tuple(reversed(context.cameras)),
    })
    reversed_evidence = PilotObservationExport.model_validate(evidence.model_dump() | {
        "frames": tuple(reversed(evidence.frames)),
    })
    variants = (("primary", context, evidence), ("repeat", context, evidence),
                ("reordered", reversed_context, reversed_evidence))
    for name, binding, inputs in variants:
        sidecar = composer.project_export(binding, inputs)
        write_json(output / (name + ".json"), sidecar)
        frames = composer.project_policy_frames(inputs, binding)
        write_json(output / ("policy_frames_" + name + ".json"), {
            "label": binding.label, "status": "DIAGNOSTIC_POLICY_PROJECTED_FRAMES",
            "dataset": frames.model_dump(mode="json"),
        })
    arguments = ["--observations", str(observations_path), "--context", str(context_path)]
    run_cli("phase1_projection_policy.py", [
        *arguments, "--output", str(output / "fresh.json"),
        "--frames-output", str(output / "policy_frames_fresh.json"),
    ])
    graphs = {}
    runtime = {}
    for mode in ("legacy", "policy"):
        started = time.perf_counter()
        prefix = mode + "_graph_"
        graph: dict[str, Any] = {"status": "INPUT_REJECTED", "termination": None}
        try:
            graph_run = run_pilot_downstream(
                observations_path, context_path, output / (prefix + "primary"),
                projector=composer.project_policy_frames if mode == "policy" else None,
            )
        except ValueError as error:
            graph["reason"] = str(error)
            runtime[mode + "_primary_inference_wall_seconds"] = None
        else:
            runtime[mode + "_primary_inference_wall_seconds"] = time.perf_counter() - started
            run_pilot_downstream(
                observations_path, context_path, output / (prefix + "repeat"),
                projector=composer.project_policy_frames if mode == "policy" else None,
            )
            run_cli("replay_phase1_finalization_diagnostics.py", [
                "--graph-worker", "--projection-mode", mode, *arguments,
                "--output", str(output / (prefix + "fresh")),
            ])
            graph = {
                "status": "DIAGNOSTIC", "candidate_count": graph_run.report["candidate_count"],
                "hypothesis_count": graph_run.report["hypothesis_count"],
                "candidate_order": [[candidate.candidate_id for candidate in gap.event.candidates]
                                    for gap in graph_run.gaps],
                "expanded_states": [gap.search_result.expanded_nodes for gap in graph_run.gaps],
                "termination": graph_run.report["termination_reason"],
                "projection_adapter_applied": mode == "policy",
                "multiview_points_in_graph_input": sum(
                    sample.projected_point is not None and sample.projected_point.plane_id
                    == "EXACT_TIME_MULTIVIEW_NO_PLANE_ASSUMPTION"
                    for sample in graph_run.projection.frames.samples
                ),
                "physical_scope_certified": False,
                "events": [gap.event.model_dump(mode="json") for gap in graph_run.gaps],
            }
        graphs[mode] = graph
    write_json(output / "runtime.json", {
        "measurements": runtime, "status": "DIAGNOSTIC_PRIMARY_INFERENCE_WALL_RUNTIME",
    })
    return {"context": context, "graphs": graphs}


def evaluate_site(
    dataset: Path, output: Path, site: str, frozen: dict[str, Any], *, demos: bool = True,
) -> dict[str, Any]:
    """Evaluation/debug stage after every stream's baseline inference has frozen."""
    context = frozen["context"]
    observations_path = dataset / "inference" / site / "observations.json"
    context_path = dataset / "inference" / site / "context.json"
    primary = json.loads((output / "primary.json").read_bytes())
    truth = json.loads((dataset / "evaluation" / site / "ground_truth.json").read_bytes())
    poisoned = json.loads(json.dumps(truth))
    for row in poisoned["samples"]:
        row["position"] = [value + 100000 * (axis + 1)
                           for axis, value in enumerate(row["position"])]
    poison_root = output / "poison_dataset"
    copied = poison_root / "inference" / site
    copied.mkdir(parents=True)
    shutil.copyfile(observations_path, copied / "observations.json")
    shutil.copyfile(context_path, copied / "context.json")
    write_json(poison_root / "evaluation" / site / "ground_truth.json", poisoned)
    poison_arguments = ["--observations", str(copied / "observations.json"),
                        "--context", str(copied / "context.json")]
    run_cli("phase1_projection_policy.py", [
        *poison_arguments, "--output", str(output / "poison.json"),
        "--frames-output", str(output / "policy_frames_poison.json"),
    ])
    hashes = {name: digest(output / (name + ".json"))
              for name in ("primary", "repeat", "reordered", "fresh", "poison")}
    frame_hashes = {name: digest(output / ("policy_frames_" + name + ".json"))
                    for name in ("primary", "repeat", "reordered", "fresh", "poison")}
    projection_equal = len(set(hashes.values())) == len(set(frame_hashes.values())) == 1
    evaluation = projection_error(primary, truth)
    poison_evaluation = projection_error(primary, poisoned)
    write_json(output / "projection_evaluation.json", evaluation)
    write_json(output / "poison_projection_evaluation.json", poison_evaluation)
    graphs = frozen["graphs"]
    events = []
    for mode, graph in graphs.items():
        if graph["status"] != "DIAGNOSTIC":
            continue
        prefix = mode + "_graph_"
        run_cli("replay_phase1_finalization_diagnostics.py", [
            "--graph-worker", "--projection-mode", mode, *poison_arguments,
            "--output", str(output / (prefix + "poison")),
        ])
        graph_hashes = {name: inference_hashes(output / (prefix + name))
                        for name in ("primary", "repeat", "fresh", "poison")}
        graph["byte_identical"] = all(value == graph_hashes["primary"]
                                      for value in graph_hashes.values())
        graph["hashes"] = graph_hashes
        events = graph.pop("events")
    summary = {
        "site": site, "status": "DIAGNOSTIC", "formal_cases_executed": False,
        "formal_case_metrics": "N/A / NOT_RUN_PENDING_AUTHORITY_AND_PROTOCOL_GATE",
        "projection_inference_hashes": hashes, "projection_byte_identical": projection_equal,
        "policy_frame_dataset_hashes": frame_hashes,
        "gt_poison_changes_only_evaluation": projection_equal and evaluation != poison_evaluation,
        "projection_method_counts": dict(Counter(row["method"] for row in primary["rows"])),
        "projection_state_counts": dict(Counter(row["state"] for row in primary["rows"])),
        "retained_evidence_count": primary["retained_evidence_count"],
        "projection_evaluation": evaluation, "legacy_graph": graphs["legacy"],
        "policy_graph": graphs["policy"],
        "demo": write_demo(context, primary, truth, events, output / "demo") if demos else None,
        "technical_checks_pass": projection_equal and evaluation != poison_evaluation
        and all(graph["status"] != "DIAGNOSTIC" or graph["byte_identical"]
                for graph in graphs.values()),
    }
    write_json(output / "summary.json", summary)
    return summary


def run(dataset: Path, output: Path, *, demos: bool = True) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError("diagnostic replay requires a fresh output directory")
    manifest = verify_dataset(dataset)
    sites = [row["stream"] for row in manifest["streams"]]
    if len(set(sites)) != len(sites):
        raise ValueError("dataset manifest stream identities must be unique")
    if any(not isinstance(site, str) or Path(site).name != site for site in sites):
        raise ValueError("dataset stream identity must be a safe directory name")
    frozen = {site: infer_site(dataset, output / site, site) for site in sites}
    # The external integrity/evaluation stage may now open GT and recipes.
    if verify_dataset(dataset, inference_only=False) != manifest:
        raise ValueError("dataset manifest changed while inference was running")
    summaries = [evaluate_site(dataset, output / site, site, frozen[site], demos=demos)
                 for site in sites]
    report = {
        "status": "DIAGNOSTIC_TECHNICAL_PASS" if all(row["technical_checks_pass"]
                                                      for row in summaries) else "FAILED",
        "formal_cases_executed": False,
        "dataset_manifest_sha256": digest(dataset / "manifest.json"),
        "source_sha256": manifest["source_sha256"], "dataset_version": manifest["dataset_version"],
        "dataset_artifact_hashes_verified": True, "streams": summaries,
        "config_sha256": manifest.get("config_sha256"),
        "live_source_verified_by_replay": False,
        "canonical_artifacts": {
            str(path.relative_to(output)): digest(path) for path in sorted(output.rglob("*"))
            if path.is_file() and path.suffix != ".rrd" and path.name != "runtime.json"
        },
        "noncanonical_artifacts": {
            str(path.relative_to(output)): "RECORDING_SERIALIZATION_OR_DIAGNOSTIC_WALL_RUNTIME"
            for path in sorted(output.rglob("*"))
            if path.is_file() and (path.suffix == ".rrd" or path.name == "runtime.json")
        },
        "formal_baseline_abc": "NOT_RUN_PENDING_APPROVED_PROTOCOL_AND_SCOPE",
        "limitations": [
            "Diagnostic streams do not instantiate approved formal Cases 1–3.",
            "Optional additive projection hook uses unchanged Graph/schema contracts.",
            "Legacy topology requires fixed-plane handoff endpoints; multi-view topology is gated.",
            "Camera-plane/navigation authority remains provisional.",
            "Full school mesh and approved collision-pruned examples are not included.",
            "RRD bytes and measured wall runtime are excluded from canonical hash equality.",
        ],
    }
    if verify_dataset(dataset, inference_only=False) != manifest:
        raise ValueError("dataset changed during replay")
    write_json(output / "verification.json", report)
    write_json(output.parent / "verification.json", report)
    write_json(output.parent / "diagnostics.json", {
        "status": report["status"], "formal_cases_executed": False, "sites": summaries,
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-demo", action="store_true")
    parser.add_argument("--graph-worker", action="store_true")
    parser.add_argument("--projection-mode", choices=("legacy", "policy"), default="policy")
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--context", type=Path)
    args = parser.parse_args()
    if args.graph_worker:
        if args.observations is None or args.context is None:
            parser.error("graph worker requires --observations and --context")
        run_pilot_downstream(
            args.observations, args.context, args.output,
            projector=module("phase1_projection_policy").project_policy_frames
            if args.projection_mode == "policy" else None,
        )
        return
    if args.dataset is None:
        parser.error("diagnostic replay requires --dataset")
    report = run(args.dataset, args.output, demos=not args.no_demo)
    print(json.dumps({"status": report["status"], "formal_cases_executed": False}))
    if report["status"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
