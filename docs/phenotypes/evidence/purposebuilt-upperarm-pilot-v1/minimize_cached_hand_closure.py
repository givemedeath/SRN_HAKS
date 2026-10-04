"""Finite local node min-cut, exact global flood/witness checks, fresh grid only."""
from collections import deque
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import time

import numpy as np

PILOT=Path(__file__).resolve().parent
ROOT=PILOT.parents[2]
INPUT=PILOT/'hand-leak-independent-v1'
PARENT=INPUT/'localized-512-closure-v1'
OUT=INPUT/'localized-512-mincut-v2'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


base=module('closure',PILOT/'close_cached_hand_leak.py')
support=base.support
sha=base.sha
require=base.require


class Dinic:
    def __init__(self,n):self.graph=[[] for _ in range(n)]

    def edge(self,u,v,capacity):
        a=[v,len(self.graph[v]),int(capacity)];b=[u,len(self.graph[u]),0]
        self.graph[u].append(a);self.graph[v].append(b)

    def flow(self,source,sink):
        total=0
        while True:
            levels=[-1]*len(self.graph);levels[source]=0;queue=deque([source])
            while queue:
                u=queue.popleft()
                for v,_,cap in self.graph[u]:
                    if cap and levels[v]<0:levels[v]=levels[u]+1;queue.append(v)
            if levels[sink]<0:break
            cursor=[0]*len(self.graph)
            def send(u,value):
                if u==sink:return value
                while cursor[u]<len(self.graph[u]):
                    edge=self.graph[u][cursor[u]];v,reverse,capacity=edge
                    if capacity and levels[v]==levels[u]+1:
                        pushed=send(v,min(value,capacity))
                        if pushed:
                            edge[2]-=pushed;self.graph[v][reverse][2]+=pushed
                            return pushed
                    cursor[u]+=1
                return 0
            while True:
                amount=send(source,10**30)
                if not amount:break
                total+=amount
        reachable=np.zeros(len(self.graph),bool);reachable[source]=True;queue=deque([source])
        while queue:
            u=queue.popleft()
            for v,_,capacity in self.graph[u]:
                if capacity and not reachable[v]:reachable[v]=True;queue.append(v)
        return total,reachable


def self_test():
    graph=Dinic(4);graph.edge(0,1,4);graph.edge(0,2,2);graph.edge(1,3,2);graph.edge(2,3,3);graph.edge(1,2,1)
    flow,reached=graph.flow(0,3)
    require(flow==5 and reached[0] and not reached[3],'Independent known-flow fixture failed')


