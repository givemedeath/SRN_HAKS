"""Append-only working pelvis35 -> local cuff5 diagnostic; never a canonical part."""
from collections import Counter
import argparse
import copy
import json
from pathlib import Path
import shutil
import numpy as np
import target_contract as tc
import diagnostic_pelvis_terminal as parent_helper
from place_purposebuilt_pelvis import BASIS, accessor, embedded_maps, read_glb, write_glb
from conservative_face_selection import topology

KIND = 'target-part-diagnostic-pelvis-cuff-contour5'
OPERATION = 'same-topology-world-XY-local-cuff-contraction'
SCOPE = 'offline-working-pelvis-cuff-contour5-diagnostic'
ROLES = [0, 1, 1, 2, 0, 2]
FLAGS = ['closedExteriorClaim', 'geometryAccepted', 'anatomyAccepted', 'collisionAccepted',
         'materialAccepted', 'capOwnershipAccepted', 'clothBoundaryAccepted', 'stagingAccepted',
         'nativeAccepted', 'clientAccepted', 'productionAccepted', 'selectionMade']
RECIPE = {'part': 'pelvis', 'coordinateSpace': 'working', 'radialReduction': .05,
          'worldZFullWeightThrough': .942, 'worldZZeroWeightFrom': .965,
          'centralXProtectedThrough': .020, 'lateralXFullWeightFrom': .027,
          'statureApplications': 0, 'capRoundMetres': 0., 'fitReapplied': False,
          'terminal35Reapplied': False, 'worldZUnchanged': True}

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def center_array(centers):
    tc.require(set(centers) == {'positive', 'negative'}, 'Exact two cap centers required')
    c = np.array([centers['negative'], centers['positive']], dtype=float)
    tc.require(c.shape == (2, 2) and np.isfinite(c).all(), 'Finite world XY centers required')
    tc.require(c[0, 0] < -.027 and c[1, 0] > .027, 'Centers must lie beyond central blend')
    return c

def field(p, centers):
    """C2 XY contraction; Z literal. Return mapped world P, proper J and weight."""
    p = np.asarray(p, dtype=float)
    tc.require(p.ndim == 2 and p.shape[1] == 3 and np.isfinite(p).all(), 'Finite world P required')
    c = center_array(centers)[(p[:, 0] > 0).astype(int)]
    x, z = abs(p[:, 0]), p[:, 2]
    tx = np.clip((x - .020) / .007, 0, 1)
    tz = np.clip((z - .942) / .023, 0, 1)
    smooth = lambda t: t*t*t*(10+t*(-15+6*t))
    deriv = lambda t: 30*t*t*(t-1)**2
    w = np.where(z <= .942, 1., np.where(z >= .965, 0., 1-smooth(tz)))
    chi = np.where(x <= .020, 0., np.where(x >= .027, 1., smooth(tx)))
    dx = np.where((x > .020) & (x < .027), deriv(tx)*np.sign(p[:, 0])/.007, 0.)*w
    dz = np.where((z > .942) & (z < .965), -deriv(tz)/.023, 0.)*chi
    weight = w*chi
    v = p[:, :2]-c
    q = 1-.05*weight
    J = np.broadcast_to(np.eye(3), (len(p), 3, 3)).copy()
    J[:, 0, 0] = q-.05*v[:, 0]*dx
    J[:, 1, 1] = q
    J[:, 1, 0] = -.05*v[:, 1]*dx
    J[:, 0, 2] = -.05*v[:, 0]*dz
    J[:, 1, 2] = -.05*v[:, 1]*dz
    tc.require(np.all(np.linalg.det(J) >= .9025-1e-12), 'Positive determinant bound violated')
    result = p.copy()
    affected = weight != 0
    result[affected, :2] -= .05*weight[affected, None]*v[affected]
    return result, J, weight

