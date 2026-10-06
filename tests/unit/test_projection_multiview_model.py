"""Additive exact-time triangulation preserves evidence and fails closed without GT."""

from __future__ import annotations

import builtins
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from amidst.datasets.pilot import PilotInferenceContext, PilotZoneContext
from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import GapReason, ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.simulation.virtual_camera import project_world

SCRIPT = Path(__file__).parents[2] / "scripts" / "projection_multiview_model.py"
SPEC = importlib.util.spec_from_file_location("projection_multiview_tests", SCRIPT)
assert SPEC and SPEC.loader
model = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(model)


def camera(identity: str, x: float, **changes: Any) -> Camera:
    matrix = np.eye(4)
    matrix[0, 3] = x
    return Camera.model_validate({
        "camera_id": identity, "camera_to_world": matrix.tolist(),
        "fx": 500, "fy": 510, "cx": 640, "cy": 360, "width": 1280, "height": 720,
        "clip_start": .1, "clip_end": 1000, "floor_id": "DIAGNOSTIC",
    } | changes)


def context(cameras: tuple[Camera, ...] | None = None) -> PilotInferenceContext:
    cameras = cameras if cameras is not None else (camera("a", -2), camera("b", 2))
    return PilotInferenceContext(
        label="PILOT / SYNTHETIC SAMPLE", data_kind="SYNTHETIC", site_id="fixture",
        source_id="fixture-exact-time", spatial_context_id="local-fixture-context",
        source_asset_sha256="a" * 64, observations_sha256="b" * 64, cameras=cameras,
        plane=Plane(plane_id="unused-plane", point=(0, 0, -10), normal=(0, 0, 1),
                    floor_id="DIAGNOSTIC", zone_id="LOCAL"),
        zone=PilotZoneContext(
            floor_id="DIAGNOSTIC", zone_id="LOCAL", walkable_object_id="fixture-only",
            bounds_min=(-20, -20, -1500), bounds_max=(20, 20, -1),
            authority="ANNOTATION_AABB_ONLY_PROVISIONAL",
        ),
    )


def frames(
    binding: PilotInferenceContext, position: tuple[float, float, float] = (0, .4, -10),
) -> tuple[ObservationFrame, ...]:
    result = []
    for cam in binding.cameras:
        projection = project_world(cam, position)
        assert projection.point_2d is not None
        result.append(ObservationFrame(
            frame_id=5, timestamp=1., target_id="synthetic-target", camera_id=cam.camera_id,
            status=VisibilityStatus.OBSERVED, point_2d=projection.point_2d,
            provenance=Provenance.OBSERVED,
        ))
    return tuple(result)


def changed(frame: ObservationFrame, **updates: Any) -> ObservationFrame:
    return ObservationFrame.model_validate(frame.model_dump(mode="python") | updates)


def test_exact_point_has_strict_additive_provenance_and_no_plane_identity() -> None:
    binding = context()
    result = model.triangulate_exact_time(binding, frames(binding))
    assert result["status"] == "ACCEPTED"
    assert result["method"] == "EXACT_TIME_MULTI_VIEW_TRIANGULATION"
    assert result["ground_truth_used"] is False
    assert result["pair_selected_by_ground_truth"] is False
    assert result["hypotheses_selected_by_ground_truth"] is False
    hypothesis, = result["hypotheses"]
    np.testing.assert_allclose(hypothesis["world_position"], (0, .4, -10), atol=2e-14)
    assert hypothesis["provenance"] == "PROJECTED_DIAGNOSTIC"
    assert hypothesis["model_kind"] == "MULTIVIEW"
    assert "plane_id" not in hypothesis
    assert hypothesis["ray_miss_distance_scene_units"] < 1e-14
    assert all(row["residual_pixels"] < 2e-13 for row in hypothesis["reprojections"])
    assert all(ref["provenance"] == "OBSERVED" for ref in hypothesis["evidence_refs"])
    json.dumps(result, allow_nan=False)
    assert model.MultiViewResult.model_validate(result).model_dump(mode="json") == result


def test_all_pairs_survive_without_ranking_and_permutation_is_deterministic() -> None:
    binding = context((camera("c", 0), camera("a", -2), camera("b", 2)))
    samples = frames(binding)
    result = model.triangulate_exact_time(binding, samples)
    pairs = [row["camera_ids"] for row in result["hypotheses"]]
    assert pairs == [["a", "b"], ["a", "c"], ["b", "c"]]
    reordered = PilotInferenceContext.model_validate(
        binding.model_dump(mode="python") | {"cameras": tuple(reversed(binding.cameras))}
    )
    assert result == model.triangulate_exact_time(reordered, tuple(reversed(samples)))
    assert result == model.triangulate_exact_time(binding, samples)


