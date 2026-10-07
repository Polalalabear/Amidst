"""GT-free route inventory for a reviewed complete rectangular physical domain.

This module consumes the reviewed provider itself. A local rectangle proves a
single major source-distinct route class, not an arbitrary number of configured
parallel polylines. Simulation recipes are frozen here before export; inference
uses only the resulting projected endpoint observations.
"""

from __future__ import annotations

import hashlib
import math
from itertools import pairwise
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel, Provenance, Vec3
from amidst.domain.navigation import (
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
)
from amidst.domain.observation import Observation
from amidst.domain.pipeline import PipelineConfig
from amidst.domain.reconstruction import ReconstructionPolicy
from amidst.domain.search import GraphSearchPolicy, MovementConstraints
from amidst.domain.topology import (
    CameraTopologyConfig,
    CameraTopologyNode,
    CameraTransition,
    CameraTransitionType,
)
from amidst.local_semantic_review import ReviewedRestrictedLocalPhysicalProvider
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import Digest

CASE2_BLOCKER = "CASE2_REQUIRES_SOURCE_DISTINCT_BRANCHES_OUTSIDE_APPROVED_RECTANGLE"


class RecipeWaypoint(DomainModel):
    timestamp: FiniteFloat = Field(ge=0)
    position: Vec3


class ReviewedCaseRecipe(DomainModel):
    case_id: Literal["case1", "case2", "case3"]
    status: Literal["FROZEN_PENDING_FRESH_VISIBILITY", "BLOCKED_SCOPE"]
    blockers: tuple[str, ...] = ()
    site_id: Literal["office"] = "office"
    trajectory_id: str = Field(min_length=1)
    floor_id: Literal["1F"] = "1F"
    zone_id: Literal["AREA_1F_OFFICE"] = "AREA_1F_OFFICE"
    walkable_id: Literal["WALK_1F_OFFICE"] = "WALK_1F_OFFICE"
    camera_ids: tuple[str, str]
    waypoints: tuple[RecipeWaypoint, ...]
    landmark_offset_bu: FiniteFloat = Field(ge=0)
    landmark_plane_z_bu: FiniteFloat
    support_z_bu: FiniteFloat
    footpoint_bounds_min: Vec3
    footpoint_bounds_max: Vec3

    @model_validator(mode="after")
    def ordered_schedule(self) -> Self:
        if self.camera_ids[0] == self.camera_ids[1]:
            raise ValueError("reviewed case requires two existing distinct cameras")
        low, high = self.footpoint_bounds_min, self.footpoint_bounds_max
        if low[0] >= high[0] or low[1] >= high[1] or low[2] != high[2]:
            raise ValueError("reviewed recipe requires a positive rectangle on one support plane")
        if self.support_z_bu != low[2] or (
            self.landmark_plane_z_bu - low[2] != self.landmark_offset_bu
        ):
            raise ValueError("landmark offset must be source plane minus support, without GT")
        if self.status == "BLOCKED_SCOPE":
            if self.case_id != "case2" or self.waypoints or self.blockers != (CASE2_BLOCKER,):
                raise ValueError("blocked Case2 cannot carry a fabricated export recipe")
        elif len(self.waypoints) < 2 or self.blockers:
            raise ValueError("executable recipe requires at least two waypoints and no blocker")
        if self.waypoints and self.waypoints[0].timestamp != 0:
            raise ValueError("source schedule must start at zero")
        for first, last in pairwise(self.waypoints):
            if first.timestamp >= last.timestamp:
                raise ValueError("source recipe timestamps must be strictly increasing")
        for point in self.waypoints:
            if not all(lo <= value <= hi for value, lo, hi in zip(
                point.position, low, high, strict=True,
            )):
                raise ValueError("source recipe footpoint is outside the approved rectangle")
        return self


