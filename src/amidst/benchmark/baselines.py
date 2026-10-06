"""Protocol baseline adapters over the single existing bounded graph traversal.

Geometric routes that cannot fit the observed GAP remain untimed N/A records.
Physical consumers preserve their exact approval scopes; diagnostic support does
not confer school authority or authorize a formal benchmark.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from time import monotonic
from typing import Literal

from amidst.domain.common import DomainModel, Vec3
from amidst.domain.pipeline import InferenceInput
from amidst.domain.trajectory import Event, ReconstructionResult
from amidst.graph.engine import (
    GeometricSearchResult,
    GraphFactorMask,
    SpatiotemporalGraphEngine,
)
from amidst.local_physical_scopes import RestrictedLocalPhysicalProvider
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.physical_collision import CylinderCollisionConsumer
from amidst.reconstruction.blind_gap import BlindGapReconstructor
from amidst.scene_geometry import GeometryAuthorityError


class ConstraintMask(DomainModel):
    travel_time_filter: bool
    camera_topology_filter: bool
    collision_filter: bool


class BaselineCapability(DomainModel):
    baseline_id: Literal["A", "B", "C", "D", "E"]
    method_id: str
    candidate_policy: str
    required_mask: ConstraintMask | None
    current_mask: ConstraintMask | None = None
    diagnostic_available: bool = False
    formal_available: Literal[False] = False
    engineering_prerequisites: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class AblationCapability(DomainModel):
    ablation_id: str
    reference_method: Literal["C", "D"] = "C"
    changed_factor: str | None
    diagnostic_available: bool = False
    formal_available: Literal[False] = False
    existing_entrypoint: str | None = None
    engineering_prerequisites: tuple[str, ...] = ()


class BaselineUnavailableError(ValueError):
    """Unsupported masks and formal claims are rejected before any inference."""

    def __init__(self, identity: str, reasons: tuple[str, ...]) -> None:
        self.identity = identity
        self.reasons = reasons
        super().__init__(f"{identity} unavailable: {', '.join(reasons)}")


def baseline_capabilities() -> tuple[BaselineCapability, ...]:
    geometric_mask = ConstraintMask(
        travel_time_filter=False, camera_topology_filter=False, collision_filter=True,
    )
    full_mask = ConstraintMask(
        travel_time_filter=True, camera_topology_filter=True, collision_filter=True,
    )
    current_mask = ConstraintMask(
        travel_time_filter=True, camera_topology_filter=True, collision_filter=False,
    )
    formal_prerequisites = (
        "APPROVED_CASE_LOCAL_PHYSICAL_SCOPE_REQUIRED",
        "FROZEN_FORMAL_METRIC_AND_CASE_CONFIG_REQUIRED",
    )
    return (
        BaselineCapability(
            baseline_id="A", method_id="shortest_path",
            candidate_policy="ONE_CANONICAL_SHORTEST_AUTHORIZED_GEOMETRIC_ROUTE",
            required_mask=geometric_mask,
            current_mask=ConstraintMask(
                travel_time_filter=False, camera_topology_filter=False, collision_filter=False,
            ), diagnostic_available=True,
            engineering_prerequisites=formal_prerequisites,
            limitations=("TIMING_INFEASIBLE_ROUTES_RETAINED_AS_UNTIMED_NA",),
        ),
        BaselineCapability(
            baseline_id="B", method_id="geometry",
            candidate_policy="DETERMINISTIC_MULTIPLE_AUTHORIZED_GEOMETRIC_ROUTES",
            required_mask=geometric_mask,
            current_mask=ConstraintMask(
                travel_time_filter=False, camera_topology_filter=False, collision_filter=False,
            ), diagnostic_available=True,
            engineering_prerequisites=formal_prerequisites,
            limitations=("TIMING_INFEASIBLE_ROUTES_RETAINED_AS_UNTIMED_NA",),
        ),
        BaselineCapability(
            baseline_id="C", method_id="spatiotemporal",
            candidate_policy="CURRENT_BOUNDED_SPATIOTEMPORAL_GRAPH",
            required_mask=full_mask, current_mask=current_mask, diagnostic_available=True,
            engineering_prerequisites=formal_prerequisites,
            limitations=(
                "CONFIGURED_TIME_AND_CAMERA_TOPOLOGY_DIAGNOSTIC_ONLY",
                "SUPPLIED_GRAPH_CONFIG_DOES_NOT_GRANT_SCHOOL_GEOMETRY_AUTHORITY",
                "COLLISION_FILTER_REQUIRES_SUPPLIED_APPROVED_PURPOSE_BOUND_CONSUMER",
            ),
        ),
        BaselineCapability(
            baseline_id="D", method_id="semantic",
            candidate_policy="INTERFACE_ONLY", required_mask=None,
            engineering_prerequisites=("APPROVED_SEMANTIC_POLICY_NOT_IMPLEMENTED",),
        ),
        BaselineCapability(
            baseline_id="E", method_id="agent",
            candidate_policy="INTERFACE_ONLY", required_mask=None,
            engineering_prerequisites=("AGENT_RANKING_NOT_IMPLEMENTED",),
        ),
    )


def ablation_capabilities() -> tuple[AblationCapability, ...]:
    return (
        AblationCapability(
            ablation_id="remove_travel_time", changed_factor="TRAVEL_TIME_FILTER",
            diagnostic_available=True,
        ),
        AblationCapability(
            ablation_id="remove_collision", changed_factor="COLLISION_FILTER",
            diagnostic_available=True,
            engineering_prerequisites=("REFERENCE_RUN_REQUIRES_APPROVED_COLLISION_CONSUMER",),
        ),
        AblationCapability(
            ablation_id="remove_topology", changed_factor="CAMERA_TOPOLOGY_FILTER",
            diagnostic_available=True,
        ),
        AblationCapability(
            ablation_id="shortest_path_only", changed_factor="CANDIDATE_ENUMERATOR",
            diagnostic_available=True,
            existing_entrypoint="amidst.pipeline.reconstruct_input(inputs, max_paths=1)",
        ),
        AblationCapability(
            ablation_id="full_deterministic_graph", changed_factor=None,
            diagnostic_available=True,
            existing_entrypoint="amidst.pipeline.reconstruct_input(inputs)",
        ),
        AblationCapability(
            ablation_id="add_semantic_information", changed_factor="SEMANTIC_FEATURE_POLICY",
            engineering_prerequisites=("APPROVED_SEMANTIC_POLICY_NOT_IMPLEMENTED",),
        ),
        AblationCapability(
            ablation_id="add_agent_ranking", reference_method="D", changed_factor="RANKING_POLICY",
            engineering_prerequisites=("AGENT_RANKING_NOT_IMPLEMENTED",),
        ),
    )


def require_supported_baseline(
    method_id: str, *, ablation_id: str | None = None, formal: bool = False,
) -> BaselineCapability:
    """Preflight support only; source/protocol authority remains a separate gate.

    Passing this function never authorizes a formal run and never rewrites inputs,
    movement speeds, endpoint times, topology, requested K or search budgets.
    """
    baseline = next(
        (item for item in baseline_capabilities() if item.method_id == method_id), None,
    )
    if baseline is None:
        raise BaselineUnavailableError(method_id, ("UNKNOWN_PROTOCOL_METHOD",))
    if not baseline.diagnostic_available:
        raise BaselineUnavailableError(method_id, baseline.engineering_prerequisites)
    if ablation_id is not None:
        ablation = next(
            (item for item in ablation_capabilities() if item.ablation_id == ablation_id), None,
        )
        if ablation is None:
            raise BaselineUnavailableError(ablation_id, ("UNKNOWN_PROTOCOL_ABLATION",))
        if ablation.reference_method != baseline.baseline_id:
            raise BaselineUnavailableError(ablation_id, ("WRONG_REFERENCE_METHOD",))
        if not ablation.diagnostic_available:
            raise BaselineUnavailableError(ablation_id, ablation.engineering_prerequisites)
    if formal:
        raise BaselineUnavailableError(method_id, (
            *baseline.engineering_prerequisites,
            "FORMAL_SCENE_AND_FROZEN_PROTOCOL_GATES_NOT_SATISFIED_BY_CAPABILITY_PREFLIGHT",
        ))
    return baseline


def baseline_capability_manifest() -> dict[str, object]:
    """Return serializable capability evidence, with no fabricated measurements."""
    return {
        "schema_version": "phase1-baseline-capability-v1",
        "protocol_version": "phase1-benchmark-protocol-v1",
        "status": "DIAGNOSTIC_PREFLIGHT",
        "formal_execution_enabled": False,
        "inference_executed": False,
        "gt_read": False,
        "baseline_order": [item.baseline_id for item in baseline_capabilities()],
        "baselines": [item.model_dump(mode="json") for item in baseline_capabilities()],
        "ablations": [item.model_dump(mode="json") for item in ablation_capabilities()],
        "shared_contracts": {
            "geometry": "EXPLICIT_DIRECTED_NAVIGATION_WITH_FLOOR_STAIR_AUTHORIZATION",
            "timing": "EXISTING_BLIND_GAP_RECONSTRUCTOR",
            "ordering": "EXISTING_GRAPH_DISTANCE_THEN_EDGE_IDS_THEN_TRANSITION_IDS",
            "requested_k": "UNCHANGED_NO_DUPLICATE_ROUTE_PADDING",
            "factor_masks": "EXPLICIT_FILTER_MASKS_NO_SPEED_TIME_OR_TOPOLOGY_SUBSTITUTION",
        },
    }


class RoutePhysicalRecord(DomainModel):
    polyline_m: tuple[Vec3, ...]
    state: str
    reasons: tuple[str, ...] = ()


class BaselineRun(DomainModel):
    method_id: str
    ablation_id: str | None
    result_type: Literal["DIAGNOSTIC"] = "DIAGNOSTIC"
    factors: GraphFactorMask
    requested_k: int
    geometric_result: GeometricSearchResult
    timed_result: ReconstructionResult
    event: Event
    timing_unavailable_route_ids: tuple[str, ...]
    timed_metrics_status: Literal["AVAILABLE", "N/A_TIMING_UNAVAILABLE"]
    physical_records: tuple[RoutePhysicalRecord, ...]
    physical_status: Literal["N/A", "PARTIAL_APPROVED", "APPROVED_LOCAL_SCOPE"]
    physical_scope_id: str | None


def run_baseline(
    inputs: InferenceInput, method_id: str, *, ablation_id: str | None = None,
    collision_consumer: CylinderCollisionConsumer | None = None,
    local_provider: RestrictedLocalPhysicalProvider | None = None,
    clock: Callable[[], float] = monotonic,
) -> BaselineRun:
    """Run A/B/C diagnostic support with unchanged data, timing, K and budgets.

    Approved known-component hard rejection occurs before Top-K truncation, but
    its partial coverage never certifies whole-route free space. A local provider
    additionally constrains every footpoint to its exact source-bound certificate.
    """
    capability = require_supported_baseline(method_id, ablation_id=ablation_id)
    inputs = InferenceInput.model_validate(inputs.model_dump(mode="python"))
    assert capability.current_mask is not None
    factors = GraphFactorMask(
        travel_time_filter=capability.current_mask.travel_time_filter,
        camera_topology_filter=capability.current_mask.camera_topology_filter,
    )
    if ablation_id == "remove_travel_time":
        factors = GraphFactorMask(travel_time_filter=False, camera_topology_filter=True)
    elif ablation_id == "remove_topology":
        factors = GraphFactorMask(travel_time_filter=True, camera_topology_filter=False)
    remove_collision = ablation_id == "remove_collision"
    if remove_collision and collision_consumer is None:
        raise BaselineUnavailableError("remove_collision", (
            "REFERENCE_RUN_REQUIRES_APPROVED_COLLISION_CONSUMER",
        ))
    source_sha256 = inputs.navigation.source_asset_sha256
    if collision_consumer is not None:
        if not isinstance(collision_consumer, CylinderCollisionConsumer) or (
            collision_consumer.inputs.source_sha256 != source_sha256
        ):
            raise ValueError("collision consumer must bind the same navigation source asset")
    if local_provider is not None:
        if not isinstance(local_provider, RestrictedLocalPhysicalProvider) or (
            local_provider.certificate.source_sha256 != source_sha256
        ):
            raise ValueError("local provider must bind the same navigation source asset")
    records: list[RoutePhysicalRecord] = []

    def validate_route(polyline: tuple[Vec3, ...]) -> bool:
        # The floor/support scope remains enforced even in the collision ablation.
        if local_provider is not None:
            ratio = local_provider.contract.scale.metres_per_blender_unit
            points_bu = tuple((point[0] / ratio, point[1] / ratio, point[2] / ratio)
                              for point in polyline)
            try:
                local_provider.validate_polyline(points_bu)
            except GeometryAuthorityError as error:
                records.append(RoutePhysicalRecord(
                    polyline_m=polyline, state="UNVALIDATED", reasons=error.reasons,
                ))
                return False
        if collision_consumer is not None and not remove_collision:
            decision = collision_consumer.validate(polyline)
            records.append(RoutePhysicalRecord(
                polyline_m=polyline, state=decision.state, reasons=decision.reasons,
            ))
            return decision.state == "RETAINED"
        return True

    network = NavigationNetwork(
        NavigationGraph(inputs.navigation), CameraTopologyGraph(inputs.topology),
    )
    engine = SpatiotemporalGraphEngine(
        network, inputs.movement, inputs.search_policy, clock=clock, factors=factors,
        route_filter=validate_route if collision_consumer is not None or local_provider else None,
    )
    requested_k = inputs.search_policy.max_candidate_paths
    selected_k = 1 if capability.baseline_id == "A" or ablation_id == "shortest_path_only" else (
        requested_k
    )
    geometry = engine.propose_geometric_routes(
        inputs.start_observation, inputs.end_observation, max_paths=selected_k,
    )
    candidates = tuple(
        candidate for route in geometry.routes
        if (candidate := engine.timed_candidate(route)) is not None
    )
    timed = ReconstructionResult(
        candidates=candidates, termination_reason=geometry.termination_reason,
        expanded_nodes=geometry.expanded_nodes, complete=geometry.complete,
        rejection_reasons=geometry.rejection_reasons,
    )
    event = BlindGapReconstructor(inputs.reconstruction_policy).reconstruct_gap(
        inputs.start_observation, inputs.end_observation, timed,
    )
    status: Literal["N/A", "PARTIAL_APPROVED", "APPROVED_LOCAL_SCOPE"] = "N/A"
    scope_id = None
    if collision_consumer is not None and not remove_collision:
        status, scope_id = "PARTIAL_APPROVED", collision_consumer.inputs.scope.scope_id
    if local_provider is not None:
        status, scope_id = "APPROVED_LOCAL_SCOPE", local_provider.certificate.scope_id
    return BaselineRun(
        method_id=method_id, ablation_id=ablation_id, factors=factors, requested_k=requested_k,
        geometric_result=geometry, timed_result=timed, event=event,
        timing_unavailable_route_ids=tuple(
            route.candidate_id for route in geometry.routes if route.timing_status == "UNAVAILABLE"
        ),
        # Do not evaluate the compressed feasible subset as if it were original Top-K.
        timed_metrics_status=(
            "N/A_TIMING_UNAVAILABLE"
            if any(route.timing_status == "UNAVAILABLE" for route in geometry.routes)
            else "AVAILABLE"
        ),
        physical_records=tuple(records), physical_status=status, physical_scope_id=scope_id,
    )


def diagnostic_baseline_regression() -> dict[str, object]:
    """Execute only existing synthetic Cases 1–3 fixtures and supported masks.

    This callable is for regeneration evidence. It does not open school geometry,
    evaluation references, or Ground Truth and produces no accuracy measurements.
    """
    from amidst.pipeline import reconstruct_input
    from amidst.simulation.mock_scenarios import scenario_inputs

    def digest(value: object) -> str:
        return hashlib.sha256(json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()

    root = Path(__file__).resolve().parents[3]
    paths = (
        "src/amidst/benchmark/baselines.py", "src/amidst/graph/engine.py",
        "src/amidst/domain/trajectory.py", "src/amidst/reconstruction/blind_gap.py",
        "src/amidst/simulation/mock_scenarios.py", "configs/benchmarks/protocol_v1.json",
    )
    rows: list[dict[str, object]] = []
    all_repeat = True
    all_ordering = True
    default_c_parity = True
    variants = (
        ("shortest_path", None), ("geometry", None), ("spatiotemporal", None),
        ("spatiotemporal", "remove_travel_time"), ("spatiotemporal", "remove_topology"),
        ("spatiotemporal", "shortest_path_only"),
        ("spatiotemporal", "full_deterministic_graph"),
    )
    for inputs in scenario_inputs()[:3]:
        reversed_data = inputs.model_dump(mode="python")
        for name in ("nodes", "edges"):
            reversed_data["navigation"][name] = tuple(reversed(reversed_data["navigation"][name]))
        for name in ("nodes", "transitions"):
            reversed_data["topology"][name] = tuple(reversed(reversed_data["topology"][name]))
        reordered = InferenceInput.model_validate(reversed_data)
        for method_id, ablation_id in variants:
            result = run_baseline(inputs, method_id, ablation_id=ablation_id, clock=lambda: 0.0)
            repeated = run_baseline(inputs, method_id, ablation_id=ablation_id, clock=lambda: 0.0)
            ordered = run_baseline(reordered, method_id, ablation_id=ablation_id, clock=lambda: 0.0)
            repeat_equal = result == repeated
            ordering_equal = result == ordered
            all_repeat = all_repeat and repeat_equal
            all_ordering = all_ordering and ordering_equal
            if method_id == "spatiotemporal" and ablation_id is None:
                default, event = reconstruct_input(inputs, clock=lambda: 0.0)
                default_c_parity = default_c_parity and (
                    result.timed_result == default and result.event == event
                )
            rows.append({
                "fixture_id": inputs.dataset_id,
                "result_type": "DIAGNOSTIC", "status": "EXECUTED_SYNTHETIC_FIXTURE",
                "method_id": method_id, "ablation_id": ablation_id,
                "input_sha256": digest(inputs.model_dump(mode="json")),
                "inference_sha256": digest(result.model_dump(mode="json")),
                "seed": inputs.random_seed, "requested_k": result.requested_k,
                "factors": result.factors.model_dump(mode="json"),
                "candidate_order": [route.candidate_id for route in result.geometric_result.routes],
                "corridor_order": [
                    route.navmesh_corridor for route in result.geometric_result.routes
                ],
                "candidate_count": len(result.geometric_result.routes),
                "timed_candidate_count": len(result.timed_result.candidates),
                "timing_unavailable_count": len(result.timing_unavailable_route_ids),
                "timed_metrics_status": result.timed_metrics_status,
                "expanded_states": result.geometric_result.expanded_nodes,
                "termination": result.geometric_result.termination_reason,
                "search_complete": result.geometric_result.complete,
                "physical_status": result.physical_status,
                "repeat_equal": repeat_equal, "configuration_ordering_equal": ordering_equal,
                "accuracy_metrics": None,
            })
        rows.append({
            "fixture_id": inputs.dataset_id, "method_id": "spatiotemporal",
            "ablation_id": "remove_collision", "result_type": "N/A",
            "status": "NOT_EXECUTED",
            "reason": "REFERENCE_FIXTURE_HAS_NO_SUPPLIED_APPROVED_COLLISION_CONSUMER",
        })
    return {
        "schema_version": "phase1-baseline-regression-v1",
        "result_type": "DIAGNOSTIC", "fixture_only": True,
        "formal_school_cases_executed": False, "ground_truth_read": False,
        "accuracy_metrics_evaluated": False,
        "producer_hashes": {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
                            for path in paths},
        "capabilities": baseline_capability_manifest(), "runs": rows,
        "repeated_inference_equal": all_repeat,
        "configuration_ordering_equal": all_ordering,
        "default_c_artifact_parity": default_c_parity,
        "case4": "DEFERRED",
    }
