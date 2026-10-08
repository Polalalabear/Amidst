"""The viewing workspace shares one loaded frame without changing review evidence."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "human_review"
PLAYBACK = REVIEW / "playback"
MEDIA_MANIFESTS = (
    "human_review/frames/motion_context/motion_manifest.json",
    "human_review/frames/topology_context/topology_data.json",
    "human_review/frames/hr02_camera_audit/audit_data.json",
    "human_review/frames/hr02_camera_audit/renderer_manifest.json",
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_builder(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, REVIEW / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


@pytest.fixture
def manifest_root(tmp_path: Path) -> Path:
    """Only copied public manifests/receipts; no GT, scene or renders are needed."""
    status = load_builder("build_playback_status")
    paths = [*MEDIA_MANIFESTS, *(source[0] for source in status.SOURCE_FILES.values())]
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    return tmp_path


def node_eval(action: str) -> Any:
    node = shutil.which("node")
    if node is None:
        pytest.skip("playback controller checks require Node.js")
    script = """
const api = require(process.argv[1]);
const action = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
Promise.resolve(new Function('api', action)(api)).then(result => {
  process.stdout.write(JSON.stringify(result));
}).catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run(
        [node, "-e", script, str(PLAYBACK / "player.js")],
        input=json.dumps(action),
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_status_distinguishes_applied_approvals_from_incomplete_exit() -> None:
    status = load_builder("build_playback_status").build_status(ROOT)
    assert status["mode"] == "VIEW_ONLY"
    assert status["checkpoint_sha"] == "883204af854bed301506b39d63ccb33312b79ff2"
    assert status["human_approvals"]["approved"] == status["human_approvals"]["total"] == 4
    assert status["human_approvals"]["status"] == "APPROVED_AND_APPLIED"
    assert status["phase1"]["status"] == "PHASE1_FINALIZATION_BLOCKED"
    assert status["phase1"]["full_exit_complete"] is False
    assert status["phase1"]["freeze_allowed"] is False
    assert status["physical"]["status"] == "PARTIAL_APPROVED"
    cases = {row["id"]: row for row in status["cases"]}
    assert cases["case1"]["status"] == "FORMAL_REVIEWED_LOCAL_RUN"
    assert "BLOCKED" in cases["case2"]["status"]
    assert cases["case3"]["status"] == "FORMAL_REVIEWED_LOCAL_TEMPORAL_COMPONENT"
    assert cases["case3"]["full_stress_complete"] is False
    assert status["media_status"] == "HISTORICAL_DIAGNOSTIC_REVIEW_VISUALS"
    assert len(status["sources"]) == 8
    for source in status["sources"]:
        assert source["sha256"] == hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest()


def test_changed_status_receipt_cannot_silently_promote_display(manifest_root: Path) -> None:
    path = manifest_root / "data/finalization/recovery_checkpoint_20261008/validation.json"
    receipt = read_json(path)
    receipt["limits"]["freeze_allowed"] = True
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="Status receipt differs"):
        load_builder("build_playback_status").build_status(manifest_root)


def test_payload_preserves_frozen_motion_and_all_views_share_one_frame(manifest_root: Path) -> None:
    before = {
        path.relative_to(manifest_root): path.read_bytes()
        for path in manifest_root.rglob("*.json")
    }
    payload = load_builder("build_playback_workspace").build_payload(
        manifest_root, verify_assets=False
    )
    motion = read_json(manifest_root / MEDIA_MANIFESTS[0])
    topology = read_json(manifest_root / MEDIA_MANIFESTS[1])
    audit = read_json(manifest_root / MEDIA_MANIFESTS[2])
    renderer = read_json(manifest_root / MEDIA_MANIFESTS[3])
    assert payload["motion"] == motion
    assert payload["topology"] == topology
    assert {key: value for key, value in payload["audit"].items() if key != "images"} == {
        key: value for key, value in audit.items() if key != "images"
    }
    assert len(payload["motion"]["frames"]) == 50
    for frame, graph, cameras in zip(
        payload["motion"]["frames"], payload["topology"]["frames"],
        payload["audit"]["frames"], strict=True,
    ):
        assert frame["frame_id"] == graph["frame_id"] == cameras["frame_id"]
        assert frame["timestamp"] == graph["timestamp"] == cameras["timestamp"]
        assert frame["landmark_position_bu"] == graph["current_position"]["raw_position_bu"]
        # The audit uses double-precision public positions; the historical
        # Blender animation stores float32 display coordinates. Preserve both.
        original_camera_frame = audit["frames"][frame["frame_id"]]
        assert cameras["landmark_position_bu"] == original_camera_frame["landmark_position_bu"]
        assert cameras["foot_position_bu"] == original_camera_frame["foot_position_bu"]
    for view in ("wide", "side"):
        displayed = payload["audit"]["images"][view]
        assert displayed["sha256"] == renderer[view]["sha256"]
        assert displayed["static_context_only"] is True
        assert displayed["baked_person_or_frame_rays"] is False
        assert displayed["view"] == {
            key: value for key, value in renderer[view]["view"].items()
            if key != "fit_points_bu"
        }
    stills = payload["audit"]["images"]["camera_stills"]
    assert stills == renderer["camera_stills"]
    assert len(stills) == 6
    assert {row["frame_id"] for row in stills} == {20, 25, 45}
    assert all(row["rendered_pixel_visibility_certification"] is False for row in stills)
    assert before == {
        path.relative_to(manifest_root): path.read_bytes()
        for path in manifest_root.rglob("*.json")
    }


