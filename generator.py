"""Generate reproducible clutter overlays for the bundled 7052 room."""
import argparse
import json
import math
import os
from pathlib import Path
import random
import sys

# Use Isaac Sim's USD build when running directly with its bundled Python.
_dlls = []
if 'omni.usd' not in sys.modules:
    configured_root = os.environ.get('ISAAC_SIM_PATH')
    candidates = [Path(configured_root)] if configured_root else []
    candidates.extend(Path(sys.executable).resolve().parents)
    isaac_root = next((p for p in candidates if (p / 'extscache').is_dir()), None)
    if isaac_root:
        libraries = sorted((isaac_root / 'extscache').glob('omni.usd.libs-*'))
        if libraries:
            library = libraries[-1]
            sys.path.insert(0, str(library))
            if os.name == 'nt':
                for directory in [library / 'bin', isaac_root / 'kit']:
                    if directory.is_dir():
                        _dlls.append(os.add_dll_directory(str(directory)))
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade

ROOT = Path(__file__).resolve().parent
ROOM = ROOT / 'assets' / 'room7052' / '7052_ver3_0925.usda'
COLA_ASSET = ROOT/'assets'/'so101_cola'/'cola_can.usda'
LEVELS = {'clean': (0, 0, 0), 'low': (4, 2, 3), 'medium': (7, 4, 7), 'high': (9, 7, 13)}
MOVABLES = ['Water1', 'Mug1', 'Tea1', 'Water2', 'Mug2', 'Tea2', 'Tea3', 'CookiePack1', 'CookiePack2']
SURFACES = [
    {'name': 'minibar_counter', 'prim': '/root/_7052_Flat_Walnut_Counter', 'rect': [-.86, -.55, -3.85, -2.86]},
    {'name': 'window_round_table', 'prim': '/root/_7052_Round_Table_Top', 'circle': [-.662, -6.704, .30]},
    {'name': 'bedside_table', 'prim': '/root/_7052_Asset_single_side_table', 'rect': [2.00, 2.46, -3.96, -3.68]},
    {'name': 'entry_bench', 'prim': '/root/_7052_Bench_Marble_Top', 'rect': [-1.00, -.67, -1.10, -.15]},
]
FLOORS = [
    {'name': 'floor_bed_aisle', 'rect': [-.27, .25, -6.35, -4.20], 'z': .001, 'prim': '/root/_7052_Floor_Backfill'},
    {'name': 'floor_minibar_aisle', 'rect': [-.26, .20, -3.78, -2.88], 'z': .001, 'prim': '/root/_7052_Floor_Backfill'},
    {'name': 'floor_entry', 'rect': [-.38, .10, -2.45, -1.35], 'z': .001, 'prim': '/root/_7052_Floor_Backfill'},
]

def bounds(stage, prim):
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default', 'render', 'proxy'])
    box = cache.ComputeWorldBound(prim).ComputeAlignedRange()
    return list(box.GetMin()), list(box.GetMax())

def intersects(a, b, margin=.008):
    return all(a[0][i] < b[1][i] + margin and a[1][i] > b[0][i] - margin for i in range(3))

def material(stage, path, color, metallic=0., roughness=.7, texture=None):
    m = UsdShade.Material.Define(stage, path)
    s = UsdShade.Shader.Define(stage, path + '/Surface')
    s.CreateIdAttr('UsdPreviewSurface')
    s.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    s.CreateInput('metallic', Sdf.ValueTypeNames.Float).Set(metallic)
    s.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(roughness)
    if texture:
        reader = UsdShade.Shader.Define(stage, path + '/UV')
        reader.CreateIdAttr('UsdPrimvarReader_float2')
        reader.CreateInput('varname', Sdf.ValueTypeNames.Token).Set('st')
        reader.CreateOutput('result', Sdf.ValueTypeNames.Float2)
        tex = UsdShade.Shader.Define(stage, path + '/Texture')
        tex.CreateIdAttr('UsdUVTexture')
        tex.CreateInput('file', Sdf.ValueTypeNames.Asset).Set(texture)
        tex.CreateInput('sourceColorSpace', Sdf.ValueTypeNames.Token).Set('sRGB')
        tex.CreateInput('st', Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(), 'result')
        tex.CreateOutput('rgb', Sdf.ValueTypeNames.Float3)
        s.GetInput('diffuseColor').ConnectToSource(tex.ConnectableAPI(), 'rgb')
    s.CreateOutput('surface', Sdf.ValueTypeNames.Token)
    m.CreateSurfaceOutput().ConnectToSource(s.ConnectableAPI(), 'surface')
    return m

