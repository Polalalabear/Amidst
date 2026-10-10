"""Source-bound geometry and public historical motion, without GT or rendering."""

import gzip
import hashlib
import json
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from amidst.engineering.registry import content_hash
from amidst.workbench import source_presentation as source


def save(repo: Path, ref: str, value: dict[str, Any]) -> str:
    path = repo / ref
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    if ref.endswith(".gz"):
        raw = gzip.compress(raw, mtime=0)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[Path, dict[str, str]]]:
    repo = tmp_path / "source-fixture"
    frames, old_frames, samples = [], [], []
    output = BytesIO()
    Image.new("RGB", (2, 2), (30, 80, 100)).save(output, format="PNG")
    png = output.getvalue()
    for index in range(50):
        observed = index <= 20 or index >= 45
        foot = [1400, 1940 + index * 3.2, 20]
        landmark = [*foot[:2], 75]
        path = repo / f"human_review/frames/motion_context/motion_{index:03d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
        row = {"frame_id": index, "timestamp": index / 5, "body_base_bu": foot,
               "landmark_position_bu": landmark,
               "role": "OBSERVED / PUBLIC PROJECTED" if observed else "GAP / INFERRED CANDIDATE",
               "state": "OBSERVED" if observed else "INFERRED_GAP",
               "joint_pose_authority": "DISPLAY_ONLY", "body_pose_display_only": True,
               "path": path.name, "sha256": hashlib.sha256(png).hexdigest(), "bytes": len(png),
               "hidden_actor_id": "DO_NOT_EXPORT"}
        frames.append(row)
        old_frames.append(dict(row))
        samples.append({"frame_id": index, "camera_id": "CAM_ORIGINAL",
                        "projected_point": {"world_position": landmark} if observed else None})
    scene = {"name": "Scene", "frame": 220, "subframe": 0.0}
    archive = {
        "source_sha256": source.SOURCE_SHA256, "evaluated_scene": scene,
        "policy": {"gt_used": False}, "geometry_modified": False, "saved": False,
        "architectural_scale": {"metres_per_blender_unit": 0.0247},
        "meshes": [
            {"source_object_id": "group_a", "full_object_exported": True,
             "geometry_sha256": "a" * 64,
             "vertices": [[1300, 1880, 20], [1500, 1880, 20], [1400, 2100, 20],
                          [1400, 2100, 130]], "triangles": [[0, 1, 2], [1, 2, 3]]},
            {"source_object_id": "group_b", "full_object_exported": True,
             "geometry_sha256": "b" * 64,
             "vertices": [[1400, 2010, 20], [1470, 2010, 20], [1400, 2110, 20]],
             "triangles": [[0, 1, 2]]},
            {"source_object_id": "outside_not_exported", "full_object_exported": True,
             "geometry_sha256": "c" * 64, "vertices": [[9000, 9000, 0]], "triangles": []},
        ],
    }
    scale = {"metres_per_blender_unit": 0.0247, "source_asset_sha256": source.SOURCE_SHA256,
             "authority": "APPROVED"}
    candidates = {"results": [{"termination_reason": "COMPLETE", "complete": True,
        "candidates": [{"candidate_id": "original-route-2", "polyline": [[1400, 1940, 75],
                                                                           [1400, 2100, 75]]},
                       {"candidate_id": "original-route-1", "polyline": [[1400, 1940, 75],
                                                [1450, 2020, 75], [1400, 2100, 75]]}]}]}
    context = {"cameras": [{"camera_id": "CAM_ORIGINAL", "camera_to_world": [
        [1, 0, 0, 1500], [0, 1, 0, 2000], [0, 0, 1, 160], [0, 0, 0, 1],
    ]}], "hidden_target_id": "DO_NOT_EXPORT"}
    values: dict[str, dict[str, Any]] = {
        source._GEOMETRY: archive, source._SCALE: scale, source._SUPPORT: {},
              source._CONTEXT: context, source._PROJECTION: {"dataset": {"samples": samples}},
              source._CANDIDATES: candidates, source._VISUAL: {
                  "gt_used": False, "evaluation_files_read": False, "simulation_recipe_read": False,
                  "source_asset_sha256": source.SOURCE_SHA256, "sequence_fps": 5,
                  "frames": old_frames,
              }}
    pins = {ref: save(repo, ref, value) for ref, value in values.items()}
    motion = {
        "source_sha256": source.SOURCE_SHA256, "gt_used": False,
        "evaluation_files_read": False, "simulation_recipe_read": False,
        "fps": 5, "new_route_generated": False, "joint_pose_authority": "DISPLAY_ONLY",
        "frames": frames, "inputs": [{"path": ref, "sha256": sha} for ref, sha in pins.items()],
        "approved_body_dimensions_m": {"radius": 0.3, "height": 1.7, "clearance": 0.05},
        "foot_binding_authority": "PENDING_HR02_NOT_APPROVED",
        "scope_authority": "PENDING_HR01_NOT_CERTIFIED",
        "render_policy": {"source_frame": scene, "display_crop_bu": {
            "minimum": [1320, 1880, -1], "maximum": [1500, 2170, 110],
        }, "source_objects": ["group_a", "group_b"], "retained_source_triangles": 2},
    }
    pins[source._MOTION] = save(repo, source._MOTION, motion)
    monkeypatch.setattr(source, "_PINS", pins)
    source._assemble.cache_clear()
    yield repo, pins
    source._assemble.cache_clear()


