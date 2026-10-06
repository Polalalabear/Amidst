"""Mock composition, canonical queries and strict read-only transport boundaries."""

import json
import subprocess
from http import HTTPStatus
from pathlib import Path
from wsgiref.util import setup_testing_defaults
from wsgiref.validate import validator

import pytest
from pydantic import ValidationError

from amidst.domain.interfaces import ObservationProvider
from amidst.domain.stream import BoundGapEvent
from amidst.integration.api import IntegrationApplication, api_contract, encode_event_key
from amidst.integration.config import ServiceConfig
from amidst.integration.contracts import BackendAPI, EventResponse, RecordQuery
from amidst.integration.local_repository import InMemoryRepository, LocalJsonRepository
from amidst.integration.repositories import RepositorySnapshot
from amidst.integration.service import MockIntegrationService
from amidst.integration.wiring import build_mock_service

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/integration/mock_v1.json"


def test_mock_provider_and_stored_query_contracts_preserve_identities() -> None:
    service = build_mock_service(CONFIG, search_clock=lambda: 0.0)
    api: BackendAPI = service
    provider: ObservationProvider = service.observation_provider("single_path")
    snapshot = service.repository.snapshot()
    assert len(snapshot.gaps) == 4
    for gap in snapshot.gaps:
        for time in gap.event.time_range:
            query = RecordQuery(time_range=(time, time), source_id=gap.binding.source_id)
            assert api.events(query).items == (gap,)
        assert api.event(gap.event.event_id).gap == gap
        trajectories = api.trajectories(gap.event.event_id)
        assert trajectories.candidates == gap.event.candidates
        assert trajectories.hypotheses == gap.event.trajectories
        assert trajectories.complete == gap.search_result.complete
    single = next(gap for gap in snapshot.gaps if gap.binding.source_id == "mock:single_path")
    start = single.start.observation
    assert provider.get_observations(
        start.camera_id, (start.start_time, start.end_time),
    ) == (start,)
    assert api.observations(RecordQuery(time_range=(start.start_time, start.start_time),
                                      source_id=single.binding.source_id)).items == (single.start,)
    assert api.events(RecordQuery(time_range=(0, 100), camera_id="UNKNOWN")).items == ()
    assert api.observations(RecordQuery(time_range=(0, 100), source_id="UNKNOWN")).items == ()


def test_http_json_roundtrip_and_wsgi_protocol() -> None:
    service = build_mock_service(CONFIG, search_clock=lambda: 0.0)
    gap = service.repository.snapshot().gaps[0]
    app = IntegrationApplication(service)
    environ = {}
    setup_testing_defaults(environ)
    environ["PATH_INFO"] = "/v1/events/" + encode_event_key(gap.event.event_id)
    environ["QUERY_STRING"] = ""
    environ["SERVER_PROTOCOL"] = "HTTP/1.0"
    captured = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    response = validator(app)(environ, start_response)
    try:
        payload = b"".join(response)
    finally:
        response.close()
    assert captured["status"] == "200 OK"
    assert EventResponse.model_validate_json(payload).gap == gap
    assert json.loads(payload)["metadata"]["data_kind"] == "SYNTHETIC"


@pytest.mark.parametrize("query_string", [
    "", "start=0", "start=2&end=1", "start=nan&end=1", "start=0&end=inf",
    "start=0&end=1&start=0", "start=0&end=1&utc=true", "start=0&end=1&camera_id=",
])
def test_http_rejects_invalid_queries(query_string: str) -> None:
    app = IntegrationApplication(build_mock_service(CONFIG, search_clock=lambda: 0.0))
    status, error = app.handle("GET", "/v1/events", query_string)
    assert status == HTTPStatus.BAD_REQUEST
    assert error.model_dump()["code"] == "INVALID_REQUEST"


