from pathlib import Path
from types import SimpleNamespace

import pytest

from amidst.research_accuracy.baseline import isolated_package


def test_evaluation_input_shares_raw_and_rejects_changed_locator(tmp_path: Path) -> None:
    class Package(SimpleNamespace):
        def model_copy(self, *, update: dict[str, Path]) -> "Package":
            return Package(**(vars(self) | update))

    truth = tmp_path / "source.json"
    truth.write_text('{"boundary":"EVALUATION_DEBUG_ONLY"}')
    source = Package(simulation_export_path=truth)
    output = tmp_path / "evaluation"
    projected = isolated_package(source, output)  # type: ignore[arg-type]
    assert projected.simulation_export_path.is_symlink()
    assert projected.simulation_export_path.resolve() == truth
    other = tmp_path / "other.json"
    other.write_text("{}")
    with pytest.raises(ValueError, match="locator conflict"):
        isolated_package(Package(simulation_export_path=other), output)  # type: ignore[arg-type]
    assert truth.read_text() == '{"boundary":"EVALUATION_DEBUG_ONLY"}'


def test_evaluation_refuses_existing_raw_copy(tmp_path: Path) -> None:
    path = tmp_path / "simulation/export/ground_truth.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    with pytest.raises(ValueError, match="source symlink"):
        isolated_package(SimpleNamespace(simulation_export_path=path), tmp_path)  # type: ignore[arg-type]
