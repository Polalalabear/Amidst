"""Present saved PILOT inference outputs; never generate or rank candidates.

The core presentation consumes only source-bound ObservationAggregation,
PipelineConfig and BoundGapEvent outputs. Evaluation GT is loaded separately
after that core is complete, and is displayed only as a named debug overlay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import quote

import numpy as np
import rerun as rr
import rerun.blueprint as rrb

from amidst.domain.pipeline import PipelineConfig
from amidst.domain.stream import BoundGapEvent, ObservationAggregation

LABEL = "PILOT / SYNTHETIC SAMPLE"
OBSERVED_COLOR = (40, 190, 80)
GT_COLOR = (160, 160, 170)
ROUTE_COLORS = (
    (240, 103, 98),
    (245, 174, 64),
    (156, 115, 235),
    (65, 187, 218),
    (222, 192, 76),
    (222, 108, 182),
)
TIMELINE = "event_time"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON value: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def build_presentation(
    aggregation: ObservationAggregation,
    pipeline: PipelineConfig,
    gaps: tuple[BoundGapEvent, ...],
) -> dict[str, Any]:
    """GT-free presentation boundary, preserving all supplied candidate order."""
    aggregation = ObservationAggregation.model_validate(aggregation.model_dump())
    pipeline = PipelineConfig.model_validate(pipeline.model_dump())
    gaps = tuple(BoundGapEvent.model_validate(gap.model_dump()) for gap in gaps)
    navigation, topology = pipeline.navigation, pipeline.topology
    source_sha = navigation.source_asset_sha256
    if not source_sha or (
        topology.source_asset_sha256 != source_sha
        or topology.navigation_graph_id != navigation.graph_id
        or topology.spatial_context_id != navigation.spatial_context_id
    ):
        raise ValueError("pilot visualization requires matching source/context navigation/topology")
    for sample in aggregation.samples:
        if (
            sample.source_asset_sha256 != source_sha
            or sample.spatial_context_id != navigation.spatial_context_id
            or sample.data_kind != "SYNTHETIC"
        ):
            raise ValueError("observation aggregation source/context does not match navigation")
    observations = {bound.observation.observation_id: bound for bound in aggregation.observations}
    targets = {sample.target_id for sample in aggregation.samples}
    if len(targets) != 1 or not aggregation.samples:
        raise ValueError("this pilot visualization requires one target and nonempty samples")
    events = []
    for gap in gaps:
        if (
            gap.binding.source_asset_sha256 != source_sha
            or gap.binding.spatial_context_id != navigation.spatial_context_id
            or observations.get(gap.start.observation.observation_id) != gap.start
            or observations.get(gap.end.observation.observation_id) != gap.end
        ):
            raise ValueError("gap event must preserve the supplied aggregation source/endpoints")
        ranks = {
            candidate.candidate_id: rank for rank, candidate in enumerate(gap.event.candidates)
        }
        events.append(
            {
                "event_id": gap.event.event_id,
                "time_range": list(gap.event.time_range),
                "termination_reason": gap.event.termination_reason.value,
                "candidates": [
                    {
                        "rank": index + 1,
                        "color": list(ROUTE_COLORS[index % len(ROUTE_COLORS)]),
                        **candidate.model_dump(mode="json"),
                    }
                    for index, candidate in enumerate(gap.event.candidates)
                ],
                "hypotheses": [
                    {
                        "color": list(ROUTE_COLORS[ranks[item.candidate_id] % len(ROUTE_COLORS)]),
                        **item.model_dump(mode="json"),
                    }
                    for item in gap.event.trajectories
                ],
            }
        )
    times = [float(sample.timestamp) for sample in aggregation.samples]
    return {
        "schema_version": "pilot-downstream-presentation-v1",
        "label": LABEL,
        "purpose": "SAVED_OUTPUT_DEBUG_PRESENTATION_ONLY",
        "physical_authority": "PROVISIONAL_CONFIGURED_NAVIGATION_NOT_MESH_CERTIFICATION",
        "coordinate_units": "BLENDER_SCENE_UNITS_PHYSICAL_SCALE_UNVERIFIED",
        "source_asset_sha256": source_sha,
        "spatial_context_id": navigation.spatial_context_id,
        "target_id": next(iter(targets)),
        "time_range": [min(times), max(times)],
        "navigation": navigation.model_dump(mode="json"),
        "observations": [
            {
                "observation_id": bound.observation.observation_id,
                "camera_id": bound.observation.camera_id,
                "points": [
                    point.model_dump(mode="json") for point in bound.observation.projected_path
                ],
            }
            for bound in aggregation.observations
        ],
        "samples": [
            {
                "camera_id": sample.camera_id,
                "timestamp": sample.timestamp,
                "status": sample.visibility.value,
                "position": (
                    list(sample.projected_point.world_position)
                    if sample.projected_point is not None
                    else None
                ),
            }
            for sample in aggregation.samples
        ],
        "events": events,
        "candidate_selection": "SUPPLIED_ORDER_PRESERVED_NO_GT_SELECTION_OR_RERANKING",
        "inference_executed_by_visualizer": False,
    }


def load_gt_overlay(path: Path, presentation: dict[str, Any]) -> dict[str, Any]:
    """Read evaluation-only truth after the GT-free presentation is completed."""
    raw = read_json(path)
    if (
        raw.get("label") != LABEL
        or raw.get("source_asset_sha256") != presentation["source_asset_sha256"]
        or raw.get("target_id") != presentation["target_id"]
        or not isinstance(raw.get("trajectory_id"), str)
        or not raw["trajectory_id"]
    ):
        raise ValueError("GT debug overlay must match pilot label, source and target")
    points = raw.get("samples", [])
    if len(points) < 2:
        raise ValueError("GT debug overlay requires at least two samples")
    previous = -math.inf
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
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(value)
                for value in position
            )
            or not isinstance(point.get("floor_id"), str)
        ):
            raise ValueError("GT overlay requires finite ordered timestamps/3D positions/floors")
        previous = timestamp
    return {**raw, "provenance": "GROUND_TRUTH", "usage": "DEBUG_EVALUATION_ONLY"}


def _entity(identity: str) -> str:
    return quote(identity, safe="")


def display_samples(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Interpolate display markers at 5 Hz without changing saved hypotheses."""
    start, end = points[0]["timestamp"], points[-1]["timestamp"]
    if (end - start) * 5 > 10_000:
        raise ValueError("pilot display marker budget exceeded")
    timestamps = sorted(
        {
            *(point["timestamp"] for point in points),
            *(
                start + index / 5
                for index in range(math.ceil((end - start) * 5) + 1)
                if start + index / 5 <= end
            ),
        }
    )
    result = []
    segment = 1
    for timestamp in timestamps:
        while segment < len(points) - 1 and points[segment]["timestamp"] < timestamp:
            segment += 1
        before, after = points[segment - 1], points[segment]
        fraction = (timestamp - before["timestamp"]) / (after["timestamp"] - before["timestamp"])
        result.append(
            {
                "timestamp": timestamp,
                "world_position": [
                    left + fraction * (right - left)
                    for left, right in zip(
                        before["world_position"], after["world_position"], strict=True
                    )
                ],
                "provenance": "INFERRED_GAP",
            }
        )
    return result


