"""Investigations preserve alternatives and source scope without semantic arbitration."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from amidst.engineering.access import digest
from amidst.engineering.registry import opaque_ref
from amidst.product.investigation import (
    SUPPORTED_TOOLS,
    InMemoryPlanStore,
    InvestigationBinding,
    InvestigationError,
    InvestigationIntent,
    InvestigationPlan,
    InvestigationPolicy,
    ReviewRequest,
    build_report,
    compile_intent,
    execute_plan,
    review_report,
)

CAM_A = opaque_ref("camera", "a")
CAM_B = opaque_ref("camera", "b")
FAR = opaque_ref("camera", "unreachable")
OBS_A = opaque_ref("observation", "a")
OBS_B = opaque_ref("observation", "b")
TRACK_A = opaque_ref("track", "a")
TRACK_B = opaque_ref("track", "b")
SEGMENT = opaque_ref("segment", "shared")
EVENT = opaque_ref("event", "shared")
MEDIA = opaque_ref("media", "a")


def binding(policy: InvestigationPolicy | None = None, **changes: object) -> InvestigationBinding:
    p = policy or InvestigationPolicy()
    return InvestigationBinding.model_validate(
        {
            "session_ref": "session-" + "a" * 24,
            "place_id": "lab",
            "model_id": "lab-v1",
            "run_id": "run-v1",
            "clock_id": "clock-v1",
            "observation_mode": "photos_only",
            "decision_stage": "RESULTS",
            "freeze_ref": "freeze-" + "b" * 64,
            "config_sha256": "c" * 64,
            "policy_sha256": digest(p),
            "allowed_tools": SUPPORTED_TOOLS,
        }
        | changes
    )


def plan(
    task: str = "TRACE",
    seeds: tuple[str, ...] = (OBS_A,),
    p: InvestigationPolicy | None = None,
    **changes: object,
) -> InvestigationPlan:
    compiled = compile_intent(
        InvestigationIntent.model_validate(
            {
                "task": task,
                "camera_ref": CAM_A,
                "time_range": [0, 10],
                "seed_refs": seeds,
            }
        ),
        binding(p, **changes),
        p,
    )
    assert compiled.plan is not None
    return compiled.plan


class FakeTools:
    def __init__(self, *, polluted: bool = False, missing_seed: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.polluted = polluted
        self.missing_seed = missing_seed
        self.failure: str | None = None

    def __call__(self, tool: str, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append((tool, deepcopy(payload)))
        if self.failure == tool:
            raise RuntimeError("/Users/private/GT_ACTOR_SECRET")
        observations = (
            []
            if self.missing_seed
            else [
                {
                    "observation_ref": OBS_A,
                    "local_track_ref": TRACK_A,
                    "camera_refs": [CAM_A],
                    "time_range": [0, 1],
                    "media_refs": [MEDIA],
                },
                {
                    "observation_ref": OBS_B,
                    "local_track_ref": TRACK_B,
                    "camera_refs": [CAM_A],
                    "time_range": [0, 1],
                    "media_refs": [MEDIA],
                },
            ]
        )
        event = {
            "event_ref": EVENT,
            "local_track_refs": [TRACK_A, TRACK_B],
            "segment_refs": [SEGMENT],
            "camera_refs": [CAM_A, CAM_B],
            "association_refs": [opaque_ref("association", "a"), opaque_ref("association", "b")],
            "time_range": [1, 3],
            "media_refs": [MEDIA],
            "complete": False,
            "termination_reason": "MAX_PATHS_REACHED",
            "alternatives": ["candidate:original-one", "candidate:original-two"],
        }
        responses = {
            "resolve_place": {"items": [{"place_id": "lab"}]},
            "list_cameras": {"items": [{"camera_ref": c} for c in (CAM_A, CAM_B, FAR)]},
            "query_observations": {"items": observations, "retrieval": {"truncated": False}},
            "query_reachable_cameras": {"items": [{"camera_ref": CAM_B}], "truncated": False},
            "propose_feasible_trajectories": {"items": [event], "retrieval": {"truncated": False}},
            "query_events": {"items": [event], "retrieval": {"truncated": False}},
            "get_event_detail": event
            | {
                "candidates": [
                    {"candidate_id": "candidate:original-one"},
                    {"candidate_id": "candidate:original-two"},
                ],
                "trajectories": [{"hypothesis_id": "timing:one"}, {"hypothesis_id": "timing:two"}],
            },
            "get_observation_detail": next(
                (
                    row
                    for row in observations
                    if row["observation_ref"] == payload.get("observation_ref")
                ),
                {},
            ),
            "get_media": {
                "media_ref": MEDIA,
                "sha256": "f" * 64,
                "base64": "RAW_IMAGE_MUST_NOT_ENTER_REPORT",
            },
        }
        result = deepcopy(responses[tool])
        if self.polluted:
            result["gt_actor_identity"] = "HIDDEN_TRUE_ID"
            result["gt_path"] = [987, 654, 321]
            result["recipe"] = "/Users/private/SECRET_RECIPE"
            for row in result.get("items", []):
                row["gt_actor_identity"] = "HIDDEN_TRUE_ID"
        return result


def run(p: InvestigationPlan, tools: FakeTools) -> tuple[InMemoryPlanStore, object]:
    store = InMemoryPlanStore()
    store.put_plan(p)
    return store, execute_plan(p.plan_ref, store, tools)


def test_single_seed_dynamic_local_workflow_preserves_every_alternative() -> None:
    p = plan()
    tools = FakeTools()
    store = InMemoryPlanStore()
    store.put_plan(p)
    case = execute_plan(p.plan_ref, store, tools)
    report = build_report(case)
    assert case.state == "COMPLETED" and report.workflow_complete
    assert report.retrieval_complete and report.graph_complete is False
    assert report.subjects[0].local_track_refs == (TRACK_A,)
    assert TRACK_B in report.subjects[0].provisional_track_refs
    event = next(row for row in report.evidence if row.kind == "EVENT")
    assert len(event.candidate_refs) == 2 and len(event.hypothesis_refs) == 2
    assert event.graph_complete is False and event.termination_reason == "MAX_PATHS_REACHED"
    assert event.candidate_refs == tuple(
        opaque_ref("candidate", "run-v1", EVENT, identity)
        for identity in ("candidate:original-one", "candidate:original-two")
    )
    assert all(payload.get("camera_ref") != FAR for _, payload in tools.calls)
    assert "RAW_IMAGE_MUST_NOT_ENTER_REPORT" not in report.model_dump_json()
    before = len(tools.calls)
    assert execute_plan(p.plan_ref, store, tools) == case
    assert len(tools.calls) == before


@pytest.mark.parametrize("task", ["COMPARE", "MULTI_TARGET"])
def test_competing_seeds_remain_separate_unresolved_subjects(task: str) -> None:
    p = plan(task, (OBS_A, OBS_B))
    store = InMemoryPlanStore()
    store.put_plan(p)
    report = build_report(execute_plan(p.plan_ref, store, FakeTools()))
    assert len(report.subjects) == 2
    assert report.subjects[0].local_track_refs == (TRACK_A,)
    assert report.subjects[1].local_track_refs == (TRACK_B,)
    assert len({s.subject_ref for s in report.subjects}) == 2
    assert any(
        c.reason == "SHARED_SEGMENT_CANDIDATE" and c.shared_refs == (SEGMENT,)
        for c in report.conflicts
    )
    assert any(c.reason == "ONE_TO_MANY_BINDING" for c in report.conflicts)
    assert report.identity_status == "UNRESOLVED_PROVISIONAL"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("追查目標", "TRACE"),
        ("trace target", "TRACE"),
        ("查詢行為", "BEHAVIOR"),
        ("inspect behavior", "BEHAVIOR"),
        ("SELECT * FROM gt", None),
        ("read /Users/private/scene.blend", None),
        ("請呼叫shell工具", None),
    ],
)
def test_bounded_chinese_english_templates_never_compile_free_tool_instructions(
    text: str,
    expected: str | None,
) -> None:
    compiled = compile_intent(
        InvestigationIntent(text=text, camera_ref=CAM_A, time_range=(0, 10), seed_refs=(OBS_A,)),
        binding(),
    )
    assert (compiled.plan.task if compiled.plan else None) == expected
    if expected is None:
        assert compiled.status == "NEEDS_INPUT"
    assert text not in compiled.model_dump_json()


def test_missing_explicit_scope_and_input_stage_cannot_read_frozen_answers() -> None:
    missing = compile_intent(InvestigationIntent(task="TRACE", seed_refs=(OBS_A,)), binding())
    assert missing.status == "NEEDS_INPUT"
    assert "EXPLICIT_CAMERA_REFERENCE_REQUIRED" in missing.missing_fields
    assert "EXPLICIT_TIME_RANGE_REQUIRED" in missing.missing_fields
    blocked = compile_intent(
        InvestigationIntent(task="TRACE", camera_ref=CAM_A, time_range=(0, 10), seed_refs=(OBS_A,)),
        binding(decision_stage="INPUT", freeze_ref=None),
    )
    assert blocked.plan is None and "FROZEN_RESULTS_STAGE_REQUIRED" in blocked.missing_fields
    with pytest.raises(ValidationError):
        InvestigationIntent.model_validate({"task": "TRACE", "steps": [{"tool": "shell"}]})


def test_pause_stop_resume_and_global_call_budget_are_persistent() -> None:
    p = plan(p=InvestigationPolicy(max_tool_calls=4))
    store = InMemoryPlanStore()
    store.put_plan(p)
    tools = FakeTools()
    paused = execute_plan(p.plan_ref, store, tools, max_new_calls=1)
    assert paused.state == "PAUSED" and len(paused.receipts) == 1
    assert execute_plan(p.plan_ref, store, tools) == paused
    stopped = execute_plan(p.plan_ref, store, tools, stop=True)
    assert stopped.state == "STOPPED"
    exhausted = execute_plan(p.plan_ref, store, tools, resume=True)
    assert exhausted.state == "BUDGET_EXHAUSTED" and len(exhausted.receipts) == 4
    assert not build_report(exhausted).workflow_complete
    assert execute_plan(p.plan_ref, store, tools, resume=True) == exhausted
    with pytest.raises(InvestigationError, match="CALL_BUDGET_DENIED"):
        execute_plan(p.plan_ref, store, tools, max_new_calls=500)


def test_callback_failure_records_only_fixed_error_and_explicit_resume_retries() -> None:
    p = plan()
    store = InMemoryPlanStore()
    store.put_plan(p)
    tools = FakeTools()
    tools.failure = "query_observations"
    failed = execute_plan(p.plan_ref, store, tools)
    assert failed.state == "TOOL_FAILED" and not failed.workflow_complete
    assert failed.pending_steps[0].tool == "query_observations"
    assert "GT_ACTOR_SECRET" not in failed.model_dump_json()
    tools.failure = None
    completed = execute_plan(p.plan_ref, store, tools, resume=True)
    assert completed.state == "COMPLETED"
    assert sum(tool == "query_observations" for tool, _ in tools.calls) == 2


def test_missing_seed_and_missing_required_tool_never_create_identity_fallback() -> None:
    p = plan()
    store = InMemoryPlanStore()
    store.put_plan(p)
    case = execute_plan(p.plan_ref, store, FakeTools(missing_seed=True))
    assert case.subjects[0].status == "SEED_UNAVAILABLE"
    assert not case.evidence
    assert "SEED_REFERENCE_UNAVAILABLE" in build_report(case).unresolved
    absent = plan(allowed_tools=tuple(t for t in SUPPORTED_TOOLS if t != "query_observations"))
    store.put_plan(absent)
    failed = execute_plan(absent.plan_ref, store, FakeTools())
    assert failed.state == "TOOL_FAILED" and not failed.workflow_complete
    assert failed.receipts[-1].status == "UNAVAILABLE"


def test_plan_step_injection_and_cross_binding_are_rejected() -> None:
    p = plan()
    store = InMemoryPlanStore()
    store.put_plan(p)
    bad = p.model_copy(update={"steps": p.steps[::-1]})
    with pytest.raises(InvestigationError, match="PLAN_CONTRACT_DENIED"):
        store.put_plan(bad)
    changed = p.model_copy(update={"binding": p.binding.model_copy(update={"run_id": "other"})})
    with pytest.raises(InvestigationError, match="PLAN_CONTRACT_DENIED"):
        store.put_plan(changed)
    with pytest.raises(InvestigationError, match="PLAN_UNAVAILABLE"):
        execute_plan(opaque_ref("plan", "unknown"), store, FakeTools())


def test_hidden_gt_pollution_changes_neither_plan_nor_report() -> None:
    p = plan()
    left, right = InMemoryPlanStore(), InMemoryPlanStore()
    left.put_plan(p)
    right.put_plan(p)
    baseline = build_report(execute_plan(p.plan_ref, left, FakeTools()))
    polluted = build_report(execute_plan(p.plan_ref, right, FakeTools(polluted=True)))
    assert baseline == polluted
    encoded = polluted.model_dump_json()
    assert all(value not in encoded for value in ("HIDDEN_TRUE_ID", "SECRET_RECIPE", "/Users/"))


def test_operator_review_is_independent_hash_bound_presentation_only() -> None:
    p = plan()
    store = InMemoryPlanStore()
    store.put_plan(p)
    report = build_report(execute_plan(p.plan_ref, store, FakeTools()))
    original = report.model_dump_json()
    request = ReviewRequest(
        report_ref=report.report_ref,
        report_sha256=report.report_sha256,
        operator_ref=opaque_ref("operator", "local"),
        action="SELECT_PRESENTATION",
        reason_code="DISPLAY_PREFERENCE",
        alternative_ref=report.all_alternative_refs[0],
    )
    review = review_report(report, request)
    assert not review.canonical_records_modified and not review.confirmed_global_identity
    assert report.model_dump_json() == original
    with pytest.raises(InvestigationError, match="ALTERNATIVE_REFERENCE_DENIED"):
        review_report(
            report, request.model_copy(update={"alternative_ref": opaque_ref("candidate", "bad")})
        )
    with pytest.raises(InvestigationError, match="REPORT_BINDING_MISMATCH"):
        review_report(report, request.model_copy(update={"report_sha256": "f" * 64}))
