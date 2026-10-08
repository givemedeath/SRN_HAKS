"""One target-bound diagnostic thigh width-only affine descendant plus true mirror."""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
import target_contract as c
from place_purposebuilt_pelvis import BASIS,read_glb,write_glb,accessor,raw_corners,node_matrix,embedded_maps
from mirror_stock_limb_part import reflection_between_frames

def width_matrix(shaft,width_hint,factor):
 shaft=np.asarray(shaft,float);hint=np.asarray(width_hint,float)
 c.require(shaft.shape==hint.shape==(3,)and np.isfinite(shaft).all()and np.isfinite(hint).all()and np.linalg.norm(shaft)>1e-8,'Finite measured shaft/widthhint required')
 c.require(type(factor)in(int,float)and 0<factor<=1,'Positive width reduction required')
 u=shaft/np.linalg.norm(shaft);a=hint-hint.dot(u)*u;c.require(np.linalg.norm(a)>1e-8,'Widthhint parallel to shaft rejected');a/=np.linalg.norm(a);b=np.cross(u,a);M=np.eye(3)+(factor-1)*np.outer(a,a)
 return M,a,b,u

def transport(N,T,M):
 N=np.asarray(N,float);length=np.linalg.norm(N,axis=-1);c.require(np.isfinite(N).all()and np.all(length>1e-8),'Finite nonzero authored normals required')
 q=N@np.linalg.inv(M);q*= (length/np.linalg.norm(q,axis=-1))[...,None]
 t=None
 if T is not None:
  T=np.asarray(T,float);t=T.copy();orig=np.linalg.norm(T[...,:3],axis=-1);unit=q/length[...,None];v=T[...,:3]@M.T;v-=np.sum(v*unit,axis=-1)[...,None]*unit;c.require(np.isfinite(v).all()and np.all(np.linalg.norm(v,axis=-1)>1e-8),'Transported tangent degeneracy rejected');v*= (orig/np.linalg.norm(v,axis=-1))[...,None];t[...,:3]=v
 return q,t

def encode(doc,binary,M,translation,reflection=False):
 c.require(len(doc['nodes'])==1 and doc['nodes'][0].get('mesh')==0 and np.array_equal(node_matrix(doc['nodes'][0]),np.eye(4)),'Canonical detached identitysource required')
 c.require(len(doc['meshes'])==1 and len(doc['meshes'][0]['primitives'])==1,'One detached primitive required')
 primitive=doc['meshes'][0]['primitives'][0];attr=primitive['attributes'];c.require(set(attr)<= {'POSITION','NORMAL','TEXCOORD_0','TANGENT','COLOR_0'}and {'POSITION','NORMAL','TEXCOORD_0','TANGENT'}<=set(attr),'Explicit authored PNUT required')
 P=accessor(doc,binary,attr['POSITION']).astype(float)@BASIS.T;N=accessor(doc,binary,attr['NORMAL']).astype(float)@BASIS.T;T=accessor(doc,binary,attr['TANGENT']).astype(float);T[:,:3]=T[:,:3]@BASIS.T;ids=accessor(doc,binary,primitive['indices']).reshape(-1,3).astype(int)
 newP=P@M.T+translation
 if reflection:
  newN=N@M.T;newT=T.copy();newT[:,:3]=T[:,:3]@M.T;newT[:,3]*=-1
 else:newN,newT=transport(N,T,M)
 result=copy.deepcopy(doc);payload=bytearray(binary)
 def append(rows,index=False):
  rows=np.asarray(rows,dtype='<u4'if index else'<f4');c.require(np.isfinite(rows).all(),'Serialization overflow');payload.extend(b'\0'*(-len(payload)%4));start=len(payload);payload.extend(rows.tobytes());payload.extend(b'\0'*(-len(payload)%4));result['bufferViews'].append({'buffer':0,'byteOffset':start,'byteLength':rows.nbytes});width=1 if rows.ndim==1 else rows.shape[1];info={'bufferView':len(result['bufferViews'])-1,'componentType':5125 if index else 5126,'count':len(rows),'type':{1:'SCALAR',3:'VEC3',4:'VEC4'}[width]}
  if not index and width==3:info.update(min=rows.min(0).astype(float).tolist(),max=rows.max(0).astype(float).tolist())
  result['accessors'].append(info);return len(result['accessors'])-1
 outprim=result['meshes'][0]['primitives'][0];outprim['attributes']['POSITION']=append(newP@BASIS);outprim['attributes']['NORMAL']=append(newN@BASIS);rt=newT.copy();rt[:,:3]=newT[:,:3]@BASIS;outprim['attributes']['TANGENT']=append(rt)
 if reflection:outprim['indices']=append(ids[:,[0,2,1]].reshape(-1),True)
 result['buffers'][0]['byteLength']=len(payload)
 c.require(bytes(payload[:len(binary)])==binary and embedded_maps(doc,binary)==embedded_maps(result,bytes(payload)),'OriginalBIN/maps changed')
 for field in ['materials','images','textures','samplers']:c.require(result.get(field)==doc.get(field),'Materialclosure changed '+field)
 c.require(outprim['attributes']['TEXCOORD_0']==attr['TEXCOORD_0'],'OriginalUVaccessor changed')
 return result,bytes(payload),ids

