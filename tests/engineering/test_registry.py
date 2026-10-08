"""Resource identity, unit authority and media-containment tests."""

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.engineering.registry import (
    IDENTITY4,
    CameraCorrespondence,
    CameraEntry,
    ClockBinding,
    CoordinateBinding,
    LocationModel,
    LocationRegistry,
    MediaFrame,
    ModelDerivation,
    PixelPlaneCalibration,
    RegistryStore,
    ResourceScope,
    content_hash,
    opaque_ref,
    scope_parts,
)


def scope(run_id: str = "run-1", place_id: str = "lab") -> ResourceScope:
    return ResourceScope(place_id=place_id, model_id="lab-model", model_revision="1",
                         run_id=run_id, source_id="synthetic-source", source_sha256="a" * 64,
                         spatial_context_id="lab-context", spatial_context_sha256="b" * 64,
                         clock_id="synthetic-seconds")


def model(binding: ResourceScope, **extra: object) -> LocationModel:
    return LocationModel(
        scope=binding, display_name="Simulation lab", aliases=("lab",),
        coordinates=CoordinateBinding(native_units="METRES", metres_per_unit=1,
                                      normalization_policy="IDENTITY",
                                      authority="SYNTHETIC_CONFIG"),
        clock=ClockBinding(clock_id=binding.clock_id, mapping_sha256="c" * 64,
                           authority="SYNTHETIC_CONFIG"),
        authority="SYNTHETIC_CONFIG", **extra,
    )


def camera(binding: ResourceScope) -> CameraEntry:
    calibration = PixelPlaneCalibration(camera_id="CAM_A", width=320, height=240,
                                        ground_to_pixel=((38, 0, 16), (0, -8, 218)))
    return CameraEntry(scope=binding, camera_id="CAM_A",
                       camera_ref=opaque_ref("camera", *scope_parts(binding), "CAM_A"),
                       affine_calibration=calibration,
                       calibration_sha256=content_hash(calibration.model_dump(mode="json")),
                       authority="SYNTHETIC_CONFIG")


def frame(binding: ResourceScope, data: bytes = b"rgb-image") -> MediaFrame:
    digest = hashlib.sha256(data).hexdigest()
    return MediaFrame(scope=binding, camera_id="CAM_A",
                      camera_ref=opaque_ref("camera", *scope_parts(binding), "CAM_A"),
                      media_ref=opaque_ref("media", *scope_parts(binding), "CAM_A", "0", digest),
                      frame_id=0, timestamp=0, relative_path="rgb/CAM_A/000.png", sha256=digest,
                      size_bytes=len(data), width=320, height=240)


def test_valid_registry_json_roundtrip_and_namespaced_original_ids() -> None:
    one, two = scope(), scope("run-2")
    registry = LocationRegistry(models=(model(one), model(two)),
                                cameras=(camera(one), camera(two)), frames=(frame(one), frame(two)))
    assert LocationRegistry.model_validate_json(registry.model_dump_json()) == registry
    assert registry.cameras[0].camera_id == registry.cameras[1].camera_id == "CAM_A"
    assert registry.cameras[0].camera_ref != registry.cameras[1].camera_ref
    assert registry.frames[0].media_ref != registry.frames[1].media_ref
    assert len(registry.sha256) == 64


def test_place_ambiguity_empty_results_and_scoped_frame_lookup(tmp_path: Path) -> None:
    one, two = scope(), scope("run-2", "second-lab")
    registry = LocationRegistry(models=(model(one), model(two)),
                                cameras=(camera(one), camera(two)), frames=(frame(one),))
    store = RegistryStore(registry, tmp_path)
    assert len(store.resolve_place("Simulation lab")) == 2
    assert store.resolve_place("missing") == ()
    assert store.list_cameras(one) == (camera(one),)
    assert store.query_frames(one, time_range=(0, 0)) == (frame(one),)
    assert store.query_frames(two) == ()
    with pytest.raises(KeyError, match="resource unavailable"):
        store.get_frame(two, frame(one).media_ref)
    with pytest.raises(ValueError, match="time range"):
        store.query_frames(one, time_range=(2, 1))


def test_media_integrity_verifies_exact_bytes_without_source_copy(tmp_path: Path) -> None:
    binding = scope()
    item = frame(binding)
    registry = LocationRegistry(models=(model(binding),), cameras=(camera(binding),),
                                frames=(item,))
    path = tmp_path / item.relative_path
    path.parent.mkdir(parents=True)
    path.write_bytes(b"rgb-image")
    store = RegistryStore(registry, tmp_path)
    assert store.media_bytes(binding, item.media_ref) == b"rgb-image"
    path.write_bytes(b"changed!!")
    with pytest.raises(ValueError, match="integrity"):
        store.media_bytes(binding, item.media_ref)
    path.unlink()
    with pytest.raises(ValueError, match="unavailable"):
        store.media_bytes(binding, item.media_ref)


