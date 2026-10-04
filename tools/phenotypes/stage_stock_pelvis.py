"""Stage reviewed pelvis skin/briefs and byte-exact frozen chest; never compile.

Requires a source-hash-bound explicit semantic label artifact. This adapter does
not infer clothing from color, geometry height, or a legacy whole-body donor.
Run with bundled Python --config CONFIG --output FRESH_DIRECTORY.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

import stage_stock_part as stock

MODEL = 'pmh0_pelvis001'
CHEST = 'pmh0_chest001'
CHEST_RESOURCES = {CHEST + suffix for suffix in ('.mdl', '.mtr', '.plt', 'n.tga')}
PELVIS_MATERIALS = {MODEL + suffix for suffix in ('.plt', '.mtr', 'n.tga', 'f.tga', 'f.mtr')}


def corner_hash(p, uv, n):
    """Face/corner order in raw_triangles' NWN axes and once-flipped UV space."""
    return hashlib.sha256(np.concatenate((p, uv, n), axis=2).astype('<f8').tobytes()).hexdigest()


def verify_file(path, expected, purpose):
    path = Path(path).resolve()
    stock.require(path.is_file() and stock.sha(path) == expected, purpose + ' changed/missing: ' + str(path))
    return path


def similarity_corners(config, selected, baseline):
    """Independently verify an explicitly declared lossless similarity wrapper.

    Only this pelvis adapter accepts that declared wrapper. The older stock-part
    loader remains unit-scale-only. Native UVs are consumed without another flip.
    """
    import copy
    import place_purposebuilt_pelvis as placement

    declared = config['similarityFit']
    receipt_path = verify_file(declared['placementReceipt'], declared['placementReceiptSha256'], 'Similarity receipt')
    original = verify_file(declared['originalSource'], declared['originalSourceSha256'], 'Original generated source')
    archive_path = verify_file(declared['nativeCornerArchive'], declared['nativeCornerArchiveSha256'], 'Similarity native corners')
    receipt = json.loads(receipt_path.read_text())
    stock.require(receipt.get('schemaVersion') == 1 and receipt.get('phase') == 'place'
        and receipt.get('diagnosticOnly') is True and receipt.get('stockRigChanged') is False
        and receipt.get('frozenTorsoChanged') is False, 'Unsupported similarity proof')
    stock.require(receipt.get('sourceSha256') == stock.sha(original)
        and receipt.get('placedSourceSha256') == stock.sha(selected['source']), 'Similarity source/wrapper hash mismatch')
    proof = receipt['proof']; archived = proof['nativeCornerArchive']
    stock.require(Path(archived['path']).resolve() == archive_path and archived['sha256'] == stock.sha(archive_path),
                  'Similarity archive not associated with receipt')
    fit = receipt['configuration']
    stock.require(fit.get('sourceSha256') == stock.sha(original)
        and fit.get('stockRootSha256') == stock.sha(baseline / 'ascii/pmh0.mdl')
        and fit.get('frozenTorsoSha256') == placement.TORSO_HASH, 'Similarity stock/source association mismatch')
    generation_path = verify_file(receipt_path.parent / 'frozen-generation.json', fit['generationSha256'], 'Frozen generation receipt')
    generation = json.loads(generation_path.read_text())
    stock.require(generation.get('state') == 'success' and generation.get('promptId') == receipt['jobPromptId'] == fit['jobPromptId']
        and any(row.get('sha256') == stock.sha(original) for row in generation.get('outputs', [])), 'Similarity source not associated with actual completed generation')
    scale = float(fit['uniformScale']); r = np.asarray(receipt['properRotationMatrixNwn'], dtype=float)
    anchor = np.asarray(fit['sourceAnchorNwn'], dtype=float); target = np.asarray(fit['targetAnchorPelvisLocal'], dtype=float)
    stock.require(np.isfinite(scale) and 0 < scale < 10 and r.shape == (3, 3)
        and np.isfinite(r).all() and np.allclose(r.T @ r, np.eye(3), atol=1e-12, rtol=0)
        and abs(np.linalg.det(r) - 1) < 1e-12, 'Similarity requires one positive scale and proper rotation')
    stock.require(anchor.shape == target.shape == (3,) and np.isfinite(anchor).all() and np.isfinite(target).all(), 'Invalid similarity anchors')
    stock.require(np.allclose(r, placement.rotation_xyz(fit['rotationDegreesXYZ']), atol=1e-12, rtol=0), 'Rotation controls differ from recorded matrix')
    matrix = np.eye(4); basis = placement.BASIS
    matrix[:3, :3] = basis.T @ r @ basis * scale
    matrix[:3, 3] = basis.T @ (target - scale * r @ anchor)
    stock.require(np.allclose(matrix, receipt['rawGlTFWrapperMatrix'], atol=1e-12, rtol=0), 'Wrapper matrix differs from declared similarity')
    doc, binary = placement.read_glb(original); actual_doc, actual_bin = placement.read_glb(selected['source'])
    expected_doc = copy.deepcopy(doc)
    scene = expected_doc['scenes'][expected_doc.get('scene', 0)]; roots = scene['nodes'][:]
    index = len(expected_doc['nodes'])
    expected_doc['nodes'].append({'name': 'Recorded pelvis uniform placement',
        'matrix': matrix.reshape(-1, order='F').tolist(), 'children': roots})
    scene['nodes'] = [index]
    # Numeric wrapper entries tolerate serialization arithmetic only; all other
    # node/scene/material/accessor metadata and original BIN must be exact.
    comparison = copy.deepcopy(actual_doc)
    stock.require(len(comparison.get('nodes', [])) == index + 1, 'Undeclared placement nodes')
    actual_matrix = comparison['nodes'][index].get('matrix', [])
    stock.require(len(actual_matrix) == 16 and np.allclose(np.asarray(actual_matrix).reshape(4, 4, order='F'), matrix, atol=1e-12, rtol=0),
                  'Actual wrapper matrix differs')
    comparison['nodes'][index]['matrix'] = expected_doc['nodes'][index]['matrix']
    stock.require(comparison == expected_doc and actual_bin == binary, 'Placement changed original GLB data beyond wrapper')
    # Existing loader verifies maps, static triangles and unit-scale source nodes.
    source_p, source_uv, source_n, materials = stock.raw_triangles(original, selected['color'], selected['normal'])
    actual_p, actual_n, actual_uv, records = placement.raw_corners(actual_doc, actual_bin, allow_wrapper=True)
    native_uv = actual_uv.copy(); native_uv[:, :, 1] = 1 - native_uv[:, :, 1]
    expected_p = (source_p - anchor) @ r.T * scale + target
    expected_n = source_n @ r.T
    stock.require(np.max(abs(actual_p - expected_p)) < 2e-12
        and np.max(abs(actual_n - expected_n)) < 2e-12
        and np.array_equal(source_uv, native_uv), 'Similarity raw-corner mathematical proof failed')
    with np.load(archive_path, allow_pickle=False) as archive:
        for key, expected in [('placedPositionsPelvisLocal', actual_p), ('placedNormalsPelvisLocal', actual_n),
                              ('placedUVNative', native_uv), ('placedUVGlTF', actual_uv)]:
            stock.require(key in archive and np.array_equal(archive[key], expected), 'Native corner archive differs: ' + key)
        for key, expected in [('sourceSha256', stock.sha(original)), ('placedSourceSha256', stock.sha(selected['source'])),
                              ('jobPromptId', receipt['jobPromptId'])]:
            stock.require(str(archive[key].item()) == expected, 'Archive source/job association mismatch')
    inputs = {str(path): stock.sha(path) for path in [receipt_path, original, archive_path, generation_path, Path(placement.__file__).resolve()]}
    return actual_p, native_uv, actual_n, materials, inputs, {
        'receiptSha256': stock.sha(receipt_path), 'originalSourceSha256': stock.sha(original),
        'wrapperSha256': stock.sha(selected['source']), 'nativeCornerArchiveSha256': stock.sha(archive_path),
        'originalBinBytesExact': True, 'onlyDeclaredWrapperAdded': True, 'uniformScale': scale,
        'properRotationMatrixNwn': r.tolist(), 'nativeUVFlipCount': 1,
        'normalPolicy': 'Authored normals rotated by proper R only; uniform scale does not change lengths',
        'maximumPositionProofError': float(np.max(abs(actual_p - expected_p))),
        'maximumNormalProofError': float(np.max(abs(actual_n - expected_n)))}


