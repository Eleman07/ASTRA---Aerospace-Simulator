extends Node3D
## Presentation only: actual thrust/spool/rotor speed drive VFX and onboard audio.
var jets=[]
var discs=[]
var players={}
var state={}
var running=false
var audio_enabled=true
var audio_volume=.6
var gain=0.0
var fx_time=0.0
var light
var smoke
var kind="space"
var thrust=0.0
var rcs_level=0.0
var cinematic=true
var reentry_heat=0.0
var heat_shell
var audio_elapsed=0.0
var flame_texture
var smoke_texture
var last_state_time=-1.0

func setup(asset_root):
    for file in ["flame-16x4.exr","smoke-8x8.exr"]:
        var image=Image.load_from_file(asset_root.path_join("vfx/"+file))
        if image!=null and not image.is_empty():
            image.convert(Image.FORMAT_RGBAH);image.generate_mipmaps()
            var texture=ImageTexture.create_from_image(image)
            if file.begins_with("flame"):flame_texture=texture
            else:smoke_texture=texture
    for sound in ["rocket","aircraft","drone","rcs"]:
        var bytes=FileAccess.get_file_as_bytes(asset_root.path_join("audio/"+sound+".wav"))
        if bytes.size()<44:continue
        var stream=AudioStreamWAV.new();stream.format=AudioStreamWAV.FORMAT_16_BITS;stream.mix_rate=22050
        stream.data=bytes.slice(44);stream.loop_mode=AudioStreamWAV.LOOP_FORWARD;stream.loop_end=stream.data.size()/2
        var player=AudioStreamPlayer.new();player.stream=stream;player.volume_db=-80;add_child(player);player.play();players[sound]=player

func clear_vehicle():
    for jet in jets:
        if is_instance_valid(jet):jet.queue_free()
    jets.clear();discs.clear()
    if is_instance_valid(light):light.queue_free()
    if is_instance_valid(smoke):smoke.queue_free()
    if is_instance_valid(heat_shell):heat_shell.queue_free()

func add_jet(parent,origin,axis,radius,length_value,rcs=false):
    var node=MeshInstance3D.new();var mesh=CylinderMesh.new()
    mesh.height=1;mesh.top_radius=radius;mesh.bottom_radius=radius*(2.4 if not rcs else 1.4);mesh.radial_segments=24;mesh.rings=4
    mesh.cap_top=false;mesh.cap_bottom=false
    node.mesh=mesh;node.position=origin+axis*length_value*.5
    var y=-axis.normalized();var x=Vector3.FORWARD.cross(y).normalized()
    if x.length_squared()<.01:x=Vector3.RIGHT
    node.basis=Basis(x,y,x.cross(y)).orthonormalized()
    node.scale.y=length_value
    var material=ShaderMaterial.new();material.shader=load("res://plume.gdshader");material.set_shader_parameter("rcs",rcs)
    if flame_texture!=null and not rcs:
        material.set_shader_parameter("flame_flipbook",flame_texture)
        material.set_shader_parameter("use_flipbook",true)
    node.material_override=material;node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    node.set_meta("rcs",rcs);node.set_meta("origin",origin);node.set_meta("axis",axis);node.set_meta("length",length_value)
    parent.add_child(node);node.visible=false;jets.append(node)
    return node

func build(parent,bounds,vehicle,orbital):
    clear_vehicle();kind=vehicle
    if kind!="space":return
    var radius=maxf(.06,minf(.5,bounds.size.x*.13))
    var y=bounds.position.y+.03
    add_jet(parent,Vector3(0,y,0),Vector3.DOWN,radius,.9 if orbital else 6.0)
    if orbital:
        for axis in [Vector3.LEFT,Vector3.RIGHT,Vector3.FORWARD,Vector3.BACK,Vector3.UP,Vector3.DOWN]:
            add_jet(parent,axis*bounds.size*.45,axis,.035,.4,true)
    light=OmniLight3D.new();light.position=Vector3(0,y-.2,0);light.light_color=Color(.35,.6,1);light.omni_range=8;light.shadow_enabled=false;light.light_energy=0;parent.add_child(light)
    heat_shell=MeshInstance3D.new();var shell=SphereMesh.new()
    shell.radius=maxf(.1,bounds.size.x*.55);shell.height=maxf(.2,bounds.size.y*1.06)
    heat_shell.mesh=shell;heat_shell.position=bounds.get_center()
    var heat_material=ShaderMaterial.new();heat_material.shader=load("res://reentry.gdshader");heat_shell.material_override=heat_material
    heat_shell.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;heat_shell.visible=false;parent.add_child(heat_shell)
    if not orbital:
        smoke=GPUParticles3D.new();smoke.amount=96;smoke.lifetime=1.4;smoke.emitting=false;smoke.visibility_aabb=AABB(Vector3(-20,-30,-20),Vector3(40,45,40))
        smoke.position=Vector3(0,y-.8,0)
        var process=ParticleProcessMaterial.new();process.direction=Vector3(0,-1,0);process.spread=18
        process.initial_velocity_min=3;process.initial_velocity_max=10;process.gravity=Vector3(0,.8,0)
        process.scale_min=.35;process.scale_max=1.8;process.color=Color(.35,.38,.42,.18);smoke.process_material=process
        var mesh=QuadMesh.new();mesh.size=Vector2.ONE
        var material=StandardMaterial3D.new();material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
        material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;material.billboard_mode=BaseMaterial3D.BILLBOARD_ENABLED;material.vertex_color_use_as_albedo=true
        material.albedo_color=Color(.4,.42,.45,.1);mesh.material=material;smoke.draw_pass_1=mesh
        var gradient=Gradient.new();gradient.colors=PackedColorArray([Color(1,1,1,.35),Color(1,1,1,0)])
        var texture=GradientTexture2D.new();texture.gradient=gradient;texture.width=64;texture.height=64
        texture.fill=GradientTexture2D.FILL_RADIAL;texture.fill_from=Vector2(.5,.5);texture.fill_to=Vector2(.5,0)
        material.albedo_texture=texture
        if smoke_texture!=null:
            material.albedo_texture=smoke_texture
            material.billboard_mode=BaseMaterial3D.BILLBOARD_PARTICLES
            material.particles_anim_h_frames=8;material.particles_anim_v_frames=8;material.particles_anim_loop=false
            material.albedo_color=Color(.5,.52,.55,.65)
            process.anim_speed_min=.7;process.anim_speed_max=1.
        smoke.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;parent.add_child(smoke)

