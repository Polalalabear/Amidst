"""User-defined scale authority and units do not confer geometry authority."""

import copy
import json
import math
from contextlib import nullcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.architectural_scale import ArchitecturalScale, load_architectural_scale
from amidst.scene_geometry import Authority

CONFIG = Path("configs/architectural_scale_school_v3.json")


def test_user_setting_is_approved_without_external_dimensions() -> None:
    scale = load_architectural_scale(CONFIG)
    assert scale.authority == Authority.APPROVED
    assert scale.metres_per_blender_unit == 0.0247
    assert scale.approval_basis == "USER_DEFINED_RESEARCH_MODEL_SETTING"
    assert not scale.external_dimensions_required
    assert not scale.source_geometry_scaled
    assert scale.measurement_role == "SANITY_CHECK_EVIDENCE"
    assert scale.to_metres(25) == pytest.approx(0.6175)
    assert scale.to_blender_units(1.7) == pytest.approx(68.825910931)
    assert scale.to_square_metres(10) == pytest.approx(0.0061009)
    assert scale.to_cubic_metres(10) == pytest.approx(0.00015069223)
    assert scale.speed_to_metres_per_second(10) == pytest.approx(0.247)
    assert scale.speed_to_blender_units_per_second(1) == pytest.approx(40.48582996)


@pytest.mark.parametrize("quantity", [math.nan, math.inf, -math.inf, True])
def test_invalid_quantity_fails_fast(quantity: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        load_architectural_scale(CONFIG).to_metres(quantity)


@pytest.mark.parametrize("change", [
    {"authority": "HUMAN_REVIEW"}, {"approval_id": ""}, {"evidence_ids": []},
    {"metres_per_blender_unit": 0}, {"metres_per_blender_unit": math.nan},
    {"source_geometry_scaled": True}, {"external_dimensions_required": True},
])
def test_approval_cannot_be_forged_or_inferred_from_mesh(change: dict[str, object]) -> None:
    value = load_architectural_scale(CONFIG).model_dump(mode="json")
    value.update(change)
    with pytest.raises(ValidationError):
        ArchitecturalScale.model_validate_json(json.dumps(value))


def test_conversion_revalidates_unchecked_copy_and_source_binding() -> None:
    scale = load_architectural_scale(CONFIG)
    with pytest.raises(ValueError, match="source SHA-256"):
        scale.require_source_sha256("a" * 64)
    forged = scale.model_copy(update={"authority": Authority.HUMAN_REVIEW})
    with pytest.raises(ValidationError):
        forged.to_metres(10)
    changed = copy.deepcopy(scale.model_dump(mode="json"))
    changed["ground_truth"] = {"position": [0, 0, 0]}
    with pytest.raises(ValidationError):
        ArchitecturalScale.model_validate_json(json.dumps(changed))


@pytest.mark.parametrize("ratio", [1e308, 1e-300])
def test_unrepresentable_area_volume_factors_fail_explicitly(ratio: float) -> None:
    scale = load_architectural_scale(CONFIG).model_copy(
        update={"metres_per_blender_unit": ratio},
    )
    with pytest.raises(ValueError, match="physical unit factor"):
        scale.to_square_metres(1)
    with pytest.raises(ValueError, match="physical unit factor"):
        scale.to_cubic_metres(1)


@pytest.mark.parametrize("ratio", [0, "invalid"])
def test_all_conversion_directions_revalidate_before_factor_arithmetic(ratio: object) -> None:
    forged = load_architectural_scale(CONFIG).model_copy(
        update={"metres_per_blender_unit": ratio},
    )
    for convert in (forged.to_metres, forged.to_blender_units,
                    forged.to_square_metres, forged.to_cubic_metres):
        serializer_warning = (
            pytest.warns(UserWarning, match="Pydantic serializer warnings")
            if isinstance(ratio, str) else nullcontext()
        )
        with serializer_warning, pytest.raises(ValidationError):
            convert(1)