def test_noisy_rays_preserve_pixel_evidence_and_report_nonzero_residuals() -> None:
    binding = context()
    first, second = frames(binding)
    assert first.point_2d is not None
    noisy = changed(first, point_2d=(first.point_2d[0] + .25, first.point_2d[1] + .1))
    result = model.triangulate_exact_time(binding, (noisy, second))
    hypothesis, = result["hypotheses"]
    assert result["status"] == "ACCEPTED"
    assert hypothesis["world_position"] != [0, .4, -10]
    assert hypothesis["ray_miss_distance_scene_units"] > 0
    assert any(row["residual_pixels"] > 0 for row in hypothesis["reprojections"])
    assert hypothesis["evidence_refs"][0]["point_2d"] == list(noisy.point_2d)


def test_pilot_plane_changes_do_not_change_multiview_coordinates_or_identity() -> None:
    binding = context()
    other_plane = binding.plane.model_copy(update={"point": (0, 0, -900)})
    updated = binding.model_copy(update={"plane": other_plane})
    assert model.triangulate_exact_time(binding, frames(binding)) == (
        model.triangulate_exact_time(updated, frames(binding))
    )


def test_source_or_calibration_changes_change_hypothesis_identity() -> None:
    binding = context()
    first = model.triangulate_exact_time(binding, frames(binding))["hypotheses"][0]
    updated = binding.model_copy(update={"source_id": "independent-fixture"})
    second = model.triangulate_exact_time(updated, frames(updated))["hypotheses"][0]
    assert first["hypothesis_id"] != second["hypothesis_id"]
    calibrated = binding.model_copy(update={
        "cameras": (binding.cameras[0].model_copy(update={"fx": 500.01}), binding.cameras[1]),
    })
    third = model.triangulate_exact_time(calibrated, frames(binding))["hypotheses"][0]
    assert first["hypothesis_id"] != third["hypothesis_id"]
    assert first["calibration_sha256"] != third["calibration_sha256"]


def test_empty_or_single_camera_evidence_does_not_fabricate_position() -> None:
    binding = context()
    none = model.triangulate_exact_time(binding, ())
    assert none["status"] == "NO_EVIDENCE" and not none["hypotheses"]
    sample = frames(binding)[0]
    one = model.triangulate_exact_time(binding, (sample,))
    assert one["status"] == "REJECTED" and not one["hypotheses"]
    assert one["rejection_reason"] == "INSUFFICIENT_EXACT_TIME_EVIDENCE"


def test_gap_recovery_is_not_filled_from_other_camera_or_time() -> None:
    binding = context()
    first, second = frames(binding)
    gap = changed(second, status="GAP", point_2d=None, provenance=None,
                  gap_reason=GapReason.OCCLUDED)
    result = model.triangulate_exact_time(binding, (first, gap))
    assert result["status"] == "REJECTED" and not result["hypotheses"]
    assert len(result["evidence_refs"]) == 1


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("timestamp", 1.00001, "EXACT_TIME_IDENTITY_MISMATCH"),
    ("frame_id", 6, "EXACT_TIME_IDENTITY_MISMATCH"),
    ("target_id", "other", "TARGET_MISMATCH"),
    ("camera_id", "unbound", "CAMERA_NOT_IN_SOURCE_BINDING"),
    ("data_kind", "REAL_CV", "SOURCE_DATA_KIND_MISMATCH"),
])
def test_identity_and_binding_mismatch_fail_closed(field: str, value: Any, reason: str) -> None:
    binding = context()
    first, second = frames(binding)
    result = model.triangulate_exact_time(binding, (first, changed(second, **{field: value})))
    assert result["status"] == "REJECTED"
    assert result["rejection_reason"] == reason
    assert not result["hypotheses"]


def test_duplicate_camera_evidence_is_rejected() -> None:
    binding = context()
    first = frames(binding)[0]
    result = model.triangulate_exact_time(binding, (first, first))
    assert result["rejection_reason"] == "DUPLICATE_CAMERA_EVIDENCE"


@pytest.mark.parametrize("offset", [0., .00001])
def test_parallel_and_nearly_parallel_rays_fail_closed(offset: float) -> None:
    binding = context()
    first, second = frames(binding)
    parallel = (changed(first, point_2d=(640, 360)),
                changed(second, point_2d=(640 + offset, 360)))
    result = model.triangulate_exact_time(binding, parallel)
    assert result["status"] == "REJECTED" and not result["hypotheses"]
    assert result["pair_rejections"][0]["reason"] == "INSUFFICIENT_PARALLAX"


def test_antiparallel_rays_fail_closed_instead_of_reporting_good_parallax() -> None:
    rotation = np.diag((-1., 1., -1., 1.))
    rotation[2, 3] = -20
    binding = context((camera("a", 0), camera("b", 0, camera_to_world=rotation.tolist())))
    result = model.triangulate_exact_time(binding, frames(binding, (0, 0, -10)))
    assert result["status"] == "REJECTED"
    assert result["pair_rejections"][0]["reason"] == "INSUFFICIENT_PARALLAX"


def test_intersection_behind_camera_is_rejected() -> None:
    binding = context()
    first, second = frames(binding)
    divergent = (changed(first, point_2d=(540, 360)), changed(second, point_2d=(740, 360)))
    result = model.triangulate_exact_time(binding, divergent)
    assert result["pair_rejections"][0]["reason"] == "INTERSECTION_BEHIND_CAMERA"
    assert not result["hypotheses"]


