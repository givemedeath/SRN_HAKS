"""Read-only connector review packet from explicit, pinned ASCII and motion inputs."""
import argparse
import json
from pathlib import Path
import numpy as np
from run_preparation import PreparationContext
from prepare_effective_body_preview import mesh_corners
from shared_toolchain import sha
from shared_tools import sha, read_json, write_json
from tool_runtime import record_dependencies


def matrix(value):
    m=np.asarray(value,float)
    if m.shape!=(4,4) or not np.isfinite(m).all() or not np.allclose(m[3],[0,0,0,1]) or not np.allclose(m[:3,:3].T@m[:3,:3],np.eye(3),atol=1e-9) or np.linalg.det(m[:3,:3])<=0:
        raise ValueError('Explicit rigid attachment frame required')
    return m


def points(context,row):
    if sha(row['path'])!=row['sha256']:raise ValueError('Declared geometry changed')
    meshes=context.prepared(row['path'],'geometry-decode',lambda data:mesh_corners(data.decode('cp1252')),
        settings={'encoding':'cp1252','decoderSha256':sha(Path(__file__).with_name('prepare_effective_body_preview.py'))})
    p=np.concatenate([mesh['position'].reshape(-1,3) for mesh in meshes])
    frame=matrix(row['attachmentFrame'])
    p=p@frame[:3,:3].T+frame[:3,3]
    band=np.asarray(row['connectorBounds'],float)
    if band.shape!=(2,3) or np.any(band[0]>band[1]):raise ValueError('Explicit ordered connector bounds required')
    selected=p[np.all((p>=band[0])&(p<=band[1]),axis=1)]
    if not len(selected):raise ValueError('Empty connector band; reconcile coordinate space')
    return selected,{'attachmentFrame':frame.tolist(),'joint':row['joint'],
        'center':selected.mean(axis=0).tolist(),'min':selected.min(axis=0).tolist(),
        'max':selected.max(axis=0).tolist(),'extent':np.ptp(selected,axis=0).tolist(),'corners':len(selected)}


def contact(a,b,origin,axis):
    axis=np.asarray(axis,float);length=np.linalg.norm(axis)
    if length<1e-12:raise ValueError('Measured contact axis required')
    axis/=length;origin=np.asarray(origin,float)
    left=(a-origin)@axis;right=(b-origin)@axis
    # Bounded memory; a closest-corner diagnostic is not surface intersection.
    nearest=min(float(np.linalg.norm(x[:,None,:]-y[None,:,:],axis=2).min())
                for x in np.array_split(a,max(1,(len(a)+255)//256))
                for y in np.array_split(b,max(1,(len(b)+255)//256)))
    return {'axialOverlap':float(left.max()-right.min()),'closestCornerDistance':nearest,
            'parentPastJoint':float(left.max()),'neighborBeforeJoint':float(-right.min()),
            'interpretation':'Axial intervals and corner proximity; not volumetric contact or anatomical acceptance'}


def build(config_path,output):
    if Path(output).exists():raise FileExistsError('Fresh immutable joint review packet required')
    config_path=Path(config_path).resolve();config=read_json(config_path)
    settings=config['reviewSettings']
    if not 1<=settings.get('threads',4)<=4 or settings.get('cameraScale',0)<=0:
        raise ValueError('Positive matched camera scale and at most four render threads required')
    if config.get('coordinateSpace')!='nwn-part-local':raise ValueError('Explicit NWN part-local coordinate space required')
    samples=config['motionSamples']
    if not samples or not any(row.get('standing') is True for row in samples) or len(samples)<2:
        raise ValueError('Standing and measured motion samples required')
    helpers=[Path(__file__).resolve(),Path(__file__).with_name('prepare_effective_body_preview.py'),
             Path(__file__).with_name('audit_geometry.py'),Path(__file__).with_name('place_purposebuilt_pelvis.py')]
    context=PreparationContext(target_revision=config['targetRevision'],rig_revision=config['rigRevision'],
        animation_revision=config['animationRevision'],settings=config['reviewSettings'],dependencies=[config_path,*helpers])
    prepared={};connectors={}
    for name in ('parent','candidate','neighbor'):
        prepared[name],connectors[name]=points(context,config[name])
    materials=[]
    for pin in config.get('materialInputs',[]):
        context.read(pin['path'])
        if sha(pin['path'])!=pin['sha256']:raise ValueError('Material input changed')
        materials.append(pin)
    rows=[]
    for row in samples:
        matrices,receipt=context.pose(config['asciiDirectory'],config['prefix'],row['clip'],row['time'],config.get('stockDirectory'))
        transformed={}
        for name,p in prepared.items():
            m=matrices[config[name]['joint'].lower()]
            transformed[name]=p@m[:3,:3].T+m[:3,3]
        neighbor_frame=matrices[config['neighbor']['joint'].lower()]
        origin=neighbor_frame[:3,3];axis=neighbor_frame[:3,:3]@np.asarray(config['contactAxis'],float)
        rows.append({'sample':row,'pose':receipt,'parent':contact(transformed['parent'],transformed['neighbor'],origin,axis),
            'candidate':contact(transformed['candidate'],transformed['neighbor'],origin,axis)})
    worst_overlap=min(rows,key=lambda row:row['candidate']['axialOverlap'])['sample']
    worst_distance=max(rows,key=lambda row:row['candidate']['closestCornerDistance'])['sample']
    packet={'schemaVersion':1,'kind':'joint-review-packet','coordinateSpace':config['coordinateSpace'],
        'inputHashes':context.receipt()['inputs'],'geometry':{name:config[name] for name in prepared},
        'connectors':connectors,'motionMeasurements':rows,'initialReviewSamples':
            {'standing':[row for row in samples if row.get('standing')],'worstAxialOverlap':worst_overlap,'worstCornerDistance':worst_distance},
        'reviewViews':[{'mode':mode,'settings':config['reviewSettings'],'settingsMatch':True} for mode in ['clay','unlit-color','native-material']],
        'materialInputs':materials,'preparation':context.receipt(),
        'reviewQuestions':{'placement':'Do attachment centers move together?', 'excessGeometry':'Do caps/shelves protrude or penetrate during motion?',
            'materialTransition':'Does the same defect persist in clay and unlit color?',
            'previewImportDiscrepancy':'Compare decoded ASCII, imported corner counts and native attribute audit before editing geometry.'},
        'numericSuccessApprovesAnatomy':False,'broaderMotionMatrixRequiredBeforePromotion':True,
        'clientEvidence':False,'productionAccepted':False}
    packet['dependencyReceipt']=str(record_dependencies(packet['inputHashes']))
    write_json(output,packet,fresh=True);return packet

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();build(a.config,a.output)
