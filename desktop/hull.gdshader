shader_type spatial;
uniform float heat_dose=0.0;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
void fragment(){
    vec2 p=UV*vec2(24.,18.);
    vec2 edge=abs(fract(p)-.5);
    float seams=smoothstep(.475,.492,max(edge.x,edge.y));
    float scratch=smoothstep(.996,.999,hash(floor(UV*vec2(2800.,500.))));
    float dose=1.-exp(-max(0.,heat_dose-2e6)/3e7);
    float char_mask=dose*pow(1.-UV.y,3.);
    ALBEDO=mix(mix(vec3(.72,.77,.81),vec3(.12,.16,.21),seams*.85),vec3(.035,.025,.018),char_mask);
    METALLIC=mix(.25,.8,seams);
    ROUGHNESS=clamp(.27+seams*.15+scratch*.2+char_mask*.4,.15,.9);
}
