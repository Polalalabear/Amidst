"""Authority lineage tests; no fixture grants school collision authority."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.finalization.reviewed_collision_lock import (
    ReviewedCollisionInferenceLock,
    load_frozen_collision_binding,
    load_reviewed_collision_lock,
)
from amidst.finalization.reviewed_pipeline import digest, freeze_inference, write_json
from amidst.obstacle_volume_authority import content_sha256

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "configs/finalization/reviewed_case_inference_lock_v2.json"


def _lock() -> dict[str, Any]:
    raw = BASE.read_bytes()
    base = json.loads(raw)
    return {
        "schema_version": "phase1-reviewed-case-inference-lock-v3",
        "base_inference_lock": base,
        "base_inference_lock_file_sha256": hashlib.sha256(raw).hexdigest(),
        "base_inference_lock_content_sha256": content_sha256(base),
        "known_collision": {
            "context_path": "configs/physical_context_school_v3.json",
            "physical_manifest_file_sha256": "a" * 64,
            "source_sha256": base["base_inference_config"]["source_sha256"],
            "scope_ids": ["synthetic-test-scope"],
        },
        "status": "FROZEN_BEFORE_NEW_EXPORT_AND_INFERENCE",
    }


def test_v3_preserves_v2_policy_and_reference_hashes_without_annotations(tmp_path: Path) -> None:
    document = _lock()
    target = tmp_path / "v3.json"
    target.write_text(json.dumps(document))
    lock = load_reviewed_collision_lock(target, repo_root=ROOT)
    assert lock.known_collision.coverage == "PARTIAL_KNOWN_COLLIDERS"
    assert lock.known_collision.complete_school_collision_claimed is False
    assert lock.base_inference_lock.model_dump(mode="json") == json.loads(BASE.read_bytes())
    assert not any(key in json.dumps(document) for key in (
        '"reference_movement_annotations"', '"waypoints"', '"ground_truth"',
    ))


@pytest.mark.parametrize("mutation", ["source", "base", "scope", "purpose", "coverage"])
def test_v3_rejects_authority_and_lineage_drift(mutation: str) -> None:
    document = _lock()
    if mutation == "source":
        document["known_collision"]["source_sha256"] = "b" * 64
    elif mutation == "base":
        document["base_inference_lock_content_sha256"] = "c" * 64
    elif mutation == "scope":
        document["known_collision"]["scope_ids"] *= 2
    elif mutation == "purpose":
        document["known_collision"]["purpose"] = "FREE_SPACE_CERTIFICATION"
    else:
        document["known_collision"]["coverage"] = "COMPLETE"
    with pytest.raises(ValidationError):
        ReviewedCollisionInferenceLock.model_validate(document)


@pytest.mark.parametrize("path", ["../context.json", "/tmp/context.json",
                                  "data/evaluation/context.json", "data/simulation/context.json"])
def test_v3_refuses_private_or_escaping_context(path: str) -> None:
    document = _lock()
    document["known_collision"]["context_path"] = path
    with pytest.raises(ValidationError, match="safe public"):
        ReviewedCollisionInferenceLock.model_validate(document)


@pytest.mark.parametrize("field", ["reference_movement_annotations", "ground_truth", "waypoints"])
def test_v3_refuses_reference_payload_fields(field: str) -> None:
    document = _lock()
    document["known_collision"][field] = []
    with pytest.raises(ValidationError, match="Extra inputs"):
        ReviewedCollisionInferenceLock.model_validate(document)


def test_v3_checks_exact_original_lock_file_hash(tmp_path: Path) -> None:
    document = _lock()
    document["base_inference_lock_file_sha256"] = "e" * 64
    target = tmp_path / "v3.json"
    target.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="original V2 lock bytes"):
        load_reviewed_collision_lock(target, repo_root=ROOT)


@pytest.mark.parametrize("mutation", [None, "source", "content", "binding", "config",
                                      "body_guard", "ground_truth"])
def test_frozen_collision_lineage_reconstructs_exact_lock(
    tmp_path: Path, mutation: str | None,
) -> None:
    lock = ReviewedCollisionInferenceLock.model_validate(_lock())
    lock_path = tmp_path / "collision_inference_lock.json"
    write_json(lock_path, lock.model_dump(mode="json"))
    document = {
        "schema_version": "phase1-reviewed-inference-collision-binding-v1",
        "inference_lock_file_sha256": digest(lock_path),
        "inference_lock_content_sha256": content_sha256(lock.model_dump(mode="json")),
        "binding": lock.known_collision.model_dump(mode="json"),
        "consumer": {"fixture": "NO_SCHOOL_AUTHORITY"},
        "domain_body_guard_retained_for_all_variants": True,
        "independent_evaluation_collision_checks_retained": True,
        "ground_truth_read": False,
    }
    if mutation == "content":
        document["inference_lock_content_sha256"] = "d" * 64
    elif mutation == "binding":
        document["binding"]["scope_ids"] = ["another-test-scope"]  # type: ignore[index]
    elif mutation == "config":
        document["inference_lock_file_sha256"] = "d" * 64
    elif mutation == "body_guard":
        document["domain_body_guard_retained_for_all_variants"] = False
    elif mutation == "ground_truth":
        document["ground_truth_read"] = True
    write_json(tmp_path / "collision_authority.json", document)
    freeze = freeze_inference(
        tmp_path, dataset_manifest_sha256="a" * 64, config_sha256=digest(lock_path),
    )
    # Even self-consistently frozen false claims must fail independent lineage checks.
    expected_source = "f" * 64 if mutation == "source" else lock.known_collision.source_sha256
    if mutation:
        with pytest.raises((ValueError, ValidationError)):
            load_frozen_collision_binding(
                tmp_path, freeze, repo_root=ROOT, expected_source_sha256=expected_source,
            )
    else:
        loaded = load_frozen_collision_binding(
            tmp_path, freeze, repo_root=ROOT, expected_source_sha256=expected_source,
        )
        assert loaded.binding == lock.known_collision


def test_frozen_collision_lock_is_required_not_only_a_digest_claim(tmp_path: Path) -> None:
    write_json(tmp_path / "collision_authority.json", {"digest_claim": "a" * 64})
    freeze = freeze_inference(tmp_path, dataset_manifest_sha256="a" * 64,
                              config_sha256="b" * 64)
    with pytest.raises(ValueError, match="lineage is absent"):
        load_frozen_collision_binding(tmp_path, freeze, repo_root=ROOT,
                                      expected_source_sha256="c" * 64)
