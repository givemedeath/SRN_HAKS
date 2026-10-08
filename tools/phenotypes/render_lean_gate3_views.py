"""Blender: offline Gate 3 views of a compiled single-PLT body for every declared colour variant (palette x dye).

Same neutral setup as the accepted Gate 3 sheets (render-gate3-offline-views-v3): literal native compiled P/N/UV/T/sign
drive the shader (render_target_pilot_materials_v2.native_material: native TBN, PLT palette colour, runtime normal and
roughness maps); two area lights, orthographic camera, Standard / Medium High Contrast, Cycles CPU 16 spp + OIDN,
4 threads; rigid joint matrices of the pinned rig recipe samples. Full-body front/left/rear views of the idle sample
and every worst-case motion sample, plus the declared close-ups. --part-index/--part-count select a deterministic
round-robin share of the views for parallel processes. Not NWN client evidence.

Usage: blender ... --python render_lean_gate3_views.py -- --inputs <manifest> --output <fresh dir> [--part-index i --part-count n]
       [--variants k1,k2] [--only id1,id2]
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pose_preview_render_settings import apply_render_settings  # noqa: E402
from render_target_pilot_materials_v2 import mesh_object, native_material, texture  # noqa: E402

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser = argparse.ArgumentParser()
parser.add_argument('--inputs', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--part-index', type=int, default=0); parser.add_argument('--part-count', type=int, default=1)
parser.add_argument('--variants'); parser.add_argument('--only')
A = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
IN = A.inputs.resolve(); D = A.output.resolve(); assert not D.exists(); D.mkdir(parents=True)
man = json.loads(IN.read_text(encoding='utf-8')); frozen = {str(IN): sha(IN)}


def check(row):
    p = Path(row['path']); h = sha(p); assert h == row['sha256'], p; frozen[str(p)] = h; return p


rig = json.loads(check(man['rigRecipe']).read_text(encoding='utf-8')); samples = rig['samples']
variants = [v['key'] for v in man['variants']]
if A.variants: variants = [v for v in variants if v in A.variants.split(',')]
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False); scene = bpy.context.scene
settings = apply_render_settings(scene, 'cycles-cpu'); scene.cycles.seed = 0
scene.render.image_settings.file_format = 'PNG'; scene.view_settings.view_transform = 'Standard'; scene.view_settings.look = 'Medium High Contrast'
scene.world.use_nodes = True; bg = scene.world.node_tree.nodes['Background']; bg.inputs[0].default_value = (.13, .13, .13, 1); bg.inputs[1].default_value = .5
lights = []
for name, power, size in [('key', 420, 4), ('fill', 180, 4)]:
    dat = bpy.data.lights.new(name, 'AREA'); dat.energy = power; dat.shape = 'DISK'; dat.size = size
    ob = bpy.data.objects.new(name, dat); scene.collection.objects.link(ob); lights.append(ob)
cam = bpy.data.objects.new('camera', bpy.data.cameras.new('camera')); scene.collection.objects.link(cam); scene.camera = cam
cam.data.type = 'ORTHO'; cam.data.clip_start = .001; cam.data.clip_end = 50

objects = []; color_nodes = []; build = {}; t0 = time.monotonic()
for model in man['models']:
    check(model['binary'])
    for m in model['meshes']:
        a = np.load(check(m['arrays'])); native = {k: a[k] for k in ('position', 'normal', 'uv', 'tangent', 'sign', 'faces')}
        ob, ev = mesh_object(m['mesh'], native)
        mat, col = native_material(m['mesh']+'-mat', check(m['colors'][variants[0]]), check(m['normal']), check(m['roughness']))
        ob.data.materials.append(mat); objects.append((ob, model['joint']))
        color_nodes.append((col, {k: check(m['colors'][k]) for k in variants}))
        build[m['mesh']] = {'part': model['part'], 'role': m['role'], 'pltLayers': m['pltLayers'], **{k: ev[k] for k in ('vertices', 'triangles')}}
for ctx in man['context']:
    a = np.load(check(ctx['arrays'])); P = a['position']; F = a['faces'].astype(int); N = a['normal']; U = a['uv']
    me = bpy.data.meshes.new(ctx['name']); me.from_pydata(P.tolist(), [], F.tolist()); me.update()
    for poly in me.polygons: poly.use_smooth = True
    me.normals_split_custom_set_from_vertices((N/np.linalg.norm(N, axis=1)[:, None]).tolist())
    lv = np.empty(len(me.loops), dtype='i4'); me.loops.foreach_get('vertex_index', lv); lay = me.uv_layers.new(name='NativeUV'); lay.data.foreach_set('uv', U[lv].ravel())
    mat = bpy.data.materials.new(ctx['name']+'-mat'); mat.use_nodes = True; bs = mat.node_tree.nodes['Principled BSDF']
    col = texture(mat, check(ctx['colors'][variants[0]])); mat.node_tree.links.new(col.outputs['Color'], bs.inputs['Base Color']); bs.inputs['Roughness'].default_value = .8
    me.materials.append(mat); ob = bpy.data.objects.new(ctx['name'], me); scene.collection.objects.link(ob); objects.append((ob, ctx['joint']))
    color_nodes.append((col, {k: check(ctx['colors'][k]) for k in variants}))
build_seconds = time.monotonic()-t0


def sample_of(clip, fraction): return next(s for s in samples if s['clip'] == clip and abs(s['fraction']-fraction) < 1e-9)


def pose(s):
    for ob, joint in objects: ob.matrix_world = Matrix(s['matrices'][joint])
    bpy.context.view_layer.update()


def joint_pos(s, j): return Vector(np.asarray(s['matrices'][j])[:3, 3].tolist())


def bbox():
    pts = [ob.matrix_world@Vector(c) for ob, _ in objects for c in ob.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


DIRS = {'front': (0, 1, 0), 'rear': (0, -1, 0), 'left': (1, 0, 0), 'right': (-1, 0, 0), 'front-left': (.72, .72, 0), 'front-right': (-.72, .72, 0),
        'rear-left': (.72, -.72, 0), 'rear-right': (-.72, -.72, 0), 'below-rear': (0, -.8, -.6), 'below-front': (0, .8, -.5), 'char-left': (-1, 0, 0),
        'front-char-left': (-.72, .72, 0), 'front-char-right': (.72, .72, 0), 'rear-char-left': (-.72, -.72, 0), 'rear-char-right': (.72, -.72, 0),
        'front-above': (0, .8, .6), 'rear-above': (0, -.6, .8)}


def aim(center, direction, scale, resx, resy):
    d = Vector(direction).normalized(); cam.location = center+d*4; cam.rotation_euler = (center-cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = scale; scene.render.resolution_x = resx; scene.render.resolution_y = resy
    side = d.cross(Vector((0, 0, 1))); side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
    for ob, off in zip(lights, [(-3*side+d*4+Vector((0, 0, 4))), (3*side+d*2+Vector((0, 0, 2)))]):
        ob.location = center+off; ob.rotation_euler = (center-ob.location).to_track_quat('-Z', 'Y').to_euler()


idle = man['idleSample']; worst = man['worstCaseMotion']; motion = {'idle': idle, **worst}
views = []
for label, s in [('idle', idle)]+list(worst.items()):
    for view in ('front', 'left', 'rear'):
        views.append({'id': f'full-{label}-{view}', 'kind': 'full', 'clip': s['clip'], 'fraction': s['fraction'], 'view': view})
for row in man['closeups']:
    s = motion[row['sample']]
    views.append({'id': row['id'], 'kind': 'close', 'clip': s['clip'], 'fraction': s['fraction'], 'center': row['center'], 'view': row['view'],
                  'scale': row['scale'], 'offset': row.get('offset', [0, 0, 0])})
if A.only: views = [v for v in views if v['id'] in A.only.split(',')]
views = views[A.part_index::A.part_count]
rendered = []; timings = []
for v in views:
    s = sample_of(v['clip'], v['fraction']); pose(s)
    if v['kind'] == 'full':
        lo, hi = bbox(); center = (lo+hi)/2; size = hi-lo; d = Vector(DIRS[v['view']])
        width = abs(size.x) if abs(d.y) > .5 else abs(size.y)
        aim(center, DIRS[v['view']], max(size.z*1.06, width*1.06*1.5), 600, 900)
    else:
        center = sum((joint_pos(s, j) for j in v['center']), Vector())/len(v['center'])+Vector(v['offset'])
        aim(center, DIRS[v['view']], v['scale'], 560, 560)
    for key in variants:
        for node, files in color_nodes: node.image = bpy.data.images.load(str(files[key]), check_existing=True)
        dest = D/f"{v['id']}-{key}.png"; scene.render.filepath = str(dest); began = time.monotonic()
        bpy.ops.render.render(write_still=True); sec = round(time.monotonic()-began, 2); timings.append(sec)
        rendered.append({**{k: v[k] for k in ('id', 'kind', 'clip', 'fraction', 'view')}, 'variant': key, 'path': str(dest), 'sha256': sha(dest), 'seconds': sec,
                         'cameraWorld': [list(r) for r in cam.matrix_world], 'orthoScale': cam.data.ortho_scale})
        print(json.dumps({'rendered': dest.name, 'seconds': sec}), flush=True)
for p, h in frozen.items(): assert sha(p) == h, p
helper_dir = Path(__file__).resolve().parent
report = {'kind': 'lean-gate3-offline-views', 'inputs': {'path': str(IN), 'sha256': sha(IN)}, 'renderSettings': settings, 'samplesPerPixel': scene.cycles.samples,
          'partIndex': A.part_index, 'partCount': A.part_count, 'variants': variants, 'buildSeconds': round(build_seconds, 2),
          'renderSecondsTotal': round(sum(timings), 2), 'renders': rendered, 'meshes': build, 'frozenInputs': frozen,
          'helpers': {name: sha(helper_dir/name) for name in ('render_lean_gate3_views.py', 'render_target_pilot_materials_v2.py', 'pose_preview_render_settings.py')},
          'compiledRuntimeBinariesRendered': True, 'normalMapEnabled': True,
          'limits': ['Neutral Cycles CPU lighting/BRDF, not the NWN client shader.', 'Head/neck context lacks native tangents; authored normals only.',
                     'Matrices are the pinned rig recipe samples; continuous motion between samples is not shown.']}
(D/'render-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8'); print(json.dumps({'report': str(D/'render-report.json')}), flush=True)
