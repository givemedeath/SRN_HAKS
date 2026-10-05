"""Explicit diagnostic replacement: untouched LEFT85 thigh, one-sided back30."""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
import target_contract as tc
from diagnostic_axis_radial import append_attributes,TOPOLOGY_KEYS
from diagnostic_thigh_proximal_back import parent,input_pin
from place_purposebuilt_pelvis import BASIS,accessor,embedded_maps,read_glb,write_glb
from conservative_face_selection import topology
KIND='target-part-diagnostic-thigh-one-sided-proximal-backward-Y'
OPERATION='replace-window-from-radial85-world-Z-ramp-backward-Y'
PENDING=('geometryAccepted','anatomyAccepted','connectorAccepted','materialAccepted','nativeAccepted','stagingAccepted','clientAccepted','productionAccepted','selectionMade')

class OneSidedBackward:
    def __init__(self,amount=.030,zero=.800,full=.930):
        tc.require(amount>0 and np.isfinite(amount) and np.isfinite(zero) and np.isfinite(full) and zero<full,'Positive finite one-sided support')
        self.amount=float(amount);self.zero=float(zero);self.full=float(full)
    def weight(self,z):
        z=np.asarray(z,float);u=np.clip((z-self.zero)/(self.full-self.zero),0.,1.);w=np.clip(u*u*u*(10+u*(-15+6*u)),0.,1.);dw=30*u*u*(1-u)*(1-u)/(self.full-self.zero)
        return np.where(z<=self.zero,0.,np.where(z>=self.full,1.,w)),np.where((z<=self.zero)|(z>=self.full),0.,dw)
    def transform(self,p):
        p=np.asarray(p,float);out=p.copy();w,_=self.weight(p[:,2]);out[:,1]-=self.amount*w;return out
    def jacobian(self,p):
        _,dw=self.weight(np.asarray(p)[:,2]);J=np.broadcast_to(np.eye(3),(len(p),3,3)).copy();J[:,1,2]=-self.amount*dw;return J
    def transport(self,p,n,t,geometry_affected=None):
        p=np.asarray(p,float);n=np.asarray(n,float);t=np.asarray(t,float);J=self.jacobian(p);m=np.any(J!=np.eye(3),axis=(1,2))
        if geometry_affected is not None:m&=np.asarray(geometry_affected,bool)
        nr=n.copy();tr=t.copy()
        if not m.any():return nr,tr
        nm=np.linalg.norm(n[m],axis=1);tm=np.linalg.norm(t[m,:3],axis=1);tc.require(np.isfinite(n[m]).all() and np.isfinite(t[m]).all() and np.all(nm>1e-12) and np.all(tm>1e-12),'Affected degenerate authored N/T rejected')
        nn=n[m].copy();nn[:,2]-=J[m,1,2]*nn[:,1];unit=nn/np.linalg.norm(nn,axis=1)[:,None];tv=np.einsum('nij,nj->ni',J[m],t[m,:3]);tv-=np.sum(tv*unit,axis=1)[:,None]*unit;mag=np.linalg.norm(tv,axis=1);tc.require(np.all(mag>1e-12),'Affected collapsed tangent rejected')
        nr[m]=unit*nm[:,None];tr[m,:3]=tv/mag[:,None]*tm[:,None];tc.require(tr[:,3].tobytes()==t[:,3].tobytes(),'Literal tangent W');return nr,tr

def validate_approval(a,c):
    tc.require(a.get('kind')=='root-approved-thigh-one-sided-proximal-backward-Y30-diagnostic' and a.get('reviewedBy')=='/root' and a.get('authorizeImplementationAndOneFreshExport') is True and a.get('configuration')==c,'Exact executed root one-sided30 approval')
    exact={'kind':'root-review-only-one-sided-proximal-thigh-back30-config','part':'legl','joint':'lthigh_g','coordinateSpace':'working','statureApplications':0,'factor85Reapplied':False,'historicalBack20Stacked':False,'replacesHistoricSymmetricWindow':True,'deltaWorldMetres':[0.,-.030,0.],'zeroAtOrBelowWorldZMetres':.800,'fullAtOrAboveWorldZMetres':.930,'transition':'one-sided-quintic-C2-ramp-no-upper-return','fullShiftThroughAllUpperCollarAndCap':True}
    tc.require(all(c.get(k)==v for k,v in exact.items()),'Exact scoped one-sided30 replacement recipe')
    tc.require(c.get('changedActiveRows')==16034 and c.get('affectedOriginalFaces')==27143,'Exact reviewed active mask')
    tc.require(c['selectedFacetProof']['originalNormalBeyond90DegreeFaceIds']==[] and c['selectedFacetProof']['nonpositiveCentroidExpectedNormalFaceIds']==[],'No disclosed exception needed for this corrected field')

