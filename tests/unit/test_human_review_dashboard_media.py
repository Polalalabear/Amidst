"""Media navigation must not change the pending review or run extra players."""

from __future__ import annotations

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
