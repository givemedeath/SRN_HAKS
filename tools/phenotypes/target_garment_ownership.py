"""Propose and apply reviewed chest/pelvis skin/cloth face ownership.

Proposal masks are diagnostic data, never approval. Application requires a
separate target/source/proposal-bound review receipt and complete face roles.
Mixed, unknown, degenerate or wrapping UV footprints block application. This
helper cannot subdivide geometry or waive a crossing garment boundary.

An accepted split duplicates material JSON and adds index-accessor slices only.
The complete original BIN, attribute accessors, texture bindings and map bytes
remain exact; a native-corner archive preserves the fitted-parent precision.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

import target_contract as contract
from place_purposebuilt_pelvis import accessor, embedded_maps, raw_corners, read_glb, write_glb
from target_part_pipeline import pin, read_target, verify_source_receipt
from target_part_stage import image_pixels, material_inputs

CODES = {'skin': 0, 'unknown': 127, 'garment': 255}


def digest_bytes(value):
    return hashlib.sha256(value).hexdigest()


def context(config_path, kind):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    contract.require(config.get('kind') == kind and config.get('diagnosticOnly') is True,
                     'Explicit diagnostic garment ownership configuration required')
    common = {'schemaVersion', 'kind', 'diagnosticOnly', 'targetContract', 'targetContractSha256',
              'part', 'coordinateSpace', 'source', 'sourceSha256', 'sourceReceipt',
              'sourceReceiptSha256', 'protectedInputs', 'notes'}
    specific = {'target-garment-mask-proposal': {'ownershipMask', 'diagnosticColorRule', 'filterRadiusPixels'},
                'target-garment-mask-apply': {'proposalReceipt', 'proposalReceiptSha256',
                                            'selectionReceipt', 'selectionReceiptSha256', 'maxOutputPrimitives'}}
    contract.require(set(config) <= common | specific[kind], 'Unknown garment ownership controls')
    target_path, target = read_target(config)
    part, space = config['part'], config['coordinateSpace']
    contract.require(part in {'chest', 'pelvis'} and part in contract.fixed_garment_parts(target),
                     'Garment ownership requires a declared chest/pelvis owner')
    contract.require(space in ('working', 'runtime'), 'Explicit garment coordinate space required')
    source = pin(config['source'], config['sourceSha256'])
    receipt_path = pin(config['sourceReceipt'], config['sourceReceiptSha256'])
    parent = verify_source_receipt(source, receipt_path, target_path, target, part, space)
    frozen = {str(path): contract.sha(path) for path in (config_path, target_path, source, receipt_path)}
    for name, expected in config.get('protectedInputs', {}).items():
        path = pin(name, expected); frozen[str(path)] = expected
    doc, binary = read_glb(source)
    contract.require(doc['nodes'] == [{'name': 'detached_geometry', 'mesh': 0}] and len(doc['meshes']) == 1,
                     'Canonical detached identity-node candidate required')
    positions, normals, uv, primitives = raw_corners(doc, binary)
    active = {row['material'] for row in primitives}
    contract.require(all(type(value) is int for value in active), 'Explicit source material references required')
    for value in active:
        contract.require(not doc['materials'][value].get('extensions'), 'Material extensions require an explicit adapter')
    # Verifies opaque, 2K, identity color factor, authored normal strength and ORM transport.
    material_inputs(doc, binary, {value: 'skin' for value in active}, part, 0, {part})
    return config_path, config, target_path, target, source, receipt_path, parent, frozen, doc, binary, positions, normals, uv


def mask_pixels(path):
    image = Image.open(path)
    contract.require(image.size == (2048, 2048) and image.mode in ('L', 'RGB'), 'Explicit 2K categorical ownership mask required')
    data = np.asarray(image)
    if data.ndim == 3:
        contract.require(np.array_equal(data[:, :, 0], data[:, :, 1]) and np.array_equal(data[:, :, 0], data[:, :, 2]),
                         'Ownership mask RGB channels must agree')
        data = data[:, :, 0]
    contract.require(set(np.unique(data).tolist()) <= set(CODES.values()), 'Ownership mask requires 0 skin, 127 unknown or 255 garment')
    return data


def measure_uv_faces(uv, mask, filter_radius):
    """Conservative triangle/pixel-square support, expanded for bilinear filtering.

    The three oriented half-planes plus expanded axis bounds describe the
    triangle Minkowski-summed with a square. Thus partial pixel coverage is
    included; triangle-center sampling cannot hide a crossing garment edge.
    """
    contract.require(type(filter_radius) in (int, float) and filter_radius == 1,
                     'Reviewed bilinear footprint radius must be one pixel')
    uv = np.asarray(uv, dtype=float)
    contract.require(uv.ndim == 3 and uv.shape[1:] == (3, 2) and np.isfinite(uv).all(), 'Finite triangle UVs required')
    height, width = mask.shape
    roles, counts, issues = [], [], []
    radius = .5 + filter_radius
    for index, triangle in enumerate(uv):
        values = np.zeros(3, dtype=np.int64)
        reason = None
        if triangle.min() < 0 or triangle.max() > 1:
            reason = 'wrapping-or-clipped-uv'
        else:
            points = triangle * [width, height] - .5
            edges = np.roll(points, -1, axis=0) - points
            diagonal = points[2] - points[0]
            signed = edges[0, 0]*diagonal[1] - edges[0, 1]*diagonal[0]
            if abs(float(signed)) < 1e-12:
                reason = 'degenerate-uv'
            else:
                low = np.maximum(np.ceil(points.min(0) - radius).astype(int), [0, 0])
                high = np.minimum(np.floor(points.max(0) + radius).astype(int), [width-1, height-1])
                y, x = np.mgrid[low[1]:high[1]+1, low[0]:high[0]+1]
                sample = np.stack((x, y), axis=-1)
                covered = np.ones(x.shape, dtype=bool)
                sign = 1 if signed > 0 else -1
                for origin, edge in zip(points, edges):
                    delta = sample - origin
                    inside = sign * (edge[0]*delta[:, :, 1] - edge[1]*delta[:, :, 0])
                    covered &= inside >= -radius*(abs(edge[0])+abs(edge[1]))-1e-10
                sampled = mask[low[1]:high[1]+1, low[0]:high[0]+1][covered]
                values = np.asarray([np.count_nonzero(sampled == value) for value in (0, 127, 255)], dtype=np.int64)
                if not len(sampled): reason = 'empty-uv-footprint'
                elif values[1]: reason = 'unknown-mask-texels'
                elif values[0] and values[2]: reason = 'mixed-skin-garment-footprint'
        role = 'unknown' if reason else ('garment' if values[2] else 'skin')
        roles.append(role); counts.append(values)
        if reason: issues.append({'sourceFace': index, 'reason': reason, 'pixelCounts': values.tolist()})
    return roles, np.asarray(counts), issues


def boundary_metrics(positions, roles):
    edges = {}
    for face, triangle in enumerate(positions):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((tuple(triangle[a].tolist()), tuple(triangle[b].tolist()))))
            edges.setdefault(key, []).append((face, roles[face]))
    boundary = [np.asarray(edge) for edge, rows in edges.items() if {'skin', 'garment'} <= {role for _, role in rows}]
    lengths = [float(np.linalg.norm(edge[1]-edge[0])) for edge in boundary]
    return {'crossRoleEdges': len(boundary), 'totalBoundaryLengthMeters': sum(lengths),
            'maximumBoundaryEdgeMeters': max(lengths, default=0),
            'nonmanifoldEdgeCount': sum(len(rows)>2 for rows in edges.values()),
            'method': 'Read-only exact-position edge association; no coordinate weld is written.',
            'limits': 'Does not approve garment cut, palette filtering or client appearance.'}, np.asarray(boundary).reshape(-1, 2, 3)


def proposal(config_path, output):
    values = context(config_path, 'target-garment-mask-proposal')
    config_path, config, target_path, target, source, receipt_path, parent, frozen, doc, binary, p, n, uv = values
    contract.require(('ownershipMask' in config) != ('diagnosticColorRule' in config), 'Use one explicit mask or one diagnostic color rule')
    radius = config.get('filterRadiusPixels', 1)
    if 'ownershipMask' in config:
        source_mask = pin(config['ownershipMask']['path'], config['ownershipMask']['sha256'])
        mask = mask_pixels(source_mask); frozen[str(source_mask)] = contract.sha(source_mask)
        method = 'Explicit source ownership mask; pending independent review'
    else:
        rule = config['diagnosticColorRule']
        contract.require(set(rule) == {'garmentMaxChannel', 'skinMinChannel'} and
                         all(type(rule[key]) is int for key in rule) and
                         0 <= rule['garmentMaxChannel'] < rule['skinMinChannel'] <= 255, 'Bounded diagnostic color thresholds required')
        active = {row.get('material') for row in doc['meshes'][0]['primitives']}
        material = doc['materials'][next(iter(active))]
        color = image_pixels(doc, binary, material['pbrMetallicRoughness']['baseColorTexture'])
        intensity = color.max(axis=2)
        mask = np.full(intensity.shape, 127, dtype=np.uint8)
        mask[intensity <= rule['garmentMaxChannel']] = 255; mask[intensity >= rule['skinMinChannel']] = 0
        method = 'Unapproved maximum-RGB threshold diagnostic; painted shadows can be false garment detections'
    roles, counts, issues = measure_uv_faces(uv, mask, radius)
    metrics, edges = boundary_metrics(p, roles)
    output = Path(output).resolve(); contract.require(not output.exists(), 'Fresh immutable ownership proposal required')
    output.mkdir(parents=True)
    mask_path = output / 'ownership-mask.png'
    if 'ownershipMask' in config: shutil.copyfile(source_mask, mask_path)
    else: Image.fromarray(mask).save(mask_path)
    archive = output / 'face-footprints.npz'
    np.savez_compressed(archive, sourceTriangleIds=np.arange(len(p)), pixelCounts=counts,
                        roleCodes=np.asarray([CODES[role] for role in roles], dtype=np.uint8), boundaryEdges=edges)
    snapshots = {}
    directory = output / 'helper-snapshots'; directory.mkdir()
    for name in ('target_garment_ownership.py', 'target_contract.py', 'target_part_pipeline.py', 'target_part_stage.py', 'place_purposebuilt_pelvis.py'):
        original = Path(__file__).with_name(name).resolve(); copied = directory / name; shutil.copyfile(original, copied)
        frozen[str(copied)] = contract.sha(copied); snapshots[str(original)] = {'snapshot': str(copied), 'sha256': contract.sha(copied)}
    record = {'schemaVersion': 2, 'kind': 'target-garment-mask-proposal', **contract.binding(target_path, target, config['coordinateSpace']),
        'part': config['part'], 'model': contract.model(target, config['part']), 'source': str(source), 'sourceSha256': contract.sha(source),
        'sourceReceipt': str(receipt_path), 'sourceReceiptSha256': contract.sha(receipt_path),
        'ownershipMask': {'path': str(mask_path), 'sha256': contract.sha(mask_path), 'pixelSha256': digest_bytes(mask.tobytes())},
        'maskConvention': 'gltf-UV v0 corresponds to decoded image row0; 0=skin, 127=unknown, 255=garment',
        'maskMethod': method, 'filterRadiusPixels': radius, 'sourceFaces': len(p), 'faceRoles': roles,
        'mixedOrUnknownFaces': issues, 'boundaryMetrics': metrics, 'footprintArchive': {'path': str(archive), 'sha256': contract.sha(archive)},
        'sourceEmbeddedMaps': embedded_maps(doc, binary), 'readyForIndependentReview': not issues and set(roles) == {'skin', 'garment'},
        'decision': 'unreviewed', 'diagnosticOnly': True, 'accepted': False, 'productionAccepted': False, 'clientAccepted': False,
        'sourceChanged': False, 'frozenInputs': frozen, 'helperSnapshots': snapshots,
        'limits': ['Proposal never grants approval; a separate explicit review receipt is required.',
                   'Mixed, unknown, degenerate and wrapping footprints block assignment; subdivision requires a separately reviewed geometry descendant.']}
    path = output / 'proposal.json'; path.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    template = {key: record[key] for key in ('targetContract', 'targetContractSha256', 'targetId', 'rigRevision',
        'coordinateSpace', 'part', 'model', 'source', 'sourceSha256', 'sourceReceipt', 'sourceReceiptSha256', 'ownershipMask')}
    template.update(schemaVersion=2, kind='target-garment-mask-review', accepted=False, decision='pending',
        reviewer=None, notes=None, proposalReceipt={'path': str(path), 'sha256': contract.sha(path)},
        faceRoles=roles, reviewedViews=[], reviewEvidence=[])
    (output / 'pending-review-template.json').write_text(json.dumps(template, indent=2)+'\n', encoding='utf-8')
    return path


def partition(doc, binary, roles, maximum_primitives):
    """Keep global triangle order and every BIN byte using index-accessor slices."""
    contract.require(type(maximum_primitives) is int and 1 <= maximum_primitives <= 100000, 'Explicit bounded primitive budget required')
    result = copy.deepcopy(doc); original = doc['meshes'][0]['primitives']
    result['meshes'][0]['primitives'] = []; material_roles = {}; aliases = {}; offset = 0; output_ids = []
    for primitive in original:
        item = doc['accessors'][primitive['indices']]
        contract.require(item['type'] == 'SCALAR' and item['componentType'] in (5121, 5123, 5125) and not item.get('normalized'), 'Unsigned scalar triangle indices required')
        indices = accessor(doc, binary, primitive['indices']).reshape(-1)
        contract.require(len(indices)%3 == 0, 'Complete indexed source triangles required')
        count = len(indices)//3; labels = roles[offset:offset+count]
        contract.require(len(labels) == count and set(labels) <= {'skin', 'garment'}, 'Complete explicit face ownership required')
        view = doc['bufferViews'][item['bufferView']]
        size = {5121: 1, 5123: 2, 5125: 4}[item['componentType']]
        stride = view.get('byteStride', size); start = 0
        while start < count:
            end = start+1
            while end < count and labels[end] == labels[start]: end += 1
            role = labels[start]; owner = (primitive['material'], role)
            if owner not in aliases:
                aliases[owner] = len(result['materials']); result['materials'].append(copy.deepcopy(doc['materials'][owner[0]]))
                material_roles[str(aliases[owner])] = role
            sliced = copy.deepcopy(item); sliced['byteOffset'] = item.get('byteOffset', 0) + start*3*stride
            sliced['count'] = (end-start)*3; sliced.pop('min', None); sliced.pop('max', None)
            result['accessors'].append(sliced)
            copied = copy.deepcopy(primitive); copied['indices'] = len(result['accessors'])-1; copied['material'] = aliases[owner]
            output_ids.extend([len(result['meshes'][0]['primitives'])]*(end-start))
            result['meshes'][0]['primitives'].append(copied); start = end
        offset += count
    contract.require(offset == len(roles) and len(result['meshes'][0]['primitives']) <= maximum_primitives,
                     'Face ownership coverage or primitive budget differs')
    before = raw_corners(doc, binary, extra={}); after = raw_corners(result, binary, extra={})
    contract.require(all(np.array_equal(a, b) for a, b in zip(before[:3], after[:3])), 'Serialized attribute or triangle order changed')
    return result, material_roles, np.asarray(output_ids, dtype=np.int64)


def apply(config_path, output):
    values = context(config_path, 'target-garment-mask-apply')
    config_path, config, target_path, target, source, receipt_path, parent, frozen, doc, binary, p, n, uv = values
    proposal_path = pin(config['proposalReceipt'], config['proposalReceiptSha256'])
    selection_path = pin(config['selectionReceipt'], config['selectionReceiptSha256'])
    proposed, reviewed = (json.loads(path.read_text(encoding='utf-8')) for path in (proposal_path, selection_path))
    contract.require(proposed.get('schemaVersion') == 2 and proposed.get('kind') == 'target-garment-mask-proposal'
                     and proposed.get('decision') == 'unreviewed' and proposed.get('accepted') is False,
                     'Original unapproved ownership proposal required')
    contract.require(reviewed.get('schemaVersion') == 2 and reviewed.get('kind') == 'target-garment-mask-review'
                     and reviewed.get('accepted') is True and reviewed.get('decision') == 'approved-face-ownership'
                     and reviewed.get('reviewer') and reviewed.get('notes'), 'Explicit independent reviewed face selection required')
    for record in (proposed, reviewed):
        contract.verify_binding(record, target_path, target, config['coordinateSpace'])
        contract.require(record['part'] == config['part'] and record['model'] == contract.model(target, config['part'])
                         and Path(record['source']).resolve() == source and record['sourceSha256'] == contract.sha(source)
                         and Path(record['sourceReceipt']).resolve() == receipt_path
                         and record['sourceReceiptSha256'] == contract.sha(receipt_path), 'Selection target/source ownership differs')
    contract.require(reviewed.get('proposalReceipt') == {'path': str(proposal_path), 'sha256': contract.sha(proposal_path)}
                     and reviewed.get('ownershipMask') == proposed['ownershipMask'], 'Review must bind the exact proposal and mask')
    contract.require(reviewed.get('reviewEvidence') and set(reviewed.get('reviewedViews', [])) >= {'front', 'rear', 'side', 'uv-mask'},
                     'Assembly and UV-mask review evidence required')
    for value in reviewed['reviewEvidence']:
        path = pin(value['path'], value['sha256']); frozen[str(path)] = value['sha256']
    for name, expected in proposed['frozenInputs'].items():
        frozen[str(pin(name, expected))] = expected
    mask_path = pin(proposed['ownershipMask']['path'], proposed['ownershipMask']['sha256']); mask = mask_pixels(mask_path)
    contract.require(digest_bytes(mask.tobytes()) == proposed['ownershipMask']['pixelSha256'], 'Ownership mask pixels changed')
    roles, counts, issues = measure_uv_faces(uv, mask, proposed['filterRadiusPixels'])
    measured_boundary, _ = boundary_metrics(p, roles)
    contract.require(proposed['boundaryMetrics'] == measured_boundary and proposed['sourceEmbeddedMaps'] == embedded_maps(doc, binary),
                     'Garment boundary or embedded map evidence differs')
    contract.require(not issues and set(roles) == {'skin', 'garment'}, 'Mixed or incomplete garment boundary requires a reviewed topology descendant')
    contract.require(proposed['sourceFaces'] == len(p) and proposed['faceRoles'] == roles and reviewed.get('faceRoles') == roles,
                     'Reviewed selection must completely own every source face')
    footprint = pin(proposed['footprintArchive']['path'], proposed['footprintArchive']['sha256'])
    with np.load(footprint, allow_pickle=False) as data:
        contract.require(np.array_equal(data['sourceTriangleIds'], np.arange(len(p))) and np.array_equal(data['pixelCounts'], counts),
                         'Reviewed footprint archive differs from measured source')
    result, material_roles, primitive_ids = partition(doc, binary, roles, config.get('maxOutputPrimitives', 100000))
    corner_path = pin(parent['nativeCornerArchive']['path'], parent['nativeCornerArchive']['sha256'])
    with np.load(corner_path, allow_pickle=False) as data:
        archive = {key: data[key].copy() for key in data.files}
    contract.require(archive['positions'].shape == p.shape and archive['normals'].shape == n.shape
                     and np.array_equal(archive['uvGltf'], uv), 'Authoritative fitted corner inventory differs')
    contract.require(np.max(np.abs(archive['positions']-p)) <= parent['proof']['maximumPositionFloat32ErrorMetres']+1e-12
                     and np.max(np.abs(archive['normals']-n)) <= parent['proof']['maximumNormalFloat32Error']+1e-12,
                     'Authoritative parent corner precision differs')
    archive['primitiveIds'] = primitive_ids
    frozen.update({str(path): contract.sha(path) for path in (proposal_path, selection_path, mask_path, footprint, corner_path)})
    output = Path(output).resolve(); contract.require(not output.exists(), 'Fresh immutable garment descendant required')
    output.mkdir(parents=True)
    candidate = output / 'candidate-local.glb'; write_glb(candidate, result, binary)
    reloaded, serialized = read_glb(candidate)
    contract.require(serialized == binary and reloaded['materials'][:len(doc['materials'])] == doc['materials']
                     and reloaded['images'] == doc['images'] and reloaded['textures'] == doc['textures']
                     and reloaded['bufferViews'] == doc['bufferViews'] and reloaded['buffers'] == doc['buffers']
                     and reloaded['accessors'][:len(doc['accessors'])] == doc['accessors'], 'Original BIN/material/texture data changed')
    corners = output / 'native-corners.npz'; np.savez_compressed(corners, **archive)
    snapshots = {}; directory = output / 'helper-snapshots'; directory.mkdir()
    for name in ('target_garment_ownership.py', 'target_contract.py', 'target_part_pipeline.py', 'target_part_stage.py', 'place_purposebuilt_pelvis.py'):
        original = Path(__file__).with_name(name).resolve(); copied = directory / name; shutil.copyfile(original, copied)
        frozen[str(copied)] = contract.sha(copied); snapshots[str(original)] = {'snapshot': str(copied), 'sha256': contract.sha(copied)}
    for name, expected in frozen.items(): pin(name, expected)
    record = {'schemaVersion': 2, 'kind': 'target-part-geometry', 'operation': 'material-ownership',
        **contract.binding(target_path, target, config['coordinateSpace']), 'part': config['part'], 'joint': contract.PART_JOINTS[config['part']],
        'model': contract.model(target, config['part']), 'sourcePart': parent.get('sourcePart'), 'source': str(source),
        'sourceSha256': contract.sha(source), 'sourceReceipt': str(receipt_path), 'sourceReceiptSha256': contract.sha(receipt_path),
        'candidate': str(candidate), 'candidateSha256': contract.sha(candidate), 'materialRoles': material_roles,
        'nativeCornerArchive': {'path': str(corners), 'sha256': contract.sha(corners)}, 'statureApplications': parent['statureApplications'],
        'sourceToAttachmentLocal': np.eye(4).tolist(), 'attachmentWorld': parent['attachmentWorld'],
        'parentSourceToAttachmentLocal': parent['sourceToAttachmentLocal'], 'reflectionWorld': parent.get('reflectionWorld'),
        'selectionReceipt': {'path': str(selection_path), 'sha256': contract.sha(selection_path)},
        'proposalReceipt': {'path': str(proposal_path), 'sha256': contract.sha(proposal_path)},
        'proof': {**parent['proof'], 'garmentOwnership': {'completeSourceFaces': len(roles),
            'faceRoleCounts': {role: roles.count(role) for role in ('skin', 'garment')},
            'sourceFaceOrderPreserved': True, 'sourceBINPreserved': True, 'sourceBINByteSha256': digest_bytes(binary),
            'attributeAccessorsPreserved': True, 'originalMaterialsPreserved': True, 'embeddedMapsPreserved': True,
            'sourceEmbeddedMaps': embedded_maps(doc, binary), 'clonedMaterialRoles': material_roles,
            'mixedFootprints': 0, 'subdivisionPerformed': False, 'boundaryMetrics': proposed['boundaryMetrics']}},
        'frozenInputs': frozen, 'helperSnapshots': snapshots, 'diagnosticOnly': True, 'rigMode': contract.rig_mode(target),
        'rigValidated': contract.rig_ready(target), 'rigPilotAccepted': target['rig'].get('pilotAccepted', False),
        'productionAccepted': False, 'nativeCompiled': False, 'clientAccepted': False,
        'limitation': 'Explicit reviewed face ownership only; garment cut, palette edges, native materials and client appearance remain separate checks.'}
    path = output / 'geometry.json'; path.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('propose', 'apply'), required=True)
    parser.add_argument('--config', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); path = (proposal if args.mode == 'propose' else apply)(args.config, args.output)
    print(json.dumps({'receipt': str(path), 'sha256': contract.sha(path)}))
