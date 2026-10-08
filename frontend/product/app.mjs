import * as THREE from '/vendor/three.module.js';
import {SoftSyncClock, observeVideo} from './timeline.mjs';

const $ = id => document.getElementById(id);
const node = (tag, text, className) => {const item = document.createElement(tag);
  if (text !== undefined) item.textContent = text; if (className) item.className = className; return item;};
const state = {contexts: [], context: null, epoch: 0, observations: [], events: [], details: new Map(),
  plan: null, case: null, report: null, videos: new Map(), videoCleanup: [], clock: null, scene: null,
  logs: [], activeEventRefs: new Set(), seeking: false, operatorRef: null, pendingRequests: new Set(),
  workflowSerial: 0, historySerial: 0, caseRequestSerial: 0, reportSerial: 0, history: []};
const labels = {TRACE:'追查單一種子', COMPARE:'比較兩個種子', BEHAVIOR:'局部行為證據',
  MULTI_TARGET:'多目標歧義調查', ENTER_DOOR:'跨越門界進入', EXIT_DOOR:'跨越門界離開',
  TURN_CORNER:'可見轉角通過', DWELL:'局部停留', POSSIBLE_LOITERING:'可能的往返停留',
  LOST_NEAR_CORNER:'轉角附近失去可見證據', INFERRED_GAP_ALTERNATIVES:'不可見區段的路線假說',
  SAME_CAMERA_RECOVERY:'同鏡頭 recovery 待查', OVERLAPPING_VISIBILITY:'重疊可見關聯', UNMATCHED:'尚未關聯',
  READY:'計畫已保存', RUNNING:'執行中', PAUSED:'在步驟邊界暫停', STOPPED:'已保存停止狀態',
  COMPLETED:'有限工作流程完成', TOOL_FAILED:'工具／證據未取得', BUDGET_EXHAUSTED:'操作預算已用完',
  UNRESOLVED:'關聯仍有歧義', SEED_UNAVAILABLE:'種子證據未取得'};
const missingLabels = {EXPLICIT_CAMERA_REFERENCE_REQUIRED:'請指定鏡頭', EXPLICIT_TIME_RANGE_REQUIRED:'請指定時間窗',
  ONE_SEED_REFERENCE_REQUIRED:'追查須選一個種子', TWO_SEED_REFERENCES_REQUIRED:'比較須選兩個種子',
  BOUNDED_MULTIPLE_SEEDS_REQUIRED:'多目標須選至少兩個種子', SUPPORTED_TASK_TEMPLATE_REQUIRED:'請使用支援的意圖模板',
  FROZEN_RESULTS_STAGE_REQUIRED:'此調查須先完成同 run 的推論 freeze'};
const session = () => state.context?.session_ref;
const announce = (message, error = false) => {$('status').textContent = message;
  $('status').classList.toggle('error', error);};
const raw = (id, value) => {$(id).textContent = JSON.stringify(value, null, 2);};
const seconds = value => Number.isFinite(value) ? value.toFixed(2) : '—';
const completeLabel = value => value === null || value === undefined ? '未進行此項搜尋' : value ? '範圍內完整' : '仍有未列舉範圍';
const selectedSeeds = () => [...$('seeds').querySelectorAll('input:checked')].map(input => input.value);
const timeRange = () => {const start = Number($('start').value), end = Number($('end').value);
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end < start) throw Error('請填入有效時間範圍。');
  return [start, end];};
const cameraRef = () => {if (!$('camera').value) throw Error('尚未定位鏡頭。'); return $('camera').value;};
function error(error) {if (error.message === 'SESSION_CHANGED') return; announce(error.message || '本機操作未完成。', true);}

async function post(path, params = {}, responseFormat = 'json') {
  const epoch = state.epoch, ref = session();
  if (!ref) throw Error('尚未定位資料來源。');
  const controller = new AbortController(); state.pendingRequests.add(controller);
  let response, result;
  try {
    response = await fetch(path, {method: 'POST', signal: controller.signal,
      headers: {'Content-Type':'application/json'}, body: JSON.stringify({session_ref: ref, ...params})});
    result = response.ok && responseFormat === 'text' ? await response.text() : await response.json();
  } catch (cause) {
    if (cause.name === 'AbortError' || epoch !== state.epoch) throw Error('SESSION_CHANGED');
    throw cause;
  } finally {state.pendingRequests.delete(controller);}
  if (epoch !== state.epoch || ref !== session()) throw Error('SESSION_CHANGED');
  state.logs.push({action: path.split('/').at(-1), status: response.status}); raw('logs', state.logs);
  if (!response.ok) throw Error(result.error || 'REQUEST_UNAVAILABLE');
  return result;
}
function tool(name, params = {}) {
  if (!state.context?.allowed_tools.includes(name)) return Promise.reject(Error('TOOL_NOT_ALLOWED_IN_THIS_STAGE'));
  return post('/product/v1/tools/' + name, params);
}
const mediaURL = ref => '/product/v1/media/' + encodeURIComponent(ref) + '?session_ref=' + encodeURIComponent(session());

