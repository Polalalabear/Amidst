import pytest

from amidst.engineering.access import AccessDenied, FreezeReceipt, RunBinding, SessionGuard


def binding(mode: str = "photos_only") -> RunBinding:
    return RunBinding.model_validate({
        "place_id": "lab", "model_id": "lab-v1", "model_revision": "1",
        "source_ref": "source-lab", "spatial_context_id": "context-lab",
        "run_id": "run-v1", "clock_id": "clock-v1", "observation_mode": mode,
        **{name + "_sha256": "a" * 64 for name in (
            "dataset", "config", "producer", "registry", "media",
        )},
    })


def test_photos_only_cannot_read_results_until_bound_freeze() -> None:
    scope = binding()
    guard = SessionGuard(scope)
    for tool in ("query_observations", "query_events", "get_event_detail", "get_replay"):
        with pytest.raises(AccessDenied, match="STAGE_DENIED"):
            guard.require(guard.session_ref, tool)  # type: ignore[arg-type]
    receipt = FreezeReceipt.create(scope, {"events": []}, {"tracks": []})
    guard.freeze(receipt, {"events": []}, {"tracks": []})
    guard.require(guard.session_ref, "get_replay")
    assert guard.context(()).freeze_ref == "freeze-" + receipt.receipt_sha256


@pytest.mark.parametrize("field", [
    "run_id", "observation_mode", "config_sha256", "dataset_sha256", "producer_sha256",
    "registry_sha256", "media_sha256", "source_ref", "spatial_context_id", "clock_id",
])
def test_any_freeze_binding_change_is_rejected(field: str) -> None:
    scope = binding()
    replacement = "photos_plus_observations" if field == "observation_mode" else (
        "b" * 64 if field.endswith("sha256") else "different"
    )
    changed = RunBinding.model_validate(scope.model_dump() | {field: replacement})
    receipt = FreezeReceipt.create(changed, {}, {})
    guard = SessionGuard(scope)
    with pytest.raises(AccessDenied, match="FREEZE_BINDING_MISMATCH"):
        guard.freeze(receipt, {}, {})
    assert guard.stage == "INPUT"


def test_plus_input_and_cross_session_are_bound() -> None:
    guard = SessionGuard(binding("photos_plus_observations"))
    guard.require(guard.session_ref, "query_observations")
    with pytest.raises(AccessDenied, match="STAGE_DENIED"):
        guard.require(guard.session_ref, "get_event_summary")
    with pytest.raises(AccessDenied, match="SCOPE_DENIED"):
        guard.require("session-other-run", "get_media")
    receipt = FreezeReceipt.create(guard.binding, {}, {})
    with pytest.raises(AccessDenied):
        guard.freeze(receipt, {"changed": True}, {})