def main():
    begun=time.perf_counter();self_test()
    require(not OUT.exists(),'Fresh local mincut required')
    parent_path=PARENT/'closure.json';parent=json.loads(parent_path.read_text())
    require(sha(parent['grid']['path'])==parent['grid']['sha256'],'Parent sealed grid changed')
    for path,pin in parent['frozenInputs'].items():require(sha(path)==pin,'Parent actual input/helper changed')
    fine_path=base.FORE/'conservative-fill-diagnostic-512-v2/diagnostic-grid.npz'
    regions_path=INPUT/'diagnostic-regions.npz'
    source=base.HAND/'comfy-v6/generated/shape-master_00001.glb'
    grip_path=base.HAND/'grip-pocket-rays-v1/measurement.json'
    pins={str(p.resolve()):sha(p) for p in [parent_path,Path(parent['grid']['path']),fine_path,regions_path,source,grip_path,
           Path(__file__),PILOT/'close_cached_hand_leak.py',PILOT/'analyze_cached_hand_leak.py']}
    g=support.grid(fine_path);sealed=support.grid(parent['grid']['path'])
    with np.load(PARENT/'patch-cells.npz') as data:old_indices=data['indices'].copy()
    with np.load(regions_path) as data:
        body=base.packed_region(data,'bodyThickPacked',g['shape'])
        exterior=base.packed_region(data,'exteriorThickPacked',g['shape'])
    lo=np.maximum(old_indices.min(axis=0)-6,0)
    hi=np.minimum(old_indices.max(axis=0)+7,np.array(g['shape']))
    region=tuple(slice(int(a),int(b)) for a,b in zip(lo,hi))
    free=g['outside'][region]
    b=body[region];e=exterior[region]
    boundary=np.zeros(free.shape,bool)
    for axis in range(3):
        s=[slice(None)]*3;s[axis]=0;boundary[tuple(s)]=True
        s[axis]=-1;boundary[tuple(s)]=True
    allowed=free&~b&~e&~boundary
    grip=json.loads(grip_path.read_text())
    clear=[r['rayOriginRawGltf'] for r in grip['records'] if r['entireAxialLineClear']]
    for point in clear:
        idx=np.floor((np.array(point)-g['origin'])/g['pitch']).astype(int)-lo
        y,z=idx[1:]
        if y+2<0 or y-2>=free.shape[1] or z+2<0 or z-2>=free.shape[2]:continue
        allowed[:,max(0,y-2):min(free.shape[1],y+3),max(0,z-2):min(free.shape[2],z+3)]=False
    candidate_local=np.argwhere(allowed)
    candidate_global=candidate_local+lo
    points=g['origin']+(candidate_global+.5)*g['pitch']
    nearest=base.support_distances(points,source)
    distances=np.array([row['distanceSourceCoordinates'] for row in nearest])
    bound=np.sqrt(3)/384
    keep=distances<=bound
    allowed[:]=False
    for idx in candidate_local[keep]:allowed[tuple(idx)]=True
    accepted_candidates=candidate_global[keep]
    accepted_distances=distances[keep]
    penalty=np.rint(accepted_distances/g['pitch']*100).astype(np.int64)
    primary_weight=int(penalty.sum())+1
    capacity=np.full(free.shape,0,np.int64)
    for idx,value in zip(candidate_local[keep],penalty):capacity[tuple(idx)]=primary_weight+int(value)
    infinity=int(capacity.sum())+1
    local_source=b|(boundary&~sealed['outside'][region])
    local_sink=e|(boundary&sealed['outside'][region])
    require(not np.any(local_source&local_sink),'ROI boundary source/sink ownership conflicts')
    require(np.any(local_source&free) and np.any(local_sink&free),'ROI must contain both sides')
    indices=np.argwhere(free)
    ids=np.full(free.shape,-1,np.int32)
    ids[tuple(indices.T)]=np.arange(len(indices))
    src=2*len(indices);dst=src+1
    graph=Dinic(dst+1)
    for ordinal,idx in enumerate(indices):
        key=tuple(idx)
        graph.edge(2*ordinal,2*ordinal+1,int(capacity[key]) if allowed[key] else infinity)
        if local_source[key]:graph.edge(src,2*ordinal,infinity)
        if local_sink[key]:graph.edge(2*ordinal+1,dst,infinity)
        for axis in range(3):
            other=idx.copy();other[axis]+=1
            if other[axis]>=free.shape[axis]:continue
            opposite=int(ids[tuple(other)])
            if opposite>=0:
                graph.edge(2*ordinal+1,2*opposite,infinity)
                graph.edge(2*opposite+1,2*ordinal,infinity)
    flow,reachable=graph.flow(src,dst)
    require(flow<infinity,'No finite permitted local cut')
    selected_ordinals=np.flatnonzero(reachable[:src:2]&~reachable[1:src:2])
    selected_local=indices[selected_ordinals]
    selected=selected_local+lo
    require(all(allowed[tuple(idx)] for idx in selected_local),'Cut includes a forbidden cell')
    require(sum(int(capacity[tuple(idx)]) for idx in selected_local)==flow,'Flow/cut dual certificate failed')
    require(len(selected)<=parent['finalPatchCells'],'Local mincut should not exceed known feasible25-cell set')
    patch=np.zeros(g['shape'],bool);patch[tuple(selected.T)]=True
    outside,statistics=base.flood(g['surface']|patch)
    require(not np.any(outside&body),'Local cut did not close actual full-domain flood')
    clear_records=[]
    for point in clear:
        _,idx=support.at_point(outside,point,g['origin'],g['pitch'])
        before=g['outside'][:,idx[1],idx[2]];after=outside[:,idx[1],idx[2]]
        require(np.array_equal(before,after),'Min-cut changes original clear-line occupancy')
        clear_records.append({'originRawGltf':point,'occupancyExactBaseline':True,'wholeLineClear':bool(after.all())})
    centre_records=base.support_distances(g['origin']+(selected+.5)*g['pitch'],source)
    bounds=support.world_bounds(np.where(patch),g['origin'],g['pitch'])
    corners=[]
    for idx in selected:
        for bits in np.ndindex((2,2,2)):corners.append(g['origin']+(idx+np.array(bits))*g['pitch'])
    corner_points=np.unique(np.array(corners),axis=0)
    corner_records=base.support_distances(corner_points,source)
    maximum_corner=max(x['distanceSourceCoordinates'] for x in corner_records)
    # Confirm inclusion-minimal under actual whole-domain connectivity as well.
    indispensable=[]
    for idx in selected:
        patch[tuple(idx)]=False
        trial,_=base.flood(g['surface']|patch)
        require(np.any(trial&body),'Min-cut selected a redundant whole-domain cell')
        patch[tuple(idx)]=True
        indispensable.append(idx.tolist())
    OUT.mkdir()
    np.savez_compressed(OUT/'patched-grid.npz',shape=np.array(g['shape']),origin=g['origin'],pitch=g['pitch'],
                        surfacePacked=np.packbits((g['surface']|patch).ravel(),bitorder='big'),
                        outsidePacked=np.packbits(outside.ravel(),bitorder='big'))
    np.savez_compressed(OUT/'patch-cells.npz',indices=selected,centres=g['origin']+(selected+.5)*g['pitch'],
                        pitch=g['pitch'],origin=g['origin'],shape=np.array(g['shape']))
    shutil.copy2(__file__,OUT/'executed-mincut.py')
    for path,pin in pins.items():require(sha(path)==pin,'Immutable parent/input changed during minimum-cut operation')
    report={'schemaVersion':1,'operation':'Finite localized weighted node cut with whole-domain six-connected flood validation.',
            'sourceAdopted':False,'meshCreated':False,'originalGridsMutated':False,'sourceGeometryMutated':False,
            'gpuUsed':False,'clientControlled':False,'frozenInputs':pins,'sameGridTransform':True,'originalSurfaceCellsExact':True,
            'roi':{'minimumIndex':lo.tolist(),'maximumIndexExclusive':hi.tolist(),
                   'boundsRawGltf':[list(g['origin']+lo*g['pitch']),list(g['origin']+hi*g['pitch'])],
                   'ownership':'All ROI boundary free cells have exact side ownership from independently globally sealed25-cell parent.'},
            'permittedCellRule':'Original free-space interstitial cells only, within exact source-centre support sqrt(3)/384 and outside all22 grip-line two-cell guards; body/exterior cores and ROI border forbidden.',
            'graph':{'freeNodes':len(indices),'splitVertices':len(graph.graph),'allowedEditCells':int(allowed.sum()),
                     'primaryCardinalityWeight':primary_weight,'secondaryCost':'round(100 * centre_source_distance / pitch)',
                     'infiniteCapacity':infinity,'maxFlow':int(flow),'selectedCutCapacity':int(flow),
                     'minimumProof':'Flow equals selected cut capacity. Since primary weight exceeds sum of all possible distance penalties, this minimizes cardinality then centre support distance in the declared fixed ROI/permitted-cell graph.'},
            'globalMinimumNotClaimed':True,'parentPatchCells':parent['finalPatchCells'],'finalPatchCells':len(selected),
            'allSelectedIndispensableInFullDomain':True,'indispensableIndices':indispensable,
            'patchBoundsRawGltf':bounds,'patchExtentRawGltf':(np.array(bounds[1])-bounds[0]).tolist(),
            'maximumPatchCentreSourceDistance':max(x['distanceSourceCoordinates'] for x in centre_records),
            'maximumPatchCornerSourceDistance':maximum_corner,
            'patchCentreSourceRecords':[{'index':idx.tolist(),**row} for idx,row in zip(selected,centre_records)],
            'patchCornerSourceRecords':[{'pointRawGltf':p.tolist(),**row} for p,row in zip(corner_points,corner_records)],
            'filledCells':int(np.count_nonzero(~outside)),'filledVolume':float(np.count_nonzero(~outside)*g['pitch']**3),
            'bodyCoreExteriorCells':int(np.count_nonzero(outside&body)),'flood':statistics,
            'all22ClearLineOccupanciesExactBaseline':True,'clearLineRecords':clear_records,
            'baselineMarginalLineLimitation':parent['sourceGridsBaselineMarginalLineLimitation'],
            'grid':{'path':str(OUT/'patched-grid.npz'),'sha256':sha(OUT/'patched-grid.npz')},
            'elapsedSeconds':time.perf_counter()-begun,
            'remainingGates':parent['remainingGates']}
    (OUT/'closure.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'phase':'completed','oldPatchCells':parent['finalPatchCells'],'newPatchCells':len(selected),
                      'maximumCentreSourceDistance':report['maximumPatchCentreSourceDistance'],
                      'maximumCornerSourceDistance':maximum_corner,'filledVolume':report['filledVolume'],
                      'output':str(OUT/'closure.json'),'sha256':sha(OUT/'closure.json'),'elapsed':time.perf_counter()-begun}),flush=True)


if __name__=='__main__':main()
