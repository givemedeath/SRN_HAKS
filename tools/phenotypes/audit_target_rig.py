"""Independently verify serialized target rigs and measure stock diagnostic motion.

The report proves offline transforms only. Native compiler bounds, visible
articulation, equipment fit, engine stride behavior and client acceptance remain
separate gates.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import numpy as np

from retarget import NODE, nodes, signature, rotations, transforms
from rig_controller_audit import (CLIP, arrays, effective_nodes, world_frames,
    compatible_parent_basis, preserved_controller_signature)
from rig_pose_audit import sample, inherited_clips
from target_contract import load, require, sha


def find_bind(key, owner, geometry, parents, fallback):
    seen=set()
    while owner!='null':
        require(owner not in seen,'Supermodel inheritance cycle')
        seen.add(owner)
        require(owner in geometry and owner in parents,'Missing source/target bind owner')
        if key in geometry[owner]:
            return geometry[owner][key],owner
        owner=parents[owner]
    require(key in fallback,'Unresolved source/target bind: '+key)
    return fallback[key],'phenotype-root-fallback'


def geometry_array(body,label):
    match=re.search(r'(?mi)^\s*'+re.escape(label)+r'\s+(\d+)[ \t]*\n',body)
    if not match:
        return None
    lines=body[match.end():].splitlines()[:int(match[1])]
    require(len(lines)==int(match[1]),'Truncated geometry array')
    return np.asarray([[float(v) for v in line.split()] for line in lines])


def close(actual,expected,message,tolerance=1e-9):
    actual,expected=np.asarray(actual),np.asarray(expected)
    require(actual.shape==expected.shape and np.isfinite(actual).all(),message+' shape/nonfinite')
    error=float(np.max(np.abs(actual-expected))) if actual.size else 0.
    require(error<=tolerance,message+' max error '+str(error))
    return error


def audit(candidate):
    contract_path=candidate/'target-contract.json'
    contract=load(contract_path)
    receipt=json.loads((candidate/'rig-export.json').read_text())
    require(receipt['targetContractSha256']==sha(contract_path),'Contract receipt hash mismatch')
    source=candidate/'source-inputs'
    inventory=json.loads((source/'baseline.json').read_text())
    aliases=contract['rig']['privateAliases']; chain=list(aliases)
    parents={name:inventory['animations'][name]['supermodel'] for name in chain}
    source_texts={name:(source/'ascii'/(name+'.mdl')).read_text(encoding='cp1252') for name in chain}
    source_geometry={name:nodes(text) for name,text in source_texts.items()}
    source_root=source_geometry[chain[0]]
    raw_count=0
    for entry in inventory['resources']:
        for directory,field in [('raw','sha256'),('ascii','asciiSha256')]:
            path=source/directory/entry['name']
            if path.exists():
                require(sha(path)==entry[field],'Extraction receipt source hash mismatch: '+str(path))
                raw_count+=directory=='raw'
    report={'schemaVersion':1,'kind':'target-rig-independent-audit',
        'targetContractSha256':sha(contract_path),'rigExportSha256':sha(candidate/'rig-export.json'),
        'sourceNativeFilesChecked':raw_count,'spaces':{},'positionBezierControllers':0,
        'clientEvidence':False,'pilotAccepted':False,'nativeBoundsAccepted':False,
        'strideBehaviorAccepted':False}
    target_parents={aliases[name]:aliases.get(parent,'null') for name,parent in parents.items()}
    all_target_texts={}
    for space,factor in [('working',1.),('runtime',contract['rig']['runtimeScale'])]:
        target_texts={name:(candidate/space/'ascii'/(aliases[name]+'.mdl')).read_text() for name in chain}
        all_target_texts[space]=target_texts
        target_geometry={aliases[name]:nodes(text) for name,text in target_texts.items()}
        target_root=target_geometry[aliases[chain[0]]]
        summary={'models':[],'clips':0,'nodes':0,'positionKeyRows':0,'rotationKeyRows':0,
                 'inheritedBindings':0,'sourceBindDiffersFromTarget':0,'maxPositionError':0.,
                 'maxParentBasisError':0.,'parentMappings':{},'bounds':{}}
        for name in chain:
            source_text,target_text=source_texts[name],target_texts[name]
            alias=aliases[name]
            target_supermodel=re.search(r'(?mi)^setsupermodel\s+\S+\s+(\S+)',target_text)
            require(target_supermodel and target_supermodel[1].lower()==
                    aliases.get(parents[name],'null'),'Private inheritance chain changed')
            model_pin=next(pin for pin in receipt['models'] if pin['space']==space and pin['source']==name)
            require(sha(candidate/space/'ascii'/(alias+'.mdl'))==model_pin['sha256'],'Model receipt hash mismatch')
            require(signature(source_text)==signature(target_text),'Timing/events changed')
            require(preserved_controller_signature(source_text,aliases)==
                    preserved_controller_signature(target_text),'Rotation/nonpositional controller ownership changed')
            for label,text in [('source',source_text),('target',target_text)]:
                scale=re.search(r'(?mi)^setanimationscale\s+(\S+)',text)
                require(scale and float(scale[1])==1.,label+' animation scale must be exactly one')
            source_effective=effective_nodes(name,source_geometry,parents,source_root)
            target_effective=effective_nodes(alias,target_geometry,target_parents,target_root)
            source_frames=world_frames(source_effective); target_frames=world_frames(target_effective)
            source_geom_matches=list(NODE.finditer(source_text.split('endmodelgeom',1)[0]))
            target_geom_matches=list(NODE.finditer(target_text.split('endmodelgeom',1)[0]))
            require(len(source_geom_matches)==len(target_geom_matches),'Geometry node ownership/count changed')
            for original,converted in zip(source_geom_matches,target_geom_matches):
                key=original[2].lower(); target_key=aliases.get(key,key)
                require(converted[1]==original[1] and converted[2].lower()==target_key,'Geometry type/owner changed')
                old=source_geometry[name][key]; new=target_geometry[alias][target_key]
                old_scale=re.findall(r'(?mi)^\s*scale\s+(\S+)',original[3])
                new_scale=re.findall(r'(?mi)^\s*scale\s+(\S+)',converted[3])
                require(old_scale==new_scale and all(float(value)==1. for value in old_scale),
                        'Non-unit or changed geometry-node scale invalidates rigid frame audit')
                expected=(np.asarray(contract['rig']['targetWorkingBindLocal'][key])*factor
                          if key in contract['rig']['targetWorkingBindLocal'] else old['position']*factor)
                close(new['position'],expected,'Geometry bind must scale exactly once')
                expected_rotation=(source_root[key]['orientation'] if key in source_root else old['orientation'])
                close(rotations(new['orientation']),rotations(expected_rotation),'Target Human-derived bind rotation')
                if key in source_root and key!='pmh0':
                    expected_parent=aliases.get(source_root[key]['parent'],source_root[key]['parent'])
                    if expected_parent==aliases[chain[0]]:
                        expected_parent=alias
                    require(new['parent']==expected_parent,'Target Human-derived hierarchy changed')
                for field in ('verts','tverts','normals','faces','colors','tangents'):
                    before,after=geometry_array(original[3],field),geometry_array(converted[3],field)
                    require((before is None)==(after is None),'Geometry attribute presence changed: '+field)
                    if before is None:
                        continue
                    close(after,before*factor if field=='verts' else before,'Geometry '+field+' changed')
                    if field=='verts' and len(after):
                        summary['bounds'][alias+'/'+target_key]={'minimum':after.min(axis=0).tolist(),
                            'maximum':after.max(axis=0).tolist(),'vertices':len(after)}
                for field in ('bitmap','materialname','texture0','texture1','texture2','texture3'):
                    before=re.findall(r'(?mi)^\s*'+field+r'\s+([^\n]+)',original[3])
                    after=re.findall(r'(?mi)^\s*'+field+r'\s+([^\n]+)',converted[3])
                    require(before==after,'Geometry texture/material binding changed')
            original_clips=list(CLIP.finditer(source_text)); converted_clips=list(CLIP.finditer(target_text))
            require(len(original_clips)==len(converted_clips),'Clip ownership changed')
            for original_clip,converted_clip in zip(original_clips,converted_clips):
                def clip_metadata(body):
                    stripped=NODE.sub('',body)
                    for original,private in aliases.items():
                        stripped=re.sub(r'(?i)\b'+re.escape(original)+r'\b',private,stripped)
                    return [tuple(line.split()) for line in stripped.splitlines()
                            if line.strip() and not line.strip().startswith('#')]
                require(clip_metadata(original_clip[2])==clip_metadata(converted_clip[2]),
                        'Animation root, metadata, timing or event ownership changed')
                original_nodes=list(NODE.finditer(original_clip[2]));converted_nodes=list(NODE.finditer(converted_clip[2]))
                for old_node,new_node in zip(original_nodes,converted_nodes):
                    key=old_node[2].lower();target_key=aliases.get(key,key)
                    source_bind,source_owner=find_bind(key,name,source_geometry,parents,source_root)
                    target_bind,target_owner=find_bind(target_key,alias,target_geometry,target_parents,target_root)
                    source_parent=re.search(r'(?mi)^\s*parent\s+(\S+)',old_node[3])[1].lower()
                    target_parent=re.search(r'(?mi)^\s*parent\s+(\S+)',new_node[3])[1].lower()
                    require(source_parent==source_bind['parent'],'Source animation parent/bind mismatch')
                    require(target_parent==target_bind['parent'],'Target animation parent/bind mismatch')
                    if aliases.get(source_parent,source_parent)!=target_parent:
                        summary['parentMappings'][name+'/'+key]={'source':source_parent,'target':target_parent}
                    spatial=bool(re.search(r'(?mi)^\s*(position(?:bezier)?key|position|orientation(?:bezier)?key|orientation)\s',old_node[3]))
                    if spatial:
                        error=compatible_parent_basis(source_bind,target_bind,source_frames,target_frames)
                        summary['maxParentBasisError']=max(summary['maxParentBasisError'],error)
                    summary['nodes']+=1
                    summary['inheritedBindings']+=source_owner!=name
                    summary['sourceBindDiffersFromTarget']+=not np.allclose(
                        target_bind['position'],source_bind['position']*factor,atol=1e-9,rtol=0)
                    original_arrays=arrays(old_node[3]);converted_arrays=arrays(new_node[3])
                    require(len(original_arrays)==len(converted_arrays),'Controller array count changed')
                    for (label,old_values,_,_), (new_label,new_values,_,_) in zip(original_arrays,converted_arrays):
                        require(new_label==label,'Controller order changed')
                        if label=='positionbezierkey':
                            report['positionBezierControllers']+=1
                            raise ValueError('No native Bezier semantics receipt supplied to this independent audit')
                        if label=='positionkey':
                            require(np.array_equal(np.asarray(old_values)[:,0],np.asarray(new_values)[:,0]),
                                    'Position key timing changed')
                            expected=[]
                            for row in old_values:
                                require(len(row)==4,'Invalid linear position arity')
                                expected.append([row[0]]+[target_bind['position'][i]+
                                    factor*(row[i+1]-source_bind['position'][i]) for i in range(3)])
                            error=close(new_values,expected,'Bind-relative controller scale applied once')
                            summary['maxPositionError']=max(summary['maxPositionError'],error)
                            summary['positionKeyRows']+=len(old_values)
                        else:
                            require(old_values==new_values,'Nonpositional key data changed')
                            summary['rotationKeyRows']+=len(old_values) if label.startswith('orientation') else 0
                    old_static=re.search(r'(?mi)^\s*position\s+([^\n]+)',old_node[3])
                    if old_static:
                        new_static=re.search(r'(?mi)^\s*position\s+([^\n]+)',new_node[3])
                        require(new_static is not None,'Static position removed')
                        values=[float(v) for v in old_static[1].split()]
                        close([float(v) for v in new_static[1].split()],
                            [target_bind['position'][i]+factor*(values[i]-source_bind['position'][i]) for i in range(3)],
                            'Static controller scale applied once')
            summary['clips']+=len(original_clips)
            summary['models'].append({'source':name,'target':alias,'sha256':model_pin['sha256'],
                                     'clipCount':len(original_clips)})
        report['spaces'][space]=summary
    source_clips=inherited_clips(chain,source_texts)
    working_clips=inherited_clips(chain,all_target_texts['working'])
    runtime_clips=inherited_clips(chain,all_target_texts['runtime'])
    report['poseSamples']=[]
    report['sockets']={}
    root_working=nodes(all_target_texts['working'][chain[0]])
    root_runtime=nodes(all_target_texts['runtime'][chain[0]])
    factor=contract['rig']['runtimeScale']
    sockets=['rhand','lhand','head','headconjure','handconjure','impact','wings','cloak_g','tail']
    bind_working=transforms(root_working);bind_runtime=transforms(root_runtime)
    for key in sockets:
        require(key in bind_working,'Required auxiliary socket missing: '+key)
        close(bind_runtime[key][:3,3],bind_working[key][:3,3]*factor,'Socket scale applied once')
        close(bind_runtime[key][:3,:3],bind_working[key][:3,:3],'Socket bind axes preserved')
        report['sockets'][key]={'workingPosition':bind_working[key][:3,3].tolist(),
                              'runtimePosition':bind_runtime[key][:3,3].tolist()}
    from build_target_diagnostic import convert_part,points
    part_texts={side:(source/'ascii'/('pmh0_foot'+side+'001.mdl')).read_text(encoding='cp1252') for side in ('l','r')}
    scaled_parts={side:convert_part(text,'pmh0_foot'+side+'001','pmg0_foot'+side+'001',factor) for side,text in part_texts.items()}
    for clip_name in ['pause1','pause2','walk','run','conjure1','kneel','deadfnt']:
        require(clip_name in source_clips,'Required diagnostic clip missing: '+clip_name)
        left,right=working_clips[clip_name],runtime_clips[clip_name]
        row={'clip':clip_name,'sourceOwner':source_clips[clip_name]['owner'],
             'sourceClipSha256':hashlib.sha256(source_clips[clip_name]['text'].encode()).hexdigest(),
             'length':left['length'],'samples':[]}
        require(left['length']==right['length'],'Sample clip length changed')
        for fraction in np.linspace(0,1,9):
            time=left['length']*fraction
            working_pose=sample(root_working,left['body'],time)
            runtime_pose=sample(root_runtime,right['body'],time)
            maximum=0.
            for key in working_pose:
                maximum=max(maximum,close(runtime_pose[key][:3,3],working_pose[key][:3,3]*factor,
                                          'Sampled joint world scale applied once'))
                close(runtime_pose[key][:3,:3],working_pose[key][:3,:3],'Sampled rotations preserved')
            soles={}
            for side in ('l','r'):
                joint=('l' if side=='l' else 'r')+'foot_g'
                working_points=points(part_texts[side],working_pose[joint])
                runtime_points=points(scaled_parts[side],runtime_pose[joint])
                close(runtime_points,working_points*factor,'Sampled sole geometry scale applied once')
                soles[side]={'workingMinimumZ':float(working_points[:,2].min()),
                             'runtimeMinimumZ':float(runtime_points[:,2].min())}
            row['samples'].append({'time':float(time),'maxWorldScaleError':maximum,'soleMinimum':soles})
        report['poseSamples'].append(row)
    require(report['poseSamples'][0]['sourceClipSha256']!=report['poseSamples'][1]['sourceClipSha256'],
            'PAUSE1 and PAUSE2 evidence must be independently sampled')
    report['strideMetadata']={'source':'Installed appearance.2da row6 and row2; no automatic table mutation',
        'sourceAppearanceSha256':sha(source/'raw/appearance.2da') if (source/'raw/appearance.2da').exists() else None,
        'runtimeScale':factor,'tableWalkRunCollisionValuesAccepted':False,
        'note':'Native movement uses table distances and engine behavior; offline foot trajectory is insufficient acceptance.'}
    table=source/'raw/appearance.2da'
    if table.exists():
        lines=[line.split() for line in table.read_text(encoding='cp1252').splitlines()
               if line.strip()]
        header=next(row for row in lines if row[0]=='LABEL')
        selected_fields=('WALKDIST','RUNDIST','MOVERATE','PERSPACE','CREPERSPACE',
                         'HEIGHT','HITDIST','SIZECATEGORY','WEAPONSCALE','HELMET_SCALE_M')
        report['strideMetadata']['installedRows']={}
        for number in ('2','5','6'):
            values=next(row for row in lines if row[0]==number)[1:]
            report['strideMetadata']['installedRows'][number]={field:values[header.index(field)]
                                                               for field in selected_fields}
        report['strideMetadata']['initialScaledHumanDistances']={
            field:float(report['strideMetadata']['installedRows']['6'][field])*factor
            for field in ('WALKDIST','RUNDIST')}
    report['verified']=True
    report['nonunitGeometryNodeScales']=0
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    require(not args.output.exists(),'Fresh audit receipt path required')
    result=audit(args.candidate.resolve())
    snapshot=args.output.parent/('audit-helpers-'+args.output.stem)
    require(not snapshot.exists(),'Fresh audit helper snapshot required')
    snapshot.mkdir()
    result['auditHelpers']={}
    for name in ('audit_target_rig.py','rig_controller_audit.py','rig_pose_audit.py',
                 'retarget.py','target_contract.py','build_target_diagnostic.py'):
        original=Path(__file__).with_name(name);destination=snapshot/name
        shutil.copy2(original,destination)
        result['auditHelpers'][str(destination.resolve())]=sha(destination)
    result['python']={'executable':sys.executable,'version':sys.version,'numpyVersion':np.__version__}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'verified':result['verified'],'spaces':{name:{key:row[key] for key in
        ('clips','nodes','positionKeyRows','rotationKeyRows','inheritedBindings','maxParentBasisError','maxPositionError')}
        for name,row in result['spaces'].items()},'poseClips':len(result['poseSamples']),
        'clientAccepted':False,'sha256':sha(args.output)}))