def transport(p, n, t, centers):
    """Only affected N/T: inverse-transpose N, J T then GS; magnitude and W retained."""
    p, n, t = np.asarray(p, float), np.asarray(n), np.asarray(t)
    tc.require(n.shape == p.shape and t.shape == (len(p), 4), 'Matching P/N/T rows required')
    tc.require(np.isfinite(n).all() and np.isfinite(t).all(), 'Finite shading required')
    _, J, weight = field(p, centers)
    active = weight != 0
    nn, tt = n.copy(), t.copy()
    if active.any():
        ns, ts = n[active].astype(float), t[active].astype(float)
        nl, tl = np.linalg.norm(ns, axis=1), np.linalg.norm(ts[:, :3], axis=1)
        tc.require((nl > 1e-8).all() and (tl > 1e-8).all() and (abs(ts[:, 3]) == 1).all(),
                   'Degenerate affected parent N/T/W rejected')
        outn = np.linalg.solve(J[active].transpose(0, 2, 1), ns[..., None])[..., 0]
        length = np.linalg.norm(outn, axis=1)
        tc.require((length > 1e-8).all(), 'Vanishing transported N rejected')
        unit = outn/length[:, None]
        nn[active] = unit*nl[:, None]
        outt = np.einsum('nij,nj->ni', J[active], ts[:, :3])
        outt -= np.sum(outt*unit, axis=1)[:, None]*unit
        length = np.linalg.norm(outt, axis=1)
        tc.require((length > 1e-8).all(), 'Vanishing orthogonal T rejected')
        tt[active, :3] = outt*(tl/length)[:, None]
    return nn, tt

def cap_centers(doc, blob, H):
    centers, boundaries = {}, {}
    for i in [1, 2]:
        p = doc['meshes'][0]['primitives'][i]
        P = accessor(doc, blob, p['attributes']['POSITION'])
        F = accessor(doc, blob, p['indices']).reshape(-1, 3).astype(np.int64)
        world = P.astype(float)@BASIS.T + H[:3, 3]
        unique, ids = np.unique(world[:, :2], axis=0, return_inverse=True)
        f = ids[F]
        edges = Counter(tuple(sorted((int(a), int(b)))) for face in f
                        for a, b in [(face[0], face[1]), (face[1], face[2]), (face[2], face[0])])
        boundary = np.unique([e for e, count in edges.items() if count == 1])
        tc.require(len(boundary) == 68 and len(unique)-len(edges)+len(F) == 1,
                   'Exact generated cap disk/68 boundary required')
        center = unique[boundary].mean(axis=0)
        side = 'positive' if center[0] > 0 else 'negative'
        tc.require(side not in centers, 'Two opposite cap sides required')
        centers[side] = center.tolist()
        boundaries[i] = np.flatnonzero(np.isin(ids, boundary))
    center_array(centers)
    return centers, boundaries

def mapped_rows(P, N, T, active, H, centers):
    tc.require(np.array_equal(H[:3, :3], np.eye(3)), 'Frozen pelvis rotation frame only')
    world = P.astype(float)@BASIS.T + H[:3, 3]
    proposed, J, weight = field(world, centers)
    changed = active & (weight != 0)
    rows = {'POSITION': P.copy(), 'NORMAL': N.copy(), 'TANGENT': T.copy()}
    rows['POSITION'][changed, 0] = (P[changed, 0].astype(float)+proposed[changed, 0]-world[changed, 0]).astype('<f4')
    rows['POSITION'][changed, 2] = (P[changed, 2].astype(float)-proposed[changed, 1]+world[changed, 1]).astype('<f4')
    n = N.astype(float)@BASIS.T
    t = T.astype(float).copy(); t[:, :3] = t[:, :3]@BASIS.T
    nn, tt = transport(world[active], n[active], t[active], centers)
    n[active], t[active] = nn, tt
    rows['NORMAL'][changed] = (n[changed]@BASIS).astype('<f4')
    t[:, :3] = t[:, :3]@BASIS
    rows['TANGENT'][changed] = t[changed].astype('<f4')
    for semantic, original in [('POSITION', P), ('NORMAL', N), ('TANGENT', T)]:
        tc.require(rows[semantic][~changed].tobytes() == original[~changed].tobytes(), 'Protected/inactive row changed')
    tc.require(rows['POSITION'][:, 1].tobytes() == P[:, 1].tobytes(), 'Axial position bytes changed')
    tc.require(rows['TANGENT'][:, 3].tobytes() == T[:, 3].tobytes(), 'Tangent W changed')
    return rows, world, J, weight, changed

