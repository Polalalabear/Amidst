"""A moving review cursor must use public positions without moving graph nodes."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "human_review"
TOPOLOGY = REVIEW / "frames/topology_context"
OFFICE = ROOT / "data/finalization/local_run/diagnostics/office/policy_graph_primary"
NAVIGATION_SHA = "9bbedd163e9a195943cfe82f3473a97ac3bc0ff3be31e83d5866cccfba4278fd"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "topology_motion_builder", REVIEW / "build_topology_view.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def independent_pixel(point: list[float], data: dict[str, Any]) -> list[float]:
    """Undo Z, Y, then X rotation independently of the production matrix."""
    camera = data["review_camera"]
    dx, dy, dz = (
        point[i] - camera["position_bu"][i] for i in range(3)
    )
    rx, ry, rz = camera["rotation_euler_radians"]
    rotated_x = math.cos(rz) * dx + math.sin(rz) * dy
    rotated_y = -math.sin(rz) * dx + math.cos(rz) * dy
    camera_x = math.cos(ry) * rotated_x - math.sin(ry) * dz
    rotated_z = math.sin(ry) * rotated_x + math.cos(ry) * dz
    camera_y = math.cos(rx) * rotated_y + math.sin(rx) * rotated_z
    pixel_scale = data["width"] / camera["ortho_scale_bu"]
    return [
        data["width"] / 2 + camera_x * pixel_scale,
        data["height"] / 2 - camera_y * pixel_scale,
    ]


def test_person_positions_are_exact_frozen_motion_not_new_nodes_or_snapped_points() -> None:
    data = read_json(TOPOLOGY / "topology_data.json")
    motion = read_json(REVIEW / "frames/motion_context/motion_manifest.json")
    navigation = data["raw_navigation"]
    canonical = json.dumps(navigation, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == NAVIGATION_SHA
    assert [node["alias"] for node in data["nodes"]] == ["N1", "N2"]
    assert [edge["alias"] for edge in data["edges"]] == ["E1", "E2", "E3"]
    assert data["node_count"] == 2 and data["interior_vertex_count"] == 4
    policy = data["person_marker_policy"]
    assert policy["graph_nodes_move"] is False
    assert policy["graph_vertices_move"] is False
    assert policy["marker_is_graph_node"] is False
    assert len(data["frames"]) == len(motion["frames"]) == 50
    for displayed, frozen in zip(data["frames"], motion["frames"], strict=True):
        assert displayed["frame_id"] == frozen["frame_id"]
        assert displayed["timestamp"] == frozen["timestamp"]
        assert displayed["sha256"] == frozen["sha256"]
        marker = displayed["current_position"]
        assert marker["raw_position_bu"] == frozen["landmark_position_bu"]
        assert marker["floor_position_bu"] == frozen["body_base_bu"]
        assert marker["schematic_position_bu"] == frozen["landmark_position_bu"]
        assert marker["role"] == frozen["role"]
        assert marker["source_state"] == frozen["state"]
        assert marker["state"] == (
            "GAP" if frozen["state"] == "INFERRED_GAP" else "OBSERVED"
        )
        assert marker["raw_pixel"] == pytest.approx(
            independent_pixel(frozen["landmark_position_bu"], data)
        )
        assert marker["floor_pixel"] == pytest.approx(
            independent_pixel(frozen["body_base_bu"], data)
        )
    assert len({tuple(frame["current_position"]["floor_pixel"]) for frame in data["frames"]}) == 50
    assert data["conversion"]["authority"] == "PENDING_HR02_SEMANTIC_BINDING"
    for key in (
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
        "physical_authority_changed",
        "formal_execution_enabled",
        "raw_graph_changed",
    ):
        assert data[key] is False


def test_endpoint_association_keeps_original_tolerance_and_double_precision_evidence() -> None:
    data = read_json(TOPOLOGY / "topology_data.json")
    policy = data["person_marker_policy"]
    assert policy["node_match_tolerance_m"] == data["raw_navigation"]["node_match_tolerance_m"]
    assert policy["node_match_tolerance_m"] == 1e-6
    assert policy["spatial_unit_scale_m"] == 0.0247
    for frame_id, node_index in ((20, 0), (45, 1)):
        marker = data["frames"][frame_id]["current_position"]
        node = data["nodes"][node_index]
        relation = marker["graph_relation"]
        assert relation["kind"] == "NODE"
        assert relation["node_alias"] == node["alias"]
        assert relation["node_id"] == node["id"]
        assert relation["association_source"] == "EXACT_PUBLIC_PROJECTION"
        assert relation["association_position_bu"] == node["raw_position_bu"]
        distance = math.dist(relation["association_position_bu"], node["raw_position_bu"])
        assert relation["node_distance_m"] == distance * policy["spatial_unit_scale_m"]
        assert relation["node_distance_m"] <= policy["node_match_tolerance_m"]
        # Blender's historical float32 display rounding exceeds the node tolerance
        # at both endpoints. Do not snap that old image coordinate or widen policy.
        display_distance = math.dist(marker["raw_position_bu"], node["raw_position_bu"])
        assert display_distance * policy["spatial_unit_scale_m"] > policy["node_match_tolerance_m"]
        assert marker["raw_position_bu"] != node["raw_position_bu"]
    inputs = {row["path"]: row["sha256"] for row in data["inputs"]}
    relative = (OFFICE / "projected_frames.json").relative_to(ROOT).as_posix()
    frozen = read_json(REVIEW / "review_template.json")["metadata"]["input_hashes"]
    assert inputs[relative] == next(row["sha256"] for row in frozen if row["path"] == relative)
    if (OFFICE / "projected_frames.json").is_file():
        samples = read_json(OFFICE / "projected_frames.json")["dataset"]["samples"]
        for row in data["frames"]:
            marker = row["current_position"]
            if marker["state"] == "OBSERVED":
                visible = sorted(
                    (
                        sample for sample in samples
                        if sample["frame_id"] == row["frame_id"]
                        and sample["projected_point"] is not None
                    ),
                    key=lambda sample: sample["camera_id"],
                )
                assert marker["graph_relation"]["association_position_bu"] == (
                    visible[0]["projected_point"]["world_position"]
                )


def test_gap_cursor_uses_existing_direct_candidate_and_outside_frames_get_no_fake_node() -> None:
    data = read_json(TOPOLOGY / "topology_data.json")
    policy = data["person_marker_policy"]
    assert (policy["gap_start_timestamp"], policy["gap_end_timestamp"]) == (4.0, 9.0)
    gap_candidate_ids = set()
    for frame in data["frames"]:
        frame_id = frame["frame_id"]
        marker = frame["current_position"]
        relation = marker["graph_relation"]
        if frame_id < 20 or frame_id > 45:
            assert relation["kind"] == "OUTSIDE_GAP_GRAPH"
            assert relation["scope"] == (
                "BEFORE_DEPARTURE" if frame_id < 20 else "AFTER_RECOVERY"
            )
            assert relation.get("node_alias") is None
            assert relation.get("node_id") is None
            assert relation.get("edge_alias") is None
            assert relation.get("edge_id") is None
        elif frame_id in (20, 45):
            assert relation["kind"] == "NODE"
            assert relation["scope"] == (
                "AT_DEPARTURE" if frame_id == 20 else "AT_RECOVERY"
            )
        else:
            assert relation["kind"] == "EDGE"
            assert relation["scope"] == "ON_EXISTING_DIRECT_CANDIDATE"
            assert relation["node_alias"] is None
            assert relation["node_id"] is None
            assert relation["edge_alias"] == "E1"
            assert relation["edge_id"] == "pilot_route:direct"
            assert (relation["from_node"], relation["to_node"]) == ("N1", "N2")
            assert relation["association_position_bu"] is None
            assert relation["association_source"] == "EXISTING_RENDERED_DIRECT_CANDIDATE"
            assert relation["progress"] == pytest.approx((frame["timestamp"] - 4.0) / 5.0)
            assert 0 < relation["progress"] < 1
            gap_candidate_ids.add(relation["candidate_id"])
    assert len(gap_candidate_ids) == 1
    if (OFFICE / "candidates.json").is_file():
        direct = read_json(OFFICE / "candidates.json")["results"][0]["candidates"][0]
        assert gap_candidate_ids == {direct["candidate_id"]}
        assert direct["polyline"] == data["edges"][0]["raw_polyline_bu"]
        assert direct["navmesh_corridor"] == ["pilot_route:direct"]


def test_marker_builder_rejects_changed_motion_public_projection_or_candidate() -> None:
    if not all((OFFICE / name).is_file() for name in ("projected_frames.json", "candidates.json")):
        pytest.skip("requires materialized frozen public projections and candidates")
    data = read_json(TOPOLOGY / "topology_data.json")
    motion = read_json(REVIEW / "frames/motion_context/motion_manifest.json")
    original = read_json(REVIEW / "frames/visual_manifest.json")
    projected = read_json(OFFICE / "projected_frames.json")
    candidates = read_json(OFFICE / "candidates.json")
    module = builder()

    def build(
        motion_source: dict[str, Any] = motion,
        projection_source: dict[str, Any] = projected,
        candidate_source: dict[str, Any] = candidates,
    ) -> Any:
        return module.build_person_markers(
            data["raw_navigation"], motion_source, original,
            projection_source, candidate_source, 0.0247,
        )

    build()
    wrong_motion = copy.deepcopy(motion)
    wrong_motion["frames"][25]["body_base_bu"][0] += 1
    with pytest.raises(ValueError):
        build(motion_source=wrong_motion)
    wrong_projection = copy.deepcopy(projected)
    endpoint = next(
        sample for sample in wrong_projection["dataset"]["samples"]
        if sample["frame_id"] == 20 and sample["projected_point"] is not None
    )
    endpoint["projected_point"]["world_position"][1] += 1
    with pytest.raises(ValueError):
        build(projection_source=wrong_projection)
    wrong_candidate = copy.deepcopy(candidates)
    wrong_candidate["results"][0]["candidates"][0]["navmesh_corridor"] = ["pilot_route:right"]
    with pytest.raises(ValueError):
        build(candidate_source=wrong_candidate)


# This synthetic DOM executes the real topology template without opening a
# browser, storage, model file, or GT. Image completion is deliberately controlled
# so the test can distinguish requested playback from a displayed loaded frame.
DOM_MODEL = r"""
const vm=require('node:vm');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
class Element {
  constructor(tag,doc){this.tagName=tag.toUpperCase();this.ownerDocument=doc;
    this.children=[];this.parentElement=null;this.attributes={};this.dataset={};
    this.listeners={};this.style={};this.value='';this._text='';this._id='';
    this.className='';this.hidden=false;this.classList={toggle(){},add(){},remove(){}};}
  set id(value){this._id=value;this.ownerDocument.ids.set(value,this);}
  get id(){return this._id;}
  set textContent(value){this._text=String(value);this.replaceChildren();}
  get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
  append(...nodes){for(let node of nodes){if(typeof node==='string'){
    const text=new Element('#text',this.ownerDocument);text._text=node;node=text;}
    if(node.parentElement)node.remove();node.parentElement=this;this.children.push(node);}}
  appendChild(node){this.append(node);return node;}
  replaceChildren(...nodes){for(const node of this.children)node.parentElement=null;
    this.children=[];this.append(...nodes);}
  remove(){if(!this.parentElement)return;
    this.parentElement.children=this.parentElement.children.filter(node=>node!==this);
    this.parentElement=null;}
  setAttribute(key,value){this.attributes[key]=String(value);
    if(key==='id')this.id=value;if(key==='class')this.className=value;
    if(key.startsWith('data-'))this.dataset[key.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(value);}
  getAttribute(key){return this.attributes[key]??this[key]??null;}
  addEventListener(type,callback){(this.listeners[type]??=[]).push(callback);}
  async fire(type,event={}){for(const callback of this.listeners[type]||[]){
    await callback({target:this,currentTarget:this,preventDefault(){},...event});}}
  matches(selector){if(selector.startsWith('#'))return this.id===selector.slice(1);
    const match=selector.match(/^([\w-]+)?(?:\[([\w-]+)(?:=["']?([^\]"']+)["']?)?\])?$/);
    if(!match)return false;const[,tag,attribute,value]=match;
    return (!tag||this.tagName===tag.toUpperCase())&&(!attribute||
      (value===undefined?this.getAttribute(attribute)!==null:String(this.getAttribute(attribute))===value));}
  querySelectorAll(selector){return this.children.flatMap(child=>[
    ...(child.matches(selector)?[child]:[]),...child.querySelectorAll(selector)]);}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
}
class Document {
  constructor(){this.ids=new Map();this.body=new Element('body',this);
    this.listeners={};this.hidden=false;}
  createElement(tag){return new Element(tag,this);}
  createElementNS(namespace,tag){const element=this.createElement(tag);
    element.namespaceURI=namespace;return element;}
  getElementById(id){return this.ids.get(id)||null;}
  addEventListener(type,callback){(this.listeners[type]??=[]).push(callback);}
  async fire(type){for(const callback of this.listeners[type]||[])await callback();}
}
const document=new Document();
for(const match of input.html.matchAll(/<([\w-]+)\b([^>]*\bid="([^"]+)"[^>]*)>/g)){
  const element=document.createElement(match[1]);element.id=match[3];
  for(const attribute of match[2].matchAll(/([\w-]+)="([^"]*)"/g)){
    element.setAttribute(attribute[1],attribute[2]);
    if(attribute[1]==='value')element.value=attribute[2];}
  document.body.append(element);}
