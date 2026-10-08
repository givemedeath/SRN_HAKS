"""Independent scratch equation replays. Historical producer Python is inert.

These functions create no verified baseline, representation context or approval.
The full factory must additionally consume a fresh sealed original-bank proof.
"""
from pathlib import Path
import json
import numpy as np
from diagnostic_descendant_representation import read_glb,accessor,embedded_maps,RepresentationError,strict_json

ATTRS=('positions','normals','uvGltf','uvNative','tangents')
def require(x,message):
 if not x: raise RepresentationError(message)
def exact(x,y,label):
 require(x.shape==y.shape and x.dtype==y.dtype and x.tobytes()==y.tobytes(),label)
def close(x,y,bound,label):
 require(x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all() and np.max(abs(x-y),initial=0)<=bound,label)
def unit(x):
 n=np.linalg.norm(x,axis=-1,keepdims=True);require(np.isfinite(x).all() and (n>0).all(),'Nonzero finite vectors required');return x/n
def raw(path):
 doc,b=read_glb(path);out={k:[] for k in ATTRS};materials=[]
 def n(v):return np.stack((v[...,0],-v[...,2],v[...,1]),axis=-1)
 for p in doc['meshes'][0]['primitives']:
  ids=accessor(doc,b,p['indices']).reshape(-1,3).astype(int);at=p['attributes']
  for k,a in [('positions','POSITION'),('normals','NORMAL'),('uvGltf','TEXCOORD_0')]:
   q=accessor(doc,b,at[a])[ids].astype(float);out[k].append(n(q) if k!='uvGltf' else q)
  u=out['uvGltf'][-1];out['uvNative'].append(np.stack((u[...,0],1-u[...,1]),axis=-1))
  require('TANGENT'in at,'Explicit original thigh tangents required');t=accessor(doc,b,at['TANGENT'])[ids].astype(float);t[...,:3]=n(t[...,:3]);out['tangents'].append(t);materials.extend([p.get('material',0)]*len(ids))
 return doc,b,{k:np.concatenate(v) for k,v in out.items()},np.asarray(materials)
def node(receipt,*,baseline=False):
 p=Path(receipt);g=strict_json(p);pr={}if baseline else strict_json(p.parent/'proof.json');a=dict(np.load(g['nativeCornerArchive']['path'],allow_pickle=False));lp=p.parent/'encoded-and-native-protected-lineage.npz';l=dict(np.load(lp,allow_pickle=False))if lp.exists()else None
 return {'path':p,'g':g,'proof':pr,'native':a,'lineage':l,'raw':raw(g['candidate'])}
def preserved_maps(n,s,*,chart_daughter=False,normal_patch_ids=None):
 d,b,_,_=n['raw'];sd,sb,_,_=s['raw']
 if normal_patch_ids is None:require(b[:len(sb)]==sb,'Original BIN prefix changed')
 else:
  require(d==sd and len(b)==len(sb),'In-place N/T patch changed GLB structure');allow=np.zeros(len(b),bool);cursor=0
  for primitive in d['meshes'][0]['primitives']:
   triangles=accessor(d,b,primitive['indices']).reshape(-1,3);selected=np.isin(np.arange(cursor,cursor+len(triangles)),normal_patch_ids);cursor+=len(triangles)
   require(not np.intersect1d(triangles[selected],triangles[~selected]).size,'Generated patch shares protected vertex')
   for semantic in ('NORMAL','TANGENT'):
    a=d['accessors'][primitive['attributes'][semantic]];view=d['bufferViews'][a['bufferView']];require(a['componentType']==5126,'Literal generated patch must f32');stride=view.get('byteStride',12 if semantic=='NORMAL'else 16);base=view.get('byteOffset',0)+a.get('byteOffset',0)
    for vertex in np.unique(triangles[selected]):allow[base+int(vertex)*stride:base+int(vertex)*stride+12]=True
  require(np.array_equal(np.frombuffer(b,dtype='u1')[~allow],np.frombuffer(sb,dtype='u1')[~allow]),'Changed non-generated-N/T binary byte')
 require(embedded_maps(d,b)==embedded_maps(sd,sb),'Original embedded maps changed')
 for k in ('nodes','scenes','scene','images','samplers'):require(d.get(k)==sd.get(k),'Original scene/maps changed: '+k)
 if chart_daughter:require(d['textures'][:len(sd['textures'])]==sd['textures']and all(t in sd['textures']for t in d['textures']),'Chart texture copies changed definitions')
 else:require(d.get('textures')==sd.get('textures'),'Original texture definitions changed')
 count=1 if chart_daughter else len(sd['materials']);require(d['materials'][:count]==sd['materials'][:count],'Original material definitions changed')
 if chart_daughter:
  def semantic(v):
   if isinstance(v,dict):return {k:(d['textures'][x]if k=='index'else semantic(x))for k,x in v.items()if k!='name'}
   return v
  require(semantic(d['materials'][0])==semantic(d['materials'][1]),'New cap material is not exact original skin')
def serialization(n,order=None):
 _,_,r,_=n['raw'];a=n['lineage'];order=np.arange(len(r['positions']))if order is None else order
 for k in ('positions','normals','uvGltf','tangents'):
  q=a['encoded_'+k][order].astype('f4').astype(float);exact(r[k],q,'Encoded serialization mismatch: '+k)