class ControlScene {
  constructor(container) {
    this.container = container; this.scene = new THREE.Scene(); this.scene.background = new THREE.Color('#edf3f7');
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.1, 250); this.camera.up.set(0,0,1);
    this.target = new THREE.Vector3(8,4,0); this.theta = -1.0; this.phi = 0.75; this.distance = 27;
    this.renderer = new THREE.WebGLRenderer({antialias:true, alpha:false}); this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.replaceChildren(this.renderer.domElement);
    this.static = new THREE.Group(); this.routes = new THREE.Group(); this.markers = new THREE.Group();
    this.scene.add(this.static, this.routes, this.markers);
    this.scene.add(new THREE.AmbientLight(0xffffff, 2));
    const light = new THREE.DirectionalLight(0xffffff, 2); light.position.set(4,-4,20); this.scene.add(light);
    this.resizeObserver = new ResizeObserver(() => this.resize()); this.resizeObserver.observe(container);
    let dragging = null;
    this.down = event => {dragging = [event.clientX,event.clientY]; container.setPointerCapture(event.pointerId);};
    this.move = event => {if (!dragging) return; this.theta -= (event.clientX - dragging[0]) * .007;
      this.phi = Math.max(.12,Math.min(1.45,this.phi+(event.clientY-dragging[1])*.006));
      dragging=[event.clientX,event.clientY]; this.render();};
    this.up = () => {dragging=null;};
    this.wheel = event => {event.preventDefault(); this.distance=Math.max(8,Math.min(70,this.distance+event.deltaY*.02)); this.render();};
    container.addEventListener('pointerdown',this.down); container.addEventListener('pointermove',this.move);
    container.addEventListener('pointerup',this.up); container.addEventListener('wheel',this.wheel,{passive:false}); this.resize();
  }
  resize() {const width=this.container.clientWidth || 480,height=this.container.clientHeight || 320;
    this.renderer.setSize(width,height,false); this.camera.aspect=width/height; this.camera.updateProjectionMatrix(); this.render();}
  disposeGroup(group) {for (const child of [...group.children]) {child.geometry?.dispose();
    if (Array.isArray(child.material)) child.material.forEach(m=>m.dispose()); else child.material?.dispose(); group.remove(child);}}
  configure(config) {this.disposeGroup(this.static);
    const palette=['#9db7d4','#bbcedc','#cadbcf','#d5c9af'];
    for (const [index,region] of (config.regions || []).entries()) {
      const [x0,y0,x1,y1]=region.bounds_xy_m;
      const plane=new THREE.Mesh(new THREE.PlaneGeometry(x1-x0,y1-y0),
        new THREE.MeshStandardMaterial({color:palette[index%palette.length],transparent:true,opacity:.52,side:THREE.DoubleSide}));
      plane.position.set((x0+x1)/2,(y0+y1)/2,region.floor_z_m || 0); this.static.add(plane);
      const edge=new THREE.LineSegments(new THREE.EdgesGeometry(plane.geometry),new THREE.LineBasicMaterial({color:'#829db4'}));
      edge.position.copy(plane.position); this.static.add(edge);
    }
    const grid=new THREE.GridHelper(24,24,'#a7bacb','#d2dce5'); grid.rotation.x=Math.PI/2; grid.position.set(8,4,-.02); this.static.add(grid);
    this.static.add(new THREE.AxesHelper(2)); this.render();
  }
  showRoutes(details) {this.disposeGroup(this.routes); const palette=[0xd69536,0x508fbc,0x8ba95d,0xb685b0];
    let index=0;
    for (const detail of details) for (const candidate of detail.candidates || []) {
      const geometry=new THREE.BufferGeometry().setFromPoints(candidate.polyline.map(p=>new THREE.Vector3(...p)));
      const line=new THREE.Line(geometry,new THREE.LineBasicMaterial({color:palette[index++%palette.length],transparent:true,opacity:.8}));
      this.routes.add(line);
    }
    this.render();
  }
  showMarkers(markers) {this.disposeGroup(this.markers);
    for (const marker of markers) {
      const mesh=new THREE.Mesh(new THREE.SphereGeometry(.13,12,8),
        new THREE.MeshStandardMaterial({color:marker.evidence_state==='PROJECTED'?0x3475c5:0xd69536}));
      mesh.position.set(...marker.world_position); this.markers.add(mesh);
    }
    this.render();
  }
  render() {const horizontal=this.distance*Math.cos(this.phi);
    this.camera.position.set(this.target.x+horizontal*Math.cos(this.theta),this.target.y+horizontal*Math.sin(this.theta),
      this.target.z+this.distance*Math.sin(this.phi)); this.camera.lookAt(this.target); this.renderer.render(this.scene,this.camera);}
  destroy() {this.resizeObserver.disconnect(); this.disposeGroup(this.static); this.disposeGroup(this.routes); this.disposeGroup(this.markers);
    this.renderer.dispose(); this.container.removeEventListener('pointerdown',this.down);
    this.container.removeEventListener('pointermove',this.move); this.container.removeEventListener('pointerup',this.up);
    this.container.removeEventListener('wheel',this.wheel);}
}

