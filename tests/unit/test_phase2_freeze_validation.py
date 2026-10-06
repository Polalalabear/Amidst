"""Freeze audit regressions without expanding the mock Integration Foundation."""

import json
import subprocess
from pathlib import Path
from urllib.parse import urlencode

import pytest

import amidst.storage.json_files as json_files
from amidst.domain.stream import BoundGapEvent
from amidst.domain.trajectory import TerminationReason
from amidst.integration.api import IntegrationApplication, api_contract, encode_event_key
from amidst.integration.consumer import replay_frame, to_consumer_event
from amidst.integration.contracts import EventPage, ObservationPage
from amidst.integration.local_repository import LocalJsonRepository
from amidst.integration.repositories import RepositorySnapshot
from amidst.integration.service import MockIntegrationService
from amidst.integration.wiring import build_mock_service

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/integration/mock_v1.json"
ROUTES = (
    "/v1/contract", "/v1/observations", "/v1/events", "/v1/events/{event_key}",
    "/v1/events/{event_key}/trajectories", "/v1/events/{event_key}/consumer",
    "/v1/events/{event_key}/replay",
)


@pytest.fixture(scope="module")
def service() -> MockIntegrationService:
    return build_mock_service(CONFIG, search_clock=lambda: 0.0)


def _request(service: MockIntegrationService, route: str) -> tuple[str, str]:
    gap = service.repository.snapshot().gaps[0]
    path = route.replace("{event_key}", encode_event_key(gap.event.event_id))
    if route in {"/v1/observations", "/v1/events"}:
        end = max(item.observation.end_time for item in service.repository.snapshot().observations)
        query = urlencode({"start": 0, "end": end})
    elif route.endswith("/replay"):
        query = urlencode({"timestamp": gap.event.time_range[0]})
    else:
        query = ""
    return path, query


@pytest.mark.parametrize("route", ROUTES)
def test_advertised_get_runtime_schema_and_error_status_matrix(
    route: str, service: MockIntegrationService,
) -> None:
    application = IntegrationApplication(service)
    path, query = _request(service, route)
    contract = api_contract()
    advertised = next(endpoint for endpoint in contract.endpoints if endpoint.path == route)
    status, response = application.handle("GET", path, query)
    assert status == 200
    assert type(response).__name__ == advertised.response
    assert contract.schemas[advertised.response] == type(response).model_json_schema()
    assert type(response).model_validate_json(response.model_dump_json()) == response
    invalid = query + ("&" if query else "") + "unexpected=1"
    assert application.handle("GET", path, invalid)[0] == 400
    assert application.handle("POST", path, query)[0] == 405
    if "{event_key}" in route:
        unknown = route.replace("{event_key}", encode_event_key("SYNTHETIC:unknown"))
        assert application.handle("GET", unknown, query)[0] == 404
        malformed = route.replace("{event_key}", "e-!!!!")
        assert application.handle("GET", malformed, query)[0] == 400


@pytest.mark.parametrize("query", ["", "timestamp=nan", "timestamp=1&timestamp=2"])
def test_replay_invalid_queries_are_400(query: str, service: MockIntegrationService) -> None:
    path, _ = _request(service, "/v1/events/{event_key}/replay")
    assert IntegrationApplication(service).handle("GET", path, query)[0] == 400


def test_http_point_queries_include_both_event_and_observation_boundaries(
    service: MockIntegrationService,
) -> None:
    application = IntegrationApplication(service)
    for gap in service.repository.snapshot().gaps:
        for timestamp in gap.event.time_range:
            query = urlencode({"start": timestamp, "end": timestamp,
                               "source_id": gap.binding.source_id})
            status, response = application.handle("GET", "/v1/events", query)
            assert status == 200
            assert EventPage.model_validate_json(response.model_dump_json()).items == (gap,)
        for endpoint in (gap.start, gap.end):
            for timestamp in (endpoint.observation.start_time, endpoint.observation.end_time):
                query = urlencode({"start": timestamp, "end": timestamp,
                                   "source_id": gap.binding.source_id,
                                   "camera_id": endpoint.observation.camera_id})
                status, response = application.handle("GET", "/v1/observations", query)
                assert status == 200
                assert ObservationPage.model_validate_json(response.model_dump_json()).items == (
                    endpoint,
                )


