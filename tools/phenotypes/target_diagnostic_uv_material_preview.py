"""Separate working-only preview of the exact reviewed six-primitive material child.

This does not supply canonical body geometry, stage or future changed-cap lineage.
"""
import argparse,json
from pathlib import Path
import numpy as np
import target_contract as contract
import target_diagnostic_lineage as diagnostic
import target_diagnostic_uv_basis as basispolicy
import target_diagnostic_uv_material_lineage as material

KIND='target-diagnostic-uv-material-preview'
REVIEW_KIND='target-diagnostic-uv-material-preview-root-review'
SCOPE='offline-working-diagnostic-uv-material-preview'
FLAGS=diagnostic.FLAGS
PIN_KEYS=('sourceGeometry','sourceCandidate','decodedAudit','footprintAudit')
IMPLEMENTATION=('target_diagnostic_uv_material_preview.py','pose_preview_target_parts.py','pose_preview.py',
                'test_target_diagnostic_uv_material_preview.py')

def verify_preview_descriptor(path,target_path,target,space='working'):
    path=Path(path).resolve();descriptor=json.loads(path.read_text());inputs={str(path):contract.sha(path)}
    fields={'schemaVersion','kind','part','joint','model','diagnosticOnly','previewScope','statureApplications',
            'attachmentWorld','candidateToAttachmentLocal','rootReview'}|set(PIN_KEYS)|set(FLAGS)|set(contract.binding(target_path,target,'working'))
    contract.require(type(descriptor) is dict and set(descriptor)==fields and space=='working'
                     and descriptor.get('schemaVersion')==2 and descriptor.get('kind')==KIND
                     and descriptor.get('previewScope')==SCOPE and descriptor.get('diagnosticOnly') is True,
                     'Separate explicit working diagnostic UV-material preview descriptor required')
    contract.verify_binding(descriptor,target_path,target,'working');diagnostic.no_acceptance(descriptor)
    for flag in FLAGS:contract.require(descriptor.get(flag) is False,'Preview pending gate must be false: '+flag)
    contract.require(target['rig'].get('offlineStructureAccepted') is True
                     and target['rig'].get('pilotAccepted') is True
                     and target['rig'].get('pilotAcceptanceScope')=='offline-rig-structure',
                     'Exact frozen offline structure required')
    contract.require(descriptor['part']=='pelvis' and descriptor['joint']=='pelvis_g'
                     and descriptor['model']==contract.model(target,'pelvis') and descriptor['statureApplications']==0
                     and np.array_equal(descriptor['attachmentWorld'],contract.frame(target,'pelvis_g','working'))
                     and np.array_equal(descriptor['candidateToAttachmentLocal'],np.eye(4)),
                     'Working pelvis identity/frozen attachment once required')
    for key in PIN_KEYS:diagnostic.pin(descriptor[key],inputs)
    review=diagnostic.load_item(descriptor['rootReview'],inputs);diagnostic.no_acceptance(review)
    review_fields=(fields-set(FLAGS)-{'rootReview','kind','diagnosticOnly','previewScope'})|{
        'kind','scope','reviewedBy','reviewed','authorizeDiagnosticPreview','pendingGates','pendingRisks','implementation'}
    contract.require(type(review) is dict and set(review)==review_fields,
                     'Exact preview review fields required; broader authorization is unsupported')
    contract.require(review.get('schemaVersion')==2 and review.get('kind')==REVIEW_KIND
                     and review.get('scope')==SCOPE and review.get('reviewedBy')=='/root'
                     and review.get('reviewed') is True and review.get('authorizeDiagnosticPreview') is True
                     and review.get('pendingGates')=={flag:False for flag in FLAGS}
                     and isinstance(review.get('pendingRisks'),list) and bool(review['pendingRisks']),
                     'Concrete root-reviewed preview-only source and pending risks required')
    contract.verify_binding(review,target_path,target,'working')
    contract.require(type(review['implementation']) is dict and set(review['implementation'])==set(IMPLEMENTATION),
                     'Exact reviewed preview implementation pins required')
    for name,item in review['implementation'].items():
        actual=Path(__file__).with_name(name).resolve()
        contract.require(diagnostic.pin(item,inputs)==actual,'Reviewed preview implementation path differs')
    for key in PIN_KEYS:
        contract.require(key in review and material.same_pin(review[key],descriptor[key]),
                         'Preview root review source/audit binding differs: '+key)
    for key in ('part','joint','model','statureApplications','attachmentWorld','candidateToAttachmentLocal'):
        contract.require(review.get(key)==descriptor[key],'Preview root review identity/frame differs: '+key)
    source_path=diagnostic.pin(descriptor['sourceGeometry'],inputs)
    prepared=material.verify_receipt(source_path,target_path,target,descriptor['decodedAudit'],descriptor['footprintAudit'])
    receipt=prepared['receipt'];inputs.update(prepared['inputs'])
    contract.require(material.same_pin(descriptor['sourceCandidate'],{'path':str(prepared['candidate']),
                     'sha256':receipt['candidateSha256']}) and receipt['kind']==basispolicy.KIND
                     and receipt['attachmentWorld']==descriptor['attachmentWorld']
                     and receipt['candidateToAttachmentLocal']==descriptor['candidateToAttachmentLocal'],
                     'Exact material child candidate/frame differs; changed-cap descendants need separate lineage')
    return {'receipt':str(path),'receiptSha256':inputs[str(path)],'receiptKind':KIND,'sourceReceiptKind':receipt['kind'],
            'part':'pelvis','joint':'pelvis_g','model':descriptor['model'],'candidate':str(prepared['candidate']),
            'candidateSha256':receipt['candidateSha256'],'coordinateSpace':'working','statureApplications':0,
            'attachmentAppliedOnce':True,'historicalFitReapplied':False,'diagnosticOnly':True,
            'canonicalNativeLineage':False,'previewScope':SCOPE,'primitiveRoleStatus':{'0':'skin','1':'unowned-neutral-diagnostic-cap','2':'unowned-neutral-diagnostic-cap',
                                   '3':'garment','4':'skin','5':'garment'},'materialRoles':material.MATERIAL_ROLES,
            'materialBodyPrimitiveGroups':{name:list(ids) for name,ids in material.GROUPS},
            'capMode':material.CAP_MODE,'newCornerShadingPolicy':basispolicy.POLICY_ID,
            'rootReview':descriptor['rootReview'],'pendingGates':{flag:False for flag in FLAGS},
            'pendingRisks':review['pendingRisks'],'clientEvidence':False,'inputs':inputs}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor',type=Path,required=True);parser.add_argument('--target-contract',type=Path,required=True)
    parser.add_argument('--coordinate-space',choices=('working','runtime'),required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();target=contract.load(args.target_contract)
    row=verify_preview_descriptor(args.descriptor,args.target_contract,target,args.coordinate_space)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'validation.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({'validation':str((args.output/'validation.json').resolve()),'candidate':row['candidate'],'diagnosticOnly':True}))
if __name__=='__main__':main()