function telemetry(data) {
  const metric = value => value === null ? 'N/A' : value.toFixed(1) + ' ms';
  $('skewMetric').textContent=metric(data.media_to_3d_skew_ms.mean); $('p95Metric').textContent=metric(data.media_to_3d_skew_ms.p95);
  $('seekMetric').textContent=metric(data.seek_recovery_ms.mean); $('frameMetric').textContent=data.actual_frame_callbacks;
  raw('telemetryRaw',data);
}
function applyTimeline(data) {
  state.scene?.showMarkers(data.markers); const fragments=[];
  for (const frame of data.frames) {
    const item=node('span',frame.camera_id+' '+(frame.status==='AVAILABLE'?
      'RGB t='+seconds(frame.frame_timestamp)+' / Δ'+seconds(frame.offset_seconds)+'s':'來源影格缺失'));
    if (frame.status!=='AVAILABLE') item.className='missing'; fragments.push(item,node('span','　'));
  }
  $('frameStatus').replaceChildren(...fragments);
}
function pausePlayback() {for (const {video} of state.videos.values()) video.pause();}
function seekTo(timestamp) {
  if (!state.clock) return;
  pausePlayback(); state.clock.seek(timestamp);
  for (const {video,info} of state.videos.values()) {
    const time=Math.max(0,Math.min(info.end_time-info.start_time,timestamp-info.start_time));
    if (Number.isFinite(video.duration)) video.currentTime=Math.min(time,video.duration); else video.currentTime=time;
  }
  $('clockTime').textContent=seconds(timestamp)+' 秒 · 等待實際影格';
}
async function playPlayback() {
  const outcomes=await Promise.allSettled([...state.videos.values()].map(({video})=>video.play()));
  if (!outcomes.length || outcomes.every(r=>r.status==='rejected')) throw Error('影片尚未可播放。');
}
function setupVideos(items) {
  $('videos').replaceChildren(); $('masterCamera').replaceChildren(); state.videos.clear();
  const master=items.find(item=>item.camera_ref===$('camera').value)||items[0];
  if (!master) {$('videos').append(node('p','沒有已登錄影片。來源照片可另按需取得。','empty')); return;}
  state.clock=new SoftSyncClock({runRef:state.context.run_ref,masterCameraRef:master.camera_ref,
    requestState:timestamp=>post('/product/v1/view/timeline',{timestamp,event_refs:[...state.activeEventRefs]}),
    applyState:applyTimeline,onTelemetry:telemetry,onError:error,
    onTime:timestamp=>{$('seek').value=timestamp;$('clockTime').textContent=seconds(timestamp)+' 秒';}});
  for (const info of items) {
    const card=node('div',undefined,'video-card'),video=node('video'); video.muted=true; video.playsInline=true; video.preload='auto';
    const caption=node('div',undefined,'video-caption'),clockLabel=node('span','待解碼');
    caption.append(node('strong',info.camera_id),clockLabel); card.append(video,caption);
    video.src='/product/v1/video/'+encodeURIComponent(info.video_ref)+'?session_ref='+encodeURIComponent(session());
    video.addEventListener('error',()=>{clockLabel.textContent='影片來源缺失'; clockLabel.className='video-error';});
    const cleanup=observeVideo(video,info,state.clock,(timestamp)=>{clockLabel.textContent=seconds(timestamp)+'s';
      const isMaster=info.camera_ref===state.clock?.masterCameraRef; clockLabel.classList.toggle('master',isMaster);
      if (isMaster) for (const {video:slave,info:slaveInfo} of state.videos.values()) {
        if (slave!==video && !slave.paused && Math.abs((slave.currentTime+slaveInfo.start_time)-timestamp)>.25)
          slave.currentTime=Math.max(0,timestamp-slaveInfo.start_time);
      }});
    state.videoCleanup.push(cleanup); state.videos.set(info.camera_ref,{video,info}); $('videos').append(card);
    const option=node('option',info.camera_id); option.value=info.camera_ref; $('masterCamera').append(option);
  }
  $('masterCamera').value=master.camera_ref; const max=Math.max(...items.map(item=>item.end_time)); $('seek').max=max;
  $('play').disabled=false; raw('videoRaw',items);
}

