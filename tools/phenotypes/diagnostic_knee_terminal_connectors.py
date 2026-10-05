"""Two explicit local working knee trials; original consumers remain closed."""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
import target_contract as tc
from place_purposebuilt_pelvis import BASIS,accessor,read_glb,write_glb,embedded_maps
from diagnostic_axis_radial import append_attributes,TOPOLOGY_KEYS
from conservative_face_selection import topology
from diagnostic_shin_girth90 import verify_receipt as verify_shin
from diagnostic_thigh_proximal_one_sided import verify_receipt as verify_thigh

SCOPE='offline-working-local-knee-terminal-diagnostic-v1'
KINDS={'shinl':'target-part-diagnostic-rounded-upper-shin-connector','legl':'target-part-diagnostic-distal-thigh-ridge'}
PARENT_SHA={'shinl':'1e141fc3c64aa0df228c2f3cb3f589c60e267445ea20318936a857373309420b','legl':'0d9a6cb0cb6f23abeba8cb564aab795ed74a596c2b09576582e02d52ee040175'}
CANDIDATE_SHA={'shinl':'77b6c11eb243e6d984fc390e8ac292083242d3933d5df730db82d1347a98b560','legl':'888c919e8d0039899c5de44f0de6ccbe6649c165d8b6bc4092973d6e386fdd1e'}
JOINT={'shinl':'lshin_g','legl':'lthigh_g'}
DISTAL={'shinl':'lfoot_g','legl':'lshin_g'}
PROPOSAL_SHA='baffddb94d989925cb2614a64c7deb0de1836f0603ae2fca5457cecab275c15f'
OWNERSHIP_SHA='1767bfb584be73252fe78090831de48ed1e89b036afd76f3069d5e9a20202971'
FLAGS=('geometryAccepted','anatomyAccepted','topologyAccepted','connectorAccepted','collisionAccepted','materialAccepted','nativeAccepted','stagingAccepted','clientAccepted','productionAccepted','selectionMade','noShelfAccepted')
DEPENDENCIES=('target_contract.py','place_purposebuilt_pelvis.py','diagnostic_axis_radial.py','conservative_face_selection.py','diagnostic_shin_girth90.py','diagnostic_thigh_proximal_one_sided.py')
INHERITED_NORMAL_FACES={'shinl':[25828,25932,30336],'legl':[37038]}
INHERITED_EVIDENCE_SHA={'shinl':'d7313008328327795c8e5e7caedcf02d54be1079b8d39ce296a63632c9e3a4f7','legl':'f5eaed5dee5ef0c5b60607772c40bcc928bb167df3e408a07b0d4191e5ce0cea'}

def pin(p):
    p=Path(p).resolve();return {'path':str(p),'sha256':tc.sha(p)}
def exact(p,pins):
    tc.require(isinstance(p,dict) and set(p)=={'path','sha256'},'Exact source pin required')
    q=Path(p['path']).resolve();tc.require(tc.sha(q)==p['sha256'],'Changed source '+str(q));tc.require(str(q) not in pins or pins[str(q)]==p['sha256'],'Conflicting source pin');pins[str(q)]=p['sha256'];return q
def pending(r):
    tc.require(r.get('pendingGates')=={k:False for k in FLAGS} and not any(r.get(k,False) for k in FLAGS),'Separate pending connector/body/material/client gates')
def functional_dependencies():
    return [pin(Path(__file__).resolve().parent/name) for name in DEPENDENCIES]
def inherited_normal_sets(part,parent_faces,child_faces):
    expected=INHERITED_NORMAL_FACES[part]
    tc.require(list(parent_faces)==expected and list(child_faces)==expected,'Only exact root-reviewed inherited source normal-cone faces; no omitted, additional or new negative face')
def smooth(x):
    u=np.clip(x,0,1);v=6*u**5-15*u**4+10*u**3;d=30*u*u*(u-1)*(u-1);d[(x<=0)|(x>=1)]=0;return v,d

