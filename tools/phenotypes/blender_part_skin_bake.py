"""Blender CPU worker: bind-pose ambient-occlusion and soft diffuse-lighting bakes for body-part GLBs.

All job parts are imported, baked transforms applied, then placed at their declared bind attachment
translation, so neighbouring parts occlude each other (armpits, groin, joints). For every part listed in
`bake`, its own image is baked from its glTF UVs (the importer's authored normal map is used for the
lighting pass). Linear float results are saved top-down (glTF V convention) in one npz per part.
Nothing is exported back into any GLB; inputs are hash-verified before and after.
"""
import hashlib, json, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Matrix, Vector


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    job_path = Path(argv[0]).resolve(); out = Path(argv[1]).resolve()
    job = json.loads(job_path.read_text())
    if out.exists():
        raise RuntimeError('Fresh output required')
    out.mkdir(parents=True)
    pins = {p['glb']: p['sha256'] for p in job['parts']}
    for path, digest in pins.items():
        if sha(path) != digest:
            raise RuntimeError('Input changed: ' + path)
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    objects = {}
    for part in job['parts']:
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.gltf(filepath=part['glb'])
        new = [o for o in bpy.context.scene.objects if o not in before and o.type == 'MESH']
        for o in new:
            w = o.matrix_world.copy(); o.parent = None; o.matrix_world = w
            bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            o.matrix_world = Matrix.Translation(Vector(part['attachment']))
            o.name = part['name']
        for o in [o for o in bpy.context.scene.objects if o not in before and o.type != 'MESH']:
            bpy.data.objects.remove(o, do_unlink=True)
        objects[part['name']] = new
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'
    scene.render.threads_mode = 'FIXED'; scene.render.threads = 4
    scene.cycles.use_denoising = False; scene.cycles.use_adaptive_sampling = False; scene.cycles.seed = job.get('seed', 7)
    scene.cycles.max_bounces = 2; scene.cycles.diffuse_bounces = 1
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background'); bg.inputs['Color'].default_value = (1, 1, 1, 1); bg.inputs['Strength'].default_value = job['worldStrength']
    scene.world.light_settings.distance = job['aoDistance']
    centre = Vector(job.get('lightTarget', [0, 0, 1.0]))
    for i, L in enumerate(job['lights']):
        bpy.ops.object.light_add(type='AREA', location=L['position'])
        light = bpy.context.object; light.data.energy = L['energy']; light.data.size = L['size']
        light.rotation_euler = (centre - light.location).to_track_quat('-Z', 'Y').to_euler()
    size = job['resolution']
    rows = []
    subsets = job.get('subsets', {})
    for name, spec in subsets.items():
        # bake only the declared faces (e.g. the skin of a part whose other material shares the UV square):
        # they are separated into their own object; the remaining faces stay in the scene as occluders only
        if sha(spec['centroids']) != spec['sha256']:
            raise RuntimeError('Subset changed: ' + spec['centroids'])
        cen = np.load(spec['centroids'])
        from mathutils import kdtree
        tree = kdtree.KDTree(len(cen))
        for i, c in enumerate(cen):
            tree.insert(Vector(c), i)
        tree.balance()
        parts_ = []
        for o in objects[name]:
            off = o.matrix_world.translation
            sel = np.array([tree.find(Vector(pl.center))[2] < spec.get('tolerance', 1e-5) for pl in o.data.polygons])
            if sel.any():
                import bmesh
                bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
                before = set(bpy.context.scene.objects)
                bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_mode(type='FACE'); bpy.ops.mesh.select_all(action='DESELECT')
                bm = bmesh.from_edit_mesh(o.data); bm.faces.ensure_lookup_table()
                for i in np.flatnonzero(sel):
                    bm.faces[int(i)].select_set(True)
                bmesh.update_edit_mesh(o.data)
                bpy.ops.mesh.separate(type='SELECTED'); bpy.ops.object.mode_set(mode='OBJECT')
                parts_ += [x for x in bpy.context.scene.objects if x not in before]
            print('subset', name, int(sel.sum()), 'of', len(sel), 'matched', len(cen), 'offset', tuple(off), flush=True)
        if sum(len(x.data.polygons) for x in parts_) != len(cen):
            raise RuntimeError('Subset faces not matched exactly for ' + name)
        objects[name] = parts_
    for name in job['bake']:
        objs = objects[name]
        result = {}
        for kind, samples in (('AO', job['aoSamples']), ('DIFFUSE', job['diffuseSamples'])):
            scene.cycles.samples = samples
            img = bpy.data.images.new(name + '-' + kind, width=size, height=size, alpha=False, float_buffer=True, is_data=True)
            for o in objs:
                for mat in o.data.materials:
                    nodes = mat.node_tree.nodes
                    node = nodes.new('ShaderNodeTexImage'); node.image = img; node.select = True; nodes.active = node
            bpy.ops.object.select_all(action='DESELECT')
            for o in objs:
                o.select_set(True)
            bpy.context.view_layer.objects.active = objs[0]
            bake = scene.render.bake
            bake.margin = job['marginPixels']; bake.margin_type = 'EXTEND'; bake.use_clear = True
            if kind == 'DIFFUSE':
                bake.use_pass_direct = True; bake.use_pass_indirect = True; bake.use_pass_color = False
            bpy.ops.object.bake(type=kind)
            px = np.empty(size * size * 4, dtype='f4'); img.pixels.foreach_get(px)
            result[kind] = px.reshape(size, size, 4)[::-1, :, :3].mean(axis=2)  # top-down rows (glTF V)
            for o in objs:
                for mat in o.data.materials:
                    nodes = mat.node_tree.nodes
                    for n in [n for n in nodes if n.type == 'TEX_IMAGE' and n.image == img]:
                        nodes.remove(n)
            bpy.data.images.remove(img)
        path = out / (name + '.npz')
        np.savez_compressed(path, ao=result['AO'].astype('f4'), diffuse=result['DIFFUSE'].astype('f4'))
        rows.append({'part': name, 'bake': str(path), 'sha256': sha(path)})
        print('baked', name, flush=True)
    for path, digest in pins.items():
        if sha(path) != digest:
            raise RuntimeError('Input changed during bake: ' + path)
    (out / 'bake.json').write_text(json.dumps({'kind': 'part-skin-bake', 'job': str(job_path), 'jobSha256': sha(job_path), 'bakes': rows,
                                               'policy': 'CPU Cycles AO + direct/indirect diffuse (no colour) in bind pose; top-down glTF V rows'}, indent=1))


main()
