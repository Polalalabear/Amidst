import test from 'node:test';
import assert from 'node:assert/strict';
import {escapeHTML, normalizeRange, eventLabel, evidenceLabel, changesForObject, eventMediaFrames, frameTimeLabel, invalidateEventState, eventRequestIsCurrent} from './app.mjs';

test('untrusted source fields cannot become HTML markup',()=>{
  assert.equal(escapeHTML('<img src=x onerror="bad()">'), '&lt;img src=x onerror=&quot;bad()&quot;&gt;');
});
test('both scene range contracts normalize and invalid ranges fail closed',()=>{
  assert.deepEqual(normalizeRange([2,14]),[2,14]);
  assert.deepEqual(normalizeRange({start:1,end:12}),[1,12]);
  assert.deepEqual(normalizeRange([9,2]),[0,0]);
  assert.deepEqual(normalizeRange([0,Infinity]),[0,0]);
});
test('provisional event wording preserves uncertainty',()=>{
  assert.equal(eventLabel('POSSIBLE_LOITERING'),'可能遊蕩');
  assert.equal(eventLabel('INFERRED_GAP_ALTERNATIVES'),'盲區路線候選');
});
test('draft changes retain original properties and only change edited values',()=>{
  const object={label:'西側門',semantic:'PORTAL',properties:{intrinsics:{fx:500,fy:500,cx:320,cy:240},source:'preserved'}};
  const changes=changesForObject(object,{label:'西側門',semantic:'ENTRY',intrinsic_fx:'510'});
  assert.deepEqual(changes,{semantic:'ENTRY',properties:{intrinsics:{fx:510,fy:500,cx:320,cy:240},source:'preserved'}});
  assert.equal(object.properties.intrinsics.fx,500);
});
test('malformed geometry cannot be submitted as a review draft',()=>{
  assert.throws(()=>changesForObject({}, {geometry:'{"type":"polygon","points":[[1,2]]}'}),/三個有效數字/);
  assert.throws(()=>changesForObject({}, {geometry:'not json'}),/JSON/);
  assert.deepEqual(changesForObject({label:'A'},{label:'A'}),{});
});
test('event media joins exact frame refs despite metadata order and repeated cameras',()=>{
  const frames=eventMediaFrames({
    media_refs:['a','b','c'],camera_ids:['WEST','DOOR'],
    source_frames:[
      {frame_ref:'c',camera_id:'DOOR',timestamp:9.2},
      {frame_ref:'a',camera_id:'DOOR',timestamp:8.4},
      {frame_ref:'b',camera_id:'WEST',timestamp:8.8},
    ],
  });
  assert.deepEqual(frames,[
    {media_ref:'a',camera_id:'DOOR',timestamp:8.4},
    {media_ref:'b',camera_id:'WEST',timestamp:8.8},
    {media_ref:'c',camera_id:'DOOR',timestamp:9.2},
  ]);
});
test('missing source metadata stays unknown instead of guessing camera or zero time',()=>{
  const frames=eventMediaFrames({media_refs:['a','missing','zero'],camera_ids:['WEST'],source_frames:[
    {frame_ref:'a',camera_id:'DOOR',timestamp:null},
    {frame_ref:'zero',camera_id:'WEST',timestamp:0},
  ]});
  assert.deepEqual(frames,[
    {media_ref:'a',camera_id:'DOOR',timestamp:null},
    {media_ref:'missing',camera_id:null,timestamp:null},
    {media_ref:'zero',camera_id:'WEST',timestamp:0},
  ]);
  assert.equal(frameTimeLabel(frames[0].timestamp),'時間未知');
  assert.equal(frameTimeLabel(frames[1].timestamp),'時間未知');
  assert.equal(frameTimeLabel(frames[2].timestamp),'0.0 s');
  assert.equal(frameTimeLabel(undefined),'時間未知');
});
test('management evidence status uses concise labels while research keeps diagnostics',()=>{
  assert.equal(evidenceLabel('INFERRED_GAP'),'盲區推論');
  assert.equal(evidenceLabel('PROJECTED'),'可見投影');
  assert.equal(evidenceLabel('INTERNAL_NEW_ENUM'),'候選事件 · 待檢視');
  assert.equal(evidenceLabel('INTERNAL_NEW_ENUM',true),'INTERNAL_NEW_ENUM');
});
test('late event and note responses cannot overwrite a newer selection in the same scene',async()=>{
  const target={sceneEpoch:3,eventEpoch:0,selectedEvent:null,event:null,notes:[]};
  const pending=[];
  const request=(ref,kind)=>{
    const ticket={sceneEpoch:target.sceneEpoch,eventEpoch:target.eventEpoch,eventRef:ref};
    return new Promise((resolve)=>pending.push(resolve)).then((data)=>{
      if(eventRequestIsCurrent(target,ticket)){
        if(kind==='note')target.notes.push(data);else target.event=data;
      }
    });
  };
  invalidateEventState(target);target.selectedEvent='A';
  const oldEvent=request('A','event'),oldNote=request('A','note');
  invalidateEventState(target);target.selectedEvent='B';
  const newEvent=request('B','event');
  pending[2]({event_ref:'B'});await newEvent;
  pending[0]({event_ref:'A'});pending[1]({note:'Only belongs to A'});
  await Promise.all([oldEvent,oldNote]);
  assert.deepEqual(target.event,{event_ref:'B'});assert.deepEqual(target.notes,[]);
});
test('object selection and query invalidation reject old responses even after selecting the same ref again',()=>{
  const target={sceneEpoch:4,eventEpoch:9,selectedEvent:'A',event:{event_ref:'A'},notes:[{note:'old'}]};
  const ticket={sceneEpoch:4,eventEpoch:9,eventRef:'A'};
  invalidateEventState(target);
  assert.equal(target.event,null);assert.deepEqual(target.notes,[]);assert.equal(target.selectedEvent,null);
  target.selectedEvent='A';
  assert.equal(eventRequestIsCurrent(target,ticket),false);
  assert.equal(eventRequestIsCurrent({...target,sceneEpoch:5},{...ticket,eventEpoch:target.eventEpoch}),false);
});
