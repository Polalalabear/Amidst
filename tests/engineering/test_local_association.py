"""M3 pixel-only lineage, alternative preservation and honest unsupported cases."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.domain.geometry import Plane
from amidst.domain.trajectory import TerminationReason
from amidst.engineering.local_association import (
    AssociationPolicy,
    ConfiguredRegion,
    GroundCalibration,
    InferenceBundle,
    InferenceScope,
    SyntheticStaticContext,
    build_inference,
    content_sha256,
)
from amidst.engineering.perception import (
    LocalTrack,
    Measurement,
    PerceptionResult,
    produce_perception,
)
from amidst.engineering.synthetic import generate_sequence

HASH = "a" * 64
CONTEXT_HASH = "b" * 64


def scope(run_id: str = "test-run") -> InferenceScope:
    return InferenceScope(
        place_id="synthetic-lab",
        model_id="lab",
        model_revision="1",
        run_id=run_id,
        clock_id="configured-seconds",
        source_ref="source:lab",
        source_sha256=HASH,
        spatial_context_id="context:lab",
        context_sha256=CONTEXT_HASH,
    )


def context() -> SyntheticStaticContext:
    plane = Plane(plane_id="floor:lab", point=(0, 0, 0), normal=(0, 0, 1), floor_id="floor:0")
    return SyntheticStaticContext(
        spatial_context_id="context:lab",
        source_sha256=HASH,
        context_sha256=CONTEXT_HASH,
        ground_plane=plane,
        walkable_bounds_xy_m=(0, 0, 8, 4),
        calibrations=tuple(
            GroundCalibration(
                camera_id=camera,
                plane=plane,
                affine_ground_to_pixel=((1, 0, 0), (0, 1, 0)),
            )
            for camera in ("CAM_A", "CAM_B")
        ),
        allowed_camera_pairs=(("CAM_A", "CAM_B"), ("CAM_B", "CAM_A")),
        detour_waypoints_m=((2, 2, 0), (2, 0.5, 0)),
        regions=(
            ConfiguredRegion(region_id="west", floor_id="floor:0", bounds_xy_m=(0, 0, 2, 4)),
            ConfiguredRegion(region_id="east", floor_id="floor:0", bounds_xy_m=(2, 0, 8, 4)),
        ),
    )


def result(
    *rows: tuple[str, str, tuple[float, ...], tuple[tuple[float, float], ...]],
    run_id: str = "test-run",
) -> PerceptionResult:
    measurements: list[Measurement] = []
    tracks: list[LocalTrack] = []
    for camera, short_id, times, pixels in rows:
        track_id = f"lab/{run_id}/{camera}/{short_id}"
        selected: list[Measurement] = []
        for index, (timestamp, pixel) in enumerate(zip(times, pixels, strict=True)):
            selected.append(
                Measurement(
                    observation_id=f"pixels:{track_id}/{index}",
                    local_track_id=track_id,
                    camera_id=camera,
                    model_id="lab",
                    run_id=run_id,
                    timestamp=timestamp,
                    frame_ref=f"media:{camera}/{timestamp}",
                    bbox_xyxy=(pixel[0] - 0.1, pixel[1] - 0.2, pixel[0] + 0.1, pixel[1] + 0.1),
                    contact_pixel=pixel,
                    appearance=(45, 80, 140),
                    uncertainty=0.2,
                    input_sha256=HASH,
                    status="DETECTED",
                    local_alternative_count=0,
                    evidence_refs=(f"media:{camera}/{timestamp}",),
                )
            )
        measurements.extend(selected)
        tracks.append(
            LocalTrack(
                local_track_id=track_id,
                camera_id=camera,
                model_id="lab",
                run_id=run_id,
                observation_ids=tuple(row.observation_id for row in selected),
                timestamps=times,
                status="COMPLETE",
                missing_timestamps=(),
                termination_reason="SEQUENCE_END",
            )
        )
    return PerceptionResult(
        model_id="lab",
        run_id=run_id,
        measurements=tuple(measurements),
        tracks=tuple(tracks),
        frame_statuses=(),
        input_manifest_sha256=HASH,
        producer_sha256=CONTEXT_HASH,
        complete=True,
    )


def ambiguous_result() -> PerceptionResult:
    return result(
        ("CAM_A", "a", (0.0, 0.2), ((1, 1), (1.2, 1))),
        ("CAM_B", "b", (2.0, 2.2), ((3, 1), (3.2, 1))),
        ("CAM_B", "c", (2.0, 2.2), ((3, 1.4), (3.2, 1.4))),
    )


def test_every_feasible_pair_and_unmatched_survives_without_global_identity() -> None:
    perception = ambiguous_result()
    immutable_before = perception.model_dump_json()
    bundle = build_inference(perception, scope=scope(), context=context())
    assert perception.model_dump_json() == immutable_before
    assert bundle.pair_count == 3
    assert bundle.association_enumeration_complete
    assert len([item for item in bundle.association_hypotheses if item.kind == "UNMATCHED"]) == 3
    feasible = [
        item
        for item in bundle.association_hypotheses
        if item.kind == "CROSS_CAMERA_GAP" and item.status == "PROVISIONAL"
    ]
    assert len(feasible) == 2
    assert len(bundle.snapshot.gaps) == 2
    assert len({item.provisional_binding_id for item in feasible}) == 2
    assert all(item.candidate_count == 3 for item in feasible)
    assert all(
        item.complete and item.termination_reason == TerminationReason.COMPLETE for item in feasible
    )
    original_by_id = {
        item.observation.observation_id: item for item in bundle.snapshot.observations
    }
    for mapping in bundle.local_record_maps:
        observation = original_by_id[mapping.canonical_observation_id]
        assert observation.observation.target_id == mapping.local_track_id
        assert observation.sample_ids == mapping.original_pixel_observation_ids
    for mapping in bundle.derived_record_maps:
        for identity in mapping.derived_observation_ids:
            assert original_by_id[identity].observation.target_id == mapping.provisional_binding_id
        assert set(mapping.original_observation_ids).isdisjoint(mapping.derived_observation_ids)
    assert InferenceBundle.model_validate_json(bundle.model_dump_json()) == bundle


def test_overlap_keeps_provisional_association_without_fake_blind_gap() -> None:
    perception = result(
        ("CAM_A", "a", (1.0, 1.2), ((1, 1), (1.2, 1))),
        ("CAM_B", "b", (1.0, 1.2), ((1.1, 1), (1.3, 1))),
    )
    bundle = build_inference(perception, scope=scope(), context=context())
    pair = next(item for item in bundle.association_hypotheses if item.kind != "UNMATCHED")
    assert pair.kind == "OVERLAPPING_VISIBILITY"
    assert pair.status == "PROVISIONAL"
    assert pair.time_range == (1.0, 1.2)
    assert pair.event_id is None and pair.complete is None
    assert pair.termination_reason is None
    assert pair.reason == "OVERLAP_ASSOCIATION_NO_BLIND_GAP_OR_CAMERA_HANDOFF"
    assert not bundle.snapshot.gaps
    assert not bundle.derived_record_maps


def test_same_camera_recovery_has_source_bound_hold_and_real_endpoints() -> None:
    perception = result(
        ("CAM_A", "a", (0.0, 0.2), ((1, 1), (1.2, 1))),
        ("CAM_A", "b", (2.0, 2.2), ((3, 1), (3.2, 1))),
    )
    bundle = build_inference(perception, scope=scope(), context=context())
    pair = next(item for item in bundle.association_hypotheses if item.kind != "UNMATCHED")
    assert pair.kind == "SAME_CAMERA_RECOVERY" and pair.status == "HOLD"
    assert pair.camera_ids == ("CAM_A", "CAM_A")
    assert pair.time_range == (0.2, 2.0)
    assert pair.source_ref == scope().source_ref
    assert pair.spatial_context_id == context().spatial_context_id
    assert pair.event_id is None and pair.complete is None
    assert not bundle.snapshot.gaps


def test_fragment_within_local_track_splits_without_merging_gap() -> None:
    perception = result(("CAM_A", "a", (0.0, 0.2, 2.0, 2.2), ((1, 1), (1.2, 1), (3, 1), (3.2, 1))))
    bundle = build_inference(perception, scope=scope(), context=context())
    assert len(bundle.local_record_maps) == 2
    assert len({item.local_track_id for item in bundle.local_record_maps}) == 1
    pair = next(item for item in bundle.association_hypotheses if item.kind != "UNMATCHED")
    assert pair.kind == "SAME_CAMERA_RECOVERY" and pair.status == "HOLD"
    assert pair.time_range == (0.2, 2.0)
    assert not bundle.snapshot.gaps


def test_cross_run_context_source_and_track_mismatch_fail_closed() -> None:
    perception = ambiguous_result()
    with pytest.raises(ValueError, match="model/run"):
        build_inference(perception, scope=scope("other-run"), context=context())
    with pytest.raises(ValueError, match="source/context"):
        build_inference(
            perception,
            scope=scope(),
            context=context().model_copy(
                update={"context_sha256": "c" * 64},
            ),
        )
    mixed = perception.model_copy(
        update={
            "tracks": (
                perception.tracks[0].model_copy(update={"run_id": "other-run"}),
                *perception.tracks[1:],
            ),
        }
    )
    with pytest.raises(ValueError, match="cross model/run"):
        build_inference(mixed, scope=scope(), context=context())


def test_missing_calibration_and_outside_scope_never_use_truth_fallback() -> None:
    perception = result(
        ("CAM_A", "a", (0.0,), ((100, 100),)), ("UNKNOWN_CAMERA", "b", (2.0,), ((1, 1),))
    )
    bundle = build_inference(perception, scope=scope(), context=context())
    assert [item.status for item in bundle.projected_measurements] == [
        "OUTSIDE_STATIC_SCOPE",
        "PROJECTION_MISSING",
    ]
    assert all(item.point is None and not item.region_ids for item in bundle.projected_measurements)
    assert all(not item.observation.projected_path for item in bundle.snapshot.observations)
    assert not bundle.snapshot.gaps


def test_all_routes_and_timing_alternatives_keep_bounded_search_status() -> None:
    policy = AssociationPolicy(graph_search={"max_candidate_paths": 1})
    bundle = build_inference(ambiguous_result(), scope=scope(), context=context(), policy=policy)
    gaps = bundle.snapshot.gaps
    assert len(gaps) == 2
    assert all(
        gap.search_result.termination_reason == TerminationReason.MAX_PATHS_REACHED
        and not gap.search_result.complete
        for gap in gaps
    )
    assert all(len(gap.event.candidates) == 1 for gap in gaps)
    assert all(gap.event.trajectories for gap in gaps)


def test_impossible_motion_retains_no_feasible_path_event() -> None:
    perception = result(("CAM_A", "a", (0.0,), ((1, 1),)), ("CAM_B", "b", (0.1,), ((7, 1),)))
    bundle = build_inference(perception, scope=scope(), context=context())
    assert len(bundle.snapshot.gaps) == 1
    gap = bundle.snapshot.gaps[0]
    assert gap.search_result.complete
    assert gap.event.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    assert gap.event.candidates == () and gap.event.trajectories == ()
    pair = next(item for item in bundle.association_hypotheses if item.kind != "UNMATCHED")
    assert pair.status == "INCOMPATIBLE" and pair.event_id == gap.event.event_id


def test_static_calibration_cannot_mix_planes_or_singular_mapping() -> None:
    plane = context().ground_plane
    with pytest.raises(ValidationError, match="nonsingular"):
        GroundCalibration(camera_id="a", plane=plane, affine_ground_to_pixel=((1, 1, 0), (2, 2, 0)))
    with pytest.raises(ValidationError, match="exact ground plane"):
        SyntheticStaticContext.model_validate(
            context().model_dump()
            | {
                "calibrations": [
                    context().calibrations[0].model_dump()
                    | {
                        "plane": plane.model_dump() | {"plane_id": "other-plane"},
                    }
                ],
                "allowed_camera_pairs": [],
            }
        )


def test_gt_sidecar_pollution_cannot_change_real_pixel_inference(tmp_path: Path) -> None:
    package = generate_sequence(tmp_path / "rgb", model_id="lab", run_id="test-run")
    plane = context().ground_plane
    static = context().model_copy(
        update={
            "source_sha256": package.source_sha256,
            "context_sha256": package.context_sha256,
            "walkable_bounds_xy_m": (0, 0, 12, 4),
            "calibrations": tuple(
                GroundCalibration(
                    camera_id=camera.camera_id,
                    plane=plane,
                    affine_ground_to_pixel=camera.ground_to_pixel,
                )
                for camera in package.cameras
            ),
        }
    )
    bound_scope = scope().model_copy(
        update={
            "source_sha256": package.source_sha256,
            "context_sha256": package.context_sha256,
        }
    )
    first_pixels = produce_perception(package.frames, model_id="lab", run_id="test-run")
    first = build_inference(first_pixels, scope=bound_scope, context=static)
    package.simulation_export_path.write_text(
        '{"gt_actor_identity":"SECRET_TRUE_ACTOR","position":[987,654,321],'
        '"recipe":"HIDDEN_REFERENCE_PATH"}',
        encoding="utf-8",
    )
    second_pixels = produce_perception(package.frames, model_id="lab", run_id="test-run")
    second = build_inference(second_pixels, scope=bound_scope, context=static)
    assert first == second
    assert content_sha256(first) == content_sha256(second)
    serialized = second.model_dump_json()
    assert "SECRET_TRUE_ACTOR" not in serialized and "HIDDEN_REFERENCE_PATH" not in serialized
    assert str(tmp_path) not in serialized
    assert any(
        item.kind == "SAME_CAMERA_RECOVERY" and item.status == "HOLD"
        for item in second.association_hypotheses
    )
    assert any(item.kind == "OVERLAPPING_VISIBILITY" for item in second.association_hypotheses)


def test_empty_pixels_remain_empty_not_a_successful_detection() -> None:
    bundle = build_inference(result(), scope=scope(), context=context())
    assert bundle.snapshot.observations == () and bundle.snapshot.gaps == ()
    assert bundle.association_hypotheses == () and bundle.projected_measurements == ()
    assert bundle.pair_count == 0


def test_persisted_bundle_cannot_drop_alternatives_or_relabel_canonical_status() -> None:
    bundle = build_inference(ambiguous_result(), scope=scope(), context=context())
    payload = bundle.model_dump(mode="python")
    with pytest.raises(ValidationError, match="retrieved pairs and unmatched"):
        InferenceBundle.model_validate(
            payload
            | {
                "association_hypotheses": bundle.association_hypotheses[1:],
            }
        )
    first = next(item for item in bundle.association_hypotheses if item.event_id is not None)
    changed = tuple(
        item.model_copy(update={"candidate_count": 999}) if item == first else item
        for item in bundle.association_hypotheses
    )
    with pytest.raises(ValidationError, match="canonical graph status"):
        InferenceBundle.model_validate(payload | {"association_hypotheses": changed})


def test_undeclared_gt_field_in_unchecked_pixel_model_is_rejected() -> None:
    perception = ambiguous_result()
    contaminated = perception.model_copy(
        update={
            "measurements": (
                perception.measurements[0].model_copy(
                    update={
                        "gt_actor_identity": "HIDDEN_ACTOR",
                        "gt_world_position": (99, 88, 77),
                    }
                ),
                *perception.measurements[1:],
            ),
        }
    )
    with pytest.raises(ValueError, match="undeclared or truth fields"):
        build_inference(contaminated, scope=scope(), context=context())


def test_late_window_omission_is_scope_limit_and_large_rgb_distance_is_soft() -> None:
    perception = result(
        ("CAM_A", "a", (0.0, 0.2), ((1, 1), (1.2, 1))),
        ("CAM_B", "b", (2.0, 2.2), ((3, 1), (3.2, 1))),
        ("CAM_B", "late", (20.0, 20.2), ((3, 1), (3.2, 1))),
    )
    changed = perception.model_copy(
        update={
            "measurements": tuple(
                item.model_copy(update={"appearance": (255, 255, 255)})
                if item.camera_id == "CAM_B"
                else item
                for item in perception.measurements
            )
        }
    )
    bundle = build_inference(changed, scope=scope(), context=context())
    pairs = [item for item in bundle.association_hypotheses if item.kind != "UNMATCHED"]
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.appearance_distance is not None and pair.appearance_distance > 110
    assert pair.status == "PROVISIONAL"
    assert pair.event_id is not None
    assert not any("WINDOW" in item.reason for item in pairs)
    assert all(
        receipt.retrieval_coverage == "SCOPED_FINITE_WINDOW"
        for receipt in bundle.retrieval_receipts
    )
    assert all(
        not receipt.excluded_outside_window_are_physical_rejections
        for receipt in bundle.retrieval_receipts
    )


def test_missing_source_clock_and_cross_scope_topology_never_fallback() -> None:
    from amidst.engineering.local_association import resource_scope
    from amidst.engineering.local_index import CameraLink, CameraRegions, ScopedTopology

    inferred_scope = resource_scope(scope())
    topo = ScopedTopology(
        scope=inferred_scope,
        camera_ids=("CAM_A", "CAM_B"),
        camera_links=(CameraLink(from_camera_id="CAM_A", to_camera_id="CAM_B"),),
        camera_regions=(CameraRegions(camera_id="CAM_A"), CameraRegions(camera_id="CAM_B")),
        clock_mapping_sha256=None,
        topology_complete=True,
    )
    bundle = build_inference(ambiguous_result(), scope=scope(), context=context(), topology=topo)
    assert bundle.pair_count == 0 and not bundle.association_enumeration_complete
    assert all(item.kind == "UNMATCHED" for item in bundle.association_hypotheses)
    assert all(
        receipt.truncation_reasons == ("CLOCK_MAPPING_MISSING",)
        for receipt in bundle.retrieval_receipts
    )
    with pytest.raises(ValueError, match="exact inference scope"):
        build_inference(
            ambiguous_result(),
            scope=scope(),
            context=context(),
            topology=topo.model_copy(
                update={
                    "scope": inferred_scope.model_copy(update={"clock_id": "other"}),
                }
            ),
        )


def test_minimum_legal_travel_bound_is_distinct_from_nearby_camera_coordinates() -> None:
    from amidst.engineering.local_association import resource_scope
    from amidst.engineering.local_index import CameraLink, CameraRegions, ScopedTopology

    topo = ScopedTopology(
        scope=resource_scope(scope()),
        camera_ids=("CAM_A", "CAM_B"),
        camera_links=(
            CameraLink(from_camera_id="CAM_A", to_camera_id="CAM_B", minimum_path_length_m=20),
        ),
        camera_regions=(CameraRegions(camera_id="CAM_A"), CameraRegions(camera_id="CAM_B")),
        clock_mapping_sha256="c" * 64,
        topology_complete=True,
    )
    bundle = build_inference(ambiguous_result(), scope=scope(), context=context(), topology=topo)
    cross = [item for item in bundle.association_hypotheses if item.kind == "CROSS_CAMERA_GAP"]
    assert len(cross) == 2
    assert all(
        item.status == "INCOMPATIBLE" and item.reason == "SOURCE_BOUND_MINIMUM_TRAVEL_TIME_EXCEEDED"
        for item in cross
    )
    assert not bundle.snapshot.gaps


def test_fixed_pool_ablations_preserve_all_graph_candidates_and_multiple_links() -> None:
    from amidst.engineering.local_association import (
        candidate_segment_pairs,
        rank_association_hypotheses,
    )

    bundle = build_inference(ambiguous_result(), scope=scope(), context=context())
    frozen = bundle.model_dump_json()
    pool = candidate_segment_pairs(bundle)
    assert content_sha256(pool) == bundle.association_pool_sha256
    full = rank_association_hypotheses(bundle)
    assert len(full) == 2  # both physically feasible cross-camera alternatives survive.
    for omitted in ("SPACE", "TIME", "APPEARANCE"):
        ablated = rank_association_hypotheses(bundle, removed_feature=omitted)
        assert {item.hypothesis_id for item in ablated} == {item.hypothesis_id for item in full}
    assert bundle.model_dump_json() == frozen


def test_projected_pixel_motion_changes_soft_time_rank_without_rejecting_turns() -> None:
    from amidst.engineering.local_association import rank_association_hypotheses

    perception = result(
        ("CAM_A", "a", (0.0, 0.2), ((1, 1), (1.2, 1))),
        ("CAM_B", "same", (2.0, 2.2), ((3, 1), (3.2, 1))),
        ("CAM_B", "reverse", (2.0, 2.2), ((3, 1), (2.8, 1))),
    )
    bundle = build_inference(perception, scope=scope(), context=context())
    cross = [
        item for item in rank_association_hypotheses(bundle) if item.kind == "CROSS_CAMERA_GAP"
    ]
    assert len(cross) == 2 and all(item.status == "PROVISIONAL" for item in cross)
    first, last = cross[0].feature_scores, cross[1].feature_scores
    assert first is not None and last is not None
    assert first.motion_alignment == pytest.approx(1)
    assert last.motion_alignment == pytest.approx(-1)
    assert first.departure_speed_m_s == pytest.approx(1)
    assert first.time_continuity > last.time_continuity
