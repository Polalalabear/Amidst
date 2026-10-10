import * as THREE from '/vendor/three.module.js';
import {calibratedFrustum,planarPolygon} from './geometry.mjs';
import {bodyMarkers} from './motion.mjs';

const finitePoint = (point) => Array.isArray(point) && point.length >= 3 && point.slice(0,3).every(Number.isFinite);
const vector = (point) => new THREE.Vector3(...point.slice(0,3));
const COLORS = {REGION:0x9487d3,PORTAL:0xd49bd2,WALKABLE:0x65c6c0,CAMERA:0x82b9dc};
function boundsOf(snapshot, objects) {
  const bounds=snapshot.bounds;
  if(Array.isArray(bounds)&&bounds.length===4&&bounds.every(Number.isFinite))return [bounds[0],bounds[1],bounds[2],bounds[3]];
  if(Array.isArray(bounds)&&bounds.length===2&&bounds.every(finitePoint))return [bounds[0][0],bounds[0][1],bounds[1][0],bounds[1][1]];
  if(bounds?.min&&bounds?.max)return [bounds.min[0],bounds.min[1],bounds.max[0],bounds.max[1]];
  const points=objects.flatMap((item)=>item.geometry?.points??[]).filter(finitePoint);
  if(!points.length)return [-1,-1,1,1];
  return [Math.min(...points.map((p)=>p[0])),Math.min(...points.map((p)=>p[1])),Math.max(...points.map((p)=>p[0])),Math.max(...points.map((p)=>p[1]))];
}