const checkWorkflow = token => {if(token!==state.workflowSerial) throw Error('SESSION_CHANGED');};
async function loadSeeds({selectedRefs=null, token=state.workflowSerial}={}) {
  const response=await tool('query_observations',{camera_ref:cameraRef(),time_range:timeRange()});
  checkWorkflow(token);
  state.observations=response.items || []; $('seeds').replaceChildren();
  if (!state.observations.length) $('seeds').append(node('p','此範圍沒有量測片段；請保留缺失結果。','empty'));
  for (const [index,observation] of state.observations.entries()) {
    const label=node('label',undefined,'seed-item'),checkbox=node('input'); checkbox.type='checkbox'; checkbox.value=observation.observation_ref;
    checkbox.checked=selectedRefs===null ? index===0 : selectedRefs.includes(observation.observation_ref)||selectedRefs.includes(observation.local_track_ref);
    if(selectedRefs?.includes(observation.local_track_ref)) checkbox.value=observation.local_track_ref;
    const text=node('span'); text.append(node('strong','相機內人物片段 '+(index+1)),
      node('small',observation.camera_ids?.join(' / ')+' · '+observation.time_range.map(seconds).join('–')+'秒'),
      node('small',(observation.measurements?.length||0)+'筆像素量測 · 身分未確認'));
    label.append(checkbox,text); $('seeds').append(label);
  }
  for(const ref of selectedRefs || []) if(!state.observations.some(row=>row.observation_ref===ref||row.local_track_ref===ref)) {
    const label=node('label',undefined,'seed-item'),checkbox=node('input');checkbox.type='checkbox';checkbox.value=ref;checkbox.checked=true;checkbox.disabled=true;
    label.append(checkbox,node('span','保存計畫的種子不在目前鏡頭／時間窗回傳範圍；保留其 reference。'));$('seeds').append(label);}
  announce('已取得 '+state.observations.length+'個原始 local segments；選擇調查種子。');
}
function refreshRouteView() {state.scene?.showRoutes([...state.details.values()].filter(detail=>state.activeEventRefs.has(detail.event_ref)));}
async function detailFor(ref) {
  const token=state.workflowSerial;
  if (state.details.has(ref)) return state.details.get(ref);
  const detail=await tool('get_event_detail',{event_ref:ref}); checkWorkflow(token);state.details.set(ref,detail); return detail;
}
async function showEventDetail(summary, container) {
  const token=state.workflowSerial;
  const detail=await detailFor(summary.event_ref);checkWorkflow(token); container.replaceChildren();
  container.append(node('p',detail.uncertainty,'event-summary'));
  const alternatives=node('ol',undefined,'alternative-list');
  for (const [index,candidate] of (detail.candidates || []).entries()) {
    alternatives.append(node('li','路線 '+(index+1)+'：'+candidate.path_length.toFixed(2)+'公尺，最低移動時間 '+candidate.minimum_travel_time.toFixed(2)+'秒。'));
  }
  if (!detail.candidates?.length) alternatives.append(node('li','沒有可行路線／此事件未使用 Graph reconstruction。'));
  container.append(alternatives,node('p',(detail.trajectories?.length||0)+'個原始時間假說；候選順序維持 canonical。','hint'));
  const photos=node('div',undefined,'evidence-photos');
  for (const ref of detail.media_refs || []) {const image=node('img'); image.src=mediaURL(ref); image.loading='lazy'; image.alt='無 GT 標註的合成來源照片';
    image.addEventListener('error',()=>image.replaceWith(node('span','來源照片缺失','hint'))); photos.append(image);}
  container.append(photos); const refs=node('details',undefined,'raw'); refs.append(node('summary','來源與完整假說'),node('pre',JSON.stringify(detail,null,2))); container.append(refs);
  state.activeEventRefs.add(detail.event_ref); refreshRouteView();
}
function renderEvents(events) {
  $('events').replaceChildren(); $('eventCount').textContent=events.length+'筆 · 保留全部回傳事件';
  if (!events.length) {$('events').append(node('p','此查詢／case 沒有回傳事件；空結果不代表目標不曾存在。','empty')); return;}
  for (const event of events) {
    const card=node('article',undefined,'event-card'),top=node('div',undefined,'event-top'); top.append(node('h3',labels[event.kind]||event.kind));
    const visible=node('input'); visible.type='checkbox'; visible.checked=state.activeEventRefs.has(event.event_ref); visible.ariaLabel='在 3D 呈現此事件'; top.append(visible); card.append(top);
    card.append(node('p',event.camera_ids.join(' → ')+' · '+event.time_range.map(seconds).join('–')+'秒','event-meta'));
    card.append(node('p',(event.evidence_state==='PROJECTED'?'來源像素的區域證據':'不可見期間的推論替代假說')+
      '。搜尋狀態：'+(event.termination_reason||'未使用 Graph')+'；'+completeLabel(event.complete)+'。','event-summary'));
    const tags=node('div',undefined,'tags'); for (const text of event.region_ids || []) tags.append(node('span',text,'tag'));
    if (event.association_states?.some(row=>row.status==='HOLD')) tags.append(node('span','關聯待查','tag warning'));
    if (event.alternatives?.length) tags.append(node('span',event.alternatives.length+'個替代 references','tag'));
    card.append(tags); const button=node('button','查看必要照片與全部路線'),container=node('div');
    button.addEventListener('click',()=>showEventDetail(event,container).then(()=>{visible.checked=true;}).catch(error));
    visible.addEventListener('change',async()=>{const token=state.workflowSerial;try {if(visible.checked) {await detailFor(event.event_ref);checkWorkflow(token); state.activeEventRefs.add(event.event_ref);}
      else state.activeEventRefs.delete(event.event_ref); refreshRouteView();}catch(e){error(e);}});
    card.append(button,container); $('events').append(card);
  }
}
async function queryEvents() {
  const token=state.workflowSerial;
  const response=await tool('query_events',{camera_ref:cameraRef(),time_range:timeRange()});
  checkWorkflow(token);
  state.events=response.items||[]; renderEvents(state.events);
  announce('讀取 '+(response.retrieval?.records_read??state.events.length)+'筆 canonical records。'+
    (response.retrieval?.truncated?'查找範圍有截斷，請縮小時間窗。':'保留全部回傳結果。'));
}
async function appearance() {
  const token=state.workflowSerial;
  const selected=selectedSeeds(); const observation=state.observations.find(row=>row.observation_ref===selected[0]||row.local_track_ref===selected[0]);
  if (!observation) throw Error('請先選一個已取得的種子。');
  const result=await tool('search_person_appearance',{camera_ref:cameraRef(),time_range:timeRange(),query_track_ref:observation.local_track_ref,top_k:6});
  checkWorkflow(token);
  const box=node('div',undefined,'appearance-box'); box.append(node('h3','外觀近似的 local tracks'),
    node('p','特徵相似度未校準，不能解讀為同一人物機率。搜尋 complete='+result.complete+'。','hint'));
  const hits=node('div',undefined,'appearance-hits');
  for (const hit of result.hits || []) {
    const card=node('div',undefined,'appearance-hit'); card.append(node('strong',hit.camera_id),
      node('p',hit.time_range.map(seconds).join('–')+'秒'),node('p','特徵相似度 '+hit.similarity.toFixed(3)+' · '+hit.status));
    for (const ref of (hit.representative_media_refs||[]).slice(0,1)) {const image=node('img');image.src=mediaURL(ref); image.alt='外觀候選來源照片'; card.append(image);}
    const refs=node('details',undefined,'raw');refs.append(node('summary','特徵來源'),node('pre',JSON.stringify(hit,null,2)));card.append(refs);hits.append(card);
  }
  if (!result.hits?.length) hits.append(node('p','沒有可用的外觀候選；不補造量測。','empty'));
  box.append(hits); $('appearanceResults').replaceChildren(box);
}

