"""Versioned raw fixture generation is reproducible and preserves endpoint evidence."""

import subprocess
import sys
from pathlib import Path

import pytest

from amidst.domain.evidence import VisibilityStatus
from amidst.domain.pipeline import InferenceInput
from amidst.experiments.versioning import load_experiment
from amidst.simulation.stream_fixture import export_stream_dataset, samples_from_input

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("name", ["single_path", "branching_top_k", "temporal_slack",
                                 "simplified_stair"])
def test_mock_endpoint_conversion_preserves_projection_without_inventing_pixels(name: str) -> None:
    inputs = InferenceInput.model_validate_json(
        (ROOT / "data/mock" / name / "inference.json").read_text()
    )
    frames = samples_from_input(inputs)
    visible = [
        sample for sample in frames.samples if sample.visibility == VisibilityStatus.OBSERVED
    ]
    assert tuple(sample.projected_point for sample in visible) == (
        *inputs.start_observation.projected_path, *inputs.end_observation.projected_path,
    )
    assert all(sample.uv is None for sample in visible)
    gap = next(sample for sample in frames.samples if sample.visibility == VisibilityStatus.GAP)
    assert gap.projected_point is None and gap.provenance is None and gap.uv is None


def test_fixture_generation_is_byte_reproducible_for_inference_files(tmp_path: Path) -> None:
    first = export_stream_dataset(ROOT / "data/mock", tmp_path / "first")
    second = export_stream_dataset(ROOT / "data/mock", tmp_path / "second")
    assert first.seed == second.seed == 20261001
    assert first.cases == second.cases
    for case in first.cases:
        for reference in (case.pipeline, case.frames):
            assert (tmp_path / "first" / reference.path).read_bytes() == (
                tmp_path / "second" / reference.path
            ).read_bytes()
            assert (ROOT / "data/mock/stream_v1" / reference.path).read_bytes() == (
                tmp_path / "first" / reference.path
            ).read_bytes()


def test_stream_fixture_cli_writes_content_bound_experiment(tmp_path: Path) -> None:
    config_path = tmp_path / "experiment.json"
    subprocess.run([
        sys.executable, str(ROOT / "scripts/generate_stream_dataset.py"),
        "--legacy-root", str(ROOT / "data/mock"),
        "--dataset-output", str(tmp_path / "dataset"),
        "--metric-config", str(ROOT / "configs/metrics/synthetic_regression_v1.json"),
        "--experiment-output", str(config_path),
    ], check=True, capture_output=True, text=True, cwd=ROOT)
    config, dataset, _ = load_experiment(config_path)
    assert config.seed == dataset.seed == 20261001
    assert len(dataset.cases) == 4
