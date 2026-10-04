"""CPU-only explicit detached hand similarity; authored geometry/maps preserved."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;R=P.parents[2]
sys.path.insert(0,str(R/'tools/phenotypes'))
from place_purposebuilt_pelvis import read_glb,write_glb,raw_corners,embedded_maps,bounds,require,rotation_xyz
from mirror_stock_limb_part import detached_affine_bake
from retarget import nodes,transforms
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def section(p,z):
    hits=[]
    for a,b in ((0,1),(1,2),(2,0)):
        f,s=p[:,a],p[:,b];dz=s[:,2]-f[:,2]
        ok=(abs(dz)>1e-12)&(np.minimum(f[:,2],s[:,2])<=z)&(np.maximum(f[:,2],s[:,2])>=z)
        v=(z-f[ok,2])/dz[ok];hits.extend(f[ok,:2]+(s[ok,:2]-f[ok,:2])*v[:,None])
    h=np.asarray(hits)
    return {'z':float(z),'points':len(h),'boundsXY':[h.min(0).tolist(),h.max(0).tolist()] if len(h) else None,'centerXY':((h.min(0)+h.max(0))/2).tolist() if len(h) else None}

def main():
    a=argparse.ArgumentParser();a.add_argument('phase',choices=['inspect','place'])
    for key in ['source','generation','output']:a.add_argument('--'+key,type=Path,required=True)
    a.add_argument('--config',type=Path);args=a.parse_args()
    out=args.output.resolve();require(not out.exists(),'Fresh output required')
    source=args.source.resolve();gen=args.generation.resolve();job=json.loads(gen.read_text())
    require(job.get('state')=='success' and job.get('promptId'),'Successful collected job receipt required')
    require(any(Path(o.get('localPath','')).resolve()==source and o.get('sha256')==sha(source) for o in job.get('outputs',[])),'Actual generated source hash absent from receipt')
    root=R/'output/phenotypes/purposebuilt-stock-inputs-v1/stock/ascii/pmh0.mdl';measurement=P/'stock-measurement-v1/measurement.json'
    require(sha(root)=='23fc893a8d18df461052ef978f33b7805da9188546833c0620b3a6014117d45a','Protected actual stock root changed')
    measured=json.loads(measurement.read_text());left=measured['sides'][0];world=transforms(nodes(root.read_text()))
    require(np.array_equal(world['lhand_g'],left['wristJointWorld']),'Actual stock attachment differs from measurement')
    for row in measured['sides']:
        for path,h in row['inputs'].items():require(sha(path)==h,'Stock part measurement input changed')
    doc,blob=read_glb(source);extra={};p,n,uv,prims=raw_corners(doc,blob,allow_wrapper=True,extra=extra)
    maps=embedded_maps(doc,blob);unique=np.unique(p.reshape(-1,3),axis=0);lo=unique.min(0);hi=unique.max(0)
    code=[Path(__file__),R/'tools/phenotypes/place_purposebuilt_pelvis.py',R/'tools/phenotypes/mirror_stock_limb_part.py',R/'tools/phenotypes/retarget.py']
    frozen={str(x):sha(x) for x in [source,gen,root,measurement,*code]}
    result={'schemaVersion':1,'diagnosticOnly':True,'part':'handl','model':'pmh0_handl001','joint':'lhand_g','source':str(source),'sourceSha256':sha(source),'generation':str(gen),'generationSha256':sha(gen),'jobPromptId':job['promptId'],'stockRoot':str(root),'stockRootSha256':sha(root),'stockMeasurement':str(measurement),'stockMeasurementSha256':sha(measurement),'sourceBoundsNwn':bounds(p),'embeddedMaps':maps,'sourcePrimitives':prims,'sourceTriangles':len(p),'sourceSections':[section(p,lo[2]+t*(hi[2]-lo[2])) for t in [.1,.25,.5,.75,.9,.95,.98]],'stockJointWorldMatrix':world['lhand_g'].tolist(),'stockRigOrAnimationsModified':False,'nativeOrClientAccepted':False,'frozenInputHashes':frozen}
    out.mkdir(parents=True)
    if args.phase=='inspect':
        archive=out/'source-corners.npz';rows={'positions':p,'normals':n,'uvGltf':uv}
        for key,value in extra.items():rows['source'+key]=np.concatenate(value['rows'])
        np.savez_compressed(archive,**rows);result['sourceCornerArchive']={'path':str(archive),'sha256':sha(archive)}
    else:
        require(args.config is not None,'Explicit reviewed similarity configuration required');cfg=json.loads(args.config.read_text());frozen[str(args.config.resolve())]=sha(args.config)
        for key in ['sourceSha256','generationSha256','jobPromptId','stockRootSha256','stockMeasurementSha256']:require(cfg.get(key)==result[key],'Fit ancestry mismatch '+key)
        allowed={'schemaVersion','sourceSha256','generationSha256','jobPromptId','stockRootSha256','stockMeasurementSha256','uniformScale','properRotationMatrixNwn','sourceAnchorNwn','targetAnchorHandLocal','orientationEvidence','label','reflectSourceAnatomyX','reflectionEvidence'}
        require(not set(cfg)-allowed and cfg.get('schemaVersion')==1,'Unknown fit controls rejected')
        scale=float(cfg['uniformScale']);rot=np.asarray(cfg['properRotationMatrixNwn'],float)
        require(scale>0 and np.isfinite(scale) and scale<10 and rot.shape==(3,3) and np.isfinite(rot).all() and np.max(abs(rot.T@rot-np.eye(3)))<1e-10 and abs(np.linalg.det(rot)-1)<1e-10,'Positive uniform scale and proper rotation required')
        anchor=np.asarray(cfg['sourceAnchorNwn'],float);target=np.asarray(cfg['targetAnchorHandLocal'],float)
        require(anchor.shape==target.shape==(3,) and np.isfinite(anchor).all() and np.isfinite(target).all(),'Finite anatomical anchors required')
        require(len(cfg.get('orientationEvidence',''))>50 and 'UNCONFIRMED' not in cfg['orientationEvidence'],'Actual anatomy/weapon axis evidence required')
        reflect=cfg.get('reflectSourceAnatomyX',False);require(isinstance(reflect,bool),'Explicit reflection boolean required')
        if reflect:require(len(cfg.get('reflectionEvidence',''))>80,'Wrong-handed source requires measured explicit chirality proof')
        linear=rot@np.diag([-1,1,1] if reflect else [1,1,1]);affine=np.eye(4);affine[:3,:3]=linear*scale;affine[:3,3]=target-scale*linear@anchor
        nd,nb,corners,proof=detached_affine_bake(doc,blob,affine,allow_reflection=reflect)
        candidate=out/'placed-local.glb';write_glb(candidate,nd,nb);ad,ab=read_glb(candidate);ap,an,au,_=raw_corners(ad,ab)
        order=[0,2,1] if reflect else [0,1,2]
        require(np.array_equal(au,uv[:,order]) and embedded_maps(ad,ab)==maps and ab[:len(blob)]==blob,'Actual map/UV/originalBIN changed')
        require(np.max(abs(ap-corners['positions']))<1e-6 and np.max(abs(an-corners['normals']))<1e-6,'Serialized FLOAT32 transport budget exceeded')
        edges=lambda q:np.linalg.norm(q[:,[1,2,0]]-q[:,[0,1,2]],axis=2)
        edge_error=float(np.max(abs(edges(corners['positions'])-edges(p[:,order])*scale)));require(edge_error<2e-12,'Triangle similarity failed')
        archive=out/'native-corners.npz';np.savez_compressed(archive,**corners)
        result.update(configuration=cfg,candidate=str(candidate),candidateSha256=sha(candidate),nativeCornerArchive={'path':str(archive),'sha256':sha(archive)},affineNwnToHandLocal=affine.tolist(),targetBoundsHandLocal=bounds(ap),proof=proof,maximumUniformTriangleEdgeErrorMetres=edge_error,geometryEditsBeyondSimilarity=False,sourceAnatomyReflectionExplicit=reflect,sourceMapsChanged=False)
        shutil.copy2(args.config,out/'executed-config.json')
    for path,h in frozen.items():require(sha(path)==h,'Frozen input changed '+path)
    for codepath in code:shutil.copy2(codepath,out/('executed-'+codepath.name))
    result['inputsUnchanged']=True;result['commandArguments']=sys.argv[1:]
    (out/('inspection.json' if args.phase=='inspect' else 'placement.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'part':'handl','triangles':len(p),'output':str(out),'bounds':result.get('targetBoundsHandLocal',result['sourceBoundsNwn'])}))
if __name__=='__main__':main()
