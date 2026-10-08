"""Local deterministic investigation planning, execution and operator review.

Only structured intent and allowlisted tool evidence enter this layer. It never
reads a scene, image locator, simulator truth, external model or raw archive.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Literal, Protocol, Self

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel, Timestamp
from amidst.engineering.access import digest
from amidst.engineering.registry import ResourceRef, opaque_ref

Task = Literal["TRACE", "COMPARE", "BEHAVIOR", "MULTI_TARGET"]
ExecutionState = Literal[
    "READY",
    "RUNNING",
    "PAUSED",
    "STOPPED",
    "COMPLETED",
    "TOOL_FAILED",
    "BUDGET_EXHAUSTED",
]
InvestigationTool = Literal[
    "resolve_place",
    "list_cameras",
    "query_observations",
    "query_events",
    "query_reachable_cameras",
    "propose_feasible_trajectories",
    "get_observation_detail",
    "get_event_detail",
    "get_media",
]
SUPPORTED_TOOLS: tuple[InvestigationTool, ...] = (
    "resolve_place",
    "list_cameras",
    "query_observations",
    "query_events",
    "query_reachable_cameras",
    "propose_feasible_trajectories",
    "get_observation_detail",
    "get_event_detail",
    "get_media",
)
_REF = re.compile(r"^[a-z]+:[0-9a-f]{24}$")
_TEMPLATES: dict[str, Task] = {
    "trace": "TRACE",
    "trace target": "TRACE",
    "追查": "TRACE",
    "追查目標": "TRACE",
    "compare": "COMPARE",
    "compare targets": "COMPARE",
    "比較": "COMPARE",
    "比較目標": "COMPARE",
    "behavior": "BEHAVIOR",
    "inspect behavior": "BEHAVIOR",
    "行為": "BEHAVIOR",
    "查詢行為": "BEHAVIOR",
    "multi target": "MULTI_TARGET",
    "multi-target": "MULTI_TARGET",
    "多目標": "MULTI_TARGET",
    "多目標調查": "MULTI_TARGET",
}


class InvestigationError(ValueError):
    """A fixed safe code, never callback exception text or caller arguments."""


class InvestigationPolicy(DomainModel):
    policy_version: Literal["local.investigation.policy.v1"] = "local.investigation.policy.v1"
    max_tool_calls: int = Field(default=32, ge=4, le=256, strict=True)
    max_cameras: int = Field(default=4, ge=1, le=32, strict=True)
    max_hops: int = Field(default=3, ge=0, le=16, strict=True)
    max_details: int = Field(default=8, ge=0, le=128, strict=True)
    max_media: int = Field(default=4, ge=0, le=64, strict=True)
    max_subjects: int = Field(default=8, ge=2, le=32, strict=True)


class InvestigationBinding(DomainModel):
    session_ref: str = Field(pattern=r"^session-[0-9a-f]{24}$")
    place_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    clock_id: str = Field(min_length=1)
    observation_mode: Literal["photos_only", "photos_plus_observations"]
    decision_stage: Literal["INPUT", "RESULTS"]
    freeze_ref: str | None = None
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    allowed_tools: tuple[InvestigationTool, ...]


class InvestigationIntent(DomainModel):
    task: Task | None = None
    text: str | None = Field(default=None, max_length=160)
    camera_ref: ResourceRef | None = None
    time_range: tuple[Timestamp, Timestamp] | None = None
    seed_refs: tuple[ResourceRef, ...] = ()

    @model_validator(mode="after")
    def explicit_scope(self) -> Self:
        if self.time_range is not None and self.time_range[1] < self.time_range[0]:
            raise ValueError("ordered explicit time range required")
        if len(set(self.seed_refs)) != len(self.seed_refs):
            raise ValueError("seed references must be unique")
        return self


class PlanStep(DomainModel):
    step_ref: ResourceRef
    tool: InvestigationTool
    camera_ref: ResourceRef | None = None
    evidence_ref: ResourceRef | None = None
    phase: Literal["LOCATE", "ANCHOR", "EXPAND", "ALTERNATIVES", "DETAIL", "MEDIA"]


class InvestigationPlan(DomainModel):
    schema_version: Literal["local.investigation.plan.v1"] = "local.investigation.plan.v1"
    plan_ref: ResourceRef
    plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    binding: InvestigationBinding
    policy: InvestigationPolicy
    task: Task
    camera_ref: ResourceRef
    time_range: tuple[Timestamp, Timestamp]
    seed_refs: tuple[ResourceRef, ...]
    procedure: Literal["LOCATE_ANCHOR_LOCAL_EXPAND_PRESERVE_REPORT_V1"] = (
        "LOCATE_ANCHOR_LOCAL_EXPAND_PRESERVE_REPORT_V1"
    )
    steps: tuple[PlanStep, ...]


class CompileResult(DomainModel):
    status: Literal["READY", "NEEDS_INPUT"]
    plan: InvestigationPlan | None = None
    missing_fields: tuple[str, ...] = ()


class EvidenceRecord(DomainModel):
    record_ref: ResourceRef
    kind: Literal["OBSERVATION", "EVENT"]
    camera_refs: tuple[ResourceRef, ...] = ()
    local_track_refs: tuple[ResourceRef, ...] = ()
    segment_refs: tuple[ResourceRef, ...] = ()
    association_refs: tuple[ResourceRef, ...] = ()
    media_refs: tuple[ResourceRef, ...] = ()
    alternative_refs: tuple[ResourceRef, ...] = ()
    candidate_refs: tuple[ResourceRef, ...] = ()
    hypothesis_refs: tuple[ResourceRef, ...] = ()
    subject_refs: tuple[ResourceRef, ...] = ()
    time_range: tuple[Timestamp, Timestamp] | None = None
    termination_reason: str | None = None
    graph_complete: bool | None = None
    missing_evidence: bool = False
    detail_received: bool = False


class SafeToolResult(DomainModel):
    records: tuple[EvidenceRecord, ...] = ()
    camera_refs: tuple[ResourceRef, ...] = ()
    found_count: int = Field(default=0, ge=0)
    retrieval_truncated: bool = False
    media_ref: ResourceRef | None = None
    media_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ToolReceipt(DomainModel):
    receipt_ref: ResourceRef
    sequence: int = Field(ge=0)
    step: PlanStep
    status: Literal["OK", "ERROR", "UNAVAILABLE"]
    error_code: Literal["TOOL_FAILED", "TOOL_UNAVAILABLE", "REFERENCE_UNAVAILABLE"] | None = None
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    result: SafeToolResult | None = None


class SubjectInquiry(DomainModel):
    subject_ref: ResourceRef
    seed_ref: ResourceRef
    anchor_observation_refs: tuple[ResourceRef, ...] = ()
    local_track_refs: tuple[ResourceRef, ...] = ()
    provisional_track_refs: tuple[ResourceRef, ...] = ()
    evidence_refs: tuple[ResourceRef, ...] = ()
    alternative_refs: tuple[ResourceRef, ...] = ()
    status: Literal["UNRESOLVED", "SEED_UNAVAILABLE"] = "UNRESOLVED"


class SubjectConflict(DomainModel):
    subject_refs: tuple[ResourceRef, ...]
    shared_refs: tuple[ResourceRef, ...]
    reason: Literal["SHARED_SEGMENT_CANDIDATE", "ONE_TO_MANY_BINDING", "UNRESOLVED_EVENT_SEED_LINK"]


class InvestigationCase(DomainModel):
    case_ref: ResourceRef
    plan_ref: ResourceRef
    binding: InvestigationBinding
    state: ExecutionState = "READY"
    pending_steps: tuple[PlanStep, ...]
    receipts: tuple[ToolReceipt, ...] = ()
    subjects: tuple[SubjectInquiry, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    conflicts: tuple[SubjectConflict, ...] = ()
    unresolved: tuple[str, ...] = ()
    retrieval_complete: bool | None = None
    workflow_complete: bool = False
    graph_complete: bool | None = None
    revision: int = Field(default=0, ge=0)


class InvestigationReport(DomainModel):
    schema_version: Literal["local.investigation.report.v1"] = "local.investigation.report.v1"
    report_ref: ResourceRef
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_ref: ResourceRef
    plan_ref: ResourceRef
    binding: InvestigationBinding
    state: ExecutionState
    subjects: tuple[SubjectInquiry, ...]
    evidence: tuple[EvidenceRecord, ...]
    conflicts: tuple[SubjectConflict, ...]
    all_alternative_refs: tuple[ResourceRef, ...]
    unresolved: tuple[str, ...]
    tool_receipt_refs: tuple[ResourceRef, ...]
    retrieval_complete: bool | None
    workflow_complete: bool
    graph_complete: bool | None
    explanation: str
    identity_status: Literal["UNRESOLVED_PROVISIONAL"] = "UNRESOLVED_PROVISIONAL"
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"


class ReviewRequest(DomainModel):
    report_ref: ResourceRef
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operator_ref: ResourceRef
    action: Literal["PRESERVE_AMBIGUITY", "REQUEST_EVIDENCE", "SELECT_PRESENTATION"]
    reason_code: Literal["AMBIGUOUS_EVIDENCE", "MISSING_EVIDENCE", "DISPLAY_PREFERENCE"]
    alternative_ref: ResourceRef | None = None


class OperatorReview(DomainModel):
    review_ref: ResourceRef
    request: ReviewRequest
    review_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority: Literal["OPERATOR_PRESENTATION_REVIEW_ONLY"] = "OPERATOR_PRESENTATION_REVIEW_ONLY"
    canonical_records_modified: Literal[False] = False
    confirmed_global_identity: Literal[False] = False


class ToolCallback(Protocol):
    def __call__(self, tool: str, payload: dict[str, object]) -> dict[str, object]: ...


class PlanStore(Protocol):
    def get_plan(self, plan_ref: str) -> InvestigationPlan: ...
    def put_plan(self, plan: InvestigationPlan) -> None: ...
    def get_case(self, plan_ref: str) -> InvestigationCase | None: ...
    def put_case(self, case: InvestigationCase) -> None: ...


class InMemoryPlanStore:
    def __init__(self) -> None:
        self._plans: dict[str, InvestigationPlan] = {}
        self._cases: dict[str, InvestigationCase] = {}

    def get_plan(self, plan_ref: str) -> InvestigationPlan:
        try:
            return self._plans[plan_ref]
        except KeyError:
            raise InvestigationError("PLAN_UNAVAILABLE") from None

    def put_plan(self, plan: InvestigationPlan) -> None:
        _verify_plan(plan)
        previous = self._plans.get(plan.plan_ref)
        if previous is not None and previous != plan:
            raise InvestigationError("PLAN_CONFLICT")
        self._plans[plan.plan_ref] = plan

    def get_case(self, plan_ref: str) -> InvestigationCase | None:
        return self._cases.get(plan_ref)

    def put_case(self, case: InvestigationCase) -> None:
        plan = self.get_plan(case.plan_ref)
        if case.binding != plan.binding:
            raise InvestigationError("CASE_BINDING_MISMATCH")
        previous = self._cases.get(case.plan_ref)
        if previous is not None and case.revision <= previous.revision and case != previous:
            raise InvestigationError("CASE_REVISION_CONFLICT")
        self._cases[case.plan_ref] = case


def _step(
    plan_key: str,
    tool: InvestigationTool,
    phase: str,
    camera: str | None = None,
    evidence: str | None = None,
) -> PlanStep:
    return PlanStep.model_validate(
        {
            "step_ref": opaque_ref("step", plan_key, tool, phase, camera or "", evidence or ""),
            "tool": tool,
            "phase": phase,
            "camera_ref": camera,
            "evidence_ref": evidence,
        }
    )


def compile_intent(
    intent: InvestigationIntent,
    binding: InvestigationBinding,
    policy: InvestigationPolicy | None = None,
) -> CompileResult:
    policy = policy or InvestigationPolicy()
    intent = InvestigationIntent.model_validate(intent.model_dump())
    binding = InvestigationBinding.model_validate(binding.model_dump())
    task = intent.task or _TEMPLATES.get((intent.text or "").strip().casefold())
    missing: list[str] = []
    if task is None or (
        intent.text is not None
        and intent.task is None
        and intent.text.strip().casefold() not in _TEMPLATES
    ):
        missing.append("SUPPORTED_TASK_TEMPLATE_REQUIRED")
    if intent.camera_ref is None or not intent.camera_ref.startswith("camera:"):
        missing.append("EXPLICIT_CAMERA_REFERENCE_REQUIRED")
    if intent.time_range is None:
        missing.append("EXPLICIT_TIME_RANGE_REQUIRED")
    if task == "TRACE" and len(intent.seed_refs) != 1:
        missing.append("ONE_SEED_REFERENCE_REQUIRED")
    if task == "COMPARE" and len(intent.seed_refs) != 2:
        missing.append("TWO_SEED_REFERENCES_REQUIRED")
    if task == "MULTI_TARGET" and not 2 <= len(intent.seed_refs) <= policy.max_subjects:
        missing.append("BOUNDED_MULTIPLE_SEEDS_REQUIRED")
    if len(intent.seed_refs) > policy.max_subjects:
        missing.append("SUBJECT_BUDGET_EXCEEDED")
    if binding.decision_stage != "RESULTS" or binding.freeze_ref is None:
        missing.append("FROZEN_RESULTS_STAGE_REQUIRED")
    if binding.policy_sha256 != digest(policy):
        missing.append("POLICY_BINDING_MISMATCH")
    if missing:
        return CompileResult(status="NEEDS_INPUT", missing_fields=tuple(dict.fromkeys(missing)))
    assert task is not None and intent.camera_ref is not None and intent.time_range is not None
    core = {
        "binding": binding.model_dump(mode="json"),
        "policy": policy.model_dump(mode="json"),
        "task": task,
        "camera_ref": intent.camera_ref,
        "time_range": intent.time_range,
        "seed_refs": intent.seed_refs,
    }
    key = digest(core)
    steps = (
        _step(key, "resolve_place", "LOCATE"),
        _step(key, "list_cameras", "LOCATE"),
        _step(key, "query_observations", "ANCHOR", intent.camera_ref),
        _step(key, "query_reachable_cameras", "EXPAND", intent.camera_ref),
    )
    payload = core | {
        "steps": [step.model_dump(mode="json") for step in steps],
        "procedure": "LOCATE_ANCHOR_LOCAL_EXPAND_PRESERVE_REPORT_V1",
        "schema_version": "local.investigation.plan.v1",
    }
    sha = digest(payload)
    plan = InvestigationPlan.model_validate(
        payload
        | {
            "plan_sha256": sha,
            "plan_ref": opaque_ref("plan", sha),
        }
    )
    return CompileResult(status="READY", plan=plan)


def _verify_plan(plan: InvestigationPlan) -> None:
    if set(plan.__dict__) - set(type(plan).model_fields):
        raise InvestigationError("PLAN_CONTRACT_DENIED")
    rebuilt = compile_intent(
        InvestigationIntent(
            task=plan.task,
            camera_ref=plan.camera_ref,
            time_range=plan.time_range,
            seed_refs=plan.seed_refs,
        ),
        plan.binding,
        plan.policy,
    )
    if rebuilt.plan != plan:
        raise InvestigationError("PLAN_CONTRACT_DENIED")


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {key: item for key, item in value.items() if isinstance(key, str)}


def _rows(value: object) -> tuple[object, ...]:
    return tuple(value) if isinstance(value, (tuple, list)) else ()


def _refs(value: object) -> tuple[str, ...]:
    return tuple(item for item in _rows(value) if isinstance(item, str) and _REF.fullmatch(item))


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _alternative_refs(
    value: object, kind: str, plan: InvestigationPlan, record_ref: str
) -> tuple[str, ...]:
    result = []
    for item in _rows(value):
        data = _mapping(item)
        identity = data.get(kind + "_id") if data else item
        if isinstance(identity, str):
            result.append(
                identity
                if _REF.fullmatch(identity)
                else opaque_ref(kind, plan.binding.run_id, record_ref, identity)
            )
    return tuple(result)


def _record(
    row: dict[str, object], plan: InvestigationPlan, *, detail: bool = False
) -> EvidenceRecord | None:
    event_ref, observation_ref = row.get("event_ref"), row.get("observation_ref")
    identity = event_ref if isinstance(event_ref, str) else observation_ref
    if not isinstance(identity, str) or not _REF.fullmatch(identity):
        return None
    termination = row.get("termination_reason")
    if termination not in {
        "COMPLETE",
        "NO_FEASIBLE_PATH",
        "MAX_PATHS_REACHED",
        "MAX_SEARCH_NODES",
        "MAX_BRANCH_FACTOR",
        "SEARCH_TIMEOUT",
        "HOLD",
        "PROVISIONAL",
        "UNMATCHED",
        "INCOMPATIBLE",
    }:
        termination = None
    complete = row.get("complete")
    time = row.get("time_range")
    if not isinstance(time, (list, tuple)) or len(time) != 2:
        time = None
    tracks = _refs(row.get("local_track_refs"))
    if isinstance(row.get("local_track_ref"), str):
        tracks = _refs([row["local_track_ref"]])
    return EvidenceRecord.model_validate(
        {
            "record_ref": identity,
            "kind": "EVENT" if isinstance(event_ref, str) else "OBSERVATION",
            "camera_refs": _refs(row.get("camera_refs")),
            "local_track_refs": tracks,
            "segment_refs": _refs(row.get("segment_refs")),
            "association_refs": _refs(row.get("association_refs")),
            "media_refs": _refs(row.get("media_refs")),
            "alternative_refs": _alternative_refs(
                row.get("alternatives"), "alternative", plan, identity
            ),
            "candidate_refs": _alternative_refs(row.get("candidates"), "candidate", plan, identity),
            "hypothesis_refs": _alternative_refs(
                row.get("trajectories", row.get("hypotheses")), "hypothesis", plan, identity
            ),
            "time_range": time,
            "termination_reason": termination,
            "graph_complete": complete if isinstance(complete, bool) else None,
            "missing_evidence": bool(row.get("missing_evidence")),
            "detail_received": detail,
        }
    )


def _sanitize(
    tool: str, raw: dict[str, object], plan: InvestigationPlan, step: PlanStep
) -> SafeToolResult:
    if "scope" in raw:
        scope = _mapping(raw["scope"])
        if any(
            scope.get(key) != value
            for key, value in (
                ("session_ref", plan.binding.session_ref),
                ("run_id", plan.binding.run_id),
                ("clock_id", plan.binding.clock_id),
                ("observation_mode", plan.binding.observation_mode),
            )
        ):
            raise InvestigationError("REFERENCE_UNAVAILABLE")
    if tool == "get_media":
        ref, sha = raw.get("media_ref"), raw.get("sha256", raw.get("input_sha256"))
        if not isinstance(ref, str) or ref != step.evidence_ref or not isinstance(sha, str):
            raise InvestigationError("REFERENCE_UNAVAILABLE")
        return SafeToolResult(media_ref=ref, media_sha256=sha)
    if tool in ("get_event_detail", "get_observation_detail"):
        summary = _mapping(raw.get("summary"))
        row = (summary | raw) if summary else raw
        record = _record(row, plan, detail=True)
        if record is None or record.record_ref != step.evidence_ref:
            raise InvestigationError("REFERENCE_UNAVAILABLE")
        return SafeToolResult(records=(record,))
    items = tuple(_mapping(item) for item in _rows(raw.get("items")))
    records = tuple(record for row in items if (record := _record(row, plan)) is not None)
    cameras = tuple(
        ref
        for row in items
        if isinstance((ref := row.get("camera_ref")), str) and _REF.fullmatch(ref)
    )
    retrieval = _mapping(raw.get("retrieval"))
    return SafeToolResult(
        records=records,
        camera_refs=cameras,
        found_count=len(items),
        retrieval_truncated=raw.get("truncated") is True or retrieval.get("truncated") is True,
    )


def _request(step: PlanStep, plan: InvestigationPlan) -> dict[str, object]:
    request: dict[str, object] = {"session_ref": plan.binding.session_ref}
    if step.tool == "resolve_place":
        request["query"] = plan.binding.place_id
    elif step.tool == "query_reachable_cameras":
        request.update(camera_ref=step.camera_ref, max_hops=plan.policy.max_hops)
    elif step.tool in ("query_observations", "query_events", "propose_feasible_trajectories"):
        request.update(camera_ref=step.camera_ref, time_range=list(plan.time_range))
        if step.tool == "propose_feasible_trajectories":
            request["seed_refs"] = list(plan.seed_refs)
    elif step.tool == "get_event_detail":
        request["event_ref"] = step.evidence_ref
    elif step.tool == "get_observation_detail":
        request["observation_ref"] = step.evidence_ref
    elif step.tool == "get_media":
        request["media_ref"] = step.evidence_ref
    return request


def _updated(case: InvestigationCase, **changes: object) -> InvestigationCase:
    return InvestigationCase.model_validate(case.model_dump(mode="python") | changes)


def _merge_record(old: EvidenceRecord | None, new: EvidenceRecord) -> EvidenceRecord:
    if old is None:
        return new
    fields = (
        "camera_refs",
        "local_track_refs",
        "segment_refs",
        "association_refs",
        "media_refs",
        "alternative_refs",
        "candidate_refs",
        "hypothesis_refs",
        "subject_refs",
    )
    payload = old.model_dump(mode="python") | new.model_dump(mode="python")
    for field in fields:
        payload[field] = _unique(tuple(getattr(old, field)) + tuple(getattr(new, field)))
    payload["detail_received"] = old.detail_received or new.detail_received
    return EvidenceRecord.model_validate(payload)


def _subjects_for_records(
    case: InvestigationCase, records: tuple[EvidenceRecord, ...], plan: InvestigationPlan
) -> InvestigationCase:
    subjects = list(case.subjects)
    unresolved = list(case.unresolved)
    if not subjects and plan.task == "BEHAVIOR":
        for row in records[: plan.policy.max_subjects]:
            if row.kind == "OBSERVATION":
                subjects.append(
                    SubjectInquiry(
                        subject_ref=opaque_ref("subject", plan.plan_ref, row.record_ref),
                        seed_ref=row.record_ref,
                    )
                )
        if len(records) > plan.policy.max_subjects:
            unresolved.append("SUBJECT_BUDGET_EXCEEDED")
    evidence = {row.record_ref: row for row in case.evidence}
    for row in records:
        matched: list[int] = []
        for index, subject in enumerate(subjects):
            if row.kind == "OBSERVATION":
                if subject.seed_ref == row.record_ref or subject.seed_ref in row.local_track_refs:
                    matched.append(index)
            elif set((*subject.local_track_refs, *subject.provisional_track_refs)) & set(
                row.local_track_refs
            ):
                matched.append(index)
        if row.kind == "EVENT" and not row.local_track_refs:
            matched = list(range(len(subjects)))
            unresolved.append("UNRESOLVED_EVENT_SEED_LINK")
        if not matched:
            continue
        row = EvidenceRecord.model_validate(
            row.model_dump()
            | {
                "subject_refs": tuple(subjects[index].subject_ref for index in matched),
            }
        )
        evidence[row.record_ref] = _merge_record(evidence.get(row.record_ref), row)
        for index in matched:
            subject = subjects[index]
            subjects[index] = SubjectInquiry.model_validate(
                subject.model_dump()
                | {
                    "anchor_observation_refs": _unique(
                        subject.anchor_observation_refs
                        + ((row.record_ref,) if row.kind == "OBSERVATION" else ())
                    ),
                    "local_track_refs": _unique(subject.local_track_refs + row.local_track_refs)
                    if row.kind == "OBSERVATION"
                    else subject.local_track_refs,
                    "provisional_track_refs": _unique(
                        subject.provisional_track_refs + row.local_track_refs
                    )
                    if row.kind == "EVENT"
                    else subject.provisional_track_refs,
                    "evidence_refs": _unique(subject.evidence_refs + (row.record_ref,)),
                    "alternative_refs": _unique(
                        subject.alternative_refs
                        + row.alternative_refs
                        + row.candidate_refs
                        + row.hypothesis_refs
                        + row.association_refs
                    ),
                    "status": "UNRESOLVED",
                }
            )
    conflicts: list[SubjectConflict] = []
    for row in evidence.values():
        if len(row.subject_refs) > 1:
            conflicts.append(
                SubjectConflict(
                    subject_refs=row.subject_refs,
                    shared_refs=row.segment_refs or (row.record_ref,),
                    reason="SHARED_SEGMENT_CANDIDATE"
                    if row.segment_refs
                    else "UNRESOLVED_EVENT_SEED_LINK",
                )
            )
    for subject in subjects:
        events = tuple(
            row
            for row in evidence.values()
            if row.kind == "EVENT" and subject.subject_ref in row.subject_refs
        )
        bindings = _unique(tuple(ref for row in events for ref in row.association_refs))
        if len(bindings) > 1:
            conflicts.append(
                SubjectConflict(
                    subject_refs=(subject.subject_ref,),
                    shared_refs=bindings,
                    reason="ONE_TO_MANY_BINDING",
                )
            )
    flags = tuple(
        row.graph_complete
        for row in evidence.values()
        if row.kind == "EVENT" and row.graph_complete is not None
    )
    graph_complete = all(flags) if flags else None
    return _updated(
        case,
        subjects=tuple(subjects),
        evidence=tuple(evidence.values()),
        conflicts=tuple(conflicts),
        unresolved=_unique(tuple(unresolved)),
        graph_complete=graph_complete,
    )


def _advance(
    case: InvestigationCase, step: PlanStep, result: SafeToolResult | None, plan: InvestigationPlan
) -> InvestigationCase:
    pending = list(case.pending_steps)
    unresolved = list(case.unresolved)
    known_steps = {item.step_ref for item in pending} | {r.step.step_ref for r in case.receipts}

    def enqueue(item: PlanStep) -> None:
        if item.step_ref not in known_steps:
            pending.append(item)
            known_steps.add(item.step_ref)

    if step.phase == "ANCHOR":
        case = _subjects_for_records(case, result.records if result else (), plan)
        unresolved.extend(case.unresolved)
        subjects = []
        for subject in case.subjects:
            if not subject.anchor_observation_refs:
                subject = SubjectInquiry.model_validate(
                    subject.model_dump()
                    | {
                        "status": "SEED_UNAVAILABLE",
                    }
                )
                unresolved.append("SEED_REFERENCE_UNAVAILABLE")
            subjects.append(subject)
        case = _updated(case, subjects=tuple(subjects))
        if plan.task == "COMPARE" and "get_observation_detail" in plan.binding.allowed_tools:
            for subject in subjects:
                for ref in subject.anchor_observation_refs:
                    enqueue(_step(plan.plan_ref, "get_observation_detail", "DETAIL", evidence=ref))
    elif step.phase == "EXPAND":
        cameras = _unique((plan.camera_ref,) + (result.camera_refs if result else ()))
        if len(cameras) > plan.policy.max_cameras:
            unresolved.append("CAMERA_EXPANSION_BUDGET_EXHAUSTED")
        if result is None:
            unresolved.append("REACHABILITY_UNAVAILABLE_LOCAL_ANCHOR_ONLY")
        tool: InvestigationTool = (
            "propose_feasible_trajectories"
            if ("propose_feasible_trajectories" in plan.binding.allowed_tools)
            else "query_events"
        )
        for camera in cameras[: plan.policy.max_cameras]:
            enqueue(_step(plan.plan_ref, tool, "ALTERNATIVES", camera))
    elif step.phase in ("ALTERNATIVES", "DETAIL") and result is not None:
        case = _subjects_for_records(case, result.records, plan)
        unresolved.extend(case.unresolved)
        relevant = {row.record_ref for row in case.evidence}
        for row in result.records:
            if row.record_ref not in relevant:
                continue
            if row.kind == "EVENT" and not row.detail_received:
                used = sum(s.phase == "DETAIL" for s in pending) + sum(
                    r.step.phase == "DETAIL" for r in case.receipts
                )
                if used < plan.policy.max_details:
                    enqueue(
                        _step(plan.plan_ref, "get_event_detail", "DETAIL", evidence=row.record_ref)
                    )
                else:
                    unresolved.append("DETAIL_BUDGET_EXHAUSTED")
            if row.detail_received:
                for media in row.media_refs:
                    used = sum(s.phase == "MEDIA" for s in pending) + sum(
                        r.step.phase == "MEDIA" for r in case.receipts
                    )
                    if used < plan.policy.max_media:
                        enqueue(_step(plan.plan_ref, "get_media", "MEDIA", evidence=media))
                    else:
                        unresolved.append("MEDIA_BUDGET_EXHAUSTED")
    truncated = result.retrieval_truncated if result else False
    retrieval_complete = case.retrieval_complete
    if step.phase in ("ANCHOR", "EXPAND", "ALTERNATIVES"):
        retrieval_complete = (
            retrieval_complete is not False and result is not None and not truncated
        )
    if truncated:
        unresolved.append("RETRIEVAL_TRUNCATED")
    return _updated(
        case,
        pending_steps=tuple(pending),
        unresolved=_unique(tuple(unresolved)),
        retrieval_complete=retrieval_complete,
    )


def execute_plan(
    plan_ref: str,
    store: PlanStore,
    tools: ToolCallback,
    *,
    max_new_calls: int | None = None,
    stop: bool = False,
    resume: bool = False,
) -> InvestigationCase:
    """Execute only a stored compiled plan; callers never supply steps or scope."""
    plan = store.get_plan(plan_ref)
    _verify_plan(plan)
    if plan.plan_ref != plan_ref:
        raise InvestigationError("PLAN_REFERENCE_MISMATCH")
    if max_new_calls is not None and (
        not isinstance(max_new_calls, int)
        or isinstance(max_new_calls, bool)
        or max_new_calls <= 0
        or max_new_calls > plan.policy.max_tool_calls
    ):
        raise InvestigationError("CALL_BUDGET_DENIED")
    case = store.get_case(plan_ref)
    if case is None:
        case = InvestigationCase(
            case_ref=opaque_ref("case", plan_ref),
            plan_ref=plan_ref,
            binding=plan.binding,
            pending_steps=plan.steps,
            subjects=tuple(
                SubjectInquiry(subject_ref=opaque_ref("subject", plan_ref, ref), seed_ref=ref)
                for ref in plan.seed_refs
            ),
        )
    if case.binding != plan.binding:
        raise InvestigationError("CASE_BINDING_MISMATCH")
    if type(stop) is not bool or type(resume) is not bool:
        raise InvestigationError("EXECUTION_CONTROL_DENIED")
    if case.state in ("COMPLETED", "BUDGET_EXHAUSTED"):
        return case
    if stop:
        case = _updated(case, state="STOPPED", workflow_complete=False, revision=case.revision + 1)
        store.put_case(case)
        return case
    if case.state in ("COMPLETED", "BUDGET_EXHAUSTED") or (
        case.state in ("STOPPED", "TOOL_FAILED", "PAUSED") and not resume
    ):
        return case
    allowance = max_new_calls or plan.policy.max_tool_calls
    count = 0
    case = _updated(case, state="RUNNING")
    while case.pending_steps and count < allowance:
        if len(case.receipts) >= plan.policy.max_tool_calls:
            case = _updated(
                case,
                state="BUDGET_EXHAUSTED",
                workflow_complete=False,
                unresolved=_unique(case.unresolved + ("TOOL_BUDGET_EXHAUSTED",)),
            )
            break
        step, remaining = case.pending_steps[0], case.pending_steps[1:]
        request = _request(step, plan)
        result: SafeToolResult | None = None
        status: Literal["OK", "ERROR", "UNAVAILABLE"] = "OK"
        code: Literal["TOOL_FAILED", "TOOL_UNAVAILABLE", "REFERENCE_UNAVAILABLE"] | None = None
        if step.tool not in plan.binding.allowed_tools:
            status, code = "UNAVAILABLE", "TOOL_UNAVAILABLE"
        else:
            try:
                raw = tools(step.tool, request)
                result = _sanitize(step.tool, raw, plan, step)
            except InvestigationError:
                status, code = "ERROR", "REFERENCE_UNAVAILABLE"
            except Exception:
                status, code = "ERROR", "TOOL_FAILED"
        sequence = len(case.receipts)
        receipt = ToolReceipt(
            receipt_ref=opaque_ref(
                "toolreceipt",
                plan_ref,
                str(sequence),
                step.step_ref,
                status,
                digest(result) if result else "",
            ),
            sequence=sequence,
            step=step,
            status=status,
            error_code=code,
            request_sha256=digest(request),
            response_sha256=digest(result) if result else None,
            result=result,
        )
        case = _updated(case, pending_steps=remaining, receipts=case.receipts + (receipt,))
        if status == "ERROR":
            case = _updated(
                case,
                state="TOOL_FAILED",
                workflow_complete=False,
                pending_steps=(step, *remaining),
                unresolved=_unique(case.unresolved + ("TOOL_FAILED",)),
            )
        else:
            if status == "UNAVAILABLE":
                case = _updated(case, unresolved=_unique(case.unresolved + ("TOOL_UNAVAILABLE",)))
            if status == "UNAVAILABLE" and step.phase in ("LOCATE", "ANCHOR", "ALTERNATIVES"):
                case = _updated(
                    case,
                    state="TOOL_FAILED",
                    workflow_complete=False,
                    pending_steps=(step, *remaining),
                )
            else:
                case = _advance(case, step, result, plan)
            if (
                step.tool == "list_cameras"
                and result is not None
                and (plan.camera_ref not in result.camera_refs)
            ):
                case = _updated(
                    case,
                    state="TOOL_FAILED",
                    unresolved=_unique(case.unresolved + ("CAMERA_REFERENCE_UNAVAILABLE",)),
                )
        count += 1
        case = _updated(case, revision=case.revision + 1)
        store.put_case(case)
        if case.state == "TOOL_FAILED":
            return case
    if case.state == "RUNNING":
        budget_exhausted = bool(case.pending_steps) and len(case.receipts) >= (
            plan.policy.max_tool_calls
        )
        case = _updated(
            case,
            state="BUDGET_EXHAUSTED"
            if budget_exhausted
            else "PAUSED"
            if case.pending_steps
            else "COMPLETED",
            workflow_complete=not case.pending_steps,
            unresolved=_unique(
                case.unresolved + (("TOOL_BUDGET_EXHAUSTED",) if budget_exhausted else ())
            ),
            revision=case.revision + 1,
        )
        store.put_case(case)
    elif case.state == "BUDGET_EXHAUSTED":
        case = _updated(case, revision=case.revision + 1)
        store.put_case(case)
    return case


def build_report(case: InvestigationCase) -> InvestigationReport:
    alternatives = _unique(
        tuple(
            ref
            for row in case.evidence
            for ref in (
                *row.alternative_refs,
                *row.candidate_refs,
                *row.hypothesis_refs,
                *row.association_refs,
            )
        )
    )
    unresolved = _unique(case.unresolved + ("IDENTITIES_REMAIN_PROVISIONAL",))
    payload = {
        "schema_version": "local.investigation.report.v1",
        "case_ref": case.case_ref,
        "plan_ref": case.plan_ref,
        "binding": case.binding.model_dump(mode="json"),
        "state": case.state,
        "subjects": [s.model_dump(mode="json") for s in case.subjects],
        "evidence": [e.model_dump(mode="json") for e in case.evidence],
        "conflicts": [c.model_dump(mode="json") for c in case.conflicts],
        "all_alternative_refs": alternatives,
        "unresolved": unresolved,
        "tool_receipt_refs": [r.receipt_ref for r in case.receipts],
        "retrieval_complete": case.retrieval_complete,
        "workflow_complete": case.workflow_complete,
        "graph_complete": case.graph_complete,
        "identity_status": "UNRESOLVED_PROVISIONAL",
        "origin": "SYNTHETIC",
        "explanation": (
            f"{len(case.subjects)} camera-local seed inquiries retain {len(case.evidence)} "
            f"evidence records and {len(alternatives)} alternative references. "
            f"{len(case.conflicts)} conflicts remain. Workflow state: {case.state}. "
            "Tool completion, retrieval coverage and canonical Graph completeness are separate. "
            "No identity confirmation, semantic ranking or behavioral intent is inferred."
        ),
    }
    sha = digest(payload)
    return InvestigationReport.model_validate(
        payload
        | {
            "report_ref": opaque_ref("report", sha),
            "report_sha256": sha,
        }
    )


def review_report(report: InvestigationReport, request: ReviewRequest) -> OperatorReview:
    report_payload = report.model_dump(mode="json")
    report_payload.pop("report_ref")
    report_payload.pop("report_sha256")
    expected_hash = digest(report_payload)
    if report.report_sha256 != expected_hash or report.report_ref != opaque_ref(
        "report", expected_hash
    ):
        raise InvestigationError("REPORT_CONTRACT_DENIED")
    if request.report_ref != report.report_ref or request.report_sha256 != report.report_sha256:
        raise InvestigationError("REPORT_BINDING_MISMATCH")
    if request.action == "SELECT_PRESENTATION":
        if request.alternative_ref not in report.all_alternative_refs:
            raise InvestigationError("ALTERNATIVE_REFERENCE_DENIED")
    elif request.alternative_ref is not None:
        raise InvestigationError("REVIEW_REFERENCE_DENIED")
    sha = digest(request)
    return OperatorReview(review_ref=opaque_ref("review", sha), request=request, review_sha256=sha)
