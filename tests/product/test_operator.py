"""Durable, frozen RGB investigation and independent operator review contracts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.engineering.access import digest
from amidst.engineering.local_pilot import build_run
from amidst.engineering.registry import opaque_ref
from amidst.engineering.research_scene import DEFAULT_CONFIG
from amidst.product.investigation import (
    InvestigationError,
    InvestigationIntent,
    InvestigationPolicy,
    PlanStep,
    ReviewRequest,
)
from amidst.product.operator import OperatorWorkspace, report_html
from amidst.product.run import build_product, load_product


@pytest.fixture(scope="module")
def operator_source(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("operator-rgb-source")
    config = json.loads(DEFAULT_CONFIG.read_bytes())
    config["duration_s"] = 6.0
    config_path = root.parent / (root.name + "-config.json")
    config_path.write_text(json.dumps(config))
    build_run(root, run_id="operator-rgb-fixture-v1", config_path=config_path)
    return root


@pytest.fixture(scope="module")
def frozen_operator_product(
    operator_source: Path, tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    root = tmp_path_factory.mktemp("operator-frozen-product")
    build_product(operator_source, root,
                  video_pool=tmp_path_factory.mktemp("operator-video-pool"), encode_video=False)
    return root


@pytest.fixture
def operator_product(frozen_operator_product: Path, tmp_path: Path) -> Path:
    root = tmp_path / "product"
    # Canonical JSON/catalog only: every test shares the immutable source RGB.
    shutil.copytree(frozen_operator_product, root)
    return root


def trace_intent(workspace: OperatorWorkspace) -> InvestigationIntent:
    base = workspace.service.base
    event = next(e for e in base.events.values() if e["candidates"])
    seed = next(o for o in base.observations.values()
                if o["local_track_ref"] in event["local_track_refs"])
    return InvestigationIntent(task="TRACE", text="追查目標", camera_ref=seed["camera_refs"][0],
                               time_range=(0, 6), seed_refs=(seed["observation_ref"],))


def test_pause_stop_resume_and_report_survive_restart_without_canonical_writes(
    operator_product: Path,
) -> None:
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0])
        receipt = workspace.service.repository.verify_run(workspace.service.scope.run_ref)
        compiled = workspace.compile(trace_intent(workspace))
        assert compiled.status == "READY" and compiled.plan is not None
        plan = compiled.plan
        assert workspace.compile(trace_intent(workspace)).plan == plan
        paused = workspace.execute(plan.plan_ref, max_new_calls=3)
        assert paused.state == "PAUSED" and len(paused.receipts) == 3
        assert workspace.execute(plan.plan_ref) == paused  # Resume is explicit.
        partial = workspace.report(plan.plan_ref)
        assert partial.workflow_complete is False
        assert partial.identity_status == "UNRESOLVED_PROVISIONAL"
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0])
        assert workspace.store.get_plan(plan.plan_ref) == plan
        assert workspace.store.get_case(plan.plan_ref) == paused
        assert workspace.report(plan.plan_ref) == partial
        stopped = workspace.execute(plan.plan_ref, stop=True)
        assert stopped.state == "STOPPED" and stopped.receipts == paused.receipts
        assert workspace.execute(plan.plan_ref) == stopped
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0])
        case = workspace.execute(plan.plan_ref, max_new_calls=6, resume=True)
        assert case.receipts[:3] == paused.receipts
        while case.state == "PAUSED":
            case = workspace.execute(plan.plan_ref, max_new_calls=6, resume=True)
        assert case.state == "COMPLETED" and case.workflow_complete
        assert {r.sequence for r in case.receipts} == set(range(len(case.receipts)))
        assert all(r.status == "OK" for r in case.receipts)
        report = workspace.report(plan.plan_ref)
        assert report.workflow_complete and report.retrieval_complete
        assert report.all_alternative_refs
        assert report.graph_complete is not None  # Independent from workflow completion.
        assert workspace.service.repository.verify_run(workspace.service.scope.run_ref) == receipt
        assert workspace.execute(plan.plan_ref, resume=True) == case
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0])
        assert workspace.report(plan.plan_ref) == report
        assert workspace.service.repository.verify_run(workspace.service.scope.run_ref) == receipt


def test_report_keeps_every_canonical_candidate_and_hypothesis_in_original_order(
    operator_product: Path,
) -> None:
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0])
        plan = workspace.compile(trace_intent(workspace)).plan
        assert plan is not None
        case = workspace.execute(plan.plan_ref)
        report = workspace.report(plan.plan_ref)
        checked = 0
        for evidence in report.evidence:
            if not evidence.detail_received or evidence.kind != "EVENT":
                continue
            original = workspace.service.base.events[evidence.record_ref]
            expected_candidates = tuple(opaque_ref("candidate", plan.binding.run_id,
                evidence.record_ref, c["candidate_id"]) for c in original["candidates"])
            expected_hypotheses = tuple(opaque_ref("hypothesis", plan.binding.run_id,
                evidence.record_ref, h["hypothesis_id"]) for h in original["trajectories"])
            assert evidence.candidate_refs == expected_candidates
            assert evidence.hypothesis_refs == expected_hypotheses
            assert set(expected_candidates + expected_hypotheses) <= set(
                report.all_alternative_refs)
            checked += bool(expected_candidates)
        assert checked and report.tool_receipt_refs == tuple(r.receipt_ref for r in case.receipts)
        assert "IDENTITIES_REMAIN_PROVISIONAL" in report.unresolved
        public = report.model_dump_json()
        assert str(runtime.source) not in public and "base64" not in public
        assert "gt_actor" not in public and "global_actor" not in public


def test_review_identity_hash_and_alternative_are_server_bound_and_append_only(
    operator_product: Path,
) -> None:
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0])
        plan = workspace.compile(trace_intent(workspace)).plan
        assert plan is not None
        workspace.execute(plan.plan_ref)
        report = workspace.report(plan.plan_ref)
        receipt = workspace.service.repository.verify_run(workspace.service.scope.run_ref)
        request = ReviewRequest(report_ref=report.report_ref, report_sha256=report.report_sha256,
            operator_ref=workspace.service.context().operator_ref, action="SELECT_PRESENTATION",
            reason_code="DISPLAY_PREFERENCE", alternative_ref=report.all_alternative_refs[0])
        with pytest.raises(InvestigationError, match="^OPERATOR_SCOPE_DENIED$"):
            workspace.review(request.model_copy(update={
                "operator_ref": opaque_ref("operator", "untrusted-caller")}))
        with pytest.raises(InvestigationError, match="REPORT_BINDING_MISMATCH"):
            workspace.review(request.model_copy(update={"report_sha256": "f" * 64}))
        with pytest.raises(InvestigationError, match="ALTERNATIVE_REFERENCE_DENIED"):
            workspace.review(request.model_copy(update={
                "alternative_ref": opaque_ref("candidate", "unavailable")}))
        review = workspace.review(request)
        assert workspace.review(request) == review  # Idempotent receipt, not overwritten evidence.
        assert review.canonical_records_modified is False
        assert review.confirmed_global_identity is False
        assert review.authority == "OPERATOR_PRESENTATION_REVIEW_ONLY"
        assert workspace.service.repository.verify_run(workspace.service.scope.run_ref) == receipt
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0])
        assert workspace.review(request) == review
        row = workspace.service.repository.get_revision(workspace.service.scope.run_ref,
                                                        "REVIEW", review.review_ref)
        assert row is not None and row.version == 1
        assert row.payload == review.model_dump(mode="json")
        assert workspace.report(plan.plan_ref) == report


def test_cross_mode_plan_and_review_cannot_reuse_another_session(
    operator_product: Path,
) -> None:
    with load_product(operator_product) as runtime:
        first, second = (OperatorWorkspace(s) for s in runtime.services)
        plan = first.compile(trace_intent(first)).plan
        assert plan is not None
        first.execute(plan.plan_ref)
        report = first.report(plan.plan_ref)
        with pytest.raises(InvestigationError, match="^PLAN_UNAVAILABLE$"):
            second.execute(plan.plan_ref)
        request = ReviewRequest(report_ref=report.report_ref, report_sha256=report.report_sha256,
            operator_ref=second.service.context().operator_ref, action="PRESERVE_AMBIGUITY",
            reason_code="AMBIGUOUS_EVIDENCE")
        with pytest.raises(InvestigationError, match="^REPORT_UNAVAILABLE$"):
            second.review(request)


def test_policy_budget_and_case_state_are_durable_not_reset_by_resume(
    operator_product: Path,
) -> None:
    policy = InvestigationPolicy(max_tool_calls=4)
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0], policy)
        plan = workspace.compile(trace_intent(workspace)).plan
        assert plan is not None and plan.binding.policy_sha256 == digest(policy)
        case = workspace.execute(plan.plan_ref)
        assert case.state == "BUDGET_EXHAUSTED" and len(case.receipts) == 4
        assert case.pending_steps and not case.workflow_complete
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0], policy)
        assert workspace.execute(plan.plan_ref, max_new_calls=4, resume=True) == case
        report = workspace.report(plan.plan_ref)
        assert not report.workflow_complete and "TOOL_BUDGET_EXHAUSTED" in report.unresolved
        # Policy/session binding cannot be changed after the plan is stored.
        default_workspace = OperatorWorkspace(runtime.services[0])
        with pytest.raises(InvestigationError, match="^PLAN_BINDING_MISMATCH$"):
            default_workspace.execute(plan.plan_ref)


def test_tool_failure_private_text_is_not_saved_and_restart_retry_keeps_receipts(
    operator_product: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0])
        plan = workspace.compile(trace_intent(workspace)).plan
        assert plan is not None
        def unavailable(*args: object, **kwargs: object) -> dict[str, object]:
            raise OSError("private /Users/operator/source/raw.json secret gt_actor_42")
        monkeypatch.setattr(workspace.service, "call", unavailable)
        case = workspace.execute(plan.plan_ref, max_new_calls=1)
        assert case.state == "TOOL_FAILED" and len(case.receipts) == 1
        assert case.receipts[0].error_code == "TOOL_FAILED"
        assert "secret" not in case.model_dump_json()
        report = workspace.report(plan.plan_ref)
        assert "raw.json" not in report.model_dump_json()
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0])
        retry = workspace.execute(plan.plan_ref, max_new_calls=1, resume=True)
        assert retry.state == "PAUSED" and len(retry.receipts) == 2
        assert retry.receipts[0] == case.receipts[0]
        assert retry.receipts[1].status == "OK"


def test_strict_intent_and_stored_step_injection_are_denied(operator_product: Path) -> None:
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0])
        intent = trace_intent(workspace)
        with pytest.raises(ValidationError):
            InvestigationIntent.model_validate(intent.model_dump() | {
                "steps": [{"tool": "shell", "path": "/private/raw"}]})
        plan = workspace.compile(intent).plan
        assert plan is not None
        for value in (True, 1.0, "1", 0, 257):
            with pytest.raises(InvestigationError, match="^CALL_BUDGET_DENIED$"):
                workspace.execute(plan.plan_ref, max_new_calls=value)  # type: ignore[arg-type]
        injected = plan.model_copy(update={
            "plan_ref": opaque_ref("plan", "injected"),
            "steps": (*plan.steps, PlanStep(step_ref=opaque_ref("step", "injected"),
                tool="get_media", phase="MEDIA", evidence_ref=opaque_ref("media", "private"))),
        })
        workspace.store.put_plan(injected)
        with pytest.raises(InvestigationError, match="^PLAN_CONTRACT_DENIED$"):
            workspace.execute(injected.plan_ref)
        assert workspace.store.get_case(injected.plan_ref) is None


def test_report_export_uses_escaped_safe_evidence_without_private_source(
    operator_product: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_bytes = Path.read_bytes
    def rgb_boundary(path: Path) -> bytes:
        assert "simulation" not in path.parts, "operator must not read the GT sidecar"
        return read_bytes(path)
    monkeypatch.setattr(Path, "read_bytes", rgb_boundary)
    with load_product(operator_product) as runtime:
        workspace = OperatorWorkspace(runtime.services[0])
        plan = workspace.compile(trace_intent(workspace)).plan
        assert plan is not None
        workspace.execute(plan.plan_ref)
        report = workspace.report(plan.plan_ref)
        exported = report_html(report)
        assert report.report_sha256 in exported and "UNRESOLVED_PROVISIONAL" in exported
        assert str(runtime.source) not in exported and "base64" not in exported
        unsafe = report.model_copy(update={"explanation": "<script>secret</script>"})
        assert "<script>" not in report_html(unsafe)
        assert "&lt;script&gt;" in report_html(unsafe)
