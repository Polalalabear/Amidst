"""Read-only JSON/WSGI adapter for the transport-neutral integration service."""

import base64
import binascii
from collections.abc import Iterable
from http import HTTPStatus
from urllib.parse import parse_qs
from wsgiref.types import StartResponse, WSGIEnvironment

from amidst.domain.common import DomainModel
from amidst.integration.consumer import ConsumerEvent, ReplayFrame, ReplaySeek
from amidst.integration.contracts import (
    ApiContract,
    ApiError,
    EventPage,
    EventResponse,
    ObservationPage,
    RecordQuery,
    TrajectoryResponse,
)
from amidst.integration.service import MockIntegrationService


def api_contract() -> ApiContract:
    models = (
        RecordQuery, ObservationPage, EventPage, EventResponse, TrajectoryResponse,
        ConsumerEvent, ReplaySeek, ReplayFrame, ApiError, ApiContract,
    )
    return ApiContract(schemas={model.__name__: model.model_json_schema() for model in models})


def encode_event_key(event_id: str) -> str:
    """Opaque URL-safe key; preserve literal slashes, percent signs and Unicode IDs."""
    if not event_id:
        raise ValueError("event_id cannot be empty")
    return "e-" + base64.urlsafe_b64encode(event_id.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_event_key(key: str) -> str:
    if not key.startswith("e-"):
        raise ValueError("event route requires a versioned base64url event key")
    encoded = key[2:]
    try:
        event_id = base64.b64decode(encoded + "=" * (-len(encoded) % 4),
                                   altchars=b"-_", validate=True).decode("utf-8")
    except (ValueError, binascii.Error, UnicodeError) as error:
        raise ValueError("invalid event key") from error
    if encode_event_key(event_id) != key:
        raise ValueError("event key must use canonical encoding")
    return event_id


def _parameters(query_string: str, allowed: set[str]) -> dict[str, str]:
    parsed = parse_qs(query_string, keep_blank_values=True, strict_parsing=True, max_num_fields=10)
    if set(parsed) - allowed or any(len(values) != 1 for values in parsed.values()):
        raise ValueError("unknown or repeated query parameter")
    return {name: values[0] for name, values in parsed.items()}


def _record_query(query_string: str) -> RecordQuery:
    parameters = _parameters(query_string, {
        "start", "end", "camera_id", "target_id", "source_id", "spatial_context_id",
    })
    if "start" not in parameters or "end" not in parameters:
        raise ValueError("start and end configured seconds are required")
    return RecordQuery.model_validate({
        "time_range": (float(parameters.pop("start")), float(parameters.pop("end"))),
        **parameters,
    })


class IntegrationApplication:
    """Small mock WSGI transport; no authentication or production server claim."""

    def __init__(self, service: MockIntegrationService) -> None:
        self.service = service

    def handle(
        self, method: str, path: str, query_string: str = "",
    ) -> tuple[HTTPStatus, DomainModel]:
        if method != "GET":
            return HTTPStatus.METHOD_NOT_ALLOWED, ApiError(
                code="METHOD_NOT_ALLOWED", message="this foundation exposes GET contracts",
            )
        try:
            if path == "/v1/contract":
                _parameters(query_string, set())
                return HTTPStatus.OK, api_contract()
            if path == "/v1/observations":
                return HTTPStatus.OK, self.service.observations(_record_query(query_string))
            if path == "/v1/events":
                return HTTPStatus.OK, self.service.events(_record_query(query_string))
            prefix = "/v1/events/"
            if path.startswith(prefix):
                parts = path[len(prefix):].split("/")
                event_id = _decode_event_key(parts[0])
                operation = parts[1] if len(parts) == 2 else "" if len(parts) == 1 else None
                if operation == "replay":
                    parameters = _parameters(query_string, {"timestamp"})
                    if "timestamp" not in parameters:
                        raise ValueError("timestamp in configured seconds is required")
                    seek = ReplaySeek(event_id=event_id, timestamp=float(parameters["timestamp"]))
                    return HTTPStatus.OK, self.service.replay(seek)
                _parameters(query_string, set())
                if operation == "":
                    return HTTPStatus.OK, self.service.event(event_id)
                if operation == "trajectories":
                    return HTTPStatus.OK, self.service.trajectories(event_id)
                if operation == "consumer":
                    return HTTPStatus.OK, self.service.consumer(event_id)
            return HTTPStatus.NOT_FOUND, ApiError(code="NOT_FOUND", message="unknown API route")
        except LookupError:
            return HTTPStatus.NOT_FOUND, ApiError(code="NOT_FOUND", message="unknown event")
        except ValueError:
            return HTTPStatus.BAD_REQUEST, ApiError(
                code="INVALID_REQUEST", message="request violates the configured-time contract",
            )

    def __call__(
        self, environ: WSGIEnvironment, start_response: StartResponse,
    ) -> Iterable[bytes]:
        status, model = self.handle(
            environ["REQUEST_METHOD"], environ["PATH_INFO"], environ.get("QUERY_STRING", ""),
        )
        payload = model.model_dump_json().encode("utf-8")
        headers = [("Content-Type", "application/json; charset=utf-8"),
                   ("Content-Length", str(len(payload)))]
        if status == HTTPStatus.METHOD_NOT_ALLOWED:
            headers.append(("Allow", "GET"))
        start_response(f"{status.value} {status.phrase}", headers)
        return [payload]
