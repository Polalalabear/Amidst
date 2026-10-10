import test from 'node:test';
import assert from 'node:assert/strict';
import {observationSamples,sampleVisible,bodyMarkers,invalidateVersionResults} from './motion.mjs';
const obs={observation_ref:'obs',local_track_ref:'local',origin:'SYNTHETIC',image_measurement:true,
  measurements:[{timestamp:0},{timestamp:.4},{timestamp:.8},{timestamp:3}],projected_path:[[0,0,0],[.4,0,0],[.8,0,0],[3,0,0]]};
test('tuple projections retain measurement clocks, absent positions remain absent',()=>{
  assert.equal(observationSamples(obs).length,4);
  assert.deepEqual(observationSamples({...obs,projected_path:[null]}),[]);
  assert.deepEqual(observationSamples({projected_path:[[1,2,0]]}),[]);
  assert.deepEqual(observationSamples({...obs,projected_path:[[1,2,0]]}),[]);
});
test('visual interpolation stops at observation gaps and never extrapolates',()=>{
  const samples=observationSamples(obs);
  assert.equal(sampleVisible(samples,-.1),null);assert.equal(sampleVisible(samples,4),null);
  assert.equal(sampleVisible(samples,2),null);
  assert.deepEqual(sampleVisible(samples,.2).world_position,[.2,0,0]);
  assert.equal(sampleVisible(samples,.4).interpolated,false);
});
test('every canonical alternative is retained and is never a confirmed identity',()=>{
  const event={trajectories:[1,2,3].map(n=>({hypothesis_id:'h'+n,candidate_id:'c'+n,
    timed_points:[{timestamp:1,world_position:[0,n,0]},{timestamp:2,world_position:[1,n,0]}]}))};
  const markers=bodyMarkers([obs],[event],1.5);assert.equal(markers.length,3);
  assert.ok(markers.every(m=>m.evidence_state==='INFERRED_GAP'&&m.identity_confirmed===false&&m.presentation_only));
  assert.equal(bodyMarkers([obs],[event],4).length,0);
});
test('publication invalidates both cached version-dependent result views',()=>{
  const state={test:{passed:true},evaluation:{},event:'immutable'};invalidateVersionResults(state);
  assert.equal(state.test,null);assert.equal(state.evaluation,null);assert.equal(state.event,'immutable');
});