def test_media_symlink_outside_root_is_rejected(tmp_path: Path) -> None:
    binding = scope()
    item = frame(binding)
    root = tmp_path / "media"
    root.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"rgb-image")
    path = root / item.relative_path
    path.parent.mkdir(parents=True)
    path.symlink_to(outside)
    store = RegistryStore(LocationRegistry(models=(model(binding),), cameras=(camera(binding),),
                                           frames=(item,)), root)
    with pytest.raises(ValueError, match="unavailable"):
        store.media_bytes(binding, item.media_ref)


@pytest.mark.parametrize("relative", ["/private/source.png", "../source.png", "rgb/../source.png",
                                      "rgb\\source.png", "./rgb/source.png"])
def test_media_rejects_noncontained_or_noncanonical_paths(relative: str) -> None:
    values = frame(scope()).model_dump()
    values["relative_path"] = relative
    with pytest.raises(ValidationError, match="contained relative path"):
        MediaFrame.model_validate(values)


def test_unknown_coverage_and_unverified_calibration_do_not_gain_authority() -> None:
    values = camera(scope()).model_dump()
    values["region_ids"] = ("area-guessed-from-name",)
    with pytest.raises(ValidationError, match="unknown coverage"):
        CameraEntry.model_validate(values)
    values = camera(scope()).model_dump()
    values["calibration_sha256"] = "d" * 64
    with pytest.raises(ValidationError, match="hash mismatch"):
        CameraEntry.model_validate(values)


def test_scoped_reference_dimensions_and_duplicate_records_fail() -> None:
    one = scope()
    values = frame(one).model_dump()
    values["scope"] = scope("different-run").model_dump()
    with pytest.raises(ValidationError, match="scope mismatch"):
        MediaFrame.model_validate(values)
    values = frame(one).model_dump()
    values["width"] = 123
    wrong_size = MediaFrame.model_validate(values)
    with pytest.raises(ValidationError, match="dimensions"):
        LocationRegistry(models=(model(one),), cameras=(camera(one),), frames=(wrong_size,))
    with pytest.raises(ValidationError, match="unique"):
        LocationRegistry(models=(model(one),), cameras=(camera(one),),
                         frames=(frame(one), frame(one)))


def test_diagnostic_annotation_is_not_trackable_rgb() -> None:
    values = frame(scope()).model_dump()
    values["annotations"] = "DIAGNOSTIC"
    with pytest.raises(ValidationError, match="diagnostic annotations"):
        MediaFrame.model_validate(values)
    values["purpose"] = "DIAGNOSTIC_REFERENCE"
    assert MediaFrame.model_validate(values).purpose == "DIAGNOSTIC_REFERENCE"


def test_source_unit_scale_cannot_be_relabelled_or_boolean() -> None:
    approved = CoordinateBinding(native_units="NATIVE_BU", metres_per_unit=0.0247,
                                 normalization_policy="SCALE_TO_METRES",
                                 authority="APPROVED_SCHOOL_V3_SCALE")
    for changes in ({"native_units": "METRES"}, {"metres_per_unit": 1},
                    {"normalization_policy": "IDENTITY"}, {"metres_per_unit": True}):
        with pytest.raises(ValidationError):
            CoordinateBinding.model_validate(approved.model_dump() | changes)


def test_derivation_requires_all_camera_calibration_correspondence() -> None:
    binding = scope()
    child = camera(binding)
    correspondence = CameraCorrespondence(parent_camera_id="CAM_PARENT", child_camera_id="CAM_A",
                                           parent_calibration_sha256="d" * 64,
                                           child_calibration_sha256=child.calibration_sha256,
                                           mapping_sha256="e" * 64)
    derivation = ModelDerivation(parent_model_id="parent", parent_revision="old",
                                 parent_source_sha256="f" * 64,
                                 derivation_manifest_sha256="0" * 64,
                                 parent_to_child_metres=IDENTITY4,
                                 camera_correspondence=(correspondence,))
    assert LocationRegistry(models=(model(binding, derivation=derivation),),
                            cameras=(child,)).models[0].derivation == derivation
    values = derivation.model_dump()
    values["camera_correspondence"][0]["child_calibration_sha256"] = "a" * 64
    bad = ModelDerivation.model_validate(values)
    with pytest.raises(ValidationError, match="correspondence"):
        LocationRegistry(models=(model(binding, derivation=bad),), cameras=(child,))


def test_affine_calibration_is_finite_invertible_and_strict() -> None:
    with pytest.raises(ValidationError, match="invertible"):
        PixelPlaneCalibration(camera_id="CAM", width=320, height=240,
                              ground_to_pixel=((1, 2, 0), (2, 4, 0)))
    with pytest.raises(ValidationError):
        PixelPlaneCalibration(camera_id="CAM", width=True, height=240,
                              ground_to_pixel=((1, 0, 0), (0, 1, 0)))
