"""Synthetic Blender integration smoke; never creates or approves a Cougar asset."""
import argparse
from pathlib import Path
import sys
import bpy
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.headkit.common import pin, read, write, require
from tools.headkit.gltf import write_mesh
from tools.itemkit import blender_worker as worker


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fit-only', action='store_true', help='Run affine and native fit regressions without baking')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:]); root = args.output.resolve(); root.mkdir(parents=True, exist_ok=False)
    # A closed cuboid in NWN/Blender basis, mapped back to glTF Y-up for import.
    vertices = np.array([[-.02, -.2, -.01], [.02, -.2, -.01], [.02, .8, -.01], [-.02, .8, -.01],
                         [-.02, -.2, .01], [.02, -.2, .01], [.02, .8, .01], [-.02, .8, .01]])
    faces = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                      [3, 7, 6], [3, 6, 2], [0, 4, 7], [0, 7, 3], [1, 2, 6], [1, 6, 5]])
    gltf = vertices[:, [0, 2, 1]].copy(); gltf[:, 2] *= -1
    source = root/'synthetic.glb'; write_mesh(source, gltf, faces)
    # Cutting triangulated side walls inserts collinear rim corners. Both sides
    # must retain the same contour and close without degenerate cap triangles.
    worker.reset(); cut_source = worker.import_source(source, 'cap-regression')
    cuts = []
    for keep_above in (False, True):
        obj = worker.duplicate(cut_source, 'cap-half-'+str(keep_above))
        worker.cut(obj, .13783, keep_above)
        vertices_cut, faces_cut = worker.arrays(obj)
        require(worker.topology(vertices_cut, faces_cut)['closedWound'], 'Cut cap is not closed and outward')
        rim = vertices_cut[np.abs(vertices_cut[:,1]-.13783)<1e-7]
        cuts.append(np.unique(rim, axis=0))
    require(np.array_equal(cuts[0], cuts[1]), 'Mating cap contours differ')
    # Native-axis width/depth calibration following a general rotation contains
    # shear in source axes. Object-transform assignment silently decomposes it.
    worker.reset(); affine = worker.import_source(source, 'affine-regression')
    affine.data.uv_layers.new(name='retained-uv')
    for i, row in enumerate(affine.data.uv_layers.active.data): row.uv = (i/100., i/200.)
    theta = .31; rotation = np.array([[np.cos(theta), -np.sin(theta), 0],
                                    [np.sin(theta), np.cos(theta), 0], [0, 0, 1]])
    matrix = np.eye(4); matrix[:3, :3] = np.diag([.45, 1., .64]) @ rotation
    matrix[:3, 3] = [.03, -.02, .01]
    before, triangles = worker.arrays(affine)
    expected = worker.transform(before, matrix)
    affine_result = worker.apply_fit(affine, matrix)
    require(np.allclose(worker.arrays(affine)[0], expected, atol=1e-7, rtol=0),
            'Rotated transverse calibration must preserve the exact affine map')
    require(worker.topology(*worker.arrays(affine))['closedWound'], 'Affine fit reversed the shell')
    cfg = {'source': str(source), 'family': read(Path(__file__).parent/'profiles/cougar-shortsword.json'),
           'fit': {'reviewed': True, 'sourceSha256': pin(source)['sha256'], 'matrix': np.eye(4).tolist(),
                   'gripEndpoints': [[0, -.06, 0], [0, .06, 0]]},
           'processing': {'joinY': [-.06, .06], 'openingProbes': [], 'thicknessProbes': [], 'uvMargin': .016,
                          'cageExtrusion': .001, 'maxRayDistance': .003, 'capColour': [.08, .08, .08]}}
    cfg['family']['native'] = {'gripOrigin': [0, 0, 0], 'gripLength': .12}
    results = {'affineCalibration': affine_result}
    for stage, action in [('fit', worker.fit), ('reduce', worker.reduce), ('unwrap', worker.unwrap), ('bake', worker.bake),
                          ('shadow', lambda c, o: worker.reduce(c, o, shadow=True)), ('export-arrays', worker.export_arrays)]:
        output = root/stage; output.mkdir()
        try:
            results[stage] = action(cfg, output)
        except Exception:
            for obj in bpy.data.objects:
                if obj.type == 'MESH':
                    v, f = worker.arrays(obj)
                    write(output/(obj.name+'.json'), {'vertices': v.tolist(), 'faces': f.tolist()}, fresh=True)
            raise
        if (output/'scene.blend').exists(): cfg['scene'] = str(output/'scene.blend')
        if stage == 'fit':
            if args.fit_only: break
            donor = bpy.data.objects['donor']; donor.data.materials.clear()
            donor.data.materials.append(worker.flat_material('synthetic-donor', (.1, .2, .3)))
            bpy.ops.wm.save_as_mainfile(filepath=cfg['scene'])
    write(root/'smoke.json', {'syntheticOnly': True, 'blender': list(bpy.app.version), 'stages': results,
                            'generatedCougar': False, 'clientValidated': False, 'fitOnly': args.fit_only}, fresh=True)


if __name__ == '__main__': main()
