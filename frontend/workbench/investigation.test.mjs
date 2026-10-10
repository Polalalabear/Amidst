import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {SoftSyncClock,observeVideo} from '../product/timeline.mjs';

const deferred=()=>{let resolve;const promise=new Promise(done=>{resolve=done;});return {promise,resolve};};
const clone=value=>JSON.parse(JSON.stringify(value));
const binding={session_ref:'session-original',freeze_ref:'freeze-original',observation_mode:'photos_only'};
const plan=(ref='plan:a',max=8)=>({plan_ref:ref,task:'MULTI_TARGET',camera_ref:'camera:a',
  time_range:[0,4],seed_refs:['observation:b','observation:a'],policy:{max_tool_calls:max,max_cameras:4,max_hops:3},binding});
const caseData=(ref='plan:a',count=0,state='PAUSED',revision=count)=>({plan_ref:ref,case_ref:'case:'+ref,
  binding,revision,state,receipts:Array.from({length:count},(_,i)=>({receipt_ref:'receipt:'+i})),
  pending_steps:state==='COMPLETED'?[]:[{step_ref:'next'}],subjects:[],evidence:[],
  workflow_complete:state==='COMPLETED',retrieval_complete:true,graph_complete:null});
const observation=ref=>({observation_ref:ref,local_track_ref:'track:'+ref,camera_ids:['CAM_A'],
  time_range:[0,4],measurements:[{timestamp:0}],projected_path:[[1,2,0]]});
const context=()=>({observation_mode:'photos_only',product_context:{session_ref:binding.session_ref,
  product_freeze_ref:binding.freeze_ref,run_ref:'run:original'},available_modes:['photos_only','photos_plus_observations'],
  cameras:[{camera_ref:'camera:a',camera_id:'CAM_A'}],source:{time_range:[0,4],source_rgb_rate_hz:2.5,model_id:'lab'}});
const timeline=timestamp=>({run_ref:'run:original',timestamp,presentation_only:true,
  frames:[{camera_id:'CAM_A',status:'AVAILABLE',frame_timestamp:0,offset_seconds:-timestamp}],
  markers:[{marker_ref:'actual',event_ref:'event:a',timestamp:0,world_position:[1,2,0],
    evidence_state:'PROJECTED',interpolated:false,source_frame_ref:'media:actual',sample_offset_seconds:-timestamp},
    ...[1,2,3].map(i=>({marker_ref:'alternative:'+i,event_ref:'event:a',timestamp,
      world_position:[i,0,0],evidence_state:'INFERRED_GAP',candidate_ref:'candidate:'+i,hypothesis_ref:'hypothesis:'+i}))]});
const detail=ref=>({event_ref:ref,uncertainty:'unresolved',candidates:[{candidate_id:'second'},{candidate_id:'first'}],
  trajectories:[],media_refs:['media:a'],projected_path:[]});
const report=()=>({report_ref:'report:a',report_sha256:'a'.repeat(64),plan_ref:'plan:a',binding,
  identity_status:'UNRESOLVED_PROVISIONAL',explanation:'all alternatives retained',subjects:[],conflicts:[],
  all_alternative_refs:['alternative:b','alternative:a'],state:'PAUSED'});