class ReviewedCaseInventoryConfig(DomainModel):
    """Pre-export lock; never pass this recipe-bearing object to inference."""
    schema_version: Literal["phase1-reviewed-case-inventory-v1"]
    status: Literal["FROZEN_BEFORE_SIMULATION_AND_EVALUATION"]
    protocol_version: Literal["phase1-benchmark-protocol-v1"]
    protocol_sha256: Digest
    source_sha256: Digest
    source_size_bytes: int = Field(gt=0)
    human_decisions_sha256: Digest
    reviewed_certificate_content_sha256: Digest
    semantic_review_content_sha256: Digest
    scope_id: str = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    metres_per_blender_unit: FiniteFloat = Field(gt=0)
    export_seed: Literal[20261005]
    inference_seed: Literal[42]
    sampling_fps: Literal[5]
    sampling_extent: Literal["SOURCE_ENDPOINTS_INCLUSIVE_NO_REJECTION"]
    eligibility: Literal["ONE_CANONICAL_DIRECT_ROUTE_PER_SOURCE_DISTINCT_CLASS"]
    source_distinct_route_classes: Literal[1]
    branch_count: Literal[0]
    aggregation_max_visible_sample_gap_s: FiniteFloat = Field(gt=0)
    source_camera_zones: dict[str, str]
    search_policy: GraphSearchPolicy
    movement: MovementConstraints
    reconstruction_policy: ReconstructionPolicy
    k_values: tuple[Literal[1], Literal[2], Literal[3]]
    baseline_protocol: Literal["EXISTING_A_B_C_FACTOR_MASKS_AND_SUPPORTED_ABLATIONS"]
    supported_ablations: tuple[str, ...]
    cases: tuple[ReviewedCaseRecipe, ReviewedCaseRecipe, ReviewedCaseRecipe]
    reference_sampling_policy: Literal["ALL_REFERENCE_TIMESTAMPS_5HZ_ENDPOINTS_INCLUSIVE"]
    temporal_alignment_policy: Literal["ALL_GROUND_TRUTH_TIMESTAMPS_EXACT_EXTENT"]
    interpolation_policy: Literal["PIECEWISE_LINEAR"]
    ground_truth_used_for_inventory: Literal[False]
    simulation_or_evaluation_executed_before_lock: Literal[False]
    config_locked_before_simulation: Literal[True]
    overall_exit_gate_enabled: Literal[False]

    @model_validator(mode="after")
    def locked_lineage(self) -> Self:
        if self.metres_per_blender_unit != 0.0247 or (
            self.aggregation_max_visible_sample_gap_s != 0.200001
        ):
            raise ValueError("reviewed scale and 5 Hz aggregation policy are fixed")
        if tuple(case.case_id for case in self.cases) != ("case1", "case2", "case3"):
            raise ValueError("inventory must retain ordered Case1/2/3 including blocked Case2")
        expected_budget = GraphSearchPolicy(
            max_candidate_paths=3, max_search_nodes=1000, max_path_length_m=24.7,
            max_search_time_s=10, max_branch_factor=3, max_detour_ratio=2,
        )
        if self.search_policy != expected_budget:
            raise ValueError("reviewed search budget differs from normalized pilot lineage")
        if self.movement.max_speed_m_s != 0.7904 or self.reconstruction_policy != (
            ReconstructionPolicy(
                direct_path_slack_tolerance_s=1, include_dwell_hypotheses=True,
                endpoint_tolerance_m=0.0000000247,
            )
        ):
            raise ValueError("reviewed speed/slack/dwell differ from approved normalized lineage")
        if self.cases[1].status != "BLOCKED_SCOPE":
            raise ValueError("single-class domain cannot enable a branching Case2")
        domain = (self.cases[0].footpoint_bounds_min, self.cases[0].footpoint_bounds_max)
        cameras = self.cases[0].camera_ids
        for case in self.cases:
            if (case.footpoint_bounds_min, case.footpoint_bounds_max) != domain or (
                case.camera_ids != cameras or set(cameras) != set(self.source_camera_zones)
            ):
                raise ValueError("all recipes must use the same reviewed source domain/cameras")
            for first, last in pairwise(case.waypoints):
                native_speed = math.dist(first.position, last.position) / (
                    last.timestamp - first.timestamp
                )
                if native_speed > 32:
                    raise ValueError("frozen source recipe exceeds approved speed ceiling")
            if any(abs(point.timestamp * 5 - round(point.timestamp * 5)) > 1e-9
                   for point in case.waypoints):
                raise ValueError("source endpoints must lie on the fixed 5 Hz sampling grid")
        return self

    def case(self, case_id: str) -> ReviewedCaseRecipe:
        return next(case for case in self.cases if case.case_id == case_id)