def derive(doc, blob, H, centers, masks=None):
    prims = doc['meshes'][0]['primitives']
    tc.require(len(prims) == 6 and [p['material'] for p in prims] == ROLES, 'Exact six role primitives required')
    actual_centers, boundaries = cap_centers(doc, blob, H)
    tc.require(actual_centers == centers, 'Frozen cap centers differ')
    groups, used, inventory = [], set(), []
    oldPs, newPs, allFs, offset = [], [], [], 0
    records = {}
    for i, p in enumerate(prims):
        key = tuple(p['attributes'][s] for s in ['POSITION', 'NORMAL', 'TANGENT'])
        if key in used: continue
        used.add(key)
        ids = [j for j, item in enumerate(prims) if tuple(item['attributes'][s] for s in ['POSITION', 'NORMAL', 'TANGENT']) == key]
        P, N, T = [accessor(doc, blob, p['attributes'][s]) for s in ['POSITION', 'NORMAL', 'TANGENT']]
        active = parent_helper.shared_active_rows(doc, blob, p)
        rows, world, J, weight, changed = mapped_rows(P, N, T, active, H, centers)
        newworld = rows['POSITION'].astype(float)@BASIS.T + H[:3, 3]
        groups.append((ids, rows))
        for j in ids:
            f = accessor(doc, blob, prims[j]['indices']).reshape(-1, 3).astype(np.int64)
            tc.require(len(f) == parent_helper.COUNTS[j], 'Original primitive face count differs')
            owned = np.zeros(len(P), bool); owned[np.unique(f)] = True
            changed_owned = owned & (weight != 0)
            if masks is not None:
                tc.require(np.array_equal(np.flatnonzero(changed_owned), masks[f'percent5p{j}changedOwnedRows']), 'Approved changed-row mask differs')
                tc.require(np.array_equal(rows['POSITION'], masks[f'percent5p{j}proposedP_RAM']), 'Measured exact proposed positions differ')
            oldc, newc = world[f], newworld[f]
            on = np.cross(oldc[:, 1]-oldc[:, 0], oldc[:, 2]-oldc[:, 0])
            gn = np.cross(newc[:, 1]-newc[:, 0], newc[:, 2]-newc[:, 0])
            tc.require((np.linalg.norm(on, axis=1) > 2e-15).all() and (np.linalg.norm(gn, axis=1) > 2e-15).all(), 'Degenerate face requires separate review')
            _, jf, _ = field(oldc.mean(axis=1), centers)
            expected = np.linalg.solve(jf.transpose(0, 2, 1), on[..., None])[..., 0]
            dots = np.sum(expected*gn, axis=1)/np.linalg.norm(expected, axis=1)/np.linalg.norm(gn, axis=1)
            tc.require((dots > 0).all(), 'Centroid transported body/cap normal exception')
            if j in [1, 2]:
                tc.require(np.all(weight[owned] == 1) and np.all(J[owned] == np.diag([.95, .95, 1.])), 'Entire cap must remain one affine contraction')
                tc.require((on[:, 2]*gn[:, 2] > 0).all(), 'Serialized cap XY orientation flip')
            inventory.append({'primitive': j, 'material': prims[j]['material'], 'faces': len(f),
                              'changedOwnedRows': int(changed_owned.sum()),
                              'changedFaces': int(np.any(changed_owned[f], axis=1).sum()),
                              'maximumDisplacementMetres': float(np.linalg.norm(newworld-world, axis=1)[changed_owned].max()) if changed_owned.any() else 0.,
                              'minimumCentroidTransportedNormalDot': float(dots.min()),
                              'sampledDeterminantMinimum': float(np.linalg.det(J).min())})
            records[j] = {'P': rows['POSITION'], 'N': rows['NORMAL'], 'T': rows['TANGENT'], 'F': f, 'parentP': P, 'parentN': N, 'parentT': T}
            oldPs.append(P); newPs.append(rows['POSITION']); allFs.append(f+offset); offset += len(P)
    before = topology(np.concatenate(oldPs), np.concatenate(allFs))
    after = topology(np.concatenate(newPs), np.concatenate(allFs))
    tc.require(all(before[k] == after[k] for k in parent_helper.TOPOLOGY_KEYS), 'New aggregate topology defect')
    body_points = {v.tobytes() for j in [0, 3, 4, 5] for v in records[j]['P'][records[j]['F']].reshape(-1, 3)}
    for j in [1, 2]:
        tc.require(all(v.tobytes() in body_points for v in records[j]['P'][boundaries[j]]), 'Cap/body exact boundary disconnected')
    d, b = parent_helper.append(doc, blob, groups)
    return d, b, records, {'beforeTopology': before, 'afterTopology': after,
                           'continuousMinimumDeterminantBound': .9025,
                           'originalBinPrefixExact': True, 'protectedInactivePNTExact': True,
                           'indicesUVMapsMaterialsRolesExact': True, 'capEntirelyAffine': True,
                           'capXYFootprintChanged': True, 'capOwnershipAccepted': False}, sorted(inventory, key=lambda x: x['primitive'])

