from __future__ import annotations

import json
from pathlib import Path

import pytest

from amidst.storage.json_files import write_json


def test_json_atomic_nonoverwrite_and_protected_inputs(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    write_json(path, {"finite": 1})
    with pytest.raises(FileExistsError):
        write_json(path, {"finite": 2})
    with pytest.raises(ValueError, match="input"):
        write_json(path, {"finite": 3}, overwrite=True, protected_inputs=(path,))
    assert json.loads(path.read_text()) == {"finite": 1}
    assert list(tmp_path.iterdir()) == [path]


def test_json_rejects_blend_and_nonfinite_payload(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_json(tmp_path / "source.blend", {})
    with pytest.raises(ValueError):
        write_json(tmp_path / "data.json", {"nan": float("nan")})
    assert not list(tmp_path.iterdir())
