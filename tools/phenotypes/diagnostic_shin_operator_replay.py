"""Finite exact shin descendant replay; historical scripts are inert provenance.
The native and serialized authorities remain separate; no runtime approvals.
"""
from pathlib import Path
import copy
import numpy as np
from diagnostic_thigh_operator_replay import *
from diagnostic_descendant_representation import sha
from measure_stock_target_basis import section_points

def validate_initial_cut_cap(n,s):
 proximal=False
 a=n['lineage'];z=n['native'];old=s['native'];_,_,src,sm=s['raw'];pr=n['proof'];w=a['sourceCutBarycentricWeights'];count=len(w);parents=a['directParentFaceIds'][:count]if'directParentFaceIds'in a else a['sourceFaceIds'][:count];new=a['newGeneratedCapFaceIds']if'newGeneratedCapFaceIds'in a else a['generatedCapFaceIds'];require(np.array_equal(new,np.arange(count,len(z['positions']))),'Generated cap ancestry range');whole=np.all(w==np.eye(3),axis=(1,2));require(np.array_equal(a['retainedOutputFaceIds'],np.flatnonzero(whole)),'Retained whole face IDs');computedParent,computedW=literal_historical_cut_weights(src['positions'],pr['cut'],False);exact(w,computedW,'Literal f32 cut edge fraction replay');require(np.array_equal(parents,computedParent),'Literal cut parent sequence')
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
def periodic_radius(contour,theta,center,radii):
 q=(contour[:,:2]-center[:2])/radii[:2];ang=np.mod(np.arctan2(q[:,1],q[:,0]),2*np.pi);order=np.argsort(ang);ang=ang[order];q=q[order];keep=np.r_[True,np.diff(ang)>1e-10];ang=ang[keep];q=q[keep]
 ang=np.r_[ang[-1]-2*np.pi,ang,ang[0]+2*np.pi];q=np.vstack((q[-1],q,q[0]));k=np.clip(np.searchsorted(ang,theta,side='right')-1,0,len(ang)-2);a=q[k];b=q[k+1];d=np.column_stack((np.cos(theta),np.sin(theta)));edge=b-a;den=d[:,0]*edge[:,1]-d[:,1]*edge[:,0];r=(a[:,0]*b[:,1]-a[:,1]*b[:,0])/den
 assert np.isfinite(r).all() and (r>0).all();return r
def hermite(r0,r1,d0,d1,t,span):
 return (2*t**3-3*t*t+1)*r0+(t**3-2*t*t+t)*span*d0+(-2*t**3+3*t*t)*r1+(t**3-t*t)*span*d1
def ellipsoid_cap(loop,center,radii,axis,rings=12):
 c=np.asarray(center);r=np.asarray(radii);boundary=loop['positions'];lat0=np.arcsin((boundary[0,2]-c[2])/r[2]);lat=np.linspace(lat0,axis*np.pi/2,rings+1)[:-1];theta=np.arctan2((boundary[:,1]-c[1])/r[1],(boundary[:,0]-c[0])/r[0]);n=len(boundary);nodes=np.concatenate([c+np.column_stack((r[0]*np.cos(a)*np.cos(theta),r[1]*np.cos(a)*np.sin(theta),np.full(n,r[2]*np.sin(a))))for a in lat]);nodes[:n]=boundary;pole=len(nodes);nodes=np.vstack((nodes,c+[0,0,axis*r[2]]));faces=[]
 for j in range(rings-1):
  for i in range(n):
   k=(i+1)%n;a=j*n+i;b=j*n+k;u=(j+1)*n+i;v=(j+1)*n+k;faces.extend([[b,a,u],[b,u,v]])
 for i in range(n):faces.append([(rings-1)*n+(i+1)%n,(rings-1)*n+i,pole])
 faces=np.asarray(faces);tri=nodes[faces];normal=(nodes-c)/r**2;normal/=np.linalg.norm(normal,axis=1)[:,None];cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);sign=np.sign(np.sum(cross*normal[faces].mean(1),axis=1));assert np.all(sign==1)
 uv=(nodes[:,:2]-c[:2])/(2*r.max())+.5;u=uv[faces];dp1=tri[:,1]-tri[:,0];dp2=tri[:,2]-tri[:,0];du1=u[:,1]-u[:,0];du2=u[:,2]-u[:,0];den=du1[:,0]*du2[:,1]-du1[:,1]*du2[:,0];assert (np.abs(den)>1e-14).all();t=(dp1*du2[:,1,None]-dp2*du1[:,1,None])/den[:,None];b=(-dp1*du2[:,0,None]+dp2*du1[:,0,None])/den[:,None];N=normal[faces];T=np.broadcast_to(t[:,None],N.shape).copy();T-=N*np.sum(T*N,axis=2)[...,None];T/=np.linalg.norm(T,axis=2)[...,None];ts=np.where(np.sum(np.cross(N,T)*b[:,None],axis=2)>=0,1.,-1.);T=np.concatenate((T,ts[...,None]),axis=2)
 return {'positions':tri,'normals':N,'uvGltf':u,'uvNative':np.stack((u[:,:,0],1-u[:,:,1]),axis=2),'tangents':T},{'nodes':nodes,'faces':faces,'boundaryCount':n,'boundaryExact':True,'generatedChartUntextured':True,'triangleCount':len(faces),'minDoubleArea':float(np.linalg.norm(cross,axis=1).min()),'pole':nodes[pole].tolist(),'normalZAtPole':float(normal[pole,2]),'tangentSigns':np.unique(ts).tolist()}
