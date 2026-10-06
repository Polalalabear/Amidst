"""The additive composer retains evidence, uses geometry only and stays provisional."""

from __future__ import annotations

import builtins
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from amidst.datasets.pilot import (
    PilotInferenceContext,
    PilotObservationExport,
    PilotZoneContext,
    project_pilot_observations,
)
from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import InverseProjectionService
from amidst.observation.aggregation import AggregationInputError
from amidst.simulation.virtual_camera import project_world

SCRIPT = Path(__file__).parents[2] / "scripts" / "phase1_projection_policy.py"
SPEC = importlib.util.spec_from_file_location("phase1_projection_composer_tests", SCRIPT)
assert SPEC and SPEC.loader
policy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = policy
SPEC.loader.exec_module(policy)


def camera(identity: str, x: float) -> Camera:
    matrix = np.eye(4)
    matrix[0, 3] = x
    return Camera(
        camera_id=identity, camera_to_world=matrix.tolist(), fx=500, fy=510,
        cx=640, cy=360, width=1280, height=720, clip_start=.1, clip_end=1000,
        floor_id="DIAGNOSTIC",
    )


def context() -> PilotInferenceContext:
    return PilotInferenceContext(
        label="PILOT / SYNTHETIC SAMPLE", data_kind="SYNTHETIC", site_id="fixture",
        source_id="source", spatial_context_id="context", source_asset_sha256="a" * 64,
        observations_sha256="b" * 64,
        cameras=(camera("a", -5), camera("b", 2), camera("c", 5)),
        plane=Plane(plane_id="landmark", point=(0, 0, -10), normal=(0, 0, 1),
                    floor_id="DIAGNOSTIC", zone_id="LOCAL"),
        zone=PilotZoneContext(
            floor_id="DIAGNOSTIC", zone_id="LOCAL", walkable_object_id="fixture",
            bounds_min=(-20, -20, -30), bounds_max=(20, 20, -1),
            authority="ANNOTATION_AABB_ONLY_PROVISIONAL",
        ),
    )


def frames(binding: PilotInferenceContext) -> tuple[ObservationFrame, ...]:
    rows = []
    for cam in binding.cameras:
        pixel = project_world(cam, (0, .4, -10)).point_2d
        assert pixel is not None
        rows.append(ObservationFrame(
            frame_id=5, timestamp=1., target_id="synthetic-target", camera_id=cam.camera_id,
            status="OBSERVED", point_2d=pixel, provenance=Provenance.OBSERVED,
        ))
    return tuple(rows)


def gap(frame: ObservationFrame) -> ObservationFrame:
    return ObservationFrame.model_validate(frame.model_dump() | {
        "status": "GAP", "point_2d": None, "provenance": None, "gap_reason": "OCCLUDED",
    })


def evidence(binding: PilotInferenceContext) -> PilotObservationExport:
    return PilotObservationExport(
        label=binding.label, data_kind="SYNTHETIC", site_id=binding.site_id,
        source_asset_sha256=binding.source_asset_sha256, frames=frames(binding),
    )


def test_multiview_priority_retains_every_pair_and_plane_point() -> None:
    binding = context()
    source = frames(binding)
    result = policy.project_exact_time(binding, source)
    assert result["method"] == "EXACT_TIME_MULTIVIEW"
    assert result["selected_camera_ids"] == ["a", "c"]
    np.testing.assert_allclose(result["selected_world_position"], (0, .4, -10), atol=1e-14)
    assert len(result["multiview"]["hypotheses"]) == 3
    assert len(result["fixed_plane_sidecars"]) == len(source) == result["observed_count"]
    assert result["evidence_rejected_by_confidence"] == 0
    for row, frame in zip(result["fixed_plane_sidecars"], source, strict=True):
        original = InverseProjectionService(
            next(cam for cam in binding.cameras if cam.camera_id == frame.camera_id), binding.plane,
        ).project_frame(frame)
        assert row["conditioning"]["projected_point"] == original.model_dump(mode="json")
    assert result["uncertainty"]["status"] == "UNAVAILABLE"
    assert result["uncertainty"]["reason"] == "MULTIVIEW_COVARIANCE_NOT_MODELED"
    assert result["state"] == "LOW_CONFIDENCE"
    assert result["graph_contract_modified"] is False
    assert result["policy_status"] == "PROVISIONAL_NOT_APPROVED_SCHOOL_CAMERA_PLANE_BINDING"
    assert result["surface_constrained_school_inference"] == "N/A / UNAVAILABLE_AUTHORITY"