@pytest.mark.parametrize(("clip_start", "clip_end", "reason"), [
    (11., 1000., "NEAR_CLIPPED"), (0.1, 9., "FAR_CLIPPED"),
])
def test_triangulated_point_must_satisfy_both_camera_clip_contracts(
    clip_start: float, clip_end: float, reason: str,
) -> None:
    original = context()
    samples = frames(original)
    clipped = original.model_copy(update={
        "cameras": tuple(cam.model_copy(update={"clip_start": clip_start, "clip_end": clip_end})
                         for cam in original.cameras),
    })
    result = model.triangulate_exact_time(clipped, samples)
    assert result["pair_rejections"][0]["reason"] == reason
    assert not result["hypotheses"]


def test_outside_image_pixel_is_rejected_before_triangulation() -> None:
    binding = context()
    first, second = frames(binding)
    result = model.triangulate_exact_time(binding, (changed(first, point_2d=(1280, 360)), second))
    assert result["pair_rejections"][0]["reason"] == "PIXEL_OUTSIDE_IMAGE"
    assert not result["hypotheses"]


def test_nonrigid_camera_pose_fails_closed_without_repairing_calibration() -> None:
    binding = context()
    matrix = np.asarray(binding.cameras[0].camera_to_world).copy()
    matrix[0, 0] = 2
    invalid = binding.model_copy(update={
        "cameras": (Camera.model_validate(binding.cameras[0].model_dump()
                                      | {"camera_to_world": matrix.tolist()}),
                    binding.cameras[1]),
    })
    result = model.triangulate_exact_time(invalid, frames(binding))
    assert result["pair_rejections"][0]["reason"] == "INVALID_CAMERA_POSE"
    assert not result["hypotheses"]


def test_small_export_rotation_rounding_is_preserved_not_orthogonalized() -> None:
    binding = context()
    matrix = np.asarray(binding.cameras[0].camera_to_world).copy()
    matrix[0, 0] += 1e-7
    rounded = binding.model_copy(update={
        "cameras": (Camera.model_validate(binding.cameras[0].model_dump()
                                      | {"camera_to_world": matrix.tolist()}),
                    binding.cameras[1]),
    })
    result = model.triangulate_exact_time(rounded, frames(rounded))
    assert result["status"] == "ACCEPTED"
    np.testing.assert_allclose(result["hypotheses"][0]["world_position"], (0, .4, -10), atol=2e-14)


@pytest.mark.parametrize(
    "injection", ["frame_truth", "provenance", "context_truth", "camera_truth"],
)
def test_unchecked_provenance_or_hidden_fields_are_rejected(injection: str) -> None:
    binding = context()
    first, second = frames(binding)
    if injection == "frame_truth":
        first = first.model_copy(update={"world_position": (0, .4, -10)})
    elif injection == "provenance":
        first = first.model_copy(update={"provenance": "GROUND_TRUTH"})
    elif injection == "context_truth":
        binding = binding.model_copy(update={"truth": (0, .4, -10)})
    else:
        binding = binding.model_copy(update={"cameras": (
            binding.cameras[0].model_copy(update={"ground_truth": (0, .4, -10)}),
            binding.cameras[1],
        )})
    with pytest.raises(ValueError, match="contract|outside"):
        model.triangulate_exact_time(binding, (first, second))


def test_sidecar_forbids_hidden_truth_and_false_provenance() -> None:
    binding = context()
    result = model.triangulate_exact_time(binding, frames(binding))
    with pytest.raises(ValueError, match="Extra inputs"):
        model.MultiViewResult.model_validate(result | {"ground_truth": [0, .4, -10]})
    hypothesis = result["hypotheses"][0]
    with pytest.raises(ValueError, match="literal"):
        model.MultiViewHypothesis.model_validate(hypothesis | {"provenance": "GROUND_TRUTH"})


@pytest.mark.parametrize("angle", [0., -1., 91., float("nan"), float("inf")])
def test_invalid_parallax_policy_is_rejected(angle: float) -> None:
    binding = context()
    with pytest.raises(ValueError, match="minimum acute parallax"):
        model.triangulate_exact_time(binding, frames(binding), minimum_acute_angle_degrees=angle)


def test_inference_is_pure_no_file_read_or_hidden_simulation_input(monkeypatch: Any) -> None:
    binding = context()
    samples = frames(binding)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("projection model attempted to read a file")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    assert model.triangulate_exact_time(binding, samples)["status"] == "ACCEPTED"


def test_finite_but_overflowing_intrinsics_fail_closed() -> None:
    binding = context()
    altered = binding.model_copy(update={
        "cameras": (binding.cameras[0].model_copy(update={"fx": 1e-320}), binding.cameras[1]),
    })
    result = model.triangulate_exact_time(altered, frames(binding))
    assert result["status"] == "REJECTED"
    assert result["pair_rejections"][0]["reason"] == "NUMERICAL_FAILURE"
    assert not result["hypotheses"]
