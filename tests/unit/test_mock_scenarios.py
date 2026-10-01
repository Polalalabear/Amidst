"""Checked-in fixtures are reproducible strict domain data, with separate truth."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.pipeline import InferenceInput
from amidst.simulation.mock_scenarios import SCENARIO_IDS, SEED, export_scenarios

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "mock"


def test_regeneration_is_byte_identical_and_refuses_overwrite(tmp_path: Path) -> None:
    export_scenarios(tmp_path)
    for generated in tmp_path.rglob("*.json"):
        assert generated.read_bytes() == (FIXTURES / generated.relative_to(tmp_path)).read_bytes()
    with pytest.raises(FileExistsError):
        export_scenarios(tmp_path)


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_fixture_schema_and_truth_separation(scenario: str) -> None:
    source = FIXTURES / scenario / "inference.json"
    payload = InferenceInput.model_validate_json(source.read_text())
    assert payload.random_seed == SEED
    truth = GroundTruthTrajectory.model_validate_json(
        (source.parent / "ground_truth.json").read_text()
    )
    assert truth.random_seed == SEED
    assert truth.target_id == payload.start_observation.target_id
    assert "GROUND_TRUTH" not in source.read_text()
    injected = payload.model_dump(mode="python")
    injected["ground_truth_3d"] = (123, 456, 789)
    with pytest.raises(ValidationError):
        InferenceInput.model_validate(injected)
