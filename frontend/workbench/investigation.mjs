import {SceneView} from './scene.mjs';
import {SoftSyncClock,observeVideo} from '../product/timeline.mjs';

const h=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const technical=(label,value)=>'<details class="technical"><summary>'+h(label)+'</summary><pre>'+h(JSON.stringify(value,null,2))+'</pre></details>';
const terminal=state=>['COMPLETED','BUDGET_EXHAUSTED'].includes(state);
const resumable=state=>['PAUSED','STOPPED','TOOL_FAILED'].includes(state);
export const caseStatusText=data=>data.state+' · '+data.receipts.length+' 次工具紀錄 · '+data.pending_steps.length+' 個待執行步驟 · 身分未確認';
export const retrievalText=receipt=>{
  if(!receipt)return '查詢完整性尚未提供；此清單不代表完整 inventory。';
  const complete=receipt.query_complete??receipt.complete;
  const registeredPage=receipt.coverage==='EXACT_REGISTERED_BUCKET_WITHIN_WINDOW'&&
    receipt.truncated===false&&receipt.next_cursor===null&&
    /^[0-9a-f]{64}$/.test(receipt.record_set_receipt_sha256??'');
  return (receipt.truncated?'此頁已截斷；':registeredPage?'此註冊 bucket／時間窗無下一頁；':
    complete===true?'核准查詢範圍已完成；':'查詢完整性未確認；')+
    'graph_complete='+(receipt.graph_complete??'N/A')+'。';
};
export class InvestigationPanel {
  constructor(container,{call,snapshot,mediaURL,videoURL,exportReport}){
    Object.assign(this,{container,call,snapshot,mediaURL,videoURL,exportReport,
      closed:false,serial:0,workflowSerial:0,eventSerial:0,sequence:{},
      videos:[],cleanup:[],details:new Map(),activeEventRefs:new Set(),observations:[],events:[],
      timelineBindings:new WeakMap(),
      plan:null,case:null,report:null,lastTimeline:null,executionPromise:null,stopRequested:false});
    this.initialize().catch(error=>this.error(error));
  }
  q(selector){return this.container.querySelector(selector);}
  error(error){
    if(this.closed||error.message==='SESSION_CHANGED')return;
    const box=this.q('[data-error]');
    if(box)box.textContent=error.message;
    else this.container.innerHTML='<div class="notice warning">'+h(error.message)+'</div>';
  }
  token(scopeOnly=false){return {scope:this.serial,workflow:scopeOnly?null:this.workflowSerial};}
  current(token){return !this.closed&&token.scope===this.serial&&
    (token.workflow===null||token.workflow===this.workflowSerial);}
  check(token){if(!this.current(token))throw Error('SESSION_CHANGED');}
  next(name){this.sequence[name]=(this.sequence[name]??0)+1;return this.sequence[name];}
  checkSequence(token,name,sequence){this.check(token);if(sequence!==this.sequence[name])throw Error('SESSION_CHANGED');}
  async request(action,payload={},token=this.token()){
    this.check(token);const result=await this.call(action,payload);this.check(token);return result;
  }
  tool(tool,params,token=this.token()){return this.request('tool',{tool,params},token);}
  invalidateReport(){
    this.next('report');this.report=null;this.q('[data-report-output]')?.replaceChildren();
  }
  resetWorkflow({clearSeeds=false}={}){
    this.workflowSerial++;this.eventSerial++;this.next('case');this.next('timeline');
    this.plan=null;this.case=null;this.invalidateReport();
    this.stopRequested=true;this.details.clear();this.activeEventRefs.clear();this.events=[];
    this.lastTimeline=null;this.timelineBindings=new WeakMap();
    for(const selector of ['[data-plan]','[data-case]','[data-results]','[data-events]'])
      this.q(selector)?.replaceChildren();
    if(this.q('[data-plan]'))this.q('[data-plan]').textContent='尚未建立計畫。';
    if(this.q('[data-event-retrieval]'))this.q('[data-event-retrieval]').textContent='尚未查詢。';
    if(clearSeeds){
      this.observations=[];this.q('[data-seeds]')?.replaceChildren();
      if(this.q('[data-seed-retrieval]'))this.q('[data-seed-retrieval]').textContent='尚未查詢。';
    }
    this.scene?.setMarkers([],Number(this.q('[data-video-seek]')?.value??0));
    this.updateControls();return this.token();
  }
  async initialize(mode=null){
    this.serial++;this.resetView();this.resetWorkflow({clearSeeds:true});this.context=null;
    this.container.innerHTML='<p class="notice">正在取得此模式的凍結來源；原畫面已清除。</p>';
    const token=this.token(true);
    const context=await this.request('context',mode?{observation_mode:mode}:{},token);
    if(!context.product_context)throw Error('此場景沒有已認證的產品 run；不套用其他模型的結果。');
    this.context=context;this.render();await this.loadVideos(token);this.check(token);await this.history();
  }
  render(){
    const c=this.context,start=c.source.time_range[0],end=Math.min(c.source.time_range[1],start+10);
    this.container.innerHTML=`<div data-error class="inline-error" role="status"></div><div class="notice"><p>調查只引用已凍結結果。候選、HOLD 與多解都保留；執行完成不表示確認人物身分。影片 15fps 為原 RGB ${h(c.source.source_rgb_rate_hz)}Hz 影格重用，步態 DISPLAY_ONLY。</p></div>
    <div class="investigation-grid"><section class="panel"><div class="panel-head"><h2>人物片段與調查</h2></div><div class="panel-body">
    <label class="field"><span>照片輸入模式</span><select data-product-mode>${c.available_modes.map(mode=>`<option value="${mode}" ${mode===c.observation_mode?'selected':''}>${mode}</option>`).join('')}</select></label>
    <label class="field"><span>查詢鏡頭</span><select data-product-camera>${c.cameras.map(camera=>`<option value="${h(camera.camera_ref)}">${h(camera.camera_id)}</option>`).join('')}</select></label>
    <label class="field"><span>起始秒數</span><input data-product-start type="number" step=".1" value="${start}"></label><label class="field"><span>結束秒數</span><input data-product-end type="number" step=".1" value="${end}"></label>
    <button class="btn primary" data-product-seeds>取得局部人物片段</button><p data-seed-retrieval></p><div data-seeds class="wide-section">請先查詢有限鏡頭／時間窗。</div>
    <div class="investigation-controls"><button class="btn small" data-product-appearance>外觀查找</button><button class="btn small" data-product-stitch>同鏡頭恢復假說</button></div>
    <label class="field"><span>調查任務</span><select data-task><option value="TRACE">追查</option><option value="COMPARE">比較</option><option value="BEHAVIOR">行為</option><option value="MULTI_TARGET">多目標</option></select></label>
    <label class="field"><span>可選的有限意圖文字</span><input data-intent maxlength="160" placeholder="例如：追查目標／多目標調查"></label><button class="btn primary" data-compile>建立並保存計畫</button>
    <label class="field wide-section"><span>保存的案例</span><select data-history><option value="">尚未載入</option></select></label><button class="btn" data-load-case>開啟保存案例</button>
    </div></section><div><section class="panel"><div class="panel-head"><h2>場景與四鏡頭影片</h2><span class="badge cyan">${h(c.source.model_id)}</span></div><div class="panel-body"><div class="viewport" data-investigation-scene></div>
    <div class="investigation-controls"><button class="btn primary" data-video-play>播放影片</button><button class="btn" data-video-pause>暫停</button><label>主鏡頭 <select data-video-master></select></label><label>速度 <select data-video-speed><option value=".5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option></select></label><strong data-media-time>0.0 s</strong></div>
    <input class="timeline-range" aria-label="影片時間" data-video-seek type="range" min="${start}" max="${c.source.time_range[1]}" step=".1" value="${start}"><div class="investigation-video-grid" data-videos></div><p class="body-caption" data-frame-status>等待實際影片 clock 與來源影格。</p>${technical('來源、模式與凍結版本',c)}<details class="technical"><summary>同步診斷</summary><pre data-video-telemetry></pre></details></div></section>
    <section class="panel wide-section"><div class="panel-head"><h2>計畫、證據與全部替代</h2><button class="btn small" data-query-events>查詢局部事件</button></div><div class="panel-body"><div data-plan>尚未建立計畫。</div><div class="investigation-controls"><button class="btn primary" data-execute disabled>執行下一步</button><button class="btn" data-execute-all disabled>執行到停止條件</button><button class="btn" data-stop disabled>停止</button><button class="btn" data-resume disabled>續跑</button><button class="btn" data-report disabled>取得報告</button></div><div data-case></div><div data-results></div><p data-event-retrieval>尚未查詢。</p><div data-events></div><div data-report-output></div></div></section></div></div>`;
    this.makeScene();this.updateControls();
    const bind=(selector,action)=>{this.q(selector).onclick=async()=>{const button=this.q(selector);button.disabled=true;try{await action();}catch(e){this.error(e);}finally{if(button.isConnected){button.disabled=false;this.updateControls();}}};};
    bind('[data-product-seeds]',()=>this.loadSeeds());bind('[data-product-appearance]',()=>this.appearance());bind('[data-product-stitch]',()=>this.stitch());
    bind('[data-compile]',()=>this.compile());bind('[data-load-case]',()=>this.loadSaved());
    bind('[data-execute]',()=>this.execute({max_new_calls:1}));bind('[data-execute-all]',()=>this.execute({all:true}));bind('[data-stop]',()=>this.execute({stop:true}));bind('[data-resume]',()=>this.execute({resume:true}));bind('[data-report]',()=>this.loadReport());bind('[data-query-events]',()=>this.queryEvents());
    bind('[data-video-play]',async()=>{const result=await Promise.allSettled(this.videos.map(v=>v.video.play()));if(!result.length||result.every(r=>r.status==='rejected'))throw Error('影片來源尚不可播放。');});
    this.q('[data-video-pause]').onclick=()=>this.videos.forEach(v=>v.video.pause());
    this.q('[data-video-seek]').onchange=e=>this.seek(Number(e.target.value)).catch(error=>this.error(error));
    this.q('[data-video-master]').onchange=e=>this.clock?.setMaster(e.target.value);
    this.q('[data-video-speed]').onchange=e=>this.videos.forEach(v=>{v.video.playbackRate=Number(e.target.value);});
    this.q('[data-product-mode]').onchange=e=>this.initialize(e.target.value).catch(error=>this.error(error));
  }
  updateControls(){
    const available=Boolean(this.plan),busy=Boolean(this.executionPromise);
    const state=this.case?.state??'READY',done=terminal(state);
    const controls={
      '[data-execute]':!available||busy||done||['STOPPED','TOOL_FAILED'].includes(state),
      '[data-execute-all]':!available||busy||done||['STOPPED','TOOL_FAILED'].includes(state),
      '[data-stop]':!available||done||(!busy&&state==='STOPPED'),
      '[data-resume]':!available||busy||!resumable(state),
      '[data-report]':!available||busy||!this.case,
      '[data-compile]':busy,'[data-load-case]':busy,
      '[data-video-play]':!this.videos.length,'[data-video-pause]':!this.videos.length,
      '[data-video-master]':!this.videos.length,'[data-video-speed]':!this.videos.length,
    };
    for(const [selector,disabled] of Object.entries(controls)){
      const element=this.q(selector);if(element)element.disabled=disabled;
    }
  }
  makeScene(){
    const pose=this.scene?.getPose();this.scene?.dispose();
    this.scene=new SceneView(this.q('[data-investigation-scene]'),{
      snapshot:this.snapshot,objects:this.snapshot.objects??[],
      events:[...this.details.values()],observations:[],pose,onSelect:()=>{}});
    this.scene.setMarkers(this.lastTimeline?.markers??[],
      this.lastTimeline?.timestamp??Number(this.q('[data-video-seek]')?.value??0));
  }
  window(){
    const start=Number(this.q('[data-product-start]').value),end=Number(this.q('[data-product-end]').value);
    if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<start||end-start>120)
      throw Error('請選取有效且不超過120秒的時間窗。');
    return [start,end];
  }
  cameraRef(){return this.q('[data-product-camera]').value;}
  seeds(){return [...this.container.querySelectorAll('[data-seed]:checked')].map(input=>input.value);}
  async loadSeeds({selectedRefs=null,token=this.token()}={}){
    const sequence=this.next('seeds');
    const result=await this.tool('query_observations',{camera_ref:this.cameraRef(),time_range:this.window()},token);
    this.checkSequence(token,'seeds',sequence);this.observations=result.items??[];
    const selected=new Set(selectedRefs??this.observations.slice(0,1).map(o=>o.observation_ref));
    this.q('[data-seeds]').innerHTML=this.observations.map((o,i)=>
      '<label class="seed-item"><input data-seed type="checkbox" value="'+h(o.observation_ref)+'" '+
      (selected.has(o.observation_ref)?'checked':'')+'><span>局部片段 '+(i+1)+'<small>'+
      h(o.camera_ids.join(' / '))+' · '+h(o.time_range.join('–'))+' s · '+
      (o.measurements??[]).length+' 筆像素量測</small></span></label>').join('')||
      '沒有可用量測片段；缺失保留。';
    const missing=[...selected].filter(ref=>!this.observations.some(o=>o.observation_ref===ref));
    this.q('[data-seed-retrieval]').textContent=retrievalText(result.retrieval)+
      (missing.length?' '+missing.length+' 個保存種子未在此頁取得；不補造。':'');
    this.q('[data-seeds]').innerHTML+=technical('局部人物查詢收據',{retrieval:result.retrieval,missing_seed_refs:missing});
  }
  async appearance(){
    const token=this.token(),sequence=this.next('results');
    const observation=this.observations.find(o=>this.seeds().includes(o.observation_ref));
    if(!observation)throw Error('請先選取已查得的局部片段。');
    const result=await this.tool('search_person_appearance',{camera_ref:this.cameraRef(),
      time_range:this.window(),query_track_ref:observation.local_track_ref,top_k:6},token);
    this.checkSequence(token,'results',sequence);
    this.q('[data-results]').innerHTML='<h3>外觀候選 · 相似度不是同一人物機率</h3><p>'+
      h(retrievalText(result))+'</p>'+(result.hits??[]).map(hit=>'<div class="result-card">'+
      h(hit.camera_id)+' · '+h(hit.status)+' · '+h(hit.similarity)+
      (hit.representative_media_refs??[]).slice(0,1).map(ref=>'<img style="max-width:150px" src="'+
      h(this.mediaURL(ref))+'" alt="外觀候選來源照片">').join('')+
      technical('特徵來源',hit)+'</div>').join('')+technical('外觀查詢收據',result);
    if(!result.hits?.length)this.q('[data-results]').innerHTML+='<p>沒有候選；未確認人物不存在。</p>';
  }
  async stitch(){
    const token=this.token(),sequence=this.next('results');
    const observation=this.observations.find(o=>this.seeds().includes(o.observation_ref));
    if(!observation)throw Error('請先選取局部片段。');
    const result=await this.tool('get_stitch_hypotheses',{local_track_ref:observation.local_track_ref},token);
    this.checkSequence(token,'results',sequence);
    this.q('[data-results]').innerHTML='<h3>同鏡頭恢復 · provisional／HOLD</h3>'+technical('全部假說與來源',result);
  }
  assertBinding(record){
    const context=this.context.product_context,binding=record.binding;
    if(binding.session_ref!==context.session_ref||binding.freeze_ref!==context.product_freeze_ref||
      binding.observation_mode!==this.context.observation_mode)throw Error('PRODUCT_BINDING_DENIED');
  }
  async compile(){
    const intent={camera_ref:this.cameraRef(),time_range:this.window(),seed_refs:this.seeds()};
    const text=this.q('[data-intent]').value.trim();if(text)intent.text=text;else intent.task=this.q('[data-task]').value;
    const token=this.resetWorkflow();this.q('[data-plan]').textContent='正在建立安全計畫…';
    const result=await this.request('intent',{intent},token);
    if(result.status!=='READY'||!result.plan){
      this.q('[data-plan]').textContent='需要補充：'+(result.missing_fields??[]).join('、');
      this.updateControls();return;
    }
    this.assertBinding(result.plan);this.plan=result.plan;this.showPlan();await this.history(token);
  }
  showPlan(){
    const camera=this.context.cameras.find(c=>c.camera_ref===this.plan.camera_ref);
    this.q('[data-plan]').innerHTML='<strong>'+h(this.plan.task)+' · '+this.plan.seed_refs.length+
      ' 個種子</strong><p>固定鏡頭 '+h(camera?.camera_id??'來源鏡頭')+' · '+
      h(this.plan.time_range.join('–'))+' s。</p><p>最多 '+this.plan.policy.max_tool_calls+' 次工具、'+
      this.plan.policy.max_cameras+' 鏡頭、'+this.plan.policy.max_hops+
      ' hops；原替代順序保留。</p>'+technical('固定計畫與來源綁定',this.plan);
    this.updateControls();
  }
  acceptCase(data,plan){
    if(data.plan_ref!==plan.plan_ref)throw Error('PLAN_REFERENCE_MISMATCH');
    this.assertBinding(data);
    if(this.case?.plan_ref===data.plan_ref&&data.revision<this.case.revision)return false;
    this.case=data;this.showCase();return true;
  }
  async execute(flags={}){
    if(flags.stop)return this.stop();
    if(!this.plan)throw Error('請先建立或開啟計畫。');
    if(this.executionPromise)throw Error('此計畫正在執行；可停止後續批次。');
    const token=this.token(),plan=this.plan;
    this.invalidateReport();this.stopRequested=false;
    const operation=this.performExecution(plan,token,flags);
    this.executionPromise=operation;this.updateControls();
    try{return await operation;}
    finally{
      if(this.executionPromise===operation)this.executionPromise=null;
      if(this.current(token))this.updateControls();
    }
  }
  async performExecution(plan,token,flags){
    let first=true;
    do{
      this.check(token);
      if(this.stopRequested){
        if(!terminal(this.case?.state)){
          const stopped=await this.request('execute',{plan_ref:plan.plan_ref,stop:true},token);
          this.acceptCase(stopped,plan);
        }
        break;
      }
      if(terminal(this.case?.state))break;
      const remaining=plan.policy.max_tool_calls-(this.case?.receipts.length??0);
      if(remaining<=0)break;
      const maxCalls=Math.min(flags.max_new_calls??(flags.all?6:1),remaining);
      const resume=flags.resume===true||this.case?.state==='PAUSED'||(!first&&resumable(this.case?.state));
      const data=await this.request('execute',{plan_ref:plan.plan_ref,max_new_calls:maxCalls,resume},token);
      this.acceptCase(data,plan);first=false;
      if(this.stopRequested)continue;
      if(!flags.all||terminal(data.state)||['STOPPED','TOOL_FAILED'].includes(data.state))break;
      await new Promise(resolve=>setTimeout(resolve,0));this.check(token);
    }while(true);
    await this.history(token);this.check(token);return this.case;
  }
  async stop(){
    this.stopRequested=true;
    if(this.executionPromise)return this.executionPromise;
    if(!this.plan)throw Error('請先建立或開啟計畫。');
    const token=this.token(),plan=this.plan;this.invalidateReport();
    const operation=(async()=>{
      const data=await this.request('execute',{plan_ref:plan.plan_ref,stop:true},token);
      this.acceptCase(data,plan);await this.history(token);return data;
    })();
    this.executionPromise=operation;this.updateControls();
    try{return await operation;}
    finally{
      if(this.executionPromise===operation)this.executionPromise=null;
      if(this.current(token))this.updateControls();
    }
  }
  showCase(){
    const data=this.case;
    this.q('[data-case]').innerHTML='<div class="result-card"><strong>'+h(caseStatusText(data))+
      '</strong><p>workflow_complete='+h(data.workflow_complete)+'；retrieval_complete='+
      h(data.retrieval_complete)+'；graph_complete='+h(data.graph_complete)+'</p>'+
      data.subjects.map((s,i)=>'<p>目標 '+(i+1)+' · '+h(s.status)+' · '+
      s.alternative_refs.length+' 個替代 references</p>').join('')+
      technical('衝突、缺失與工具紀錄',data)+'</div>';
    this.renderEvents(data.evidence.filter(e=>e.kind==='EVENT').map(e=>({event_ref:e.record_ref})));
    this.updateControls();
  }
  renderEvents(events,receipt=null){
    this.eventSerial++;this.next('timeline');this.events=events;
    this.activeEventRefs=new Set(events.map(e=>e.event_ref));
    for(const ref of this.details.keys())if(!this.activeEventRefs.has(ref))this.details.delete(ref);
    this.lastTimeline=null;
    this.q('[data-event-retrieval]').textContent=receipt?retrievalText(receipt):
      '此列表引用 case 已取得的 evidence；未確認完整 scene inventory。';
    this.q('[data-events]').innerHTML=events.map((e,i)=>'<div class="result-card">'+
      (e.kind?'<strong>'+h(e.kind)+' · '+h(e.time_range.join('–'))+' s</strong><p>'+
      h(e.termination_reason)+' · search complete='+h(e.complete)+' · '+
      h(e.candidate_count)+' 路線／'+h(e.hypothesis_count)+' 時間假說</p>':'')+
      '<button class="btn small" data-case-event="'+h(e.event_ref)+'">按需取得事件 '+(i+1)+
      '、照片與全部路線</button><div data-event-detail="'+h(e.event_ref)+'"></div></div>').join('')||
      '空結果；未推定不存在。';
    if(receipt)this.q('[data-events]').innerHTML+=technical('事件查詢收據',receipt);
    this.container.querySelectorAll('[data-case-event]').forEach(button=>{
      const ref=button.dataset.caseEvent;
      const target=this.q('[data-event-detail="'+ref+'"]');
      if(this.details.has(ref))this.renderDetail(this.details.get(ref),target);
      button.onclick=()=>this.detail(ref,target).catch(error=>this.error(error));
    });
    this.makeScene();
    this.refreshTimeline(Number(this.q('[data-video-seek]').value)).catch(error=>this.error(error));
  }
  async queryEvents(){
    const token=this.token(),sequence=this.next('events');
    this.renderEvents([]);this.q('[data-event-retrieval]').textContent='正在查詢有限範圍…';
    const result=await this.tool('query_events',{camera_ref:this.cameraRef(),time_range:this.window()},token);
    this.checkSequence(token,'events',sequence);this.renderEvents(result.items??[],result.retrieval);
  }
  renderDetail(detail,container){
    container.innerHTML='<p>'+h(detail.uncertainty)+'</p><p>'+
      (detail.candidates?.length??0)+' 條原始路線、'+(detail.trajectories?.length??0)+
      ' 個時間假說。</p>'+(detail.media_refs??[]).map(media=>
      '<img style="max-width:180px" src="'+h(this.mediaURL(media))+
      '" alt="未標註的合成證據照片">').join('')+technical('完整 canonical 候選',detail);
  }
  async detail(ref,container){
    const token=this.token(),eventSerial=this.eventSerial;
    const detail=await this.tool('get_event_detail',{event_ref:ref},token);
    this.check(token);
    if(eventSerial!==this.eventSerial||!container?.isConnected||!this.activeEventRefs.has(ref))
      throw Error('SESSION_CHANGED');
    if(detail.event_ref!==ref)throw Error('REFERENCE_DENIED');
    this.details.set(ref,detail);this.renderDetail(detail,container);this.makeScene();
  }
  async history(token=this.token()){
    const sequence=this.next('history'),result=await this.request('cases',{},token);
    this.checkSequence(token,'history',sequence);
    this.q('[data-history]').innerHTML='<option value="">選擇已保存案例</option>'+
      result.items.map((item,i)=>'<option value="'+h(item.plan_ref)+'">案例 '+(i+1)+
      ' · '+h(item.task)+' · '+h(item.state)+'</option>').join('');
    if(this.plan)this.q('[data-history]').value=this.plan.plan_ref;
    this.q('[data-history]').title=result.truncated?'只列最新保存案例；清單已截斷。':'此 scope 回傳清單完整。';
  }
  async loadSaved(){
    const ref=this.q('[data-history]').value;if(!ref)throw Error('請選取保存案例。');
    const token=this.resetWorkflow({clearSeeds:true});
    const plan=await this.request('plan',{plan_ref:ref},token);this.assertBinding(plan);
    if(!this.context.cameras.some(c=>c.camera_ref===plan.camera_ref))throw Error('REFERENCE_DENIED');
    this.plan=plan;this.showPlan();this.q('[data-product-camera]').value=plan.camera_ref;
    this.q('[data-product-start]').value=plan.time_range[0];this.q('[data-product-end]').value=plan.time_range[1];
    this.q('[data-task]').value=plan.task;this.q('[data-intent]').value='';
    await this.loadSeeds({selectedRefs:plan.seed_refs,token});this.check(token);
    try{
      const saved=await this.request('case',{plan_ref:ref},token);this.acceptCase(saved,plan);
      const eventSerial=this.eventSerial;
      for(const eventRef of this.activeEventRefs){
        const target=this.q('[data-event-detail="'+eventRef+'"]');
        try{await this.detail(eventRef,target);}
        catch(error){
          this.check(token);
          const code=error.code??error.message;
          if(eventSerial!==this.eventSerial||code!=='REFERENCE_DENIED')throw error;
          target.textContent='細節未取得；保留原 evidence reference，不補造路線。';
        }
      }
    }catch(error){
      this.check(token);
      if((error.code??error.message)!=='CASE_UNAVAILABLE')throw error;
      this.q('[data-case]').textContent='已讀取保存計畫；case 尚未建立。';this.updateControls();
    }
  }
  async loadReport(){
    if(!this.plan||!this.case)throw Error('請先取得此計畫的 case。');
    const token=this.token(),plan=this.plan,sequence=this.next('report');
    const report=await this.request('report',{plan_ref:plan.plan_ref},token);
    this.checkSequence(token,'report',sequence);
    if(report.plan_ref!==plan.plan_ref)throw Error('PLAN_REFERENCE_MISMATCH');
    this.assertBinding(report);this.report=report;const r=report;
    this.q('[data-report-output]').innerHTML='<h3>調查報告 · '+h(r.identity_status)+
      '</h3><p>'+h(r.explanation)+'</p><p>'+r.subjects.length+' 個 scoped 目標、'+
      r.all_alternative_refs.length+' 個替代、'+r.conflicts.length+' 個衝突；'+h(r.state)+
      '。</p><button class="btn" data-export-report>匯出 HTML 報告</button>'+
      '<div class="investigation-controls"><button class="btn" data-preserve-review>人審：保留歧義</button>'+
      '<button class="btn" data-evidence-review>人審：要求更多證據</button>'+
      '<select data-review-alternative>'+r.all_alternative_refs.map((ref,i)=>
      '<option value="'+h(ref)+'">替代 '+(i+1)+' · '+h(ref.split(':')[0])+'</option>').join('')+
      '</select><button class="btn" data-select-review '+(!r.all_alternative_refs.length?'disabled':'')+
      '>人審：選擇呈現</button></div><p>選擇只追加呈現偏好，不確認 global 身分或改寫候選。</p>'+
      '<div data-review-status></div>'+technical('完整報告與 freeze/hash',r);
    this.q('[data-export-report]').onclick=()=>this.downloadReport().catch(error=>this.error(error));
    for(const [selector,action] of [['[data-preserve-review]','PRESERVE_AMBIGUITY'],
      ['[data-evidence-review]','REQUEST_EVIDENCE'],['[data-select-review]','SELECT_PRESENTATION']])
      this.q(selector).onclick=()=>this.review(action).catch(error=>this.error(error));
  }
  async review(action){
    const reasons={PRESERVE_AMBIGUITY:'AMBIGUOUS_EVIDENCE',REQUEST_EVIDENCE:'MISSING_EVIDENCE',
      SELECT_PRESENTATION:'DISPLAY_PREFERENCE'};
    if(!this.report||!reasons[action])throw Error('REPORT_UNAVAILABLE');
    const token=this.token(),report=this.report;
    const review={report_ref:report.report_ref,report_sha256:report.report_sha256,
      action,reason_code:reasons[action]};
    if(action==='SELECT_PRESENTATION'){
      const alternative=this.q('[data-review-alternative]').value;
      if(!report.all_alternative_refs.includes(alternative))throw Error('REFERENCE_DENIED');
      review.alternative_ref=alternative;
    }
    const result=await this.request('review',{review},token);
    if(this.report!==report)throw Error('SESSION_CHANGED');
    this.q('[data-review-status]').textContent='已追加人審紀錄；原候選與身分狀態保留。';
    this.q('[data-review-status]').innerHTML+=technical('人審收據',result);
    return result;
  }
  async downloadReport(){
    if(!this.report)throw Error('REPORT_UNAVAILABLE');
    const token=this.token(),report=this.report;
    const current=()=>this.current(token)&&this.report===report;
    await this.exportReport(report.report_ref,current);
    if(!current())throw Error('SESSION_CHANGED');
  }
  timelineRefs(){return [...this.activeEventRefs].slice(0,128);}
  async timelineRequest(timestamp,token=this.token()){
    const eventSerial=this.eventSerial;
    const state=await this.request('timeline',{timestamp,event_refs:this.timelineRefs()},token);
    if(eventSerial!==this.eventSerial)throw Error('SESSION_CHANGED');
    if(state.run_ref!==this.context.product_context.run_ref||!Number.isFinite(state.timestamp)||
      Math.abs(state.timestamp-timestamp)>1e-8||
      state.presentation_only!==true)throw Error('TIMELINE_BINDING_DENIED');
    this.timelineBindings.set(state,{token,eventSerial});
    return state;
  }
  applyTimeline(state){
    const binding=this.timelineBindings.get(state);
    if(!binding||!this.current(binding.token)||binding.eventSerial!==this.eventSerial)
      throw Error('SESSION_CHANGED');
    this.lastTimeline=state;this.scene?.setMarkers(state.markers,state.timestamp);
    this.q('[data-video-seek]').value=state.timestamp;
    this.q('[data-media-time]').textContent=state.timestamp.toFixed(2)+' s';
    this.q('[data-frame-status]').textContent=state.frames.map(f=>f.camera_id+' '+f.status+
      (f.frame_timestamp!==null?' 原影格 t='+f.frame_timestamp+' s；offset='+f.offset_seconds+' s':'')).join(' · ')+
      (this.activeEventRefs.size>128?'；時間軸僅呈現前128個事件 references，其餘保留於列表。':'');
  }
  async refreshTimeline(timestamp){
    const token=this.token(),sequence=this.next('timeline');
    const state=await this.timelineRequest(timestamp,token);
    this.checkSequence(token,'timeline',sequence);this.applyTimeline(state);
    return state;
  }
  async loadVideos(token=this.token(true)){
    const result=await this.request('videos',{},token),items=result.items;
    if(!items.length){
      this.q('[data-videos]').textContent='沒有已登錄影片；保留來源照片時間軸。';
      this.q('[data-video-telemetry]').textContent='影片尚未物化，media callback／同步指標 N/A。';
      this.updateControls();await this.refreshTimeline(this.context.source.time_range[0]);return;
    }
    const clock=new SoftSyncClock({runRef:this.context.product_context.run_ref,masterCameraRef:items[0].camera_ref,
      requestState:timestamp=>this.timelineRequest(timestamp),
      applyState:state=>{if(this.current(token)&&this.clock===clock)this.applyTimeline(state);},
      onTime:()=>{},onTelemetry:data=>{if(this.current(token)&&this.clock===clock)
        this.q('[data-video-telemetry]').textContent=JSON.stringify(data,null,2);},
      onError:error=>this.error(error)});
    this.clock=clock;
    for(const info of items){
      const card=document.createElement('div'),video=document.createElement('video');
      video.muted=true;video.playsInline=true;video.preload='metadata';video.src=this.videoURL(info.video_ref);
      card.append(video);const label=document.createElement('small');
      label.textContent=info.camera_id+' · 原來源 '+result.source_rgb_rate_hz+'Hz';card.append(label);
      this.q('[data-videos]').append(card);this.videos.push({video,info});
      const option=document.createElement('option');option.value=info.camera_ref;option.textContent=info.camera_id;
      this.q('[data-video-master]').append(option);
      this.cleanup.push(observeVideo(video,info,clock,t=>{
        if(!this.current(token)||this.clock!==clock||info.camera_ref!==clock.masterCameraRef)return;
        for(const other of this.videos)
          if(other.video!==video&&!other.video.paused&&Math.abs(other.video.currentTime+other.info.start_time-t)>.25)
            other.video.currentTime=Math.max(0,Math.min(other.info.end_time-other.info.start_time,t-other.info.start_time));
      }));
      video.onerror=()=>{if(this.current(token)&&this.clock===clock)
        label.textContent=info.camera_id+' · 影片來源缺失';};
    }
    this.updateControls();
  }
  async seek(timestamp){
    if(!Number.isFinite(timestamp)||timestamp<this.context.source.time_range[0]||
      timestamp>this.context.source.time_range[1])throw Error('INVALID_SEEK');
    this.next('timeline');
    if(!this.videos.length)return this.refreshTimeline(timestamp);
    this.clock?.seek(timestamp);
    for(const {video,info} of this.videos){
      video.pause();video.currentTime=Math.max(0,Math.min(info.end_time-info.start_time,timestamp-info.start_time));
    }
  }
  resetView(){
    this.cleanup.forEach(fn=>fn());this.cleanup=[];this.clock?.close();this.clock=null;
    this.videos.forEach(v=>{v.video.pause();v.video.removeAttribute('src');v.video.load();});
    this.videos=[];this.scene?.dispose();this.scene=null;this.lastTimeline=null;
  }
  dispose(){this.closed=true;this.serial++;this.workflowSerial++;this.stopRequested=true;this.resetView();}
}
