"""Actual pixel fragments yield provisional alternatives without canonical writes."""

from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from amidst.engineering.perception import RGBFrame, produce_perception
from amidst.engineering.registry import (
    CameraEntry,
    ClockBinding,
    CoordinateBinding,
    LocationModel,
    LocationRegistry,
    MediaFrame,
    RegistryStore,
    ResourceScope,
    opaque_ref,
    scope_parts,
)
from amidst.product.appearance import build_appearance_bundle
from amidst.product.stitching import StitchConfig, StitchError, build_stitch_bundle


def _recovery(
    tmp_path: Path, *, missing_endpoint: bool = False
) -> tuple[object, object, ResourceScope]:
    scope = ResourceScope(
        place_id="fixture",
        model_id="fixture-model",
        model_revision="1",
        run_id="recovery-v1",
        source_id="rgb-fixture",
        source_sha256="a" * 64,
        spatial_context_id="fixture-context",
        spatial_context_sha256="b" * 64,
        clock_id="seconds",
    )
    camera_ref = opaque_ref("camera", *scope_parts(scope), "CAM_A")
    frames, media, links = [], [], {}
    for index in range(14):
        path = tmp_path / "rgb" / f"f-{index:04d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (240, 120), (10, 20, 30))
        draw = ImageDraw.Draw(image)
        positions = (
            [20 + index * 8]
            if index < 3
            else [70 + (index - 7) * 6, 100 + (index - 7) * 6]
            if index >= 7
            else []
        )
        for x in positions:
            draw.rectangle((x, 55, x + 10, 80), fill=(200, 40, 40))
        image.save(path)
        fingerprint = sha256(path.read_bytes()).hexdigest()
        original_ref = f"rgb:{index:04d}"
        ref = opaque_ref("media", *scope_parts(scope), "CAM_A", str(index), fingerprint)
        links[original_ref] = ref
        frames.append(
            RGBFrame(
                media_ref=original_ref,
                camera_id="CAM_A",
                timestamp=index / 5,
                path=path,
                sha256=fingerprint,
                width=240,
                height=120,
            )
        )
        media.append(
            MediaFrame(
                scope=scope,
                camera_id="CAM_A",
                camera_ref=camera_ref,
                media_ref=ref,
                frame_id=index,
                timestamp=index / 5,
                relative_path=path.relative_to(tmp_path).as_posix(),
                sha256=fingerprint,
                size_bytes=path.stat().st_size,
                width=240,
                height=120,
            )
        )
    model = LocationModel(
        scope=scope,
        display_name="Recovery fixture",
        coordinates=CoordinateBinding(
            native_units="METRES",
            metres_per_unit=1,
            normalization_policy="IDENTITY",
            authority="SYNTHETIC_CONFIG",
        ),
        clock=ClockBinding(
            clock_id=scope.clock_id, mapping_sha256="c" * 64, authority="SYNTHETIC_CONFIG"
        ),
        authority="SYNTHETIC_CONFIG",
    )
    registry = LocationRegistry(
        models=(model,),
        cameras=(
            CameraEntry(
                scope=scope,
                camera_id="CAM_A",
                camera_ref=camera_ref,
                authority="SYNTHETIC_CONFIG",
            ),
        ),
        frames=tuple(media),
    )
    perception = produce_perception(frames, model_id=scope.model_id, run_id=scope.run_id)
    if missing_endpoint:
        (tmp_path / "rgb" / "f-0002.png").unlink()
    appearance = build_appearance_bundle(
        perception, RegistryStore(registry, tmp_path), scope, links, input_config_sha256="d" * 64
    )
    return perception, appearance, scope


