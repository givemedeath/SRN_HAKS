"""Immutable design preferences, distinct from measurement uncertainty."""
import argparse, hashlib, json, math
from pathlib import Path

def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def pin(path):
    p=Path(path).resolve()
    return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def finite(value): return isinstance(value,(int,float)) and math.isfinite(value)

def measurement_policy(key,row,packet):
    value=row.get('modelFittingMeters')
    if not finite(value) or value<=0:
        return {'preferredMeters':None,'confidence':'unavailable','guideOnly':True,'reason':'No available positive proposed dimension'}
    section=key.removesuffix('Width').removesuffix('Depth').removesuffix('Length')
    width_depth=key.endswith(('Width','Depth')) or key=='footLength'
    uncertainty=row.get('uncertaintyMeters')
    if not finite(uncertainty):
        candidates=[v[key].get('uncertaintyMeters') for v in packet.get('views',{}).values() if key in v]
        uncertainty=max((u for u in candidates if finite(u) and u>=0),default=None)
    evidence=json.dumps(row).lower()
    flags=[]
    if row.get('referenceViewDisagreementFlag') or row.get('referenceRatioAuthority',{}).get('flagOverTwoPercent'):flags.append('view-disagreement')
    if 'garment' in evidence or 'clothed' in evidence:flags.append('garment-surface')
    if 'pose consistency unverified' in evidence or 'provisional' in evidence:flags.append('provisional-or-pose-sensitive')
    if row.get('referenceHumanViewDisagreement',{}).get('flagOverTwoPercent'):flags.append('uncertain-human-denominator')
    confidence='low' if flags else 'medium'
    slack=.10 if width_depth else .05
    return {'preferredMeters':float(value),'designSlackFraction':slack,'designSlackMeters':slack*value,
            'measurementUncertaintyMeters':uncertainty,'confidence':confidence,
            'confidenceWeight':.35 if confidence=='low' else .7,'guideOnly':False,
            'preferenceIsNotEqualityConstraint':True,'uncertaintyWasWidened':False,
            'designPreferredRangeMeters':[value*(1-slack),value*(1+slack)],'evidenceFlags':flags}

def for_target(packet):
    identity=packet['slug'] in ('human_male_fit','human_female_fit')
    return {'kind':'anatomy-first-fitting-policy-v15','version':15,'target':packet['slug'],
      'referenceRole':'proportion-and-size-guide','preserveExactHumanFit':identity,
      'priority':['geometry-joints-and-natural-motion','race-gender-build-character','stature-and-broad-proportions','individual-reference-measurements'],
      'targetStatureMeters':packet['targetStatureMeters'],'maximumDerivedStatureErrorFraction':.01,
      'measurements':{k:measurement_policy(k,v,packet) for k,v in packet.get('proposedTargets',{}).items() if isinstance(v,dict)},
      'stage1':{'bilateralScaleMultipliers':True,'nativeMotionDefault':True,'previewIKDefault':False,'referenceLandmarksAreSoft':True},
      'morph':{'input':'fresh frozen stage1','passCount':1,'regionalBackoff':True,'preserveLimbCenterlines':True,'sourceEndpointRestoreAfterMorph':False},
      'manualCleanup':{'allowed':True,'topologyChanges':False,'layerMustBeReproducible':True},
      'approvalScope':{'referenceApprovalInheritedOnlyForExactHumanFits':identity,'candidateValidated':False,'nativeValidated':False,'clientValidated':False,'productionAccepted':False}}

def build(targets,extras,freeze,output):
    output=Path(output).resolve()
    if output.exists():raise ValueError('Fresh immutable policy directory required')
    inputs={}
    def consume(p,expected=None):
        row=pin(p)
        if expected and row['sha256']!=expected:raise ValueError('Changed source '+row['path'])
        if row['path'] in inputs and inputs[row['path']]!=row['sha256']:raise ValueError('Input changed')
        inputs[row['path']]=row['sha256'];return Path(row['path'])
    f=read(consume(freeze))
    for p in f['protectedInputs']:consume(p['path'],p['sha256'])
    packets={}
    for index_path in (targets,extras):
        if not index_path:continue
        path=consume(index_path);index=read(path)
        for row in index['entries']:
            p=consume(path.parent/row['path'],row['sha256']);packet=read(p)
            if packet['slug']!=row['slug']:raise ValueError('Packet identity mismatch')
            packets[row['slug']]=(p,packet)
    if len(packets)!=20:raise ValueError('Exactly20 existing target guides required')
    output.mkdir(parents=True);entries=[]
    for slug,(path,packet) in sorted(packets.items()):
        policy=for_target(packet);policy['sourcePacket']=pin(path);p=output/(slug+'.json')
        p.write_text(json.dumps(policy,indent=2)+'\n',encoding='utf-8');entries.append({'slug':slug,**pin(p)})
    for p,h in inputs.items():
        if pin(p)['sha256']!=h:raise ValueError('Source changed before policy completion')
    result={'kind':'anatomy-first-policy-index-v15','entries':entries,'parentFreeze':pin(freeze),
            'rejected':'v14f pelvis-only endpoint restoration','unfinishedAndNotSelected':'v14g',
            'inputs':[{'path':p,'sha256':h} for p,h in sorted(inputs.items())],'frozenInputsUnchanged':True,'assetApprovalCreated':False}
    (output/'policy-index.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'targets':len(entries),'output':str(output),'policyIndex':pin(output/'policy-index.json')}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('targets','parent-freeze','output'):p.add_argument('--'+k,required=True)
    p.add_argument('--extra-targets');a=p.parse_args();build(a.targets,a.extra_targets,a.parent_freeze,a.output)