def conditioned_corners(config, selected, baseline):
    """Accept a separately proven localized descendant, never similarity-only."""
    import texture_pelvis_caps as cap_material
    declared = config['conditionedFit']
    receipt_path = verify_file(declared['materialReceipt'], declared['materialReceiptSha256'], 'Conditioned material receipt')
    receipt = json.loads(receipt_path.read_text())
    stock.require(receipt.get('schemaVersion') == 1 and receipt.get('diagnosticOnly') is True
        and receipt.get('operation') == 'localized-caps-source-skin-UV-only'
        and receipt.get('stockRigChanged') is False and receipt.get('frozenTorsoChanged') is False,
        'Unsupported conditioned-fit operation/rig change')
    for path, expected in receipt['frozenInputs'].items(): verify_file(path, expected, 'Conditioned input')
    for key in ['color', 'normal']:
        row = receipt['maps'][key]
        stock.require(Path(row['path']).resolve() == selected[key] and row['sha256'] == stock.sha(selected[key]), 'Conditioned map association differs')
    source_row = receipt['conditionedSource']
    conditioned_source = verify_file(source_row['path'], source_row['sha256'], 'Conditioned baseline source')
    stock.require(config.get('postFitSimilarity') or conditioned_source == selected['source'], 'Conditioned source association differs')
    first_fit = receipt['firstFit']
    wrapper = verify_file(first_fit['source'], first_fit['sourceSha256'], 'Protected first similarity')
    source_p, source_uv, source_n, _, first_inputs, first_proof = similarity_corners({'similarityFit': first_fit},
        {'source': wrapper, 'color': selected['color'], 'normal': selected['normal']}, baseline)
    stock.require(receipt['sourceSha256'] == first_proof['originalSourceSha256'] == cap_material.SOURCE_HASH
        and receipt['placementReceiptSha256'] == first_proof['receiptSha256'], 'Conditioned descendant not bound to original generation/first fit')
    geometry_path = verify_file(receipt['geometryReceipt']['path'], receipt['geometryReceipt']['sha256'], 'Localized geometry receipt')
    geometry = json.loads(geometry_path.read_text())
    geometry_archive = verify_file(receipt['geometryArchive']['path'], receipt['geometryArchive']['sha256'], 'Localized geometry corners')
    stock.require(geometry['sourceSha256'] == receipt['sourceSha256']
        and geometry['placementReceiptSha256'] == receipt['placementReceiptSha256'], 'Localized source/placement association differs')
    stock.require(Path(geometry['nativeCornerArchive']['path']).resolve() == geometry_archive
        and geometry['nativeCornerArchive']['sha256'] == stock.sha(geometry_archive), 'Geometry archive receipt association differs')
    with np.load(geometry_archive, allow_pickle=False) as archive:
        expected, protected_proof = cap_material.validate_geometry(archive, (source_p, source_uv, source_n), geometry)
    cap = expected['faceOriginType'] == 'cap'
    uv = cap_material.UV_LOW + expected['capUVLocal'][cap] * (cap_material.UV_HIGH - cap_material.UV_LOW)
    uv[:, :, 1] = 1 - uv[:, :, 1]; expected['uvNative'][cap] = uv
    wall_proof=cap_material.repair_cap_wall_uv(expected,geometry)
    stock.require(receipt.get('capWallUVProof') == wall_proof,'Cap wall UV/tangent preflight receipt differs')
    row = receipt['nativeCornerArchive']; archive_path = verify_file(row['path'], row['sha256'], 'Conditioned authoritative native corners')
    with np.load(archive_path, allow_pickle=False) as archive:
        stock.require(set(archive.files) == set(expected), 'Unexpected conditioned native attributes')
        for name, array in expected.items():
            if np.issubdtype(array.dtype, np.floating):
                same = np.array_equal(archive[name], array, equal_nan=True)
            else: same = np.array_equal(archive[name], array)
            stock.require(same, 'Conditioned source/cap corner proof differs: ' + name)
    actual_p, actual_uv, actual_n, materials = stock.raw_triangles(conditioned_source, selected['color'], selected['normal'])
    errors = {key: float(np.max(abs(actual - wanted))) for key, actual, wanted in
        [('positionMetres', actual_p, expected['positions']), ('authoredNormal', actual_n, expected['normals']), ('uv', actual_uv, expected['uvNative'])]}
    stock.require(all(value < 1e-7 for value in errors.values())
        and errors == receipt['diagnosticFloat32MaximumErrors'], 'Conditioned rendered GLB differs from authoritative corner proof')
    inputs = {str(path): stock.sha(path) for path in [receipt_path, geometry_path, geometry_archive, archive_path,
        Path(cap_material.__file__).resolve()]}; inputs.update(first_inputs); inputs.update(receipt['frozenInputs'])
    proof = {'materialReceiptSha256': stock.sha(receipt_path), 'geometryReceiptSha256': stock.sha(geometry_path),
        'originalSourceSha256': receipt['sourceSha256'], 'firstSimilarityReceiptSha256': receipt['placementReceiptSha256'],
        'descendantSourceSha256': stock.sha(conditioned_source), 'authoritativeNativeArchiveSha256': stock.sha(archive_path),
        'protectedCornerProof': protected_proof, 'diagnosticFloat32MaximumErrors': errors,
        'sourceMode': 'separately-recorded-localized-condition', 'unchangedSimilarityClaimed': False,
        'allCapsSkin': True, 'originalMapsUnchanged': True, 'firstFit': first_proof}
    p, uv, n = expected['positions'], expected['uvNative'], expected['normals']
    if config.get('postFitSimilarity'):
        p, uv, n, post_inputs, post_proof = postfit_corners(config['postFitSimilarity'], selected, expected,
            geometry_path, geometry_archive, receipt_path, archive_path)
        inputs.update(post_inputs); proof['postFitSimilarity'] = post_proof
        proof['finalSourceSha256'] = stock.sha(selected['source'])
    return p, uv, n, materials, inputs, proof, cap


