shader_type spatial;
render_mode unshaded,blend_add,cull_disabled,depth_draw_never;
uniform float pressure_ratio=1.0;
uniform float fx_time=0.0;
uniform float intensity=1.0;
uniform bool rcs=false;
uniform bool use_flipbook=false;
uniform sampler2D flame_flipbook : filter_linear_mipmap, repeat_disable;
void vertex(){
    float edge=UV.y*UV.y;
    VERTEX.x+=sin(UV.y*36.-fx_time*24.)*edge*.035;
    VERTEX.z+=cos(UV.y*31.-fx_time*21.)*edge*.035;
}
void fragment(){
    float axis=abs(UV.x-.5)*2.;
    float fade=pow(max(0.,1.-UV.y),1.8);
    float cells=1.0-pressure_ratio*.14*(1.0-cos(UV.y*60.-fx_time*28.));
    float turbulent=.83+.17*sin(UV.y*94.-fx_time*70.+sin(UV.x*38.+fx_time*23.));
    vec3 hot=mix(vec3(.65,.82,1.),mix(vec3(.1,.35,1.),vec3(1.,.32,.055),pressure_ratio),UV.y);
    float texture_density=1.;
    if(use_flipbook && pressure_ratio>.01){
        float frame=mod(floor(fx_time*24.),64.);
        vec2 tile=vec2(mod(frame,16.),floor(frame/16.));
        vec2 safe_uv=clamp(UV,vec2(.008),vec2(.992));
        vec4 sample_value=texture(flame_flipbook,(tile+safe_uv)/vec2(16.,4.));
        texture_density=mix(1.,clamp(sample_value.a*.8+.2,0.,1.),pressure_ratio);
        hot=mix(hot,mix(vec3(.12,.3,.8),sample_value.rgb*2.,.65),pressure_ratio*.65);
    }
    ALBEDO=hot*fade*(rcs?2.:5.)*intensity*turbulent;
    EMISSION=ALBEDO;
    float edge=pow(abs(dot(normalize(NORMAL),normalize(VIEW))),.7);
    ALPHA=fade*cells*(1.-axis*.3)*.5*intensity*edge*texture_density;
}
