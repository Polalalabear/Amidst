"""Evaluation waits for freeze; GT influences only independent debug metrics."""

import json
from pathlib import Path

import pytest

from amidst.engineering.evaluation import (
    FrozenRunError,
    evaluate_frozen_run,
    export_inference_demo,
)
from amidst.engineering.run import materialize_run

CONFIG = Path(__file__).resolve().parents[2] / "configs" / "engineering" / "simulation_v1.json"


@pytest.fixture
def frozen_run(tmp_path: Path) -> Path:
    materialize_run(tmp_path, CONFIG, run_id="evaluation-test-v1")
    return tmp_path


def test_independent_synthetic_metrics_and_separate_debug(frozen_run: Path) -> None:
    summary = evaluate_frozen_run(frozen_run)
    encoded = json.dumps(summary)
    assert summary["status"] == "SYNTHETIC_ENGINEERING_MEASURED"
    assert not summary["formal_phase1_acceptance"]
    assert "blue-person" not in encoded and str(frozen_run) not in encoded
    modes = summary["modes"]
    assert isinstance(modes, dict)
    assert modes["photos_only"] == modes["photos_plus_observations"]
    mode = modes["photos_only"]
    assert mode["measurement_count"] == 89
    assert 0 < mode["eligible_detection_recall_24px"] < 1
    assert mode["nearest_eligible_pixel_contact_error_px"]["samples"] > 50
    assert mode["same_nearest_contact_ground_error_m"]["mean"] > 0
    assert mode["association_identity_precision"] == "N/A"
    debug = frozen_run / "evaluation" / "debug" / "details.json"
    assert "blue-person" in debug.read_text()
    assert json.loads((frozen_run / "evaluation" / "summary.json").read_text()) == summary


def test_unfrozen_evaluation_refuses_before_any_gt_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes
    touched = []

    def track(path: Path) -> bytes:
        if path.name == "ground_truth.json":
            touched.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", track)
    with pytest.raises(FrozenRunError, match="FREEZE_REQUIRED"):
        evaluate_frozen_run(tmp_path)
    assert not touched


@pytest.mark.parametrize("corruption", ["receipt", "perception", "scope", "config", "media"])
def test_mismatched_freeze_refuses_before_gt(
    frozen_run: Path, corruption: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_path = frozen_run / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if corruption == "receipt":
        manifest["receipts"][0]["receipt_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest))
    elif corruption == "scope":
        manifest["scope"]["run_id"] = "different-run"
        manifest_path.write_text(json.dumps(manifest))
    elif corruption == "perception":
        path = frozen_run / "perception_photos_only.json"
        value = json.loads(path.read_text())
        value["measurements"][0]["appearance"] = [0, 0, 0]
        path.write_text(json.dumps(value))
    elif corruption == "config":
        path = frozen_run / "engineering_config.json"
        value = json.loads(path.read_text())
        value["fps"] = 3
        path.write_text(json.dumps(value))
    else:
        path = frozen_run / "rgb" / "CAM_A" / "frame-0000.png"
        path.write_bytes(b"changed RGB pixels")
    touched = []
    original = Path.read_bytes

    def track(path: Path) -> bytes:
        if path.name == "ground_truth.json":
            touched.append(path)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", track)
    with pytest.raises(FrozenRunError):
        evaluate_frozen_run(frozen_run)
    assert not touched


def test_gt_contamination_changes_only_evaluation_not_frozen_inference(frozen_run: Path) -> None:
    before = evaluate_frozen_run(frozen_run)
    frozen_paths = [
        frozen_run / f"{kind}_{mode}.json"
        for kind in ("perception", "inference", "snapshot")
        for mode in ("photos_only", "photos_plus_observations")
    ]
    frozen_bytes = [path.read_bytes() for path in frozen_paths]
    gt_path = frozen_run / "simulation" / "export" / "ground_truth.json"
    truth = json.loads(gt_path.read_text())
    for row in truth["ground_truth"]:
        for actor in row.get("actors", []):
            actor["position_xyz_m"][0] += 10
    gt_path.write_text(json.dumps(truth))
    after = evaluate_frozen_run(frozen_run)
    assert before["evaluation_truth_sha256"] != after["evaluation_truth_sha256"]
    assert before["freeze_receipt_sha256"] == after["freeze_receipt_sha256"]
    assert [path.read_bytes() for path in frozen_paths] == frozen_bytes
    assert before["modes"] != after["modes"]


def test_missing_truth_reference_refuses_incomplete_metrics(frozen_run: Path) -> None:
    gt_path = frozen_run / "simulation" / "export" / "ground_truth.json"
    truth = json.loads(gt_path.read_text())
    truth["ground_truth"].pop()
    gt_path.write_text(json.dumps(truth))
    with pytest.raises(FrozenRunError, match="EVALUATION_TRUTH_INCOMPLETE"):
        evaluate_frozen_run(frozen_run)


def test_no_gt_presentation_png_and_reader_verified_rrd(
    frozen_run: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rerun.chunk import RrdReader

    gt_path = frozen_run / "simulation" / "export" / "ground_truth.json"
    gt_path.unlink()
    original = Path.read_bytes

    def deny_gt(path: Path) -> bytes:
        if path.name == "ground_truth.json":
            raise AssertionError("presentation must never read GT")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", deny_gt)
    result = export_inference_demo(frozen_run)
    assert result["gt_overlay"] is False and result["all_route_alternatives"] is True
    png = frozen_run / "presentation" / "inference.png"
    rrd = frozen_run / "presentation" / "inference.rrd"
    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert rrd.stat().st_size > 1000
    recording = RrdReader(rrd)
    assert len(recording.recordings()) == 1
    assert len(recording.store()) > 0
    paths = {chunk.entity_path for chunk in recording.stream()}
    assert any("/projected/" in path for path in paths)
    assert not any("ground_truth" in path for path in paths)
