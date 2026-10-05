"""One approved working chest002 regional pilot, preserving indexed stock data.

No affine stager or source model is modified. Runtime conversion is separate.
"""
import argparse,json,re,shutil
from pathlib import Path
import numpy as np
import target_contract as tc
from equipment_section_field import evaluate,transport_native_normals,validate_source_correspondence
from stage_target_rigid_equipment import mesh_data
from retarget import nodes,transforms

ARTIFACT_ROOT=Path(__file__).resolve().parents[2]/'output/phenotypes/troll-male-purposebuilt-v1'
SOURCE='pmh0_chest002';TARGET='pmg0_chest002'


def require(v,m):
    if not v:raise ValueError(m)


def array_span(text,key):
    hits=list(re.finditer(r'(?m)^([ \t]*)'+re.escape(key)+r'[ \t]+(\d+)[ \t]*\n',text))
    require(len(hits)==1,'Exactly one source '+key+' table required')
    hit=hits[0];end=hit.end()+sum(len(x) for x in text[hit.end():].splitlines(keepends=True)[:int(hit[2])])
    return hit.start(),end,text[hit.start():end]


def serialize37(source,positions,normals):
    require(np.asarray(positions).shape==np.asarray(normals).shape==(37,3) and np.isfinite(positions).all() and np.isfinite(normals).all(),'Exactly37 finite P/N rows required')
    require(not re.search(r'(?mi)^\s*(normals|tangents|weights)\s+',source),'Original chest002 must have no authored ASCII N/T/skin arrays')
    require(re.search(r'(?mi)^setsupermodel\s+'+SOURCE+r'\s+NULL\s*$',source) is not None,'Source static component supermodel must be NULL')
    rows=mesh_data(source);require(len(rows)==1,'One stock static mesh required');row=next(iter(rows.values()))
    require(len(row['vertices'])==37 and len(row['arrays']['faces'])==70 and len(row['arrays']['tverts'])==51 and np.array_equal(row['frame'],np.eye(4)),'Exact37/70/51 identity normalized source required')
    start,end,original=array_span(source,'verts')
    block='  verts 37\n'+''.join('    '+' '.join(format(float(v),'.17g') for v in p)+'\n' for p in positions)
    normal='  normals 37\n'+''.join('    '+' '.join(format(float(v),'.17g') for v in p)+'\n' for p in normals)
    text=source[:start]+block+normal+source[end:]
    text=text.replace(SOURCE,TARGET)
    # Reverse only the explicitly declared resource/root/bitmap mapping and P/N edit.
    restored=text.replace(TARGET,SOURCE);ns,ne,_=array_span(restored,'normals');restored=restored[:ns]+restored[ne:];vs,ve,_=array_span(restored,'verts');restored=restored[:vs]+original+restored[ve:]
    require(restored==source,'Source material/UV/face/smoothing/bind text changed outside declared P/N and family mapping')
    after=next(iter(mesh_data(text).values()))
    require(after['arrays']==row['arrays'] and np.array_equal(after['frame'],np.eye(4)) and np.array_equal(after['vertices'],positions) and np.array_equal(after['normals'],normals),'Serialized indexed P/N or protected arrays changed')
    return text


def check_approval(config_ref,approval):
    require(approval.get('kind')=='root-approved-regional-equipment-working-pilot' and approval.get('reviewedBy')=='/root','Explicit root regional pilot approval required')
    require(approval.get('configuration')==config_ref and approval.get('authorizeImplementationAndOneFreshWorkingPilot') is True and approval.get('authorizeIndependentNativeCompileAndDecode') is True,'Approval does not authorize this exact config and pilot')
    require(all(approval.get(k) is False for k in ('geometryAccepted','equipmentFitAccepted','collisionAccepted','materialAccepted','clientAccepted','productionAccepted')),'Pilot must remain unaccepted')