class ReviewedInferenceCase(DomainModel):
    case_id: Literal["case1", "case2", "case3"]
    status: Literal["FROZEN_PENDING_FRESH_VISIBILITY", "BLOCKED_SCOPE"]
    blockers: tuple[str, ...]
    floor_id: Literal["1F"]
    zone_id: Literal["AREA_1F_OFFICE"]
    walkable_id: Literal["WALK_1F_OFFICE"]
    camera_ids: tuple[str, str]


class ReviewedCaseInferenceConfig(DomainModel):
    """Strict GT-free lock: source recipes/trajectory IDs are forbidden fields."""

    schema_version: Literal["phase1-reviewed-case-inference-lock-v1"]
    status: Literal["FROZEN_BEFORE_INFERENCE"]
    export_config_file_sha256: Digest
    export_config_content_sha256: Digest
    protocol_version: Literal["phase1-benchmark-protocol-v1"]
    protocol_sha256: Digest
    source_sha256: Digest
    human_decisions_sha256: Digest
    reviewed_certificate_content_sha256: Digest
    semantic_review_content_sha256: Digest
    scope_id: str = Field(min_length=1)
    metres_per_blender_unit: FiniteFloat = Field(gt=0)
    inference_seed: Literal[42]
    sampling_fps: Literal[5]
    sampling_extent: Literal["SOURCE_ENDPOINTS_INCLUSIVE_NO_REJECTION"]
    eligibility: Literal["ONE_CANONICAL_DIRECT_ROUTE_PER_SOURCE_DISTINCT_CLASS"]
    source_distinct_route_classes: Literal[1]
    branch_count: Literal[0]
    aggregation_max_visible_sample_gap_s: FiniteFloat = Field(gt=0)
    source_camera_zones: dict[str, str]
    footpoint_bounds_min: Vec3
    footpoint_bounds_max: Vec3
    search_policy: GraphSearchPolicy
    movement: MovementConstraints
    reconstruction_policy: ReconstructionPolicy
    k_values: tuple[Literal[1], Literal[2], Literal[3]]
    baseline_protocol: Literal["EXISTING_A_B_C_FACTOR_MASKS_AND_SUPPORTED_ABLATIONS"]
    supported_ablations: tuple[str, ...]
    cases: tuple[ReviewedInferenceCase, ReviewedInferenceCase, ReviewedInferenceCase]
    overall_exit_gate_enabled: Literal[False]
    simulation_recipe_positions_available_to_inference: Literal[False]
    ground_truth_available_to_inference: Literal[False]

    @model_validator(mode="after")
    def validate_lineage(self) -> Self:
        if self.metres_per_blender_unit != .0247 or (
            self.aggregation_max_visible_sample_gap_s != .200001
        ):
            raise ValueError("inference scale/aggregation must retain approved fixed lineage")
        if self.search_policy != GraphSearchPolicy(
            max_candidate_paths=3, max_search_nodes=1000, max_path_length_m=24.7,
            max_search_time_s=10, max_branch_factor=3, max_detour_ratio=2,
        ) or self.movement.max_speed_m_s != .7904 or (
            self.reconstruction_policy != ReconstructionPolicy(
                direct_path_slack_tolerance_s=1, include_dwell_hypotheses=True,
                endpoint_tolerance_m=.0000000247,
            )
        ):
            raise ValueError("inference budgets/speed/timing must retain normalized pilot lineage")
        low, high = self.footpoint_bounds_min, self.footpoint_bounds_max
        if low[0] >= high[0] or low[1] >= high[1] or low[2] != high[2]:
            raise ValueError("inference requires the exact reviewed fixed-floor rectangle")
        if tuple(case.case_id for case in self.cases) != ("case1", "case2", "case3"):
            raise ValueError("inference must retain ordered Case1/2/3 status")
        for case in self.cases:
            if set(case.camera_ids) != set(self.source_camera_zones):
                raise ValueError("inference source camera identities differ from binding")
            if case.case_id == "case2":
                if case.status != "BLOCKED_SCOPE" or case.blockers != (CASE2_BLOCKER,):
                    raise ValueError("single-class inference cannot enable Case2 branching")
            elif case.status != "FROZEN_PENDING_FRESH_VISIBILITY" or case.blockers:
                raise ValueError("Case1/3 execution still requires fresh visible-gap proof")
        return self

    def case(self, case_id: str) -> ReviewedInferenceCase:
        return next(case for case in self.cases if case.case_id == case_id)


