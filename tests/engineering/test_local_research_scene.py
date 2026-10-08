"""Reproducible perspective pixels, separate recipes and post-freeze evaluation."""

import json
from pathlib import Path

import pytest

from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.engineering.access import FreezeReceipt, RunBinding, digest
from amidst.engineering.local_association import InferenceBundle, build_inference
from amidst.engineering.local_behavior import BehaviorConfig, compose_local_behaviors
from amidst.engineering.local_evaluation import evaluate_local_pilot, evaluator_policy
from amidst.engineering.local_index import RetrievalPolicy
from amidst.engineering.perception import PerceptionResult, produce_perception
from amidst.engineering.research_scene import (
    DEFAULT_CONFIG,
    ResearchPackage,
    generate_research_sequence,
    project_world,
)
from amidst.geometry.inverse_projection import InverseProjectionService


@pytest.fixture(scope="module")
def package(tmp_path_factory: pytest.TempPathFactory) -> ResearchPackage:
    return generate_research_sequence(tmp_path_factory.mktemp("local-research"))


@pytest.fixture(scope="module")
def perception(package: ResearchPackage) -> PerceptionResult:
    return produce_perception(package.frames, model_id=package.model_id, run_id=package.run_id)


@pytest.fixture(scope="module")
def inference(package: ResearchPackage, perception: PerceptionResult) -> InferenceBundle:
    return build_inference(perception, scope=package.scope, context=package.context)


@pytest.fixture(scope="module")
def receipt(package: ResearchPackage, perception: PerceptionResult,
            inference: InferenceBundle) -> FreezeReceipt:
    binding = RunBinding(
        place_id=package.scope.place_id, model_id=package.model_id,
        model_revision=package.revision, source_ref=package.scope.source_ref,
        spatial_context_id=package.scope.spatial_context_id, run_id=package.run_id,
        clock_id=package.scope.clock_id, observation_mode="photos_only",
        dataset_sha256=package.dataset_sha256, config_sha256=package.config_sha256,
        producer_sha256=perception.producer_sha256, registry_sha256="a" * 64,
        media_sha256="b" * 64,
    )
    return FreezeReceipt.create(binding, inference, perception.model_dump(mode="json"))


def test_pinhole_roundtrip_and_depth_scale(package: ResearchPackage) -> None:
    calibration = package.context.calibrations[0]
    camera = package.cameras[0]
    assert calibration.pinhole == camera
    assert calibration.affine_ground_to_pixel is None
    contact = project_world(camera, (2.0, 2.0, 0.0))
    assert contact is not None
    frame = ObservationFrame(frame_id=1, camera_id=camera.camera_id,
                             target_id="test-local", timestamp=1.0,
                             status=VisibilityStatus.OBSERVED, point_2d=contact[:2],
                             provenance=Provenance.OBSERVED)
    projected = InverseProjectionService(camera, calibration.plane).project_frame(frame)
    assert projected.world_position == pytest.approx((2.0, 2.0, 0.0), abs=1e-9)
    near = project_world(camera, (2.0, 1.0, 1.7))
    near_floor = project_world(camera, (2.0, 1.0, 0.0))
    far = project_world(camera, (2.0, 3.0, 1.7))
    far_floor = project_world(camera, (2.0, 3.0, 0.0))
    assert near and near_floor and far and far_floor
    assert abs(near[1] - near_floor[1]) > abs(far[1] - far_floor[1])


def test_pixels_deterministic_with_no_generator_truth_fields(package: ResearchPackage) -> None:
    repeated = generate_research_sequence(package.frames[0].path.parents[2])
    assert repeated.dataset_sha256 == package.dataset_sha256
    assert [frame.sha256 for frame in repeated.frames] == [frame.sha256 for frame in package.frames]
    assert len(package.frames) == 244
    assert len(package.cameras) == 4
    assert not any("ISLAND" in pair for pair in package.adjacency)
    assert "actor_identity" not in package.model_dump_json()
    assert '"waypoints"' not in package.model_dump_json()
    assert package.simulation_export_path.parent.name == "export"
    assert package.evidence_level == "E1_CONFIGURED_PINHOLE_RGB"