def bounds(presentation: dict[str, Any]) -> tuple[np.ndarray, float]:
    points = [node["position"] for node in presentation["navigation"]["nodes"]]
    points.extend(
        point["world_position"]
        for observation in presentation["observations"]
        for point in observation["points"]
    )
    points.extend(
        point
        for event in presentation["events"]
        for candidate in event["candidates"]
        for point in candidate["polyline"]
    )
    coordinates = np.asarray(points, dtype=np.float64)
    low, high = coordinates.min(axis=0), coordinates.max(axis=0)
    return (low + high) / 2, max(float(np.max(high - low)), 1.0)


def log_recording(
    presentation: dict[str, Any],
    output: Path,
    gt_overlay: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Save an RRD without starting a viewer or changing any inference output."""
    if output.exists():
        raise FileExistsError(output)
    recording = rr.RecordingStream("amidst_pilot_synthetic_downstream_debug")
    counts = {"candidates": 0, "hypotheses": 0, "projected_samples": 0, "gt_samples": 0}
    try:
        with output.open("xb"):
            pass
        recording.save(output)
        recording.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
        recording.log(
            "debug/pilot",
            rr.TextDocument(
                json.dumps(
                    {
                        key: presentation[key]
                        for key in (
                            "label",
                            "purpose",
                            "physical_authority",
                            "coordinate_units",
                            "source_asset_sha256",
                            "candidate_selection",
                            "inference_executed_by_visualizer",
                        )
                    },
                    indent=2,
                )
            ),
            static=True,
        )
        for edge in presentation["navigation"]["edges"]:
            recording.log(
                f"world/navigation/{_entity(edge['edge_id'])}",
                rr.LineStrips3D(
                    [edge["polyline"]], colors=(100, 125, 140), radii=rr.Radius.ui_points(1)
                ),
                static=True,
            )
        for observation in presentation["observations"]:
            positions = [point["world_position"] for point in observation["points"]]
            if positions:
                recording.log(
                    f"world/observed_paths/{_entity(observation['observation_id'])}",
                    rr.LineStrips3D(
                        [positions], colors=OBSERVED_COLOR, radii=rr.Radius.ui_points(3)
                    ),
                    static=True,
                )
        for sample in presentation["samples"]:
            root = f"world/observed_markers/{_entity(sample['camera_id'])}"
            recording.set_time(TIMELINE, duration=sample["timestamp"])
            if sample["position"] is None:
                recording.log(root, rr.Clear(recursive=True))
            else:
                recording.log(
                    root,
                    rr.Points3D(
                        [sample["position"]],
                        colors=OBSERVED_COLOR,
                        radii=rr.Radius.ui_points(5),
                        labels=["OBSERVED pixel → PROJECTED landmark"],
                    ),
                )
                counts["projected_samples"] += 1
        for event in presentation["events"]:
            root = f"world/inferred/{_entity(event['event_id'])}"
            for candidate in event["candidates"]:
                recording.log(
                    f"{root}/candidates/{_entity(candidate['candidate_id'])}",
                    rr.LineStrips3D(
                        [candidate["polyline"]],
                        colors=candidate["color"],
                        radii=rr.Radius.ui_points(2),
                        labels=[f"Top-{candidate['rank']} INFERRED_GAP"],
                    ),
                    static=True,
                )
                counts["candidates"] += 1
            for hypothesis in event["hypotheses"]:
                hroot = f"{root}/hypotheses/{_entity(hypothesis['hypothesis_id'])}"
                recording.log(
                    hroot + "/path",
                    rr.LineStrips3D(
                        [[point["world_position"] for point in hypothesis["timed_points"]]],
                        colors=hypothesis["color"],
                        radii=rr.Radius.ui_points(1),
                    ),
                    static=True,
                )
                recording.log(
                    "debug/" + hroot, rr.TextDocument(json.dumps(hypothesis, indent=2)), static=True
                )
                for point in display_samples(hypothesis["timed_points"]):
                    recording.set_time(TIMELINE, duration=point["timestamp"])
                    recording.log(
                        hroot + "/marker",
                        rr.Points3D(
                            [point["world_position"]],
                            colors=hypothesis["color"],
                            radii=rr.Radius.ui_points(4),
                            labels=[hypothesis["kind"] + " INFERRED_GAP"],
                        ),
                    )
                counts["hypotheses"] += 1
                recording.set_time(
                    TIMELINE, duration=hypothesis["timed_points"][-1]["timestamp"] + 1e-6
                )
                recording.log(hroot + "/marker", rr.Clear(recursive=True))
        if gt_overlay is not None:
            root = "world/debug_ground_truth/" + _entity(gt_overlay["trajectory_id"])
            recording.log(
                root + "/dotted_path",
                rr.Points3D(
                    [point["position"] for point in gt_overlay["samples"]],
                    colors=GT_COLOR,
                    radii=rr.Radius.ui_points(2),
                ),
                static=True,
            )
            for point in gt_overlay["samples"]:
                recording.set_time(TIMELINE, duration=point["timestamp"])
                recording.log(
                    root + "/marker",
                    rr.Points3D(
                        [point["position"]],
                        colors=GT_COLOR,
                        radii=rr.Radius.ui_points(4),
                        labels=["GROUND_TRUTH · evaluation/debug only"],
                    ),
                )
                counts["gt_samples"] += 1
        center, extent = bounds(presentation)
        recording.send_blueprint(
            rrb.Blueprint(
                rrb.Horizontal(
                    rrb.Spatial3DView(
                        origin="/world",
                        name=LABEL,
                        eye_controls=rrb.EyeControls3D(
                            position=center + np.asarray((0.8, -1.2, 1.0)) * extent,
                            look_target=center,
                            eye_up=(0, 0, 1),
                        ),
                    ),
                    rrb.TextDocumentView(
                        origin="/debug/pilot", name="Provisional physical authority"
                    ),
                    column_shares=[0.8, 0.2],
                ),
                auto_views=False,
                auto_layout=False,
            )
        )
        recording.flush()
    finally:
        recording.disconnect()
    return counts


def write_static_preview(
    presentation: dict[str, Any],
    destination: Path,
    gt_overlay: dict[str, Any] | None = None,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure = plt.figure(figsize=(11, 7), dpi=140)
    axis = figure.add_subplot(projection="3d")
    for edge in presentation["navigation"]["edges"]:
        values = np.asarray(edge["polyline"])
        axis.plot(*values.T, color="#98a4ad", alpha=0.35, linewidth=1)
    for index, observation in enumerate(presentation["observations"]):
        values = np.asarray([point["world_position"] for point in observation["points"]])
        if len(values):
            axis.plot(
                *values.T,
                color=np.asarray(OBSERVED_COLOR) / 255,
                linewidth=3,
                label="Observed → projected" if index == 0 else None,
            )
    for event in presentation["events"]:
        for candidate in event["candidates"]:
            values = np.asarray(candidate["polyline"])
            axis.plot(
                *values.T,
                color=np.asarray(candidate["color"]) / 255,
                linestyle="--",
                linewidth=2,
                label=f"Top-{candidate['rank']} inferred gap",
            )
    if gt_overlay is not None:
        values = np.asarray([point["position"] for point in gt_overlay["samples"]])
        axis.plot(
            *values.T,
            color=np.asarray(GT_COLOR) / 255,
            linestyle=":",
            linewidth=2,
            label="GT · debug/evaluation only",
        )
    center, extent = bounds(presentation)
    axis.set_xlim(center[0] - extent * 0.6, center[0] + extent * 0.6)
    axis.set_ylim(center[1] - extent * 0.6, center[1] + extent * 0.6)
    axis.set_zlim(center[2] - extent * 0.25, center[2] + extent * 0.25)
    axis.set_box_aspect((1, 1, 0.4))
    axis.set(xlabel="X (scene units)", ylabel="Y (scene units)", zlabel="Z (scene units)")
    axis.set_title(LABEL + "\nConfigured navigation · physical authority provisional")
    axis.legend(loc="upper left", fontsize=8)
    figure.tight_layout()
    figure.savefig(destination)
    plt.close(figure)


HTML = Path(__file__).with_name("pilot_downstream_3d_template.html").read_text(encoding="utf-8")


def write_html(
    presentation: dict[str, Any],
    destination: Path,
    gt_overlay: dict[str, Any] | None = None,
) -> None:
    payload = presentation | {"debug_ground_truth": gt_overlay}
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    destination.write_text(HTML.replace("__DATA__", encoded), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregation", type=Path, required=True)
    parser.add_argument("--pipeline-config", type=Path, required=True)
    parser.add_argument("--gap-events", type=Path, required=True)
    parser.add_argument("--evaluation-gt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    def unwrap(path: Path, key: str) -> Any:
        value = read_json(path)
        if not isinstance(value, dict) or value.get("label") != LABEL or key not in value:
            raise ValueError(f"{path.name} requires its PILOT label and {key} wrapper")
        return value[key]

    aggregation = ObservationAggregation.model_validate(unwrap(args.aggregation, "aggregation"))
    pipeline = PipelineConfig.model_validate(unwrap(args.pipeline_config, "pipeline"))
    raw_gaps = unwrap(args.gap_events, "gaps")
    if not isinstance(raw_gaps, list):
        raise ValueError("gap_events.json must contain a list of strict BoundGapEvent objects")
    gaps = tuple(BoundGapEvent.model_validate(raw) for raw in raw_gaps)
    presentation = build_presentation(aggregation, pipeline, gaps)
    # Separate truth load occurs only after the saved inference presentation is complete.
    gt_overlay = load_gt_overlay(args.evaluation_gt, presentation) if args.evaluation_gt else None
    args.output.mkdir(parents=True, exist_ok=False)
    counts = log_recording(presentation, args.output / "debug.rrd", gt_overlay)
    write_html(presentation, args.output / "review_3d.html", gt_overlay)
    write_static_preview(presentation, args.output / "preview_3d.png", gt_overlay)
    (args.output / "presentation.json").write_text(
        json.dumps(presentation, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (args.output / "visualization_manifest.json").write_text(
        json.dumps(
            {
                "label": LABEL,
                "physical_authority": presentation["physical_authority"],
                "counts": counts,
                "gt_overlay_enabled": gt_overlay is not None,
                "inference_executed": False,
                "inputs": {
                    str(path.resolve()): sha256(path)
                    for path in (
                        args.aggregation,
                        args.pipeline_config,
                        args.gap_events,
                        *((args.evaluation_gt,) if args.evaluation_gt else ()),
                    )
                },
                "outputs": {path.name: sha256(path) for path in args.output.iterdir()},
            },
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"label": LABEL, "counts": counts, "output": str(args.output.resolve())}))


if __name__ == "__main__":
    main()
