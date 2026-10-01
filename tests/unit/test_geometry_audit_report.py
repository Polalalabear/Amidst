"""Regression checks for source-bound diagnostic evidence, not NavMesh approval."""

from __future__ import annotations

import json
from pathlib import Path

REPORT_PATH = (
    Path(__file__).resolve().parents[2] / "data/scene_audit/school_v2_geometry_audit.json"
)


def load_report() -> dict:
    def reject_nonfinite(value: str) -> None:
        raise ValueError(value)

    return json.loads(REPORT_PATH.read_text(encoding="utf-8"), parse_constant=reject_nonfinite)


def test_geometry_evidence_is_source_bound_and_not_navigation_approval() -> None:
    report = load_report()
    source = report["source"]
    assert source["sha256_before"] == source["sha256_after"]
    assert source["sha256_before"] == (
        "1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38"
    )
    assert report["audit_kind"] == "READ_ONLY_GEOMETRY_DIAGNOSTIC"
    assert all(
        report["read_only_contract"][key]
        for key in ("source_hash_unchanged", "source_size_unchanged", "source_mtime_unchanged")
    )
    assert report["read_only_contract"]["save_operation_performed"] is False
    assert report["read_only_contract"]["render_operation_performed"] is False
    assert not any(report["interpretation_boundary"].values())
    assert "/Users/" not in REPORT_PATH.read_text(encoding="utf-8")


def test_mesh_geometry_supports_two_primary_floor_bands_without_names() -> None:
    report = load_report()
    assert report["mesh_object_count_excluding_annotations"] == 370
    assert report["evaluated_triangle_count"] == 25_098
    assert report["analysis_parameters"]["annotation_collection_excluded"] == "Areas"
    patches = report["largest_connected_upward_horizontal_patches"]
    for z in (20.07885, 161.811096):
        assert any(
            abs(patch["z"] - z) < 0.001
            and patch["area"] > 1_000_000
            and patch["object"] == "group_0"
            for patch in patches
        )


def test_stair_region_evidence_is_not_a_validated_cross_floor_path() -> None:
    stairs = load_report()["stair_region_evidence"]
    assert {row["area"] for row in stairs} == {"AREA_STAIR01", "AREA_STAIR02"}
    for row in stairs:
        assert row["ascending_surfaces"] == []
        assert row["grid_samples_with_surface"] == 81
        clusters = row["grid_top_surface_height_clusters"]
        assert len(clusters) == 1
        assert clusters[0]["sample_count"] == 81
        assert abs(clusters[0]["z_mean"] - 161.8111) < 0.001
