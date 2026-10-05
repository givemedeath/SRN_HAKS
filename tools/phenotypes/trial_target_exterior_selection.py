"""Blender CPU BVH: explicitly pinned outer-sheet index-only repair trial.

Retain a measured coherent visible outer component, remove its internal sheet,
and close at most one tiny original defect using existing source vertex rows.
No new anatomy, displacement, remesh, fit, normals, UVs or material pixels.
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

from conservative_face_selection import (cap_one_micro_boundary, descendant, face_components,
                                         mesh_arrays, topology)
from place_purposebuilt_pelvis import accessor, read_glb
from target_contract import load, require, sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    config_path=args.config.resolve();config=json.loads(config_path.read_text())
    require(config.get('schemaVersion')==2 and config.get('kind')=='target-exterior-selection-trial' and
            config['diagnosticOnly'] is True,'Explicit v2 diagnostic face-selection configuration required')
    source=Path(config['source']).resolve();classified_path=Path(config['classification']).resolve()
    target_path=Path(config['targetContract']).resolve();target=load(target_path)
    pins={str(source):config['sourceSha256'],str(classified_path):config['classificationSha256'],
          str(target_path):config['targetContractSha256'],**config['protectedInputs']}
    pins[str(config_path)]=sha(config_path)
    for name in ('trial_target_exterior_selection.py','conservative_face_selection.py',
                 'place_purposebuilt_pelvis.py','target_contract.py'):
        path=Path(__file__).with_name(name).resolve();pins[str(path)]=sha(path)
    for name,pin in pins.items():require(sha(name)==pin,'Frozen trial input changed: '+name)
    classified=json.loads(classified_path.read_text())
    require(classified['kind']=='target-sheet-face-classification' and classified['source']==str(source) and
            classified['sourceSha256']==config['sourceSha256'] and classified['targetContractSha256']==sha(target_path)
            and classified['targetId']==target['id'] and classified['rigRevision']==target['rig']['revision'],
            'Classification source/target binding differs')
    archive=Path(classified['faceArchive']['path']);require(sha(archive)==classified['faceArchive']['sha256'],
            'Face classification archive changed');pins[str(archive)]=sha(archive)
    # Historical executable snapshots are immutable evidence even after a new
    # helper revision is introduced; never reinterpret them as current code.
    for origin,pin in classified['frozenInputs'].items():
        if origin in classified['helperSnapshots']:
            snapshot=Path(classified['helperSnapshots'][origin]['snapshot'])
            require(sha(snapshot)==pin,'Historical classification helper snapshot changed')
            pins[str(snapshot)]=pin
        else:require(sha(origin)==pin,'Classification data input changed: '+origin);pins[origin]=pin
    document,binary=read_glb(source);positions,faces,primitive=mesh_arrays(document,binary)
    data=np.load(archive,allow_pickle=False);require(np.array_equal(data['sourceFaces'],faces),
            'Exact ordered source face association required')
    exposed_ids=np.flatnonzero(data['sampledExposedMask'])
    components=face_components(positions,faces[exposed_ids]);require(len(components)>0,'No classified exterior')
    kept=np.sort(exposed_ids[components[0]])
    fragment_ids=np.sort(np.concatenate([exposed_ids[row] for row in components[1:]])) if len(components)>1 else np.empty(0,int)
    require(len(fragment_ids)<=config['maximumExposedFragmentFaces'],
            'Multiple substantial sampled-visible components make exterior selection ambiguous')
    added,cap=cap_one_micro_boundary(positions,faces[kept],config['maximumConnectorChord'],config['maximumConnectorArea'])
    repaired_faces=np.concatenate((faces[kept],added))
    points=positions.astype(float);old=BVHTree.FromPolygons([Vector(v) for v in points],faces.tolist(),all_triangles=True)
    new=BVHTree.FromPolygons([Vector(v) for v in points],repaired_faces.tolist(),all_triangles=True)
    keep_mask=np.zeros(len(faces),bool);keep_mask[kept]=True;deleted=np.flatnonzero(~keep_mask)
    direction=np.asarray(classified['rayDirections'])
    barycentric=np.asarray(config['visibilityBarycentricSamples'],float)
    require(barycentric.ndim==2 and barycentric.shape[1]==3 and len(barycentric)>=7 and
            np.all(barycentric>0) and np.allclose(barycentric.sum(1),1,atol=1e-12,rtol=0),
            'Explicit interior barycentric visibility samples required')
    epsilon=config['rayEpsilon'];distance=float(np.linalg.norm(np.ptp(points,axis=0))*3)
    cap_coords=points[added].reshape(-1,3);cap_min=cap_coords.min(0);cap_max=cap_coords.max(0)
    visible_ids=set();shadowed_ids=set();unsafe=[];rays=0;begun=time.time()
    for offset,face in enumerate(deleted):
        if offset%2500==0:print(json.dumps({'phase':'deleted-face-corner-edge-rays','processed':offset,
                     'total':len(deleted),'elapsedSeconds':time.time()-begun}),flush=True)
        for sample in barycentric@points[faces[face]]:
            for ray in direction:
                origin=sample+ray*distance;rays+=1
                old_location,_,old_face,_=old.ray_cast(Vector(origin),Vector(-ray),distance+epsilon*10)
                if old_face!=face:continue
                visible_ids.add(int(face))
                new_location,_,new_face,_=new.ray_cast(Vector(origin),Vector(-ray),distance+epsilon*10)
                # A deleted inner point can lie behind the hole's bounding box.
                # Only the actual new tiny cap may occlude it, and the depth
                # change is independently bounded, preserving the cap silhouette.
                cap_shadow_depth=float(np.linalg.norm(np.asarray(old_location)-np.asarray(new_location))) if new_location is not None else np.inf
                if new_face is not None and new_face>=len(kept) and cap_shadow_depth<=config['maximumCapShadowDepth']:
                    shadowed_ids.add(int(face))
                elif len(unsafe)<100:
                    unsafe.append({'sourceFace':int(face),'sample':sample.tolist(),'direction':ray.tolist(),
                                   'sourceFirstHit':list(old_location),'newFace':new_face,
                                   'newFirstHit':list(new_location) if new_location is not None else None})
    normals=accessor(document,binary,primitive['attributes']['NORMAL']).astype(float)
    uv=accessor(document,binary,primitive['attributes']['TEXCOORD_0']).astype(float)
    coords=points[added];cross=np.cross(coords[:,1]-coords[:,0],coords[:,2]-coords[:,0]);cross/=np.linalg.norm(cross,axis=1)[:,None]
    authored=normals[added];authored/=np.linalg.norm(authored,axis=2)[:,:,None]
    normal_dot=np.einsum('ij,ikj->ik',cross,authored)
    cap['addedFaceAuthoredNormalGeometricDotRange']=[float(normal_dot.min()),float(normal_dot.max())]
    cap['addedRawUvTriangles']=uv[added].tolist()
    output=args.output.resolve();require(not output.exists(),'Fresh immutable face-selection trial output required')
    output.mkdir(parents=True);(output/'tools').mkdir();snapshots={}
    for name,pin in pins.items():
        path=Path(name)
        if path.suffix=='.py' and path.parent==Path(__file__).parent:
            copied=output/'tools'/path.name;shutil.copy2(path,copied)
            snapshots[name]={'snapshot':str(copied),'sha256':pin}
    shutil.copy2(config_path,output/'config.json')
    selection=output/'source-face-selection.npz'
    np.savez_compressed(selection,sourceFaces=faces,keptSourceFaceIds=kept,deletedSourceFaceIds=deleted,
                        excludedExposedFragmentSourceFaceIds=fragment_ids,addedSourceVertexFaces=added,
                        visibleDeletedSourceFaceIds=np.asarray(sorted(visible_ids),np.int64),
                        capShadowedDeletedSourceFaceIds=np.asarray(sorted(shadowed_ids),np.int64))
    candidate=output/'repaired-source.glb'
    eligible=not unsafe and bool(visible_ids==shadowed_ids)
    proof=descendant(source,candidate,kept,added) if eligible else None
    report={'schemaVersion':2,'kind':'target-face-selection-trial','diagnosticOnly':True,
            'targetContract':str(target_path),'targetContractSha256':sha(target_path),'targetId':target['id'],
            'rigRevision':target['rig']['revision'],'part':config['part'],'model':target['models'][config['part']],
            'source':str(source),'sourceSha256':sha(source),'sourceCoordinates':'Unfitted original GLB X/Y-up/Z-depth',
            'candidate':str(candidate) if eligible else None,'candidateSha256':sha(candidate) if eligible else None,
            'faceSelectionArchive':{'path':str(selection),'sha256':sha(selection)},
            'keptOriginalFaceIds':kept.tolist(),
            'activeSourcePrimitiveMapping':{'node':0,'mesh':0,'primitive':0,
                'attributes':primitive['attributes'],'originalIndexAccessor':primitive['indices'],
                'attributeAccessorDefinitions':{key:document['accessors'][value]
                                               for key,value in primitive['attributes'].items()},
                'originalIndexAccessorDefinition':document['accessors'][primitive['indices']],
                'faceIdPolicy':'Zero-based original serialized primitive index triples; order/winding retained',
                'capTriangleVertexIds':added.tolist()},
            'keptSourceFaceCount':len(kept),'deletedSourceFaceCount':len(deleted),'addedConnectorFaceCount':len(added),
            'excludedExposedFragmentSourceFaceIds':fragment_ids.tolist(),
            'microConnectorRepair':cap,'sourceEncodingProof':proof,
            'deletedFaceVisibility':{'barycentricSamples':barycentric.tolist(),'directionCount':len(direction),
                'rayCount':rays,'sampledVisibleDeletedFaceIds':sorted(visible_ids),
                'maximumCapShadowDepthBound':config['maximumCapShadowDepth'],
                'allSampledDeletedVisibilityOccludedByMicroCap':visible_ids==shadowed_ids,
                'unsafeFirstHitChanges':unsafe,'elapsedSeconds':time.time()-begun,
                'wholeTriangleContinuousVisibilityProof':False},
            'frozenInputs':pins,'helperSnapshots':snapshots,'sourceChanged':False,'protectedNeighborsChanged':False,
            'eligibleForOfflineReview':eligible,'rigPilotAccepted':False,'clientAccepted':False,'productionAccepted':False,
            'limitations':['Finite visibility samples do not prove every unsampled grazing direction.',
                'One tiny source hole is closed with neighboring original authored normals/UVs; native material/shading and posed seams require review.',
                'Chest shoulder-cap ownership/protrusion is a separate unresolved demonstrated defect.',
                'No fitting or stature conversion has been applied; selection requires a separately bound target fit receipt.']}
    for name,pin in pins.items():require(sha(name)==pin,'Trial input changed during execution: '+name)
    path=output/'face-selection.json';path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'receipt':str(path),'sha256':sha(path),'eligibleForOfflineReview':eligible,
        'keptFaces':len(kept),'deletedFaces':len(deleted),'addedFaces':len(added),
        'sampledVisibleDeletedFaces':len(visible_ids),'unsafeFirstHitChanges':len(unsafe),
        'candidateSha256':report['candidateSha256']}),flush=True)


if __name__=='__main__':main()