def exact_role_seams(records, seam_path):
    positions = {}
    with np.load(seam_path, allow_pickle=False) as s:
        for role in ['skin', 'garment']:
            for j in np.unique(s[role+'_primitiveIds']):
                mask = s[role+'_primitiveIds'] == j
                rec = records[int(j)]
                points = rec['P'][rec['F']][s[role+'_primitiveFaceIds'][mask], s[role+'_primitiveCornerIds'][mask]]
                for point, p in zip(s[role+'_sharedPointIds'][mask], points):
                    old = positions.setdefault(int(point), p.tobytes())
                    tc.require(old == p.tobytes(), 'Skin/opaque-garment seam disconnected')
    tc.require(len(positions) == 2404, 'Exact 2404 role seam points required')


def derived_archives(parent, H, centers, records):
    with np.load(parent['bodyFloat64DeformedCornerArchive']['path'], allow_pickle=False) as ar:
        body = {k: ar[k].copy() for k in ar.files}
    for name in ['positions', 'normals', 'tangents']:
        tc.require('contourParent'+name.title() not in body, 'Contour cannot be applied twice')
        body['contourParent'+name.title()] = body[name].copy()
    shape = body['positions'].shape
    bp = body['positions'].reshape(-1, 3); bn = body['normals'].reshape(-1, 3); bt = body['tangents'].reshape(-1, 4)
    world = bp+H[:3, 3]; q, _, weight = field(world, centers); affected = weight != 0
    p = bp.copy(); p[affected, :2] += q[affected, :2]-world[affected, :2]
    n, t = transport(world, bn, bt, centers)
    body['positions'] = p.reshape(shape); body['normals'] = n.reshape(body['normals'].shape); body['tangents'] = t.reshape(body['tangents'].shape)
    with np.load(parent['generatedCapDeformedCornerArchive']['path'], allow_pickle=False) as ar:
        caps = {k: ar[k].copy() for k in ar.files}
    for name in ['POSITION', 'NORMAL', 'TANGENT']:
        tc.require('contourParentGenerated'+name not in caps, 'Cap contour cannot be applied twice')
        old = np.concatenate([records[j]['parent'+{'POSITION': 'P', 'NORMAL': 'N', 'TANGENT': 'T'}[name]][records[j]['F']] for j in [1, 2]])
        tc.require(caps[name].dtype == old.dtype and caps[name].tobytes() == old.tobytes(), 'Generated cap parent corner lineage differs')
        caps['contourParentGenerated'+name] = caps[name].copy()
        caps[name] = np.concatenate([records[j][{'POSITION': 'P', 'NORMAL': 'N', 'TANGENT': 'T'}[name]][records[j]['F']] for j in [1, 2]])
    rawp = caps['contourParentGeneratedPOSITION'].astype(float).reshape(-1, 3)
    local = rawp@BASIS.T; world = local+H[:3, 3]; q, _, weight = field(world, centers)
    p = local.copy(); affected = weight != 0; p[affected, :2] += q[affected, :2]-world[affected, :2]
    raw_n = caps['contourParentGeneratedNORMAL'].astype(float).reshape(-1, 3)@BASIS.T
    raw_t = caps['contourParentGeneratedTANGENT'].astype(float).reshape(-1, 4); raw_t[:, :3] = raw_t[:, :3]@BASIS.T
    n, t = transport(world, raw_n, raw_t, centers)
    caps['derivedWorkingPositions'] = p.reshape(caps['POSITION'].shape)
    caps['derivedWorkingNormals'] = n.reshape(caps['NORMAL'].shape)
    caps['derivedWorkingTangents'] = t.reshape(caps['TANGENT'].shape)
    return body, caps


