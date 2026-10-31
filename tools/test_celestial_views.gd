extends SceneTree
const Scene=preload("res://native_scene.gd")

func _initialize():run.call_deferred()

func run():
    var args=OS.get_cmdline_user_args()
    var scene=Scene.new();root.add_child(scene);scene.setup(args[0],"high")
    var catalogue=JSON.parse_string(FileAccess.get_file_as_string(args[1]))
    var results=[]
    scene.show_solar_map(catalogue)
    await create_timer(.7).timeout
    await RenderingServer.frame_post_draw
    assert(scene.map_root.get_child_count()>20)
    root.get_texture().get_image().save_png(args[2]+"-solar-map.png")
    for id in ["moon","earth","mars","jupiter"]:
        scene.inspect_body(catalogue,id)
        await create_timer(.7).timeout
        await RenderingServer.frame_post_draw
        assert(scene.map_root.get_child_count()==2)
        var body=scene.map_root.get_child(0)
        assert(body.mesh is SphereMesh and body.material_override.albedo_texture!=null)
        var path=args[2]+"-"+id+".png"
        assert(root.get_texture().get_image().save_png(path)==OK)
        results.append({"body":id,"spherical":true,"texture_loaded":true,"capture":path})
    var file=FileAccess.open(args[2]+".json",FileAccess.WRITE)
    file.store_string(JSON.stringify(results,"  "))
    print("CELESTIAL VIEWS PASS")
    quit()
