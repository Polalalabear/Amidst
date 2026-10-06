"""Scale reporting rejects inconsistent evidence without changing native data."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from amidst.architectural_scale import load_architectural_scale

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "validate_school_scale", ROOT / "scripts/validate_school_scale.py",
)
assert SPEC is not None and SPEC.loader is not None
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)


def evidence() -> dict[str, object]:
    return json.loads((ROOT / "data/scene_audit/school_v3_scale_calibration_20261006"
                      / "measurements.json").read_text())


def test_approved_evidence_has_consistent_native_and_metric_units() -> None:
    document = evidence()
    before = copy.deepcopy(document)
    scale = load_architectural_scale(ROOT / "configs/architectural_scale_school_v3.json")
    assert SCRIPT.validate_measurement_units(document, scale) > 100
    assert document == before


@pytest.mark.parametrize("change", [
    {"annotation_length_m": 999}, {"used_to_derive_scale": True},
    {"scale_authority": "HUMAN_REVIEW"}, {"metres_per_blender_unit": 1},
])
def test_inconsistent_or_authority_inferred_measurement_is_rejected(
    change: dict[str, object],
) -> None:
    document = evidence()
    document["measurements"][0].update(change)  # type: ignore[index,union-attr]
    scale = load_architectural_scale(ROOT / "configs/architectural_scale_school_v3.json")
    with pytest.raises(ValueError):
        SCRIPT.validate_measurement_units(document, scale)