def validate_configuration(c):
    tc.require(c.get('schemaVersion') == 1 and c.get('kind') == 'pelvis-cuff-contour5-configuration' and c.get('scope') == SCOPE, 'Explicit cuff5 configuration required')
    tc.require(all(c.get(k) == v for k, v in RECIPE.items()), 'Only exact reviewed cuff5 recipe supported')
    center_array(c['centersWorldXY'])
    tc.require(c.get('acceptance') == {k: False for k in FLAGS}, 'Diagnostic scopes cannot authorize final acceptance')


def validate_approval(a):
    tc.require(a.get('schemaVersion') == 1 and a.get('kind') == 'root-approved-pelvis-cuff-contour5-diagnostic' and a.get('scope') == SCOPE, 'Explicit root cuff5 review required')
    tc.require(a.get('reviewedBy') == '/root' and a.get('reviewed') is True and a.get('authorizeImplementationAndOneFreshExport') is True, 'One fresh export must be explicitly reviewed')
    tc.require(a.get('acceptance') == {k: False for k in FLAGS}, 'Conflicting acceptance scope rejected')
    return a


def validate_parent_proof(proof, c):
    tc.require(proof.get('schemaVersion') == 1 and proof.get('kind') == 'independent-decoded-pelvis-terminal-shortening35-audit' and proof.get('passed') is True,
               'Exact successful independent pelvis35 audit required')
    tc.require(proof.get('receipt') == c['parentReceipt'] and proof.get('candidate') == c['parentCandidate'], 'Independent parent proof ancestry differs')
    tc.require(proof.get('statureApplications') == 0 and proof.get('capRoundMetres') == 0., 'Parent proof scaling/dome scope differs')
    for name in ['closedExteriorClaim', 'sourceTopologyResolved', 'geometryAccepted', 'materialAccepted', 'nativeAccepted', 'clientAccepted', 'productionAccepted']:
        tc.require(proof.get(name) is False, 'Parent proof cannot authorize acceptance')