function panel(transport=async()=>undefined){
  const nodes=new Map(),calls=[],scenes=[];
  class Element{
    constructor(name){this.name=name;this._html='';this.textContent='';this.value='';this.disabled=false;
      this.isConnected=true;this.children=[];this.dataset={};}
    get innerHTML(){return this._html;}
    set innerHTML(value){this._html=value;this.textContent='';}
    replaceChildren(...children){this._html='';this.textContent='';this.children=children;}
    append(...children){this.children.push(...children);}
  }
  const get=selector=>{if(!nodes.has(selector))nodes.set(selector,new Element(selector));return nodes.get(selector);};
  const container=new Element('container');
  container.querySelector=get;
  container.querySelectorAll=selector=>{
    if(selector==='[data-seed]:checked')return [...get('[data-seeds]').innerHTML.matchAll(/data-seed[^>]*value="([^"]+)"([^>]*)>/g)]
      .filter(match=>match[2].includes('checked')).map(match=>({value:match[1]}));
    if(selector==='[data-case-event]')return [...get('[data-events]').innerHTML.matchAll(/data-case-event="([^"]+)"/g)]
      .map(match=>{const node=get('button:'+match[1]);node.dataset.caseEvent=match[1];return node;});
    return [];
  };
  class Scene{
    constructor(_container,options){this.options=options;this.markers=[];this.disposed=false;scenes.push(this);}
    setMarkers(markers,timestamp){this.markers=markers;this.timestamp=timestamp;}
    getPose(){return null;}
    dispose(){this.disposed=true;}
  }
  const source=readFileSync(new URL('./investigation.mjs',import.meta.url),'utf8')
    .replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
  const environment={SceneView:Scene,SoftSyncClock,observeVideo,setTimeout,WeakMap,Map,Set,
    document:{createElement:tag=>new Element(tag)}};
  runInNewContext(source+'\nglobalThis.Panel=InvestigationPanel;globalThis.retrieval=retrievalText;',environment);
  const ui=Object.create(environment.Panel.prototype);
  Object.assign(ui,{container,closed:false,serial:1,workflowSerial:1,eventSerial:0,sequence:{},
    snapshot:{objects:[]},context:context(),videos:[],cleanup:[],details:new Map(),activeEventRefs:new Set(),
    timelineBindings:new WeakMap(),observations:[],events:[],plan:null,case:null,report:null,lastTimeline:null,
    executionPromise:null,stopRequested:false,mediaURL:ref=>'/opaque/'+ref,videoURL:ref=>'/video/'+ref,
    exportReport:async()=>{},call:async(action,payload)=>{
      calls.push({action,payload:clone(payload)});const value=await transport(action,payload);
      if(value!==undefined)return value;
      if(action==='cases')return {items:[],truncated:false};
      if(action==='timeline')return timeline(payload.timestamp);
      if(action==='videos')return {items:[]};
      if(action==='tool'&&payload.tool==='query_observations')return {
        items:[observation('observation:a'),observation('observation:b')],
        retrieval:{query_complete:true,truncated:false,graph_complete:null}};
      throw Error('UNEXPECTED_REQUEST');
    }});
  get('[data-product-camera]').value='camera:a';get('[data-product-start]').value=0;
  get('[data-product-end]').value=4;get('[data-video-seek]').value=0;get('[data-task]').value='TRACE';
  ui.makeScene();return {ui,get,calls,scenes,retrieval:environment.retrieval};
}

test('unsupported new intent clears old plan/actions/report before the compiler replies',async()=>{
  const pending=deferred(),{ui,get}=panel(action=>action==='intent'?pending.promise:undefined);
  ui.plan=plan();ui.case=caseData();ui.report=report();ui.details.set('event:old',detail('event:old'));
  get('[data-report-output]').innerHTML='OLD REPORT';get('[data-intent]').value='unsupported arbitrary text';
  const compiling=ui.compile();
  assert.equal(ui.plan,null);assert.equal(ui.case,null);assert.equal(ui.report,null);
  assert.equal(get('[data-execute]').disabled,true);assert.equal(get('[data-report-output]').innerHTML,'');
  assert.equal(ui.details.size,0);
  pending.resolve({status:'NEEDS_INPUT',plan:null,missing_fields:['SUPPORTED_TASK_TEMPLATE_REQUIRED']});
  await compiling;assert.equal(ui.plan,null);assert.equal(get('[data-execute-all]').disabled,true);
});

