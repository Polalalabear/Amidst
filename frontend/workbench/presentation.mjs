import {SceneView} from './scene.mjs';
const h=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export class PresentationPanel {
  constructor(container,{call,mediaURL}){this.container=container;this.call=call;this.mediaURL=mediaURL;this.closed=false;this.timer=null;this.timestamp=0;this.speed=1;this.loop=false;this.initialize().catch(e=>this.error(e));}
  error(error){if(!this.closed)this.container.innerHTML=`<div class="notice warning">${h(error.message??'來源暫不可用')}</div>`;}
  async initialize(){
    const response=await this.call('presentations');if(this.closed)return;
    if(!response.items?.length){this.container.innerHTML='<div class="empty-state">沒有已認證的來源展示素材；請先依來源指南物化。</div>';return;}
    this.items=response.items;await this.load(response.items[0].presentation_ref);
  }
  async load(ref){
    this.pause();const result=await this.call('presentation',{presentation_ref:ref});if(this.closed)return;
    if(!result.presentation)throw Error('來源綁定不可用，未替換成其他模型。');this.data=result.presentation;this.timestamp=this.data.frames[0]?.timestamp??0;this.render();
  }
  render(){
    this.view?.dispose();const data=this.data,last=data.frames.at(-1)?.timestamp??0;
    this.container.innerHTML=`<section class="panel"><div class="panel-head"><div><h2>${h(data.label)}</h2><p>來源模型與公開推論位置的互動展示</p></div><span class="badge amber">DIAGNOSTIC · 無 GT overlay</span></div>
      <div class="panel-body"><label class="field"><span>展示來源</span><select data-presentation-select>${this.items.map(i=>`<option value="${h(i.presentation_ref)}">${h(i.label)}</option>`).join('')}</select></label>
      <div class="notice"><p>灰色為原模型局部 mesh；青色為公開觀測投影，黃色為盲區候選。人形與步態只作 DISPLAY_ONLY 表達，不代表量測到骨架或確認人物身分。</p></div>
      <div class="viewport source-viewport"><div data-source-scene style="height:100%"></div><div class="viewport-overlay"><span class="badge cyan">公尺 · 1 BU = 0.0247 m</span><span class="badge">局部來源幾何 · 未擴大權限</span></div><div class="viewport-controls"><button class="btn small" data-source-reset>重設視角</button></div></div>
      <div class="timeline-panel"><div class="timeline-top"><button class="btn primary" data-source-play>播放</button><button class="btn" data-source-prev>上一格</button><button class="btn" data-source-next>下一格</button><strong data-source-time>0.0 s</strong><label>速度 <select data-source-speed><option value=".5">0.5×</option><option value="1" selected>1×</option><option value="2">2×</option></select></label><label><input type="checkbox" data-source-loop>循環</label></div><input class="timeline-range" aria-label="模型動畫時間" data-source-seek type="range" min="${this.timestamp}" max="${last}" step="${data.frame_step_s}" value="${this.timestamp}"><p data-source-state></p></div>
      <details class="technical"><summary>原診斷影格與來源綁定</summary><p>這是原模型視角的診斷圖，不是 camera RGB sequence。</p><img data-source-frame alt="原模型診斷影格" style="max-width:100%;max-height:380px"><pre>${h(JSON.stringify({binding:data.binding,origin:data.origin,image_measurement:data.image_measurement,authority:data.authority,humanoid:data.humanoid,routes:data.routes?.map(r=>({candidate_ref:r.candidate_ref,complete:r.complete}))},null,2))}</pre></details></div></section>`;
    const snapshot={...data.snapshot,bounds:data.bounds};
    this.view=new SceneView(this.container.querySelector('[data-source-scene]'),{snapshot,objects:snapshot.objects??[],event:{candidates:(data.routes??[]).map(r=>({polyline:r.points}))},presentation:data,onSelect:()=>{}});
    const q=s=>this.container.querySelector(s);
    q('[data-source-play]').onclick=()=>this.timer?this.pause():this.play();
    q('[data-source-prev]').onclick=()=>{this.pause();this.setTime(Math.max(data.frames[0].timestamp,this.timestamp-data.frame_step_s));};
    q('[data-source-next]').onclick=()=>{this.pause();this.setTime(Math.min(last,this.timestamp+data.frame_step_s));};
    q('[data-source-seek]').oninput=e=>{this.pause();this.setTime(Number(e.target.value));};
    q('[data-source-speed]').onchange=e=>{this.speed=Number(e.target.value);this.started=performance.now();this.startTime=this.timestamp;};
    q('[data-source-loop]').onchange=e=>{this.loop=e.target.checked;};
    q('[data-source-reset]').onclick=()=>this.view.reset();
    q('[data-presentation-select]').onchange=e=>this.load(e.target.value).catch(error=>this.error(error));
    this.setTime(this.timestamp);
  }
  setTime(timestamp){
    this.timestamp=timestamp;this.view?.setTimestamp(timestamp);
    const q=s=>this.container.querySelector(s),frame=this.data.frames.slice().sort((a,b)=>Math.abs(a.timestamp-timestamp)-Math.abs(b.timestamp-timestamp))[0];
    q('[data-source-seek]').value=timestamp;q('[data-source-time]').textContent=timestamp.toFixed(1)+' s';
    q('[data-source-state]').textContent=(frame?.evidence_state==='INFERRED_GAP'?'盲區推論 · 候選位置':'可見公開投影')+' · 原影格 '+(frame?.timestamp??0).toFixed(1)+' s · 步態 DISPLAY_ONLY';
    const image=q('[data-source-frame]');if(frame?.media_ref){if(image.dataset.ref!==frame.media_ref){image.dataset.ref=frame.media_ref;image.src=this.mediaURL(frame.media_ref);}}else image.removeAttribute('src');
  }
  play(){
    const last=this.data.frames.at(-1).timestamp;if(this.timestamp>=last)this.setTime(this.data.frames[0].timestamp);
    this.started=performance.now();this.startTime=this.timestamp;
    this.timer=setInterval(()=>{let t=this.startTime+(performance.now()-this.started)/1000*this.speed;
      if(t>=last){if(this.loop){this.started=performance.now();this.startTime=this.data.frames[0].timestamp;t=this.startTime;}else{t=last;this.pause();}}this.setTime(t);},50);
    this.container.querySelector('[data-source-play]').textContent='暫停';
  }
  pause(){clearInterval(this.timer);this.timer=null;const button=this.container.querySelector('[data-source-play]');if(button)button.textContent='播放';}
  dispose(){this.closed=true;this.pause();this.view?.dispose();}
}