def bind(prim, mat):
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(mat)

def mesh(stage, path, points, indices, counts, mat):
    m = UsdGeom.Mesh.Define(stage, path)
    m.CreatePointsAttr(points)
    m.CreateFaceVertexIndicesAttr(indices)
    m.CreateFaceVertexCountsAttr(counts)
    m.CreateSubdivisionSchemeAttr('none')
    m.CreateDoubleSidedAttr(True)
    bind(m.GetPrim(), mat)
    return m

def rigid(prim, mass):
    rb = UsdPhysics.RigidBodyAPI.Apply(prim)
    rb.CreateRigidBodyEnabledAttr(True)
    # Frozen per-episode placements: perception never chases teleported props.
    rb.CreateKinematicEnabledAttr(True)
    UsdPhysics.MassAPI.Apply(prim).CreateMassAttr(mass)

def make_can(stage, path, lying, rng):
    if not COLA_ASSET.is_file():
        raise FileNotFoundError(COLA_ASSET)
    root = UsdGeom.Xform.Define(stage, path)
    relative = os.path.relpath(COLA_ASSET, Path(stage.GetRootLayer().realPath).parent).replace('\\', '/')
    root.GetPrim().GetReferences().AddReference(relative, '/ColaCan')
    # Inherit the source geometry, photo textures, mass, inertia and colliders.
    UsdPhysics.RigidBodyAPI(root.GetPrim()).CreateKinematicEnabledAttr(True)
    # PhysX requires dynamic-body CCD to be off for kinematic scene props.
    root.GetPrim().CreateAttribute('physxRigidBody:enableCCD', Sdf.ValueTypeNames.Bool).Set(False)
    root.AddRotateXYZOp().Set(Gf.Vec3f(0, 90 if lying else 0, 0))
    return root.GetPrim()

def make_paper(stage, path, rng):
    root = UsdGeom.Xform.Define(stage, path)
    rigid(root.GetPrim(), .0015)
    paper = UsdShade.Material(stage.GetPrimAtPath('/Clutter/Looks/Paper'))
    pts, idx, counts = [], [], []
    n, rings = 18, 10
    scale = rng.uniform(.85, 1.20)
    for i in range(rings + 1):
        phi = math.pi * (i + .04) / (rings + .08)
        for j in range(n):
            a = 2*math.pi*j/n
            r = .034 * scale * rng.uniform(.67, 1.25)
            pts.append((r*math.sin(phi)*math.cos(a), r*math.sin(phi)*math.sin(a), r*.70*math.cos(phi)))
    for i in range(rings):
        for j in range(n):
            a=i*n+j; b=i*n+(j+1)%n; c=(i+1)*n+j; d=(i+1)*n+(j+1)%n
            idx.extend([a,b,d,a,d,c]); counts.extend([3,3])
    # Close both poles; faceted creases remain visible and the collision hull is stable.
    for ring, reverse in [(0, True), (rings, False)]:
        points = list(range(ring*n, (ring+1)*n))
        idx.extend(points[::-1] if reverse else points); counts.append(n)
    m = mesh(stage, path+'/CrumpledSheet', pts, idx, counts, paper)
    UsdPhysics.CollisionAPI.Apply(m.GetPrim())
    UsdPhysics.MeshCollisionAPI.Apply(m.GetPrim()).CreateApproximationAttr('convexHull')
    return root.GetPrim()

def place(stage, prim, center, floor_z, yaw):
    low, high = bounds(stage, prim)
    old_center = Gf.Vec3d(*[(a+b)/2 for a,b in zip(low, high)])
    world = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0)
    parent = UsdGeom.Xformable(prim.GetParent()).ComputeLocalToWorldTransform(0)
    new_center = Gf.Vec3d(center[0], center[1], floor_z + (high[2]-low[2])/2 + .001)
    delta = Gf.Matrix4d().SetTranslate(-old_center) * Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0,0,1),yaw)) * Gf.Matrix4d().SetTranslate(new_center)
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTransformOp(opSuffix='clutter').Set(world * delta * parent.GetInverse())
    rigid(prim, .0015 if 'Paper' in prim.GetName() else .025) if not prim.HasAPI(UsdPhysics.RigidBodyAPI) else UsdPhysics.RigidBodyAPI(prim).CreateKinematicEnabledAttr(True)