def native_transform(parent,M,t,reflection=False):
 result={k:np.asarray(v).copy()for k,v in parent.items()};order=[0,2,1]if reflection else[0,1,2]
 P=parent['positions']@M.T+t
 if reflection:
  N=parent['normals']@M.T;T=parent['tangents'].copy();T[:,:,:3]=T[:,:,:3]@M.T;T[:,:,3]*=-1
 else:N,T=transport(parent['normals'],parent['tangents'],M)
 for key,value in [('positions',P),('normals',N),('tangents',T),('uvNative',parent['uvNative']),('uvGltf',parent['uvGltf'])]:result[key]=value[:,order]
 result['parentPositions']=parent['positions'][:,order].copy();result['parentNormals']=parent['normals'][:,order].copy();result['parentTangents']=parent['tangents'][:,order].copy();result['parentFaceIds']=np.arange(len(P),dtype=np.int64);result['parentCornerOrder']=np.tile(order,(len(P),1));return result

def execute(config_path,output):
 cfg=json.loads(Path(config_path).read_text());c.require(cfg['kind']=='target-thigh-width-diagnostic'and cfg['schemaVersion']==2 and cfg['widthFactor']==.78,'One frozen approved.78 thigh trial required')
 targetpath=Path(cfg['targetContract']).resolve();target=c.load(targetpath);parentpath=Path(cfg['parentReceipt']).resolve();parent=json.loads(parentpath.read_text());c.verify_binding(parent,targetpath,target,'working');c.require(parent['part']=='legl'and parent['operation']=='fit'and parent['statureApplications']==0,'Original working leftthigh fit required')
 source=Path(parent['candidate']);archivepath=Path(parent['nativeCornerArchive']['path']);pins={**parent['frozenInputs'],**cfg['protectedInputs'],str(targetpath):cfg['targetContractSha256'],str(parentpath):cfg['parentReceiptSha256'],str(source):parent['candidateSha256'],str(archivepath):parent['nativeCornerArchive']['sha256'],str(Path(config_path).resolve()):c.sha(config_path)}
 for n in ['scale_target_limb_width.py','target_contract.py','place_purposebuilt_pelvis.py','mirror_stock_limb_part.py']:p=Path(__file__).with_name(n).resolve();pins[str(p)]=c.sha(p)
 for p,h in pins.items():c.require(c.sha(p)==h,'Frozen input changed '+p)
 hip=c.frame(target,'lthigh_g','working');knee=c.frame(target,'lshin_g','working');shaft=(np.linalg.inv(hip)@knee)[:3,3];hint=hip[:3,:3].T@np.array([1.,0,0]);M,a,b,u=width_matrix(shaft,hint,.78);c.require(np.allclose(M,cfg['matrixLocal'],atol=1e-14,rtol=0)and np.allclose(a,cfg['widthAxisLocal'],atol=1e-14,rtol=0),'Measured frozen widthbasis changed')
 doc,binary=read_glb(source);base=dict(np.load(archivepath,allow_pickle=False));newdoc,newbin,ids=encode(doc,binary,M,np.zeros(3));newnative=native_transform(base,M,np.zeros(3));extra={};p,n,uv,_=raw_corners(newdoc,newbin,extra=extra);T=np.concatenate(extra['TANGENT']['rows']);c.require(np.array_equal(uv,newnative['uvGltf']),'UV changed')
 errors={k:float(np.max(abs(x-newnative[y])))for k,x,y in [('P',p,'positions'),('N',n,'normals'),('T',T,'tangents')]};c.require(max(errors.values())<1e-7,'Encoded/native lineage mismatch')
 c.require(np.max(abs((newnative['positions']-base['positions'])@u))<1e-14 and np.max(abs((newnative['positions']-base['positions'])@b))<1e-14,'Shaft/AP dimensions changed')
 C0=np.cross(base['positions'][:,1]-base['positions'][:,0],base['positions'][:,2]-base['positions'][:,0]);C1=np.cross(newnative['positions'][:,1]-newnative['positions'][:,0],newnative['positions'][:,2]-newnative['positions'][:,0]);mapped=C0@np.linalg.inv(M)*np.linalg.det(M);c.require(np.max(abs(C1-mapped))<1e-15,'Finiteface differential orientation mismatch')
 proof={'widthFactor':.78,'matrixLocal':M.tolist(),'widthAxisLocal':a.tolist(),'APAxisLocal':b.tolist(),'shaftAxisLocal':u.tolist(),'determinant':float(np.linalg.det(M)),'conditionNumber':float(np.linalg.cond(M)),'shaftAndAPCornerCoordinatePreservationError':float(max(np.max(abs((newnative['positions']-base['positions'])@u)),np.max(abs((newnative['positions']-base['positions'])@b)))),'widthRatio':float(np.ptp(newnative['positions']@a)/np.ptp(base['positions']@a)),'maximumInwardDisplacementMetres':float(np.max(np.linalg.norm(newnative['positions']-base['positions'],axis=2))),'encodedVersusNativeMaximumErrors':errors,'originalBinPrefixExact':True,'UVIndexMapsAndTriangleCountExact':True,'normalPolicy':'Inverse-transpose direction, authored magnitude retained; no source-normal repair','tangentPolicy':'Forward transform and projection onto transformed authored normal plane; magnitude retained; W unchanged','intersectionPolicy':'One global positive invertible affine map preserves exact intersections/topology in double lineage; float32 near-contact microgeometry and native/client gates remain open.','triangles':len(p),'selected':False}
 output=Path(output).resolve();c.require(not output.exists(),'Fresh output required');output.mkdir(parents=True);shutil.copyfile(__file__,output/'executed-width-helper.py')
 def save(part,d,document,payload,native,receiptparent,parenthash,operation,extra_proof,frozen,reflection=None):
  d.mkdir();candidate=d/'candidate-local.glb';write_glb(candidate,document,payload);npz=d/'native-corners.npz';np.savez_compressed(npz,**native);receipt={**c.binding(targetpath,target,'working'),'schemaVersion':2,'kind':'target-part-geometry','operation':operation,'part':part,'joint':c.PART_JOINTS[part],'model':c.model(target,part),'source':receiptparent['candidate'],'sourceSha256':receiptparent['candidateSha256'],'sourceReceipt':str(parenthash[0]),'sourceReceiptSha256':parenthash[1],'candidate':str(candidate),'candidateSha256':c.sha(candidate),'nativeCornerArchive':{'path':str(npz),'sha256':c.sha(npz)},'statureApplications':0,'attachmentWorld':c.frame(target,c.PART_JOINTS[part],'working').tolist(),'reflectionWorld':reflection,'proof':extra_proof,'frozenInputs':frozen,'diagnosticOnly':True,'clientAccepted':False,'productionAccepted':False,'limitation':'Width review only; source cap normals, garment/joint ownership, full motion/equipment/native/client remain unaccepted.'};path=d/'geometry.json';path.write_text(json.dumps(receipt,indent=2)+'\n');return path,receipt
 lp,lr=save('legl',output/'left',newdoc,newbin,newnative,parent,(parentpath,c.sha(parentpath)),'bone-axis-width-affine',proof,pins)
 left_receipt_hash=c.sha(lp)
 # Explicit measured stock midplane and actualoppositeframes; independently require hip midplane matching.
 plane=float(cfg['mirrorPlaneWorldX']);c.require(abs(plane-(hip[0,3]+c.frame(target,'rthigh_g','working')[0,3])/2)<1e-12,'Thigh reflection midplane differs')
 matrix,worldref=reflection_between_frames(hip,c.frame(target,'rthigh_g','working'),[plane,0,0],[1,0,0]);rightdoc,rightbin,_=encode(newdoc,newbin,matrix[:3,:3],matrix[:3,3],True);rightnative=native_transform(newnative,matrix[:3,:3],matrix[:3,3],True);rp,rn,ru,_=raw_corners(rightdoc,rightbin);c.require(np.array_equal(ru,newnative['uvGltf'][:,[0,2,1]])and np.max(abs(rp-rightnative['positions']))<1e-7,'Mirror encoded/native/UV mismatch');rproof={'reflectionWorld':worldref.tolist(),'sourceToRightLocal':matrix.tolist(),'triangleCornerOrder':[0,2,1],'tangentWFlipsExactly':True,'originalLeftBinPrefixExact':True,'mapsAndRawUVAccessorExact':True,'triangles':len(rp),'reflected':True,'widthParentUnchanged':c.sha(lp)==left_receipt_hash,'selected':False};rfrozen={**pins,str(lp):c.sha(lp),lr['candidate']:lr['candidateSha256'],lr['nativeCornerArchive']['path']:lr['nativeCornerArchive']['sha256']};rp,rr=save('legr',output/'right',rightdoc,rightbin,rightnative,lr,(lp,c.sha(lp)),'mirror',rproof,rfrozen,worldref.tolist())
 for pth,h in pins.items():c.require(c.sha(pth)==h,'Protected neighbor/source changed '+pth)
 return lp,rp,proof

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();l,r,proof=execute(a.config,a.output);print(json.dumps({'leftReceipt':str(l),'leftReceiptSHA256':c.sha(l),'rightReceipt':str(r),'rightReceiptSHA256':c.sha(r),'proof':proof},indent=2))
if __name__=='__main__':main()


