shader_type spatial;
void fragment(){
    vec2 p=UV*vec2(24.,12.);
    float wrinkle=sin(p.x*7.0+sin(p.y*3.))*sin(p.y*9.+sin(p.x*4.));
    float seam=smoothstep(.47,.495,max(abs(fract(p.x*.25)-.5),abs(fract(p.y*.25)-.5)));
    ALBEDO=mix(vec3(.53,.31,.055),vec3(.78,.52,.14),wrinkle*.5+.5)*(1.-seam*.25);
    METALLIC=.85;ROUGHNESS=.24+abs(wrinkle)*.16;
    NORMAL_MAP=normalize(vec3(dFdx(wrinkle)*.7,dFdy(wrinkle)*.7,1.))*.5+.5;
}
