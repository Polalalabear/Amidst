"""Role/scope and HTTP checks for the human-only local desktop workbench."""

import json
from copy import deepcopy
from io import BytesIO

import pytest

from amidst.workbench.reviews import ReviewStore
from amidst.workbench.service import Application, Denied, Workbench


class FakeScene:
    def __init__(self, scene_id="alpha"):
        self.scene_id = scene_id
        self.label = "測試場景"
        self.description = "獨立合成 fixture"
        self.source_hash = "a" * 64
        self.model_revision = "r1"
        self.run_id = scene_id + "-run"
        self.event_ref = scene_id + "-event"
        self.media_ref = scene_id + "-media"
        self.event_data = {
            "event_ref": self.event_ref, "kind": "DWELL", "time_range": [1, 2],
            "camera_ids": ["C1"], "media_refs": [self.media_ref],
            "uncertainty": "暫定", "evidence_state": "PROJECTED",
            "config_sha256": "b" * 64, "association_refs": ["internal"],
            "projected_path": [{"world_position": [1, 1, 0]}], "candidates": [],
            "source_frames": [{"frame_ref": self.media_ref, "camera_id": "C1",
                               "timestamp": 1.2, "private_field": "not-for-management"}],
        }

    def snapshot(self):
        return {
            "scene_id": self.scene_id, "label": self.label, "description": self.description,
            "source_hash": self.source_hash, "model_revision": self.model_revision,
            "run_id": self.run_id, "capabilities": {"images": True},
            "time_range": [0, 5], "bounds": [0, 0, 5, 5],
            "cameras": [{"camera_id": "C1", "label": "入口", "position": [1, 2, 3]}],
            "objects": [{"object_id": "R1", "kind": "REGION", "label": "区域",
                         "semantic": "ROOM", "geometry": {"type": "polygon", "points":
                         [[0, 0, 0], [3, 0, 0], [3, 3, 0], [0, 3, 0]]},
                         "properties": {}, "editable_fields": ["label", "geometry", "semantic"],
                         "authority": "SYNTHETIC_CONFIG"}],
        }

    def query(self, camera_id, start, end):
        if camera_id != "C1":
            raise ValueError("private/camera/path")
        return {"events": [deepcopy(self.event_data)], "observations": [{"internal_id": "x"}],
                "retrieval": {"truncated": False, "records_read": 1, "index_entries_touched": 1}}

    def event(self, ref):
        if ref != self.event_ref:
            raise ValueError("cross scene ref")
        return deepcopy(self.event_data)

    def media(self, ref):
        if ref != self.media_ref:
            raise ValueError("unregistered media")
        return "image/png", b"verified-pixels"

    def frames(self, camera_ids, timestamp):
        if any(c != "C1" for c in camera_ids):
            raise ValueError("unknown camera")
        return {"frames": [{"camera_id": "C1", "media_ref": self.media_ref,
                            "timestamp": timestamp, "status": "AVAILABLE"}]}

    def evaluation(self):
        return {"status": "AVAILABLE", "ground_truth_only_for_evaluation": True}


@pytest.fixture
def workbench(tmp_path):
    catalog = {s.scene_id: s for s in [FakeScene(), FakeScene("beta")]}
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    store = ReviewStore(tmp_path / "reviews.db", {
        key: {k: scene.snapshot()[k] for k in keys} for key, scene in catalog.items()
    })
    return Workbench(catalog, store)


def session(workbench, role="research"):
    return workbench.session({"role": role})["session_ref"]


def call(workbench, token, action, **kwargs):
    return workbench.call(action, {"session_ref": token, **kwargs})


def http(app, path, payload=None, method="POST", origin=None, host="127.0.0.1:8016"):
    data = json.dumps(payload or {}).encode()
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_TYPE": "application/json",
               "CONTENT_LENGTH": str(len(data)), "wsgi.input": BytesIO(data),
               "HTTP_HOST": host, "SERVER_PORT": "8016"}
    if origin:
        environ["HTTP_ORIGIN"] = origin
    response = {}
    def start(status, headers):
        response.update(status=status, headers=dict(headers))
    body = b"".join(app(environ, start))
    return response["status"], json.loads(body)


def test_manager_projection_and_issued_media(workbench):
    token = session(workbench, "management")
    result = call(workbench, token, "scene", scene_id="alpha")
    assert result["review_state"] is None
    assert "source_hash" not in result["snapshot"]
    assert result["snapshot"]["objects"] == []
    with pytest.raises(Denied, match="MEDIA_DENIED"):
        workbench.media(token, "alpha", "alpha-media")
    result = call(workbench, token, "query", scene_id="alpha", camera_id="C1", start=0, end=3)
    assert result["observations"] == []
    assert "records_read" not in result["retrieval"]
    assert "config_sha256" not in result["events"][0]
    assert "association_refs" not in result["events"][0]
    assert result["events"][0]["source_frames"] == [
        {"frame_ref": "alpha-media", "camera_id": "C1", "timestamp": 1.2}]
    assert workbench.media(token, "alpha", "alpha-media")[1] == b"verified-pixels"
    with pytest.raises(Denied):
        workbench.media(token, "beta", "alpha-media")


@pytest.mark.parametrize("action,fields", [
    ("review_state", {}), ("evaluation", {}), ("logs", {}),
    ("export", {"version": 0}),
    ("test", {"camera_id": "C1", "start": 0, "end": 3}),
    ("timeline", {"camera_ids": ["C1"], "timestamp": 1}),
    ("draft", {"object_id": "R1", "changes": {"label": "changed"}, "base_version": 0,
               "reviewer": "test", "reason": "reason"}),
    ("result_review", {"event_ref": "alpha-event", "decision": "SUPPORT",
                       "reviewer": "test", "reason": "reason"}),
])
def test_manager_research_routes_denied(workbench, action, fields):
    with pytest.raises(Denied, match="ROLE_DENIED"):
        call(workbench, session(workbench, "management"), action, scene_id="alpha", **fields)


