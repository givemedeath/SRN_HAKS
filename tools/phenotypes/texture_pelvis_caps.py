"""Associate measured pelvis caps with approved real skin UVs, no pixel edits.

Consumes a separate localized cut/cap artifact after the recorded similarity
pass. Retained native corners remain authoritative float64; disposable GLB
FLOAT32 differences are measured explicitly. No geometry operations occur here.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil

import numpy as np
import stage_stock_pelvis as stage
import place_purposebuilt_pelvis as placement

SOURCE_HASH = 'e97df8c96cecdcada8e97bda19d9af125a6c45d2dd97b3b1557062df6c7cbb53'
COLOR_HASH = '9849f865a6940f513fbfe31ac64b37ca5df8983a9008bf3be21e14ab2f5af07d'
NORMAL_HASH = 'f5c076b8320fb830200b912daf3465e7b7fd811558fd836cd50717d294e5bc65'
UV_LOW = np.asarray([.3681640625, .1796875])
UV_HIGH = np.asarray([.4150390625, .2265625])
require = stage.stock.require
sha = stage.stock.sha
save = stage.stock.save


def validate_geometry(archive, source_arrays, geometry_receipt):
    p, uv, n = source_arrays
    fields = ['positions', 'normals', 'uvNative', 'sourceFaceIds', 'barycentrics', 'faceOriginType', 'capId', 'capUVLocal']
    require(all(name in archive for name in fields), 'Conditioned geometry corner contract incomplete')
    arrays = {name: np.array(archive[name], copy=True) for name in fields}
    count = len(arrays['positions'])
    for name, width in [('positions', 3), ('normals', 3), ('uvNative', 2), ('capUVLocal', 2)]:
        require(arrays[name].shape == (count, 3, width), 'Conditioned corner shape differs: ' + name)
    require(arrays['barycentrics'].shape == (count, 3, 3)
        and all(arrays[name].shape == (count,) for name in ['sourceFaceIds', 'faceOriginType', 'capId']), 'Conditioned provenance shape differs')
    origins = arrays['faceOriginType']; ids = arrays['sourceFaceIds']; cap = origins == 'cap'
    retained = origins == 'retained'; clipped = origins == 'clipped'
    require(set(origins.tolist()) <= {'retained', 'clipped', 'cap'} and cap.any() and retained.any(), 'Unknown/empty conditioned ownership')
    require(np.issubdtype(ids.dtype, np.integer) and np.all(ids[cap] == -1)
        and np.all((ids[~cap] >= 0) & (ids[~cap] < len(p))), 'Invalid conditioned source-face ownership')
    require(np.isfinite(arrays['positions']).all() and np.isfinite(arrays['normals']).all()
        and np.min(np.linalg.norm(arrays['normals'], axis=2)) > .5, 'Invalid conditioned geometry/normals')
    require(np.all(arrays['capId'][~cap] == 'none')
        and all(value in ('top', 'left', 'right') or value.startswith('repair-') for value in arrays['capId'][cap].tolist()), 'Undeclared cap ownership')
    require({'top', 'left', 'right'} <= set(arrays['capId'][cap].tolist()), 'Top and both thigh closures must be explicit')
    require(np.isfinite(arrays['capUVLocal'][cap]).all() and np.all(arrays['capUVLocal'][cap] >= 0)
        and np.all(arrays['capUVLocal'][cap] <= 1), 'Cap local UV chart outside0..1')
    require(np.isfinite(arrays['barycentrics'][~cap]).all()
        and np.max(abs(arrays['barycentrics'][~cap].sum(2) - 1)) < 1e-12
        and np.min(arrays['barycentrics'][~cap]) > -1e-12, 'Invalid cut barycentrics')
    retained_ids = ids[retained]
    require(len(np.unique(retained_ids)) == len(retained_ids), 'Retained source face duplicated')
    require(np.array_equal(arrays['barycentrics'][retained], np.broadcast_to(np.eye(3), (retained.sum(), 3, 3))), 'Retained source corner order changed')
    for name, original in [('positions', p), ('normals', n), ('uvNative', uv)]:
        require(np.array_equal(arrays[name][retained], original[retained_ids]), 'Protected retained corners differ: ' + name)
    if clipped.any():
        for name, original in [('positions', p), ('uvNative', uv)]:
            expected = np.einsum('tij,tjk->tik', arrays['barycentrics'][clipped], original[ids[clipped]])
            require(np.max(abs(arrays[name][clipped] - expected)) < 2e-12, 'Cut source interpolation differs: ' + name)
    protected = geometry_receipt['protectedRetainedSourceFaceIds']
    require(sorted(protected) == sorted(retained_ids.tolist()), 'Protected retained face receipt differs')
    for plane in geometry_receipt['cutPlanes']:
        require(plane.get('keep') == 'nonnegative', 'Unsupported cut-plane side')
        normal = np.asarray(plane['normal']); offset = float(plane['offset'])
        require(normal.shape == (3,) and np.isfinite(normal).all() and np.isfinite(offset), 'Invalid cut-plane controls')
        require(np.min(arrays['positions'][~cap] @ normal - offset) > -2e-12, 'Source face crosses removed cut side')
    return arrays, {'retainedFaces': int(retained.sum()), 'clippedFaces': int(clipped.sum()), 'capFaces': int(cap.sum()),
        'retainedPositionsNormalsUVExact': True, 'clippedPositionsUVBarycentricProofPassed': True,
        'allCapsRequireSkin': True, 'capCounts': {value: int((arrays['capId'] == value).sum()) for value in np.unique(arrays['capId'][cap])}}


def write_material_glb(path, source, p, uv_native, n):
    """Keep source materials/image blobs; only serialize supplied corner data."""
    doc, original_bin = placement.read_glb(source)
    primitive = doc['meshes'][0]['primitives'][0]
    require(len(doc['meshes']) == 1 and len(doc['meshes'][0]['primitives']) == 1, 'Explicit single source material required')
    require('COLOR_0' not in primitive['attributes'], 'Source vertex color needs an explicit retention policy')
    binary = bytearray(); views = []; accessors = []
    def blob(data):
        offset = len(binary); binary.extend(data); binary.extend(b'\0' * (-len(binary) % 4))
        views.append({'buffer': 0, 'byteOffset': offset, 'byteLength': len(data)})
        return len(views) - 1
    def attribute(array, dtype, kind, component):
        array = np.asarray(array, dtype=dtype); view = blob(array.tobytes())
        accessors.append({'bufferView': view, 'componentType': component, 'count': len(array), 'type': kind})
        return len(accessors) - 1
    raw_p = (p @ placement.BASIS).reshape(-1, 3).astype('<f4')
    raw_n = (n @ placement.BASIS).reshape(-1, 3).astype('<f4')
    raw_uv = uv_native.copy(); raw_uv[:, :, 1] = 1 - raw_uv[:, :, 1]; raw_uv = raw_uv.reshape(-1, 2).astype('<f4')
    # Corner-linear indexing intentionally retains UV/normal seams; native writer
    # later deduplicates exact (position, authored normal) independently from UV.
    attrs = {'POSITION': attribute(raw_p, '<f4', 'VEC3', 5126), 'NORMAL': attribute(raw_n, '<f4', 'VEC3', 5126),
             'TEXCOORD_0': attribute(raw_uv, '<f4', 'VEC2', 5126)}
    indices = attribute(np.arange(len(raw_p)), '<u4', 'SCALAR', 5125)
    images = copy.deepcopy(doc.get('images', []))
    for image in images:
        require('bufferView' in image and not image.get('uri'), 'External image prohibited')
        view = doc['bufferViews'][image['bufferView']]; offset = view.get('byteOffset', 0)
        image['bufferView'] = blob(original_bin[offset:offset + view['byteLength']])
    result = {'asset': {'version': '2.0'}, 'buffers': [{'byteLength': len(binary)}], 'bufferViews': views,
        'accessors': accessors, 'nodes': [{'mesh': 0}], 'scenes': [{'nodes': [0]}], 'scene': 0,
        'meshes': [{'primitives': [{'attributes': attrs, 'indices': indices, 'material': primitive['material']}]}],
        'materials': copy.deepcopy(doc['materials']), 'images': images, 'textures': copy.deepcopy(doc['textures'])}
    if 'samplers' in doc: result['samplers'] = copy.deepcopy(doc['samplers'])
    placement.write_glb(path, result, bytes(binary))


def repair_cap_wall_uv(arrays, geometry_receipt):
    """Give shallow extruded walls a nonsingular arclength/depth skin chart.

    Protected source UVs and all geometry/normals remain exact. The wall strip
    samples only the approved real-skin patch; the planar cap keeps its chart.
    """
    cap = arrays['faceOriginType'] == 'cap'; domain = arrays['capUVLocal']
    a = domain[:, 1]-domain[:, 0]; b = domain[:, 2]-domain[:, 0]
    determinant = a[:,0]*b[:,1]-a[:,1]*b[:,0]
    area = np.linalg.norm(np.cross(arrays['positions'][:,1]-arrays['positions'][:,0],
        arrays['positions'][:,2]-arrays['positions'][:,0]),axis=1)
    wall = cap & (abs(determinant) < 1e-14) & (area > 1e-14)
    before = arrays['uvNative'].copy(); reports=[]
    for capid in np.unique(arrays['capId'][wall]):
        details=[row for row in geometry_receipt['caps'] if row['capId'] == capid and not row.get('notCapped')]
        require(len(details) == 1, 'Wall chart requires one measured cap plane: '+capid)
        detail=details[0]; outward=np.asarray(detail['outward']); centre=np.asarray(detail['centre']); depth=float(detail['depth'])
        require(depth > 0 and abs(np.linalg.norm(outward)-1) < 1e-10, 'Wall chart requires unit outward/depth')
        ids=np.flatnonzero(wall & (arrays['capId'] == capid))
        values,inverse=np.unique(domain[ids].reshape(-1,2),axis=0,return_inverse=True); corners=inverse.reshape(-1,3)
        adjacency={i:set() for i in range(len(values))}; endpoints={}
        for face, vertices in zip(ids,corners):
            unique=np.unique(vertices); require(len(unique) == 2,'Wall triangle must span one rim edge')
            x,y=unique; adjacency[x].add(y); adjacency[y].add(x)
            for corner, vertex in enumerate(vertices):
                point=arrays['positions'][face,corner]; h=float((point-centre)@outward)
                require(-1e-10 <= h <= depth+1e-10,'Wall corner outside measured extrusion')
                rim=point-outward*h
                if vertex in endpoints: require(np.max(abs(endpoints[vertex]-rim)) < 1e-10,'Wall domain aliases different rim points')
                else: endpoints[vertex]=rim
        require(all(len(neighbors) == 2 for neighbors in adjacency.values()),'Wall perimeter not simple closed ring')
        order=[0]; previous=None; current=0
        while True:
            choices=sorted(adjacency[current]-({previous} if previous is not None else set()))
            next_vertex=choices[0]
            if next_vertex == 0: break
            require(next_vertex not in order,'Wall ring crosses/repeats')
            order.append(next_vertex); previous,current=current,next_vertex
        require(len(order) == len(values),'Wall chart ring has disconnected component')
        edge_lengths=np.asarray([np.linalg.norm(endpoints[order[(i+1)%len(order)]]-endpoints[vertex]) for i,vertex in enumerate(order)])
        require(np.min(edge_lengths)>1e-12,'Wall chart has zero rim edge')
        distance=np.r_[0,np.cumsum(edge_lengths[:-1])]/edge_lengths.sum(); arc={vertex:distance[i] for i,vertex in enumerate(order)}
        seam={order[-1],order[0]}
        for face,vertices in zip(ids,corners):
            closing=set(np.unique(vertices)) == seam
            u=np.asarray([1. if closing and vertex == order[0] else arc[vertex] for vertex in vertices])
            h=(arrays['positions'][face]-centre)@outward/depth
            chart=np.c_[.02+.96*u,.80+.18*np.clip(h,0,1)]
            gltf=UV_LOW+chart*(UV_HIGH-UV_LOW); gltf[:,1]=1-gltf[:,1]; arrays['uvNative'][face]=gltf
        reports.append({'capId':str(capid),'wallFaceIds':ids.tolist(),'rimVertices':len(values),'perimeterMetres':float(edge_lengths.sum()),
            'stripDomainU':[.02,.98],'stripDomainV':[.80,.98],'seamRimVertexIndices':[int(value) for value in sorted(seam)]})
    require(np.array_equal(before[~wall],arrays['uvNative'][~wall]),'Wall chart touched non-wall UVs')
    auv=arrays['uvNative']; a=auv[:,1]-auv[:,0]; b=auv[:,2]-auv[:,0]; det=a[:,0]*b[:,1]-a[:,1]*b[:,0]
    require(np.all(abs(det[cap & (area>1e-14)])>1e-14),'Cap retains singular UV triangle')
    return {'operation':'arclength-and-extrusion-depth-skin-strip','wallFaces':int(wall.sum()),'caps':reports,
        'minimumWallUVAreaTwice':float(np.min(abs(det[wall]))) if wall.any() else None,
        'sourceUVsExact':True,'planarCapUVsExact':True,'positionsNormalsExact':True,
        'nativeTangentValidityClaimed':False,'nativeCompilerInspectionStillRequired':True}


def run(config_path, output):
    config_path = Path(config_path).resolve(); config = json.loads(config_path.read_text())
    require(config.get('schemaVersion') == 1 and config.get('diagnosticOnly') is True, 'Explicit cap material diagnostic required')
    require(config.get('sourceSha256') == SOURCE_HASH and config.get('colorSha256') == COLOR_HASH
        and config.get('normalSha256') == NORMAL_HASH, 'Unreviewed source/cap chart association')
    original = stage.verify_file(config['source'], SOURCE_HASH, 'Anatomical source')
    color = stage.verify_file(config['color'], COLOR_HASH, 'Source color')
    normal = stage.verify_file(config['normal'], NORMAL_HASH, 'Source normal')
    geometry_receipt_path = stage.verify_file(config['geometryReceipt'], config['geometryReceiptSha256'], 'Localized geometry receipt')
    geometry_archive_path = stage.verify_file(config['geometryArchive'], config['geometryArchiveSha256'], 'Localized native corner archive')
    geometry_receipt = json.loads(geometry_receipt_path.read_text())
    first_fit = config['firstFit']; wrapper = stage.verify_file(first_fit['source'], first_fit['sourceSha256'], 'First uniform fit')
    require(geometry_receipt.get('sourceSha256') == SOURCE_HASH
        and geometry_receipt.get('placementReceiptSha256') == first_fit['placementReceiptSha256'], 'Geometry not associated with reviewed generation/first fit')
    require(Path(geometry_receipt['nativeCornerArchive']['path']).resolve() == geometry_archive_path
        and geometry_receipt['nativeCornerArchive']['sha256'] == sha(geometry_archive_path), 'Geometry archive receipt differs')
    ownership = geometry_receipt['componentOwnershipProof']
    ownership_path = stage.verify_file(ownership['path'], ownership['sha256'], 'Independent outward/inward ownership proof')
    fit_p, fit_uv, fit_n, _, fit_inputs, fit_proof = stage.similarity_corners({'similarityFit': first_fit},
        {'source': wrapper, 'color': color, 'normal': normal}, Path(config['stockBaseline']).resolve())
    require(fit_proof['originalSourceSha256'] == SOURCE_HASH, 'First fit came from different generated anatomy')
    with np.load(geometry_archive_path, allow_pickle=False) as archive:
        arrays, protected_proof = validate_geometry(archive, (fit_p, fit_uv, fit_n), geometry_receipt)
    cap = arrays['faceOriginType'] == 'cap'; before_uv = arrays['uvNative'].copy()
    cap_uv = UV_LOW + arrays['capUVLocal'][cap] * (UV_HIGH - UV_LOW)
    cap_uv[:, :, 1] = 1 - cap_uv[:, :, 1]
    arrays['uvNative'][cap] = cap_uv
    wall_proof=repair_cap_wall_uv(arrays,geometry_receipt)
    require(np.array_equal(before_uv[~cap], arrays['uvNative'][~cap]), 'Cap operation altered retained source UV')
    output = Path(output).resolve(); output.mkdir(exist_ok=False)
    material_glb = output / 'cap-skin-local.glb'
    write_material_glb(material_glb, original, arrays['positions'], arrays['uvNative'], arrays['normals'])
    actual_p, actual_uv, actual_n, _ = stage.stock.raw_triangles(material_glb, color, normal)
    errors = {key: float(np.max(abs(actual - expected))) for key, actual, expected in
        [('positionMetres', actual_p, arrays['positions']), ('authoredNormal', actual_n, arrays['normals']), ('uv', actual_uv, arrays['uvNative'])]}
    require(errors['positionMetres'] < 1e-7 and errors['authoredNormal'] < 1e-7 and errors['uv'] < 1e-7, 'Unexpected diagnostic FLOAT32 serialization loss')
    archive_path = output / 'conditioned-native-corners.npz'; np.savez_compressed(archive_path, **arrays)
    template = {'schemaVersion': 1, 'reviewed': False, 'policy': 'explicit-reviewed-semantic',
        'sourceSha256': sha(material_glb), 'originalSourceSha256': SOURCE_HASH,
        'placementReceiptSha256': first_fit['placementReceiptSha256'], 'colorSha256': COLOR_HASH, 'normalSha256': NORMAL_HASH,
        'orderedCornerSha256': stage.corner_hash(arrays['positions'], arrays['uvNative'], arrays['normals']),
        'faceCount': len(cap), 'labels': ['capSkin' if value else 'unresolved' for value in cap],
        'mask': {'path': None, 'sha256': None, 'uvSpace': 'gltf-top-left'}, 'reviewEvidence': []}
    save(output / 'semantic-label-template.json', template)
    inputs = {str(path): sha(path) for path in [config_path, original, color, normal, geometry_receipt_path,
        geometry_archive_path, ownership_path, Path(__file__).resolve(), Path(stage.__file__).resolve()]}; inputs.update(fit_inputs)
    receipt = {'schemaVersion': 1, 'diagnosticOnly': True, 'operation': 'localized-caps-source-skin-UV-only',
        'sourceSha256': SOURCE_HASH, 'placementReceiptSha256': first_fit['placementReceiptSha256'],
        'firstFit': first_fit, 'geometryReceipt': {'path': str(geometry_receipt_path), 'sha256': sha(geometry_receipt_path)},
        'geometryArchive': {'path': str(geometry_archive_path), 'sha256': sha(geometry_archive_path)},
        'componentOwnershipProof': {'path': str(ownership_path), 'sha256': sha(ownership_path)},
        'conditionedSource': {'path': str(material_glb), 'sha256': sha(material_glb)},
        'nativeCornerArchive': {'path': str(archive_path), 'sha256': sha(archive_path)},
        'maps': {'color': {'path': str(color), 'sha256': COLOR_HASH}, 'normal': {'path': str(normal), 'sha256': NORMAL_HASH}},
        'capSkinChart': {'rectanglePixelsTopLeft': [738, 352, 866, 480], 'insetPixels': 16,
            'uvGlTFMinimum': UV_LOW.tolist(), 'uvGlTFMaximum': UV_HIGH.tolist(), 'allCapIdsSkin': True},
        'protectedProof': protected_proof, 'capWallUVProof':wall_proof, 'diagnosticFloat32MaximumErrors': errors,
        'originalMapPixelsAndBytesExact': True, 'nonCapNativeUVExact': True, 'positionsNormalsNotEditedHere': True,
        'originalSourceModified': False, 'stockRigChanged': False, 'frozenTorsoChanged': False,
        'frozenInputs': inputs, 'nativeCompiled': False, 'clientLaunched': False, 'clientAccepted': False}
    for path, expected in inputs.items(): stage.verify_file(path, expected, 'Frozen cap material input')
    save(output / 'cap-skin-material.json', receipt)
    template['materialReceiptSha256'] = sha(output / 'cap-skin-material.json')
    save(output / 'semantic-label-template.json', template)
    shutil.copyfile(Path(__file__), output / 'executed-texture-pelvis-caps.py')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); receipt = run(args.config, args.output)
    print(json.dumps({'output': str(args.output.resolve()), 'capsSkin': receipt['protectedProof']['capFaces'],
                      'mapsUnchanged': True, 'nativeCompiled': False, 'clientLaunched': False}))


if __name__ == '__main__': main()
