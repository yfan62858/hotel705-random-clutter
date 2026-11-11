"""Isaac Sim viewer, reproducible episode controls and rendered verification."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser()
parser.add_argument('--seed',type=int,default=705)
parser.add_argument('--level',choices=['clean','low','medium','high'],default='medium')
mode=parser.add_mutually_exclusive_group()
mode.add_argument('--preview',action='store_true')
mode.add_argument('--check-controls',action='store_true')
args=parser.parse_args()

from isaacsim import SimulationApp
renderer_args=['--/renderer/multiGpu/enabled=false']
if os.name == 'nt':
    renderer_args += ['--d3d12','--/app/vulkan=false','--/app/d3d12=true']
app=SimulationApp({'headless':args.preview,'width':1440,'height':900,'active_gpu':0,'multi_gpu':False,
    'extra_args':renderer_args})
import carb
import omni.usd
import omni.ui as ui
import omni.timeline
from omni.kit.viewport.utility import get_active_viewport,capture_viewport_to_file
from isaacsim.core.utils.viewports import set_camera_view
from omni.physx import get_physx_scene_query_interface
from pxr import Gf, UsdGeom
from generator import generate,validate_scene

CAMERAS={
    'Room overview':([-.10,-2.45,2.02],[.45,-5.65,.45],14.),
    'Minibar tabletop':([.05,-4.22,1.65],[-.88,-3.30,.89],23.),
    'Floor litter':([-.20,-3.20,1.35],[.02,-5.30,.04],20.),
    'Window table':([.20,-6.25,1.65],[-.65,-6.70,.78],27.),
}
ctx=omni.usd.get_context()
timeline=omni.timeline.get_timeline_interface()
state={'seed':args.seed,'level':args.level,'busy':False,'ready':False,'exit':False,'failed':False}
status_model=ui.SimpleStringModel('Loading 7052 clutter...')
seed_model=ui.SimpleIntModel(args.seed)
level_names=['clean','low','medium','high']
level_model=ui.SimpleIntModel(level_names.index(args.level))
window=None
status_label=None

def message(s):
    print('[705 CLUTTER] '+s,flush=True)
    status_model.set_value(s)
    if status_label is not None:
        status_label.text=s
    (ROOT/'status.txt').write_text(s,encoding='utf-8')

async def ticks(count):
    for _ in range(count):
        await omni.kit.app.get_app().next_update_async()

def camera(name):
    stage=ctx.get_stage()
    path='/Clutter/ViewCamera'
    cam=UsdGeom.Camera.Define(stage,path)
    eye,target,focal=CAMERAS[name]
    cam.CreateFocalLengthAttr(focal)
    cam.CreateClippingRangeAttr(Gf.Vec2f(.02,100.))
    viewport=get_active_viewport()
    viewport.set_active_camera(path)
    set_camera_view(eye=eye,target=target,camera_prim_path=path,viewport_api=viewport)

async def support_check(manifest):
    # PhysX raycasts run below each item's bottom, so a prop cannot support itself.
    timeline.play()
    await ticks(12)
    query=get_physx_scene_query_interface()
    checks=[]
    for item in manifest['objects']:
        x,y,z=item['center_world']
        support_z=item['support_z']
        hit=query.raycast_closest((x,y,support_z+.0005),(0,0,-1),.04)
        ok=bool(hit.get('hit')) and abs(hit['position'][2]-support_z)<.012
        checks.append({'id':item['id'],'hit':bool(hit.get('hit')),'collider':str(hit.get('collision','')),'support_z_expected':support_z,'hit_z':float(hit['position'][2]) if hit.get('hit') else None,'passed':ok})
    timeline.pause()
    return checks

async def load(seed,level,capture=False):
    if state['busy']: return
    state['busy']=True
    try:
        message(f'Generating {level}, seed {seed}...')
        timeline.stop()
        path,manifest=generate(seed,level)
        validation=validate_scene(path)
        assert await ctx.open_stage_async(str(path)), 'Could not open clutter stage'
        await ticks(65)
        stage=ctx.get_stage()
        stage.SetEditTarget(stage.GetSessionLayer())
        carb.settings.get_settings().set('/physics/updateToUsd',True)
        carb.settings.get_settings().set('/persistent/app/viewport/displayOptions',0)
        # The original room's CPU collision setting matches the navigation integration.
        from pxr import PhysxSchema
        physics=PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath('/root/PhysicsScene'))
        physics.CreateEnableGPUDynamicsAttr(False)
        physics.CreateBroadphaseTypeAttr('MBP')
        physics.CreateEnableCCDAttr(True)
        camera('Room overview')
        await ticks(45)
        checks=await support_check(manifest)
        validation['physx_support_checks']=checks
        validation['all_physx_support_checks_passed']=all(x['passed'] for x in checks)
        validation['rendered_in']='Isaac Sim 5.1 / ' + ('Direct3D 12' if os.name == 'nt' else 'Vulkan')
        path.with_name('runtime_validation.json').write_text(json.dumps(validation,indent=2),encoding='utf-8')
        state.update(seed=seed,level=level,scene=path,manifest=manifest,ready=True)
        seed_model.set_value(seed)
        level_model.set_value(level_names.index(level))
        (ROOT/'active_scene.txt').write_text(str(path),encoding='utf-8')
        bad=[x['id'] for x in checks if not x['passed']]
        if bad:
            state['failed']=True
            message('Support check failed: '+', '.join(bad))
        else:
            message(f'Ready: {level} / seed {seed} / {len(manifest["objects"])} objects')
        if capture:
            for name in CAMERAS:
                camera(name)
                await ticks(55)
                filename=name.lower().replace(' ','_')+'.png'
                await capture_viewport_to_file(get_active_viewport(),str(path.parent/filename)).wait_for_result()
            camera('Room overview')
            message(f'CAPTURE COMPLETE: {level} seed {seed}; support checks: {not bool(bad)}')
            (ROOT/'preview_result.json').write_text(json.dumps({'scene':str(path),'validation':validation},indent=2),encoding='utf-8')
            state['exit']=True
    except Exception:
        state['failed']=True
        message(traceback.format_exc())
        if capture: state['exit']=True
    finally:
        state['busy']=False

def schedule(seed=None,level=None):
    if state['busy']: return
    return asyncio.ensure_future(load(seed if seed is not None else seed_model.get_value_as_int(),level or level_names[level_model.get_value_as_int()]))

async def snapshot():
    if state['busy'] or not state['ready']: return
    await capture_viewport_to_file(get_active_viewport(),str(state['scene'].parent/'snapshot.png')).wait_for_result()
    message('Saved snapshot.png beside the scene')

if not args.preview:
    window=ui.Window('705 Clutter | episode setup',width=345,height=440)
    with window.frame:
        with ui.VStack(spacing=8):
            ui.Label('705 HOTEL / RANDOM CLUTTER',height=28,style={'font_size':18})
            ui.Label('Generate before a task; props stay fixed during search.',word_wrap=True,height=35)
            with ui.HStack(height=26):
                ui.Label('Seed',width=80)
                ui.IntField(model=seed_model)
            with ui.HStack(height=26):
                ui.Label('Clutter',width=80)
                combo=ui.ComboBox(level_names.index(args.level),*level_names)
                level_model=combo.model.get_item_value_model()
            ui.Button('Generate this seed',clicked_fn=lambda:schedule(),height=30)
            ui.Button('New random layout (seed + 1)',clicked_fn=lambda:schedule(seed_model.get_value_as_int()+1),height=30)
            ui.Button('Restore clean room',clicked_fn=lambda:schedule(level='clean'),height=30)
            with ui.HStack(height=28):
                ui.Button('Room',clicked_fn=lambda:camera('Room overview'))
                ui.Button('Tabletop',clicked_fn=lambda:camera('Minibar tabletop'))
                ui.Button('Floor',clicked_fn=lambda:camera('Floor litter'))
            ui.Button('Save screenshot',clicked_fn=lambda:asyncio.ensure_future(snapshot()),height=28)
            ui.Label('',height=1)
            status_label=ui.Label('Preparing scene...',word_wrap=True,height=65)
            ui.Label('Paper is a rigid approximation. No ROS/navigation starts.',word_wrap=True,height=35)

async def check_controls():
    results=[]
    for seed,level in [(705,'medium'),(706,'medium'),(705,'clean'),(705,'medium')]:
        await schedule(seed,level)
        assert state['ready'] and state['seed']==seed and state['level']==level
        runtime=json.loads(state['scene'].with_name('runtime_validation.json').read_text())
        assert runtime['all_physx_support_checks_passed']
        results.append({'seed':seed,'level':level,'objects':len(state['manifest']['objects']),'support_passed':True})
    camera('Floor litter')
    await ticks(55)
    await capture_viewport_to_file(get_active_viewport(),str(state['scene'].parent/'floor_litter.png')).wait_for_result()
    camera('Minibar tabletop')
    await ticks(55)
    await capture_viewport_to_file(get_active_viewport(),str(state['scene'].parent/'minibar_tabletop.png')).wait_for_result()
    (ROOT/'controls_validation.json').write_text(json.dumps({'ui_constructed':True,'regenerate_new_seed_restore_clean_and_replay':results},indent=2))
    message('Ready: controls checked / medium / seed 705 / 18 objects')

asyncio.ensure_future(check_controls() if args.check_controls else load(args.seed,args.level,args.preview))
while app.is_running() and not state['exit']:
    app.update()
app.close()
if state['failed']:
    sys.exit(1)
