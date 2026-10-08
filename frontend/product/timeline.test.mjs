import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {sampleCanonicalTrajectory, sampleAllAlternatives, statistics, SoftSyncClock, observeVideo}
  from './timeline.mjs';

const hypothesis = {hypothesis_id: 'h1', candidate_id: 'c1', timed_points: [
  {timestamp: 0, world_position: [0, 0, 0], provenance: 'PROJECTED'},
  {timestamp: 2, world_position: [2, 4, 0], provenance: 'PROJECTED'},
]};
const state = t => ({run_ref: 'run:a', timestamp: t, markers: [], frames: [], presentation_only: true});

 test('sampling retains canonical alternatives, exact provenance and immutable source', () => {
  const input = structuredClone(hypothesis), original = JSON.stringify(input);
  const second = {...structuredClone(input), hypothesis_id: 'h2', candidate_id: 'c2'};
  const markers = sampleAllAlternatives([input, second], 1);
  assert.deepEqual(markers.map(row => row.hypothesis_id), ['h1', 'h2']);
  assert.deepEqual(markers[0].world_position, [1, 2, 0]);
  assert.equal(markers[0].provenance, 'INFERRED_GAP');
  assert.equal(markers[0].interpolated, true);
  assert.equal(sampleCanonicalTrajectory(input, 0).provenance, 'PROJECTED');
  assert.equal(sampleCanonicalTrajectory(input, 3), null);
  markers[0].world_position[0] = 99;
  assert.equal(JSON.stringify(input), original);
});

test('telemetry is N/A before callbacks and derived only from actual presented frames', async () => {
  let now = 0;
  const applied = [];
  const clock = new SoftSyncClock({runRef: 'run:a', masterCameraRef: 'camera:a', now: () => now,
    requestState: async t => state(t), applyState: s => applied.push(s), requestIntervalMs: 0});
  assert.equal(clock.telemetry().media_to_3d_skew_ms.mean, null);
  await clock.presented('camera:a', 0);
  now += 100;
  await clock.presented('camera:a', 0.1);
  await clock.presented('camera:b', 0.15);
  assert.equal(clock.telemetry().actual_frame_callbacks, 3);
  assert.equal(clock.telemetry().media_to_3d_skew_ms.mean, 100);
  assert.ok(Math.abs(clock.telemetry().camera_media_skew_ms.mean - 50) < 1e-9);
  await clock.presented('camera:a', 0.2, 0, {actualFrame: false});
  assert.equal(clock.telemetry().actual_frame_callbacks, 3);
  assert.equal(clock.telemetry().fallback_media_callbacks, 1);
  assert.equal(clock.telemetry().dropped_video_frames, null);
  assert.equal(applied.length, 3);
});

test('seek waits for actual media time; stale seek response cannot repaint newer state', async () => {
  let now = 0;
  const resolvers = [], applied = [];
  const clock = new SoftSyncClock({runRef: 'run:a', masterCameraRef: 'camera:a', now: () => now,
    requestState: () => new Promise(resolve => resolvers.push(resolve)),
    applyState: s => applied.push(s.timestamp), requestIntervalMs: 0});
  clock.seek(1);
  assert.equal(await clock.presented('camera:a', 0), false);
  assert.equal(resolvers.length, 0);
  const old = clock.presented('camera:a', 1);
  now = 20; clock.seek(4);
  const latest = clock.presented('camera:a', 4);
  now = 45; resolvers[1](state(4));
  assert.equal(await latest, true);
  resolvers[0](state(1));
  assert.equal(await old, false);
  assert.deepEqual(applied, [4]);
  assert.equal(clock.telemetry().seek_recovery_ms.mean, 25);
});

test('missing frame selections and wrong run are explicit', async () => {
  let bad = false, error = null;
  const clock = new SoftSyncClock({runRef: 'run:a', masterCameraRef: 'camera:a', requestIntervalMs: 0,
    requestState: async t => bad ? {...state(t), run_ref: 'run:b'} :
      {...state(t), frames: [{status: 'NO_FRAME_WITHIN_TOLERANCE'}]},
    applyState: () => {}, onError: e => {error = e;}});
  assert.equal(await clock.presented('camera:a', 1), true);
  assert.equal(clock.telemetry().missing_frame_selections, 1);
  bad = true;
  assert.equal(await clock.presented('camera:a', 2), false);
  assert.equal(error.message, 'TIMELINE_BINDING_DENIED');
});

