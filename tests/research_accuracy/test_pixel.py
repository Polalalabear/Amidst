"""Continuity improvements keep the detector population and uncertainty visible."""

from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pydantic import ValidationError

from amidst.engineering import perception as detector
from amidst.engineering.perception import FrameStatus, Measurement, PerceptionResult, RGBFrame
from amidst.research_accuracy.pixel import (
    PRODUCER_VERSION,
    PixelContinuityConfig,
    _minimum_assignment,
    produce_perception_v2,
    producer_sha256,
    reassociate_perception_v2,
)


def _detected(
    frames: list[tuple[float, list[tuple[float, tuple[float, float, float]]]]],
) -> PerceptionResult:
    measurements = tuple(
        Measurement(
            observation_id=f"pixel:model:run:CAM:{index:04d}:{component:02d}",
            local_track_id=f"legacy:{index}:{component}", camera_id="CAM", model_id="model",
            run_id="run", timestamp=timestamp, frame_ref=f"frame:{index}",
            bbox_xyxy=(x - 3, 10, x + 4, 41), contact_pixel=(x, 40), appearance=color,
            uncertainty=0.25, input_sha256="a" * 64, status="DETECTED",
            local_alternative_count=0, evidence_refs=(f"frame:{index}",),
        )
        for index, (timestamp, rows) in enumerate(frames)
        for component, (x, color) in enumerate(rows)
    )
    return PerceptionResult(
        model_id="model", run_id="run", measurements=measurements, tracks=(),
        frame_statuses=tuple(FrameStatus(
            frame_ref=f"frame:{index}", camera_id="CAM", timestamp=timestamp,
            status="MEASURED" if rows else "NO_DETECTION", measurement_count=len(rows),
        ) for index, (timestamp, rows) in enumerate(frames)),
        input_manifest_sha256="b" * 64,
        producer_sha256=sha256(Path(detector.__file__).read_bytes()).hexdigest(), complete=True,
    )


BLUE = (20.0, 40.0, 200.0)
RED = (200.0, 40.0, 20.0)


def _track_at(result: PerceptionResult, timestamp: float, x: float) -> str:
    return next(row.local_track_id for row in result.measurements
                if row.timestamp == timestamp and row.contact_pixel[0] == x)


def test_frame_wide_assignment_prevents_first_component_stealing_continuation() -> None:
    fixed = _detected([(0, [(60, BLUE)]), (0.4, [(40, BLUE), (65, BLUE)])])
    config = PixelContinuityConfig(use_velocity=False, appearance_weight=0, shape_weight=0)
    global_result = reassociate_perception_v2(fixed, config=config)
    greedy = reassociate_perception_v2(
        fixed, config=config.model_copy(update={"assignment": "greedy"}),
    )
    assert _track_at(global_result, 0, 60) == _track_at(global_result, 0.4, 65)
    assert _track_at(global_result, 0, 60) != _track_at(global_result, 0.4, 40)
    assert _track_at(greedy, 0, 60) == _track_at(greedy, 0.4, 40)


def test_velocity_maintains_crossing_similar_components_with_fixed_detections() -> None:
    fixed = _detected([
        (0, [(20, BLUE), (80, BLUE)]), (0.4, [(40, BLUE), (60, BLUE)]),
        (0.8, [(40, BLUE), (60, BLUE)]),
    ])
    moving = reassociate_perception_v2(fixed)
    static = reassociate_perception_v2(fixed, config=PixelContinuityConfig(use_velocity=False))
    assert _track_at(moving, 0, 20) == _track_at(moving, 0.8, 60)
    assert _track_at(moving, 0, 80) == _track_at(moving, 0.8, 40)
    assert _track_at(static, 0, 20) == _track_at(static, 0.8, 40)


def test_appearance_is_soft_and_can_be_removed_independently() -> None:
    fixed = _detected([(0, [(60, RED)]), (0.4, [(50, BLUE), (70, RED)])])
    appearance = reassociate_perception_v2(fixed)
    no_appearance = reassociate_perception_v2(
        fixed, config=PixelContinuityConfig(appearance_weight=0),
    )
    assert _track_at(appearance, 0, 60) == _track_at(appearance, 0.4, 70)
    assert _track_at(no_appearance, 0, 60) == _track_at(no_appearance, 0.4, 50)
    # Color is never a hard rejection: a single changing-color continuation can match.
    changed = reassociate_perception_v2(_detected([(0, [(60, RED)]), (0.4, [(61, BLUE)])]))
    assert _track_at(changed, 0, 60) == _track_at(changed, 0.4, 61)


def test_merge_is_retained_without_contaminating_either_predicted_track() -> None:
    fixed = _detected([
        (0, [(20, BLUE), (80, BLUE)]), (0.4, [(40, BLUE), (60, BLUE)]),
        (0.8, [(50, BLUE)]), (1.2, [(20, BLUE), (80, BLUE)]),
    ])
    merged = fixed.measurements[4].model_copy(update={"bbox_xyxy": (35, 10, 66, 41)})
    fixed = fixed.model_copy(update={"measurements": (*fixed.measurements[:4], merged,
                                                       *fixed.measurements[5:])})
    result = reassociate_perception_v2(fixed)
    contact = result.measurements[4]
    assert contact.status == "MERGED_OR_PARTIAL"
    assert contact.local_alternative_count == 2 and contact.uncertainty >= 0.75
    assert contact.local_track_id not in {_track_at(result, 0, 20), _track_at(result, 0, 80)}
    assert _track_at(result, 0, 20) == _track_at(result, 1.2, 80)
    assert _track_at(result, 0, 80) == _track_at(result, 1.2, 20)
    assert len(result.measurements) == len(fixed.measurements)
    assert result.frame_statuses[2].status == "AMBIGUOUS_COMPONENT"
    recovered = [track for track in result.tracks if len(track.timestamps) == 3]
    assert all(track.missing_timestamps == (0.8,) and track.status == "FRAGMENTED"
               for track in recovered)