def postfit_corners(declared, selected, expected, geometry_path, geometry_archive,
                    material_receipt_path=None, material_archive_path=None):
    """Compose a small recorded uniform similarity after local conditioning.

    Source conditioning remains proved in its original frame. This branch does
    not claim that transformed corners are unchanged first-fit geometry.
    """
    import copy
    import place_purposebuilt_pelvis as placement
    receipt_path = verify_file(declared['receipt'], declared['receiptSha256'], 'Post-fit receipt')
    receipt = json.loads(receipt_path.read_text())
    stock.require(receipt.get('diagnosticOnly') is True, 'Post-fit diagnostic flag required')
    is_material=receipt.get('baselineReceiptKind') == 'cap-material'
    parent_receipt=material_receipt_path if is_material else geometry_path
    parent_archive=material_archive_path if is_material else geometry_archive
    stock.require(parent_receipt is not None and parent_archive is not None,'Post-fit baseline type lacks independent association')
    stock.require(Path(receipt['baselineReceipt']).resolve() == parent_receipt.resolve()
        and receipt['baselineReceiptSha256'] == stock.sha(parent_receipt), 'Post-fit conditioning/material receipt differs')
    base_archive_row = receipt['baselineNativeCornerArchive']
    stock.require(Path(base_archive_row['path']).resolve() == parent_archive.resolve()
        and base_archive_row['sha256'] == stock.sha(parent_archive), 'Post-fit conditioning/material archive differs')
    base = verify_file(receipt['baselineSource'], receipt['baselineSourceSha256'], 'Post-fit baseline source')
    parent = json.loads(parent_receipt.read_text())
    parent_source=parent['conditionedSource']['path'] if is_material else parent['candidate']
    parent_hash=parent['conditionedSource']['sha256'] if is_material else parent['candidateSha256']
    stock.require(Path(parent_source).resolve() == base and parent_hash == stock.sha(base),
        'Post-fit baseline not bound to localized geometry')
    stock.require(Path(receipt['candidate']).resolve() == selected['source']
        and receipt['candidateSha256'] == stock.sha(selected['source']), 'Post-fit final source differs')
    fit = receipt['configuration']; scale = float(fit['uniformScale'])
    degrees = np.asarray(fit['rotationDegreesXYZ'], dtype=float); anchor = np.asarray(fit['anchorPelvisLocal'], dtype=float)
    r = np.asarray(receipt['properRotationMatrix'], dtype=float)
    stock.require(np.isfinite(scale) and .96 <= scale <= 1.04 and degrees.shape == anchor.shape == (3,)
        and np.isfinite(degrees).all() and np.isfinite(anchor).all() and abs(degrees[0]) <= 6
        and degrees[1] == degrees[2] == 0, 'Post-fit exceeds recorded uniform/X-pitch-only scope')
    stock.require(r.shape == (3,3) and np.isfinite(r).all() and np.allclose(r.T@r,np.eye(3),atol=1e-12,rtol=0)
        and abs(np.linalg.det(r)-1) < 1e-12 and np.allclose(r,placement.rotation_xyz(degrees),atol=1e-12,rtol=0),
        'Post-fit requires declared proper rotation')
    delta=np.asarray(fit.get('translationPelvisLocal',[0,0,0]),float)
    stock.require(delta.shape == (3,) and np.isfinite(delta).all() and np.max(abs(delta)) <= .015,'Post-fit translation exceeds small declared bounds')
    translation=anchor+delta-scale*r@anchor; matrix=np.eye(4)
    matrix[:3,:3]=placement.BASIS.T@r@placement.BASIS*scale
    matrix[:3,3]=placement.BASIS.T@translation
    stock.require(np.allclose(receipt['rawWrapperMatrix'],matrix,atol=1e-12,rtol=0)
        and np.allclose(receipt['nativeAffineTranslation'],translation,atol=1e-12,rtol=0), 'Post-fit matrix/anchor differs')
    doc,binary=placement.read_glb(base); actual_doc,actual_binary=placement.read_glb(selected['source'])
    expected_doc=copy.deepcopy(doc); index=len(doc['nodes']); scene=expected_doc['scenes'][expected_doc.get('scene',0)]
    expected_doc['nodes'].append({'name':'Declared diagnostic postfit similarity','matrix':matrix.flatten(order='F').tolist(),'children':list(scene['nodes'])})
    scene['nodes']=[index]; comparison=copy.deepcopy(actual_doc)
    stock.require(len(comparison.get('nodes',[])) == index+1
        and np.allclose(np.asarray(comparison['nodes'][index].get('matrix',[])).reshape(4,4,order='F'),matrix,atol=1e-12,rtol=0),
        'Post-fit wrapper differs')
    comparison['nodes'][index]['matrix']=expected_doc['nodes'][index]['matrix']
    stock.require(comparison == expected_doc and actual_binary == binary, 'Post-fit changed baseline beyond wrapper')
    # Check the actually wrapped GLB, not only its receipt or archive. The base
    # render file is FLOAT32 while native authoritative arrays remain FLOAT64.
    bp,buv,bn,_=stock.raw_triangles(base,selected['color'],selected['normal'])
    stock.require(np.max(abs(bp-expected['positions'])) < 1e-7
        and np.max(abs(bn-expected['normals'])) < 1e-7 and np.max(abs(buv-expected['uvNative'])) < 1e-7,
        'Post-fit baseline does not match current conditioned material/corners')
    ap,an,auv,_=placement.raw_corners(actual_doc,actual_binary,allow_wrapper=True)
    auv[:,:,1]=1-auv[:,:,1]
    p=expected['positions']@r.T*scale+translation; n=expected['normals']@r.T; uv=expected['uvNative']
    errors={'positionMetres':float(np.max(abs(ap-p))),'authoredNormal':float(np.max(abs(an-n))),
        'uv':float(np.max(abs(auv-uv)))}
    stock.require(all(value < 1e-7 for value in errors.values()), 'Post-fit raw GLB/corner derivation differs')
    row=receipt['nativeCornerArchive']; archive_path=verify_file(row['path'],row['sha256'],'Post-fit native corners')
    with np.load(archive_path,allow_pickle=False) as archive:
        stock.require(set(archive.files) == set(expected)|{'postFitBasePositions','postFitBaseNormals'}, 'Post-fit archive fields differ')
        for name,value in {**expected,'positions':p,'normals':n,
            'postFitBasePositions':expected['positions'],'postFitBaseNormals':expected['normals']}.items():
            same=np.array_equal(archive[name],value,equal_nan=True) if np.issubdtype(value.dtype,np.floating) else np.array_equal(archive[name],value)
            stock.require(same,'Post-fit authoritative provenance/corners differ: '+name)
    inputs={str(path):stock.sha(path) for path in [receipt_path,base,selected['source'],archive_path,geometry_path,geometry_archive,parent_receipt,parent_archive]}
    proof={'receiptSha256':stock.sha(receipt_path),'baselineSourceSha256':stock.sha(base),
        'baselineGeometryReceiptSha256':stock.sha(geometry_path),'finalSourceSha256':stock.sha(selected['source']),
        'nativeCornerArchiveSha256':stock.sha(archive_path),'uniformScale':scale,'properRotationMatrix':r.tolist(),
        'anchorPelvisLocal':anchor.tolist(),'targetAnchorPelvisLocal':(anchor+delta).tolist(),
        'originalBinBytesExact':True,'onlyDeclaredWrapperAdded':True,'sourceFaceUVCapProvenanceExact':True,
        'normalPolicy':'Proper R only; authored magnitudes preserved', 'diagnosticFloat32MaximumErrors':errors,
        'conditioningProofFrameUnchanged':True,'unchangedFirstFitClaimed':False}
    return p,uv,n,inputs,proof