def test_whole_trajectory_split_is_disjoint(tmp_path: Path, package: ResearchPackage) -> None:
    development = generate_research_sequence(tmp_path / "development", split="development")
    test_truth = json.loads(package.simulation_export_path.read_text())
    development_truth = json.loads(development.simulation_export_path.read_text())
    first = {actor["actor_identity"] for actor in test_truth["recipe"]["actors"]}
    second = {actor["actor_identity"] for actor in development_truth["recipe"]["actors"]}
    assert first.isdisjoint(second)
    assert development.config_sha256 == package.config_sha256
    assert development.context_sha256 == package.context_sha256
    assert development.dataset_sha256 != package.dataset_sha256
    config = json.loads(DEFAULT_CONFIG.read_text())
    assert config["split_unit"] == "WHOLE_TRAJECTORY"
    assert config["policy_frozen_before_test"]
    assert not config["appearance_generalization_claim"]


def test_different_feasible_blind_middle_has_identical_rgb_and_inference(
    tmp_path: Path, package: ResearchPackage, inference: InferenceBundle,
) -> None:
    config = json.loads(DEFAULT_CONFIG.read_text())
    actor = next(row for row in config["splits"]["test"]["actors"]
                 if row["scenario"] == "long_blind_alternative_endpoints")
    original = actor["waypoints"]
    actor["waypoints"] = [original[0], original[1], [2.8, 8.3, 0.8],
                          [4.8, 8.3, 3.4], *original[3:]]
    # Every alternative ground point before the return is in the explicit blind
    # strip x=(8.0,8.7); both detour legs remain below the fixed 3m/s hard limit.
    for first, last in zip(actor["waypoints"], actor["waypoints"][1:], strict=False):
        speed = ((last[1] - first[1]) ** 2 + (last[2] - first[2]) ** 2) ** 0.5 / (
            last[0] - first[0])
        assert speed <= 3.0
    alternative_config = tmp_path / "blind-detour.json"
    alternative_config.write_text(json.dumps(config))
    alternate = generate_research_sequence(tmp_path / "blind-detour", run_id=package.run_id,
                                            config_path=alternative_config)
    assert alternate.dataset_sha256 == package.dataset_sha256
    assert alternate.context == package.context
    measured = produce_perception(alternate.frames, model_id=alternate.model_id,
                                  run_id=alternate.run_id)
    inferred = build_inference(measured, scope=alternate.scope, context=alternate.context)
    assert digest(inferred) == digest(inference)
    assert alternate.simulation_export_path.read_bytes() != (
        package.simulation_export_path.read_bytes())


def test_gt_and_recipe_poisoning_never_changes_pixels_or_inference(
    package: ResearchPackage, perception: PerceptionResult, inference: InferenceBundle,
) -> None:
    before = package.simulation_export_path.read_bytes()
    try:
        package.simulation_export_path.write_text('{"recipe":"poisoned","GT":"removed"}')
        fresh = produce_perception(package.frames, model_id=package.model_id, run_id=package.run_id)
        recomputed = build_inference(fresh, scope=package.scope, context=package.context)
        assert digest(fresh) == digest(perception)
        assert digest(recomputed) == digest(inference)
    finally:
        package.simulation_export_path.write_bytes(before)


def test_evaluator_rejects_bad_freeze_before_attempting_to_read_truth(
    package: ResearchPackage, perception: PerceptionResult, inference: InferenceBundle,
    receipt: FreezeReceipt,
) -> None:
    missing = package.model_copy(update={"simulation_export_path": Path("/does-not-exist/GT")})
    forged = receipt.model_copy(update={"inference_sha256": "f" * 64})
    with pytest.raises(ValueError, match="freeze/package"):
        evaluate_local_pilot(missing, perception, inference, receipt=forged)


