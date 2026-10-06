"""Display saved PILOT robustness results and accepted prefixes without inference.

Rejected context/pixels never become observed 3D evidence. Truth is opened only
after a GT-free accepted core has been frozen, solely for a named debug overlay.
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import rerun as rr

from amidst.domain.pipeline import PipelineConfig
from amidst.domain.stream import BoundGapEvent, ObservationAggregation

_SPEC = importlib.util.spec_from_file_location(
    "saved_pilot_visualization", Path(__file__).with_name("visualize_pilot_downstream.py")
)
assert _SPEC and _SPEC.loader
BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(BASE)
LABEL = "PILOT / SYNTHETIC SAMPLE"
PHYSICAL = "PROVISIONAL_CONFIGURED_NAVIGATION_NOT_MESH_CERTIFICATION"
INPUT_REJECTION_STAGES = {"INPUT_CONTEXT", "INPUT", "CONTEXT"}


def read_labeled(path: Path) -> dict[str, Any]:
    value = BASE.read_json(path)
    if not isinstance(value, dict) or value.get("label") != LABEL:
        raise ValueError(f"{path.name} requires its PILOT / SYNTHETIC SAMPLE label")
    return value


def _metadata(status: dict[str, Any]) -> dict[str, Any]:
    required = ("scenario_id", "outcome", "stage_states", "available_artifacts")
    if any(key not in status for key in required) or not status["scenario_id"]:
        raise ValueError("robustness status requires a scenario and accepted-artifact inventory")
    if (
        not isinstance(status["stage_states"], dict)
        or not isinstance(status["available_artifacts"], list)
        or any(not isinstance(name, str) for name in status["available_artifacts"])
    ):
        raise ValueError("robustness status requires stage states and relative artifact names")
    return {
        key: status.get(key)
        for key in (
            "scenario_id",
            "outcome",
            "failed_stage",
            "reason",
            "termination_reason",
            "evaluation_eligible",
            "stage_states",
            "physical_validity",
            "binding_validated",
            "candidate_count_state",
        )
    }


def build_prefix(
    status: dict[str, Any],
    aggregation: ObservationAggregation | None,
) -> dict[str, Any]:
    """An accepted prefix has no invented navigation, endpoint, or inferred route."""
    metadata = _metadata(status)
    if (
        status.get("failed_stage") in INPUT_REJECTION_STAGES
        or status.get("binding_validated") is False
    ) and aggregation is not None:
        raise ValueError("rejected input/context cannot be promoted to trusted projection")
    observations: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    if aggregation is not None:
        aggregation = ObservationAggregation.model_validate(aggregation.model_dump())
        expected = (
            status.get("source_asset_sha256"),
            status.get("spatial_context_id"),
            status.get("target_id"),
            status.get("source_id"),
        )
        if not all(expected) or not aggregation.samples:
            raise ValueError("accepted prefix requires a source/context/target binding")
        for sample in aggregation.samples:
            actual = (
                sample.source_asset_sha256,
                sample.spatial_context_id,
                sample.target_id,
                sample.source_id,
            )
            if actual != expected or sample.data_kind != "SYNTHETIC":
                raise ValueError("accepted aggregation must match the scenario source binding")
        observations = [
            {
                "observation_id": bound.observation.observation_id,
                "camera_id": bound.observation.camera_id,
                "points": [p.model_dump(mode="json") for p in bound.observation.projected_path],
            }
            for bound in aggregation.observations
        ]
        samples = [
            {
                "camera_id": sample.camera_id,
                "timestamp": sample.timestamp,
                "status": sample.visibility.value,
                "position": (
                    list(sample.projected_point.world_position)
                    if sample.projected_point is not None
                    else None
                ),
                "gap_reason": sample.gap_reason.value if sample.gap_reason else None,
            }
            for sample in aggregation.samples
        ]
    times = [float(sample["timestamp"]) for sample in samples]
    return {
        "schema_version": "pilot-robustness-prefix-presentation-v1",
        "label": LABEL,
        "purpose": "ACCEPTED_PREFIX_DEBUG_PRESENTATION_ONLY",
        "physical_authority": PHYSICAL,
        "coordinate_units": "BLENDER_SCENE_UNITS_PHYSICAL_SCALE_UNVERIFIED",
        "source_asset_sha256": status.get("source_asset_sha256") if aggregation else None,
        "spatial_context_id": status.get("spatial_context_id") if aggregation else None,
        "target_id": status.get("target_id") if aggregation else None,
        "time_range": [min(times), max(times)] if times else None,
        "navigation": {"nodes": [], "edges": []},
        "observations": observations,
        "samples": samples,
        "events": [],
        "scenario_status": metadata,
        "binding_validated": aggregation is not None,
        "trusted_projection_available": any(s["position"] is not None for s in samples),
        "candidate_selection": "NO_ROUTE_OR_ENDPOINT_INVENTION",
        "inference_executed_by_visualizer": False,
    }


def load_debug_overlay(path: Path, core: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    """Support the saved evaluation overlay or the explicit native pilot GT export."""
    if not core.get("binding_validated"):
        raise ValueError("debug GT pairing requires an accepted source-bound prefix")
    raw = read_labeled(path)
    if (
        raw.get("source_asset_sha256") != core["source_asset_sha256"]
        or ("target_id" in raw and raw["target_id"] != core["target_id"])
        or (status.get("site_id") and raw.get("site_id") not in (None, status["site_id"]))
        or (status.get("trajectory_id") and raw.get("trajectory_id") != status["trajectory_id"])
        or ("target_id" not in raw and raw.get("provenance") != "GROUND_TRUTH")
        or not isinstance(raw.get("trajectory_id"), str)
        or not raw["trajectory_id"]
    ):
        raise ValueError("debug GT must preserve explicit scenario/source/target lineage")
    points = raw.get("samples", [])
    if not isinstance(points, list) or len(points) < 2:
        raise ValueError("debug GT requires at least two samples")
    previous = -math.inf
    cleaned = []
    for point in points:
        timestamp, position = point.get("timestamp"), point.get("position")
        if (
            not isinstance(timestamp, int | float)
            or isinstance(timestamp, bool)
            or not math.isfinite(timestamp)
            or timestamp < 0
            or timestamp <= previous
            or not isinstance(position, list)
            or len(position) != 3
            or any(
                isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v)
                for v in position
            )
            or not isinstance(point.get("floor_id"), str)
            or ("trajectory_id" in point and point["trajectory_id"] != raw["trajectory_id"])
            or ("provenance" in point and point["provenance"] != "GROUND_TRUTH")
        ):
            raise ValueError("debug GT requires finite ordered source-bound 3D samples")
        cleaned.append(
            {"timestamp": timestamp, "position": position, "floor_id": point["floor_id"]}
        )
        previous = timestamp
    return {
        "label": LABEL,
        "provenance": "GROUND_TRUTH",
        "usage": "DEBUG_EVALUATION_ONLY",
        "source_asset_sha256": core["source_asset_sha256"],
        "target_id": core["target_id"],
        "trajectory_id": raw["trajectory_id"],
        "samples": cleaned,
    }


def _summary(core: dict[str, Any]) -> dict[str, Any]:
    return {
        **core["scenario_status"],
        "label": LABEL,
        "physical_authority": PHYSICAL,
        "trusted_projection_available": core["trusted_projection_available"],
        "observed_projected_rows": sum(s["position"] is not None for s in core["samples"]),
        "observations": len(core["observations"]),
        "bounded_gaps": len(core["events"]),
        "candidates": sum(len(e["candidates"]) for e in core["events"]),
        "hypotheses": sum(len(e["hypotheses"]) for e in core["events"]),
        "inference_executed_by_visualizer": False,
    }


def _prefix_recording(core: dict[str, Any], output: Path, overlay: dict[str, Any] | None) -> dict:
    if output.exists():
        raise FileExistsError(output)
    recording = rr.RecordingStream("amidst_pilot_synthetic_robustness_diagnostic")
    counts = {"candidates": 0, "hypotheses": 0, "projected_samples": 0, "gt_samples": 0}
    try:
        with output.open("xb"):
            pass
        recording.save(output)
        recording.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
        recording.log(
            "debug/scenario_status",
            rr.TextDocument(json.dumps(_summary(core), indent=2)),
            static=True,
        )
        for observation in core["observations"]:
            positions = [point["world_position"] for point in observation["points"]]
            if positions:
                recording.log(
                    "world/accepted_observed/" + BASE._entity(observation["observation_id"]),
                    rr.LineStrips3D(
                        [positions], colors=BASE.OBSERVED_COLOR, radii=rr.Radius.ui_points(3)
                    ),
                    static=True,
                )
        for sample in core["samples"]:
            recording.set_time(BASE.TIMELINE, duration=sample["timestamp"])
            entity = "world/accepted_markers/" + BASE._entity(sample["camera_id"])
            if sample["position"] is None:
                recording.log(entity, rr.Clear(recursive=True))
            else:
                recording.log(
                    entity,
                    rr.Points3D(
                        [sample["position"]],
                        colors=BASE.OBSERVED_COLOR,
                        radii=rr.Radius.ui_points(5),
                        labels=["ACCEPTED PROJECTED PREFIX"],
                    ),
                )
                counts["projected_samples"] += 1
        if overlay is not None:
            entity = "world/debug_ground_truth/" + BASE._entity(overlay["trajectory_id"])
            recording.log(
                entity + "/dotted_path",
                rr.Points3D(
                    [point["position"] for point in overlay["samples"]],
                    colors=BASE.GT_COLOR,
                    radii=rr.Radius.ui_points(2),
                ),
                static=True,
            )
            for point in overlay["samples"]:
                recording.set_time(BASE.TIMELINE, duration=point["timestamp"])
                recording.log(
                    entity + "/marker",
                    rr.Points3D(
                        [point["position"]],
                        colors=BASE.GT_COLOR,
                        radii=rr.Radius.ui_points(4),
                        labels=["GROUND_TRUTH · evaluation/debug only"],
                    ),
                )
                counts["gt_samples"] += 1
        recording.flush()
    finally:
        recording.disconnect()
    return counts


def _plot(axis: Any, core: dict[str, Any], overlay: dict[str, Any] | None, *, flat: bool) -> None:
    coordinates = []

    def line(
        points: list, *, color: Any, width: float, style: str, label: str | None = None
    ) -> None:
        if not points:
            return
        values = np.asarray(points, dtype=np.float64)
        coordinates.extend(values.tolist())
        axes = values.T[:2] if flat else values.T
        if len(values) == 1:
            axis.scatter(*axes, color=color, s=12, label=label)
        else:
            axis.plot(*axes, color=color, linewidth=width, linestyle=style, label=label)

    for edge in core["navigation"]["edges"]:
        line(edge["polyline"], color="#98a4ad", width=1, style="-")
    for index, observation in enumerate(core["observations"]):
        line(
            [p["world_position"] for p in observation["points"]],
            color=np.asarray(BASE.OBSERVED_COLOR) / 255,
            width=3,
            style="-",
            label="Accepted observed → projected" if index == 0 else None,
        )
    for event in core["events"]:
        for candidate in event["candidates"]:
            line(
                candidate["polyline"],
                color=np.asarray(candidate["color"]) / 255,
                width=2,
                style="--",
                label=f"Top-{candidate['rank']} inferred gap",
            )
    if overlay is not None:
        line(
            [p["position"] for p in overlay["samples"]],
            color=np.asarray(BASE.GT_COLOR) / 255,
            width=2,
            style=":",
            label="GT · independent debug only",
        )
    if coordinates:
        values = np.asarray(coordinates)
        center = (values.min(axis=0) + values.max(axis=0)) / 2
        extent = max(float(np.max(values.max(axis=0) - values.min(axis=0))), 1)
        axis.set_xlim(center[0] - extent * 0.6, center[0] + extent * 0.6)
        axis.set_ylim(center[1] - extent * 0.6, center[1] + extent * 0.6)
        if flat:
            axis.set_aspect("equal", adjustable="box")
        else:
            axis.set_zlim(center[2] - extent * 0.25, center[2] + extent * 0.25)
            axis.set_box_aspect((1, 1, 0.4))
    else:
        text = axis.text if flat else axis.text2D
        text(
            0.5,
            0.5,
            "NO TRUSTED 3D PROJECTION\nNo invented recovery or route",
            transform=axis.transAxes,
            ha="center",
            va="center",
            color="#9a3737",
        )
    axis.set_xlabel("X (scene units)")
    axis.set_ylabel("Y (scene units)")
    if not flat:
        axis.set_zlabel("Z (scene units)")


def _preview(core: dict[str, Any], output: Path, overlay: dict[str, Any] | None) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure = plt.figure(figsize=(11, 7), dpi=140)
    axis = figure.add_subplot(projection="3d")
    _plot(axis, core, overlay, flat=False)
    metadata = core["scenario_status"]
    status = f"{metadata['outcome']} · failed stage: {metadata['failed_stage'] or 'none'}"
    axis.set_title(f"{LABEL}\n{metadata['scenario_id']} · {status}")
    handles, labels = axis.get_legend_handles_labels()
    if handles:
        axis.legend(handles, labels, loc="upper left", fontsize=8)
    figure.text(
        0.03,
        0.02,
        "Physical authority PROVISIONAL · No mesh certification or formal benchmark",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.04, 1, 1))
    figure.savefig(output, metadata={"DatasetLabel": LABEL, "DataKind": "SYNTHETIC"})
    plt.close(figure)


def _detail_html(output: Path, summary: dict[str, Any], *, interactive: bool) -> None:
    encoded = html.escape(json.dumps(summary, ensure_ascii=False, indent=2))
    title = html.escape(str(summary["scenario_id"]))
    link = '<a href="review_3d.html">Interactive saved 3D view</a> · ' if interactive else ""
    output.write_text(
        '<!doctype html><meta charset="utf-8"><title>PILOT / SYNTHETIC SAMPLE</title>'
        "<style>body{font:16px system-ui;max-width:1200px;margin:30px auto;padding:20px}"
        "img{width:100%}pre{white-space:pre-wrap;background:#edf1f4;padding:20px}</style>"
        f"<h1>{LABEL} — {title}</h1><p>Physical authority PROVISIONAL. "
        "Only accepted evidence prefixes are shown; GT is an independent debug overlay.</p>"
        f'<p>{link}<a href="debug.rrd">Rerun recording</a></p>'
        f'<img src="preview_3d.png" alt="PILOT scenario 3D diagnostic"><pre>{encoded}</pre>',
        encoding="utf-8",
    )


def create_visualization(runroot: Path, gtpath: Path | None = None) -> dict[str, Any]:
    """Create one immutable display directory from saved full output or accepted prefix."""
    runroot = runroot.resolve()
    statuspath = runroot / "robustness_status.json"
    status = read_labeled(statuspath)
    metadata = _metadata(status)
    inputs = {str(statuspath): BASE.sha256(statuspath)}
    rejected = (
        status.get("failed_stage") in INPUT_REJECTION_STAGES
        or status.get("binding_validated") is False
    )
    available = status["available_artifacts"]

    def artifact(name: str) -> dict | None:
        if rejected or name not in available:
            return None
        path = runroot / name
        inputs[str(path)] = BASE.sha256(path)
        return read_labeled(path)

    aggregation_raw = artifact("aggregation.json")
    aggregation = (
        ObservationAggregation.model_validate(aggregation_raw["aggregation"])
        if aggregation_raw is not None
        else None
    )
    pipeline_raw, gaps_raw = artifact("pipeline_config.json"), artifact("gap_events.json")
    full = aggregation is not None and pipeline_raw is not None and gaps_raw is not None
    if full:
        pipeline = PipelineConfig.model_validate(pipeline_raw["pipeline"])
        gaps = tuple(BoundGapEvent.model_validate(row) for row in gaps_raw["gaps"])
        core = BASE.build_presentation(aggregation, pipeline, gaps)
        # Check the status binding independently before accepting the complete result.
        build_prefix(status, aggregation)
        core["scenario_status"] = metadata
        core["purpose"] = {
            "presentation": "SAVED_OUTPUT_DEBUG_PRESENTATION_ONLY",
            "scenario_status": metadata,
        }
        core["binding_validated"] = True
        core["trusted_projection_available"] = any(
            sample.projected_point is not None for sample in aggregation.samples
        )
        for event, gap in zip(core["events"], gaps, strict=True):
            event["enumeration_complete"] = gap.search_result.complete
            event["rejection_reasons"] = list(gap.search_result.rejection_reasons)
    else:
        core = build_prefix(status, aggregation)
    frozen = json.dumps(core, sort_keys=True, allow_nan=False)
    overlay = None
    if gtpath is not None and core["binding_validated"] and not rejected:
        gtpath = gtpath.resolve()
        overlay = load_debug_overlay(gtpath, core, status)
        inputs[str(gtpath)] = BASE.sha256(gtpath)
    if json.dumps(core, sort_keys=True, allow_nan=False) != frozen:
        raise RuntimeError("debug GT changed the frozen evidence/candidate presentation")
    output = runroot / "visualization"
    output.mkdir(exist_ok=False)
    counts = (
        BASE.log_recording(core, output / "debug.rrd", overlay)
        if full
        else _prefix_recording(core, output / "debug.rrd", overlay)
    )
    _preview(core, output / "preview_3d.png", overlay)
    summary = _summary(core) | {"gt_overlay_enabled": overlay is not None, "counts": counts}
    if full:
        BASE.write_html(core, output / "review_3d.html", overlay)
    _detail_html(output / "review.html", summary, interactive=full)
    (output / "presentation.json").write_text(json.dumps(core, indent=2, allow_nan=False) + "\n")
    for path, digest in inputs.items():
        if BASE.sha256(Path(path)) != digest:
            raise RuntimeError("saved input changed while visualization was being generated")
    manifest = summary | {
        "runroot": str(runroot),
        "output": str(output),
        "inputs": inputs,
        "gt_overlay_input": str(gtpath) if overlay is not None else None,
        "outputs": {p.name: BASE.sha256(p) for p in output.iterdir()},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return manifest


def create_overview(manifests: list[dict[str, Any]], destination: Path) -> None:
    """A comparison index and XY contact sheet; GT never changes candidate ordering."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not manifests:
        raise ValueError("overview requires saved scenario visualizations")
    destination.mkdir(parents=True, exist_ok=False)
    rows = math.ceil(len(manifests) / 3)
    figure, axes = plt.subplots(rows, 3, figsize=(15, 4.5 * rows), squeeze=False, dpi=130)
    cards = []
    for axis, manifest in zip(axes.flat, manifests, strict=False):
        output = Path(manifest["output"])
        core = read_labeled(output / "presentation.json")
        overlay = None
        if manifest["gt_overlay_input"]:
            status = read_labeled(Path(manifest["runroot"]) / "robustness_status.json")
            overlay = load_debug_overlay(Path(manifest["gt_overlay_input"]), core, status)
        _plot(axis, core, overlay, flat=True)
        stage = manifest["failed_stage"] or "none"
        axis.set_title(f"{manifest['scenario_id']}\n{manifest['outcome']} · {stage}", fontsize=10)
        relative = Path(os.path.relpath(output / "review.html", destination))
        cards.append(
            f'<li><a href="{html.escape(relative.as_posix(), quote=True)}">'
            f"{html.escape(str(manifest['scenario_id']))}</a> — "
            f"{html.escape(str(manifest['outcome']))}; stage={html.escape(str(stage))}; "
            f"observed={manifest['observed_projected_rows']}; candidates={manifest['candidates']}; "
            f"hypotheses={manifest['hypotheses']}</li>"
        )
    for axis in list(axes.flat)[len(manifests) :]:
        axis.axis("off")
    figure.suptitle(
        LABEL + " — robustness XY overview\n"
        "Green accepted projection · colored all Top-K · gray independent GT debug\n"
        "Physical authority PROVISIONAL · rejected inputs never plotted",
        fontsize=14,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.93))
    figure.savefig(destination / "overview.png", metadata={"DatasetLabel": LABEL})
    plt.close(figure)
    (destination / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>PILOT / SYNTHETIC SAMPLE</title>'
        "<style>body{font:16px system-ui;max-width:1500px;margin:30px auto;padding:20px}"
        "img{width:100%}li{margin:12px 0}</style>"
        f"<h1>{LABEL} — robustness</h1><p>Physical authority PROVISIONAL. "
        "Accepted evidence and every saved candidate are preserved. "
        "GT appears only as independent debug; no inference or formal benchmark is run.</p>"
        '<img src="overview.png" alt="PILOT robustness scenario overview">'
        "<ul>" + "".join(cards) + "</ul>",
        encoding="utf-8",
    )
    (destination / "manifest.json").write_text(
        json.dumps(
            {
                "label": LABEL,
                "physical_authority": PHYSICAL,
                "scenarios": [m["scenario_id"] for m in manifests],
                "inference_executed": False,
                "outputs": {p.name: BASE.sha256(p) for p in destination.iterdir()},
            },
            indent=2,
        )
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--inventory", type=Path)
    source.add_argument("--run", type=Path)
    parser.add_argument("--ground-truth", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.run is not None:
        manifest = create_visualization(args.run, args.ground_truth)
        print(
            json.dumps(
                {
                    "label": LABEL,
                    "scenario": manifest["scenario_id"],
                    "output": manifest["output"],
                    "counts": manifest["counts"],
                }
            )
        )
        return
    if args.output is None:
        parser.error("--inventory requires --output for the overview directory")
    inventory = read_labeled(args.inventory)
    manifests = []
    for entry in inventory["scenarios"]:
        runroot = Path(entry["path"])
        if not runroot.is_absolute():
            runroot = args.inventory.parent / runroot
        if not (runroot / "robustness_status.json").is_file():
            runroot = runroot / "run_01"
        if read_labeled(runroot / "robustness_status.json")["scenario_id"] != entry["scenario_id"]:
            raise ValueError("inventory and saved scenario identities differ")
        truth = Path(entry["ground_truth"]) if entry.get("ground_truth") else None
        if truth is not None and not truth.is_absolute():
            truth = args.inventory.parent / truth
        manifest = create_visualization(runroot, truth)
        manifests.append(manifest)
    create_overview(manifests, args.output)
    print(json.dumps({"label": LABEL, "scenarios": len(manifests), "output": str(args.output)}))


if __name__ == "__main__":
    main()