def read_labels(path, source, color, normal, p, uv, n, allow_cap_skin=False):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    stock.require(data.get('schemaVersion') == 1 and data.get('reviewed') is True,
                  'Require explicit reviewed semantic labels schema1')
    stock.require(data.get('policy') == 'explicit-reviewed-semantic', 'Automatic clothing classifier prohibited')
    for key, origin in [('sourceSha256', source), ('colorSha256', color), ('normalSha256', normal)]:
        stock.require(data.get(key) == stock.sha(origin), 'Semantic labels not bound to selected ' + key)
    stock.require(data.get('orderedCornerSha256') == corner_hash(p, uv, n), 'Semantic face/corner order changed')
    labels = data.get('labels')
    stock.require(isinstance(labels, list) and data.get('faceCount') == len(p) == len(labels),
                  'Require one semantic label per ordered source triangle')
    if allow_cap_skin:
        stock.require({'briefs', 'capSkin'} <= set(labels) <= {'skin', 'briefs', 'capSkin'}, 'Require explicit capSkin/briefs; unresolved labels rejected')
    else:
        stock.require(set(labels) == {'skin', 'briefs'}, 'Require nonempty skin/briefs groups; unresolved labels rejected')
    mask = data.get('mask', {})
    stock.require(mask.get('uvSpace') == 'gltf-top-left', 'Semantic mask orientation must be explicit')
    mask_path = verify_file(mask['path'], mask['sha256'], 'Reviewed semantic mask')
    with Image.open(mask_path) as image:
        stock.require(image.mode == 'L' and image.size == (2048, 2048), 'Semantic mask must be 2K single-channel')
        values = set(np.unique(np.asarray(image)).tolist())
    stock.require(values <= {0, 128, 255} and {0, 255} <= values,
                  'Mask values: skin0, unresolved/background128, briefs255')
    evidence = data.get('reviewEvidence', [])
    stock.require(isinstance(evidence, list) and len(evidence) > 0, 'Require concrete semantic boundary review evidence')
    inputs = {str(mask_path): stock.sha(mask_path)}
    for row in evidence:
        item = verify_file(row['path'], row['sha256'], 'Semantic review evidence')
        inputs[str(item)] = stock.sha(item)
    mixed = data.get('reviewedBoundaryFaceIds', [])
    stock.require(isinstance(mixed, list) and all(type(i) is int and 0 <= i < len(p) for i in mixed)
                  and len(set(mixed)) == len(mixed), 'Invalid reviewed semantic boundary face IDs')
    return np.asarray(labels), data, inputs


