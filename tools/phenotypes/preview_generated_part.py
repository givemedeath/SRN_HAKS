"""Blender CPU-only, read-only orthographic review of a collected detached GLB.

These renders inspect generated anatomy; they are not NWN client evidence.
Source geometry, authored normals, UVs and material bytes remain unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Matrix, Vector


def sha(path):
    with Path(path).open('rb') as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--generation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--material-mode', choices=('textured', 'clay', 'base-color'), default='textured')
    parser.add_argument('--anterior-axis',choices=('-Y','+Y'),default='-Y',
                        help='Reviewed anatomical anterior after GLB BASIS; legacy -Y is an orbit assumption and requires visual verification')
    parser.add_argument('--resolution', type=int, default=512)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    source = args.source.resolve()
    pin = sha(source)
    generation = json.loads(args.generation.read_text(encoding='utf-8'))
    if generation.get('state') != 'success' or sum(
        Path(row['localPath']).resolve() == source and row['sha256'] == pin
        for row in generation.get('outputs', [])
    ) != 1:
        raise RuntimeError('A successful collected generation output is required')
    if not 128 <= args.resolution <= 2048:
        raise RuntimeError('Review resolution outside supported range')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if not meshes:
        raise RuntimeError('No generated mesh')
    points = [obj.matrix_world @ vertex.co for obj in meshes for vertex in obj.data.vertices]
    low = Vector([min(p[i] for p in points) for i in range(3)])
    high = Vector([max(p[i] for p in points) for i in range(3)])
    centre = (low + high) / 2
    span = max(high - low)
    if span <= 0:
        raise RuntimeError('Invalid source bounds')
    if args.material_mode == 'clay':
        material = bpy.data.materials.new('offline_geometry_clay')
        material.use_nodes = True
        material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.48, .45, .39, 1)
        material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = .8
        for obj in meshes:
            obj.data.materials.clear()
            obj.data.materials.append(material)
    if args.material_mode == 'base-color':
        # Diagnostic scene shader only: use exact imported base-color input with
        # emission to separate painted shadows from lighting/normal-map relief.
        materials={material for obj in meshes for material in obj.data.materials if material is not None}
        for material in materials:
            material.use_nodes=True;tree=material.node_tree
            bsdf=next((node for node in tree.nodes if node.type=='BSDF_PRINCIPLED'),None)
            output_node=next((node for node in tree.nodes if node.type=='OUTPUT_MATERIAL'),None)
            if bsdf is None or output_node is None:raise RuntimeError('Imported source base-color shader required')
            color=bsdf.inputs['Base Color'];emission=tree.nodes.new('ShaderNodeEmission');emission.inputs['Strength'].default_value=1
            if color.is_linked:tree.links.new(color.links[0].from_socket,emission.inputs['Color'])
            else:emission.inputs['Color'].default_value=color.default_value
            for link in list(output_node.inputs['Surface'].links):tree.links.remove(link)
            tree.links.new(emission.outputs[0],output_node.inputs['Surface'])
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = True
    scene.view_settings.view_transform = 'Standard'
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .4
    for location, energy, size in (((-2, -3, 3), 140, 3), ((2, 2, 2), 100, 3), ((0, 1, -2), 45, 2)):
        bpy.ops.object.light_add(type='AREA', location=centre + Vector(location) * span)
        light = bpy.context.object
        light.data.energy = energy * span * span
        light.data.shape = 'DISK'
        light.data.size = size * span
        light.rotation_euler = (centre - light.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = span * 1.12
    scene.camera = camera
    # glTF importer maps X/Y/Z to NWN X/Z/-Y. Columns are camera right/up/outward.
    cameras = {
        'front': ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
        'left': ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
        'back': ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
        'right': ((0, -1, 0), (0, 0, 1), (-1, 0, 0)),
        'top': ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
        'bottom': ((1, 0, 0), (0, -1, 0), (0, 0, -1)),
    }
    if args.anterior_axis == '+Y':
        # A proper half-turn maps the legacy orbit to reviewed +Y anatomy.
        # Geometry stays in its original source coordinate system.
        for name in ('front','left','back','right'):
            cameras[name]=tuple(tuple(-value if index < 2 else value for index,value in enumerate(axis)) for axis in cameras[name])
    frames = {}
    for name, basis in cameras.items():
        matrix = Matrix(basis).transposed().to_4x4()
        matrix.translation = centre + Vector(basis[2]) * span * 3
        camera.matrix_world = matrix
        scene.render.filepath = str(output / (name + '.png'))
        bpy.ops.render.render(write_still=True)
        frames[name] = {'rightUpOutward': basis, 'matrixWorld': [list(row) for row in matrix],
                        'orthoScale': camera.data.ortho_scale, 'sha256': sha(output / (name + '.png'))}
    if sha(source) != pin:
        raise RuntimeError('Source changed during preview')
    shutil.copyfile(__file__, output / 'executed-helper.py')
    receipt = {'schemaVersion': 1, 'kind': 'generated-part-offline-preview',
        'source': str(source), 'sourceSha256': pin, 'generation': str(args.generation.resolve()),
        'generationSha256': sha(args.generation), 'promptId': generation['promptId'],
        'blenderVersion': bpy.app.version_string, 'engine': 'Cycles CPU', 'samples': 16,
        'materialMode': args.material_mode,'reviewedAnteriorAxis':args.anterior_axis,'sourceMapsEdited':False, 'boundsNwn': [list(low), list(high)],
        'geometryRescaled': False, 'sourceUnchanged': True, 'views': frames,
        'cameraPolicy': 'Explicit reviewed anterior '+args.anterior_axis+' after GLB BASIS. Side cameras follow that anatomical choice; top +Z with X right/Y up. Geometry remains unchanged; orientation is independently reviewed before fitting.',
        'helperSha256': sha(output / 'executed-helper.py'), 'clientEvidence': False,
        'limitation': 'Offline glTF/Blender rendering; original maps interpreted by Blender, not the installed NWN shader.'}
    (output / 'preview.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'preview': str(output / 'preview.json'), 'clientEvidence': False}))


if __name__ == '__main__':
    main()
