"""Blender CPU BVH: read-only visibility/opposed-sheet classification.

Centroid rays are evidence, not proof of complete triangle invisibility. A
deletion recommendation additionally requires neighborhood checks, protected
connector bands, and a closed coherent retained topology. No source is edited.
"""
import argparse
import itertools
import json
from pathlib import Path
import shutil
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from conservative_face_selection import mesh_arrays, topology
from place_purposebuilt_pelvis import read_glb
from target_contract import load, require, sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    config_path=args.config.resolve();config=json.loads(config_path.read_text())
    require(config['kind']=='target-sheet-investigation' and config['schemaVersion']==2 and
            config['diagnosticOnly'] is True,'Explicit v2 diagnostic investigation required')
    source=Path(config['source']).resolve();job_path=Path(config['generationReceipt']).resolve()
    target_path=Path(config['targetContract']).resolve();target=load(target_path)
    require(config['part'] in target['models'],'Declared target ownership required')
    pins={str(source):config['sourceSha256'],str(job_path):config['generationReceiptSha256'],
          str(target_path):config['targetContractSha256'],**config['protectedInputs'],**config['evidenceInputs']}
    pins[str(config_path)]=sha(config_path)
    for name in ('investigate_target_sheet.py','conservative_face_selection.py',
                 'place_purposebuilt_pelvis.py','target_contract.py'):
        path=Path(__file__).with_name(name).resolve();pins[str(path)]=sha(path)
    for name,pin in pins.items():require(sha(name)==pin,'Frozen investigation input changed: '+name)
    job=json.loads(job_path.read_text())
    require(job['state']=='success' and len([r for r in job['outputs'] if
        Path(r['localPath']).resolve()==source and r['sha256']==config['sourceSha256']])==1,
        'Exact same-source collected master required')
    output=args.output.resolve();require(not output.exists(),'Fresh read-only evidence directory required')
    output.mkdir(parents=True);(output/'tools').mkdir()
    snapshots={}
    for name,pin in pins.items():
        path=Path(name)
        if path.suffix=='.py':
            copied=output/'tools'/path.name;require(not copied.exists(),'Snapshot name collision')
            shutil.copy2(path,copied);snapshots[name]={'snapshot':str(copied),'sha256':pin}
    shutil.copy2(config_path,output/'config.json')
    document,binary=read_glb(source);positions,faces,primitive=mesh_arrays(document,binary)
    points=positions.astype(float);triangles=points[faces]
    cross=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    lengths=np.linalg.norm(cross,axis=1);require(np.all(lengths>1e-15),'Nondegenerate source faces required')
    normals=cross/lengths[:,None];centers=triangles.mean(1)
    bvh=BVHTree.FromPolygons([Vector(p) for p in points],faces.tolist(),all_triangles=True)
    span=np.ptp(points,axis=0);distance=float(np.linalg.norm(span)*3)
    epsilon=float(config['rayEpsilon']);max_pair=float(config['maximumSheetPairDistance'])
    require(0<epsilon<max_pair/100 and max_pair<.05,'Explicit bounded source-coordinate pairing distances required')
    directions=np.asarray([v for v in itertools.product((-1.,0.,1.),repeat=3) if v!=(0.,0.,0.)])
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    visible=np.zeros(len(faces),dtype=np.uint32);forward_face=np.full(len(faces),-1,np.int64)
    forward_distance=np.full(len(faces),np.inf);back_face=np.full(len(faces),-1,np.int64)
    back_distance=np.full(len(faces),np.inf)
    begun=time.time()
    for i,(center,normal) in enumerate(zip(centers,normals)):
        if i%5000==0:print(json.dumps({'phase':'face-centroid-rays','processed':i,'total':len(faces),
                                    'elapsedSeconds':time.time()-begun}),flush=True)
        for index,direction in enumerate(directions):
            _,_,hit,_=bvh.ray_cast(Vector(center+direction*distance),Vector(-direction),distance+epsilon*10)
            if hit==i:visible[i]|=np.uint32(1<<index)
        for sign,face_rows,distance_rows in ((1,forward_face,forward_distance),(-1,back_face,back_distance)):
            _,_,hit,d=bvh.ray_cast(Vector(center+normal*epsilon*sign),Vector(normal*sign),distance)
            if hit is not None:face_rows[i]=hit;distance_rows[i]=d+epsilon
    exposed=(visible!=0)|(forward_face<0)
    pair_valid=(back_face>=0)&(back_distance<=max_pair)&(back_distance>=epsilon*10)
    opposition=np.full(len(faces),np.nan)
    opposition[pair_valid]=np.einsum('ij,ij->i',normals[pair_valid],normals[back_face[pair_valid]])
    confident=pair_valid & (opposition<=config['maximumPairedNormalDot']) & ~exposed
    ids=np.flatnonzero(confident)
    confident[ids]&=exposed[back_face[ids]]
    protected=np.zeros(len(faces),bool)
    for band in config['protectedConnectorBands']:
        axis=band['axis'];lower,upper=band['interval']
        require(axis in (0,1,2) and lower<=upper,'Explicit source-coordinate connector bands required')
        protected|=np.any((triangles[:,:,axis]>=lower)&(triangles[:,:,axis]<=upper),axis=1)
    protected_ids=np.flatnonzero(protected);delete=confident & ~protected
    # Classification alone must not justify deleting any sampled-visible face.
    require(not np.any(delete&exposed),'Selected concealed sheet contains sampled exterior faces')
    proposed=topology(positions,faces[~delete]);before=topology(positions,faces)
    array_path=output/'face-classification.npz'
    np.savez_compressed(array_path,sourceFaces=faces,geometricNormals=normals,centroids=centers,
                        visibleDirectionBits=visible,forwardHitFace=forward_face,
                        forwardHitDistance=forward_distance,opposedSheetFace=back_face,
                        opposedSheetDistance=back_distance,pairedNormalDot=opposition,
                        sampledExposedMask=exposed,confidentConcealedSheetMask=confident,
                        protectedConnectorMask=protected,proposedDeleteMask=delete)
    report={'schemaVersion':2,'kind':'target-sheet-face-classification','readOnly':True,
            'targetContract':str(target_path),'targetContractSha256':config['targetContractSha256'],
            'targetId':target['id'],'rigRevision':target['rig']['revision'],'part':config['part'],
            'model':target['models'][config['part']], 'source':str(source),'sourceSha256':sha(source),
            'sourceCoordinates':'Original GLB X horizontal / Y vertical / Z depth, no fitting or stature conversion',
            'faceArchive':{'path':str(array_path),'sha256':sha(array_path)},
            'method':'26 external direction centroid visibility rays; outward-normal escape; inward-normal opposed-near-sheet ray pairing',
            'rayDirections':directions.tolist(),'rayEpsilon':epsilon,'maximumSheetPairDistance':max_pair,
            'maximumPairedNormalDot':config['maximumPairedNormalDot'],
            'protectedConnectorBands':config['protectedConnectorBands'],
            'counts':{'sourceFaces':len(faces),'sampledExposedFaces':int(exposed.sum()),
                      'opposedNearPairs':int(pair_valid.sum()),'confidentConcealedSheetFaces':int(confident.sum()),
                      'protectedConnectorFaces':len(protected_ids),'proposedDeletedFaces':int(delete.sum()),
                      'proposedRetainedFaces':int((~delete).sum())},
            'pairedDistancesOfProposedDeletedFaces':{'minimum':float(back_distance[delete].min()) if delete.any() else None,
                'maximum':float(back_distance[delete].max()) if delete.any() else None,
                'median':float(np.median(back_distance[delete])) if delete.any() else None},
            'beforeTopology':before,'proposedSelectionTopology':proposed,
            'sourceChanged':False,'protectedNeighborsChanged':False,'descendantWritten':False,
            'frozenInputs':pins,'helperSnapshots':snapshots,'elapsedSeconds':time.time()-begun,
            'deletionSafeForAutomaticDescendant':False,'rigPilotAccepted':False,'clientAccepted':False,
            'limitations':['Face-centroid visibility does not prove whole-triangle invisibility.',
                'Protected original connector bands retain their inner-wall faces; removal may create broad irregular boundaries.',
                'No connector, anatomy, material or native/client acceptance is inferred.']}
    for name,pin in pins.items():require(sha(name)==pin,'Investigation input changed during execution: '+name)
    for name,pin in snapshots.items():require(sha(pin['snapshot'])==pin['sha256'],'Helper snapshot changed')
    (output/'classification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'output':str(output/'classification.json'),'sha256':sha(output/'classification.json'),
                      'counts':report['counts'],'proposedTopology':{k:v for k,v in proposed.items()
                            if k not in ('boundaryLoops','nonmanifoldEdgeRecords','boundaryIncidentFaceIds')}}),flush=True)


if __name__=='__main__':main()
