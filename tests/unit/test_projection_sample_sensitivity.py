"""Strict per-sample sensitivity preserves provenance, shared noise and input copies."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.domain.evidence import ObservationFrame

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sample_sensitivity_analysis", ROOT / "scripts" / "analyze_projection_samples.py"
)
assert SPEC and SPEC.loader
ANALYSIS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYSIS)


@pytest.fixture
def source(tmp_path: Path) -> dict[str, Path]:
    observations = {
        "label": ANALYSIS.PILOT_LABEL,
        "data_kind": "SYNTHETIC",
        "site_id": "test",
        "source_asset_sha256": "a" * 64,
        "frames": [
            {
                "camera_id": camera,
                "target_id": "target",
                "frame_id": index,
                "timestamp": index / 5,
                "status": "OBSERVED" if camera == "C1" else "GAP",
                "point_2d": [49 + index, 50 + index] if camera == "C1" else None,
                "gap_reason": None if camera == "C1" else "OUTSIDE_FOV",
                "provenance": "OBSERVED" if camera == "C1" else None,
                "data_kind": "SYNTHETIC",
            }
            for index in range(2)
            for camera in ("C1", "C2")
        ],
    }
    observation_path = tmp_path / "observations.json"
    observation_path.write_text(json.dumps(observations))
    camera = {
        "camera_id": "C1",
        "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 100], [0, 0, 0, 1]],
        "fx": 100,
        "fy": 100,
        "cx": 50,
        "cy": 50,
        "width": 100,
        "height": 100,
        "clip_start": 0.1,
        "clip_end": 1000,
        "floor_id": "1F",
        "zone_id": "Z",
    }
    context = {
        "label": ANALYSIS.PILOT_LABEL,
        "data_kind": "SYNTHETIC",
        "site_id": "test",
        "source_id": "source_test",
        "spatial_context_id": "context_test",
        "source_asset_sha256": "a" * 64,
        "observations_sha256": hashlib.sha256(observation_path.read_bytes()).hexdigest(),
        "cameras": [camera, camera | {"camera_id": "C2"}],
        "plane": {
            "plane_id": "plane",
            "point": [0, 0, 0],
            "normal": [0, 0, 1],
            "floor_id": "1F",
            "zone_id": "Z",
        },
        "zone": {
            "floor_id": "1F",
            "zone_id": "Z",
            "walkable_object_id": "walk",
            "bounds_min": [-100, -100, 0],
            "bounds_max": [100, 100, 0],
            "authority": "ANNOTATION_AABB_ONLY_PROVISIONAL",
        },
    }
    context_path = tmp_path / "projection_context.json"
    context_path.write_text(json.dumps(context))
    return {"observations": observation_path, "context": context_path}


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_noise_shares_draws_and_exactly_matches_legacy_quarter_pixel_seed(
    source: dict[str, Path],
    tmp_path: Path,
) -> None:
    output = tmp_path / "analysis"
    summary = ANALYSIS.analyze_sources([source], output)
    rows = jsonl(output / "per_sample.jsonl")
    assert summary["baseline_visible_samples"] == 2
    assert len(rows) == 2 * len(ANALYSIS.AMPLITUDES) * len(ANALYSIS.SEEDS)
    assert set(r["camera_id"] for r in rows) == {"C1"}
    legacy = random.Random(20261006)
    for frame in range(2):
        selected = [r for r in rows if r["frame_id"] == frame and r["seed"] == 20261006]
        assert len({tuple(r["common_unit_random_draw"]) for r in selected}) == 1
        quarter = next(r for r in selected if r["amplitude_half_width_pixels"] == 0.25)
        assert quarter["delta_uv_pixels"] == [
            legacy.uniform(-0.25, 0.25),
            legacy.uniform(-0.25, 0.25),
        ]
        zero = next(r for r in selected if r["amplitude_half_width_pixels"] == 0)
        assert zero["world_displacement_norm_bu"] == 0
        assert zero["local_amplification_bu_per_pixel"] is None
        for row in selected:
            assert math.isclose(
                row["world_displacement_norm_bu"], row["pixel_noise_vector_norm"], abs_tol=1e-12
            )
            assert row["directional_prediction_residual_norm_bu"] < 1e-12
    no_visible = next(row for row in summary["cameras"] if row["camera_id"] == "C2")
    assert no_visible["visible_pixel_samples"] == 0
    assert no_visible["quarter_pixel_seed_20261006_rms_displacement_bu"] is None
    assert "NOT_GT_ACCURACY" in summary["reference"]


def test_analysis_reads_only_strict_pairs_and_never_runs_aggregation(
    source: dict[str, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import amidst.datasets.pilot as pilot
    import amidst.observation.aggregation as aggregation

    def prohibited(*args, **kwargs):
        raise AssertionError("full aggregation was executed")

    monkeypatch.setattr(pilot, "aggregate_frames", prohibited)
    monkeypatch.setattr(aggregation, "aggregate_frames", prohibited)
    poison = tmp_path / "ground_truth.json"
    poison.write_text("poison: no analysis may read GT")
    allowed = {path.resolve() for path in source.values()}
    original = Path.read_bytes

    def guarded(path: Path) -> bytes:
        if path.resolve() == poison.resolve():
            raise AssertionError("Ground Truth read")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded)
    summary = ANALYSIS.analyze_sources([source], tmp_path / "analysis")
    assert {Path(path) for path in summary["inputs_sha256"]} == allowed
    assert not summary["ground_truth_read"]
    assert not summary["aggregation_graph_ranking_reconstruction_executed"]
    with pytest.raises(ValueError, match="only explicit"):
        ANALYSIS.analyze_sources([source | {"ground_truth": poison}], tmp_path / "other")


def test_calibration_variants_preserve_original_pixels_and_files(
    source: dict[str, Path],
    tmp_path: Path,
) -> None:
    original = {path: path.read_bytes() for path in source.values()}
    output = tmp_path / "analysis"
    ANALYSIS.analyze_sources([source], output)
    rows = jsonl(output / "calibration_samples.jsonl")
    assert rows
    assert all(row["original_pixels_preserved"] for row in rows)
    assert {row["perturbation_kind"] for row in rows} == {"camera", "plane"}
    for row in rows:
        assert row["original_pixel"] == [49 + row["frame_id"], 50 + row["frame_id"]]
        assert row["variant_id"] == row["variant"]["variant_id"]
    grouped = json.loads((output / "calibration_summary.json").read_text())["rows"]
    assert all(row["sample_count"] == 2 for row in grouped)
    assert {path: path.read_bytes() for path in source.values()} == original


def test_noise_rejection_is_recorded_without_clamping(source: dict[str, Path]) -> None:
    observations, context, _ = ANALYSIS.load_source(source["observations"], source["context"])
    frame = ObservationFrame.model_validate(
        observations.frames[0].model_dump() | {"point_2d": [99.9, 50]}
    )
    baseline, state = ANALYSIS.project(context.cameras[0], context.plane, frame)
    assert state == "PROJECTED"
    row = ANALYSIS.noise_result(
        context.cameras[0], context.plane, frame, baseline, [[1, 0], [0, -1], [0, 0]], (1, 0)
    )
    assert row["perturbed_pixel"][0] == 100.9
    assert row["projection_state"] == "PIXEL_OUTSIDE_IMAGE"
    assert row["projected_position"] is None
    assert row["world_displacement_norm_bu"] is None


def test_invalid_binding_and_gt_provenance_are_rejected(source: dict[str, Path]) -> None:
    context = json.loads(source["context"].read_text())
    context["observations_sha256"] = "b" * 64
    source["context"].write_text(json.dumps(context))
    with pytest.raises(ValueError, match="binding differs"):
        ANALYSIS.load_source(source["observations"], source["context"])
    raw = json.loads(source["observations"].read_text())
    raw["frames"][0]["provenance"] = "GROUND_TRUTH"
    source["observations"].write_text(json.dumps(raw))
    with pytest.raises(ValidationError):
        ANALYSIS.load_source(source["observations"], source["context"])


def test_summary_uses_vector_rms_and_preserves_rejected_samples() -> None:
    rows = [
        {"camera_id": "C", "world_displacement_norm_bu": value, "projection_state": state}
        for value, state in ((5, "PROJECTED"), (13, "PROJECTED"), (None, "NEAR_CLIPPED"))
    ]
    result = ANALYSIS.summarize(rows, ("camera_id",))[0]
    assert result["rms_vector_displacement_bu"] == math.sqrt((25 + 169) / 2)
    assert result["mean_vector_displacement_bu"] == 9
    assert result["max_vector_displacement_bu"] == 13
    assert result["sample_count"] == 3
    assert result["comparison_count"] == 2
    assert result["projection_states"]["NEAR_CLIPPED"] == 1


def test_existing_output_is_never_overwritten(source: dict[str, Path], tmp_path: Path) -> None:
    output = tmp_path / "analysis"
    output.mkdir()
    sentinel = output / "sentinel"
    sentinel.write_text("preserve")
    with pytest.raises(FileExistsError):
        ANALYSIS.analyze_sources([source], output)
    assert sentinel.read_text() == "preserve"