def write_semantic_ascii(path, p, uv, n, labels):
    """Use stable one-mesh serializer, then verify the actual two-node union."""
    stock.require(len(p) == len(uv) == len(n) == len(labels), 'Corner/label length mismatch')
    stock.require('briefs' in labels and np.isin(labels, ['skin', 'capSkin']).any()
        and set(labels.tolist()) <= {'skin', 'briefs', 'capSkin'}, 'Require palette skin/capSkin plus fixed briefs only')
    proof = {}; blocks = []; reconstructed = [np.empty_like(p), np.empty_like(uv), np.empty_like(n)]
    with tempfile.TemporaryDirectory(prefix='pelvis-ascii-proof-', dir=path.parent) as temporary:
        for semantic, suffix, material in [('skin', 'p', MODEL), ('briefs', 'f', MODEL + 'f')]:
            ids = np.flatnonzero(np.isin(labels, ['skin', 'capSkin']) if semantic == 'skin' else labels == semantic)
            fragment = Path(temporary) / (semantic + '.mdl')
            counts = stock.write_ascii(fragment, MODEL, p[ids], uv[ids], n[ids])
            body = re.search(r'(?ms)^node trimesh \S+\n(.*?)^endnode', fragment.read_text())[1]
            body = body.replace('  bitmap ' + MODEL + '\n', '  bitmap ' + material + '\n')
            body = body.replace('  materialname ' + MODEL + '\n', '  materialname ' + material + '\n')
            blocks.append('node trimesh ' + MODEL + suffix + '\n' + body + 'endnode')
            proof[semantic] = {**counts, 'sourceFaceIds': ids.tolist(), 'bitmap': material, 'materialname': material}
            if semantic == 'skin': proof[semantic]['semanticCounts'] = {name: int((labels[ids] == name).sum()) for name in ['skin', 'capSkin']}
    text = '\n'.join([f'newmodel {MODEL}', f'setsupermodel {MODEL} NULL', 'classification CHARACTER',
        'setanimationscale 1', f'beginmodelgeom {MODEL}', f'node dummy {MODEL}', '  parent NULL',
        'endnode', *blocks, f'endmodelgeom {MODEL}', f'donemodel {MODEL}']) + '\n'
    path.write_text(text, encoding='ascii')
    actual_nodes = re.findall(r'(?ms)^node trimesh (\S+)\n(.*?)^endnode', path.read_text())
    stock.require([name for name, body in actual_nodes] == [MODEL + 'p', MODEL + 'f'], 'Unexpected native material nodes')
    for (name, body), semantic in zip(actual_nodes, ['skin', 'briefs']):
        ids = np.asarray(proof[semantic]['sourceFaceIds'])
        vp = np.asarray(stock.arrays(body, 'verts')); vn = np.asarray(stock.arrays(body, 'normals'))
        vu = np.asarray(stock.arrays(body, 'tverts'))[:, :2]; faces = np.asarray(stock.arrays(body, 'faces'), dtype=int)
        reconstructed[0][ids] = vp[faces[:, :3]]
        reconstructed[1][ids] = vu[faces[:, 4:7]]
        reconstructed[2][ids] = vn[faces[:, :3]]
        for attribute, expected in [('parent', MODEL), ('bitmap', proof[semantic]['bitmap']),
                                    ('materialname', proof[semantic]['materialname'])]:
            stock.require(re.findall(r'(?m)^  ' + attribute + r' (\S+)$', body) == [expected],
                          'Unexpected semantic node binding: ' + attribute)
    errors = {key: float(np.max(np.abs(actual - expected))) for key, actual, expected in
              zip(['position', 'uv', 'normal'], reconstructed, [p, uv, n])}
    stock.require(all(error == 0 for error in errors.values()), 'Two-node source corner union differs')
    proof['union'] = {'triangles': len(p), 'everySourceFaceExactlyOnce': True,
        'orderedCornerSha256': corner_hash(*reconstructed), 'actualAsciiCornerMaximumErrors': errors}
    return proof


