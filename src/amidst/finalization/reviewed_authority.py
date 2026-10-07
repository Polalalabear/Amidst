"""Reviewed authority around unchanged projection, search and metric producers.

The original pilot containers retain their diagnostic literals. Fresh evidence
gets a separate source/receipt binding; no historical stream is promoted. A
reviewed physical provider is kept intact at every consumer boundary.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from time import monotonic
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from amidst.benchmark.baselines import RoutePhysicalRecord, require_supported_baseline
from amidst.datasets.pilot import PilotInferenceContext
from amidst.domain.common import DomainModel, Vec3
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.metric_config import MetricConfig
from amidst.domain.observation import Observation
from amidst.domain.pipeline import InferenceInput, PipelineConfig
from amidst.domain.stream import ObservationAggregation, StreamBinding
from amidst.domain.trajectory import Event, ReconstructionResult
from amidst.graph.engine import GeometricSearchResult, GraphFactorMask, SpatiotemporalGraphEngine
from amidst.local_semantic_review import (
    ReviewedLocalScopeCertificate,
    ReviewedRestrictedLocalPhysicalProvider,
)
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.network import NavigationNetwork
from amidst.navigation.topology import CameraTopologyGraph
from amidst.observation.aggregation import aggregate_frames
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_collision import CylinderCollisionConsumer
from amidst.physical_policy_contract import load_physical_policy_contract
from amidst.physical_units import native_projected_point_to_metres
from amidst.reconstruction.blind_gap import BlindGapReconstructor
from amidst.scene_geometry import FloorAuthority, GeometryAuthorityError, GeometrySurface
from amidst.walkable_clearance import WalkableClearanceDomain

NO_PLANE = "EXACT_TIME_MULTIVIEW_NO_PLANE_ASSUMPTION"
APPLICATION_FILES = frozenset({
    "human_decisions.json", "review_receipt.json", "certificate_result.json",
    "approved_input_lock.json", "resume_plan.json",
})


def review_content_sha256(value: object) -> str:
    """Match the human-review UTF-8 canonical hash, including non-ASCII text."""
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _object(raw: bytes) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("reviewed artifact must contain a JSON object")
    return value


def _safe(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or any(
        part.lower() in {"evaluation", "ground_truth", "simulation"} for part in path.parts
    ):
        raise ValueError("review authority cannot read GT/evaluation/simulation inputs")
    result = (root / path).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("review authority input escapes repository")
    return result


def _chosen(document: Mapping[str, Any], identity: str) -> dict[str, Any]:
    items = [item for item in document["items"] if item["id"] == identity]
    if len(items) != 1 or items[0]["decision"] != "APPROVE":
        raise ValueError("each original human decision must remain explicitly APPROVE")
    options = [option for option in items[0]["approve_options"]
               if option["id"] == items[0]["selected_option"]]
    if len(options) != 1:
        raise ValueError("human approval profile must be exactly defined")
    return dict(options[0]["payload"])


def _immutable_decisions(document: dict[str, Any]) -> dict[str, Any]:
    immutable = deepcopy(document)
    immutable.pop("review_payload_sha256", None)
    immutable["metadata"].pop("reviewer", None)
    immutable["metadata"].pop("submitted_at", None)
    for item in immutable["items"]:
        item.pop("decision", None)
        item.pop("selected_option", None)
    return immutable


@dataclass(frozen=True, slots=True)
class ReviewedAuthority:
    source_sha256: str
    human_decisions_sha256: str
    review_payload_sha256: str
    application_manifest_sha256: str
    certificate_content_sha256: str
    semantic_review_content_sha256: str
    approved_input_lock: dict[str, Any]
    approved_input_lock_content_sha256: str
    historical_context: PilotInferenceContext
    floor_support_z_bu: float
    projection_authority_content_sha256: str
    provider: ReviewedRestrictedLocalPhysicalProvider

    @property
    def certificate(self) -> ReviewedLocalScopeCertificate:
        return self.provider.certificate

    def validate(self) -> None:
        """Revalidate the full wrapper; never hand a bare certificate to consumers."""
        if review_content_sha256(self.approved_input_lock) != (
            self.approved_input_lock_content_sha256
        ):
            raise ValueError("reviewed input lock changed after loading")
        if content_sha256({
            "historical_context": self.historical_context.model_dump(mode="json"),
            "floor_support_z_bu": self.floor_support_z_bu,
        }) != self.projection_authority_content_sha256:
            raise ValueError("reviewed source calibration/support binding changed after loading")
        checked = ReviewedRestrictedLocalPhysicalProvider(
            self.provider.certificate, self.provider.domain, self.provider.contract,
            self.certificate_content_sha256, self.human_decisions_sha256,
        )
        if (
            checked.certificate.semantic_review.source_sha256 != self.source_sha256
            or checked.certificate.semantic_review_content_sha256
            != self.semantic_review_content_sha256
            or self.approved_input_lock["human_decisions_sha256"] != self.human_decisions_sha256
            or self.approved_input_lock["source_sha256"] != self.source_sha256
        ):
            raise ValueError("reviewed source/receipt/lock authority mismatch")


def load_reviewed_authority(
    application_directory: Path, *, repo_root: Path,
) -> ReviewedAuthority:
    """Load only hash-bound public review/support artifacts, with no GT input."""
    manifest_raw = (application_directory / "manifest.json").read_bytes()
    manifest = _object(manifest_raw)
    if manifest["schema_version"] != "phase1-human-review-application-v1":
        raise ValueError("unsupported reviewed application manifest")
    rows = manifest["artifacts"]
    if {row["path"] for row in rows} != APPLICATION_FILES or len(rows) != len(APPLICATION_FILES):
        raise ValueError("reviewed application file allowlist differs")
    loaded = {}
    for row in rows:
        relative = row["path"]
        if Path(relative).name != relative:
            raise ValueError("application files must be direct children")
        path = _safe(application_directory, relative)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("reviewed application artifact hash mismatch: " + relative)
        loaded[relative] = _object(raw)
    decisions = loaded["human_decisions.json"]
    decisions_sha = review_content_sha256(decisions)
    receipt = loaded["review_receipt.json"]
    lock = loaded["approved_input_lock.json"]
    if (
        receipt["schema_version"] != "phase1-human-review-receipt-v1"
        or receipt["human_decisions_sha256"] != decisions_sha
        or receipt["source_sha256"] != decisions["metadata"]["source_sha256"]
        or receipt["review_payload_sha256"] != decisions["review_payload_sha256"]
        or receipt["certificate_status"] != "PASS"
        or receipt["formal_execution_enabled"] is not False
        or lock["formal_execution_enabled"] is not False
        or lock["physical_certificate_status"] != "PASS"
        or lock["legacy_diagnostic_artifacts_promoted"] is not False
        or lock["human_decisions_sha256"] != decisions_sha
    ):
        raise ValueError("reviewed authority requires consistent applied PASS receipts")
    expected_profiles = {
        "geometry_semantics": "HR-01", "projection_binding": "HR-02",
        "coverage": "HR-03", "timing": "HR-04",
    }
    if any(lock[key] != _chosen(decisions, identity)
           for key, identity in expected_profiles.items()) or (
        lock["automatic_settings"] != decisions["metadata"]["automatic_settings"]
    ):
        raise ValueError("applied settings differ from the exact approved profiles")
    # The application cannot replace the original human approval document.
    original_decisions = _object((repo_root / "human_review/decisions.json").read_bytes())
    if review_content_sha256(original_decisions) != decisions_sha:
        raise ValueError("applied decisions differ from the original approval")
    template = _object((repo_root / "human_review/review_template.json").read_bytes())
    if (
        _immutable_decisions(decisions) != _immutable_decisions(template)
        or review_content_sha256(_immutable_decisions(decisions))
        != decisions["review_payload_sha256"]
    ):
        raise ValueError("immutable reviewed questions/profiles/source changed")
    input_rows = decisions["metadata"]["input_hashes"]
    by_path = {row["path"]: row["sha256"] for row in input_rows}
    if len(by_path) != len(input_rows):
        raise ValueError("reviewed original input paths must be unique")

    def read_original(relative: str) -> bytes:
        raw = _safe(repo_root, relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != by_path[relative]:
            raise ValueError("reviewed historical input SHA-256 mismatch: " + relative)
        return raw

    # All 29 original inputs stay required. No substitute formal dataset is accepted.
    for relative in sorted(by_path):
        read_original(relative)
    certificate = ReviewedLocalScopeCertificate.model_validate_json(
        json.dumps(loaded["certificate_result.json"]["certificate"]),
    )
    physical = certificate.physical_certificate
    support = _object(gzip.decompress(read_original(
        "data/scene_audit/phase1_physical_policy_approval_20261006/floor_support_details.json.gz",
    )))
    if support["source_sha256"] != receipt["source_sha256"]:
        raise ValueError("reviewed actual support source differs")
    contract = load_physical_policy_contract(
        repo_root / "configs/physical_policy_runtime_school_v3.json",
    )
    floor = FloorAuthority.model_validate_json(json.dumps(next(
        row for row in support["floor_authorities"] if row["floor_id"] == physical.floor_id
    )))
    surfaces = tuple(GeometrySurface.model_validate_json(json.dumps(row))
                     for row in support["support_surfaces"]
                     if row["surface_id"] in physical.support_surface_ids)
    domain = WalkableClearanceDomain.from_surfaces(
        surfaces, floor=floor, scale=contract.scale, policy=contract.policy,
        expected_source_sha256=receipt["source_sha256"],
    )
    certificate_sha = content_sha256(certificate.model_dump(mode="json"))
    provider = ReviewedRestrictedLocalPhysicalProvider(
        certificate, domain, contract, certificate_sha, decisions_sha,
    )
    historical = PilotInferenceContext.model_validate_json(read_original(
        "data/finalization/local_run/dataset/inference/office/context.json",
    ))
    office = next(row for row in support["walkable_reviews"]
                  if row["walkable_id"] == "WALK_1F_OFFICE")
    support_z = float(office["source_support_height_bu"])
    result = ReviewedAuthority(
        source_sha256=receipt["source_sha256"], human_decisions_sha256=decisions_sha,
        review_payload_sha256=receipt["review_payload_sha256"],
        application_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        certificate_content_sha256=certificate_sha,
        semantic_review_content_sha256=certificate.semantic_review_content_sha256,
        approved_input_lock=lock,
        approved_input_lock_content_sha256=review_content_sha256(lock),
        historical_context=historical,
        floor_support_z_bu=support_z,
        projection_authority_content_sha256=content_sha256({
            "historical_context": historical.model_dump(mode="json"),
            "floor_support_z_bu": support_z,
        }), provider=provider,
    )
    result.validate()
    return result


class ReviewedInferenceContext(DomainModel):
    schema_version: Literal["phase1-reviewed-inference-context-v1"] = (
        "phase1-reviewed-inference-context-v1"
    )
    result_type: Literal["FORMAL"] = "FORMAL"
    computation_context: PilotInferenceContext
    human_decisions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    certificate_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_review_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fresh_export_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    landmark_reference: Literal["RIGID_UPRIGHT_SOURCE_BOUND_MARKER"] = (
        "RIGID_UPRIGHT_SOURCE_BOUND_MARKER"
    )
    inference_reference: Literal["FLOOR_CONTACT_POINT"] = "FLOOR_CONTACT_POINT"
    conversion: Literal["SUBTRACT_SOURCE_BOUND_Z_OFFSET_KEEP_XY"] = (
        "SUBTRACT_SOURCE_BOUND_Z_OFFSET_KEEP_XY"
    )
    coordinate_units: Literal["METRES_AFTER_NATIVE_PROJECTION"] = "METRES_AFTER_NATIVE_PROJECTION"
    offset_bu: float
    offset_m: float

    @model_validator(mode="after")
    def finite_offset(self) -> Self:
        if not math.isfinite(self.offset_bu) or not math.isfinite(self.offset_m):
            raise ValueError("reviewed rigid landmark offset must be finite")
        return self

    @property
    def binding(self) -> StreamBinding:
        return self.computation_context.binding


def _validate_context(context: ReviewedInferenceContext, authority: ReviewedAuthority) -> None:
    authority.validate()
    native = PilotInferenceContext.model_validate(context.computation_context.model_dump())
    historical = authority.historical_context
    if (
        context.human_decisions_sha256 != authority.human_decisions_sha256
        or context.certificate_content_sha256 != authority.certificate_content_sha256
        or context.semantic_review_content_sha256 != authority.semantic_review_content_sha256
        or native.source_asset_sha256 != authority.source_sha256
        or native.cameras != historical.cameras or native.plane != historical.plane
        or native.zone != historical.zone or native.site_id != historical.site_id
        or native.source_id == historical.source_id
        or native.spatial_context_id == historical.spatial_context_id
        or native.observations_sha256 == historical.observations_sha256
    ):
        raise ValueError("reviewed context must bind fresh evidence and exact approved calibration")
    offset = float(native.plane.point[2]) - authority.floor_support_z_bu
    if (
        context.offset_bu != offset
        or context.offset_m != authority.provider.contract.scale.to_metres(offset)
        or authority.approved_input_lock["projection_binding"]["conversion"] != context.conversion
        or native.plane.normal != (0, 0, 1)
    ):
        raise ValueError("rigid landmark offset differs from approved source support")


def build_reviewed_context(
    authority: ReviewedAuthority, native_context: PilotInferenceContext, *,
    observations_sha256: str, fresh_export_config_sha256: str,
) -> ReviewedInferenceContext:
    native = PilotInferenceContext.model_validate(native_context.model_dump())
    if observations_sha256 != native.observations_sha256:
        raise ValueError("fresh observations digest differs from native context binding")
    offset = float(native.plane.point[2]) - authority.floor_support_z_bu
    result = ReviewedInferenceContext(
        computation_context=native, human_decisions_sha256=authority.human_decisions_sha256,
        certificate_content_sha256=authority.certificate_content_sha256,
        semantic_review_content_sha256=authority.semantic_review_content_sha256,
        fresh_export_config_sha256=fresh_export_config_sha256, offset_bu=offset,
        offset_m=authority.provider.contract.scale.to_metres(offset),
    )
    _validate_context(result, authority)
    return result


def convert_landmark_dataset(
    dataset: FrameSampleDataset, context: ReviewedInferenceContext, authority: ReviewedAuthority,
    *, projection_sidecar: Mapping[str, Any],
) -> FrameSampleDataset:
    """Apply only the approved rigid Z offset, then BU→SI; preserve every raw frame.

    Method, no-plane identity, uncertainty and conditioning remain in the pinned
    sidecar. No projection is clipped, snapped, rejected or selected with GT.
    Points outside authority are retained and fail at the physical consumer.
    """
    _validate_context(context, authority)
    dataset = FrameSampleDataset.model_validate(dataset.model_dump())
    native = context.computation_context
    if (
        projection_sidecar.get("ground_truth_read") is not False
        or projection_sidecar.get("source_asset_sha256") != authority.source_sha256
        or projection_sidecar.get("observations_sha256") != native.observations_sha256
        or projection_sidecar.get("retained_evidence_count") != len(dataset.samples)
    ):
        raise ValueError("reviewed projection sidecar must preserve fresh source-bound evidence")
    sidecar_rows = {(row["timestamp"], row["frame_id"], row["target_id"]): row
                    for row in projection_sidecar["rows"]}
    samples = []
    camera_ids = {camera.camera_id for camera in native.cameras}
    for sample in dataset.samples:
        if sample.binding != context.binding or sample.camera_id not in camera_ids:
            raise ValueError("reviewed samples must preserve source/context/camera binding")
        point = sample.projected_point
        if point is not None:
            row = sidecar_rows[(sample.timestamp, sample.frame_id, sample.target_id)]
            if (
                point.floor_id != native.zone.floor_id or point.zone_id != native.zone.zone_id
                or point.plane_id not in {native.plane.plane_id, NO_PLANE}
                or row["ground_truth_read"] is not False
                or row["selection_uses_ground_truth"] is not False
                or (point.plane_id == NO_PLANE and (
                    row["method"] != "EXACT_TIME_MULTIVIEW"
                    or point.camera_id not in row["selected_camera_ids"]
                ))
            ):
                raise ValueError("reviewed projection method/floor/zone provenance mismatch")
            values = point.model_dump()
            p = point.world_position
            values["world_position"] = (p[0], p[1], p[2] - context.offset_bu)
            shifted = type(point).model_validate(values)
            point = native_projected_point_to_metres(
                shifted, authority.provider.contract.scale,
                source_asset_sha256=authority.source_sha256,
            )
        values = sample.model_dump()
        values["projected_point"] = None if point is None else point.model_dump()
        samples.append(type(sample).model_validate(values))
    return FrameSampleDataset(samples=aggregate_frames(tuple(samples)).samples)


def validate_reviewed_endpoints(
    aggregation: ObservationAggregation, context: ReviewedInferenceContext,
    authority: ReviewedAuthority,
) -> tuple[Observation, Observation]:
    """Bind legal multiview or fixed-plane endpoints without fabricating plane proof."""
    _validate_context(context, authority)
    aggregation = ObservationAggregation.model_validate(aggregation.model_dump())
    if aggregate_frames(aggregation.samples, aggregation.policy) != aggregation:
        raise ValueError("reviewed topology requires the canonical evidence partition")
    if len(aggregation.observations) != 2:
        raise ValueError("reviewed independent GAP requires exactly two visible segments")
    bound = sorted(aggregation.observations, key=lambda item: (
        item.observation.start_time, item.observation.end_time, item.observation.observation_id,
    ))
    if any(item.binding != context.binding for item in bound):
        raise ValueError("reviewed endpoint source/context binding mismatch")
    start, end = (item.observation for item in bound)
    native = context.computation_context
    camera_ids = {camera.camera_id for camera in native.cameras}
    if (
        start.target_id != end.target_id or start.camera_id == end.camera_id
        or start.camera_id not in camera_ids or end.camera_id not in camera_ids
        or not start.projected_path or not end.projected_path
        or start.end_time >= end.start_time
    ):
        raise ValueError("reviewed GAP requires independent source-camera endpoint evidence")
    interior = tuple(sample for sample in aggregation.samples
                     if start.end_time < sample.timestamp < end.start_time)
    if not interior or any(sample.visibility.value != "GAP" for sample in interior):
        raise ValueError("reviewed GAP requires missing evidence across the complete interior")
    if any(sample.binding != context.binding for sample in aggregation.samples):
        raise ValueError("reviewed GAP raw sample binding differs")
    for observation in (start, end):
        for point in observation.projected_path:
            if (
                point.plane_id not in {native.plane.plane_id, NO_PLANE}
                or point.floor_id != native.zone.floor_id or point.zone_id != native.zone.zone_id
            ):
                raise ValueError("reviewed endpoint preserves projection method/floor/zone")
    ratio = authority.provider.contract.scale.metres_per_blender_unit
    points = tuple(tuple(float(value) / ratio for value in point.world_position)
                   for point in (start.projected_path[-1], end.projected_path[0]))
    authority.provider.validate_polyline(points)  # type: ignore[arg-type]
    return start, end


class ReviewedMetricConfig(DomainModel):
    schema_version: Literal["phase1-reviewed-metrics-v1"] = "phase1-reviewed-metrics-v1"
    result_type: Literal["FORMAL"] = "FORMAL"
    human_decisions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_input_lock_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    computation_config: MetricConfig
    sampling_hz: Literal[5] = 5
    sampling_extent: Literal["SOURCE_ENDPOINTS_INCLUSIVE_NO_REJECTION"] = (
        "SOURCE_ENDPOINTS_INCLUSIVE_NO_REJECTION"
    )
    cross_case_aggregation: Literal["NONE"] = "NONE"


def reviewed_metric_config(authority: ReviewedAuthority) -> ReviewedMetricConfig:
    authority.validate()
    lock = authority.approved_input_lock
    coverage, settings = lock["coverage"], lock["automatic_settings"]
    if (
        coverage["distance_metric"] != "ADE" or coverage["comparison"] != "STRICTLY_LESS_THAN"
        or coverage["epsilon_m"] != 0.5 or settings["k_values"] != [1, 2, 3]
        or settings["sampling_hz"] != 5
        or settings["sampling_extent"] != "SOURCE_ENDPOINTS_INCLUSIVE_NO_REJECTION"
    ):
        raise ValueError("reviewed metrics differ from original approved HR-03")
    config = MetricConfig(
        metric_config_version="phase1-reviewed-metric-computation-v1",
        k_values=tuple(settings["k_values"]), coverage_epsilon_m=coverage["epsilon_m"],
        collision_tolerance_m=authority.provider.contract.parameter("collision_tolerance_m"),
    )
    return ReviewedMetricConfig(
        human_decisions_sha256=authority.human_decisions_sha256,
        reviewed_input_lock_content_sha256=authority.approved_input_lock_content_sha256,
        computation_config=config,
    )


class ReviewedBaselineRun(DomainModel):
    schema_version: Literal["phase1-reviewed-baseline-run-v1"] = "phase1-reviewed-baseline-run-v1"
    method_id: str
    ablation_id: str | None
    result_type: Literal["FORMAL"] = "FORMAL"
    human_decisions_sha256: str
    certificate_content_sha256: str
    semantic_review_content_sha256: str
    frozen_config_sha256: str
    case_readiness_sha256: str
    factors: GraphFactorMask
    requested_k: int
    geometric_result: GeometricSearchResult
    timed_result: ReconstructionResult
    event: Event
    timing_unavailable_route_ids: tuple[str, ...]
    timed_metrics_status: Literal["AVAILABLE", "N/A_TIMING_UNAVAILABLE"]
    physical_records: tuple[RoutePhysicalRecord, ...]
    physical_status: Literal["APPROVED_LOCAL_SCOPE"] = "APPROVED_LOCAL_SCOPE"
    physical_scope_id: str


def run_reviewed_baseline(
    inputs: InferenceInput, method_id: str, *, authority: ReviewedAuthority,
    context: ReviewedInferenceContext, frozen_config_sha256: str, case_readiness_sha256: str,
    case_readiness: Mapping[str, Any], aggregation: ObservationAggregation,
    ablation_id: str | None = None, collision_consumer: CylinderCollisionConsumer | None = None,
    clock: Callable[[], float] = monotonic,
) -> ReviewedBaselineRun:
    """Use exactly the existing baseline masks, traversal and timing implementations.

    The caller must first establish the case-readiness proof and freeze its config;
    their hashes remain in every run. These hashes do not grant overall Exit Gate
    readiness. No GT, simulation recipe or evaluation reference is an input.
    """
    _validate_context(context, authority)
    for digest in (frozen_config_sha256, case_readiness_sha256):
        if len(digest) != 64 or any(letter not in "0123456789abcdef" for letter in digest):
            raise ValueError("reviewed execution requires frozen config/readiness SHA-256")
    inputs = InferenceInput.model_validate(inputs.model_dump())
    start, end = validate_reviewed_endpoints(aggregation, context, authority)
    if inputs.start_observation != start or inputs.end_observation != end:
        raise ValueError("reviewed baseline endpoint observations differ from fresh aggregation")
    case_id = case_readiness.get("case_id")
    pipeline = PipelineConfig(
        navigation=inputs.navigation, topology=inputs.topology, movement=inputs.movement,
        search_policy=inputs.search_policy, reconstruction_policy=inputs.reconstruction_policy,
    )
    if (
        content_sha256(case_readiness) != case_readiness_sha256
        or case_readiness.get("schema_version") != "phase1-reviewed-case-readiness-v1"
        or case_readiness.get("case_execution_ready") is not True
        or case_readiness.get("physical_certificate_pass") is not True
        or case_readiness.get("ground_truth_used") is not False
        or case_readiness.get("case_config_content_sha256") != frozen_config_sha256
        or case_readiness.get("source_sha256") != authority.source_sha256
        or case_readiness.get("reviewed_certificate_content_sha256")
        != authority.certificate_content_sha256
        or case_readiness.get("semantic_review_content_sha256")
        != authority.semantic_review_content_sha256
        or case_readiness.get("human_decisions_sha256") != authority.human_decisions_sha256
        or case_readiness.get("endpoint_observation_content_sha256") != content_sha256({
            "start": start.model_dump(mode="json"), "end": end.model_dump(mode="json"),
        })
        or case_readiness.get("graph_content_sha256")
        != content_sha256(pipeline.model_dump(mode="json"))
        or case_readiness.get("aggregation_policy") != aggregation.policy.model_dump(mode="json")
        or case_readiness.get("aggregation_policy_content_sha256")
        != content_sha256(aggregation.policy.model_dump(mode="json"))
        or (case_id == "case1" and case_readiness.get("unique_major_source_route") is not True)
        or (case_id == "case2" and case_readiness.get("source_distinct_routes", 0) < 2)
        or (case_id == "case3" and case_readiness.get("long_gap") is not True)
        or case_id not in {"case1", "case2", "case3"}
    ):
        raise ValueError("reviewed baseline requires exact automatic per-case readiness proof")
    native = context.computation_context
    timing = authority.approved_input_lock["timing"]
    if (
        inputs.navigation.source_asset_sha256 != authority.source_sha256
        or inputs.topology.source_asset_sha256 != authority.source_sha256
        or inputs.navigation.spatial_context_id != native.spatial_context_id
        or inputs.topology.spatial_context_id != native.spatial_context_id
        or inputs.movement.max_speed_m_s != timing["max_speed_m_s"]
        or inputs.reconstruction_policy.direct_path_slack_tolerance_s
        != timing["direct_path_slack_tolerance_s"]
        or inputs.reconstruction_policy.include_dwell_hypotheses
        != timing["include_dwell_hypotheses"]
    ):
        raise ValueError("reviewed inference source/context/speed/timing differs from approval")
    capability = require_supported_baseline(method_id, ablation_id=ablation_id)
    assert capability.current_mask is not None
    factors = GraphFactorMask(
        travel_time_filter=capability.current_mask.travel_time_filter,
        camera_topology_filter=capability.current_mask.camera_topology_filter,
    )
    if ablation_id == "remove_travel_time":
        factors = GraphFactorMask(travel_time_filter=False, camera_topology_filter=True)
    elif ablation_id == "remove_topology":
        factors = GraphFactorMask(travel_time_filter=True, camera_topology_filter=False)
    if collision_consumer is not None and collision_consumer.inputs.source_sha256 != (
        authority.source_sha256
    ):
        raise ValueError("reviewed collision consumer source differs")
    if ablation_id == "remove_collision" and collision_consumer is None:
        raise ValueError("remove_collision requires a supplied approved collision consumer")
    records: list[RoutePhysicalRecord] = []
    ratio = authority.provider.contract.scale.metres_per_blender_unit

    def validate_route(polyline: tuple[Vec3, ...]) -> bool:
        points_bu = tuple(tuple(float(value) / ratio for value in point) for point in polyline)
        try:
            authority.provider.validate_polyline(points_bu)  # type: ignore[arg-type]
        except GeometryAuthorityError as error:
            records.append(RoutePhysicalRecord(
                polyline_m=polyline, state="UNVALIDATED", reasons=error.reasons,
            ))
            return False
        if collision_consumer is not None and ablation_id != "remove_collision":
            decision = collision_consumer.validate(polyline)
            records.append(RoutePhysicalRecord(
                polyline_m=polyline, state=decision.state, reasons=decision.reasons,
            ))
            return decision.state == "RETAINED"
        records.append(RoutePhysicalRecord(polyline_m=polyline, state="RETAINED"))
        return True

    network = NavigationNetwork(
        NavigationGraph(inputs.navigation), CameraTopologyGraph(inputs.topology),
    )
    engine = SpatiotemporalGraphEngine(
        network, inputs.movement, inputs.search_policy, clock=clock, factors=factors,
        route_filter=validate_route,
    )
    requested = inputs.search_policy.max_candidate_paths
    selected = (
        1 if capability.baseline_id == "A" or ablation_id == "shortest_path_only" else requested
    )
    geometry = engine.propose_geometric_routes(
        inputs.start_observation, inputs.end_observation, max_paths=selected,
    )
    candidates = tuple(candidate for route in geometry.routes
                       if (candidate := engine.timed_candidate(route)) is not None)
    timed = ReconstructionResult(
        candidates=candidates, termination_reason=geometry.termination_reason,
        expanded_nodes=geometry.expanded_nodes, complete=geometry.complete,
        rejection_reasons=geometry.rejection_reasons,
    )
    event = BlindGapReconstructor(inputs.reconstruction_policy).reconstruct_gap(
        inputs.start_observation, inputs.end_observation, timed,
    )
    return ReviewedBaselineRun(
        method_id=method_id, ablation_id=ablation_id,
        human_decisions_sha256=authority.human_decisions_sha256,
        certificate_content_sha256=authority.certificate_content_sha256,
        semantic_review_content_sha256=authority.semantic_review_content_sha256,
        frozen_config_sha256=frozen_config_sha256, case_readiness_sha256=case_readiness_sha256,
        factors=factors, requested_k=requested, geometric_result=geometry, timed_result=timed,
        event=event, timing_unavailable_route_ids=tuple(
            route.candidate_id for route in geometry.routes if route.timing_status == "UNAVAILABLE"
        ), timed_metrics_status=(
            "N/A_TIMING_UNAVAILABLE"
            if any(route.timing_status == "UNAVAILABLE" for route in geometry.routes)
            else "AVAILABLE"
        ), physical_records=tuple(records),
        physical_scope_id=authority.certificate.physical_certificate.scope_id,
    )


def reviewed_physical_metrics(
    event: Event, authority: ReviewedAuthority,
) -> dict[str, Any]:
    """Evaluate continuous footpoint segments only inside the intact reviewed scope."""
    authority.validate()
    ratio = authority.provider.contract.scale.metres_per_blender_unit
    count, invalid = 0, 0
    failures = []
    for hypothesis in event.trajectories:
        for start, end in pairwise(hypothesis.timed_points):
            count += 1
            points = tuple(tuple(float(value) / ratio for value in point.world_position)
                           for point in (start, end))
            try:
                authority.provider.validate_polyline(points)  # type: ignore[arg-type]
            except GeometryAuthorityError as error:
                invalid += 1
                failures.append({"hypothesis_id": hypothesis.hypothesis_id,
                                 "reasons": error.reasons})
    return {
        "status": "AVAILABLE" if count else "N/A_NO_TIMED_SEGMENTS", "result_type": "FORMAL",
        "method": "COMPLETE_REVIEWED_SCOPE_CONTINUOUS_SEGMENTS", "segment_count": count,
        "violation_segment_count": invalid,
        "violation_rate": None if not count else invalid / count,
        "certificate_content_sha256": authority.certificate_content_sha256,
        "semantic_review_content_sha256": authority.semantic_review_content_sha256,
        "scope_id": authority.certificate.physical_certificate.scope_id,
        "outside_scope": "REFUSE_VALIDATION", "failures": failures,
    }
