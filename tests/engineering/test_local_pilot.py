"""Frozen indexed tool flow, evidence isolation and tampering integration checks."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from amidst.engineering.access import digest
from amidst.engineering.facade import ToolFailure
from amidst.engineering.local_association import AssociationPolicy, build_inference
from amidst.engineering.local_pilot import (
    LocalApplication,
    _load,
    build_run,
    load_services,
    mock_agent,
)
from amidst.engineering.perception import produce_perception


@pytest.fixture(scope="module")
def run_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("indexed-pilot")
    build_run(root, run_id="test-indexed-tool-flow")
    return root


def test_full_scoped_flow_and_direct_evidence_reads(run_root: Path) -> None:
    services = load_services(run_root)
    flows = [mock_agent(service) for service in services]
    assert len(flows) == 2
    assert all(flow["cards"] for flow in flows)
    assert {entry["tool"] for flow in flows for entry in flow["tools"]} == {
        "resolve_place",
        "list_cameras",
        "query_events",
        "get_event_summary",
        "get_event_detail",
        "get_media",
        "get_replay",
    }
    for service in services:
        session = {"session_ref": service.guard.session_ref}
        camera = next(iter(service.cameras))
        observations = service.call(
            "query_observations",
            session
            | {
                "camera_ref": camera,
                "time_range": [0, 1],
            },
        )
        assert observations["retrieval"]["records_read"] < len(service.observations)
        event = next(iter(service.events.values()))
        assert 1 <= len(event["media_refs"]) <= 5
        assert len(event["media_refs"]) == len(event["source_frames"])
        assert event["detail_ref"] == event["event_ref"]
        # Neither tool contexts nor logs carry raw paths, recipes or actor labels.
        public = json.dumps({"flow": mock_agent(service), "context": service.context()})
        for secret in (
            str(run_root),
            "actor_identity",
            "shirt_rgb",
            "recipe",
            "render_annotations",
        ):
            assert secret not in public


def test_missing_anchor_wrong_scope_and_caller_stage_denied(run_root: Path) -> None:
    service = load_services(run_root)[0]
    session = {"session_ref": service.guard.session_ref}
    with pytest.raises(ToolFailure, match="LOCAL_ANCHOR_REQUIRED"):
        service.call("query_events", session | {"time_range": [0, 24]})
    with pytest.raises(ToolFailure, match="SCOPE_DENIED"):
        service.call(
            "query_events", session | {"time_range": [0, 24], "camera_ref": "camera:" + "f" * 24}
        )
    with pytest.raises(ToolFailure, match="INVALID_OR_UNAVAILABLE"):
        service.call("list_cameras", session | {"decision_stage": "RESULTS"})
    with pytest.raises(ToolFailure, match="SCOPE_DENIED"):
        service.call("list_cameras", {"session_ref": "session-another-run"})
    with pytest.raises(ToolFailure, match="REFERENCE_DENIED"):
        service.call("get_media", session | {"media_ref": "media:" + "f" * 24})


def test_input_modes_cannot_bypass_frozen_stage(run_root: Path) -> None:
    photos, plus = load_services(run_root, input_stage=True)
    session = {"session_ref": photos.guard.session_ref}
    camera = next(iter(photos.cameras))
    with pytest.raises(ToolFailure, match="STAGE_DENIED"):
        photos.call("query_observations", session | {"camera_ref": camera, "time_range": [0, 2]})
    with pytest.raises(ToolFailure, match="STAGE_DENIED"):
        photos.call("get_event_detail", session | {"event_ref": next(iter(photos.events))})
    visible = plus.call(
        "query_observations",
        {
            "session_ref": plus.guard.session_ref,
            "camera_ref": camera,
            "time_range": [0, 24],
        },
    )
    assert visible["items"]
    assert all(
        "projected_path" not in item and "region_ids" not in item for item in visible["items"]
    )
    assert all("measurements" in item for item in visible["items"])
    with pytest.raises(ToolFailure, match="STAGE_DENIED"):
        plus.call(
            "query_observations",
            {
                "session_ref": plus.guard.session_ref,
                "region_id": "west",
                "time_range": [0, 24],
            },
        )


def test_gt_poison_removal_preserves_runtime_and_recomputed_pixels(run_root: Path) -> None:
    package, _, topology, manifest = _load(run_root)
    before = [mock_agent(s) for s in load_services(run_root)]
    original = package.simulation_export_path.read_bytes()
    try:
        package.simulation_export_path.write_text('{"recipe":"poison","reference":"fake"}')
        assert [mock_agent(s) for s in load_services(run_root)] == before
        package.simulation_export_path.unlink()
        assert [mock_agent(s) for s in load_services(run_root)] == before
        pixels = produce_perception(
            package.frames, model_id=package.model_id, run_id=package.run_id
        )
        from amidst.engineering.local_index import RetrievalPolicy

        inference = build_inference(
            pixels,
            scope=package.scope,
            context=package.context,
            topology=topology,
            policy=AssociationPolicy.model_validate(manifest["association_policy"]),
            retrieval_policy=RetrievalPolicy.model_validate(manifest["retrieval_policy"]),
        )
        assert digest(inference) == manifest["receipts"]["photos_only"]["inference_sha256"]
        assert (
            digest(pixels.model_dump(mode="json"))
            == manifest["receipts"]["photos_only"]["measurement_sha256"]
        )
    finally:
        package.simulation_export_path.write_bytes(original)


@pytest.mark.parametrize(
    "filename",
    [
        "manifest.json",
        "events_photos_only.json",
        "runtime_config.json",
        "inference_photos_only.json",
    ],
)
def test_frozen_artifact_tampering_rejected(run_root: Path, filename: str) -> None:
    path = run_root / filename
    original = path.read_bytes()
    try:
        payload = json.loads(original)
        if filename == "manifest.json":
            payload["receipts"]["photos_only"]["binding"]["run_id"] = "wrong-run"
        elif filename.startswith("events"):
            payload["events"][0]["uncertainty"] = "poisoned certainty"
        elif filename == "runtime_config.json":
            payload["fps"] = 999
        else:
            payload["association_pool_sha256"] = "f" * 64
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError):
            load_services(run_root)
    finally:
        path.write_bytes(original)


def test_transport_fixed_errors_and_unsafe_extra_fields(run_root: Path) -> None:
    app = LocalApplication(load_services(run_root))
    statuses: list[str] = []

    def respond(status: str, headers: list[tuple[str, str]]) -> None:
        statuses.append(status)

    result = app(
        {
            "PATH_INFO": "/api/tool/list_cameras",
            "REQUEST_METHOD": "POST",
            "QUERY_STRING": "mode=photos_only",
            "CONTENT_LENGTH": "20",
            "wsgi.input": BytesIO(b'{"secret":"/private"}'),
        },
        respond,
    )
    assert statuses == ["400 Bad Request"]
    assert b"/private" not in b"".join(result)
    assert b"INVALID_OR_UNAVAILABLE" in b"".join(result)
    result = app(
        {
            "PATH_INFO": "/api/context",
            "REQUEST_METHOD": "GET",
            "QUERY_STRING": "mode=photos_only&stage=RESULTS",
        },
        respond,
    )
    assert statuses[-1] == "400 Bad Request"


def test_runtime_queries_do_not_enumerate_record_maps(run_root: Path) -> None:
    service = load_services(run_root)[0]

    class DirectOnly(dict[str, Any]):
        def values(self) -> Any:
            raise AssertionError("global record scan")

        def items(self) -> Any:
            raise AssertionError("global record scan")

        def __iter__(self) -> Any:
            raise AssertionError("global record scan")

    service.events = DirectOnly(service.events)
    session = {"session_ref": service.guard.session_ref}
    camera = next(iter(service.cameras))
    result = service.call("query_events", session | {"camera_ref": camera, "time_range": [0, 24]})
    assert result["items"]
    ref = result["items"][0]["event_ref"]
    assert service.call("get_event_detail", session | {"event_ref": ref})["event_ref"] == ref


def test_new_checkpoint_reuses_pixels_preserves_old_freeze(run_root: Path) -> None:
    old_manifest = (run_root / "manifest.json").read_bytes()
    _, original_registry, _, original = _load(run_root)
    checkpoint = run_root / "checkpoints" / "reused"
    rebuilt = build_run(checkpoint, run_id="test-indexed-tool-flow", reuse_from=run_root)
    services = load_services(checkpoint)
    assert not (checkpoint / "rgb").exists()
    assert services[0].store.registry.sha256 == original_registry.sha256
    assert rebuilt["receipts"] == original["receipts"]
    assert (run_root / "manifest.json").read_bytes() == old_manifest
    assert mock_agent(services[0])["cards"]
