"""Bound a hidden foot-ankle taper after stock similarity fit and topology repair."""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
from place_purposebuilt_pelvis import BASIS,read_glb,raw_corners,embedded_maps,write_glb,require,sha
from round_generated_waist_cap import append_accessor

def field(points,start,end,crown_scale,centre):
    require(np.isfinite([start,end,crown_scale,*centre]).all() and 0<=start<end<=.1 and .4<=crown_scale<=1,'Bounded hidden ankle taper required')
    points=np.asarray(points,float);q=np.clip((points[:,2]-start)/(end-start),0,1)
    weight=q*q*(3-2*q);scale=1-(1-crown_scale)*weight
    derivative=-(1-crown_scale)*6*q*(1-q)/(end-start)
    delta=points[:,:2]-np.asarray(centre)
    result=points.copy();result[:,:2]=centre+delta*scale[:,None]
    jac=np.tile(np.eye(3),(len(points),1,1));jac[:,0,0]=jac[:,1,1]=scale
    jac[:,:2,2]=delta*derivative[:,None]
    identity=points[:,2]<=start;result[identity]=points[identity]
    return result,jac

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('parent-receipt','config','output'):parser.add_argument('--'+key,type=Path,required=True)
    a=parser.parse_args();require(not a.output.exists(),'Fresh taper descendant required')
    parent_path=a.parent_receipt.resolve();parent=json.loads(parent_path.read_text());config=json.loads(a.config.read_text())
    require(parent['part']=='footl' and parent['joint']=='lfoot_g','Explicit left-foot parent required')
    source=Path(parent['candidate']);archive=Path(parent['nativeCornerArchive']['path'])
    require(sha(source)==parent['candidateSha256'] and sha(archive)==parent['nativeCornerArchive']['sha256'] and sha(parent_path)==config['parentReceiptSha256'],'Parent association changed')
    for path,digest in config['evidenceHashes'].items():require(sha(path)==digest,'Measured fit evidence changed')
    data=dict(np.load(archive,allow_pickle=False));p=data['positions'];n=data['normals'];t=data['tangents']
    centre=config['centreXY'];start=config['startZ'];end=config['endZ'];amount=config['crownScale']
    flat,jac=field(p.reshape(-1,3),start,end,amount,centre);newp=flat.reshape(p.shape)
    identity=p[:,:,2]<=start
    ln=np.linalg.norm(n.reshape(-1,3),axis=1);nn=np.einsum('nij,nj->ni',np.linalg.inv(jac).transpose(0,2,1),n.reshape(-1,3))
    nn*= (ln/np.linalg.norm(nn,axis=1))[:,None];newn=nn.reshape(n.shape);newn[identity]=n[identity]
    tangent=t[:,:,:3].reshape(-1,3);lt=np.linalg.norm(tangent,axis=1)
    tt=np.einsum('nij,nj->ni',jac,tangent);unit=nn/ln[:,None];tt-=unit*np.sum(unit*tt,1)[:,None]
    require(np.linalg.norm(tt,axis=1).min()>1e-8,'Nondegenerate taper tangents required')
    tt*= (lt/np.linalg.norm(tt,axis=1))[:,None];newt=t.copy();newt[:,:,:3]=tt.reshape(p.shape);newt[identity]=t[identity]
    displacement=float(np.linalg.norm(newp-p,axis=2).max())
    require(0<config['maximumMovementMetres']<=.025 and displacement<=config['maximumMovementMetres'],'Measured taper movement budget exceeded')
    require(np.array_equal(newp[:,:,2],p[:,:,2]) and np.linalg.det(jac).min()>0,'Height/proper differential changed')
    doc,blob=read_glb(source);op,on,ou,_=raw_corners(doc,blob)
    require(np.max(abs(op-p))<6e-8 and np.max(abs(on-n))<1e-7,'Actual parent/archive transport differs')
    newdoc=copy.deepcopy(doc);binary=bytearray(blob);attrs=newdoc['meshes'][0]['primitives'][0]['attributes']
    require(len(newdoc['nodes'])==1 and newdoc['nodes'][0]=={'mesh':0} and len(newdoc['meshes'][0]['primitives'])==1,'Canonical detached one-material foot required')
    native_t=newt.copy();native_t[:,:,:3]=native_t[:,:,:3]@BASIS
    for key,value in [('POSITION',newp@BASIS),('NORMAL',newn@BASIS),('TANGENT',native_t)]:attrs[key]=append_accessor(newdoc,binary,value.reshape(-1,value.shape[-1]).astype('<f4'),key)
    binary.extend(b'\0'*(-len(binary)%4));newdoc['buffers'][0]['byteLength']=len(binary)
    out=a.output.resolve();out.mkdir(parents=True);candidate=out/'tapered-local.glb';write_glb(candidate,newdoc,bytes(binary))
    actualdoc,actualbin=read_glb(candidate);ap,an,au,_=raw_corners(actualdoc,actualbin)
    require(np.max(abs(ap-newp))<6e-8 and np.max(abs(an-newn))<1e-7 and np.array_equal(au,ou),'Taper transport/UV mismatch')
    require(embedded_maps(actualdoc,actualbin)==embedded_maps(doc,blob) and actualdoc['materials']==doc['materials'] and actualbin[:len(blob)]==blob,'Original maps/material/BIN changed')
    require(np.array_equal(ap[identity],op[identity]) and np.array_equal(an[identity],on[identity]),'Protected lower anatomy altered')
    data.update(positions=newp,normals=newn,tangents=newt)
    target_archive=out/'native-corners.npz';np.savez_compressed(target_archive,**data)
    record={'schemaVersion':1,'diagnosticOnly':True,'part':'footl','model':'pmh0_footl001','joint':'lfoot_g','phase':'measured-hidden-ankle-taper',
      'candidate':str(candidate),'candidateSha256':sha(candidate),'parentReceipt':str(parent_path),'parentReceiptSha256':sha(parent_path),'parentCandidate':str(source),'parentCandidateSha256':sha(source),
      'nativeCornerArchive':{'path':str(target_archive),'sha256':sha(target_archive)},'configuration':config,'configSha256':sha(a.config),'helperSha256':sha(__file__),
      'proof':{'protectedLowerPositionsNormalsTangentsExact':True,'uvMapsMaterialsTopologyExact':True,'heightExact':True,'maximumDisplacementMetres':displacement,'minimumJacobianDeterminant':float(np.linalg.det(jac).min()),'changedPositionCorners':int((~identity).sum()),
      'normalPolicy':'Local inverse-transpose Jacobian with authored length preserved; tangent forward Jacobian orthogonalized with authored length/sign preserved. Exact identity below declared start.'},
      'independentGeometryMotionReviewPending':True,'nativeOrClientAccepted':False}
    (out/'taper.json').write_text(json.dumps(record,indent=2)+'\n');shutil.copy2(__file__,out/'executed-helper.py');shutil.copy2(a.config,out/'executed-config.json')
    print(json.dumps(record['proof']))

if __name__=='__main__':main()