def test_evaluator_rejects_wrong_run_even_with_valid_receipt(
    package: ResearchPackage, perception: PerceptionResult, inference: InferenceBundle,
    receipt: FreezeReceipt,
) -> None:
    wrong_run = package.model_copy(update={"run_id": "other-run"})
    with pytest.raises(ValueError, match="freeze/package"):
        evaluate_local_pilot(wrong_run, perception, inference, receipt=receipt)


@pytest.mark.parametrize("corruption", ("wrong_run", "wrong_track", "wrong_segment", "wrong_frame"))
def test_same_hash_wrong_behavior_lineage_is_rejected_before_truth_read(
    package: ResearchPackage, perception: PerceptionResult, inference: InferenceBundle,
    receipt: FreezeReceipt, corruption: str,
) -> None:
    config = BehaviorConfig(scope=package.scope, config_version="fixed-test-v1",
                            regions=package.context.regions)
    behaviors = compose_local_behaviors(inference, config, tracks=perception.tracks)
    assert behaviors.events
    event = behaviors.events[0]
    if corruption == "wrong_run":
        event = event.model_copy(update={"scope": event.scope.model_copy(
            update={"run_id": "wrong-development-run"})})
    elif corruption == "wrong_track":
        event = event.model_copy(update={"local_track_ids": ("other-track",)})
    elif corruption == "wrong_segment":
        event = event.model_copy(update={"segment_ids": ("other-segment",)})
    else:
        frame = event.source_frames[0].model_copy(update={"frame_ref": "other-frame"})
        event = event.model_copy(update={"source_frames": (frame, *event.source_frames[1:])})
    fake_hash = digest([event.model_dump(mode="json")])
    missing = package.model_copy(update={"simulation_export_path": Path("/nonexistent-truth")})
    with pytest.raises(ValueError, match="behavior"):
        evaluate_local_pilot(missing, perception, inference, receipt=receipt,
                             events=(event,), events_sha256=fake_hash)


def test_same_run_behavior_bundle_and_evaluator_policy_are_bound(
    package: ResearchPackage, perception: PerceptionResult, inference: InferenceBundle,
    receipt: FreezeReceipt,
) -> None:
    config = BehaviorConfig(scope=package.scope, config_version="fixed-test-v1",
                            regions=package.context.regions)
    behaviors = compose_local_behaviors(inference, config, tracks=perception.tracks)
    events_hash = digest([event.model_dump(mode="json") for event in behaviors.events])
    summary = evaluate_local_pilot(package, perception, inference, receipt=receipt,
                                   events=behaviors.events, events_sha256=events_hash,
                                   behavior_bundle=behaviors)
    assert summary["behavior_bundle_binding_verified"] is True
    assert summary["evaluator_policy"] == evaluator_policy()
    assert summary["evaluator_policy_sha256"] == digest(evaluator_policy())
    assert len(summary["evaluator_sha256"]) == 64  # type: ignore[arg-type]
    behavior = summary["behavior"]
    assert isinstance(behavior, dict)
    gaps = behavior["groups"]["inferred_gap"]
    assert gaps["hypothesis_event_count"] == sum(
        event.evidence_state == "INFERRED_GAP" for event in behaviors.events)
    assert gaps["hypothesis_event_count"] > 0
    assert gaps["canonical_candidate_count"] == sum(
        len(event.candidates) for event in behaviors.events
        if event.evidence_state == "INFERRED_GAP")
    assert all(row["precision"] == "N/A" and row["recall"] == "N/A"
               and row["false_negative"] == "N/A" for row in gaps["per_kind"].values())