def field(points,origin,axis,recipe):
    p=np.asarray(points,float);a=np.asarray(origin,float);d=np.asarray(axis,float)
    tc.require(p.ndim==2 and p.shape[1]==3 and a.shape==d.shape==(3,) and np.isfinite(p).all() and np.isfinite(a).all() and np.isfinite(d).all() and abs(np.linalg.norm(d)-1)<1e-14,'Finite points and proper unit frozen axis')
    R=np.eye(3)-np.outer(d,d);s=(p-a)@d;r=(p-a)@R
    if recipe['part']=='shinl':
        e=recipe['ellipseDerivedFromActualCapMask'];u=np.asarray(e['coordinateU']);vAxis=np.asarray(e['coordinateV']);cu,cv=e['centerUV'];ru,rv=e['radiusUV']
        tc.require(np.isfinite([cu,cv,ru,rv]).all() and ru>.01 and rv>.01 and np.allclose(np.stack([u,vAxis,d])@np.stack([u,vAxis,d]).T,np.eye(3),atol=1e-14,rtol=0) and np.allclose(np.cross(d,u),vAxis,atol=1e-14,rtol=0),'Proper source cap ellipse basis/radii')
        v,dv=smooth((s+.035)/.095);w=1-v;dw=-dv/.095;ur=(r@u-cu)/ru;vr=(r@vAxis-cv)/rv;rho2=ur*ur+vr*vr;g=(1-rho2)/(1+rho2)
        gradg=-2/(1+rho2)[:,None]**2*(2*ur[:,None]/ru*u+2*vr[:,None]/rv*vAxis)
        delta=(.035-.025*g)[:,None]*d-.25*r;q=p+w[:,None]*delta
        J=np.eye(3)[None]-.25*w[:,None,None]*R[None]+delta[:,:,None]*(dw[:,None]*d)[:,None,:]-.025*w[:,None,None]*d[None,:,None]*gradg[:,None,:]
        protected=s>=.060
    elif recipe['part']=='legl':
        inward=np.asarray(recipe['inwardDirectionBindWorld']);tc.require(inward.shape==(3,) and np.isfinite(inward).all() and abs(inward@d)<1e-14 and abs(np.linalg.norm(inward)-1)<1e-14,'Anatomical inward direction transverse to limb axis')
        u=-inward;t=r@u;ax,da=smooth((s-.405)/.040);lat,dl=smooth((t-.005)/.030);w=ax*lat;grad=da[:,None]/.040*lat[:,None]*d+dl[:,None]/.030*ax[:,None]*u
        q=p+.006*w[:,None]*inward;J=np.eye(3)[None]+.006*inward[None,:,None]*grad[:,None,:];protected=(s<=.405)|(t<=.005)
    else:raise ValueError('Only separately owned LEFT shin/thigh local fields')
    q[protected]=p[protected];J[protected]=np.eye(3)
    tc.require(np.isfinite(q).all() and np.isfinite(J).all() and (np.linalg.det(J)>0).all(),'Positive finite actual field; no fold waiver')
    return q,J,protected

def shading(normals,tangents,J,affected):
    n=np.asarray(normals,float);t=np.asarray(tangents,float);nr=n.copy();tr=t.copy();m=np.asarray(affected,bool)&np.any(J!=np.eye(3),axis=(1,2))
    if not m.any():return nr,tr
    nm=np.linalg.norm(n[m],axis=1);tm=np.linalg.norm(t[m,:3],axis=1)
    tc.require(np.isfinite(n[m]).all() and np.isfinite(t[m]).all() and (nm>1e-12).all() and (tm>1e-12).all() and np.isin(t[m,3],[-1.,1.]).all(),'Affected invalid authored N/T/W rejected')
    originalUnit=n[m]/nm[:,None];originalOrthogonal=t[m,:3]-(t[m,:3]*originalUnit).sum(1)[:,None]*originalUnit;tc.require((np.linalg.norm(originalOrthogonal,axis=1)>1e-12).all(),'Original authored tangent basis degenerate')
    nn=np.linalg.solve(J[m].transpose(0,2,1),n[m,...,None])[...,0];unit=nn/np.linalg.norm(nn,axis=1)[:,None];tv=np.einsum('nij,nj->ni',J[m],t[m,:3]);tv-=(tv*unit).sum(1)[:,None]*unit;mag=np.linalg.norm(tv,axis=1);tc.require((mag>1e-12).all(),'Collapsed transported tangent rejected')
    nr[m]=unit*nm[:,None];tr[m,:3]=tv/mag[:,None]*tm[:,None];tc.require(tr[:,3].tobytes()==t[:,3].tobytes(),'Literal tangent sign retained');return nr,tr

