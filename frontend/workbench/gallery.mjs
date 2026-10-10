const h=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const galleryItems=(items,debug)=>items.filter(item=>Boolean(item.gt_debug_only)===debug);
export const materializationLabel=status=>({MATERIALIZED:'素材已核對',PARTIAL:'部分素材可用',MISSING:'缺少素材',CANONICAL_ROOT_UNAVAILABLE:'原素材來源未接入'})[status]??status;
const cell=value=>typeof value==='number'?Number(value.toPrecision(5)).toString():String(value??'N/A');
export class GalleryPanel {
  constructor(container,{call,mediaURL}){this.container=container;this.call=call;this.mediaURL=mediaURL;this.closed=false;this.serial=0;this.debug=false;this.initialize().catch(e=>this.error(e));}
  error(e){if(!this.closed)this.container.innerHTML=`<div class="notice warning">${h(e.message)}</div>`;}
  async initialize(){const packet=await this.call('gallery_list');if(this.closed)return;this.items=packet.items??[];this.complete=packet.complete;this.render();}
  render(){
    this.serial++;
    const items=galleryItems(this.items,this.debug);
    this.container.innerHTML=`<section class="panel"><div class="panel-head"><div><h2>實驗展示庫</h2><p>固定索引的展示家族，依來源及缺失狀態索引。</p></div><span class="badge">${this.items.length} 家族 · ${this.complete?'固定索引完整':'索引未完成'}</span></div>
      <div class="panel-body"><div class="mode-tabs"><button class="btn ${!this.debug?'primary':''}" data-gallery-audience="research">研究診斷</button><button class="btn ${this.debug?'primary':''}" data-gallery-audience="debug">GT debug（獨立）</button></div>
      <p class="status-text">此區為人類研究檢視；素材存在、展示接入與正式研究通過分別記錄。RRD／歷史 MP4 只列存在狀態；互動影片請用人物調查頁。</p>
      ${this.debug?'<div class="notice warning"><p>獨立歷史 debug：可能含 GT 或人工標記，不是推論依據，也不會出現在主展示與 Agent 工具。</p></div>':''}
      <div class="gallery-families">${items.map(item=>`<button class="result-card" data-gallery-family="${h(item.family_ref)}"><strong>${h(item.title)}</strong><span>${h(materializationLabel(item.status))} · ${h(item.classification)}</span><small>${item.counts.images} PNG · ${item.counts.tables} 表 · ${item.counts.rrd} RRD · ${item.counts.mp4} MP4 · ${item.counts.missing} 缺項</small></button>`).join('')}</div>
      <div data-gallery-detail>${items.length?'選取家族查看圖表與來源狀態。':'此分類沒有可用家族。'}</div></div></section>`;
    this.container.querySelectorAll('[data-gallery-audience]').forEach(button=>button.onclick=()=>{this.debug=button.dataset.galleryAudience==='debug';this.render();});
    this.container.querySelectorAll('[data-gallery-family]').forEach(button=>button.onclick=()=>this.load(button.dataset.galleryFamily).catch(e=>this.error(e)));
  }
  async load(ref){
    const serial=++this.serial;let detail;
    try{detail=await this.call('gallery_detail',{family_ref:ref});}catch(error){if(!this.closed&&serial===this.serial)this.error(error);return;}
    if(this.closed||serial!==this.serial)return;
    const data=detail.family??detail;
    if(Boolean(data.gt_debug_only)!==this.debug)throw Error('GALLERY_AUDIENCE_CHANGED');
    this.container.querySelector('[data-gallery-detail]').innerHTML=`<div class="wide-section"><div class="panel-head"><div><h3>${h(data.title)}</h3><p>${h(materializationLabel(data.status))} · ${h(data.classification)}</p></div></div>
      ${(data.limitations??[]).map(text=>`<p class="status-text">${h(text)}</p>`).join('')}
      ${(data.tables??[]).map(table=>`<details class="technical" open><summary>${h(table.label)} · ${h(table.status)} · ${table.rows?.length??0} 列</summary>${table.status==='AVAILABLE'?`<p>complete=${h(table.complete)} · 原表內容另存；N/A／NOT_RUN 保留。數值顯示五位有效數字。</p>${table.columns.includes('result_type')?'<p>原表 FORMAL 是當時的局部記錄類型；此展示不代表 full Exit 驗收。</p>':''}<div class="gallery-table"><table><thead><tr>${table.columns.map(c=>`<th>${h(c)}</th>`).join('')}</tr></thead><tbody>${table.rows.map(row=>`<tr>${row.map(value=>`<td>${h(cell(value))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:''}</details>`).join('')}
      <div class="gallery-images">${(data.images??[]).map(image=>`<figure><img loading="lazy" src="${h(this.mediaURL(image.media_ref))}" alt="${h(image.label)}"><figcaption>${h(image.label)} · ${image.width}×${image.height} · ${h(image.audience)}${image.gt_overlay===true?' · GT overlay':''}</figcaption></figure>`).join('')}</div>
      <details class="technical"><summary>來源與素材狀態</summary><pre>${h(JSON.stringify({family_ref:data.family_ref,classification:data.classification,status:data.status,model_id:data.model_id,source_sha256:data.source_sha256,provenance_sha256:data.provenance_sha256,source_locations:data.source_locations,preview_frame_count:data.preview_frame_count,verified_preview_frames:data.verified_preview_frames,missing_preview_frame_indices:data.missing_preview_frame_indices,origin:data.origin,authority:data.authority,artifacts:data.artifacts,counts:data.counts,normal_presentation_allowed:data.normal_presentation_allowed},null,2))}</pre></details></div>`;
  }
  dispose(){this.closed=true;this.serial++;}
}
