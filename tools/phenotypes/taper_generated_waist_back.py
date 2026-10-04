"""Recorded local posterior or remaining-perimeter taper; preserve the stock fit."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

from round_generated_waist_cap import append_accessor, read_glb, sha, topology, write_glb


def smooth(value):
    t = np.clip(value, 0, 1)
    weight = t * t * (3 - 2 * t)
    derivative = np.where((value > 0) & (value < 1), 6 * t * (1 - t), 0)
    return weight, derivative


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-candidate', required=True, type=Path)
    parser.add_argument('--configuration', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source-glb-name', default='capped-local.glb')
    parser.add_argument('--result-glb-name', default='capped-local.glb')
    parser.add_argument('--cap-provenance', type=Path)
    parser.add_argument('--comparison-candidate', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('Fresh taper output required')
    if Path(args.source_glb_name).name != args.source_glb_name or Path(args.result_glb_name).name != args.result_glb_name:
        raise RuntimeError('Plain GLB filenames required')
    source = args.source_candidate / args.source_glb_name
    before_hash = sha(source)
    config = json.loads(args.configuration.read_text())
    if config.get('schemaVersion') != 1 or config.get('sourceSha256') != before_hash:
        raise RuntimeError('Explicit immutable capped-source configuration required')
    amount = float(config['maximumInwardMetres'])
    cut = float(config['waistCutChestLocalZ'])
    top = float(config['protectedAboveChestLocalZ'])
    mode = config.get('mode', 'posterior')
    if not all(np.isfinite(v) for v in [amount, cut, top]):
        raise RuntimeError('Finite field dimensions required')
    if not 0 < amount <= .004 or not cut < top <= cut + .020001:
        raise RuntimeError('Only at-most-4mm local taper in the 20mm band above the cut is authorized')
    document, original_binary, attrs, faces = read_glb(source, allow_multiple=True)
    if set(attrs) != {'POSITION', 'NORMAL', 'TEXCOORD_0'}:
        raise RuntimeError('Explicit position/normal/UV policy required')
    positions = attrs['POSITION'].astype(float)
    normal = attrs['NORMAL'].astype(float)
    vertical, derivative_vertical = smooth((top - positions[:, 1]) / (top - cut))
    derivative_vertical /= -(top - cut)
    used = np.zeros(len(positions), dtype=bool)
    used[np.unique(faces)] = True
    shifted = positions.copy()
    transformed_normal = normal.copy()
    prior_posterior_proof = None
    if mode == 'posterior':
        start = float(config['posteriorBlendStartRawGLB_Z'])
        full = float(config['posteriorBlendFullRawGLB_Z'])
        if not all(np.isfinite(v) for v in [start, full]) or not 0 <= start < full:
            raise RuntimeError('Finite ordered posterior field bounds required')
        determinant_bound = 1 - amount * 1.5 / (full - start)
        if determinant_bound <= .85:
            raise RuntimeError('Posterior taper is insufficiently bounded/invertible')
        posterior, derivative_posterior = smooth((positions[:, 2] - start) / (full - start))
        derivative_posterior /= full - start
        changed = used & (vertical > 0) & (posterior > 0)
        shift = amount * vertical * posterior
        shifted[changed, 2] -= shift[changed]
        fy = -amount * derivative_vertical * posterior
        determinant = 1 - amount * vertical * derivative_posterior
        transformed_normal[changed, 1] = normal[changed, 1] - fy[changed] * normal[changed, 2] / determinant[changed]
        transformed_normal[changed, 2] = normal[changed, 2] / determinant[changed]
        protected = (positions[:, 1] >= top) | (positions[:, 2] <= start) | ~used
        protected_label = 'upper/front/unused'
    elif mode == 'remaining-perimeter':
        centre = np.asarray(config['radialCentreRawGLB_XZ'], dtype=float)
        fade_full = float(config['perimeterPosteriorFadeFullRawGLB_Z'])
        posterior_stop = float(config['approvedPosteriorProtectedRawGLB_Z'])
        radius_start = float(config['radialFadeStartMetres'])
        radius_full = float(config['radialFadeFullMetres'])
        if centre.shape != (2,) or not np.isfinite(centre).all() or not all(np.isfinite(v) for v in [fade_full, posterior_stop, radius_start, radius_full]):
            raise RuntimeError('Finite measured perimeter field parameters required')
        if not fade_full < posterior_stop or not 0 < radius_start < radius_full:
            raise RuntimeError('Ordered posterior and pole fade bounds required')
        determinant_bound = (1 - amount / radius_start) * (1 - amount * 1.5 / (radius_full - radius_start) - amount * 1.5 / (posterior_stop - fade_full))
        if determinant_bound <= .5:
            raise RuntimeError('Perimeter field lacks a conservative positive global Jacobian bound')
        radial = positions[:, [0, 2]] - centre
        radius = np.linalg.norm(radial, axis=1)
        safe_radius = np.where(radius > 0, radius, 1.)
        unit = radial / safe_radius[:, None]
        radial_weight, radial_derivative = smooth((radius - radius_start) / (radius_full - radius_start))
        radial_derivative /= radius_full - radius_start
        posterior_weight, posterior_derivative = smooth((posterior_stop - positions[:, 2]) / (posterior_stop - fade_full))
        posterior_derivative /= -(posterior_stop - fade_full)
        magnitude = amount * vertical * posterior_weight * radial_weight
        changed = used & (magnitude > 0)
        shifted[changed, 0] -= magnitude[changed] * unit[changed, 0]
        shifted[changed, 2] -= magnitude[changed] * unit[changed, 1]
        gradient = amount * vertical[:, None] * (
            posterior_weight[:, None] * radial_derivative[:, None] * unit +
            radial_weight[:, None] * posterior_derivative[:, None] * np.asarray([0., 1.])[None])
        identity = np.eye(2)[None]
        outer_unit = unit[:, :, None] * unit[:, None, :]
        horizontal_jacobian = identity - unit[:, :, None] * gradient[:, None, :] - (magnitude / safe_radius)[:, None, None] * (identity - outer_unit)
        jacobian = np.broadcast_to(np.eye(3), (len(positions), 3, 3)).copy()
        jacobian[:, 0, 0] = horizontal_jacobian[:, 0, 0]
        jacobian[:, 0, 2] = horizontal_jacobian[:, 0, 1]
        jacobian[:, 2, 0] = horizontal_jacobian[:, 1, 0]
        jacobian[:, 2, 2] = horizontal_jacobian[:, 1, 1]
        vertical_gradient = amount * derivative_vertical * posterior_weight * radial_weight
        jacobian[:, 0, 1] = -vertical_gradient * unit[:, 0]
        jacobian[:, 2, 1] = -vertical_gradient * unit[:, 1]
        determinant = np.linalg.det(jacobian)
        if determinant.min() < determinant_bound - 1e-7:
            raise RuntimeError('Analytic perimeter Jacobian violates its global bound')
        transformed_normal[changed] = np.linalg.solve(jacobian[changed].transpose(0, 2, 1), normal[changed, :, None])[:, :, 0]
        protected = (positions[:, 1] >= top) | (positions[:, 2] >= posterior_stop) | (radius <= radius_start) | ~used
        protected_label = 'upper/approved-posterior/hidden-pole/unused'
        prior_path = args.source_candidate / 'taper-provenance.npz'
        if not prior_path.exists():
            raise RuntimeError('Recorded approved posterior provenance required')
        prior_ids = np.load(prior_path)['affectedVertexIndices']
        if changed[prior_ids].any():
            raise RuntimeError('Perimeter extension would double-taper an approved posterior vertex')
        prior_posterior_proof = {'source': str(prior_path.resolve()), 'sha256': sha(prior_path), 'protectedPreviouslyAffectedVertices': len(prior_ids)}
    else:
        raise RuntimeError('Unknown local taper mode')
    transformed_normal[changed] /= np.linalg.norm(transformed_normal[changed], axis=1)[:, None]
    output_attrs = {key: value.copy() for key, value in attrs.items()}
    output_attrs['POSITION'][changed] = shifted[changed].astype(np.float32)
    output_attrs['NORMAL'][changed] = transformed_normal[changed].astype(np.float32)
    before_topology = topology(attrs, faces)
    after_topology = topology(output_attrs, faces)
    for field in ['boundaryEdges', 'nonmanifoldEdges', 'inconsistentManifoldWindingEdges', 'degenerateTriangles']:
        if after_topology[field] != before_topology[field]:
            raise RuntimeError('Local taper changed source topology validity')
    if before_topology['boundaryPositions'] != after_topology['boundaryPositions']:
        raise RuntimeError('Unrelated source boundary edges moved')
    for key in attrs:
        if not np.array_equal(output_attrs[key][protected], attrs[key][protected]):
            raise RuntimeError('Protected regional attributes changed')
    if not np.array_equal(output_attrs['TEXCOORD_0'], attrs['TEXCOORD_0']):
        raise RuntimeError('Taper changed UVs')
    old_tri, new_tri = positions[faces], output_attrs['POSITION'][faces].astype(float)
    old_cross = np.cross(old_tri[:, 1] - old_tri[:, 0], old_tri[:, 2] - old_tri[:, 0])
    new_cross = np.cross(new_tri[:, 1] - new_tri[:, 0], new_tri[:, 2] - new_tri[:, 0])
    area_ratio = np.linalg.norm(new_cross, axis=1) / np.linalg.norm(old_cross, axis=1)
    winding_dot = np.einsum('ij,ij->i', old_cross, new_cross) / (np.linalg.norm(old_cross, axis=1) * np.linalg.norm(new_cross, axis=1))
    if area_ratio.min() <= .85 or winding_dot.min() <= .9:
        raise RuntimeError('Taper damages actual triangle area or winding')
    binary = bytearray(original_binary)
    indices = {key: append_accessor(document, binary, output_attrs[key].astype('<f4'), key) for key in ['POSITION', 'NORMAL']}
    for primitive in document['meshes'][0]['primitives']:
        primitive['attributes'].update(indices)
    args.output.mkdir(parents=True)
    shutil.copy2(source, args.output / 'frozen-selected-source.glb')
    shutil.copy2(args.configuration, args.output / 'configuration.json')
    shutil.copy2(__file__, args.output / Path(__file__).name)
    shutil.copy2(Path(__file__).with_name('round_generated_waist_cap.py'), args.output / 'frozen-round_generated_waist_cap.py')
    provenance_path = args.cap_provenance or args.source_candidate / 'cap-provenance.npz'
    shutil.copy2(provenance_path, args.output / 'cap-provenance.npz')
    result = args.output / args.result_glb_name
    write_glb(result, document, binary)
    _, serialized_binary, serialized_attrs, serialized_faces = read_glb(result, allow_multiple=True)
    if serialized_binary[:len(original_binary)] != original_binary or not np.array_equal(serialized_faces, faces):
        raise RuntimeError('Serialization changed source buffers or triangles')
    for key in output_attrs:
        if not np.array_equal(serialized_attrs[key], output_attrs[key]):
            raise RuntimeError('Serialized attribute arrays differ')
    if sha(source) != before_hash:
        raise RuntimeError('Immutable capped source changed')
    protected_faces = np.flatnonzero(protected[faces].all(axis=1))
    protected_hash = hashlib.sha256()
    for key in sorted(attrs):
        protected_hash.update(key.encode())
        protected_hash.update(attrs[key][faces[protected_faces]].tobytes())
    np.savez_compressed(args.output / 'taper-provenance.npz', affectedVertexIndices=np.flatnonzero(changed),
                        protectedVertexIndices=np.flatnonzero(protected), protectedFaceIndices=protected_faces,
                        sourcePositions=attrs['POSITION'], resultPositions=output_attrs['POSITION'],
                        sourceNormals=attrs['NORMAL'], resultNormals=output_attrs['NORMAL'], faces=faces)
    receipt = {'schemaVersion': 1, 'phase': 'posteriorWaistTaperDiagnostic' if mode == 'posterior' else 'remainingWaistPerimeterTaperDiagnostic', 'source': str(source.resolve()),
        'sourceSha256': before_hash, 'sourceUnchanged': True, 'sourceCandidate': str(args.source_candidate.resolve()),
        'configuration': config, 'configurationSha256': sha(args.configuration), 'scriptSha256': sha(Path(__file__)),
        'result': str(result.resolve()), 'resultSha256': sha(result), 'coordinateFrame': 'Actual capped-local raw GLB X-horizontal/Y-chest-local-vertical/Z=-BlenderY-depth.',
        'maximumActualInwardMetres': float(np.max(np.linalg.norm(output_attrs['POSITION'][changed] - attrs['POSITION'][changed], axis=1))),
        'affectedUsedVertices': int(changed.sum()), 'protectedVerticesExact': int(protected.sum()),
        'protectedFacesExact': len(protected_faces), 'protectedRegion': protected_label, 'protectedTriangleAttributeSha256': protected_hash.hexdigest(),
        'affectedOriginalBoundsRawGLB': [positions[changed].min(0).tolist(), positions[changed].max(0).tolist()],
        'normalPolicy': 'Analytic inverse-transpose Jacobian applied only to affected actual exported normals; protected rows untouched.',
        'minimumTheoreticalJacobianDeterminant': determinant_bound, 'minimumActualSampledJacobianDeterminant': float(determinant[changed].min()),
        'minimumActualTriangleAreaRatio': float(area_ratio.min()), 'minimumActualTriangleWindingDot': float(winding_dot.min()),
        'uvRowsExact': True, 'triangleIndicesExact': True, 'originalMaterialImageBuffersExact': True,
        'beforeTopology': before_topology, 'afterTopology': after_topology,
        'sourceDefectsRemain': True, 'nativeCommonAtlasPending': True, 'productionAccepted': False, 'clientAccepted': False,
        'priorApprovedPosteriorProof': prior_posterior_proof,
        'limitations': ['Only the configured lower waist and cap region is tapered; source inner walls, upper rim and unrelated defects remain.',
                       'UVs/maps are unchanged; actual mapped seam shading and native materials still require review.']}
    if args.comparison_candidate:
        _, _, comparison_attrs, comparison_faces = read_glb(args.comparison_candidate, allow_multiple=True)
        comparison_proof = {}
        for key in ['POSITION', 'NORMAL']:
            actual = serialized_attrs[key][serialized_faces]
            expected = comparison_attrs[key][comparison_faces]
            if not np.array_equal(actual, expected):
                raise RuntimeError('Actual ordered geometric corners differ from approved separate-atlas taper')
            comparison_proof[key] = {'orderedCornersExact': True, 'sha256': hashlib.sha256(actual.tobytes()).hexdigest()}
        receipt['comparisonProof'] = {'source': str(args.comparison_candidate.resolve()), 'sourceSha256': sha(args.comparison_candidate),
                                      'attributes': comparison_proof, 'orderedCornerCount': int(faces.size)}
    if (args.source_candidate / 'stock-replacement.json').exists():
        replacement = json.loads((args.source_candidate / 'stock-replacement.json').read_text())
        replacement['label'] = 'Purpose-built torso common atlas with posterior waist taper' if mode == 'posterior' else 'Purpose-built torso common atlas with remaining-perimeter waist taper'
        replacement['parts']['chest'] = str(result.resolve())
        replacement['chestSha256'] = sha(result)
        replacement['taperEvidence'] = str((args.output / 'waist-taper.json').resolve())
        (args.output / 'stock-replacement.json').write_text(json.dumps(replacement, indent=2) + '\n')
        receipt['nativeCommonAtlasPending'] = False
        receipt['commonAtlasBytesAndUvAccessorsExact'] = True
        inherited_receipt = args.source_candidate / 'common-atlas.json'
        if not inherited_receipt.exists():
            inherited_receipt = args.source_candidate / 'frozen-common-atlas.json'
        receipt['inheritedCommonAtlasReceipt'] = str(inherited_receipt.resolve())
        shutil.copy2(inherited_receipt, args.output / 'frozen-common-atlas.json')
        for path in args.source_candidate.glob('common-*.png'):
            shutil.copy2(path, args.output / path.name)
    (args.output / 'waist-taper.json').write_text(json.dumps(receipt, indent=2) + '\n')
    (args.output / 'waist-cap.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k: receipt[k] for k in ['result', 'resultSha256', 'maximumActualInwardMetres', 'affectedUsedVertices',
                                           'protectedFacesExact', 'minimumActualTriangleAreaRatio', 'minimumActualTriangleWindingDot']}, indent=2))


if __name__ == '__main__':
    main()
