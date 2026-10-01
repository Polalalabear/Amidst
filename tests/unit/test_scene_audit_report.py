from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_JSON = REPO_ROOT / "data/scene_audit/school_v2_scene_audit.json"
AUDIT_README = REPO_ROOT / "data/scene_audit/README.md"
EXPECTED_SOURCE_SHA256 = "1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38"


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def test_scene_audit_is_strict_machine_readable_json() -> None:
    raw = AUDIT_JSON.read_text(encoding="utf-8")
    report = json.loads(raw, parse_constant=_reject_nonfinite)

    assert report["schema_version"] == "1.0.0"
    assert report["audit_kind"] == "READ_ONLY_SCENE_AUDIT"
    assert report["read_only_contract"]["save_operation_performed"] is False
    assert report["read_only_contract"]["source_hash_unchanged"] is True
    assert report["read_only_contract"]["source_size_unchanged"] is True
    assert report["source"]["sha256_before"] == EXPECTED_SOURCE_SHA256
    assert report["source"]["sha256_after"] == EXPECTED_SOURCE_SHA256
    assert report["source"]["sha256_during_blender_run"] == EXPECTED_SOURCE_SHA256


def test_scene_audit_captures_required_inventory_and_blockers() -> None:
    report = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    codes = {finding["code"] for finding in report["analysis"]["core_findings"]}

    assert report["counts"]["objects"] == 2_796
    assert report["counts"]["research_cameras_cam_prefix"] == 29
    assert report["counts"]["cameras"] == 30
    assert len(report["analysis"]["semantic_area_box_inventory"]["area_objects"]) == 30
    assert len(report["analysis"]["semantic_area_box_inventory"]["portal_objects"]) == 28
    assert {
        "UNIT_SCALE_REVIEW_REQUIRED",
        "NONFINITE_CAMERA_INTRINSICS",
        "NO_EXPLICIT_NAVMESH_OBJECT",
        "STAIR_TRANSITION_METADATA_MISSING",
        "CROSS_FLOOR_PORTAL_TRANSFORM_OVERLAP",
    } <= codes


def test_scene_audit_redacts_local_and_nondeterministic_metadata() -> None:
    raw = AUDIT_JSON.read_text(encoding="utf-8")

    assert "/Users/" not in raw
    assert "address=0x" not in raw
    assert "verify=" not in raw
    assert ":\\\\Users\\\\" not in raw


def test_scene_audit_summary_is_bilingual() -> None:
    summary = AUDIT_README.read_text(encoding="utf-8")

    assert "## English" in summary
    assert "## 繁體中文" in summary
    assert EXPECTED_SOURCE_SHA256 in summary
