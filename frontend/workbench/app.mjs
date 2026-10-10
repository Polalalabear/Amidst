import {invalidateVersionResults} from './motion.mjs';
const ICONS = {
  home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/><path d="M9 21v-8h6v8"/>',
  layers:'<path d="m12 3 10 6-10 6L2 9Z"/><path d="m2 13 10 6 10-6M2 17l10 6 10-6"/>',
  cube:'<path d="m12 3 9 5v10l-9 5-9-5V8Z"/><path d="m3 8 9 5 9-5M12 13v10M7.5 5.5l9 5"/>',
  camera:'<path d="M3 7h12v12H3Z"/><path d="m15 10 6-3v12l-6-3"/>',
  review:'<path d="M14 3H5v18h14V9"/><path d="m10 14 1-4 8-8 3 3-8 8Z"/><path d="M8 17h5"/>',
  test:'<path d="M9 3h6M10 3v7L4 20h16l-6-10V3M7 15h10"/>',
  arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',
  switch:'<path d="M4 7h16l-4-4M20 17H4l4 4"/>',
  chevron:'<path d="m9 5 7 7-7 7"/>',
  time:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
  person:'<circle cx="12" cy="7" r="4"/><path d="M4 21v-3a8 8 0 0 1 16 0v3"/>',
  event:'<path d="m12 3-3 7H4l5 4-2 7 5-4 5 4-2-7 5-4h-5Z"/>',
  link:'<path d="m9 15 6-6m-8 4-2 2a4 4 0 0 0 6 6l3-3m-4-12 3-3a4 4 0 0 1 6 6l-2 2"/>',
  check:'<path d="m5 12 4 4L20 5"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  play:'<path d="m8 4 12 8-12 8Z"/>',
  pause:'<path d="M8 4v16M16 4v16"/>',
  reset:'<path d="M4 11a8 8 0 1 1 2 7M4 4v7h7"/>',
  region:'<path d="M3 5h18v14H3Z"/><path d="M8 5v14m8-14v14M3 12h18"/>',
  portal:'<path d="M5 21V3h14v18M3 21h18M14 12h.01"/>',
  log:'<path d="M5 3h14v18H5ZM8 7h8M8 11h8M8 15h5"/>',
  expand:'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
};
const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
export const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const h = escapeHTML;
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] ?? ICONS.info}</svg>`;
const json = (value) => h(JSON.stringify(value, null, 2));
const safeList = (value) => Array.isArray(value) ? value : [];
export function normalizeRange(value) {
  const start = Number(Array.isArray(value) ? value[0] : value?.start ?? 0);
  const end = Number(Array.isArray(value) ? value[1] : value?.end ?? start);
  return Number.isFinite(start) && Number.isFinite(end) && end >= start ? [start, end] : [0, 0];
}
export function eventLabel(value) {
  return ({ENTER_DOOR:'進門',EXIT_DOOR:'出門',TURN_CORNER:'轉角',POSSIBLE_LOITERING:'可能遊蕩',DWELL:'停留',LOST_NEAR_CORNER:'轉角附近失去觀測',INFERRED_GAP_ALTERNATIVES:'盲區路線候選'})[value] ?? String(value ?? '事件');
}
export function objectLabel(value) {
  return ({REGION:'區域',PORTAL:'門／通道',WALKABLE:'可行走面',CAMERA:'鏡頭'})[value] ?? String(value ?? '物件');
}
const objectIcon = (value) => ({REGION:'region',PORTAL:'portal',WALKABLE:'layers',CAMERA:'camera'})[value] ?? 'cube';
const fmt = (value, precision = 1) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)) ? Number(value).toFixed(precision) : '—';
const time = (value) => `${fmt(value)} s`;
export const frameTimeLabel = (timestamp) => Number.isFinite(timestamp) ? time(timestamp) : '時間未知';
export function evidenceLabel(value, research = false) {
  if (research) return value ?? '候選事件 · 待檢視';
  return ({INFERRED_GAP:'盲區推論',PROJECTED:'可見投影',OBSERVED:'可見證據',UNKNOWN:'證據不足',UNRESOLVED:'待確認'})[value] ?? '候選事件 · 待檢視';
}
const short = (value, length = 22) => String(value ?? '').length > length ? `${String(value).slice(0, length)}…` : String(value ?? '—');
const technical = (label, value) => `<details class="technical"><summary>${h(label)}</summary><pre>${json(value)}</pre></details>`;
const badge = (text, tone = '') => `<span class="badge ${tone}">${h(text)}</span>`;
const empty = (title, description = '', glyph = 'layers') => `<div class="empty-state">${icon(glyph)}<div>${h(title)}</div>${description ? `<small>${h(description)}</small>` : ''}</div>`;
const sourceVersion = (s) => s.review?.current_version ?? 0;
const state = {
  bootstrap:null,session:null,role:null,sceneId:null,snapshot:null,review:null,page:'dashboard',mode:'display',
  resourceTab:'objects',events:[],observations:[],retrieval:null,frames:[],cameraId:null,cameraIds:[],start:0,end:0,timestamp:0,
  selectedObject:null,selectedEvent:null,event:null,notes:[],draft:null,validation:null,publication:null,previewVersion:null,draftPreview:false,
  test:null,evaluation:null,logs:null,loading:false,error:null,scopeMessage:null,reviewDecision:'UNKNOWN',
  sceneEpoch:0,queryEpoch:0,eventEpoch:0,timelineEpoch:0,controller:null,playTimer:null,view:null,viewPose:null,toastTimer:null,panel:null,
};
export function invalidateEventState(target) {
  target.eventEpoch=(target.eventEpoch??0)+1;
  target.selectedEvent=null;target.event=null;target.notes=[];
}
export function eventRequestIsCurrent(target,ticket) {
  return target.sceneEpoch===ticket.sceneEpoch && target.eventEpoch===ticket.eventEpoch && target.selectedEvent===ticket.eventRef;
}
const isResearch = () => state.role === 'research';
const activeReview = () => state.page === 'review' || state.page === 'workspace' && state.mode === 'review';
const previewVersion = () => state.previewVersion ?? sourceVersion(state);
const historicalPreview = () => activeReview() && previewVersion() !== sourceVersion(state);
const objects = () => {
  if (!activeReview()) return safeList(state.snapshot?.objects);
  const version = safeList(state.review?.versions).find((item) => item.version === previewVersion());
  return safeList(version?.objects ?? state.review?.objects ?? state.snapshot?.objects);
};
const cameras = () => safeList(state.snapshot?.cameras);
const selectedObject = () => objects().find((item) => item.object_id === state.selectedObject);
const renderedObjects = () => activeReview() && state.draft && state.draftPreview ? objects().map((item)=>item.object_id===state.draft.object_id ? state.draft.after : item) : objects();
const cameraName = (id) => cameras().find((camera) => camera.camera_id === id)?.label ?? id ?? '鏡頭未知';
const selectedScene = () => safeList(state.bootstrap?.scenes).find((scene) => scene.scene_id === state.sceneId);
const mediaURL = (ref) => `/api/media?${new URLSearchParams({session_ref:state.session?.session_ref ?? '',scene_id:state.sceneId ?? '',ref})}`;

async function api(action, payload = {}, options = {}) {
  const response = await fetch(`/api/${action}`, {
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({session_ref:state.session?.session_ref,...payload}),
    signal:options.signal ?? state.controller?.signal,
  });
  let result;
  try { result = await response.json(); } catch { throw new Error('服務回應無法讀取，請確認本機工作台服務。'); }
  if (!response.ok || result.error) throw new Error(result.error?.message ?? `請求失敗 (${response.status})`);
  return result;
}
function toast(message) {
  const node = $('#toast');
  node.textContent = message;
  node.classList.add('visible');
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => node.classList.remove('visible'), 4200);
}
function stopPlayback() {
  clearTimeout(state.playTimer);
  state.playTimer = null;
  const button = $('[data-action="play"]');
  if (button) { button.innerHTML = icon('play'); button.setAttribute('aria-label','開始回放'); }
}
function clearContext() {
  state.panel?.dispose();state.panel=null;
  stopPlayback();
  state.controller?.abort();
  state.controller = new AbortController();
  state.sceneEpoch += 1;
  state.queryEpoch += 1;
  state.timelineEpoch += 1;
  invalidateEventState(state);
  state.view?.dispose(); state.view = null; state.viewPose = null;
  Object.assign(state,{snapshot:null,review:null,events:[],observations:[],retrieval:null,frames:[],event:null,notes:[],
    selectedObject:null,selectedEvent:null,draft:null,validation:null,publication:null,test:null,evaluation:null,logs:null,
    error:null,scopeMessage:null,cameraIds:[],previewVersion:null,draftPreview:false});
}
async function selectRole(role) {
  clearContext();
  state.loading = true;
  const buttons = $$('[data-role]'); buttons.forEach((button) => button.disabled = true);
  try {
    const session = await api('session',{role});
    Object.assign(state,{session,role:session.role ?? role,page:'dashboard',mode:'display'});
    const first = safeList(state.bootstrap?.scenes)[0];
    if (!first) throw new Error('尚未註冊可用場景。');
    await loadScene(first.scene_id);
  } catch (error) {
    if (error.name !== 'AbortError') { state.error = error.message; state.loading = false; render(); }
  }
}
async function loadScene(sceneId) {
  clearContext(); state.sceneId = sceneId; state.loading = true; render();
  const epoch = state.sceneEpoch;
  try {
    const result = await api('scene',{scene_id:sceneId});
    if (epoch !== state.sceneEpoch) return;
    state.snapshot = result.snapshot;
    state.review = isResearch() ? result.review_state : null;
    state.cameraId = cameras()[0]?.camera_id ?? null;
    state.cameraIds = cameras().slice(0,3).map((camera) => camera.camera_id);
    const range = normalizeRange(state.snapshot.time_range);
    state.start = range[0]; state.end = Math.min(range[1],range[0]+10); state.timestamp = range[0];
    state.selectedObject = objects()[0]?.object_id ?? null;
    state.loading = false; render();
    await Promise.allSettled([queryScope(),isResearch() ? fetchTimeline(state.timestamp) : Promise.resolve()]);
  } catch (error) {
    if (error.name !== 'AbortError' && epoch === state.sceneEpoch) { state.error = error.message; state.loading = false; render(); }
  }
}
async function queryScope() {
  if (!state.snapshot || !state.cameraId) return;
  const epoch = ++state.queryEpoch; const sceneEpoch = state.sceneEpoch;
  invalidateEventState(state);state.timelineEpoch+=1;
  Object.assign(state,{scopeMessage:null,test:null,events:[],observations:[],retrieval:null});render();
  try {
    const result = await api('query',{scene_id:state.sceneId,camera_id:state.cameraId,start:state.start,end:state.end});
    if (epoch !== state.queryEpoch || sceneEpoch !== state.sceneEpoch) return;
    state.events = safeList(result.events); state.observations = safeList(result.observations); state.retrieval = result.retrieval;
    state.scopeMessage = result.message ?? null;
    render();
  } catch (error) {
    if (error.name !== 'AbortError' && epoch === state.queryEpoch && sceneEpoch === state.sceneEpoch) { state.error = error.message; render(); }
  }
}
async function fetchTimeline(timestamp) {
  if (!isResearch() || !state.snapshot || !state.cameraIds.length) return;
  const sceneEpoch = state.sceneEpoch; const epoch = ++state.timelineEpoch;
  try {
    const result = await api('timeline',{scene_id:state.sceneId,camera_ids:state.cameraIds,timestamp});
    if (sceneEpoch !== state.sceneEpoch || epoch !== state.timelineEpoch) return;
    state.frames = safeList(result.frames); state.timestamp = timestamp;
    updateTimelineDOM();
  } catch (error) {
    if (error.name !== 'AbortError' && epoch === state.timelineEpoch && sceneEpoch === state.sceneEpoch) toast(error.message);
  }
}
async function selectEvent(ref) {
  stopPlayback();
  invalidateEventState(state);state.timelineEpoch+=1;
  state.selectedEvent=ref;state.selectedObject=null;
  const ticket={sceneEpoch:state.sceneEpoch,eventEpoch:state.eventEpoch,eventRef:ref};
  render();
  try {
    const result = await api('event',{scene_id:state.sceneId,event_ref:ref});
    if (!eventRequestIsCurrent(state,ticket)) return;
    Object.assign(state,{event:result.event,notes:safeList(result.notes),selectedEvent:ref,selectedObject:null,page:'workspace',mode:'display',resourceTab:'events'});
    const range = normalizeRange(result.event.time_range);
    state.timestamp = range[0]; render();
    if (isResearch()) await fetchTimeline(state.timestamp);
  } catch (error) { if (error.name !== 'AbortError' && eventRequestIsCurrent(state,ticket)) toast(error.message); }
}

function gateway() {
  return `<main class="gateway"><section class="gateway-left"><div class="brand"><span class="brand-mark">A</span><div>AMIDST<small>SPATIAL RESEARCH WORKBENCH</small></div></div>
    <div class="gateway-copy"><div class="eyebrow">ONE WORKSPACE. EVERY SCENE.</div><h1>從每個畫面，<br>看見<span>空間裡的脈絡。</span></h1><p>在同一個工作台，探索場景、檢視證據，<br>讓每一次人工審查都有跡可循。</p>
    <div class="scene-motif" aria-hidden="true"><div class="motif-plane"><div class="motif-zone"></div><div class="motif-zone two"></div><div class="motif-dot"></div></div></div></div>
    <div class="gateway-footer"><span>DESKTOP WORKSPACE</span><span>LOCAL · VERSION 01</span></div></section>
    <section class="gateway-right"><div class="eyebrow">CHOOSE YOUR WORKSPACE</div><h2>選擇你的工作身份</h2><p class="gateway-caption">直接進入，隨時可以切換身份。</p>
    ${state.error ? `<div class="inline-error">${h(state.error)}</div>` : ''}
    <button class="role-card" data-role="research"><span class="role-icon">${icon('test')}</span><span class="arrow">${icon('arrow')}</span><h3>研究 <small>RESEARCH</small></h3><p>從影像與空間證據出發，測試候選結果，編輯及發布人工審查版本。</p><span class="tags"><span class="tag">完整研究資料</span><span class="tag">場景人審</span><span class="tag">測試與診斷</span></span></button>
    <button class="role-card management" data-role="management"><span class="role-icon">${icon('layers')}</span><span class="arrow">${icon('arrow')}</span><h3>管理 <small>MANAGEMENT</small></h3><p>掌握場域與事件概況，檢視必要證據，記錄備註與處理狀態。</p><span class="tags"><span class="tag">事件摘要</span><span class="tag">證據檢視</span><span class="tag">處理紀錄</span></span></button>
    <p class="gateway-note">本機展示採直接身份切換，無需登入。<br>研究與管理使用各自的資料視圖；此入口不作為帳號驗證。</p></section></main>`;
}
function sidebar() {
  const nav = [ ['dashboard','home','主控板','OVERVIEW'],['workspace','cube','共用工作區','WORKSPACE'],
    ...(isResearch() ? [['presentations','play','實驗展示','PRESENTATIONS'],['review','review','人工審查','REVIEW'],['test','test','測試與評估','TEST']] : []) ];
  return `<aside class="sidebar"><div class="brand"><span class="brand-mark">A</span><div>AMIDST<small>SHARED WORKBENCH</small></div></div><div class="nav-label">WORKSPACE</div><nav class="side-nav">${nav.map(([id,glyph,label]) => `<button class="nav-button ${state.page === id ? 'active' : ''}" data-page="${id}">${icon(glyph)}<span>${label}</span>${state.page === id ? '<span class="tiny">●</span>' : ''}</button>`).join('')}</nav>
    <div class="sidebar-context"><div class="nav-label" style="padding:0">CURRENT SCENE</div><div class="context-title"><span class="status-dot"></span>${h(short(state.snapshot?.label ?? selectedScene()?.label ?? '載入中',20))}</div><div class="context-sub">${isResearch() ? `標註版本 v${h(sourceVersion(state))}<br>局部範圍 · 按需載入` : '事件與必要證據<br>精簡管理視圖'}</div></div>
    <div class="sidebar-bottom"><div class="role-current"><div class="avatar">${isResearch() ? '研' : '管'}</div><div><strong>${isResearch() ? '研究工作台' : '管理主控板'}</strong><small>${isResearch() ? 'Research · full workspace' : 'Management · overview'}</small></div></div><button class="role-switch" data-action="switch-role">${icon('switch')}切換身份</button></div></aside>`;
}
function topbar() {
  const title = ({dashboard:'主控板',workspace:'共用工作區',review:'人工審查',test:'測試與評估',presentations:'實驗展示',investigation:'人物調查'})[state.page];
  return `<header class="topbar"><div class="breadcrumb">工作台 ${icon('chevron')} <strong>${title}</strong></div><div class="topbar-tools"><label class="select-shell">${icon('layers')}<select id="scene-select" aria-label="切換場景">${safeList(state.bootstrap?.scenes).map((scene) => `<option value="${h(scene.scene_id)}" ${scene.scene_id === state.sceneId ? 'selected' : ''}>${h(scene.label ?? scene.scene_id)}</option>`).join('')}</select></label>${badge('本機資料','cyan')}</div></header>`;
}
function pageHead(eyebrow,title,description,actions = '') {
  return `<div class="page-head"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${description}</p></div>${actions ? `<div class="head-actions">${actions}</div>` : ''}</div>`;
}
function eventRows(limit = 6) {
  if (!state.events.length) return empty('目前範圍沒有事件','可切換鏡頭或調整時間窗。','event');
  return `<div class="event-list">${state.events.slice(0,limit).map((event) => {
    const [start,end] = normalizeRange(event.time_range);
    return `<button class="event-row ${event.event_ref === state.selectedEvent ? 'selected' : ''}" data-event="${h(event.event_ref)}"><span class="event-icon">${icon(event.kind === 'INFERRED_GAP_ALTERNATIVES' ? 'link' : 'event')}</span><span class="event-text"><strong>${h(eventLabel(event.kind))}</strong><small>${h(safeList(event.camera_ids).map(cameraName).join(' · '))}<br>${h(evidenceLabel(event.evidence_state,isResearch()))}</small></span><span>${fmt(start)}–${fmt(end)} s</span></button>`;
  }).join('')}</div>`;
}
function frameHTML(frame) {
  const ref = frame.media_ref ?? frame.ref;
  return `<div class="frame">${ref ? `<button class="frame-enlarge" data-image="${h(ref)}" aria-label="放大 ${h(cameraName(frame.camera_id))} 來源影像"><img src="${h(mediaURL(ref))}" alt="${h(cameraName(frame.camera_id))}，${h(frameTimeLabel(frame.timestamp))} 的來源影像" loading="lazy"></button>` : `<div class="frame-empty">${icon('camera')}<span>${h(frame.status ?? '此時間沒有影像')}</span></div>`}<div class="frame-caption"><strong>${h(cameraName(frame.camera_id))}</strong><span>${h(frameTimeLabel(frame.timestamp))}</span></div></div>`;
}
function currentFrames(limit = 3) {
  return state.frames.slice(0,limit).map(frameHTML).join('') || `<div class="frame-empty" style="grid-column:1/-1">${icon('camera')}<span>此場景尚未提供可同步的來源影像</span></div>`;
}
function dashboard() {
  const cameraCount = cameras().length;
  const isSceneOnly = !state.events.length && !state.observations.length;
  const scope = state.cameraId ? `${h(cameraName(state.cameraId))} · ${fmt(state.start)}–${fmt(state.end)} s` : '場景資料';
  const stats = [
    ['已載入鏡頭',cameraCount,'個','camera','場景資料包提供的鏡頭'],
    [isResearch() ? '可審查物件' : '範圍內事件',isResearch() ? objects().length : state.events.length,'項',isResearch() ? 'cube' : 'event',isResearch() ? '區域、門、可行走面與鏡頭' : scope],
    [isResearch() ? '範圍內事件' : '來源場景',isResearch() ? state.events.length : 1,isResearch() ? '項' : '個','event',isResearch() ? scope : h(state.snapshot.label)],
    [isResearch() ? '標註版本' : '證據狀態',isResearch() ? `v${sourceVersion(state)}` : '待檢視','','review',isResearch() ? '原始資料與歷史版本保留' : '候選事件需人工確認'],
  ];
  return `${pageHead(isResearch() ? 'RESEARCH OVERVIEW' : 'MANAGEMENT OVERVIEW',isResearch() ? '研究主控板' : '場域概況',isResearch() ? '把場景、證據與人工判定放在同一個脈絡裡。' : '查看目前場景的事件摘要，從必要證據了解每個候選事件。',`<button class="btn primary" data-page="workspace">開啟工作區 ${icon('arrow')}</button>`)}
    <div class="stats-grid">${stats.map(([label,value,unit,glyph,caption],i) => `<article class="stat-card ${i===0?'highlight':''}"><span class="stat-icon">${icon(glyph)}</span><div class="stat-label">${label}</div><div class="stat-value">${h(value)}<small>${unit}</small></div><div class="stat-caption">${caption}</div></article>`).join('')}</div>
    <div class="dashboard-grid"><section class="panel"><div class="panel-head"><div><h2>目前場景</h2><p>共用畫面，依場景能力顯示資料</p></div>${badge(isSceneOnly ? '場景審查' : '影像與事件','purple')}</div><div class="context-cover"><div class="eyebrow">ACTIVE SCENE</div><h3>${h(state.snapshot.label)}</h3><p>${h(state.snapshot.description ?? '檢視此場景已提供的資產、鏡頭與審查對象。')}</p></div>
    <div class="source-strip"><div><span>資料範圍</span><strong>${scope}</strong></div><div><span>${isResearch() ? '標註版本' : '顯示模式'}</span><strong>${isResearch() ? `v${sourceVersion(state)} · 版本綁定` : '管理 · 事件摘要'}</strong></div><div><span>可用能力</span><strong>${cameraCount} 個鏡頭${isResearch() ? ` · ${objects().length} 個物件` : ''}</strong></div></div>
    ${isResearch() ? `<div class="snapshot-frames" data-frames="dashboard">${currentFrames()}</div>` : `<div class="panel-body" style="padding-top:18px"><p class="muted" style="font-size:11px;margin:0">點選右側事件，即可檢視來源畫面及處理紀錄。</p></div>`}</section>
    <section class="panel"><div class="panel-head"><div><h2>事件速覽</h2><p>${scope}</p></div>${badge(`${state.events.length} 項`)}</div>${eventRows(5)}<div class="panel-foot"><span>顯示目前局部查詢結果</span><button class="micro-link" data-page="workspace">檢視全部 ${icon('arrow')}</button></div></section></div>
    ${isResearch() ? `<div class="workflow"><button class="workflow-card" data-page="workspace"><span class="step-number">01</span><div><h3>探索與展示</h3><p>同步查看來源影像、局部空間與候選事件。</p></div></button><button class="workflow-card" data-page="review"><span class="step-number">02</span><div><h3>人工審查</h3><p>編輯草案，驗證差異後發布新標註版本。</p></div></button><button class="workflow-card" data-page="test"><span class="step-number">03</span><div><h3>測試與追溯</h3><p>執行範圍檢查，獨立查看評估與工具紀錄。</p></div></button></div>` : managementPlaceholder()}
    ${isResearch() ? technical('場景來源與版本資訊',{scene_id:state.snapshot.scene_id,source_hash:state.snapshot.source_hash,model_revision:state.snapshot.model_revision,run_id:state.snapshot.run_id,capabilities:state.snapshot.capabilities}) : ''}`;
}
function managementPlaceholder() {
  return `<section class="panel placeholder-panel"><div class="panel-head"><div><h2>空間與多鏡頭展示</h2><p>為後續管理展示保留一致的空間</p></div>${badge('尚未接入')}</div><div class="placeholder-space"><div class="placeholder-main">${icon('cube')}<h3>3D 場景展示區</h3><p>此版本先提供事件與必要證據。<br>空間模型及多鏡頭模擬畫面將在此呈現。</p></div><div class="placeholder-cameras">${[1,2,3].map((i) => `<div class="placeholder-camera">${icon('camera')}CAMERA ${String(i).padStart(2,'0')} · 預留</div>`).join('')}</div></div></section>`;
}
function scopeBar() {
  return `<form id="scope-form" class="scope-bar"><label class="field"><span>查詢鏡頭</span><select name="camera_id" ${!cameras().length?'disabled':''}>${cameras().map((camera) => `<option value="${h(camera.camera_id)}" ${camera.camera_id === state.cameraId?'selected':''}>${h(camera.label ?? camera.camera_id)}</option>`).join('')}</select></label><label class="field time-input"><span>起始秒數</span><input name="start" type="number" step="0.1" value="${state.start}" required></label><label class="field time-input"><span>結束秒數</span><input name="end" type="number" step="0.1" value="${state.end}" required></label><button class="btn primary" type="submit" ${!state.cameraId?'disabled':''}>更新範圍</button><div class="scope-note">${icon('info')} 僅載入選定範圍；擴展鏡頭需主動選取。</div></form>${state.scopeMessage ? `<div class="notice">${icon('info')}<p>${h(state.scopeMessage)}</p></div>` : ''}`;
}
function workspaceTabs() {
  if (!isResearch()) return '';
  return `<div class="tabs" role="tablist" aria-label="工作模式">${[['display','cube','展示'],['review','review','人審'],['test','test','測試']].map(([id,glyph,label]) => `<button class="tab ${state.mode===id?'active':''}" data-mode="${id}" role="tab" aria-selected="${state.mode===id}">${icon(glyph)}${label}</button>`).join('')}</div>`;
}
function resourceList() {
  return `<aside class="resources"><div class="resource-head">場景資源 ${badge(state.resourceTab==='objects' ? objects().length : state.events.length)}</div><div class="resource-tabs"><button class="resource-tab ${state.resourceTab==='objects'?'active':''}" data-resource-tab="objects">物件</button><button class="resource-tab ${state.resourceTab==='events'?'active':''}" data-resource-tab="events">事件</button></div><div class="resource-items">${state.resourceTab === 'objects' ? objects().map((item) => `<button class="resource-item ${item.object_id === state.selectedObject?'selected':''}" data-object="${h(item.object_id)}">${icon(objectIcon(item.kind))}<span><strong>${h(item.label ?? item.object_id)}</strong><small>${h(objectLabel(item.kind))}</small></span></button>`).join('') || empty('沒有可選物件') : state.events.map((event) => `<button class="resource-item ${event.event_ref === state.selectedEvent?'selected':''}" data-event="${h(event.event_ref)}">${icon('event')}<span><strong>${h(eventLabel(event.kind))}</strong><small>${normalizeRange(event.time_range).map((v)=>fmt(v)).join('–')} s</small></span></button>`).join('') || empty('範圍內没有事件')}</div></aside>`;
}
function viewport() {
  return `<div class="viewport"><div class="viewport-overlay">${badge('局部 3D · 公尺','cyan')} ${badge(activeReview() ? state.draft && state.draftPreview ? '草案預覽 · 尚未發布' : `標註 v${previewVersion()} · 審查預覽` : '來源基線 · 凍結結果')}</div><div data-scene-stage style="height:100%"><div class="viewport-fallback">正在載入場景…</div></div><div class="viewport-help">拖曳旋轉 · Shift＋拖曳平移 · 滾輪縮放 · 點選物件</div><div class="viewport-controls"><button class="btn small ghost" data-action="reset-view" title="重設視角">${icon('reset')}</button></div></div><div class="legend"><span>區域</span><span class="teal">可行走面</span><span class="pink">門／通道</span><span class="amber">候選路線</span></div>`;
}
function timeline() {
  const [start,end] = normalizeRange(state.snapshot.time_range);
  return `<div class="timeline-panel"><div class="timeline-top"><button class="play-button" data-action="play" aria-label="開始回放" ${end<=start || !state.cameraIds.length?'disabled':''}>${icon(state.playTimer?'pause':'play')}</button><strong>同步時間軸</strong><span data-current-time>${time(state.timestamp)}</span></div><input class="timeline-range" id="timeline-range" aria-label="影像回放時間" type="range" min="${start}" max="${end}" step="0.4" value="${state.timestamp}" ${end<=start?'disabled':''}><div class="timeline-labels"><span>${time(start)}</span><span>${time(end)}</span></div><div class="time-lanes" data-time-lanes>${timeLanes()}</div><p class="replay-status">以來源時間選取可用影格；無資料時保留缺圖狀態。</p></div>`;
}
function timeLanes() {
  const [start,end] = normalizeRange(state.snapshot.time_range); const length = Math.max(.001,end-start);
  return state.cameraIds.map((cameraId) => `<div class="time-lane"><span>${h(cameraName(cameraId))}</span><div class="time-track">${state.events.filter((event) => safeList(event.camera_ids).includes(cameraId)).map((event) => {
    const [a,b] = normalizeRange(event.time_range);
    return `<span class="time-mark ${event.kind==='INFERRED_GAP_ALTERNATIVES'?'gap':''}" title="${h(eventLabel(event.kind))}" style="left:${Math.max(0,Math.min(100,(a-start)/length*100))}%;width:${Math.max(.6,Math.min(100,(b-a)/length*100))}%"></span>`;
  }).join('')}<span class="time-mark current" style="left:${Math.max(0,Math.min(100,(state.timestamp-start)/length*100))}%"></span></div></div>`).join('');
}
function cameraSelectors() {
  return `<div class="camera-selectors">${cameras().map((camera) => `<button class="camera-chip ${state.cameraIds.includes(camera.camera_id)?'selected':''}" data-toggle-camera="${h(camera.camera_id)}" aria-pressed="${state.cameraIds.includes(camera.camera_id)}">${icon('camera')} ${h(camera.label ?? camera.camera_id)}</button>`).join('')}</div>`;
}
function researchDisplay() {
  return `${scopeBar()}${sourceVersion(state)>0 ? `<div class="notice warning">${icon('info')}<p>標註 v${sourceVersion(state)} 已發布，研究結果尚未重跑。此展示保留來源基線與原本凍結推論；新版幾何請至人審模式預覽。</p></div>` : ''}<div class="workspace-grid">${resourceList()}<div class="workspace-center">${viewport()}${timeline()}${cameraSelectors()}<div class="camera-grid" data-frames="workspace">${currentFrames(4)}</div>${state.retrieval ? technical('局部查詢收據',state.retrieval) : ''}</div>${inspector()}</div>`;
}
function notesForm() {
  if (!state.event) return '';
  return `<div class="detail-line"><h4>事件處理</h4><form id="note-form"><label class="field"><span>處理狀態</span><select name="status"><option value="OPEN">待處理</option><option value="IN_PROGRESS">處理中</option><option value="RESOLVED">已處理</option></select></label><label class="field"><span>記錄者</span><input name="reviewer" placeholder="填寫名稱" required maxlength="100"></label><label class="field"><span>備註</span><textarea name="note" placeholder="記錄目前處理進度或待補證據" required maxlength="2000"></textarea></label><button class="btn full-button" type="submit">儲存處理紀錄</button></form>${state.notes.map((note) => `<div class="history-item"><strong>${h(({OPEN:'待處理',IN_PROGRESS:'處理中',RESOLVED:'已處理'})[note.status] ?? note.status)} · ${h(note.reviewer)}</strong><p>${h(note.note)}</p></div>`).join('')}</div>`;
}
function uncertainty(event) {
  const value = event.uncertainty;
  if (Array.isArray(value)) return value.map((item)=>typeof item==='string'?item:JSON.stringify(item)).join('；');
  return typeof value==='string' ? value : value ? JSON.stringify(value) : '此結果為候選解釋，應依來源影像與支持證據進行判讀。';
}
function inspector() {
  if (state.event) return eventInspector();
  const object = selectedObject();
  if (!object) return `<aside class="inspector">${empty('選取一個對象','從左側資源列或 3D 場景，選取物件與候選事件。','cube')}</aside>`;
  return `<aside class="inspector"><div class="inspector-head"><div class="eyebrow">SELECTED OBJECT</div><h3>${h(object.label ?? object.object_id)}</h3>${badge(objectLabel(object.kind),'purple')}</div><div class="inspector-body"><div class="detail-grid"><div><span>語意</span><strong>${h(object.semantic ?? '未標註')}</strong></div><div><span>顯示版本</span><strong>${activeReview() ? `標註 v${previewVersion()}` : '來源基線 v0'}</strong></div></div><div class="detail-line"><h4>來源權限</h4><p>${h(typeof object.authority==='string'?object.authority:JSON.stringify(object.authority ?? '未核准'))}</p></div><p>選取既有場景物件，在人審模式中編輯標註草案，驗證後另存新版本。</p><button class="btn primary full-button" data-mode="review">${icon('review')}開始審查</button>${technical('物件 ID 與來源資料',object)}</div></aside>`;
}
function eventInspector() {
  const event = state.event; const [start,end] = normalizeRange(event.time_range);
  return `<aside class="inspector"><div class="inspector-head"><div class="eyebrow">EVENT EVIDENCE</div><h3>${h(eventLabel(event.kind))}</h3>${badge(evidenceLabel(event.evidence_state,isResearch()),'amber')}</div><div class="inspector-body"><div class="detail-grid"><div><span>時間範圍</span><strong>${fmt(start)}–${fmt(end)} s</strong></div><div><span>鏡頭</span><strong>${h(safeList(event.camera_ids).map(cameraName).join('、'))}</strong></div></div><div class="detail-line"><h4>行為摘要</h4><p>${h(event.summary ?? event.description ?? eventLabel(event.kind))}</p></div><div class="detail-line"><h4>判讀限制</h4><p>${h(uncertainty(event))}</p></div>
    ${isResearch() ? `<div class="detail-line"><h4>研究結果審查</h4><p>人工判定另存，保留原始演算法候選。</p><div class="review-toggle">${[['SUPPORT','支持'],['REJECT','否定'],['UNKNOWN','未知'],['MORE_EVIDENCE','需要證據']].map(([value,label])=>`<button class="decision-button ${state.reviewDecision===value?'selected':''}" data-decision="${value}">${label}</button>`).join('')}</div><form id="result-review-form"><label class="field"><span>審查者</span><input name="reviewer" required placeholder="填寫名稱" maxlength="100"></label><label class="field"><span>判定理由</span><textarea name="reason" required maxlength="2000" placeholder="說明支持、衝突或缺少的證據"></textarea></label><button class="btn full-button" type="submit">儲存人工判定</button></form></div>` : ''}${notesForm()}${isResearch() ? technical('來源、候選與診斷資料',event) : ''}</div></aside>`;
}
export function eventMediaFrames(event) {
  const sourceByRef = new Map(safeList(event?.source_frames).map((frame)=>[frame.frame_ref,frame]));
  return safeList(event?.media_refs).map((item) => {
    const ref = typeof item === 'string' ? item : item.media_ref ?? item.frame_ref;
    const source = sourceByRef.get(ref);
    return {
      media_ref:ref,
      camera_id:typeof source?.camera_id === 'string' && source.camera_id ? source.camera_id : null,
      timestamp:Number.isFinite(source?.timestamp) ? source.timestamp : null,
    };
  });
}
function managementDisplay() {
  return `${scopeBar()}<div class="management-detail"><section class="panel"><div class="panel-head"><h2>${state.event ? '來源證據' : '目前範圍的事件'}</h2>${state.event ? `<button class="btn small ghost" data-action="clear-event">返回事件列表</button>` : badge(`${state.events.length} 項`)}</div>${state.event ? `<div class="panel-body"><div class="snapshot-frames">${eventMediaFrames(state.event).map(frameHTML).join('') || empty('此事件沒有可用影像')}</div><p class="status-text">來源影像是候選事件的檢視依據，事件解釋仍需人工確認。</p></div>` : eventRows(state.events.length)}</section>${state.event ? eventInspector() : `<aside class="inspector">${empty('選取事件查看細節','提供必要影像、判讀限制及事件處理紀錄。','event')}</aside>`}</div>${managementPlaceholder()}`;
}
function reviewMode() {
  const object = selectedObject() ?? objects()[0];
  if (!state.selectedObject && object) state.selectedObject = object.object_id;
  return `<div class="notice">${icon('info')}<p>場景編輯另存為 annotation／config 版本。來源資產與已凍結研究結果保留原來的版本綁定。</p></div><div class="review-process"><span class="current">01 選取對象</span>${icon('chevron')}<span>02 編輯草案</span>${icon('chevron')}<span>03 驗證差異</span>${icon('chevron')}<span>04 人工核准並發布</span></div><div class="review-grid"><section class="panel review-preview"><div class="panel-head"><div><h2>場景審查</h2><p>從場景或下方清單選取審查對象</p></div><label class="select-shell"><select id="review-version" aria-label="預覽標註版本">${safeList(state.review?.versions).slice().reverse().map((version)=>`<option value="${version.version}" ${version.version===previewVersion()?'selected':''}>標註 v${version.version}${version.version===sourceVersion(state)?' · 目前版本':' · 歷史預覽'}</option>`).join('')}</select></label></div>${viewport()}<div class="review-list">${objects().map((item)=>`<button class="resource-item ${item.object_id===state.selectedObject?'selected':''}" data-object="${h(item.object_id)}">${icon(objectIcon(item.kind))}<span><strong>${h(item.label ?? item.object_id)}</strong><small>${h(objectLabel(item.kind))}</small></span></button>`).join('')}</div>${state.draft ? draftDifference() : ''}<div class="panel-body"><div class="split-title"><h3>版本與來源</h3><button class="btn small ghost" data-action="export-annotation">${icon('log')}匯出標註 v${previewVersion()}</button></div>${technical('版本紀錄與來源綁定',{current_version:sourceVersion(state),versions:state.review?.versions,history:state.review?.history})}</div></section><aside class="inspector">${object ? reviewEditor(object) : empty('目前沒有可審查物件')}</aside></div>${state.publication ? publicationSummary() : ''}`;
}
function editable(object, field) {
  if (historicalPreview()) return false;
  const fields = safeList(object.editable_fields);
  return fields.includes(field) || (field.startsWith('properties.') && fields.includes('properties'));
}
function reviewEditor(object) {
  const edited = state.draft?.object_id===object.object_id ? state.draft.after : object;
  const intrinsics = edited.properties?.intrinsics ?? edited.properties ?? {};
  const canGeometry = editable(object,'geometry');
  const fields = object.kind === 'CAMERA' && (intrinsics.calibration_kind === 'PINHOLE' || ['fx','fy'].every((key)=>Number.isFinite(intrinsics[key]))) ? ['fx','fy','cx','cy'].filter((key) => editable(object,`properties.${key}`) || editable(object,`properties.intrinsics.${key}`)) : [];
  const noFields = !editable(object,'label') && !editable(object,'semantic') && !canGeometry && !fields.length;
  return `<div class="inspector-head"><div class="eyebrow">ANNOTATION EDITOR</div><h3>${h(object.label ?? object.object_id)}</h3>${badge(objectLabel(object.kind),'purple')}</div><div class="inspector-body"><form id="draft-form"><label class="field"><span>顯示名稱</span><input name="label" value="${h(edited.label)}" ${editable(object,'label')?'':'disabled'} required maxlength="200"></label><label class="field"><span>語意</span><input name="semantic" value="${h(edited.semantic)}" ${editable(object,'semantic')?'':'disabled'} required maxlength="200"></label>${canGeometry ? `<label class="field"><span>幾何範圍 · XYZ 公尺</span><textarea class="mono" name="geometry" rows="7" spellcheck="false">${json(edited.geometry)}</textarea><small class="hint-label">編輯此物件的 type 與 points；驗證器會檢查幾何結構。</small></label>` : ''}${fields.length ? `<div class="form-two">${fields.map((key)=>`<label class="field"><span>${key} · 像素</span><input name="intrinsic_${key}" type="number" step="any" value="${h(intrinsics[key] ?? '')}" required></label>`).join('')}</div>` : ''}${editable(object,'properties') ? `<details class="technical"><summary>進階：物件屬性</summary><label class="field" style="padding:0 10px 10px"><textarea name="properties" class="mono" rows="8" spellcheck="false">${json(edited.properties ?? {})}</textarea></label></details>` : ''}<div class="subtle-rule"></div><label class="field"><span>審查者</span><input name="reviewer" required placeholder="填寫名稱" maxlength="100" value="${h(state.draft?._reviewer ?? state.draft?.reviewer ?? '')}"></label><label class="field"><span>修改理由</span><textarea name="reason" required placeholder="依據哪些來源證據修改？" maxlength="2000">${h(state.draft?._reason ?? state.draft?.reason ?? '')}</textarea></label><button class="btn primary full-button" type="submit" ${noFields?'disabled':''}>${icon('review')}建立審查草案</button></form>${noFields ? `<p class="hint-label">${historicalPreview()?'歷史版本為唯讀預覽。請切回目前版本以編輯新草案。':'此來源未開放可編輯欄位。'}</p>` : ''}<div class="review-note">尚未發布的草案不會改變場景版本。核准後會產生新版本，既有凍結結果保持原樣。</div>${state.draft ? reviewValidationControls() : ''}${technical('物件來源與允許編輯欄位',object)}</div>`;
}
function diffEntries() {
  if (!state.draft) return [];
  const explicit = state.draft.diff ?? state.draft.differences;
  if (Array.isArray(explicit)) return explicit.map((entry)=>({field:entry.field ?? entry.path,before:entry.before ?? entry.old,after:entry.after ?? entry.new}));
  const object = objects().find((item)=>item.object_id===state.draft.object_id) ?? selectedObject() ?? {};
  return Object.entries(state.draft.changes ?? {}).map(([field,after])=>({field,before:state.draft.before?.[field] ?? object[field],after}));
}
const displayValue = (value) => typeof value === 'string' ? value : JSON.stringify(value,null,2);
function draftDifference() {
  return `<div class="panel-body"><div class="split-title"><h3>草案差異</h3><button class="btn small ghost" data-action="toggle-draft-preview">${state.draftPreview?'查看修改前':'預覽草案'}</button></div><table class="diff-table"><thead><tr><th style="width:20%">欄位</th><th>目前版本</th><th>草案</th></tr></thead><tbody>${diffEntries().map((entry)=>`<tr><td>${h(entry.field)}</td><td>${h(displayValue(entry.before))}</td><td>${h(displayValue(entry.after))}</td></tr>`).join('')}</tbody></table></div>`;
}
function validationPassed() {
  return state.validation?.valid === true || state.validation?.passed === true || ['PASS','VALID'].includes(state.validation?.status);
}
function reviewValidationControls() {
  return `<div class="detail-line"><h4>草案驗證與發布</h4><button class="btn full-button" data-action="validate-draft">${icon('check')}驗證此草案</button>${state.validation ? `<div class="validation-banner ${validationPassed()?'':'fail'}">${validationPassed()?'草案驗證通過，可由人工核准發布。':'草案未通過驗證，請查看差異與錯誤。'}</div>${technical('驗證結果',state.validation)}` : ''}${validationPassed() ? `<form id="publish-form"><label class="confirm-row"><input name="confirm" type="checkbox" required><span>我已查看修改前後差異，核准此草案並發布為新的標註版本。</span></label><button class="btn cyan full-button" type="submit">核准並發布新版本</button></form>` : ''}</div>`;
}
function publicationSummary() {
  return `<section class="panel wide-section"><div class="panel-head"><div><h2>新版本已發布</h2><p>目前場景已套用標註 v${sourceVersion(state)}，既有結果仍保留原來版本。</p></div>${badge('發布完成','cyan')}</div><div class="panel-body"><div class="review-lock">使用舊標註版本的凍結結果並未重新計算。請依影響清單決定是否建立新的研究 run。</div>${technical('發布版本與影響清單',state.publication)}</div></section>`;
}
function testMode() {
  const checks = safeList(state.test?.checks);
  return `${scopeBar()}<div class="test-grid"><section class="panel"><div class="panel-head"><div><h2>共用測試面板</h2><p>對目前場景與選定範圍執行可重現檢查</p></div>${badge('範圍檢查','purple')}</div><div class="panel-body"><div class="test-options"><div class="test-feature"><h3>場景與標註</h3><p>檢查場景資料、版本綁定與可用能力。</p></div><div class="test-feature"><h3>局部資料查詢</h3><p>檢查鏡頭、時間窗與回傳資料的來源。</p></div></div><button class="btn primary" data-action="run-test">${icon('test')}執行目前範圍檢查</button><p class="status-text">此處執行工作台的資料與接口檢查，結果不代表研究精度或 formal gates 通過。</p></div><div class="test-result">${state.test ? `<div class="notice">${icon('info')}<p>${h(typeof state.test.summary === 'string' ? state.test.summary : JSON.stringify(state.test.summary ?? '檢查完成'))}</p></div>${checks.map((check) => { const pass = check.passed === true || check.valid === true || ['PASS','PASSED'].includes(check.status); return `<div class="check-item ${pass?'':'fail'}">${icon(pass?'check':'info')}<div><strong>${h(check.label ?? check.name ?? check.check ?? '資料檢查')}</strong><p>${h(check.message ?? check.detail ?? (typeof check.details === 'string' ? check.details : JSON.stringify(check.details ?? {})))}</p></div>${badge(check.status ?? (pass?'PASS':'CHECK'))}</div>`; }).join('')}${technical('完整檢查結果',state.test)}` : empty('尚未執行檢查','檢查結果將綁定目前的場景與範圍。','test')}</div></section>
    <section class="panel"><div class="panel-head"><div><h2>獨立評估區</h2><p>凍結研究結果與評估資料分開存取</p></div>${badge('RESEARCH')}</div><div class="panel-body"><div class="notice warning">${icon('info')}<p>此處只讀已認證的 aggregate 評估摘要；完整 GT debug 與實驗執行不在此入口，Agent 權限維持原範圍。</p></div><button class="btn" data-action="load-evaluation">查看已凍結評估</button>${state.evaluation ? `<div class="wide-section">${evaluationDisplay()}</div>` : '<p class="status-text">由你主動開啟後，才讀取此場景可用的評估結果。</p>'}</div></section></div><section class="panel wide-section"><div class="panel-head"><div><h2>工具紀錄</h2><p>追溯目前 session 的工作台操作</p></div><button class="btn small ghost" data-action="load-logs">${icon('log')}載入紀錄</button></div><div class="panel-body">${state.logs ? technical('請求與操作紀錄',state.logs) : '<p class="status-text">紀錄保留在研究视圖；管理介面不提供技術 ID 與原始 log。</p>'}</div></section>`;
}
function evaluationDisplay() {
  const evaluation = state.evaluation;
  return `${evaluation.message || evaluation.status ? `<div class="notice">${icon('info')}<p>${h(evaluation.message ?? evaluation.status)}</p></div>` : ''}${technical('評估內容與來源範圍',evaluation)}`;
}
function workspace() {
  const mode = state.page === 'review' ? 'review' : state.page === 'test' ? 'test' : state.mode;
  state.mode = mode;
  return `${pageHead('SHARED WORKSPACE',!isResearch()?'檢視事件與來源證據':mode==='review'?'讓每次修改，都有依據。':mode==='test'?'測試、比較與追溯。':'把畫面放回空間脈絡。',!isResearch()?'選取事件，查看必要影像、判讀限制與處理紀錄。':mode==='review'?'同一套審查流程，套用至不同場景的區域、門與鏡頭。':mode==='test'?'以當前版本與局部範圍檢查資料，獨立查看評估證據。':'選取物件或事件，同步檢視影像、時間與局部空間。')}${workspaceTabs()}${!isResearch() ? managementDisplay() : mode==='review' ? reviewMode() : mode==='test' ? testMode() : researchDisplay()}`;
}
function render() {
  state.panel?.dispose();state.panel=null;
  if (state.view) { state.viewPose = state.view.getPose(); state.view.dispose(); state.view = null; }
  const app = $('#app');
  if (!state.role) { app.innerHTML = gateway(); return; }
  const content=!state.snapshot?'':state.page==='presentations'&&isResearch()?`${pageHead('SOURCE MODEL PRESENTATION','讓人物回到場景裡。','局部建築幾何、公開投影與盲區候選使用同一時間軸；來源與推論綁定分別顯示。')}<div data-presentation-panel></div>`:state.page==='dashboard'?dashboard():workspace();
  app.innerHTML = `<div class="shell">${sidebar()}<main class="main-scroll">${topbar()}${state.error ? `<div class="inline-error" style="margin-top:22px">${h(state.error)}</div>` : ''}${state.snapshot ? content : '<div class="initial-loading" style="height:65vh"><span class="brand-mark">A</span><p>正在載入場景資料…</p></div>'}<footer class="page-footer"><span>AMIDST · SHARED RESEARCH WORKBENCH</span><span>來源可追溯 · 判定可比較 · 版本可回看</span></footer></main>${state.loading?'<div class="loading-bar"></div>':''}</div>`;
  mountScene();
  mountPanel();
}
async function mountPanel(){
  const container=$('[data-presentation-panel]');if(!container||!isResearch())return;
  const {PresentationPanel}=await import('./presentation.mjs');if(!container.isConnected)return;
  state.panel=new PresentationPanel(container,{call:(action,payload)=>api(action,payload),mediaURL:ref=>`/api/presentation_media?${new URLSearchParams({session_ref:state.session.session_ref,ref})}`});
}
async function mountScene() {
  const container = $('[data-scene-stage]');
  if (!container || !state.snapshot || !isResearch()) return;
  const epoch = state.sceneEpoch;
  try {
    const {SceneView} = await import('./scene.mjs');
    if (epoch !== state.sceneEpoch || !container.isConnected) return;
    state.view = new SceneView(container,{snapshot:state.snapshot,objects:renderedObjects(),event:activeReview()?null:state.event,observations:activeReview()?[]:state.observations,selectedId:state.selectedObject,pose:state.viewPose,onSelect:(id)=>selectObject(id)});
    state.view.setTimestamp(state.timestamp);
  } catch (error) {
    if (container.isConnected) container.innerHTML = `<div class="viewport-fallback">${icon('cube')}<p>3D 顯示暫時無法載入。<br>你仍可由資源清單檢視物件與進行人審。</p><small>${h(error.message)}</small></div>`;
  }
}
function selectObject(id) {
  invalidateEventState(state);state.timelineEpoch+=1;
  Object.assign(state,{selectedObject:id,selectedEvent:null,event:null,notes:[],draft:null,validation:null,draftPreview:false}); render();
}
function updateTimelineDOM() {
  $$('[data-frames]').forEach((node)=>node.innerHTML = currentFrames(node.dataset.frames==='dashboard'?3:4));
  const range = $('#timeline-range'); if (range) range.value = state.timestamp;
  const label = $('[data-current-time]'); if (label) label.textContent = time(state.timestamp);
  const lanes = $('[data-time-lanes]'); if (lanes) lanes.innerHTML = timeLanes();
  state.view?.setTimestamp(state.timestamp);
}
async function togglePlayback() {
  if (state.playTimer) { stopPlayback(); return; }
  const epoch = state.sceneEpoch; const [start,end] = normalizeRange(state.snapshot.time_range);
  if (state.timestamp >= end) state.timestamp = start;
  const step = async () => {
    if (epoch !== state.sceneEpoch || !state.playTimer) return;
    const next = Math.min(end,state.timestamp+.4);
    await fetchTimeline(next);
    if (epoch !== state.sceneEpoch || !state.playTimer) return;
    if (next>=end) stopPlayback(); else state.playTimer = setTimeout(step,400);
  };
  state.playTimer = setTimeout(step,0);
  const button = $('[data-action="play"]'); if (button) { button.innerHTML=icon('pause'); button.setAttribute('aria-label','暫停回放'); }
}
function formValues(form) { return Object.fromEntries(new FormData(form).entries()); }
export function changesForObject(object, values) {
  const changes = {};
  for (const field of ['label','semantic']) if (field in values && values[field] !== String(object[field] ?? '')) changes[field] = values[field].trim();
  if ('geometry' in values) {
    let parsed;
    try { parsed = JSON.parse(values.geometry); } catch { throw new Error('幾何資料必須是有效的 JSON。'); }
    if (!parsed || !['polygon','line','point'].includes(parsed.type) || !Array.isArray(parsed.points)) throw new Error('幾何資料必須包含 type 與 points。');
    if (!parsed.points.every((point)=>Array.isArray(point) && point.length===3 && point.every(Number.isFinite))) throw new Error('每個幾何座標都必須包含三個有效數字 [x, y, z]。');
    if (JSON.stringify(parsed)!==JSON.stringify(object.geometry)) changes.geometry=parsed;
  }
  let props = structuredClone(object.properties ?? {});
  if ('properties' in values) {
    try { props=JSON.parse(values.properties); } catch { throw new Error('物件屬性必須是有效的 JSON。'); }
    if(!props || typeof props!=='object' || Array.isArray(props))throw new Error('物件屬性必須是 JSON 物件。');
  }
  let changedProps=JSON.stringify(props)!==JSON.stringify(object.properties ?? {});
  for (const key of ['fx','fy','cx','cy']) if (`intrinsic_${key}` in values) {
    const numeric = Number(values[`intrinsic_${key}`]);
    if (!Number.isFinite(numeric)) throw new Error(`${key} 必須是有效數字。`);
    const target = props.intrinsics ?? props;
    if (numeric !== target[key]) { target[key]=numeric; changedProps=true; }
  }
  if (changedProps) changes.properties=props;
  return changes;
}
async function handleSubmit(event) {
  const form = event.target;
  if (!['scope-form','draft-form','publish-form','note-form','result-review-form'].includes(form.id)) return;
  event.preventDefault(); const values=formValues(form); const button=$('button[type="submit"]',form);
  if (button) button.disabled=true;
  const epoch=state.sceneEpoch;
  const eventTicket={sceneEpoch:state.sceneEpoch,eventEpoch:state.eventEpoch,eventRef:state.selectedEvent};
  try {
    if (form.id==='scope-form') {
      const start=Number(values.start),end=Number(values.end);
      if (!Number.isFinite(start)||!Number.isFinite(end)||end<start) throw new Error('結束時間必須大於或等於起始時間。');
      Object.assign(state,{cameraId:values.camera_id,start,end,error:null}); stopPlayback(); await queryScope();
    } else if (form.id==='draft-form') {
      const object=selectedObject(); const changes=changesForObject(object,values);
      if (!Object.keys(changes).length) throw new Error('請先修改至少一個欄位，再建立草案。');
      const result=await api('draft',{scene_id:state.sceneId,object_id:object.object_id,changes,base_version:sourceVersion(state),reviewer:values.reviewer.trim(),reason:values.reason.trim()});
      if(epoch!==state.sceneEpoch)return;
      state.draft={...result.draft,_reviewer:values.reviewer.trim(),_reason:values.reason.trim()}; state.validation=null; state.publication=null; state.draftPreview=true; render(); toast('草案已建立，請檢視差異並驗證。');
    } else if (form.id==='publish-form') {
      if (!values.confirm || !validationPassed()) throw new Error('請先通過驗證，並確認已核對草案差異。');
      const result=await api('publish',{draft_id:state.draft.draft_id,expected_version:sourceVersion(state),reviewer:state.draft._reviewer ?? state.draft.reviewer,reason:state.draft._reason ?? state.draft.reason});
      if(epoch!==state.sceneEpoch)return;
      state.publication=result.publication; state.review=result.review_state; state.previewVersion=null; state.draft=null; state.validation=null; state.draftPreview=false; invalidateVersionResults(state); render(); toast(`標註版本 v${sourceVersion(state)} 已發布。`);
    } else if(form.id==='note-form') {
      const result=await api('note',{scene_id:state.sceneId,event_ref:eventTicket.eventRef,status:values.status,note:values.note.trim(),reviewer:values.reviewer.trim()});
      if(!eventRequestIsCurrent(state,eventTicket))return;
      state.notes.push(result.note); render(); toast('事件處理紀錄已儲存。');
    } else if(form.id==='result-review-form') {
      await api('result_review',{scene_id:state.sceneId,event_ref:eventTicket.eventRef,decision:state.reviewDecision,reason:values.reason.trim(),reviewer:values.reviewer.trim()});
      if(!eventRequestIsCurrent(state,eventTicket))return;
      form.reset(); toast('人工判定已另存，原始候選結果保留。');
    }
  } catch(error) { if(error.name!=='AbortError' && epoch===state.sceneEpoch && (!['note-form','result-review-form'].includes(form.id) || eventRequestIsCurrent(state,eventTicket)))toast(error.message); }
  finally { if(button?.isConnected)button.disabled=false; }
}
async function handleClick(event) {
  const button=event.target.closest('button'); if(!button || button.disabled)return;
  if(button.dataset.role) { await selectRole(button.dataset.role); return; }
  if(button.dataset.page) {
    stopPlayback();state.eventEpoch+=1; state.page=button.dataset.page;
    if(state.page==='workspace')state.mode='display';
    if(state.page==='review')state.mode='review';
    if(state.page==='test')state.mode='test';
    state.error=null; render(); $('.main-scroll')?.scrollTo(0,0); return;
  }
  if(button.dataset.mode) {
    if(!isResearch())return;
    stopPlayback();state.eventEpoch+=1; state.mode=button.dataset.mode; state.page=state.mode==='display'?'workspace':state.mode; render(); return;
  }
  if(button.dataset.object) { selectObject(button.dataset.object); return; }
  if(button.dataset.event) { await selectEvent(button.dataset.event); return; }
  if(button.dataset.resourceTab) { state.resourceTab=button.dataset.resourceTab;render();return; }
  if(button.dataset.decision) { state.reviewDecision=button.dataset.decision;$$('[data-decision]').forEach((node)=>node.classList.toggle('selected',node.dataset.decision===state.reviewDecision));return; }
  if(button.dataset.toggleCamera) {
    stopPlayback();const id=button.dataset.toggleCamera;
    state.cameraIds=state.cameraIds.includes(id)?state.cameraIds.filter((item)=>item!==id):[...state.cameraIds,id].slice(-4);
    render();if(state.cameraIds.length)await fetchTimeline(state.timestamp);else{state.frames=[];updateTimelineDOM();}return;
  }
  if(button.dataset.image) {
    const dialog=document.createElement('dialog');dialog.className='media-dialog';dialog.innerHTML=`<img src="${h(mediaURL(button.dataset.image))}" alt="放大的來源影像"><button class="btn" autofocus>關閉影像</button>`;
    dialog.querySelector('button').addEventListener('click',()=>dialog.close());dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();return;
  }
  const action=button.dataset.action;if(!action)return;
  if(action==='switch-role'){clearContext();state.role=null;state.session=null;state.loading=false;render();return;}
  if(action==='reset-view'){state.view?.reset();return;}
  if(action==='play'){await togglePlayback();return;}
  if(action==='clear-event'){invalidateEventState(state);state.timelineEpoch+=1;render();return;}
  if(action==='toggle-draft-preview'&&isResearch()){state.draftPreview=!state.draftPreview;render();return;}
  if(!isResearch())return;
  button.disabled=true; const epoch=state.sceneEpoch;const queryEpoch=state.queryEpoch;
  try {
    if(action==='validate-draft') {
      const result=await api('validate',{draft_id:state.draft.draft_id});
      if(epoch!==state.sceneEpoch)return;state.validation=result.validation;render();
    }else if(action==='run-test') {
      const result=await api('test',{scene_id:state.sceneId,camera_id:state.cameraId,start:state.start,end:state.end});
      if(epoch!==state.sceneEpoch||queryEpoch!==state.queryEpoch)return;state.test=result;render();toast('目前範圍檢查已完成。');
    }else if(action==='load-evaluation') {
      const result=await api('evaluation',{scene_id:state.sceneId});if(epoch!==state.sceneEpoch)return;state.evaluation=result.evaluation;render();
    }else if(action==='export-annotation') {
      const result=await api('export',{scene_id:state.sceneId,version:previewVersion()});
      if(epoch!==state.sceneEpoch)return;
      const blob=new Blob([JSON.stringify({annotation:result.annotation,receipt:result.receipt},null,2)],{type:'application/json'});
      const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=result.filename;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('標註版本與來源收據已匯出。');
    }else if(action==='load-logs') {
      const result=await api('logs',{scene_id:state.sceneId});if(epoch!==state.sceneEpoch)return;state.logs=result.items;render();
    }
  }catch(error){if(error.name!=='AbortError'&&epoch===state.sceneEpoch&&(action!=='run-test'||queryEpoch===state.queryEpoch))toast(error.message);}finally{if(button.isConnected)button.disabled=false;}
}
async function bootstrap() {
  document.addEventListener('click',handleClick);document.addEventListener('submit',handleSubmit);
  document.addEventListener('change',async(event)=>{
    if(event.target.id==='scene-select')await loadScene(event.target.value);
    if(event.target.id==='review-version'){state.previewVersion=Number(event.target.value);state.draft=null;state.validation=null;state.selectedObject=objects()[0]?.object_id??null;render();}
    if(event.target.id==='timeline-range'){stopPlayback();await fetchTimeline(Number(event.target.value));}
  });
  document.addEventListener('input',(event)=>{if(event.target.id==='timeline-range'){stopPlayback();const label=$('[data-current-time]');if(label)label.textContent=time(event.target.value);}});
  try {
    const response=await fetch('/api/bootstrap');if(!response.ok)throw new Error('工作台初始化失敗。');
    state.bootstrap=await response.json();render();
  }catch(error){state.error=error.message;render();}
}
if(typeof document!=='undefined')bootstrap();