def test_short_gap_recovers_but_never_fills_missing_measurements() -> None:
    fixed = _detected([
        (0, [(20, BLUE)]), (0.4, [(30, BLUE)]), (0.8, []), (1.2, [(50, BLUE)]),
        (2.8, [(90, BLUE)]),
    ])
    result = reassociate_perception_v2(fixed)
    assert _track_at(result, 0, 20) == _track_at(result, 1.2, 50)
    assert _track_at(result, 0, 20) != _track_at(result, 2.8, 90)
    assert len(result.measurements) == 4
    assert result.tracks[0].missing_timestamps == (0.8,)
    assert result.frame_statuses[2].status == "NO_DETECTION"


def test_detector_population_ids_and_bytes_are_preserved_and_v2_is_bound() -> None:
    fixed = _detected([(0, [(20, BLUE)]), (0.4, [(30, BLUE)])])
    before = fixed.model_dump_json()
    result = reassociate_perception_v2(fixed)
    assert fixed.model_dump_json() == before
    assert result.producer_version == PRODUCER_VERSION
    assert result.producer_sha256 != fixed.producer_sha256
    assert producer_sha256(PixelContinuityConfig()) != producer_sha256(
        PixelContinuityConfig(use_velocity=False),
    )
    for old, new in zip(fixed.measurements, result.measurements, strict=True):
        assert (old.bbox_xyxy, old.contact_pixel, old.appearance,
                old.frame_ref, old.input_sha256) == (
            new.bbox_xyxy, new.contact_pixel, new.appearance, new.frame_ref, new.input_sha256,
        )
        assert new.observation_id.startswith("pixel-v2:")
    assert PerceptionResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValueError, match="bound v1 RGB detector"):
        reassociate_perception_v2(result)
    with pytest.raises(ValueError, match="bound v1 RGB detector"):
        reassociate_perception_v2(fixed.model_copy(update={"producer_sha256": "0" * 64}))


def _rgb_sequence(root: Path) -> tuple[RGBFrame, ...]:
    frames = []
    for index, positions in enumerate([[], [60], [40, 65], [30, 70], [], [], []]):
        image = Image.new("RGB", (120, 80), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        for x in positions:
            draw.rectangle((x - 3, 10, x + 3, 40), fill=(20, 40, 200))
        path = root / f"{index}.png"
        image.save(path)
        frames.append(RGBFrame(media_ref=f"frame:{index}", camera_id="CAM", timestamp=index * 0.4,
                               path=path, sha256=sha256(path.read_bytes()).hexdigest(),
                               width=120, height=80))
    return tuple(frames)


def test_real_verified_rgb_flow_reproduces_and_cannot_read_gt(tmp_path: Path) -> None:
    frames = _rgb_sequence(tmp_path)
    baseline = detector.produce_perception(frames, model_id="model", run_id="run")
    first = produce_perception_v2(frames, model_id="model", run_id="run")
    sidecar = tmp_path / "ground_truth.json"
    sidecar.write_text('{"actor_identity":"poison","path":[999,999]}')
    assert first == produce_perception_v2(frames, model_id="model", run_id="run")
    sidecar.unlink()
    assert first == produce_perception_v2(tuple(reversed(frames)), model_id="model", run_id="run")
    assert first == reassociate_perception_v2(baseline)
    assert len(first.measurements) == len(baseline.measurements) == 5
    assert _track_at(first, 0.4, 60) == _track_at(first, 0.8, 65)
    assert _track_at(baseline, 0.4, 60) == _track_at(baseline, 0.8, 40)
    assert "poison" not in first.model_dump_json() and str(tmp_path) not in first.model_dump_json()


def test_rgb_failures_empty_input_and_namespace_validation(tmp_path: Path) -> None:
    frames = _rgb_sequence(tmp_path)
    frames[0].path.unlink()
    frames[1].path.write_bytes(b"corrupt")
    result = produce_perception_v2(frames, model_id="model", run_id="run")
    assert not result.complete
    assert result.frame_statuses[0].status == "MISSING_IMAGE"
    assert result.frame_statuses[1].status == "HASH_MISMATCH"
    assert all(row.frame_ref not in {frames[0].media_ref, frames[1].media_ref}
               for row in result.measurements)
    empty = produce_perception_v2((), model_id="model", run_id="run")
    assert empty.complete and not empty.measurements and not empty.tracks
    with pytest.raises(ValueError, match="duplicate frame"):
        produce_perception_v2((frames[2], frames[2]), model_id="model", run_id="run")
    with pytest.raises(ValueError, match="namespaces"):
        produce_perception_v2((), model_id="", run_id="run")
    with pytest.raises(ValidationError):
        PixelContinuityConfig(max_gap_s=0)
    with pytest.raises(ValidationError):
        PixelContinuityConfig(appearance_weight=-1)


def test_global_assignment_is_minimum_and_allows_independent_unmatched_rows() -> None:
    assert _minimum_assignment([]) == []
    assert _minimum_assignment([[0.8, 1.05, 1.05], [0.2, 1.05, 1.05]]) == [1, 0]
    assert _minimum_assignment([[0, 0], [0, 0]]) == [0, 1]
