"""Invalid evidence/calibration never produces a projected graph endpoint."""

from typing import Any

import pytest
from pydantic import ValidationError

from amidst.domain.camera import Camera
from amidst.domain.evidence import ObservationFrame
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import InverseProjectionError, InverseProjectionService

from .guards_helpers import guards_fixture, guards_numeric_tokens

FIXTURE = guards_fixture("guards_projection.json")


@pytest.mark.parametrize("scenario", FIXTURE["scenarios"], ids=lambda item: item["scenario_id"])
def test_invalid_projection_fails_before_graph_with_deterministic_reason(
    scenario: dict[str, Any],
) -> None:
    base = FIXTURE["input"]
    case = scenario["input"]
    patch = guards_numeric_tokens(case["patch"])
    if "point_2d" in patch:
        patch["point_2d"] = tuple(patch["point_2d"])
    if "camera_to_world" in patch:
        patch["camera_to_world"] = tuple(tuple(row) for row in patch["camera_to_world"])
    expected = scenario["expected"]
    assert expected["candidates"] == expected["rejected_transitions"] == []
    assert expected["termination"] == "NOT_STARTED"
    assert expected["provenance"] == "NONE"
    assert expected["metric_behavior"] == "SKIPPED_INVALID_INPUT"
    failures = []
    for _ in range(3):
        camera = Camera.model_validate(base["camera"])
        plane = Plane.model_validate(base["plane"])
        frame = ObservationFrame.model_validate(base["frame"])
        if expected["failure"] == "SCHEMA_REJECTED":
            missing = base["camera"] | patch
            for field in case["remove_fields"]:
                missing.pop(field)
            with pytest.raises(ValidationError) as captured_schema:
                Camera.model_validate(missing)
            if case["remove_fields"]:
                assert {error["loc"][0] for error in captured_schema.value.errors()} == set(
                    case["remove_fields"]
                )
            else:
                assert all(
                    error["loc"][0] == "camera_to_world"
                    for error in captured_schema.value.errors()
                )
            failures.append("SCHEMA_REJECTED")
            continue
        if case["stage"] == "camera":
            camera = camera.model_copy(update=patch)
        elif case["stage"] == "plane":
            plane = Plane.model_validate(base["plane"] | patch)
        else:
            # Also verify the service revalidates model_copy's unchecked payload.
            frame = frame.model_copy(update=patch)
        with pytest.raises(InverseProjectionError) as captured:
            InverseProjectionService(camera, plane).project_frame(frame)
        failures.append(captured.value.failure.value)
        assert str(captured.value)
    assert failures == [expected["failure"]] * 3
