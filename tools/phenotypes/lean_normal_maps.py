"""LEAN step 4: bake tangent-space normal maps for the LEAN geometry in the compiler's own tangent basis.

Because the reduction keeps each node's UV layout, every atlas texel maps to a parent surface point and a LEAN surface
point at the same UV. Target object-space normal at a texel = parent native TBN (compiled N, T, handedness, exactly as
the shader reconstructs it) applied to the parent's detail normal-map texel, i.e. parent geometry + existing detail.
It is encoded in the LEAN basis decoded from the compiled LEAN binaries (positions, normals, UVs, tangents and signs of
the native compile of the basis composition): compilemodel splits vertices whose faces have mixed UV handedness, so
only the decoded compiled basis matches what the client shades with. Texels outside LEAN coverage keep the parent map,
with a short dilation of new values over gutters (z clamped to >= 0.02). Nodes sharing one map are merged by coverage
(first node in name order owns overlaps; gutter conflicts keep the first writer). Geometry, UVs, PLTs and roughness
are untouched.

Usage: lean_normal_maps.py --parent <manifest> --basis <compiled basis dir (basis.json + native-compile.json)> --output <fresh dir>
"""
import argparse
import json
from pathlib import Path
import time

import numpy as np

import lean_common as L
from audit_target_native_part import decode
from nwn_ascii_trimesh import AsciiModel
from uv_atlas_raster import raster, uv_to_pixels


def target_field(parent_arrays, normal_map):
    """Parent object-space normals (native TBN x detail texel) per covered texel, dilated 6 texels."""
    P = parent_arrays['position'].astype(float); N = parent_arrays['normal'].astype(float); U = parent_arrays['uv'].astype(float)
    T = parent_arrays['tangent'].astype(float); S = parent_arrays['sign'].astype(float).ravel(); F = parent_arrays['faces'].astype(np.int64)
    H, W = normal_map.shape[:2]
    face_ids, bary = raster(uv_to_pixels(U, W, H), F, W, H); covered = face_ids >= 0
    index = np.nonzero(covered.ravel())[0]; f = face_ids.ravel()[index]; b = bary.reshape(-1, 3)[index].astype(float)
    n_, t_, b_ = L.tbn(L.interp(N, F, f, b), L.interp(T, F, f, b), L.interp(S[:, None], F, f, b)[:, 0])
    encoded = normal_map.reshape(-1, 3)[index].astype(float)/255*2-1; x, y = encoded[:, 0], encoded[:, 1]
    z = np.sqrt(np.maximum(1-x*x-y*y, 0))
    world = x[:, None]*t_+y[:, None]*b_+z[:, None]*n_; world /= np.linalg.norm(world, axis=1)[:, None]
    field = np.zeros((H, W, 3)); field.reshape(-1, 3)[index] = world
    return L.dilate_values(field, covered, 6)


def encode(field, filled, lean, normal_map):
    """Encode the target field in the decoded compiled LEAN basis; returns (image, LEAN coverage, stats)."""
    H, W = normal_map.shape[:2]
    P = lean['position'].astype(float); N = lean['normal'].astype(float); U = lean['uv'].astype(float); F = lean['faces'].astype(np.int64)
    T = lean['tangent'].astype(float); S = lean['sign'].astype(float).ravel()
    face_ids, bary = raster(uv_to_pixels(U, W, H), F, W, H); covered = face_ids >= 0
    index = np.nonzero(covered.ravel())[0]; f = face_ids.ravel()[index]; b = bary.reshape(-1, 3)[index].astype(float)
    n_, t_, b_ = L.tbn(L.interp(N, F, f, b), L.interp(T, F, f, b), L.interp(S[:, None], F, f, b)[:, 0])
    target = field.reshape(-1, 3)[index]; have = filled.ravel()[index]
    basis = np.stack([t_, b_, n_], 2); xyz = np.linalg.solve(basis, target[:, :, None])[:, :, 0]
    xyz[:, 2] = np.maximum(xyz[:, 2], 0.02); xyz /= np.linalg.norm(xyz, axis=1)[:, None]; xyz[~have] = [0, 0, 1]
    result = normal_map.astype(float).copy().reshape(-1, 3)/255*2-1
    buffer = np.zeros((H, W, 3)); buffer.reshape(-1, 3)[index] = xyz
    buffer, new = L.dilate_values(buffer, covered, 4)
    selected = new.ravel(); result[selected] = buffer.reshape(-1, 3)[selected]
    image = np.clip(np.round((result*0.5+0.5)*255), 0, 255).astype(np.uint8).reshape(H, W, 3)
    angle = np.degrees(np.arccos(np.clip((n_*target).sum(1), -1, 1)))
    stats = {'texelsLean': int(covered.sum()), 'leanTexelsWithoutParentTarget': int((~have).sum()),
             'normalCorrectionDegMean': float(angle[have].mean()) if have.any() else 0.0,
             'normalCorrectionDegP95': float(np.percentile(angle[have], 95)) if have.any() else 0.0}
    return image, covered, stats


