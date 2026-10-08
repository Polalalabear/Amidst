import io
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.engineering.api import AgentApplication
from amidst.engineering.facade import AgentFacade
from amidst.engineering.run import load_facades, materialize_run


@pytest.fixture(scope="module")
def facade(tmp_path_factory: pytest.TempPathFactory) -> AgentFacade:
    root = tmp_path_factory.mktemp("agent-transport")
    materialize_run(root, Path("configs/engineering/simulation_v1.json"), run_id="transport-v1")
    return load_facades(root)[0]

def request(app: AgentApplication, path: str, payload: object = None,
            method: str = "POST") -> tuple[str, dict[str, Any]]:
    body = json.dumps(payload).encode()
    env = {"PATH_INFO": path, "REQUEST_METHOD": method, "CONTENT_TYPE": "application/json",
           "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)}
    statuses: list[str] = []
    output = b"".join(app(env, lambda status, headers: statuses.append(status)))
    return statuses[0], json.loads(output)


def test_transport_allowlist_and_safe_errors(facade: AgentFacade) -> None:
    app = AgentApplication((facade,))
    assert request(app, "/agent/v1/contexts", method="GET")[0] == "200 OK"
    assert request(app, "/agent/v1/contract", method="GET")[0] == "200 OK"
    assert request(app, "/v1/events", method="GET")[0] == "404 Not Found"
    assert request(app, "/agent/v1/query_events", {"session_ref": "foreign"})[0] == "403 Forbidden"
    status, result = request(app, "/agent/v1/get_media", {"session_ref": facade.guard.session_ref,
                                                        "media_ref": "/Users/private/secret"})
    assert status == "403 Forbidden" and "/Users" not in json.dumps(result)
    assert request(app, "/agent/v1/list_cameras", method="GET")[0] == "405 Method Not Allowed"
