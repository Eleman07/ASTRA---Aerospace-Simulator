import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseGlb} from '../vehicle-glb.js';
const files=['sls-block1-high.glb','innerscene-propeller-aircraft-high.glb','quadrotor-innerscene.glb','sls-orion-spacecraft.glb'];
for(const name of files){
 const bytes=readFileSync(new URL('../assets/vehicles/'+name,import.meta.url));
 const parsed=parseGlb(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),{maxTriangles:800000,maxPrimitives:500,maxVertices:2000000});
 assert.ok(parsed.triangles>0);
 for(const {material:m} of parsed.primitives){
  assert.ok((m.metallicFactor??0)>=0&&(m.metallicFactor??0)<=1);
  assert.ok((m.roughnessFactor??1)>=0&&(m.roughnessFactor??1)<=1);
  if(m.metalRoughTextureIndex!=null)assert.ok(parsed.images[m.metalRoughTextureIndex]);
 }
 console.log(name,parsed.triangles,'triangles',parsed.primitives.length,'primitives: PASS');
}
// One triangle + custom PBR material makes propagation of glTF factors observable.
const geometry=new Float32Array([0,0,0,1,0,0,0,1,0]);
function fixture(material){
 const doc={asset:{version:'2.0'},buffers:[{byteLength:36}],bufferViews:[{buffer:0,byteLength:36}],accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3'}],materials:[material],meshes:[{primitives:[{attributes:{POSITION:0},material:0}]}],nodes:[{mesh:0}],scenes:[{nodes:[0]}],scene:0};
 let json=JSON.stringify(doc);while(json.length%4)json+=' ';
 const output=new ArrayBuffer(12+8+json.length+8+36),v=new DataView(output);
 v.setUint32(0,0x46546c67,true);v.setUint32(4,2,true);v.setUint32(8,output.byteLength,true);
 v.setUint32(12,json.length,true);v.setUint32(16,0x4e4f534a,true);new Uint8Array(output,20,json.length).set(new TextEncoder().encode(json));
 v.setUint32(20+json.length,36,true);v.setUint32(24+json.length,0x004e4942,true);new Uint8Array(output,28+json.length).set(new Uint8Array(geometry.buffer));return output;
}
const m=parseGlb(fixture({pbrMetallicRoughness:{metallicFactor:.65,roughnessFactor:.23},emissiveFactor:[.1,.2,.3]})).primitives[0].material;
assert.equal(m.metallicFactor,.65);assert.equal(m.roughnessFactor,.23);assert.deepEqual(m.emissiveFactor,[.1,.2,.3]);
assert.throws(()=>parseGlb(fixture({pbrMetallicRoughness:{metallicRoughnessTexture:{index:7}}})),/metallic\/roughness/);
console.log('PBR factor propagation and invalid texture rejection: PASS');
