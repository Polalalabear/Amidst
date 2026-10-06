"""Submission guards: entirely synthetic; never approve or apply school evidence."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "human_review"))
from apply_decisions import (  # noqa: E402
    apply_completed,
    approved_input_lock,
    safe_input_path,
    validate_decisions,
)
from assemble_review import content_hash, immutable_document  # noqa: E402


@pytest.fixture
def template() -> dict:
    document = {
        "metadata": {
            "checkpoint_sha": "fake",
            "source_sha256": "fake",
            "reviewer": "",
            "submitted_at": None,
            "automatic_settings": {"k_values": [1, 2, 3]},
            "case_blocker_map": {},
            "input_hashes": [],
            "scope_limitations": [],
        },
        "items": [
            {
                "id": f"HR-{i:02d}",
                "decision": None,
                "selected_option": None,
                "approve_options": [{"id": "ONLY", "payload": {"value": i}}],
            }
            for i in range(1, 5)
        ],
    }
    document["review_payload_sha256"] = content_hash(immutable_document(document))
    return document


def completed(template: dict) -> dict:
    result = copy.deepcopy(template)
    result["metadata"].update(reviewer="SYNTHETIC_TEST_ONLY", submitted_at="2026-10-06T00:00:00Z")
    for item in result["items"]:
        item.update(decision="APPROVE", selected_option="ONLY")
    return result


def test_pending_never_approves(template: dict) -> None:
    assert validate_decisions(template, template)["status"] == "HUMAN_REVIEW_PENDING"
    assert all(item["decision"] is None for item in template["items"])


def test_pending_application_writes_nothing(template: dict, tmp_path: Path) -> None:
    output = tmp_path / "not-created"
    with pytest.raises(ValueError, match="pending or blocking"):
        apply_completed(template, template, root=tmp_path, output=output)
    assert not output.exists()


def test_synthetic_complete_receipt_keeps_failed_certificate_and_formal_disabled(
    template: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    from types import SimpleNamespace

    (tmp_path / "human_review").mkdir()
    (tmp_path / "human_review/geometry_evidence.json").write_text("{}")
    calls = []

    def fake_certificate(*args: object) -> dict:
        calls.append(args)
        return {
            "certificate": None,
            "result": {"status": "REVIEW"},
            "declaration": {"test_only": True},
        }

    monkeypatch.setitem(
        sys.modules,
        "certificate_application",
        SimpleNamespace(regenerate_from_completed_review=fake_certificate),
    )
    output = tmp_path / "application"
    state = apply_completed(completed(template), template, root=tmp_path, output=output)
    assert len(calls) == 1
    assert state["certificate_status"] == "NOT_CERTIFIED"
    lock = json.loads((output / "approved_input_lock.json").read_text())
    assert not lock["formal_execution_enabled"]
    assert lock["physical_certificate_status"] == "NOT_CERTIFIED"
    assert json.loads((output / "certificate_result.json").read_text())["certificate"] is None
    assert (output / "manifest.json").is_file()
    with pytest.raises(ValueError, match="fresh"):
        apply_completed(completed(template), template, root=tmp_path, output=output)
    assert len(calls) == 1


@pytest.mark.parametrize("edit", ["epsilon", "source", "extra", "order", "input_hash"])
def test_immutable_edits_rejected(template: dict, edit: str) -> None:
    document = completed(template)
    if edit == "epsilon":
        document["items"][2]["approve_options"][0]["payload"]["value"] = 100
    elif edit == "source":
        document["metadata"]["source_sha256"] = "changed"
    elif edit == "extra":
        document["items"][0]["new_setting"] = True
    elif edit == "order":
        document["items"].reverse()
    else:
        document["metadata"]["input_hashes"].append({"path": "poison"})
    with pytest.raises(ValueError, match="immutable"):
        validate_decisions(document, template)


@pytest.mark.parametrize("choice", ["REJECT", "FIX_GEOMETRY", "KEEP_REVIEW"])
def test_nonapproval_blocks_application(template: dict, choice: str) -> None:
    document = completed(template)
    document["items"][0].update(decision=choice, selected_option=None)
    state = validate_decisions(document, template)
    assert state["status"] == "HUMAN_REVIEW_BLOCKED"
    assert not state["formal_execution_enabled"]


@pytest.mark.parametrize("option", [None, "CUSTOM", "AUTO"])
def test_approve_requires_defined_profile(template: dict, option: str | None) -> None:
    document = completed(template)
    document["items"][0]["selected_option"] = option
    with pytest.raises(ValueError, match="explicit profile"):
        validate_decisions(document, template)


def test_completed_approval_does_not_enable_formal(template: dict) -> None:
    document = completed(template)
    state = validate_decisions(document, template)
    assert state["status"] == "EXPLICIT_APPROVALS_READY_FOR_AUTOMATIC_CERTIFICATION"
    assert not approved_input_lock(document, "NOT_CERTIFIED")["formal_execution_enabled"]
    assert not approved_input_lock(document, "PASS")["legacy_diagnostic_artifacts_promoted"]


@pytest.mark.parametrize(
    "field,value",
    [("reviewer", ""), ("submitted_at", None), ("submitted_at", "2026-10-06T00:00:00")],
)
def test_complete_requires_human_identity_and_time(
    template: dict, field: str, value: object
) -> None:
    document = completed(template)
    document["metadata"][field] = value
    with pytest.raises(ValueError):
        validate_decisions(document, template)


@pytest.mark.parametrize(
    "path",
    [
        "../escape",
        "/absolute",
        "data/evaluation/truth.json",
        "data/ground_truth/secret",
        "data/simulation/recipe",
    ],
)
def test_path_boundary_refuses_truth_and_escape(tmp_path: Path, path: str) -> None:
    with pytest.raises(ValueError):
        safe_input_path(tmp_path, path)