def map_profile(p,rec):
  p=np.asarray(p);shape=p.shape;flat=p.reshape(-1,3);out=flat.copy();t=(flat[:,2]-rec['sourceZ'][0])/(rec['sourceZ'][-1]-rec['sourceZ'][0]);mask=(t>0)&(t<=1.001);q=flat[mask];tt=t[mask];xy=(q[:,:2]-np.asarray(rec['center'])[:2])/np.asarray(rec['radii'])[:2];theta=np.mod(np.arctan2(xy[:,1],xy[:,0]),2*np.pi);rad=np.stack([periodic_radius(c,theta,np.asarray(rec['center']),np.asarray(rec['radii']))for c in [np.asarray(x)for x in rec['sourceContours']]]);h=np.asarray(rec['sourceZ'])[1]-np.asarray(rec['sourceZ'])[0];sl=np.gradient(rad,h,axis=0);i=np.clip((tt*34).astype(int),0,33);u=tt*34-i;j=np.arange(len(q));src=hermite(rad[i,j],rad[i+1,j],sl[i,j],sl[i+1,j],u,h);delta=1-rad[0];m0=(rec['sourceZ'][-1]-rec['sourceZ'][0])*sl[0];m0=np.sign(delta)*np.minimum(np.maximum(np.sign(delta)*m0,0),3*np.abs(delta));mono=hermite(rad[0],1,m0,0,tt,1);v=np.clip(tt*abs(rec['sourceZ'][-1]-rec['sourceZ'][0])/rec['gradualInteriorBlendMeters'],0,1);blend=v**3*(10+v*(-15+6*v));desired=src*(1-blend)+mono*blend;assert (src>0).all()and(desired>0).all();ratio=desired/src;out[mask,:2]=np.asarray(rec['center'])[:2]+(q[:,:2]-np.asarray(rec['center'])[:2])*ratio[:,None];s=tt*tt*(3-2*tt);out[mask,2]=q[:,2]-rec['sourceZ'][-1]*s;return out.reshape(shape)

def validate_shin_polish(n,s):
 pr=n['proof'];old=s['native'];z=n['native'];ids=np.asarray(pr['selectedKneeCapFaceIds'],dtype=int)
 require(ids.ndim==1 and len(np.unique(ids))==len(ids)and np.isin(ids,old['generatedCapFaceIds']).all()and np.all(old['sourceFaceIds'][ids]==-1),'Polish only source-generated cap')
 for k in old:
  if k not in ('normals','tangents'):exact(z[k],old[k],'Normal-only changed native '+k)
 N,T=normal_polish(old['positions'],old['normals'],old['tangents'],ids,-0.009999999776482582,.025,1)
 exact(z['normals'],N,'Native shin normal polish');exact(z['tangents'],T,'Native shin tangent polish')
 _,_,a,_=n['raw'];_,_,b,_=s['raw']
 for k in ('positions','uvGltf','uvNative'):exact(a[k],b[k],'Normal-only encoded '+k)
 en=b['normals'].copy();et=b['tangents'].copy();en[ids]=N[ids].astype('f4').astype(float);et[ids,:,:3]=T[ids,:,:3].astype('f4').astype(float)
 exact(a['normals'],en,'Encoded source cap N');exact(a['tangents'],et,'Encoded source cap T');preserved_maps(n,s,normal_patch_ids=ids)
 return {'kind':'shin-generated-normal-polish','faces':len(ids)}

