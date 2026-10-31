shader_type spatial;
render_mode unshaded,blend_add,cull_disabled,depth_draw_never;
uniform float intensity=0.;
uniform float fx_time=0.;
void fragment(){
    float rim=pow(1.-abs(dot(normalize(NORMAL),normalize(VIEW))),2.8);
    float flow=.65+.35*sin(UV.y*85.-fx_time*35.+sin(UV.x*40.)*2.);
    EMISSION=mix(vec3(1.,.08,.01),vec3(.7,.45,1.),rim)*rim*flow*intensity*4.;
    ALBEDO=EMISSION;ALPHA=rim*flow*intensity*.4;
}
