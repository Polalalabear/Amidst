"""Saveable Rerun presentation of configured geometry and reconstructed events.

Camera topology anchors describe the navigation interface, not calibrated camera
positions or FOV. Ground Truth has its own explicitly enabled debug entry point.
"""

from __future__ import annotations

import json
import math
from bisect import bisect_right
from collections.abc import Mapping
from itertools import pairwise
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

import rerun as rr

from amidst.domain.calibration import CameraCalibrationCatalog
from amidst.domain.common import Provenance, Vec3
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.navigation import NavigationGraphConfig
from amidst.domain.observation import Observation
from amidst.domain.topology import CameraTopologyConfig
from amidst.domain.trajectory import Event, TimedTrajectoryPoint
from amidst.geometry.calibration import (
    frustum_line_segments,
    validate_camera_calibration_catalog,
)

PROVENANCE_COLORS: Mapping[Provenance, tuple[int, int, int]] = {
    Provenance.OBSERVED: (40, 190, 80),
    Provenance.PROJECTED: (40, 110, 235),
    Provenance.INFERRED_GAP: (245, 145, 40),
    Provenance.GROUND_TRUTH: (150, 150, 150),
}
EVENT_TIMELINE = "event_time"


class RecordingSink(Protocol):
    """Small injectable SDK surface used to verify actual logged data."""

    def log(self, entity_path: str, entity: rr.AsComponents, *, static: bool = False) -> None: ...

    def set_time(self, timeline: str, *, duration: float) -> None: ...

    def save(self, path: str | Path) -> None: ...

    def flush(self) -> None: ...

    def disconnect(self) -> None: ...


def _segment_name(identity: str) -> str:
    return quote(identity, safe="")


def _interpolate(start: Vec3, end: Vec3, fraction: float) -> Vec3:
    return (
        start[0] + fraction * (end[0] - start[0]),
        start[1] + fraction * (end[1] - start[1]),
        start[2] + fraction * (end[2] - start[2]),
    )


def _dashed_strips(polyline: tuple[Vec3, ...]) -> list[list[Vec3]]:
    """Create real gaps in geometry because LineStrips3D has no dash component."""
    result: list[list[Vec3]] = []
    total_length = sum(math.dist(start, end) for start, end in pairwise(polyline))
    # A visual subdivision cap keeps long configured paths practical to inspect.
    dash_length = max(0.35, total_length / 2000)
    for start, end in pairwise(polyline):
        length = math.dist(start, end)
        if length == 0:
            continue
        offset = 0.0
        while offset < length:
            finish = min(offset + dash_length, length)
            result.append([
                _interpolate(start, end, offset / length),
                _interpolate(start, end, finish / length),
            ])
            offset += dash_length * 1.6
    return result


def _dotted_points(polyline: tuple[Vec3, ...]) -> list[Vec3]:
    total_length = sum(math.dist(start, end) for start, end in pairwise(polyline))
    spacing = max(0.3, total_length / 2000)
    points: list[Vec3] = []
    for start, end in pairwise(polyline):
        count = max(1, math.ceil(math.dist(start, end) / spacing))
        points.extend(_interpolate(start, end, index / count) for index in range(count))
    points.append(polyline[-1])
    return points


def _resample_markers(
    points: tuple[TimedTrajectoryPoint, ...], rate_hz: float, budget: int,
) -> tuple[TimedTrajectoryPoint, ...]:
    """Sample only the display marker; preserve every original keyframe exactly."""
    duration = points[-1].timestamp - points[0].timestamp
    interval_count = duration * rate_hz
    if (
        len(points) > budget
        or not math.isfinite(interval_count)
        or interval_count > budget - 1
    ):
        raise ValueError("display marker sample budget exceeded")
    grid_count = math.ceil(interval_count) + 1
    declared = {point.timestamp: point for point in points}
    timestamps = sorted({
        *declared,
        *(
            points[0].timestamp + index / rate_hz
            for index in range(grid_count)
            if points[0].timestamp + index / rate_hz <= points[-1].timestamp
        ),
    })
    if len(timestamps) > budget:
        raise ValueError("display marker sample budget exceeded")
    declared_times = [point.timestamp for point in points]
    result: list[TimedTrajectoryPoint] = []
    for timestamp in timestamps:
        if timestamp in declared:
            result.append(declared[timestamp])
        else:
            before_index = bisect_right(declared_times, timestamp) - 1
            before, after = points[before_index], points[before_index + 1]
            fraction = (timestamp - before.timestamp) / (after.timestamp - before.timestamp)
            result.append(TimedTrajectoryPoint(
                timestamp=timestamp,
                world_position=_interpolate(before.world_position, after.world_position, fraction),
                provenance=Provenance.INFERRED_GAP,
            ))
    return tuple(result)