def field(c):return OneSidedBackward(-c['deltaWorldMetres'][1],c['zeroAtOrBelowWorldZMetres'],c['fullAtOrAboveWorldZMetres'])

def mapped_rows(P,N,T,F,H,f):
    world=P.astype(float)@BASIS.T+H[:3,3];active=np.zeros(len(P),bool);active[np.unique(F)]=True;w,_=f.weight(world[:,2]);requested=active&(w>0);Q=P.copy();Q[requested,2]=(P[requested,2].astype(float)+f.amount*w[requested]).astype('<f4');changed=active&np.any(Q!=P,axis=1);shade=changed&np.any(f.jacobian(world)!=np.eye(3),axis=(1,2));n=N.astype(float)@BASIS.T;t=T.astype(float).copy();t[:,:3]=t[:,:3]@BASIS.T;nn,tt=f.transport(world[shade],n[shade],t[shade]);NN=N.copy();TT=T.copy();NN[shade]=(nn@BASIS).astype('<f4');tt[:,:3]=tt[:,:3]@BASIS;TT[shade]=tt.astype('<f4');rows={'POSITION':Q,'NORMAL':NN,'TANGENT':TT}
    for sem,v in rows.items():tc.require(v[~changed].tobytes()=={'POSITION':P,'NORMAL':N,'TANGENT':T}[sem][~changed].tobytes(),'Unused/outside/zero-byte-effect PNT literal');tc.require(np.isfinite(v).all(),'Finite serialized PNT')
    tc.require(Q[:,[0,1]].tobytes()==P[:,[0,1]].tobytes() and NN[~shade].tobytes()==N[~shade].tobytes() and TT[~shade].tobytes()==T[~shade].tobytes(),'Exact worldXZ/identity-J authored shading');return rows,world,changed,shade

def discrete(P,Q,F,H,f):
    before=topology(P,F);after=topology(Q,F)
    for key in TOPOLOGY_KEYS:tc.require(before[key]==after[key],'Introduced topology '+key)
    a=P.astype(float)@BASIS.T+H[:3,3];b=Q.astype(float)@BASIS.T+H[:3,3];A=a[F];B=b[F];n=np.cross(A[:,1]-A[:,0],A[:,2]-A[:,0]);g=np.cross(B[:,1]-B[:,0],B[:,2]-B[:,0]);tc.require((np.linalg.norm(g,axis=1)>2e-15).all(),'Serialized degenerate');tc.require(np.array_equal(n[:,1],g[:,1]),'Literal signedXZ projection');nz=n[:,1]!=0;tc.require((np.sum(n[~nz]*g[~nz],axis=1)>0).all(),'ZeroXZ planar orientation')
    e1=A[nz,1]-A[nz,0];e2=A[nz,2]-A[nz,0];dy=(B-A)[nz,:,1];den=e1[:,0]*e2[:,2]-e1[:,2]*e2[:,0];gx=((dy[:,1]-dy[:,0])*e2[:,2]-(dy[:,2]-dy[:,0])*e1[:,2])/den;gz=(e1[:,0]*(dy[:,2]-dy[:,0])-e2[:,0]*(dy[:,1]-dy[:,0]))/den;expected=n[nz].copy();expected[:,0]-=gx*n[nz,1];expected[:,2]-=gz*n[nz,1];error=float(np.max(abs(expected-g[nz])));dot=(expected*g[nz]).sum(1)/np.linalg.norm(expected,axis=1)/np.linalg.norm(g[nz],axis=1);tc.require(error<2e-15 and dot.min()>.99999999,'Independent edge-secant cofactor graph proof')
    oldDot=(n*g).sum(1)/np.linalg.norm(n,axis=1)/np.linalg.norm(g,axis=1);tc.require(oldDot.min()>0,'Corrected recipe has no beyond90-degree nodal rotation');J=f.jacobian(A.mean(1));cn=np.linalg.solve(J.transpose(0,2,1),n[...,None])[...,0];cd=(cn*g).sum(1)/np.linalg.norm(cn,axis=1)/np.linalg.norm(g,axis=1);tc.require(cd.min()>0,'Corrected recipe no centroid cone exceptions')
    return {'beforeTopology':before,'afterTopology':after,'signedWorldXZProjectedDoubleAreasExact':True,'zeroXZPlanarOrientationRetained':True,'minimumIndependentSecantExpectedDot':float(dot.min()),'maximumSecantExpectedNormalError':error,'minimumOldNewGeometricNormalDot':float(oldDot.min()),'minimumCentroidExpectedNormalDot':float(cd.min()),'noNewZeroAreas':True,'globalIntersectionClaim':False}

