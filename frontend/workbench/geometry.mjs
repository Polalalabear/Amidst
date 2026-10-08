// Pure geometry conversions shared by the renderer and numerical regression tests.
const finitePoint = (point) => Array.isArray(point) && point.length === 3 && point.every(Number.isFinite);

export function calibratedPixelPoint(calibration, pixel, depth) {
  const k=calibration??{},matrix=k.camera_to_world;
  if(k.calibration_kind!=='PINHOLE'||k.convention!=='BLENDER_NEG_Z_UP_Y')return null;
  if(!Array.isArray(matrix)||matrix.length!==4||!matrix.every((row)=>Array.isArray(row)&&row.length===4&&row.every(Number.isFinite)))return null;
  if(![k.fx,k.fy,k.cx,k.cy,depth,...pixel].every(Number.isFinite)||k.fx<=0||k.fy<=0||depth<=0)return null;
  const [u,v]=pixel;
  const local=[(u-k.cx)/k.fx*depth,-(v-k.cy)/k.fy*depth,-depth,1];
  const transformed=matrix.map((row)=>row.reduce((sum,value,index)=>sum+value*local[index],0));
  if(!transformed.every(Number.isFinite)||Math.abs(transformed[3])<1e-12)return null;
  return transformed.slice(0,3).map((value)=>value/transformed[3]);
}

export function calibratedFrustum(calibration,depth) {
  if(!Number.isFinite(calibration?.width)||!Number.isFinite(calibration?.height)||calibration.width<=0||calibration.height<=0)return null;
  const corners=[[0,0],[calibration.width,0],[calibration.width,calibration.height],[0,calibration.height]].map((pixel)=>calibratedPixelPoint(calibration,pixel,depth));
  return corners.every((point)=>point!==null)?corners:null;
}

export function planarPolygon(points) {
  if(!Array.isArray(points)||points.length<3||!points.every(finitePoint))return null;
  // Newell's normal remains stable for vertical/tilted contours; triangulate only
  // on its dominant projection and retain the original XYZ for every vertex.
  const normal=[0,0,0];
  for(let i=0;i<points.length;i++){
    const a=points[i],b=points[(i+1)%points.length];
    normal[0]+=(a[1]-b[1])*(a[2]+b[2]);
    normal[1]+=(a[2]-b[2])*(a[0]+b[0]);
    normal[2]+=(a[0]-b[0])*(a[1]+b[1]);
  }
  const magnitude=Math.hypot(...normal);
  if(magnitude<1e-12)return null;
  const unit=normal.map((value)=>value/magnitude);
  const dropAxis=normal.map(Math.abs).indexOf(Math.max(...normal.map(Math.abs)));
  const axes=[0,1,2].filter((axis)=>axis!==dropAxis);
  return {
    positions:points.flat(),
    projected:points.map((point)=>axes.map((axis)=>point[axis])),
    normal:unit,
    dropAxis,
  };
}
