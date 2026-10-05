"""Four-face index-only child of the reviewed bounded Troll pelvis diagnostic.

The old BIN and all attribute accessors remain untouched, including an unused
near-zero normal. Its inactive status is explicit, not an accessor-wide pass.
Existing fully closed, stage and Human guards are neither changed nor bypassed.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np

from conservative_face_selection import topology
from place_purposebuilt_pelvis import accessor, embedded_maps, read_glb, write_glb
from stage_stock_part import geometry
from write_bounded_pelvis_diagnostic import append_accessor

ORIGINAL_PAIRS = ((45990, 45991), (48153, 48154))
DIAGNOSTIC_BODY_ROWS = (41966, 41967, 43938, 43939)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp(path):
    return {'path': str(Path(path).resolve()), 'sha256': sha(path)}


def primitives(doc, binary):
    require(not doc.get('skins') and not doc.get('animations') and len(doc['meshes']) == 1, 'Detached bounded diagnostic required')
    return [{'primitive': prim, 'attributes': {key: accessor(doc, binary, index) for key, index in prim['attributes'].items()},
             'faces': accessor(doc, binary, prim['indices']).reshape(-1, 3).astype(np.int64)}
            for prim in doc['meshes'][0]['primitives']]


def pair_equivalence(attributes, first, second):
    """Require exact opposite P/N/UV/T corner ownership, not zero area."""
    p = attributes['POSITION']; xyz = p[np.asarray([first, second])].astype(float)
    cross = np.cross(xyz[:, 1]-xyz[:, 0], xyz[:, 2]-xyz[:, 0]); lengths = np.linalg.norm(cross, axis=1)
    require(np.all(lengths > 1e-14), 'Nonzero-area reviewed opposite pair required')
    require(float(cross[0]@cross[1]/(lengths[0]*lengths[1])) < -.999999, 'Exact opposite pair winding required')
    permutation = []
    for point in xyz[0]:
        matches = np.flatnonzero(np.all(xyz[1] == point, axis=1))
        require(len(matches) == 1, 'Exact one-to-one pair positions required')
        permutation.append(int(matches[0]))
    aligned = np.asarray(second)[permutation]
    for key, rows in attributes.items():
        require(np.array_equal(rows[first], rows[aligned]), 'Opposite pair corner attribute differs: '+key)
    return {'secondCornerPermutation': permutation, 'allAuthoredCornerAttributesExact': True,
            'nonzeroArea': True, 'oppositeWinding': True, 'areaEach': (lengths/2).tolist()}


def index_child(doc, binary, keep_body_mask):
    rows = primitives(doc, binary); mask = np.asarray(keep_body_mask, bool)
    require(len(rows) == 3 and len(mask) == len(rows[0]['faces']) and np.count_nonzero(~mask) == 4, 'Only four body faces may change; both cap primitives required')
    result = copy.deepcopy(doc)
    output, index = append_accessor(result, bytes(binary), rows[0]['faces'][mask], 'indices')
    result['meshes'][0]['primitives'][0]['indices'] = index
    output += b'\0' * (-len(output) % 4); result['buffers'][0]['byteLength'] = len(output)
    return result, output


def preservation(before_doc, before_bin, after_doc, after_bin, mask):
    before, after = primitives(before_doc, before_bin), primitives(after_doc, after_bin)
    require(after_bin[:len(before_bin)] == before_bin, 'Original BIN prefix changed')
    for key in ('accessors', 'bufferViews'):
        require(after_doc[key][:len(before_doc[key])] == before_doc[key], 'Original accessor/view metadata changed')
    require(len(after_doc['accessors']) == len(before_doc['accessors'])+1 and
            len(after_doc['bufferViews']) == len(before_doc['bufferViews'])+1, 'Only one index accessor/view may append')
    for key in before_doc:
        if key not in ('accessors', 'bufferViews', 'meshes', 'buffers'):
            require(after_doc[key] == before_doc[key], 'Original metadata changed: '+key)
    body = copy.deepcopy(after[0]['primitive']); body['indices'] = before[0]['primitive']['indices']
    require(body == before[0]['primitive'], 'Body material/attribute bindings changed')
    require(np.array_equal(after[0]['faces'], before[0]['faces'][mask]), 'Retained body corner order changed')
    for key in before[0]['attributes']:
        require(np.array_equal(after[0]['attributes'][key], before[0]['attributes'][key]), 'Original body '+key+' rows changed')
    for index in (1, 2):
        require(after[index]['primitive'] == before[index]['primitive'] and
                np.array_equal(after[index]['faces'], before[index]['faces']) and
                all(np.array_equal(after[index]['attributes'][key], before[index]['attributes'][key]) for key in before[index]['attributes']),
                'Protected cap primitive/corners/attributes changed')
    require(embedded_maps(before_doc, before_bin) == embedded_maps(after_doc, after_bin), 'Embedded map changed')
    return {'allOriginalBinBytesExact': True, 'originalBinPrefixBytes': len(before_bin),
            'originalBinPrefixSha256': hashlib.sha256(before_bin).hexdigest(), 'oldAccessorsAndViewsExact': True,
            'onlyOneIndexAccessorAndViewAppended': True, 'retainedBodyCornerOrderAndAllAttributeBytesExact': True,
            'bodyMaterialBindingExact': True, 'bothCapPrimitivesAndAllCapCornerBytesExact': True,
            'allExistingMaterialsMapsTexturesSamplersAndSceneExact': True, 'embeddedMaps': embedded_maps(after_doc, after_bin)}


def merged(rows):
    p, f, offset = [], [], 0
    for row in rows:
        positions = row['attributes']['POSITION']; p.append(positions); f.append(row['faces']+offset); offset += len(positions)
    return np.concatenate(p), np.concatenate(f)


def active_inventory(rows):
    inventory = []; arrays = {}
    for i, row in enumerate(rows):
        refs = np.unique(row['faces']); stored = len(row['attributes']['POSITION'])
        normals = row['attributes']['NORMAL'].astype(float); lengths = np.linalg.norm(normals, axis=1)
        stored_bad = np.flatnonzero(lengths <= 1e-12); active_bad = np.intersect1d(refs, stored_bad)
        require(len(active_bad) == 0 and float(lengths[refs].min()) > .5, 'Referenced invalid authored normal remains')
        inventory.append({'primitive': i, 'attributeAccessors': row['primitive']['attributes'], 'indexAccessor': row['primitive']['indices'],
            'storedAttributeRows': stored, 'referencedRows': len(refs), 'unusedRows': stored-len(refs),
            'storedNearZeroNormalRows': stored_bad.tolist(), 'activeNearZeroNormalRows': active_bad.tolist(),
            'minimumActiveAuthoredNormalLength': float(lengths[refs].min()),
            'minimumStoredAuthoredNormalLength': float(lengths.min()),
            'policy': 'Only declared indexed corners are active; every unused original row is retained unchanged. This is not permission to relax an accessor-wide guard.'})
        arrays['primitive'+str(i)+'ReferencedOriginalAccessorRows'] = refs
    return inventory, arrays


def topology_compare(before_rows, after_rows):
    before, after = topology(*merged(before_rows)), topology(*merged(after_rows))
    def edge_map(t):
        return {tuple(sorted(map(tuple, e['positions']))): len(e['incidentFaces']) for e in t['nonmanifoldEdgeRecords']}
    def boundary_set(t):
        return {tuple(sorted(map(tuple, loop['positions']))) for loop in t['boundaryLoops']}
    old_edges, new_edges = edge_map(before), edge_map(after)
    require(boundary_set(before) == boundary_set(after), 'Original boundary loops changed')
    require(set(new_edges) <= set(old_edges) and len(old_edges)-len(new_edges) == 2 and
            all(new_edges[key] == old_edges[key] for key in new_edges), 'Only two reviewed duplicate hinges may resolve')
    old_links, new_links = set(map(tuple, before['nonmanifoldVertexPositions'])), set(map(tuple, after['nonmanifoldVertexPositions']))
    require(new_links <= old_links and len(old_links)-len(new_links) == 5, 'Only reviewed link defects may resolve')
    require(before['boundaryEdges'] == after['boundaryEdges'] == 12 and before['nonmanifoldEdges'] == 144 and after['nonmanifoldEdges'] == 142 and
            before['nonmanifoldVertexLinks'] == 491 and after['nonmanifoldVertexLinks'] == 486 and
            before['inconsistentManifoldEdgeWindings'] == after['inconsistentManifoldEdgeWindings'] == 0 and
            before['zeroAreaFaces'] == after['zeroAreaFaces'] == 0 and before['components'] == after['components'] == 1,
            'Exact reviewed topology transition required')
    corners = np.concatenate([r['attributes']['POSITION'][r['faces']].astype(float) for r in after_rows])
    geom = geometry(corners)
    require(geom['coincidentTriangles'] == geom['degenerateTriangles'] == 0, 'Active coincident/degenerate triangles remain')
    excluded = ('boundaryLoops', 'nonmanifoldVertexPositions', 'nonmanifoldEdgeRecords', 'boundaryIncidentFaceIds')
    return {'before': {k: v for k, v in before.items() if k not in excluded},
            'after': {k: v for k, v in after.items() if k not in excluded},
            'originalBoundaryPositionSetsExact': True, 'remainingNonmanifoldEdgePositionsAndIncidencesExact': True,
            'resolvedOnlyTwoReviewedHingeEdges': [{'positions': [list(p) for p in key], 'before': old_edges[key], 'after': 2} for key in old_edges.keys()-new_edges.keys()],
            'resolvedOnlyFiveOriginalBadVertexLinks': [list(v) for v in old_links-new_links],
            'activeGeometryGuard': geom,
            'intersectionProof': 'Every active after triangle is an exact unchanged before triangle. Removal and index-only append cannot introduce an intersection; both prior audited caps are byte-identical.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    config = json.loads(args.config.read_text()); output = args.output.resolve(); require(not output.exists(), 'Fresh output required')
    require(config['kind'] == 'authorized-troll-pelvis-four-face-index-repair' and config['acceptance'] is False, 'Explicit unaccepted four-face configuration required')
    pins = config['inputs']
    for key, pin in pins.items(): require(sha(pin['path']) == pin['sha256'], 'Changed input: '+key)
    parent = json.loads(Path(pins['parentDiagnostic']['path']).read_text())
    proposal = json.loads(Path(pins['selectedProposal']['path']).read_text())
    require(parent['kind'] == 'bounded-troll-pelvis-port-diagnostic' and parent['targetId'] == 'troll-male-muscular-purposebuilt-v1' and
            parent['part'] == 'pelvis' and parent['coordinateSpace'] == 'working' and parent['statureApplications'] == 0,
            'Exact original bounded Troll working lineage required')
    require(proposal['boundedDiagnostic']['sha256'] == pins['parentDiagnostic']['sha256'] and
            proposal['targetSpecificProposedOperation']['removeOnlyOriginalFaceIds'] == [45990, 45991, 48153, 48154], 'Selected exact four-face proposal required')
    for path, h in parent['frozenInputs'].items(): require(sha(path) == h, 'Protected parent input changed')
    mapping = np.load(parent['faceMapping']['path']); old_original = mapping['keptOriginalFaceIds']
    removed_original = np.asarray([v for pair in ORIGINAL_PAIRS for v in pair]); mask = ~np.isin(old_original, removed_original)
    require(tuple(np.flatnonzero(~mask)) == DIAGNOSTIC_BODY_ROWS and np.count_nonzero(~mask) == 4, 'Exact source-to-diagnostic face IDs required')
    output.mkdir(parents=True); spaces = {}; active_arrays = {}
    for space in ('source', 'working'):
        source = Path(parent['exports'][space]['candidate']['path']); require(sha(source) == parent['exports'][space]['candidate']['sha256'], 'Parent candidate changed')
        doc, binary = read_glb(source); old_rows = primitives(doc, binary); proofs = []
        require(len(old_rows[0]['faces']) == 44854, 'Expected original bounded body count')
        for original_pair in ORIGINAL_PAIRS:
            ids = [int(np.flatnonzero(old_original == v)[0]) for v in original_pair]
            proofs.append(pair_equivalence(old_rows[0]['attributes'], *old_rows[0]['faces'][ids]))
        result, out_bin = index_child(doc, binary, mask); candidate = output/(space+'-diagnostic.glb')
        write_glb(candidate, result, out_bin); final_doc, final_bin = read_glb(candidate)
        preservation_proof = preservation(doc, binary, final_doc, final_bin, mask); new_rows = primitives(final_doc, final_bin)
        transition = topology_compare(old_rows, new_rows); inventory, refs = active_inventory(new_rows)
        require(inventory[0]['storedNearZeroNormalRows'] == [34936] and 34936 not in refs['primitive0ReferencedOriginalAccessorRows'], 'Unused original bad row ownership required')
        active_arrays.update({space+'_'+k: v for k, v in refs.items()})
        corners = {}; mats = []; originals = []; primids = []
        for i, row in enumerate(new_rows):
            for key, values in row['attributes'].items(): corners.setdefault(key, []).append(values[row['faces']])
            mats.extend([row['primitive'].get('material')]*len(row['faces'])); primids.extend([i]*len(row['faces']))
            originals.extend(old_original[mask].tolist() if i == 0 else [-1]*len(row['faces']))
        archive = output/(space+'-active-corners.npz')
        np.savez_compressed(archive, **{key: np.concatenate(value) for key, value in corners.items()},
            materialIds=np.asarray(mats), primitiveIds=np.asarray(primids), sourceOriginalFaceIds=np.asarray(originals))
        spaces[space] = {'candidate': stamp(candidate), 'parentCandidate': stamp(source), 'activeCornerArchive': stamp(archive),
            'pairEquivalence': proofs, 'preservation': preservation_proof, 'activeAccessorInventory': inventory, 'topologyTransition': transition}
    archive = output/'original-face-active-row-mapping.npz'
    np.savez_compressed(archive, parentKeptOriginalFaceIds=old_original, keptOriginalFaceIds=old_original[mask],
        removedOriginalFaceIds=removed_original, parentPrimitive0KeepMask=mask,
        removedParentPrimitive0FaceIds=np.flatnonzero(~mask), sourceOriginalFaces=mapping['sourceOriginalFaces'], **active_arrays)
    snapshots = {}; snap = output/'helper-snapshots'; snap.mkdir()
    for name in ('repair_troll_pelvis_opposite_pairs.py', 'write_bounded_pelvis_diagnostic.py', 'conservative_face_selection.py', 'place_purposebuilt_pelvis.py', 'stage_stock_part.py'):
        path = Path(__file__).with_name(name); dst = snap/name; shutil.copyfile(path, dst); snapshots[str(path.resolve())] = stamp(dst)
    for key, pin in pins.items(): require(sha(pin['path']) == pin['sha256'], 'Input changed after repair: '+key)
    for path, h in parent['frozenInputs'].items(): require(sha(path) == h, 'Protected parent changed after repair')
    receipt = {'schemaVersion': 1, 'kind': 'bounded-troll-pelvis-original-opposite-pair-index-repair',
        'config': stamp(args.config), 'parentDiagnostic': pins['parentDiagnostic'], 'selectedReadOnlyProposal': pins['selectedProposal'],
        'targetContract': parent['targetContract'], 'targetContractSha256': parent['targetContractSha256'], 'targetId': parent['targetId'],
        'rigRevision': parent['rigRevision'], 'coordinateSpace': 'working', 'part': 'pelvis', 'joint': parent['joint'], 'model': parent['model'],
        'source': parent['source'], 'properFit': parent['properFit'], 'sourceToAttachmentLocal': parent['sourceToAttachmentLocal'],
        'attachmentWorld': parent['attachmentWorld'], 'statureApplications': 0, 'sourceMastersChanged': False,
        'removedOnlyOriginalFaceIds': removed_original.tolist(), 'removedParentPrimitive0FaceIds': list(DIAGNOSTIC_BODY_ROWS),
        'retainedOriginalBodyFaces': 44850, 'capFacesUnchanged': 1444, 'diagnosticFaces': 46294,
        'faceAndActiveRowMapping': stamp(archive), 'exports': spaces,
        'frozenInputs': {pin['path']: pin['sha256'] for pin in pins.values()}, 'helperSnapshots': snapshots,
        'activeAccessorHandling': 'Original near-zero normal row34936 stays byte-identical in the stored original accessor but is unreferenced. Downstream adapters must verify the explicit per-primitive referenced-row inventory and active corner archive. Accessor-wide validators still see the bad stored row and retain their existing behavior; this receipt is not a silent normal override.',
        'visibilityCaveat': 'Selected read-only evidence sampled55 interior points and30 directions per pair in source/working; no observed exterior contribution or holes. Finite sampling cannot prove invisibility from every possible client view. Fresh child comparison and literal review are separate receipts.',
        'existingGuardsUnchanged': True, 'unsupportedExistingClosedLineage': True, 'closedExteriorClaim': False,
        'geometryDiagnosticGuardsPassed': True, 'selectionMade': False, 'materialAccepted': False, 'stagingAccepted': False,
        'anatomyAccepted': False, 'productionAccepted': False, 'clientAccepted': False}
    path = output/'diagnostic.json'; path.write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'receipt': stamp(path), 'candidates': {space: data['candidate'] for space, data in spaces.items()},
                     'afterTopology': spaces['working']['topologyTransition']['after']}), flush=True)


if __name__ == '__main__': main()
