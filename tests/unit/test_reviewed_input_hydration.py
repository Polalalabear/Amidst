"""The fresh-review boundary refuses drift before writing historical inputs."""

import hashlib
import json
from pathlib import Path

import pytest

from amidst.reviewed_input_hydration import hydrate_historical_inputs


def _write(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root, historical, durable = (tmp_path / name for name in ("root", "historical", "durable"))
    raw_hash = _write(durable / "frames/frame.json", {"original": True})
    input_hash = _write(historical / "data/public.json", {"projected": True})
    manifest_hash = _write(durable / "manifest.json", {
        "source_sha256": "source", "review_payload_sha256": "payload",
        "artifacts": [{"path": "frames/frame.json", "sha256": raw_hash}],
    })
    _write(root / "docs/PHASE1_POST_APPROVAL_CHECKPOINT.json", {
        "source": {"sha256": "source"}, "review_payload_sha256": "payload",
        "durable_review": {"manifest_sha256": manifest_hash},
        "review_bound_inputs": [{"path": "data/public.json", "sha256": input_hash}],
    })
    return root, historical, durable


def test_copy_missing_and_verify_repeat(tmp_path: Path) -> None:
    root, historical, durable = _fixture(tmp_path)
    receipt = hydrate_historical_inputs(root, historical_root=historical, durable_review=durable)
    assert receipt["copied_file_count"] == receipt["verified_file_count"] == 3
    repeat = hydrate_historical_inputs(root, historical_root=historical, durable_review=durable)
    assert repeat["copied_file_count"] == 0
    assert (root / "data/public.json").read_bytes() == (
        historical / "data/public.json"
    ).read_bytes()


@pytest.mark.parametrize("drift", ["source", "target", "manifest"])
def test_drift_refuses_before_copy(tmp_path: Path, drift: str) -> None:
    root, historical, durable = _fixture(tmp_path)
    target = {
        "source": historical / "data/public.json",
        "target": root / "data/public.json",
        "manifest": durable / "manifest.json",
    }[drift]
    _write(target, {"changed": True})
    with pytest.raises(ValueError, match="mismatch|differs"):
        hydrate_historical_inputs(root, historical_root=historical, durable_review=durable)
    assert not (root / "human_review").exists()


@pytest.mark.parametrize("relative", ["../outside", "/absolute", ".git/config", "evaluation/gt"])
def test_unsafe_or_gt_input_refused(tmp_path: Path, relative: str) -> None:
    root, historical, durable = _fixture(tmp_path)
    path = root / "docs/PHASE1_POST_APPROVAL_CHECKPOINT.json"
    checkpoint = json.loads(path.read_text())
    checkpoint["review_bound_inputs"][0]["path"] = relative
    _write(path, checkpoint)
    with pytest.raises(ValueError, match="safe|GT"):
        hydrate_historical_inputs(root, historical_root=historical, durable_review=durable)
    assert not (root / "human_review").exists()


def test_symlink_escape_refused(tmp_path: Path) -> None:
    root, historical, durable = _fixture(tmp_path)
    (root / "human_review").symlink_to(durable, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        hydrate_historical_inputs(root, historical_root=historical, durable_review=durable)


def test_review_bound_package_overlap_retains_original_hash(tmp_path: Path) -> None:
    root, historical, durable = _fixture(tmp_path)
    path = root / "docs/PHASE1_POST_APPROVAL_CHECKPOINT.json"
    checkpoint = json.loads(path.read_text())
    checkpoint["review_bound_inputs"].append({
        "path": "human_review/frames/frame.json",
        "sha256": hashlib.sha256((durable / "frames/frame.json").read_bytes()).hexdigest(),
    })
    _write(path, checkpoint)
    result = hydrate_historical_inputs(root, historical_root=historical, durable_review=durable)
    assert result["verified_file_count"] == 3
    assert result["review_bound_input_count"] == 2
