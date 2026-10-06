"""Guards for the new diagnostic report; existing inference contracts stay unchanged."""

from __future__ import annotations

import copy
import csv
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/scene_audit/school_v3_scale_calibration_20261006"
SPEC = importlib.util.spec_from_file_location(
    "measure_school_scale", ROOT / "scripts/measure_school_scale.py",
)
assert SPEC is not None and SPEC.loader is not None
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)
finish_cross_sections = SCRIPT.finish_cross_sections
measurement_row = SCRIPT.measurement_row
render_markdown = SCRIPT.render_markdown
validate_config = SCRIPT.validate_config


def config() -> dict[str, object]:
    return json.loads((ROOT / "configs/school_v3_scale_measurement_v1.json").read_text())


@pytest.mark.parametrize("scale", [0, -1, math.nan, math.inf, True])
def test_invalid_scale_fails_before_measurement(scale: object) -> None:
    document = config()
    document["proposed_metres_per_blender_unit"] = scale
    with pytest.raises(ValueError, match="finite and positive"):
        validate_config(document)


def test_measurement_config_cannot_approve_scale_or_mutate_source() -> None:
    document = config()
    assert validate_config(document) == 0.0247
    for key, value in [("scale_authority", "APPROVED"),
                       ("known_real_dimensions", [{"length_m": 1}]),
                       ("policy", {"source_save_allowed": True})]:
        rejected = copy.deepcopy(document)
        rejected[key] = value
        with pytest.raises(ValueError):
            validate_config(rejected)


def test_partial_source_hits_never_fabricate_missing_width_or_approval() -> None:
    row = measurement_row("portal:X", "DOOR", "portal", "1F", None, 0,
                          [0, 0, 0], [40, 0, 0], 0.0247)
    row["source_cross_sections"] = [{"length_bu": None, "side_orientation_matches": False}]
    finish_cross_sections(row, 0.0247)
    assert row["actual_source_length_bu"] is None
    assert row["actual_source_length_proposed_m"] is None
    assert not row["human_confirmation_candidate"]
    assert not row["suitable_for_scale_approval"]


def test_variable_source_profile_remains_explicit_and_unapproved() -> None:
    row = measurement_row("room:Y", "ROOM", "room", "2F", None, 1,
                          [0, 0, 0], [0, 400, 0], 0.0247)
    row["source_cross_sections"] = [
        {"length_bu": 10, "side_orientation_matches": True},
        {"length_bu": 390, "side_orientation_matches": True},
    ]
    finish_cross_sections(row, 0.0247)
    assert row["actual_source_length_bu"] == 200
    assert row["source_width_range_bu"] == [10, 390]
    assert "WIDTH_VARIES_WITH_HEIGHT" in row["ambiguities"]
    assert not row["human_confirmation_candidate"]
    assert not row["suitable_for_scale_approval"]


def test_real_source_report_keeps_endpoints_units_and_review_authority() -> None:
    report = json.loads((OUTPUT / "measurements.json").read_text())
    assert report["source"]["before"] == report["source"]["after"]
    assert report["scale_authority"] == "HUMAN_REVIEW"
    assert report["cross_validation_status"] == "AWAITING_REAL_DIMENSIONS"
    assert report["independent_known_dimensions"] == []
    assert not report["formal_physical_use_allowed"]
    assert not report["saved"] and not report["rendered"] and not report["geometry_modified"]
    assert not report["gt_used"]
    assert len(report["human_anchor_shortlist"]) == 5
    assert report["floor_height"]["vertical_height_proposed_m"] == pytest.approx(3.500786486)
    for row in report["measurements"]:
        assert not row["suitable_for_scale_approval"]
        assert row["known_real_length_m"] is None
        assert row["annotation_length_proposed_m"] == pytest.approx(
            math.dist(*row["annotation_endpoints_bu"]) * 0.0247,
        )
        for section in row["source_cross_sections"]:
            if section["length_bu"] is None:
                continue
            assert section["length_bu"] == pytest.approx(
                math.dist(*[hit["endpoint_bu"] for hit in section["hits"]]),
            )
            for hit in section["hits"]:
                assert hit["source_polygon_vertices_bu"]
                assert hit["evaluated_polygon_index"] >= 0
                assert hit["semantic_role"] == "UNASSIGNED_SOURCE_GEOMETRY"


def test_source_width_and_annotation_span_are_distinct_and_csv_agrees() -> None:
    report = json.loads((OUTPUT / "measurements.json").read_text())
    row = next(r for r in report["measurements"] if r["object"] == "PORTAL_1F_RESTAURANT_A")
    assert row["annotation_length_bu"] == 40
    assert row["actual_source_length_bu"] == pytest.approx(35.43310547)
    with (OUTPUT / "measurements.csv").open(newline="") as stream:
        csv_row = next(
            (r for r in csv.DictReader(stream) if r["measurement_id"] == row["measurement_id"]),
        )
    assert float(csv_row["actual_source_length_proposed_m"]) == (
        row["actual_source_length_proposed_m"]
    )
    assert json.loads(csv_row["source_cross_sections"]) == row["source_cross_sections"]
    modified = copy.deepcopy(report)
    modified["proposed_metres_per_blender_unit"] = 0.03
    assert "0.03 m/BU" in render_markdown(modified)


def test_camera_and_canonical_reference_audits_preserve_history() -> None:
    camera = json.loads((OUTPUT / "camera_references.json").read_text())
    assert camera["decision"]["active_consuming_reference_count"] == 0
    assert not camera["decision"]["delete_performed"]
    assert camera["blender_dependency_audit"]["research_camera_count"] == 29
    assert camera["source"]["unchanged"]
    canonical = json.loads((OUTPUT / "canonical_references.json").read_text())
    assert canonical["historical_artifacts_modified"] is False
    assert canonical["exact_duplicate_geometry_surface_groups"] == []
    assert canonical["elevator"]["status"] == "NOT_APPLICABLE"
