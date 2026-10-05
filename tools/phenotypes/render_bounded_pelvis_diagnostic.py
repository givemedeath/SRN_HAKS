"""Literal CPU clay closeups of the separately declared bounded pelvis trial.

Offline geometric clay and explicit annotations; no NWN/client material claim.
The original-before and diagnostic-after meshes are decoded from pinned GLBs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

import numpy as np
import bpy
from mathutils import Vector

from place_purposebuilt_pelvis import BASIS, read_glb
from write_bounded_pelvis_diagnostic import decoded_primitives


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp(path):
    return {'path': str(Path(path).resolve()), 'sha256': sha(path)}


def material(name, color, emission=False, roughness=.72):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    node = mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value = (*color, 1.)
    node.inputs['Roughness'].default_value = roughness
    if emission:
        node.inputs['Emission Color'].default_value = (*color, 1.)
        node.inputs['Emission Strength'].default_value = 1.
    return mat


def orient(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z', 'Y').to_euler()


def curve(name, points, color, radius):
    data = bpy.data.curves.new(name, 'CURVE'); data.dimensions = '3D'
    data.bevel_depth = radius; data.bevel_resolution = 2
    spline = data.splines.new('POLY'); spline.points.add(len(points)-1)
    for row, p in zip(spline.points, points): row.co = (*p, 1.)
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new(name, data); bpy.context.collection.objects.link(obj)
    data.materials.append(material(name, color, True))


def legend(camera, scene, body):
    bpy.context.view_layer.update(); corners = camera.data.view_frame(scene=scene)
    xmin, xmax, ymin = min(v.x for v in corners), max(v.x for v in corners), min(v.y for v in corners)
    data = bpy.data.curves.new('annotation-legend', 'FONT'); data.body = body
    data.size = (xmax-xmin)*.017; data.space_line = 1.05
    obj = bpy.data.objects.new('annotation-legend', data); bpy.context.collection.objects.link(obj)
    obj.matrix_world = camera.matrix_world.copy()
    obj.location = camera.matrix_world @ Vector((xmin*.95, ymin+(len(body.splitlines())+1)*data.size*1.15, -camera.data.clip_start*3))
    data.materials.append(material('legend-white', (.92, .96, 1.), True))
    ymax = min(max(v.y for v in corners), ymin+(len(body.splitlines())+1)*data.size*1.3)
    mesh = bpy.data.meshes.new('legend-panel'); mesh.from_pydata([(xmin*.99, ymin*.99, 0.), (xmax*.99, ymin*.99, 0.),
        (xmax*.99, ymax, 0.), (xmin*.99, ymax, 0.)], [], [(0, 1, 2, 3)])
    panel = bpy.data.objects.new('legend-panel', mesh); bpy.context.collection.objects.link(panel)
    panel.matrix_world = camera.matrix_world.copy(); panel.location = camera.matrix_world @ Vector((0., 0., -camera.data.clip_start*4))
    mesh.materials.append(material('legend-dark', (.015, .02, .03), True))


def world(points, matrix):
    return (np.column_stack((np.asarray(points) @ BASIS.T, np.ones(len(points)))) @ np.asarray(matrix).T)[:, :3]


def setup(rows, fit, kept, label, foundation):
    bpy.ops.wm.read_factory_settings(use_empty=True); scene = bpy.context.scene
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 16
    scene.cycles.use_denoising = False; scene.render.threads_mode = 'FIXED'; scene.render.threads = 4
    scene.render.resolution_x = 1600; scene.render.resolution_y = 1400; scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'; scene.render.image_settings.color_mode = 'RGBA'; scene.render.image_settings.color_depth = '16'
    scene.view_settings.view_transform = 'Standard'; scene.view_settings.look = 'Medium High Contrast'
    scene.world = bpy.data.worlds.new('neutral-offline-world'); scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.065, .075, .09, 1.)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .2
    meshes = []; bounds = []; proofs = []
    for index, row in enumerate(rows):
        p = world(row['attributes']['POSITION'], fit['attachmentWorld']); f = row['faces']
        mesh = bpy.data.meshes.new('literal-'+label+'-primitive-'+str(index)); mesh.from_pydata(p.tolist(), [], f.tolist()); mesh.update()
        obj = bpy.data.objects.new(mesh.name, mesh); bpy.context.collection.objects.link(obj); meshes.append(obj)
        mesh.materials.append(material('protected-original-clay', (.45, .49, .53)))
        mesh.materials.append(material('original-foundation-before', (.72, .10, .055)))
        mesh.materials.append(material('reviewed-face35709-before', (1., .75, .015)))
        mesh.materials.append(material('neutral-diagnostic-cap', (.36, .36, .36), roughness=1.))
        for i, poly in enumerate(mesh.polygons):
            poly.use_smooth = False
            if index: poly.material_index = 3
            elif label == 'before': poly.material_index = 2 if i == 35709 else (1 if i in foundation else 0)
        actual = np.array([v.co[:] for v in mesh.vertices]); actualf = np.array([poly.vertices[:] for poly in mesh.polygons])
        if not np.array_equal(actualf, f) or not np.array_equal(actual.astype(np.float32), p.astype(np.float32)):
            raise AssertionError('Literal decoded working display bridge')
        proofs.append({'primitive': index, 'faces': len(f), 'decodedGeometryDisplayedExactlyAtFloat32': True,
                       'displayMaterial': 'Geometric-normal clay; cap uses declared neutral matte base factor'})
        bounds.append(p[f].reshape(-1, 3))
    # Freeze matched lighting against ORIGINAL fitted body points, not changed bound extents.
    original = world(rows[0]['attributes']['POSITION'], fit['attachmentWorld']); center = original.mean(0); scale = .54
    lights = []
    for name, offset, energy, size in [('key', (1., -1., 2.), 18., 1.2), ('fill', (-1., .6, 1.), 12., 1.), ('rim', (0., 1., -1.), 9., .8)]:
        data = bpy.data.lights.new(name, 'AREA'); data.energy = energy*scale**2; data.shape = 'DISK'; data.size = size*scale
        obj = bpy.data.objects.new(name, data); bpy.context.collection.objects.link(obj); obj.location = Vector(center+np.asarray(offset)*scale); orient(obj, center)
        lights.append(obj)
    data = bpy.data.cameras.new('literal-orthographic'); data.type = 'ORTHO'; data.clip_start = .00054; data.clip_end = 54.
    camera = bpy.data.objects.new('literal-orthographic', data); bpy.context.collection.objects.link(camera); scene.camera = camera
    return scene, camera, proofs, np.concatenate(bounds)


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--diagnostic', type=Path, required=True)
    parser.add_argument('--previous-literal', type=Path, required=True); parser.add_argument('--sections', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    begun = time.monotonic(); output = args.output.resolve()
    if output.exists(): raise ValueError('Fresh output required')
    diagnostic = json.loads(args.diagnostic.read_text()); fitpath = Path(diagnostic['properFit']['path']); fit = json.loads(fitpath.read_text())
    working = Path(diagnostic['exports']['working']['candidate']['path'])
    pins = {str(args.diagnostic.resolve()): sha(args.diagnostic), str(fitpath): diagnostic['properFit']['sha256'],
        str(working): diagnostic['exports']['working']['candidate']['sha256'], str(Path(fit['candidate'])): fit['candidateSha256'],
        str(args.previous_literal.resolve()): sha(args.previous_literal), str(args.sections.resolve()): sha(args.sections),
        diagnostic['faceMapping']['path']: diagnostic['faceMapping']['sha256']}
    for path, pin in pins.items():
        if sha(path) != pin: raise ValueError('Pinned input changed')
    if diagnostic['kind'] != 'bounded-troll-pelvis-port-diagnostic' or not diagnostic['geometryDiagnosticGuardsPassed'] or diagnostic['selectionMade']:
        raise ValueError('Unselected, verified bounded diagnostic required')
    mapping = np.load(diagnostic['faceMapping']['path']); kept = mapping['keptOriginalFaceIds']; deleted = mapping['deletedOriginalFaceIds']
    original_rows = decoded_primitives(*read_glb(fit['candidate'])); repaired_rows = decoded_primitives(*read_glb(working))
    previous = json.loads(args.previous_literal.read_text()); previous_views = {r['view']: r for r in previous['captures'] if r['space'] == 'working-fit054'}
    sections = json.loads(args.sections.read_text())['protectedOutermostLegLoops']
    output.mkdir(parents=True); captures = []
    body = world(original_rows[0]['attributes']['POSITION'], fit['attachmentWorld'])
    body_referenced = body[original_rows[0]['faces']].reshape(-1, 3); center = (body_referenced.min(0)+body_referenced.max(0))/2
    matrix = np.asarray(fit['attachmentWorld']) @ np.asarray(fit['sourceToAttachmentLocal'])
    for label, view in [('before', 'underside'), ('after', 'underside'), ('after', 'front'), ('after', 'left'), ('after', 'right-port-detail')]:
        rows = original_rows if label == 'before' else repaired_rows
        scene, camera, proofs, displayed = setup(rows, fit, kept, label, set(map(int, deleted))-{35709})
        projected = view == 'underside'
        if view == 'underside':
            previous_view = previous_views['foundation-underside']; focus = np.asarray(previous_view['cameraFocus'])
            direction = np.asarray(previous_view['cameraDirectionTowardCamera']); scale = previous_view['cameraOrthoScale']
        elif view == 'right-port-detail':
            previous_view = previous_views['face35709-first-hit']; focus = np.asarray(previous_view['cameraFocus'])
            direction = np.asarray(previous_view['cameraDirectionTowardCamera']); scale = previous_view['cameraOrthoScale']
        else:
            focus = center; direction = np.asarray([0., 1., 0.] if view == 'front' else [-1., 0., 0.]); scale = .73
        for side in ('left', 'right'):
            ring = world(original_rows[0]['attributes']['POSITION'][mapping[side+'CapOriginalPortRows']], fit['attachmentWorld'])
            curve('exact-fixed-port-'+side, ring, (.05, .8, 1.), .000378)
        for i, row in enumerate(sections):
            src = np.asarray(row['points']) @ BASIS.T
            points = (np.column_stack((src, np.ones(len(src)))) @ matrix.T)[:, :3]
            if projected: points[:, 2] = displayed[:, 2].min()-.0015
            curve('protected-thigh-footprint-'+str(i), points, (.15, 1., .25), .00054)
        camera.location = Vector(focus+direction*1.35); camera.data.ortho_scale = scale; orient(camera, focus)
        caption = ('BEFORE | Original proper 0.54 fit | All 49452 original faces\nRed: reviewed foundation. Gold: 35709. Original anatomy unchanged.' if label == 'before' else
            'AFTER | Bounded unaccepted working diagnostic | 44854 retained + 1444 caps\nOnly reviewed foundation/35709 removed; body attributes/maps remain exact.')
        caption += '\nCyan: exact fixed 68-vertex ports. Green: protected thigh contours.'
        caption += '\nNeutral matte caps: 0.54 mm below original minimum; provisional shading.' if label == 'after' else ''
        caption += '\nGreen underside contours are projected annotations only.' if projected else ''
        caption += '\nCycles CPU clay; no material, anatomy, closed-exterior or client acceptance.'
        legend(camera, scene, caption); bpy.context.view_layer.update(); path = output/(label+'-'+view+'.png')
        scene.render.filepath = str(path); print(json.dumps({'phase': 'literal-bounded-diagnostic-render', 'view': label+'-'+view}), flush=True)
        bpy.ops.render.render(write_still=True)
        blend = output/(label+'-'+view+'.blend'); bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        captures.append({'view': label+'-'+view, 'image': stamp(path), 'blend': stamp(blend), 'geometryProofs': proofs,
            'cameraMatrixWorld': [list(r) for r in camera.matrix_world], 'cameraOrthoScale': camera.data.ortho_scale,
            'cameraFocus': focus.tolist(), 'cameraDirectionTowardCamera': direction.tolist(), 'protectedContoursProjectedForAnnotation': projected,
            'lights': [{'name': o.name, 'matrixWorld': [list(r) for r in o.matrix_world], 'energy': o.data.energy, 'size': o.data.size} for o in scene.objects if o.type == 'LIGHT']})
    for path, pin in pins.items():
        if sha(path) != pin: raise AssertionError('Protected input changed')
    (output/'helper-snapshots').mkdir()
    for name in ('render_bounded_pelvis_diagnostic.py', 'write_bounded_pelvis_diagnostic.py', 'bounded_pelvis_connector_v2.py', 'place_purposebuilt_pelvis.py'):
        shutil.copyfile(Path(__file__).with_name(name), output/'helper-snapshots'/name)
    receipt = {'schemaVersion': 1, 'kind': 'literal-bounded-pelvis-diagnostic-closeups', 'diagnostic': stamp(args.diagnostic),
        'frozenInputs': pins, 'captures': captures, 'renderEngine': 'Cycles CPU', 'samples': 16, 'threads': 4,
        'elapsedSeconds': time.monotonic()-begun, 'literalDecodedWorkingGeometry': True,
        'matchedBeforeAfterUndersideCameraLighting': True, 'displayMaterial': 'Geometric-normal clay with declared neutral matte cap factor; source maps unchanged',
        'allBodyOriginalInputsUnchanged': True, 'selectionMade': False, 'materialAccepted': False, 'anatomyAccepted': False,
        'closedExteriorClaim': False, 'clientAccepted': False}
    path = output/'literal-closeups.json'; path.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'receipt': stamp(path), 'captures': len(captures)}), flush=True)


if __name__ == '__main__': main()