def load_reviewed_case_inference_config(
    path: Path, *, expected_sha256: str | None = None,
) -> ReviewedCaseInferenceConfig:
    raw = path.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reviewed inference lock file SHA-256 mismatch")
    return ReviewedCaseInferenceConfig.model_validate_json(raw)


def load_reviewed_case_inventory(
    path: Path, *, expected_sha256: str | None = None,
) -> ReviewedCaseInventoryConfig:
    raw = path.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reviewed case config file SHA-256 mismatch")
    return ReviewedCaseInventoryConfig.model_validate_json(raw)


def _checked_provider(
    provider: ReviewedRestrictedLocalPhysicalProvider,
) -> ReviewedRestrictedLocalPhysicalProvider:
    if not isinstance(provider, ReviewedRestrictedLocalPhysicalProvider):
        raise ValueError("inventory requires the reviewed provider, including semantic receipt")
    return ReviewedRestrictedLocalPhysicalProvider(
        provider.certificate, provider.domain, provider.contract,
        provider.expected_certificate_content_sha256, provider.expected_human_decisions_sha256,
    )


def reviewed_rectangle_inventory(
    provider: ReviewedRestrictedLocalPhysicalProvider,
) -> dict[str, object]:
    """Prove a single major route class from complete, convex free-space authority.

    For any fixed endpoints a,b and any continuous permitted path p(t),
    H(s,t)=(1-s)p(t)+s((1-t)a+tb) lies in this convex rectangle for every s,t.
    Endpoints stay fixed. This is an analytic proof over the complete domain,
    not sampled branch counting or an exhaustive count of all possible curves.
    """
    checked = _checked_provider(provider)
    certificate = checked.certificate
    physical = certificate.physical_certificate
    low, high = physical.footpoint_bounds_bu
    z = (low[2] + high[2]) / 2
    perimeter = (
        (low[0], low[1], z), (high[0], low[1], z),
        (high[0], high[1], z), (low[0], high[1], z), (low[0], low[1], z),
    )
    checked.validate_polyline(perimeter)
    ratio = checked.contract.scale.metres_per_blender_unit
    return {
        "schema_version": "reviewed-rectangle-route-proof-v1",
        "status": "PASS_SINGLE_MAJOR_ROUTE_CLASS",
        "source_sha256": physical.source_sha256,
        "scope_id": physical.scope_id,
        "reviewed_certificate_content_sha256": checked.expected_certificate_content_sha256,
        "human_decisions_sha256": checked.expected_human_decisions_sha256,
        "semantic_review_content_sha256": certificate.semantic_review_content_sha256,
        "source_evidence_content_sha256": physical.evidence_content_sha256,
        "footpoint_bounds_bu": physical.footpoint_bounds_bu,
        "width_m": (high[0] - low[0]) * ratio,
        "length_m": (high[1] - low[1]) * ratio,
        "complete_free_space_basis": physical.coverage,
        "proof": "FIXED_ENDPOINT_STRAIGHT_LINE_HOMOTOPY_IN_CONVEX_COMPLETE_FREE_RECTANGLE",
        "homotopy": "H(s,t)=(1-s)*p(t)+s*((1-t)*a+t*b)",
        "source_distinct_route_classes": 1,
        "branch_count": 0,
        "hole_count": 0,
        "approved_portal_or_cross_scope_transitions": 0,
        "eligibility": "ONE_CANONICAL_DIRECT_ROUTE_PER_SOURCE_DISTINCT_CLASS",
        "all_geometric_curves_enumerated": False,
        "parallel_offsets_are_distinct_branches": False,
        "timing_hypotheses_are_distinct_routes": False,
        "case2_blockers": (CASE2_BLOCKER,),
        "ground_truth_read": False,
        "simulation_recipe_read": False,
    }


