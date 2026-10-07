"""Media navigation must not change the pending review or run extra players."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "human_review"


@pytest.fixture
def dashboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, dict, Any]:
    spec = importlib.util.spec_from_file_location(
        "dashboard_builder", REVIEW / "build_dashboard.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clarity_path = REVIEW / "frames/review_clarity/manifest.json"
    if clarity_path.is_file():
        clarity = json.loads(clarity_path.read_text())
        rows = [clarity[key] for key in ("floor", "office", "hr02")]
        rows += clarity["approach_frames"]
        if all((clarity_path.parent / row["path"]).is_file() for row in rows):
            # Exercise the production companion with its real relative links.
            # The temporary HTML sits beside index.html and is removed at once.
            with tempfile.NamedTemporaryFile(suffix=".html", dir=REVIEW) as temporary:
                output = Path(temporary.name)
                monkeypatch.setattr(
                    sys,
                    "argv",
                    [
                        "build_dashboard",
                        "--output",
                        str(output),
                        "--clarity-manifest",
                        str(clarity_path),
                    ],
                )
                module.main()
                return (
                    output.read_text(),
                    json.loads((REVIEW / "decisions.json").read_text()),
                    module,
                )
    output = tmp_path / "index.html"
    monkeypatch.setattr(sys, "argv", ["build_dashboard", "--output", str(output)])
    module.main()
    return output.read_text(), json.loads((REVIEW / "decisions.json").read_text()), module


# This model executes the actual dashboard JavaScript with synthetic DOM and
# storage. It has no browser connection and cannot inspect the user's drafts.
DOM_MODEL = r"""
const vm=require('node:vm');
const input=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
class Element {
  constructor(tag,doc){this.tagName=tag.toUpperCase();this.ownerDocument=doc;
    this.children=[];this.parentElement=null;this.attributes={};this.dataset={};
    this.listeners={};this.style={};this.value='';this.checked=false;this.open=false;
    this.files=[];this._text='';this._id='';this.className='';this.hidden=false;
    this.classList={toggle:(name,force)=>{
      const names=new Set(this.className.split(/\s+/).filter(Boolean));
      const add=force===undefined?!names.has(name):force;
      if(add)names.add(name);else names.delete(name);
      this.className=[...names].join(' ');return add;},
      add:(name)=>this.classList.toggle(name,true),remove:(name)=>this.classList.toggle(name,false)};
  }
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
    if(selector.startsWith('.'))return this.className.split(/\s+/).includes(selector.slice(1));
    const match=selector.match(/^([\w-]+)?(?:\[([\w-]+)(?:=["']?([^\]"']+)["']?)?\])?(:checked)?$/);
    if(!match)return false;const [,tag,attribute,value,checked]=match;
    return (!tag||this.tagName===tag.toUpperCase())&&(!attribute||
      (value===undefined?this.getAttribute(attribute)!==null:String(this.getAttribute(attribute))===value))&&
      (!checked||this.checked);}
  querySelectorAll(selector){return this.children.flatMap(child=>[
    ...(child.matches(selector)?[child]:[]),...child.querySelectorAll(selector)]);}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  closest(selector){return this.matches(selector)?this:this.parentElement?.closest(selector)||null;}
  focus(){}
  select(){}
  click(){return this.fire('click');}
  showModal(){this.open=true;}
  close(){this.open=false;void this.fire('close');}
}
class Document {
  constructor(){this.ids=new Map();this.body=new Element('body',this);}
  createElement(tag){return new Element(tag,this);}
  createElementNS(namespace,tag){const element=this.createElement(tag);
    element.namespaceURI=namespace;return element;}
  getElementById(id){return this.ids.get(id)||null;}
  querySelectorAll(selector){return this.body.querySelectorAll(selector);}
  querySelector(selector){return this.body.querySelector(selector);}
}
const document=new Document();
for(const match of input.html.matchAll(/<([\w-]+)\b[^>]*\bid="([^"]+)"[^>]*>/g)){
  const element=document.createElement(match[1]);element.id=match[2];document.body.append(element);}