def validate_config(c,tp,target,proposal):
    pending(c);part=c.get('part');tc.require(part in KINDS and c.get('kind')=='root-pinned-local-knee-terminal-configuration' and c.get('schemaVersion')==1 and c.get('scope')==SCOPE,'Named two-owner configuration')
    tc.verify_binding(c,tp,target,'working');tc.require(c.get('coordinateSpace')=='working' and c.get('statureApplications')==0 and c.get('fieldApplications')==1 and c.get('parentFieldsReapplied') is False and c.get('globalScaleOrTranslation') is False and c.get('joint')==JOINT[part] and c.get('model')==tc.model(target,part),'No fit/frame/scale/ancestor field repeat')
    tc.require(target['rig'].get('pilotAcceptanceScope')=='offline-rig-structure' and target['rig'].get('offlineStructureAccepted') is True,'Exact frozen offline structural rig scope')
    expected=next(x for x in proposal['records'] if x['part']==part);tc.require(c['recipe']==expected['recipe'] and expected['newZeroFaces']==0 and expected['newFiniteOrientationFailures']==0,'Exact root-reviewed single RAM candidate; no numeric fold exceptions')
    tc.require(c.get('ramArrays')==proposal.get('arrayArchive'),'Exact reviewed RAM array archive association')
    H=tc.frame(target,JOINT[part],'working');end=tc.frame(target,DISTAL[part],'working')[:3,3];d=end-H[:3,3];L=float(np.linalg.norm(d));tc.require(np.isfinite(L) and L>1e-8,'Distinct finite frozen joint span');d/=L
    tc.require(np.array_equal(c['attachmentWorld'],H) and np.array_equal(c['axisOriginWorld'],H[:3,3]) and np.array_equal(c['axisUnitWorld'],d) and c['jointSpanMetres']==L,'Exact bone/frame/span/axis contract')
    tc.require(np.array_equal(H[:3,:3],np.eye(3)),'These exact source descendants require identity working bind orientation')
    e=c['expectedExecutor'];tc.require(Path(e['path']).resolve()==Path(__file__).resolve() and e['sha256']==tc.sha(__file__),'Exact executing reviewed new helper')
    tc.require(c.get('functionalDependencies')==functional_dependencies(),'Exact imported target/math/topology/storage/parent verifier dependencies')
    tc.require(c.get('inheritedAuthoredNormalExceptionFaces')==INHERITED_NORMAL_FACES[part],'Explicit exact source-specific diagnostic shading exception; no final material acceptance')
    tc.require(c.get('inheritedNormalConeEvidence',{}).get('sha256')==INHERITED_EVIDENCE_SHA[part],'Exact root-reviewed measured inherited cone evidence')
    tc.require(c['parentReceipt']['sha256']==PARENT_SHA[part] and c['parentCandidate']['sha256']==CANDIDATE_SHA[part] and c['ramProposal']['sha256']==PROPOSAL_SHA and c['pixelOwnership']['sha256']==OWNERSHIP_SHA,'Exact source-owned original candidate parents')
    return H,d,L