def test_pair_and_input_ordering_are_deterministic() -> None:
    binding = context()
    source = frames(binding)
    expected = policy.project_exact_time(binding, source)
    reordered = PilotInferenceContext.model_validate(
        binding.model_dump() | {"cameras": tuple(reversed(binding.cameras))},
    )
    assert policy.project_exact_time(reordered, tuple(reversed(source))) == expected
    assert policy.project_exact_time(binding, source) == expected
    assert expected["selected_multiview_hypothesis_id"] == min(
        expected["multiview"]["hypotheses"],
        key=lambda row: (row["line_system_condition_number"], tuple(row["camera_ids"])),
    )["hypothesis_id"]


def test_no_pair_falls_back_and_gap_evidence_never_gets_coordinates() -> None:
    binding = context()
    first, second, third = frames(binding)
    source = (first, gap(second), gap(third))
    result = policy.project_exact_time(binding, source)
    assert result["method"] == "SINGLE_VIEW_FIXED_PLANE"
    assert result["selected_camera_ids"] == ["a"]
    assert result["multiview"]["rejection_reason"] == "INSUFFICIENT_EXACT_TIME_EVIDENCE"
    assert result["multiview_unavailable_is_inference_failure"] is False
    assert len(result["input_evidence"]) == 3
    assert result["state"] == "LOW_CONFIDENCE"
    assert result["uncertainty"]["reason"] == "PIXEL_SIGMA_NOT_DECLARED"
    assert all(row["point_2d"] is None for row in result["input_evidence"][1:])
    assert len(result["fixed_plane_sidecars"]) == 1


def test_declared_sigma_produces_only_conditional_uncertainty() -> None:
    binding = context()
    first, second, third = frames(binding)
    source = (first, gap(second), gap(third))
    result = policy.project_exact_time(
        binding, source, policy=policy.ProjectionPolicy(pixel_sigma_px=.002),
    )
    assert result["uncertainty"]["covariance_status"] == "CONDITIONAL_EXACT_PLANE"
    assert result["uncertainty"]["measurement_status"] == "UNMEASURED_ASSUMPTION"
    assert result["uncertainty"]["normal_height_uncertainty_modeled"] is False
    assert result["confidence_is_calibrated_probability"] is False
    assert result["uncertainty"]["downstream_policy_applied"] is False


def test_zero_sigma_never_claims_perfect_certainty_or_rejects_point() -> None:
    binding = context()
    first, second, third = frames(binding)
    result = policy.project_exact_time(
        binding, (first, gap(second), gap(third)),
        policy=policy.ProjectionPolicy(pixel_sigma_px=0),
    )
    assert result["uncertainty"]["use_state"] == "UNAVAILABLE_ZERO_VARIANCE"
    assert result["state"] == "LOW_CONFIDENCE"
    assert result["selected_world_position"] is not None
    assert result["evidence_rejected_by_confidence"] == 0


def test_uncertainty_review_keeps_the_same_fixed_plane_coordinates() -> None:
    binding = context()
    first, second, third = frames(binding)
    source = (first, gap(second), gap(third))
    normal = policy.project_exact_time(
        binding, source, policy=policy.ProjectionPolicy(pixel_sigma_px=.002),
    )
    review = policy.project_exact_time(
        binding, source, policy=policy.ProjectionPolicy(pixel_sigma_px=1),
    )
    assert review["uncertainty"]["use_state"] == "REVIEW_REQUIRED"
    assert review["state"] == "LOW_CONFIDENCE"
    assert review["selected_world_position"] == normal["selected_world_position"]
    assert review["input_evidence"] == normal["input_evidence"]
    assert review["observed_count"] == normal["observed_count"]
    assert review["evidence_rejected_by_confidence"] == 0


