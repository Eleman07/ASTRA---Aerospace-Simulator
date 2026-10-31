shader_type sky;


uniform vec3 sun_direction = vec3(0.6,0.7,0.4);
global uniform float atmosphere;
uniform float nebula_strength : hint_range(0.0,2.0) = 0.9;
uniform int nebula_steps = 4;
uniform int atmosphere_steps = 8;
uniform float reflection_refresh=0.0;
uniform bool use_baked_nebula=false;
uniform int bake_component=-1;
uniform sampler2D nebula_emission : filter_linear_mipmap, repeat_enable;
uniform sampler2D nebula_transmission : filter_linear_mipmap, repeat_enable;
uniform bool planet_visible = false;
uniform float planet_radius=6.378137;
uniform bool lunar_planet=false;
uniform sampler2D planet_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
global uniform vec3 planet_center;
global uniform mat3 planet_rotation;
uniform bool companion_visible=false;
global uniform vec3 companion_center;
uniform float companion_radius=1.7374;
uniform sampler2D companion_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;

float hash(vec3 p){p=fract(p*vec3(.1031,.11369,.13787));p+=dot(p,p.yzx+19.19);return fract((p.x+p.y)*p.z);}
float noise(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1)),f.x),f.y),f.z);}
float fbm(vec3 p){return noise(p)*.57+noise(p*2.03+9.7)*.28+noise(p*4.07+5.2)*.15;}

vec2 sphere_hit(vec3 origin,vec3 direction,float radius){float b=dot(origin,direction),c=dot(origin,origin)-radius*radius,h=b*b-c;if(h<0.)return vec2(-1.);return vec2(-b-sqrt(h),-b+sqrt(h));}
float henyey_greenstein(float mu,float g){float g2=g*g;return (1.-g2)/(12.5663706*pow(max(1e-4,1.+g2-2.*g*mu),1.5));}
float star_layer(vec2 uv,vec2 grid,float density,float radius,float brightness,vec3 seed){
    vec2 p=uv*grid;vec2 cell=floor(p);vec2 f=fract(p)-vec2(.2+.6*hash(vec3(cell,seed.x)),.2+.6*hash(vec3(cell,seed.y)));
    float chance=step(1.-density,hash(vec3(cell,seed.z)));
    float core=exp(-dot(f,f)/max(radius,1e-5));
    return chance*core*mix(.35,brightness,pow(hash(vec3(cell,seed.x+seed.y)),5.));
}
vec3 planet_background(vec3 ray,vec3 behind){
    float radius=planet_radius;
    vec3 origin=-planet_center;
    vec2 hit=sphere_hit(origin,ray,radius);
    vec3 surface=behind;
    if(hit.y>0. && hit.x>0.){
        vec3 normal=normalize(origin+ray*hit.x);
        vec3 mapped=planet_rotation*normal;
        vec2 uv=vec2(atan(mapped.z,mapped.x)/6.2831853+.5,.5-asin(clamp(mapped.y,-1.,1.))/3.14159265);
        float nl=max(dot(normal,normalize(sun_direction)),0.);
        vec3 texel=texture(planet_texture,uv).rgb;
        surface=texel*(.004+nl*1.52);
        if(!lunar_planet){
            // The NASA surface map already includes cloud cover; avoid adding
            // synthetic noise over it so land, coastlines and cloud bands stay sharp.
            // A restrained ocean glint adds scale cues near the day-side limb.
            float ocean=smoothstep(.025,.12,texel.b-texel.r)*smoothstep(.015,.09,texel.b-texel.g);
            vec3 half_vector=normalize(normalize(sun_direction)-ray);
            float glint=pow(max(dot(normal,half_vector),0.0),48.0)*ocean*nl;
            surface+=vec3(.10,.25,.42)*glint*.42;
            // Thin blue airglow follows the curvature, strongest at the limb.
            float limb=pow(1.0-clamp(abs(dot(normal,-ray)),0.0,1.0),4.0);
            float sunlit_limb=.22+.78*max(dot(normal,normalize(sun_direction)),0.0);
            surface+=vec3(.055,.25,.78)*limb*sunlit_limb*.42;
        }
        if(lunar_planet){surface=texel*(.007+nl*1.15);}
        vec3 h=normalize(normalize(sun_direction)-ray);
        surface+=vec3(.9,.8,.65)*pow(max(dot(normal,h),0.),110.)*.06;
    }
    if(lunar_planet)return surface;
    vec2 shell=sphere_hit(origin,ray,radius+.085);
    if(shell.y<=0.)return surface;
    float start=max(0.,shell.x),end=shell.y;
    if(hit.x>0.)end=min(end,hit.x);
    int samples=clamp(atmosphere_steps,4,16);
    float ds=max(0.,end-start)/float(samples);
    vec3 T=vec3(1.),L=vec3(0.);
    vec3 beta_rayleigh=vec3(.0058,.0135,.0331);
    vec3 beta_mie=vec3(.0038);
    float view_sun=dot(ray,normalize(sun_direction));
    float phase_rayleigh=3./(50.2654825)*(1.+view_sun*view_sun);
    float phase_mie=henyey_greenstein(-view_sun,.76);
    for(int i=0;i<16;i++){
        if(i>=samples)break;
        vec3 p=origin+ray*(start+(float(i)+.5)*ds);
        float altitude=max(0.,(length(p)-radius)*1000.);
        float density_rayleigh=exp(-altitude/8.);
        float density_mie=exp(-altitude/1.25);
        vec3 optical_depth=(beta_rayleigh*density_rayleigh+beta_mie*density_mie)*ds*1000.;
        vec3 stepT=exp(-optical_depth);
        float day=smoothstep(-.05,.15,dot(normalize(p),normalize(sun_direction)));
        vec3 source=(beta_rayleigh*density_rayleigh*phase_rayleigh+
                     beta_mie*density_mie*phase_mie)*vec3(1.,.91,.74)*day*24.;
        L+=T*source*(1.-stepT);T*=stepT;
    }
    return surface*T+L;
}