def retains_profile_directions(before,after,tolerance=.0001):
    before=np.asarray(before,float);after=np.asarray(after,float);tc.require(before.ndim==after.ndim==1 and before.shape==after.shape and len(before)>=3 and np.isfinite(before).all() and np.isfinite(after).all(),'Finite source-matched contour profile')
    old=np.diff(before);new=np.diff(after);significant=abs(old)>tolerance
    return bool(np.all(old[significant]*new[significant]>0))

def contour_guard(P,Q,F,H,c,pins):
    pp=input_pin(c['sourceFacingAndNotchCauseEvidence']['path'],c['sourceFacingAndNotchCauseEvidence']['sha256'],pins,c);p=json.loads(pp.read_text());tc.require(p['kind']=='literal-thigh-v7-high-band-source-facing-and-profile-readonly-proof' and p['profileRayCount']==51,'Exact published literal facing/band cause proof')
    cp=next(Path(s) for s in p['frozenInputs'] if s.endswith('thigh-back20-pelvis35-hand130-matched-v1\\pause1\\comparison.json'));input_pin(cp,p['frozenInputs'][str(cp)],pins,c);cmp=json.loads(cp.read_text());G=np.asarray(cmp['specimens'][0]['jointWorldMatrices']['lthigh_g']);old=P.astype(float)@BASIS.T@G[:3,:3].T+G[:3,3];new=Q.astype(float)@BASIS.T@G[:3,:3].T+G[:3,3];lines=[]
    for line in p['finiteLiteralVerticalProfiles']:
        rows=[]
        for s in line['samples']:
            b=np.asarray(s['barycentric']);fid=s['sourceFaceId'];a=b@old[F[fid]];q=b@new[F[fid]];tc.require(np.max(abs(a-np.asarray(s['positionsAllStatesSameOriginalCorner']['radial85'])))<2e-15,'Original source-profile correspondence changed');rows.append((q[2],a[1],q[1],s['positionsAllStatesSameOriginalCorner']['back20'][1],fid))
        rows.sort(key=lambda x:x[0]);a=np.asarray(rows);tc.require(retains_profile_directions(a[:,1],a[:,2]),'New shelf/ridge/annular groove: source-matched contour directions changed');tc.require(not retains_profile_directions(a[:,1],a[:,3]),'Historical symmetric window defect must remain explicitly rejected');lines.append({'pixelColumn':line['pixelColumn'],'sampleCount':len(rows),'sourceFaceIds':[int(x) for x in a[:,4]],'originalDirectionRetainedAllSignificantSteps':True,'historicSymmetricWindowRejected':True,'minimumCorrectedAdjacentMagnitudeMetres':float(abs(np.diff(a[:,2])).min())})
    return {'standingHumanRule':'No new unintended shelves/ridges/annular grooves when tapering or positioning; analytic C2 and positiveJ alone do not satisfy acceptance.','literalSourceMatchedSampleCount':51,'profiles':lines,'allSourceMatchedDirectionsRetained':True,'historicalSymmetricBack20Rejected':True,'actualLiteralJointRenderReviewStillRequired':True,'finiteSamplesNotGlobalNoShelfClaim':True}
def native_child(arc,H,f):
    out={k:v.copy() for k,v in arc.items()};p=arc['positions'].reshape(-1,3);world=p+H[:3,3];w,_=f.weight(world[:,2]);q=p.copy();q[:,1]-=f.amount*w;changed=np.any(q!=p,axis=1);n,t=f.transport(world,arc['normals'].reshape(-1,3),arc['tangents'].reshape(-1,4),changed);out.update(oneSidedParentPositions=arc['positions'].copy(),oneSidedParentNormals=arc['normals'].copy(),oneSidedParentTangents=arc['tangents'].copy());out['positions']=q.reshape(arc['positions'].shape);out['normals']=n.reshape(arc['normals'].shape);out['tangents']=t.reshape(arc['tangents'].shape);return out

