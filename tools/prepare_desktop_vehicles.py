"""Blender: prepare existing attributed vehicles, preserving their geometry.

No vehicle is constructed from primitives. The only generated nodes are pivots
and assembly transforms from upstream CAD/SDF metadata.
Run: blender --background --python tools/prepare_desktop_vehicles.py
"""
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET
import bpy
import bmesh
from mathutils import Matrix,Vector,Euler

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'assets/source/vehicles'
OUT=ROOT/'assets/vehicles'
REPORT=[]

def reset():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)

def bounds(objects):
    points=[obj.matrix_world@Vector(v) for obj in objects if obj.type=='MESH' for v in obj.bound_box]
    return (Vector(tuple(min(p[i] for p in points) for i in range(3))),
            Vector(tuple(max(p[i] for p in points) for i in range(3))))

def pivot(name,objects,point):
    node=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(node);node.location=point
    bpy.context.view_layer.update()
    for obj in objects:
        world=obj.matrix_world.copy();obj.parent=node;obj.matrix_world=world
    return node

def blades(count):
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and 'blade' in o.name.lower() and ('propeller' in o.name.lower() or 'prop ' in o.name.lower())]
    if not meshes:return
    groups=[meshes] if count==1 else [[o for o in meshes if (bounds([o])[0].y+bounds([o])[1].y>0)==side] for side in (False,True)]
    for i,group in enumerate(groups):
        if group:
            low,high=bounds(group);pivot('Propeller_'+str(i),group,(low+high)*.5)

def quad_blades():
    # Separate only the existing blade faces, using the author's rotor centres.
    original=[o for o in bpy.context.scene.objects if o.type=='MESH']
    centers=[Vector((x,-z,.235)) for x,z in [(.22,.22),(-.22,.22),(-.22,-.22),(.22,-.22)]]
    for obj in original:
        bpy.context.view_layer.objects.active=obj
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        mesh=obj.data
        groups={i:[] for i in range(4)}
        for face in mesh.polygons:
            c=obj.matrix_world@face.center
            material=mesh.materials[face.material_index].name.lower() if mesh.materials else ''
            if not ('orange' in material or material=='black'):continue
            for i,center in enumerate(centers):
                d=math.hypot(c.x-center.x,c.y-center.y)
                if .028<d<.14 and .203<c.z<.252:
                    groups[i].append(face.index);break
        for i,indices in groups.items():
            if not indices:continue
            bm=bmesh.new();bm.from_mesh(mesh)
            bm.faces.ensure_lookup_table();keep=set(indices)
            bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index not in keep],context='FACES')
            data=bpy.data.meshes.new('Original rotor blade faces');bm.to_mesh(data);bm.free()
            for mat in mesh.materials:data.materials.append(mat)
            blade=bpy.data.objects.new('Original_blades_'+str(i),data);bpy.context.collection.objects.link(blade);blade.matrix_world=obj.matrix_world.copy()
            pivot('Rotor_'+str(i),[blade],centers[i])
        remove={j for indices in groups.values() for j in indices}
        bm=bmesh.new();bm.from_mesh(mesh);bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index in remove],context='FACES');bm.to_mesh(mesh);bm.free()

def export(name,low_budget=0):
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    groups={}
    for obj in objects:
        ancestor=obj.parent;animated=False
        while ancestor:
            if ancestor.name.startswith(('Rotor_','Propeller_')):animated=True;break
            ancestor=ancestor.parent
        names=tuple(mat.name if mat else '' for mat in obj.data.materials)
        if animated or any('glaz' in n.lower() or 'glass' in n.lower() or 'lens' in n.lower() for n in names):continue
        groups.setdefault(names,[]).append(obj)
    for group in groups.values():
        if len(group)<2:continue
        bpy.ops.object.select_all(action='DESELECT')
        for obj in group:
            world=obj.matrix_world.copy();obj.parent=None;obj.matrix_world=world;obj.select_set(True)
        bpy.context.view_layer.objects.active=group[0]
        bpy.ops.object.join()
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    for obj in objects:
        if low_budget and len(obj.data.polygons)>1000:
            mod=obj.modifiers.new('Display LOD','DECIMATE');mod.ratio=max(.15,min(1,low_budget/sum(len(o.data.polygons) for o in objects)))
    bpy.ops.export_scene.gltf(filepath=str(OUT/name),export_format='GLB',export_draco_mesh_compression_enable=False,
        export_apply=True,export_extras=True,export_yup=True)
    low,high=bounds(objects)
    graph=bpy.context.evaluated_depsgraph_get()
    REPORT.append(dict(file=name,bounds_blender=[list(low),list(high)],objects=len(objects),
                       triangles=sum(sum(len(p.vertices)-2 for p in o.evaluated_get(graph).data.polygons) for o in objects),
                       pivots=[o.name for o in bpy.context.scene.objects if o.type=='EMPTY' and (o.name.startswith('Rotor_') or o.name.startswith('Propeller_'))]))