test('late compiler cannot replace a newer immutable plan',async()=>{
  const old=deferred(),current=deferred();let count=0;
  const {ui}=panel(action=>action==='intent'?(++count===1?old.promise:current.promise):undefined);
  const first=ui.compile().catch(error=>error.message),second=ui.compile();
  current.resolve({status:'READY',plan:plan('plan:new')});await second;
  old.resolve({status:'READY',plan:plan('plan:old')});
  assert.equal(await first,'SESSION_CHANGED');assert.equal(ui.plan.plan_ref,'plan:new');
});

test('late or detached event detail cannot reinsert old route or media evidence',async()=>{
  const pending=deferred(),{ui,get}=panel((action,p)=>action==='tool'&&p.tool==='get_event_detail'?pending.promise:undefined);
  ui.activeEventRefs.add('event:old');const target=get('[data-event-detail="event:old"]');
  const loading=ui.detail('event:old',target).catch(error=>error.message);
  ui.resetWorkflow();pending.resolve(detail('event:old'));
  assert.equal(await loading,'SESSION_CHANGED');assert.equal(ui.details.size,0);assert.equal(target.innerHTML,'');
  ui.activeEventRefs.add('event:old');target.isConnected=false;
  await assert.rejects(ui.detail('event:old',target),/SESSION_CHANGED/);assert.equal(ui.details.size,0);
});

test('saved plan races restore only newest camera/time/task/seeds without execute',async()=>{
  const old=deferred(),current=deferred(),{ui,get,calls}=panel((action,p)=>{
    if(action==='plan')return p.plan_ref==='plan:old'?old.promise:current.promise;
    if(action==='case')throw Error('CASE_UNAVAILABLE');
  });
  ui.case=caseData();ui.report=report();get('[data-report-output]').innerHTML='OLD';
  get('[data-history]').value='plan:old';const first=ui.loadSaved().catch(error=>error.message);
  get('[data-history]').value='plan:new';const second=ui.loadSaved();
  current.resolve(plan('plan:new'));await second;old.resolve(plan('plan:old'));
  assert.equal(await first,'SESSION_CHANGED');assert.equal(ui.plan.plan_ref,'plan:new');
  assert.equal(ui.case,null);assert.equal(ui.report,null);assert.equal(get('[data-report-output]').innerHTML,'');
  assert.equal(get('[data-task]').value,'MULTI_TARGET');assert.deepEqual(Array.from(ui.seeds()).sort(),['observation:a','observation:b']);
  assert.equal(calls.some(c=>c.action==='execute'),false);
});

test('saved-case errors other than CASE_UNAVAILABLE propagate and do not restore old case',async()=>{
  const {ui,get}=panel(action=>{if(action==='plan')return plan();if(action==='case')throw Error('PRODUCT_BINDING_DENIED');});
  get('[data-history]').value='plan:a';ui.case=caseData('old');
  await assert.rejects(ui.loadSaved(),/PRODUCT_BINDING_DENIED/);assert.equal(ui.case,null);
});

test('localized errors use their fixed code and only absent case is handled as READY',async()=>{
  const missing=Object.assign(Error('此操作或資料不在目前角色範圍內。'),{code:'CASE_UNAVAILABLE'});
  const denied=Object.assign(Error('此操作或資料不在目前角色範圍內。'),{code:'STAGE_DENIED'});
  let failure=missing;
  const {ui,get}=panel(action=>{if(action==='plan')return plan();if(action==='case')throw failure;});
  get('[data-history]').value='plan:a';await ui.loadSaved();
  assert.equal(ui.case,null);assert.match(get('[data-case]').textContent,/尚未建立/);
  failure=denied;await assert.rejects(ui.loadSaved(),error=>error.code==='STAGE_DENIED');
});

