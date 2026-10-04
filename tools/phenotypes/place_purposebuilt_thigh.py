"""Inspect/fit one actual generated LEFT Human male thigh, no mesh editing.

Uses a recorded proper rotation, one positive uniform scale and translation.
Detached geometry bake keeps original accessor/image bytes in its BIN prefix;
new transformed position/normal/tangent accessors have measured float32 error.
Authoritative double corner arrays preserve authored normal directions/lengths.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np

from place_purposebuilt_pelvis import (bounds, embedded_maps, raw_corners,
    read_glb, require, rotation_xyz, sha, write_glb)
from retarget import nodes, transforms

TORSO_SHA = '3ae78d023ba522d94c44d9914bac0b36f35b640c42b9532015575e5572161a50'
PELVIS_SHA = 'db0bdf16099068da3bb685bcb61ae93ebed115e6ddbae90990c0b55e59b8d98a'
STOCK_HEIGHT = .5348146


def compact_section(points, height, band=.008):
    selected=points[np.abs(points[:,2]-height)<=band/2]
    return {'z':float(height),'bandThickness':band,'sampleCount':len(selected),
        'bounds':bounds(selected) if len(selected) else None,
        'mean':selected.mean(0).tolist() if len(selected) else None}


def section_centroid(triangles, height):
    """Length-weighted real horizontal intersections, avoiding vertex density bias."""
    segments=[]
    for tri in triangles:
        rows=[]
        for p,q in zip(tri,np.roll(tri,-1,axis=0)):
            a,b=p[2]-height,q[2]-height
            if abs(a)<1e-12:rows.append(p)
            if a*b<0:rows.append(p+(q-p)*(-a/(b-a)))
        if len(rows)==2 and np.linalg.norm(rows[1]-rows[0])>1e-12:segments.append(rows)
    require(segments,'No actual connector section at proposed anchor')
    segments=np.asarray(segments)
    weight=np.linalg.norm(segments[:,1]-segments[:,0],axis=1)
    centre=np.average(segments.mean(1),axis=0,weights=weight)
    return centre, {'z':float(height),'segments':len(segments),'perimeterSum':float(weight.sum()),
        'lengthWeightedCentroid':centre.tolist(),'bounds':bounds(segments),
        'limits':'Includes every intersected shell; reject anchors if actual topology shows nested/internal surfaces biasing centre.'}


def centerline_proposal(triangles, orientation_degrees, measured):
    """Measured two-landmark similarity proposal, never an anatomy classifier.