def export(config_path,approval_path,target_path,output):
    output=Path(output).resolve()
    require(not output.exists(),'Fresh once-only regional pilot output required')
    require(output.is_relative_to(ARTIFACT_ROOT.resolve()) and output.name.startswith('equipment-chest002-regional-working-pilot-'),'Isolated target equipment output required; source/global/Human/female writes rejected')
    pins={}
    def pin(path,h=None):
        path=Path(path).resolve();v=tc.sha(path);require(h is None or h==v,'Frozen input changed: '+str(path));pins[str(path)]=v;return path
    def ref(path):return {'path':str(Path(path).resolve()),'sha256':tc.sha(path)}
    def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    cp=pin(config_path);config_ref=ref(cp);ap=pin(approval_path);approval=read(ap);check_approval(config_ref,approval);c=read(cp)
    tp=pin(target_path,c['targetContractSha256']);target=tc.load(tp);tc.verify_binding(c,tp,target,'working')
    require(c['kind']=='target-equipment-regional-field-review' and c['part']=='chest' and c['attachmentJoint']=='torso_g' and c['sourceResource']==SOURCE+'.mdl' and c['futureTargetModel']==TARGET+'.mdl' and c['futureTargetPalette']==TARGET+'.plt','Exact source and target chest002 ownership required')
    require(c['statureApplications']==0 and c['fieldConfigurationApproved'] is False and c['actualModelExported'] is False,'Prepared working input must have no adopted field or stature conversion')
    for p,h in c['frozenInputs'].items():pin(p,h)
    source=pin(c['sourceNormalized']['path'],c['sourceNormalized']['sha256']);bank_path=pin(c['sourceArrayBank']['path'],c['sourceArrayBank']['sha256']);a=np.load(bank_path)
    validate_source_correspondence(a['sourcePositions'],a['sourceFaces'],a['sourceUVTable'],a['nativePositions'],a['nativeNormals'],a['nativeUV'],a['nativeFaces'],a['nativePositionOwner'],a['nativeUVOwner'])
    P=a['sourcePositions'];Q,J=evaluate(c['field'],P);N=transport_native_normals(a['nativeNormals'],a['nativePositionOwner'],J);N37=[]
    for i in range(37):
        ids=np.flatnonzero(a['nativePositionOwner']==i);require(np.array_equal(a['nativeNormals'][ids],np.broadcast_to(a['nativeNormals'][ids[0]],(len(ids),3))) and np.array_equal(N[ids],np.broadcast_to(N[ids[0]],(len(ids),3))),'Native normal owner seam ambiguity');N37.append(N[ids[0]])
    N37=np.array(N37);protected=np.asarray(c['protectedExactSourcePositionIds']);require(np.array_equal(Q[protected],P[protected]) and np.array_equal(Q[:,2],P[:,2]) and np.linalg.norm(Q-P,axis=1).max()<=c['positionDisplacementBoundMetres'],'Reviewed protection/physical displacement bound violated')
    source_text=source.read_text(encoding='ascii');text=serialize37(source_text,Q,N37)
    freeze=read(pin(tp.parent/'freeze.json'));owner_models={}
    for m in freeze['modelCopies']:
        if m['space']=='working':
            path=pin(m['destination'],m['sha256']);owner_models[m['model']]=ref(path)
    require(set(owner_models)=={'pmg0',*(f'sr_tmg0_{i:02}' for i in range(1,8))},'Complete private frozen Troll chain required')
    ancestry={}
    for name,row in owner_models.items():
        match=re.search(r'(?mi)^setsupermodel\s+(\S+)\s+(\S+)\s*$',Path(row['path']).read_text());require(match and match[1].lower()==name,'Private supermodel declaration mismatch');parent=match[2].lower();require(parent=='null' or parent in owner_models,'Human/global supermodel inheritance forbidden');ancestry[name]=parent
    for name in ancestry:
        seen=set();cur=name
        while cur!='null':require(cur not in seen,'Private supermodel cycle');seen.add(cur);cur=ancestry[cur]
    actual_frame=transforms(nodes(Path(owner_models['pmg0']['path']).read_text()))['torso_g'];require(np.max(abs(actual_frame-tc.frame(target,'torso_g','working')))<5e-13,'Frozen private torso bind differs from target frame')
    palette=pin(c['sourcePalette']['path'],c['sourcePalette']['sha256']);pin(__file__)
    output.mkdir();(output/'ascii').mkdir();(output/'resources').mkdir();(output/'source-snapshots').mkdir()
    model=output/'ascii'/c['futureTargetModel'];model.write_text(text,encoding='ascii');plt=output/'resources'/c['futureTargetPalette'];shutil.copyfile(palette,plt)
    for path in (source,cp,ap,Path(__file__),Path(c['mathHelper']['path'])):shutil.copyfile(path,output/'source-snapshots'/path.name)
    array=output/'source-correspondent-native-owner-arrays.npz';np.savez_compressed(array,sourceP37=P,workingP37=Q,workingN37=N37,sourceFullFaces=a['sourceFaces'],sourceUVTable=a['sourceUVTable'],sourceNativeP122=a['nativePositions'],sourceNativeN122=a['nativeNormals'],sourceNativeUV122=a['nativeUV'],sourceNativeFaces=a['nativeFaces'],sourcePositionOwner=a['nativePositionOwner'],sourceUVOwner=a['nativeUVOwner'],workingN122=N,jacobian37=J)
    receipt={'schemaVersion':2,'kind':'target-regional-rigid-equipment-working-pilot',**tc.binding(tp,target,'working'),'configuration':config_ref,'rootApproval':ref(ap),'sourceModel':ref(source),'sourceArrayBank':ref(bank_path),'sourcePalette':ref(palette),'targetModel':ref(model),'targetPalette':ref(plt),'sourceOwnerArchive':ref(array),'part':'chest','attachmentJoint':'torso_g','assemblyAttachmentFrameNwn':tc.frame(target,'torso_g','working').tolist(),'componentSupermodel':'NULL','privateRigOwnership':{'engineAssemblyRoot':'pmg0','attachmentOwner':'pmg0','privateModelFiles':owner_models,'supermodelAncestry':ancestry,'componentPolicy':'Stock static body component remainsNULL; private frozen rig owns the assembly attachment and controllers, not component inheritance.'},'sourcePositions':37,'sourceTriangles':70,'sourceUVRows':51,'nativeSourceRows':122,'authoredNormalRows':37,'orderedSourceFaceUVSmoothingAndOtherFieldsExact':True,'sourceNormalOwnerPolicy':'Exact unique native source N per position owner, inverse-J transpose and original magnitude. No averaging/regeneration/tangent invention.','maximumDisplacementMetres':float(np.linalg.norm(Q-P,axis=1).max()),'statureApplications':0,'hierarchyBakesDuringThisExport':0,'attachmentTranslationsBakedIntoModel':0,'geometryAccepted':False,'equipmentFitAccepted':False,'collisionAccepted':False,'materialAccepted':False,'clientAccepted':False,'productionAccepted':False,'knownReviewLimits':c['rootReviewRequired'],'frozenInputs':pins}
    for p,h in pins.items():require(tc.sha(p)==h,'Frozen input changed during pilot export: '+p)
    p=output/'pilot.json';p.write_text(json.dumps(receipt,indent=2)+'\n');return p


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=Path);p.add_argument('--approval',required=True,type=Path);p.add_argument('--target',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();r=export(a.config,a.approval,a.target,a.output);print(json.dumps({'receipt':str(r),'sha256':tc.sha(r)}))


if __name__=='__main__':main()