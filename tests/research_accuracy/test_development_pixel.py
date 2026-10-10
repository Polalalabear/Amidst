"""Development-only guard and freeze verification precede evaluator truth access."""

import json
from pathlib import Path

import pytest

from amidst.research_accuracy import development_pixel


@pytest.mark.parametrize("split", ["test", None, "unknown"])
def test_non_development_source_refuses_before_loader_or_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, split: str | None,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "package.json").write_text(json.dumps({"split": split}))
    output = tmp_path / "output"

    def unexpected_loader(path: Path) -> object:
        raise AssertionError("a rejected source must not load RGB, inference or truth")

    monkeypatch.setattr(development_pixel, "_load", unexpected_loader)
    with pytest.raises(ValueError, match="DEVELOPMENT; test sources are forbidden"):
        development_pixel.build(source, output)
    assert not output.exists()


def test_incomplete_freeze_refuses_before_source_or_truth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "manifest.json").write_text(json.dumps({
        "schema_version": "accuracy.pixel-development-freeze.v2",
        "version": development_pixel.VERSION, "split": "test", "algorithms": {},
    }))

    def unexpected_source(path: Path) -> object:
        raise AssertionError("a mismatched freeze must not access source or truth")

    monkeypatch.setattr(development_pixel, "_development_source", unexpected_source)
    with pytest.raises(ValueError, match="freeze/source version mismatch"):
        development_pixel.evaluate(tmp_path)


def test_saved_ablation_policies_change_exactly_one_factor_from_selected_defaults() -> None:
    configs = development_pixel.ablation_configs()
    full = configs["full"].model_dump(mode="json")
    expected = {
        "greedy": "assignment", "no_velocity": "use_velocity",
        "no_appearance": "appearance_weight", "no_shape": "shape_weight",
        "no_quarantine": "merge_quarantine",
    }
    assert set(configs) == {"full", *expected}
    for name, field in expected.items():
        row = configs[name].model_dump(mode="json")
        assert {key for key in row if row[key] != full[key]} == {field}