class RerunDebugVisualizationAdapter:
    """VisualizationAdapter with separate opt-in evaluation/debug overlays.

    Call ``save`` before logging, then ``close`` to finalize a readable RRD.
    The adapter accepts ordinary domain Event/Observation/configuration schemas;
    it neither proposes candidates nor changes ranking/reconstruction results.
    Marker playback uses presentation-only 1 Hz interpolation by default and
    includes every declared keyframe. ``max_marker_samples`` bounds each Event.
    """

    def __init__(
        self,
        *,
        observations: tuple[Observation, ...] = (),
        navigation_config: NavigationGraphConfig | None = None,
        topology_config: CameraTopologyConfig | None = None,
        calibration_catalog: CameraCalibrationCatalog | None = None,
        recording: RecordingSink | None = None,
        debug_mode: bool = False,
        application_id: str = "amidst_debug",
        display_sample_rate_hz: float = 1.0,
        max_marker_samples: int = 20_000,
    ) -> None:
        if not math.isfinite(display_sample_rate_hz) or display_sample_rate_hz <= 0:
            raise ValueError("display sample rate must be finite and positive")
        if (
            not isinstance(max_marker_samples, int)
            or isinstance(max_marker_samples, bool)
            or max_marker_samples < 2
        ):
            raise ValueError("display marker sample budget must be an integer of at least 2")
        validated = tuple(Observation.model_validate(item.model_dump()) for item in observations)
        if len({item.observation_id for item in validated}) != len(validated):
            raise ValueError("visualization observation identities must be unique")
        self.observations = {item.observation_id: item for item in validated}
        self.navigation_config = (
            NavigationGraphConfig.model_validate(navigation_config.model_dump())
            if navigation_config is not None else None
        )
        self.topology_config = (
            CameraTopologyConfig.model_validate(topology_config.model_dump())
            if topology_config is not None else None
        )
        self.calibration_catalog = (
            validate_camera_calibration_catalog(calibration_catalog)
            if calibration_catalog is not None else None
        )
        if self.navigation_config is not None and self.topology_config is not None and (
            self.topology_config.navigation_graph_id != self.navigation_config.graph_id
            or self.topology_config.spatial_context_id != self.navigation_config.spatial_context_id
        ):
            raise ValueError("visualization topology/navigation context mismatch")
        self.recording: RecordingSink = recording or rr.RecordingStream(application_id)
        self.debug_mode = debug_mode
        self.display_sample_rate_hz = display_sample_rate_hz
        self.max_marker_samples = max_marker_samples
        self._started = False
        self._saved = False
        self._closed = False
        self._event_time_end: float | None = None

    def save(self, path: str | Path) -> None:
        """Attach a fresh RRD destination before any data; never overwrite files."""
        self._ensure_open()
        destination = Path(path)
        if destination.suffix.lower() != ".rrd":
            raise ValueError("debug recordings require an .rrd output path")
        if self._saved or self._started:
            raise RuntimeError("save must be called once before logging any data")
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also protects against an existing symlink or race.
        with destination.open("xb"):
            pass
        self.recording.save(destination)
        self._saved = True

    def flush(self) -> None:
        self._ensure_open()
        self.recording.flush()

    def close(self) -> None:
        if not self._closed:
            self.recording.flush()
            self.recording.disconnect()
            self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("recording is closed")

    def _begin(self) -> None:
        self._ensure_open()
        if not self._started:
            self._started = True
            self.recording.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
            self._document("debug/provenance_legend", {
                "OBSERVED": "green 2D camera evidence",
                "PROJECTED": "blue projected world evidence",
                "INFERRED_GAP": "orange dashed paths and moving markers",
                "GROUND_TRUTH": "gray dotted paths, debug mode only",
                "camera_anchors": "navigation/evidence anchors, not calibrated camera poses/FOV",
                "navigation": "configured waypoints, not Blender mesh walkability certification",
                "timestamps": "configured event-time seconds, not real-world capture authority",
            })
            self._log_navigation()
            self._log_topology()
            self._log_calibration()

    def _document(self, path: str, payload: object) -> None:
        self.recording.log(
            path,
            rr.TextDocument(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)),
            static=True,
        )

    def _log_navigation(self) -> None:
        config = self.navigation_config
        if config is None:
            return
        self._document("debug/navigation", config.model_dump(mode="json"))
        self.recording.log(
            "world/navigation/nodes",
            rr.Points3D(
                [node.position for node in config.nodes],
                colors=(110, 150, 170),
                radii=0.07,
                labels=[f"{node.node_id} [{node.floor_id}]" for node in config.nodes],
            ),
            static=True,
        )
        for edge in config.edges:
            self.recording.log(
                f"world/navigation/edges/{_segment_name(edge.edge_id)}",
                rr.LineStrips3D(
                    [edge.polyline], colors=(110, 150, 170), radii=0.015,
                    labels=[f"{edge.edge_id}: {edge.transition_type.value}"],
                ),
                static=True,
            )

    def _log_calibration(self) -> None:
        catalog = self.calibration_catalog
        if catalog is None:
            return
        self._document("debug/camera_calibration", catalog.model_dump(mode="json"))
        for calibration in catalog.cameras:
            root = f"world/calibrated_cameras/{_segment_name(calibration.camera.camera_id)}"
            self.recording.log(
                f"{root}/position",
                rr.Points3D(
                    [calibration.pose.position_world], colors=(80, 200, 210), radii=0.14,
                    labels=[f"{calibration.camera_name} actual calibrated pose"],
                ),
                static=True,
            )
            self.recording.log(
                f"{root}/frustum",
                rr.LineStrips3D(
                    frustum_line_segments(calibration), colors=(80, 200, 210), radii=0.015,
                    labels=[f"{calibration.camera_name} actual near/far frustum"] * 12,
                ),
                static=True,
            )

    def _log_topology(self) -> None:
        config = self.topology_config
        if config is None:
            return
        self._document("debug/camera_topology", config.model_dump(mode="json"))
        nodes = (
            {node.node_id: node.position for node in self.navigation_config.nodes}
            if self.navigation_config is not None else {}
        )
        anchors: dict[str, set[Vec3]] = {node.camera_id: set() for node in config.nodes}
        for transition in config.transitions:
            if transition.navigation_from_node_id in nodes:
                anchors[transition.from_camera_id].add(nodes[transition.navigation_from_node_id])
            if transition.navigation_to_node_id in nodes:
                anchors[transition.to_camera_id].add(nodes[transition.navigation_to_node_id])
        for observation in self.observations.values():
            if observation.camera_id in anchors:
                anchors[observation.camera_id].update(
                    point.world_position for point in observation.projected_path
                )
        for node in config.nodes:
            positions = sorted(anchors[node.camera_id])
            if positions:
                self.recording.log(
                    f"world/camera_anchors/{_segment_name(node.camera_id)}",
                    rr.Points3D(
                        positions, colors=(80, 200, 210), radii=0.14,
                        labels=[f"{node.camera_id} [{node.floor_id}] anchor"] * len(positions),
                    ),
                    static=True,
                )

    def log_event(self, event: Event) -> None:
        """Log every candidate and timed hypothesis in input order without selecting by truth."""
        self._ensure_open()
        validated = Event.model_validate(event.model_dump())
        marker_samples: dict[str, tuple[TimedTrajectoryPoint, ...]] = {}
        remaining_budget = self.max_marker_samples
        for hypothesis in validated.trajectories:
            samples = _resample_markers(
                hypothesis.timed_points, self.display_sample_rate_hz, remaining_budget,
            )
            marker_samples[hypothesis.hypothesis_id] = samples
            remaining_budget -= len(samples)
        self._begin()
        self._event_time_end = validated.time_range[1]
        event_path = f"events/{_segment_name(validated.event_id)}"
        self._document(f"debug/{event_path}", {
            "event_id": validated.event_id,
            "target_id": validated.target_id,
            "time_range": validated.time_range,
            "termination_reason": validated.termination_reason.value,
            "candidate_count": len(validated.candidates),
            "hypothesis_count": len(validated.trajectories),
            "candidate_order": [item.candidate_id for item in validated.candidates],
            "display_sample_rate_hz": self.display_sample_rate_hz,
            "marker_sample_count": self.max_marker_samples - remaining_budget,
            "marker_interpolation": "presentation only; generated samples are INFERRED_GAP",
        })
        for observation_id in validated.observation_ids:
            observation = self.observations.get(observation_id)
            if observation is not None:
                self._log_observation(observation)
        for rank, candidate in enumerate(validated.candidates, start=1):
            candidate_name = _segment_name(candidate.candidate_id)
            candidate_path = f"world/{event_path}/candidates/{candidate_name}"
            strips = _dashed_strips(candidate.polyline)
            if strips:
                self.recording.log(
                    candidate_path,
                    rr.LineStrips3D(
                        strips, colors=PROVENANCE_COLORS[Provenance.INFERRED_GAP], radii=0.025,
                        labels=[f"Top-{rank}: {candidate.candidate_id} INFERRED_GAP"] * len(strips),
                    ),
                    static=True,
                )
            self._document(f"debug/{event_path}/candidates/{candidate_name}", {
                "rank": rank,
                **candidate.model_dump(mode="json"),
            })
        for hypothesis in validated.trajectories:
            hypothesis_path = (
                f"world/{event_path}/hypotheses/{_segment_name(hypothesis.hypothesis_id)}"
            )
            label = (
                f"{hypothesis.hypothesis_id}: {hypothesis.kind.value} INFERRED_GAP "
                f"slack={hypothesis.temporal_slack:g}s"
            )
            strips = _dashed_strips(
                tuple(point.world_position for point in hypothesis.timed_points)
            )
            if strips:
                self.recording.log(
                    f"{hypothesis_path}/path",
                    rr.LineStrips3D(
                        strips, colors=PROVENANCE_COLORS[Provenance.INFERRED_GAP], radii=0.035,
                        labels=[label] * len(strips),
                    ),
                    static=True,
                )
            self._document(
                f"debug/{event_path}/hypotheses/{_segment_name(hypothesis.hypothesis_id)}",
                hypothesis.model_dump(mode="json"),
            )
            for point in marker_samples[hypothesis.hypothesis_id]:
                self.recording.set_time(EVENT_TIMELINE, duration=point.timestamp)
                self.recording.log(
                    f"{hypothesis_path}/marker",
                    rr.Points3D(
                        [point.world_position], colors=PROVENANCE_COLORS[point.provenance],
                        radii=0.11, labels=[f"{label}; sample={point.provenance.value}"],
                    ),
                )

    def _log_observation(self, observation: Observation) -> None:
        name = _segment_name(observation.observation_id)
        for frame in observation.frames:
            if frame.point_2d is not None:
                self.recording.set_time(EVENT_TIMELINE, duration=frame.timestamp)
                self.recording.log(
                    f"cameras/{_segment_name(frame.camera_id)}/observed/{name}",
                    rr.Points2D(
                        [frame.point_2d], colors=PROVENANCE_COLORS[Provenance.OBSERVED],
                        radii=3, labels=[f"{name} OBSERVED"],
                    ),
                )
        for point in observation.projected_path:
            self.recording.set_time(EVENT_TIMELINE, duration=point.timestamp)
            self.recording.log(
                f"world/projected/{name}",
                rr.Points3D(
                    [point.world_position], colors=PROVENANCE_COLORS[Provenance.PROJECTED],
                    radii=0.1, labels=[f"{observation.observation_id} PROJECTED"],
                ),
            )

    def log_debug_ground_truth(self, ground_truth: GroundTruthTrajectory) -> None:
        """Truth is an optional gray debug overlay; this method cannot affect Event."""
        if not self.debug_mode:
            raise PermissionError("Ground Truth overlay requires explicit debug mode")
        validated = GroundTruthTrajectory.model_validate(ground_truth.model_dump())
        self._begin()
        root = f"world/debug_ground_truth/{_segment_name(validated.trajectory_id)}"
        self.recording.log(
            f"{root}/dotted_path",
            rr.Points3D(
                _dotted_points(tuple(sample.position for sample in validated.samples)),
                colors=PROVENANCE_COLORS[Provenance.GROUND_TRUTH], radii=0.025,
            ),
            static=True,
        )
        self._document(f"debug/ground_truth/{_segment_name(validated.trajectory_id)}", {
            "provenance": Provenance.GROUND_TRUTH.value,
            "scene_id": validated.scene_id,
            "data_kind": validated.data_kind,
            "sample_source": validated.sample_source,
            "random_seed": validated.random_seed,
            "usage": "debug/evaluation only",
        })
        for sample in validated.samples:
            self.recording.set_time(EVENT_TIMELINE, duration=sample.timestamp)
            self.recording.log(
                f"{root}/marker",
                rr.Points3D(
                    [sample.position], colors=PROVENANCE_COLORS[Provenance.GROUND_TRUTH],
                    radii=0.09, labels=[f"{validated.trajectory_id} GROUND_TRUTH"],
                ),
            )

    def log_metrics(self, metrics: Mapping[str, object]) -> None:
        """Display evaluation results without passing them back to reconstruction."""
        self._begin()
        self._document("debug/evaluation_metrics", dict(metrics))
        if self._event_time_end is not None:
            self.recording.set_time(EVENT_TIMELINE, duration=self._event_time_end)
        for name, value in metrics.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not math.isfinite(value):
                    raise ValueError("visualization metric values must be finite")
                self.recording.log(f"metrics/{_segment_name(name)}", rr.Scalars(value))
