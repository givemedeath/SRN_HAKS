"""Independent original LEFTfoot120 decode and preview-only typed evidence.

No fitting, mirroring, staging, geometry writing, native compilation or acceptance.
The generic target-part pipeline is intentionally not extended by this verifier.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import target_contract as tc
from place_purposebuilt_pelvis import BASIS, accessor, embedded_maps, node_matrix, read_glb

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'output/phenotypes/troll-male-purposebuilt-v1'
TARGET = BASE/'rig-frozen-v1/target-contract.json'
CONFIG = BASE/'inspection/foot120-uniform-preparation-v2/review-config.json'
CONFIG_SHA = '8b62288f6df20a84c40ba05dfe801eef6f08aa9730a43e9ddc0fa6d9f20ae824'
APPROVAL = BASE/'inspection/foot120-uniform-root-approved-left-v1/root-approval.json'
APPROVAL_SHA = '8f9f29bcf6367be97e3207807f08088e86602faf72a753163c2c7c7f8cdf7211'
GEOMETRY = BASE/'repairs/foot120-uniform-v1/left/geometry.json'
GEOMETRY_SHA = '55b77cd23c1425feb5c7850efe858c733324ec46bcf8d5137fb4e1edca1791bf'
OPERATION = 'uniform-scale-original-working-foot'
PREVIEW_KIND = 'prevalidated-original-foot120-preview-row'
FLAGS = ('closedExteriorClaim','geometryAccepted','anatomyAccepted','collisionAccepted',
         'materialAccepted','capOwnershipAccepted','clothBoundaryAccepted','stagingAccepted',
         'nativeAccepted','clientAccepted','productionAccepted','selectionMade')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def ref(path):
    return {'path':str(Path(path).resolve()),'sha256':tc.sha(path)}


def equal_bytes(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def fingerprint(a):
    return {'dtype':str(a.dtype),'shape':list(a.shape),
            'sha256':hashlib.sha256(a.tobytes()).hexdigest()}


def verify_position_classes(original, child):
    old_unique,old_classes=np.unique(original,axis=0,return_inverse=True)
    new_unique,new_classes=np.unique(child,axis=0,return_inverse=True)
    pairs=np.unique(np.c_[old_classes,new_classes],axis=0)
    tc.require(len(old_unique)==len(new_unique)==len(pairs) and
               np.all(np.bincount(pairs[:,0],minlength=len(old_unique))==1) and
               np.all(np.bincount(pairs[:,1],minlength=len(new_unique))==1),
               'Exact position seam/incidence classes changed through rounding')
    return len(old_unique)


def verify_serialized(parent, binary, child, output_binary, pivot):
    """Verify independent expected f32 POSITION plus complete unchanged storage."""
    tc.require(len(parent.get('nodes',[])) == len(parent.get('meshes',[])) ==
               len(parent.get('scenes',[])) == 1 and
               np.array_equal(node_matrix(parent['nodes'][0]),np.eye(4)) and
               not parent.get('skins') and not parent.get('animations'),
               'One detached static original source required')
    tc.require(len(parent['meshes'][0]['primitives']) == 1, 'One original primitive required')
    pr = parent['meshes'][0]['primitives'][0]
    tc.require(set(pr['attributes']) == {'POSITION','NORMAL','TANGENT','TEXCOORD_0'},
               'Exact original authored attribute inventory required')
    rows = {key:accessor(parent,binary,value) for key,value in pr['attributes'].items()}
    tc.require(all(a.dtype == np.dtype('<f4') and np.isfinite(a).all() for a in rows.values()),
               'Original attributes must be finite float32')
    cg = np.asarray(pivot,dtype=float)@BASIS
    expected = (cg+1.2*(rows['POSITION'].astype(float)-cg)).astype('<f4')
    tc.require(output_binary[:len(binary)] == binary and len(binary)%4 == 0 and
               len(output_binary) == len(binary)+expected.nbytes and
               output_binary[len(binary):] == expected.tobytes(),
               'Only exact scaled POSITION may append; original BIN prefix must match')
    wanted = copy.deepcopy(parent)
    wanted['bufferViews'].append({'buffer':0,'byteOffset':len(binary),'byteLength':expected.nbytes})
    wanted['accessors'].append({'bufferView':len(parent['bufferViews']),'componentType':5126,
        'count':len(expected),'type':'VEC3','min':expected.min(0).astype(float).tolist(),
        'max':expected.max(0).astype(float).tolist()})
    wanted['meshes'][0]['primitives'][0]['attributes']['POSITION'] = len(parent['accessors'])
    wanted['buffers'][0]['byteLength'] = len(output_binary)
    tc.require(child == wanted,'Only declared POSITION accessor/view/buffer length may change')
    cp = child['meshes'][0]['primitives'][0]
    actual = {key:accessor(child,output_binary,value) for key,value in cp['attributes'].items()}
    tc.require(equal_bytes(actual['POSITION'],expected),'Decoded POSITION bits differ')
    verify_position_classes(rows['POSITION'],actual['POSITION'])
    for key in ('NORMAL','TANGENT','TEXCOORD_0'):
        tc.require(equal_bytes(rows[key],actual[key]),'Original authored attribute changed: '+key)
    original_indices = accessor(parent,binary,pr['indices'])
    tc.require(equal_bytes(original_indices,accessor(child,output_binary,cp['indices'])),
               'Original topology/winding changed')
    tc.require(embedded_maps(parent,binary) == embedded_maps(child,output_binary),
               'Original material map bytes changed')
    return rows, actual, original_indices.reshape(-1,3).astype(np.int64)


def verify_archives(parent, child, frame, pivot, decoded_rows, faces):
    """Own-coordinate exact formula plus independent world-affine reconstruction."""
    tc.require(set(parent) == set(child),'Archive ownership inventory differs')
    tc.require(parent['positions'].dtype == np.dtype('float64') and
               parent['positions'].shape == (len(faces),3,3),'Original f64 triangle corners required')
    c = np.asarray(pivot,dtype=float)
    expected = c+(parent['positions']-c)*1.2
    tc.require(equal_bytes(child['positions'],expected),'Authoritative own-coordinate field differs')
    for key in parent:
        if key != 'positions':
            tc.require(equal_bytes(parent[key],child[key]),'Protected archive array changed: '+key)
    A = np.asarray(frame,dtype=float)
    tc.require(A.shape == (4,4) and np.isfinite(A).all() and
               np.array_equal(A[3],[0,0,0,1]) and
               np.allclose(A[:3,:3].T@A[:3,:3],np.eye(3),atol=1e-13,rtol=0) and
               np.linalg.det(A[:3,:3])>0,'Proper immutable attachment required')
    before = parent['positions']@A[:3,:3].T+A[:3,3]
    after = child['positions']@A[:3,:3].T+A[:3,3]
    sole = float(before[...,2].min())
    cw = np.array([A[0,3],A[1,3],sole])
    tc.require(np.array_equal(np.linalg.solve(A[:3,:3],cw-A[:3,3]),c),
               'Pivot is not original measured sole projection of frozen ankle')
    independently_expected = before*1.2+cw*(1.-1.2)
    error = float(abs(after-independently_expected).max())
    tc.require(error<2e-16,'Independent world affine differs')
    tc.require(float(after[...,2].min()) == sole,'Original f64 bind sole minimum changed')
    bounds0 = np.array([before.min((0,1)),before.max((0,1))])
    bounds1 = np.array([after.min((0,1)),after.max((0,1))])
    tc.require(abs(np.diff(bounds1,axis=0)-1.2*np.diff(bounds0,axis=0)).max()<2e-16,
               'All XYZ extents must scale uniformly')
    f32 = (decoded_rows['POSITION'].astype(float)@BASIS.T)[faces]
    serialization_error = float(abs(f32-child['positions']).max())
    tc.require(serialization_error<3e-8,'Serialized/authoritative POSITION correspondence differs')
    tc.require(np.array_equal(child['uvGltf'],decoded_rows['TEXCOORD_0'].astype(float)[faces]) and
               np.array_equal(child['tangents'][...,3],decoded_rows['TANGENT'].astype(float)[faces,3]),
               'Exact ordered UV/W corner correspondence changed')
    n_error = float(abs(child['normals']-decoded_rows['NORMAL'].astype(float)[faces]@BASIS.T).max())
    t_error = float(abs(child['tangents'][...,:3]-decoded_rows['TANGENT'].astype(float)[faces,:3]@BASIS.T).max())
    tc.require(max(n_error,t_error)<1e-12,'Proper GLTF/NWN source N/T association differs')
    return {'originalWorldBounds':bounds0.tolist(),'actualWorldBounds':bounds1.tolist(),
        'originalBindSoleMinimumWorldZ':sole,'actualBindSoleMinimumWorldZ':float(after[...,2].min()),
        'independentWorldAffineMaxErrorMetres':error,
        'serializedToAuthoritativeCornerMaxErrorMetres':serialization_error,
        'actualSerializedBindSoleMinimumWorldZ':float((f32@A[:3,:3].T+A[:3,3])[...,2].min()),
        'sourceLocalAnkleAnchorShift':((1.-1.2)*c).tolist(),
        'upperFootTopRiseMetres':float(bounds1[1,2]-bounds0[1,2]),
        'sourceNormalTangentAssociationErrors':{'N':n_error,'TXYZ':t_error,'W':0.},
        'allXYZExtentRatio':1.2,'uniformJacobianDeterminant':1.2**3}


def validate_typed_receipt(receipt, target_path, target):
    tc.require(receipt.get('kind') == 'target-part-geometry' and receipt.get('schemaVersion') == 2 and
               receipt.get('operation') == OPERATION and receipt.get('part') == 'footl' and
               receipt.get('sourcePart') == 'footl','Only explicitly typed original LEFTfoot120 operation supported')
    tc.verify_binding(receipt,target_path,target,'working')
    tc.require(receipt.get('joint') == 'lfoot_g' and receipt.get('model') == tc.model(target,'footl') and
               np.array_equal(receipt.get('attachmentWorld'),tc.frame(target,'lfoot_g','working')) and
               receipt.get('reflectionWorld') is None,'Frozen LEFT attachment/resource ownership differs')
    tc.require(receipt.get('statureApplications') == 0 and receipt.get('sourceOriginalRatio') == 1.2 and
               receipt.get('sizeScaleApplicationsOnOriginalBaseline') == 1 and
               receipt.get('priorLargerOrCompressedFootReapplied') is False and
               receipt.get('diagnosticOnly') is True,'One original-baseline uniform size operation only')
    for key in ('geometryAccepted','topologyAccepted','capOwnershipAccepted','connectorAccepted',
                'soleContactAccepted','materialAccepted','clientAccepted','productionAccepted'):
        tc.require(receipt.get(key) is False,'Foot diagnostic acceptance must remain false: '+key)


def verify_receipt(path, target_path, target, space='working'):
    """Full bundled-Python proof; returned row is preview-only, never canonical."""
    tc.require(space == 'working' and Path(path).resolve() == GEOMETRY.resolve() and
               Path(target_path).resolve() == TARGET.resolve(),'Exact current LEFT working diagnostic only')
    inputs = {}
    def pin(p,h=None):
        p=Path(p).resolve();actual=tc.sha(p)
        tc.require(h is None or actual == h,'Pinned foot evidence changed: '+str(p))
        inputs[str(p)] = actual
        return p
    pin(path,GEOMETRY_SHA);pin(CONFIG,CONFIG_SHA);pin(APPROVAL,APPROVAL_SHA)
    cfg = read(CONFIG);approval=read(APPROVAL);receipt=read(path)
    validate_typed_receipt(receipt,target_path,target)
    tc.verify_binding(cfg,target_path,target,'working')
    tc.require(approval.get('kind') == 'root-approved-original-left-foot120-uniform' and
               approval.get('configuration') == cfg and approval.get('authorizeImplementationAndOneFreshLeftExport') is True and
               approval.get('intendedOutput') == str(GEOMETRY.parent) and
               approval.get('rightMirrorAuthorized') is False,'Exact executed LEFT-only approval required')
    for p,h in cfg['protectedInputs'].items():pin(p,h)
    for p,h in receipt['frozenInputs'].items():pin(p,h)
    tc.require(receipt['configuration'] == ref(CONFIG) and receipt['explicitReviewedConfigurationSha256'] == CONFIG_SHA and
               receipt['sourceReceipt'] == cfg['sourceGeometry']['path'] and receipt['sourceReceiptSha256'] == cfg['sourceGeometry']['sha256'] and
               receipt['source'] == cfg['sourceCandidate']['path'] and receipt['sourceSha256'] == cfg['sourceCandidate']['sha256'],
               'Reviewed original source/provenance differs')
    parent=read(pin(cfg['sourceGeometry']['path'],cfg['sourceGeometry']['sha256']))
    tc.require(parent['operation'] == 'fit' and parent['sourcePart'] is None and parent['part'] == 'footl' and
               parent['statureApplications'] == 0 and np.array_equal(parent['attachmentWorld'],receipt['attachmentWorld']),
               'Untouched original fit/attachment required')
    M=np.diag([1.2]*3+[1.]);M[:3,3]=(1.-1.2)*np.asarray(cfg['pivotLocal'])
    tc.require(np.array_equal(receipt['sourceToAttachmentLocal'],M) and
               cfg['sourceCandidateToNewLocal'] == M.tolist(),'Exact once-only sole-projected affine required')
    d,b=read_glb(pin(receipt['source'],receipt['sourceSha256']))
    nd,nb=read_glb(pin(receipt['candidate'],receipt['candidateSha256']))
    rows,actual,F=verify_serialized(d,b,nd,nb,cfg['pivotLocal'])
    tc.require(rows['POSITION'].shape == (32800,3) and F.shape == (50000,3),
               'Frozen original32800 rows/50000triangles required')
    def archive(item):
        with np.load(pin(item['path'],item['sha256']),allow_pickle=False) as z:
            return {key:z[key].copy() for key in z.files}
    original=archive(cfg['sourceNativeCorners']);child=archive(receipt['nativeCornerArchive'])
    measurement=verify_archives(original,child,receipt['attachmentWorld'],cfg['pivotLocal'],actual,F)
    shin=read(pin(cfg['unchangedLeftShin85']['path'],cfg['unchangedLeftShin85']['sha256']))
    tc.verify_binding(shin,target_path,target,'working')
    tc.require(shin['part']=='shinl' and shin['factor']==.85 and shin['statureApplications']==0 and
               np.array_equal(shin['attachmentWorld'],tc.frame(target,'lshin_g','working')),
               'Exact unchanged current LEFTshin85 required')
    pin(shin['candidate'],shin['candidateSha256']);pin(shin['nativeCornerArchive']['path'],shin['nativeCornerArchive']['sha256'])
    # Exact prepared snapshot resolution remains recorded; all current geometric pins above stay literal.
    for entry in cfg['shinHistoricalPreviewClosure']:pin(entry['snapshot']['path'],entry['snapshot']['sha256'])
    for p in [__file__,tc.__file__,ROOT/'tools/phenotypes/place_purposebuilt_pelvis.py']:pin(p)
    topology_path=BASE/'inspection/foot-imagegen-v1-topology-v1/inspection/topology-and-depth-sections.json'
    topology=read(pin(topology_path,'d18bd16a1dbb14b1e9adead095ba2eb00d654fedf1dc52cbaf35604383121445'))
    tc.require(len(topology['sources'])==1 and topology['sources'][0]['sha256']==parent['sourceSha256'] and
               topology['sources'][0]['nonmanifoldEdgeCount']==39,'Exact original39-NM source evidence required')
    proof={'schemaVersion':2,'kind':'independent-actual-original-left-foot120-uniform-decode',
        **tc.binding(target_path,target,'working'),'sourceGeometry':ref(cfg['sourceGeometry']['path']),
        'actualGeometry':ref(path),'actualCandidate':ref(receipt['candidate']),
        'actualNativeCornerArchive':ref(receipt['nativeCornerArchive']['path']),
        'configuration':ref(CONFIG),'executedApproval':ref(APPROVAL),**measurement,
        'originalBINPrefixExact':True,'onlyExactPOSITIONAccessorAppended':True,
        'storedNormalTangentWUVIndexMapsMaterialsExact':True,'archiveArraysExceptPositionsExact':True,
        'originalArchiveArrayFingerprints':{k:fingerprint(v) for k,v in original.items()},
        'actualPositionFingerprint':fingerprint(child['positions']),
        'nativeCompiled':False,'rigFrameJointSocketFixed':True,'attachmentAppliedOnce':True,
        'statureApplications':0,'sizeScaleApplicationsOnOriginalBaseline':1,
        'originalNonmanifoldEdgesRiskRetained':39,'originalTopologyEvidence':ref(topology_path),
        'exactPositionSeamIncidenceClassesPreserved':True,
        'historicalNeighborPreviewClosure':cfg['shinHistoricalPreviewClosure'],
        'limits':['Existing39 nonmanifold edges, visible toe creases/possible inner walls retained; no topology/cap acceptance.',
                  'Sole minimum preserved arithmetically; sole planarity, motion/ground contact and upperfoot/shin intersections await literal review.',
                  'Uniform global affine has no taper window or returning field; actual outline/no-new-shelves review remains mandatory.',
                  'Typed row is offline preview only; unsupported canonical operation is not promoted or mirrored.'],
        'pendingGates':{key:False for key in FLAGS},'geometryAccepted':False,'soleContactAccepted':False,
        'connectorAccepted':False,'materialAccepted':False,'clientAccepted':False,'productionAccepted':False,
        'frozenInputs':inputs}
    row={'receiptKind':PREVIEW_KIND,'sourceReceiptKind':'target-part-geometry','sourceOperation':OPERATION,
        **tc.binding(target_path,target,'working'),'receipt':str(Path(path).resolve()),'receiptSha256':GEOMETRY_SHA,
        'part':'footl','joint':'lfoot_g','model':receipt['model'],'candidate':receipt['candidate'],
        'candidateSha256':receipt['candidateSha256'],'sourceReceipt':ref(path),
        'originalCanonicalAncestor':ref(cfg['sourceGeometry']['path']),
        'nativeCornerArchive':receipt['nativeCornerArchive'],'attachmentWorld':receipt['attachmentWorld'],
        'candidateToAttachmentLocal':np.eye(4).tolist(),'attachmentAppliedOnce':True,
        'sourceOriginalRatio':1.2,'statureApplications':0,'sizeScaleApplicationsOnOriginalBaseline':1,
        'pendingGates':{key:False for key in FLAGS},'canonicalNativeLineage':False,
        'blenderExecutesIndependentAudits':False,'clientEvidence':False,
        'inputs':inputs,'footTopologyRisksRetained':39,'rightMirrorAuthorized':False,
        'literalAnkleSoleMotionRequired':True,'historialPreviewSnapshotClosure':cfg['shinHistoricalPreviewClosure']}
    return proof,row


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    output=Path(args.output).resolve()
    tc.require(not output.exists() and output.parent==BASE/'inspection' and
               output.name.startswith('foot120-uniform-actual-decode-v'),'Fresh target-owned actual proof output required')
    proof,row=verify_receipt(GEOMETRY,TARGET,tc.load(TARGET))
    output.mkdir();pp=output/'actual-decode.json';pp.write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    row['independentActualDecode']=ref(pp);row['inputs'][str(pp)]=tc.sha(pp)
    rp=output/'leftfoot120-row.json';rp.write_text(json.dumps(row,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'proof':ref(pp),'row':ref(rp),'measurement':{k:proof[k] for k in
        ['independentWorldAffineMaxErrorMetres','serializedToAuthoritativeCornerMaxErrorMetres',
         'actualBindSoleMinimumWorldZ','actualSerializedBindSoleMinimumWorldZ','upperFootTopRiseMetres']}},indent=2))

if __name__ == '__main__':main()