def source(c,tp,target,pins):
    proposal=json.loads(exact(c['ramProposal'],pins).read_text());H,d,L=validate_config(c,tp,target,proposal);part=c['part'];owned=json.loads(exact(c['pixelOwnership'],pins).read_text());report=next(x for x in owned['reports'] if x['part']==part)
    for dependency in c['functionalDependencies']:exact(dependency,pins)
    evidence=json.loads(exact(c['inheritedNormalConeEvidence'],pins).read_text());tc.require(evidence['configurationWithoutExportReview']['part']==part and evidence['failedSourceFaceIDs']==INHERITED_NORMAL_FACES[part] and evidence['allAffectedSourceNegativeNormalFaces']==INHERITED_NORMAL_FACES[part] and evidence['actualGeometryExported'] is False,'Exact failed source-cone evidence; no invented new exception')
    tc.require(report['sourceFaceID']==(35078 if part=='shinl' else 36983),'Exact separately owned visible source face')
    rp=exact(c['parentReceipt'],pins);parent=(verify_shin if part=='shinl' else verify_thigh)(rp,tp,target,space='working');cp=exact(c['parentCandidate'],pins);tc.require(cp==parent['candidate'] and np.array_equal(parent['receipt']['attachmentWorld'],H),'Exact typed parent and attachment once');pins.update(parent['inputs'])
    for p in c['protectedInputs']:exact(p,pins)
    human=json.loads(exact(c['humanShapeApproval'],pins).read_text());tc.require(human.get('shinGirthAndLengthFrozen') is True and human.get('foot120SizeAndNonconnectorShapeFrozen') is True and human.get('noNewShelvesRuleRetained') is True and human.get('connectorAccepted') is False,'Current accepted surrounding bulk remains protected, connector unaccepted')
    doc,blob=read_glb(cp);tc.require(len(doc['meshes'])==1 and len(doc['meshes'][0]['primitives'])==1 and doc['nodes']==[{'name':'detached_geometry','mesh':0}],'Only current static identity single-part source')
    p=doc['meshes'][0]['primitives'][0];rows={s:accessor(doc,blob,p['attributes'][s]) for s in ['POSITION','NORMAL','TANGENT']};F=accessor(doc,blob,p['indices']).reshape(-1,3).astype('i8');ap=exact(parent['receipt']['nativeCornerArchive'],pins)
    with np.load(ap,allow_pickle=False) as z:arc={k:z[k].copy() for k in z.files}
    tc.require(np.array_equal(arc['sourceTriangleIds'],np.arange(len(F))) and np.array_equal(arc['sourceCornerOrder'],np.tile([0,1,2],(len(F),1))),'Exact ordered original native corner provenance')
    return parent['receipt'],doc,blob,rows,F,H,d,L,arc

def mapped(rows,F,H,d,recipe):
    P,N,T=(rows[k] for k in ['POSITION','NORMAL','TANGENT']);world=P.astype(float)@BASIS.T+H[:3,3];q,J,protected=field(world,H[:3,3],d,recipe);active=np.zeros(len(P),bool);active[np.unique(F)]=True
    Q=P.copy();requested=active&~protected;Q[requested]=((q[requested]-H[:3,3])@BASIS).astype('<f4');changed=active&np.any(Q!=P,axis=1)
    n=N.astype(float)@BASIS.T;t=T.astype(float).copy();t[:,:3]=t[:,:3]@BASIS.T;nn,tt=shading(n,t,J,changed);NN=N.copy();TT=T.copy();shade=changed&np.any(J!=np.eye(3),axis=(1,2));NN[shade]=(nn[shade]@BASIS).astype('<f4');TT[shade,:3]=(tt[shade,:3]@BASIS).astype('<f4')
    result={'POSITION':Q,'NORMAL':NN,'TANGENT':TT}
    for s,v in result.items():tc.require(v[~changed].tobytes()==rows[s][~changed].tobytes() and np.isfinite(v).all(),'Protected/unused/zero-byte-effect authored rows literal')
    tc.require(TT[:,3].tobytes()==T[:,3].tobytes(),'Authored tangent W exact');return result,world,q,J,protected,changed