def execute(approval_path,output):
    ap=Path(approval_path).resolve();a=json.loads(ap.read_text());c=a['configuration'];validate_approval(a,c);pins={};input_pin(ap,tc.sha(ap),pins,c);pp=input_pin(a['proposal']['path'],a['proposal']['sha256'],pins,c);tc.require(json.loads(pp.read_text())==c,'Exact proposal');tp=input_pin(c['targetContract'],c['targetContractSha256'],pins,c);target=tc.load(tp);tc.require(target['identity']['race']=='troll' and target['identity']['gender']=='male','Troll male only');r,doc,blob,P,N,T,UV,F,active,H,arc=parent(c,tp,target,pins);f=field(c);out=Path(output).resolve();tc.require(not out.exists(),'Fresh immutable output');rows,world,changed,shade=mapped_rows(P,N,T,F,H,f)
    mp=input_pin(c['exactRAMMask']['path'],c['exactRAMMask']['sha256'],pins,c)
    with np.load(mp,allow_pickle=False) as m:
        requested=active&(f.weight(world[:,2])[0]>0);tc.require(np.array_equal(np.flatnonzero(requested),m[c['maskKeys']['changedRows']]) and np.array_equal(np.flatnonzero(np.any(requested[F],axis=1)),m[c['maskKeys']['affectedOriginalFaceIds']]) and np.all(~changed|requested),'Exact reviewed continuous support and actual serialized subset');tc.require(rows['POSITION'].tobytes()==m[c['maskKeys']['proposedPosition']].tobytes(),'Exact reviewed RAM P')
    for key in ['currentPelvisShorteningReceipt','currentPelvisCandidate','sourceFacingAndNotchCauseEvidence','readOnlyComparison']:input_pin(c[key]['path'],c[key]['sha256'],pins,c)
    proof=discrete(P,rows['POSITION'],F,H,f);contour=contour_guard(P,rows['POSITION'],F,H,c,pins);nw=rows['POSITION'].astype(float)@BASIS.T+H[:3,3];err=float(np.max(abs(nw[active]-f.transform(world)[active])));tc.require(err<2e-8,'Serialization residual');native=native_child(arc,H,f)
    helpers=[Path(__file__),Path(__file__).with_name('test_diagnostic_thigh_proximal_one_sided.py')]+[Path(__file__).with_name(n) for n in ['diagnostic_thigh_proximal_back.py','diagnostic_axis_radial.py','diagnostic_connector_shear.py','target_contract.py','target_part_pipeline.py','place_purposebuilt_pelvis.py','conservative_face_selection.py']]
    for p in helpers:input_pin(p,tc.sha(p),pins,c)
    out.mkdir();nd,nb=append_attributes(doc,blob,rows);candidate=out/'candidate-local.glb';write_glb(candidate,nd,nb);archive=out/'native-float64-one-sided-corners.npz';np.savez_compressed(archive,**native);(out/'helpers').mkdir();snapshots={}
    for p in helpers:dest=out/'helpers'/p.name;shutil.copyfile(p,dest);snapshots[str(p.resolve())]={'path':str(dest),'sha256':tc.sha(dest)}
    receipt={**tc.binding(tp,target,'working'),'schemaVersion':1,'kind':KIND,'operation':OPERATION,'part':'legl','joint':'lthigh_g','model':tc.model(target,'legl'),'diagnosticOnly':True,'canonicalNativeLineage':False,'candidate':str(candidate),'candidateSha256':tc.sha(candidate),'candidateToAttachmentLocal':np.eye(4).tolist(),'attachmentWorld':H.tolist(),'parentRadialDiagnosticReceipt':c['parentRadialDiagnosticReceipt'],'parentCandidate':c['parentCandidate'],'parentNativeCornerArchive':r['nativeCornerArchive'],'nativeCornerArchive':{'path':str(archive),'sha256':tc.sha(archive)},'rootApproval':{'path':str(ap),'sha256':tc.sha(ap)},'fieldConfiguration':c,'historicalExecutedSourceRecoveries':c['historicalExecutedSourceRecoveries'],'statureApplications':0,'factor85Reapplied':False,'historicalBack20Stacked':False,'rigOrNeighborsChanged':False,'hipKneeBindLengthUnchanged':True,'worldXZStoredComponentsExact':True,'inclinedMeshAxisCoordinateUnchangedClaim':False,'fullPlateauDeltaAlongOriginalAxisMetres':float(np.asarray(r['axisUnitWorld'])@np.asarray(c['deltaWorldMetres'])),'oldInclinedMeshAxisEnvelope':c['oldInclinedMeshAxisEnvelope'],'newInclinedMeshAxisEnvelope':c['newInclinedMeshAxisEnvelope'],'requestedSupportActiveRows':int(requested.sum()),'requestedSupportOriginalFaces':int(np.any(requested[F],axis=1).sum()),'supportWithLiteralPositionRows':np.flatnonzero(requested&~changed).tolist(),'changedActiveRows':int(changed.sum()),'affectedOriginalFaces':int(np.any(changed[F],axis=1).sum()),'transportedShadingActiveRows':int(shade.sum()),'proof':proof,'noUnintendedShelfSourceProfileGuard':contour,'maximumWorldMappingSerializationErrorMetres':err,'frozenInputs':pins,'helperSnapshots':snapshots,'limits':['One-sided total30 replaces historical symmetric20 from untouched85; no previous field stacking.','Inherited945boundaries/1NM/5badlinks remain; finite contact/profile measurements and graph checks do not imply all-pose global nonintersection/anatomy acceptance.','WorldXZ and joints/rig lengths literal; mesh coordinate along inclined axis changes by disclosed pure-Y projection.'],**{k:False for k in PENDING}};rp=out/'diagnostic-one-sided-proximal-geometry.json';rp.write_text(json.dumps(receipt,indent=2)+'\n');verify_receipt(rp,tp,target);return rp

