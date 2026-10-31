/* Linear-light metallic/roughness shading. Environment lighting is analytic,
   not a claim of ray-traced reflections or physically simulated weather. */
export const surfaceFragmentShader = `#version 300 es
precision highp float;
in vec3 vN; in vec3 vW; in vec2 vUV;
in vec4 vShadow;
uniform vec4 uColor;
uniform sampler2D uTex, uMetalRoughTex, uNormalTex, uOcclusionTex, uEmissiveTex;
uniform int uTexOn, uAtmo, uSky, uAlphaMode, uEarthSurface, uMetalRoughOn;
uniform float uAlphaCutoff, uMetallic, uRoughness, uFogDensity;
uniform int uNormalOn,uOcclusionOn,uEmissiveOn,uAtmosphereQuality;
uniform float uNormalScale,uOcclusionStrength,uExposure;
uniform vec3 uLightDir, uWorldUp, uEmissive;
uniform sampler2D uShadowTex;
uniform int uShadowOn,uLinearOutput,uCloudLayer;
uniform vec2 uShadowTexel;
uniform vec3 uPlanetCenterEye;
uniform float uPlanetRadius;
out vec4 frag;
const float PI=3.14159265359;
vec3 linearize(vec3 c){return mix(c/12.92,pow((c+.055)/1.055,vec3(2.4)),step(vec3(.04045),c));}
vec3 displayColor(vec3 c){return mix(c*12.92,1.055*pow(max(c,vec3(0.)),vec3(1./2.4))-.055,step(vec3(.0031308),c));}
vec3 filmic(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}
vec3 outputColor(vec3 c){return uLinearOutput==1?c:displayColor(filmic(c*uExposure));}
float shadowVisibility(vec3 n,vec3 l){if(uShadowOn==0||vShadow.w<=0.)return 1.;vec3 q=vShadow.xyz/vShadow.w*.5+.5;if(any(lessThan(q,vec3(0)))||any(greaterThan(q,vec3(1))))return 1.;float bias=max(.00008,.0003*(1.-max(dot(n,l),0.)));float lit=0.;for(int y=-1;y<=1;y++)for(int x=-1;x<=1;x++){float d=texture(uShadowTex,q.xy+vec2(x,y)*uShadowTexel).r;lit+=q.z-bias<=d?1.:0.;}return lit/9.;}
vec2 sphereHit(vec3 o,vec3 d,float r){float b=dot(o,d),c=dot(o,o)-r*r,h=b*b-c;if(h<0.)return vec2(-1.);h=sqrt(h);return vec2(-b-h,-b+h);}
vec3 atmosphereScatter(vec3 ray,vec3 sun){vec3 origin=-uPlanetCenterEye;float R=uPlanetRadius,km=6378.137/R;float top=R+90./km;vec2 hit=sphereHit(origin,ray,top);float start=max(0.,hit.x),end=hit.y;vec2 ground=sphereHit(origin,ray,R);if(ground.x>0.)end=min(end,ground.x);if(end<=start)return vec3(0);float stepSize=(end-start)/8.;vec3 beta=vec3(.0058,.0135,.0331);vec2 optical=vec2(0);vec3 sumR=vec3(0),sumM=vec3(0);for(int i=0;i<8;i++){vec3 p=origin+ray*(start+(float(i)+.5)*stepSize);float h=max(0.,(length(p)-R)*km);vec2 density=exp(-h/vec2(8.,1.2));optical+=density*stepSize*km;vec2 sunlight=sphereHit(p,sun,top);vec2 occult=sphereHit(p,sun,R);if(occult.x>0.)continue;float ds=max(0.,sunlight.y)/4.;vec2 sunDepth=vec2(0);for(int j=0;j<4;j++){float hs=max(0.,(length(p+sun*(float(j)+.5)*ds)-R)*km);sunDepth+=exp(-hs/vec2(8.,1.2))*ds*km;}vec3 trans=exp(-beta*(optical.x+sunDepth.x)-vec3(.004)*(optical.y+sunDepth.y));sumR+=trans*density.x*stepSize*km;sumM+=trans*density.y*stepSize*km;}float mu=dot(ray,sun),g=.76;float phaseR=3./(16.*PI)*(1.+mu*mu);float phaseM=(1.-g*g)/(4.*PI*pow(max(1.+g*g-2.*g*mu,.02),1.5));return 18.*(sumR*beta*phaseR+sumM*.003*phaseM);}
void main(){
 if(uSky==1){frag=vec4(outputColor(linearize(texture(uTex,vUV).rgb)),1.);return;}
 vec3 n=normalize(vN)*(gl_FrontFacing?1.:-1.);
 // Cotangent frame from eye-space/UV derivatives, also valid after nonuniform scale.
 vec3 dp1=dFdx(vW),dp2=dFdy(vW);vec2 duv1=dFdx(vUV),duv2=dFdy(vUV);
 float uvdet=duv1.x*duv2.y-duv1.y*duv2.x;
 if(uNormalOn==1&&abs(uvdet)>1e-10){
   vec3 t=(dp1*duv2.y-dp2*duv1.y)/uvdet,bRaw=(dp2*duv1.x-dp1*duv2.x)/uvdet;
   t-=n*dot(n,t);
   if(dot(t,t)>1e-16){t=normalize(t);vec3 b=normalize(cross(n,t))*sign(dot(cross(n,t),bRaw));vec3 sampleN=texture(uNormalTex,vUV).xyz*2.-1.;sampleN.xy*=uNormalScale;if(dot(sampleN,sampleN)>1e-12)n=normalize(mat3(t,b,n)*sampleN);}
 }
 vec3 v=normalize(-vW),l=normalize(uLightDir),h=normalize(v+l);
 float nv=max(dot(n,v),.001),nl=max(dot(n,l),0.);
 if(uAtmo==1){if(uAtmosphereQuality==0){frag=vec4(0.);return;}frag=vec4(outputColor(atmosphereScatter(normalize(vW),l)),1.);return;}
 vec4 texel=uTexOn==1?texture(uTex,vUV):vec4(1.);
 vec4 base=vec4(linearize(texel.rgb)*uColor.rgb,texel.a*uColor.a);
 if(uEarthSurface==1&&base.a<.01)discard;
 if(uAlphaMode==1&&base.a<uAlphaCutoff)discard;
 if(uCloudLayer==1){float day=smoothstep(-.12,.18,dot(n,l));frag=vec4(outputColor(vec3(.88,.92,1.)*(.04+1.5*nl)*day),base.a*.78);return;}
 float metal=clamp(uMetallic,0.,1.),rough=clamp(uRoughness,.06,1.);
 if(uMetalRoughOn==1){vec4 mr=texture(uMetalRoughTex,vUV);metal*=mr.b;rough=max(.06,rough*mr.g);}
 if(uEarthSurface==1){
   float day=smoothstep(-.12,.28,dot(n,l));
   vec3 surface=base.rgb*(.008+1.25*nl);
   float ocean=(1.-smoothstep(.03,.14,base.r))*smoothstep(.005,.055,base.b-base.r);
   surface+=vec3(1.,.84,.62)*pow(max(dot(n,h),0.),100.)*ocean*.35*day;
   surface+=vec3(.06,.20,.38)*pow(1.-nv,4.)*day*.14;
   surface*=mix(.25,1.,shadowVisibility(n,l));vec3 mapped=outputColor(surface);float haze=1.-exp(-length(vW)*uFogDensity);frag=vec4(mix(mapped,uLinearOutput==1?linearize(vec3(.58,.70,.77)):vec3(.58,.70,.77),haze),1.);return;
 }
 float a=rough*rough,a2=a*a,nh=max(dot(n,h),0.),hv=max(dot(h,v),0.);
 float denom=nh*nh*(a2-1.)+1.;
 float D=a2/max(PI*denom*denom,.00001);
 float k=(rough+1.)*(rough+1.)/8.;
 float G=(nv/(nv*(1.-k)+k))*(nl/(nl*(1.-k)+k));
 vec3 f0=mix(vec3(.04),base.rgb,metal),F=f0+(1.-f0)*pow(1.-hv,5.);
 vec3 spec=D*G*F/max(4.*nv*nl,.001);
 vec3 diffuse=(1.-F)*(1.-metal)*base.rgb/PI;
 vec3 direct=(diffuse+spec)*vec3(3.5,3.25,2.95)*nl*shadowVisibility(n,l);
 float hemi=dot(n,uWorldUp)*.5+.5;
 vec3 ambient=mix(vec3(.055,.065,.075),vec3(.28,.37,.49),hemi);
 vec3 reflection=reflect(-v,n);
 float rsky=smoothstep(-.15,.7,dot(reflection,uWorldUp));
 vec3 env=mix(vec3(.06,.07,.09),vec3(.5,.65,.84),rsky);
 vec3 fresnel=f0+(max(vec3(1.-rough),f0)-f0)*pow(1.-nv,5.);
 float ao=uOcclusionOn==1?mix(1.,texture(uOcclusionTex,vUV).r,uOcclusionStrength):1.;
 vec3 emission=uEmissive*(uEmissiveOn==1?linearize(texture(uEmissiveTex,vUV).rgb):vec3(1.));
 vec3 color=direct+(ambient*base.rgb*(1.-metal)+env*fresnel*(1.-rough*.65))*ao+emission;
 vec3 mapped=outputColor(color);float haze=1.-exp(-length(vW)*uFogDensity);frag=vec4(mix(mapped,uLinearOutput==1?linearize(vec3(.58,.70,.77)):vec3(.58,.70,.77),haze),uAlphaMode==2?base.a:1.);
}`;