for(const match of input.html.matchAll(
    /<script type="application\/json" id="([^"]+)">([\s\S]*?)<\/script>/g)){
  document.getElementById(match[1]).textContent=match[2];}
const stored=new Map(),downloads=[];
const context={document,structuredClone,console,Blob,Date,setTimeout:fn=>fn(),
  localStorage:{getItem:key=>stored.get(key)??null,setItem:(key,value)=>stored.set(key,value)},
  URL:{createObjectURL:blob=>{downloads.push(blob);return 'blob:synthetic-download';},
    revokeObjectURL(){}},
  navigator:{},stored,downloads};
context.window=context;
vm.createContext(context);
for(const match of input.html.matchAll(/<script>([\s\S]*?)<\/script>/g)){
  vm.runInContext(match[1],context);}
Promise.resolve(vm.runInContext(input.action,context)).then(result=>{
  process.stdout.write(JSON.stringify(result));}).catch(error=>{console.error(error);process.exitCode=1;});
"""


def browser_model(html: str, embedded: dict, action: str) -> Any:
    node = shutil.which("node")
    if node is None:
        pytest.skip("dashboard behavior checks require Node.js; no real browser storage is used")
    result = subprocess.run(
        [node, "-e", DOM_MODEL],
        input=json.dumps({"html": html, "embedded": embedded, "action": action}),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def camera_enabled_dashboard(dashboard: tuple[str, dict, Any]) -> tuple[str, dict, str]:
    """Exercise feature-gated JS even when regenerable renderer images are absent."""
    html, document, _ = dashboard
    match = re.search(r"const hr02CameraViewHash='([a-f0-9]*)';", html)
    assert match is not None
    if match[1]:
        return html, document, match[1]
    # This is synthetic DOM input only. No receipt, real browser, decision or
    # package file is edited; the separate gate test checks actual hash binding.
    synthetic_hash = hashlib.sha256(b"synthetic HR02 media-navigation fixture").hexdigest()
    return (
        html.replace(match[0], f"const hr02CameraViewHash='{synthetic_hash}';"),
        document,
        synthetic_hash,
    )


@pytest.fixture
def camera_hash_fixture(
    dashboard: tuple[str, dict, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, dict, Path, dict]:
    _, document, module = dashboard
    fixture_root = tmp_path / "camera-hash-fixture"
    directory = fixture_root / "human_review/frames/hr02_camera_audit"
    directory.mkdir(parents=True)
    manifest = {
        "source_sha256": document["metadata"]["source_sha256"],
        "review_payload_sha256": document["review_payload_sha256"],
        "result_type": "DIAGNOSTIC",
        "frame_count": 50,
        "fps": 5,
        "camera_still_frames": [20, 25, 45],
        "separate_public_record_and_projected_replay": True,
        "camera_stills_are_representative_not_current_playback": True,
        **dict.fromkeys(
            (
                "gt_used",
                "evaluation_files_read",
                "simulation_recipe_read",
                "physical_authority_changed",
                "formal_execution_enabled",
                "decisions_changed",
                "projection_changed",
                "raw_graph_changed",
                "original_source_point_available",
            ),
            False,
        ),
    }
    for key, filename in (
        ("view", "view.html"),
        ("data", "audit_data.json"),
        ("producer", "manifest.json"),
        ("renderer", "renderer_manifest.json"),
    ):
        path = directory / filename
        path.write_text("<p>Synthetic diagnostic fixture</p>" if key == "view" else "{}\n")
        manifest[key] = {"path": filename, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (directory / "view_manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(module, "ROOT", fixture_root)
    return module, document, directory, manifest


def test_dashboard_media_preserves_four_questions_storage_and_import_export_guards(
    dashboard: tuple[str, dict, Any],
) -> None:
    html, document, module = dashboard
    match = re.search(
        r'<script type="application/json" id="review-data">(.*?)</script>', html, re.S
    )
    assert match is not None
    embedded = json.loads(match[1].replace("<\\/", "</"))
    assert embedded == document
    template = json.loads((REVIEW / "review_template.json").read_text())
    assert [item["id"] for item in embedded["items"]] == ["HR-01", "HR-02", "HR-03", "HR-04"]
    assert module.review_identity(embedded) == module.review_identity(template)
    assert module.payload_hash(embedded) == template["review_payload_sha256"]
    result = browser_model(
        html,
        embedded,
        r"""(async()=>{
          const initialIdentity=canonical(reviewIdentity(documentState));
          const candidate=structuredClone(embedded);
          candidate.metadata.reviewer='Synthetic test';candidate.metadata.submitted_at=null;
          for(const item of candidate.items){item.decision='APPROVE';
            item.selected_option=item.approve_options?.[0]?.id||null;}
          const good=samePayload(candidate)&&validDecisions(candidate);
          const changedQuestion=structuredClone(candidate);
          changedQuestion.items[0].media={path:'new.html'};
          const changedSource=structuredClone(candidate);
          changedSource.metadata.source_sha256='different';
          const changedOrder=structuredClone(candidate);changedOrder.items.reverse();
          const badProfile=structuredClone(candidate);
          badProfile.items[0].selected_option='invented';
          await document.getElementById('import-file').fire('change',{
            target:{files:[{text:async()=>JSON.stringify(candidate)}],value:'synthetic.json'}});
          await document.getElementById('export').fire('click');
          const exported=JSON.parse(await downloads[0].text());
          return {storageKey,good,rejectQuestion:!samePayload(changedQuestion),
            rejectSource:!samePayload(changedSource),rejectOrder:!samePayload(changedOrder),
            rejectProfile:!validDecisions(badProfile),
            identity:canonical(reviewIdentity(documentState))===initialIdentity,
            exportedIdentity:canonical(reviewIdentity(exported))===initialIdentity,
            exportedReviewer:exported.metadata.reviewer,exportedDecisions:exported.items.map(i=>i.decision),
            draftKeys:[...stored.keys()],draft:JSON.parse(stored.get(storageKey))};
        })()""",
    )
    expected_key = ".".join(
        (
            "amidst.phase1.review",
            document["metadata"]["checkpoint_sha"],
            document["metadata"]["source_sha256"],
            template["review_payload_sha256"],
        )
    )
    assert result["storageKey"] == expected_key
    assert result["draftKeys"] == [expected_key]
    assert all(
        result[key]
        for key in (
            "good",
            "rejectQuestion",
            "rejectSource",
            "rejectOrder",
            "rejectProfile",
            "identity",
            "exportedIdentity",
        )
    )
    assert result["exportedReviewer"] == "Synthetic test"
    assert result["exportedDecisions"] == ["APPROVE"] * 4
    assert result["draft"]["review_payload_hash"] == template["review_payload_sha256"]
    assert result["draft"]["document"]["metadata"]["formal_execution_enabled"] is False


def test_media_tabs_load_one_active_player_and_pause_for_modal_without_saving_decisions(
    dashboard: tuple[str, dict, Any],
) -> None:
    html, document, _ = dashboard
    result = browser_model(
        html,
        document,
        r"""(async()=>{
          const before=canonical(documentState),counts=[];
          const frames=()=>document.querySelectorAll('iframe');
          const sample=()=>counts.push(frames().length);
          sample();const first=frames()[0];sharedMediaWorkspace.select('motion');
          const repeatedSelectionKeptPlayer=first===frames()[0];sample();
          const paths=[],linkPaths=[];
          for(const id of ['context','motion','topology']){
            sharedMediaWorkspace.select(id);sample();paths.push(frames()[0].src);
            linkPaths.push(sharedMediaWorkspace.host.querySelector('.media-links')
              .querySelector('a').href);}
          const detachedPrevious=first.parentElement===null;
          const previous=frames()[0],selectedBefore=sharedMediaWorkspace.selectedView;
          const unknownRejected=sharedMediaWorkspace.select('unknown')===false&&
            previous===frames()[0]&&sharedMediaWorkspace.selectedView===selectedBefore;
          sharedMediaWorkspace.select('issues');sample();
          await document.getElementById('shared-review-issues').fire('keydown',{key:'ArrowLeft'});
          sample();const keyboardSelection=sharedMediaWorkspace.selectedView;
          openItem('HR-01');sample();
          const sharedStopped=document.getElementById('visual-review-workspace')
            .querySelectorAll('iframe').length===0;
          const modalCount=document.getElementById('item-visual-workspace')
            .querySelectorAll('iframe').length;
          closeItem();sample();
          return {counts,paths,linkPaths,clarityHash:reviewClarity.manifest_sha256||null,
            repeatedSelectionKeptPlayer,detachedPrevious,unknownRejected,
            keyboardSelection,sharedStopped,modalCount,finalFrames:frames().length,
            documentUnchanged:before===canonical(documentState),draftWrites:stored.size};
        })()""",
    )
    context_url = urlsplit(result["paths"][0])
    assert context_url.path == "frames/spatial_context/guide.html"
    assert context_url.scheme == context_url.netloc == context_url.fragment == ""
    if result["clarityHash"] is not None:
        assert re.fullmatch(r"[a-f0-9]{64}", result["clarityHash"])
        manifest_path = REVIEW / "frames/review_clarity/manifest.json"
        assert result["clarityHash"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        assert parse_qsl(context_url.query, keep_blank_values=True) == [
            ("review", result["clarityHash"])
        ]
    else:
        assert context_url.query == ""
    assert result["paths"][1] == "frames/motion_context/player.html"
    topology_url = urlsplit(result["paths"][2])
    assert topology_url.path == "frames/topology_context/view.html"
    assert topology_url.scheme == topology_url.netloc == topology_url.fragment == ""
    topology_manifest = REVIEW / "frames/topology_context/topology_manifest.json"
    if topology_manifest.is_file():
        expected_hash = json.loads(topology_manifest.read_text())["view"]["sha256"]
        assert (
            expected_hash
            == hashlib.sha256((topology_manifest.parent / "view.html").read_bytes()).hexdigest()
        )
        assert parse_qsl(topology_url.query) == [("review", expected_hash)]
    else:
        assert topology_url.query == ""
    assert result["linkPaths"] == result["paths"]
    assert result["counts"] == [1, 1, 1, 1, 1, 0, 1, 1, 0]
    assert result["modalCount"] == 1 and result["finalFrames"] == 0
    assert result["keyboardSelection"] == "topology"
    assert all(
        result[key]
        for key in (
            "repeatedSelectionKeptPlayer",
            "detachedPrevious",
            "unknownRejected",
            "sharedStopped",
            "documentUnchanged",
        )
    )
    assert result["draftWrites"] == 0
    without_clarity = re.sub(
        r'(<script type="application/json" id="review-clarity-data">).*?(</script>)',
        r"\1{}\2",
        html,
        flags=re.S,
    )
    fallback = browser_model(
        without_clarity,
        document,
        r"""(()=>{
          sharedMediaWorkspace.select('context');
          return {path:document.querySelector('iframe').src,
            link:sharedMediaWorkspace.host.querySelector('.media-links').querySelector('a').href,
            playerCount:document.querySelectorAll('iframe').length,draftWrites:stored.size,
            questionIdentity:canonical(reviewIdentity(documentState))===
              canonical(reviewIdentity(embedded)),storageKey};
        })()""",
    )
    assert fallback["path"] == fallback["link"] == "frames/spatial_context/guide.html"
    assert fallback["playerCount"] == 1
    assert fallback["draftWrites"] == 0
    assert fallback["questionIdentity"] is True
    assert fallback["storageKey"] == ".".join(
        [
            "amidst.phase1.review",
            document["metadata"]["checkpoint_sha"],
            document["metadata"]["source_sha256"],
            document["review_payload_sha256"],
        ]
    )


def test_hr01_hr02_keep_original_images_and_lazy_sequence_as_exclusive_evidence(
    dashboard: tuple[str, dict, Any],
) -> None:
    html, document, _ = dashboard
    result = browser_model(
        html,
        document,
        r"""(async()=>{
          const before=canonical(documentState),results=[];
          for(const id of ['HR-01','HR-02']){
            openItem(id);const body=document.getElementById('item-content');
            const original=body.querySelector('[data-role="original-evidence-images"]');
            const originalNodes=original.querySelectorAll('img');
            const images=originalNodes.map(image=>image.src);
            const extraImages=body.querySelectorAll('img')
              .filter(image=>!originalNodes.includes(image)).map(image=>image.src);
            const callout=body.querySelector('[data-role="hr02-foot-callout"]');
            const footPixel=callout?[
              Number(callout.getAttribute('cx')),Number(callout.getAttribute('cy'))]:null;
            const imageLinks=body.querySelectorAll('a').map(link=>link.href);
            const legacy=body.querySelector('[data-role="legacy-sequence"]');
            const initiallyClosed=!legacy.open&&legacy.querySelectorAll('iframe').length===0;
            const sequenceLink=legacy.querySelector('a').href;
            legacy.open=true;await legacy.fire('toggle');
            const exclusiveLegacy=document.querySelectorAll('iframe').length===1&&
              legacy.querySelectorAll('iframe').length===1;
            const legacySource=legacy.querySelector('iframe').src;
            modalMediaWorkspace.select('topology');
            const legacyStopped=!legacy.open&&legacy.querySelectorAll('iframe').length===0;
            const exclusiveNew=document.querySelectorAll('iframe').length===1;
            closeItem();
            results.push({id,images,extraImages,footPixel,imageLinks,
              initiallyClosed,sequenceLink,exclusiveLegacy,
              legacySource,legacyStopped,exclusiveNew,closedFrames:
                document.querySelectorAll('iframe').length});
          }
          return {results,clarityData:reviewClarity,
            documentUnchanged:before===canonical(documentState),
            draftWrites:stored.size};
        })()""",
    )
    originals = {item["id"]: item for item in document["items"]}
    for row in result["results"]:
        evidence = originals[row["id"]]["evidence"]
        expected_images = [
            image["path"].removeprefix("human_review/") for image in evidence["images"]
        ]
        expected_sequence = evidence["sequence"].removeprefix("human_review/")
        assert row["images"] == expected_images
        expected_extra = (
            [result["clarityData"]["hr02"]["path"]]
            if row["id"] == "HR-02" and result["clarityData"].get("hr02")
            else []
        )
        assert row["extraImages"] == expected_extra
        if expected_extra:
            expected_pixel = result["clarityData"]["hr02"]["display_projection"]["foot_pixel"]
            assert row["footPixel"] == pytest.approx(expected_pixel)
        else:
            assert row["footPixel"] is None
        assert set(expected_images).issubset(row["imageLinks"])
        assert row["sequenceLink"] == row["legacySource"] == expected_sequence
        assert all(
            row[key]
            for key in ("initiallyClosed", "exclusiveLegacy", "legacyStopped", "exclusiveNew")
        )
        assert row["closedFrames"] == 0
    assert result["documentUnchanged"] is True
    assert result["draftWrites"] == 0
    if result["clarityData"]:
        assert result["clarityData"]["result_type"] == "DIAGNOSTIC"
        assert result["clarityData"]["gt_used"] is False
        assert result["clarityData"]["physical_authority_changed"] is False
        assert result["clarityData"]["formal_execution_enabled"] is False


def test_hr02_camera_tab_and_modal_use_one_player_without_recording_decisions(
    camera_enabled_dashboard: tuple[str, dict, str],
) -> None:
    html, document, camera_hash = camera_enabled_dashboard
    result = browser_model(
        html,
        document,
        r"""(async()=>{
          const before=canonical(documentState),counts=[];
          const frames=()=>document.querySelectorAll('iframe');
          const sample=()=>counts.push(frames().length);
          const sharedTabs=sharedMediaWorkspace.host.querySelectorAll('button[role="tab"]')
            .map(button=>({id:button.id,label:button.textContent}));
          sample();const first=frames()[0];
          const cameraSelected=sharedMediaWorkspace.select('camera-audit');sample();
          const cameraFrame=frames()[0],cameraPath=cameraFrame.src;
          const cameraLink=sharedMediaWorkspace.host.querySelector('.media-links')
            .querySelector('a').href;
          sharedMediaWorkspace.select('camera-audit');sample();
          const repeatedCameraKeptPlayer=cameraFrame===frames()[0];
          sharedMediaWorkspace.select('topology');sample();
          const oldCameraUnloaded=cameraFrame.src==='about:blank'&&cameraFrame.parentElement===null;
          sharedMediaWorkspace.select('issues');sample();
          await document.getElementById('shared-review-issues').fire('keydown',{key:'ArrowRight'});
          sample();const keyboardSelection=sharedMediaWorkspace.selectedView;
          const playingShared=frames()[0];openItem('HR-02');sample();
          const hr02Initial=modalMediaWorkspace.selectedView;
          const hr02Path=frames()[0].src;
          const hr02Choices=document.getElementById('decision-select').children.map(e=>e.value);
          const hr02NoChoice=document.getElementById('decision-select').value==='';
          const sharedUnloaded=playingShared.src==='about:blank'&&
            playingShared.parentElement===null&&
            document.getElementById('visual-review-workspace').querySelectorAll('iframe').length===0;
          const modalCamera=frames()[0];modalMediaWorkspace.select('motion');sample();
          const modalCameraUnloaded=modalCamera.src==='about:blank'&&
            modalCamera.parentElement===null;
          modalMediaWorkspace.select('camera-audit');sample();
          const closingFrame=frames()[0];closeItem();sample();
          const closeUnloaded=closingFrame.src==='about:blank'&&closingFrame.parentElement===null;
          openItem('HR-01');sample();const hr01Initial=modalMediaWorkspace.selectedView;
          const hr01Path=frames()[0].src;closeItem();sample();
          return {counts,sharedTabs,cameraSelected,cameraPath,cameraLink,hr02Initial,hr02Path,
            hr02Choices,hr02NoChoice,hr01Initial,hr01Path,keyboardSelection,
            firstUnloaded:first.src==='about:blank'&&first.parentElement===null,
            repeatedCameraKeptPlayer,oldCameraUnloaded,sharedUnloaded,modalCameraUnloaded,
            closeUnloaded,documentUnchanged:before===canonical(documentState),
            decisions:documentState.items.map(i=>i.decision),
            selectedOptions:documentState.items.map(i=>i.selected_option),draftWrites:stored.size};
        })()""",
    )
    assert [tab["id"] for tab in result["sharedTabs"]] == [
        "shared-review-context",
        "shared-review-motion",
        "shared-review-topology",
        "shared-review-issues",
        "shared-review-camera-audit",
    ]
    assert [tab["label"] for tab in result["sharedTabs"]][:4] == [
        "1 空間定位",
        "2 行走動畫",
        "3 模型＋拓樸",
        "4 接縫／binding",
    ]
    assert result["sharedTabs"][-1]["label"] == "HR02 相機／遮擋"
    expected_path = f"frames/hr02_camera_audit/view.html?review={camera_hash}"
    assert result["cameraPath"] == result["cameraLink"] == result["hr02Path"] == expected_path
    assert result["hr02Initial"] == result["keyboardSelection"] == "camera-audit"
    assert result["hr01Initial"] == "motion"
    assert result["hr01Path"] == "frames/motion_context/player.html"
    assert result["hr02Choices"] == ["", "APPROVE", "REJECT", "FIX_GEOMETRY", "KEEP_REVIEW"]
    assert result["decisions"] == [item["decision"] for item in document["items"]]
    assert result["selectedOptions"] == [item["selected_option"] for item in document["items"]]
    assert result["counts"] == [1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 0]
    assert result["draftWrites"] == 0
    assert all(
        result[key]
        for key in (
            "cameraSelected",
            "hr02NoChoice",
            "firstUnloaded",
            "repeatedCameraKeptPlayer",
            "oldCameraUnloaded",
            "sharedUnloaded",
            "modalCameraUnloaded",
            "closeUnloaded",
            "documentUnchanged",
        )
    )


def test_camera_media_requires_verified_view_receipt_and_preserves_missing_receipt_fallback(
    dashboard: tuple[str, dict, Any], camera_hash_fixture: tuple[Any, dict, Path, dict]
) -> None:
    html, document, _ = dashboard
    module, fixture_document, directory, manifest = camera_hash_fixture
    original = copy.deepcopy(fixture_document)
    assert module.hr02_camera_view_hash(fixture_document) == manifest["view"]["sha256"]
    assert fixture_document == original
    (directory / "view_manifest.json").unlink()
    assert module.hr02_camera_view_hash(fixture_document) == ""
    match = re.search(r"const hr02CameraViewHash='([a-f0-9]*)';", html)
    assert match is not None
    canonical_receipt = REVIEW / "frames/hr02_camera_audit/view_manifest.json"
    if canonical_receipt.is_file():
        receipt = json.loads(canonical_receipt.read_text())
        expected_hash = hashlib.sha256(
            (canonical_receipt.parent / "view.html").read_bytes()
        ).hexdigest()
        assert match[1] == receipt["view"]["sha256"] == expected_hash
    else:
        assert match[1] == ""
    without_camera = html.replace(match[0], "const hr02CameraViewHash='';")
    result = browser_model(
        without_camera,
        document,
        r"""(()=>{
          const before=canonical(documentState),original=document.querySelector('iframe');
          const rejected=sharedMediaWorkspace.select('camera-audit')===false;
          openItem('HR-02');const fallback=modalMediaWorkspace.selectedView;
          closeItem();return {rejected,fallback,originalUnloaded:original.src==='about:blank',
            tabs:sharedMediaWorkspace.host.querySelectorAll('button[role="tab"]').map(e=>e.id),
            documentUnchanged:before===canonical(documentState),draftWrites:stored.size};
        })()""",
    )
    assert result["rejected"] is True
    assert result["fallback"] == "motion"
    assert len(result["tabs"]) == 4
    assert result["originalUnloaded"] is result["documentUnchanged"] is True
    assert result["draftWrites"] == 0


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "review",
        "formal",
        "gt",
        "original_source_3d",
        "frame_count",
        "merged_visibility",
        "canonical_path",
        "view_drift",
        "renderer_drift",
    ],
)
def test_camera_dashboard_gate_rejects_promoted_or_changed_evidence(
    camera_hash_fixture: tuple[Any, dict, Path, dict], change: str
) -> None:
    module, document, directory, original = camera_hash_fixture
    assert module.hr02_camera_view_hash(document) == original["view"]["sha256"]
    changed = copy.deepcopy(original)
    if change == "source":
        changed["source_sha256"] = "0" * 64
    elif change == "review":
        changed["review_payload_sha256"] = "0" * 64
    elif change == "formal":
        changed["formal_execution_enabled"] = True
    elif change == "gt":
        changed["gt_used"] = True
    elif change == "original_source_3d":
        changed["original_source_point_available"] = True
    elif change == "frame_count":
        changed["frame_count"] = 49
    elif change == "merged_visibility":
        changed["separate_public_record_and_projected_replay"] = False
    elif change == "canonical_path":
        changed["data"]["path"] = "../unlisted.json"
    elif change == "view_drift":
        (directory / "view.html").write_text("changed view")
    elif change == "renderer_drift":
        (directory / "renderer_manifest.json").write_text("changed renderer")
    (directory / "view_manifest.json").write_text(json.dumps(changed))
    with pytest.raises(ValueError):
        module.hr02_camera_view_hash(document)


@pytest.mark.parametrize("with_camera_evidence", [True, False])
def test_hr02_evidence_recommendation_changes_display_only_and_keeps_original_profiles(
    camera_enabled_dashboard: tuple[str, dict, str], with_camera_evidence: bool
) -> None:
    html, document, _ = camera_enabled_dashboard
    if not with_camera_evidence:
        html = re.sub(
            r"const hr02CameraViewHash='[a-f0-9]{64}';",
            "const hr02CameraViewHash='';",
            html,
        )
    result = browser_model(
        html,
        document,
        r"""(async()=>{
          const before=canonical(documentState),original=embedded.items.find(i=>i.id==='HR-02');
          const display=evidenceRecommendation(original);
          const tableRow=document.getElementById('decision-table').children
            .find(row=>row.children[0].textContent==='HR-02');
          const tableRecommendation=tableRow.children[3].textContent;
          const originalRecommendation=original.recommended_decision;
          openItem('HR-02');const body=document.getElementById('item-content');
          const recommendedSection=body.querySelectorAll('section')
            .find(section=>section.children[0]?.textContent==='Recommended decision:');
          const modalRecommendation=recommendedSection.textContent;
          const select=document.getElementById('decision-select'),initialChoice=select.value;
          select.value='APPROVE';await select.fire('change');
          const radios=body.querySelectorAll('input[name="approval-profile"]');
          const profileIds=radios.map(r=>r.value);
          const checked=radios.filter(r=>r.checked).map(r=>r.value);
          closeItem();
          return {tableRecommendation,modalRecommendation,displayDecision:display.decision,
            displayOption:display.option?.id||null,originalRecommendation,initialChoice,
            profileIds,checked,documentUnchanged:before===canonical(documentState),
            questionsUnchanged:canonical(reviewIdentity(documentState))===
              canonical(reviewIdentity(embedded)),draftWrites:stored.size,
            decisions:documentState.items.map(i=>i.decision)};
        })()""",
    )
    original = next(item for item in document["items"] if item["id"] == "HR-02")
    assert result["originalRecommendation"] == original["recommended_decision"] == "APPROVE"
    if with_camera_evidence:
        assert result["displayDecision"] == "KEEP_REVIEW"
        assert result["displayOption"] is None
        for field in ("tableRecommendation", "modalRecommendation"):
            assert "KEEP_REVIEW" in result[field]
            assert "先確認目標房間／鏡頭與追蹤點語意" in result[field]
            assert "原 offset 提案保留供核對" in result[field]
    else:
        assert result["displayDecision"] == "APPROVE"
        assert result["displayOption"] == original["recommended_option"]
        assert "APPROVE" in result["tableRecommendation"]
        assert "APPROVE" in result["modalRecommendation"]
    assert result["profileIds"] == [option["id"] for option in original["approve_options"]]
    assert result["checked"] == [original["recommended_option"]]
    assert result["initialChoice"] == ""
    assert result["documentUnchanged"] is result["questionsUnchanged"] is True
    assert result["draftWrites"] == 0
    assert result["decisions"] == [item["decision"] for item in document["items"]]
