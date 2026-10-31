shader_type spatial;
render_mode unshaded,cull_disabled,depth_draw_never;
uniform float intensity=0.0;
void fragment(){
    vec2 p=UV*2.-1.;float r=length(p);
    if(r>1.||r<.12){discard;}
    ALBEDO=vec3(.14,.18,.23);
    ALPHA=(1.-smoothstep(.8,1.,r))*.12*intensity;
}
