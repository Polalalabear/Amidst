"""Presentation samples from canonical frozen timing; no inference or extrapolation."""

from bisect import bisect_left
from collections.abc import Sequence
from typing import Literal

from amidst.domain.common import Vec3
from amidst.engineering.registry import MediaFrame, opaque_ref
from amidst.product.contracts import EventDetail, FrameSelection, Marker, TimelineState


def timeline_state(run_ref: str, timestamp: float, frames: Sequence[MediaFrame],
                   events: Sequence[EventDetail], *, tolerance_s: float = 0.25) -> TimelineState:
    cameras = dict.fromkeys(frame.camera_ref for frame in frames)
    selected = []
    for camera_ref in cameras:
        group = [frame for frame in frames if frame.camera_ref == camera_ref]
        nearest = min(group, key=lambda f: (abs(f.timestamp - timestamp), f.timestamp))
        available = abs(nearest.timestamp - timestamp) <= tolerance_s
        selected.append(FrameSelection(
            camera_ref=camera_ref, camera_id=nearest.camera_id,
            media_ref=nearest.media_ref if available else None,
            frame_timestamp=nearest.timestamp if available else None,
            requested_timestamp=timestamp,
            status="AVAILABLE" if available else "NO_FRAME_WITHIN_TOLERANCE",
            offset_seconds=nearest.timestamp - timestamp if available else None,
        ))
    markers: list[Marker] = []
    seen: set[str] = set()
    source_samples = {frame.camera_id: frame for frame in selected
                      if frame.status == "AVAILABLE"}
    for event in events:
        if not event.time_range[0] <= timestamp <= event.time_range[1]:
            continue
        # Hold the nearest actual RGB measurement, retaining its original timestamp.
        # This is presentation sampling, never a newly observed/interpolated position.
        for point in event.projected_path:
            source = source_samples.get(point.camera_id)
            if (source is not None and source.frame_timestamp is not None
                and abs(point.timestamp - source.frame_timestamp) < 1e-8
                and point.observation_id not in seen):
                seen.add(point.observation_id)
                markers.append(Marker(marker_ref=opaque_ref("marker", point.observation_id),
                    event_ref=event.event_ref, timestamp=point.timestamp,
                    world_position=point.world_position, evidence_state="PROJECTED",
                    interpolated=False, camera_id=point.camera_id,
                    source_frame_ref=source.media_ref,
                    sample_offset_seconds=point.timestamp - timestamp))
        for hypothesis in event.trajectories:
            points = hypothesis.timed_points
            if not points or not points[0].timestamp <= timestamp <= points[-1].timestamp:
                continue
            index = bisect_left([p.timestamp for p in points], timestamp)
            exact = points[index].timestamp == timestamp
            state: Literal["PROJECTED", "INFERRED_GAP"]
            position: Vec3
            if exact:
                position = points[index].world_position
                state = "PROJECTED" if points[index].provenance == "PROJECTED" else "INFERRED_GAP"
            else:
                before, after = points[index - 1], points[index]
                fraction = (timestamp - before.timestamp) / (after.timestamp - before.timestamp)
                position = (
                    before.world_position[0] + fraction * (
                        after.world_position[0] - before.world_position[0]),
                    before.world_position[1] + fraction * (
                        after.world_position[1] - before.world_position[1]),
                    before.world_position[2] + fraction * (
                        after.world_position[2] - before.world_position[2]),
                )
                state = "INFERRED_GAP"
            markers.append(Marker(
                marker_ref=opaque_ref("marker", event.event_ref, hypothesis.hypothesis_id),
                event_ref=event.event_ref, timestamp=timestamp, world_position=position,
                evidence_state=state, interpolated=not exact,
                candidate_ref=hypothesis.candidate_id, hypothesis_ref=hypothesis.hypothesis_id,
            ))
    return TimelineState(run_ref=run_ref, timestamp=timestamp, frames=tuple(selected),
                         markers=tuple(markers))