def generate(seed=705, level='medium', output=None):
    if level not in LEVELS:
        raise ValueError(level)
    if not ROOM.is_file():
        raise FileNotFoundError('Room asset missing. Download and extract the full GitHub Release ZIP. Expected: ' + str(ROOM))
    rng = random.Random(int(seed))
    out = Path(output) if output else ROOT/'scenes'/f'{level}_seed_{seed}'/'hotel705_clutter.usda'
    out = out.resolve(); out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        # Only replace our own generated overlay, never the source room.
        assert out.name == 'hotel705_clutter.usda' and out.parent.is_relative_to(ROOT/'scenes')
        layer = Sdf.Layer.FindOrOpen(str(out)); layer.Clear() if layer else None
        stage = Usd.Stage.Open(layer) if layer else Usd.Stage.CreateNew(str(out))
    else:
        stage = Usd.Stage.CreateNew(str(out))
    stage.GetRootLayer().subLayerPaths = [os.path.relpath(ROOM, out.parent).replace('\\', '/')]
    stage.SetDefaultPrim(stage.GetPrimAtPath('/root'))
    UsdGeom.SetStageMetersPerUnit(stage, 1.)
    UsdGeom.SetStageUpAxis(stage, 'Z')
    stage.SetStartTimeCode(0); stage.SetEndTimeCode(1000000)
    UsdGeom.Xform.Define(stage, '/Clutter')
    material(stage, '/Clutter/Looks/Paper', (.91,.90,.86), 0., .94)
    surfaces = [dict(s) for s in SURFACES]
    for s in surfaces:
        s['z'] = bounds(stage, stage.GetPrimAtPath(s['prim']))[1][2]
    moved_count, can_count, paper_count = LEVELS[level]
    moved_names = set(MOVABLES[:moved_count])
    occupied = []
    # Static bounds are conservative: large legacy scan groups are not usable AABB obstacles.
    for p in stage.GetPrimAtPath('/root').GetChildren():
        if p.GetName() in moved_names or p.GetName() in ('World', 'Looks', 'Joints', 'PhysicsScene'):
            continue
        if not p.IsA(UsdGeom.Xform):
            continue
        lo, hi = bounds(stage, p)
        if all(math.isfinite(v) for v in lo+hi) and hi[0]-lo[0] < 3.0 and hi[1]-lo[1] < 3.0:
            occupied.append((lo, hi))
    records=[]

    def sample(prim, kind, category, regions):
        lo,hi=bounds(stage,prim)
        radius=math.hypot(hi[0]-lo[0],hi[1]-lo[1])/2
        height=hi[2]-lo[2]
        # Reserve a circumscribed footprint, so any sampled yaw remains on its support.
        for _ in range(1200):
            s=rng.choice(regions)
            if 'circle' in s:
                cx,cy,r=s['circle']; r=r-radius-.018
                if r<=0: continue
                a=rng.uniform(0,2*math.pi); d=math.sqrt(rng.random())*r
                x,y=cx+d*math.cos(a),cy+d*math.sin(a)
            else:
                xmin,xmax,ymin,ymax=s['rect']
                if xmax-xmin < 2*radius+.02 or ymax-ymin < 2*radius+.02: continue
                x=rng.uniform(xmin+radius+.01,xmax-radius-.01)
                y=rng.uniform(ymin+radius+.01,ymax-radius-.01)
            candidate=([x-radius,y-radius,s['z']+.001],[x+radius,y+radius,s['z']+height+.001])
            if any(intersects(candidate,b,margin=0) for b in occupied): continue
            yaw=rng.uniform(-180,180)
            place(stage,prim,(x,y),s['z'],yaw)
            lo,hi=bounds(stage,prim)
            assert abs(lo[2]-(s['z']+.001))<1e-5, (prim.GetPath(),lo,s)
            occupied.append((lo,hi))
            prim.CreateAttribute('clutter:class',Sdf.ValueTypeNames.String).Set(kind)
            prim.CreateAttribute('clutter:taskCategory',Sdf.ValueTypeNames.String).Set(category)
            records.append({'id':prim.GetName(),'prim':str(prim.GetPath()),'class':kind,'task_category':category,'support':s['name'],'support_prim':s['prim'],'support_z':s['z'],'yaw_degrees':yaw,'center_world':[(a+b)/2 for a,b in zip(lo,hi)],'bounds_min':lo,'bounds_max':hi,'fixed_during_episode':True})
            return
        raise RuntimeError(f'No safe placement for {prim.GetPath()}')

    # Place larger props first so the small paper cannot consume all tabletop space.
    for i in range(can_count):
        lying = level=='high' and i%3==2
        p=make_can(stage,f'/Clutter/ColaCan_{i+1:02}',lying,rng)
        sample(p,'cola_can','unassigned',surfaces[:3])
    for name in MOVABLES[:moved_count]:
        prim=stage.GetPrimAtPath('/root/'+name)
        assert prim and prim.HasAPI(UsdPhysics.RigidBodyAPI), name
        kind='water_bottle' if name.startswith('Water') else 'mug' if name.startswith('Mug') else 'tea_packet' if name.startswith('Tea') else 'snack_packet'
        sample(prim,kind,'return_amenity',surfaces)
    for i in range(paper_count):
        p=make_paper(stage,f'/Clutter/UsedPaper_{i+1:02}',rng)
        # Mostly floor litter, some tabletop litter in high clutter.
        regions=surfaces[:2] if level=='high' and i%4==3 else FLOORS
        sample(p,'used_tissue','trash',regions)
    manifest={'schema_version':1,'seed':int(seed),'level':level,'room_version':'7052 ver3','scene':out.name,'counts':{'moved_amenities':moved_count,'cola_cans':can_count,'used_tissues':paper_count},'placement_mode':'kinematic_per_episode','objects':records,'notes':['Ground-truth metadata is for evaluation only; do not use as object-search input.','Used paper is a rigid visual approximation, not deformable paper.','Trash/return_amenity are scenario tags, not validated hotel service rules.']}
    manifest['cola_asset'] = {
        'path': os.path.relpath(COLA_ASSET, out.parent).replace('\\', '/'),
        'model': 'SO-101 photo-textured Coca-Cola 250 mL',
        'height_m': .0916, 'diameter_m': .06622, 'estimated_mass_kg': .275}
    stage.GetRootLayer().customLayerData={'generator':'705_clutter_v2_so101_cola','seed':int(seed),'level':level}
    stage.GetRootLayer().Save()
    out.with_name('objects.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return out,manifest

def validate_scene(path):
    from pxr import UsdUtils
    stage=Usd.Stage.Open(str(path)); data=json.loads(path.with_name('objects.json').read_text(encoding='utf-8'))
    assert sum(1 for p in stage.Traverse() if p.IsA(UsdGeom.Mesh))>=1650
    assert not UsdUtils.ComputeAllDependencies(str(path))[2]
    records=data['objects']
    for i,a in enumerate(records):
        p=stage.GetPrimAtPath(a['prim'])
        assert UsdPhysics.RigidBodyAPI(p).GetKinematicEnabledAttr().Get()
        if a['class'] == 'cola_can':
            assert p.GetChild('Shell').IsA(UsdGeom.Mesh), a['id']
            assert p.GetChild('Collision').HasAPI(UsdPhysics.CollisionAPI), a['id']
            assert p.GetChild('BodyContact').HasAPI(UsdPhysics.CollisionAPI), a['id']
            assert abs(UsdPhysics.MassAPI(p).GetMassAttr().Get() - .275) < 1e-6, a['id']
            assert p.GetAttribute('physxRigidBody:enableCCD').Get() is False, a['id']
        assert abs(a['bounds_min'][2]-a['support_z']-.001)<1e-5
        for b in records[i+1:]:
            assert not intersects((a['bounds_min'],a['bounds_max']),(b['bounds_min'],b['bounds_max']),margin=0), (a['id'],b['id'])
    return {'seed':data['seed'],'level':data['level'],'objects':len(records),'asset_references_resolved':True,'object_bounds_do_not_overlap':True,'all_props_fixed_per_episode':True}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--seed',type=int,default=705)
    parser.add_argument('--level',choices=list(LEVELS),default='medium')
    a=parser.parse_args()
    file,_=generate(a.seed,a.level)
    print(json.dumps({'scene':str(file),'validation':validate_scene(file)},ensure_ascii=False,indent=2))