def verify_bank(config):
    inventory_path = verify_file(config['inputInventory'], config['inputInventorySha256'], 'Stock input inventory')
    inventory = json.loads(inventory_path.read_text()); bank = inventory_path.parent
    stock.require(inventory.get('customBodyAssetsCopied') is False, 'Input bank must exclude custom body assets')
    inputs = {str(inventory_path): stock.sha(inventory_path)}; allowed = {inventory_path}
    for relative, row in inventory['files'].items():
        path = (bank / relative).resolve()
        stock.require(path.is_relative_to(bank), 'Input inventory escapes bank')
        verify_file(path, row['sha256'], 'Stock/fixture input')
        inputs[str(path)] = row['sha256']; allowed.add(path)
    stock.require({p.resolve() for p in bank.rglob('*') if p.is_file()} == allowed, 'Undeclared input bank artifact')
    stock.require(Path(config['stockBaseline']).resolve() == bank / 'stock'
        and Path(config['fixtureBaseline']).resolve() == bank / 'fixture', 'Stock/fixture bank mismatch')
    return bank / 'stock', bank / 'fixture', inputs


def verify_torso(config):
    frozen = config['frozenTorso']; converted = Path(frozen['convertedDirectory']).resolve()
    stock.require(set(frozen['resourceHashes']) == CHEST_RESOURCES, 'Frozen torso import must enumerate exactly four chest resources')
    inputs = {}
    ascii_path = verify_file(converted / 'ascii' / (CHEST + '.mdl'), frozen['asciiSha256'], 'Frozen chest ASCII')
    inputs[str(ascii_path)] = frozen['asciiSha256']
    for name, digest in frozen['resourceHashes'].items():
        path = verify_file(converted / 'resources' / name, digest, 'Frozen chest resource')
        inputs[str(path)] = digest
    receipt_path = verify_file(converted / 'native-compile.json', frozen['nativeReceiptSha256'], 'Frozen chest compiler receipt')
    inputs[str(receipt_path)] = frozen['nativeReceiptSha256']
    receipt = json.loads(receipt_path.read_text())
    stock.require(receipt.get('complete') is True and receipt.get('clientSha256') == frozen['clientSha256'],
                  'Incomplete/wrong-client frozen chest receipt')
    stock.require(len(receipt.get('models', [])) == 1, 'Require independent chest-only native receipt')
    model = receipt['models'][0]
    stock.require(model.get('name') == CHEST + '.mdl' and model.get('sourceSha256') == frozen['asciiSha256']
        and model.get('binarySha256') == frozen['resourceHashes'][CHEST + '.mdl'], 'Frozen chest native source/binary mismatch')
    dependencies = {name: digest for name, digest in frozen['resourceHashes'].items() if name != CHEST + '.mdl'}
    stock.require(receipt.get('materialResourceHashes') == dependencies, 'Frozen chest compiler dependency mismatch')
    stock.require((converted / 'resources' / (CHEST + '.mdl')).read_bytes()[:4] == b'\0\0\0\0',
                  'Frozen chest is not native compiled binary')
    return converted, receipt, inputs


