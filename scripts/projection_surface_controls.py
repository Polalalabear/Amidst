"""GT-free E/F contract controls, exclusively for declared synthetic fixtures.

These planar footprint descriptors are not the school Geometry Provider and do
not grant school authority. They test refusal and all-hypothesis retention only;
no Graph integration, scene reconstruction or accuracy efficacy is claimed.
"""

import math
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from amidst.domain.camera import Camera
from amidst.domain.common import DomainModel, Provenance, Vec3
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import InverseProjectionError, InverseProjectionService
from amidst.observation.aggregation import validate_stream_model

LABEL = "PILOT / SYNTHETIC SAMPLE"
SCOPE: Literal["SYNTHETIC_FIXTURE_ONLY"] = "SYNTHETIC_FIXTURE_ONLY"
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identity = Annotated[str, Field(min_length=1)]
Authority = Literal["APPROVED", "HIGH_CONFIDENCE", "HUMAN_REVIEW", "REJECTED"]
TargetReference = Literal["FOOTPOINT", "BODY_LANDMARK"]


class SyntheticSurfaceBinding(DomainModel):
    """Caller-supplied fixture binding, not school calibration approval."""

    scope: Literal["SYNTHETIC_FIXTURE_ONLY"] = SCOPE
    source_sha256: Digest
    floor_id: Identity
    target_reference: TargetReference
    coordinate_units: Literal["BLENDER_SCENE_UNITS"] = "BLENDER_SCENE_UNITS"
    scale_authority: Authority
    scale_approval_id: Identity | None = None

    @model_validator(mode="after")
    def approved_scale_has_identity(self) -> Self:
        if self.scale_authority == "APPROVED" and self.scale_approval_id is None:
            raise ValueError("approved fixture scale needs an explicit approval identity")
        return self


class SyntheticSurface(DomainModel):
    """Exact declared plane bounded by an explicit XY footprint in a toy fixture."""

    scope: Literal["SYNTHETIC_FIXTURE_ONLY"] = SCOPE
    surface_id: Identity
    source_sha256: Digest
    floor_id: Identity
    target_reference: TargetReference
    role: Literal["FLOOR", "WALKABLE"] = "WALKABLE"
    plane_point: Vec3
    plane_normal: Vec3
    footprint_min: Vec3
    footprint_max: Vec3
    semantic_authority: Authority
    physical_authority: Authority
    floor_authority: Authority
    scale_authority: Authority
    coordinate_units: Literal["BLENDER_SCENE_UNITS"] = "BLENDER_SCENE_UNITS"
    approval_id: Identity | None = None

    @model_validator(mode="after")
    def valid_declared_surface(self) -> Self:
        if not math.isclose(math.hypot(*self.plane_normal), 1, rel_tol=0, abs_tol=1e-6):
            raise ValueError("fixture plane normal must be unit length")
        if any(a > b for a, b in zip(self.footprint_min, self.footprint_max, strict=True)):
            raise ValueError("footprint bounds must be ordered")
        if any(self.footprint_min[i] >= self.footprint_max[i] for i in (0, 1)):
            raise ValueError("footprint needs positive XY extent")
        if "APPROVED" in (
            self.semantic_authority, self.physical_authority,
            self.floor_authority, self.scale_authority,
        ) and self.approval_id is None:
            raise ValueError("approved fixture descriptors need explicit approval identity")
        return self


class SyntheticLandmarkOffset(DomainModel):
    """Explicit fixture-only target-reference conversion; never inferred from GT."""

    scope: Literal["SYNTHETIC_FIXTURE_ONLY"] = SCOPE
    source_sha256: Digest
    floor_id: Identity
    from_reference: Literal["FOOTPOINT"] = "FOOTPOINT"
    to_reference: Literal["BODY_LANDMARK"] = "BODY_LANDMARK"
    offset: Vec3
    authority: Authority
    approval_id: Identity | None = None

    @model_validator(mode="after")
    def approved_offset_has_identity(self) -> Self:
        if self.authority == "APPROVED" and self.approval_id is None:
            raise ValueError("approved fixture offset needs an explicit approval identity")
        return self


