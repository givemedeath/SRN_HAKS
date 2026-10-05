"""Explicit working diagnostic consumer for the reviewed UV-basis pelvis child.

No canonical receipt coercion, cap skin ownership, transforms or acceptance.
"""
import json
from pathlib import Path
import numpy as np
import target_contract as contract
import target_diagnostic_lineage as diagnostic
import target_diagnostic_material_lineage as lineage
import target_diagnostic_uv_basis as basispolicy
from place_purposebuilt_pelvis import BASIS,accessor,read_glb

STAGE_KIND='target-diagnostic-uv-material-stage'
COMPOSITION_KIND='target-diagnostic-uv-material-composition'
AUDIT_KIND='target-diagnostic-uv-material-native-audit'
REVIEW_SCOPE='offline-working-diagnostic-pelvis-material-stage'
CAP_MODE='literal-unowned-neutral-gray'
MATERIAL_ROLES={'0':'skin','1':'unowned-neutral-diagnostic-cap','2':'garment'}
GROUPS=(('skin',(0,4)),('garment',(3,5)),('cap-left',(1,)),('cap-right',(2,)))


def same_pin(first,second):
    """Exact file identity with optional truthful byte-size metadata.

    Receipts may include bytes for reporting; it is not a different source pin.
    Both paths/hashes are still independently verified, and provided sizes must
    match the real file. This does not coerce kinds, lineage, ownership or gates.
    """
    paths=[]
    for item in (first,second):
        contract.require(isinstance(item,dict) and set(item)<={'path','sha256','bytes'},
                         'Supported exact path/hash/optional-bytes pin required')
        path=diagnostic.pin(item,{})
        if 'bytes' in item:
            contract.require(type(item['bytes']) is int and item['bytes']==path.stat().st_size,
                             'Optional evidence size differs from actual file')
        paths.append(path)
    return paths[0]==paths[1] and first['sha256']==second['sha256']

def stage_review(review,source_receipt,source_candidate):
    allowed={'reviewed','reviewedBy','scope','sourceReceipt','sourceCandidate','newCornerShadingPolicy',
             'capMode','aoComparisons','authorizeStageExports','authorizeOfflineNativeCompilation',
             'evidence','notes'}
    contract.require(type(review) is dict and set(review)==allowed and review.get('reviewed') is True
                     and review.get('reviewedBy')=='/root' and review.get('scope')==REVIEW_SCOPE
                     and review.get('authorizeStageExports') is True and review.get('authorizeOfflineNativeCompilation') is True
                     and review.get('capMode')==CAP_MODE and review.get('aoComparisons')==[0,.15,.35]
                     and review.get('newCornerShadingPolicy')==basispolicy.POLICY_ID
                     and review.get('sourceReceipt')==source_receipt and review.get('sourceCandidate')==source_candidate
                     and isinstance(review.get('notes'),str) and bool(review['notes'].strip())
                     and type(review.get('evidence')) is list and bool(review['evidence']),
                     'Explicit root review of this diagnostic source/caps/AO/native stage required')
    diagnostic.no_acceptance(review)
    return review


