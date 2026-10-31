shader_type spatial;
uniform bool lunar = false;
uniform sampler2D ground_image : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool use_image=false;
uniform float patch_radius=8000.0;
uniform float patch_visibility=1.0;
uniform bool streamed=false;
instance uniform vec2 chunk_origin=vec2(0.);
uniform vec2 stream_center=vec2(0.);
varying vec3 world_position;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1)),f.x),f.y);}
float height_at(vec2 p){
    float r=length(p),fade=smoothstep(35.,110.,r);
    float h=smoothstep(25.,100.,abs(p.x))*fade*(6.*sin(p.x*.002)*cos(p.y*.0018)+2.*sin(p.y*.006));
    if(lunar){
        h=sin(p.x*.012)*cos(p.y*.019)*2.+sin(p.x*.06+p.y*.02)*.4;
        vec3 craters[4]={vec3(230.,140.,150.),vec3(-310.,220.,210.),vec3(120.,-460.,240.),vec3(-700.,-240.,300.)};
        for(int i=0;i<4;i++){float d=length(p-craters[i].xy)/craters[i].z;h+=craters[i].z*(.09*exp(-pow((d-1.)*8.,2.))-.15*exp(-d*d*2.8));}
        h*=fade;
    }
    return h;
}
void vertex(){
    world_position=VERTEX;
    if(streamed){
        vec2 p=VERTEX.xz+chunk_origin;
        float h=height_at(p);
        VERTEX.y+=h;
        NORMAL=normalize(vec3(height_at(p-vec2(.3,0.))-height_at(p+vec2(.3,0.)),.6,height_at(p-vec2(0.,.3))-height_at(p+vec2(0.,.3))));
        world_position=vec3(p.x,h,p.y);
    }
}
void fragment(){
    vec2 p=world_position.xz;
    float coverage=(1.-smoothstep(patch_radius*.72,patch_radius,length(p-(streamed?stream_center:vec2(0.)))))*patch_visibility;
    // Screen-door fade keeps depth/shadows opaque while removing square edges.
    if(fract(sin(dot(FRAGCOORD.xy,vec2(12.9898,78.233)))*43758.5453)>coverage){discard;}
    float coarse=noise(p*.006)*.6+noise(p*.03)*.4;
    float fine=noise(p*1.8);
    vec3 soil=mix(vec3(.065,.095,.055),vec3(.16,.18,.10),coarse);
    if(lunar){soil=mix(vec3(.15,.145,.135),vec3(.28,.27,.25),coarse);}
    if(use_image){vec2 image_uv=p/3000.+.5;float inside=step(0.,image_uv.x)*step(0.,image_uv.y)*step(image_uv.x,1.)*step(image_uv.y,1.);soil=mix(soil,texture(ground_image,image_uv).rgb*.6,inside*.7);}
    ALBEDO=soil*(.92+fine*.16);
    float detail=1.-smoothstep(.08,.7,length(fwidth(p)));
    float hx=noise((p+vec2(.04,0))*1.8)-noise((p-vec2(.04,0))*1.8);
    float hy=noise((p+vec2(0,.04))*1.8)-noise((p-vec2(0,.04))*1.8);
    NORMAL_MAP=normalize(vec3(-hx*detail*.6,-hy*detail*.6,1.))*.5+.5;
    ROUGHNESS=lunar?.95:.9;
    METALLIC=0.;
}
