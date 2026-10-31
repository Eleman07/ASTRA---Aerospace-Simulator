extends Node

const NativeScene=preload("res://native_scene.gd")
const NativeMain=preload("res://main.gd")

class RecordedUI extends NativeMain:
    func _ready():pass
    func _process(_dt):pass
    func resize_ui():
        var size=Vector2(1920,1080)
        widgets.header.size.x=size.x-36
        widgets.left.size.y=size.y-194
        widgets.right.position.x=size.x-360
        widgets.right.size.y=size.y-194
        widgets.bottom.position.y=size.y-112
        widgets.bottom.size=Vector2(maxf(300,size.x-684),96)

var scene
var tape=[]
var manifest={}
var shot={}
var frame=-64
var count=0
var warmup=64
var preview=false
var done=false
var work=""
var shot_id=""
var layer
var title_group
var headline
var subtitle
var accent
var stamp
var python_panel
var python_metrics
var ui_main
var outro_group
var font
var bold
var mono
var darken

func label(parent,text,position,size,color=Color(.92,.96,1),use_font=null):
    var node=Label.new();node.text=text;node.position=position
    node.add_theme_font_override("font",font if use_font==null else use_font)
    node.add_theme_font_size_override("font_size",size)
    node.add_theme_color_override("font_color",color)
    node.add_theme_constant_override("outline_size",2)
    node.add_theme_color_override("font_outline_color",Color(0,.01,.025,.25))
    parent.add_child(node);return node

func rect(parent,position,size,color):
    var node=ColorRect.new();node.position=position;node.size=size;node.color=color;node.mouse_filter=Control.MOUSE_FILTER_IGNORE
    parent.add_child(node);return node

func _ready():
    var args=OS.get_cmdline_user_args()
    for i in range(args.size()):
        if args[i]=="--work":work=args[i+1]
        elif args[i]=="--shot":shot_id=args[i+1]
        elif args[i]=="--preview":preview=true
    manifest=JSON.parse_string(FileAccess.get_file_as_string(work.path_join("manifest.json")))
    for item in manifest.shots:
        if item.id==shot_id:shot=item
    if shot.is_empty():push_error("shot missing");get_tree().quit(1);return
    warmup=int(manifest.warmup_frames);frame=-warmup
    tape=JSON.parse_string(FileAccess.get_file_as_string(shot.path));count=tape.size()
    font=load("res://fonts/bahnschrift.ttf");bold=load("res://fonts/arialbd.ttf");mono=load("res://fonts/consola.ttf")
    get_viewport().gui_disable_input=true
    DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
    scene=NativeScene.new();add_child(scene);scene.setup(manifest.asset_root,"high")
    scene.set_process_unhandled_input(false);scene.asset_choice=shot.asset
    scene.effects.audio_enabled=false;scene.effects.audio_volume=0
    scene.environment.tonemap_exposure=float(shot.exposure)
    scene.camera.fov=float(shot.fov)
    scene.camera.h_offset=-1.05 if shot.get("python",false) else -2.8 if shot_id=="01_orbit" else 0
    scene.camera.attributes.dof_blur_far_enabled=shot_id=="02_detail"
    scene.camera.attributes.dof_blur_amount=.035
    scene.sky_material.set_shader_parameter("nebula_strength",1.05)
    scene.set_snapshot(tape[0]);scene.camera.fov=float(shot.fov)
    if shot.get("native_ui",false):make_native_ui()
    make_titles()
    process_priority=-100

func make_native_ui():
    ui_main=RecordedUI.new();add_child(ui_main);ui_main.set_process_input(false);ui_main.set_process_unhandled_key_input(false)
    ui_main.scene=scene;ui_main.studies=JSON.parse_string(FileAccess.get_file_as_string("res://studies.json"))
    ui_main.models=manifest.models;ui_main.make_interface()
    ui_main.ui.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
    ui_main.ui.size=Vector2(1920,1080);ui_main.ui.scale=Vector2(2,2)
    ui_main.vehicle="aircraft";ui_main.scenario="mission";ui_main.free_mode=true;ui_main.fill_models()
    ui_main.mission_selection.select(8)
    ui_main.catalog=JSON.parse_string(FileAccess.get_file_as_string("res://vehicles.json"))
    for child in ui_main.get_children():
        if child is CanvasLayer:child.layer=5

