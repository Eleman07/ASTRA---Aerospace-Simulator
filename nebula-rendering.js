/* Distant synthetic nebula in Galactic coordinates. Emission/extinction are
   artistic relative radiance, not a calibrated survey or local flight medium.
   Static in time: travelling metres must not move clouds light-years away. */
export const skyVertexShader=`#version 300 es
out vec2 vUv;void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);vUv=p;gl_Position=vec4(p*2.-1.,1.,1.);}`;

export const skyFragmentShader=`#version 300 es
precision highp float;
precision highp sampler3D;
in vec2 vUv;
uniform sampler2D uAirTex,uSpaceTex;
uniform sampler3D uNebulaNoise;
uniform mat3 uSkyRotation;
uniform vec3 uRight,uUp,uForward,uAtmosphereUp,uAtmosphereEast,uAtmosphereNorth,uSunDirection;
uniform float uAspect,uTanHalfFov,uTransition,uNebulaStrength;
uniform int uNebulaSteps;
out vec4 frag;
const float PI=3.141592653589793;
vec3 decode(vec3 c){return mix(c/12.92,pow((c+.055)/1.055,vec3(2.4)),step(vec3(.04045),c));}
float field(vec3 p,float lod){return textureLod(uNebulaNoise,p*.03125,lod).r*.58+textureLod(uNebulaNoise,p*.0625,lod).g*.28+textureLod(uNebulaNoise,p*.125,lod).b*.14;}
vec3 nebulaRadiance(vec3 direction,vec3 background,float footprint){
 if(uNebulaSteps==0||uNebulaStrength<=0.)return background;
 // Angular domain is seamless at both panorama edges and poles.
 float band=exp(-pow(abs(direction.y+.06)*4.8,2.));
 float lobe=exp(-pow((direction.x+.42)*2.4,2.)-pow((direction.y-.12)*5.,2.));
 float mask=max(band*.75,lobe*.65);
 if(mask<.006)return background;
 float ds=9./float(uNebulaSteps);
 vec3 radiance=vec3(0),transmittance=vec3(1);
 // Pixel footprint controls volume noise filtering, not random frame jitter.
 float lod=clamp(log2(max(footprint*64.*9.,1.)),0.,4.);
 for(int i=0;i<10;i++){
  if(i>=uNebulaSteps)break;
  vec3 p=direction*(1.5+(float(i)+.5)*ds)+vec3(11.7,4.2,-8.3);
  vec3 warp=textureLod(uNebulaNoise,p*.009,lod).gba*2.-1.;
  float broad=field(p*.55+warp*.7,lod);
  float fine=field(p*1.85+warp*1.2,lod);
  float ridge=pow(max(0.,1.-abs(fine*2.-1.)),5.);
  float gas=smoothstep(.38,.72,broad)*ridge*mask;
  float dust=smoothstep(.48,.72,field(p*.85+vec3(9,3,17),lod))*mask;
  vec3 extinction=(vec3(.025)+dust*vec3(.55,.78,1.05))*uNebulaStrength;
  vec3 source=mix(vec3(.018,.055,.18),vec3(.035,.20,.31),smoothstep(.42,.64,broad));
  source*=gas*.18*uNebulaStrength;
  vec3 stepT=exp(-extinction*ds);
  radiance+=transmittance*source*(1.-stepT)/max(extinction,vec3(1e-5));
  transmittance*=stepT;
 }
 return background*transmittance+radiance;
}
void main(){
 vec2 p=vUv*2.-1.;
 vec3 ray=normalize(uForward+uRight*(p.x*uAspect*uTanHalfFov)+uUp*(p.y*uTanHalfFov));
 vec3 airRay=normalize(vec3(dot(ray,uAtmosphereEast),dot(ray,uAtmosphereUp),dot(ray,uAtmosphereNorth)));
 vec2 airUv=vec2(fract(atan(airRay.x,airRay.z)/(2.*PI)+.5),clamp(.5+asin(clamp(airRay.y,-1.,1.))/PI,.001,.999));
 vec3 starRay=normalize(uSkyRotation*ray);
 vec2 spaceUv=vec2(fract(atan(starRay.x,starRay.z)/(2.*PI)+.5),clamp(.5+asin(clamp(starRay.y,-1.,1.))/PI,.001,.999));
 vec3 distant=decode(texture(uSpaceTex,spaceUv).rgb)*.12;
 float footprint=max(length(dFdx(starRay)),length(dFdy(starRay)));
 float transition=smoothstep(0.,1.,uTransition);
 // Avoid the volume samples entirely under the daytime atmosphere.
 if(transition>.001)distant=nebulaRadiance(starRay,distant,footprint);
 vec3 air=decode(texture(uAirTex,airUv).rgb);
 float haze=exp(-abs(airRay.y)*12.)*(1.-transition);
 air=mix(air,decode(vec3(.68,.81,.87)),haze*.13);
 vec3 sky=mix(air,distant,transition);
 float mu=clamp(dot(ray,normalize(uSunDirection)),0.,1.);
 float disk=smoothstep(cos(.0049),cos(.0042),mu);
 vec3 solar=vec3(1.,.91,.76)*disk*12.;
 solar+=vec3(.42,.31,.19)*pow(mu,420.)*.1*(1.-transition);
 frag=vec4(sky+solar,1.); // Scene linear: final renderer applies exposure once.
}`;

export function makeNebulaNoiseData(size=64,seed=0x4e454255){
 if(!Number.isInteger(size)||size<8||size>128||(size&(size-1)))throw new RangeError('Noise volume size must be a power of two from 8 to 128');
 const data=new Uint8Array(size*size*size*4);let value=seed>>>0;
 for(let i=0;i<data.length;i++){value=(Math.imul(value,1664525)+1013904223)>>>0;data[i]=value>>>24;}
 return data;
}