test('saved case restores all event details/media/routes without inference and keeps missing references',async()=>{
  const canonical=caseData('plan:a',3,'COMPLETED');canonical.evidence=[
    {kind:'EVENT',record_ref:'event:a'},{kind:'EVENT',record_ref:'event:b'}];
  const {ui,get,calls}=panel((action,p)=>{
    if(action==='plan')return plan();
    if(action==='case')return canonical;
    if(action==='tool'&&p.tool==='get_event_detail'){
      if(p.params.event_ref==='event:b')throw Error('REFERENCE_DENIED');
      return detail('event:a');
    }
  });
  get('[data-history]').value='plan:a';await ui.loadSaved();
  assert.deepEqual([...ui.activeEventRefs],['event:a','event:b']);
  assert.deepEqual([...ui.details.keys()],['event:a']);
  assert.match(get('[data-event-detail="event:b"]').textContent,/不補造/);
  assert.equal(ui.scene.options.events[0].candidates[0].candidate_id,'second');
  assert.equal(calls.some(c=>c.action==='execute'),false);
});

test('next step automatically resumes PAUSED while retaining server receipts and terminal controls',async()=>{
  let count=0,current;
  const {ui,get,calls}=panel((action,p)=>{
    if(action!=='execute')return;
    if(current?.state==='PAUSED'&&!p.resume)return current;
    count+=p.max_new_calls;current=caseData('plan:a',count,count===2?'COMPLETED':'PAUSED');return current;
  });
  ui.plan=plan();await ui.execute({max_new_calls:1});await ui.execute({max_new_calls:1});
  const executions=calls.filter(c=>c.action==='execute');
  assert.deepEqual(executions.map(c=>c.payload.max_new_calls),[1,1]);
  assert.equal(executions[1].payload.resume,true);assert.equal(ui.case.receipts.length,2);
  assert.equal(get('[data-execute]').disabled,true);assert.equal(get('[data-stop]').disabled,true);
});

test('run-to-stop uses finite six-call batches and actual remaining policy budget',async()=>{
  let count=0;
  const {ui,get,calls}=panel((action,p)=>{
    if(action!=='execute')return;
    count+=p.max_new_calls;return caseData('plan:a',count,count===8?'BUDGET_EXHAUSTED':'PAUSED');
  });
  ui.plan=plan();ui.report=report();get('[data-report-output]').innerHTML='old';
  await ui.execute({all:true});
  assert.deepEqual(calls.filter(c=>c.action==='execute').map(c=>c.payload.max_new_calls),[6,2]);
  assert.equal(ui.case.state,'BUDGET_EXHAUSTED');assert.equal(ui.report,null);
  assert.equal(get('[data-report-output]').innerHTML,'');assert.equal(get('[data-resume]').disabled,true);
});

test('stop during an in-flight batch sends STOP only after it and schedules no further tool batch',async()=>{
  const pending=deferred(),{ui,calls,get}=panel((action,p)=>{
    if(action==='execute')return p.stop?caseData('plan:a',6,'STOPPED',7):pending.promise;
  });
  ui.plan=plan('plan:a',32);const running=ui.execute({all:true}),stopping=ui.stop();
  await assert.rejects(ui.execute({max_new_calls:1}),/正在執行/);
  pending.resolve(caseData('plan:a',6,'PAUSED'));await Promise.all([running,stopping]);
  const executed=calls.filter(c=>c.action==='execute');
  assert.equal(executed.length,2);assert.equal(executed[0].payload.max_new_calls,6);
  assert.equal(executed[1].payload.stop,true);assert.equal(ui.case.state,'STOPPED');
  assert.equal(get('[data-resume]').disabled,false);
});

test('late execute and report cannot overwrite a newer workflow',async()=>{
  const pending=deferred(),{ui}=panel(action=>action==='execute'?pending.promise:undefined);
  ui.plan=plan();const running=ui.execute().catch(error=>error.message);
  ui.resetWorkflow();ui.plan=plan('plan:new');pending.resolve(caseData('plan:a',1));
  assert.equal(await running,'SESSION_CHANGED');assert.equal(ui.plan.plan_ref,'plan:new');assert.equal(ui.case,null);
  const reportPending=deferred();ui.case=caseData('plan:new');
  ui.call=action=>action==='report'?reportPending.promise:Promise.resolve({items:[]});
  const reporting=ui.loadReport().catch(error=>error.message);ui.resetWorkflow();
  reportPending.resolve({...report(),plan_ref:'plan:new'});
  assert.equal(await reporting,'SESSION_CHANGED');assert.equal(ui.report,null);
});

