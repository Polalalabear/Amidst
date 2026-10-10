import test from 'node:test';
import assert from 'node:assert/strict';
import {GalleryPanel,galleryItems,materializationLabel} from './gallery.mjs';
test('debug artifacts are excluded from the default research gallery',()=>{
  const items=[{family_ref:'diagnostic',gt_debug_only:false},{family_ref:'debug',gt_debug_only:true}];
  assert.deepEqual(galleryItems(items,false).map(i=>i.family_ref),['diagnostic']);
  assert.deepEqual(galleryItems(items,true).map(i=>i.family_ref),['debug']);
});
test('missing and partial artifact states are retained',()=>{
  assert.equal(materializationLabel('PARTIAL'),'部分素材可用');
  assert.equal(materializationLabel('MISSING'),'缺少素材');
  assert.equal(materializationLabel('NOT_RUN'),'NOT_RUN');
});
test('a late rejected detail cannot replace a newer family or audience',async()=>{
  let rejectOld;const old=new Promise((_resolve,reject)=>{rejectOld=reject;});
  const detail={innerHTML:''},container={innerHTML:'current panel',querySelector:()=>detail};
  const panel=Object.create(GalleryPanel.prototype);
  Object.assign(panel,{container,closed:false,serial:0,debug:false,mediaURL:()=>'',call:(_action,{family_ref})=>family_ref==='old'?old:Promise.resolve({family:{title:'new',gt_debug_only:false,images:[],tables:[]}})});
  const pending=panel.load('old');await panel.load('new');
  assert.match(detail.innerHTML,/new/);rejectOld(Error('old failure'));await pending;
  assert.equal(container.innerHTML,'current panel');assert.match(detail.innerHTML,/new/);
});
