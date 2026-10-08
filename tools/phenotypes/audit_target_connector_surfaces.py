"""Read-only exact-pose connector surface intersections/exposure; CPU Blender."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_geometry import arrays
from connector_surface_math import triangle_relation,distinct_ray_hits,parity_consensus
from conservative_face_selection import mesh_arrays,topology
from place_purposebuilt_pelvis import raw_corners,read_glb
from retarget import NODE,nodes,rotations
import target_contract as contract
from connector_audit_inputs import load_config,verify_pose

SAMPLES=np.asarray([[1/3,1/3,1/3],[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
RAYS=np.asarray([[1,.173,.297],[-.211,1,.319],[.233,-.431,1],[-1,.427,-.193],[.379,-1,-.517]])
RAYS/=np.linalg.norm(RAYS,axis=1)[:,None]
CONTACT=2e-6


def world(points,frame): return points@frame[:3,:3].T+frame[:3,3]


def ascii_mesh(path):
    text=Path(path).read_text(encoding='cp1252').split('endmodelgeom')[0];parsed=nodes(text);parts=[]
    def frame(name,seen=()):
        contract.require(name not in seen and name in parsed,'Unresolved stock mesh hierarchy')
        item=parsed[name];local=np.eye(4);local[:3,:3]=rotations(item['orientation']);local[:3,3]=item['position']
        parent=item['parent'];return local if parent=='null' else frame(parent,seen+(name,))@local
    for match in NODE.finditer(text):
        verts,faces=arrays(match[3],'verts'),arrays(match[3],'faces')
        if not verts or not faces: continue
        contract.require(match[1].lower() in ('trimesh','danglymesh'),'Unsupported stock weighted geometry')
        local=frame(match[2].lower());vertices=world(np.asarray(verts,dtype='f4').astype(float),local)
        ids=np.asarray(faces,dtype=float)[:,:3].astype(int);parts.append(vertices[ids])
    contract.require(parts,'No stock triangle geometry');return np.concatenate(parts)


class Surface:
    def __init__(self,triangles,closed):
        self.triangles=triangles;self.closed=closed
        self.tree=BVHTree.FromPolygons([Vector(v) for v in triangles.reshape(-1,3)],
                                      np.arange(triangles.size//3).reshape(-1,3).tolist(),all_triangles=True,epsilon=1e-7)
        self.maximum_ray=max(2.,float(np.linalg.norm(np.ptp(triangles.reshape(-1,3),axis=0))*4))

    def nearest(self,point):
        location,normal,face,distance=self.tree.find_nearest(Vector(point))
        contract.require(face is not None,'No nearest actual triangle');return float(distance),int(face),np.asarray(location)

    def state(self,point,distance):
        if distance<=CONTACT: return 'contact',[-1]*len(RAYS)
        if not self.closed: return 'unsupported-open-volume',[-1]*len(RAYS)
        counts=[]
        for direction in RAYS:
            origin=np.asarray(point);travel=0.;hits=[]
            for step in range(128):
                location,_,face,dist=self.tree.ray_cast(Vector(origin),Vector(direction),self.maximum_ray-travel)
                if face is None: break
                travel+=float(dist);hits.append(travel);travel+=CONTACT
                if travel>=self.maximum_ray: break
                origin=np.asarray(point)+travel*direction
            else: raise RuntimeError('Unbounded repeated ray crossings')
            counts.append(distinct_ray_hits(hits))
        return parity_consensus(counts),counts


def exact_overlap(first,second,face_ids,archive,prefix):
    selected=first.triangles[face_ids];tree=Surface(selected,False).tree
    candidates=tree.overlap(second.tree)
    contract.require(len(candidates)<=75000,'Intersection candidate bound exceeded; explicit smaller regions required')
    rows=[];segments=[]
    for region_face,adjacent_face in candidates:
        relation=triangle_relation(selected[region_face],second.triangles[adjacent_face])
        if relation is None: continue
        row={'subjectFace':int(face_ids[region_face]),'adjacentFace':int(adjacent_face),'kind':relation['kind'],
             'intersectionLengthMetres':relation['length'],'coplanarAreaSquareMetres':relation['area']}
        rows.append(row)
        if relation['kind'] in ('segment','point'): segments.append(relation['points'])
    segment_rows=np.asarray(segments).reshape(-1,2,3)
    archive[prefix+'_intersectionSegments']=segment_rows
    archive[prefix+'_intersectionFacePairs']=np.asarray([[row['subjectFace'],row['adjacentFace']] for row in rows],dtype='i8').reshape(-1,2)
    distinct={}
    for segment in segment_rows:
        key=tuple(sorted(tuple(np.rint(point/1e-6).astype('i8')) for point in segment))
        distinct[key]=float(np.linalg.norm(segment[1]-segment[0]))
    return {'bvhBoxCandidatePairs':len(candidates),'actualTriangleContactPairs':len(rows),
            'segmentPairs':sum(row['kind']=='segment' for row in rows),'pointPairs':sum(row['kind']=='point' for row in rows),
            'coplanarPairs':sum(row['kind']=='coplanar' for row in rows),
            'distinctSegmentEndpointToleranceMetres':1e-6,'distinctSegmentLengthSumMetres':sum(distinct.values()),
            'coplanarAreaPairSumSquareMetres':sum(row['coplanarAreaSquareMetres'] for row in rows),
            'actualContactFaces':sorted({row['subjectFace'] for row in rows}),
            'meaning':'Actual pairwise surface intersection; segment sums do not measure penetration volume or required repair displacement.'}


def exposure(first,second,face_ids,archive,prefix,views,directed):
    triangles=first.triangles[face_ids];cross=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    areas=np.linalg.norm(cross,axis=1)/2;points=np.einsum('bc,tci->tbi',SAMPLES,triangles).reshape(-1,3)
    weights=np.repeat(areas/len(SAMPLES),len(SAMPLES));states=[];distances=[];votes=[];nearest_faces=[]
    visible={name:[] for name in views};depths={name:[] for name in directed}
    for point in points:
        distance,face,_=second.nearest(point);state,counts=second.state(point,distance)
        states.append(state);distances.append(distance);votes.append(counts);nearest_faces.append(face)
        for name,direction in views.items():
            origin=point+direction*3.;self_hit,_,self_face,self_distance=first.tree.ray_cast(Vector(origin),Vector(-direction),3.1)
            _,_,other_face,other_distance=second.tree.ray_cast(Vector(origin),Vector(-direction),3.1)
            self_visible=self_face is not None and abs(self_distance-3.)<=2e-5
            visible[name].append(self_visible and (other_face is None or other_distance>=3.-CONTACT))
        for name,direction in directed.items():
            if state!='outside': depths[name].append(np.nan);continue
            _,_,other_face,other_distance=second.tree.ray_cast(Vector(point+CONTACT*direction),Vector(direction),.20)
            depths[name].append(float(other_distance)+CONTACT if other_face is not None else np.nan)
    state_rows=np.asarray(states);distance_rows=np.asarray(distances)
    codes={'inside':1,'outside':2,'contact':3,'ambiguous':4,'unsupported-open-volume':5}
    archive[prefix+'_faceIds']=face_ids;archive[prefix+'_samplePoints']=points;archive[prefix+'_sampleWeights']=weights
    archive[prefix+'_sampleStates']=np.asarray([codes[state] for state in states],dtype='u1')
    archive[prefix+'_rayCrossings']=np.asarray(votes,dtype='i4');archive[prefix+'_nearestDistances']=distance_rows
    archive[prefix+'_nearestFaces']=np.asarray(nearest_faces,dtype='i8')
    categories={state:{'samples':int(np.count_nonzero(state_rows==state)),
                        'sampleWeightedAreaSquareMetres':float(weights[state_rows==state].sum())} for state in codes}
    view_rows={}
    for name,mask in visible.items():
        mask=np.asarray(mask);archive[prefix+'_visible_'+name]=mask
        view_rows[name]={'geometricallyUnoccludedSamples':int(mask.sum()),'sampleWeightedAreaSquareMetres':float(weights[mask].sum()),
                         'outsideAndUnoccludedSamples':int(np.count_nonzero(mask&(state_rows=='outside'))),
                         'outsideAndUnoccludedAreaSquareMetres':float(weights[mask&(state_rows=='outside')].sum())}
    direction_rows={}
    for name,values in depths.items():
        values=np.asarray(values);archive[prefix+'_directedHit_'+name]=values;finite=np.isfinite(values)
        direction_rows[name]={'outsideSampleRays':categories['outside']['samples'],'surfaceHitsWithin200mm':int(finite.sum()),
                              'hitDistanceMetresRange':[float(values[finite].min()),float(values[finite].max())] if finite.any() else None,
                              'misses':int(np.count_nonzero((state_rows=='outside')&~finite)),
                              'meaning':'Directional distance to actual adjacent triangles; finite hits alone do not authorize moving/removing protected vertices.'}
    return {'faces':len(face_ids),'actualAreaSquareMetres':float(areas.sum()),'samplesPerFace':len(SAMPLES),'categories':categories,
            'nearestActualTriangleDistancesMetres':{'minimum':float(distance_rows.min()),'median':float(np.median(distance_rows)),
                                                     'p95':float(np.percentile(distance_rows,95)),'maximum':float(distance_rows.max())},
            'surfaceExposureViews':view_rows,'directedSurfaceHits':direction_rows,
            'meaning':'Area coverage is quadrature over actual triangle interiors, not exact clipped overlap area. Volume classification requires closed, consistent adjacent geometry.'}


def rim(first,second,vertices,edges,frame,archive,prefix):
    values=[];lengths=[]
    for start,end in edges:
        a,b=world(vertices[[start,end]],frame);length=np.linalg.norm(b-a)
        for fraction in (np.arange(8)+.5)/8: values.append(a+(b-a)*fraction);lengths.append(length/8)
    states=[];distances=[]
    for point in values:
        distance,_,_=second.nearest(point);state,_=second.state(point,distance);states.append(state);distances.append(distance)
    archive[prefix+'_rimPoints']=np.asarray(values);archive[prefix+'_rimDistance']=np.asarray(distances)
    return {'closedMeshTransitionRingNotOpenBoundary':True,'localVertexEdges':edges.tolist(),'lengthMetres':float(sum(lengths)),
            'samples':len(values),'categories':{name:{'samples':states.count(name),'sampleWeightedLengthMetres':float(sum(length for length,state in zip(lengths,states) if state==name))}
                                               for name in ['inside','outside','contact','ambiguous','unsupported-open-volume']},
            'nearestActualTriangleDistanceMetresRange':[min(distances),max(distances)]}


def cap_ring(triangles,upper,expected_faces=4):
    vertices,inverse=np.unique(triangles.reshape(-1,3),axis=0,return_inverse=True);faces=inverse.reshape(-1,3)
    apex=int(np.argmax(vertices[:,2]) if upper else np.argmin(vertices[:,2]));cap=np.flatnonzero((faces==apex).any(1))
    edges=faces[cap][:,[[0,1],[1,2],[2,0]]].reshape(-1,2);edges=np.sort(edges,axis=1)
    unique,counts=np.unique(edges,axis=0,return_counts=True);ring=unique[counts==1]
    contract.require(len(cap)==expected_faces and len(ring)==expected_faces,'Frozen stock neck apex cap/ring topology differs')
    return cap,vertices,ring


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,help='Legacy Troll v6 checkpoint base')
    parser.add_argument('--config',type=Path,help='Target-aware pinned geometry, stock parts, poses and measured connector regions')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);output=args.output.resolve()
    contract.require(bool(args.base) != bool(args.config),'Choose the legacy base or explicit target connector config')
    contract.require(not output.exists(),'Fresh immutable surface audit required')
    if args.config:
        config,target_path,target,source_paths,stock_paths,pose_sources,regions,pins=load_config(args.config)
        legacy=False
    else:
        base=args.base.resolve();legacy=True;config={}
        target_path=base/'rig-v6/target-contract.json';target=contract.load(target_path);pins={str(target_path):contract.sha(target_path)}
        source_paths={'chest':base/'repairs/chest-v6-working-forward-exterior-v2/geometry.json','bicepl':base/'fits/upperarm-v1-fit-v2/left/geometry.json',
                      'bicepr':base/'fits/upperarm-v1-fit-v2/right/geometry.json'}
        stock_paths={part:base/'diagnostic-working-rig-v6-v1/ascii'/('pmg0_'+part+'001.mdl') for part in ['head','neck']}
        pose_sources=[('pause2',base/'pilot-pause2-quarter-forward-v2/comparison.json'),('conjure1',base/'pilot-conjure1-quarter-forward-v2/comparison.json')]
        regions={'neckChestSurface':{'absoluteXMaximum':.10,'bindZMinimum':1.63},
                 'shoulderTerminalCaps':{side:{'lateralMinimum':.210,'bindZInterval':[1.43,1.68],'outwardNormalMinimumDot':.8} for side in ['left','right']},
                 'upperArmProximalCaps':{'axialIntervalMetres':[-.08,.015],'oppositeShaftNormalMinimumDot':.35},'neckCapFaces':4}
    parts={};receipts={};topologies={}
    for part,relative in source_paths.items():
        path=Path(relative).resolve();receipt=json.loads(path.read_text());contract.verify_binding(receipt,target_path,target,'working')
        contract.require(receipt['part']==part and receipt['statureApplications']==0,'Explicit unscaled working part required')
        candidate=Path(receipt['candidate']);contract.require(contract.sha(candidate)==receipt['candidateSha256'],'Candidate hash differs')
        doc,binary=read_glb(candidate);corners=raw_corners(doc,binary)[0];vertices,faces,_=mesh_arrays(doc,binary)
        parts[part]=corners;receipts[part]=receipt;topologies[part]=topology(vertices,faces)
        pins[str(path)]=contract.sha(path);pins[str(candidate)]=contract.sha(candidate)
    for part in ['neck','head']:
        path=stock_paths[part].resolve();stock_paths[part]=path;parts[part]=ascii_mesh(path)
        topologies[part]=topology(parts[part].reshape(-1,3),np.arange(parts[part].size//3).reshape(-1,3));pins[str(path)]=contract.sha(path)
    closed={part:all(row[key]==0 for key in ['boundaryEdges','nonmanifoldEdges','inconsistentManifoldEdgeWindings','nonmanifoldVertexLinks'])
            for part,row in topologies.items()}
    frames={'bind':{part:contract.frame(target,contract.PART_JOINTS[part],'working') for part in parts}}
    pose_rows=[]
    for label,path in pose_sources:
        path=Path(path).resolve();pose=json.loads(path.read_text());specimens=[row for row in pose['specimens'] if row.get('target')]
        contract.require(len(specimens)==1,'One declared target specimen per connector pose required');specimen=specimens[0]
        verify_pose(specimen,target_path,target,receipts,stock_paths,pins)
        frames[label]={part:np.asarray(specimen['jointWorldMatrices'][contract.PART_JOINTS[part]]) for part in parts}
        pins[str(path)]=contract.sha(path);pose_rows.append({'state':label,'clip':specimen['clip'],'time':specimen['time'],'comparison':str(path),'comparisonSha256':pins[str(path)]})
    bind={part:world(points,frames['bind'][part]) for part,points in parts.items()};zones={}
    lower,neck_vertices,lower_ring=cap_ring(parts['neck'],False,regions['neckCapFaces']);upper,_,upper_ring=cap_ring(parts['neck'],True,regions['neckCapFaces'])
    zones['neck_lower_cap']=('neck','chest',lower);zones['neck_upper_cap']=('neck','head',upper)
    chest=bind['chest'];cross=np.cross(chest[:,1]-chest[:,0],chest[:,2]-chest[:,0]);normal=cross/np.linalg.norm(cross,axis=1)[:,None]
    chest_center=chest.mean(1);neck_region=regions['neckChestSurface']
    zones['chest_neck_upper_surface']=('chest','neck',np.flatnonzero((abs(chest_center[:,0])<=neck_region['absoluteXMaximum'])&(chest_center[:,2]>=neck_region['bindZMinimum'])))
    contract.require(len(zones['chest_neck_upper_surface'][2])>0,'No measured neck/chest surface region')
    classification={}
    for side,sign,part,elbow in [('left',-1,'bicepl','lforearm_g'),('right',1,'bicepr','rforearm_g')]:
        region=regions['shoulderTerminalCaps'][side];z_min,z_max=region['bindZInterval'];normal_dot=region['outwardNormalMinimumDot']
        limit=max(region['lateralMinimum'],float(np.max(chest[:,:,0]*sign)-.015)) if legacy else region['lateralMinimum']
        cap=np.flatnonzero(np.all(chest[:,:,0]*sign>=limit,axis=1)&np.all((chest[:,:,2]>=z_min)&(chest[:,:,2]<=z_max),axis=1)&(normal[:,0]*sign>=normal_dot))
        contract.require(len(cap)>0,'No fixed terminal chest cap region')
        zones[side+'_chest_terminal_cap']=('chest',part,cap)
        shoulder=frames['bind'][part][:3,3];axis=contract.frame(target,elbow,'working')[:3,3]-shoulder;axis/=np.linalg.norm(axis)
        arm=bind[part];arm_center=arm.mean(1);arm_cross=np.cross(arm[:,1]-arm[:,0],arm[:,2]-arm[:,0]);arm_normal=arm_cross/np.linalg.norm(arm_cross,axis=1)[:,None]
        axial=(arm_center-shoulder)@axis
        proximal_region=regions['upperArmProximalCaps'];a_min,a_max=proximal_region['axialIntervalMetres'];opposite_dot=proximal_region['oppositeShaftNormalMinimumDot']
        proximal=np.flatnonzero((axial>=a_min)&(axial<=a_max)&(arm_normal@axis<=-opposite_dot))
        contract.require(len(proximal)>0,'No arm proximal cap measurement region')
        zones[side+'_arm_proximal_cap']=(part,'chest',proximal)
        classification[side]={'chestTerminalMinimumLateralAbsX':limit,'chestNormalOutwardDotMinimum':normal_dot,'chestBindZInterval':[z_min,z_max],
                              'armAxialIntervalMetres':[a_min,a_max],'armOppositeShaftNormalMinimumDot':opposite_dot,'armBindShaftAxis':axis.tolist()}
    archive={};rows=[]
    views={'front':np.asarray([0,1,0.]),'left':np.asarray([-1,0,0.]),'right':np.asarray([1,0,0.])}
    for state,state_frames in frames.items():
        surfaces={part:Surface(world(points,state_frames[part]),closed[part]) for part,points in parts.items()}
        for zone,(subject,adjacent,ids) in zones.items():
            print(json.dumps({'phase':'connector-zone','state':state,'zone':zone,'faces':len(ids)}),flush=True)
            key=state+'_'+zone;directed={}
            if '_chest_terminal_cap' in zone:
                sign=-1 if zone.startswith('left') else 1
                relative=state_frames['chest'][:3,:3]@frames['bind']['chest'][:3,:3].T
                directed={'inwardLateral':relative@np.asarray([-sign,0,0.]),'forward':relative@np.asarray([0,1,0.])}
            row={'state':state,'zone':zone,'subject':subject,'adjacent':adjacent,
                 'surfaceIntersections':exact_overlap(surfaces[subject],surfaces[adjacent],ids,archive,key),
                 'surfaceCoverage':exposure(surfaces[subject],surfaces[adjacent],ids,archive,key,views,directed)}
            if zone=='neck_lower_cap':row['rim']=rim(surfaces['neck'],surfaces['chest'],neck_vertices,lower_ring,state_frames['neck'],archive,key)
            if zone=='neck_upper_cap':row['rim']=rim(surfaces['neck'],surfaces['head'],neck_vertices,upper_ring,state_frames['neck'],archive,key)
            rows.append(row)
    for path,pin in pins.items():contract.require(contract.sha(path)==pin,'Frozen geometry/pose input changed during read-only audit')
    output.mkdir(parents=True);helpers=output/'helper-snapshots';helpers.mkdir()
    for name in ['audit_target_connector_surfaces.py','connector_audit_inputs.py','connector_surface_math.py','conservative_face_selection.py','audit_geometry.py','place_purposebuilt_pelvis.py','retarget.py','target_contract.py']:
        copied=helpers/name;shutil.copyfile(Path(__file__).with_name(name),copied);pins[str(copied)]=contract.sha(copied)
    data=output/'surface-samples.npz';np.savez_compressed(data,**archive);pins[str(data)]=contract.sha(data)
    report={'schemaVersion':2,'kind':'target-connector-actual-surface-audit','createdUtc':datetime.now(timezone.utc).isoformat(),
            'target':contract.binding(target_path,target,'working'),'statureApplications':0,'poses':pose_rows,
            'configuration':{'path':str(args.config.resolve()),'sha256':contract.sha(args.config)} if args.config else None,
            'partTopologies':topologies,'closedVolumeClassificationAvailable':closed,'classificationZones':classification,
            'neckTransitionRingPolicy':str(regions['neckCapFaces'])+' cap faces incident to each extreme-Z stock neck apex; the transition ring is not an open boundary.',
            'sampleBarycentricWeights':SAMPLES.tolist(),'rayDirections':RAYS.tolist(),'surfaceContactToleranceMetres':CONTACT,
            'measurements':rows,'sampleArchive':{'path':str(data),'sha256':contract.sha(data)},
            'repairRecommendations':{'selected':False,'protectedGeometry':config.get('protectedGeometry',['Current measured stock head/neck','Complete fitted candidate parts',
                'Original material/UV/normal/tangent rows']),
                'policy':'Choose the smallest demonstrated connector region. Exact directional ray hits quantify candidate displacements; misses disprove a simple move in that direction for those samples. Do not infer a trim/remesh from AABB or unsigned nearest distances.',
                'pending':'Root review of actual holes/disconnections/unintended exposed shoulder cap face IDs and intersections; no cosmetic neck-rim change or descendant produced.',
                'userPreference':config.get('reviewedGeometryPreference','No aesthetic acceptance is inherited by this measurement receipt.')},
            'frozenInputs':pins,'geometryOrMaterialsChanged':False,'selectionOrLedgerChanged':False,
            'rigMode':contract.rig_mode(target),'rigValidated':contract.rig_ready(target),'rigPilotAccepted':target['rig'].get('pilotAccepted',False),'productionAccepted':False,'clientAccepted':False,
            'limitations':['Actual triangle intersection curves are measured only within declared connector regions.',
                'Surface area coverage and ring length coverage use finite quadrature, not exact clipped area integration.',
                'Volume parity is unavailable for open/inconsistent meshes; ambiguous rays remain unresolved.',
                'BVH uses Blender float precision for candidates/rays; narrow-phase triangles use double precision and1e-8m tolerance.',
                'Only declared bind/comparison states are sampled; no new render or actual client evidence.',
                'Color/palette differences are not measured or used as geometry evidence.',
                'Stock dangly meshes use their declared static bind surfaces; secondary simulation is not sampled.']}
    result=output/'connector-surface-audit.json';result.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'receipt':str(result),'sha256':contract.sha(result)}),flush=True)


if __name__=='__main__':main()