def stage(config_path, output):
    config_path = Path(config_path).resolve(); config = json.loads(config_path.read_text())
    stock.require(config.get('schemaVersion') == 1 and config.get('diagnosticOnly') is True, 'Require explicit diagnostic schema1')
    stock.require(config.get('model') == MODEL and config.get('part') == 'pelvis' and config.get('joint') == 'pelvis_g'
        and config.get('prefix') == 'pmh0' and config.get('gender') == 'male' and config.get('raceId') == 6,
        'Adapter supports actual Human male pelvis only')
    stock.require(config.get('normalStrength') == 1 and config.get('skinLayer') == 0
        and config.get('equipmentMode') == 'stock-identity', 'Require unchanged normals/layer0/identity equipment')
    stock.require(config.get('stockHeightMeters') == 1.9339157, 'Human stock height changed')
    slug = config['slug']; stock.require(re.fullmatch(r'[a-z0-9_]+', slug), 'Invalid slug')
    baseline, fixture, inputs = verify_bank(config)
    torso, native_torso, torso_inputs = verify_torso(config); inputs.update(torso_inputs)
    selected = {}
    for key in ['source', 'color', 'normal', 'semanticLabels']:
        path = verify_file(config[key], config['expectedInputHashes'][key], 'Selected ' + key)
        selected[key] = path; inputs[str(path)] = config['expectedInputHashes'][key]
    for path in [config_path, Path(__file__).resolve(), Path(stock.__file__).resolve()]:
        inputs[str(path)] = stock.sha(path)
    similarity_proof = None; conditioned_proof = None; cap_faces = None
    stock.require(not (config.get('similarityFit') and config.get('conditionedFit')), 'Choose unchanged similarity or localized conditioned descendant, not both')
    stock.require(not config.get('postFitSimilarity') or config.get('conditionedFit'), 'Post-fit requires original conditioned-fit association')
    if config.get('conditionedFit'):
        p, uv, n, primitives, fit_inputs, conditioned_proof, cap_faces = conditioned_corners(config, selected, baseline)
        inputs.update(fit_inputs)
    elif config.get('similarityFit'):
        p, uv, n, primitives, fit_inputs, similarity_proof = similarity_corners(config, selected, baseline)
        inputs.update(fit_inputs)
    else:
        p, uv, n, primitives = stock.raw_triangles(selected['source'], selected['color'], selected['normal'])
    stock.require(p.shape[0] > 0 and np.isfinite(p).all() and np.isfinite(n).all() and np.isfinite(uv).all()
        and np.min(np.linalg.norm(n, axis=2)) > .5, 'Invalid authored source corner attributes')
    labels, semantic, label_inputs = read_labels(selected['semanticLabels'], selected['source'], selected['color'], selected['normal'], p, uv, n,
        allow_cap_skin=conditioned_proof is not None)
    if similarity_proof:
        stock.require(semantic.get('originalSourceSha256') == similarity_proof['originalSourceSha256']
            and semantic.get('placementReceiptSha256') == similarity_proof['receiptSha256'], 'Semantic labels not bound to original source/placement receipt')
    if conditioned_proof:
        stock.require(semantic.get('originalSourceSha256') == conditioned_proof['originalSourceSha256']
            and semantic.get('placementReceiptSha256') == conditioned_proof['firstSimilarityReceiptSha256']
            and semantic.get('materialReceiptSha256') == conditioned_proof['materialReceiptSha256'], 'Conditioned semantic receipt association differs')
        stock.require(np.array_equal(labels == 'capSkin', cap_faces), 'ALL new caps and only new caps must be explicitly capSkin')
        if conditioned_proof.get('postFitSimilarity'):
            stock.require(semantic.get('postFitReceiptSha256') == conditioned_proof['postFitSimilarity']['receiptSha256'],
                'Semantic labels not rebound to final post-fit frame')
    inputs.update(label_inputs); geom = stock.geometry(p)
    stock.require(not geom['degenerateTriangles'] and not geom['coincidentTriangles'], 'Invalid pelvis geometry cannot be staged')
    root = Path(output).resolve(); root.mkdir(exist_ok=False)
    converted = root / slug / 'converted'; ascii_dir = converted / 'ascii'; resources = converted / 'resources'
    ascii_dir.mkdir(parents=True); resources.mkdir()
    proof = write_semantic_ascii(ascii_dir / (MODEL + '.mdl'), p, uv, n, labels)
    shutil.copyfile(torso / 'ascii' / (CHEST + '.mdl'), ascii_dir / (CHEST + '.mdl'))
    for name in CHEST_RESOURCES: shutil.copyfile(torso / 'resources' / name, resources / name)
    preserved = root / 'preserved-torso'; preserved.mkdir()
    shutil.copyfile(torso / 'native-compile.json', preserved / 'native-compile.json')
    stock.save(preserved / 'import.json', {'configuration': config['frozenTorso'], 'receiptCopiedExactly': True,
        'nativeReceiptSha256': stock.sha(torso / 'native-compile.json'), 'nativeCompiledHere': False})
    rgb = np.asarray(Image.open(selected['color']).convert('RGB'))
    intensity = np.clip(rgb.astype(float) @ [.2126, .7152, .0722], 0, 255).astype(np.uint8)
    pixels = np.stack([intensity, np.zeros_like(intensity)], axis=2)[::-1].copy()
    (resources / (MODEL + '.plt')).write_bytes(b'PLT V1  ' + struct.pack('<IIII', 10, 0, 2048, 2048) + pixels.tobytes())
    Image.open(selected['normal']).convert('RGB').save(resources / (MODEL + 'n.tga'))
    Image.open(selected['color']).convert('RGB').save(resources / (MODEL + 'f.tga'))
    common = 'renderhint NormalTangents\n'
    parameters = 'parameter float Roughness 0.72\nparameter float Specularity 0.04\nparameter float Metallicness 0.001\n'
    (resources / (MODEL + '.mtr')).write_text(common + 'texture1 ' + MODEL + 'n\n' + parameters, encoding='ascii')
    (resources / (MODEL + 'f.mtr')).write_text(common + 'texture0 ' + MODEL + 'f\ntexture1 ' + MODEL + 'n\n' + parameters, encoding='ascii')
    decoded = np.frombuffer((resources / (MODEL + '.plt')).read_bytes()[24:], dtype=np.uint8).reshape(2048, 2048, 2)[::-1]
    stock.require(np.array_equal(decoded[:, :, 0], intensity) and not decoded[:, :, 1].any(), 'Skin palette proof failed')
    for name, expected in [(MODEL + 'f.tga', rgb), (MODEL + 'n.tga', np.asarray(Image.open(selected['normal']).convert('RGB')))]:
        stock.require(np.array_equal(np.asarray(Image.open(resources / name).convert('RGB')), expected), 'Texture RGB conversion changed selected pixels')
    sources = root / 'selected-source'; sources.mkdir()
    for key, path in selected.items(): shutil.copyfile(path, sources / (key + path.suffix))
    shutil.copyfile(Path(__file__), root / 'executed-stage-stock-pelvis.py')
    shutil.copyfile(Path(stock.__file__), root / 'imported-stage-stock-part.py')
    for name in ['human-template.json', 'ttr01.set', 'ttr01_edge.2da']:
        target = root / 'baseline' / name; target.parent.mkdir(exist_ok=True)
        shutil.copyfile(fixture / name, target)
    stock.save(root / 'manifest.json', {'combinations': [{'slug': slug, 'appearance': config.get('appearance', 6),
        'raceId': 6, 'gender': 'male', 'phenotype': 0, 'height': config['stockHeightMeters'], 'race': 'Human', 'body_type': 'Fit'}]})
    conversion = {'modelPrefix': 'pmh0', 'height': config['stockHeightMeters'], 'stockReferenceHeight': config['stockHeightMeters'],
        'parts': [{'part': 'chest', 'model': CHEST, 'preservedNativeBinary': True}, {'part': 'pelvis', 'model': MODEL, 'counts': proof}],
        'textures': {}, 'geometryStatus': 'single-stock-part-diagnostic', 'declaredStockReplacementParts': ['chest', 'pelvis'],
        'rigMode': 'stock-exact-game-fallback', 'stockOtherPartsFromGame': True, 'diagnosticOnly': True, 'clientAccepted': False,
        'ownedResourceHashes': {name: stock.sha(resources / name) for name in sorted(CHEST_RESOURCES | PELVIS_MATERIALS)},
        'preservedNativeReceipt': str(preserved / 'native-compile.json'), 'pelvisNativeCompiled': False}
    stock.save(converted / 'conversion.json', conversion)
    if config.get('stageHumanStockComparator'):
        helper = Path(__file__).with_name('stock_body_control.py'); inputs[str(helper)] = stock.sha(helper)
        subprocess.run([sys.executable, str(helper), '--output', str(root), '--baseline', str(baseline)], check=True)
    stock.require({path.name for path in ascii_dir.iterdir()} == {CHEST + '.mdl', MODEL + '.mdl'}, 'Undeclared ASCII override')
    stock.require({path.name for path in resources.iterdir()} == CHEST_RESOURCES | PELVIS_MATERIALS, 'Undeclared resource staged')
    for name, expected in config['frozenTorso']['resourceHashes'].items():
        stock.require(stock.sha(resources / name) == expected, 'Frozen chest resource changed during stage')
    stock.require(stock.sha(ascii_dir / (CHEST + '.mdl')) == config['frozenTorso']['asciiSha256']
        and stock.sha(preserved / 'native-compile.json') == config['frozenTorso']['nativeReceiptSha256'], 'Frozen chest ASCII/receipt copy changed')
    for path, expected in inputs.items(): verify_file(path, expected, 'Frozen input')
    world = stock.transforms(stock.nodes((baseline / 'ascii/pmh0.mdl').read_text(encoding='cp1252')))
    receipt = {'configuration': config, 'frozenInputs': inputs,
        'rawAttributeAsciiProof': proof, 'primitiveAtlasProofs': primitives, 'geometry': geom,
        'declaredSimilarityProof': similarity_proof,
        'conditionedFitProof': conditioned_proof,
        'semanticOwnership': {'policy': semantic['policy'], 'labelArtifactSha256': stock.sha(selected['semanticLabels']),
            'skinFaces': int((labels == 'skin').sum()), 'briefsFaces': int((labels == 'briefs').sum()),
            'capSkinFaces': int((labels == 'capSkin').sum()),
            'maskSha256': semantic['mask']['sha256'], 'reviewedBoundaryFaceIds': semantic.get('reviewedBoundaryFaceIds', [])},
        'paletteProof': {'width': 2048, 'height': 2048, 'allLayer0Skin': True, 'intensityPixelsExact': True},
        'fixedBriefsPixelsExact': True, 'normalTgaPixelsExact': True, 'pltDiffuseOverride': False,
        'authoredNormalLengthRange': [float(np.min(np.linalg.norm(n, axis=2))), float(np.max(np.linalg.norm(n, axis=2)))],
        'frozenTorsoBytesExact': True, 'frozenTorsoNativeReceiptPreserved': True,
        'stockAttachmentWorld': world['pelvis_g'].tolist(), 'stockControllersModified': False,
        'stockOtherPartsFromGame': True, 'equipmentMode': 'stock-identity', 'normalStrength': 1,
        'nativeCompiled': False, 'pelvisNativeCompiled': False, 'packageBuilt': False,
        'clientLaunched': False, 'clientAccepted': False, 'diagnosticOnly': True, 'productionGeometryGatePassed': False,
        'stagedFiles': {str(path.relative_to(root)): stock.sha(path) for path in sorted(root.rglob('*')) if path.is_file()}}
    stock.save(root / 'stock-pelvis-stage.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path); parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); receipt = stage(args.config, args.output)
    print(json.dumps({'output': str(args.output.resolve()), 'faces': receipt['geometry']['triangles'],
                      'frozenTorsoBytesExact': True, 'nativeCompiled': False, 'clientLaunched': False}, indent=2))


if __name__ == '__main__': main()
