extends SceneTree

func _initialize():run.call_deferred()

func run():
    var root_node=Node3D.new();root.add_child(root_node)
    var camera=Camera3D.new();root_node.add_child(camera);camera.current=true
    var sky=Sky.new();sky.radiance_size=Sky.RADIANCE_SIZE_512;sky.process_mode=Sky.PROCESS_MODE_QUALITY
    var material=ShaderMaterial.new();material.shader=load("res://sky.gdshader")
    material.set_shader_parameter("nebula_steps",6)
    material.set_shader_parameter("atmosphere",0.)
    material.set_shader_parameter("nebula_strength",.9)
    sky.sky_material=material
    var environment=Environment.new();environment.background_mode=Environment.BG_SKY;environment.sky=sky
    var world=WorldEnvironment.new();world.environment=environment;root_node.add_child(world)
    var target=OS.get_cmdline_user_args()[0]
    for part in ["emission","transmission"]:
        material.set_shader_parameter("bake_component",0 if part=="emission" else 1)
        for i in range(20):await process_frame
        await RenderingServer.frame_post_draw
        var image=RenderingServer.sky_bake_panorama(sky.get_rid(),1.,false,Vector2i(2048,1024))
        if image==null or image.is_empty():push_error("Sky bake failed");quit(1);return
        if image.save_exr(target.path_join("nebula-blue-"+part+"-2k.exr"))!=OK:quit(1);return
        image.resize(1024,512,Image.INTERPOLATE_BILINEAR)
        image.save_exr(target.path_join("nebula-blue-"+part+"-1k.exr"))
    print("AZURE NEBULA HDR BAKE PASS")
    quit()