test('unmaterialized video keeps source-only seek and exact server marker provenance with N/A metrics',async()=>{
  const {ui,get,calls}=panel();ui.activeEventRefs.add('event:a');
  await ui.loadVideos();await ui.seek(.2);
  assert.equal(get('[data-video-play]').disabled,true);assert.match(get('[data-video-telemetry]').textContent,/N\/A/);
  assert.equal(ui.scene.markers[0].timestamp,0);assert.equal(ui.scene.markers[0].source_frame_ref,'media:actual');
  assert.deepEqual(ui.scene.markers[0].world_position,[1,2,0]);assert.equal(ui.scene.markers[0].interpolated,false);
  assert.equal(ui.scene.markers.length,4);assert.match(get('[data-frame-status]').textContent,/offset=-0.2/);
  assert.equal(ui.scene.options.observations.length,0);
  assert.ok(calls.filter(c=>c.action==='timeline').every(c=>c.payload.event_refs[0]==='event:a'));
});

test('stale seeks and a state resolved before a plan switch cannot repaint or invent positions',async()=>{
  const old=deferred(),current=deferred();let count=0;
  const {ui}=panel(action=>action==='timeline'?(++count===1?old.promise:current.promise):undefined);
  const first=ui.seek(.1).catch(error=>error.message),second=ui.seek(.2);
  current.resolve(timeline(.2));await second;old.resolve(timeline(.1));
  assert.equal(await first,'SESSION_CHANGED');assert.equal(ui.scene.timestamp,.2);
  ui.call=async()=>timeline(.3);
  const state=await ui.timelineRequest(.3);ui.resetWorkflow();
  assert.throws(()=>ui.applyTimeline(state),/SESSION_CHANGED/);
});

test('wrong run timeline is refused before reaching the scene',async()=>{
  const {ui}=panel(action=>action==='timeline'?{...timeline(.2),run_ref:'run:other'}:undefined);
  await assert.rejects(ui.seek(.2),/TIMELINE_BINDING_DENIED/);assert.equal(ui.scene.markers.length,0);
});

test('all three review actions use fixed reasons and original report hash without caller identity',async()=>{
  const original=report(),saved=JSON.stringify(original),{ui,get,calls}=panel(action=>action==='review'?{review_ref:'review:a'}:undefined);
  ui.report=original;get('[data-review-alternative]').value='alternative:a';
  for(const action of ['PRESERVE_AMBIGUITY','REQUEST_EVIDENCE','SELECT_PRESENTATION'])await ui.review(action);
  const reviews=calls.filter(c=>c.action==='review').map(c=>c.payload.review);
  assert.deepEqual(reviews.map(r=>r.reason_code),['AMBIGUOUS_EVIDENCE','MISSING_EVIDENCE','DISPLAY_PREFERENCE']);
  assert.equal(reviews[2].alternative_ref,'alternative:a');assert.ok(reviews.every(r=>r.report_sha256===original.report_sha256&&!('operator_ref' in r)));
  assert.equal(JSON.stringify(original),saved);
  get('[data-review-alternative]').value='alternative:other';await assert.rejects(ui.review('SELECT_PRESENTATION'),/REFERENCE_DENIED/);
});

test('late HTML export receives a live guard and cannot download after workflow replacement',async()=>{
  const pending=deferred(),downloads=[],{ui}=panel();ui.report=report();
  ui.exportReport=async(ref,current)=>{await pending.promise;if(!current())throw Error('SESSION_CHANGED');downloads.push(ref);};
  const exporting=ui.downloadReport().catch(error=>error.message);ui.resetWorkflow();pending.resolve();
  assert.equal(await exporting,'SESSION_CHANGED');assert.deepEqual(downloads,[]);
});