def cap_edges(P,ids):
 vertices,v=np.unique(P.reshape(-1,3),axis=0,return_inverse=True);v=v.reshape(-1,3);es=np.r_[v[:,[0,1]],v[:,[1,2]],v[:,[2,0]]];sign=np.where(es[:,0]<es[:,1],1,-1);e,inv,count=np.unique(np.sort(es,axis=1),axis=0,return_inverse=True,return_counts=True);direction=np.bincount(inv,weights=sign);lookup={tuple(x):(int(c),int(d))for x,c,d in zip(e,count,direction)};ce=np.unique(np.sort(np.r_[v[ids][:,[0,1]],v[ids][:,[1,2]],v[ids][:,[2,0]]],axis=1),axis=0);require(all(lookup[tuple(x)]==(2,0)for x in ce),'New cap exact edge closure/winding failure')
 require((np.linalg.norm(np.cross(P[ids,1]-P[ids,0],P[ids,2]-P[ids,0]),axis=-1)>0).all(),'Degenerate cap face')
def dome(boundary,center,depth,sign,rings):
 n=len(boundary);delta=boundary[:,:2]-center;nodes=[]
 for t in np.linspace(0,np.pi/2,rings+1)[:-1]:
  q=np.zeros((n,3));q[:,:2]=center+delta*np.cos(t);q[:,2]=boundary[:,2]+sign*depth*np.sin(t);nodes.extend(q)
 nodes=np.asarray(nodes);nodes[:n]=boundary;nodes=np.vstack((nodes,[*center,boundary[0,2]+sign*depth]));faces=[]
 for r in range(rings-1):
  for j in range(n):
   k=(j+1)%n;a=r*n+j;b=r*n+k;c=(r+1)*n+j;d=(r+1)*n+k;faces.extend([[b,a,c],[b,c,d]])
 for j in range(n):faces.append([(rings-1)*n+(j+1)%n,(rings-1)*n+j,rings*n])
 f=np.asarray(faces);p=nodes[f];cross=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);N=np.zeros_like(nodes)
 for j in range(3):np.add.at(N,f[:,j],cross)
 N=unit(N);radius=np.linalg.norm(delta,axis=1).max();uv=np.clip((nodes[:,:2]-center)/(2*radius)+.5,0,1);u=uv[f];dp1=p[:,1]-p[:,0];dp2=p[:,2]-p[:,0];du1=u[:,1]-u[:,0];du2=u[:,2]-u[:,0];den=du1[:,0]*du2[:,1]-du1[:,1]*du2[:,0];require((abs(den)>1e-14).all(),'Degenerate cap chart');baseT=(dp1*du2[:,1,None]-dp2*du1[:,1,None])/den[:,None];baseB=(-dp1*du2[:,0,None]+dp2*du1[:,0,None])/den[:,None];nn=N[f];T=np.broadcast_to(baseT[:,None],nn.shape).copy();T=unit(T-nn*np.sum(T*nn,axis=-1)[...,None]);W=np.where(np.sum(np.cross(nn,T)*baseB[:,None],axis=-1)>=0,1.,-1.);return nodes,f,N,u,np.concatenate((T,W[...,None]),axis=-1)
def literal_historical_cut_weights(P,cut,keep_above,*,precision='f4'):
 # Original NumPy weak-scalar f32 edge fraction, then f32(1-t), stored f64.
 # This is a precision operation, not an enlarged sum-to-one tolerance.
 p=P.astype(precision);parents=[];rows=[]
 for face,tri in enumerate(p):
  flags=tri[:,2]>=cut if keep_above else tri[:,2]<=cut
  if flags.all():parents.append(face);rows.append(np.eye(3));continue
  if not flags.any():continue
  polygon=[]
  for a,b in ((0,1),(1,2),(2,0)):
   if flags[a]:polygon.append(np.eye(3)[a])
   if flags[a]!=flags[b]:
    t=(cut-tri[a,2])/(tri[b,2]-tri[a,2]);w=np.zeros(3);w[a]=1-t;w[b]=t;polygon.append(w)
  for j in range(1,len(polygon)-1):parents.append(face);rows.append(np.asarray((polygon[0],polygon[j],polygon[j+1])))
 return np.asarray(parents),np.asarray(rows)
def literal_historical_encoded_cut_positions(P,parents,w,cut,*,precision='f4'):
 # Historical encoded shared-edge protocol rounded source endpoints to12places.
 # It is reproduced explicitly; no native/original corner is newly rounded.
 out=np.einsum('fci,fij->fcj',w,P[parents]);cache={}
 for face in range(len(w)):
  for corner in range(3):
   active=np.flatnonzero(abs(w[face,corner])>1e-15)
   if len(active)!=2:continue
   endpoints=P[parents[face],active].astype(precision);key=tuple(sorted(tuple(np.round(p,12))for p in endpoints))
   if key not in cache:
    a,b=np.asarray(key[0]),np.asarray(key[1]);t=(cut-a[2])/(b[2]-a[2]);q=a+t*(b-a);q[2]=cut;cache[key]=q
   out[face,corner]=cache[key]
 return out
