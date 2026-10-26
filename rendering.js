/* Linear-light metallic/roughness shading. Environment lighting is analytic,
   not a claim of ray-traced reflections or physically simulated weather. */
export const surfaceFragmentShader = `#version 300 es
precision highp float;
in vec3 vN; in vec3 vW; in vec2 vUV;
uniform vec4 uColor;
uniform sampler2D uTex, uMetalRoughTex;
uniform int uTexOn, uAtmo, uSky, uAlphaMode, uEarthSurface, uMetalRoughOn;
uniform float uAlphaCutoff, uMetallic, uRoughness, uFogDensity;
uniform vec3 uLightDir, uWorldUp, uEmissive;
out vec4 frag;
const float PI=3.14159265359;
vec3 linearize(vec3 c){return mix(c/12.92,pow((c+.055)/1.055,vec3(2.4)),step(vec3(.04045),c));}
vec3 displayColor(vec3 c){return mix(c*12.92,1.055*pow(max(c,vec3(0.)),vec3(1./2.4))-.055,step(vec3(.0031308),c));}
vec3 filmic(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}
void main(){
 if(uSky==1){frag=vec4(texture(uTex,vUV).rgb,1.);return;}
 vec3 n=normalize(vN);
 vec3 v=normalize(-vW),l=normalize(uLightDir),h=normalize(v+l);
 float nv=max(dot(n,v),.001),nl=max(dot(n,l),0.);
 if(uAtmo==1){float rim=pow(1.-nv,2.7);float sun=.2+.8*max(dot(n,l),0.);frag=vec4(mix(vec3(.08,.24,.6),uColor.rgb,sun),rim*.64*uColor.a);return;}
 vec4 texel=uTexOn==1?texture(uTex,vUV):vec4(1.);
 vec4 base=vec4(linearize(texel.rgb)*uColor.rgb,texel.a*uColor.a);
 if(uEarthSurface==1&&base.a<.01)discard;
 if(uAlphaMode==1&&base.a<uAlphaCutoff)discard;
 float metal=clamp(uMetallic,0.,1.),rough=clamp(uRoughness,.06,1.);
 if(uMetalRoughOn==1){vec4 mr=texture(uMetalRoughTex,vUV);metal*=mr.b;rough=max(.06,rough*mr.g);}
 if(uEarthSurface==1){
   float day=smoothstep(-.12,.28,dot(n,l));
   vec3 surface=base.rgb*(.035+1.25*nl);
   float ocean=(1.-smoothstep(.03,.14,base.r))*smoothstep(.005,.055,base.b-base.r);
   surface+=vec3(1.,.84,.62)*pow(max(dot(n,h),0.),100.)*ocean*.35*day;
   surface+=vec3(.06,.20,.38)*pow(1.-nv,4.)*day*.14;
   vec3 mapped=displayColor(filmic(surface));float haze=1.-exp(-length(vW)*uFogDensity);frag=vec4(mix(mapped,vec3(.58,.70,.77),haze),1.);return;
 }
 float a=rough*rough,a2=a*a,nh=max(dot(n,h),0.),hv=max(dot(h,v),0.);
 float denom=nh*nh*(a2-1.)+1.;
 float D=a2/max(PI*denom*denom,.00001);
 float k=(rough+1.)*(rough+1.)/8.;
 float G=(nv/(nv*(1.-k)+k))*(nl/(nl*(1.-k)+k));
 vec3 f0=mix(vec3(.04),base.rgb,metal),F=f0+(1.-f0)*pow(1.-hv,5.);
 vec3 spec=D*G*F/max(4.*nv*nl,.001);
 vec3 diffuse=(1.-F)*(1.-metal)*base.rgb/PI;
 vec3 direct=(diffuse+spec)*vec3(3.5,3.25,2.95)*nl;
 float hemi=dot(n,uWorldUp)*.5+.5;
 vec3 ambient=mix(vec3(.055,.065,.075),vec3(.28,.37,.49),hemi);
 vec3 reflection=reflect(-v,n);
 float rsky=smoothstep(-.15,.7,dot(reflection,uWorldUp));
 vec3 env=mix(vec3(.06,.07,.09),vec3(.5,.65,.84),rsky);
 vec3 fresnel=f0+(max(vec3(1.-rough),f0)-f0)*pow(1.-nv,5.);
 vec3 color=direct+ambient*base.rgb*(1.-metal)+env*fresnel*(1.-rough*.65)+uEmissive;
 vec3 mapped=displayColor(filmic(color));float haze=1.-exp(-length(vW)*uFogDensity);frag=vec4(mix(mapped,vec3(.58,.70,.77),haze),uAlphaMode==2?base.a:1.);
}`;