def test_http_unknown_ids_write_methods_and_json_schemas() -> None:
    app = IntegrationApplication(build_mock_service(CONFIG, search_clock=lambda: 0.0))
    assert app.handle("GET", "/v1/events/" + encode_event_key("unknown"))[0] == HTTPStatus.NOT_FOUND
    assert app.handle("GET", "/missing")[0] == HTTPStatus.NOT_FOUND
    assert app.handle("POST", "/v1/events")[0] == HTTPStatus.METHOD_NOT_ALLOWED
    contract = api_contract()
    assert contract.metadata.mode == "MOCK_INTEGRATION_ONLY"
    assert "ConsumerEvent" in contract.schemas
    assert "ReplayFrame" in contract.schemas
    for endpoint in contract.endpoints:
        assert endpoint.response in contract.schemas
        if endpoint.request is not None:
            assert endpoint.request in contract.schemas


@pytest.mark.parametrize("event_id", ["literal%2Fidentifier", "a/b/consumer", "合成 event ?#%"])
def test_url_keys_preserve_special_event_identifiers(event_id: str) -> None:
    original = build_mock_service(CONFIG, search_clock=lambda: 0.0).repository.snapshot().gaps[0]
    payload = original.model_dump(mode="json")
    payload["event"]["event_id"] = event_id
    gap = BoundGapEvent.model_validate(payload)
    snapshot = RepositorySnapshot(observations=(gap.start, gap.end), gaps=(gap,))
    app = IntegrationApplication(MockIntegrationService(InMemoryRepository(snapshot)))
    key = encode_event_key(event_id)
    assert "/" not in key and "%" not in key
    status, response = app.handle("GET", "/v1/events/" + key)
    assert status == HTTPStatus.OK
    assert EventResponse.model_validate_json(response.model_dump_json()).gap == gap
    assert app.handle("GET", "/v1/events/" + key + "/consumer")[0] == HTTPStatus.OK


@pytest.mark.parametrize("key", ["e-", "e-Zg=", "bad", "e-!!!!"])
def test_event_routes_reject_noncanonical_keys(key: str) -> None:
    app = IntegrationApplication(build_mock_service(CONFIG, search_clock=lambda: 0.0))
    assert app.handle("GET", "/v1/events/" + key)[0] == HTTPStatus.BAD_REQUEST


def test_typescript_route_keys_match_backend_for_arbitrary_ids(
    node_with_typescript: str,
) -> None:
    node = node_with_typescript
    identities = ["literal%2Fidentifier", "a/b/consumer", "合成 event ?#%"]
    source = ROOT / "frontend/phase2/consumer.ts"
    script = (
        "import {eventPath} from " + json.dumps(source.as_uri()) + ";"
        "console.log(JSON.stringify(JSON.parse(process.argv[1]).map(eventPath)));"
    )
    result = subprocess.run([node, "--input-type=module", "-e", script, json.dumps(identities)],
                            check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == ["/v1/events/" + encode_event_key(i) for i in identities]


def _local_config(tmp_path: Path, **changes: object) -> Path:
    config = json.loads(CONFIG.read_text())
    config["dataset_manifest"]["path"] = str(ROOT / "data/mock/stream_v1/dataset.json")
    config.update(changes)
    path = tmp_path / "service.json"
    path.write_text(json.dumps(config))
    return path


def test_local_repository_reopens_identical_service_snapshot(tmp_path: Path) -> None:
    config = _local_config(tmp_path, repository_kind="LOCAL_JSON", repository_path="store.json")
    first = build_mock_service(config, search_clock=lambda: 0.0)
    second = build_mock_service(config, search_clock=lambda: 0.0)
    assert first.repository.snapshot() == second.repository.snapshot()
    assert LocalJsonRepository(tmp_path / "store.json").snapshot() == first.repository.snapshot()


def test_production_backend_and_input_overwrite_are_rejected(tmp_path: Path) -> None:
    config = _local_config(tmp_path, repository_kind="POSTGRESQL")
    with pytest.raises(NotImplementedError, match="interface only"):
        build_mock_service(config)
    config = _local_config(tmp_path, repository_kind="LOCAL_JSON",
                           repository_path=str(ROOT / "data/mock/stream_v1/dataset.json"))
    with pytest.raises(ValueError, match="must not replace"):
        build_mock_service(config)
    with pytest.raises(ValidationError):
        ServiceConfig.model_validate({"provider_kind": "REAL_CV"})