function resetInvestigation() {
  state.caseRequestSerial++;state.reportSerial++;
  pausePlayback();state.clock?.seek(Number($('seek').value));state.scene?.showMarkers([]);
  state.plan=null;state.case=null;state.report=null;state.details.clear();state.activeEventRefs.clear();refreshRouteView();
  state.events=[];
  for(const id of ['events','subjects','conflicts','reportSummary','appearanceResults']) $(id).replaceChildren();
  for(const id of ['planRaw','caseRaw','reportRaw']) $(id).textContent='';
  $('eventCount').textContent='尚未查詢';$('caseSummary').textContent='調查計畫尚未執行。';$('reviewResult').textContent='';
  $('reviewAlternative').replaceChildren();$('reviewPanel').hidden=true;
  for(const id of ['execute','pause','resume','reportButton','exportReport']) $(id).disabled=true;
}
function presentPlan(plan) {
  state.plan=plan;raw('planRaw',plan);
  $('planSummary').replaceChildren(node('strong',labels[plan.task]),
    node('p',plan.seed_refs.length+'個 scoped 種子；最多 '+plan.policy.max_tool_calls+'次工具調用、'+plan.policy.max_cameras+'個局部鏡頭。'));
  $('execute').disabled=false;$('pause').disabled=false;$('resume').disabled=true;
}
async function refreshHistory() {
  const serial=++state.historySerial;
  const result=await post('/product/v1/cases');
  if(serial!==state.historySerial) return;
  state.history=result.items||[];$('history').replaceChildren(node('option','選擇此 session 保存的計畫'));
  $('history').firstChild.value='';
  for(const [index,item] of state.history.entries()) {const option=node('option',
    '調查 '+(index+1)+' · '+(labels[item.task]||item.task)+' · '+(labels[item.state]||item.state));
    option.value=item.plan_ref;$('history').append(option);}
  if(state.plan&&state.history.some(item=>item.plan_ref===state.plan.plan_ref)) $('history').value=state.plan.plan_ref;
  $('history').disabled=!state.history.length;$('loadPlan').disabled=!$('history').value;
  $('historyStatus').textContent=state.history.length+'份保存計畫'+(result.truncated?'；清單只回傳最新 100 份。':'；此 session 清單完整。')+
    '開啟只讀取原計畫與 case。';
}
async function loadSavedPlan() {
  const ref=$('history').value;if(!ref) throw Error('請選擇保存計畫。');
  const token=++state.workflowSerial;resetInvestigation();$('planSummary').textContent='正在取得保存計畫…';
  const plan=await post('/product/v1/plan',{plan_ref:ref});checkWorkflow(token);
  if(plan.binding.session_ref!==session()||plan.binding.freeze_ref!==state.context.product_freeze_ref) throw Error('PLAN_BINDING_DENIED');
  if(![...$('camera').options].some(option=>option.value===plan.camera_ref)) throw Error('CAMERA_REFERENCE_UNAVAILABLE');
  $('camera').value=plan.camera_ref;$('start').value=plan.time_range[0];$('end').value=plan.time_range[1];
  $('task').value=plan.task;$('intent').value='';presentPlan(plan);
  await loadSeeds({selectedRefs:plan.seed_refs,token});checkWorkflow(token);
  const caseSerial=state.caseRequestSerial;
  try {const saved=await post('/product/v1/case',{plan_ref:ref});checkWorkflow(token);
    if(caseSerial===state.caseRequestSerial) {renderCase(saved);await restoreCaseEvents(saved,token,caseSerial);}}
  catch(cause) {if(cause.message!=='CASE_UNAVAILABLE') throw cause;}
  announce('已讀取保存計畫、原鏡頭／時間／種子與 case；尚未執行任何調查步驟。');
}
async function compile() {
  const intent={camera_ref:cameraRef(),time_range:timeRange(),seed_refs:selectedSeeds()};
  if ($('intent').value.trim()) intent.text=$('intent').value.trim(); else intent.task=$('task').value;
  const token=++state.workflowSerial;resetInvestigation();$('planSummary').textContent='正在建立安全計畫…';
  const compiled=await post('/product/v1/intent',{intent});checkWorkflow(token); raw('planRaw',compiled);
  if (compiled.status!=='READY') {$('planSummary').textContent=(compiled.missing_fields||[]).map(code=>missingLabels[code]||code).join('；');
    $('execute').disabled=true;announce('計畫需要補充資料。');return;}
  presentPlan(compiled.plan);await refreshHistory();checkWorkflow(token);
  $('reportButton').disabled=true; $('reviewPanel').hidden=true; announce('安全計畫已保存。執行只引用此 plan，不接受任意工具步驟。');
}
function renderCase(caseData) {
  if(state.case?.plan_ref===caseData.plan_ref && caseData.revision<state.case.revision) return;
  state.case=caseData; raw('caseRaw',caseData);
  $('caseSummary').textContent=(labels[caseData.state]||caseData.state)+' · '+caseData.receipts.length+'份工具 receipts · '+caseData.pending_steps.length+'個待執行步驟。';
  $('subjects').replaceChildren();
  for (const [index,subject] of caseData.subjects.entries()) {const card=node('div',undefined,'subject-card');
    card.append(node('h3','調查目標 '+(index+1)+' · '+(labels[subject.status]||subject.status)),
      node('p',subject.anchor_observation_refs.length+'個原始種子片段；'+subject.evidence_refs.length+'筆證據；'+subject.alternative_refs.length+'個替代 references。'),
      node('p','原始 local tracks 與 provisional tracks 分開保存；沒有唯一 global 身分。'));
    const refs=node('details',undefined,'raw');refs.append(node('summary','此目標的來源與替代關聯'),node('pre',JSON.stringify(subject,null,2)));card.append(refs);$('subjects').append(card);}
  $('conflicts').replaceChildren(); for (const conflict of caseData.conflicts) $('conflicts').append(node('div',
    (conflict.reason==='SHARED_SEGMENT_CANDIDATE'?'多個種子競爭同一 segment 候選':conflict.reason==='ONE_TO_MANY_BINDING'?
      '一個種子保留多個 provisional bindings':'事件與種子的關係尚未證明')+' · '+conflict.subject_refs.length+'個 scoped 目標','conflict'));
  $('execute').disabled=caseData.state!=='READY'; $('pause').disabled=['COMPLETED','BUDGET_EXHAUSTED'].includes(caseData.state);
  $('resume').disabled=!['PAUSED','STOPPED','TOOL_FAILED'].includes(caseData.state); $('reportButton').disabled=false;
}
async function restoreCaseEvents(caseData,token,serial) {
  const current=()=>{checkWorkflow(token);if(serial!==state.caseRequestSerial) throw Error('SESSION_CHANGED');};
  current();const eventRefs=new Set(caseData.evidence.filter(row=>row.kind==='EVENT').map(row=>row.record_ref));
  state.activeEventRefs=eventRefs;const details=[],unavailable=[];
  for(const ref of eventRefs) {
    try {const detail=await detailFor(ref);current();details.push(detail);}
    catch(cause) {current();if(cause.message==='SESSION_CHANGED') throw cause;unavailable.push(ref);}
  }
  current();state.events=details;refreshRouteView();renderEvents(details);
  if(unavailable.length) {
    const missing=node('div',undefined,'disabled-note');missing.append(node('p',unavailable.length+'份 case 事件細節尚未取得；保留原 evidence references，不補造路線。'));
    const refs=node('details',undefined,'raw');refs.append(node('summary','未取得的事件 references'),node('pre',JSON.stringify(unavailable,null,2)));missing.append(refs);$('events').append(missing);
    $('eventCount').textContent=details.length+'筆已取得 · '+unavailable.length+'份細節缺失';
  }
}
async function execute(control={}) {
  if (!state.plan) throw Error('請先建立調查計畫。');
  const token=state.workflowSerial,serial=++state.caseRequestSerial;state.reportSerial++;
  state.report=null;$('exportReport').disabled=true;$('reviewPanel').hidden=true;
  $('reportSummary').replaceChildren();$('reportRaw').textContent='';
  const remaining=state.plan.policy.max_tool_calls-(state.case?.receipts.length||0);
  const params={plan_ref:state.plan.plan_ref,...control};
  if(!control.stop && remaining>0) params.max_new_calls=Math.min(6,remaining);
  const result=await post('/product/v1/execute',params);
  checkWorkflow(token);if(serial!==state.caseRequestSerial) throw Error('SESSION_CHANGED');
  renderCase(result); announce(labels[result.state]||result.state);
  await restoreCaseEvents(result,token,serial);
  await refreshHistory();checkWorkflow(token);
}
async function report() {
  if (!state.plan) throw Error('尚未保存調查計畫。');
  const token=state.workflowSerial,serial=++state.reportSerial;
  const result=await post('/product/v1/report',{plan_ref:state.plan.plan_ref});checkWorkflow(token);
  if(serial!==state.reportSerial) throw Error('SESSION_CHANGED');state.report=result;raw('reportRaw',result);
  const wrapper=node('div',undefined,'report-summary');
  for(const [label,value] of [['工具工作流程',result.workflow_complete?'有限流程已完成':'尚未完成'],
    ['Retrieval 範圍',completeLabel(result.retrieval_complete)],['Graph 搜尋',completeLabel(result.graph_complete)]]) {
    const cell=node('div',label,'report-cell');cell.append(node('strong',value));wrapper.append(cell);}
  $('reportSummary').replaceChildren(wrapper,node('p',result.subjects.length+'個目標、'+result.evidence.length+'筆證據、'+
    result.all_alternative_refs.length+'個替代 references。身分維持未確認。','event-summary'),
    node('p','未解項目：'+result.unresolved.join(' · '),'report-unresolved'));
  $('reviewAlternative').replaceChildren();for(const [index,ref] of result.all_alternative_refs.entries()) {
    const option=node('option','替代候選 '+(index+1)+' · '+ref.split(':')[0]);option.value=ref;$('reviewAlternative').append(option);}
  $('reviewPanel').hidden=false;$('exportReport').disabled=false;announce('報告綁定原 frozen run；retrieval、Graph 與操作完成分開記錄。');
}
async function exportReport() {
  if(!state.report) throw Error('請先取得此 case 的報告。');
  const token=state.workflowSerial,ref=state.report.report_ref;
  const html=await post('/product/v1/export-report',{report_ref:ref},'text');checkWorkflow(token);
  if(state.report?.report_ref!==ref) throw Error('SESSION_CHANGED');
  const url=URL.createObjectURL(new Blob([html],{type:'text/html;charset=utf-8'}));
  const link=node('a');link.href=url;link.download='amidst-'+ref.replace(':','-')+'.html';
  document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  announce('已下載綁定目前 report hash 的本機 HTML 證據報告。');
}
async function review() {
  if(!state.report) throw Error('請先取得報告。');
  const token=state.workflowSerial,reportRef=state.report.report_ref;
  const action=$('reviewAction').value; const reasons={PRESERVE_AMBIGUITY:'AMBIGUOUS_EVIDENCE',REQUEST_EVIDENCE:'MISSING_EVIDENCE',SELECT_PRESENTATION:'DISPLAY_PREFERENCE'};
  const params={report_ref:state.report.report_ref,report_sha256:state.report.report_sha256,
    operator_ref:state.operatorRef,action,reason_code:reasons[action],
    alternative_ref:action==='SELECT_PRESENTATION'?$('reviewAlternative').value:null};
  if(!params.operator_ref) throw Error('此 session 未提供操作員 reference。');
  const result=await post('/product/v1/review',{review:params});checkWorkflow(token);
  if(state.report?.report_ref!==reportRef) throw Error('SESSION_CHANGED');
  $('reviewResult').textContent='已保存獨立 review；canonical_records_modified='+result.canonical_records_modified+'。';
}