for(const match of input.html.matchAll(
    /<script id="([^"]+)" type="application\/json">([\s\S]*?)<\/script>/g)){
  document.getElementById(match[1]).textContent=match[2];}
document.getElementById('mode').value='floor';
const pendingImages=[],timers=new Map();let nextTimer=1;
class Image {
  constructor(){this.complete=false;}
  set src(value){this._src=value;pendingImages.push(this);}
  get src(){return this._src;}
}
const context={document,Image,console,pendingImages,timers,structuredClone,
  setInterval:callback=>{const id=nextTimer++;timers.set(id,callback);return id;},
  clearInterval:id=>timers.delete(id),setTimeout:callback=>callback()};
context.window=context;vm.createContext(context);
for(const match of input.html.matchAll(/<script>([\s\S]*?)<\/script>/g)){
  vm.runInContext(match[1],context);}
Promise.resolve(vm.runInContext(input.action,context)).then(result=>{
  process.stdout.write(JSON.stringify(result));}).catch(error=>{console.error(error);process.exitCode=1;});
"""


def browser_model(html: str, action: str) -> Any:
    node = shutil.which("node")
    if node is None:
        pytest.skip("topology behavior checks require Node.js; no real browser is used")
    result = subprocess.run(
        [node, "-e", DOM_MODEL],
        input=json.dumps({"html": html, "action": action}),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_loaded_frame_cursor_tracks_scrubbing_playback_and_mode_without_moving_graph() -> None:
    html = (TOPOLOGY / "view.html").read_text()
    embedded = re.search(
        r'<script id="topology-data" type="application/json">(.*?)</script>', html, re.S
    )
    assert embedded is not None
    data = json.loads(embedded[1].replace("<\\/", "</"))
    assert data == read_json(TOPOLOGY / "topology_data.json")
    result = browser_model(
        html,
        r"""(async()=>{
          const serialize=element=>({tag:element.tagName,attributes:element.attributes,
            text:element._text,children:element.children.map(serialize)});
          const tree=id=>JSON.stringify(serialize(document.getElementById(id)));
          const pixel=id=>{const element=document.getElementById(id);
            return ['cx','cy'].map(key=>Number(element.getAttribute(key)));};
          const sample=()=>({frame:Number(document.getElementById('frame')
              .getAttribute('data-loaded-frame')),image:document.getElementById('frame').src,
            modelFrame:Number(document.getElementById('model-person').getAttribute('data-frame-id')),
            graphFrame:Number(document.getElementById('graph-person').getAttribute('data-frame-id')),
            model:pixel('model-person-foot'),raw:pixel('model-person-landmark'),
            graph:pixel('graph-person-foot'),
            state:document.getElementById('model-person').getAttribute('data-state'),
            node:document.getElementById('model-person').getAttribute('data-node-id'),
            edge:document.getElementById('graph-person').getAttribute('data-edge-id'),
            scope:document.getElementById('graph-person').getAttribute('data-scope'),
            relation:document.getElementById('current-relation').textContent,
            time:document.getElementById('current-time-state').textContent,
            source:document.getElementById('current-source').textContent});
          pendingImages.at(-1).onload();
          const staticModel=tree('fixed-model-topology'),staticGraph=tree('fixed-graph-topology');
          const samples=[];
          for(let i=0;i<50;i++){
            await document.getElementById('slider').fire('input',{target:{value:String(i)}});
            pendingImages.at(-1).onload();samples.push(sample());}
          const staticAfterScrub=staticModel===tree('fixed-model-topology')&&
            staticGraph===tree('fixed-graph-topology');
          await document.getElementById('slider').fire('input',{target:{value:'20'}});
          pendingImages.at(-1).onload();
          await document.getElementById('play').fire('click');
          const timerCountPlaying=timers.size;[...timers.values()][0]();
          const whileLoading=sample();pendingImages.at(-1).onload();const afterTick=sample();
          document.hidden=true;await document.fire('visibilitychange');
          const timerCountHidden=timers.size;document.hidden=false;
          const beforeMode=sample();document.getElementById('mode').value='raw';
          await document.getElementById('mode').fire('change');const afterRawMode=sample();
          const rawStaticDifferent=staticModel!==tree('fixed-model-topology');
          document.getElementById('mode').value='floor';
          await document.getElementById('mode').fire('change');
          const floorStaticRestored=staticModel===tree('fixed-model-topology');
          const graphStaticUnchanged=staticGraph===tree('fixed-graph-topology');
          show(0);const stale=pendingImages.at(-1);show(49);const latest=pendingImages.at(-1);
          stale.onload();const afterStaleBeforeLatest=sample();
          latest.onload();const afterLatest=sample();stale.onload();const afterStale=sample();
          show(12);pendingImages.at(-1).onerror();const afterFailure=sample();
          return {samples,staticAfterScrub,timerCountPlaying,whileLoading,afterTick,
            timerCountHidden,beforeMode,afterRawMode,rawStaticDifferent,
            floorStaticRestored,graphStaticUnchanged,afterStaleBeforeLatest,
            afterLatest,afterStale,afterFailure,timersAfterFailure:timers.size};
        })()""",
    )
    samples = result["samples"]
    assert len(samples) == 50
    for sample, frame in zip(samples, data["frames"], strict=True):
        position = frame["current_position"]
        relation = position["graph_relation"]
        assert sample["frame"] == sample["modelFrame"] == sample["graphFrame"] == frame["frame_id"]
        assert sample["image"] == frame["path"]
        assert sample["model"] == position["floor_pixel"]
        assert sample["raw"] == position["raw_pixel"]
        assert sample["state"] == position["state"]
        assert sample["node"] == (relation["node_id"] or "")
        assert sample["edge"] == (relation["edge_id"] or "")
        assert sample["scope"] == relation["scope"]
        assert sample["source"] == position["role"]
        assert f'{frame["timestamp"]:.1f} s' in sample["time"]
        assert position["state"] in sample["time"]
    assert len({tuple(sample["graph"]) for sample in samples}) == 50
    # The diagram retains motion outside the finite GAP graph as well: the
    # cursor must not stick to N1 before departure or N2 after recovery.
    assert samples[0]["graph"][1] > samples[20]["graph"][1]
    assert samples[49]["graph"][1] < samples[45]["graph"][1]
    assert "N1" in samples[20]["relation"] and "N2" in samples[45]["relation"]
    assert "E1" in samples[25]["relation"] and "20%" in samples[25]["relation"]
    assert "範圍外" in samples[0]["relation"] and "範圍外" in samples[49]["relation"]
    assert result["staticAfterScrub"] is True
    assert result["timerCountPlaying"] == 1 and result["timerCountHidden"] == 0
    assert result["whileLoading"]["frame"] == 20
    assert result["afterTick"]["frame"] == 21
    assert result["beforeMode"] == result["afterRawMode"]
    assert result["rawStaticDifferent"] is True
    assert result["floorStaticRestored"] is True
    assert result["graphStaticUnchanged"] is True
    assert result["afterStaleBeforeLatest"]["frame"] == 21
    assert result["afterLatest"]["frame"] == 49
    assert result["afterStale"] == result["afterLatest"]
    assert result["afterFailure"] == result["afterLatest"]
    assert result["timersAfterFailure"] == 0


def test_playback_status_elements_stay_mounted_during_load_commit_pause_and_error() -> None:
    """Status changes must not insert/remove rows around the fixed model viewport.

    CSS reserves the status slots; this executes the actual template to ensure
    playback never bypasses those slots by removing or hiding the elements.
    The native-browser check separately verifies the rendered bounding boxes.
    """
    html = (TOPOLOGY / "view.html").read_text()
    result = browser_model(
        html,
        r"""(async()=>{
          const ids=['load-state','frame-state','current-time-state',
            'current-relation','current-source','play','time'];
          const original=new Map(ids.map(id=>[id,document.getElementById(id)]));
          const sample=()=>Object.fromEntries(ids.map(id=>{
            const element=document.getElementById(id);
            return [id,{same:element===original.get(id),mounted:!!element.parentElement,
              hidden:element.hidden,display:element.style.display||'',
              height:element.style.height||'',width:element.style.width||'',
              text:element.textContent}];}));
          const snapshots=[sample()];pendingImages.at(-1).onload();snapshots.push(sample());
          for(let i=0;i<50;i++){
            await document.getElementById('slider').fire('input',{target:{value:String(i)}});
            snapshots.push(sample());pendingImages.at(-1).onload();snapshots.push(sample());}
          await document.getElementById('play').fire('click');snapshots.push(sample());
          await document.getElementById('play').fire('click');snapshots.push(sample());
          show(25);snapshots.push(sample());pendingImages.at(-1).onerror();snapshots.push(sample());
          return {snapshots,timers:timers.size,
            displayed:Number(document.getElementById('frame').getAttribute('data-loaded-frame'))};
        })()""",
    )
    assert result["displayed"] == 49
    assert result["timers"] == 0
    snapshots = result["snapshots"]
    assert len(snapshots) == 106
    for snapshot in snapshots:
        for status in snapshot.values():
            assert status["same"] is True and status["mounted"] is True
            assert status["hidden"] is False and status["display"] != "none"
            assert status["height"] == status["width"] == ""
    texts = {snapshot["load-state"]["text"] for snapshot in snapshots}
    assert "" in texts
    assert any("載入" in text for text in texts)
    assert any("失敗" in text for text in texts)
    assert {snapshot["play"]["text"] for snapshot in snapshots} - {""} == {
        "播放 10 秒", "暫停"
    }
    assert any("OBSERVED" in snapshot["current-time-state"]["text"] for snapshot in snapshots)
    assert any("GAP" in snapshot["current-time-state"]["text"] for snapshot in snapshots)


def test_playback_text_has_reserved_slots_and_loading_overlay_cannot_move_the_model() -> None:
    """Guard the flow contract that prevents empty/loading and role-text jitter.

    The JavaScript test above covers the real status transitions; these rules
    ensure neither those strings nor the play/pause label can resize the flow.
    Overflow remains readable rather than silently truncating review evidence.
    """
    for filename in ("template.html", "view.html"):
        html = (TOPOLOGY / filename).read_text()
        style = re.search(r"<style>(.*?)</style>", html, re.S)
        assert style is not None

        def declarations(selector: str, style_text: str = style[1]) -> dict[str, str]:
            result = {}
            for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", style_text):
                if selector in (part.strip() for part in selectors.split(",")):
                    result.update(
                        tuple(part.strip() for part in declaration.split(":", 1))
                        for declaration in body.split(";") if ":" in declaration
                    )
            return result

        for selector in (
            "#frame-state", "#current-time-state", "#current-relation", "#current-source"
        ):
            slot = declarations(selector)
            assert slot["block-size"].endswith("em")
            assert float(slot["block-size"][:-2]) == 2 * float(slot["line-height"])
            assert slot["overflow"] == "auto"
        loading = declarations("#load-state")
        assert loading["position"] == "absolute"
        assert declarations(".model")["position"] == "relative"
        assert declarations("#load-state:empty")["visibility"] == "hidden"
        assert declarations("html")["overflow-y"] == "scroll"
        assert declarations("#play")["inline-size"] == "8em"
        assert declarations("#play")["flex"] == "0 0 8em"
        assert declarations("#time")["inline-size"] == "9em"
        assert declarations("#time")["flex"] == "0 0 9em"
        assert declarations("#time")["white-space"] == "nowrap"

        class LoadingParent(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.stack: list[tuple[str, dict[str, str | None]]] = []
                self.parents: list[list[tuple[str, dict[str, str | None]]]] = []

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                attributes = dict(attrs)
                if attributes.get("id") == "load-state":
                    self.parents.append(self.stack.copy())
                if tag not in {"meta", "input", "img", "br", "hr", "link"}:
                    self.stack.append((tag, attributes))

            def handle_endtag(self, tag: str) -> None:
                for i in range(len(self.stack) - 1, -1, -1):
                    if self.stack[i][0] == tag:
                        del self.stack[i:]
                        return

        ancestry = LoadingParent()
        ancestry.feed(html)
        assert len(ancestry.parents) == 1
        assert any(
            "model" in (attributes.get("class") or "").split()
            for _, attributes in ancestry.parents[0]
        )
