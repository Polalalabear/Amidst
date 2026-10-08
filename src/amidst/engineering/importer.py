"""Independent reviewed recovery import with native-unit certification.

This adapter is deliberately separate from the COMPLETE artifacts.json legacy
importer. Historical structured UV records remain structured simulation records;
certification never makes them pixel measurements or Agent allowlisted answers.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from amidst.architectural_scale import load_architectural_scale
from amidst.domain.camera import Camera
from amidst.domain.common import DomainModel
from amidst.domain.stream import BoundGapEvent, BoundObservation, ObservationAggregation
from amidst.domain.trajectory import Event, ReconstructionResult
from amidst.engineering.registry import (
    CameraEntry,
    ClockBinding,
    CoordinateBinding,
    LocationModel,
    LocationRegistry,
    ResourceScope,
    Sha256,
    content_hash,
    opaque_ref,
    safe_relative_path,
    scope_parts,
)
from amidst.integration.repositories import RepositorySnapshot
from amidst.physical_units import native_camera_to_metres


class ReviewedImportCertificate(DomainModel):
    schema_version: Literal["engineering.reviewed-import-certificate.v1"] = (
        "engineering.reviewed-import-certificate.v1"
    )
    status: Literal["CERTIFIED_STRUCTURED_RECOVERY_PARTIAL_SCOPE"] = (
        "CERTIFIED_STRUCTURED_RECOVERY_PARTIAL_SCOPE"
    )
    dataset_manifest_sha256: Sha256
    inference_freeze_sha256: Sha256
    inference_config_sha256: Sha256
    source_sha256: Sha256
    scale_sha256: Sha256
    native_units: Literal["NATIVE_BU"] = "NATIVE_BU"
    canonical_units: Literal["METRES"] = "METRES"
    metres_per_native_unit: float = Field(default=0.0247, ge=0.0247, le=0.0247)
    normalization: Literal["SOURCE_BOUND_Z_OFFSET_THEN_BU_TO_METRES"] = (
        "SOURCE_BOUND_Z_OFFSET_THEN_BU_TO_METRES"
    )
    cases: tuple[str, ...]
    blocked_cases: tuple[str, ...]
    checked_dataset_files: int = Field(ge=0)
    checked_inference_files: int = Field(ge=0)
    normalized_camera_count: int = Field(ge=0)
    checked_projection_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    snapshot_sha256: Sha256
    registry_sha256: Sha256
    gt_deserialized: Literal[False] = False
    image_measurement: Literal[False] = False
    source_files_mutated: Literal[False] = False
    formal_phase1_acceptance: Literal[False] = False
    agent_allowlist_certified: Literal[False] = False
    limitations: tuple[str, ...] = (
        "Existing structured simulation records only; camera RGB sequence absent",
        "Scope remains the reviewed office recovery, without corridor-union expansion",
        "Case2 and full Case3 research exit gates remain blocked",
        "Legacy synthetic identity and raw source references remain internal",
    )


@dataclass(frozen=True)
class ReviewedImport:
    snapshot: RepositorySnapshot
    registry: LocationRegistry
    certificate: ReviewedImportCertificate


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(root: Path, relative: str) -> bytes:
    path = root.joinpath(*safe_relative_path(relative).parts).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("reviewed artifact unavailable")
    return path.read_bytes()


def _json_object(data: bytes) -> dict[str, Any]:
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("reviewed artifact must be a JSON object")
    return value


def _verify_artifacts(root: Path, manifest: dict[str, Any]) -> dict[str, bytes]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("reviewed manifest has no hash-bound artifacts")
    checked: dict[str, bytes] = {}
    for relative, digest in artifacts.items():
        if not isinstance(relative, str) or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("invalid reviewed artifact binding")
        data = _read(root, relative)
        if _digest(data) != digest:
            raise ValueError("reviewed artifact integrity mismatch")
        checked[relative] = data
    return checked


def certify_reviewed_package(
    run_root: Path, *, source_scene: Path, scale_path: Path,
    expected_dataset_sha256: str, expected_freeze_sha256: str,
) -> ReviewedImport:
    """Read and verify one existing frozen package; never execute inference.

    Expected manifest/freeze hashes bind certification to a reviewed checkpoint.
    Evaluation/simulation bytes are hash-checked but never deserialized. Only
    approved static contexts, projection receipts and canonical inference records
    are parsed. Native calibration is normalized in a new registry; the old
    camera's misleading fixed metres field is never used as unit authority.
    """
    root = run_root.resolve()
    dataset_root, inference_root = root / "dataset", root / "inference_primary"
    dataset_bytes = _read(dataset_root, "manifest.json")
    freeze_bytes = _read(inference_root, "inference_freeze.json")
    if _digest(dataset_bytes) != expected_dataset_sha256 or (
        _digest(freeze_bytes) != expected_freeze_sha256
    ):
        raise ValueError("reviewed checkpoint manifest binding mismatch")
    dataset, freeze = _json_object(dataset_bytes), _json_object(freeze_bytes)
    if dataset.get("schema_version") != "phase1-reviewed-dataset-v1" or (
        freeze.get("schema_version") != "phase1-reviewed-inference-freeze-v1"
        or freeze.get("status") != "FROZEN_BEFORE_EVALUATION"
        or freeze.get("ground_truth_read") is not False
        or freeze.get("dataset_manifest_sha256") != expected_dataset_sha256
        or dataset.get("coordinate_storage") != "BLENDER_NATIVE_UNITS"
        or dataset.get("scale_authority") != "APPROVED"
        or dataset.get("metres_per_blender_unit") != 0.0247
        or dataset.get("sampling_fps") != 5
    ):
        raise ValueError("reviewed source/clock/unit/freeze contract mismatch")
    source_hash = dataset["source_sha256"]
    with source_scene.open("rb") as stream:
        actual_source_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual_source_hash != source_hash or (
        source_scene.stat().st_size != dataset["source_size_bytes"]
    ):
        raise ValueError("reviewed source bytes mismatch")
    scale = load_architectural_scale(scale_path, expected_source_sha256=source_hash)
    if scale.metres_per_blender_unit != 0.0247:
        raise ValueError("reviewed package requires the approved school-v3 scale")
    dataset_artifacts = _verify_artifacts(dataset_root, dataset)
    inference_artifacts = _verify_artifacts(inference_root, freeze)
    cases = tuple(item["case_id"] for item in dataset["cases"] if item["status"] != "BLOCKED")
    blocked = tuple(item["case_id"] for item in dataset["cases"] if item["status"] == "BLOCKED")
    if not cases:
        raise ValueError("reviewed package has no available case")
    models: list[LocationModel] = []
    cameras: list[CameraEntry] = []
    observations: list[BoundObservation] = []
    gaps: list[BoundGapEvent] = []
    projection_count = 0
    clock_id = opaque_ref("clock", expected_dataset_sha256)
    clock = ClockBinding(clock_id=clock_id, mapping_sha256=content_hash({
        "dataset": expected_dataset_sha256, "fps": 5, "origin": 0,
        "time_basis": "CONFIGURED_SYNTHETIC_SECONDS",
    }), authority="REVIEWED_EXPORT_CONFIG")
    coordinates = CoordinateBinding(native_units="NATIVE_BU", metres_per_unit=0.0247,
                                    normalization_policy="SCALE_TO_METRES",
                                    authority="APPROVED_SCHOOL_V3_SCALE")
    for case_id in cases:
        context_bytes = dataset_artifacts[f"inference/{case_id}/context.json"]
        native = _json_object(context_bytes)
        reviewed = _json_object(inference_artifacts[f"{case_id}/reviewed_context.json"])
        if (
            native.get("source_asset_sha256") != source_hash
            or reviewed.get("coordinate_units") != "METRES_AFTER_NATIVE_PROJECTION"
            or reviewed.get("conversion") != "SUBTRACT_SOURCE_BOUND_Z_OFFSET_KEEP_XY"
            or not math.isclose(reviewed["offset_m"], reviewed["offset_bu"] * 0.0247,
                                rel_tol=0, abs_tol=1e-12)
            or reviewed["computation_context"]["source_asset_sha256"] != source_hash
            or reviewed["computation_context"]["cameras"] != native["cameras"]
            or reviewed["computation_context"]["source_id"] != native["source_id"]
            or reviewed["computation_context"]["spatial_context_id"] != native["spatial_context_id"]
            or native["observations_sha256"] != dataset["artifacts"][
                f"inference/{case_id}/observations.json"
            ]
        ):
            raise ValueError("reviewed native/context/calibration conversion mismatch")
        scope = ResourceScope(place_id="school-v3-reviewed-office", model_id="school-v3",
                              model_revision=source_hash, run_id=root.name,
                              source_id=native["source_id"], source_sha256=source_hash,
                              spatial_context_id=native["spatial_context_id"],
                              spatial_context_sha256=_digest(context_bytes), clock_id=clock_id)
        models.append(LocationModel(scope=scope, display_name=f"Reviewed office {case_id}",
                                    aliases=("school-v3", "office"), coordinates=coordinates,
                                    clock=clock, authority="SOURCE_VERIFIED_PARTIAL_REVIEW"))
        camera_ids = set()
        for raw in native["cameras"]:
            calibration = native_camera_to_metres(Camera.model_validate(raw), scale,
                                                  source_asset_sha256=source_hash)
            if calibration.camera_id in camera_ids:
                raise ValueError("duplicate reviewed camera identity")
            camera_ids.add(calibration.camera_id)
            cameras.append(CameraEntry(
                scope=scope, camera_id=calibration.camera_id,
                camera_ref=opaque_ref("camera", *scope_parts(scope), calibration.camera_id),
                calibration=calibration,
                calibration_sha256=content_hash(calibration.model_dump(mode="json")),
                authority="SOURCE_VERIFIED_PARTIAL_REVIEW", coverage_status="UNKNOWN",
            ))
        aggregation = ObservationAggregation.model_validate_json(
            inference_artifacts[f"{case_id}/aggregation.json"]
        )
        projection = _json_object(inference_artifacts[f"{case_id}/projection.json"])
        if projection.get("ground_truth_read") is not False or (
            projection.get("source_asset_sha256") != source_hash
            or projection.get("observations_sha256") != native["observations_sha256"]
        ):
            raise ValueError("reviewed projection provenance mismatch")
        rows = {(row["timestamp"], row["frame_id"], row["target_id"]): row
                for row in projection["rows"]}
        for sample in aggregation.samples:
            if (
                sample.source_asset_sha256 != source_hash
                or sample.source_id != scope.source_id
                or sample.spatial_context_id != scope.spatial_context_id
                or sample.camera_id not in camera_ids
                or not math.isclose(sample.timestamp * 5, sample.frame_id, abs_tol=1e-8)
            ):
                raise ValueError("reviewed sample source/context/camera/clock mismatch")
            if sample.projected_point is not None:
                row = rows[(sample.timestamp, sample.frame_id, sample.target_id)]
                if row["ground_truth_read"] is not False or (
                    row["selection_uses_ground_truth"] is not False
                ):
                    raise ValueError("reviewed projection selection violates isolation")
                native_point = row["selected_world_position"]
                expected = tuple((value - (reviewed["offset_bu"] if i == 2 else 0)) * 0.0247
                                 for i, value in enumerate(native_point))
                if not all(math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10) for a, b in
                           zip(expected, sample.projected_point.world_position, strict=True)):
                    raise ValueError("canonical point differs from normalized native projection")
                projection_count += 1
        observations.extend(aggregation.observations)
        result = _json_object(inference_artifacts[f"{case_id}/full_deterministic_graph.json"])
        event = Event.model_validate(result["event"])
        endpoints = {item.observation.observation_id: item for item in aggregation.observations}
        start, end = (endpoints[identity] for identity in event.observation_ids)
        gaps.append(BoundGapEvent(binding=start.binding, start=start, end=end, event=event,
                                  search_result=ReconstructionResult.model_validate(
                                      result["timed_result"])))
    snapshot = RepositorySnapshot(observations=tuple(observations), gaps=tuple(gaps))
    registry = LocationRegistry(models=tuple(models), cameras=tuple(cameras))
    certificate = ReviewedImportCertificate(
        dataset_manifest_sha256=expected_dataset_sha256,
        inference_freeze_sha256=expected_freeze_sha256,
        inference_config_sha256=freeze["config_sha256"], source_sha256=source_hash,
        scale_sha256=_digest(scale_path.read_bytes()), cases=cases, blocked_cases=blocked,
        checked_dataset_files=len(dataset_artifacts),
        checked_inference_files=len(inference_artifacts),
        normalized_camera_count=len(cameras), checked_projection_count=projection_count,
        observation_count=len(snapshot.observations), event_count=len(snapshot.gaps),
        snapshot_sha256=content_hash(snapshot.model_dump(mode="json")),
        registry_sha256=registry.sha256,
    )
    return ReviewedImport(snapshot=snapshot, registry=registry, certificate=certificate)
