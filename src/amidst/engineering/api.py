"""Loopback-only typed transport with fixed errors and no raw request logging."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, cast
from wsgiref.simple_server import WSGIRequestHandler, make_server

from amidst.engineering.access import TOOLS, Tool
from amidst.engineering.dto import RESPONSE_TYPES
from amidst.engineering.facade import (
    AgentFacade,
    EventRequest,
    MediaRequest,
    QueryRequest,
    ReplayRequest,
    ResolveRequest,
    ToolFailure,
    ToolRequest,
)


class AgentApplication:
    def __init__(self, facades: tuple[AgentFacade, ...]) -> None:
        self.facades = {f.guard.session_ref: f for f in facades}

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]
                 ) -> Iterable[bytes]:
        def respond(status: str, data: object, mime: str = "application/json") -> list[bytes]:
            payload = (data if isinstance(data, bytes) else
                       json.dumps(data, allow_nan=False, separators=(",", ":")).encode())
            start_response(status, [("Content-Type", mime), ("Content-Length", str(len(payload))),
                                    ("Cache-Control", "no-store"),
                                    ("X-Content-Type-Options", "nosniff")])
            return [payload]

        path, method = environ.get("PATH_INFO", ""), environ.get("REQUEST_METHOD", "")
        if method == "GET" and path == "/":
            return respond("200 OK", Path(__file__).with_name("ui.html").read_bytes(),
                           "text/html; charset=utf-8")
        if method == "GET" and path == "/agent/v1/contexts":
            return respond("200 OK", {"items": [f.context() for f in self.facades.values()]})
        if method == "GET" and path == "/agent/v1/contract":
            schemas: dict[str, type[ToolRequest]] = {
                "resolve_place": ResolveRequest, "list_cameras": ToolRequest,
                "query_observations": QueryRequest, "query_events": QueryRequest,
                "get_event_summary": EventRequest, "get_event_detail": EventRequest,
                "get_media": MediaRequest, "get_replay": ReplayRequest,
            }
            return respond("200 OK", {"version": "simulation.agent.v1", "tools": TOOLS,
                "request_schemas": {name: cls.model_json_schema()
                                    for name, cls in schemas.items()},
                "response_schemas": {name: cls.model_json_schema()
                                     for name, cls in RESPONSE_TYPES.items()}})
        if not path.startswith("/agent/v1/") or path.removeprefix("/agent/v1/") not in TOOLS:
            return respond("404 Not Found", {"error": "ROUTE_UNAVAILABLE"})
        if method != "POST":
            return respond("405 Method Not Allowed", {"error": "METHOD_DENIED"})
        try:
            if environ.get("CONTENT_TYPE", "").split(";")[0] != "application/json":
                raise ValueError("content type")
            size = int(environ.get("CONTENT_LENGTH", "0"))
            if not 0 < size <= 65536 or environ.get("QUERY_STRING"):
                raise ValueError("request envelope")
            payload = json.loads(environ["wsgi.input"].read(size))
            if not isinstance(payload, dict) or not isinstance(payload.get("session_ref"), str):
                raise ValueError("session envelope")
            facade = self.facades.get(payload["session_ref"])
            if facade is None:
                return respond("403 Forbidden", {"error": "SCOPE_DENIED"})
            tool = cast(Tool, path.removeprefix("/agent/v1/"))
            result = facade.invoke(tool, payload)
            return respond("200 OK", result)
        except ToolFailure as error:
            return respond("403 Forbidden", {"error": str(error)})
        except (ValueError, TypeError, KeyError, OSError):
            return respond("400 Bad Request", {"error": "INVALID_REQUEST"})


class SafeRequestHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        """Typed tool logs replace request URLs that can contain arbitrary secrets."""


def serve(facades: tuple[AgentFacade, ...], port: int = 8010) -> None:
    with make_server("127.0.0.1", port, AgentApplication(facades),
                     handler_class=SafeRequestHandler) as server:
        print(f"Amidst local synthetic research: http://127.0.0.1:{port}", flush=True)
        server.serve_forever()