def _authority_reasons(
    surface: SyntheticSurface, binding: SyntheticSurfaceBinding,
) -> list[str]:
    reasons = []
    for field in ("semantic_authority", "physical_authority", "floor_authority"):
        if getattr(surface, field) != "APPROVED":
            reasons.append(f"{field.upper()}_UNAPPROVED")
    if surface.source_sha256 != binding.source_sha256:
        reasons.append("SOURCE_BINDING_MISMATCH")
    if surface.floor_id != binding.floor_id:
        reasons.append("FLOOR_BINDING_MISMATCH")
    if surface.coordinate_units != binding.coordinate_units:
        reasons.append("COORDINATE_UNITS_MISMATCH")
    if surface.scale_authority != "APPROVED" or binding.scale_authority != "APPROVED":
        reasons.append("SCALE_AUTHORITY_UNAPPROVED")
    return reasons


def project_surface_candidates(
    *, camera: Camera, frame: ObservationFrame, binding: SyntheticSurfaceBinding,
    surfaces: tuple[SyntheticSurface, ...],
    offsets: tuple[SyntheticLandmarkOffset, ...] = (),
) -> dict[str, object]:
    """Return every approved fixture hit, sorted by ID, without best-hit selection.

    A landmark ray cannot be treated as a footpoint ray. An explicitly approved,
    source/floor-bound offset may translate the support plane into a landmark
    plane; the support footprint is tested after undoing that declared offset.
    """
    # Dump/revalidate also closes model_construct / unchecked-copy bypasses.
    camera = validate_stream_model(camera, Camera)
    frame = validate_stream_model(frame, ObservationFrame)
    binding = validate_stream_model(binding, SyntheticSurfaceBinding)
    surfaces = tuple(validate_stream_model(s, SyntheticSurface) for s in surfaces)
    offsets = tuple(validate_stream_model(o, SyntheticLandmarkOffset) for o in offsets)
    if len({s.surface_id for s in surfaces}) != len(surfaces):
        raise ValueError("duplicate fixture surface identity")
    if camera.floor_id != binding.floor_id:
        raise ValueError("camera floor differs from fixture binding")
    hits = []
    decisions = []
    for surface in sorted(surfaces, key=lambda s: s.surface_id):
        reasons = _authority_reasons(surface, binding)
        offset = (0.0, 0.0, 0.0)
        if surface.target_reference != binding.target_reference:
            matching = [o for o in offsets if (
                o.from_reference == surface.target_reference
                and o.to_reference == binding.target_reference
                and o.source_sha256 == binding.source_sha256
                and o.floor_id == binding.floor_id and o.authority == "APPROVED"
            )]
            if len(matching) == 1:
                offset = matching[0].offset
            else:
                reasons.append("TARGET_REFERENCE_MISMATCH_OR_OFFSET_UNAPPROVED")
        point = None
        if not reasons:
            plane = Plane(
                plane_id=f"fixture-surface:{surface.surface_id}",
                point=(
                    surface.plane_point[0] + offset[0],
                    surface.plane_point[1] + offset[1],
                    surface.plane_point[2] + offset[2],
                ),
                normal=surface.plane_normal, floor_id=surface.floor_id,
            )
            try:
                point = InverseProjectionService(camera, plane).project_frame(frame)
            except InverseProjectionError as error:
                reasons.append(f"INVERSE_PROJECTION:{error.failure.value}")
            if point is not None:
                support_point = tuple(
                    a - b for a, b in zip(point.world_position, offset, strict=True)
                )
                if not all(
                    low <= value <= high for low, value, high in zip(
                        surface.footprint_min, support_point, surface.footprint_max, strict=True,
                    )
                ):
                    reasons.append("OUTSIDE_DECLARED_FOOTPRINT")
        accepted = point is not None and not reasons
        decisions.append({
            "surface_id": surface.surface_id, "status": "ACCEPTED" if accepted else "REFUSED",
            "reasons": sorted(reasons),
        })
        if accepted:
            assert point is not None
            hits.append({
                "surface_id": surface.surface_id,
                "target_reference": binding.target_reference,
                "applied_authorized_offset": list(offset),
                "projected_point": point.model_dump(mode="json"),
            })
    return {
        "label": LABEL, "scope": SCOPE,
        "purpose": "AUTHORITY_GATE_AND_HYPOTHESIS_RETENTION_CONTROL_ONLY",
        "actual_school_authority": "UNAVAILABLE_AUTHORITY",
        "graph_integration": False, "accuracy_efficacy_claim": False,
        "binding": binding.model_dump(mode="json"),
        "candidate_count": len(hits), "projection_hypotheses": hits,
        "unique_surface_status": (
            "UNIQUE_APPROVED_HIT" if len(hits) == 1 else
            "MULTIPLE_APPROVED_HITS" if len(hits) > 1 else "NO_APPROVED_HIT"
        ),
        "unique_projection": hits[0]["projected_point"] if len(hits) == 1 else None,
        "surface_decisions": decisions,
        "selection_policy": "ALL_APPROVED_HITS_SORTED_BY_SURFACE_ID_NO_BEST_SELECTION",
    }