func add_rotor_disc(rotor,axis):
    var bounds=rotor.get_aabb() if rotor is MeshInstance3D else AABB(Vector3(-.2,0,-.2),Vector3(.4,.01,.4))
    var node=MeshInstance3D.new();var mesh=QuadMesh.new()
    var diameter=clampf(maxf(bounds.size.x,maxf(bounds.size.y,bounds.size.z)),.2,3.)
    mesh.size=Vector2(diameter,diameter);node.mesh=mesh
    node.rotation=Vector3(-PI/2,0,0) if axis=="y" else Vector3(0,PI/2,0)
    var material=ShaderMaterial.new();material.shader=load("res://rotor.gdshader");node.material_override=material
    node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;rotor.add_child(node);node.visible=false;discs.append(node)

func update_state(snapshot):
    state=snapshot.get("state",{})
    var simulation_time=float(state.get("time_s",0))
    running=bool(snapshot.get("desktop",{}).get("running",false)) or (snapshot.get("desktop",{}).get("clock_owner","")=="external" and simulation_time>last_state_time)
    last_state_time=simulation_time
    thrust=float(state.get("propulsion",{}).get("applied_thrust_N",0))
    var torques=state.get("attitude_control",{}).get("rcs_torque_body_N_m",[0,0,0])
    rcs_level=minf(1.,Vector3(float(torques[0]),float(torques[1]),float(torques[2])).length()/10.)

func _process(dt):
    var power=0.0
    if kind=="space":power=clampf(sqrt(thrust/(24.0 if state.get("scenario")=="orbital" else 320000.0)),0,1)
    elif kind=="aircraft":power=float(state.get("propulsion",{}).get("actual_power_pct",0))/100
    else:
        var rpm=state.get("propulsion_actuators",{}).get("motor_speed_actual_rpm",[])
        if not rpm.is_empty():
            for value in rpm:power+=float(value)/9000.0/rpm.size()
    gain=lerpf(gain,power,1.-exp(-dt*12))
    fx_time=float(state.get("time_s",0))
    if running:fx_time+=fmod(Time.get_ticks_msec()*.001,.08)
    for jet in jets:
        if not is_instance_valid(jet):continue
        var rcs=bool(jet.get_meta("rcs"));var level=rcs_level if rcs else gain
        jet.visible=level>.005
        var length_value=float(jet.get_meta("length"))*lerpf(.25,1.,level)
        jet.scale.y=length_value;jet.position=jet.get_meta("origin")+jet.get_meta("axis")*length_value*.5
        jet.material_override.set_shader_parameter("fx_time",fx_time)
        jet.material_override.set_shader_parameter("intensity",level)
        jet.material_override.set_shader_parameter("pressure_ratio",clampf(float(state.get("environment",{}).get("pressure_Pa",0))/101325.,0,1))
    for disc in discs:
        if is_instance_valid(disc):disc.visible=gain>.08;disc.material_override.set_shader_parameter("intensity",gain)
    if is_instance_valid(light):light.light_energy=gain*2.5
    if is_instance_valid(heat_shell):
        var heating=clampf(reentry_heat/1e6,0,1) if cinematic else 0.0
        heat_shell.visible=heating>.015
        heat_shell.material_override.set_shader_parameter("intensity",heating)
        heat_shell.material_override.set_shader_parameter("fx_time",fx_time)
    if is_instance_valid(smoke):
        smoke.emitting=gain>.08 and float(state.get("environment",{}).get("pressure_Pa",0))>500
        smoke.speed_scale=1.0 if running else 0.0
    var selected="rocket" if kind=="space" else kind
    audio_elapsed+=dt
    if audio_elapsed<.05:return
    audio_elapsed=0.0
    for sound in players:
        var level=rcs_level if sound=="rcs" else gain if sound==selected else 0.0
        var audible=audio_enabled and running
        players[sound].volume_db=linear_to_db(maxf(.0001,level*audio_volume*.48)) if audible else -80
        players[sound].pitch_scale=lerpf(.7,1.25,gain) if sound in ["aircraft","drone"] else 1.0