export class SceneView {
  constructor(container,{snapshot,objects,event,events=[],observations=[],presentation=null,selectedId,pose,onSelect}) {
    this.container=container;this.snapshot=snapshot;this.onSelect=onSelect;this.disposed=false;this.pickables=[];this.event=event;
    this.scene=new THREE.Scene();this.scene.background=new THREE.Color(0x121927);
    this.events=events.length?events:[event].filter(Boolean);this.observations=observations;this.presentation=presentation;this.bodies=new THREE.Group();
    this.scene.add(this.bodies);this.bodyInstances=new Map();
    this.camera=new THREE.PerspectiveCamera(43,1,.01,10000);this.camera.up.set(0,0,1);
    this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'});
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));this.renderer.outputColorSpace=THREE.SRGBColorSpace;
    container.replaceChildren(this.renderer.domElement);
    this.bounds=boundsOf(snapshot,objects);const [x0,y0,x1,y1]=this.bounds;
    this.span=Math.max(x1-x0,y1-y0,2);this.center=new THREE.Vector3((x0+x1)/2,(y0+y1)/2,0);
    this.target=this.center.clone();this.yaw=-Math.PI/2.8;this.pitch=.77;this.distance=this.span*1.5;
    this.scene.add(new THREE.HemisphereLight(0xd6e6ff,0x222b45,2.2));
    const light=new THREE.DirectionalLight(0xcad9ff,2);light.position.set(0,-10,20);this.scene.add(light);
    const gridSize=Math.ceil(this.span*1.35);const grid=new THREE.GridHelper(gridSize,Math.min(gridSize*2,80),0x37445a,0x222f43);
    grid.rotation.x=Math.PI/2;grid.position.copy(this.center);grid.position.z=-.04;grid.material.transparent=true;grid.material.opacity=.6;this.scene.add(grid);
    this.addAxes();objects.forEach((object)=>this.addObject(object,object.object_id===selectedId));
    this.addSourceMeshes(presentation?.meshes??[]);
    this.addCalibratedCameras(objects.filter((object)=>object.kind==='CAMERA').map((object)=>({camera_id:object.object_id,position:object.geometry?.points?.[0]??null,properties:object.properties})));this.events.forEach(item=>this.addEvent(item));
    if(pose){this.target.fromArray(pose.target);this.yaw=pose.yaw;this.pitch=pose.pitch;this.distance=pose.distance;}
    this.updateCamera();this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(container);this.resize();
    this.pointerDown=this.onPointerDown.bind(this);this.pointerMove=this.onPointerMove.bind(this);this.pointerUp=this.onPointerUp.bind(this);this.wheel=this.onWheel.bind(this);this.contextMenu=(e)=>e.preventDefault();
    const canvas=this.renderer.domElement;canvas.addEventListener('pointerdown',this.pointerDown);canvas.addEventListener('pointermove',this.pointerMove);canvas.addEventListener('pointerup',this.pointerUp);canvas.addEventListener('pointercancel',this.pointerUp);canvas.addEventListener('wheel',this.wheel,{passive:false});canvas.addEventListener('contextmenu',this.contextMenu);
    this.render();
  }
  addAxes() {
    const origin=new THREE.Vector3(this.bounds[0],this.bounds[1],.02);const len=this.span*.08;
    [[new THREE.Vector3(1,0,0),0xc77589],[new THREE.Vector3(0,1,0),0x77bdac],[new THREE.Vector3(0,0,1),0x869ade]].forEach(([dir,color])=>this.scene.add(new THREE.ArrowHelper(dir,origin,len,color,len*.17,len*.07)));
  }
  addObject(object,selected) {
    const points=(object.geometry?.points??[]).filter(finitePoint);if(!points.length)return;
    const color=selected?0xe7dcff:COLORS[object.kind]??0x8d93b6;const vectors=points.map(vector);const group=new THREE.Group();group.userData.objectId=object.object_id;
    if(object.geometry.type==='polygon'&&points.length>=3){
      const polygon=planarPolygon(points);if(!polygon)return;
      const triangles=THREE.ShapeUtils.triangulateShape(polygon.projected.map((point)=>new THREE.Vector2(...point)),[]);
      const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(polygon.positions,3));geometry.setIndex(triangles.flat());geometry.computeVertexNormals();
      const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,transparent:true,opacity:selected?.29:.13,side:THREE.DoubleSide,depthWrite:false,roughness:1,polygonOffset:true,polygonOffsetFactor:1,polygonOffsetUnits:1}));
      mesh.userData.objectId=object.object_id;group.add(mesh);this.pickables.push(mesh);
      const line=new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(vectors),new THREE.LineBasicMaterial({color,transparent:true,opacity:selected?1:.75}));line.userData.objectId=object.object_id;group.add(line);this.pickables.push(line);
    }else if(vectors.length>1){
      const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(vectors),new THREE.LineBasicMaterial({color,linewidth:selected?3:2}));line.position.z=.035;line.userData.objectId=object.object_id;group.add(line);this.pickables.push(line);
      if(object.kind==='PORTAL'){vectors.forEach((p)=>{const dot=new THREE.Mesh(new THREE.SphereGeometry(this.span*.009,10,8),new THREE.MeshBasicMaterial({color}));dot.position.copy(p);dot.position.z+=.04;dot.userData.objectId=object.object_id;group.add(dot);this.pickables.push(dot);});}
    }else {
      const mesh=new THREE.Mesh(object.kind==='CAMERA'?new THREE.BoxGeometry(this.span*.025,this.span*.017,this.span*.017):new THREE.SphereGeometry(this.span*.012,12,8),new THREE.MeshStandardMaterial({color}));mesh.position.copy(vectors[0]);mesh.userData.objectId=object.object_id;group.add(mesh);this.pickables.push(mesh);
    }
    group.traverse((child)=>{child.userData.pickPriority=({CAMERA:0,PORTAL:1,REGION:2,WALKABLE:3})[object.kind]??4;});this.scene.add(group);
  }
  addCalibratedCameras(cameras) {
    for(const camera of cameras){
      if(!finitePoint(camera.position))continue;
      const p=vector(camera.position);
      // Frusta require explicit calibrated camera-to-world matrices. Unknown affine poses stay absent.
      const converted=calibratedFrustum(camera.properties,this.span*.13);
      // Unsupported conventions intentionally have no frustum; camera markers remain selectable.
      if(!converted)continue;
      const corners=converted.map(vector);
      const segments=[];for(let i=0;i<4;i++){segments.push(p,corners[i],corners[i],corners[(i+1)%4]);}
      this.scene.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(segments),new THREE.LineBasicMaterial({color:0x78c1c4,transparent:true,opacity:.38})));
    }
  }
  addEvent(event) {
    if(!event)return;
    const detail=event.detail??event;const projected=detail.projected_path??event.projected_path??[];
    this.projected=projected.filter((point)=>finitePoint(point.world_position));
    for(const point of this.projected){const marker=new THREE.Mesh(new THREE.SphereGeometry(this.span*.009,10,8),new THREE.MeshBasicMaterial({color:0xc4e6e2}));marker.position.copy(vector(point.world_position));marker.position.z+=.08;this.scene.add(marker);}
    const candidates=detail.candidates??event.candidates??[];
    candidates.forEach((candidate,index)=>{
      const points=(candidate.polyline??[]).filter(finitePoint).map(vector);if(points.length<2)return;
      const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineDashedMaterial({color:[0xddbc83,0xa59ce0,0x70bdb5,0xc996bf][index%4],dashSize:this.span*.025,gapSize:this.span*.015,transparent:true,opacity:.8,depthTest:false}));line.position.z=.09+index*.006;line.renderOrder=5;line.computeLineDistances();this.scene.add(line);
    });
    if(this.projected.length){this.timeMarker=new THREE.Mesh(new THREE.SphereGeometry(this.span*.018,14,10),new THREE.MeshBasicMaterial({color:0x80eadb}));this.timeMarker.position.copy(vector(this.projected[0].world_position));this.timeMarker.position.z+=.1;this.scene.add(this.timeMarker);}
  }
  addSourceMeshes(meshes) {
    for(const source of meshes){
      if(!Array.isArray(source.vertices)||!Array.isArray(source.triangles))continue;
      if(!source.vertices.every(finitePoint))continue;
      const indices=source.triangles.flat();
      if(indices.some(i=>!Number.isInteger(i)||i<0||i>=source.vertices.length))continue;
      const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(source.vertices.flat(),3));
      geometry.setIndex(indices);geometry.computeVertexNormals();
      const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:0x71838b,roughness:.9,side:THREE.DoubleSide,transparent:true,opacity:.62}));
      this.scene.add(mesh);
      const edges=new THREE.LineSegments(new THREE.EdgesGeometry(geometry,25),new THREE.LineBasicMaterial({color:0xa7bec9,transparent:true,opacity:.18}));this.scene.add(edges);
    }
  }
  makeBody(inferred) {
    const root=new THREE.Group(),color=inferred?0xffc266:0x63dfdd;
    const material=new THREE.MeshStandardMaterial({color,roughness:.5,transparent:inferred,opacity:inferred?.62:1});
    const sphere=(radius,z)=>{const mesh=new THREE.Mesh(new THREE.SphereGeometry(radius,12,8),material);mesh.position.z=z;root.add(mesh);return mesh;};
    sphere(.11,1.58);sphere(.13,.84);
    const torso=new THREE.Mesh(new THREE.CapsuleGeometry(.14,.38,4,10),material);torso.rotation.x=Math.PI/2;torso.position.z=1.14;root.add(torso);
    const limb=(x,z,length,radius)=>{const pivot=new THREE.Group();pivot.position.set(x,0,z);const mesh=new THREE.Mesh(new THREE.CapsuleGeometry(radius,length,3,8),material);mesh.rotation.x=Math.PI/2;mesh.position.z=-length/2; pivot.add(mesh);root.add(pivot);return pivot;};
    root.userData.legs=[limb(-.09,.79,.68,.055),limb(.09,.79,.68,.055)];
    root.userData.arms=[limb(-.22,1.33,.49,.045),limb(.22,1.33,.49,.045)];
    const ring=new THREE.Mesh(new THREE.RingGeometry(.24,.27,24),new THREE.MeshBasicMaterial({color,transparent:true,opacity:.55,side:THREE.DoubleSide}));ring.position.z=.015;root.add(ring);
    return root;
  }
  updateBodies(timestamp) {
    let markers=bodyMarkers(this.observations,this.events,timestamp);
    if(this.presentation?.frames?.length){
      const frames=this.presentation.frames;const step=this.presentation.frame_step_s??.2;
      const frame=frames.slice().sort((a,b)=>Math.abs(a.timestamp-timestamp)-Math.abs(b.timestamp-timestamp))[0];
      if(frame&&Math.abs(frame.timestamp-timestamp)<=step/2+.00001)markers=[{ref:'source-display-body',world_position:frame.world_position,
        evidence_state:frame.evidence_state,joint_pose_authority:'DISPLAY_ONLY',presentation_only:true}];
    }
    const active=new Set();
    for(const marker of markers){
      if(!finitePoint(marker.world_position))continue;
      const inferred=marker.evidence_state==='INFERRED_GAP',key=marker.ref+':'+inferred;
      active.add(key);let body=this.bodyInstances.get(key);
      if(!body){body=this.makeBody(inferred);this.bodies.add(body);this.bodyInstances.set(key,body);}
      body.visible=true;body.position.copy(vector(marker.world_position));
      // Gait and anatomy are schematic presentation, never image-measured pose.
      const previous=body.userData.previous;
      const moved=previous?Math.hypot(marker.world_position[0]-previous[0],marker.world_position[1]-previous[1]):0;
      if(moved>.0001)body.rotation.z=Math.atan2(-(marker.world_position[0]-previous[0]),marker.world_position[1]-previous[1]);
      if(moved>.0001)body.userData.movingUntil=timestamp+.25;
      const phase=Math.sin(timestamp*7),swing=timestamp<=(body.userData.movingUntil??-1)?phase*.24:0;
      body.userData.legs.forEach((limb,i)=>limb.rotation.x=swing*(i?1:-1));
      body.userData.arms.forEach((limb,i)=>limb.rotation.x=swing*(i?-1:1));
      body.userData.previous=[...marker.world_position];
    }
    for(const [key,body] of this.bodyInstances)body.visible=active.has(key);
  }
  setTimestamp(timestamp){
    this.updateBodies(timestamp);
    if(!this.timeMarker||!this.projected?.length){this.render();return;}
    const eligible=this.projected.filter((point)=>Number.isFinite(point.timestamp)&&Math.abs(point.timestamp-timestamp)<=.6);
    this.timeMarker.visible=eligible.length>0;
    if(eligible.length){eligible.sort((a,b)=>Math.abs(a.timestamp-timestamp)-Math.abs(b.timestamp-timestamp));this.timeMarker.position.copy(vector(eligible[0].world_position));this.timeMarker.position.z+=.1;}
    this.render();
  }
  updateCamera(){this.camera.position.set(this.target.x+this.distance*Math.cos(this.pitch)*Math.cos(this.yaw),this.target.y+this.distance*Math.cos(this.pitch)*Math.sin(this.yaw),this.target.z+this.distance*Math.sin(this.pitch));this.camera.lookAt(this.target);}
  resize(){if(this.disposed)return;const w=this.container.clientWidth,h=this.container.clientHeight;if(!w||!h)return;this.renderer.setSize(w,h,false);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.render();}
  render(){if(!this.disposed)this.renderer.render(this.scene,this.camera);}
  getPose(){return {target:this.target.toArray(),yaw:this.yaw,pitch:this.pitch,distance:this.distance};}
  reset(){this.target.copy(this.center);this.yaw=-Math.PI/2.8;this.pitch=.77;this.distance=this.span*1.5;this.updateCamera();this.render();}
  onPointerDown(e){this.drag={x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY,pan:e.button!==0||e.shiftKey};this.renderer.domElement.setPointerCapture(e.pointerId);}
  onPointerMove(e){if(!this.drag)return;const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;this.drag.x=e.clientX;this.drag.y=e.clientY;if(this.drag.pan){const scale=this.distance/Math.max(this.container.clientHeight,1)*.9;const right=new THREE.Vector3(-Math.sin(this.yaw),Math.cos(this.yaw),0);const forward=new THREE.Vector3(Math.cos(this.yaw),Math.sin(this.yaw),0);this.target.addScaledVector(right,-dx*scale).addScaledVector(forward,dy*scale);}else{this.yaw-=dx*.006;this.pitch=Math.max(.08,Math.min(1.48,this.pitch+dy*.006));}this.updateCamera();this.render();}
  onPointerUp(e){if(!this.drag)return;const moved=Math.hypot(e.clientX-this.drag.startX,e.clientY-this.drag.startY);const pan=this.drag.pan;this.drag=null;if(moved>5||pan)return;const rect=this.renderer.domElement.getBoundingClientRect();const cursor=new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);const raycaster=new THREE.Raycaster();raycaster.params.Line.threshold=this.span*.012;raycaster.setFromCamera(cursor,this.camera);const hits=raycaster.intersectObjects(this.pickables,false);hits.sort((a,b)=>(a.object.userData.pickPriority??4)-(b.object.userData.pickPriority??4)||a.distance-b.distance);if(hits.length)this.onSelect(hits[0].object.userData.objectId);}
  onWheel(e){e.preventDefault();this.distance=Math.max(this.span*.15,Math.min(this.span*8,this.distance*Math.exp(e.deltaY*.001)));this.updateCamera();this.render();}
  dispose(){if(this.disposed)return;this.disposed=true;this.resizeObserver.disconnect();const canvas=this.renderer.domElement;canvas.removeEventListener('pointerdown',this.pointerDown);canvas.removeEventListener('pointermove',this.pointerMove);canvas.removeEventListener('pointerup',this.pointerUp);canvas.removeEventListener('pointercancel',this.pointerUp);canvas.removeEventListener('wheel',this.wheel);canvas.removeEventListener('contextmenu',this.contextMenu);this.scene.traverse((obj)=>{obj.geometry?.dispose();if(Array.isArray(obj.material))obj.material.forEach((m)=>m.dispose());else obj.material?.dispose();});this.renderer.dispose();this.renderer.forceContextLoss();}
}