void sky(){
    vec3 ray=normalize(EYEDIR);
    float band=exp(-pow(abs(ray.y+.12)*4.0,2.0));
    vec3 light=vec3(0.0),T=vec3(1.0);
    if(use_baked_nebula){
        vec2 uv=vec2(atan(ray.z,ray.x)/6.2831853+.5,acos(clamp(ray.y,-1.,1.))/3.14159265);
        light=texture(nebula_emission,uv).rgb*(nebula_strength/.9);
        T=pow(clamp(texture(nebula_transmission,uv).rgb,vec3(.001),vec3(1.)),vec3(nebula_strength/.9));
    }else if(atmosphere<.99 && nebula_steps>0){
        float ds=9.0/float(nebula_steps);
        for(int i=0;i<8;i++){
            if(i>=nebula_steps){break;}
            vec3 p=ray*(2.0+(float(i)+.5)*ds)+vec3(12.7,4.3,-8.1);
            float broad=fbm(p*.5),ridge=pow(1.0-abs(fbm(p*1.4)*2.0-1.0),5.0);
            float gas=smoothstep(.35,.72,broad)*ridge*band;
            float dust=smoothstep(.48,.72,fbm(p*.8+17.0))*band;
            vec3 sigma=(vec3(.025)+dust*vec3(.5,.7,1.0))*nebula_strength;
            vec3 stepT=exp(-sigma*ds);
            vec3 source=mix(vec3(.018,.055,.19),vec3(.035,.20,.34),smoothstep(.4,.67,broad))*gas*.18*nebula_strength;
            light+=T*source*(1.0-stepT)/max(sigma,vec3(.0001));T*=stepT;
        }
    }
    if(bake_component>=0){COLOR=bake_component==0?light:T;}else{
    vec2 star_uv=vec2(atan(ray.z,ray.x)/6.2831853+.5,acos(clamp(ray.y,-1.,1.))/3.14159265);
    float faint=star_layer(star_uv,vec2(1440.,720.),.035,.0016,.7,vec3(11.,17.,29.));
    float medium=star_layer(star_uv,vec2(620.,310.),.052,.0038,1.8,vec3(37.,43.,59.));
    float bright=star_layer(star_uv,vec2(240.,120.),.04,.006,2.7,vec3(71.,83.,101.));
    float galactic_plane=exp(-pow(ray.y+.10+.16*sin(atan(ray.z,ray.x)*2.),2.)*48.);
    float galactic_dust=fbm(ray*18.+vec3(6.,2.,9.));
    vec3 milky_way=vec3(.003,.006,.014)*galactic_plane*(.35+galactic_dust*1.3);
    vec3 white_stars=vec3(1.0)*(faint+medium+bright);
    // Extinction colors the nebula and galactic background; keep point stars
    // outside that transmittance so every star stays neutral white.
    vec3 space=(vec3(.0003,.00055,.001)+milky_way)*T+light+white_stars;
    if(companion_visible){
        vec2 other=sphere_hit(-companion_center,ray,companion_radius);
        if(other.x>0.){
            vec3 n=normalize(-companion_center+ray*other.x);
            vec3 mapped=planet_rotation*n;
            vec2 uv=vec2(atan(mapped.z,mapped.x)/6.2831853+.5,.5-asin(clamp(mapped.y,-1.,1.))/3.14159265);
            space=texture(companion_texture,uv).rgb*(.006+1.4*max(0.,dot(n,normalize(sun_direction))));
        }
    }
    if(planet_visible)space=planet_background(ray,space);
    float elevation=max(0.0,ray.y);
    vec3 air=mix(vec3(.36,.51,.66),vec3(.045,.17,.37),pow(elevation,.36));
    float mu=max(0.0,dot(ray,normalize(sun_direction)));
    float sun=smoothstep(cos(.005),cos(.0043),mu);
    if(planet_visible && sphere_hit(-planet_center,ray,planet_radius).x>0.)sun=0.;
    COLOR=mix(space,air,atmosphere)+vec3(1,.9,.72)*sun*16.0;
    if(AT_CUBEMAP_PASS)COLOR+=vec3(reflection_refresh*0.000000000001);
    }
}
