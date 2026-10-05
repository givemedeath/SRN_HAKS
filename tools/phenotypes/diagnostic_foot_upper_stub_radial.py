"""Source-bound LEFTfoot120 upper-stub preparation; no mesh-export CLI.

The canonical pipeline continues to reject this unsupported diagnostic operation.
Only the exact current source, frozen ankle and complete reviewed masks are used.
A distinct concrete review is required before adding/executing any exporter.
"""
import argparse
import copy
import json
from pathlib import Path
import numpy as np
import target_contract as tc
from place_purposebuilt_pelvis import BASIS, accessor, embedded_maps, read_glb
from conservative_face_selection import mesh_arrays
from diagnostic_axis_radial import append_attributes, verify_discrete
from verify_diagnostic_foot_uniform120 import verify_receipt as verify_parent
from foot_upper_stub_math import parameters, profile, transport

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'output/phenotypes/troll-male-purposebuilt-v1'
TARGET = BASE/'rig-frozen-v1/target-contract.json'
TARGET_SHA = '65e25102a970193786a6c6bffd1b9e1ee15c9c0e323f4a83e17deb5e23e97c0a'
PROPOSAL = BASE/'inspection/foot120-upper-stub-source-bound-proposal-v1/review-config.json'
PROPOSAL_SHA = '5654faa568cc56b8c2cd2c9751e5bee6d8a3bb1363807ed100e8e3b508bbddd6'
PARENT_SHA = '55b77cd23c1425feb5c7850efe858c733324ec46bcf8d5137fb4e1edca1791bf'
CANDIDATE_SHA = '1e88f35568d436f774722dba46b131c48fc04cf12bee4e632cffbd3797f34d72'
START, END, FACTOR = .027324198800000008, .05560602092591471, .5855251506097975
MASK_KEYS = ('affectedSourceRowIDs','protectedOriginalZeroOrLowerSourceRowIDs',
             'outsideSourceRowIDs','allAffectedVertexSourceFaceIDs',
             'crossingAffectedProtectedSourceFaceIDs','protectedWholeSourceFaceIDs')