def discrete(rows,newrows,F,H,d,recipe):
    P=rows['POSITION'];Q=newrows['POSITION'];a=topology(P,F);b=topology(Q,F)
    tc.require(all(a[k]==b[k] for k in TOPOLOGY_KEYS),'No introduced topology/collapse/winding defects')
    _,i=np.unique(P,axis=0,return_inverse=True);_,j=np.unique(Q,axis=0,return_inverse=True);tc.require(len(np.unique(np.c_[i,j],axis=0))==len(np.unique(i))==len(np.unique(j)),'Exact source geometric weld partition retained')
    world=P.astype(float)@BASIS.T+H[:3,3];actual=Q.astype(float)@BASIS.T+H[:3,3];ideal,J,protected=field(world,H[:3,3],d,recipe);old=world[F];new=actual[F];oc=np.cross(old[:,1]-old[:,0],old[:,2]-old[:,0]);nc=np.cross(new[:,1]-new[:,0],new[:,2]-new[:,0]);area=np.linalg.norm(nc,axis=1);tc.require((area>0).all(),'No actual serialized zero face')
    expected=np.linalg.solve(J[F].mean(1).transpose(0,2,1),oc[...,None])[...,0];dot=(nc*expected).sum(1)/np.linalg.norm(expected,axis=1)/area;tc.require((dot>0).all(),'No finite actual face inversion; positiveJ alone insufficient')
    active=np.unique(F);err=float(np.max(abs(actual[active]-ideal[active])));tc.require(err<4e-8,'Bounded local-coordinate serialization error')
    changed=np.any(Q!=P,axis=1);sing=np.linalg.svd(J[changed],compute_uv=False)
    affected=np.any(changed[F],axis=1);n=newrows['NORMAL'].astype(float)@BASIS.T;oldn=rows['NORMAL'].astype(float)@BASIS.T;cornerDot=(n[F]*nc[:,None,:]).sum(2);oldDot=(oldn[F]*oc[:,None,:]).sum(2);bad=np.flatnonzero(affected&np.any(cornerDot<=0,axis=1));oldbad=np.flatnonzero(affected&np.any(oldDot<=0,axis=1));inherited_normal_sets(recipe['part'],oldbad.tolist(),bad.tolist())
    exceptions=[]
    for face in bad:
        od=oldDot[face]/np.linalg.norm(oldn[F[face]],axis=1)/np.linalg.norm(oc[face]);nd=cornerDot[face]/np.linalg.norm(n[F[face]],axis=1)/area[face]
        if recipe['part']=='legl':
            tc.require(np.array_equal(J[F[face]],np.broadcast_to(np.eye(3),(3,3,3))) and np.array_equal(old[face]-np.roll(old[face],1,axis=0),new[face]-np.roll(new[face],1,axis=0)) and rows['NORMAL'][F[face]].tobytes()==newrows['NORMAL'][F[face]].tobytes() and rows['TANGENT'][F[face]].tobytes()==newrows['TANGENT'][F[face]].tobytes() and np.array_equal(od,nd) and np.linalg.norm(oc[face])==area[face],'Exact permitted thigh microface is rigid translated only: J/edges/N/T/dots/area literal; no worsening')
        exceptions.append({'sourceFaceID':int(face),'sourceVertexIDs':F[face].tolist(),'originalCornerNormalDots':od.tolist(),'childCornerNormalDots':nd.tolist(),'originalCornerAnglesDegrees':np.degrees(np.arccos(np.clip(od,-1,1))).tolist(),'childCornerAnglesDegrees':np.degrees(np.arccos(np.clip(nd,-1,1))).tolist(),'originalAreaMetres2':float(np.linalg.norm(oc[face])/2),'childAreaMetres2':float(area[face]/2),'scope':'Exact measured Troll-source inherited shading microdefect, diagnostic export/render only; no normal or tangent-sign patch and no final material acceptance.'})
    return {'beforeTopology':{k:a[k] for k in TOPOLOGY_KEYS},'afterTopology':{k:b[k] for k in TOPOLOGY_KEYS},'changedRows':int(changed.sum()),'affectedSourceFaces':int(affected.sum()),'protectedRowsExact':int(protected.sum()),'minimumActualFaceTransportDot':float(dot.min()),'maximumWorldSerializationErrorMetres':err,'minimumJacobianDeterminant':float(np.linalg.det(J[changed]).min()),'singularValueRange':[float(sing.min()),float(sing.max())],'newZeroFaces':0,'newFiniteOrientationFailures':0,'affectedAuthoredNormalBeyond90DegreeSourceFaces':bad.tolist(),'inheritedAuthoredNormalDiagnosticExceptions':exceptions,'literalNoShelfAccepted':False}

