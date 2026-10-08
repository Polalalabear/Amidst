"""Source-bound local resource catalog; file locators never form Agent DTOs.

Coverage is evidence, not an inference from camera or place names. Coordinates
in a calibration are explicitly normalized before being exposed to services.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, FiniteFloat, model_validator

from amidst.domain.camera import Camera, Matrix4
from amidst.domain.common import DomainModel, PositiveFinite, Timestamp

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ResourceRef = Annotated[str, Field(pattern=r"^[a-z]+:[0-9a-f]{24}$")]
Name = Annotated[str, Field(min_length=1)]
Affine2 = tuple[tuple[FiniteFloat, FiniteFloat, FiniteFloat],
                tuple[FiniteFloat, FiniteFloat, FiniteFloat]]
IDENTITY4: Matrix4 = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))


def content_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def opaque_ref(kind: str, *bindings: str) -> str:
    if not kind.isascii() or not kind.isalpha() or not kind.islower():
        raise ValueError("invalid resource kind")
    return f"{kind}:{content_hash(bindings)[:24]}"


class RegistryModel(DomainModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True, strict=True)


class ResourceScope(RegistryModel):
    place_id: Name
    model_id: Name
    model_revision: Name
    run_id: Name
    source_id: Name
    source_sha256: Sha256
    spatial_context_id: Name
    spatial_context_sha256: Sha256
    clock_id: Name


class ClockBinding(RegistryModel):
    clock_id: Name
    time_basis: Literal["CONFIGURED_SYNTHETIC_SECONDS"] = "CONFIGURED_SYNTHETIC_SECONDS"
    unit: Literal["SECONDS"] = "SECONDS"
    origin_seconds: Timestamp = 0
    mapping_sha256: Sha256
    authority: Literal["SYNTHETIC_CONFIG", "REVIEWED_EXPORT_CONFIG"]


class CoordinateBinding(RegistryModel):
    coordinate_frame: Literal["RIGHT_HANDED_XYZ_Z_UP"] = "RIGHT_HANDED_XYZ_Z_UP"
    native_units: Literal["NATIVE_BU", "METRES"]
    metres_per_unit: PositiveFinite
    normalized_units: Literal["METRES"] = "METRES"
    normalization_policy: Literal["IDENTITY", "SCALE_TO_METRES"]
    authority: Literal["SYNTHETIC_CONFIG", "APPROVED_SCHOOL_V3_SCALE"]

    @model_validator(mode="after")
    def explicit_units(self) -> Self:
        if self.native_units == "METRES" and (
            self.metres_per_unit != 1 or self.normalization_policy != "IDENTITY"
        ):
            raise ValueError("metre inputs require identity normalization")
        if self.native_units == "NATIVE_BU" and self.normalization_policy != "SCALE_TO_METRES":
            raise ValueError("native BU must be explicitly normalized")
        if self.authority == "APPROVED_SCHOOL_V3_SCALE" and (
            self.native_units != "NATIVE_BU" or self.metres_per_unit != 0.0247
        ):
            raise ValueError("school-v3 approved scale is 0.0247 metres per BU")
        return self


class CameraCorrespondence(RegistryModel):
    parent_camera_id: Name
    child_camera_id: Name
    parent_calibration_sha256: Sha256
    child_calibration_sha256: Sha256
    mapping_sha256: Sha256


class ModelDerivation(RegistryModel):
    parent_model_id: Name
    parent_revision: Name
    parent_source_sha256: Sha256
    derivation_manifest_sha256: Sha256
    parent_to_child_metres: Matrix4
    camera_correspondence: tuple[CameraCorrespondence, ...] = Field(min_length=1)
    authority_policy: Literal["SUBSET_NO_AUTHORITY_EXPANSION"] = "SUBSET_NO_AUTHORITY_EXPANSION"

    @model_validator(mode="after")
    def unique_mapping(self) -> Self:
        children = [item.child_camera_id for item in self.camera_correspondence]
        if len(children) != len(set(children)) or self.parent_to_child_metres[3] != (0, 0, 0, 1):
            raise ValueError("derivation requires unique camera mapping and affine transform")
        a, b, c = self.parent_to_child_metres[:3]
        determinant = (a[0] * (b[1] * c[2] - b[2] * c[1])
                       - a[1] * (b[0] * c[2] - b[2] * c[0])
                       + a[2] * (b[0] * c[1] - b[1] * c[0]))
        if abs(determinant) < 1e-12:
            raise ValueError("derivation coordinate transform must be invertible")
        return self


class LocationModel(RegistryModel):
    scope: ResourceScope
    display_name: Name
    aliases: tuple[Name, ...] = ()
    coordinates: CoordinateBinding
    clock: ClockBinding
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["SYNTHETIC_CONFIG", "SOURCE_VERIFIED_PARTIAL_REVIEW"]
    derivation: ModelDerivation | None = None

    @model_validator(mode="after")
    def clock_matches(self) -> Self:
        if self.clock.clock_id != self.scope.clock_id:
            raise ValueError("model clock must match scope")
        return self


class PixelPlaneCalibration(RegistryModel):
    camera_id: Name
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    ground_to_pixel: Affine2
    plane_z_m: FiniteFloat = 0
    calibration_kind: Literal["AFFINE_GROUND_PLANE_SYNTHETIC"] = "AFFINE_GROUND_PLANE_SYNTHETIC"
    units: Literal["METRES"] = "METRES"
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["SYNTHETIC_CONFIG"] = "SYNTHETIC_CONFIG"

    @model_validator(mode="after")
    def invertible(self) -> Self:
        a, b = self.ground_to_pixel
        if abs(a[0] * b[1] - a[1] * b[0]) < 1e-12:
            raise ValueError("affine ground-plane calibration must be invertible")
        return self


class CameraEntry(RegistryModel):
    scope: ResourceScope
    camera_id: Name
    camera_ref: ResourceRef
    group_ids: tuple[Name, ...] = ()
    coverage_status: Literal["UNKNOWN", "CONFIGURED_SYNTHETIC", "REVIEWED_PARTIAL"] = "UNKNOWN"
    region_ids: tuple[Name, ...] = ()
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["SYNTHETIC_CONFIG", "SOURCE_VERIFIED_PARTIAL_REVIEW"]
    calibration: Camera | None = None
    affine_calibration: PixelPlaneCalibration | None = None
    calibration_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def camera_binding(self) -> Self:
        expected = opaque_ref("camera", *scope_parts(self.scope), self.camera_id)
        if self.camera_ref != expected:
            raise ValueError("camera reference must bind its model and run")
        if self.coverage_status == "UNKNOWN" and self.region_ids:
            raise ValueError("unknown coverage cannot assert regions")
        if self.calibration is not None and self.affine_calibration is not None:
            raise ValueError("camera must select a single calibration model")
        calibration = self.calibration or self.affine_calibration
        if (calibration is None) != (self.calibration_sha256 is None):
            raise ValueError("calibration and hash must be supplied together")
        if calibration is not None and (
            calibration.camera_id != self.camera_id
            or content_hash(calibration.model_dump(mode="json")) != self.calibration_sha256
        ):
            raise ValueError("camera calibration identity/hash mismatch")
        return self


class MediaFrame(RegistryModel):
    scope: ResourceScope
    camera_id: Name
    camera_ref: ResourceRef
    media_ref: ResourceRef
    frame_id: int = Field(ge=0, strict=True)
    timestamp: Timestamp
    relative_path: Name
    sha256: Sha256
    size_bytes: int = Field(gt=0, strict=True)
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    media_type: Literal["image/png", "image/jpeg"] = "image/png"
    purpose: Literal["RGB_SEQUENCE", "DIAGNOSTIC_REFERENCE"] = "RGB_SEQUENCE"
    annotations: Literal["NONE", "DIAGNOSTIC"] = "NONE"
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"

    @model_validator(mode="after")
    def frame_binding(self) -> Self:
        safe_relative_path(self.relative_path)
        if self.camera_ref != opaque_ref("camera", *scope_parts(self.scope), self.camera_id):
            raise ValueError("frame camera reference scope mismatch")
        if self.media_ref != opaque_ref("media", *scope_parts(self.scope), self.camera_id,
                                       str(self.frame_id), self.sha256):
            raise ValueError("media reference must bind scope, frame and bytes")
        if self.purpose == "RGB_SEQUENCE" and self.annotations != "NONE":
            raise ValueError("trackable RGB sequence cannot contain diagnostic annotations")
        return self


def scope_parts(scope: ResourceScope) -> tuple[str, ...]:
    return (scope.place_id, scope.model_id, scope.model_revision, scope.run_id,
            scope.source_id, scope.source_sha256, scope.spatial_context_id,
            scope.spatial_context_sha256, scope.clock_id)


def safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if "\\" in value or path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ValueError("resource locator must be a canonical contained relative path")
    return path


class LocationRegistry(RegistryModel):
    schema_version: Literal["engineering.location-registry.v1"] = "engineering.location-registry.v1"
    models: tuple[LocationModel, ...]
    cameras: tuple[CameraEntry, ...]
    frames: tuple[MediaFrame, ...] = ()

    @model_validator(mode="after")
    def complete_index(self) -> Self:
        scopes = {scope_parts(item.scope): item for item in self.models}
        cameras = {item.camera_ref: item for item in self.cameras}
        if len(scopes) != len(self.models) or len(cameras) != len(self.cameras):
            raise ValueError("model scopes and camera refs must be unique")
        frames = {(item.camera_ref, item.frame_id) for item in self.frames}
        if len(frames) != len(self.frames) or (
            len({f.media_ref for f in self.frames}) != len(frames)
        ):
            raise ValueError("media/frame identities must be unique")
        for camera in self.cameras:
            model = scopes.get(scope_parts(camera.scope))
            if model is None:
                raise ValueError("camera model scope is not registered")
            if model.derivation is not None and not any(
                item.child_camera_id == camera.camera_id
                and item.child_calibration_sha256 == camera.calibration_sha256
                for item in model.derivation.camera_correspondence
            ):
                raise ValueError("derived camera requires explicit calibration correspondence")
        for frame in self.frames:
            registered = cameras.get(frame.camera_ref)
            if registered is None or registered.scope != frame.scope or (
                registered.camera_id != frame.camera_id
            ):
                raise ValueError("media frame camera/scope is not registered")
            calibration = registered.calibration or registered.affine_calibration
            if calibration is not None and (
                frame.width != calibration.width or frame.height != calibration.height
            ):
                raise ValueError("media dimensions must match scoped calibration")
        return self

    @property
    def sha256(self) -> str:
        return content_hash(self.model_dump(mode="json"))


class RegistryStore:
    """Immutable catalog lookup and verified media bytes; no directory scanning."""

    def __init__(self, registry: LocationRegistry, media_root: Path):
        self.registry = registry
        self.media_root = media_root.resolve()

    def resolve_place(self, name: str) -> tuple[LocationModel, ...]:
        folded = name.casefold()
        return tuple(item for item in self.registry.models if folded in {
            item.scope.place_id.casefold(), item.display_name.casefold(),
            *(alias.casefold() for alias in item.aliases),
        })

    def list_cameras(self, scope: ResourceScope) -> tuple[CameraEntry, ...]:
        return tuple(item for item in self.registry.cameras if item.scope == scope)

    def query_frames(self, scope: ResourceScope, *, camera_id: str | None = None,
                     time_range: tuple[float, float] | None = None) -> tuple[MediaFrame, ...]:
        if time_range is not None:
            if len(time_range) != 2 or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0 for value in time_range
            ) or time_range[1] < time_range[0]:
                raise ValueError("invalid time range")
        return tuple(item for item in self.registry.frames if item.scope == scope
                     and (camera_id is None or item.camera_id == camera_id)
                     and (time_range is None or time_range[0] <= item.timestamp <= time_range[1]))

    def get_frame(self, scope: ResourceScope, media_ref: str) -> MediaFrame:
        for frame in self.registry.frames:
            if frame.scope == scope and frame.media_ref == media_ref:
                return frame
        raise KeyError("resource unavailable")

    def media_bytes(self, scope: ResourceScope, media_ref: str) -> bytes:
        frame = self.get_frame(scope, media_ref)
        path = self.media_root.joinpath(*safe_relative_path(frame.relative_path).parts).resolve()
        if not path.is_relative_to(self.media_root) or not path.is_file():
            raise ValueError("media unavailable")
        data = path.read_bytes()
        if len(data) != frame.size_bytes or hashlib.sha256(data).hexdigest() != frame.sha256:
            raise ValueError("media integrity mismatch")
        return data