def profile_attributes(P,N,T,rec):
 out=map_profile(P,rec);changed=np.any(out!=P,axis=-1);q=P[changed];J=np.empty((len(q),3,3));step=1e-6
 for axis in range(3):
  d=np.zeros(3);d[axis]=step;J[:,:,axis]=(map_profile(q+d,rec)-map_profile(q-d,rec))/(2*step)
 det=np.linalg.det(J);require(det.min()>0,'Positive equator Jacobian');NN=N.copy();TT=T.copy();nn=np.linalg.solve(np.swapaxes(J,1,2),N[changed,...,None])[...,0];nn=unit(nn);NN[changed]=nn;tt=np.einsum('ijk,ik->ij',J,T[changed,:3]);tt=unit(tt-nn*np.sum(tt*nn,axis=-1)[:,None]);TT[changed,:3]=tt
 return out,NN,TT,changed,det

def validate_equator(n,s,support):
 a=n['lineage'];z=n['native'];pr=n['proof'];rec=pr['profileContouring'];delta=np.asarray(rec['actualKneeDeltaFromPartLocal']);w=a['sourceCutBarycentricWeights'];count=len(w);ids=a['directParentFaceIds'][:count];new=a['newGeneratedCapFaceIds'];whole=np.all(w==np.eye(3),axis=(1,2));_,_,src,sm=s['raw'];stats={}
 require(len(rec['sourceContours'])==35 and rec['gradualInteriorBlendMeters']==.016 and np.array_equal(rec['radii'],[.041,.048,.04]),'Exact dense equator domain required')
 for zlevel,contour in zip(rec['sourceZ'],rec['sourceContours']):
  exact(np.asarray(contour),section_points(src['positions']+delta,np.zeros(3),np.array([0,0,1]),zlevel),'Literal original section contour')

 for label,source,result in [('encoded',src,{k:v for k,v in a.items()if k.startswith('encoded_')}),('native',s['native'],z)]:
  pre=a['preProfile'+label.title()+'Positions'];before=(literal_historical_encoded_cut_positions(source['positions']+delta,ids,w,pr['cut'],precision='f8') if label=='encoded' else np.einsum('fci,fij->fcj',w,source['positions'][ids]+delta))-delta;before[whole]=source['positions'][ids[whole]]
  if label=='native':before+=a['newSplitNativePositionWeldDeltas'];require((a['newSplitNativePositionWeldDeltas'][whole]==0).all(),'Protected source weld forbidden')
  close(pre,before,2e-14,'Equator direct source prefield '+label)
  inp={}
  for k in ('normals','tangents','uvGltf'):
   inp[k]=np.einsum('fci,fij->fcj',w,source[k][ids]);inp[k][whole]=source[k][ids[whole]]
  P,N,T,changed,det=profile_attributes(pre+delta,inp['normals'],inp['tangents'],rec);P-=delta
  mask=a['protected'+label.title()+'CornerMask'];corners=w.argmax(2);P[mask]=source['positions'][ids[:,None],corners][mask]
  for k,v in [('positions',P),('normals',N),('tangents',T),('uvGltf',inp['uvGltf'])]:
   actual=result[('encoded_'+k)if label=='encoded'else k][:count];close(actual,v,2e-14,'Equator literal field '+label+':'+k);exact(actual[mask],source[k][ids[:,None],corners][mask],'Equator protected '+label+':'+k)
  require(np.array_equal(changed,a[label+'ProfileChangedCornerMask']),'Declared changed domain differs');stats[label]=[float(det.min()),float(det.max())]
 # Fresh connected ellipsoid cap with held actual native source boundary.
 for domain,cp in zip(pr['capDomains'],pr['caps']):
  br=np.asarray(domain['sourceRetainedBoundaryRows']);rim=a['encoded_positions'][br[:,0],br[:,1]]+delta;nb=len(rim);attrs,p=ellipsoid_cap({'positions':rim},rec['center'],rec['radii'],1,12);f=p['faces'];nodeN=np.zeros_like(p['nodes']);nodeN[f.reshape(-1)]=attrs['normals'].reshape(-1,3);geom=nodeN.copy();nodeN[:nb]=a['encoded_normals'][br[:,0],br[:,1]];nodeN[nb:2*nb]=unit(.5*nodeN[:nb]+.5*geom[nb:2*nb]);EN=nodeN[f];ET=attrs['tangents'].copy();ET[...,:3]=unit(ET[...,:3]-unit(EN)*np.sum(ET[...,:3]*unit(EN),axis=-1)[...,None]);NP=p['nodes'].copy();NP[:nb]=z['positions'][br[:,0],br[:,1]]+delta;NN=nodeN.copy();NN[:nb]=z['normals'][br[:,0],br[:,1]];NT=ET.copy();NT[...,:3]=unit(NT[...,:3]-unit(NN[f])*np.sum(NT[...,:3]*unit(NN[f]),axis=-1)[...,None]);UV=attrs['uvGltf']*np.asarray(pr['capUVPositiveUniformJacobian'])+np.asarray(pr['capUVTranslation'])
  for k,e,v in [('positions',p['nodes'][f]-delta,NP[f]-delta),('normals',EN,NN[f]),('tangents',ET,NT),('uvGltf',UV,UV)]:close(a['encoded_'+k][new],e,2e-14,'Equator new cap encoded '+k);close(z[k][new],v,2e-14,'Equator new cap native '+k)
 order=np.r_[*[np.flatnonzero(sm[ids]==mid)for mid in np.unique(sm)],new];serialization(n,order);preserved_maps(n,s);skin_support(a['encoded_uvGltf'][new],support,n['g']['part']);cap_edges(z['positions'],new);cap_edges(n['raw'][2]['positions'],np.flatnonzero(order>=count))
 return {'kind':'dense35-source-equator-field-and-connected-ellipsoid','positiveJacobianRanges':stats,'newFaces':len(new)}

