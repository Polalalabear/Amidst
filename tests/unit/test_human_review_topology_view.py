"""Topology display must keep the configured graph and source-model projection."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "human_review"
TOPOLOGY = REVIEW / "frames/topology_context"
PIPELINE = ROOT / (
    "data/finalization/local_run/diagnostics/office/policy_graph_primary/pipeline_config.json"
)
MOTION = REVIEW / "frames/motion_context/motion_manifest.json"
PIPELINE_SHA = "492591e47c48642e157621c9c05adf111f3c6909d671d84e248c4ae0807c80e1"
NAVIGATION_SHA = "9bbedd163e9a195943cfe82f3473a97ac3bc0ff3be31e83d5866cccfba4278fd"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def builder() -> Any:
    path = REVIEW / "build_topology_view.py"
    spec = importlib.util.spec_from_file_location("build_topology_view", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def old_images() -> dict[str, str]:
    visual = read_json(REVIEW / "frames/visual_manifest.json")
    spatial = read_json(REVIEW / "frames/spatial_context/spatial_context_manifest.json")
    motion = read_json(MOTION)
    rows = sum(
        (
            visual[key]
            for key in (
                "frames",
                "still_frames",
                "camera_stills",
                "closeup_frames",
            )
        ),
        [],
    )
    result = {"human_review/" + row["path"]: row["sha256"] for row in rows}
    rows = [spatial[key] for key in ("overview", "floor", "office")] + spatial["approach_frames"]
    result.update(
        {"human_review/frames/spatial_context/" + row["path"]: row["sha256"] for row in rows}
    )
    result.update(
        {
            "human_review/frames/motion_context/" + row["path"]: row["sha256"]
            for row in motion["frames"]
        }
    )
    return result


def test_registered_graph_and_source_polyline_vertices_remain_exact() -> None:
    data = read_json(TOPOLOGY / "topology_data.json")
    navigation = data["raw_navigation"]
    canonical = json.dumps(navigation, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == NAVIGATION_SHA
    inputs = {row["path"]: row["sha256"] for row in data["inputs"]}
    assert inputs[PIPELINE.relative_to(ROOT).as_posix()] == PIPELINE_SHA
    assert data["pipeline_output_digests_verified"]["pipeline_config.json"] == PIPELINE_SHA
    if PIPELINE.is_file():
        assert digest(PIPELINE) == PIPELINE_SHA
        assert navigation == read_json(PIPELINE)["pipeline"]["navigation"]
    assert [node["id"] for node in data["nodes"]] == [
        "projected_departure",
        "projected_recovery",
    ]
    assert [edge["id"] for edge in data["edges"]] == [
        "pilot_route:direct",
        "pilot_route:left",
        "pilot_route:right",
    ]
    assert data["node_count"] == 2 and data["edge_count"] == 3
    assert data["interior_vertex_count"] == 4
    for display, source in zip(data["edges"], navigation["edges"], strict=True):
        assert display["from_node"] == "N1" and display["to_node"] == "N2"
        assert display["raw_polyline_bu"] == source["polyline"]
        assert [v["raw_position_bu"] for v in display["interior_vertices"]] == (
            source["polyline"][1:-1]
        )
        assert all(v["role"] == "POLYLINE_VERTEX_NOT_NODE" for v in display["interior_vertices"])
        assert display["raw_graph_edge_retained"] is True
        assert display["physical_route_approved"] is False
    module = builder()
    invented = copy.deepcopy(navigation)
    invented["nodes"].append(
        {
            "node_id": "invented_junction",
            "position": invented["edges"][1]["polyline"][1],
        }
    )
    with pytest.raises(ValueError, match="existing two graph nodes"):
        module.validate_navigation(invented)


def test_model_floor_overlay_changes_only_height_and_keeps_binding_pending() -> None:
    data = read_json(TOPOLOGY / "topology_data.json")
    visual = read_json(REVIEW / "frames/visual_manifest.json")
    conversion = data["conversion"]
    assert conversion["authority"] == "PENDING_HR02_SEMANTIC_BINDING"
    assert conversion["offset_bu"] == visual["proposed_exact_landmark_offset_bu"]
    assert conversion["floor_z_bu"] == visual["approved_support_z_bu"]
    assert conversion["xy_preserved"] is True
    pairs = [(node["raw_position_bu"], node["floor_position_bu"]) for node in data["nodes"]]
    for edge in data["edges"]:
        pairs.extend(zip(edge["raw_polyline_bu"], edge["floor_polyline_bu"], strict=True))
    for raw, floor in pairs:
        assert raw[:2] == floor[:2]
        assert raw[2] == visual["landmark_z_bu"]
        assert floor[2] == pytest.approx(raw[2] - conversion["offset_bu"], abs=1e-10)
        assert floor[2] == pytest.approx(conversion["floor_z_bu"], abs=1e-10)
    for key in (
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
        "source_opened_by_builder",
        "physical_authority_changed",
        "formal_execution_enabled",
        "raw_graph_changed",
    ):
        assert data[key] is False
    assert data["result_type"] == "DIAGNOSTIC"
    assert conversion["raw_graph_changed"] is False


def test_model_pixels_follow_blender_orthographic_pose_and_render_dimensions() -> None:
    module = builder()
    # Blender's horizontal AUTO sensor fit uses ortho_scale as image width.
    # A 960x600 view with width 330 BU consequently spans 206.25 BU vertically.
    # Source: blender/blender camera.cc, BKE_camera_view_frame_ex.
    camera = {
        "position_bu": [10.0, 20.0, 30.0],
        "rotation_euler_radians": [0.0, 0.0, 0.0],
        "ortho_scale_bu": 330.0,
    }
    assert module.project_point([10.0, 20.0, 20.0], camera) == pytest.approx([480.0, 300.0])
    assert module.project_point([175.0, 20.0, 20.0], camera) == pytest.approx([960.0, 300.0])
    assert module.project_point([10.0, 123.125, 20.0], camera) == pytest.approx([480.0, 0.0])
    camera["rotation_euler_radians"] = [0.0, 0.0, math.pi / 2]
    assert module.project_point([10.0, 185.0, 20.0], camera) == pytest.approx([960.0, 300.0])
    assert module.project_point([-93.125, 20.0, 20.0], camera) == pytest.approx([480.0, 0.0])
    camera["rotation_euler_radians"] = [math.pi / 2, 0.0, 0.0]
    assert module.project_point([175.0, 30.0, 30.0], camera) == pytest.approx([960.0, 300.0])
    assert module.project_point([10.0, 30.0, 133.125], camera) == pytest.approx([480.0, 0.0])
    data, motion = read_json(TOPOLOGY / "topology_data.json"), read_json(MOTION)
    assert data["review_camera"] == motion["review_camera"]
    assert (data["width"], data["height"]) == (
        motion["render_policy"]["width"],
        motion["render_policy"]["height"],
    )
    for node in data["nodes"]:
        for point_key, pixel_key in (
            ("raw_position_bu", "raw_pixel"),
            ("floor_position_bu", "floor_pixel"),
        ):
            expected = module.project_point(
                node[point_key], data["review_camera"], data["width"], data["height"]
            )
            assert node[pixel_key] == pytest.approx(expected)
    for edge in data["edges"]:
        for points, pixels in (
            (edge["raw_polyline_bu"], edge["raw_pixels"]),
            (edge["floor_polyline_bu"], edge["floor_pixels"]),
        ):
            for point, pixel in zip(points, pixels, strict=True):
                expected = module.project_point(
                    point, data["review_camera"], data["width"], data["height"]
                )
                assert pixel == pytest.approx(expected)


def test_gt_and_recipe_inputs_are_rejected_before_builder_or_reader_opens_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = builder()

    def unexpected_open(_path: Path, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("topology source opened before its public-path guard")

    monkeypatch.setattr(Path, "open", unexpected_open)
    for relative in (
        "data/finalization/local_run/dataset/evaluation/office/ground_truth.json",
        "data/finalization/local_run/dataset/simulation/office/recipe.json",
        "data/finalization/local_run/diagnostics/office/projection_evaluation.json",
    ):
        forbidden = ROOT / relative
        with pytest.raises(ValueError):
            module.read_public(forbidden)
        with pytest.raises(ValueError):
            module.build_topology(forbidden, MOTION, tmp_path / "view.html")
        with pytest.raises(ValueError):
            module.build_topology(PIPELINE, forbidden, tmp_path / "view.html")


def test_topology_generation_preserves_135_pngs_gif_questions_and_old_guides(
    tmp_path: Path,
) -> None:
    receipt = read_json(TOPOLOGY / "topology_manifest.json")
    images = old_images()
    assert len(images) == 135
    gif = read_json(REVIEW / "frames/motion_context/gif_manifest.json")["artifact"]
    preserved = receipt["preserved_original_files"]
    gif_path = "human_review/frames/motion_context/" + gif["path"]
    expected = images | {gif_path: gif["sha256"]}
    for path, value in expected.items():
        assert preserved[path] == value
        if (ROOT / path).is_file():
            assert digest(ROOT / path) == value
    assert (
        receipt["review_payload_sha256"]
        == read_json(REVIEW / "review_template.json")["review_payload_sha256"]
    )
    frozen = read_json(REVIEW / "review_template.json")["metadata"]["input_hashes"]
    prerequisites = [ROOT / row["path"] for row in frozen]
    prerequisites += [ROOT / path for path in expected]
    prerequisites += [
        PIPELINE,
        PIPELINE.with_name("digests.json"),
        PIPELINE.with_name("topology_evidence.json"),
        PIPELINE.with_name("candidates.json"),
    ]
    if any(not path.is_file() for path in prerequisites):
        pytest.skip("requires materialized frozen topology inputs and original PNG/GIF previews")
    protected = [ROOT / path for path in preserved]
    before = {path: digest(path) for path in protected}
    result = builder().build_topology(PIPELINE, MOTION, tmp_path / "view.html")
    assert {path: digest(path) for path in protected} == before
    assert result["node_count"] == 2 and result["edge_count"] == 3
    assert result["raw_graph_changed"] is False and result["gt_used"] is False
