"""Actual loopback product workflow/transport checks; never reads GT or local archives."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


def validate(base_url: str) -> dict[str, object]:
    parsed = urlparse(base_url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path
        or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("EXACT_LOOPBACK_URL_REQUIRED")
    receipts: list[dict[str, object]] = []

    def request(path: str, value: dict[str, object] | None = None, *, expected: int = 200,
                headers: dict[str, str] | None = None) -> Any:
        body = None if value is None else json.dumps(value).encode()
        outgoing = {"Content-Type": "application/json"} if body is not None else {}
        outgoing.update(headers or {})
        query = Request(base_url + path, body, outgoing)
        try:
            with urlopen(query, timeout=30) as response:
                status, data = response.status, response.read()
                mime = response.headers.get_content_type()
        except HTTPError as error:
            status, data, mime = error.code, error.read(), error.headers.get_content_type()
        assert status == expected, (path, status, expected)
        receipts.append({"route": path.split("?")[0].rsplit("/", 1)[-1], "status": status,
                         "bytes": len(data), "response_sha256": hashlib.sha256(data).hexdigest()})
        if mime == "application/json":
            text = data.decode()
            assert all(marker not in text for marker in (
                "/Users/", "relative_path", "gt_actor", "ground_truth", "simulation_export_path",
            ))
            return json.loads(data)
        return data

    contexts = request("/product/v1/contexts")
    assert isinstance(contexts, dict) and len(contexts["items"]) == 2
    assert {c["context"]["observation_mode"] for c in contexts["items"]} == {
        "photos_only", "photos_plus_observations"}
    contract = request("/product/v1/contract")
    assert isinstance(contract, dict) and len(contract["tools"]) == 13
    modes = []
    for context in contexts["items"]:
        session = {"session_ref": context["session_ref"]}

        def post(endpoint: str, payload: dict[str, object] | None = None,
                 expected: int = 200, *,
                 bound_session: dict[str, object] = session) -> dict[str, Any]:
            value = request("/product/v1/" + endpoint, bound_session | (payload or {}),
                            expected=expected)
            assert isinstance(value, dict)
            return value

        cameras = post("tools/list_cameras")["items"]
        assert isinstance(cameras, list) and len(cameras) == 4
        camera = cameras[0]["camera_ref"]
        observations = post("tools/query_observations", {
            "camera_ref": camera, "time_range": [0, 24], "limit": 2})
        seeds = tuple(item["observation_ref"] for item in observations["items"])
        assert len(seeds) == 2
        if observations["retrieval"]["next_cursor"]:
            post("tools/query_observations", {"camera_ref": camera, "time_range": [0, 24],
                 "limit": 2, "cursor": observations["retrieval"]["next_cursor"]})
        indexed_events = {}
        for registered_camera in cameras:
            page = post("tools/query_events", {"time_range": [0, 24],
                        "camera_ref": registered_camera["camera_ref"]})
            indexed_events.update({row["event_ref"]: row for row in page["items"]})
        events = list(indexed_events.values())
        assert len(events) == 64
        event = next(item for item in events if item["candidate_count"])
        detail = post("tools/get_event_detail", {"event_ref": event["event_ref"]})
        assert len(detail["candidates"]) == event["candidate_count"]
        assert len(detail["trajectories"]) == event["hypothesis_count"]
        post("tools/get_replay", {"event_ref": event["event_ref"],
                                 "timestamp": event["time_range"][0]})
        obs = post("tools/get_observation_detail", {"observation_ref": seeds[0]})
        appearance = post("tools/search_person_appearance", {
            "query_track_ref": obs["local_track_ref"], "time_range": [0, 24],
            "camera_ref": camera, "top_k": 3})
        post("tools/get_stitch_hypotheses", {"local_track_ref": obs["local_track_ref"]})
        media_ref = obs["media_refs"][0]
        media = request("/product/v1/media/" + media_ref + "?" + urlencode(session))
        assert isinstance(media, bytes) and media.startswith(b"\x89PNG")
        scene = post("view/scene")
        assert scene["units"] == "METRES"
        videos = post("view/videos")["items"]
        assert isinstance(videos, list) and len(videos) == 4
        video_url = "/product/v1/video/" + videos[0]["video_ref"] + "?" + urlencode(session)
        chunk = request(video_url, headers={"Range": "bytes=0-31"}, expected=206)
        assert isinstance(chunk, bytes) and len(chunk) == 32
        request(video_url, headers={"Range": "bytes=999999999-"}, expected=416)
        post("view/timeline", {"timestamp": 2.13, "event_refs": [event["event_ref"]]})
        compiled = post("intent", {"intent": {"task": "MULTI_TARGET", "camera_ref": camera,
                         "time_range": [0, 24], "seed_refs": seeds}})
        assert compiled["status"] == "READY"
        plan_ref = compiled["plan"]["plan_ref"]
        assert post("plan", {"plan_ref": plan_ref}) == compiled["plan"]
        case = post("execute", {"plan_ref": plan_ref, "max_new_calls": 3})
        if case["pending_steps"]:
            stopped = post("execute", {"plan_ref": plan_ref, "stop": True})
            assert stopped["state"] == "STOPPED"
            case = post("execute", {"plan_ref": plan_ref, "resume": True, "max_new_calls": 6})
        while case["state"] in ("PAUSED", "STOPPED"):
            case = post("execute", {"plan_ref": plan_ref, "resume": True, "max_new_calls": 6})
        assert case["state"] == "COMPLETED"
        assert len(case["subjects"]) == 2
        calls = len(case["receipts"])
        assert post("execute", {"plan_ref": plan_ref})["receipts"] == case["receipts"]
        report = post("report", {"plan_ref": plan_ref})
        review = post("review", {"review": {"report_ref": report["report_ref"],
            "report_sha256": report["report_sha256"], "operator_ref": context["operator_ref"],
            "action": "PRESERVE_AMBIGUITY", "reason_code": "AMBIGUOUS_EVIDENCE"}})
        assert review["canonical_records_modified"] is False
        exported = request("/product/v1/export-report",
                           session | {"report_ref": report["report_ref"]})
        assert isinstance(exported, bytes) and exported.startswith(b"<!doctype html>")
        history = post("cases")
        assert plan_ref in [item["plan_ref"] for item in history["items"]]
        other = next(c for c in contexts["items"] if c["session_ref"] != context["session_ref"])
        request("/product/v1/plan", {"session_ref": other["session_ref"], "plan_ref": plan_ref},
                expected=400)
        assert not post("tools/query_events", {
            "time_range": [40, 50], "camera_ref": camera})["items"]
        post("tools/query_events", {"time_range": [0, 24]}, expected=403)
        post("tools/get_event_detail", {"event_ref": "event:" + "f" * 24}, expected=403)
        post("tools/query_events", {"time_range": [0, 24], "camera_ref": camera,
                                   "decision_stage": "RESULTS"},
             expected=403)
        post("tools/shell", {"command": "/Users/private/GT_SECRET"}, expected=403)
        modes.append({"mode": context["context"]["observation_mode"],
                      "run_ref": context["run_ref"],
                      "product_freeze_ref": context["product_freeze_ref"],
                      "plan_ref": plan_ref, "state": case["state"], "tool_calls": calls,
                      "subjects": len(case["subjects"]), "events": len(events),
                      "appearance_hits": len(appearance["hits"]),
                      "report_sha256": report["report_sha256"],
                      "alternatives": len(report["all_alternative_refs"]),
                      "graph_complete": report["graph_complete"],
                      "retrieval_complete": report["retrieval_complete"]})
    request("/product/v1/contexts", headers={"Host": "attacker.example",
             "Origin": "http://attacker.example"}, expected=403)
    request("/product/v1/contexts", headers={"Origin": "https://attacker.example"}, expected=403)
    request("/simulation/export/gt.json", expected=404)
    return {"schema_version": "product.http-validation.v1", "status": "PASS",
            "requests": len(receipts), "modes": modes, "receipts": receipts,
            "external_model_calls": False, "source_truth_read": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8020")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.url)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "requests": result["requests"],
                      "modes": result["modes"]}, indent=2))


if __name__ == "__main__":
    main()