def validate_rgb(n,s):
 d,b,r,m=n['raw'];sd,sb,sr,sm=s['raw'];require(b[:len(sb)]==sb,'RGB binding changed source BIN');
 for k in ATTRS:exact(r[k],sr[k],'RGB binding geometry '+k);exact(n['native'][k],s['native'][k],'RGB binding native '+k)
 for k in n['lineage']:exact(n['lineage'][k],s['lineage'][k],'RGB binding lineage '+k)
 binding=n['proof']['newSkinRGBBindingDiagnostic'];rgb=binding['originalDerivedRGB'];require(sha(rgb['path'])==rgb['sha256'],'Stale finite RGB donor parent');tex=binding['sharedBaseColorTextureID'];view=d['bufferViews'][d['images'][d['textures'][tex]['source']]['bufferView']];require(b[view.get('byteOffset',0):view.get('byteOffset',0)+view['byteLength']]==Path(rgb['path']).read_bytes(),'RGB binding atlas differs')
 for key in ('accessors','nodes','scenes','scene','asset','samplers'):require(d.get(key)==sd.get(key),'RGB binding protected document '+key)
 for key in ('materials','textures','images','bufferViews'):require(d[key][:len(sd[key])]==sd[key],'RGB binding original inventory '+key)
 dd=copy.deepcopy(d['meshes'])
 for old,new in zip(sd['meshes'][0]['primitives'],dd[0]['primitives']):
  clone=copy.deepcopy(d['materials'][new['material']]);original=copy.deepcopy(sd['materials'][old['material']]);clone.pop('name',None);original.pop('name',None);clone['pbrMetallicRoughness']['baseColorTexture']=original['pbrMetallicRoughness']['baseColorTexture'];require(clone==original,'RGB binding changes N/ORM/material');new['material']=old['material']
 require(dd==sd['meshes'],'RGB binding source topology');return {'kind':'finite-original-donor-RGB-material-only-binding','geometryChanged':False}