def validate_inventory_authority(
    config: ReviewedCaseInventoryConfig, provider: ReviewedRestrictedLocalPhysicalProvider,
) -> None:
    config = ReviewedCaseInventoryConfig.model_validate(config.model_dump(mode="python"))
    checked = _checked_provider(provider)
    physical = checked.certificate.physical_certificate
    if (
        config.source_sha256 != physical.source_sha256
        or config.scope_id != physical.scope_id
        or config.reviewed_certificate_content_sha256
        != checked.expected_certificate_content_sha256
        or config.human_decisions_sha256 != checked.expected_human_decisions_sha256
        or config.semantic_review_content_sha256
        != checked.certificate.semantic_review_content_sha256
        or config.metres_per_blender_unit != checked.contract.scale.metres_per_blender_unit
    ):
        raise ValueError("inventory differs from reviewed source/receipt/certificate authority")
    low, high = physical.footpoint_bounds_bu
    recipe = config.cases[0]
    if recipe.footpoint_bounds_min[:2] != low[:2] or (
        recipe.footpoint_bounds_max[:2] != high[:2]
        or not low[2] <= recipe.footpoint_bounds_min[2] <= high[2]
    ):
        raise ValueError("frozen inventory expands or changes the certified local footprint")
    for case in config.cases:
        if case.waypoints:
            checked.validate_polyline(tuple(point.position for point in case.waypoints))


def validate_inference_authority(
    config: ReviewedCaseInferenceConfig, provider: ReviewedRestrictedLocalPhysicalProvider,
) -> None:
    if not isinstance(config, ReviewedCaseInferenceConfig):
        raise ValueError("inference accepts only a GT-free lock, never simulation recipes")
    config = ReviewedCaseInferenceConfig.model_validate(config.model_dump(mode="python"))
    checked = _checked_provider(provider)
    physical = checked.certificate.physical_certificate
    if (
        config.source_sha256 != physical.source_sha256
        or config.scope_id != physical.scope_id
        or config.reviewed_certificate_content_sha256
        != checked.expected_certificate_content_sha256
        or config.human_decisions_sha256 != checked.expected_human_decisions_sha256
        or config.semantic_review_content_sha256
        != checked.certificate.semantic_review_content_sha256
        or config.metres_per_blender_unit != checked.contract.scale.metres_per_blender_unit
    ):
        raise ValueError("inference differs from reviewed source/receipt/certificate authority")
    low, high = physical.footpoint_bounds_bu
    if config.footpoint_bounds_min[:2] != low[:2] or (
        config.footpoint_bounds_max[:2] != high[:2]
        or not low[2] <= config.footpoint_bounds_min[2] <= high[2]
    ):
        raise ValueError("inference lock expands or changes the certified footprint")