def native_child(arc,H,d,recipe):
    out={k:v.copy() for k,v in arc.items()};p=arc['positions'];n=arc['normals'];t=arc['tangents'];world=p.reshape(-1,3)+H[:3,3];q,J,protected=field(world,H[:3,3],d,recipe);changed=~protected&np.any(q!=world,axis=1);nn,tt=shading(n.reshape(-1,3),t.reshape(-1,4),J,changed)
    local=p.reshape(-1,3).copy();local[changed]=q[changed]-H[:3,3];out.update(kneeTerminalParentPositions=p.copy(),kneeTerminalParentNormals=n.copy(),kneeTerminalParentTangents=t.copy());out['positions']=local.reshape(p.shape);out['normals']=nn.reshape(n.shape);out['tangents']=tt.reshape(t.shape);return out

def native_bridge(original,newrows,F,protected,arc,native):
    """Measure continuous f64 versus literal serialized rows; never reconstruct either."""
    P=newrows['POSITION'][F].astype(float)@BASIS.T;N=newrows['NORMAL'][F].astype(float)@BASIS.T;T=newrows['TANGENT'][F].astype(float).copy();T[:,:,:3]=T[:,:,:3]@BASIS.T
    changed=np.any(newrows['POSITION']!=original['POSITION'],axis=1)
    nativeChanged=np.any(native['positions']!=arc['positions'],axis=2)
    nearKnot=(~changed[F])&(~protected[F])&nativeChanged
    def metrics(mask):
        count=int(mask.sum())
        return {'corners':count,'maximumPComponentErrorMetres':float(np.max(abs(P[mask]-native['positions'][mask]))) if count else 0.,'maximumNComponentError':float(np.max(abs(N[mask]-native['normals'][mask]))) if count else 0.,'maximumTComponentError':float(np.max(abs(T[mask]-native['tangents'][mask]))) if count else 0.}
    return {'allOrderedCorners':metrics(np.ones(F.shape,bool)),'serializedPIdentityContinuousFloat64FieldCorners':{**metrics(nearKnot),'sourceVertexIDs':np.unique(F[nearKnot]).tolist(),'sourceFaceIDs':np.flatnonzero(nearKnot.any(1)).tolist(),'sourceFaceCornerIDs':np.argwhere(nearKnot).tolist()},'policy':'Serialized P-byte-identity rows keep authored N/T/W literal; authoritative float64 current corners receive the continuous local field. Measured bridge remains distinct, without reconstruction or tolerance waiver.'}

def storage(old,blob,doc,newblob,newrows):
    tc.require(newblob[:len(blob)]==blob and embedded_maps(old,blob)==embedded_maps(doc,newblob),'Original BIN/map encoded payload literal');restore=copy.deepcopy(doc);restore['meshes'][0]['primitives'][0]['attributes']=old['meshes'][0]['primitives'][0]['attributes'];restore['accessors']=restore['accessors'][:-3];restore['bufferViews']=restore['bufferViews'][:-3];restore['buffers'][0]['byteLength']=old['buffers'][0]['byteLength'];tc.require(restore==old,'Original UV/index/material/nodes/accessor descriptors exact')
    for s,v in newrows.items():tc.require(accessor(doc,newblob,doc['meshes'][0]['primitives'][0]['attributes'][s]).tobytes()==v.tobytes(),'Exact appended local PNT')

