from __future__ import annotations

import pytest
from pydantic import ValidationError

from amidst.domain.ground_truth import PathKeyframe, TrajectoryConfig


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0])
def test_time_and_coordinates_reject_nonfinite_or_negative_time(value: float) -> None:
    with pytest.raises(ValidationError):
        PathKeyframe(timestamp=value, position=(0, 0, 0))
    if value != -1:
        with pytest.raises(ValidationError):
            PathKeyframe(timestamp=0, position=(value, 0, 0))


def test_models_forbid_unknown_fields_and_unordered_keyframes() -> None:
    with pytest.raises(ValidationError):
        PathKeyframe.model_validate({"timestamp": 0, "position": [0, 0, 0], "secret": 1})
    with pytest.raises(ValidationError):
        TrajectoryConfig(
            keyframes=(
                PathKeyframe(timestamp=1, position=(0, 0, 0)),
                PathKeyframe(timestamp=1, position=(1, 0, 0)),
            )
        )