def validate_cut_cap(n,s,*,proximal=False):
 a=n['lineage'];z=n['native'];old=s['native'];_,_,src,sm=s['raw'];pr=n['proof'];w=a['sourceCutBarycentricWeights'];count=len(w);parents=a['directParentFaceIds'][:count]if'directParentFaceIds'in a else a['sourceFaceIds'][:count];new=a['newGeneratedCapFaceIds']if'newGeneratedCapFaceIds'in a else a['generatedCapFaceIds'];require(np.array_equal(new,np.arange(count,len(z['positions']))),'Generated cap ancestry range');whole=np.all(w==np.eye(3),axis=(1,2));require(np.array_equal(a['retainedOutputFaceIds'],np.flatnonzero(whole)),'Retained whole face IDs');computedParent,computedW=literal_historical_cut_weights(src['positions'],pr['cut'],not proximal);exact(w,computedW,'Literal f32 cut edge fraction replay');require(np.array_equal(parents,computedParent),'Literal cut parent sequence')
 for k in ATTRS:
  sourceUVN=np.stack((src['uvGltf'][...,0].astype('f4'),1-src['uvGltf'][...,1].astype('f4')),axis=-1).astype(float)
  original=sourceUVN if k=='uvNative'else src[k]
  q=literal_historical_encoded_cut_positions(src[k],parents,w,pr['cut'])if k=='positions'else np.einsum('fci,fij->fcj',w,original[parents]);q[whole]=original[parents[whole]];close(q,a['encoded_'+k][:count],2e-14,'Encoded source cut replay: '+k)
  q=np.einsum('fci,fij->fcj',w,old[k][parents]);q[whole]=old[k][parents[whole]]
  if k=='positions':
   exact(q,a['newSplitNativeBarycentricPositionsBeforeWeld'],'Native pre-weld replay');delta=a['newSplitNativePositionWeldDeltas'];q+=delta;require((delta[whole]==0).all(),'Retained original corner weld forbidden');require((delta[a['newSplitCanonicalSeamIDs']<0]==0).all(),'Undeclared seam weld');require(abs(delta).max()<=pr['newSplitPositionWeldPolicy']['maximumNativeBarycentricDeltaMeters'],'Operator-specific weld bound')
  close(q,z[k][:count],2e-14,'Native source cut replay: '+k);exact(z[k][:count][whole],old[k][parents[whole]],'Protected native source attribute: '+k);exact(a['encoded_'+k][:count][whole],original[parents[whole]],'Protected encoded source attribute: '+k)
 cursor=count
 for domain,c in zip(pr['capDomains'],pr['caps']):
  br=np.asarray(domain['sourceRetainedBoundaryRows']);rim=a['encoded_positions'][br[:,0],br[:,1]];nnodes,f,N,U,T=dome(rim,np.asarray(domain['centerXY']),domain['depthMeters'],domain['poleExpectedAxisSign'],(c['triangleCount']//c['boundaryCount']+1)//2);nativeNodes=nnodes.copy();nativeNodes[:len(rim)]=z['positions'][br[:,0],br[:,1]];nativeN=N.copy()
  if proximal:
   seam=a['encoded_normals'][br[:,0],br[:,1]];geom=N.copy();N[:len(rim)]=seam;N[len(rim):2*len(rim)]=unit(.5*seam+.5*geom[len(rim):2*len(rim)]);nativeN=N.copy();nativeN[:len(rim)]=z['normals'][br[:,0],br[:,1]];normalUnit=unit(N[f]);T[...,:3]=unit(T[...,:3]-normalUnit*np.sum(T[...,:3]*normalUnit,axis=-1)[...,None]);U=U*np.asarray(pr['capUVPositiveUniformJacobian'])+np.asarray(pr['capUVTranslation'])
  ids=np.arange(cursor,cursor+len(f));close(a['encoded_positions'][ids],nnodes[f],2e-14,'Dome encoded P');close(z['positions'][ids],nativeNodes[f],2e-14,'Dome native P');close(a['encoded_normals'][ids],N[f],2e-14,'Dome encoded N');close(z['normals'][ids],nativeN[f],2e-14,'Dome native N');close(a['encoded_tangents'][ids],T,2e-14,'Dome authored tangent');close(z['tangents'][ids],T,2e-14,'Dome native tangent');close(a['encoded_uvGltf'][ids],U,2e-14,'Dome chart');close(z['uvGltf'][ids],U,2e-14,'Dome native chart');cursor+=len(f)
 require(cursor==len(z['positions']),'Extra cap faces');order=np.r_[*[np.flatnonzero(sm[parents]==mid)for mid in np.unique(sm)],new];serialization(n,order);preserved_maps(n,s);cap_edges(z['positions'],new);cap_edges(n['raw'][2]['positions'],np.flatnonzero(order>=count));return {'kind':'proximal-cut-cap'if proximal else'distal-cut-cap','newFaces':len(new),'positiveJ':'not-applicable cut and cap'}
def validate_chart(n,s,support):
 pr=n['proof'];old=s['native'];z=n['native'];caps=old['generatedCapFaceIds'];hold=np.ones(len(old['positions']),bool);hold[caps]=False;_,_,src,_=s['raw'];_,_,actual,_=n['raw']
 for k in ('positions','normals','tangents'):exact(z[k],old[k],'Chart changed native '+k);exact(actual[k],src[k],'Chart changed encoded '+k)
 for k in ('uvGltf','uvNative'):exact(z[k][hold],old[k][hold],'Chart changed retained native UV')
 exact(actual['uvGltf'][hold],src['uvGltf'][hold],'Chart changed retained encoded UV');scale=np.asarray(pr['newUVJacobianDiagonal']);offset=np.asarray(pr['UVTranslation']);require(scale[0]==scale[1]>0,'Chart scale must positive isotropic');expected=src['uvGltf'][caps]*scale+offset;exact(actual['uvGltf'][caps],expected.astype('f4').astype(float),'Chart equation serialization');exact(z['uvGltf'][caps],actual['uvGltf'][caps],'Native chart explicit f32-output grounding');skin_support(actual['uvGltf'][caps],support,n['g']['part']);preserved_maps(n,s,chart_daughter=True);return {'kind':'chart-only','generatedFaces':len(caps)}
def skin_support(uv,support,part):
 mask=dict(np.load(support['cases'][part]['mask']['path'],allow_pickle=False));patch=np.asarray(support['cases'][part]['candidates'][0]['pixelRectXYExclusive']);p=uv.reshape(-1,2)*2048;lo=p.min(0);hi=p.max(0);require(np.r_[lo-patch[:2],patch[2:]-hi].min()>=4,'Skin chart padding');a=np.floor(lo-.5).astype(int);b=np.floor(hi-.5).astype(int)+1;sl=np.s_[a[1]:b[1]+1,a[0]:b[0]+1];require(mask['safeSkinOnlyNeutral'][sl].all()and mask['sourceSkinFootprint'][sl].all()and not mask['sourceClothFootprint'][sl].any(),'Bilinear support not exclusively original skin')
def normal_polish(P,N,T,ids,cut,depth,sign):
 cap=np.zeros(len(P),bool);cap[ids]=True;vertices,v=np.unique(P.reshape(-1,3),axis=0,return_inverse=True);v=v.reshape(-1,3);boundary=np.intersect1d(np.unique(v[cap]),np.unique(v[~cap]));q=vertices[boundary];require(len(q)>=3 and abs(q[:,2]-cut).max()<=1e-7,'Literal cap seam domain');summed=np.zeros_like(vertices)
 for j in range(3):np.add.at(summed,v[~cap,j],N[~cap,j])
 seam=unit(summed[boundary]);flat=P[ids].reshape(-1,3);pole=flat[np.argmax(sign*(flat[:,2]-cut))];center=pole[:2];angle=np.arctan2(q[:,1]-center[1],q[:,0]-center[0]);order=np.argsort(angle);angle=angle[order];seam=seam[order];require((np.diff(angle)>1e-12).all(),'Duplicate angular samples');theta=np.arctan2(flat[:,1]-center[1],flat[:,0]-center[0]);extended=np.r_[angle[-1]-2*np.pi,angle,angle[0]+2*np.pi];values=np.vstack((seam[-1],seam,seam[0]));interpolated=unit(np.column_stack([np.interp(theta,extended,values[:,j])for j in range(3)]));progress=np.clip(sign*(flat[:,2]-cut)/depth,0,1);lookup={int(k):unit(summed[k])for k in boundary}
 for i,k in enumerate(v[ids].reshape(-1)):
  if int(k)in lookup:interpolated[i]=lookup[int(k)];progress[i]=0
 weight=1-progress**2*(3-2*progress);corrected=unit(unit(N[ids].reshape(-1,3))*(1-weight[:,None])+interpolated*weight[:,None]);direction=unit(T[ids,:,:3].reshape(-1,3)-corrected*np.sum(T[ids,:,:3].reshape(-1,3)*corrected,axis=-1)[:,None]);outN=N.copy();outT=T.copy();outN[ids]=corrected.reshape(-1,3,3);outT[ids,:,:3]=direction.reshape(-1,3,3);return outN,outT

def normal_polish_domain(source, selected):
 if not isinstance(selected,list) or not selected or not all(type(x)is int for x in selected):raise RepresentationError('Generated normal-polish face IDs must be explicit integers')
 ids=np.asarray(selected,dtype=np.int64)
 require(len(np.unique(ids))==len(ids),'Repeated normal-polish face ID')
 require(np.all(ids>=0)and np.all(ids<len(source['positions'])),'Normal-polish face out of range')
 require(np.isin(ids,source['generatedCapFaceIds']).all()and np.isin(ids,source['inheritedGeneratedCapFaceIds']).all(),'Normal polish crosses generated inherited knee-cap domain')
 require(np.all(source['sourceFaceIds'][ids]==-1),'Normal polish touches original authored source faces')
 return ids

def validate_normal_polish(n,s):
 pr=n['proof'];old=s['native'];z=n['native'];ids=normal_polish_domain(old,pr['selectedKneeCapFaceIds']);_,_,src,_=s['raw'];_,_,actual,_=n['raw'];cut=-.45170098543167114;depth=.025
 for key in old:
  if key not in ('normals','tangents'):exact(z[key],old[key],'Normal polish changed native '+key)
 for k in ('positions','uvGltf','uvNative'):exact(actual[k],src[k],'Normal polish changed encoded '+k)
 N,T=normal_polish(old['positions'],old['normals'],old['tangents'],ids,cut,depth,-1)
 exact(z['normals'],N,'Native normal polish N equation');exact(z['tangents'],T,'Native normal polish T equation')
 encodedN=src['normals'].copy();encodedT=src['tangents'].copy();encodedN[ids]=N[ids].astype('f4').astype(float);encodedT[ids,:,:3]=T[ids,:,:3].astype('f4').astype(float)
 exact(actual['normals'],encodedN,'Encoded cap N native-result-to-f32 protocol');exact(actual['tangents'],encodedT,'Encoded cap T native-result-to-f32 protocol')
 preserved_maps(n,s,normal_patch_ids=ids);return {'kind':'generated-knee-normal-polish','generatedFaces':len(ids)}
def validate_precision(n,s):
 before=s['lineage'];after=n['lineage'];ids=before['newGeneratedCapFaceIds'];held=np.ones(len(before['encoded_positions']),bool);held[ids]=False
 require(before.keys()==after.keys(),'Precision lineage schema changed')
 for k in before:
  if k not in ('encoded_normals','encoded_tangents'):exact(before[k],after[k],'Precision protected lineage '+k)
 N=unit(before['encoded_normals'][ids]);T=before['encoded_tangents'][ids].copy();length=np.linalg.norm(T[...,:3],axis=-1);T[...,:3]=unit(T[...,:3]-N*np.sum(T[...,:3]*N,axis=-1)[...,None])*length[...,None];exact(N,after['encoded_normals'][ids],'Precision normalization equation');exact(T,after['encoded_tangents'][ids],'Precision tangent projection equation')
 for k in ('encoded_normals','encoded_tangents'):exact(before[k][held],after[k][held],'Precision retained source '+k)
 for k in n['native']:exact(n['native'][k],s['native'][k],'Precision changed native '+k)
 serialization(n);preserved_maps(n,s);return {'kind':'encoded-new-cap-normal-tangent-precision','generatedFaces':len(ids)}

def axial(P,N,T,B,L,C,H):
 d=-np.sum(P*B[2],axis=-1);u=np.minimum(np.maximum(d/H,0),1);scale=1+C/(L-C-H/2);S=10*u**3-15*u**4+6*u**5;I=np.where(d<H,H*(2.5*u**4-3*u**5+u**6),d-H/2);I=np.where(d>0,I,0);J=np.where(d>0,1+(scale-1)*S,1);Q=P-(scale-1)*I[...,None]*B[2];Q[d<=0]=P[d<=0];nn=N@B.T;nn[...,2]/=J;nn*=np.linalg.norm(N,axis=-1)[...,None]/np.linalg.norm(nn,axis=-1)[...,None];NN=nn@B;NN[d<=0]=N[d<=0];tt=T[...,:3]@B.T;tt[...,2]*=J;tt*=np.linalg.norm(T[...,:3],axis=-1)[...,None]/np.linalg.norm(tt,axis=-1)[...,None];TT=T.copy();TT[...,:3]=tt@B;TT[d<=0]=T[d<=0];return Q,NN,TT,J
def validate_axial(n,s,support):
 a=n['lineage'];z=n['native'];old=s['native'];g=n['g'];pr=n['proof'];_,_,src,sm=s['raw'];B=np.asarray(g['axialField']['properAxisBasisRows']);L=g['axialField']['sourceTrueAxisHipToKneeLength'];C=g['axialField']['sourceCutAboveBindKnee'];H=g['axialField']['hipProtectedTransitionLength'];require(np.linalg.det(B)>0,'Improper thigh frame');close(B@B.T,np.eye(3),2e-15,'Thigh frame not orthonormal');require(H==.04 and abs(C-.13)<2e-8 and 0<C<L-H,'Unsupported explicit actual 130mm cut policy');w=a['sourceCutBarycentricWeights'];count=len(w);parents=a['directParentFaceIds'][:count];new=z['newGeneratedCapFaceIds'];whole=np.all(w==np.eye(3),axis=(1,2));axis=src['positions']@B.T;expectedParent,expectedW=literal_historical_cut_weights(axis,g['axisPlaneCoordinate'],True,precision='f8');exact(w,expectedW,'True-axis source cut weight equation');require(np.array_equal(parents,expectedParent),'True-axis cut parent sequence');preEncoded=literal_historical_encoded_cut_positions(axis,parents,w,g['axisPlaneCoordinate'],precision='f8')@B;preEncoded[whole]=src['positions'][parents[whole]];close(preEncoded,a['preProfileEncodedPositions'],2e-15,'Encoded pre-field exact source clip');preNative=np.einsum('fci,fij->fcj',w,old['positions'][parents]);preNative[whole]=old['positions'][parents[whole]];exact(preNative,a['newSplitNativeBarycentricPositionsBeforeWeld'],'Native source cut arithmetic');delta=a['newSplitNativePositionWeldDeltas'];require((delta[whole]==0).all()and(delta[a['newSplitCanonicalSeamIDs']<0]==0).all(),'Axial native weld changed original corner');require(abs(delta).max()<=pr['newSplitPositionWeldPolicy']['maximumNativeBarycentricDeltaMeters'],'Axial op-specific seam weld exceeded');preNative+=delta;exact(preNative,a['preProfileNativePositions'],'Axial native pre-field provenance')
 ranges={}
 for name,source,pre,result in [('encoded',src,preEncoded,{k:a['encoded_'+k]for k in ATTRS}),('native',old,preNative,z)]:
  inputs={}
  for k in ('normals','tangents','uvGltf'):
   q=np.einsum('fci,fij->fcj',w,source[k][parents]);q[whole]=source[k][parents[whole]];inputs[k]=q
  Q,N,T,J=axial(pre,inputs['normals'],inputs['tangents'],B,L,C,H);require(J.min()>=1,'Axial nonpositive determinant');ranges[name]=[float(J.min()),float(J.max())]
  for k,q in [('positions',Q),('normals',N),('tangents',T)]:close(result[k][:count],q,2e-14,'Axial independent attribute '+name+':'+k)
  close((result['positions'][:count]-pre)@B[:2].T,np.zeros((*pre.shape[:2],2)),2e-16,'Axial operation changed width');exact(result['tangents'][:count,:,3],inputs['tangents'][...,3],'Axial handedness changed');close(result['uvGltf'][:count],inputs['uvGltf'],1e-15,'Axial source UV changed');protected=np.asarray(a['protectedEncodedCornerMask'if name=='encoded'else'protectedNativeCornerMask']);
  for k in ('positions','normals','tangents','uvGltf'):exact(result[k][:count][protected],source[k][parents][protected],'Axial protected hip '+name+':'+k)
 order=np.r_[*[np.flatnonzero(sm[parents]==mid)for mid in np.unique(sm)],new];serialization(n,order);preserved_maps(n,s);skin_support(n['raw'][2]['uvGltf'][np.argsort(order)][new],support,g['part']);cap_edges(z['positions'],new);cap_edges(n['raw'][2]['positions'],np.flatnonzero(order>=count))
 # Reconstruct the encoded dome independently, then explicit native rim copy.
 for domain,c in zip(pr['capDomains'],pr['caps']):
  br=np.asarray(domain['sourceRetainedBoundaryRows']);rim=a['encoded_positions'][br[:,0],br[:,1]];nodes,f,N,U,T=dome(rim@B.T,np.asarray(domain['centerXY']),domain['depthMeters'],-1,(c['triangleCount']//c['boundaryCount']+1)//2);nodes=nodes@B;N=N@B;T[...,:3]=T[...,:3]@B;seam=unit(a['encoded_normals'][br[:,0],br[:,1]]);nb=len(rim);geom=N.copy();N[:nb]=seam;N[nb:2*nb]=unit(.5*seam+.5*geom[nb:2*nb]);T[...,:3]=unit(T[...,:3]-unit(N[f])*np.sum(T[...,:3]*unit(N[f]),axis=-1)[...,None]);nativeNodes=nodes.copy();nativeNodes[:nb]=z['positions'][br[:,0],br[:,1]];nativeN=N.copy();nativeN[:nb]=unit(z['normals'][br[:,0],br[:,1]]);nativeT=T.copy();nativeT[...,:3]=unit(nativeT[...,:3]-unit(nativeN[f])*np.sum(nativeT[...,:3]*unit(nativeN[f]),axis=-1)[...,None]);close(a['encoded_positions'][new],nodes[f],2e-14,'Axial generated dome P');close(z['positions'][new],nativeNodes[f],2e-14,'Axial native generated dome P');close(a['encoded_normals'][new],N[f],2e-14,'Axial generated N blend');close(z['normals'][new],nativeN[f],2e-14,'Axial native generated N blend');close(a['encoded_tangents'][new],T,2e-14,'Axial generated T');close(z['tangents'][new],nativeT,2e-14,'Axial native generated T');U=U*np.asarray(pr['capUVPositiveUniformJacobian'])+np.asarray(pr['capUVTranslation']);close(a['encoded_uvGltf'][new],U,2e-14,'Axial cap original-skin chart')
 return {'kind':'true-axis-130mm-chop-axial-elongation','positiveJacobianRanges':ranges,'newFaces':len(new)}

def radial_mapping(P,B,hinge,z,radii,target,*,expanded_equation=False):
 slopes=np.gradient(radii,z,axis=0)
 def angle(table,theta):
  u=np.mod(theta,2*np.pi)*table.shape[-1]/(2*np.pi);i=np.floor(u).astype(int);v=u-i;return table[...,i]*(1-v)+table[...,(i+1)%table.shape[-1]]*v
 def H(a,b,da,db,t,h):
  if expanded_equation:return (1-3*t*t+2*t*t*t)*a+(t-2*t*t+t*t*t)*h*da+(3*t*t-2*t*t*t)*b+(t*t*t-t*t)*h*db
  return (2*t**3-3*t*t+1)*a+(t**3-2*t*t+t)*h*da+(-2*t**3+3*t*t)*b+(t**3-t*t)*h*db
 q=(P-hinge)@B.T;flat=q.reshape(-1,3);out=flat.copy();mask=(flat[:,2]<z[0])&(flat[:,2]>=-1e-4);x=flat[mask];theta=np.arctan2(x[:,1],x[:,0]);t=np.clip((x[:,2]-z[0])/(z[-1]-z[0]),0,1);rad=angle(radii,theta);sl=angle(slopes,theta);i=np.clip(np.floor(t*(len(z)-1)).astype(int),0,len(z)-2);u=t*(len(z)-1)-i;j=np.arange(len(x));source=H(rad[i,j],rad[i+1,j],sl[i,j],sl[i+1,j],u,z[1]-z[0]);end=angle(target,theta);delta=end-rad[0];m0=(z[-1]-z[0])*sl[0];m0=np.sign(delta)*np.minimum(np.maximum(np.sign(delta)*m0,0),3*abs(delta));desired=H(rad[0],end,m0,0,t,1);v=np.clip((z[0]-x[:,2])/.016,0,1);blend=v**3*(10-15*v+6*v*v);desired=source*(1-blend)+desired*blend;require((source>0).all()and(desired>0).all(),'Nonpositive actual radial field');out[mask,:2]=x[:,:2]*(desired/source)[:,None];result=out.reshape(q.shape)@B+hinge;result[~mask.reshape(q.shape[:-1])]=P[~mask.reshape(q.shape[:-1])];return result
def radial_attributes(source,B,hinge,z,radii,target):
 result={k:v.copy()for k,v in source.items()};P=source['positions'];Q=radial_mapping(P,B,hinge,z,radii,target);changed=np.any(Q!=P,axis=-1);result['positions']=Q;q=P[changed];J=np.empty((len(q),3,3));step=1e-6
 for k in range(3):
  delta=np.zeros(3);delta[k]=step;J[:,:,k]=(radial_mapping(q+delta,B,hinge,z,radii,target)-radial_mapping(q-delta,B,hinge,z,radii,target))/(2*step)
 terminal=((q-hinge)@B[2])<2e-6
 if terminal.any():
  dz=(radial_mapping(q[terminal]+B[2]*step,B,hinge,z,radii,target)-radial_mapping(q[terminal],B,hinge,z,radii,target))/step;oldZ=np.einsum('ijk,k->ij',J[terminal],B[2]);J[terminal]+=np.einsum('ij,k->ijk',dz-oldZ,B[2])
 determinant=np.linalg.det(J);require(len(determinant)>0 and determinant.min()>0,'Actual radial J not positive');N=source['normals'][changed];nn=np.linalg.solve(J.swapaxes(1,2),N[...,None])[...,0];nn=nn/np.linalg.norm(nn,axis=1)[:,None]*np.linalg.norm(N,axis=1)[:,None];result['normals'][changed]=nn;T=source['tangents'][changed];tt=np.einsum('ijk,ik->ij',J,T[:,:3]);nu=nn/np.linalg.norm(nn,axis=1)[:,None];tt-=nu*np.sum(tt*nu,axis=1)[:,None];tt=tt/np.linalg.norm(tt,axis=1)[:,None]*np.linalg.norm(T[:,:3],axis=1)[:,None];result['tangents'][changed,:3]=tt;return result,changed,determinant
def validate_radial(n,s,support):
 a=n['lineage'];z=n['native'];old=s['native'];pr=n['proof'];_,_,src,_=s['raw'];count=int(old['newGeneratedCapFaceIds'].min());new=z['newGeneratedCapFaceIds'];held=z['inheritedGeneratedCapFaceIds'];require(np.array_equal(new,np.arange(count,len(z['positions']))),'Radial new cap IDs');require(np.array_equal(held,old['inheritedGeneratedCapFaceIds']),'Radial inherited hip IDs');require(np.array_equal(z['directParentFaceIds'][:count],np.arange(count))and(z['directParentFaceIds'][new]==-1).all(),'Radial direct parent lineage');B=a['properAxisBasisRows'];hinge=a['hingeCenterOwnerLocal'];stations=a['sourceZ'];radii=a['sourceContourRadii'];target=a['targetRadii'];exact(stations,np.linspace(.12,0,61),'Actual lower120mm station policy');require(radii.shape==(61,720)and target.shape==(720,),'Finite radial contour chart dimensions');close(B@B.T,np.eye(3),2e-15,'Radial basis not proper orthonormal');require(np.linalg.det(B)>0,'Radial basis reflected');ranges={}
 for name,source,result,mask in [('native',{k:old[k][:count]for k in ATTRS},z,a['nativeProfileChangedCornerMask']),('encoded',{k:src[k][:count].astype('f4')for k in ATTRS},{k:a['encoded_'+k]for k in ATTRS},a['encodedProfileChangedCornerMask'])]:
  for k in ('positions','normals','uvGltf','tangents'):exact(a['preProfile'+('Native_'if name=='native'else'Encoded_')+k],source[k],'Radial physical pre-profile source '+name+':'+k)
  out,changed,J=radial_attributes(source,B,hinge,stations,radii,target);require(np.array_equal(changed,mask),'Radial changed mask equation');ranges[name]=[float(J.min()),float(J.max())]
  for k in ('positions','normals','tangents'):exact(result[k][:count].astype(out[k].dtype),out[k],'Radial literal operation arithmetic '+name+':'+k)
  alternative=radial_mapping(source['positions'],B,hinge,stations,radii,target,expanded_equation=True);close(out['positions'],alternative,2e-15,'Expanded independent radial equation');close((out['positions']-source['positions'])@B[2],np.zeros(source['positions'].shape[:2]),2e-16,'Radial operation changed limb axis')
  for k in ('positions','normals','uvGltf','tangents'):
   exact(result[k][:count][~mask].astype(source[k].dtype),source[k][~mask],'Protected radial source '+name+':'+k);exact(result[k][held].astype(source[k].dtype),source[k][held],'Protected hip '+name+':'+k)
  exact(result['uvGltf'][:count].astype(source['uvGltf'].dtype),source['uvGltf'],'Radial changed body UV');exact(result['tangents'][:count,:,3].astype(source['tangents'].dtype),source['tangents'][...,3],'Radial changed tangent signs');axis=(source['positions']-hinge)@B.T;negative=mask&(axis[...,2]<0);boundary=a['sourceBoundaryRows'];seam={tuple(x)for x in source['positions'][boundary[:,0],boundary[:,1]]};require(all(tuple(x)in seam for x in source['positions'][negative]),'Radial negative continuation exceeds literal seam')
 serialization(n);preserved_maps(n,s);skin_support(n['raw'][2]['uvGltf'][new],support,n['g']['part']);cap_edges(z['positions'],new);cap_edges(n['raw'][2]['positions'],new)
 br=a['sourceBoundaryRows'];nb=len(br);rim=a['encoded_positions'][br[:,0],br[:,1]];axisrim=(rim-hinge)@B.T;nodes=[]
 for latitude in range(12):
  angle=latitude*np.pi/24;q=axisrim.copy();q[:,:2]*=np.cos(angle);q[:,2]-=.04*np.sin(angle);nodes.extend(q)
 nodes=np.vstack((nodes,[0,0,axisrim[0,2]-.04]));nodes=nodes@B+hinge;nodes[:nb]=rim;close(nodes,a['capNodesEncoded'],2e-15,'Radial40mmcap equation');nativeNodes=nodes.copy();nativeNodes[:nb]=z['positions'][br[:,0],br[:,1]];close(nativeNodes,a['capNodesNative'],2e-15,'Radial native literal seam');f=[]
 for r in range(11):
  for j in range(nb):
   k=(j+1)%nb;v0=r*nb+j;v1=r*nb+k;v2=(r+1)*nb+j;v3=(r+1)*nb+k;f.extend([[v1,v0,v2],[v1,v2,v3]])
 for j in range(nb):f.append([11*nb+(j+1)%nb,11*nb+j,12*nb])
 f=np.asarray(f);require(np.array_equal(f,a['capFaces']),'Radial cap triangle topology');exact(a['encoded_positions'][new],a['capNodesEncoded'][f],'Encoded radial cap P');exact(z['positions'][new],a['capNodesNative'][f],'Native radial cap P')
 # New generated attributes have no source-face donor. Reconstruct the actual
 # axis-space cap geometry normals/chart derivative and authored seam blend.
 axisNodes,axisFaces,geomAxis,U,Taxis=dome(axisrim,np.zeros(2),.04,-1,12);require(np.array_equal(axisFaces,f),'Cap core angular topology');geom=geomAxis@B;close(geom,a['capNodesBeforeNormalBlend'],2e-15,'Generated geometric node N');N=geom.copy();seam=a['encoded_normals'][br[:,0],br[:,1]].astype('f4');seam=unit(seam);N[:nb]=seam;N[nb:2*nb]=unit(seam*.5+geom[nb:2*nb]*.5);T=Taxis.copy();T[...,:3]=T[...,:3]@B;Nfaces=N[f];T[...,:3]=unit(T[...,:3]-Nfaces*np.sum(T[...,:3]*Nfaces,axis=-1)[...,None]);nativeN=N.copy();nativeSeam=unit(z['normals'][br[:,0],br[:,1]]);nativeN[:nb]=nativeSeam;nativeN[nb:2*nb]=unit(.5*nativeSeam+.5*geom[nb:2*nb]);nativeT=T.copy();nativeNfaces=nativeN[f];nativeT[...,:3]=unit(nativeT[...,:3]-nativeNfaces*np.sum(nativeT[...,:3]*nativeNfaces,axis=-1)[...,None]);close(a['encoded_normals'][new],Nfaces,2e-15,'Encoded cap generated N/source seam blend');close(z['normals'][new],nativeNfaces,2e-15,'Native cap generated N/source seam blend');close(a['encoded_tangents'][new],T,2e-15,'Encoded generated UV derivative/T reprojection');close(z['tangents'][new],nativeT,2e-15,'Native generated T second reprojection');U=U*np.asarray(pr['capUVPositiveUniformScale'])+np.asarray(pr['capUVTranslation']);close(a['encoded_uvGltf'][new],U,2e-15,'Generated positive skin chart');close(z['uvGltf'][new],U,2e-15,'Native generated positive skin chart')
 return {'kind':'lower120mm-periodic-radial-field-40mm-cap','positiveJacobianRanges':ranges,'newFaces':len(new),'completeGeneratedCapNTReplay':True}
