"""CPU offline views from target-bound native geometry/material preparation.

No glTF tangent reconstruction, native compilation, engine playback or acceptance.
The stock legacy path has literal normals and explicitly lacks a normal-map TBN.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import target_contract as c
from prepare_target_native_material_preview import pin, save, digest_array, native_arrays, verify_loop_representation
from render_target_pilot_materials_v2 import mesh_object, native_material, texture
from pose_preview_render_settings import apply_render_settings


def asset_pin(row, frozen):
    return pin({'path': row['path'], 'sha256': row['sha256']}, frozen)


def literal_mesh(name, native):
    native_arrays(native)
    if 'tangent' in native:
        obj, original = mesh_object(name, native)
    else:
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(native['position'].tolist(), [], native['faces'].tolist())
        mesh.update()
        obj = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(obj)
        layer = mesh.uv_layers.new(name='NativeUV')
        loops = np.empty(len(mesh.loops), dtype=np.int32); mesh.loops.foreach_get('vertex_index', loops)
        layer.data.foreach_set('uv', native['uv'][loops].ravel())
        attr = mesh.attributes.new('native_normal', 'FLOAT_VECTOR', 'POINT')
        attr.data.foreach_set('vector', native['normal'].ravel())
        original = {'blenderRegeneratedTangentsUsed': False, 'missingNativeTangentArrays': True}
    mesh = obj.data
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    if hasattr(mesh, 'use_auto_smooth'):
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = np.pi
    mesh.normals_split_custom_set_from_vertices(native['normal'].tolist())
    mesh.update()
    if hasattr(mesh, 'calc_normals_split'):
        mesh.calc_normals_split()
    c.require(mesh.has_custom_normals, 'Native custom normals are not active')
    loops = np.empty(len(mesh.loops), dtype=np.int32); mesh.loops.foreach_get('vertex_index', loops)
    positions = np.empty(len(mesh.vertices)*3, dtype='f4'); mesh.vertices.foreach_get('co', positions)
    normals = np.empty(len(mesh.loops)*3, dtype='f4'); mesh.loops.foreach_get('normal', normals)
    uv = np.empty(len(mesh.loops)*2, dtype='f4'); mesh.uv_layers['NativeUV'].data.foreach_get('uv', uv)
    attributes = {}
    for key, attr_name in [('normal', 'native_normal'), ('tangent', 'native_tangent'), ('sign', 'native_handedness')]:
        if key not in native:
            continue
        width = native[key].size; value = np.empty(width, dtype='f4')
        mesh.attributes[attr_name].data.foreach_get('value' if key == 'sign' else 'vector', value)
        attributes[key] = value.reshape(native[key].shape)
    proof = verify_loop_representation(native, loops, positions.reshape(-1, 3)[loops],
                                       normals.reshape(-1, 3), uv.reshape(-1, 2), attributes)
    return obj, {**original, **proof, 'autoSmoothEnabledWhereSupported': getattr(mesh, 'use_auto_smooth', None),
                 'nativeArrayDigests': {key: digest_array(value) for key, value in native.items()}}


def stock_material(name, color_path):
    material = bpy.data.materials.new(name); material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    color = texture(material, color_path)
    material.node_tree.links.new(color.outputs['Color'], shader.inputs['Base Color'])
    shader.inputs['Roughness'].default_value = .8
    shader.inputs['Metallic'].default_value = 0
    shader.inputs['Specular IOR Level'].default_value = .5
    return material, color


def fixture_test(output):
    """Actual Blender loop normals must follow nongeometric literal native N."""
    output = Path(output).resolve(); c.require(not output.exists(), 'Fresh Blender self-test output required'); output.mkdir()
    p = np.asarray([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype='<f4')
    n = np.tile(np.asarray([0, .6, .8], dtype='<f4'), (3, 1))
    native = {'position': p, 'normal': n, 'uv': p[:, :2].copy(),
              'tangent': np.tile(np.asarray([1, 0, 0], dtype='<f4'), (3, 1)),
              'sign': np.ones((3, 1), dtype='<f4'), 'faces': np.asarray([[0, 1, 2]], dtype='<u2')}
    obj, proof = literal_mesh('nongeometric-authored-normal-fixture', native)
    mesh = obj.data
    mesh.normals_split_custom_set_from_vertices(np.tile([0, 0, 1], (3, 1)).tolist())
    if hasattr(mesh, 'calc_normals_split'):
        mesh.calc_normals_split()
    actual = np.empty(9, dtype='f4'); mesh.loops.foreach_get('normal', actual)
    rejected = False
    try:
        verify_loop_representation(native, np.asarray([0, 1, 2]), p, actual.reshape(-1, 3),
                                   native['uv'], {key: native[key] for key in ('normal', 'tangent', 'sign')})
    except ValueError:
        rejected = True
    c.require(rejected, 'Geometric normals must not silently replace native normals')
    save(output/'self-test.json', {'kind': 'offline-native-material-blender-loop-self-test', 'pass': True,
         'actualLiteralNormalLoopProof': proof, 'silentlyGeometricNormalsRejected': rejected,
         'blenderVersion': bpy.app.version_string, 'sourceAssetsUsed': False, 'offlineOnly': True})


def render(preparation_path, preparation_sha256, output):
    preparation_path = Path(preparation_path).resolve(); frozen = {}
    pin({'path': str(preparation_path), 'sha256': preparation_sha256}, frozen)
    prep = json.loads(preparation_path.read_text(encoding='utf-8'))
    c.require(prep['schemaVersion'] == 1 and prep['kind'] == 'target-offline-native-material-preview-preparation'
              and prep['offlineOnly'] is True and prep['nativeDisplayScale'] == 1 and prep['paletteRows'] == [3, 8],
              'Completed literal offline native preview preparation required')
    tp = pin({'path': prep['targetContract'], 'sha256': prep['targetContractSha256']}, frozen)
    target = c.load(tp); c.verify_binding(prep, tp, target, prep['coordinateSpace'])
    from prepare_target_native_material_preview import validate_identity
    validate_identity(target)
    for path, h in {**prep['frozenInputs'], **prep['outputHashes']}.items():
        pin({'path': path, 'sha256': h}, frozen)
    output = Path(output).resolve(); c.require(not output.exists(), 'Fresh immutable native render output required')
    output.mkdir(); (output/'helpers').mkdir()
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    objects = {}; material_rows = {}; proofs = {}; literal_arrays = {}
    for part, rows in prep['parts'].items():
        for row in rows:
            q = asset_pin(row['arrays'], frozen)
            with np.load(q, allow_pickle=False) as archive:
                native = {key: archive[key] for key in archive.files}
            c.require(set(native) == set(row['arrays']['digests'])
                      and all(digest_array(value) == row['arrays']['digests'][key] for key, value in native.items()),
                      'Literal native archive differs from preparation')
            obj, proof = literal_mesh(row['name'], native)
            objects[(part, row['name'])] = obj; proofs[row['name']] = proof; literal_arrays[row['name']] = native
            color_path = asset_pin(row['colors']['3'], frozen)
            if row['normal'] is not None:
                normal = pin(row['normal'], frozen); roughness = pin(row['roughness'], frozen)
                material, color = native_material(row['name'], color_path, normal, roughness)
                policy = 'Original RG normal map through normalized native N/T/sign; original roughness; neutral offline Principled.'
            else:
                c.require('tangent' not in native or prep['partProvenance'][part]['kind'] == 'installed-stock-neck',
                          'Missing normal material needs explicit stock policy')
                material, color = stock_material(row['name'], color_path)
                policy = 'Stock native custom normals + actual PLT; neutral diffuse roughness .8; no normal map or synthesized tangents.'
            obj.data.materials.append(material)
            shader = next(node for node in material.node_tree.nodes if node.type == 'BSDF_PRINCIPLED')
            material_rows[(part, row['name'])] = (row, material, color, shader, policy)
    scene = bpy.context.scene; settings = apply_render_settings(scene, 'cycles-cpu')
    scene.cycles.use_denoising = False; scene.cycles.use_adaptive_sampling = False
    scene.cycles.seed = 41; scene.cycles.use_animated_seed = False
    settings.update(denoising=False, adaptiveSampling=False, seed=41)
    scene.render.resolution_x = prep['render']['width']; scene.render.resolution_y = prep['render']['height']
    scene.render.resolution_percentage = 100; scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'; scene.render.image_settings.color_depth = '16'
    scene.view_settings.view_transform = 'Standard'; scene.view_settings.look = 'None'; scene.view_settings.gamma = 1
    scene.world.use_nodes = True; world = scene.world.node_tree.nodes.get('Background')
    world.inputs['Color'].default_value = (.15, .15, .15, 1)
    bpy.ops.object.camera_add(); camera = bpy.context.object; scene.camera = camera
    camera.data.type = 'ORTHO'; camera.data.clip_start = .00001; camera.data.clip_end = 100
    lights = []
    for energy in (2.4, .8):
        bpy.ops.object.light_add(type='SUN'); light = bpy.context.object; light.data.energy = energy
        light.data.angle = .15; lights.append(light)
    renders = []
    for pose in prep['poses']:
        for (part, name), obj in objects.items():
            obj.matrix_world = Matrix(pose['matrices'][part])
        bpy.context.view_layer.update()
        for plan in pose['cameras']:
            matrix = np.asarray(plan['matrixWorld'], float); camera.matrix_world = Matrix(matrix)
            camera.data.ortho_scale = plan['orthographicHeightMetres']
            u, v, z = matrix[:3, 0], matrix[:3, 1], matrix[:3, 2]
            for light, direction in zip(lights, (z+.6*u+.8*v, z-.8*u+.2*v)):
                light.rotation_euler = (-Vector(direction)).to_track_quat('-Z', 'Y').to_euler()
            for palette_row in prep['paletteRows']:
                for row, material, color, shader, policy in material_rows.values():
                    path = asset_pin(row['colors'][str(palette_row)], frozen)
                    color.image = bpy.data.images.load(str(path), check_existing=True)
                    color.image.colorspace_settings.name = 'sRGB'
                for mode in prep['render']['modes']:
                    emission = mode == 'emission-only-color'
                    scene.cycles.samples = 8 if emission else 16
                    scene.view_settings.exposure = 0 if emission else -.7
                    world.inputs['Strength'].default_value = 0 if emission else .35
                    for light in lights:
                        light.hide_render = emission
                    for row, material, color, shader, policy in material_rows.values():
                        tree = material.node_tree
                        out = next(node for node in tree.nodes if node.type == 'OUTPUT_MATERIAL')
                        for link in list(out.inputs['Surface'].links):
                            tree.links.remove(link)
                        if emission:
                            emit = tree.nodes.get('LiteralPaletteEmission') or tree.nodes.new('ShaderNodeEmission')
                            emit.name = 'LiteralPaletteEmission'; emit.inputs['Strength'].default_value = 1
                            tree.links.new(color.outputs['Color'], emit.inputs['Color'])
                            tree.links.new(emit.outputs[0], out.inputs['Surface'])
                        else:
                            tree.links.new(shader.outputs[0], out.inputs['Surface'])
                    name = pose['definition']['id']+'-'+plan['id']+'-palette'+str(palette_row)+'-'+mode+'.png'
                    path = output/name; scene.render.filepath = str(path)
                    print('RENDER '+name, flush=True); bpy.ops.render.render(write_still=True)
                    row = {'path': str(path), 'sha256': c.sha(path), 'pose': pose['definition'], 'camera': plan,
                           'paletteRow': palette_row, 'mode': mode, 'exposure': scene.view_settings.exposure,
                           'samples': scene.cycles.samples, 'offlineOnly': True, 'clientAccepted': False}
                    save(output/(name+'.receipt.json'), row); renders.append(row)
    helper_snapshots = {}
    tools = Path(__file__).resolve().parent
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.suffix == '.py' and tools in path.parents:
                c.require(str(path) in frozen and c.sha(path) == frozen[str(path)], 'Unpinned render helper: '+str(path))
                destination = output/'helpers'/path.name; shutil.copyfile(path, destination)
                helper_snapshots[str(path)] = {'path': str(destination), 'sha256': c.sha(destination)}
    input_pin = {'path': str(Path(__file__).resolve()), 'sha256': c.sha(__file__)}
    c.require(frozen.get(input_pin['path']) == input_pin['sha256'], 'Renderer differs from prepared snapshot')
    for path, h in frozen.items():
        c.require(c.sha(path) == h, 'Native preview input changed while rendering')
    result = {'schemaVersion': 1, 'kind': 'offline-native-material-preview',
              **c.binding(tp, target, prep['coordinateSpace']), 'preparation': {'path': str(preparation_path), 'sha256': preparation_sha256},
              'literalMeshRepresentation': proofs, 'partProvenance': prep['partProvenance'],
              'renderSettings': settings, 'renders': renders, 'helperSnapshots': helper_snapshots,
              'frozenInputs': frozen, 'paletteLookupBeforeFiltering': True, 'nativeDisplayScale': 1,
              'statureApplications': 0, 'nativeGeometryEdited': False, 'nativeMapsEdited': False,
              'blenderRegeneratedTangentsUsed': False, 'offlineOnly': True, 'literalClientCapture': False,
              'clientAccepted': False, 'productionAccepted': False,
              'limitations': ['Offline Cycles filtering, interpolation, normal encoding, BRDF, lighting and color response differ from NWN.',
                  'Level-zero per-texel palette lookup does not prove engine mip behavior or ordinary/HQ shaders.',
                  'Only declared parts/poses/views are shown. Garment ownership and full-body/equipment/client acceptance remain separate.',
                  'Stock neck uses literal native P/N/UV/F/white colors but no normal map or invented missing T/sign. Neutral roughness is declared.']}
    receipt = output/'preview.json'; save(receipt, result)
    print(json.dumps({'receipt': str(receipt), 'sha256': c.sha(receipt), 'renders': len(renders)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path)
    parser.add_argument('--preparation-sha256')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    c.require(args.self_test != bool(args.preparation) and (args.self_test or args.preparation_sha256),
              'Choose pinned preparation or isolated nonasset loop self-test')
    if args.self_test:
        fixture_test(args.output)
    else:
        render(args.preparation, args.preparation_sha256, args.output)