@pytest.mark.parametrize("relative", MEDIA_MANIFESTS)
def test_changed_diagnostic_inputs_are_rejected_even_without_media(
    manifest_root: Path, relative: str,
) -> None:
    path = manifest_root / relative
    document = read_json(path)
    document["source_sha256"] = "0" * 64
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen preview source changed"):
        load_builder("build_playback_workspace").build_payload(manifest_root, verify_assets=False)


def test_missing_or_corrupt_media_never_overwrites_evidence_or_publishes_partial_player(
    manifest_root: Path,
) -> None:
    builder = load_builder("build_playback_workspace")
    output = manifest_root / "human_review/playback"
    with pytest.raises(FileNotFoundError, match="supply --media-root"):
        builder.build_workspace(manifest_root)
    assert not output.exists()
    corrupt = manifest_root / "human_review/frames/motion_context/motion_000.png"
    corrupt.write_bytes(b"pre-existing source must never be overwritten")
    with pytest.raises(ValueError, match="does not match frozen evidence"):
        builder.build_workspace(manifest_root, media_root=REVIEW)
    assert corrupt.read_bytes() == b"pre-existing source must never be overwritten"
    assert not output.exists()


def test_latest_loaded_frame_wins_and_failure_retains_all_previous_panes() -> None:
    result = node_eval(r"""
return (async () => {
  const pending = new Map(), commits = [], states = [];
  let panes = [null, null, null, null];
  const controller = new api.FrameController({frameCount: 50, fps: 5,
    loadFrame: index => new Promise((resolve, reject) => pending.set(index, {resolve, reject})),
    commitFrame: (index, payload) => {
      panes = [...payload.panes];
      commits.push({index, panes});
    }, onState: state => states.push(state)});
  const finish = index => pending.get(index).resolve({panes: Array(4).fill(index)});
  const first = controller.seek(0); finish(0); await first;
  const older = controller.seek(20), latest = controller.seek(45);
  const duringLoad = {state: controller.snapshot(), panes: [...panes]};
  finish(45); const latestSuccess = await latest;
  finish(20); const staleSuccess = await older;
  const afterStale = {state: controller.snapshot(), panes: [...panes]};
  const failure = controller.seek(25);
  pending.get(25).reject(new Error('missing source image'));
  const failedSuccess = await failure;
  const afterFailure = {state: controller.snapshot(), panes: [...panes]};
  const recovery = controller.seek(49); finish(49); await recovery;
  const invalid = await controller.seek(Number.NaN);
  return {commits, duringLoad, latestSuccess, staleSuccess, failedSuccess,
    afterStale, afterFailure, recovered: controller.snapshot(), panes, invalid,
    loadingStates: states.filter(state => state.loading)};
})()
""")
    assert result["duringLoad"]["state"]["index"] == 0
    assert result["duringLoad"]["state"]["requestedIndex"] == 45
    assert result["duringLoad"]["panes"] == [0] * 4
    assert result["latestSuccess"] is True
    assert result["staleSuccess"] is result["failedSuccess"] is result["invalid"] is False
    assert result["afterStale"]["state"]["index"] == 45
    assert result["afterStale"]["panes"] == [45] * 4
    assert result["afterFailure"]["state"]["index"] == 45
    assert result["afterFailure"]["state"]["error"] == "missing source image"
    assert result["afterFailure"]["state"]["loading"] is False
    assert result["afterFailure"]["state"]["playing"] is False
    assert result["afterFailure"]["panes"] == [45] * 4
    assert result["recovered"]["index"] == 49
    assert result["recovered"]["error"] is None
    assert result["panes"] == [49] * 4
    assert result["commits"] == [
        {"index": index, "panes": [index] * 4} for index in (0, 45, 49)
    ]