def imported(source,output,count=0,quad=False,budget=0):
    reset();bpy.ops.import_scene.gltf(filepath=str(source))
    if count:blades(count)
    if quad:quad_blades()
    export(output,budget)

def pose(text):
    values=[float(v) for v in (text or '0 0 0 0 0 0').split()]
    return Matrix.Translation(Vector(values[:3]))@Euler(values[3:],'XYZ').to_matrix().to_4x4()

def typhoon():
    reset();folder=SOURCE/'px4-typhoon'
    xml=ET.parse(folder/'typhoon_h480.sdf.jinja').getroot().find('model')
    palette={'DarkGrey':(.045,.05,.06,1),'Black':(.015,.018,.022,1),'Grey':(.25,.27,.3,1),'White':(.72,.74,.76,1)}
    for link in xml.findall('link'):
        parent=bpy.data.objects.new(link.attrib['name'],None);bpy.context.collection.objects.link(parent)
        parent.matrix_world=pose(xml.findtext('pose'))@pose(link.findtext('pose'))
        if parent.name.startswith('rotor_'):parent.name='Rotor_'+parent.name.split('_')[1]
        for visual in link.findall('visual'):
            mesh=visual.find('geometry/mesh')
            if mesh is None:continue
            path=folder/Path(mesh.findtext('uri')).name
            if not path.exists():continue
            before=set(bpy.context.scene.objects)
            bpy.ops.wm.stl_import(filepath=str(path))
            objects=set(bpy.context.scene.objects)-before
            color_name=visual.findtext('material/script/name','Gazebo/DarkGrey').split('/')[-1]
            material=bpy.data.materials.get(color_name) or bpy.data.materials.new(color_name)
            material.diffuse_color=palette.get(color_name,palette['DarkGrey']);material.use_nodes=True
            bsdf=material.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=material.diffuse_color
            bsdf.inputs['Roughness'].default_value=.38
            for obj in objects:
                obj.name=visual.attrib.get('name',path.stem);obj.parent=parent
                obj.matrix_parent_inverse=Matrix.Identity(4)
                obj.matrix_basis=pose(visual.findtext('pose'))@Matrix.Diagonal([*map(float,mesh.findtext('scale','1 1 1').split()),1])
                obj.data.materials.clear();obj.data.materials.append(material)
                for face in obj.data.polygons:face.use_smooth=True
    export('px4-typhoon-h480-high.glb')
    export('px4-typhoon-h480.glb',60000)

OUT.mkdir(parents=True,exist_ok=True)
imported(SOURCE/'nasa-insight-panels-stowed.glb','nasa-insight-descent.glb')
imported(SOURCE/'nasa-insight-panels-deployed.glb','nasa-insight-landed.glb')
imported(SOURCE/'innerscene-twin-turboprop.glb','innerscene-twin-turboprop-high.glb',count=2)
imported(SOURCE/'innerscene-twin-turboprop.glb','innerscene-twin-turboprop.glb',count=2,budget=55000)
imported(OUT/'innerscene-propeller-aircraft-high.glb','desktop-propeller-aircraft-high.glb',count=1)
imported(OUT/'innerscene-propeller-aircraft.glb','desktop-propeller-aircraft.glb',count=1)
imported(OUT/'quadrotor-innerscene.glb','desktop-quadcopter.glb',quad=True)
typhoon()
(ROOT/'build/prebuilt-vehicles.json').write_text(json.dumps(REPORT,indent=2)+'\n')
print('PREBUILT VEHICLES READY: '+str(len(REPORT)))