def verify_receipt(receipt_path,target_path,target,space='working'):
    path=Path(receipt_path).resolve();r=json.loads(path.read_text());tc.require(r['schemaVersion']==1 and r['kind']==KIND and r['operation']==OPERATION and space=='working' and r['canonicalNativeLineage'] is False and all(r[k] is False for k in PENDING),'Exact typed pending working one-sided child');tc.verify_binding(r,target_path,target,space);tc.require(r['part']=='legl' and r['joint']=='lthigh_g' and r['model']==tc.model(target,'legl') and r['statureApplications']==0 and r['factor85Reapplied'] is False and r['historicalBack20Stacked'] is False and np.array_equal(r['candidateToAttachmentLocal'],np.eye(4)),'No fit/frame/radial/window/stature repeat');c=r['fieldConfiguration'];pins={}
    for p,h in r['frozenInputs'].items():input_pin(p,h,pins,c)
    tc.require(tc.sha(r['candidate'])==r['candidateSha256'] and tc.sha(r['nativeCornerArchive']['path'])==r['nativeCornerArchive']['sha256'],'Child/archive hashes');a=json.loads(Path(r['rootApproval']['path']).read_text());validate_approval(a,c);pr,old,blob,P,N,T,UV,F,active,H,arc=parent(c,target_path,target,pins);doc,nb=read_glb(r['candidate']);rows,world,changed,shade=mapped_rows(P,N,T,F,H,field(c));tc.require(nb[:len(blob)]==blob and embedded_maps(doc,nb)==embedded_maps(old,blob),'Original immutable BIN/maps');expected=copy.deepcopy(doc);expected['meshes'][0]['primitives'][0]['attributes']=old['meshes'][0]['primitives'][0]['attributes'];expected['accessors']=expected['accessors'][:-3];expected['bufferViews']=expected['bufferViews'][:-3];expected['buffers'][0]['byteLength']=old['buffers'][0]['byteLength'];tc.require(expected==old,'Undeclared source/index/UV/material/accessor change');attrs=doc['meshes'][0]['primitives'][0]['attributes']
    for sem,v in rows.items():tc.require(accessor(doc,nb,attrs[sem]).tobytes()==v.tobytes(),'Exact one-sided PNT transport')
    ea=native_child(arc,H,field(c))
    with np.load(r['nativeCornerArchive']['path'],allow_pickle=False) as ca:tc.require(set(ca.files)==set(ea) and all(ca[k].dtype==v.dtype and ca[k].shape==v.shape and ca[k].tobytes()==v.tobytes() for k,v in ea.items()),'Exact authoritative f64 PNT and original corner provenance')
    proof=discrete(P,rows['POSITION'],F,H,field(c));contour=contour_guard(P,rows['POSITION'],F,H,c,pins);tc.require(contour==r['noUnintendedShelfSourceProfileGuard'],'Standing no-shelf profile proof changed');tc.require(proof==r['proof'] and int(changed.sum())==r['changedActiveRows'] and int(shade.sum())==r['transportedShadingActiveRows'],'Proof/count mismatch');pins.update({str(path):tc.sha(path),r['candidate']:r['candidateSha256'],r['nativeCornerArchive']['path']:r['nativeCornerArchive']['sha256']});return {'receipt':r,'candidate':Path(r['candidate']),'inputs':pins,'primitiveInventory':[{'primitive':0,'part':'legl','material':doc['meshes'][0]['primitives'][0]['material'],'faces':len(F),'changedRows':int(changed.sum())}]}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approval',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();rp=execute(a.approval,a.output);print(json.dumps({'receipt':str(rp),'sha256':tc.sha(rp)}),flush=True)