func make_titles():
    layer=CanvasLayer.new();layer.layer=20;add_child(layer)
    stamp=label(layer,"A S T R A   /   IN-ENGINE FOOTAGE",Vector2(170,125),32,Color(.69,.83,.93))
    rect(layer,Vector2(170,185),Vector2(100,4),Color(.3,.82,1))
    title_group=Control.new();layer.add_child(title_group)
    accent=rect(title_group,Vector2.ZERO,Vector2(94,7),Color(.25,.8,1))
    var fontsize=166 if shot_id=="01_orbit" else 102
    headline=label(title_group,shot.title,Vector2(0,42),fontsize,Color(.95,.98,1),bold)
    subtitle=label(title_group,shot.subtitle,Vector2(4,244 if shot_id=="01_orbit" else 180),36,Color(.63,.82,.94))
    if shot.get("python",false):make_python()
    if shot.get("outro",false):make_outro()

func make_python():
    title_group.visible=false
    label(layer,"CODE THE FLIGHT",Vector2(170,270),104,Color(.95,.98,1),bold)
    label(layer,"PYTHON API  /  CLOSED-LOOP CONTROL",Vector2(174,402),36,Color(.36,.78,1))
    python_panel=Control.new();python_panel.position=Vector2(170,530);layer.add_child(python_panel)
    rect(python_panel,Vector2.ZERO,Vector2(1900,1330),Color(.008,.022,.042,.94))
    rect(python_panel,Vector2.ZERO,Vector2(6,1330),Color(.24,.79,1,.9))
    label(python_panel,"ASTRA_CLIENT.PY",Vector2(65,40),31,Color(.5,.73,.89),mono)
    var rich=RichTextLabel.new();rich.position=Vector2(65,115);rich.size=Vector2(1790,1170)
    rich.bbcode_enabled=true;rich.scroll_active=false
    rich.add_theme_font_override("normal_font",mono);rich.add_theme_font_size_override("normal_font_size",39)
    var lines=str(manifest.python_code).split("\n");var text=""
    for line in lines:
        var safe=str(line).replace("[","[lb]")
        var tint="9ad8ff" if line.begins_with("from ") or line.begins_with("for ") else "f2d6a1" if "client." in line else "c8d9e9"
        text+="[color=#"+tint+"]"+safe+"[/color]\n"
    rich.text=text;python_panel.add_child(rich)
    python_metrics=label(layer,"",Vector2(2300,1550),49,Color(.8,.91,1),mono)
    label(layer,"EXECUTED THROUGH THE ASTRA PYTHON SDK",Vector2(2300,1810),28,Color(.4,.74,.92))

func make_outro():
    title_group.visible=false;stamp.visible=false
    darken=rect(layer,Vector2.ZERO,Vector2(3840,2160),Color(.002,.008,.023,.65))
    outro_group=Control.new();layer.add_child(outro_group)
    var logo=label(outro_group,"A S T R A",Vector2(0,400),190,Color(.94,.98,1),bold)
    logo.size.x=3840;logo.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
    var name=label(outro_group,"BY EMANUELE MAGNO",Vector2(0,700),45,Color(.52,.76,.91))
    name.size.x=3840;name.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
    var call=label(outro_group,"EXPLORE THE PORTFOLIO",Vector2(0,1120),49,Color(.74,.88,.98))
    call.size.x=3840;call.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
    var url=label(outro_group,"elemanprojects.com",Vector2(0,1210),145,Color(.95,.99,1),bold)
    url.size.x=3840;url.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
    rect(outro_group,Vector2(1530,1450),Vector2(780,5),Color(.2,.79,1))
    var credit=label(outro_group,'Music: "Horizons" by Scott Buckley  /  CC BY 4.0  /  scottbuckley.com.au\nFalcon 9 mesh: Fac-tory-o  /  CC BY-SA 4.0  ·  Full asset credits included',Vector2(0,1880),31,Color(.55,.67,.77))
    credit.size.x=3840;credit.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER

func _process(_dt):
    if done or tape.is_empty():return
    var index=clampi(frame,0,count-1)
    if preview:index=mini(count-1,int(float(manifest.fps)*2.5))
    var progress=float(index)/maxf(1,count-1)
    var t=float(index)/float(manifest.fps)
    scene.set_snapshot(tape[index])
    if shot.asset=="space-x-crew-dragon":scene.focus_height=0.0
    scene.pose_period=1.0/float(manifest.fps);scene.pose_elapsed=scene.pose_period
    scene.is_running=true
    var ease=progress*progress*(3.0-2.0*progress)
    var c=shot.camera
    scene.azimuth=deg_to_rad(lerpf(float(c[0]),float(c[3]),ease))
    scene.elevation=deg_to_rad(lerpf(float(c[1]),float(c[4]),ease))
    scene.distance=lerpf(float(c[2]),float(c[5]),ease)
    var fade=smoothstep(.25,1.0,t)*(1.0-smoothstep(float(shot.duration)-1.0,float(shot.duration)-.25,t))
    title_group.modulate.a=fade
    title_group.position=Vector2(175,1560+65*(1.0-smoothstep(.15,1.2,t)))
    if shot_id=="01_orbit":
        title_group.position=Vector2(175,680+65*(1.0-smoothstep(.15,1.2,t)))
        title_group.modulate.a=fade*(1.0-smoothstep(5.0,6.0,t))
        subtitle.text="ENGINEER THE NEXT FRONTIER"
        stamp.text="A S T R A   /   FALCON 9 IN SPACE"
    if shot.get("python",false):
        var s=tape[index].state
        python_metrics.text="TARGET     3.000 m\nALTITUDE   %.3f m\nTHROTTLE   %.1f %%\nLOOP       %03d / 300"%[float(s.altitude_m),float(s.command.throttle_pct),index+1]
    if ui_main!=null:
        ui_main.state=tape[index].state;ui_main.desktop=tape[index].desktop
        ui_main.details=tape[index].get("flight_details",[]);ui_main.update_hud()
        ui_main.widgets.render.text="IN-ENGINE CAPTURE  /  4K"
        ui_main.ui.modulate.a=1.0-smoothstep(3.0,4.0,t)
        title_group.position.x=790
        headline.add_theme_font_size_override("font_size",87)
    if shot.get("outro",false):
        outro_group.modulate.a=smoothstep(.25,1.1,t)
        outro_group.position.y=35*(1.0-smoothstep(.15,1.1,t))
        darken.color.a=lerpf(.45,.86,smoothstep(0,3,t))
    if frame==0:
        if scene.last_model_import_ok==false:push_error(scene.asset_error);get_tree().quit(2);return
        if preview:finish.call_deferred();done=true
    frame+=1
    if frame>=count and not done:done=true;finish.call_deferred()

func finish():
    await RenderingServer.frame_post_draw
    var texture=get_viewport().get_texture();var image=texture.get_image()
    if image.get_width()!=3840 or image.get_height()!=2160:
        push_error("Native 4K resolution required, got "+str(image.get_size()));get_tree().quit(3);return
    var file=work.path_join(shot_id+("-preview.png" if preview else "-last.png"))
    image.save_png(file)
    var report={"shot":shot_id,"native_size":[image.get_width(),image.get_height()],"frames":frame,"asset":scene.active_asset_id,"asset_loaded":scene.last_model_import_ok,"preview":preview,"screenshot":file}
    var out=FileAccess.open(work.path_join(shot_id+("-preview.json" if preview else "-capture.json")),FileAccess.WRITE)
    out.store_string(JSON.stringify(report,"  "))
    print("TRAILER CAPTURE: "+JSON.stringify(report))
    get_tree().quit()