def build_reviewed_case_pipeline(
    start_observation: Observation, end_observation: Observation,
    provider: ReviewedRestrictedLocalPhysicalProvider, config: ReviewedCaseInferenceConfig,
    case_id: str, spatial_context_id: str,
) -> PipelineConfig:
    """Bind one source-distinct direct route to actual SI projected endpoints.

    The caller validates fresh stream/context authority. Plane identifiers and
    projection provenance remain untouched, including legal exact-time multiview.
    No source recipe position is used to snap or choose inference endpoints.
    """
    validate_inference_authority(config, provider)
    case = config.case(case_id)
    if case.status == "BLOCKED_SCOPE":
        raise ValueError(CASE2_BLOCKER)
    start = Observation.model_validate(start_observation.model_dump(mode="python"))
    end = Observation.model_validate(end_observation.model_dump(mode="python"))
    if (
        start.target_id != end.target_id or start.provenance != Provenance.PROJECTED
        or end.provenance != Provenance.PROJECTED or start.end_time >= end.start_time
        or (start.camera_id, end.camera_id) != case.camera_ids
    ):
        raise ValueError("reviewed graph requires ordered PROJECTED source-camera gap endpoints")
    first, last = start.projected_path[-1], end.projected_path[0]
    if any(point.floor_id != case.floor_id or point.zone_id != case.zone_id
           for point in (first, last)):
        raise ValueError("projected endpoints differ from reviewed floor/zone authority")
    a, b = first.world_position, last.world_position
    if math.dist(a, b) <= config.reconstruction_policy.endpoint_tolerance_m:
        raise ValueError("reviewed moving route requires distinct observed footpoint endpoints")
    ratio = config.metres_per_blender_unit
    provider.validate_polyline(tuple((p[0] / ratio, p[1] / ratio, p[2] / ratio) for p in (a, b)))
    identity = content_sha256({
        "case_id": case_id, "config": config.model_dump(mode="json"),
        "start": start.model_dump(mode="json"), "end": end.model_dump(mode="json"),
        "context_id": spatial_context_id,
    })[:24]
    graph_id, edge_id = f"reviewed_graph:{identity}", f"reviewed_route:{case_id}:direct"
    navigation = NavigationGraphConfig(
        graph_id=graph_id, spatial_context_id=spatial_context_id,
        data_kind=NavigationDataKind.CONFIGURED, source_asset_sha256=config.source_sha256,
        node_match_tolerance_m=config.reconstruction_policy.endpoint_tolerance_m,
        nodes=(
            NavigationNode(node_id="projected_departure", position=a,
                           floor_id=case.floor_id, zone_id=case.zone_id),
            NavigationNode(node_id="projected_recovery", position=b,
                           floor_id=case.floor_id, zone_id=case.zone_id),
        ),
        edges=(NavigationEdge(edge_id=edge_id, from_node_id="projected_departure",
                              to_node_id="projected_recovery", polyline=(a, b)),),
    )
    topology = CameraTopologyConfig(
        topology_id=f"reviewed_topology:{identity}", navigation_graph_id=graph_id,
        spatial_context_id=spatial_context_id, data_kind=NavigationDataKind.CONFIGURED,
        source_asset_sha256=config.source_sha256,
        nodes=tuple(CameraTopologyNode(camera_id=camera, floor_id=case.floor_id,
                                       zone_id=config.source_camera_zones[camera])
                    for camera in case.camera_ids),
        transitions=(CameraTransition(
            transition_id=f"reviewed_handoff:{case_id}:direct",
            from_camera_id=start.camera_id, to_camera_id=end.camera_id,
            transition_type=CameraTransitionType.ADJACENT,
            navigation_from_node_id="projected_departure",
            navigation_to_node_id="projected_recovery", navigation_edge_ids=(edge_id,),
        ),),
    )
    NavigationNetwork(NavigationGraph(navigation), CameraTopologyGraph(topology))
    return PipelineConfig(
        navigation=navigation, topology=topology, movement=config.movement,
        search_policy=config.search_policy, reconstruction_policy=config.reconstruction_policy,
    )


