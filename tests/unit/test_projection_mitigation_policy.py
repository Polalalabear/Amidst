"""Pilot confidence/rejection preserve strict GT-free projection contracts."""

from __future__ import annotations

import builtins
import importlib.util
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from amidst.datasets.pilot import PilotInferenceContext
from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import GapReason, ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import InverseProjectionService

_PATH = Path(__file__).parents[2] / "scripts" / "projection_mitigation_policy.py"
_SPEC = importlib.util.spec_from_file_location("projection_mitigation_policy_test", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
policy = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = policy
_SPEC.loader.exec_module(policy)


def camera(**changes: Any) -> Camera:
    return Camera.model_validate(
        {
            "camera_id": "front",
            "camera_to_world": np.eye(4).tolist(),
            "fx": 640,
            "fy": 640,
            "cx": 640,
            "cy": 360,
            "width": 1280,
            "height": 720,
            "clip_start": 0.01,
            "clip_end": 1000,
            "floor_id": "1F",
        }
        | changes
    )


def plane(**changes: Any) -> Plane:
    return Plane.model_validate(
        {
            "plane_id": "landmark",
            "floor_id": "1F",
            "zone_id": "AREA_ROOM",
            "point": (0, 0, -100),
            "normal": (0, 0, 1),
        }
        | changes
    )


def frame(**changes: Any) -> ObservationFrame:
    return ObservationFrame.model_validate(
        {
            "frame_id": 3,
            "timestamp": 0.6,
            "target_id": "synthetic_pixel",
            "camera_id": "front",
            "status": VisibilityStatus.OBSERVED,
            "point_2d": (700, 400),
            "provenance": Provenance.OBSERVED,
        }
        | changes
    )


def diagnostics(gain: float, incidence: float) -> dict:
    return {
        "status": "ACCEPTED",
        "geometry": {"normalized_incidence": incidence},
        "jacobian": {"max_gain_bu_per_px": gain},
    }


def context(**changes: Any) -> PilotInferenceContext:
    return PilotInferenceContext.model_validate(
        {
            "label": policy.LABEL,
            "data_kind": "SYNTHETIC",
            "site_id": "room",
            "source_id": "source",
            "spatial_context_id": "room_context",
            "source_asset_sha256": "a" * 64,
            "observations_sha256": "b" * 64,
            "cameras": [camera(), camera(camera_id="rear")],
            "plane": plane(),
            "zone": {
                "floor_id": "1F",
                "zone_id": "AREA_ROOM",
                "walkable_object_id": "WALK_ROOM",
                "bounds_min": (0, 0, -200),
                "bounds_max": (100, 100, 0),
                "authority": "ANNOTATION_AABB_ONLY_PROVISIONAL",
            },
        }
        | changes
    )


def receipt(**changes: Any) -> Any:
    return policy.LocalPlaneReceipt.model_validate(
        {
            "site_id": "room",
            "source_asset_sha256": "a" * 64,
            "floor_id": "1F",
            "zone_id": "AREA_ROOM",
            "mesh_object_id": "independent_probe_mesh",
            "independent_mesh_probe_xy": (10, 20),
            "physical_floor_z": -150.05,
            "physical_floor_normal": (0, 0, -1),
            "foot_clearance_units": 0.05,
            "landmark_offset_units": 50,
        }
        | changes
    )


def test_fast_diagnostics_match_previous_analytic_and_actual_service() -> None:
    source_camera, source_plane, source_frame = camera(), plane(), frame()
    inputs = [item.model_dump(mode="json") for item in (source_camera, source_plane, source_frame)]
    result = policy.diagnose_sample(source_camera, source_plane, source_frame)
    reference = policy._conditioning().diagnose_projection(
        source_camera, source_plane, source_frame
    )
    assert result["projected_point"] == reference["baseline_projected_point"]
    assert result["projected_point"]["provenance"] == "PROJECTED"
    assert result["service_quality"] == reference["geometry"]["service_projection_quality"]
    np.testing.assert_allclose(
        result["jacobian"]["analytic_bu_per_px"],
        reference["jacobian"]["analytic_scene_units_per_pixel"],
        atol=1e-13,
    )
    assert (
        result["jacobian"]["max_gain_bu_per_px"]
        == reference["jacobian"]["max_scene_units_per_pixel"]
    )
    assert result["geometry"]["camera_point_distance_bu"] == pytest.approx(
        reference["geometry"]["camera_point_euclidean_distance_scene_units"]
    )
    assert result["geometry"]["intersection_distance_bu"] == pytest.approx(
        reference["geometry"]["intersection_euclidean_distance_scene_units"]
    )
    assert result["geometry"]["axial_projected_depth_bu"] == pytest.approx(100)
    assert result["geometry"]["signed_unnormalized_denominator"] == -1
    assert result["ground_truth_used"] is False
    assert result["source_camera_or_plane_modified"] is False
    assert inputs == [
        item.model_dump(mode="json") for item in (source_camera, source_plane, source_frame)
    ]


def test_normal_sign_is_preserved_and_does_not_change_gain_or_point() -> None:
    positive = policy.diagnose_sample(camera(), plane(), frame())
    negative = policy.diagnose_sample(camera(), plane(normal=(0, 0, -1)), frame())
    assert negative["geometry"]["signed_unnormalized_denominator"] == 1
    assert positive["geometry"]["signed_unnormalized_denominator"] == -1
    assert positive["projected_point"] == negative["projected_point"]
    assert positive["jacobian"] == negative["jacobian"]
    assert positive["confidence"] == negative["confidence"]


def test_distance_and_grazing_conditioning_monotonically_reduce_confidence() -> None:
    central_frame = frame(point_2d=(640, 360))
    near = policy.diagnose_sample(camera(), plane(point=(0, 0, -100)), central_frame)
    far = policy.diagnose_sample(camera(), plane(point=(0, 0, -800)), central_frame)
    assert far["jacobian"]["max_gain_bu_per_px"] == pytest.approx(
        near["jacobian"]["max_gain_bu_per_px"] * 8
    )
    assert far["confidence"]["confidence_score"] < near["confidence"]["confidence_score"]
    gains, confidence = [], []
    for incidence in (1, 0.2, 0.1, 0.05, 0.01):
        normal = (math.sqrt(1 - incidence**2), 0, incidence)
        result = policy.diagnose_sample(
            camera(), plane(point=(0, 0, -300), normal=normal), central_frame
        )
        gains.append(result["jacobian"]["max_gain_bu_per_px"])
        confidence.append(result["confidence"]["confidence_score"])
        assert result["geometry"]["normalized_incidence"] == pytest.approx(incidence)
        assert result["geometry"]["conditioning_indicator"] == pytest.approx(1 / incidence)
    assert gains == sorted(gains)
    assert confidence == sorted(confidence, reverse=True)


@pytest.mark.parametrize(
    ("gain", "incidence", "low", "standard", "extreme"),
    [
        (5, 0.2, False, True, True),
        (5.00001, 0.2, True, True, True),
        (5, 0.19999, True, True, True),
        (10, 0.1, True, True, True),
        (10.00001, 0.1, True, False, True),
        (10, 0.09999, True, False, True),
        (20, 0.05, True, False, True),
        (20.00001, 0.05, True, False, False),
        (20, 0.04999, True, False, False),
    ],
)
def test_review_and_rejection_boundaries_are_strict_and_predeclared(
    gain: float, incidence: float, low: bool, standard: bool, extreme: bool
) -> None:
    diagnostic = diagnostics(gain, incidence)
    baseline = policy.classify(diagnostic)
    assert baseline["accepted"] is True
    assert baseline["low_confidence"] is low
    assert policy.classify(diagnostic, rejection_mode="STANDARD")["accepted"] is standard
    assert policy.classify(diagnostic, rejection_mode="EXTREME_ONLY")["accepted"] is extreme
    expected = min(1, incidence / 0.2) / (1 + (gain * 0.002 / 0.02) ** 2)
    assert baseline["confidence_score"] == pytest.approx(expected)
    assert baseline["confidence_interpretation"] == "NONPROBABILISTIC_ENGINEERING_HEURISTIC"


def test_rejection_leaves_original_projected_evidence_untouched() -> None:
    normal = (math.sqrt(1 - 0.04**2), 0, 0.04)
    result = policy.diagnose_sample(camera(), plane(normal=normal), frame(point_2d=(640, 360)))
    original = result["projected_point"].copy()
    classification = policy.classify(result, rejection_mode="STANDARD")
    assert classification["accepted"] is False
    assert result["projected_point"] == original
    assert original["provenance"] == "PROJECTED"
    assert policy.classify(result)["accepted"] is True


def test_gap_preserves_no_projection_instead_of_fabricating_confidence() -> None:
    gap = frame(
        status=VisibilityStatus.GAP,
        point_2d=None,
        provenance=None,
        gap_reason=GapReason.OCCLUDED,
    )
    result = policy.diagnose_sample(camera(), plane(), gap)
    assert result["status"] == "REJECTED"
    assert result["failure"] == "FRAME_NOT_OBSERVED"
    assert result["projected_point"] is None
    assert result["geometry"] is None
    assert result["confidence"]["label"] == "SERVICE_REJECTED"
    assert result["confidence"]["confidence_score"] is None


@pytest.mark.parametrize("contract", ["camera", "plane", "frame", "policy"])
def test_hidden_gt_fields_on_unchecked_models_fail_closed(contract: str) -> None:
    models = {
        "camera": camera(),
        "plane": plane(),
        "frame": frame(),
        "policy": policy.ConditioningPolicy(),
    }
    poisoned = models[contract].model_copy(update={"gt_position": (999, 999, 999)})
    models[contract] = poisoned
    with pytest.raises(ValueError, match="fields outside"):
        policy.diagnose_sample(
            models["camera"], models["plane"], models["frame"], policy=models["policy"]
        )


def test_ground_truth_provenance_cannot_bypass_observation_contract() -> None:
    hidden = frame().model_copy(update={"provenance": Provenance.GROUND_TRUTH})
    with pytest.raises(ValueError, match="contract"):
        policy.diagnose_sample(camera(), plane(), hidden)


def test_policies_are_frozen_and_cannot_be_trained_from_unknown_fields() -> None:
    current = policy.ConditioningPolicy()
    with pytest.raises(ValidationError, match="frozen"):
        current.reject_gain_bu_per_px = 999
    with pytest.raises(ValidationError, match="Extra inputs"):
        policy.ConditioningPolicy.model_validate({"gt_optimal_threshold": 7})
    with pytest.raises(ValidationError, match="ordering"):
        policy.ConditioningPolicy(review_gain_bu_per_px=11)
    with pytest.raises(ValueError, match="unknown"):
        policy.classify(diagnostics(10, 0.1), rejection_mode="GT_SELECTED")


@pytest.mark.parametrize(
    ("gain", "incidence"), [(math.inf, 0.2), (math.nan, 0.2), (-1, 0.2), (1, -0.1), (1, 1.1)]
)
def test_invalid_conditioning_values_do_not_get_reliable_confidence(
    gain: float, incidence: float
) -> None:
    with pytest.raises(ValueError, match="finite valid"):
        policy.classify(diagnostics(gain, incidence))


def test_helpers_perform_no_evidence_or_evaluation_file_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy._conditioning()

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("pure policy unexpectedly opened an evidence or evaluation file")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    result = policy.diagnose_sample(camera(), plane(), frame())
    assert result["status"] == "ACCEPTED"
    assert policy.bind_local_landmark_plane(context(), receipt()).point == (10, 20, -100)


def test_local_receipt_reanchors_same_plane_without_approving_mesh_authority() -> None:
    original = context()
    local_receipt = receipt()
    local = policy.bind_local_landmark_plane(original, local_receipt)
    assert local.point == (10, 20, -100)
    assert local.plane_id == original.plane.plane_id
    assert local.normal == original.plane.normal
    assert local.floor_id == original.plane.floor_id
    assert local.zone_id == original.plane.zone_id
    before = InverseProjectionService(camera(), original.plane).project_frame(frame())
    after = InverseProjectionService(camera(), local).project_frame(frame())
    assert before == after
    assert original.plane.point == (0, 0, -100)
    assert local_receipt.purpose == "PILOT_DIAGNOSTIC_ONLY"
    assert not hasattr(local_receipt, "surface_authority")
    reversed_normal = context(plane=plane(normal=(0, 0, -1)))
    assert policy.bind_local_landmark_plane(reversed_normal, receipt()).normal == (0, 0, -1)


@pytest.mark.parametrize(
    "changes",
    [
        {"source_asset_sha256": "c" * 64},
        {"site_id": "other_site"},
        {"floor_id": "2F"},
        {"zone_id": "AREA_OTHER"},
    ],
)
def test_local_receipt_source_site_floor_zone_mismatch_rejected(changes: dict) -> None:
    with pytest.raises(ValueError, match="source/site/floor/zone"):
        policy.bind_local_landmark_plane(context(), receipt(**changes))


def test_floor_surface_cannot_replace_body_landmark_plane() -> None:
    with pytest.raises(ValueError, match="body offset differs"):
        policy.bind_local_landmark_plane(context(), receipt(landmark_offset_units=0))
    with pytest.raises(ValueError, match="body offset differs"):
        policy.bind_local_landmark_plane(context(), receipt(physical_floor_z=-160))
    with pytest.raises(ValueError, match="outside"):
        policy.bind_local_landmark_plane(context(), receipt(independent_mesh_probe_xy=(-10, 20)))
    with pytest.raises(ValidationError, match="horizontal"):
        receipt(physical_floor_normal=(0.6, 0, 0.8))


def test_local_binding_rejects_hidden_gt_and_nonhorizontal_context() -> None:
    hidden = receipt().model_copy(update={"gt_position": (10, 20, -100)})
    with pytest.raises(ValueError, match="fields outside"):
        policy.bind_local_landmark_plane(context(), hidden)
    bad_context = context().model_copy(update={"ground_truth": [1, 2, 3]})
    with pytest.raises(ValueError, match="fields outside"):
        policy.bind_local_landmark_plane(bad_context, receipt())
    with pytest.raises(ValueError, match="horizontal"):
        policy.bind_local_landmark_plane(context(plane=plane(normal=(0.6, 0, 0.8))), receipt())


def test_finite_extreme_gain_saturates_score_without_numerical_overflow() -> None:
    result = policy.classify(diagnostics(1e308, 0.2), rejection_mode="EXTREME_ONLY")
    assert result["confidence_score"] == 0
    assert result["accepted"] is False
    assert math.isfinite(result["linearized_point_uncertainty_bu"])


@pytest.mark.parametrize("invalid", [True, "10", None])
def test_nonnumeric_diagnostic_gain_is_rejected(invalid: Any) -> None:
    with pytest.raises(ValueError, match="finite valid"):
        policy.classify(diagnostics(invalid, 0.2))
