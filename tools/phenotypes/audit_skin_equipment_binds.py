"""Audit robe/cloak skin bind ownership separately from rigid Armory output.

The point transform is a bind-relative weighted conversion in one declared
coordinate space. Resource export remains blocked until all bone owners and
model-local overrides are reviewed against the accepted target rig.
"""
import argparse
import json
from pathlib import Path
import re
import numpy as np
from armory_rigid import rigid_frames
from audit_geometry import arrays
from pipeline import digest, save_json
from retarget import NODE
import target_contract


def parse_weights(body, count):
    found=re.search(r'(?mi)^\s*weights\s+(\d+)\s*\n',body)
    if not found or int(found[1])!=count:raise RuntimeError('Skin weight/vertex counts differ')
    rows=body[found.end():].splitlines()[:count]
    result=[]
    for row in rows:
        cells=row.split()
        if len(cells)%2 or not cells:raise RuntimeError('Skin weights must contain bone-name/weight pairs')
        pairs=[(cells[index].lower(),float(cells[index+1])) for index in range(0,len(cells),2)]
        if any(not np.isfinite(weight) or weight<0 for _,weight in pairs):raise RuntimeError('Invalid skin weight')
        if abs(sum(weight for _,weight in pairs)-1)>1e-5:raise RuntimeError('Unnormalized skin weights')
        result.append(pairs)
    return result


def retarget_skin_points(points, weights, source_frames, target_frames, displacement_scale):
    points=np.asarray(points,float)
    if points.ndim!=2 or points.shape[1]!=3 or len(points)!=len(weights) or not np.isfinite(points).all():
        raise RuntimeError('Skin positions and weights must correspond one-to-one')
    if not np.isfinite(displacement_scale) or displacement_scale<=0:raise RuntimeError('Positive skin displacement scale required')
    for bank in (source_frames,target_frames):
        for name,frame in bank.items():
            frame=np.asarray(frame,float)
            if frame.shape!=(4,4) or not np.isfinite(frame).all() or not np.allclose(frame[3],[0,0,0,1],atol=1e-12,rtol=0):
                raise RuntimeError('Invalid skin bind frame: '+name)
            rotation=frame[:3,:3]
            if not np.allclose(rotation.T@rotation,np.eye(3),atol=1e-8,rtol=0) or abs(np.linalg.det(rotation)-1)>1e-8:
                raise RuntimeError('Skin bind frame must be proper/rigid: '+name)
    output=np.zeros_like(points)
    for index,row in enumerate(weights):
        if not row or any(not np.isfinite(weight) or weight<0 for _,weight in row) or abs(sum(weight for _,weight in row)-1)>1e-5:
            raise RuntimeError('Invalid skin weights at vertex '+str(index))
        for bone,weight in row:
            if weight==0:continue
            if bone not in source_frames or bone not in target_frames:raise RuntimeError('Unresolved skin bind: '+bone)
            source,target=np.asarray(source_frames[bone]),np.asarray(target_frames[bone])
            relative=source[:3,:3].T@(points[index]-source[:3,3])
            output[index]+=weight*(target[:3,3]+displacement_scale*(target[:3,:3]@relative))
    return output