def test_recovery_alternatives_overlap_and_original_ids_preserved(tmp_path: Path) -> None:
    perception, appearance, scope = _recovery(tmp_path)
    original = perception.model_dump_json()
    result = build_stitch_bundle(perception, appearance, scope=scope)
    assert len(perception.tracks) == 3
    recoveries = [row for row in result.hypotheses if row.kind == "SHORT_GAP_RECOVERY"]
    assert len(recoveries) == 2 and all(row.status == "PROVISIONAL" for row in recoveries)
    assert all(row.alternatives and row.missing_intervals for row in recoveries)
    assert all(
        not row.confirmed_identity and not row.creates_observed_gap_samples
        for row in result.hypotheses
    )
    overlaps = [row for row in result.hypotheses if row.kind == "OVERLAPPING_TRACKLETS"]
    assert len(overlaps) == 1 and overlaps[0].status == "INCOMPATIBLE"
    assert len([row for row in result.hypotheses if row.kind == "UNMATCHED"]) == 3
    assert {row.original_track_id for row in result.original_tracks} == {
        row.local_track_id for row in perception.tracks
    }
    assert perception.model_dump_json() == original
    assert not result.canonical_records_rewritten and not result.physical_authority_expanded


def test_partial_endpoints_hold_instead_of_confirming_stitch(tmp_path: Path) -> None:
    perception, appearance, scope = _recovery(tmp_path)
    updated = tuple(
        row.model_copy(update={"status": "MERGED_OR_PARTIAL"})
        if row.observation_id == perception.tracks[0].observation_ids[-1]
        else row
        for row in perception.measurements
    )
    perception = perception.model_copy(update={"measurements": updated})
    # Change only the valid source-bound pixel producer metadata fixture, then bind it explicitly.
    from amidst.engineering.access import digest

    appearance = appearance.model_copy(
        update={"perception_sha256": digest(perception.model_dump(mode="json"))}
    )
    result = build_stitch_bundle(
        perception, appearance, scope=scope, config=StitchConfig(minimum_quality=0)
    )
    assert all(
        row.status == "HOLD" for row in result.hypotheses if row.kind == "SHORT_GAP_RECOVERY"
    )


def test_missing_endpoint_holds_and_search_completion_remains_separate(tmp_path: Path) -> None:
    perception, appearance, scope = _recovery(tmp_path, missing_endpoint=True)
    result = build_stitch_bundle(perception, appearance, scope=scope)
    assert result.complete and not result.source_inputs_complete
    candidates = [row for row in result.hypotheses if row.kind == "SHORT_GAP_RECOVERY"]
    assert len(candidates) == 2
    assert all(
        row.status == "HOLD" and row.reason == "ENDPOINT_APPEARANCE_UNAVAILABLE"
        for row in candidates
    )


def test_pair_budget_window_and_foreign_run_guard(tmp_path: Path) -> None:
    perception, appearance, scope = _recovery(tmp_path)
    limited = build_stitch_bundle(
        perception, appearance, scope=scope, config=StitchConfig(max_pairs=1)
    )
    assert limited.truncated and not limited.complete and limited.pairs_inspected == 1
    short = build_stitch_bundle(
        perception, appearance, scope=scope, config=StitchConfig(max_gap_s=0.5)
    )
    assert short.excluded_beyond_gap_window == 2
    assert not any(row.kind == "SHORT_GAP_RECOVERY" for row in short.hypotheses)
    foreign = scope.model_copy(update={"run_id": "different"})
    with pytest.raises(StitchError, match="STITCH_INPUT_BINDING_MISMATCH"):
        build_stitch_bundle(perception, appearance, scope=foreign)


def test_gt_injection_rejected_without_changing_originals(tmp_path: Path) -> None:
    perception, appearance, scope = _recovery(tmp_path)
    original = perception.model_dump_json()
    polluted = perception.model_copy()
    polluted.__dict__["actor_identity"] = "simulator-global-answer"
    with pytest.raises(ValueError, match="UNDECLARED_INPUT"):
        build_stitch_bundle(polluted, appearance, scope=scope)
    assert perception.model_dump_json() == original
    assert build_stitch_bundle(perception, appearance, scope=scope).complete
