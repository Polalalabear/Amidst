/** Display-only bodies from actual projected samples and canonical alternatives. */
import {sampleCanonicalTrajectory} from '../product/timeline.mjs';

export const finitePosition = p => Array.isArray(p) && p.length === 3 && p.every(Number.isFinite);
export function observationSamples(observation) {
  const path=observation?.projected_path??[], measurements=observation?.measurements??[];
  if(path.some(Array.isArray)&&path.length!==measurements.length)return [];
  return path.map((point,index)=>({timestamp:point?.timestamp??measurements[index]?.timestamp,
    world_position:Array.isArray(point)?point:point?.world_position,provenance:'PROJECTED'}))
    .filter(p=>Number.isFinite(p.timestamp)&&finitePosition(p.world_position))
    .sort((a,b)=>a.timestamp-b.timestamp);
}
export function sampleVisible(points,timestamp) {
  if(!Number.isFinite(timestamp)||!points.length||timestamp<points[0].timestamp||timestamp>points.at(-1).timestamp)return null;
  const exact=points.find(p=>p.timestamp===timestamp);
  if(exact)return {...exact,world_position:[...exact.world_position],interpolated:false,presentation_only:true};
  const i=points.findIndex(p=>p.timestamp>timestamp),a=points[i-1],b=points[i];
  const steps=points.slice(1).map((p,j)=>p.timestamp-points[j].timestamp).filter(dt=>dt>0);
  const maxGap=Math.min(...steps)*1.51;
  if(!a||!b||b.timestamp-a.timestamp>maxGap)return null;
  const ratio=(timestamp-a.timestamp)/(b.timestamp-a.timestamp);
  return {timestamp,world_position:a.world_position.map((v,j)=>v+ratio*(b.world_position[j]-v)),
    provenance:'PROJECTED',interpolated:true,presentation_only:true};
}
export function bodyMarkers(observations,events,timestamp) {
  const visible=observations.flatMap(observation=>{
    const points=observationSamples(observation),sample=sampleVisible(points,timestamp);
    if(!sample)return [];
    return [{...sample,ref:observation.local_track_ref??observation.observation_ref,
      evidence_state:'PROJECTED',origin:observation.origin,image_measurement:observation.image_measurement,
      joint_pose_authority:'DISPLAY_ONLY'}];
  });
  const alternatives=events.flatMap(event=>((event?.detail??event)?.trajectories??[]).flatMap(hypothesis=>{
    const sample=sampleCanonicalTrajectory(hypothesis,timestamp);
    if(!sample||!finitePosition(sample.world_position))return [];
    // A gap endpoint is still a provisional hypothesis marker, never a resolved person.
    return [{...sample,ref:`${event.event_ref}:${hypothesis.hypothesis_id}`,evidence_state:sample.provenance,
      joint_pose_authority:'DISPLAY_ONLY',identity_confirmed:false}];
  }));
  return [...visible,...alternatives];
}
export function serverBodyMarkers(markers){
  return markers.filter(marker=>typeof marker.marker_ref==='string'&&finitePosition(marker.world_position)
    &&['PROJECTED','INFERRED_GAP'].includes(marker.evidence_state)).map(marker=>({...marker,
      world_position:[...marker.world_position],ref:marker.marker_ref,joint_pose_authority:'DISPLAY_ONLY',
      presentation_only:true,identity_confirmed:false}));
}
export function invalidateVersionResults(target) {
  target.test=null;target.evaluation=null;
}
