/* Deterministic shader checks in a separate, network-isolated browser. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const assert=require('node:assert/strict');
async function main(){
 const root=path.resolve(__dirname,'..'),output=path.join(root,'test-results');
 const shader=await import(pathToFileURL(path.join(root,'nebula-rendering.js')).href);
 const noise=shader.makeNebulaNoiseData();
 assert.deepEqual(noise,shader.makeNebulaNoiseData());
 assert.notDeepEqual(noise,shader.makeNebulaNoiseData(64,13));
 const browser=await chromium.launch({headless:true,channel:process.env.ASTRA_BROWSER_CHANNEL||undefined,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const context=await browser.newContext({viewport:{width:1000,height:620}});
  const external=[];await context.route('**/*',route=>{external.push(route.request().url());return route.abort();});
  const page=await context.newPage();
  await page.setContent('<html><body style="margin:0;background:#02050b"><canvas width="960" height="540" style="width:960px;height:540px"></canvas></body></html>');
  const result=await page.evaluate(({vs,fs,noise})=>{
   const canvas=document.querySelector('canvas'),g=canvas.getContext('webgl2',{preserveDrawingBuffer:true,antialias:false});
   if(!g)throw Error('WebGL2 unavailable');
   const compile=(type,source)=>{const s=g.createShader(type);g.shaderSource(s,source);g.compileShader(s);if(!g.getShaderParameter(s,g.COMPILE_STATUS))throw Error(g.getShaderInfoLog(s));return s;};
   // Preview uses the same HDR-to-display curve as the current app. The shader
   // itself remains linear; this wrapper is only a screenshot display target.
   const display=fs.replace('frag=vec4(sky+solar,1.);','vec3 x=sky+solar;vec3 y=clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);frag=vec4(pow(y,vec3(1./2.2)),1.);');
   const p=g.createProgram();g.attachShader(p,compile(g.VERTEX_SHADER,vs));g.attachShader(p,compile(g.FRAGMENT_SHADER,display));g.linkProgram(p);if(!g.getProgramParameter(p,g.LINK_STATUS))throw Error(g.getProgramInfoLog(p));g.useProgram(p);
   const u=n=>g.getUniformLocation(p,n);
   for(const[name,value]of[['uRight',[1,0,0]],['uUp',[0,1,0]],['uForward',[0,0,-1]],['uAtmosphereUp',[0,1,0]],['uAtmosphereEast',[1,0,0]],['uAtmosphereNorth',[0,0,1]],['uSunDirection',[0,-1,0]]])g.uniform3fv(u(name),value);
   g.uniformMatrix3fv(u('uSkyRotation'),false,[1,0,0,0,1,0,0,0,1]);g.uniform1f(u('uAspect'),960/540);g.uniform1f(u('uTanHalfFov'),.9);g.uniform1f(u('uTransition'),1);
   for(const[name,unit]of[['uAirTex',0],['uSpaceTex',1]]){g.activeTexture(g.TEXTURE0+unit);const t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);g.texImage2D(g.TEXTURE_2D,0,g.RGBA,1,1,0,g.RGBA,g.UNSIGNED_BYTE,new Uint8Array([24,29,39,255]));g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.LINEAR);g.uniform1i(u(name),unit);}
   g.activeTexture(g.TEXTURE2);const volume=g.createTexture();g.bindTexture(g.TEXTURE_3D,volume);g.texImage3D(g.TEXTURE_3D,0,g.RGBA8,64,64,64,0,g.RGBA,g.UNSIGNED_BYTE,new Uint8Array(noise));g.generateMipmap(g.TEXTURE_3D);g.texParameteri(g.TEXTURE_3D,g.TEXTURE_MIN_FILTER,g.LINEAR_MIPMAP_LINEAR);g.texParameteri(g.TEXTURE_3D,g.TEXTURE_MAG_FILTER,g.LINEAR);g.uniform1i(u('uNebulaNoise'),2);
   const render=(steps,strength)=>{g.uniform1i(u('uNebulaSteps'),steps);g.uniform1f(u('uNebulaStrength'),strength);g.drawArrays(g.TRIANGLES,0,3);const pixels=new Uint8Array(960*540*4);g.readPixels(0,0,960,540,g.RGBA,g.UNSIGNED_BYTE,pixels);return pixels;};
   const low=render(0,.9),zero=render(10,0),high=render(7,.9),repeat=render(7,.9);
   let identity=true,deterministic=true,maxDelta=0,changed=0;
   for(let i=0;i<high.length;i+=4)for(let c=0;c<3;c++){identity&&=low[i+c]===zero[i+c];deterministic&&=high[i+c]===repeat[i+c];const d=Math.abs(high[i+c]-low[i+c]);maxDelta=Math.max(d,maxDelta);if(d>2)changed++;}
   return{identityAtZeroStrength:identity,deterministic,maximumChannelChange:maxDelta,changedChannels:changed,glError:g.getError(),noiseBytes:noise.length};
  },{vs:shader.skyVertexShader,fs:shader.skyFragmentShader,noise:Array.from(noise)});
  assert(result.identityAtZeroStrength);assert(result.deterministic);assert(result.maximumChannelChange>5);assert(result.changedChannels>500);assert.equal(result.glError,0);assert.deepEqual(external,[]);
  fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'nebula-shader-preview.png')});fs.writeFileSync(path.join(output,'nebula-shader.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