async function loadContext(index) {
  state.workflowSerial++;state.historySerial++;state.caseRequestSerial++;state.reportSerial++;state.history=[];
  state.epoch++; state.pendingRequests.forEach(controller=>controller.abort());state.pendingRequests.clear();
  state.clock?.close();pausePlayback(); state.videoCleanup.forEach(cleanup=>cleanup());state.videoCleanup=[];
  for(const {video} of state.videos.values()) {video.removeAttribute('src');video.load();}
  state.videos.clear();state.clock=null;state.scene?.destroy();state.scene=null;
  $('videos').replaceChildren();$('masterCamera').replaceChildren();$('camera').replaceChildren();
  $('scene').replaceChildren(node('p','正在載入此 scope 的呈現資料…','empty'));
  state.context=state.contexts[index];state.operatorRef=state.context.operator_ref||null;
  state.observations=[];state.events=[];
  state.plan=null;state.case=null;state.report=null;state.details.clear();state.activeEventRefs.clear();state.logs=[];
  for(const id of ['seeds','events','subjects','conflicts','reportSummary','appearanceResults']) $(id).replaceChildren();
  $('eventCount').textContent='尚未查詢';
  for(const id of ['planRaw','caseRaw','reportRaw','telemetryRaw','videoRaw','logs']) $(id).textContent='';
  $('planSummary').textContent='尚未建立計畫。';$('caseSummary').textContent='調查計畫尚未執行。';$('reviewResult').textContent='';
  $('history').replaceChildren(node('option','尚未載入'));$('history').firstChild.value='';
  $('history').disabled=true;$('loadPlan').disabled=true;$('reloadHistory').disabled=true;
  $('historyStatus').textContent='此 session 尚未取得保存計畫。';
  $('reviewAlternative').replaceChildren();$('clockTime').textContent='0.00 秒';$('seek').value='0';
  for(const id of ['skewMetric','p95Metric','seekMetric']) $(id).textContent='N/A';$('frameMetric').textContent='0';
  $('frameStatus').textContent='此 scope 的來源影格狀態尚未量測。';
  $('reviewPanel').hidden=true;for(const id of ['execute','pause','resume','reportButton','exportReport','play']) $(id).disabled=true;
  raw('contextRaw',state.context);const context=state.context.context;
  $('scopeLabel').textContent=context.place_id+' · '+context.run_id+' · '+context.clock_id+' · '+context.decision_stage;
  announce('正在載入固定 scope 的鏡頭、影片與結果…');
  const cameras=await tool('list_cameras');$('camera').replaceChildren();for(const camera of cameras.items) {
    const option=node('option',camera.camera_id+' · '+camera.coverage_status);option.value=camera.camera_ref;$('camera').append(option);}
  const results=context.decision_stage==='RESULTS';
  $('loadSeeds').disabled=!state.context.allowed_tools.includes('query_observations');
  $('queryEvents').disabled=!state.context.allowed_tools.includes('query_events');$('appearance').disabled=!state.context.allowed_tools.includes('search_person_appearance');
  $('compile').disabled=!results;
  if(!results) {$('scene').replaceChildren(node('p','INPUT stage：已保存投影、區域與路線結果仍受守門。','disabled-note'));announce('先完成對應 mode 的推論 freeze，才能進入結果調查。');return;}
  const [config,videos]=await Promise.all([post('/product/v1/view/scene'),post('/product/v1/view/videos')]);
  try {state.scene=new ControlScene($('scene'));state.scene.configure(config);}catch(e) {
    $('scene').replaceChildren(node('p','3D WebGL 無法啟動；仍可查詢來源證據與完整結果。','disabled-note'));}
  setupVideos(videos.items);await loadSeeds();$('reloadHistory').disabled=false;await refreshHistory();
}