def test_interactive_source_subset_normalization_frames_and_all_alternatives(
    fixture: tuple[Path, dict[str, str]],
) -> None:
    repo, _ = fixture
    asset = source.load_source_presentation(repo)
    assert len(asset["meshes"]) == 2
    assert sum(len(m["triangles"]) for m in asset["historical_meshes"]) == 2
    assert asset["historical_meshes"][0]["vertices"][0] == pytest.approx(
        [1300 * .0247, 1880 * .0247, .494],
    )
    assert asset["bounds"] == [[1320 * .0247, 1880 * .0247, -.0247],
                               [1500 * .0247, 2170 * .0247, 110 * .0247]]
    assert len(asset["frames"]) == 50 and asset["time_range"] == [0.0, 9.8]
    assert asset["frame_step_s"] == .2
    assert sum(f["evidence_state"] == "PROJECTED" for f in asset["frames"]) == 26
    assert sum(f["evidence_state"] == "INFERRED_GAP" for f in asset["frames"]) == 24
    assert asset["frames"][21]["source_state"] == "INFERRED_GAP"
    assert asset["frames"][21]["world_position"] == pytest.approx([1400*.0247, 2007.2*.0247, .494])
    assert asset["frames"][0]["landmark_position"][-1] == 75 * .0247
    assert asset["snapshot"]["cameras"][0]["position"] == [1500*.0247, 2000*.0247, 160*.0247]
    assert [r["original_order"] for r in asset["routes"]] == [0, 1]
    assert [len(r["points"]) for r in asset["routes"]] == [2, 3]
    assert asset["complete"] is True and asset["termination_reason"] == "COMPLETE"
    assert not asset["image_measurement"] and asset["origin"] == "SYNTHETIC"
    assert asset["humanoid"]["joint_pose_authority"] == "DISPLAY_ONLY"
    assert asset["humanoid"]["historical_foot_binding_authority"] == "PENDING_HR02_NOT_APPROVED"
    assert asset["humanoid"]["historical_scope_authority"] == "PENDING_HR01_NOT_CERTIFIED"
    encoded = json.dumps(asset)
    for forbidden in (
        str(repo), "DO_NOT_EXPORT", "target_id", "hidden_actor_id", "source_object_id",
    ):
        assert forbidden not in encoded


def test_summary_and_copy_cache_never_mutate_original_inputs(
    fixture: tuple[Path, dict[str, str]],
) -> None:
    repo, pins = fixture
    before = {ref: (repo/ref).read_bytes() for ref in pins}
    asset = source.load_source_presentation(repo)
    asset["frames"][0]["world_position"][0] = -999
    again = source.load_source_presentation(repo)
    assert again["frames"][0]["world_position"][0] > 0
    summary = source.source_presentation_summary(repo)
    assert summary["presentation_ref"] == again["presentation_ref"]
    assert summary["frame_count"] == 50 and summary["candidate_count"] == 2
    assert "meshes" not in summary and "frames" not in summary
    assert before == {ref: (repo/ref).read_bytes() for ref in pins}


def test_clipped_derivation_is_bounded_source_faces_without_caps_or_authority_expansion(
    fixture: tuple[Path, dict[str, str]],
) -> None:
    repo, _ = fixture
    asset = source.load_source_presentation(repo)
    low, high = asset["bounds"]
    assert asset["geometry_presentation"]["historical_triangle_count"] == 2
    assert asset["geometry_presentation"]["display_triangle_count"] > 2
    assert asset["geometry_presentation"]["non_horizontal_triangle_count"] > 0
    for mesh in asset["meshes"]:
        for point in mesh["vertices"]:
            assert all(low[a] - 1e-9 <= point[a] <= high[a] + 1e-9 for a in range(3))
        receipt = mesh["derivation"]
        assert mesh["derivation_sha256"] == content_hash(receipt)
        assert receipt["parent_archive_sha256"] == source._PINS[source._GEOMETRY]
        assert receipt["parent_source_sha256"] == source.SOURCE_SHA256
        assert receipt["geometry_sha256"] == content_hash({
            "vertices": mesh["vertices"], "triangles": mesh["triangles"],
        })
        assert receipt["new_caps_created"] is False
        assert receipt["physical_authority_changed"] is False
        assert receipt["semantic_classification_performed"] is False
        assert mesh["authority"] == "DISPLAY_CONTEXT_ONLY"
    # Every emitted triangle is either an original horizontal face or a piece
    # of the original sloped face; clipping never creates a roof on Z=110BU.
    for triangle in asset["meshes"][0]["triangles"]:
        points = [asset["meshes"][0]["vertices"][i] for i in triangle]
        assert not all(abs(p[2] - 110 * .0247) < 1e-9 for p in points)
    assert all(m["source_vertices_unchanged"] for m in asset["historical_meshes"])