def test_manager_cannot_validate_or_publish_known_draft(workbench):
    r = session(workbench)
    draft = call(workbench, r, "draft", scene_id="alpha", object_id="R1",
                 changes={"label": "Reviewed room"}, base_version=0, reviewer="human",
                 reason="clear label")["draft"]
    m = session(workbench, "management")
    with pytest.raises(Denied, match="ROLE_DENIED"):
        call(workbench, m, "validate", draft_id=draft["draft_id"])
    with pytest.raises(Denied, match="ROLE_DENIED"):
        call(workbench, m, "publish", draft_id=draft["draft_id"], expected_version=0,
             reviewer="human", reason="clear label")


def test_review_closed_loop_does_not_change_frozen_scene(workbench):
    token = session(workbench)
    before = workbench.catalog["alpha"].snapshot()
    draft = call(workbench, token, "draft", scene_id="alpha", object_id="R1",
                 changes={"label": "已審閱區域"}, base_version=0, reviewer="UI test",
                 reason="測試草案")["draft"]
    assert call(workbench, token, "validate", draft_id=draft["draft_id"])["validation"]["valid"]
    result = call(workbench, token, "publish", draft_id=draft["draft_id"], expected_version=0,
                  reviewer="UI test", reason="測試新版本")
    assert result["review_state"]["current_version"] == 1
    assert result["review_state"]["objects"][0]["label"] == "已審閱區域"
    assert workbench.catalog["alpha"].snapshot() == before
    assert workbench.reviews.state("beta")["current_version"] == 0
    exported = call(workbench, token, "export", scene_id="alpha", version=1)
    assert exported["annotation"]["objects"][0]["label"] == "已審閱區域"
    assert exported["receipt"]["formal_approval"] is False
    test = call(workbench, token, "test", scene_id="alpha", camera_id="C1", start=0, end=3)
    assert any(row["status"] == "NEEDS_RERUN" for row in test["checks"])


def test_note_not_research_judgment(workbench):
    token = session(workbench, "management")
    result = call(workbench, token, "note", scene_id="alpha", event_ref="alpha-event",
                  status="IN_PROGRESS", note="已交由操作員檢視", reviewer="管理")
    assert result["note"]["status"] == "IN_PROGRESS"
    assert "run_ref" not in result["note"]
    assert workbench.reviews.state("alpha")["result_reviews"] == []
    assert call(workbench, token, "event", scene_id="alpha",
                event_ref="alpha-event")["notes"][0]["note"] == "已交由操作員檢視"


def test_session_scene_and_input_bounds(workbench):
    token = session(workbench)
    with pytest.raises(Denied):
        call(workbench, "missing" * 4, "scene", scene_id="alpha")
    with pytest.raises(Denied):
        call(workbench, token, "scene", scene_id="unknown")
    with pytest.raises(ValueError):
        call(workbench, token, "event", scene_id="beta", event_ref="alpha-event")
    with pytest.raises(ValueError):
        workbench.media(token, "beta", "alpha-media")
    with pytest.raises(Denied, match="FINITE_WINDOW_REQUIRED"):
        call(workbench, token, "query", scene_id="alpha", camera_id="C1", start=0, end=1000)


def test_draft_cannot_escape_session_scene_allowlist(workbench):
    token = session(workbench)
    draft = call(workbench, token, "draft", scene_id="alpha", object_id="R1",
                 changes={"label": "Reviewed"}, base_version=0, reviewer="human",
                 reason="review")["draft"]
    call(workbench, token, "validate", draft_id=draft["draft_id"])
    workbench.sessions[token].scene_ids = frozenset({"beta"})
    with pytest.raises(Denied, match="SCENE_DENIED"):
        call(workbench, token, "validate", draft_id=draft["draft_id"])
    with pytest.raises(Denied, match="SCENE_DENIED"):
        call(workbench, token, "publish", draft_id=draft["draft_id"], expected_version=0,
             reviewer="human", reason="review")


def test_http_rejects_extra_roles_paths_origins_and_hides_errors(workbench, tmp_path):
    app = Application(workbench, tmp_path)
    token = session(workbench)
    status, result = http(app, "/api/query", {"session_ref": token, "scene_id": "alpha",
                         "camera_id": "bad", "start": 0, "end": 1})
    assert status.startswith("400")
    assert "private" not in json.dumps(result)
    status, _ = http(app, "/api/scene", {"session_ref": token, "scene_id": "alpha",
                                        "role": "research"})
    assert status.startswith("400")
    status, _ = http(app, "/api/session", {"role": "research"}, origin="http://elsewhere")
    assert status.startswith("403")
    status, _ = http(app, "/../../pyproject.toml", method="GET")
    assert status.startswith("403")
    status, _ = http(app, "/api/session", {"role": "research"},
                     host="attacker.example:8016", origin="http://attacker.example:8016")
    assert status.startswith("403")
    status, _ = http(app, "/api/bootstrap", method="GET", host="localhost:8080")
    assert status.startswith("403")


def test_evaluation_stays_outside_normal_data(workbench):
    token = session(workbench)
    for action in ("scene", "logs"):
        assert "ground_truth" not in json.dumps(call(workbench, token, action, scene_id="alpha"))
    evaluation = call(workbench, token, "evaluation", scene_id="alpha")
    assert evaluation["evaluation"]["ground_truth_only_for_evaluation"] is True
