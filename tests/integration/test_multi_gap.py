"""Independent blind gaps over a deterministic producer-neutral visible stream."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import amidst.events.aggregation as event_module
from amidst.domain.common import Provenance
from amidst.domain.evidence import GapReason, VisibilityStatus
from amidst.domain.navigation import (
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
)
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.pipeline import PipelineConfig
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.stream import (
    AggregationPolicy,
    BoundGapEvent,
    BoundObservation,
    ObservationAggregation,
    OcclusionState,
    RawProjectedFrameSample,
)
from amidst.domain.topology import (
    CameraTopologyConfig,
    CameraTopologyNode,
    CameraTransition,
    CameraTransitionType,
)
from amidst.domain.trajectory import HypothesisKind, TerminationReason
from amidst.events import EventAggregationError, reconstruct_gaps
from amidst.graph.engine import GraphInputError
from amidst.observation import AggregationInputError, aggregate_frames

SEED = 20261001


def _sample(
    camera: str,
    timestamp: float,
    *,
    visible: bool = True,
    source_id: str = "synthetic_source",
    target_id: str = "person",
    spatial_context_id: str = "SYNTHETIC:multi_gap",
) -> RawProjectedFrameSample:
    identity = f"{source_id}:{target_id}:{camera}:{timestamp}"
    position = {"CAM_A": (0.0, 0.0, 0.0), "CAM_B": (20.0, 0.0, 0.0), "CAM_C": (40.0, 0.0, 0.0)}[
        camera
    ]
    return RawProjectedFrameSample(
        sample_id=identity,
        source_id=source_id,
        spatial_context_id=spatial_context_id,
        target_id=target_id,
        camera_id=camera,
        timestamp=timestamp,
        frame_id=int(timestamp * 10),
        uv=None,
        visibility=VisibilityStatus.OBSERVED if visible else VisibilityStatus.GAP,
        occlusion_state=OcclusionState.CLEAR if visible else OcclusionState.OCCLUDED,
        provenance=Provenance.PROJECTED if visible else None,
        projected_point=ProjectedPoint(
            point_id=f"{identity}:point",
            camera_id=camera,
            plane_id="floor_1F",
            timestamp=timestamp,
            world_position=position,
            floor_id="1F",
        )
        if visible
        else None,
        gap_reason=None if visible else GapReason.OCCLUDED,
    )


def _pipeline(*, second_reachable: bool = True) -> PipelineConfig:
    nodes = tuple(
        NavigationNode(node_id=node_id, position=(float(index * 20), 0, 0), floor_id="1F")
        for index, node_id in enumerate(("A", "B", "C"))
    )
    navigation = NavigationGraphConfig(
        graph_id="multi_gap_graph",
        spatial_context_id="SYNTHETIC:multi_gap",
        data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
        nodes=nodes,
        edges=tuple(
            NavigationEdge(
                edge_id=f"{start.node_id}{end.node_id}",
                from_node_id=start.node_id,
                to_node_id=end.node_id,
                polyline=(start.position, end.position),
            )
            for start, end in zip(nodes[:-1], nodes[1:], strict=True)
        ),
    )
    topology = CameraTopologyConfig(
        topology_id="multi_gap_topology",
        navigation_graph_id=navigation.graph_id,
        spatial_context_id=navigation.spatial_context_id,
        data_kind=navigation.data_kind,
        nodes=tuple(
            CameraTopologyNode(camera_id=f"CAM_{node.node_id}", floor_id="1F") for node in nodes
        ),
        transitions=tuple(
            CameraTransition(
                transition_id=f"CAM_{start.node_id}{end.node_id}",
                from_camera_id=f"CAM_{start.node_id}",
                to_camera_id=f"CAM_{end.node_id}",
                transition_type=CameraTransitionType.ADJACENT,
                navigation_from_node_id=start.node_id,
                navigation_to_node_id=end.node_id,
                navigation_edge_ids=(f"{start.node_id}{end.node_id}",),
            )
            for start, end in zip(
                nodes[: 2 if second_reachable else 1],
                nodes[1 : 3 if second_reachable else 2],
                strict=True,
            )
        ),
    )
    return PipelineConfig(
        navigation=navigation,
        topology=topology,
        movement=MovementConstraints(max_speed_m_s=1),
        search_policy=GraphSearchPolicy(max_candidate_paths=3, max_search_time_s=60),
    )


def _stream() -> tuple[RawProjectedFrameSample, ...]:
    return (
        _sample("CAM_A", 0),
        _sample("CAM_A", 1),
        _sample("CAM_A", 2, visible=False),
        _sample("CAM_B", 21),
        _sample("CAM_B", 22, visible=False),
        _sample("CAM_C", 41),
    )


def _run(
    samples: tuple[RawProjectedFrameSample, ...],
    pipeline: PipelineConfig | None = None,
    **kwargs: Any,
) -> tuple[BoundGapEvent, ...]:
    return reconstruct_gaps(
        aggregate_frames(samples),
        pipeline or _pipeline(),
        dataset_id="multi_gap",
        random_seed=SEED,
        clock=lambda: 0.0,
        **kwargs,
    )


def test_two_gaps_preserve_brief_recovery_and_independent_endpoints() -> None:
    gaps = _run(_stream())
    assert len(gaps) == 2
    first, second = gaps
    assert first.end == second.start
    assert first.start.observation.camera_id == "CAM_A"
    assert first.end.observation.camera_id == "CAM_B"
    assert second.end.observation.camera_id == "CAM_C"
    assert first.end.observation.start_time == first.end.observation.end_time == 21
    assert first.event.time_range == (1, 21)
    assert second.event.time_range == (21, 41)
    assert first.event.event_id != second.event.event_id
    assert first.event.observation_ids != second.event.observation_ids
    assert all(gap.binding == gap.start.binding == gap.end.binding for gap in gaps)
    assert all(
        gap.search_result.termination_reason
        == gap.event.termination_reason
        == TerminationReason.COMPLETE
        for gap in gaps
    )
    assert all(
        len(gap.search_result.candidates) == len(gap.event.trajectories) == 1 for gap in gaps
    )
    assert all(gap.event.trajectories[0].kind == HypothesisKind.DIRECT_PATH for gap in gaps)


def test_raw_input_permutations_are_bitwise_deterministic_for_all_events() -> None:
    first = _run(_stream())
    second = _run(tuple(reversed(_stream())))
    assert tuple(gap.model_dump_json() for gap in first) == tuple(
        gap.model_dump_json() for gap in second
    )


def test_camera_handoffs_without_explicit_gap_markers_are_missing_intervals() -> None:
    samples = (_sample("CAM_A", 1), _sample("CAM_B", 21), _sample("CAM_C", 41))
    assert tuple(gap.event.time_range for gap in _run(samples)) == ((1, 21), (21, 41))


def test_continuous_same_camera_visibility_and_open_ended_gaps_create_no_event() -> None:
    assert _run((_sample("CAM_A", 1), _sample("CAM_A", 21))) == ()
    assert _run((_sample("CAM_A", 1), _sample("CAM_A", 2, visible=False))) == ()
    assert _run((_sample("CAM_A", 0, visible=False), _sample("CAM_B", 21))) == ()
    assert _run(()) == ()


def test_same_camera_explicit_gap_uses_normal_stationary_graph_contract() -> None:
    gaps = _run((_sample("CAM_A", 1), _sample("CAM_A", 2, visible=False), _sample("CAM_A", 21)))
    assert len(gaps) == 1
    assert gaps[0].search_result.candidates[0].path_length == 0
    assert gaps[0].event.trajectories[0].kind == HypothesisKind.DWELL
    assert gaps[0].event.trajectories[0].dwell_duration == 20


def test_source_changes_break_chains_including_changes_in_gap_markers() -> None:
    samples = (_sample("CAM_A", 1), _sample("CAM_B", 21, source_id="other"), _sample("CAM_C", 41))
    assert _run(samples) == ()
    marker = _sample("CAM_A", 2, source_id="other", visible=False)
    assert _run((_sample("CAM_A", 1), marker, _sample("CAM_A", 21))) == ()


def test_distinct_target_streams_never_cross_associate() -> None:
    samples = (
        *_stream(),
        *tuple(
            sample.model_copy(
                update={
                    "sample_id": f"other:{sample.sample_id}",
                    "target_id": "other_person",
                }
            )
            for sample in _stream()
        ),
    )
    gaps = _run(samples)
    assert len(gaps) == 4
    assert {gap.event.target_id for gap in gaps} == {"person", "other_person"}
    assert all(gap.start.observation.target_id == gap.end.observation.target_id for gap in gaps)


def test_impossible_second_gap_has_its_own_termination_and_does_not_erase_first() -> None:
    gaps = _run(_stream(), _pipeline(second_reachable=False))
    assert gaps[0].event.termination_reason == TerminationReason.COMPLETE
    assert gaps[1].event.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    assert gaps[1].event.candidates == gaps[1].event.trajectories == ()
    bounded = _pipeline()
    policy = bounded.search_policy.model_copy(update={"max_search_nodes": 1})
    limited = _run(_stream(), bounded.model_copy(update={"search_policy": policy}))
    assert all(
        gap.event.termination_reason == TerminationReason.MAX_SEARCH_NODES for gap in limited
    )


def test_context_and_source_sha_mismatches_fail_before_graph_is_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("graph must not receive mismatched bindings")

    monkeypatch.setattr(event_module, "reconstruct_input", forbidden)
    for change in ({"spatial_context_id": "wrong"}, {"source_asset_sha256": "f" * 64}):
        samples = tuple(sample.model_copy(update=change) for sample in _stream())
        with pytest.raises(EventAggregationError, match="source/context"):
            _run(samples)


def test_overlapping_or_tied_camera_visibility_fails_before_any_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("ambiguous camera visibility must not reach graph")

    monkeypatch.setattr(event_module, "reconstruct_input", forbidden)
    samples = (_sample("CAM_A", 1), _sample("CAM_B", 1), _sample("CAM_C", 41))
    with pytest.raises(EventAggregationError, match="overlapping"):
        _run(samples)


def test_off_network_endpoints_are_not_semantically_snapped() -> None:
    samples = list(_stream())
    assert samples[0].projected_point is not None
    point = samples[0].projected_point.model_copy(update={"world_position": (1, 0, 0)})
    # The gap starts at the last visible CAM_A sample.
    samples[1] = samples[1].model_copy(
        update={
            "projected_point": point.model_copy(
                update={
                    "timestamp": 1,
                    "point_id": "off_network_point",
                }
            )
        }
    )
    with pytest.raises(GraphInputError, match="outside the configured"):
        _run(tuple(samples))


def test_forged_aggregation_geometry_hidden_fields_and_gap_metadata_are_revalidated() -> None:
    aggregation = aggregate_frames(_stream())
    start = aggregation.observations[0]
    point = start.observation.projected_path[0].model_copy(update={"world_position": (999, 0, 0)})
    forged_observation = start.observation.model_copy(
        update={
            "projected_path": (point, *start.observation.projected_path[1:]),
        }
    )
    forged = aggregation.model_copy(
        update={
            "observations": (
                start.model_copy(update={"observation": forged_observation}),
                *aggregation.observations[1:],
            )
        }
    )
    with pytest.raises(AggregationInputError, match="ObservationAggregation contract"):
        reconstruct_gaps(forged, _pipeline(), dataset_id="test", random_seed=SEED)
    with pytest.raises(AggregationInputError, match="outside its declared"):
        reconstruct_gaps(
            aggregation.model_copy(update={"ground_truth": object()}),
            _pipeline(),
            dataset_id="test",
            random_seed=SEED,
        )
    gap = _run(_stream())[0]
    with pytest.raises(ValidationError, match="search termination"):
        BoundGapEvent.model_validate(
            gap.model_dump()
            | {
                "event": gap.event.model_dump()
                | {"termination_reason": TerminationReason.MAX_SEARCH_NODES},
            }
        )


@pytest.mark.parametrize(
    "field, value",
    [
        ("dataset_id", ""),
        ("random_seed", True),
        ("random_seed", "47"),
    ],
)
def test_gap_run_identity_inputs_are_strict(field: str, value: object) -> None:
    arguments: dict[str, Any] = {"dataset_id": "test", "random_seed": SEED}
    arguments[field] = value
    with pytest.raises(EventAggregationError):
        reconstruct_gaps(aggregate_frames(_stream()), _pipeline(), **arguments)


def test_real_cv_producer_contract_does_not_claim_a_real_cv_inference_implementation() -> None:
    samples = tuple(sample.model_copy(update={"data_kind": "REAL_CV"}) for sample in _stream())
    with pytest.raises(EventAggregationError, match="REAL_CV inference is deferred"):
        _run(samples)


def test_explicit_sampling_gap_policy_is_saved_and_accepted_by_event_inference() -> None:
    samples = (_sample("CAM_A", 1), _sample("CAM_A", 21))
    policy = AggregationPolicy(max_visible_sample_gap_s=2)
    aggregation = aggregate_frames(samples, policy)
    assert aggregation.policy == policy
    assert ObservationAggregation.model_validate_json(aggregation.model_dump_json()) == aggregation
    gaps = reconstruct_gaps(aggregation, _pipeline(), dataset_id="test", random_seed=SEED)
    assert len(gaps) == 1
    assert gaps[0].event.time_range == (1, 21)


def test_external_aggregation_cannot_merge_visible_samples_across_an_explicit_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("forged partition must not reach graph")

    monkeypatch.setattr(event_module, "reconstruct_input", forbidden)
    samples = (_sample("CAM_A", 0), _sample("CAM_A", 1, visible=False), _sample("CAM_A", 2))
    canonical = aggregate_frames(samples)
    first = canonical.observations[0]
    projected = tuple(
        ProjectedPoint.model_validate(
            sample.projected_point.model_dump()
            | {
                "observation_id": "forged_merge",
            }
        )
        for sample in (samples[0], samples[2])
        if sample.projected_point is not None
    )
    merged = Observation.model_validate(
        first.observation.model_dump()
        | {
            "observation_id": "forged_merge",
            "end_time": 2,
            "projected_path": projected,
        }
    )
    forged = ObservationAggregation(
        samples=canonical.samples,
        observations=(
            BoundObservation(
                binding=first.binding,
                observation=merged,
                sample_ids=(samples[0].sample_id, samples[2].sample_id),
            ),
        ),
    )
    with pytest.raises(EventAggregationError, match="canonical partition"):
        reconstruct_gaps(forged, _pipeline(), dataset_id="test", random_seed=SEED)


def test_external_aggregation_cannot_add_artificial_splits_to_continuous_visibility() -> None:
    samples = (_sample("CAM_A", 0), _sample("CAM_A", 2))
    genuine = aggregate_frames(samples)
    forged = ObservationAggregation(
        samples=genuine.samples,
        observations=(
            aggregate_frames((samples[0],)).observations[0],
            aggregate_frames((samples[1],)).observations[0],
        ),
    )
    with pytest.raises(EventAggregationError, match="canonical partition"):
        reconstruct_gaps(forged, _pipeline(), dataset_id="test", random_seed=SEED)


def test_external_aggregation_cannot_reorder_canonical_samples_or_observations() -> None:
    aggregation = aggregate_frames(_stream())
    reordered = ObservationAggregation(
        samples=tuple(reversed(aggregation.samples)),
        observations=aggregation.observations,
    )
    with pytest.raises(EventAggregationError, match="canonical partition"):
        reconstruct_gaps(reordered, _pipeline(), dataset_id="test", random_seed=SEED)


@pytest.mark.parametrize(
    "change",
    [
        {"binding": {"source_id": "wrong", "spatial_context_id": "SYNTHETIC:multi_gap"}},
        {"event": "wrong_target"},
        {"event": "wrong_endpoints"},
        {"event": "wrong_time"},
    ],
)
def test_gap_event_contract_rejects_changed_binding_endpoint_or_time_metadata(
    change: dict[str, Any],
) -> None:
    gap = _run(_stream())[0]
    payload = gap.model_dump()
    if "binding" in change:
        payload["binding"] = change["binding"]
    elif change["event"] == "wrong_target":
        payload["event"]["target_id"] = "other"
    elif change["event"] == "wrong_endpoints":
        payload["event"]["observation_ids"] = tuple(reversed(payload["event"]["observation_ids"]))
    else:
        payload["event"]["time_range"] = (0, 21)
    with pytest.raises(ValidationError):
        BoundGapEvent.model_validate(payload)


def test_event_inference_imports_do_not_access_hidden_geometry_or_consumers() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "amidst" / "events"
    for path in root.rglob("*.py"):
        modules = []
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                modules.append(node.module or "")
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
        assert not any(
            word in module
            for word in ("ground_truth", ".simulation", ".evaluation", ".visualization")
            for module in modules
        ), path
