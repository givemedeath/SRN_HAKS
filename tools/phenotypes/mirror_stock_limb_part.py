"""Bake a detached GLB similarity/reflection; never mirror a stock rig.

NWN coordinates are +Y anterior/+Z up. A mirror is explicitly conjugated
between measured attachment frames. Maps and UV accessors are retained, while
new position/normal/tangent/index accessors produce identity-node geometry.
This is a geometry diagnostic, not a native/client acceptance gate.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil

import numpy as np

from place_purposebuilt_pelvis import (BASIS, accessor, embedded_maps,
    node_matrix, raw_corners, read_glb, require, sha, write_glb)
from retarget import nodes, transforms


def similarity(matrix, allow_reflection=False):
    matrix = np.asarray(matrix, dtype=float)
    require(matrix.shape == (4, 4) and np.isfinite(matrix).all(), 'Finite affine 4x4 required')
    require(np.allclose(matrix[3], [0, 0, 0, 1], atol=1e-12, rtol=0), 'Projective transform rejected')
    linear = matrix[:3, :3]
    scale = float(abs(np.linalg.det(linear)) ** (1/3))
    require(scale > 1e-12, 'Singular transform rejected')
    rotation = linear / scale
    require(np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-10, rtol=0), 'Nonuniform stretch rejected')
    reflected = np.linalg.det(rotation) < 0
    require(allow_reflection or not reflected, 'Reflection requires explicit authorization')
    return scale, rotation, reflected


def reflection_between_frames(source_world, target_world, origin_world, normal_world):
    """Geometry-only source-local to target-local reflection, no joint edits."""
    source_world = np.asarray(source_world, dtype=float)
    target_world = np.asarray(target_world, dtype=float)
    for frame in [source_world, target_world]:
        scale, _, reflected = similarity(frame)
        require(abs(scale-1) < 1e-10 and not reflected, 'Stock attachment must be rigid/proper')
    normal = np.asarray(normal_world, dtype=float)
    origin = np.asarray(origin_world, dtype=float)
    require(normal.shape == origin.shape == (3,) and np.isfinite(normal).all() and np.isfinite(origin).all(), 'Explicit finite reflection plane required')
    require(np.linalg.norm(normal) > 1e-12, 'Zero plane normal')
    normal = normal / np.linalg.norm(normal)
    reflection = np.eye(4)
    reflection[:3, :3] -= 2*np.outer(normal, normal)
    reflection[:3, 3] = 2*normal*np.dot(normal, origin)
    result = np.linalg.inv(target_world) @ reflection @ source_world
    scale, _, reflected = similarity(result, allow_reflection=True)
    require(reflected and abs(scale-1) < 1e-10, 'Measured frame mirror must be an orthogonal reflection')
    return result, reflection


def detached_affine_bake(doc, binary, affine_nwn, allow_reflection=False):
    """Return new doc/BIN, authoritative ordered corner arrays and proof.