def test_one_timer_drives_loop_speed_end_and_pause() -> None:
    result = node_eval(r"""
return (async () => {
  const timers = new Map(), commits = []; let serial = 0;
  const controller = new api.FrameController({frameCount: 50, fps: 5,
    loadFrame: async index => index,
    commitFrame: index => commits.push(index),
    schedule: (callback, delay) => {timers.set(++serial, {callback, delay}); return serial;},
    unschedule: id => timers.delete(id)});
  const sample = () => ({...controller.snapshot(), timers: timers.size,
    delays: [...timers.values()].map(timer => timer.delay)});
  const tick = async () => {const [id, timer] = [...timers.entries()][0];
    timers.delete(id); await timer.callback();};
  await controller.seek(48); await controller.play(); await controller.play();
  const playing = sample(); await tick(); const lastFrame = sample();
  await tick(); const ended = sample();
  controller.setLoop(true); await controller.play(); const restarted = sample();
  await controller.seek(49, {pause: false}); await tick(); const looped = sample();
  controller.setSpeed(.5); const half = sample();
  controller.setSpeed(2); controller.setSpeed(3); const double = sample();
  controller.pause(); const paused = sample();
  await controller.step(-1); const previous = sample();
  await controller.seek(500); const clamped = sample();
  return {playing, lastFrame, ended, restarted, looped, half, double, paused,
    previous, clamped, commits};
})()
""")
    assert result["playing"]["timers"] == 1
    assert result["playing"]["delays"] == [200]
    assert result["lastFrame"]["index"] == 49
    assert result["ended"]["index"] == 49
    assert result["ended"]["timers"] == 0
    assert result["ended"]["playing"] is False
    assert result["restarted"]["index"] == result["looped"]["index"] == 0
    assert result["looped"]["timers"] == 1
    assert result["half"]["delays"] == [400]
    assert result["double"]["delays"] == [100]
    assert result["double"]["speed"] == 2
    assert result["paused"]["timers"] == 0
    assert result["paused"]["playing"] is False
    assert result["previous"]["index"] == 0
    assert result["clamped"]["index"] == 49


def test_slow_frame_does_not_queue_more_ticks_and_pause_prevents_reschedule() -> None:
    result = node_eval(r"""
return (async () => {
  const timers = new Map(), commits = [], pending = new Map(); let serial = 0;
  const controller = new api.FrameController({frameCount: 50, fps: 5,
    loadFrame: index => new Promise(resolve => pending.set(index, resolve)),
    commitFrame: index => commits.push(index),
    schedule: (callback, delay) => {timers.set(++serial, {callback, delay}); return serial;},
    unschedule: id => timers.delete(id)});
  const first = controller.play(); pending.get(0)(0); await first;
  const [id, timer] = [...timers.entries()][0]; timers.delete(id);
  const tick = timer.callback();
  controller.setSpeed(2);
  const loading = {...controller.snapshot(), timers: timers.size, commits: [...commits]};
  controller.pause(); pending.get(1)(1); await tick;
  const paused = {...controller.snapshot(), timers: timers.size, commits: [...commits]};
  return {loading, paused};
})()
""")
    assert result["loading"]["loading"] is True
    assert result["loading"]["index"] == 0
    assert result["loading"]["requestedIndex"] == 1
    assert result["loading"]["commits"] == [0]
    assert result["loading"]["timers"] == 0
    assert result["paused"]["index"] == 1
    assert result["paused"]["loading"] is False
    assert result["paused"]["playing"] is False
    assert result["paused"]["timers"] == 0
    assert result["paused"]["commits"] == [0, 1]


def test_display_helpers_preserve_association_projection_and_local_asset_boundary() -> None:
    topology = read_json(REVIEW / "frames/topology_context/topology_data.json")
    positions = [frame["current_position"] for frame in topology["frames"]]
    action = "const positions = " + json.dumps(positions) + r""";
const view = {width: 1920, height: 1080, view: {position_bu: [10,20,30],
  right: [1,0,0], up: [0,0,1], ortho_scale_bu: 192}};
const unsafe = ['../secret.png', '/secret.png', 'https://host/image.png',
  'folder/../secret.png', 'image.png?token=1', '%2e%2e/secret.png', 'folder\\secret.png'];
return {labels: positions.map(api.relationText),
  center: api.project([10,20,30],view), point: api.project([12,80,35],view),
  asset: api.resolveAsset('../frames/motion_context/', 'motion_025.png'),
  rejected: unsafe.map(path => {try {api.resolveAsset('../frames/',path); return false;}
    catch (_) {return true;}})};
"""
    result = node_eval(action)
    assert "N1" in result["labels"][20]
    assert "N2" in result["labels"][45]
    assert "E1" in result["labels"][25] and "20%" in result["labels"][25]
    assert "範圍外" in result["labels"][0] and "範圍外" in result["labels"][49]
    assert result["center"] == [960, 540]
    assert result["point"] == [980, 490]
    assert result["asset"] == "../frames/motion_context/motion_025.png"
    assert all(result["rejected"])