def synthetic_surface_controls() -> dict[str, object]:
    """Run exactly five toy contract controls; no scene/GT files are read."""
    source_sha = "a" * 64
    binding = SyntheticSurfaceBinding(
        source_sha256=source_sha, floor_id="SYNTHETIC_FLOOR",
        target_reference="FOOTPOINT", scale_authority="APPROVED",
        scale_approval_id="SYNTHETIC_DECLARED_SCALE",
    )
    camera = Camera(
        camera_id="SYNTHETIC_FIXTURE_CAMERA", fx=320, fy=320, cx=320, cy=240,
        width=640, height=480, floor_id=binding.floor_id,
        camera_to_world=((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
    )
    frame = ObservationFrame(
        frame_id=0, timestamp=0, target_id="SYNTHETIC_FOOTPOINT_PIXEL",
        camera_id=camera.camera_id, status=VisibilityStatus.OBSERVED, point_2d=(320, 240),
        provenance=Provenance.OBSERVED,
    )
    first = SyntheticSurface(
        surface_id="surface_a", source_sha256=source_sha, floor_id=binding.floor_id,
        target_reference="FOOTPOINT", plane_point=(0, 0, -10), plane_normal=(0, 0, 1),
        footprint_min=(-1, -1, -10), footprint_max=(1, 1, -10),
        semantic_authority="APPROVED", physical_authority="APPROVED",
        floor_authority="APPROVED", scale_authority="APPROVED",
        approval_id="SYNTHETIC_DECLARED_SUPPORT_A",
    )
    second = SyntheticSurface.model_validate(first.model_dump() | {
        "surface_id": "surface_b", "plane_point": (0, 0, -20),
        "footprint_min": (-1, -1, -20), "footprint_max": (1, 1, -20),
        "approval_id": "SYNTHETIC_DECLARED_SUPPORT_B",
    })
    cases = {
        "unique_surface": (binding, (first,)),
        "multiple_surfaces": (binding, (second, first)),
        "review_only": (binding, (SyntheticSurface.model_validate(first.model_dump() | {
            "physical_authority": "HUMAN_REVIEW",
        }),)),
        "wrongsource": (binding, (SyntheticSurface.model_validate(first.model_dump() | {
            "source_sha256": "b" * 64,
        }),)),
        "wrongtargetreference": (SyntheticSurfaceBinding.model_validate(binding.model_dump() | {
            "target_reference": "BODY_LANDMARK",
        }), (first,)),
    }
    results = {
        key: project_surface_candidates(
            camera=camera, frame=frame, binding=query_binding, surfaces=surfaces,
        ) for key, (query_binding, surfaces) in cases.items()
    }
    return {
        "label": LABEL, "scope": SCOPE, "control_count": len(results),
        "purpose": "TOY_E_F_AUTHORITY_CONTROLS_NOT_SCHOOL_MITIGATION_EFFICACY",
        "actual_school_E_F": "UNAVAILABLE_AUTHORITY",
        "ground_truth_inputs": False, "graph_integration": False, "controls": results,
    }
