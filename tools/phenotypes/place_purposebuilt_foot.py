"""Inspect and uniformly fit an immutable generated LEFT foot to stock frames.

Only a proper similarity is permitted. The canonical detached bake retains
source BIN/map/UV evidence, authored normal/tangent magnitudes and float64
ordered-corner proof; rendered FLOAT32 precision is measured separately.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from place_purposebuilt_pelvis import bounds, embedded_maps, raw_corners, read_glb, require, rotation_xyz, sha, write_glb
from place_purposebuilt_thigh import compact_section
from retarget import nodes, transforms

PROTECTED = {
    'torso':'3ae78d023ba522d94c44d9914bac0b36f35b640c42b9532015575e5572161a50',
    'pelvis':'db0bdf16099068da3bb685bcb61ae93ebed115e6ddbae90990c0b55e59b8d98a',
    'left-thigh':'5420a77d5e9d51b7841f678d12710ce335bab16ed5ad417ae49b67f1e2950ab6',
    'right-thigh':'3c002789b74bfb5e94392d7c557e3105924e078f0133c47d496b1c123764b980',
    'left-shin':'bde4b16194010cd42ad40d282512e1189c7c992a5ab6df06d0d24c27c5123ee7',
    'right-shin':'7efe4b5a9e85bacd1b8d23958c96fe4518e186363f5c6c8b91aed5b17b3f4e24'}
STOCK_HEIGHT = .1632612


def landmark_similarity(source_landmarks, measured, weights=(4.,1.,1.)):
    """Rigid ankle anchor plus one least-squares proper/uniform fit.

    All source landmarks must be explicitly measured after anatomy review.
    Sole-under-ankle has greater weight than heel/toe extremes; returned
    residuals expose any incompatible source aspect instead of stretching it.
    """
    source = np.asarray([source_landmarks[k] for k in ['ankle','soleUnderAnkle','heel','toe']],float)
    require(source.shape==(4,3) and np.isfinite(source).all(),'Four finite anatomical source landmarks required')
    design = measured['leftDesign']
    target = np.asarray([[0,0,0],[0,0,design['soleApproximateLocalZ']],
                         design['heelExtremePoint'],design['toeExtremePoint']],float)
    a,b = source[1:]-source[0],target[1:]-target[0]
    w = np.asarray(weights,float)
    require(w.shape==(3,) and np.isfinite(w).all() and np.all(w>0),'Positive finite landmark weights required')
    require(np.linalg.matrix_rank(a)>=2,'Landmarks cannot be collinear')
    u,_,vt = np.linalg.svd(a.T@(b*w[:,None]))
    parity = np.eye(3); parity[2,2] = np.linalg.det(vt.T@u.T)
    r = vt.T@parity@u.T
    scale = float(np.sum(w[:,None]*(a@r.T)*b)/np.sum(w[:,None]*a*a))
    require(scale>0 and np.isfinite(scale),'Positive uniform landmark solution required')
    fitted = scale*(source-source[0])@r.T
    return {'uniformScale':scale,'properRotationMatrixNwn':r.tolist(),
            'sourceAnchorNwn':source[0].tolist(),'targetAnchorFootLocal':[0,0,0],
            'footLandmarkEvidence':{'sourceLandmarksNwn':source_landmarks,
                'targetLandmarksFootLocal':dict(zip(['ankle','soleUnderAnkle','heel','toe'],target.tolist())),
                'weightsSoleHeelToe':w.tolist(),'residualVectorsMetres':(fitted-target).tolist(),
                'residualDistancesMetres':np.linalg.norm(fitted-target,axis=1).tolist(),
                'scope':'Ankle is fixed exactly; other measured landmarks compromise only by one proper rotation/positive uniform scale. No mesh edit or authored source skeleton claimed.'}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['inspect','place'])
    for key in ['source','generation','stock-root','connectors','output','frozen-pelvis-plt',*[('frozen-'+p) for p in PROTECTED]]:
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--config',type=Path)
    args=parser.parse_args();out=args.output.resolve()
    require(not out.exists(),'Fresh output required')
    source=args.source.resolve();generation=args.generation.resolve();root=args.stock_root.resolve();connectors=args.connectors.resolve()
    job=json.loads(generation.read_text(encoding='utf-8'))
    require(job.get('state')=='success' and job.get('promptId'),'Collected successful generator receipt required')
    require(len([x for x in job.get('outputs',[]) if Path(x.get('localPath','')).resolve()==source and x.get('sha256')==sha(source)])==1,'Selected actual generator source/hash mismatch')
    plt=args.frozen_pelvis_plt.resolve()
    require(sha(plt)=='990aa66b5c642d6c45ab4f1c60ceffd732cd290b53207c9c5021698dc9181690','Accepted corrected pelvis PLT changed')
    protected={p:getattr(args,'frozen_'+p.replace('-','_')).resolve() for p in PROTECTED}
    for part,path in protected.items():require(sha(path)==PROTECTED[part],'Protected neighbour changed '+part)
    measured=json.loads(connectors.read_text(encoding='utf-8'))
    require(measured['parts']['footl']['model']=='pmh0_footl001' and measured['parts']['footr']['model']=='pmh0_footr001','Actual stock left/right foot measurements required')
    require(abs(measured['parts']['footl']['localBounds']['extent'][2]-STOCK_HEIGHT)<1e-12,'Stock foot height mismatch')
    for path,h in measured['frozenInputs'].items():require(sha(Path(path))==h,'Connector frozen source mismatch '+path)
    world=transforms(nodes(root.read_text(encoding='cp1252')))
    for joint in ['lshin_g','lfoot_g','rshin_g','rfoot_g']:
        require(np.array_equal(world[joint],np.asarray(measured['stockJointWorldMatrices'][joint])),'Measured root joint mismatch '+joint)
    doc,binary=read_glb(source);extra={};p,n,uv,primitives=raw_corners(doc,binary,allow_wrapper=True,extra=extra)
    maps=embedded_maps(doc,binary);unique=np.unique(p.reshape(-1,3),axis=0);lo,hi=unique.min(0),unique.max(0)
    code=Path(__file__).resolve();files=[source,generation,root,connectors,plt,*protected.values(),code,
        code.with_name('place_purposebuilt_pelvis.py'),code.with_name('place_purposebuilt_thigh.py'),code.with_name('retarget.py')]
    frozen={str(x):sha(x) for x in files}
    result={'schemaVersion':1,'diagnosticOnly':True,'phase':args.phase,'part':'footl','model':'pmh0_footl001','joint':'lfoot_g',
        'source':str(source),'sourceSha256':sha(source),'generation':str(generation),'generationSha256':sha(generation),'jobPromptId':job['promptId'],
        'frozenInputHashes':frozen,'coordinateBasis':'Raw glTF to NWN [X,-Z,Y]; front +Y/up +Z; exact lfoot_g local.',
        'stockJointWorldMatrix':world['lfoot_g'].tolist(),'stockShinRelativeToFoot':(np.linalg.inv(world['lfoot_g'])@world['lshin_g']).tolist(),
        'sourceBoundsNwn':bounds(p),'sourcePrimitives':primitives,'sourceTriangles':len(p),'embeddedMaps':maps,
        'sourceRelativeSections':[compact_section(unique,lo[2]+fraction*(hi[2]-lo[2])) for fraction in [.1,.25,.5,.75,.9]],
        'heightFirstUniformScaleProposal':float(STOCK_HEIGHT/(hi[2]-lo[2])),
        'orientationPolicy':'Inspect actual toes/heel/sole/big-toe medial anatomy; no rotation assumed from another part.',
        'stockRigOrAnimationsModified':False,'protectedNeighboursModified':False,'nativeOrClientAccepted':False}
    out.mkdir(parents=True)
    if args.phase=='inspect':
        archive=out/'source-corners.npz';attrs={}
        for semantic,record in extra.items():
            attrs['source'+semantic]=np.concatenate(record['rows']);attrs[semantic+'TriangleIndices']=np.asarray(record['triangleIndices'],np.int64)
        np.savez_compressed(archive,positions=p,normals=n,uvGltf=uv,**attrs)
        result['sourceCornerArchive']={'path':str(archive),'sha256':sha(archive)}
        template={'schemaVersion':1,'diagnosticOnly':True,'sourceSha256':sha(source),'generationSha256':sha(generation),'jobPromptId':job['promptId'],
            'stockRootSha256':sha(root),'connectorReceiptSha256':sha(connectors),'protectedNeighbourSha256':PROTECTED,
            'uniformScale':result['heightFirstUniformScaleProposal'],'rotationDegreesXYZ':[0,0,0],
            'sourceAnchorNwn':None,
            'targetAnchorFootLocal':[0,0,0],
            'landmarkNotes':'Supply measured anatomical ankle anchor, sole datum and heel/toe points. Bounding-box centre is not an ankle landmark.',
            'orientationEvidence':'UNCONFIRMED: inspect actual anatomy before placing.','label':'Uncalibrated left foot'}
        (out/'placement-config-template.json').write_text(json.dumps(template,indent=2)+'\n',encoding='utf-8')
    else:
        require(args.config is not None,'Explicit similarity config required');config=json.loads(args.config.read_text(encoding='utf-8'))
        frozen[str(args.config.resolve())]=sha(args.config)
        allowed={'schemaVersion','diagnosticOnly','sourceSha256','generationSha256','jobPromptId','stockRootSha256','connectorReceiptSha256','protectedNeighbourSha256','uniformScale','rotationDegreesXYZ','properRotationMatrixNwn','sourceAnchorNwn','targetAnchorFootLocal','orientationEvidence','label','landmarkNotes','footLandmarkEvidence'}
        require(not set(config)-allowed and config.get('schemaVersion')==1 and config.get('diagnosticOnly') is True,'Explicit known diagnostic controls only')
        for key,value in [('sourceSha256',sha(source)),('generationSha256',sha(generation)),('jobPromptId',job['promptId']),('stockRootSha256',sha(root)),('connectorReceiptSha256',sha(connectors)),('protectedNeighbourSha256',PROTECTED)]:require(config.get(key)==value,'Fit association mismatch '+key)
        evidence=config.get('orientationEvidence','');require(isinstance(evidence,str) and len(evidence)>20 and 'UNCONFIRMED' not in evidence,'Actual anatomical evidence required')
        scale=float(config['uniformScale']);anchor=np.asarray(config['sourceAnchorNwn'],float);target=np.asarray(config['targetAnchorFootLocal'],float)
        require(np.isfinite(scale) and 0<scale<10 and all(x.shape==(3,) and np.isfinite(x).all() for x in [anchor,target]),'Finite positive uniform similarity controls required')
        require(('rotationDegreesXYZ' in config)^('properRotationMatrixNwn' in config),'One explicit proper rotation representation required')
        if 'properRotationMatrixNwn' in config:r=np.asarray(config['properRotationMatrixNwn'],float)
        else:
            angles=np.asarray(config['rotationDegreesXYZ'],float);require(angles.shape==(3,) and np.isfinite(angles).all(),'Finite XYZ rotation required');r=rotation_xyz(angles)
        require(r.shape==(3,3) and np.isfinite(r).all() and np.max(abs(r.T@r-np.eye(3)))<1e-10 and abs(np.linalg.det(r)-1)<1e-10,'Proper orthogonal rotation required')
        affine=np.eye(4);affine[:3,:3]=r*scale;affine[:3,3]=target-scale*r@anchor
        from mirror_stock_limb_part import detached_affine_bake
        frozen[str(code.with_name('mirror_stock_limb_part.py'))]=sha(code.with_name('mirror_stock_limb_part.py'))
        newdoc,newbin,corners,proof=detached_affine_bake(doc,binary,affine,allow_reflection=False)
        candidate=out/'placed-local.glb';write_glb(candidate,newdoc,newbin)
        ad,ab=read_glb(candidate);ap,an,au,_=raw_corners(ad,ab)
        require(np.max(abs(corners['positions']-(p@affine[:3,:3].T+affine[:3,3])))<2e-12 and np.max(abs(corners['normals']-n@r.T))<2e-12,'Authoritative transform derivation failed')
        require(np.array_equal(au,uv) and embedded_maps(ad,ab)==maps and ab[:len(binary)]==binary,'Actual UV/map/source BIN evidence changed')
        require(np.max(abs(ap-corners['positions']))<1e-6 and np.max(abs(an-corners['normals']))<1e-6,'Rendered FLOAT32 precision budget failed')
        edges=lambda x:np.linalg.norm(x[:,[1,2,0]]-x[:,[0,1,2]],axis=2)
        error=float(np.max(abs(edges(corners['positions'])-edges(p)*scale)));require(error<2e-12,'Triangle similarity failed')
        archive=out/'native-corners.npz';np.savez_compressed(archive,**corners)
        result.update(configuration=config,affineNwnToFootLocal=affine.tolist(),properRotationMatrixNwn=r.tolist(),
            candidate=str(candidate),candidateSha256=sha(candidate),nativeCornerArchive={'path':str(archive),'sha256':sha(archive)},
            targetBoundsFootLocal=bounds(corners['positions']),proof=proof,maximumUniformTriangleEdgeErrorMetres=error,
            normalPolicy='Proper rotation only, authored magnitude retained; float64 archive versus measured rendered FLOAT32.',
            uvPolicy='Raw GLTF unchanged; native V flips once only.')
        replacement={'label':config.get('label','Left foot uniform first fit'),'modelPrefix':'pmh0','height':1.9339157,
            'parts':{'chest':str(protected['torso']),'pelvis':str(protected['pelvis']),'legl':str(protected['left-thigh']),'legr':str(protected['right-thigh']),'shinl':str(protected['left-shin']),'shinr':str(protected['right-shin']),'footl':str(candidate)},
            'diagnosticOnly':True,'placementReceipt':str(out/'placement.json')}
        (out/'stock-replacement.json').write_text(json.dumps(replacement,indent=2)+'\n',encoding='utf-8');shutil.copy2(args.config,out/'executed-config.json')
    shutil.copy2(source,out/'frozen-source.glb');shutil.copy2(generation,out/'frozen-generation.json');shutil.copy2(code,out/'executed-place_purposebuilt_foot.py')
    for path,h in frozen.items():require(sha(Path(path))==h,'Frozen input changed '+path)
    result['inputsUnchanged']=True;result['commandArguments']=__import__('sys').argv[1:]
    (out/('inspection.json' if args.phase=='inspect' else 'placement.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'phase':args.phase,'output':str(out),'sourceTriangles':len(p),'sourceBoundsNwn':result['sourceBoundsNwn'],'placedBounds':result.get('targetBoundsFootLocal')}))


if __name__=='__main__':main()
