"""Synthetic contract tests for reviewed wrappers; no school approval is invented."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_local_semantic_review import HUMAN, _proof_inputs, _reviewed_proof
from test_pilot_topology import context_fixture

from amidst.benchmark.baselines import run_baseline
from amidst.datasets.pilot import PilotInferenceContext
from amidst.domain.common import Provenance
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evaluation import ConstraintConfig
from amidst.domain.evidence import GapReason, VisibilityStatus
from amidst.domain.navigation import (
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
)
from amidst.domain.observation import ProjectedPoint
from amidst.domain.pipeline import InferenceInput, PipelineConfig
from amidst.domain.reconstruction import ReconstructionPolicy
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.stream import ObservationAggregation, OcclusionState, RawProjectedFrameSample
from amidst.domain.topology import (
    CameraTopologyConfig,
    CameraTopologyNode,
    CameraTransition,
    CameraTransitionType,
)
from amidst.finalization.reviewed_authority import (
    NO_PLANE,
    ReviewedAuthority,
    ReviewedInferenceContext,
    build_reviewed_context,
    convert_landmark_dataset,
    load_reviewed_authority,
    review_content_sha256,
    reviewed_metric_config,
    reviewed_physical_metrics,
    run_reviewed_baseline,
    validate_reviewed_endpoints,
)
from amidst.finalization.reviewed_evaluation import evaluate_reviewed_trajectories
from amidst.local_semantic_review import ReviewedRestrictedLocalPhysicalProvider
from amidst.observation.aggregation import aggregate_frames
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import GeometryAuthorityError

ROOT = Path(__file__).resolve().parents[2]
CONFIG = "1" * 64


@pytest.fixture(scope="module")
def authority() -> ReviewedAuthority:
    receipt, evidence, domain, contract = _proof_inputs()
    certificate, detail = _reviewed_proof(receipt, evidence, domain, contract)
    assert certificate is not None, detail
    certificate_sha = content_sha256(certificate.model_dump(mode="json"))
    provider = ReviewedRestrictedLocalPhysicalProvider(
        certificate, domain, contract, certificate_sha, HUMAN,
    )
    payload = context_fixture().model_dump()
    payload["source_asset_sha256"] = domain.source_sha256
    payload["zone"]["bounds_min"] = (0, 0, 0)
    payload["zone"]["bounds_max"] = (10, 10, 100)
    historical = PilotInferenceContext.model_validate(payload)
    lock = {
        "human_decisions_sha256": HUMAN, "source_sha256": domain.source_sha256,
        "projection_binding": {"conversion": "SUBTRACT_SOURCE_BOUND_Z_OFFSET_KEEP_XY"},
        "coverage": {"distance_metric": "ADE", "comparison": "STRICTLY_LESS_THAN",
                     "epsilon_m": 0.5},
        "timing": {"max_speed_m_s": .7904, "direct_path_slack_tolerance_s": 1.0,
                   "include_dwell_hypotheses": True},
        "automatic_settings": {"k_values": [1, 2, 3], "sampling_hz": 5,
                               "sampling_extent": "SOURCE_ENDPOINTS_INCLUSIVE_NO_REJECTION"},
    }
    return ReviewedAuthority(
        source_sha256=domain.source_sha256, human_decisions_sha256=HUMAN,
        review_payload_sha256="c" * 64, application_manifest_sha256="d" * 64,
        certificate_content_sha256=certificate_sha,
        semantic_review_content_sha256=certificate.semantic_review_content_sha256,
        approved_input_lock=lock, approved_input_lock_content_sha256=review_content_sha256(lock),
        historical_context=historical, floor_support_z_bu=0,
        projection_authority_content_sha256=content_sha256({
            "historical_context": historical.model_dump(mode="json"),
            "floor_support_z_bu": 0,
        }), provider=provider,
    )


def _context(authority: ReviewedAuthority) -> ReviewedInferenceContext:
    payload = authority.historical_context.model_dump()
    payload.update(source_id="fresh-source", spatial_context_id="fresh-context",
                   observations_sha256="9" * 64)
    return build_reviewed_context(
        authority, PilotInferenceContext.model_validate(payload),
        observations_sha256="9" * 64, fresh_export_config_sha256=CONFIG,
    )


def _dataset(
    context: ReviewedInferenceContext, *, no_plane: bool = False, outside: bool = False,
) -> tuple[FrameSampleDataset, dict[str, Any]]:
    rows, samples = [], []
    for camera, timestamp, coordinates in (
        ("CAM_FRONT", 0., (1.9 if outside else 3., 5., 75.)),
        ("CAM_FRONT", 5., None),
        ("CAM_REAR", 10., (7., 5., 75.)),
    ):
        plane_id = NO_PLANE if no_plane else context.computation_context.plane.plane_id
        point = None if coordinates is None else ProjectedPoint(
            point_id=f"point:{timestamp}", camera_id=camera, timestamp=timestamp,
            world_position=coordinates, plane_id=plane_id, projection_quality=.125,
            floor_id="1F", zone_id="AREA_1F_OFFICE",
        )
        samples.append(RawProjectedFrameSample(
            sample_id=f"sample:{timestamp}", **context.binding.model_dump(), target_id="marker",
            camera_id=camera, timestamp=timestamp, frame_id=int(timestamp * 5), uv=None,
            visibility=VisibilityStatus.GAP if point is None else VisibilityStatus.OBSERVED,
            occlusion_state=OcclusionState.OCCLUDED if point is None else OcclusionState.CLEAR,
            provenance=None if point is None else Provenance.PROJECTED,
            gap_reason=GapReason.OCCLUDED if point is None else None, projected_point=point,
        ))
        rows.append({
            "timestamp": timestamp, "frame_id": int(timestamp * 5), "target_id": "marker",
            "method": "EXACT_TIME_MULTIVIEW" if no_plane else "SINGLE_VIEW_FIXED_PLANE",
            "selected_camera_ids": [camera], "ground_truth_read": False,
            "selection_uses_ground_truth": False,
        })
    sidecar = {
        "ground_truth_read": False,
        "source_asset_sha256": context.binding.source_asset_sha256,
        "observations_sha256": context.computation_context.observations_sha256,
        "retained_evidence_count": len(samples), "rows": rows,
    }
    return FrameSampleDataset(samples=tuple(samples)), sidecar


def _inference(
    authority: ReviewedAuthority, context: ReviewedInferenceContext,
) -> tuple[InferenceInput, ObservationAggregation, dict[str, Any]]:
    dataset, sidecar = _dataset(context)
    converted = convert_landmark_dataset(dataset, context, authority, projection_sidecar=sidecar)
    aggregation = aggregate_frames(converted.samples)
    start, end = validate_reviewed_endpoints(aggregation, context, authority)
    a, b = start.projected_path[-1].world_position, end.projected_path[0].world_position
    navigation = NavigationGraphConfig(
        graph_id="synthetic-reviewed-test", spatial_context_id=context.binding.spatial_context_id,
        data_kind=NavigationDataKind.CONFIGURED, source_asset_sha256=authority.source_sha256,
        nodes=(NavigationNode(node_id="a", position=a, floor_id="1F", zone_id="AREA_1F_OFFICE"),
               NavigationNode(node_id="b", position=b, floor_id="1F", zone_id="AREA_1F_OFFICE")),
        edges=(NavigationEdge(edge_id="direct", from_node_id="a", to_node_id="b",
                              polyline=(a, b)),),
    )
    topology = CameraTopologyConfig(
        topology_id="synthetic-reviewed-test", navigation_graph_id=navigation.graph_id,
        spatial_context_id=context.binding.spatial_context_id,
        data_kind=NavigationDataKind.CONFIGURED, source_asset_sha256=authority.source_sha256,
        nodes=tuple(CameraTopologyNode(camera_id=c.camera_id, floor_id="1F", zone_id=c.zone_id)
                    for c in context.computation_context.cameras),
        transitions=(CameraTransition(
            transition_id="synthetic-reviewed-handoff", from_camera_id="CAM_FRONT",
            to_camera_id="CAM_REAR", transition_type=CameraTransitionType.ADJACENT,
            navigation_from_node_id="a", navigation_to_node_id="b",
            navigation_edge_ids=("direct",),
        ),),
    )
    inputs = InferenceInput(
        dataset_id="synthetic-reviewed-tests", random_seed=42, start_observation=start,
        end_observation=end, navigation=navigation, topology=topology,
        movement=MovementConstraints(max_speed_m_s=.7904),
        search_policy=GraphSearchPolicy(max_candidate_paths=3),
        reconstruction_policy=ReconstructionPolicy(),
    )
    readiness = {
        "schema_version": "phase1-reviewed-case-readiness-v1", "case_id": "case1",
        "case_execution_ready": True, "physical_certificate_pass": True,
        "ground_truth_used": False, "case_config_content_sha256": CONFIG,
        "source_sha256": authority.source_sha256,
        "reviewed_certificate_content_sha256": authority.certificate_content_sha256,
        "semantic_review_content_sha256": authority.semantic_review_content_sha256,
        "human_decisions_sha256": authority.human_decisions_sha256,
        "endpoint_observation_content_sha256": content_sha256({
            "start": start.model_dump(mode="json"), "end": end.model_dump(mode="json"),
        }), "unique_major_source_route": True,
        "graph_content_sha256": content_sha256(PipelineConfig(
            navigation=inputs.navigation, topology=inputs.topology, movement=inputs.movement,
            search_policy=inputs.search_policy, reconstruction_policy=inputs.reconstruction_policy,
        ).model_dump(mode="json")),
        "aggregation_policy": aggregation.policy.model_dump(mode="json"),
        "aggregation_policy_content_sha256": content_sha256(
            aggregation.policy.model_dump(mode="json"),
        ),
    }
    return inputs, aggregation, readiness


def _run(
    authority: ReviewedAuthority, method: str = "spatiotemporal", *,
    readiness_change: dict[str, Any] | None = None, ablation: str | None = None,
) -> Any:
    context = _context(authority)
    inputs, aggregation, readiness = _inference(authority, context)
    readiness.update(readiness_change or {})
    return run_reviewed_baseline(
        inputs, method, authority=authority, context=context, frozen_config_sha256=CONFIG,
        case_readiness_sha256=content_sha256(readiness), case_readiness=readiness,
        aggregation=aggregation, ablation_id=ablation, clock=lambda: 0,
    )


def test_rigid_offset_preserves_exact_method_quality_identity_and_gap(
    authority: ReviewedAuthority,
) -> None:
    context = _context(authority)
    assert context.offset_bu == 75
    for no_plane in (False, True):
        dataset, sidecar = _dataset(context, no_plane=no_plane)
        converted = convert_landmark_dataset(
            dataset, context, authority, projection_sidecar=sidecar,
        )
        assert len(converted.samples) == len(dataset.samples)
        for original, foot in zip(dataset.samples, converted.samples, strict=True):
            assert original.sample_id == foot.sample_id
            assert original.uv == foot.uv
            assert original.timestamp == foot.timestamp
            if original.projected_point is None:
                assert original == foot
            else:
                point = foot.projected_point
                assert point is not None
                assert point.world_position == (*original.projected_point.world_position[:2], 0)
                assert point.plane_id == original.projected_point.plane_id
                assert point.projection_quality == .125
        assert validate_reviewed_endpoints(aggregate_frames(converted.samples), context, authority)


def test_outside_points_are_retained_then_refused_by_physical_authority(
    authority: ReviewedAuthority,
) -> None:
    context = _context(authority)
    dataset, sidecar = _dataset(context, outside=True)
    converted = convert_landmark_dataset(dataset, context, authority, projection_sidecar=sidecar)
    assert converted.samples[0].projected_point is not None
    assert converted.samples[0].projected_point.world_position[0] == 1.9
    with pytest.raises(GeometryAuthorityError, match="OUTSIDE_APPROVED_LOCAL"):
        validate_reviewed_endpoints(aggregate_frames(converted.samples), context, authority)


@pytest.mark.parametrize("change", [
    {"source_id": "pilot-source"}, {"spatial_context_id": "PILOT:configured-envelope-fixture"},
    {"observations_sha256": "b" * 64}, {"source_asset_sha256": "1" * 64},
])
def test_historical_stream_or_other_source_cannot_get_reviewed_context(
    authority: ReviewedAuthority, change: dict[str, Any],
) -> None:
    context = _context(authority)
    native = context.computation_context.model_copy(update=change)
    with pytest.raises(ValueError, match="fresh evidence|digest differs"):
        build_reviewed_context(
            authority, native, observations_sha256=native.observations_sha256,
            fresh_export_config_sha256=CONFIG,
        )


def test_tampered_lock_and_receipt_wrapper_are_refused(authority: ReviewedAuthority) -> None:
    lock = deepcopy(authority.approved_input_lock)
    lock["coverage"]["epsilon_m"] = 2
    with pytest.raises(ValueError, match="lock changed"):
        reviewed_metric_config(replace(authority, approved_input_lock=lock))
    with pytest.raises(ValueError, match="certificate/human decisions hash mismatch"):
        _run(replace(authority, human_decisions_sha256="a" * 64))
    with pytest.raises(ValueError, match="calibration/support binding changed"):
        _context(replace(authority, floor_support_z_bu=.001))


@pytest.mark.parametrize("change", [
    {"case_execution_ready": False}, {"physical_certificate_pass": False},
    {"ground_truth_used": True}, {"unique_major_source_route": False},
    {"case_id": "case2", "source_distinct_routes": 1},
    {"case_id": "case3", "long_gap": False}, {"source_sha256": "b" * 64},
    {"endpoint_observation_content_sha256": "b" * 64},
    {"aggregation_policy": {"max_visible_sample_gap_s": .200001}},
    {"aggregation_policy_content_sha256": "b" * 64},
])
def test_readiness_hash_alone_cannot_authorize_missing_case_proofs(
    authority: ReviewedAuthority, change: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="per-case readiness"):
        _run(authority, readiness_change=change)


@pytest.mark.parametrize("method", ["shortest_path", "geometry", "spatiotemporal"])
def test_reviewed_baselines_preserve_existing_search_timing_and_factor_masks(
    authority: ReviewedAuthority, method: str,
) -> None:
    context = _context(authority)
    inputs, _, _ = _inference(authority, context)
    before = inputs.model_dump_json()
    core = run_baseline(inputs, method, clock=lambda: 0)
    reviewed = _run(authority, method)
    assert inputs.model_dump_json() == before
    assert reviewed.geometric_result == core.geometric_result
    assert reviewed.timed_result == core.timed_result
    assert reviewed.event == core.event
    assert reviewed.factors == core.factors
    assert reviewed.result_type == "FORMAL"
    assert all(row.state == "RETAINED" for row in reviewed.physical_records)
    physical = reviewed_physical_metrics(reviewed.event, authority)
    assert physical["segment_count"] > 0
    assert physical["violation_rate"] == 0
    assert physical["semantic_review_content_sha256"] == authority.semantic_review_content_sha256


def test_formal_metric_receipt_keeps_original_diagnostic_model_literals(
    authority: ReviewedAuthority,
) -> None:
    metrics = reviewed_metric_config(authority)
    assert metrics.result_type == "FORMAL"
    assert metrics.computation_config.formal_benchmark_status == "UNRESOLVED"
    assert metrics.computation_config.k_values == (1, 2, 3)
    assert metrics.computation_config.coverage_epsilon_m == .5
    assert authority.historical_context.scale_authority == "UNVERIFIED"


def test_unsupported_collision_ablation_remains_na(authority: ReviewedAuthority) -> None:
    with pytest.raises(ValueError, match="supplied approved collision consumer"):
        _run(authority, ablation="remove_collision")


def test_missing_application_and_tampered_manifest_fail_before_authority(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text('{"schema_version":"other"}')
    with pytest.raises(ValueError, match="unsupported reviewed application"):
        load_reviewed_authority(tmp_path, repo_root=ROOT)


@pytest.mark.parametrize("offset,expected", [(.499, True), (.5, False), (.501, False)])
def test_reviewed_evaluation_reuses_strict_ade_threshold_and_complete_5hz_reference(
    authority: ReviewedAuthority, offset: float, expected: bool,
) -> None:
    from amidst.domain.ground_truth import GroundTruthSample, GroundTruthTrajectory

    event = _run(authority).event
    reference = GroundTruthTrajectory(
        trajectory_id="synthetic-evaluation-only", target_id=event.target_id,
        scene_id="synthetic-reviewed-test", random_seed=42, sample_rate_hz=5,
        source_asset_sha256=authority.source_sha256,
        samples=tuple(GroundTruthSample(
            timestamp=tick / 5, position=(3 + .4 * tick / 5, 5 + offset, 0),
            velocity=(.4, 0, 0), floor_id="1F", zone_id="AREA_1F_OFFICE",
        ) for tick in range(51)),
    )
    before = event.model_dump_json()
    result = evaluate_reviewed_trajectories(
        event, reference, reviewed_metric_config(authority),
        constraints=ConstraintConfig(max_speed_m_s=.7904), authority=authority,
    )
    assert event.model_dump_json() == before
    assert result["result_type"] == "FORMAL"
    assert result["reviewed_physical"]["violation_rate"] == 0
    for row in result["computation_result"]["evaluations"]:
        assert row["coverage_at_k"] is expected
        assert row["trajectory_metrics"][0]["ground_truth_sample_count"] == 51
        assert row["trajectory_metrics"][0]["ade_m"] == pytest.approx(offset)


def test_evaluation_sampling_extent_failure_is_retained_as_error(
    authority: ReviewedAuthority,
) -> None:
    from amidst.domain.ground_truth import GroundTruthSample, GroundTruthTrajectory

    event = _run(authority).event
    reference = GroundTruthTrajectory(
        trajectory_id="synthetic-wrong-range", target_id=event.target_id,
        scene_id="synthetic-reviewed-test", random_seed=42, sample_rate_hz=5,
        source_asset_sha256=authority.source_sha256,
        samples=(GroundTruthSample(timestamp=0, position=(3, 5, 0), velocity=(.4, 0, 0)),
                 GroundTruthSample(timestamp=.2, position=(3.08, 5, 0), velocity=(.4, 0, 0))),
    )
    with pytest.raises(ValueError):
        evaluate_reviewed_trajectories(
            event, reference, reviewed_metric_config(authority),
            constraints=ConstraintConfig(max_speed_m_s=.7904), authority=authority,
        )