test('closed session and stale ordinary requests cannot apply', async () => {
  let resolve;
  let applied = 0;
  const clock = new SoftSyncClock({runRef: 'run:a', masterCameraRef: 'camera:a', requestIntervalMs: 0,
    requestState: () => new Promise(r => {resolve = r;}), applyState: () => {applied++;}});
  const request = clock.presented('camera:a', 1);
  clock.close(); resolve(state(1));
  assert.equal(await request, false); assert.equal(applied, 0);
});

test('video observer uses metadata.mediaTime and cancels rVFC', async () => {
  let callback, cancelled = false, observed;
  const video = {currentTime: 99, requestVideoFrameCallback(fn) {callback = fn; return 1;},
    cancelVideoFrameCallback() {cancelled = true;}};
  const clock = {async presented(ref, time, start) {observed = [ref, time, start];}};
  const cleanup = observeVideo(video, {camera_ref: 'camera:a', start_time: 3}, clock);
  callback(0, {mediaTime: 2});
  assert.deepEqual(observed, ['camera:a', 2, 3]);
  cleanup(); assert.equal(cancelled, true);
});

test('statistics are actual sample estimates without fabricated data', () => {
  assert.deepEqual(statistics([]), {count: 0, mean: null, p95: null});
  assert.deepEqual(statistics([-10, 20, NaN]), {count: 2, mean: 15, p95: 20});
});

test('changing master or disposing video rejects late callbacks from the old scope', async () => {
  let resolve, applied=0, callback;
  const clock=new SoftSyncClock({runRef:'run:a',masterCameraRef:'camera:a',requestIntervalMs:0,
    requestState:()=>new Promise(r=>{resolve=r;}),applyState:()=>{applied++;}});
  const old=clock.presented('camera:a',1);
  clock.setMaster('camera:b');resolve(state(1));
  assert.equal(await old,false);assert.equal(applied,0);
  const video={requestVideoFrameCallback(fn){callback=fn;return 5;},cancelVideoFrameCallback(){}};
  let observed=0;
  const dispose=observeVideo(video,{camera_ref:'camera:a',start_time:0},
    {async presented(){observed++;}});
  dispose();callback(0,{mediaTime:8});
  assert.equal(observed,0);
});

// Run the actual UI workflow functions with transport and DOM boundaries replaced.
// The renderer and boot are inactive; no external browser or network is required.
function controlRoom(fetch) {
  const nodes=new Map(),downloads=[];
  class Element {
    constructor(tag='div') {this.tag=tag;this.children=[];this.value='';this.textContent='';this.disabled=false;
      this.classList={toggle(){}};}
    append(...items) {this.children.push(...items);}
    replaceChildren(...items) {this.children=[...items];}
    get firstChild() {return this.children[0];}
    get options() {return this.children;}
    querySelectorAll() {return this.children.flatMap(child=>child.tag==='input'&&child.checked?[child]:child.querySelectorAll?.()||[]);}
    addEventListener() {}
    remove() {}
    click() {if(this.tag==='a') downloads.push({href:this.href,download:this.download});}
  }
  const get=id=>{if(!nodes.has(id)) nodes.set(id,new Element());return nodes.get(id);};
  const document={getElementById:get,createElement:tag=>new Element(tag),body:new Element('body')};
  const source=readFileSync(new URL('./app.mjs',import.meta.url),'utf8')
    .replace(/^import .*;\n/gm,'').replace(/boot\(\)\.catch\(error\);\s*$/,'');
  const environment={document,fetch,AbortController,Blob,THREE:{},setTimeout,
    URL:{createObjectURL:()=>{downloads.push({created:true});return'blob:local-report';},revokeObjectURL(){}},
    console};
  runInNewContext(source+'\nglobalThis.operations={state,loadSavedPlan,loadContext,exportReport};',environment);
  return {...environment.operations,get,downloads};
}
const jsonReply=(payload,status=200)=>({ok:status===200,status,json:async()=>payload});
const uiContext=(session,stage='RESULTS')=>({session_ref:session,run_ref:'run:'+session,
  product_freeze_ref:'freeze:'+session,operator_ref:'operator:'+session,
  allowed_tools:['list_cameras','query_observations'],context:{place_id:'lab',run_id:'rgb',clock_id:'seconds',decision_stage:stage}});
const savedPlan=(ref,session='session-a')=>({plan_ref:ref,task:'TRACE',camera_ref:'camera:a',time_range:[0,6],
  seed_refs:['observation:a'],policy:{max_tool_calls:32,max_cameras:4},
  binding:{session_ref:session,freeze_ref:'freeze:'+session}});