def ref(path):
    return {'path':str(Path(path).resolve()),'sha256':tc.sha(path)}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def exact(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def check_proposal(c):
    tc.require(c.get('schemaVersion') == 1 and
               c.get('kind') == 'review-only-foot120-upper-stub-contour-derived-radial-field' and
               c.get('part') == 'footl' and c.get('joint') == 'lfoot_g' and
               c.get('coordinateSpace') == 'working', 'Exact LEFT working stub proposal required')
    tc.require(parameters(c['startCurrentLocalMetres'],c['endCurrentLocalMetres'],
                          c['terminalRadialFactor']) == (START, END, FACTOR),
               'Only the exact contour-derived source support/factor is prepared')
    tc.require(c.get('statureApplications') == 0 and
               c.get('globalTranslationScaleRollOrFrameChange') is False and
               c.get('localOffsetProposed') is False and
               c.get('currentFoot120OriginalScaleNotReapplied') is True and
               c.get('currentFootAxialScaleUnchanged') is True,
               'No scale/length/rig/origin/offset repetition or change allowed')
    tc.require(c.get('noMeshExportOrRepairExecution') is True and
               c.get('rootReviewRequiredBeforeImplementationExport') is True and
               c.get('protectedSpecificFaces') == {'12586':True,'44222':True},
               'Unexported complete lower-wall review required')
    tc.require(all(c.get(key) is False for key in
                   ('geometryAccepted','connectorAccepted','clientAccepted','productionAccepted')),
               'All diagnostic acceptance must stay false')


def complete_masks(points, original_points, faces, masks):
    tc.require(points.shape == original_points.shape and points.ndim == 2 and
               points.shape[1] == 3 and np.isfinite(points).all() and
               np.isfinite(original_points).all(), 'Complete finite original/current correspondence')
    tc.require(np.issubdtype(faces.dtype,np.integer) and faces.ndim == 2 and
               faces.shape[1] == 3 and len(faces) > 0 and
               faces.min() >= 0 and faces.max() < len(points), 'Ordered integer source faces required')
    protected = original_points[:,2] <= 0.
    active = (points[:,2] > START) & ~protected
    expected = dict(zip(MASK_KEYS, (np.flatnonzero(active),np.flatnonzero(protected),
        np.flatnonzero(~active),np.flatnonzero(active[faces].all(1)),
        np.flatnonzero(active[faces].any(1)&~active[faces].all(1)),
        np.flatnonzero(~active[faces].any(1)))))
    for key, ids in expected.items():
        tc.require(key in masks and np.issubdtype(masks[key].dtype,np.integer) and
                   masks[key].ndim == 1 and np.array_equal(masks[key],ids),
                   'Exhaustive ordered nonambiguous row/face mask differs: '+key)
    tc.require(np.array_equal(masks['sourceFaces'],faces), 'Exact source triangle order required')
    for face in (12586,44222):
        if face < len(faces):
            tc.require(not active[faces[face]].any(), 'Protected literal lower wall changed')
    return protected, active


def archive_rows(corners, faces, count):
    """Every indexed vertex must have one exact authored f64 corner owner."""
    tc.require(corners.dtype == np.dtype('float64') and corners.shape == faces.shape+(3,) and
               np.isfinite(corners).all(), 'Finite authoritative float64 ordered position corners')
    indices = faces.ravel();values = corners.reshape(-1,3)
    rows = np.empty((count,3),dtype=float);seen = np.zeros(count,bool)
    for index, value in zip(indices,values):
        if seen[index]:
            tc.require(rows[index].tobytes() == value.tobytes(),
                       'Ambiguous original indexed vertex f64 ownership')
        else:
            rows[index] = value;seen[index] = True
    tc.require(seen.all(), 'Unreferenced original vertex lacks authoritative position owner')
    return rows


def bake_ram(doc, blob, archive, original_points, masks):
    raw, faces, primitive = mesh_arrays(doc,blob)
    tc.require(set(primitive['attributes']) == {'POSITION','NORMAL','TANGENT','TEXCOORD_0'} and
               doc['scenes'] == [{'nodes':[0]}] and len(doc['buffers']) == 1 and
               not doc['buffers'][0].get('uri'), 'One embedded original static source required')
    rows = {key:accessor(doc,blob,value) for key,value in primitive['attributes'].items()}
    tc.require(all(a.dtype == np.dtype('<f4') and len(a) == len(raw) and np.isfinite(a).all()
                   for a in rows.values()), 'Finite complete authored float32 arrays required')
    tc.require(rows['NORMAL'].shape == raw.shape and rows['TANGENT'].shape == (len(raw),4) and
               rows['TEXCOORD_0'].shape == (len(raw),2), 'Original complete attribute shapes required')
    local = raw.astype(float)@BASIS.T
    protected,active = complete_masks(local,original_points,faces,masks)
    n = rows['NORMAL'].astype(float)@BASIS.T
    t = rows['TANGENT'].astype(float).copy();t[:,:3] = t[:,:3]@BASIS.T
    q,nn,tt,J,computed_active = transport(local,n,t,protected,START,END,FACTOR)
    tc.require(np.array_equal(active,computed_active), 'Reviewed source scope differs from finite math')
    s,_ = profile(local[:,2],START,END,FACTOR);s[protected] = 1.
    tc.require(abs(s-masks['fieldScaleBySourceRow']).max() <= 2e-15,
               'Exact source contour polynomial equivalence differs')
    shaded = active & np.any(J != np.eye(3),axis=(1,2))
    newrows = {key:rows[key].copy() for key in ('POSITION','NORMAL','TANGENT')}
    newrows['POSITION'][active] = (q[active]@BASIS).astype('<f4')
    newrows['NORMAL'][shaded] = (nn[shaded]@BASIS).astype('<f4')
    rt = tt.copy();rt[:,:3] = rt[:,:3]@BASIS
    newrows['TANGENT'][shaded] = rt[shaded].astype('<f4')
    tc.require(newrows['POSITION'][:,1].tobytes() == raw[:,1].tobytes() and
               newrows['TANGENT'][:,3].tobytes() == rows['TANGENT'][:,3].tobytes(),
               'All authored axial values and W must remain bit exact')
    for key in newrows:
        tc.require(exact(newrows[key][~active],rows[key][~active]),
                   'Protected authored attribute altered: '+key)
    for key in ('NORMAL','TANGENT'):
        tc.require(exact(newrows[key][~shaded],rows[key][~shaded]), 'Identity shading bytes changed')
    before,after,mindot = verify_discrete(raw,newrows['POSITION'],faces)
    tc.require(np.array_equal(archive['sourceTriangleIds'],np.arange(len(faces))) and
               np.array_equal(archive['sourceCornerOrder'],np.tile([0,1,2],(len(faces),1))) and
               np.array_equal(archive['primitiveIds'],np.zeros(len(faces),dtype=int)),
               'Full ordered original source corner lineage required')
    ap = archive_rows(archive['positions'],faces,len(raw))
    tc.require(abs(ap-local).max() < 3e-8 and
               np.array_equal(archive['uvGltf'],rows['TEXCOORD_0'].astype(float)[faces]) and
               archive['normals'].shape == (len(faces),3,3) and
               archive['tangents'].shape == (len(faces),3,4) and
               abs(archive['normals']-n[faces]).max() < 1e-12 and
               abs(archive['tangents']-t[faces]).max() < 1e-12,
               'Current authoritative positions and exact N/T/UV corner association required')
    cm = protected[faces].ravel()
    aq,an,at,aJ,aa = transport(archive['positions'].reshape(-1,3),
        archive['normals'].reshape(-1,3),archive['tangents'].reshape(-1,4),cm,START,END,FACTOR)
    tc.require(np.array_equal(aa.reshape(faces.shape),active[faces]),
               'Authoritative/serialized support classification ambiguous')
    arc = {key:value.copy() for key,value in archive.items()}
    arc['positions'] = aq.reshape(len(faces),3,3)
    arc['normals'] = an.reshape(len(faces),3,3)
    arc['tangents'] = at.reshape(len(faces),3,4)
    for key in ('positions','normals','tangents'):
        tc.require(exact(arc[key][~active[faces]],archive[key][~active[faces]]),
                   'Protected source-native corner values changed')
    for key in archive:
        if key not in ('positions','normals','tangents'):
            tc.require(exact(arc[key],archive[key]), 'Undeclared archive ownership changed: '+key)
    changed,payload = append_attributes(doc,blob,newrows)
    restored = copy.deepcopy(changed);restored['meshes'][0]['primitives'][0]['attributes'] = primitive['attributes']
    restored['accessors'] = restored['accessors'][:-3];restored['bufferViews'] = restored['bufferViews'][:-3]
    restored['buffers'][0]['byteLength'] = doc['buffers'][0]['byteLength']
    tc.require(restored == doc and payload[:len(blob)] == blob and
               embedded_maps(changed,payload) == embedded_maps(doc,blob),
               'Only appended P/N/T bindings may change; original UV/material/BIN must remain exact')
    proof = {'minDeterminant':float(np.linalg.det(J).min()),
        'continuousDeterminantLowerBound':FACTOR**2,
        'maximumRAMVertexDisplacementMetres':float(np.linalg.norm(q-local,axis=1).max()),
        'maximumSerializedVertexDisplacementMetres':float(np.linalg.norm(
            newrows['POSITION'].astype(float)@BASIS.T-local,axis=1).max()),
        'maximumPositionSerializationErrorMetres':float(abs(
            (newrows['POSITION'].astype(float)@BASIS.T)[faces]-arc['positions']).max()),
        'maximumNormalMagnitudeError':float(abs(np.linalg.norm(nn,axis=1)-np.linalg.norm(n,axis=1)).max()),
        'maximumTangentMagnitudeError':float(abs(np.linalg.norm(tt[:,:3],axis=1)-np.linalg.norm(t[:,:3],axis=1)).max()),
        'minimumSerializedFaceNormalDot':mindot,'beforeTopology':before,'afterTopology':after,
        'activeSourceRows':int(active.sum()),'protectedOriginalLowerFootRows':int(protected.sum()),
        'outsideSourceRows':int((~active).sum()),'allAxialZExact':True,'originalWExact':True,
        'protectedPNTRowsExact':True,'computedIdentityNTExact':True,'UVMapsMaterialsFaceOrderBINExact':True,
        'uniqueOriginalIndexedF64PositionOwners':True,'additionalFootScaleApplications':0,
        'statureApplications':0,'rigFrameChanged':False,'meshExported':False,
        'noShelfVisualAcceptance':False,'connectorAccepted':False,'productionAccepted':False}
    return changed,payload,arc,proof


def prepare(output):
    out = Path(output).resolve()
    tc.require(out.parent == BASE/'inspection' and out.name.startswith('foot120-upper-stub-typed-preparation-v')
               and not out.exists(), 'Fresh target-owned inspection output only; no mesh-export CLI')
    tc.require(tc.sha(PROPOSAL) == PROPOSAL_SHA and tc.sha(TARGET) == TARGET_SHA,
               'Exact reviewed contour proposal and current frozen target required')
    c = read(PROPOSAL);check_proposal(c);target = tc.load(TARGET)
    tc.require(target['identity']['race'] == 'troll' and target['identity']['gender'] == 'male' and
               target['identity']['prefix'] == 'pmg0','Only target-owned Troll male identity')
    tc.require(c['sourceReceipt']['sha256'] == PARENT_SHA and c['sourceCandidate']['sha256'] == CANDIDATE_SHA,
               'Only exact selected original foot120 parent, no cumulative field')
    parent_path = Path(c['sourceReceipt']['path']);parent_proof,row = verify_parent(parent_path,TARGET,target,'working')
    parent = read(parent_path);tc.verify_binding(parent,TARGET,target,'working')
    tc.require(parent['operation'] == 'uniform-scale-original-working-foot' and
               np.array_equal(parent['attachmentWorld'],tc.frame(target,'lfoot_g','working')) and
               parent['statureApplications'] == 0,'Current foot120 source frame/operation must remain exact')
    pins = {}
    def pin(p,h):
        p = Path(p).resolve();tc.require(tc.sha(p) == h,'Prepared source input changed: '+str(p))
        tc.require(str(p) not in pins or pins[str(p)] == h,'Conflicting source pin')
        pins[str(p)] = h
    for p,h in c['inputs'].items():pin(p,h)
    for p,h in row['inputs'].items():pin(p,h)
    pin(c['masksAndContourArrays']['path'],c['masksAndContourArrays']['sha256'])
    doc,blob = read_glb(parent['candidate']);od,ob = read_glb(parent['source'])
    original,original_faces,_ = mesh_arrays(od,ob)
    raw,faces,_ = mesh_arrays(doc,blob);tc.require(np.array_equal(faces,original_faces), 'Original source face order changed')
    with np.load(c['masksAndContourArrays']['path'],allow_pickle=False) as z:masks={key:z[key].copy() for key in z.files}
    with np.load(parent['nativeCornerArchive']['path'],allow_pickle=False) as z:archive={key:z[key].copy() for key in z.files}
    pin(parent['nativeCornerArchive']['path'],parent['nativeCornerArchive']['sha256'])
    _,_,_,proof = bake_ram(doc,blob,archive,original.astype(float)@BASIS.T,masks)
    tc.require(raw.shape == (32800,3) and faces.shape == (50000,3), 'Exact32800/50000 current foot inventory')
    helpers = [Path(__file__),Path(__file__).with_name('foot_upper_stub_math.py'),
               Path(__file__).with_name('verify_diagnostic_foot_uniform120.py'),
               Path(__file__).with_name('diagnostic_axis_radial.py'),
               Path(__file__).with_name('conservative_face_selection.py'),
               Path(__file__).with_name('place_purposebuilt_pelvis.py'),Path(tc.__file__)]
    for p in helpers:pin(p,tc.sha(p))
    out.mkdir();snapshots = {}
    for p in helpers:
        dest = out/p.name;dest.write_bytes(p.read_bytes());snapshots[str(p.resolve())] = ref(dest)
    config = {'schemaVersion':1,'kind':'review-only-typed-foot120-upper-stub-radial-preparation',
        **tc.binding(TARGET,target,'working'),'part':'footl','joint':'lfoot_g',
        'sourceProposal':ref(PROPOSAL),'sourceReceipt':c['sourceReceipt'],'sourceCandidate':c['sourceCandidate'],
        'sourceNativeCorners':parent['nativeCornerArchive'],'sourceMasks':c['masksAndContourArrays'],
        'heldShin765Receipt':c['heldShin765Receipt'],'heldShinCandidate':c['heldShinCandidate'],
        'field':{'startLocalZ':START,'endLocalZ':END,'terminalFactor':FACTOR,'offsetXYZ':[0.,0.,0.],
                 'formula':'F=(s(z)x,s(z)y,z); s=1-(1-k)quintic(clamp(t)); originalZ<=0 protected exactly'},
        'helperSnapshots':snapshots,'protectedInputs':pins,'ramSourceProof':proof,
        'meshExportAuthorized':False,'meshExported':False,'reviewRequiredBeforeExporterExecution':True,
        'originalFoot39NonmanifoldEdgesUnchangedPending':True,'geometryAccepted':False,
        'connectorAccepted':False,'materialAccepted':False,'nativeAccepted':False,
        'clientAccepted':False,'productionAccepted':False}
    path=out/'review-config.json';path.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    template={'kind':'root-review-required-foot120-upper-stub-local-field',
        'configuration':ref(path),'sourceContourProposal':ref(PROPOSAL),
        'mustReview':['Literal source/proposed meridian and discrete edge evidence, including60.410deg largest crease increase.',
                      'No unintended shelf/ridge/dip under standing/walking literal comparison after a specifically approved one-child export.',
                      'Retained foot120 sole/toes/arch/lower-wall silhouette and frozen ankle/shin geometry.'],
        'authorizeOneFreshLeftDiagnosticExport':False,'rightMirrorAuthorized':False,
        'fieldSelectedForContinuation':False,'connectorAccepted':False,'productionAccepted':False}
    tp=out/'root-review-template.json';tp.write_text(json.dumps(template,indent=2)+'\n')
    print(json.dumps({'configuration':ref(path),'reviewTemplate':ref(tp),'proof':proof,'meshExported':False}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    prepare(p.parse_args().output)


if __name__ == '__main__':
    main()

