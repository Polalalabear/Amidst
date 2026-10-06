"""Spatial context supplements must preserve reviewed authority and evidence."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "human_review"
SPATIAL = REVIEW / "frames/spatial_context"
ORIGINAL_PAYLOAD = "e105c3116ebec64e94667f2f863bb0868f4fc34eeeedf1ced0a0b1a931ee1463"


def json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, REVIEW / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def immutable(document: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(document)
    value.pop("review_payload_sha256", None)
    value["metadata"].pop("reviewer", None)
    value["metadata"].pop("submitted_at", None)
    for item in value["items"]:
        item.pop("decision", None)
        item.pop("selected_option", None)
    return value


def test_spatial_context_preserves_four_questions_and_supports_future_filled_decisions() -> None:
    template = json_file(REVIEW / "review_template.json")
    current = json_file(REVIEW / "decisions.json")
    assert [item["id"] for item in template["items"]] == [
        "HR-01",
        "HR-02",
        "HR-03",
        "HR-04",
    ]
    assert immutable(current) == immutable(template)
    encoded = json.dumps(
        immutable(template),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    assert hashlib.sha256(encoded).hexdigest() == ORIGINAL_PAYLOAD
    assert current["review_payload_sha256"] == template["review_payload_sha256"]
    # Editable fields stay compatible without approving or writing real decisions.
    future = copy.deepcopy(current)
    future["metadata"]["reviewer"] = "SYNTHETIC_TEST_ONLY"
    future["metadata"]["submitted_at"] = "2026-10-07T00:00:00+08:00"
    future["items"][0]["decision"] = "KEEP_REVIEW"
    assert immutable(future) == immutable(template)


def original_frames() -> list[dict[str, Any]]:
    visuals = json_file(REVIEW / "frames/visual_manifest.json")
    return sum(
        (
            visuals[name]
            for name in (
                "frames",
                "still_frames",
                "camera_stills",
                "closeup_frames",
            )
        ),
        [],
    )


def spatial_images(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [manifest[name] for name in ("overview", "floor", "office")] + manifest[
        "approach_frames"
    ]


def require_spatial_renders(manifest: dict[str, Any]) -> None:
    missing = [
        row["path"] for row in spatial_images(manifest) if not (SPATIAL / row["path"]).is_file()
    ]
    if missing:
        pytest.skip("requires locally regenerated spatial preview PNGs: " + missing[0])


def require_original_renders() -> None:
    missing = [row["path"] for row in original_frames() if not (REVIEW / row["path"]).is_file()]
    if missing:
        pytest.skip("requires locally regenerated original review PNGs: " + missing[0])


def test_original_source_inputs_and_57_png_manifest_entries_remain_hash_bound() -> None:
    template = json_file(REVIEW / "review_template.json")
    inputs = template["metadata"]["input_hashes"]
    assert len(inputs) == 29
    for row in inputs:
        relative = Path(row["path"])
        assert not relative.is_absolute() and ".." not in relative.parts
        assert not set(relative.parts) & {"evaluation", "ground_truth", "simulation"}
        path = ROOT / relative
        # Ignored raw evidence is verified when materialized; committed evidence
        # stays compatible with the existing review input lock in every clone.
        if path.is_file():
            assert file_digest(path) == row["sha256"], row["path"]
    frames = original_frames()
    assert len(frames) == 57
    assert all(len(row["sha256"]) == 64 for row in frames)


def test_all_materialized_original_pngs_match_the_immutable_evidence() -> None:
    present = [row for row in original_frames() if (REVIEW / row["path"]).is_file()]
    if not present:
        pytest.skip("requires 57 locally regenerated original review PNGs")
    # Every available file is checked, so partial materialization cannot hide a mismatch.
    for row in present:
        assert file_digest(REVIEW / row["path"]) == row["sha256"], row["path"]


def test_camera_approach_is_display_context_and_cannot_promote_physical_authority() -> None:
    manifest = json_file(SPATIAL / "spatial_context_manifest.json")
    assert manifest["result_type"] == "DIAGNOSTIC"
    assert (
        manifest["source_sha256"]
        == json_file(REVIEW / "review_template.json")["metadata"]["source_sha256"]
    )
    assert manifest["display_only_camera_approach"] is True
    assert manifest["source_preserved"] is True
    for name in (
        "source_saved",
        "physical_authority_changed",
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
    ):
        assert manifest[name] is False
    assert len(manifest["approach_frames"]) >= 25
    assert manifest["approach_fps"] == 5


def test_spatial_manifest_reuses_only_frozen_public_inputs_and_preserves_old_image_identities() -> (
    None
):
    manifest = json_file(SPATIAL / "spatial_context_manifest.json")
    template = json_file(REVIEW / "review_template.json")
    frozen = {row["path"]: row["sha256"] for row in template["metadata"]["input_hashes"]}
    frozen["human_review/review_template.json"] = file_digest(REVIEW / "review_template.json")
    for row in manifest["inputs"]:
        assert row["path"] in frozen
        assert row["sha256"] == frozen[row["path"]]
        assert not set(Path(row["path"]).parts) & {"evaluation", "ground_truth", "simulation"}
    for path, expected in frozen.items():
        assert manifest["preserved_original_inputs"][path] == expected
    assert manifest["preserved_original_images"] == {
        row["path"]: row["sha256"] for row in original_frames()
    }
    assert manifest["source_sha256_after"] == manifest["source_sha256"]
    assert manifest["source_modified"] is False
    assert manifest["formal_execution_enabled"] is False
    assert manifest["person_movement_changed"] is False
    assert manifest["scope_authority"] == "PENDING_HUMAN_REVIEW_NOT_APPROVED"
    assert manifest["whole_school_context_authority"] == "PROVISIONAL_NOT_CERTIFIED"


def test_successful_producer_archive_keeps_unrendered_code_out_of_image_lineage() -> None:
    manifest = json_file(SPATIAL / "spatial_context_manifest.json")
    archive = manifest["successful_renderer_source_archive"]
    current = manifest["current_renderer_source"]
    for record in (archive, current):
        relative = Path(record["path"])
        assert record["path_base"] == "REPOSITORY_ROOT"
        assert not relative.is_absolute() and ".." not in relative.parts
        assert relative.parts[:1] == ("human_review",)
        assert file_digest(ROOT / relative) == record["sha256"]
    assert archive["sha256"] == manifest["renderer_sha256"]
    assert archive["original_runtime_relative_path"] == current["path"]
    assert archive["scope"] == "ALL_28_SUCCESSFUL_INITIAL_IMAGES"
    assert len(spatial_images(manifest)) == 28
    assert current["produced_existing_28_images"] is False
    assert current["failed_refit_output_records_changed"] is False


def test_step2_position_map_keeps_source_coordinates_and_pending_authority() -> None:
    text = (SPATIAL / "guide.html").read_text()
    match = re.search(
        r'<script\s+type="application/json"\s+id="spatial-guide-data">(.*?)</script>',
        text,
        flags=re.DOTALL,
    )
    assert match is not None
    guide = json.loads(match.group(1))
    manifest = json_file(SPATIAL / "spatial_context_manifest.json")
    for field in (
        "display_roi_bu",
        "office_context",
        "review_body_scope_bounds_bu",
        "camera_locations",
    ):
        assert guide[field] == manifest[field]
    visuals = json_file(REVIEW / "frames/visual_manifest.json")
    assert guide["movement"]["start_footpoint_bu"] == visuals["frames"][0]["body_base_bu"]
    assert guide["movement"]["end_footpoint_bu"] == visuals["frames"][-1]["body_base_bu"]
    assert guide["binding"]["authority"] == "PENDING_HR02_SEMANTIC_BINDING"
    assert guide["position_map"] == {
        "classification": "DIAGNOSTIC",
        "display_only": True,
        "authority": "DISPLAY_POSITION_CONTEXT_NOT_FOV_OR_BINDING_APPROVAL",
        "axes": "BLENDER_NATIVE_XY_NOT_GEOGRAPHIC_NORTH",
        "gt_used": False,
    }
    assert guide["source_opened_by_guide_builder"] is False
    assert guide["review_payload_sha256"] == ORIGINAL_PAYLOAD


def test_materialized_spatial_previews_pass_content_hash_validation() -> None:
    manifest = json_file(SPATIAL / "spatial_context_manifest.json")
    require_spatial_renders(manifest)
    module = load_script("build_spatial_guide")
    module.validate_manifest(manifest, SPATIAL)


@pytest.mark.parametrize(
    "relative",
    [
        "data/finalization/local_run/dataset/evaluation/office/ground_truth.json",
        "data/finalization/local_run/dataset/simulation/office/recipe.json",
        "data/finalization/local_run/diagnostics/office/projection_evaluation.json",
    ],
)
def test_context_renderer_refuses_gt_and_recipes_before_opening_files(
    relative: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    renderer = load_script("render_spatial_context")

    def unexpected_read(_path: Path) -> bytes:
        raise AssertionError("spatial renderer opened forbidden evidence")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)
    with pytest.raises(ValueError, match="explicit public source/review inputs"):
        renderer.read_public(ROOT / relative)


@pytest.mark.parametrize(
    "field",
    [
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
        "physical_authority_changed",
    ],
)
def test_truth_or_authority_promotion_is_rejected_before_reading_image_bytes(
    field: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script("build_spatial_guide")
    manifest = json_file(SPATIAL / "spatial_context_manifest.json")
    manifest[field] = True

    def unexpected_read(_path: Path) -> bytes:
        raise AssertionError("invalid supplement opened image evidence")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)
    with pytest.raises(ValueError):
        module.validate_manifest(manifest, SPATIAL)


@pytest.mark.parametrize(
    "path",
    [
        "../../../../data/evaluation/ground_truth.png",
        "/private/tmp/ground_truth.png",
    ],
)
def test_supplement_image_references_cannot_escape_its_display_directory(
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script("build_spatial_guide")
    manifest = json_file(SPATIAL / "spatial_context_manifest.json")
    manifest["overview"]["path"] = path

    def unexpected_read(_path: Path) -> bytes:
        raise AssertionError("escaping reference opened evidence")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)
    with pytest.raises(ValueError):
        module.validate_manifest(manifest, SPATIAL)


def test_person_motion_is_separate_from_static_landmark_to_footpoint_conversion() -> None:
    module = load_script("build_spatial_guide")
    visuals = json_file(REVIEW / "frames/visual_manifest.json")
    movement = module.movement_span(visuals)
    binding = module.semantic_binding(visuals)
    scale = json_file(ROOT / "configs/architectural_scale_school_v3.json")[
        "metres_per_blender_unit"
    ]
    first, last = visuals["frames"][0], visuals["frames"][-1]
    distance_bu = (
        sum(
            (a - b) ** 2
            for a, b in zip(
                first["body_base_bu"],
                last["body_base_bu"],
                strict=True,
            )
        )
        ** 0.5
    )
    assert movement["distance_bu"] == pytest.approx(distance_bu)
    assert movement["distance_m"] == pytest.approx(distance_bu * scale)
    assert movement["distance_m"] == pytest.approx(3.87, abs=0.01)
    assert binding["offset_m"] == pytest.approx(
        (visuals["landmark_z_bu"] - visuals["approved_support_z_bu"]) * scale,
    )
    assert binding["offset_m"] == pytest.approx(1.3597349528884888)
    assert first["body_base_bu"][2] == last["body_base_bu"][2]
    assert binding["authority"] == "PENDING_HR02_SEMANTIC_BINDING"
    assert movement["distance_m"] != pytest.approx(binding["offset_m"])


@pytest.mark.parametrize("helper", ["movement_span", "semantic_binding"])
def test_spatial_measurements_cannot_use_a_truth_bearing_preview(helper: str) -> None:
    module = load_script("build_spatial_guide")
    visuals = json_file(REVIEW / "frames/visual_manifest.json")
    visuals["gt_used"] = True
    with pytest.raises(ValueError, match="Ground Truth"):
        getattr(module, helper)(visuals)


def test_building_spatial_guide_does_not_rewrite_decisions_or_original_evidence(
    tmp_path: Path,
) -> None:
    require_spatial_renders(json_file(SPATIAL / "spatial_context_manifest.json"))
    require_original_renders()
    module = load_script("build_spatial_guide")
    protected = [
        REVIEW / name
        for name in (
            "decisions.json",
            "review_template.json",
            "geometry_evidence.json",
            "settings_evidence.json",
            "frames/visual_manifest.json",
        )
    ]
    before = {path: file_digest(path) for path in protected}
    output = tmp_path / "guide.html"
    module.build_guide(SPATIAL / "spatial_context_manifest.json", output)
    assert {path: file_digest(path) for path in protected} == before
    text = output.read_text()
    assert ORIGINAL_PAYLOAD in text
    assert "localStorage" not in text
    assert "DIAGNOSTIC" in text
