"""Persistent operator workflow separate from immutable evidence and inference."""

from __future__ import annotations

from html import escape
from typing import cast

from amidst.engineering.access import digest
from amidst.product.investigation import (
    SUPPORTED_TOOLS,
    CompileResult,
    InvestigationBinding,
    InvestigationCase,
    InvestigationError,
    InvestigationIntent,
    InvestigationPlan,
    InvestigationPolicy,
    InvestigationReport,
    OperatorReview,
    ReviewRequest,
    build_report,
    compile_intent,
    execute_plan,
    review_report,
)
from amidst.product.service import ProductService
from amidst.product.store import Payload, SQLiteProductStore


class SQLitePlanStore:
    def __init__(self, repository: SQLiteProductStore, run_ref: str,
                 binding: InvestigationBinding) -> None:
        self.repository, self.run_ref, self.binding = repository, run_ref, binding

    def get_plan(self, plan_ref: str) -> InvestigationPlan:
        revision = self.repository.get_revision(self.run_ref, "CASE", plan_ref, version=1)
        if revision is None or revision.payload.get("type") != "PLAN":
            raise InvestigationError("PLAN_UNAVAILABLE")
        plan = InvestigationPlan.model_validate(revision.payload.get("plan"))
        if plan.binding != self.binding:
            raise InvestigationError("PLAN_BINDING_MISMATCH")
        return plan

    def put_plan(self, plan: InvestigationPlan) -> None:
        if plan.binding != self.binding:
            raise InvestigationError("PLAN_BINDING_MISMATCH")
        existing = self.repository.get_revision(self.run_ref, "CASE", plan.plan_ref)
        if existing is not None:
            if self.get_plan(plan.plan_ref) != plan:
                raise InvestigationError("PLAN_CONFLICT")
            return
        self.repository.append_revision(self.run_ref, "CASE", plan.plan_ref,
            cast(Payload, {"type": "PLAN", "plan": plan.model_dump(mode="json")}),
            expected_version=0)

    def get_case(self, plan_ref: str) -> InvestigationCase | None:
        self.get_plan(plan_ref)
        revision = self.repository.get_revision(self.run_ref, "CASE", plan_ref)
        if revision is None or revision.payload.get("type") != "STATE":
            return None
        case = InvestigationCase.model_validate(revision.payload.get("case"))
        if case.binding != self.binding or case.plan_ref != plan_ref:
            raise InvestigationError("CASE_BINDING_MISMATCH")
        return case

    def put_case(self, case: InvestigationCase) -> None:
        self.get_plan(case.plan_ref)
        if case.binding != self.binding:
            raise InvestigationError("CASE_BINDING_MISMATCH")
        previous = self.get_case(case.plan_ref)
        if previous == case:
            return
        if previous is not None and case.revision <= previous.revision:
            raise InvestigationError("CASE_REVISION_CONFLICT")
        revision = self.repository.get_revision(self.run_ref, "CASE", case.plan_ref)
        assert revision is not None
        self.repository.append_revision(self.run_ref, "CASE", case.plan_ref,
            cast(Payload, {"type": "STATE", "case": case.model_dump(mode="json")}),
            expected_version=revision.version)