def test_policy_frames_apply_selected_pair_and_keep_original_third_camera_point() -> None:
    binding = context()
    inputs = evidence(binding)
    dataset = policy.project_policy_frames(inputs, binding)
    baseline = project_pilot_observations(inputs, binding)
    by_camera = {sample.camera_id: sample for sample in dataset.samples}
    original = {sample.camera_id: sample for sample in baseline.samples}
    for identity in ("a", "c"):
        sample = by_camera[identity]
        assert sample.projected_point.plane_id == "EXACT_TIME_MULTIVIEW_NO_PLANE_ASSUMPTION"
        assert sample.projected_point.point_id.startswith("multiview:")
        assert sample.projected_point.provenance == "PROJECTED"
        np.testing.assert_allclose(sample.projected_point.world_position, (0, .4, -10), atol=1e-14)
        assert sample.uv == original[identity].uv
        assert sample.binding == original[identity].binding
    assert by_camera["b"] == original["b"]


def test_policy_frames_fallback_is_identical_to_unchanged_service_contract() -> None:
    binding = context()
    first, second, third = frames(binding)
    inputs = PilotObservationExport.model_validate(evidence(binding).model_dump() | {
        "frames": (first, gap(second), gap(third)),
    })
    assert policy.project_policy_frames(inputs, binding) == project_pilot_observations(
        inputs, binding,
    )


@pytest.mark.parametrize("empty", [False, True])
def test_no_observed_evidence_is_explicitly_unavailable(empty: bool) -> None:
    binding = context()
    source = () if empty else tuple(gap(frame) for frame in frames(binding))
    result = policy.project_exact_time(binding, source)
    assert result["method"] == result["state"] == "UNAVAILABLE"
    assert result["selected_world_position"] is None
    assert not result["multiview"]["hypotheses"]
    assert not result["fixed_plane_sidecars"]
    assert len(result["input_evidence"]) == len(source)


def test_near_parallel_multiview_is_unavailable_but_plane_fallback_survives() -> None:
    binding = context()
    source = tuple(ObservationFrame.model_validate(frame.model_dump() | {"point_2d": (640, 360)})
                   for frame in frames(binding))
    result = policy.project_exact_time(binding, source)
    assert result["method"] == "SINGLE_VIEW_FIXED_PLANE"
    assert result["selected_camera_ids"] == ["a"]
    assert len(result["fixed_plane_sidecars"]) == 3
    assert len(result["multiview"]["pair_rejections"]) == 3
    assert result["evidence_rejected_by_confidence"] == 0


def test_invalid_geometry_retains_visible_evidence_with_no_invented_projection() -> None:
    binding = context()
    source = tuple(ObservationFrame.model_validate(frame.model_dump() | {"point_2d": (-1, 360)})
                   for frame in frames(binding))
    result = policy.project_exact_time(binding, source)
    assert result["method"] == result["state"] == "UNAVAILABLE"
    assert result["observed_count"] == len(result["input_evidence"]) == 3
    assert all(row["conditioning"]["projected_point"] is None
               for row in result["fixed_plane_sidecars"])


@pytest.mark.parametrize("changes", [
    {"frame_id": 6}, {"timestamp": 1.00001}, {"target_id": "different"},
    {"camera_id": "unknown"}, {"data_kind": "REAL_CV"},
])
def test_illegal_binding_does_not_silently_fall_back(changes: dict[str, Any]) -> None:
    binding = context()
    first, second, _ = frames(binding)
    forged = ObservationFrame.model_validate(second.model_dump() | changes)
    with pytest.raises(ValueError):
        policy.project_exact_time(binding, (first, forged))


def test_hidden_or_forged_gt_fields_fail_at_strict_boundary() -> None:
    binding = context()
    first = frames(binding)[0]
    forged = first.model_copy(update={"ground_truth": (1, 2, 3)})
    with pytest.raises(AggregationInputError):
        policy.project_exact_time(binding, (forged,))
    forged = first.model_copy(update={"provenance": "GROUND_TRUTH"})
    with pytest.raises(AggregationInputError):
        policy.project_exact_time(binding, (forged,))
    with pytest.raises(AggregationInputError):
        policy.project_exact_time(binding.model_copy(update={"gt_position": (1, 2, 3)}), (first,))
    with pytest.raises(ValidationError):
        policy.ProjectionPolicy(ground_truth=(1, 2, 3))
    with pytest.raises(AggregationInputError):
        policy.project_exact_time(binding, (first,), policy={})