def serialized_guard(archive,original,newrows,F,protected):
    tc.require(np.array_equal(archive['parentFaces'],F) and np.array_equal(archive['protectedRows'],np.flatnonzero(protected)),'Exact serialized source topology/protected region')
    for name in ['POSITION','NORMAL','TANGENT']:
        tc.require(archive['parent'+name].dtype==original[name].dtype and archive['parent'+name].shape==original[name].shape and archive['parent'+name].tobytes()==original[name].tobytes(),'Exact reviewed current authored parent '+name)
        tc.require(archive[name].dtype==newrows[name].dtype and archive[name].shape==newrows[name].shape and archive[name].tobytes()==newrows[name].tobytes(),'Exact reviewed serialized trial '+name)

def prepare(ap):
    a=json.loads(Path(ap).read_text());c=a['configuration'];pending(a);tc.require(a.get('kind')=='root-approved-local-knee-terminal-review' and a.get('scope')==SCOPE and a.get('reviewedBy')=='/root' and a.get('reviewed') is True and a.get('authorizeOneFreshExport') is True,'Explicit concrete root local connector review')
    pins={};exact(pin(ap),pins);tp=exact(c['target'],pins);target=tc.load(tp);parent,doc,blob,rows,F,H,d,L,arc=source(c,tp,target,pins);mp=exact(c['ramArrays'],pins)
    newrows,world,q,J,protected,changed=mapped(rows,F,H,d,c['recipe'])
    with np.load(mp,allow_pickle=False) as z:
        tc.require(np.array_equal(z[c['part']+'_sourceWorkingP'],world) and np.max(abs(z[c['part']+'_RAMWorkingP']-q))<6e-15 and np.array_equal(z[c['part']+'_protectedVertexIDs'],np.flatnonzero(protected)),'Exact root-reviewed source/RAM/protected mask')
    sr=exact(c['serializedRAM'],pins)
    with np.load(sr,allow_pickle=False) as z:serialized_guard(z,rows,newrows,F,protected)
    proof=discrete(rows,newrows,F,H,d,c['recipe']);native=native_child(arc,H,d,c['recipe']);proof['nativeVsSerializedBridge']=native_bridge(rows,newrows,F,protected,arc,native);exact(c['expectedExecutor'],pins)
    return a,c,tp,target,parent,doc,blob,newrows,F,H,d,L,proof,native,pins

def execute(approval_path,output):
    ap=Path(approval_path).resolve();a,c,tp,target,parent,doc,blob,rows,F,H,d,L,proof,native,pins=prepare(ap);out=Path(output).resolve();tc.require(not out.exists(),'Fresh immutable connector output');out.mkdir();nd,nb=append_attributes(doc,blob,rows);cp=out/'candidate-local.glb';write_glb(cp,nd,nb);npz=out/'native-float64-knee-terminal-corners.npz';np.savez_compressed(npz,**native)
    snaps=out/'helpers';snaps.mkdir();sp=snaps/Path(__file__).name;shutil.copyfile(__file__,sp)
    for p,h in pins.items():tc.require(tc.sha(p)==h,'Frozen source changed during export')
    r={**tc.binding(tp,target,'working'),'schemaVersion':1,'kind':KINDS[c['part']],'scope':SCOPE,'operation':'same-topology-source-owned-local-knee-terminal-field','part':c['part'],'joint':c['joint'],'model':c['model'],'candidate':str(cp),'candidateSha256':tc.sha(cp),'rootApproval':pin(ap),'fieldConfiguration':c,'parentGeometryReceipt':c['parentReceipt'],'parentCandidate':c['parentCandidate'],'parentNativeCornerArchive':parent['nativeCornerArchive'],'nativeCornerArchive':pin(npz),'attachmentWorld':H.tolist(),'candidateToAttachmentLocal':np.eye(4).tolist(),'attachmentAppliedOnce':True,'jointSpanMetres':L,'axisUnitWorld':d.tolist(),'statureApplications':0,'fieldApplications':1,'parentFieldsReapplied':False,'rigOrNeighborsChanged':False,'diagnosticOnly':True,'canonicalNativeLineage':False,'proof':proof,'pendingGates':{k:False for k in FLAGS},'frozenInputs':pins,'executedHelper':pin(sp),'limits':['Source-owned local connector only; inherited donor topology/material remains pending.','Actual literal idle/kneel source-matched joint/no-shelf review required; numerical positiveJ/profile/finite arrays not final acceptance.','Strong local shin compression is explicit in actual proof; accepted calf, thigh bulk and bone spans protected.']}
    rp=out/'diagnostic-knee-terminal-geometry.json';rp.write_text(json.dumps(r,indent=2)+'\n');verify_receipt(rp,tp,target);return pin(rp)

