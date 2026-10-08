import test from 'node:test';
import assert from 'node:assert/strict';
import {ShapeUtils,Vector2} from 'three';
import {calibratedPixelPoint,calibratedFrustum,planarPolygon} from './geometry.mjs';

const identity=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]];
const calibration={calibration_kind:'PINHOLE',convention:'BLENDER_NEG_Z_UP_Y',fx:500,fy:480,cx:320,cy:240,width:640,height:480,camera_to_world:identity};
const close=(actual,expected,tolerance=1e-9)=>actual.forEach((value,index)=>assert.ok(Math.abs(value-expected[index])<tolerance,`${actual} != ${expected}`));
function project(point,k){
  // Independent rigid-transform inverse + Blender forward projection.
  const m=k.camera_to_world,relative=point.map((value,index)=>value-m[index][3]);
  const local=[0,1,2].map((column)=>relative.reduce((sum,value,row)=>sum+m[row][column]*value,0));
  assert.ok(local[2]<0,'a visible point must lie along the negative camera Z axis');
  return [k.fx*local[0]/-local[2]+k.cx,k.cy-k.fy*local[1]/-local[2]];
}
test('Blender center/corner rays roundtrip without flipping depth or image Y',()=>{
  const pixels=[[320,240],[0,0],[640,0],[640,480],[0,480]];
  for(const pixel of pixels)close(project(calibratedPixelPoint(calibration,pixel,3),calibration),pixel);
  close(calibratedPixelPoint(calibration,[320,240],3),[0,0,-3]);
  const topLeft=calibratedFrustum(calibration,3)[0];
  assert.ok(topLeft[0]<0&&topLeft[1]>0&&topLeft[2]<0);
});
test('translated and rotated camera poses retain pixel projection roundtrips',()=>{
  const translated={...calibration,camera_to_world:[[0,0,1,10],[1,0,0,-4],[0,1,0,8],[0,0,0,1]]};
  for(const pixel of [[320,240],[0,0],[640,480],[500,111]])close(project(calibratedPixelPoint(translated,pixel,2.7),translated),pixel);
  close(calibratedPixelPoint(translated,[320,240],2),[8,-4,8]);
});
test('unsupported camera conventions have no rendered frustum',()=>{
  assert.equal(calibratedFrustum({...calibration,convention:'OPENCV'},2),null);
  assert.equal(calibratedFrustum({...calibration,convention:undefined},2),null);
  assert.equal(calibratedFrustum({...calibration,fx:0},2),null);
});
function triangulatedArea(points){
  const data=planarPolygon(points);
  assert.deepEqual(data.positions,points.flat(),'rendered vertices must preserve original XYZ');
  const triangles=ShapeUtils.triangulateShape(data.projected.map((p)=>new Vector2(...p)),[]);
  assert.equal(triangles.length,points.length-2);
  let area=0;
  for(const [a,b,c] of triangles){
    const ab=points[b].map((value,index)=>value-points[a][index]),ac=points[c].map((value,index)=>value-points[a][index]);
    const cross=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]];
    area+=Math.hypot(...cross)/2;
  }
  return {area,data};
}
test('vertical polygon triangulates in YZ while preserving its constant X and varying Z',()=>{
  const {area,data}=triangulatedArea([[5,0,0],[5,3,0],[5,3,4],[5,0,4]]);
  assert.equal(data.dropAxis,0);assert.equal(area,12);
});
test('tilted concave polygon preserves 3D surface area and nonflat Z coordinates',()=>{
  const points=[[0,0,0],[2,0,2],[2,2,4],[1,1,2],[0,2,2]];
  const {area}=triangulatedArea(points);
  assert.ok(Math.abs(area-3*Math.sqrt(3))<1e-9);
  assert.deepEqual(planarPolygon(points).positions.filter((_,index)=>index%3===2),[0,2,4,2,2]);
});
