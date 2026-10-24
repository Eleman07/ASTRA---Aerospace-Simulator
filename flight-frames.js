/* Coordinate-system adapter for the atmosphere scene.
   Dynamics: NED X north, Y east, Z down; body X forward, Y right, Z down.
   WebGL: X north, Y up, Z east. Input angles use the aerospace 3-2-1 convention.
   Output is column-major and rotates an already level-aligned GLB. */
export function aircraftPoseMatrix(rollRad, pitchRad, headingRad) {
  for (const angle of [rollRad, pitchRad, headingRad]) {
    if (!Number.isFinite(angle)) throw new RangeError('Non-finite attitude');
  }
  const cp=Math.cos(rollRad), sp=Math.sin(rollRad);
  const ct=Math.cos(pitchRad), st=Math.sin(pitchRad);
  const cy=Math.cos(headingRad), sy=Math.sin(headingRad);
  const ned=[
    [ct*cy, sp*st*cy-cp*sy, cp*st*cy+sp*sy],
    [ct*sy, sp*st*sy+cp*cy, cp*st*sy-sp*cy],
    [-st, sp*ct, cp*ct]
  ];
  // C*NED*C^T where C maps (N,E,D)->(X,Z,-Y).
  const c=[[1,0,0],[0,0,-1],[0,1,0]];
  const multiply=(a,b)=>a.map(row=>b[0].map((_,j)=>row.reduce((sum,v,k)=>sum+v*b[k][j],0)));
  const transpose=a=>a[0].map((_,i)=>a.map(row=>row[i]));
  const world=multiply(multiply(c,ned),transpose(c));
  return new Float32Array([world[0][0],world[1][0],world[2][0],0,
    world[0][1],world[1][1],world[2][1],0,
    world[0][2],world[1][2],world[2][2],0,
    0,0,0,1]);
}