def prepare(approval_path):
    ap = Path(approval_path).resolve(); a = validate_approval(read(ap)); pins = {}
    def pin(item):
        path = Path(item['path']).resolve(); actual = tc.sha(path)
        tc.require(actual == item['sha256'], 'Pinned input changed '+str(path)); pins[str(path)] = actual; return path
    pins[str(ap)] = tc.sha(ap)
    cp = pin(a['configuration']); c = read(cp); validate_configuration(c)
    for item in a['implementation'].values(): pin(item)
    tc.require(str(Path(__file__).resolve()) in pins and pins[str(Path(__file__).resolve())] == tc.sha(__file__), 'Executing helper must match approved implementation')
    tc.require(read(pin(a['focusedTests']))['exitCode'] == 0, 'Focused source tests did not pass')
    rp = pin(c['parentReceipt']); r = read(rp); tp = pin(c['targetContract']); target = tc.load(tp)
    tc.require(r.get('kind') == parent_helper.KIND and r.get('capRoundMetres') == 0. and r.get('statureApplications') == 0, 'Only current working pelvis35 typed parent')
    for key in ['closedExteriorClaim', 'geometryAccepted', 'capOwnershipAccepted', 'materialAccepted', 'nativeAccepted', 'stagingAccepted', 'clientAccepted', 'productionAccepted', 'selectionMade']:
        tc.require(r.get(key) is False, 'Parent acceptance cannot be inherited or waived')
    parent = parent_helper.verify_receipt(rp, tp, target, 'working'); pins.update(parent['inputs'])
    source = pin(c['parentCandidate']); tc.require(source == parent['candidate'].resolve() and r['candidateSha256'] == c['parentCandidate']['sha256'], 'Exact parent candidate required')
    H = np.asarray(r['attachmentWorld'], float); tc.require(np.array_equal(H, c['attachmentWorld']) and np.array_equal(H[:3, :3], np.eye(3)), 'Frozen pelvis attachment changed')
    evidence = read(pin(c['profileEvidence'])); pin(c['maskEvidence']); pin(c['seamEvidence'])
    tc.require(evidence.get('kind') == 'read-only-shortened-pelvis-local-contour-profile-proof' and evidence['parentReceipt'] == c['parentReceipt'] and evidence['parentCandidate'] == c['parentCandidate'] and evidence['arrays'] == c['maskEvidence'], 'Exact measured profile ancestry required')
    tc.require(evidence['centersWorldXY'] == c['centersWorldXY'], 'Measured centers differ')
    profile = next((v for v in evidence['variants'] if v['radialReduction'] == .05), None)
    tc.require(profile and profile['concreteExportRecommended'] is True and profile['topologyCountsUnchanged'] is True and profile['bodyNonpositiveTransportedSigns'] == [] and profile['all2404RoleSeamsAnd68CapBodyBoundariesExact'] is True, 'Failed cuff profile cannot export')
    proof = read(pin(c['parentIndependentProof'])); validate_parent_proof(proof, c)
    for path, sha in {**evidence['inputs'], **proof['frozenInputs']}.items(): pin({'path': path, 'sha256': sha})
    for key in ['bodyFloat64DeformedCornerArchive', 'generatedCapDeformedCornerArchive']: pin(r[key])
    doc, blob = read_glb(source)
    with np.load(c['maskEvidence']['path'], allow_pickle=False) as masks:
        newdoc, newblob, records, facts, inventory = derive(doc, blob, H, c['centersWorldXY'], masks)
    exact_role_seams(records, c['seamEvidence']['path'])
    body, caps = derived_archives(r, H, c['centersWorldXY'], records)
    return {'a': a, 'c': c, 'pins': pins, 'parent': r, 'targetPath': tp, 'target': target,
            'doc': newdoc, 'blob': newblob, 'facts': facts, 'inventory': inventory, 'body': body, 'caps': caps}