Hip/knee anchor Z is inferred from actual stock hidden-end allowances under
initial height calibration. A generator has no authored skeleton; visual/pose
review must approve these inferred anchors. No stock surface projection.
"""
    orient=rotation_xyz(orientation_degrees)
    oriented=triangles@orient.T
    lo,hi=oriented.reshape(-1,3).min(0),oriented.reshape(-1,3).max(0)
    initial_scale=STOCK_HEIGHT/(hi[2]-lo[2])
    hip_z=hi[2]-.0717686/initial_scale
    knee_z=lo[2]+.0021100/initial_scale
    hip,hrow=section_centroid(oriented,hip_z)
    knee,krow=section_centroid(oriented,knee_z)
    vector=knee-hip
    target=np.asarray(measured['leftDesign']['hipToKneePivotVector'])
    a,b=vector/np.linalg.norm(vector),target/np.linalg.norm(target)
    cross=np.cross(a,b);cos=float(np.dot(a,b));sine=float(np.linalg.norm(cross))
    require(cos>-.999999,'Antiparallel axial direction requires explicit orientation correction')
    k=np.asarray([[0,-cross[2],cross[1]],[cross[2],0,-cross[0]],[-cross[1],cross[0],0]])
    correction=np.eye(3)+k+k@k/(1+cos)
    rotation=correction@orient
    scale=float(np.linalg.norm(target)/np.linalg.norm(vector))
    original_hip=hip@orient
    original_knee=knee@orient
    return {'uniformScale':scale,'properRotationMatrixNwn':rotation.tolist(),
        'sourceAnchorNwn':original_hip.tolist(),'targetAnchorThighLocal':[0,0,0],
        'centerlineEvidence':{'initialOrientationDegreesXYZ':orientation_degrees,'initialHeightScale':initial_scale,
            'sourceHipAnchor':hrow,'sourceKneeAnchor':krow,'sourceKneeAnchorNwn':original_knee.tolist(),
            'targetHipAnchorThighLocal':[0,0,0],'targetKneeAnchorThighLocal':target.tolist(),
            'minimalAxisCorrectionDegrees':float(np.rad2deg(np.arctan2(sine,cos))),
            'assumption':'Source hip joint lies stock71.769mm below highestcap; knee joint stock2.110mm above lowestcap after initialheight calibration. Verify actual anatomicalend surfaces/poses.',
            'scope':'Uniformsimilarity only; inferred source attachment anchors, not an authored source skeleton.'}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['inspect','place'])
    for key in ['source','generation','stock-root','frozen-torso','frozen-pelvis','connectors','output']:
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--config',type=Path)
    args=parser.parse_args()
    require(not args.output.exists(),'Fresh output required')
    source=args.source.resolve();jobpath=args.generation.resolve();root=args.stock_root.resolve()
    torso=args.frozen_torso.resolve();pelvis=args.frozen_pelvis.resolve();connectors=args.connectors.resolve()
    job=json.loads(jobpath.read_text())
    require(job.get('state')=='success' and job.get('promptId'),'Successful collected generation required')
    matched=[o for o in job.get('outputs',[]) if Path(o.get('localPath','')).resolve()==source and o.get('sha256')==sha(source)]
    require(len(matched)==1,'Actual selected source path/hash must match successful job')
    require(sha(torso)==TORSO_SHA and sha(pelvis)==PELVIS_SHA,'Protected torso/pelvis hash mismatch')
    measured=json.loads(connectors.read_text())
    require(measured['parts']['legl']['model']=='pmh0_legl001','Actual stock left-thigh measurement required')
    require(abs(measured['parts']['legl']['localBounds']['extent'][2]-STOCK_HEIGHT)<1e-12,'Stock source height mismatch')
    world=transforms(nodes(root.read_text(encoding='cp1252')))
    require(np.array_equal(world['lthigh_g'],np.asarray(measured['stockJointWorldMatrices']['lthigh_g'])),'Measured/root left attachment mismatch')
    extra={};doc,binary=read_glb(source)
    p,n,uv,primitives=raw_corners(doc,binary,allow_wrapper=True,extra=extra)
    maps=embedded_maps(doc,binary)
    unique=np.unique(p.reshape(-1,3),axis=0);lo,hi=unique.min(0),unique.max(0)
    code=Path(__file__).resolve()
    files=[source,jobpath,root,torso,pelvis,connectors,code,code.with_name('place_purposebuilt_pelvis.py'),code.with_name('retarget.py')]
    frozen={str(path):sha(path) for path in files}
    result={'schemaVersion':1,'diagnosticOnly':True,'phase':args.phase,'part':'legl','model':'pmh0_legl001','joint':'lthigh_g',
        'source':str(source),'sourceSha256':sha(source),'generation':str(jobpath),'generationSha256':sha(jobpath),'jobPromptId':job['promptId'],
        'frozenInputHashes':frozen,'coordinateBasis':'RawglTF→NWN=[X,-Z,Y], front+Y/up+Z; target exactlthigh_g local.',
        'stockJointWorldMatrix':world['lthigh_g'].tolist(),'stockShinRelativeToThigh':(np.linalg.inv(world['lthigh_g'])@world['lshin_g']).tolist(),
        'sourceBoundsNwn':bounds(p),'sourcePrimitives':primitives,'sourceTriangles':len(p),'embeddedMaps':maps,
        'sourceEndBands':[compact_section(unique,float(z),.020) for z in [lo[2]+.010,lo[2]+.04,hi[2]-.04,hi[2]-.010]],
        'sourceRelativeSections':[compact_section(unique,lo[2]+fraction*(hi[2]-lo[2])) for fraction in [.1,.25,.5,.75,.9]],
        'heightFirstUniformScaleProposal':float(STOCK_HEIGHT/(hi[2]-lo[2])),
        'stockRigOrAnimationsModified':False,'protectedTorsoOrPelvisModified':False,'nativeOrClientAccepted':False,
        'orientationPolicy':'No anatomy orientation inferred from label or source mesh axes. Inspect actual front/rear/medial/lateral source images before selecting proper rotation.'}
    out=args.output.resolve();out.mkdir(parents=True)
    if args.phase=='inspect':
        archive=out/'source-corners.npz'
        attrs={}
        for semantic,record in extra.items():
            attrs['source'+semantic]=np.concatenate(record['rows'])
            attrs[semantic+'TriangleIndices']=np.asarray(record['triangleIndices'],dtype=np.int64)
        np.savez_compressed(archive,positions=p,normals=n,uvGltf=uv,**attrs)
        result['sourceCornerArchive']={'path':str(archive),'sha256':sha(archive)}
        template={'schemaVersion':1,'diagnosticOnly':True,'sourceSha256':sha(source),'generationSha256':sha(jobpath),
            'jobPromptId':job['promptId'],'stockRootSha256':sha(root),'frozenTorsoSha256':TORSO_SHA,'frozenPelvisSha256':PELVIS_SHA,
            'connectorReceiptSha256':sha(connectors),'uniformScale':result['heightFirstUniformScaleProposal'],
            'rotationDegreesXYZ':[0,0,0],'sourceAnchorNwn':[(lo[0]+hi[0])/2,(lo[1]+hi[1])/2,float(lo[2])],
            'targetAnchorThighLocal':[.028073,-.0247583,-.463046],
            'orientationEvidence':'UNCONFIRMED: template only; do not execute without actual anatomy inspection.',
            'label':'Uncalibrated left thigh','landmarkNotes':'Height-first proposal only. Inspect actual capcentres/tilt/width, preserve muscle volume, no stretch.'}
        (out/'placement-config-template.json').write_text(json.dumps(template,indent=2)+'\n')
    else:
        require(args.config is not None,'Explicit source-associated similarity config required')
        config=json.loads(args.config.read_text());frozen[str(args.config.resolve())]=sha(args.config)
        allowed={'schemaVersion','diagnosticOnly','sourceSha256','generationSha256','jobPromptId','stockRootSha256',
            'frozenTorsoSha256','frozenPelvisSha256','connectorReceiptSha256','uniformScale','rotationDegreesXYZ',
            'sourceAnchorNwn','targetAnchorThighLocal','orientationEvidence','label','landmarkNotes',
            'properRotationMatrixNwn','centerlineEvidence'}
        require(not set(config)-allowed,'Unknown fitting fields rejected')
        require(config.get('schemaVersion')==1 and config.get('diagnosticOnly') is True,'Explicit diagnostic fit required')
        for k,v in [('sourceSha256',sha(source)),('generationSha256',sha(jobpath)),('jobPromptId',job['promptId']),
                    ('stockRootSha256',sha(root)),('frozenTorsoSha256',TORSO_SHA),('frozenPelvisSha256',PELVIS_SHA),('connectorReceiptSha256',sha(connectors))]:
            require(config.get(k)==v,'Fit source/rig/acceptedpart association mismatch '+k)
        evidence=config.get('orientationEvidence','')
        require(isinstance(evidence,str) and len(evidence)>20 and 'UNCONFIRMED' not in evidence,'Actual anatomical orientation evidence required')
        scale=float(config['uniformScale'])
        anchor=np.asarray(config['sourceAnchorNwn'],float);target=np.asarray(config['targetAnchorThighLocal'],float)
        require(np.isfinite(scale) and 0<scale<10,'Positive finite uniform scale required')
        require(all(v.shape==(3,) and np.isfinite(v).all() for v in [anchor,target]),'Finite3D transform controls required')
        require(('rotationDegreesXYZ' in config)^('properRotationMatrixNwn' in config),'Exactly one explicit rotation representation required')
        if 'properRotationMatrixNwn' in config:
            r=np.asarray(config['properRotationMatrixNwn'],float)
            require(r.shape==(3,3) and np.isfinite(r).all() and np.max(abs(r.T@r-np.eye(3)))<1e-10 and abs(np.linalg.det(r)-1)<1e-10,'Proper orthogonal3D rotation required')
        else:
            degrees=np.asarray(config['rotationDegreesXYZ'],float)
            require(degrees.shape==(3,) and np.isfinite(degrees).all(),'FiniteXYZ angles required')
            r=rotation_xyz(degrees)
        affine=np.eye(4);affine[:3,:3]=r*scale;affine[:3,3]=target-scale*r@anchor
        from mirror_stock_limb_part import detached_affine_bake
        frozen[str(code.with_name('mirror_stock_limb_part.py'))]=sha(code.with_name('mirror_stock_limb_part.py'))
        placed_doc,placed_bin,corners,proof=detached_affine_bake(doc,binary,affine,allow_reflection=False)
        candidate=out/'placed-local.glb';write_glb(candidate,placed_doc,placed_bin)
        actual_doc,actual_bin=read_glb(candidate)
        ap,an,au,_=raw_corners(actual_doc,actual_bin)
        expected=p@affine[:3,:3].T+affine[:3,3];expected_n=n@r.T
        require(np.max(abs(corners['positions']-expected))<2e-12 and np.max(abs(corners['normals']-expected_n))<2e-12,'Authoritative similarity derivation mismatch')
        require(np.array_equal(au,uv) and embedded_maps(actual_doc,actual_bin)==maps,'Actual serialized UV/maps changed')
        require(np.max(abs(ap-corners['positions']))<1e-6 and np.max(abs(an-corners['normals']))<1e-6,'Serialized float32 transform beyond precision budget')
        require(actual_bin[:len(binary)]==binary,'Original source BIN prefix changed')
        edges=lambda x:np.linalg.norm(x[:,[1,2,0]]-x[:,[0,1,2]],axis=2)
        uniform_error=float(np.max(abs(edges(corners['positions'])-edges(p)*scale)))
        require(uniform_error<2e-12,'Triangle similarity failed; mesh deformation prohibited')
        archive=out/'native-corners.npz';np.savez_compressed(archive,**corners)
        result.update(configuration=config,affineNwnToThighLocal=affine.tolist(),properRotationMatrixNwn=r.tolist(),
            placedSource=str(candidate),placedSourceSha256=sha(candidate),candidate=str(candidate),candidateSha256=sha(candidate),targetBoundsThighLocal=bounds(corners['positions']),
            nativeCornerArchive={'path':str(archive),'sha256':sha(archive)},proof=proof,
            maximumUniformTriangleEdgeErrorMetres=uniform_error,
            normalPolicy='Rotate authored directions only; no normalization, smoothing or computed substitutions. Native archive double, rendered accessor FLOAT32.',
            uvPolicy='uvGltf raw sampling unchanged; uvNative V=1-rawV exactlyonce; no secondflip.',
            canonicalBakePolicy='Source BIN/accessors retained as prefix evidence; appended transformedP/N/T accessors and canonical identityscene. No topology/shape edits.')
        replacement={'label':config.get('label','Purpose-built left thigh firstfit'),'modelPrefix':'pmh0','height':1.9339157,
            'parts':{'chest':str(torso),'pelvis':str(pelvis),'legl':str(candidate)},'diagnosticOnly':True,
            'placementReceipt':str(out/'placement.json')}
        (out/'stock-replacement.json').write_text(json.dumps(replacement,indent=2)+'\n')
        shutil.copy2(args.config,out/'executed-config.json')
    shutil.copy2(source,out/'frozen-source.glb');shutil.copy2(jobpath,out/'frozen-generation.json')
    shutil.copy2(code,out/'executed-place_purposebuilt_thigh.py')
    for path,expected_hash in frozen.items():require(sha(path)==expected_hash,'Input changed '+path)
    result['inputsUnchanged']=True
    (out/('inspection.json' if args.phase=='inspect' else 'placement.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'phase':args.phase,'output':str(out),'triangles':len(p),'sourceBoundsNwn':result['sourceBoundsNwn'],
        'heightFirstScale':result['heightFirstUniformScaleProposal'],'placedBounds':result.get('targetBoundsThighLocal')}))


if __name__=='__main__':main()
