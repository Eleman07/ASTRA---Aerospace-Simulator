extends Node
const Scene=preload("res://native_scene.gd")
var samples=[]
var measure=false

func require(condition,message="Runtime validation failed"):
    if not condition:
        push_error(message)
        get_tree().quit(1)

func _process(dt):
    if measure:samples.append(dt*1000.)

func run(asset_path,fixtures_file,prefix,profile):
    var args=[asset_path,fixtures_file,prefix,profile]
    var root=get_tree().root
    Engine.max_fps=0;DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
    var scene=Scene.new();root.add_child(scene);scene.setup(args[0],args[3] if args.size()>3 else "high")
    require(scene.effects.flame_texture!=null and scene.effects.smoke_texture!=null,"CC0 HDR flipbooks missing")
    var fixtures=JSON.parse_string(FileAccess.get_file_as_string(args[1]))
    scene.set_snapshot(fixtures.aircraft)
    await get_tree().create_timer(1.2).timeout
    var residency=[]
    for point in [Vector2(0,0),Vector2(7000,-12000),Vector2(50000,-80000),Vector2(180000,75000),Vector2(-50000,40000)]:
        var snapshot=fixtures.aircraft.duplicate(true)
        snapshot.visual.ground_offset_m=[-point.x,-300.,-point.y]
        snapshot.visual.altitude_m=300.;snapshot.state.altitude_m=300.
        scene.set_snapshot(snapshot)
        await get_tree().create_timer(.25).timeout
        require(scene.terrain_stream.covers(point),"Streaming coverage lost")
        require(scene.terrain_stream.chunks.size()<=97)
        require(scene.terrain_stream.meshes.size()==2)
        residency.append({"position_m":[point.x,point.y],"chunks":scene.terrain_stream.chunks.size(),"covered":true})
    await get_tree().create_timer(1).timeout
    samples.clear();measure=true
    for i in range(100):
        var snapshot=fixtures.aircraft.duplicate(true)
        snapshot.state.time_s=10.+i*.033
        snapshot.visual.ground_offset_m=[-50000.,-300.,-40000.-i*4.]
        scene.set_snapshot(snapshot)
        await get_tree().create_timer(.033).timeout
    measure=false
    samples.sort()
    var p95=samples[int(samples.size()*.95)]
    var average=0.
    for value in samples:average+=value/samples.size()
    scene.asset_choice="nasa-orion-spacecraft";scene.model_key=""
    scene.set_snapshot(fixtures.orion)
    await get_tree().create_timer(.5).timeout
    var names=[]
    for node in scene.model_root.get_child(0).find_children("*","MeshInstance3D",true,false):
        for i in range(node.mesh.get_surface_count()):
            var material=node.mesh.surface_get_material(i)
            if material!=null:names.append(scene.assets.material_key(material.resource_name))
    require("nasaslswhbox" not in names,"Unwanted Orion rectangle still present")
    var bounds=scene.assets.get_bounds(scene.model_root.get_child(0))
    require(bounds.size.y>bounds.size.x and bounds.size.y>bounds.size.z,"Orion longitudinal axis must be +Y")
    require(scene.effects.jets.size()>=7)
    require(scene.effects.jets[0].visible,"Orbital propulsion missing")
    var heated=fixtures.orion.duplicate(true)
    heated.state.environment.stagnation_point_convective_heat_flux_W_m2=300000.
    scene.set_snapshot(heated)
    await get_tree().create_timer(.1).timeout
    require(scene.effects.heat_shell.visible,"Cinematic reentry heating missing")
    scene.set_snapshot(fixtures.orion)
    await get_tree().create_timer(.1).timeout
    await RenderingServer.frame_post_draw
    root.get_texture().get_image().save_png(args[2]+"-orion.png")
    # Capture generated audio samples on a dedicated test bus.
    var bus=AudioServer.bus_count;AudioServer.add_bus();AudioServer.set_bus_name(bus,"ASTRA Test Capture")
    var capture=AudioEffectCapture.new();AudioServer.add_bus_effect(bus,capture)
    for player in scene.effects.players.values():player.bus="ASTRA Test Capture"
    await get_tree().create_timer(.3).timeout
    var buffer=capture.get_buffer(capture.get_frames_available());var peak=0.
    for sample in buffer:peak=maxf(peak,maxf(absf(sample.x),absf(sample.y)))
    require(peak>.0001,"Propulsion audio is silent")
    scene.asset_choice="auto";scene.model_key="";scene.set_snapshot(fixtures.launch)
    scene.distance=45;scene.elevation=.16
    await get_tree().create_timer(.8).timeout
    require(scene.effects.jets[0].visible and scene.effects.light.light_energy>0.)
    var stand_removed=int(scene.model_root.get_child(0).get_meta("removed_print_stand_triangles",0))
    print("PRINT STAND REMOVED TRIANGLES: "+str(stand_removed))
    require(stand_removed==12,"The gray printing base must be detached from SLS/Orion")
    await RenderingServer.frame_post_draw
    root.get_texture().get_image().save_png(args[2]+"-launch.png")
    var report={"unlimited_fps":Engine.max_fps==0,"vsync_disabled":DisplayServer.window_get_vsync_mode()==DisplayServer.VSYNC_DISABLED,
        "frame_p95_ms":p95,"mean_frame_ms":average,"sampled_frames":samples.size(),"chunk_residency":residency,
        "resolution_scale":get_viewport().scaling_3d_scale,"scaling_3d_mode":get_viewport().scaling_3d_mode,
        "orion_rectangle_removed":true,"printing_stand_removed_triangles":stand_removed,"orbital_exhaust":true,"launch_exhaust":true,"cinematic_reentry":true,"cc0_hdr_flipbooks":true,"audio_peak":peak,
        "graphics":scene.quality,"renderer":RenderingServer.get_current_rendering_method(),"gpu":RenderingServer.get_video_adapter_name()}
    var file=FileAccess.open(args[2]+".json",FileAccess.WRITE);file.store_string(JSON.stringify(report,"  "))
    print("ASTRA POLISH PASS: "+JSON.stringify(report))
    for player in scene.effects.players.values():player.bus="Master";player.stop()
    AudioServer.remove_bus(bus)
    scene.queue_free()
    await get_tree().process_frame
    await RenderingServer.frame_post_draw
    get_tree().quit()