def verify_receipt(receipt_path,target_path,target,decoded_audit,footprint_audit):
    inputs={str(Path(receipt_path).resolve()):contract.sha(receipt_path)}
    receipt=json.loads(Path(receipt_path).read_text())
    contract.require(receipt.get('schemaVersion')==2 and receipt.get('kind')==basispolicy.KIND
                     and receipt.get('operation')==basispolicy.OPERATION
                     and receipt.get('newCornerShadingPolicy')==basispolicy.POLICY_ID
                     and receipt.get('part')=='pelvis' and receipt.get('joint')=='pelvis_g'
                     and receipt.get('diagnosticOnly') is True and receipt.get('canonicalNativeLineage') is False
                     and receipt.get('bodyRoleAssignmentReviewed') is True
                     and receipt.get('statureApplications')==0,
                     'Explicit reviewed working diagnostic UV-basis pelvis descendant required')
    diagnostic.no_acceptance(receipt);contract.verify_binding(receipt,target_path,target,'working')
    contract.require(np.array_equal(receipt['candidateToAttachmentLocal'],np.eye(4)),
                     'Diagnostic staging cannot reapply placement/frame/scale')
    for path,sha in receipt['frozenInputs'].items():diagnostic.pin({'path':path,'sha256':sha},inputs)
    candidate=diagnostic.pin({'path':receipt['candidate'],'sha256':receipt['candidateSha256']},inputs)
    parent_path=diagnostic.pin(receipt['sourceDiagnosticReceipt'],inputs)
    parent=lineage.prepare_parent(parent_path,target_path,target);inputs.update(parent['inputs'])
    contract.require(receipt['attachmentWorld']==parent['receipt']['attachmentWorld']
                     and receipt['fitSourceToAttachmentLocal']==parent['receipt']['fitSourceToAttachmentLocal'],
                     'Frozen proper-fit/attachment ancestry differs')
    selection=diagnostic.load_item(receipt['cutMap'],inputs)
    basispolicy.reviewed_body_map(selection,parent['rows'],parent['originalIds'])
    lineage.verify_map_bindings(selection,parent,parent_path,target_path,inputs)
    contract.require(receipt['rootBodyMapReview']==selection['rootReview'],
                     'Receipt has substituted reviewed shading/role consent')
    audits=[]
    for item,kind in [(decoded_audit,'independent-decoded-diagnostic-uv-basis-trial-audit'),
                      (footprint_audit,'independent-exhaustive-reviewed-role-footprint-trial-audit')]:
        audit=diagnostic.load_item(item,inputs);diagnostic.no_acceptance(audit)
        contract.require(audit.get('schemaVersion')==2 and audit.get('kind')==kind and audit.get('passed') is True
                         and audit.get('sourceTopologyResolved') is False
                         and audit.get('receipt',{}).get('sha256')==contract.sha(receipt_path),
                         'Pinned successful independent diagnostic audit for this exact source required')
        for key in ('driver','candidate','parentCandidate','selectedCutMap'):
            if key in audit:diagnostic.pin(audit[key],inputs)
        audits.append(audit)
    contract.require(audits[0]['candidate']['sha256']==receipt['candidateSha256']
                     and same_pin(audits[1]['selectedCutMap'],receipt['cutMap'])
                     and all(same_pin(a['receipt'],{'path':str(receipt_path),'sha256':contract.sha(receipt_path)}) for a in audits),
                     'Audit candidate/map closure differs')
    doc,blob=read_glb(candidate)
    contract.require(doc['nodes']==[{'name':'detached_geometry','mesh':0}]
                     and len(doc['meshes'])==1 and len(doc['meshes'][0]['primitives'])==6
                     and len(doc['materials'])==3, 'Supported exact six-primitive detached diagnostic child required')
    primitives=doc['meshes'][0]['primitives']
    contract.require([p.get('material') for p in primitives]==[0,1,1,2,0,2],
                     'Skin/garment ownership or literal separate neutral caps changed')
    lineage.verify_unchanged_storage(doc,blob,parent['doc'],parent['binary'])
    body=diagnostic.load_archive(receipt['bodyFloat64DerivedCornerArchive'],inputs)
    caps=diagnostic.load_archive(receipt['capSerializedFloat32CornerArchive'],inputs)
    contract.require(set(caps)==set(parent['caps']) and all(caps[k].dtype==parent['caps'][k].dtype
                     and caps[k].tobytes()==parent['caps'][k].tobytes() for k in caps),
                     'Literal separate generated cap archive differs')
    encoded=[]
    for pi,p in enumerate(primitives):
        contract.require(set(p['attributes'])==set(diagnostic.SEMANTICS) and p.get('mode',4)==4
                         and not p.get('targets'), 'Static P/N/UV/T triangles only')
        ix=accessor(doc,blob,p['indices']).reshape(-1,3)
        values={key:accessor(doc,blob,index)[ix] for key,index in p['attributes'].items()}
        contract.require(all(v.dtype==np.float32 and np.isfinite(v).all() for v in values.values()),
                         'Finite serialized float32 attributes required')
        encoded.append(values)
    body_ids=[0,3,4,5];source_body={k:np.concatenate([encoded[i][k] for i in body_ids]) for k in diagnostic.SEMANTICS}
    contract.require(np.array_equal(body['primitiveIds'],np.concatenate([np.full(len(encoded[i]['POSITION']),i) for i in body_ids])),
                     'Body primitive/source archive ordered correspondence differs')
    for key,width in [('positions',3),('normals',3),('uvGltf',2),('tangents',4)]:
        contract.require(body[key].dtype==np.float64 and body[key].shape==(len(source_body['POSITION']),3,width)
                         and np.isfinite(body[key]).all(), 'Separate float64 body archive required: '+key)
    for key,semantic in [('positions','POSITION'),('normals','NORMAL'),('uvGltf','TEXCOORD_0')]:
        actual=source_body[semantic].astype(float)
        if semantic!='TEXCOORD_0':actual=actual@BASIS.T
        contract.require(np.max(abs(actual-body[key]))<=(6e-8 if semantic=='TEXCOORD_0' else 1e-6),
                         'Diagnostic body serialized transport differs: '+key)
    t=source_body['TANGENT'].astype(float);t[:,:,:3]=t[:,:,:3]@BASIS.T
    contract.require(np.max(abs(t-body['tangents']))<=1e-6 and np.array_equal(t[:,:,3],body['tangents'][:,:,3]),
                     'Diagnostic source tangent/sign provenance differs')
    groups={}
    for name,ids in GROUPS:
        values={k:np.concatenate([encoded[i][k] for i in ids]) for k in diagnostic.SEMANTICS}
        p=values['POSITION'].astype(float)@BASIS.T;n=values['NORMAL'].astype(float)@BASIS.T
        uv=values['TEXCOORD_0'].astype(float);native=uv.copy();native[:,:,1]=1-native[:,:,1]
        tangents=values['TANGENT'].astype(float);tangents[:,:,:3]=tangents[:,:,:3]@BASIS.T
        groups[name]={'positions':p,'normals':n,'uvGltf':uv,'uvNative':native,'tangents':tangents,
                      'primitiveIds':list(ids),'triangles':len(p)}
    return {'receipt':receipt,'candidate':candidate,'doc':doc,'binary':blob,'body':body,'caps':caps,
            'groups':groups,'inputs':inputs,'audits':audits,'parent':parent}