def verify_receipt(receipt_path,target_path,target,space='working'):
    path=Path(receipt_path).resolve();r=json.loads(path.read_text());pending(r);part=r.get('part');tc.require(space=='working' and part in KINDS and r.get('kind')==KINDS[part] and r.get('scope')==SCOPE and r.get('schemaVersion')==1 and r.get('operation')=='same-topology-source-owned-local-knee-terminal-field' and r.get('statureApplications')==0 and r.get('fieldApplications')==1 and r.get('parentFieldsReapplied') is False and r.get('rigOrNeighborsChanged') is False and r.get('diagnosticOnly') is True and r.get('canonicalNativeLineage') is False,'Exact separate unaccepted local connector kind/scope')
    tc.verify_binding(r,target_path,target,'working');a,c,tp,_,parent,od,ob,rows,F,H,d,L,proof,native,pins=prepare(r['rootApproval']['path']);tc.require(Path(tp).resolve()==Path(target_path).resolve() and c==r['fieldConfiguration'] and r['parentGeometryReceipt']==c['parentReceipt'] and r['parentCandidate']==c['parentCandidate'] and r['parentNativeCornerArchive']==parent['nativeCornerArchive'] and r['rootApproval']==pin(r['rootApproval']['path']),'Exact approved parent/native lineage')
    tc.require(r['part']==c['part'] and r['joint']==c['joint'] and r['model']==c['model'] and r['attachmentWorld']==H.tolist() and np.array_equal(r['candidateToAttachmentLocal'],np.eye(4)) and r['attachmentAppliedOnce'] is True and r['jointSpanMetres']==L and r['axisUnitWorld']==d.tolist(),'No attachment/bone/model/axis substitution')
    cp=Path(r['candidate']);tc.require(tc.sha(cp)==r['candidateSha256'],'Exact candidate');nd,nb=read_glb(cp);storage(od,ob,nd,nb,rows)
    tc.require(r['frozenInputs']==pins,'Exhaustive prepared source closure; no omitted/substituted pins')
    npz=exact(r['nativeCornerArchive'],pins)
    with np.load(npz,allow_pickle=False) as z:tc.require(set(z.files)==set(native) and all(z[k].dtype==v.dtype and z[k].shape==v.shape and z[k].tobytes()==v.tobytes() for k,v in native.items()),'Exact f64 current field + all parent/source barycentric/corner/map fields')
    tc.require(r['proof']==proof and r['executedHelper']['sha256']==c['expectedExecutor']['sha256'],'Exact decoded finite proof/helper');exact(r['executedHelper'],pins)
    for p,h in r['frozenInputs'].items():tc.require(tc.sha(p)==h and pins.get(p)==h,'Exact non-substitute frozen input closure')
    pins[str(path)]=tc.sha(path);pins[str(cp.resolve())]=tc.sha(cp);return {'receipt':r,'candidate':cp,'inputs':pins,'primitiveInventory':[{'primitive':0,'part':part,'material':nd['meshes'][0]['primitives'][0]['material'],'faces':len(F)}]}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--approval',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(execute(a.approval,a.output)))
