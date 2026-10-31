extends SceneTree
const Assets=preload("res://vehicle_assets.gd")

func _initialize():
    run.call_deferred()

func run():
    var camera=Camera3D.new();root.add_child(camera);camera.current=true;camera.position=Vector3(0,8,30);camera.look_at(Vector3(0,6,0))
    var args=OS.get_cmdline_user_args()
    var loader=Assets.new();loader.setup(args[0],"high")
    var results=[]
    for pair in [["nasa-sls-block1","sls-block1.glb"],["nasa-sls-block1","sls-block1-high.glb"],["space-x-crew-dragon","falcon-9-block5.glb"],["space-x-crew-dragon","falcon-9-block5-high.glb"],["nasa-sls-block1","sls-upper-stack.glb"]]:
        print("ALIGNMENT CHECK "+pair[1])
        var instance=loader.instantiate(args[0].path_join("vehicles").path_join(pair[1]),loader.models[pair[0]],13,1)
        assert(instance!=null)
        root.add_child(instance)
        await process_frame
        await RenderingServer.frame_post_draw
        var bounds=loader.get_bounds(instance)
        assert(bounds.size.y>bounds.size.x*2 and bounds.size.y>bounds.size.z*2,"Rocket longitudinal axis must be +Y: "+pair[1])
        results.append({"file":pair[1],"vertical":true,"dimensions_m":[bounds.size.x,bounds.size.y,bounds.size.z]})
        instance.queue_free()
        await process_frame
    print("ALIGNMENT CACHE RELEASE")
    loader.clear()
    await process_frame
    var file=FileAccess.open(args[1],FileAccess.WRITE)
    file.store_string(JSON.stringify(results,"  "))
    print("ROCKET ALIGNMENT PASS: SLS/Falcon low/high and upper stage")
    quit()