$('task').addEventListener('change',()=>{$('intent').value='';});
$('loadSeeds').addEventListener('click',()=>loadSeeds().catch(error));$('queryEvents').addEventListener('click',()=>queryEvents().catch(error));
$('appearance').addEventListener('click',()=>appearance().catch(error));$('compile').addEventListener('click',()=>compile().catch(error));
$('execute').addEventListener('click',()=>execute().catch(error));$('pause').addEventListener('click',()=>execute({stop:true}).catch(error));
$('resume').addEventListener('click',()=>execute({resume:true}).catch(error));$('reportButton').addEventListener('click',()=>report().catch(error));
$('review').addEventListener('click',()=>review().catch(error));$('play').addEventListener('click',()=>playPlayback().catch(error));
$('reloadHistory').addEventListener('click',()=>refreshHistory().catch(error));
$('history').addEventListener('change',()=>{$('loadPlan').disabled=!$('history').value;});
$('loadPlan').addEventListener('click',()=>loadSavedPlan().catch(error));
$('exportReport').addEventListener('click',()=>exportReport().catch(error));
$('pausePlayback').addEventListener('click',pausePlayback);$('seek').addEventListener('input',()=>seekTo(Number($('seek').value)));
$('speed').addEventListener('change',()=>{for(const {video} of state.videos.values()) video.playbackRate=Number($('speed').value);});
$('masterCamera').addEventListener('change',()=>{state.clock?.setMaster($('masterCamera').value);seekTo(Number($('seek').value));});
$('session').addEventListener('change',()=>loadContext(Number($('session').value)).catch(error));

async function boot() {
  const response=await fetch('/product/v1/contexts');const result=await response.json();
  if(!response.ok || !result.items?.length) throw Error('沒有已登錄的產品 run。');
  state.contexts=result.items;$('session').replaceChildren();for(const [index,context] of result.items.entries()) {
    const option=node('option',(context.context.observation_mode==='photos_only'?'照片模式':'照片＋像素量測')+' · '+context.context.decision_stage);
    option.value=index;$('session').append(option);}
  await loadContext(0);
}
boot().catch(error);
