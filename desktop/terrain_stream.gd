extends Node3D
## Shared geometry, bounded chunk residency and incremental main-thread uploads.
var chunks={}
var meshes={}
var pending_chunks=[]
var centers={}
var material
var lunar=false
var built=0
var retired=0

func setup(surface,moon):
    material=surface;lunar=moon
    meshes[0]=make_grid(2048.0,32)
    meshes[1]=make_grid(8192.0,16)

func make_grid(span,n):
    var vertices=PackedVector3Array();var normals=PackedVector3Array();var uv=PackedVector2Array();var indices=PackedInt32Array();var tangents=PackedFloat32Array()
    for z in range(n+1):
        for x in range(n+1):
            vertices.append(Vector3(float(x)/n*span,0,float(z)/n*span))
            normals.append(Vector3.UP);uv.append(Vector2(float(x)/n,float(z)/n))
            tangents.append_array(PackedFloat32Array([1,0,0,1]))
    for z in range(n):
        for x in range(n):
            var a=z*(n+1)+x;var b=a+n+1
            indices.append_array(PackedInt32Array([a,a+1,b,a+1,b+1,b]))
    var arrays=[];arrays.resize(Mesh.ARRAY_MAX)
    arrays[Mesh.ARRAY_VERTEX]=vertices;arrays[Mesh.ARRAY_NORMAL]=normals;arrays[Mesh.ARRAY_TANGENT]=tangents;arrays[Mesh.ARRAY_TEX_UV]=uv;arrays[Mesh.ARRAY_INDEX]=indices
    var mesh=ArrayMesh.new();mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
    return mesh

func update_center(point):
    var wanted={}
    var changed=false
    for level in [0,1]:
        var span=2048.0 if level==0 else 8192.0
        var center=Vector2i(floori(point.x/span),floori(point.y/span))
        if centers.get(level)!=center:changed=true
        centers[level]=center
        for z in range(-3,4):
            for x in range(-3,4):
                if level==1 and x==0 and z==0:continue
                var tile=center+Vector2i(x,z);var key=Vector3i(tile.x,level,tile.y)
                wanted[key]={"key":key,"span":span,"rank":x*x+z*z+level*8}
    if not changed:return
    pending_chunks.clear()
    for key in chunks.keys():
        if not wanted.has(key):
            var node=chunks[key];remove_child(node);node.queue_free();chunks.erase(key);retired+=1
    for key in wanted:
        if not chunks.has(key):pending_chunks.append(wanted[key])
    pending_chunks.sort_custom(func(a,b):return a.rank<b.rank)
    # The nearest nine tiles cover teleports immediately. Boundary travel only
    # adds a row well outside the camera, spread over following frames.
    for i in range(mini(9 if chunks.is_empty() else 2,pending_chunks.size())):upload_next()

func upload_next():
    if pending_chunks.is_empty():return
    var item=pending_chunks.pop_front();var key=item.key
    var node=MeshInstance3D.new();node.mesh=meshes[key.y];node.material_override=material
    node.position=Vector3(key.x*item.span,-.4 if key.y==1 else 0,key.z*item.span)
    node.custom_aabb=AABB(Vector3(0,-150,0),Vector3(item.span,300,item.span))
    node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    add_child(node)
    node.set_instance_shader_parameter("chunk_origin",Vector2(node.position.x,node.position.z))
    chunks[key]=node;built+=1

func _process(_dt):
    for i in range(mini(2,pending_chunks.size())):upload_next()

func covers(point):
    return chunks.has(Vector3i(floori(point.x/2048.0),0,floori(point.y/2048.0)))
