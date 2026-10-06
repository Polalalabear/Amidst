"""Portable review transport and source-integrity checks, without school approval."""

import gzip
import json
import math
from pathlib import Path

import pytest

from amidst.physical_policy_validation import (
    read_document,
    source_fingerprint,
    validate_policy,
    write_document,
)


@pytest.mark.parametrize("extension", [".json", ".json.gz"])
def test_portable_review_retains_raw_bu_and_source_binding(
    tmp_path: Path, extension: str,
) -> None:
    document = {
        "source_sha256": "a" * 64, "scale_m_per_bu": .0247,
        "vertices_bu": [[1.1, 2.2, 20.07884979248047]],
        "physical_complete": False,
    }
    path = tmp_path / ("portable" + extension)
    write_document(path, document)
    assert read_document(path) == document


def test_gzip_payload_is_canonical_across_output_directories(tmp_path: Path) -> None:
    left, right = tmp_path / "left.json.gz", tmp_path / "right.json.gz"
    write_document(left, {"z": 2, "a": 1})
    write_document(right, {"a": 1, "z": 2})
    assert json.loads(gzip.decompress(left.read_bytes())) == read_document(right)
    # This transport has an explicitly stable header; no Blender/Rerun byte claim.
    assert left.read_bytes() == right.read_bytes()


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_invalid_review_quantities_cannot_be_exported(tmp_path: Path, value: float) -> None:
    path = tmp_path / "invalid.json"
    with pytest.raises(ValueError, match="Out of range"):
        write_document(path, {"coordinate": value})
    assert not path.exists()


def test_nonobject_review_is_explicitly_rejected(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text("[]")
    with pytest.raises(ValueError, match="expected JSON object"):
        read_document(path)


def test_source_fingerprint_is_read_only_and_detects_change(tmp_path: Path) -> None:
    source = tmp_path / "synthetic-source.bin"
    source.write_bytes(b"source geometry")
    before = source_fingerprint(source)
    assert source_fingerprint(source) == before
    source.write_bytes(b"different source geometry")
    assert source_fingerprint(source)["sha256"] != before["sha256"]


def test_wrong_validation_config_fails_before_output_creation(tmp_path: Path) -> None:
    config, output = tmp_path / "config.json", tmp_path / "output"
    config.write_text('{"schema_version":"unsupported"}')
    with pytest.raises(ValueError, match="unsupported physical policy validation config"):
        validate_policy(config, output)
    assert not output.exists()
