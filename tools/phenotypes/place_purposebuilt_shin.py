"""Inspect and uniformly fit an immutable generated LEFT shin to stock frames.

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
from place_purposebuilt_thigh import compact_section, section_centroid
from retarget import nodes, transforms

PROTECTED = {
    'torso':'3ae78d023ba522d94c44d9914bac0b36f35b640c42b9532015575e5572161a50',
    'pelvis':'db0bdf16099068da3bb685bcb61ae93ebed115e6ddbae90990c0b55e59b8d98a',
    'left-thigh':'5420a77d5e9d51b7841f678d12710ce335bab16ed5ad417ae49b67f1e2950ab6',
    'right-thigh':'3c002789b74bfb5e94392d7c557e3105924e078f0133c47d496b1c123764b980'}
STOCK_HEIGHT = .5087992


def centerline_proposal(triangles, orientation_degrees, measured, stock_triangles):
    """Infer anchors from geometry with measured stock section-to-pivot offsets.

Unlike a bare section-centre fit, this retains stock's asymmetric attachment
offsets. Anchors remain geometric assumptions, not an authored source rig.
Actual anatomy, shell ownership and posed overlaps must approve the result.
"""
    orientation = rotation_xyz(orientation_degrees)
    oriented = triangles@orientation.T
    lo,hi=oriented.reshape(-1,3).min(0),oriented.reshape(-1,3).max(0)
    height_scale=STOCK_HEIGHT/(hi[2]-lo[2])
    target_ankle=np.asarray(measured['leftDesign']['kneeToAnklePivotVector'])
    knee_z=hi[2]-measured['leftDesign']['upperEndAboveKneeJointMetres']/height_scale
    ankle_z=lo[2]+measured['leftDesign']['lowerEndBelowAnkleJointMetres']/height_scale
    knee,krow=section_centroid(oriented,knee_z);ankle,arow=section_centroid(oriented,ankle_z)
    stock_knee,skrow=section_centroid(stock_triangles,0.)
    stock_ankle,sarow=section_centroid(stock_triangles,float(target_ankle[2]))
    inferred_knee=knee-stock_knee/height_scale
    inferred_ankle=ankle+(target_ankle-stock_ankle)/height_scale
    vector=inferred_ankle-inferred_knee
    a,b=vector/np.linalg.norm(vector),target_ankle/np.linalg.norm(target_ankle)
    cross=np.cross(a,b);cos=float(np.dot(a,b));sine=float(np.linalg.norm(cross))
    require(cos>-.999999,'Antiparallel axis needs explicit anatomical rotation')
    k=np.asarray([[0,-cross[2],cross[1]],[cross[2],0,-cross[0]],[-cross[1],cross[0],0]])
    correction=np.eye(3)+k+k@k/(1+cos)
    return {'uniformScale':float(np.linalg.norm(target_ankle)/np.linalg.norm(vector)),
        'properRotationMatrixNwn':(correction@orientation).tolist(),
        'sourceAnchorNwn':(inferred_knee@orientation).tolist(),'targetAnchorShinLocal':[0,0,0],
        'centerlineEvidence':{'initialOrientationDegreesXYZ':orientation_degrees,'initialHeightScale':float(height_scale),
            'sourceKneeSection':krow,'sourceAnkleSection':arow,'stockKneeSection':skrow,'stockAnkleSection':sarow,
            'stockSectionToKneePivotOffset':(-stock_knee).tolist(),
            'stockSectionToAnklePivotOffset':(target_ankle-stock_ankle).tolist(),
            'sourceInferredAnkleAnchorNwn':(inferred_ankle@orientation).tolist(),'targetAnklePivotShinLocal':target_ankle.tolist(),
            'minimalAxisCorrectionDegrees':float(np.rad2deg(np.arctan2(sine,cos))),
            'assumption':'Initial height calibration, measured upper/lower hidden-end allowances and stock section-to-pivot offsets infer source attachments. Review actual anatomy/outer shell and poses; no authored source skeleton claimed.'}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['inspect','place'])
    for key in ['source','generation','stock-root','connectors','output',*[('frozen-'+p) for p in PROTECTED]]:
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--config',type=Path)
    args=parser.parse_args();out=args.output.resolve()
    require(not out.exists(),'Fresh output required')
    source=args.source.resolve();generation=args.generation.resolve();root=args.stock_root.resolve();connectors=args.connectors.resolve()
    job=json.loads(generation.read_text(encoding='utf-8'))
    require(job.get('state')=='success' and job.get('promptId'),'Collected successful generator receipt required')
    require(len([x for x in job.get('outputs',[]) if Path(x.get('localPath','')).resolve()==source and x.get('sha256')==sha(source)])==1,'Selected actual generator source/hash mismatch')
    protected={p:getattr(args,'frozen_'+p.replace('-','_')).resolve() for p in PROTECTED}
    for part,path in protected.items():require(sha(path)==PROTECTED[part],'Protected neighbour changed '+part)
    measured=json.loads(connectors.read_text(encoding='utf-8'))
    require(measured['parts']['shinl']['model']=='pmh0_shinl001' and measured['parts']['footl']['model']=='pmh0_footl001','Actual stock shin/foot measurements required')
    require(abs(measured['parts']['shinl']['localBounds']['extent'][2]-STOCK_HEIGHT)<1e-12,'Stock shin height mismatch')
    for path,h in measured['frozenInputs'].items():require(sha(Path(path))==h,'Connector frozen source mismatch '+path)
    world=transforms(nodes(root.read_text(encoding='cp1252')))
    for joint in ['lshin_g','lfoot_g','rshin_g','rfoot_g']:
        require(np.array_equal(world[joint],np.asarray(measured['stockJointWorldMatrices'][joint])),'Measured root joint mismatch '+joint)
    doc,binary=read_glb(source);extra={};p,n,uv,primitives=raw_corners(doc,binary,allow_wrapper=True,extra=extra)
    maps=embedded_maps(doc,binary);unique=np.unique(p.reshape(-1,3),axis=0);lo,hi=unique.min(0),unique.max(0)
    code=Path(__file__).resolve();files=[source,generation,root,connectors,*protected.values(),code,
        code.with_name('place_purposebuilt_pelvis.py'),code.with_name('place_purposebuilt_thigh.py'),code.with_name('retarget.py')]
    frozen={str(x):sha(x) for x in files}
    result={'schemaVersion':1,'diagnosticOnly':True,'phase':args.phase,'part':'shinl','model':'pmh0_shinl001','joint':'lshin_g',
        'source':str(source),'sourceSha256':sha(source),'generation':str(generation),'generationSha256':sha(generation),'jobPromptId':job['promptId'],
        'frozenInputHashes':frozen,'coordinateBasis':'Raw glTF to NWN [X,-Z,Y]; front +Y/up +Z; exact lshin_g local.',
        'stockJointWorldMatrix':world['lshin_g'].tolist(),'stockFootRelativeToShin':(np.linalg.inv(world['lshin_g'])@world['lfoot_g']).tolist(),
        'sourceBoundsNwn':bounds(p),'sourcePrimitives':primitives,'sourceTriangles':len(p),'embeddedMaps':maps,
        'sourceRelativeSections':[compact_section(unique,lo[2]+fraction*(hi[2]-lo[2])) for fraction in [.1,.25,.5,.75,.9]],
        'heightFirstUniformScaleProposal':float(STOCK_HEIGHT/(hi[2]-lo[2])),
        'orientationPolicy':'Inspect actual anterior tibia/posterior calf/medial-lateral anatomy; no rotation assumed from another part.',
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
            'sourceAnchorNwn':[(lo[0]+hi[0])/2,(lo[1]+hi[1])/2,float(lo[2])],
            'targetAnchorShinLocal':[.0031548,-.0630081,-.466704],
            'orientationEvidence':'UNCONFIRMED: inspect actual anatomy before placing.','label':'Uncalibrated left shin'}
        (out/'placement-config-template.json').write_text(json.dumps(template,indent=2)+'\n',encoding='utf-8')
    else:
        require(args.config is not None,'Explicit similarity config required');config=json.loads(args.config.read_text(encoding='utf-8'))
        frozen[str(args.config.resolve())]=sha(args.config)
        allowed={'schemaVersion','diagnosticOnly','sourceSha256','generationSha256','jobPromptId','stockRootSha256','connectorReceiptSha256','protectedNeighbourSha256','uniformScale','rotationDegreesXYZ','properRotationMatrixNwn','sourceAnchorNwn','targetAnchorShinLocal','orientationEvidence','label','landmarkNotes','centerlineEvidence'}
        require(not set(config)-allowed and config.get('schemaVersion')==1 and config.get('diagnosticOnly') is True,'Explicit known diagnostic controls only')
        for key,value in [('sourceSha256',sha(source)),('generationSha256',sha(generation)),('jobPromptId',job['promptId']),('stockRootSha256',sha(root)),('connectorReceiptSha256',sha(connectors)),('protectedNeighbourSha256',PROTECTED)]:require(config.get(key)==value,'Fit association mismatch '+key)
        evidence=config.get('orientationEvidence','');require(isinstance(evidence,str) and len(evidence)>20 and 'UNCONFIRMED' not in evidence,'Actual anatomical evidence required')
        scale=float(config['uniformScale']);anchor=np.asarray(config['sourceAnchorNwn'],float);target=np.asarray(config['targetAnchorShinLocal'],float)
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
        result.update(configuration=config,affineNwnToShinLocal=affine.tolist(),properRotationMatrixNwn=r.tolist(),
            candidate=str(candidate),candidateSha256=sha(candidate),nativeCornerArchive={'path':str(archive),'sha256':sha(archive)},
            targetBoundsShinLocal=bounds(corners['positions']),proof=proof,maximumUniformTriangleEdgeErrorMetres=error,
            normalPolicy='Proper rotation only, authored magnitude retained; float64 archive versus measured rendered FLOAT32.',
            uvPolicy='Raw GLTF unchanged; native V flips once only.')
        replacement={'label':config.get('label','Left shin uniform first fit'),'modelPrefix':'pmh0','height':1.9339157,
            'parts':{'chest':str(protected['torso']),'pelvis':str(protected['pelvis']),'legl':str(protected['left-thigh']),'legr':str(protected['right-thigh']),'shinl':str(candidate)},
            'diagnosticOnly':True,'placementReceipt':str(out/'placement.json')}
        (out/'stock-replacement.json').write_text(json.dumps(replacement,indent=2)+'\n',encoding='utf-8');shutil.copy2(args.config,out/'executed-config.json')
    shutil.copy2(source,out/'frozen-source.glb');shutil.copy2(generation,out/'frozen-generation.json');shutil.copy2(code,out/'executed-place_purposebuilt_shin.py')
    for path,h in frozen.items():require(sha(Path(path))==h,'Frozen input changed '+path)
    result['inputsUnchanged']=True;result['commandArguments']=__import__('sys').argv[1:]
    (out/('inspection.json' if args.phase=='inspect' else 'placement.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'phase':args.phase,'output':str(out),'sourceTriangles':len(p),'sourceBoundsNwn':result['sourceBoundsNwn'],'placedBounds':result.get('targetBoundsShinLocal')}))


if __name__=='__main__':main()