class OperatorWorkspace:
    def __init__(self, service: ProductService,
                 policy: InvestigationPolicy | None = None) -> None:
        policy = InvestigationPolicy() if policy is None else policy
        self.service, self.policy = service, policy
        context = service.context()
        allowed = tuple(name for name in context.allowed_tools
                        if name in SUPPORTED_TOOLS)
        self.binding = InvestigationBinding(
            session_ref=context.session_ref, place_id=context.context.place_id,
            model_id=context.context.model_id, run_id=context.context.run_id,
            clock_id=context.context.clock_id, observation_mode=context.context.observation_mode,
            decision_stage=context.context.decision_stage, freeze_ref=context.product_freeze_ref,
            config_sha256=service.scope.config_sha256, policy_sha256=digest(policy),
            allowed_tools=allowed,
        )
        self.store = SQLitePlanStore(service.repository, service.scope.run_ref, self.binding)

    def compile(self, intent: InvestigationIntent) -> CompileResult:
        if self.binding.decision_stage != "RESULTS":
            return compile_intent(intent, self.binding, self.policy)
        if intent.camera_ref is not None:
            self.service._camera(intent.camera_ref)
        if intent.seed_refs:
            self.service._seed_tracks(intent.seed_refs)
        result = compile_intent(intent, self.binding, self.policy)
        if result.plan is not None:
            self.store.put_plan(result.plan)
        return result

    def execute(self, plan_ref: str, *, max_new_calls: int | None = None,
                stop: bool = False, resume: bool = False) -> InvestigationCase:
        return execute_plan(plan_ref, self.store, self.service.call,
                            max_new_calls=max_new_calls, stop=stop, resume=resume)

    def report(self, plan_ref: str) -> InvestigationReport:
        case = self.store.get_case(plan_ref)
        if case is None:
            raise InvestigationError("CASE_UNAVAILABLE")
        report = build_report(case)
        previous = self.service.repository.get_revision(self.service.scope.run_ref, "REPORT",
                                                        report.report_ref)
        payload = cast(Payload, report.model_dump(mode="json"))
        if previous is None:
            self.service.repository.append_revision(self.service.scope.run_ref, "REPORT",
                report.report_ref, payload, expected_version=0)
        elif previous.payload != payload:
            raise InvestigationError("REPORT_CONFLICT")
        return report

    def review(self, request: ReviewRequest) -> OperatorReview:
        if request.operator_ref != self.service.context().operator_ref:
            raise InvestigationError("OPERATOR_SCOPE_DENIED")
        record = self.service.repository.get_revision(self.service.scope.run_ref, "REPORT",
                                                      request.report_ref)
        if record is None:
            raise InvestigationError("REPORT_UNAVAILABLE")
        report = InvestigationReport.model_validate(record.payload)
        if report.binding != self.binding:
            raise InvestigationError("REPORT_BINDING_MISMATCH")
        review = review_report(report, request)
        existing = self.service.repository.get_revision(self.service.scope.run_ref, "REVIEW",
                                                        review.review_ref)
        payload = cast(Payload, review.model_dump(mode="json"))
        if existing is None:
            self.service.repository.append_revision(self.service.scope.run_ref, "REVIEW",
                review.review_ref, payload, expected_version=0)
        elif existing.payload != payload:
            raise InvestigationError("REVIEW_CONFLICT")
        return review


def report_html(report: InvestigationReport) -> str:
    rows = "".join(f"<tr><td>{escape(item.record_ref)}</td><td>{escape(item.kind)}</td>"
                   f"<td>{len(item.alternative_refs)}</td>"
                   f"<td>{escape(str(item.graph_complete))}</td></tr>" for item in report.evidence)
    unresolved = "".join(f"<li>{escape(item)}</li>" for item in report.unresolved)
    return ("<!doctype html><html lang='zh-Hant'><meta charset='utf-8'>"
        "<title>Amidst 調查證據報告</title><style>body{font:16px system-ui;max-width:1000px;"
        "margin:40px auto;padding:20px}td,th{padding:10px;text-align:left;"
        "border-bottom:1px solid #ddd}"
        "code{word-break:break-all}</style><h1>Amidst 本機調查證據報告</h1>"
        f"<p>{escape(report.explanation)}</p><p>run：{escape(report.binding.run_id)}；mode："
        f"{escape(report.binding.observation_mode)}；state：{escape(report.state)}</p>"
        f"<p>subject inquiries：{len(report.subjects)}；保留替代假設："
        f"{len(report.all_alternative_refs)}；身分：UNRESOLVED_PROVISIONAL</p>"
        f"<p>Workflow complete={report.workflow_complete}，retrieval complete="
        f"{report.retrieval_complete}，Graph complete={report.graph_complete}</p>"
        "<table><tr><th>Evidence reference</th><th>Kind</th><th>Alternatives</th>"
        f"<th>Graph complete</th></tr>{rows}</table><h2>未解項目</h2><ul>{unresolved}</ul>"
        f"<p>Report hash：<code>{escape(report.report_sha256)}</code></p>"
        "<p>SYNTHETIC；此報告沒有確認全域身分、行為意圖或正式研究驗收。</p></html>")
