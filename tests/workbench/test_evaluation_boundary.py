"""Certified aggregate retrieval rejects contamination without accessing truth."""

from __future__ import annotations

import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from amidst.engineering.access import digest
from amidst.workbench.scenes import (
    _CERTIFIED_EVALUATIONS,
    MAX_EVALUATION_BYTES,
    AggregateEvaluationDTO,
    SceneAdapter,
)

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(params=("E0", "E1"))
def aggregate(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Published aggregate-only receipts suffice; no ignored RGB or GT fixture needed."""
    if request.param == "E0":
        return json.loads((REPO / "data/engineering/simulation_20261008/"
                          "evaluation_summary.json").read_bytes())
    receipt = json.loads((REPO / "data/engineering/local_camera_20261008/"
                          "validation.json").read_bytes())
    first = receipt["evaluation"]
    second = copy.deepcopy(first)
    second["freeze_sha256"] = receipt["hashes"]["receipts"]["photos_plus_observations"][
        "receipt_sha256"
    ]
    return {"photos_only": first, "photos_plus_observations": second}


def _row(value: dict[str, Any]) -> dict[str, Any]:
    return value["photos_only"] if "photos_only" in value else value


def _adapter(path: Path, value: dict[str, Any], *, certified: bool = True) -> SceneAdapter:
    # Isolate the retrieval boundary. Full scene construction/indexing has its own
    # existing tests; this fixture needs no camera producer or simulation sidecar.
    scene = object.__new__(SceneAdapter)
    row = _row(value)
    scene.run_id = row["run_id"]
    scene._evaluation_config_hash = row["config_sha256"]
    scene._evaluation_path = path
    scene._evaluation_content_sha256 = digest(value) if certified else None
    scene._evaluation_freeze_hashes = (
        {mode: value[mode]["freeze_sha256"] for mode in value}
        if "photos_only" in value else
        dict(zip(("photos_only", "photos_plus_observations"),
                 value["freeze_receipt_sha256"], strict=True))
    )
    scene.service = SimpleNamespace(guard=SimpleNamespace(binding=SimpleNamespace(
        model_id=row["model_id"], dataset_sha256=row["dataset_sha256"])))
    path.write_text(json.dumps(value))
    return scene


def test_published_aggregates_match_certificates_and_preserve_metrics_modes(
    tmp_path: Path, aggregate: dict[str, Any]
) -> None:
    row = _row(aggregate)
    key = (row["model_id"], row["run_id"], row["dataset_sha256"], row["config_sha256"])
    assert digest(aggregate) == _CERTIFIED_EVALUATIONS[key]
    scene = _adapter(tmp_path / "evaluation.json", aggregate)
    assert scene.evaluation() == aggregate
    assert AggregateEvaluationDTO.model_validate(aggregate).model_dump() == aggregate
    if "photos_only" in aggregate:
        assert set(aggregate) == {"photos_only", "photos_plus_observations"}
        assert set(row["fixed_pool_feature_ablations"]) == {
            "full", "without_appearance", "without_space", "without_time",
        }
    else:
        assert set(aggregate["modes"]) == {"photos_only", "photos_plus_observations"}


@pytest.mark.parametrize("field", ("actor_identity", "private_path", "ground_truth", "metadata"))
def test_extra_fields_rejected_even_with_matching_server_content_certificate(
    tmp_path: Path, aggregate: dict[str, Any], field: str
) -> None:
    _row(aggregate)[field] = "AUDIT_SENTINEL"
    scene = _adapter(tmp_path / "evaluation.json", aggregate)
    result = scene.evaluation()
    assert result == {"status": "UNAVAILABLE", "reason": "INVALID_EVALUATION_SUMMARY"}
    assert "AUDIT_SENTINEL" not in json.dumps(result)


def test_nested_identity_map_rejected_even_with_matching_content_certificate(
    tmp_path: Path, aggregate: dict[str, Any]
) -> None:
    if "photos_only" in aggregate:
        _row(aggregate)["behavior"]["groups"]["visible_supported"]["confusion"][
            "AUDIT_PERSON->DWELL"
        ] = 1
    else:
        aggregate["modes"]["photos_only"]["association_status_counts"]["AUDIT_PERSON"] = 1
    scene = _adapter(tmp_path / "evaluation.json", aggregate)
    assert scene.evaluation()["reason"] == "INVALID_EVALUATION_SUMMARY"


def test_private_locator_in_allowed_text_is_rejected(
    tmp_path: Path, aggregate: dict[str, Any]
) -> None:
    _row(aggregate)["limitations"] = ["Evidence located at /private/AUDIT_SENTINEL"]
    scene = _adapter(tmp_path / "evaluation.json", aggregate)
    assert scene.evaluation()["reason"] == "INVALID_EVALUATION_SUMMARY"


def test_valid_numeric_tamper_is_refused_by_content_hash(
    tmp_path: Path, aggregate: dict[str, Any]
) -> None:
    path = tmp_path / "evaluation.json"
    scene = _adapter(path, aggregate)
    if "photos_only" in aggregate:
        aggregate["photos_only"]["pixels_and_local_identity"]["measurement_count"] += 1
    else:
        aggregate["modes"]["photos_only"]["measurement_count"] += 1
    path.write_text(json.dumps(aggregate))
    assert scene.evaluation() == {
        "status": "STALE", "reason": "EVALUATION_CONTENT_HASH_MISMATCH",
    }


@pytest.mark.parametrize("field", ("run_id", "model_id", "dataset_sha256", "config_sha256"))
def test_wrong_scope_is_refused_without_payload(
    tmp_path: Path, aggregate: dict[str, Any], field: str
) -> None:
    path = tmp_path / "evaluation.json"
    scene = _adapter(path, aggregate)
    _row(aggregate)[field] = "f" * 64 if field.endswith("sha256") else "foreign-scope"
    path.write_text(json.dumps(aggregate))
    assert scene.evaluation() == {"status": "STALE", "reason": "EVALUATION_BINDING_MISMATCH"}


def test_wrong_mode_freeze_is_refused_without_payload(
    tmp_path: Path, aggregate: dict[str, Any]
) -> None:
    path = tmp_path / "evaluation.json"
    scene = _adapter(path, aggregate)
    if "photos_only" in aggregate:
        aggregate["photos_plus_observations"]["freeze_sha256"] = "f" * 64
    else:
        aggregate["freeze_receipt_sha256"][1] = "f" * 64
    path.write_text(json.dumps(aggregate))
    assert scene.evaluation() == {"status": "STALE", "reason": "EVALUATION_BINDING_MISMATCH"}


def test_missing_mode_is_refused_even_with_matching_content_certificate(
    tmp_path: Path, aggregate: dict[str, Any]
) -> None:
    path = tmp_path / "evaluation.json"
    scene = _adapter(path, aggregate)
    target = aggregate if "photos_only" in aggregate else aggregate["modes"]
    del target["photos_plus_observations"]
    scene._evaluation_content_sha256 = digest(aggregate)
    path.write_text(json.dumps(aggregate))
    assert scene.evaluation()["reason"] == "INVALID_EVALUATION_SUMMARY"


def test_missing_content_certificate_does_not_certify_requested_full_summary(
    tmp_path: Path, aggregate: dict[str, Any]
) -> None:
    scene = _adapter(tmp_path / "evaluation.json", aggregate, certified=False)
    assert scene.evaluation() == {
        "status": "UNAVAILABLE", "reason": "EVALUATION_CONTENT_CERTIFICATE_MISSING",
    }


def test_missing_and_malformed_summary_fail_closed(
    tmp_path: Path, aggregate: dict[str, Any]
) -> None:
    path = tmp_path / "evaluation.json"
    scene = _adapter(path, aggregate)
    path.unlink()
    assert scene.evaluation()["reason"] == "NO_PREEXISTING_EVALUATION"
    for payload in (b"not-json", b"[]", b'{"status": "a", "status": "b"}'):
        path.write_bytes(payload)
        assert scene.evaluation()["reason"] == "INVALID_EVALUATION_SUMMARY"


def test_raw_read_is_bounded_before_json_decode(
    tmp_path: Path, aggregate: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "evaluation.json"
    scene = _adapter(path, aggregate)
    requested: list[int] = []

    class BoundedProbe(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            requested.append(size)
            return super().read(size)

    def open_probe(_: Path, mode: str) -> BoundedProbe:
        assert mode == "rb"
        return BoundedProbe(b"x" * (MAX_EVALUATION_BYTES + 50))

    monkeypatch.setattr(Path, "open", open_probe)
    assert scene.evaluation()["reason"] == "EVALUATION_PAYLOAD_TOO_LARGE"
    assert requested == [MAX_EVALUATION_BYTES + 1]


def test_nonfinite_numbers_and_excessive_arrays_are_rejected(
    tmp_path: Path, aggregate: dict[str, Any]
) -> None:
    path = tmp_path / "evaluation.json"
    scene = _adapter(path, aggregate)
    _row(aggregate)["limitations"] = ["bounded note"] * 129
    path.write_text(json.dumps(aggregate))
    assert scene.evaluation()["reason"] == "INVALID_EVALUATION_SUMMARY"
    path.write_bytes(b'{"metric": NaN}')
    assert scene.evaluation()["reason"] == "INVALID_EVALUATION_SUMMARY"


def test_symlink_is_denied_before_reference_bytes_are_opened(
    tmp_path: Path, aggregate: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target.json"
    scene = _adapter(target, aggregate)
    path = tmp_path / "evaluation.json"
    path.symlink_to(target)
    scene._evaluation_path = path

    def unopened(*_: object, **__: object) -> None:
        raise AssertionError("reference must be rejected before any bytes are read")

    monkeypatch.setattr(Path, "open", unopened)
    assert scene.evaluation()["reason"] == "EVALUATION_REFERENCE_DENIED"


def test_evaluation_opens_only_declared_aggregate_reference(
    tmp_path: Path, aggregate: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "evaluation.json"
    scene = _adapter(path, aggregate)
    original = Path.open
    opened: list[Path] = []

    def only_summary(target: Path, mode: str) -> Any:
        assert target == path, "No evaluation or truth sidecar may be opened"
        opened.append(target)
        return original(target, mode)

    monkeypatch.setattr(Path, "open", only_summary)
    assert scene.evaluation() == aggregate
    assert opened == [path]


def test_reference_error_has_fixed_safe_response(
    tmp_path: Path, aggregate: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    scene = _adapter(tmp_path / "evaluation.json", aggregate)

    def inaccessible(_: Path) -> bool:
        raise PermissionError("AUDIT_PRIVATE_LOCATOR_SENTINEL")

    monkeypatch.setattr(Path, "is_file", inaccessible)
    assert scene.evaluation() == {"status": "UNAVAILABLE", "reason": "INVALID_EVALUATION_SUMMARY"}