Only one active detached mesh instance is supported, with any number of
primitives. Original doc/BIN remain unmodified. Source proper uniform hierarchy
is baked; normal/tangent directions use rotations only, preserving lengths.
"""
    scale, rotation, reflected = similarity(affine_nwn, allow_reflection)
    affine_nwn = np.asarray(affine_nwn, dtype=float)
    require(not doc.get('animations') and not doc.get('skins'), 'Skeletons/controllers/animations excluded')
    require(not doc.get('extensionsUsed') and not doc.get('extensionsRequired'), 'Extension policy is not defined')
    require(len(doc.get('buffers', [])) == 1 and not doc['buffers'][0].get('uri'), 'Embedded single BIN required')
    require(len(binary) % 4 == 0, 'Padded original BIN required')
    require(len(doc.get('scenes', [])) == 1, 'One scene required')
    for node in doc.get('nodes', []):
        require(not any(k in node for k in ['skin', 'camera', 'weights', 'extensions']), 'Rig/camera/morph node excluded')
        similarity(node_matrix(node))
    active = []; seen = set()
    def visit(index, parent):
        require(index not in seen, 'Cycle or duplicate node instance')
        seen.add(index)
        node = doc['nodes'][index]; world = parent @ node_matrix(node)
        similarity(world)
        if 'mesh' in node: active.append((node['mesh'], world))
        for child in node.get('children', []): visit(child, world)
    for index in doc['scenes'][doc.get('scene', 0)]['nodes']: visit(index, np.eye(4))
    require(len(active) == 1, 'Exactly one active detached mesh instance required')
    source_p, source_n, source_uv, _ = raw_corners(doc, binary, allow_wrapper=True)
    source_mesh, world = active[0]
    _, source_rotation, _ = similarity(world)
    result = copy.deepcopy(doc); output = bytearray(binary)
    primitives = []; archived = {k: [] for k in ['positions', 'normals', 'uvNative', 'uvGltf', 'sourcePositions', 'sourceNormals', 'sourceUVNative', 'primitiveIds']}
    tangent_rows = []; tangent_triangles = []; records = []; triangle_offset = 0
    order = np.asarray([0, 2, 1] if reflected else [0, 1, 2])

    def append(rows, component_type=5126, kind=None):
        rows = np.asarray(rows, dtype='<f4' if component_type == 5126 else '<u4')
        require(np.isfinite(rows).all(), 'Serialization overflow/nonfinite attributes')
        width = rows.shape[1] if rows.ndim == 2 else 1
        kind = kind or {1:'SCALAR', 2:'VEC2', 3:'VEC3', 4:'VEC4'}[width]
        output.extend(b'\0' * (-len(output) % 4)); offset = len(output)
        output.extend(rows.tobytes()); output.extend(b'\0' * (-len(output) % 4))
        result['bufferViews'].append({'buffer':0, 'byteOffset':offset, 'byteLength':rows.nbytes})
        result['accessors'].append({'bufferView':len(result['bufferViews'])-1, 'componentType':component_type,
            'count':len(rows), 'type':kind})
        return len(result['accessors'])-1

    for primitive_id, primitive in enumerate(doc['meshes'][source_mesh]['primitives']):
        require(primitive.get('mode', 4) == 4 and not primitive.get('targets') and not primitive.get('extensions'), 'Static indexed triangles required')
        attributes = primitive['attributes']
        require(set(attributes) <= {'POSITION', 'NORMAL', 'TEXCOORD_0', 'TANGENT', 'COLOR_0'}, 'Joint/unknown attributes excluded')
        require(set(['POSITION', 'NORMAL', 'TEXCOORD_0']) <= set(attributes), 'Authored P/N/UV required')
        for key in ['POSITION', 'NORMAL', 'TEXCOORD_0', 'TANGENT']:
            if key in attributes: require(doc['accessors'][attributes[key]]['componentType'] == 5126, 'Float geometry attributes required')
        p = accessor(doc, binary, attributes['POSITION']).astype(float)
        n = accessor(doc, binary, attributes['NORMAL']).astype(float)
        uv = accessor(doc, binary, attributes['TEXCOORD_0']).astype(float)
        index_accessor = doc['accessors'][primitive['indices']]
        require(index_accessor['componentType'] in [5121,5123,5125] and index_accessor['type'] == 'SCALAR', 'Unsigned scalar indices required')
        ids = accessor(doc, binary, primitive['indices']).reshape(-1, 3).astype(int)
        require(len(ids) > 0 and ids.min() >= 0 and ids.max() < len(p), 'Invalid triangle indices')
        require(p.shape == n.shape and p.shape[1] == 3 and uv.shape == (len(p), 2), 'Attribute mismatch')
        require(np.isfinite(p).all() and np.isfinite(n).all() and np.isfinite(uv).all(), 'Nonfinite source')
        base_p = (np.c_[p,np.ones(len(p))] @ world.T)[:,:3] @ BASIS.T
        base_n = n @ source_rotation.T @ BASIS.T
        transformed_p = base_p @ affine_nwn[:3,:3].T + affine_nwn[:3,3]
        transformed_n = base_n @ rotation.T
        mirrored_ids = ids[:, order]
        new = copy.deepcopy(primitive)
        new['attributes']['POSITION'] = append(transformed_p @ BASIS)
        serialized_positions = np.asarray(transformed_p @ BASIS, dtype='<f4')
        result['accessors'][-1].update(min=serialized_positions.min(0).astype(float).tolist(),
            max=serialized_positions.max(0).astype(float).tolist())
        new['attributes']['NORMAL'] = append(transformed_n @ BASIS)
        if reflected: new['indices'] = append(mirrored_ids.reshape(-1), 5125)
        if 'TANGENT' in attributes:
            t = accessor(doc, binary, attributes['TANGENT']).astype(float)
            require(t.shape == (len(p), 4) and np.isfinite(t).all() and np.all(np.abs(t[:,3]) == 1), 'Finite tangent VEC4 with handedness +/-1 required')
            transformed_t = t.copy()
            transformed_t[:,:3] = t[:,:3] @ source_rotation.T @ BASIS.T @ rotation.T
            transformed_t[:,3] *= -1 if reflected else 1
            raw_t = transformed_t.copy(); raw_t[:,:3] = transformed_t[:,:3] @ BASIS
            new['attributes']['TANGENT'] = append(raw_t)
            tangent_rows.append(transformed_t[mirrored_ids]); tangent_triangles.extend(range(triangle_offset, triangle_offset+len(ids)))
        if 'COLOR_0' in attributes:
            color = accessor(doc,binary,attributes['COLOR_0'],allow_normalized=True)
            require(color.shape[0] == len(p) and color.shape[1] in [3,4] and np.isfinite(color).all(), 'Invalid COLOR_0')
        native_uv = uv.copy(); native_uv[:,1] = 1-native_uv[:,1]
        for key, rows in [('positions', transformed_p), ('normals', transformed_n), ('uvNative', native_uv), ('uvGltf', uv),
                          ('sourcePositions', base_p), ('sourceNormals', base_n), ('sourceUVNative', native_uv)]:
            archived[key].append(rows[mirrored_ids])
        archived['primitiveIds'].append(np.full(len(ids), primitive_id, dtype=np.int64))
        records.append({'primitive':primitive_id, 'triangles':len(ids), 'material':primitive.get('material'),
            'sourceAttributeAccessors':attributes, 'outputAttributeAccessors':new['attributes'],
            'sourceIndexAccessor':primitive['indices'], 'outputIndexAccessor':new['indices']})
        triangle_offset += len(ids); primitives.append(new)
    result['meshes'] = [{'name':'detached_geometry', 'primitives':primitives}]
    result['nodes'] = [{'name':'detached_geometry', 'mesh':0}]
    result['scenes'] = [{'nodes':[0]}]; result['scene'] = 0
    result['buffers'][0]['byteLength'] = len(output)
    archive = {key:np.concatenate(rows) for key, rows in archived.items()}
    archive['sourceTriangleIds'] = np.arange(triangle_offset, dtype=np.int64)
    archive['sourceCornerOrder'] = np.tile(order, (triangle_offset, 1))
    if tangent_rows:
        archive['tangents'] = np.concatenate(tangent_rows)
        archive['tangentTriangleIds'] = np.asarray(tangent_triangles, dtype=np.int64)
    serialized_p, serialized_n, serialized_uv, _ = raw_corners(result, bytes(output))
    expected_p = (source_p @ affine_nwn[:3,:3].T + affine_nwn[:3,3])[:,order]
    expected_n = (source_n @ rotation.T)[:,order]
    require(np.array_equal(archive['positions'], expected_p) and np.array_equal(archive['normals'], expected_n), 'Ordered corner derivation mismatch')
    require(np.array_equal(serialized_uv, source_uv[:,order]), 'UV sampling changed')
    require(embedded_maps(doc,binary) == embedded_maps(result,bytes(output)), 'Embedded map changed')
    proof = {'schemaVersion':1, 'uniformScale':scale, 'orthogonalFactorNwn':rotation.tolist(), 'reflected':bool(reflected),
        'originalBinPrefixExact':bytes(output[:len(binary)]) == binary, 'identityOutputNode':True,
        'originalUVColorAccessorDefinitionsExact':True, 'materialMapDefinitionsExact':True,
        'sourceNodeWorldRaw':world.tolist(), 'triangleCornerOrder':order.tolist(), 'triangles':triangle_offset,
        'maximumPositionFloat32ErrorMetres':float(np.max(np.abs(serialized_p-archive['positions']))),
        'maximumNormalFloat32Error':float(np.max(np.abs(serialized_n-archive['normals']))),
        'maximumAuthoredNormalLengthDifference':float(np.max(np.abs(np.linalg.norm(expected_n,axis=2)-np.linalg.norm(source_n[:,order],axis=2)))),
        'normalPolicy':'Orthogonal factor only; authored magnitude preserved',
        'tangentPolicy':'XYZ orthogonal factor only; W flips exactly for reflection',
        'uvPolicy':'Raw GLTF UV accessors unchanged; native archive V=1-rawV once; no U/normal-map channel flip',
        'rigPolicy':'No stock root, skeleton, controllers or animation resources written', 'primitives':records}
    return result, bytes(output), archive, proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); config = json.loads(args.config.read_text())
    require(not args.output.exists(), 'Fresh output required')
    source = Path(config['source']); root = Path(config['stockRoot'])
    require(sha(source) == config['sourceSha256'] and sha(root) == config['stockRootSha256'], 'Source/stock frame hash mismatch')
    receipt = Path(config['sourceReceipt']); require(sha(receipt) == config['sourceReceiptSha256'], 'Donor receipt hash mismatch')
    donor = json.loads(receipt.read_text())
    from stock_limb_contract import validate_mirror_association
    validate_mirror_association(donor, config['sourceJoint'], config['targetJoint'])
    require(Path(donor['candidate']).resolve() == source.resolve() and donor['candidateSha256'] == sha(source),
        'Donor receipt must associate this canonical fitted candidate')
    world = transforms(nodes(root.read_text(encoding='cp1252')))
    matrix, reflection = reflection_between_frames(world[config['sourceJoint']],world[config['targetJoint']],
        config['planeOriginWorld'], config['planeNormalWorld'])
    doc, binary = read_glb(source)
    new_doc, new_bin, archive, proof = detached_affine_bake(doc,binary,matrix,allow_reflection=True)
    args.output.mkdir(parents=True)
    target = args.output/'mirrored-local.glb'; write_glb(target,new_doc,new_bin)
    corner_path = args.output/'mirrored-corners.npz'; np.savez_compressed(corner_path,**archive)
    shutil.copyfile(__file__,args.output/'executed-helper.py')
    result = {'schemaVersion':1, 'diagnosticOnly':True, 'configuration':config,
        'source':str(source.resolve()), 'sourceSha256':sha(source), 'sourceReceipt':str(receipt.resolve()), 'sourceReceiptSha256':sha(receipt),
        'stockRoot':str(root.resolve()), 'stockRootSha256':sha(root),
        'sourceJointWorld':world[config['sourceJoint']].tolist(), 'targetJointWorld':world[config['targetJoint']].tolist(),
        'reflectionWorld':reflection.tolist(), 'sourceToTargetLocal':matrix.tolist(),
        'candidate':str(target.resolve()), 'candidateSha256':sha(target),
        'nativeCornerArchive':{'path':str(corner_path.resolve()),'sha256':sha(corner_path)}, 'proof':proof,
        'frozenInputs':{str(p.resolve()):sha(p) for p in [source,root,receipt,args.config,Path(__file__),Path(__file__).with_name('stock_limb_contract.py'),Path(__file__).with_name('place_purposebuilt_pelvis.py'),Path(__file__).with_name('retarget.py')]},
        'limitation':'Detached geometry mirror only; opposite attachment/pose/material and actual native tangent/client validation remain required.'}
    (args.output/'mirror.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'receipt':str(args.output/'mirror.json'),'candidateSha256':sha(target)}))


if __name__ == '__main__': main()