def audit(args):
    inventory=json.loads(args.inventory.read_text())
    target=target_contract.load(args.target_contract)
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    bank=json.loads(args.target_bind_bank.read_text()) if args.target_bind_bank else None
    if bank and (bank.get('targetContractSha256')!=digest(args.target_contract) or bank.get('rigRevision')!=target['rig']['revision']):
        raise RuntimeError('Private equipment bind bank belongs to another target revision')
    records=[];frozen={str(args.inventory.resolve()):digest(args.inventory),str(args.target_contract.resolve()):digest(args.target_contract)}
    if bank:frozen[str(args.target_bind_bank.resolve())]=digest(args.target_bind_bank)
    for entry in inventory['models']:
        if entry['part'] not in ('robe','cloak'):continue
        path=Path(entry['asciiPath'])
        if digest(path)!=entry['asciiSha256']:raise RuntimeError('Skin equipment source changed: '+path.name)
        frozen[str(path.resolve())]=digest(path)
        text=path.read_text(encoding='ascii');failures=[];skins=[]
        try:_,_,source_frames=rigid_frames(text)
        except RuntimeError as exc:source_frames={};failures.append(str(exc))
        for block in NODE.finditer(text.split('endmodelgeom')[0]):
            if block[1].lower()!='skin':continue
            count=len(arrays(block[3],'verts'))
            try:weights=parse_weights(block[3],count)
            except RuntimeError as exc:failures.append(block[2]+': '+str(exc));continue
            bones=sorted(set(bone for row in weights for bone,weight in row if weight>0))
            unresolved=[bone for bone in bones if bone not in source_frames]
            candidates=bank['spaces']['working'].get(entry['supermodel'].lower(),{}).get('nodes',{}) if bank else {}
            pending=[bone for bone in bones if bone not in candidates]
            owners=[]
            for bone in bones:
                owners.append({'bone':bone,'sourceFrameNwn':source_frames[bone].tolist() if bone in source_frames else None,
                    'sourceOwner':'equipment-model-local' if bone in source_frames else None,
                    'targetCoreFramePresent':bone in target['rig']['frames']['working'],
                    'targetCandidateOwner':candidates[bone]['owner'] if bone in candidates else None,
                    'targetCandidateFrameNwn':candidates[bone]['worldFrame'] if bone in candidates else None,
                    'targetOverrideReviewed':False})
            skins.append({'node':block[2],'vertices':count,'boneOwners':owners,'sourceMissingBones':unresolved,
                          'targetEffectiveChainMissingBones':pending,'sourceAsciiSha256':digest(path),
                          'modelLocalOverridesReviewed':False,'readyToExport':False})
            if unresolved:failures.append('Unresolved source weighted bones: '+','.join(unresolved))
        records.append({'resource':entry['resource'],'sourceSha256':entry['asciiSha256'],
                        'supermodel':entry['supermodel'],'skins':skins,'sourceFailures':failures,
                        'sourceType':'weighted-skin' if skins else 'robe-or-cloak-hierarchy-without-skin',
                        'privateInheritanceAccepted':False,'profilesAccepted':False})
    result={'schemaVersion':1,'kind':'target-skin-equipment-bind-audit',
            **target_contract.binding(args.target_contract,target,'working'),
            'inventorySha256':digest(args.inventory),'frozenInputHashes':frozen,'models':records,
            'sourceFailureCount':sum(len(row['sourceFailures']) for row in records),
            'unresolvedTargetBoneCount':sum(len(skin['targetEffectiveChainMissingBones']) for row in records for skin in row['skins']),
            'targetBindBankSha256':digest(args.target_bind_bank) if bank else None,
            'pendingModelLocalOverrideReview':True,'rigPilotAccepted':target['rig'].get('pilotAccepted',False),
            'profilesAccepted':False,'clientAccepted':False,
            'requirements':['Resolve every positive weighted bone to an explicit source and target owner in the matching effective private chain.',
                            'Preserve weights, UVs and topology; native compilation must reconstruct and independently verify skin bind arrays.',
                            'Apply displacement scale once; do not pass weighted meshes through rigid Armory flattening.',
                            'Review bound robe and cloak motion, body visibility and collisions after the rig pilot freezes.']}
    save_json(output/'bind-audit.json',result)
    print(json.dumps({'models':len(records),'skinMeshes':sum(len(row['skins']) for row in records),
                      'sourceFailures':result['sourceFailureCount'],'unresolvedTargetBones':result['unresolvedTargetBoneCount'],'profilesAccepted':False}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('inventory','target-contract','output'):parser.add_argument('--'+field,type=Path,required=True)
    parser.add_argument('--target-bind-bank',type=Path)
    audit(parser.parse_args())


if __name__=='__main__':main()