def execute(approval_path, output):
    output = Path(output).resolve(); tc.require(not output.exists(), 'Fresh immutable output required')
    p = prepare(approval_path); output.mkdir(parents=True)
    candidate = output/'candidate-local.glb'; write_glb(candidate, p['doc'], p['blob'])
    bodypath, cappath = output/'body-float64-contour-corners.npz', output/'generated-cap-float64-contour-corners.npz'
    np.savez_compressed(bodypath, **p['body']); np.savez_compressed(cappath, **p['caps'])
    helpers = [Path(__file__), Path(tc.__file__), Path(parent_helper.__file__),
               Path(__file__).with_name('place_purposebuilt_pelvis.py'), Path(__file__).with_name('conservative_face_selection.py')]
    snapshots = {}; (output/'helpers').mkdir()
    for source in helpers:
        dest = output/'helpers'/source.name; shutil.copyfile(source, dest)
        p['pins'][str(source.resolve())] = tc.sha(source)
        snapshots[str(source.resolve())] = {'path': str(dest), 'sha256': tc.sha(dest)}
    r = {**tc.binding(p['targetPath'], p['target'], 'working'), **RECIPE,
         'schemaVersion': 1, 'kind': KIND, 'operation': OPERATION, 'scope': SCOPE,
         'joint': 'pelvis_g', 'model': p['parent']['model'], 'candidate': str(candidate), 'candidateSha256': tc.sha(candidate),
         'candidateToAttachmentLocal': np.eye(4).tolist(), 'fitSourceToAttachmentLocal': p['parent']['fitSourceToAttachmentLocal'],
         'attachmentWorld': p['parent']['attachmentWorld'], 'parentTerminalReceipt': p['c']['parentReceipt'],
         'parentCandidate': p['c']['parentCandidate'], 'rootApproval': {'path': str(Path(approval_path).resolve()), 'sha256': tc.sha(approval_path)},
         'fieldConfiguration': p['c'], 'bodyFloat64ContourCornerArchive': {'path': str(bodypath), 'sha256': tc.sha(bodypath)},
         'generatedCapFloat64ContourCornerArchive': {'path': str(cappath), 'sha256': tc.sha(cappath)},
         'capShadingPolicy': 'parent35-generated-cap-N-inverse-transpose-T-J-GS-original-magnitude-W',
         'capAuthoritativeBasis': 'float64-for-this-operation-derived-from-parent-generated-serialized-float32',
         'primitiveRoleStatus': {'0': 'skin', '1': 'unowned-neutral-diagnostic-cap', '2': 'unowned-neutral-diagnostic-cap', '3': 'garment', '4': 'skin', '5': 'garment'},
         'primitiveInventory': p['inventory'], 'proof': p['facts'], 'frozenInputs': p['pins'], 'helperSnapshots': snapshots,
         'diagnosticOnly': True, 'canonicalNativeLineage': False, 'acceptance': {k: False for k in FLAGS},
         'limits': ['Inherited topology and unowned generated caps remain unaccepted.', 'Continuous proper local field and exact seams do not prove global collision freedom.', 'Skin/opaque-garment ownership and original maps/UV/indices remain literal; lower cuff/hem P/N/T changes only.', 'No dome, retriangulation, fit/rig/stature/terminal35 reapplication or engine shader acceptance.']}
    path = output/'diagnostic-cuff-contour-geometry.json'; path.write_text(json.dumps(r, indent=2)+'\n', encoding='utf-8')
    verify_receipt(path, p['targetPath'], p['target'])
    return path


def validate_child_claims(r, parent):
    tc.require(r.get('diagnosticOnly') is True and r.get('joint') == 'pelvis_g' and r.get('model') == parent['model'], 'Declared pelvis identity differs')
    tc.require(r.get('fitSourceToAttachmentLocal') == parent['fitSourceToAttachmentLocal'], 'Original fit ancestry changed')
    tc.require(r.get('primitiveRoleStatus') == {'0': 'skin', '1': 'unowned-neutral-diagnostic-cap', '2': 'unowned-neutral-diagnostic-cap', '3': 'garment', '4': 'skin', '5': 'garment'}, 'Caps/garment roles cannot be relabeled')
    tc.require(r.get('capShadingPolicy') == 'parent35-generated-cap-N-inverse-transpose-T-J-GS-original-magnitude-W' and r.get('capAuthoritativeBasis') == 'float64-for-this-operation-derived-from-parent-generated-serialized-float32', 'Generated cap shading provenance changed')

