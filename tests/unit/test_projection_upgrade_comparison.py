"""Same-evidence comparison and uncertainty scope cannot imply unsupported validation."""

import importlib.util
import itertools
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "upgrade_comparison_tests",
    Path(__file__).parents[2] / "scripts/compare_projection_upgrade.py",
)
assert spec and spec.loader
upgrade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upgrade)


def test_replay_compares_canonical_saved_bytes_not_tuple_list_representation(tmp_path):
    in_memory = {"point": (1.0, 2.0, 3.0), "refs": [("camera", 0)]}
    loaded = json.loads(json.dumps(in_memory))
    assert in_memory != loaded  # Minimal reproduction of the old wrapper false alarm.
    first, second = tmp_path / "first.json", tmp_path / "replay.json"
    upgrade.write_json(first, in_memory)
    upgrade.write_json(second, loaded)
    assert upgrade.tools.digest(first) == upgrade.tools.digest(second)


@pytest.mark.parametrize(
    "authority,isolated,available", list(itertools.product([False, True], repeat=3))
)
def test_validated_requires_every_gate(authority, isolated, available):
    result = upgrade.classify_upgrade(
        same_evidence_gain=True,
        authority_sufficient=authority,
        gt_isolation_passed=isolated,
        downstream_acceptable=available,
    )
    assert (result == "MODEL_UPGRADE_VALIDATED") == (authority and isolated and available)


def test_no_same_evidence_gain_cannot_be_promising_or_validated():
    assert (
        upgrade.classify_upgrade(
            same_evidence_gain=False,
            authority_sufficient=True,
            gt_isolation_passed=True,
            downstream_acceptable=True,
        )
        == "FIXED_PLANE_ONLY_INSUFFICIENT"
    )


def test_same_evidence_comparator_averages_both_camera_rays():
    refs = [{"camera_id": cam, "frame_id": 0, "timestamp": 0.0} for cam in ("A", "B")]
    request = {"hypotheses": [{"evidence_refs": refs, "world_position": (0.5, 0.5, 0.0)}]}
    result = upgrade.multiview_evaluation(
        [request],
        {("A", 0, 0.0): (2.0, 0.0, 0.0), ("B", 0, 0.0): (0.0, 2.0, 0.0)},
        {0.0: (0.0, 0.0, 0.0)},
    )
    assert result["paired_individual_plane_stats"]["count"] == 2
    assert result["paired_mean_plane_stats"]["count"] == 1
    assert result["triangulated_stats"]["count"] == 1
    assert result["same_evidence_reduction_vs_pair_mean_pct"] == pytest.approx(50)


def test_missing_pair_evidence_not_silently_dropped():
    request = {
        "hypotheses": [
            {
                "evidence_refs": [{"camera_id": "missing", "frame_id": 0, "timestamp": 0.0}],
                "world_position": (0.0, 0.0, 0.0),
            }
        ]
    }
    with pytest.raises(ValueError, match="invent"):
        upgrade.multiview_evaluation([request], {}, {0.0: (0.0, 0.0, 0.0)})


def test_zero_variance_is_unavailable_not_perfect_calibration():
    sidecar = {
        "use_state": "UNAVAILABLE_ZERO_VARIANCE",
        "covariance_bu2": None,
        "covariance_rank": 0,
    }
    result = upgrade.conditional_covariance_evaluation([sidecar], {})
    assert result["conditional_subspace_95_coverage"] is None
    assert result["evaluated_covariance_count"] == 0
    assert result["full_3d_calibration"].startswith("UNVALIDATED")


def test_tangent_coverage_never_hides_unmodeled_normal_error():
    sidecar = {
        "use_state": "USABLE_WITH_UNCERTAINTY",
        "covariance_bu2": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]],
        "covariance_rank": 2,
        "projected_point": {"world_position": [0.0, 0.0, 5.0], "timestamp": 0.0},
        "tangential_radius_95_bu": 2.448,
    }
    result = upgrade.conditional_covariance_evaluation([sidecar], {0.0: (0.0, 0.0, 0.0)})
    assert result["conditional_subspace_95_coverage"] == 1
    assert result["unmodeled_residual_stats"]["max_bu"] == 5
    assert result["plane_normal_uncertainty_modeled"] is False
    assert result["full_3d_calibration"].startswith("UNVALIDATED")


def test_original_cameras_treatments_are_fixed_without_gt_selection():
    treatments = list(upgrade.treatment_cases())
    assert len(treatments) == 31
    assert len({name for name, _ in treatments}) == 31
    assert sum(t["kind"] == "PIXEL_NOISE" for _, t in treatments) == 21


def test_existing_results_never_overwritten(tmp_path):
    (tmp_path / "protocol.json").write_text("{}")
    (tmp_path / "cases").mkdir()
    with pytest.raises(ValueError, match="never overwrite"):
        upgrade.run(tmp_path / "missing", tmp_path / "unavailable_gt", tmp_path)