def merge(base, encoded):
    """Shared map: each node owns its LEAN-covered texels (first in name order wins), then first-writer gutters."""
    image = base.copy(); owned = np.zeros(base.shape[:2], bool); changed = np.zeros(base.shape[:2], bool)
    for name in sorted(encoded):
        new, covered = encoded[name]; own = covered & ~owned; image[own] = new[own]; owned |= own
    for name in sorted(encoded):
        new, _ = encoded[name]; extra = (new != base).any(2) & ~owned & ~changed; image[extra] = new[extra]; changed |= extra
    return image


def bake(parent_path, basis_dir, output):
    frozen = L.Frozen(); manifest = L.read_json(frozen.take(parent_path)); basis_dir = Path(basis_dir).resolve()
    basis = L.read_json(frozen.take(basis_dir/'basis.json'))
    L.require(basis['parent']['sha256'] == L.sha(parent_path), 'Basis descends from a different parent')
    native = L.read_json(frozen.take(basis_dir/'native-compile.json'))
    L.require(native.get('complete') is True and native.get('executionMode') == 'compilemodel', 'Complete basis compile required')
    rows = {row['name']: row for row in native['models']}
    output = L.fresh(output); (output/'resources').mkdir()
    maps = {}; nodes = {}; T0 = time.monotonic()
    for part in L.PARTS:
        prow = manifest['parts'][part]; model = prow['model']
        ascii_path = frozen.take(basis_dir/'ascii'/(model+'.mdl')); binary = frozen.take(basis_dir/'resources'/(model+'.mdl'))
        L.require(rows[model+'.mdl']['sourceSha256'] == L.sha(ascii_path) == basis['parts'][part]['ascii']['sha256'] and
                  rows[model+'.mdl']['binarySha256'] == L.sha(binary), 'Basis binary was not compiled from the basis ASCII: '+model)
        names = [node.name for node in AsciiModel.read(ascii_path).trimeshes()]
        meshes, _ = decode(binary.read_bytes(), model, names)
        for mesh in prow['meshes']:
            t0 = time.monotonic(); normal_path = frozen.pinned(mesh['normal'])
            meta, normal_map = L.tga_read(normal_path)
            field, filled = target_field(np.load(frozen.pinned(mesh['arrays'])), normal_map)
            image, covered, stats = encode(field, filled, meshes[mesh['mesh']], normal_map)
            maps.setdefault(normal_path.name.lower(), {'meta': meta, 'base': normal_map, 'source': mesh['normal'], 'encoded': {}})
            maps[normal_path.name.lower()]['encoded'][mesh['mesh']] = (image, covered)
            nodes[mesh['mesh']] = {'model': model, 'normalMap': normal_path.name.lower(), 'compiledVertices': int(len(meshes[mesh['mesh']]['position'])),
                                   **stats, 'seconds': round(time.monotonic()-t0, 1)}
            print(json.dumps({'mesh': mesh['mesh'], **stats}), flush=True)
    written = {}
    for name, row in sorted(maps.items()):
        image = merge(row['base'], row['encoded']); destination = output/'resources'/name
        L.tga_write(destination, row['meta'], image); L.require(np.array_equal(L.tga_read(destination)[1], image), 'TGA round trip differs: '+name)
        written[name] = {'nodes': sorted(row['encoded']), 'parentMap': row['source'], 'changedTexels': int((image != row['base']).any(2).sum()),
                         'sha256': L.sha(destination)}
    receipt = {'schemaVersion': 1, 'kind': 'lean-normal-maps', 'sex': manifest['sex'], 'parent': L.pin(parent_path),
               'basis': L.pin(basis_dir/'basis.json'), 'compiledBasis': L.pin(basis_dir/'native-compile.json'),
               'encoding': 'parent native TBN x detail texel, encoded in the decoded compiled LEAN basis',
               'maps': written, 'nodes': nodes, 'seconds': round(time.monotonic()-T0, 1),
               'frozenInputs': {**frozen.verify(), **L.helper_pins('lean_normal_maps.py', 'uv_atlas_raster.py', 'audit_target_native_part.py', 'nwn_ascii_trimesh.py')},
               'geometryEdited': False, 'uvEdited': False, 'selected': False, 'clientAccepted': False, 'productionAccepted': False}
    return L.save_json(output/'normal-maps.json', receipt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True); parser.add_argument('--basis', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); print(bake(args.parent, args.basis, args.output))
