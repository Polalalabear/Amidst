"""Actual-surface regressions for the read-only authority milestone."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from amidst.geometry_authority import (
    actual_bounds,
    exact_walkable_intrusions,
    parallel_support,
    section_intervals,
    value_digest,
    welded_component_count,
)
from amidst.scene_geometry import GeometrySurface

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "data/scene_audit/phase1_geometry_authority_20261006"
SOURCE = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"


def surface(
    identity: str, vertices: list[list[float]], triangles: list[list[int]], role: str = "WALL"
) -> GeometrySurface:
    return GeometrySurface.model_validate_json(
        json.dumps(
            {
                "surface_id": identity,
                "source_object_id": "opaque-source-id",
                "role": role,
                "floor_ids": ["1F"],
                "vertices": vertices,
                "triangles": triangles,
                "semantic_authority": "HUMAN_REVIEW",
                "physical_authority": "HUMAN_REVIEW",
                "support": "SURFACE",
            }
        )
    )


def wall(identity: str, y: float, ranges: list[tuple[float, float]]) -> GeometrySurface:
    vertices: list[list[float]] = []
    triangles: list[list[int]] = []
    for low, high in ranges:
        offset = len(vertices)
        vertices.extend([[low, y, 0.0], [high, y, 0.0], [high, y, 140.0], [low, y, 140.0]])
        triangles.extend([[offset, offset + 1, offset + 2], [offset, offset + 2, offset + 3]])
    return surface(identity, vertices, triangles)


def patch(row: GeometrySurface, plane: float) -> dict[str, Any]:
    return {
        "candidate_id": row.surface_id,
        "object": row.source_object_id,
        "floor": "1F",
        "normal": [0.0, 1.0, 0.0],
        "tangent": [1.0, 0.0, 0.0],
        "plane": plane,
        "bounds": actual_bounds(row.vertices),
        "tangent_interval": [0.0, 200.0],
        "extent": 200.0,
        "height": 140.0,
        "walkable_relation": {"section_z": 21.0, "nearby": []},
    }


def test_continuous_intrusion_detects_sliver_between_legacy_seventeen_probes() -> None:
    candidate = wall("candidate", 0.0, [(0.0, 200.0)])
    walkable = surface(
        "walk",
        [[10.0, -2.0, 0.0], [12.5, -2.0, 0.0], [12.5, 2.0, 0.0], [10.0, 2.0, 0.0]],
        [[0, 1, 2], [0, 2, 3]],
        "WALKABLE",
    )
    assert all(not 10.0 <= 200.0 * (i + 0.5) / 17 <= 12.5 for i in range(17))
    hits = exact_walkable_intrusions(
        patch(candidate, 0.0),
        candidate,
        {"walk": walkable},
        {
            "walk_probe_offset": 0.7,
            "weld_epsilon": 0.0014,
            "near_distance": 35.0,
        },
    )
    assert hits == [{"walkable_id": "walk", "continuous_intrusion_length": pytest.approx(2.5)}]


def test_actual_sections_preserve_opening_instead_of_filling_envelope() -> None:
    candidate = wall("opening", 0.0, [(0.0, 60.0), (140.0, 200.0)])
    assert section_intervals(candidate, 21.0, [1.0, 0.0, 0.0]) == [(0.0, 60.0), (140.0, 200.0)]


def test_disconnected_source_triangles_cannot_claim_one_continuous_patch() -> None:
    disconnected = wall("disconnected", 0.0, [(0.0, 60.0), (140.0, 200.0)])
    joined = wall("joined", 0.0, [(0.0, 100.0), (100.0, 200.0)])
    assert welded_component_count(disconnected, 0.0014) == 2
    assert welded_component_count(joined, 0.0014) == 1


def test_parallel_bbox_support_cannot_bridge_actual_missing_faces() -> None:
    candidate = wall("candidate", 0.0, [(0.0, 200.0)])
    peer = wall("peer", 10.0, [(0.0, 60.0), (140.0, 200.0)])
    evidence = parallel_support(
        patch(candidate, 0.0),
        patch(peer, 10.0),
        {"candidate": candidate, "peer": peer},
        {"thickness_min": 2.1, "thickness_max": 28.0},
    )
    assert evidence is not None
    assert evidence["extent_overlap_ratio"] == 1.0
    assert evidence["height_overlap_ratio"] == 1.0
    assert evidence["actual_extent_overlap_ratio"] == pytest.approx(0.6)
    assert evidence["actual_face_area_overlap_ratio"] == pytest.approx(0.6)
    assert evidence["passes"] is False


def test_existing_floor_labels_do_not_mix_walkable_intrusion() -> None:
    candidate = wall("candidate", 0.0, [(0.0, 200.0)])
    walkable = surface(
        "upper",
        [[0.0, -2.0, 140.0], [200.0, -2.0, 140.0], [0.0, 2.0, 140.0]],
        [[0, 1, 2]],
        "WALKABLE",
    )
    walkable = GeometrySurface.model_validate_json(
        json.dumps({**walkable.model_dump(mode="json"), "floor_ids": ["2F"]})
    )
    assert (
        exact_walkable_intrusions(
            patch(candidate, 0.0),
            candidate,
            {"upper": walkable},
            {
                "walk_probe_offset": 0.7,
                "weld_epsilon": 0.0014,
                "near_distance": 35.0,
            },
        )
        == []
    )


def test_exported_evidence_binds_candidate_and_semantic_content() -> None:
    meshes = json.loads((EVIDENCE / "wall_meshes.json").read_text())
    candidates = json.loads(
        (ROOT / "data/scene_audit/phase1_wall_candidates_20261005.json").read_text()
    )
    audit = json.loads((ROOT / "data/scene_audit/school_v3_semantic_audit.json").read_text())
    assert meshes["candidate_content_sha256"] == value_digest(candidates)
    assert meshes["audit_content_sha256"] == value_digest(audit)
    assert meshes["source_sha256"] == SOURCE
    assert meshes["source_preserved"] is True
    assert meshes["saved"] is False and meshes["rendered"] is False
    assert len(meshes["patches"]) == 1572
    assert sum(len(row["triangles"]) for row in meshes["patches"]) == 25006


def test_authority_replay_reproducible_across_processes_and_output_directories(
    tmp_path: Path,
) -> None:
    command = [
        sys.executable,
        "-m",
        "amidst.geometry_authority",
        "--candidates",
        "data/scene_audit/phase1_wall_candidates_20261005.json",
        "--meshes",
        "data/scene_audit/phase1_geometry_authority_20261006/wall_meshes.json",
        "--audit",
        "data/scene_audit/school_v3_semantic_audit.json",
        "--config",
        "configs/scene_validation_school_v3.json",
        "--obstacle-authorization",
        "data/scene_audit/phase1_geometry_authority_20261006/role_authorization.json",
        "--expected-source-sha256",
        SOURCE,
        "--baseline-git-commit",
        "51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e",
    ]
    directories = [tmp_path / "first", tmp_path / "second"]
    for directory in directories:
        completed = subprocess.run(
            command + ["--output", str(directory)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
    for name in ("authority.json", "geometry.json", "authority.md", "manifest.json"):
        assert (directories[0] / name).read_bytes() == (directories[1] / name).read_bytes()
    report = json.loads((directories[0] / "authority.json").read_text())
    assert report["wall_summary"]["final"] == {
        "APPROVED": 0,
        "HIGH_CONFIDENCE": 73,
        "HUMAN_REVIEW": 1422,
        "REJECTED": 77,
    }
    assert report["physical_authority"] == "PROVISIONAL"
    assert report["thresholds_lowered"] is False
    assert report["policy"]["gt_used"] is False
    refused = subprocess.run(
        command + ["--output", str(directories[0])],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert refused.returncode != 0
    assert "output exists" in refused.stderr