def test_in_memory_policy_cannot_read_gt_or_any_files(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = context()
    source = frames(binding)
    expected = policy.project_exact_time(binding, source)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("projection inference attempted a file read")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    assert policy.project_exact_time(binding, source) == expected


def test_export_groups_only_exact_synchronization_and_keeps_every_frame() -> None:
    binding = context()
    original = evidence(binding)
    delayed = ObservationFrame.model_validate(original.frames[2].model_dump() | {
        "timestamp": 1.01, "frame_id": 6,
    })
    modified = PilotObservationExport.model_validate(original.model_dump() | {
        "frames": (*original.frames[:2], delayed),
    })
    result = policy.project_export(binding, modified)
    assert [row["method"] for row in result["rows"]] == [
        "EXACT_TIME_MULTIVIEW", "SINGLE_VIEW_FIXED_PLANE",
    ]
    assert result["frame_count"] == result["retained_evidence_count"] == 3
    reversed_input = PilotObservationExport.model_validate(modified.model_dump() | {
        "frames": tuple(reversed(modified.frames)),
    })
    assert policy.project_export(binding, reversed_input) == result


def test_export_rejects_source_mismatch_and_duplicate_identity() -> None:
    binding = context()
    original = evidence(binding)
    with pytest.raises(ValueError):
        policy.project_export(binding, original.model_copy(update={
            "source_asset_sha256": "c" * 64,
        }))
    with pytest.raises(ValueError):
        policy.project_export(binding, original.model_copy(update={
            "frames": (*original.frames, original.frames[0]),
        }))


def test_fresh_process_and_gt_poison_preserve_inference_bytes(tmp_path: Path) -> None:
    binding = context()
    observations = tmp_path / "observations.json"
    observations.write_text(evidence(binding).model_dump_json())
    binding = PilotInferenceContext.model_validate(binding.model_dump() | {
        "observations_sha256": hashlib.sha256(observations.read_bytes()).hexdigest(),
    })
    context_path = tmp_path / "projection_context.json"
    context_path.write_text(binding.model_dump_json())
    gt_path = tmp_path / "ground_truth.json"
    gt_path.write_text(json.dumps({"position": [0, .4, -10]}))
    outputs = []
    evaluation_errors = []
    for index, truth in enumerate(((0, .4, -10), (9999, -8888, 7777))):
        gt_path.write_text(json.dumps({"position": truth}))
        destination = tmp_path / f"output_{index}.json"
        completed = subprocess.run([
            sys.executable, str(SCRIPT), "--observations", str(observations),
            "--context", str(context_path), "--output", str(destination),
        ], check=False, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        outputs.append(destination.read_bytes())
        frozen = json.loads(outputs[-1])
        # The evaluation reference is read only after the fresh-process inference ends.
        reference = json.loads(gt_path.read_text())["position"]
        evaluation_errors.append(math.dist(frozen["rows"][0]["selected_world_position"], reference))
    assert outputs[0] == outputs[1]
    assert evaluation_errors[0] < 1e-12 and evaluation_errors[1] > 1000
    assert json.loads(outputs[0])["ground_truth_read"] is False


def test_cli_rejects_modified_source_evidence(tmp_path: Path) -> None:
    binding = context()
    observations = tmp_path / "observations.json"
    observations.write_text(evidence(binding).model_dump_json())
    context_path = tmp_path / "projection_context.json"
    context_path.write_text(binding.model_dump_json())
    destination = tmp_path / "output.json"
    completed = subprocess.run([
        sys.executable, str(SCRIPT), "--observations", str(observations),
        "--context", str(context_path), "--output", str(destination),
    ], check=False, capture_output=True, text=True)
    assert completed.returncode != 0
    assert "SHA-256 differs" in completed.stderr
    assert not destination.exists()
