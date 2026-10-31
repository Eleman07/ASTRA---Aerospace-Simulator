shader_type spatial;
render_mode cull_disabled;
void fragment(){
    vec2 grid=UV*vec2(18.,8.);
    vec2 cell=fract(grid);
    float gap=max(step(cell.x,.025),step(cell.y,.04));
    float conductor=step(.96,fract(cell.x*3.));
    ALBEDO=mix(vec3(.015,.045,.13),vec3(.3,.37,.45),max(gap,conductor*.6));
    METALLIC=.55;ROUGHNESS=.18+gap*.2;
}