def test_missing_optional_diagnostic_png_does_not_remove_interactive_geometry_or_motion(
    fixture: tuple[Path, dict[str, str]],
) -> None:
    repo, _ = fixture
    expected = source.load_source_presentation(repo)
    (repo/"human_review/frames/motion_context/motion_000.png").unlink()
    source._assemble.cache_clear()
    assert source.load_source_presentation(repo) == expected
    with pytest.raises(source.SourcePresentationError,
                       match="^SOURCE_PRESENTATION_MEDIA_UNAVAILABLE$"):
        source.source_presentation_media(repo, expected["frames"][0]["media_ref"])


def test_gt_poison_never_opens_gt_or_changes_frozen_source_presentation(
    fixture: tuple[Path, dict[str, str]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _ = fixture
    before = source.load_source_presentation(repo)
    truth = repo/"simulation/export/ground_truth.json"
    truth.parent.mkdir(parents=True)
    truth.write_text("POISONED GT /PRIVATE / ACTOR_ID")
    original = Path.open

    def guard(path: Path, *args: Any, **kwargs: Any) -> Any:
        assert path != truth
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guard)
    source._assemble.cache_clear()
    assert source.load_source_presentation(repo) == before


@pytest.mark.parametrize("ref", [
    source._MOTION, source._GEOMETRY, source._PROJECTION, source._SCALE,
])
def test_pinned_inputs_rechecked_even_after_cache_and_errors_are_fixed(
    fixture: tuple[Path, dict[str, str]], ref: str,
) -> None:
    repo, _ = fixture
    source.load_source_presentation(repo)
    path = repo/ref
    path.write_bytes(path.read_bytes()+b"tampered")
    with pytest.raises(source.SourcePresentationError, match="^SOURCE_PRESENTATION_INVALID$"):
        source.load_source_presentation(repo)


def test_media_only_opaque_original_diagnostic_pngs_and_hash_bound_reads(
    fixture: tuple[Path, dict[str, str]],
) -> None:
    repo, _ = fixture
    ref = source.load_source_presentation(repo)["frames"][0]["media_ref"]
    mime, data = source.source_presentation_media(repo, ref)
    assert mime == "image/png" and data.startswith(b"\x89PNG")
    for invalid in ("/private/truth.json", "../ground_truth.json", "media:"+"f"*24):
        with pytest.raises(source.SourcePresentationError,
                           match="^SOURCE_PRESENTATION_MEDIA_UNAVAILABLE$"):
            source.source_presentation_media(repo, invalid)
    (repo/"human_review/frames/motion_context/motion_000.png").write_bytes(data+b"tampered")
    with pytest.raises(source.SourcePresentationError,
                       match="^SOURCE_PRESENTATION_MEDIA_UNAVAILABLE$"):
        source.source_presentation_media(repo, ref)


def test_pinned_input_symlink_escape_is_denied(
    fixture: tuple[Path, dict[str, str]], tmp_path: Path,
) -> None:
    repo, _ = fixture
    path = repo/source._CONTEXT
    outside = tmp_path/"outside.json"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(source.SourcePresentationError, match="^SOURCE_PRESENTATION_INVALID$"):
        source.load_source_presentation(repo)


@pytest.mark.parametrize("kind", ["source", "scale", "truth", "scene", "triangle"])
def test_source_unit_truth_scene_and_triangle_contracts_reject_bad_trusted_fixtures(
    fixture: tuple[Path, dict[str, str]], kind: str,
) -> None:
    repo, pins = fixture
    ref = source._GEOMETRY
    value = json.loads(gzip.decompress((repo/ref).read_bytes()))
    if kind == "source":
        value["source_sha256"] = "f"*64
    if kind == "scale":
        value["architectural_scale"]["metres_per_blender_unit"] = 1.0
    if kind == "truth":
        value["policy"]["gt_used"] = True
    if kind == "scene":
        value["evaluated_scene"]["frame"] = 1
    if kind == "triangle":
        value["meshes"][0]["triangles"][0][0] = -1
    pins[ref] = save(repo, ref, value)
    motion = json.loads((repo/source._MOTION).read_bytes())
    next(entry for entry in motion["inputs"] if entry["path"] == ref)["sha256"] = pins[ref]
    pins[source._MOTION] = save(repo, source._MOTION, motion)
    with pytest.raises(source.SourcePresentationError, match="^SOURCE_PRESENTATION_INVALID$"):
        source.load_source_presentation(repo)