def test_duplicate_truth_frame_is_rejected_after_freeze(
    package: ResearchPackage, perception: PerceptionResult, inference: InferenceBundle,
    receipt: FreezeReceipt,
) -> None:
    before = package.simulation_export_path.read_bytes()
    truth = json.loads(before)
    truth["ground_truth"].append(truth["ground_truth"][0])
    try:
        package.simulation_export_path.write_text(json.dumps(truth))
        with pytest.raises(ValueError, match="truth binding/inventory"):
            evaluate_local_pilot(package, perception, inference, receipt=receipt)
    finally:
        package.simulation_export_path.write_bytes(before)


def test_independent_inventory_and_fixed_pool_ablations_are_measured(
    package: ResearchPackage, perception: PerceptionResult, inference: InferenceBundle,
    receipt: FreezeReceipt,
) -> None:
    result = evaluate_local_pilot(package, perception, inference, receipt=receipt)
    retrieval = result["retrieval"]
    assert isinstance(retrieval, dict)
    assert retrieval["complete_scope_pair_coverage"] == 1.0
    assert retrieval["same_identity_eligible_pair_miss_count"] == 0
    assert retrieval["true_next_successor_miss_count"] == 0
    assert retrieval["retrieved_pair_count"] < (
        retrieval["full_global_pair_count_for_comparison_only"])
    ablations = result["fixed_pool_feature_ablations"]
    assert isinstance(ablations, dict)
    assert len(ablations) == 4
    assert {row["candidate_pool_sha256"] for row in ablations.values()} == {
        inference.association_pool_sha256}
    assert all(row["hard_physics_preserved"] for row in ablations.values())
    assert result["formal_phase1_acceptance"] is False
    assert result["behavior"] == {"status": "N/A", "reason":
                                  "Behavior event freeze hash is unavailable"}
    geometry = result["geometry"]
    assert isinstance(geometry, dict)
    assert geometry["hard_speed_violation_count"] == 0
    assert geometry["outside_configured_region_count"] == 0


def test_runtime_window_does_not_shrink_independent_successor_reference(
    package: ResearchPackage, perception: PerceptionResult, receipt: FreezeReceipt,
) -> None:
    restricted = build_inference(perception, scope=package.scope, context=package.context,
                                 retrieval_policy=RetrievalPolicy(window_steps_s=(0.4,)))
    frozen = FreezeReceipt.create(receipt.binding, restricted, perception.model_dump(mode="json"))
    evaluated = evaluate_local_pilot(package, perception, restricted, receipt=frozen)
    retrieval = evaluated["retrieval"]
    assert isinstance(retrieval, dict)
    assert retrieval["reference_retrieval_window_s"] == 12.0
    assert retrieval["true_next_successor_pair_count"] > 0
    assert retrieval["true_next_successor_miss_count"] > 0
    assert retrieval["true_next_successor_retrieval_recall"] < 1.0
    assert retrieval["complete_scope_pair_coverage"] < 1.0
    assert retrieval["true_next_reference_has_window_hop_or_record_budget"] is False


def test_missing_rgb_is_explicit_and_never_filled_from_truth(
    package: ResearchPackage,
) -> None:
    missing_frame = package.frames[0].model_copy(update={"path": Path("/missing-rgb/frame.png")})
    limited = produce_perception((missing_frame, *package.frames[1:]),
                                 model_id=package.model_id, run_id=package.run_id)
    status = next(row for row in limited.frame_statuses if row.frame_ref == missing_frame.media_ref)
    assert status.status == "MISSING_IMAGE"
    assert not limited.complete
    assert not any(row.frame_ref == missing_frame.media_ref for row in limited.measurements)


def test_conflicting_materialization_never_overwrites_existing_rgb(
    package: ResearchPackage,
) -> None:
    first = package.frames[0].path
    before = first.read_bytes()
    try:
        first.write_bytes(b"pre-existing-independent-data")
        with pytest.raises(ValueError, match="existing research input differs"):
            generate_research_sequence(first.parents[2])
        assert first.read_bytes() == b"pre-existing-independent-data"
    finally:
        first.write_bytes(before)
