"""Exact linear frustum exclusion, without source/semantic authority claims."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from amidst.domain.camera import Camera
from amidst.finalization.scope_inventory import (
    audit_two_sided_source_candidates,
    frustum_separating_plane,
)


def camera() -> Camera:
    return Camera(
        camera_id="SYNTHETIC_SOURCE_CAMERA",
        camera_to_world=((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)),
        fx=100, fy=100, cx=50, cy=50, width=100, height=100,
        clip_start=.1, clip_end=100, floor_id="SYNTHETIC_FLOOR",
    )


@pytest.mark.parametrize(
    "low,high,plane",
    [
        ((-1, -1, 10), (1, 1, 20), "NEAR_AXIAL_CLIP"),
        ((-1, -1, -120), (1, 1, -110), "FAR_AXIAL_CLIP"),
        ((-100, -1, -20), (-80, 1, -10), "LEFT_PIXEL_BOUNDARY"),
        ((80, -1, -20), (100, 1, -10), "RIGHT_PIXEL_BOUNDARY"),
    ],
)
def test_whole_box_outside_one_source_frustum_halfspace(low, high, plane) -> None:
    proof = frustum_separating_plane(camera(), low, high)
    assert proof is not None and proof["separating_halfspace"] == plane
    assert proof["status"] == "WHOLE_BOX_OUTSIDE_SOURCE_FRUSTUM"
    assert proof["occlusion_test_required"] is False


def test_corners_outside_different_planes_does_not_prove_whole_box_excluded() -> None:
    # The box intersects the frustum despite many individually invisible corners.
    assert frustum_separating_plane(camera(), (-100, -100, -20), (100, 100, -10)) is None


def test_frustum_inclusion_still_does_not_claim_source_occlusion_or_body_clearance() -> None:
    assert frustum_separating_plane(camera(), (-1, -1, -20), (1, 1, -10)) is None


def test_unordered_candidate_box_is_rejected() -> None:
    with pytest.raises(ValueError, match="bounds must be ordered"):
        frustum_separating_plane(camera(), (10, 0, -20), (0, 1, -10))


def test_supported_bypass_and_camera_fov_never_issue_a_physical_or_semantic_certificate() -> None:
    spec = importlib.util.spec_from_file_location(
        "synthetic_branch_support", Path(__file__).with_name("test_local_physical_scopes.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    domain = module._domain(module._contract())
    cameras = tuple(Camera(
        camera_id=identity, camera_to_world=(
            (1, 0, 0, 5 + shift), (0, 1, 0, 5), (0, 0, 1, 5), (0, 0, 0, 1),
        ), fx=100, fy=100, cx=50, cy=50, width=100, height=100,
        clip_start=.1, clip_end=100, floor_id="1F",
    ) for identity, shift in (("SYNTHETIC_CAMERA_A", 0), ("SYNTHETIC_CAMERA_B", .05)))
    candidates = {
        "source_sha256": domain.source_sha256,
        "candidates": [{
            "source_bounds_bu": {"minimum": [4, 4, 0], "maximum": [6, 6, 1]},
            "source_object_id": "SYNTHETIC_ISLAND", "source_component_id": "synthetic-component",
            "obstacle_id": "SYNTHETIC_APPROVED_ROLE_ONLY",
        }],
    }
    result = audit_two_sided_source_candidates(
        candidates, domain, cameras, floor_support_z_bu=0, proposed_landmark_offset_bu=1,
    )
    assert result["status"] == "HUMAN_REVIEW_REQUIRED"
    assert result["configured_candidate_count"] == 2
    assert result["combined_support_and_camera_fov_pair_count"] == 2
    assert result["source_distinct_feasible_branches_certified"] is False
    assert result["human_approval_applied"] is False
    assert all(row["source_occlusion"] == "NOT_RUN" for row in result["candidates"])
    candidates["source_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="support domain source differs"):
        audit_two_sided_source_candidates(
            candidates, domain, cameras, floor_support_z_bu=0, proposed_landmark_offset_bu=1,
        )