def verify_receipt(receipt_path, target_path, target, space='working'):
    path = Path(receipt_path).resolve(); r = read(path)
    tc.require(r.get('kind') == KIND and r.get('operation') == OPERATION and r.get('scope') == SCOPE and space == 'working', 'Exact cuff5 diagnostic kind/space required')
    tc.require(r.get('canonicalNativeLineage') is False and r.get('acceptance') == {k: False for k in FLAGS}, 'Final/canonical acceptance rejected')
    tc.require(all(r.get(k) == v for k, v in RECIPE.items()), 'Cuff5 recipe/one-application identity changed')
    tc.verify_binding(r, target_path, target, space)
    for filename, sha in r['frozenInputs'].items(): tc.require(tc.sha(filename) == sha, 'Frozen cuff input changed '+filename)
    tc.require(tc.sha(r['rootApproval']['path']) == r['rootApproval']['sha256'], 'Root approval changed')
    p = prepare(r['rootApproval']['path'])
    validate_child_claims(r, p['parent'])
    tc.require(all(r['frozenInputs'].get(name) == sha for name, sha in p['pins'].items()), 'Complete approved input closure cannot be dropped')
    for source, snap in r['helperSnapshots'].items():
        tc.require(Path(snap['path']).resolve() == (Path(r['candidate']).parent/'helpers'/Path(source).name).resolve() and tc.sha(snap['path']) == snap['sha256'] == r['frozenInputs'].get(source), 'Executed helper snapshot association changed')
    tc.require(r['fieldConfiguration'] == p['c'] and r['parentTerminalReceipt'] == p['c']['parentReceipt'] and r['parentCandidate'] == p['c']['parentCandidate'], 'Child parent/configuration ancestry changed')
    tc.require(np.array_equal(r['attachmentWorld'], p['parent']['attachmentWorld']) and np.array_equal(r['candidateToAttachmentLocal'], np.eye(4)), 'Attachment/fit applied again')
    tc.require(tc.sha(r['candidate']) == r['candidateSha256'], 'Candidate pin changed')
    actual_doc, actual_blob = read_glb(r['candidate'])
    tc.require(actual_doc == p['doc'] and actual_blob == p['blob'], 'Actual descriptor/serialized P/N/T/UV/index/BIN/map material differs')
    tc.require(r['primitiveInventory'] == p['inventory'] and r['proof'] == p['facts'], 'Measured proof changed')
    for key, values in [('bodyFloat64ContourCornerArchive', p['body']), ('generatedCapFloat64ContourCornerArchive', p['caps'])]:
        item = r[key]; tc.require(tc.sha(item['path']) == item['sha256'], 'Native archive pin changed')
        with np.load(item['path'], allow_pickle=False) as ar:
            tc.require(set(ar.files) == set(values), 'Original ancestry/archive fields dropped or invented')
            for name, expected in values.items():
                tc.require(ar[name].dtype == expected.dtype and ar[name].shape == expected.shape and ar[name].tobytes() == expected.tobytes(), 'Exact native float64/source/cap provenance differs '+name)
    return {'receipt': r, 'candidate': Path(r['candidate']), 'inputs': {**r['frozenInputs'], str(path): tc.sha(path), r['candidate']: r['candidateSha256'], r['bodyFloat64ContourCornerArchive']['path']: r['bodyFloat64ContourCornerArchive']['sha256'], r['generatedCapFloat64ContourCornerArchive']['path']: r['generatedCapFloat64ContourCornerArchive']['sha256']}, 'primitiveInventory': r['primitiveInventory']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approval', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = execute(args.approval, args.output)
    print(json.dumps({'receipt': str(receipt), 'sha256': tc.sha(receipt)}), flush=True)