// Crossed transparent ribbons. Shape coefficients are visual approximations;
// ignition, intensity and expansion are driven only by engine telemetry.
export const plumeVertexShader=`#version 300 es
layout(location=0) in vec3 aPos;layout(location=2) in vec2 aUV;
uniform mat4 uViewModel,uProj;out vec2 vUV;
void main(){vUV=aUV;gl_Position=uProj*uViewModel*vec4(aPos,1.);}`;
export const plumeFragmentShader=`#version 300 es
precision highp float;in vec2 vUV;uniform float uThrottle,uPressureRatio,uTime,uExposure;out vec4 frag;
void main(){float t=vUV.y;float x=abs(vUV.x*2.-1.);float radius=mix(.14,.9,t)*mix(1.,.62,uPressureRatio);float core=exp(-x*x/max(radius*radius,.001)*3.);float fade=(1.-smoothstep(.55,1.,t))*smoothstep(0.,.035,t);float cells=1.-.12*uPressureRatio*sin(t*65.-uTime*14.);float alpha=core*fade*sqrt(uThrottle)*cells*.65;if(alpha<.005)discard;vec3 color=mix(vec3(.18,.48,1.),vec3(1.,.32,.07),smoothstep(.1,.9,t));color=mix(color,vec3(1.,.93,.78),pow(core,6.)*(1.-t)*.7);color=vec3(1.)-exp(-color*uExposure*2.);frag=vec4(color,alpha);}`;
