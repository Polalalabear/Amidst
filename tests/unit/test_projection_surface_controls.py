"""Synthetic E/F contracts preserve source authority and multiple hypotheses."""

import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame

_SCRIPT = Path(__file__).parents[2] / "scripts" / "projection_surface_controls.py"
_SPEC = importlib.util.spec_from_file_location("projection_surface_controls", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
controls = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(controls)


def _inputs():
    data = controls.synthetic_surface_controls()
    example = data["controls"]["unique_surface"]
    binding = controls.SyntheticSurfaceBinding.model_validate(example["binding"])
    camera = Camera(
        camera_id="test_camera", width=640, height=480, fx=320, fy=320, cx=320, cy=240,
        floor_id=binding.floor_id,
        camera_to_world=((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
    )
    frame = ObservationFrame(
        frame_id=0, timestamp=0, target_id="test_pixel", camera_id=camera.camera_id,
        status="OBSERVED", point_2d=(320, 240), provenance="OBSERVED",
    )
    surface = controls.SyntheticSurface(
        surface_id="test_surface", source_sha256=binding.source_sha256,
        floor_id=binding.floor_id, target_reference="FOOTPOINT",
        plane_point=(0, 0, -10), plane_normal=(0, 0, 1),
        footprint_min=(-1, -1, -10), footprint_max=(1, 1, -10),
        semantic_authority="APPROVED", physical_authority="APPROVED",
        floor_authority="APPROVED", scale_authority="APPROVED",
        approval_id="EXPLICIT_SYNTHETIC_CONFIG",
    )
    return {"camera": camera, "frame": frame, "binding": binding, "surfaces": (surface,)}


def test_exactly_five_toy_controls_do_not_claim_school_efficacy():
    result = controls.synthetic_surface_controls()
    assert result["scope"] == "SYNTHETIC_FIXTURE_ONLY"
    assert result["control_count"] == 5
    assert result["actual_school_E_F"] == "UNAVAILABLE_AUTHORITY"
    assert result["ground_truth_inputs"] is result["graph_integration"] is False
    assert {k: v["candidate_count"] for k, v in result["controls"].items()} == {
        "unique_surface": 1, "multiple_surfaces": 2, "review_only": 0,
        "wrongsource": 0, "wrongtargetreference": 0,
    }


def test_unique_hit_has_projected_provenance_and_finite_bound_point():
    result = controls.project_surface_candidates(**_inputs())
    assert result["unique_surface_status"] == "UNIQUE_APPROVED_HIT"
    assert result["unique_projection"]["world_position"] == [0, 0, -10]
    assert result["unique_projection"]["provenance"] == "PROJECTED"


def test_all_hits_retained_without_nearest_or_gt_selection():
    inputs = _inputs()
    first = inputs["surfaces"][0]
    # The lexically first surface is further away; it is not a best/nearest choice.
    far = controls.SyntheticSurface.model_validate(first.model_dump() | {
        "surface_id": "a_further_surface", "plane_point": (0, 0, -20),
        "footprint_min": (-1, -1, -20), "footprint_max": (1, 1, -20),
    })
    inputs["surfaces"] = (first, far)
    result = controls.project_surface_candidates(**inputs)
    inputs["surfaces"] = (far, first)
    assert result == controls.project_surface_candidates(**inputs)
    assert result["candidate_count"] == 2
    assert result["unique_projection"] is None
    assert [h["surface_id"] for h in result["projection_hypotheses"]] == [
        "a_further_surface", "test_surface",
    ]
    assert all(h["projected_point"]["provenance"] == "PROJECTED"
               for h in result["projection_hypotheses"])


@pytest.mark.parametrize("changes,reason", [
    ({"source_sha256": "b" * 64}, "SOURCE_BINDING_MISMATCH"),
    ({"floor_id": "other_floor"}, "FLOOR_BINDING_MISMATCH"),
    ({"semantic_authority": "HIGH_CONFIDENCE"}, "SEMANTIC_AUTHORITY_UNAPPROVED"),
    ({"physical_authority": "HUMAN_REVIEW"}, "PHYSICAL_AUTHORITY_UNAPPROVED"),
    ({"floor_authority": "HUMAN_REVIEW"}, "FLOOR_AUTHORITY_UNAPPROVED"),
    ({"scale_authority": "HUMAN_REVIEW"}, "SCALE_AUTHORITY_UNAPPROVED"),
    ({"target_reference": "BODY_LANDMARK"}, "TARGET_REFERENCE_MISMATCH_OR_OFFSET_UNAPPROVED"),
])
def test_refuse_unapproved_or_mismatched_surface(changes, reason):
    inputs = _inputs()
    original = inputs["surfaces"][0]
    inputs["surfaces"] = (
        controls.SyntheticSurface.model_validate(original.model_dump() | changes),
    )
    result = controls.project_surface_candidates(**inputs)
    assert result["candidate_count"] == 0
    assert reason in result["surface_decisions"][0]["reasons"]


def test_landmark_substitution_requires_explicit_bound_offset():
    inputs = _inputs()
    binding = inputs["binding"]
    inputs["binding"] = controls.SyntheticSurfaceBinding.model_validate(binding.model_dump() | {
        "target_reference": "BODY_LANDMARK",
    })
    assert controls.project_surface_candidates(**inputs)["candidate_count"] == 0
    offset = controls.SyntheticLandmarkOffset(
        source_sha256=binding.source_sha256, floor_id=binding.floor_id,
        offset=(0, 0, 2), authority="APPROVED", approval_id="SYNTHETIC_OFFSET_CONFIG",
    )
    result = controls.project_surface_candidates(**inputs, offsets=(offset,))
    assert result["candidate_count"] == 1
    assert result["unique_projection"]["world_position"] == [0, 0, -8]
    assert result["projection_hypotheses"][0]["applied_authorized_offset"] == [0, 0, 2]
    wrong_source = controls.SyntheticLandmarkOffset.model_validate(offset.model_dump() | {
        "source_sha256": "b" * 64,
    })
    result = controls.project_surface_candidates(**inputs, offsets=(wrong_source,))
    assert result["candidate_count"] == 0


def test_duplicate_offset_authority_does_not_choose_one_conversion():
    inputs = _inputs()
    binding = inputs["binding"]
    inputs["binding"] = controls.SyntheticSurfaceBinding.model_validate(binding.model_dump() | {
        "target_reference": "BODY_LANDMARK",
    })
    offset = controls.SyntheticLandmarkOffset(
        source_sha256=binding.source_sha256, floor_id=binding.floor_id,
        offset=(0, 0, 2), authority="APPROVED", approval_id="SYNTHETIC_OFFSET_CONFIG",
    )
    result = controls.project_surface_candidates(**inputs, offsets=(offset, offset))
    assert result["candidate_count"] == 0


def test_footprint_is_not_replaced_by_infinite_plane():
    inputs = _inputs()
    original = inputs["surfaces"][0]
    inputs["surfaces"] = (controls.SyntheticSurface.model_validate(original.model_dump() | {
        "footprint_min": (1, -1, -10), "footprint_max": (2, 1, -10),
    }),)
    result = controls.project_surface_candidates(**inputs)
    assert result["candidate_count"] == 0
    assert result["surface_decisions"][0]["reasons"] == ["OUTSIDE_DECLARED_FOOTPRINT"]


@pytest.mark.parametrize("changes", [
    {"footprint_min": (float("nan"), -1, -10)},
    {"footprint_max": (float("inf"), 1, -10)},
    {"footprint_min": (2, -1, -10)},
    {"footprint_min": (1, -1, -10)},
    {"plane_normal": (0, 0, 0)},
    {"approval_id": None},
    {"ground_truth": [0, 0, -10]},
    {"provenance": "GROUND_TRUTH"},
    {"scope": "APPROVED_SCHOOL"},
])
def test_descriptor_validation_blocks_nonfinite_degenerate_gt_and_school_claim(changes):
    surface = _inputs()["surfaces"][0]
    with pytest.raises(ValidationError):
        controls.SyntheticSurface.model_validate(surface.model_dump() | changes)


def test_unchecked_descriptor_mutation_cannot_inject_gt():
    inputs = _inputs()
    original = inputs["surfaces"][0]
    inputs["surfaces"] = (original.model_copy(update={"ground_truth": (0, 0, -10)}),)
    with pytest.raises(ValueError, match="outside its declared contract"):
        controls.project_surface_candidates(**inputs)
    inputs["surfaces"] = (original.model_copy(update={"physical_authority": "GROUND_TRUTH"}),)
    with pytest.raises(ValueError):
        controls.project_surface_candidates(**inputs)


def test_input_frame_cannot_carry_gt_provenance():
    inputs = _inputs()
    inputs["frame"] = inputs["frame"].model_copy(update={"provenance": Provenance.GROUND_TRUTH})
    with pytest.raises(ValueError):
        controls.project_surface_candidates(**inputs)


def test_duplicate_ids_and_camera_floor_mismatch_fail_closed():
    inputs = _inputs()
    inputs["surfaces"] = inputs["surfaces"] * 2
    with pytest.raises(ValueError, match="duplicate"):
        controls.project_surface_candidates(**inputs)
    inputs = _inputs()
    inputs["camera"] = inputs["camera"].model_copy(update={"floor_id": "other_floor"})
    with pytest.raises(ValueError, match="camera floor"):
        controls.project_surface_candidates(**inputs)


def test_no_file_reads_and_deterministic_json(monkeypatch):
    def forbid_reads(*args, **kwargs):
        raise AssertionError("synthetic controls must not read GT or scene files")
    monkeypatch.setattr(Path, "read_text", forbid_reads)
    monkeypatch.setattr(Path, "read_bytes", forbid_reads)
    first = controls.synthetic_surface_controls()
    second = controls.synthetic_surface_controls()
    assert json.dumps(first, sort_keys=True, allow_nan=False) == json.dumps(
        second, sort_keys=True, allow_nan=False,
    )