test('actual UI saved-plan race preserves newer selection without running investigation', async () => {
  const pending=new Map(),calls=[];
  const ui=controlRoom((path,options)=>{
    const payload=JSON.parse(options.body);calls.push(path);
    if(path.endsWith('/plan')) return new Promise(resolve=>pending.set(payload.plan_ref,resolve));
    if(path.endsWith('/query_observations')) return Promise.resolve(jsonReply({items:[]}));
    if(path.endsWith('/case')) return Promise.resolve(jsonReply({error:'CASE_UNAVAILABLE'},403));
    throw Error('unexpected tool '+path);
  });
  ui.state.context=uiContext('session-a');
  ui.get('camera').append({value:'camera:a'});
  ui.get('history').value='plan:a';
  const old=ui.loadSavedPlan().catch(e=>e.message);
  ui.get('history').value='plan:b';
  const current=ui.loadSavedPlan();
  pending.get('plan:b')(jsonReply(savedPlan('plan:b')));
  await current;
  pending.get('plan:a')(jsonReply(savedPlan('plan:a')));
  assert.equal(await old,'SESSION_CHANGED');
  assert.equal(ui.state.plan.plan_ref,'plan:b');
  assert.equal(ui.get('camera').value,'camera:a');
  assert.equal(ui.get('start').value,0);assert.equal(ui.get('end').value,6);
  assert.equal(JSON.parse(ui.get('planRaw').textContent).plan_ref,'plan:b');
  assert.equal(ui.state.case,null);assert.equal(calls.some(path=>path.endsWith('/execute')),false);
});

test('actual UI rejects late HTML export after INPUT session switch and clears history', async () => {
  let resolveExport;
  const ui=controlRoom(path=>{
    if(path.endsWith('/export-report')) return new Promise(resolve=>{resolveExport=resolve;});
    if(path.endsWith('/list_cameras')) return Promise.resolve(jsonReply({items:[]}));
    throw Error('unexpected request '+path);
  });
  ui.state.contexts=[uiContext('session-a'),uiContext('session-input','INPUT')];
  ui.state.context=ui.state.contexts[0];ui.state.report={report_ref:'report:a'};
  ui.state.history=[{plan_ref:'plan:a'}];ui.get('planRaw').textContent='old result';
  ui.get('eventCount').textContent='10筆 · 保留全部回傳事件';
  const download=ui.exportReport().catch(e=>e.message);
  await ui.loadContext(1);
  resolveExport({ok:true,status:200,text:async()=>'<html>old RESULTS report</html>'});
  assert.equal(await download,'SESSION_CHANGED');
  assert.equal(ui.downloads.length,0);assert.equal(ui.state.report,null);
  assert.equal(ui.state.history.length,0);assert.equal(ui.get('planRaw').textContent,'');
  assert.equal(ui.get('eventCount').textContent,'尚未查詢');
  assert.equal(ui.get('exportReport').disabled,true);assert.equal(ui.get('reloadHistory').disabled,true);
  assert.equal(ui.get('scene').children[0].textContent.includes('INPUT stage'),true);
  assert.equal(ui.state.logs.length,1); // Only the new scope's allowlisted camera read.
});

const savedCase=ref=>({plan_ref:ref,case_ref:'case:a',revision:3,state:'COMPLETED',receipts:[],pending_steps:[],subjects:[],conflicts:[],
  evidence:[{kind:'EVENT',record_ref:'event:a'},{kind:'OBSERVATION',record_ref:'observation:a'},
    {kind:'EVENT',record_ref:'event:b'},{kind:'EVENT',record_ref:'event:a'}]});
const eventDetail=ref=>({event_ref:ref,kind:'INFERRED_GAP_ALTERNATIVES',camera_ids:['A','B'],time_range:[1,2],
  evidence_state:'INFERRED_GAP',termination_reason:'EXHAUSTIVE',complete:true,
  candidates:[{candidate_id:'first',polyline:[[0,0,0],[1,0,0]]},
    {candidate_id:'second',polyline:[[0,0,0],[0,1,0],[1,0,0]]}],trajectories:[]});