def reviewed_case_readiness(
    start_observation: Observation, end_observation: Observation,
    provider: ReviewedRestrictedLocalPhysicalProvider, config: ReviewedCaseInferenceConfig,
    case_id: str, spatial_context_id: str,
) -> dict[str, object]:
    """Separate automatic per-case proofs from an unavailable overall Exit Gate.

    Endpoint observations must come from the independently source-bound fresh
    visible/GAP partition validated by the caller. This function does not decide
    source visibility from recipe positions, and does not read a reference path.
    """
    pipeline = build_reviewed_case_pipeline(
        start_observation, end_observation, provider, config, case_id, spatial_context_id,
    )
    first, last = start_observation.projected_path[-1], end_observation.projected_path[0]
    length = math.dist(first.world_position, last.world_position)
    minimum = length / config.movement.max_speed_m_s
    gap = last.timestamp - first.timestamp
    feasible = minimum <= gap
    # The protocol gives long-GAP intent, not a numerical acceptance threshold.
    # Report the measured ratio and the explicit 180 s stress schedule separately.
    long_gap = case_id == "case3" and gap >= 20 and gap > minimum + 1
    return {
        "schema_version": "phase1-reviewed-case-readiness-v1",
        "case_id": case_id,
        "case_config_content_sha256": content_sha256(config.model_dump(mode="json")),
        "export_config_content_sha256": config.export_config_content_sha256,
        "source_sha256": config.source_sha256,
        "scope_id": config.scope_id,
        "reviewed_certificate_content_sha256": config.reviewed_certificate_content_sha256,
        "semantic_review_content_sha256": config.semantic_review_content_sha256,
        "human_decisions_sha256": config.human_decisions_sha256,
        "endpoint_observation_ids": (start_observation.observation_id,
                                     end_observation.observation_id),
        "endpoint_point_ids": (first.point_id, last.point_id),
        "endpoint_observation_content_sha256": content_sha256({
            "start": start_observation.model_dump(mode="json"),
            "end": end_observation.model_dump(mode="json"),
        }),
        "graph_content_sha256": content_sha256(pipeline.model_dump(mode="json")),
        "aggregation_policy": {
            "max_visible_sample_gap_s": config.aggregation_max_visible_sample_gap_s,
        },
        "aggregation_policy_content_sha256": content_sha256({
            "max_visible_sample_gap_s": config.aggregation_max_visible_sample_gap_s,
        }),
        "fresh_visible_gap_visible_proof_required_separately": True,
        "physical_certificate_pass": True,
        "unique_major_source_route": True,
        "source_distinct_routes": 1,
        "branch_count": 0,
        "candidate_growth_supported": False,
        "candidate_growth_status": "N/A_NO_APPROVED_BRANCHING_SCOPE",
        "long_gap": long_gap,
        "gap_duration_s": gap,
        "canonical_route_length_m": length,
        "minimum_travel_time_s": minimum,
        "gap_to_minimum_travel_time_ratio": gap / minimum if minimum > 0 else None,
        "temporal_slack_s": gap - minimum,
        "speed_time_feasible": feasible,
        "uniform_timing_primary": True,
        "departure_dwell_supported": True,
        "source_route_inventory_proof":
            "FIXED_ENDPOINT_STRAIGHT_LINE_HOMOTOPY_IN_CONVEX_COMPLETE_FREE_RECTANGLE",
        "case_execution_ready": feasible and (case_id == "case1" or long_gap),
        "case3_original_full_stress_exit_gate_complete": False,
        "case2_blockers": (CASE2_BLOCKER,),
        "ground_truth_used": False,
        "overall_exit_gate_enabled": False,
    }