test('retrieval receipt preserves truncation separately from graph completeness and query order',async()=>{
  const items=[{event_ref:'event:b',kind:'GAP',time_range:[0,4],candidate_count:2,hypothesis_count:3},
    {event_ref:'event:a',kind:'HOLD',time_range:[0,4],candidate_count:0,hypothesis_count:0}];
  const {ui,get,retrieval}=panel((action,p)=>action==='tool'&&p.tool==='query_events'?
    {items,retrieval:{query_complete:false,truncated:true,graph_complete:null}}:undefined);
  await ui.queryEvents();
  assert.deepEqual([...ui.activeEventRefs],['event:b','event:a']);
  assert.match(get('[data-event-retrieval]').textContent,/截斷/);assert.match(get('[data-event-retrieval]').textContent,/N\/A/);
  assert.match(retrieval({query_complete:true,truncated:false,graph_complete:false}),/graph_complete=false/);
});

test('actual PageInfo is described as a scoped completed page only with its explicit receipt',()=>{
  const {retrieval}=panel();
  const info={records_read:2,index_entries_touched:2,frames_read:0,bytes_read:0,
    coverage:'EXACT_REGISTERED_BUCKET_WITHIN_WINDOW',time_range:[0,4],truncated:false,
    graph_complete:null,next_cursor:null,record_set_receipt_sha256:'a'.repeat(64)};
  assert.match(retrieval(info),/此註冊 bucket／時間窗無下一頁/);
  assert.match(retrieval(info),/graph_complete=N\/A/);
  assert.match(retrieval({...info,next_cursor:'cursor:next'}),/未確認/);
  assert.match(retrieval({truncated:false,graph_complete:null}),/未確認/);
});

test('standalone stop holds execution controls until its persisted case returns',async()=>{
  const pending=deferred(),{ui,get,calls}=panel(action=>action==='execute'?pending.promise:undefined);
  ui.plan=plan();ui.case=caseData('plan:a',1);
  const stopping=ui.stop();
  assert.equal(get('[data-execute]').disabled,true);
  await assert.rejects(ui.execute(),/正在執行/);
  pending.resolve(caseData('plan:a',1,'STOPPED',2));await stopping;
  assert.equal(calls.filter(c=>c.action==='execute').length,1);
  assert.equal(ui.case.state,'STOPPED');assert.equal(get('[data-resume]').disabled,false);
});

test('mode initialization immediately clears evidence/report and disposes previous media callbacks and scene',async()=>{
  const pending=deferred(),{ui,get}=panel(action=>action==='context'?pending.promise:undefined);
  let cleanup=0,paused=0,cleared=0,closed=0;
  const oldScene=ui.scene;
  ui.cleanup=[()=>cleanup++];ui.clock={close:()=>closed++};
  ui.videos=[{video:{pause:()=>paused++,removeAttribute:()=>cleared++,load(){}}}];
  ui.plan=plan();ui.case=caseData();ui.report=report();
  ui.details.set('event:old',detail('event:old'));ui.activeEventRefs.add('event:old');
  get('[data-report-output]').innerHTML='OLD PRIVATE VIEW';
  const changing=ui.initialize('photos_plus_observations');
  assert.equal(ui.plan,null);assert.equal(ui.case,null);assert.equal(ui.report,null);
  assert.equal(ui.details.size,0);assert.equal(ui.activeEventRefs.size,0);
  assert.equal(get('[data-report-output]').innerHTML,'');assert.equal(ui.videos.length,0);
  assert.equal(oldScene.disposed,true);assert.equal(cleanup,1);assert.equal(paused,1);
  assert.equal(cleared,1);assert.equal(closed,1);assert.match(ui.container.innerHTML,/原畫面已清除/);
  pending.resolve({...context(),observation_mode:'photos_plus_observations'});
  await changing;assert.equal(ui.context.observation_mode,'photos_plus_observations');
  assert.equal(get('[data-video-play]').disabled,true);
});