test('opening saved case restores every event card and route without execute or inference', async () => {
  const calls=[],routes=[],canonical=savedCase('plan:a'),original=JSON.stringify(canonical);
  const ui=controlRoom((path,options)=>{
    const payload=JSON.parse(options.body);calls.push([path,payload]);
    if(path.endsWith('/plan')) return Promise.resolve(jsonReply(savedPlan('plan:a')));
    if(path.endsWith('/query_observations')) return Promise.resolve(jsonReply({items:[]}));
    if(path.endsWith('/case')) return Promise.resolve(jsonReply(canonical));
    if(path.endsWith('/get_event_detail')) return Promise.resolve(jsonReply(eventDetail(payload.event_ref)));
    throw Error('unexpected mutating request '+path);
  });
  ui.state.context={...uiContext('session-a'),allowed_tools:['query_observations','get_event_detail']};
  ui.state.scene={showRoutes:details=>routes.push(details),showMarkers(){}};
  ui.get('camera').append({value:'camera:a'});ui.get('history').value='plan:a';
  await ui.loadSavedPlan();
  assert.deepEqual([...ui.state.activeEventRefs],['event:a','event:b']);
  assert.deepEqual(Array.from(ui.state.events,row=>row.event_ref),['event:a','event:b']);
  assert.equal(ui.get('events').children.length,2);assert.equal(ui.get('eventCount').textContent.startsWith('2筆'),true);
  assert.deepEqual(Array.from(routes.at(-1)).flatMap(detail=>detail.candidates.map(c=>c.candidate_id)),['first','second','first','second']);
  assert.deepEqual(calls.filter(([path])=>path.endsWith('/get_event_detail')).map(([,payload])=>payload.event_ref),['event:a','event:b']);
  assert.equal(calls.every(([,payload])=>payload.session_ref==='session-a'),true);
  assert.equal(calls.some(([path])=>path.endsWith('/execute')||path.includes('inference')),false);
  assert.equal(JSON.stringify(canonical),original);
});

test('saved case keeps missing event evidence explicit without inventing a route', async () => {
  const ui=controlRoom((path,options)=>{
    const payload=JSON.parse(options.body);
    if(path.endsWith('/plan')) return Promise.resolve(jsonReply(savedPlan('plan:a')));
    if(path.endsWith('/query_observations')) return Promise.resolve(jsonReply({items:[]}));
    if(path.endsWith('/case')) return Promise.resolve(jsonReply(savedCase('plan:a')));
    if(path.endsWith('/get_event_detail')) return Promise.resolve(payload.event_ref==='event:a'?
      jsonReply(eventDetail('event:a')):jsonReply({error:'REFERENCE_DENIED'},403));
    throw Error('unexpected request '+path);
  });
  ui.state.context={...uiContext('session-a'),allowed_tools:['query_observations','get_event_detail']};
  ui.get('camera').append({value:'camera:a'});ui.get('history').value='plan:a';
  await ui.loadSavedPlan();
  assert.deepEqual([...ui.state.activeEventRefs],['event:a','event:b']);
  assert.deepEqual(Array.from(ui.state.events,row=>row.event_ref),['event:a']);
  assert.equal(ui.get('eventCount').textContent,'1筆已取得 · 1份細節缺失');
  assert.equal(ui.get('events').children.at(-1).children[0].textContent.includes('不補造路線'),true);
  assert.equal(ui.state.case.evidence.filter(row=>row.record_ref==='event:b').length,1);
});

test('late saved-case detail cannot restore old cards or routes after choosing another plan', async () => {
  let resolveDetail,enteredDetail;
  const requested=new Promise(resolve=>{enteredDetail=resolve;});
  const routes=[];
  const ui=controlRoom((path,options)=>{
    const payload=JSON.parse(options.body);
    if(path.endsWith('/plan')) return Promise.resolve(jsonReply(savedPlan(payload.plan_ref)));
    if(path.endsWith('/query_observations')) return Promise.resolve(jsonReply({items:[]}));
    if(path.endsWith('/case')) return Promise.resolve(payload.plan_ref==='plan:a'?
      jsonReply(savedCase('plan:a')):jsonReply({error:'CASE_UNAVAILABLE'},403));
    if(path.endsWith('/get_event_detail')) {enteredDetail();return new Promise(resolve=>{resolveDetail=resolve;});}
    throw Error('unexpected request '+path);
  });
  ui.state.context={...uiContext('session-a'),allowed_tools:['query_observations','get_event_detail']};
  ui.state.scene={showRoutes:details=>routes.push(details),showMarkers(){}};
  ui.get('camera').append({value:'camera:a'});ui.get('history').value='plan:a';
  const old=ui.loadSavedPlan().catch(cause=>cause.message);await requested;
  ui.get('history').value='plan:b';await ui.loadSavedPlan();
  resolveDetail(jsonReply(eventDetail('event:a')));
  assert.equal(await old,'SESSION_CHANGED');
  assert.equal(ui.state.plan.plan_ref,'plan:b');assert.equal(ui.state.case,null);
  assert.equal(ui.state.events.length,0);assert.equal(ui.state.activeEventRefs.size,0);
  assert.equal(ui.state.details.size,0);assert.equal(routes.at(-1).length,0);
  assert.equal(ui.get('eventCount').textContent,'尚未查詢');
});
