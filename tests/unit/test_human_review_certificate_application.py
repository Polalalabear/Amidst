"""Negative public input guards only; never applies a real school approval."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "certificate_application",
    Path(__file__).resolve().parents[2] / "human_review/certificate_application.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize("option", ["KEEP_REVIEW", "REJECT", "", "APPROVE"])
def test_incomplete_and_unrecognized_approval_options_do_not_open_evidence(
    option: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_read(_path: Path) -> bytes:
        raise AssertionError("pending decisions must not read/apply authority")

    monkeypatch.setattr(Path, "read_bytes", fail_if_read)
    with pytest.raises(ValueError, match="explicit approved geometry"):
        MODULE.regenerate_from_completed_review(Path("/synthetic"), {}, option, "fake", "a" * 64)


def test_evaluation_or_recipe_input_is_rejected_before_any_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_read(_path: Path) -> bytes:
        raise AssertionError("GT or recipe input was opened")

    monkeypatch.setattr(Path, "read_bytes", fail_if_read)
    with pytest.raises(ValueError, match="public evidence allowlist"):
        MODULE._verified_inputs(
            Path("/synthetic"),
            {
                "input_hashes": {"evaluation/ground_truth.json": "b" * 64},
            },
        )


def test_source_input_tampering_fails_hash_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(MODULE, "REQUIRED_INPUTS", frozenset({"synthetic_public.json"}))
    raw = b'{"source":"SYNTHETIC_ONLY"}\n'
    path = tmp_path / "synthetic_public.json"
    path.write_bytes(raw)
    good = {"input_hashes": {"synthetic_public.json": hashlib.sha256(raw).hexdigest()}}
    assert MODULE._verified_inputs(tmp_path, good)["synthetic_public.json"]["source"] == (
        "SYNTHETIC_ONLY"
    )
    path.write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="input SHA-256 mismatch"):
        MODULE._verified_inputs(tmp_path, good)
