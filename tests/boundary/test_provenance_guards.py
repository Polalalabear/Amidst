"""Structural provenance forgery is rejected before projection or graph inference."""

from typing import Any

import pytest
from pydantic import ValidationError

from amidst.domain.common import Provenance
from amidst.domain.evidence import ObservationFrame
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.stream import RawProjectedFrameSample
from amidst.observation.aggregation import AggregationInputError, aggregate_frames
from amidst.pipeline import generate_candidates, load_inference_input

from .guards_helpers import ROOT, guards_fixture, guards_truth

FIXTURE = guards_fixture("guards_provenance.json")
MODELS = {
    "ObservationFrame": (ObservationFrame, "frame"),
    "ProjectedPoint": (ProjectedPoint, "projected_point"),
    "Observation": (Observation, "observation"),
    "RawProjectedFrameSample": (RawProjectedFrameSample, "raw_sample"),
}


@pytest.mark.parametrize("scenario", FIXTURE["scenarios"], ids=lambda item: item["scenario_id"])
def test_structural_provenance_forgery_fails_schema(scenario: dict[str, Any]) -> None:
    model, key = MODELS[scenario["input"]["model"]]
    with pytest.raises(ValidationError) as captured:
        model.model_validate(FIXTURE["input"][key] | scenario["input"]["patch"])
    assert captured.value.errors()
    assert scenario["expected"]["state"] == "REJECTED_BEFORE_INFERENCE"
    assert scenario["expected"]["candidates"] == []
    assert scenario["expected"]["termination"] == "NOT_STARTED"


@pytest.mark.parametrize(
    "scenario", FIXTURE["unchecked_nested_scenarios"], ids=lambda item: item["scenario_id"],
)
def test_nested_provenance_bypass_is_rejected_by_aggregation_and_graph(
    scenario: dict[str, Any],
) -> None:
    provenance = Provenance(scenario["input"]["provenance"])
    bypass = scenario["input"]["bypass"]
    raw = RawProjectedFrameSample.model_validate(FIXTURE["input"]["raw_sample"])
    assert raw.projected_point is not None
    point = raw.projected_point
    if bypass == "copy":
        forged = point.model_copy(update={"provenance": provenance})
    else:
        forged = ProjectedPoint.model_construct(**(point.model_dump() | {"provenance": provenance}))
    raw = raw.model_copy(update={"projected_point": forged})
    with pytest.raises(AggregationInputError, match="RawProjectedFrameSample contract"):
        aggregate_frames((raw,))
    inputs = load_inference_input(ROOT / "data/mock/single_path/inference.json")
    original = inputs.start_observation.projected_path[0]
    poisoned = original.model_copy(update={"provenance": provenance})
    observation = inputs.start_observation.model_copy(update={"projected_path": (poisoned,)})
    with pytest.raises(ValidationError, match="provenance"):
        generate_candidates(inputs.model_copy(update={"start_observation": observation}))


def test_extra_ground_truth_on_unchecked_raw_evidence_is_not_silently_stripped() -> None:
    raw = RawProjectedFrameSample.model_validate(FIXTURE["input"]["raw_sample"])
    forged = raw.model_copy(update=FIXTURE["unchecked_extra"]["input"])
    with pytest.raises(AggregationInputError, match="outside its declared contract"):
        aggregate_frames((forged,))


def test_ground_truth_model_payload_cannot_be_reused_as_projected_point() -> None:
    sample = guards_truth().samples[0]
    with pytest.raises(ValidationError) as captured:
        ProjectedPoint.model_validate(FIXTURE["input"]["projected_point"] | sample.model_dump())
    assert any(error["loc"] == ("provenance",) for error in captured.value.errors())
    assert any(error["type"] == "extra_forbidden" for error in captured.value.errors())
