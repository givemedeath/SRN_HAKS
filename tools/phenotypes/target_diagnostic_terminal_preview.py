"""Separate preview-only consumer of the reviewed 35mm pelvis terminal child.

This never substitutes the child into the original literal-cap material kind.
Full validation runs with workspace Python; Blender may consume its pinned row.
"""
import argparse, copy, json
from pathlib import Path
import numpy as np
import target_contract as tc
import target_diagnostic_lineage as diagnostic
import target_diagnostic_uv_material_preview as parent_preview
import diagnostic_pelvis_terminal as terminal

KIND='target-diagnostic-terminal-preview'
REVIEW_KIND='target-diagnostic-terminal-preview-root-review'
SCOPE='offline-working-diagnostic-terminal-preview'
FLAGS=diagnostic.FLAGS
PINS=('sourceGeometry','sourceCandidate','independentAudit','parentMaterialPreview')
IMPLEMENTATION=('target_diagnostic_terminal_preview.py','test_target_diagnostic_terminal_preview.py',
                'diagnostic_pelvis_terminal.py','pose_preview.py','pose_preview_target_parts.py')

def same_pin(a,b):
    return Path(a['path']).resolve()==Path(b['path']).resolve() and a['sha256']==b['sha256']

def verify_preview_descriptor(path,target_path,target,space='working'):
    path=Path(path).resolve();d=json.loads(path.read_text());inputs={str(path):tc.sha(path)}
    common=set(tc.binding(target_path,target,'working'))|{'schemaVersion','part','joint','model',
        'statureApplications','attachmentWorld','candidateToAttachmentLocal'}|set(PINS)
    fields=common|{'kind','previewScope','diagnosticOnly','rootReview'}|set(FLAGS)
    tc.require(set(d)==fields and space=='working' and d.get('schemaVersion')==2
               and d.get('kind')==KIND and d.get('previewScope')==SCOPE and d.get('diagnosticOnly') is True,
               'Separate typed working terminal preview descriptor required')
    tc.verify_binding(d,target_path,target,'working');diagnostic.no_acceptance(d)
    tc.require(all(d[k] is False for k in FLAGS),'All terminal preview gates remain false')
    tc.require(target['rig'].get('offlineStructureAccepted') is True
               and target['rig'].get('pilotAcceptanceScope')=='offline-rig-structure',
               'Frozen offline structure required')
    tc.require(d['part']=='pelvis' and d['joint']=='pelvis_g' and d['model']==tc.model(target,'pelvis')
               and d['statureApplications']==0 and np.array_equal(d['attachmentWorld'],tc.frame(target,'pelvis_g','working'))
               and np.array_equal(d['candidateToAttachmentLocal'],np.eye(4)),
               'Exact frozen pelvis attachment once; no fit or stature application')
    for key in PINS:diagnostic.pin(d[key],inputs)
    review=diagnostic.load_item(d['rootReview'],inputs);diagnostic.no_acceptance(review)
    review_fields=common|{'kind','scope','reviewedBy','reviewed','authorizeDiagnosticPreview','pendingGates','pendingRisks','implementation'}
    tc.require(set(review)==review_fields and review.get('kind')==REVIEW_KIND
               and review.get('scope')==SCOPE and review.get('reviewedBy')=='/root'
               and review.get('reviewed') is True and review.get('authorizeDiagnosticPreview') is True
               and review.get('pendingGates')=={k:False for k in FLAGS}
               and isinstance(review.get('pendingRisks'),list) and bool(review['pendingRisks']),
               'Explicit narrow root preview review required')
    tc.verify_binding(review,target_path,target,'working')
    for key in common:
        tc.require(same_pin(review[key],d[key]) if key in PINS else review[key]==d[key],
                   'Terminal review binding differs: '+key)
    tc.require(set(review['implementation'])==set(IMPLEMENTATION),'Exact terminal preview implementation closure')
    for name,item in review['implementation'].items():
        tc.require(diagnostic.pin(item,inputs)==Path(__file__).with_name(name).resolve(),'Reviewed implementation path differs')
    audit=diagnostic.load_item(d['independentAudit'],inputs);diagnostic.no_acceptance(audit)
    tc.require(audit.get('kind')=='independent-decoded-pelvis-terminal-shortening35-audit' and audit.get('passed') is True
               and same_pin(audit['receipt'],d['sourceGeometry']) and same_pin(audit['candidate'],d['sourceCandidate'])
               and audit.get('statureApplications')==0 and audit.get('capRoundMetres')==0
               and audit.get('originalIndexUVMaterialMapsAndSourceCornerRecordsExact') is True
               and audit.get('coordinateWeldGraphIsomorphismProved') is True,
               'Successful independent exact-child terminal proof required')
    for source,expected in audit['frozenInputs'].items():diagnostic.pin({'path':source,'sha256':expected},inputs)
    parent=parent_preview.verify_preview_descriptor(d['parentMaterialPreview']['path'],target_path,target,'working')
    prepared=terminal.verify_receipt(d['sourceGeometry']['path'],target_path,target,'working');r=prepared['receipt']
    diagnostic.no_acceptance(r);inputs.update(parent['inputs']);inputs.update(prepared['inputs'])
    tc.require(r['kind']==terminal.KIND and r['operation']==terminal.OPERATION
               and same_pin(d['sourceCandidate'],{'path':str(prepared['candidate']),'sha256':r['candidateSha256']})
               and same_pin(r['parentCandidate'],{'path':parent['candidate'],'sha256':parent['candidateSha256']})
               and same_pin(r['parentMaterialGeometryReceipt'],json.loads(Path(d['parentMaterialPreview']['path']).read_text())['sourceGeometry'])
               and r['attachmentWorld']==d['attachmentWorld'] and r['candidateToAttachmentLocal']==d['candidateToAttachmentLocal'],
               'Exact typed child/fully validated original material-parent association required')
    for key in ('bodyFloat64DeformedCornerArchive','generatedCapDeformedCornerArchive'):diagnostic.pin(r[key],inputs)
    inventory=prepared['primitiveInventory']
    tc.require([x['primitive'] for x in inventory]==list(range(6))
               and [x['material'] for x in inventory]==[0,1,1,2,0,2]
               and [x['faces'] for x in inventory]==list(terminal.COUNTS),'Exact six primitive roles/counts')
    row=copy.deepcopy(parent)
    row.update(receipt=str(path),receiptSha256=inputs[str(path)],receiptKind=KIND,sourceReceiptKind=terminal.KIND,
               candidate=str(prepared['candidate']),candidateSha256=r['candidateSha256'],previewScope=SCOPE,
               rootReview=d['rootReview'],parentMaterialPreview=d['parentMaterialPreview'],sourceGeometry=d['sourceGeometry'],
               independentTerminalAudit=d['independentAudit'],capMode='deformed-unowned-neutral-gray-generated-shading',
               capShadingPolicy=r['capShadingPolicy'],terminalOperation=r['operation'],liftMetres=.035,capRoundMetres=0.,
               pendingRisks=review['pendingRisks'],inputs=inputs)
    return row

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--descriptor',type=Path,required=True)
    p.add_argument('--target-contract',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();row=verify_preview_descriptor(a.descriptor,a.target_contract,tc.load(a.target_contract))
    a.output.mkdir(parents=True,exist_ok=False);out=a.output/'validation.json';out.write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({'validation':str(out.resolve()),'sha256':tc.sha(out),'candidate':row['candidate']}),flush=True)
if __name__=='__main__':main()