def test_local_atomic_publish_failure_preserves_existing_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service: MockIntegrationService,
) -> None:
    store = tmp_path / "store.json"
    repository = LocalJsonRepository(store)
    before = store.read_bytes()

    def fail_replace(source: object, destination: object) -> None:
        raise OSError("injected single-writer publication failure")

    monkeypatch.setattr(json_files.os, "replace", fail_replace)
    with pytest.raises(OSError, match="publication failure"):
        repository.add(service.repository.snapshot())
    assert store.read_bytes() == before
    assert repository.snapshot() == RepositorySnapshot()
    assert tuple(tmp_path.iterdir()) == (store,)


def test_typescript_preserves_nullable_and_empty_incomplete_positive_contracts(
    tmp_path: Path, service: MockIntegrationService, node_with_typescript: str,
) -> None:
    node = node_with_typescript
    original = service.repository.snapshot().gaps[0]
    nullable = original.model_dump(mode="json")
    for endpoint in (nullable["start"], nullable["end"]):
        endpoint["observation"].update(
            track_ids=["SYNTHETIC:contract-only"], stitching_count=0, fragment_count=1,
            appearance_embedding=[0.125, 0.25], appearance_labels=["SYNTHETIC"],
            appearance_quality=0.7, tracking_quality=0.5,
            source_video_reference="SYNTHETIC:video-reference-only",
            entry_direction=[1, 0, 0], exit_direction=[0, 1, 0],
            projection_quality=1, occlusion_quality=0.2, observation_quality=0.5,
        )
    incomplete = original.model_dump(mode="json")
    incomplete["event"]["termination_reason"] = TerminationReason.MAX_SEARCH_NODES
    incomplete["search_result"].update(
        termination_reason=TerminationReason.MAX_SEARCH_NODES, complete=False,
    )
    empty = original.model_dump(mode="json")
    empty["event"].update(termination_reason=TerminationReason.NO_FEASIBLE_PATH,
                          candidates=[], trajectories=[])
    empty["search_result"].update(termination_reason=TerminationReason.NO_FEASIBLE_PATH,
                                  candidates=[], complete=True)
    payloads = []
    for gap in (original, *(BoundGapEvent.model_validate(value)
                           for value in (nullable, incomplete, empty))):
        timestamp = sum(gap.event.time_range) / 2
        payloads.append({"event": to_consumer_event(gap).model_dump(mode="json"),
                         "frame": replay_frame(gap, timestamp).model_dump(mode="json")})
    fixture = tmp_path / "consumer-variants.json"
    fixture.write_text(json.dumps(payloads))
    module = ROOT / "frontend/phase2/consumer.ts"
    script = (
        "import {readFileSync} from 'node:fs';"
        "import {strict as assert} from 'node:assert';"
        "import {validateConsumerEvent,validateReplayFrame,WORLD_UP} from "
        + json.dumps(module.as_uri()) + ";"
        "const rows=JSON.parse(readFileSync(process.argv[1], 'utf8'));"
        "assert.deepEqual(WORLD_UP,[0,0,1]);"
        "for (const row of rows) { const before=JSON.stringify(row);"
        "assert.equal(validateConsumerEvent(row.event),row.event);"
        "assert.equal(validateReplayFrame(row.frame,row.event),row.frame);"
        "assert.equal(JSON.stringify(row),before); }"
        "assert.equal(rows[0].event.gap.start.observation.track_ids,null);"
        "assert.deepEqual(rows[1].event.gap.start.observation.appearance_embedding,[0.125,0.25]);"
        "assert.equal(rows[2].event.gap.search_result.complete,false);"
        "assert.deepEqual(rows[3].frame.markers,[]);"
    )
    subprocess.run([node, "--input-type=module", "-e", script, str(fixture)],
                   check=True, capture_output=True, text=True)
