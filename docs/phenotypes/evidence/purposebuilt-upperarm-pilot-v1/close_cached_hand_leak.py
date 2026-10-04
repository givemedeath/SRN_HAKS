"""Bounded additive512 diagnostic/repair operation; original grids immutable."""
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
OUT=INPUT/'localized-512-closure-v1'
FORE=ROOT/'output/phenotypes/purposebuilt-forearm-pilot-v1/hand-shell-diagnosis-v1'
HAND=ROOT/'output/phenotypes/purposebuilt-hand-pilot-v1'
spec=importlib.util.spec_from_file_location('cached_diagnosis',PILOT/'analyze_cached_hand_leak.py')
support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise RuntimeError(message)


def packed_region(data,name,shape):
    return np.unpackbits(data[name],bitorder='big')[:int(np.prod(shape))].reshape(shape).astype(bool)


def flood(surface):
    labels,n=support.components(~surface)
    border=np.unique(np.concatenate([labels[0].ravel(),labels[-1].ravel(),labels[:,0].ravel(),labels[:,-1].ravel(),labels[:,:,0].ravel(),labels[:,:,-1].ravel()]))
    border=border[border!=0]
    outside=np.isin(labels,border)
    require(not np.any(outside&surface),'Flood returned occupied exterior')
    return outside,{'emptyComponents':n,'exteriorComponents':int(len(border)),'enclosedEmptyComponents':n-len(border)}


def support_distances(points,source):
    """Exact finite triangle distance by projection and three clamped edges."""
    import sys
    sys.path.insert(0,str(ROOT/'tools/phenotypes'))
    from inspect_generated_part_topology import load
    p,faces,_=load(source)
    triangles=p[faces].astype(float)
    a,b,c=triangles[:,0],triangles[:,1],triangles[:,2]
    u=b-a;v=c-a
    normal=np.cross(u,v)
    nn=np.einsum('ij,ij->i',normal,normal)
    uu=np.einsum('ij,ij->i',u,u);vv=np.einsum('ij,ij->i',v,v);uv=np.einsum('ij,ij->i',u,v)
    determinant=uu*vv-uv*uv
    result=[]
    for point in points:
        w=point-a
        signed=np.einsum('ij,ij->i',w,normal)
        projection=point-normal*(signed/np.maximum(nn,1e-30))[:,None]
        delta=projection-a
        du=np.einsum('ij,ij->i',delta,u);dv=np.einsum('ij,ij->i',delta,v)
        x=(vv*du-uv*dv)/np.maximum(determinant,1e-30)
        y=(uu*dv-uv*du)/np.maximum(determinant,1e-30)
        good=(x>=0)&(y>=0)&(x+y<=1)&(nn>1e-25)
        d2=np.where(good,signed*signed/np.maximum(nn,1e-30),np.inf)
        for aa,bb in [(a,b),(b,c),(c,a)]:
            edge=bb-aa
            ll=np.einsum('ij,ij->i',edge,edge)
            t=np.clip(np.einsum('ij,ij->i',point-aa,edge)/np.maximum(ll,1e-30),0,1)
            q=aa+t[:,None]*edge
            dd=np.einsum('ij,ij->i',point-q,point-q)
            d2=np.minimum(d2,dd)
        index=int(d2.argmin())
        result.append({'distanceSourceCoordinates':float(np.sqrt(d2[index])), 'nearestSourceFace':index})
    return result


def main():
    begun=time.perf_counter()
    require(not OUT.exists(),'Fresh localized repair destination required')
    fine_path=FORE/'conservative-fill-diagnostic-512-v2/diagnostic-grid.npz'
    coarse_path=FORE/'conservative-fill-diagnostic-384-v1/diagnostic-grid.npz'
    diagnosis_path=INPUT/'diagnosis.json'
    regions_path=INPUT/'diagnostic-regions.npz'
    grip_path=HAND/'grip-pocket-rays-v1/measurement.json'
    source=HAND/'comfy-v6/generated/shape-master_00001.glb'
    inputs={str(p.resolve()):sha(p) for p in [fine_path,coarse_path,diagnosis_path,regions_path,grip_path,source,Path(__file__),PILOT/'analyze_cached_hand_leak.py']}
    diagnosis=json.loads(diagnosis_path.read_text())
    for name,pin in diagnosis['frozenInputs'].items():require(sha(name)==pin,'Parent diagnostic cache/source changed')
    g=support.grid(fine_path)
    shape=g['shape'];origin=g['origin'];pitch=g['pitch']
    with np.load(regions_path) as data:
        require(tuple(data['shape'])==shape and np.array_equal(data['origin'],origin) and float(data['pitch'])==pitch,'Diagnostic region transform differs')
        body=packed_region(data,'bodyThickPacked',shape)
        exterior=packed_region(data,'exteriorThickPacked',shape)
    grip=json.loads(grip_path.read_text())
    clear=[r['rayOriginRawGltf'] for r in grip['records'] if r['entireAxialLineClear']]
    protected_lines=[]
    for point in clear:
        idx=np.floor((np.array(point)-origin)/pitch).astype(int)
        protected_lines.append((idx[1],idx[2]))
    # Protect two-cell Y/Z guard for every exact source-clear X-line, even the
    # existing marginal raster-contact line. No extra coverage is allowed there.
    protected=np.zeros(shape[1:],bool)
    for y,z in protected_lines:
        protected[max(0,y-2):min(shape[1],y+3),max(0,z-2):min(shape[2],z+3)]=True
    patch=np.zeros(shape,bool)
    iterations=[]
    outside=g['outside'].copy()
    for operation in range(10):
        require(np.any(body&outside),'Unexpected already-closed body before operation')
        connector=outside&~body&~exterior
        reached=support.six_dilation(body)&connector
        frontier=reached.copy()
        boundary=support.six_dilation(exterior)&connector
        selected=None
        for depth in range(1,40):
            meet=frontier&boundary
            if np.any(meet):
                selected=meet
                break
            frontier=support.six_dilation(frontier)&connector&~reached
            reached|=frontier
            if not np.any(frontier):break
        require(selected is not None,'No bounded thin-channel cross-section found')
        require(not np.any(selected[:,protected]),'Closure would enter a protected exact grip-line guard')
        indices=np.where(selected)
        bounds=support.world_bounds(indices,origin,pitch)
        count=int(selected.sum())
        require(count<=256,'Channel cross-section is not microscopic; inspect before broader edit')
        extent=np.array(bounds[1])-bounds[0]
        require(extent.max()<=pitch*16,'Channel cross-section lacks a tightly localized bound')
        patch|=selected
        outside,statistics=flood(g['surface']|patch)
        leaked=int(np.count_nonzero(outside&body))
        iterations.append({'operation':operation+1,'geodesicDepthFromBodyBoundary':depth,
                           'addedSurfaceCells':count,'boundsRawGltf':bounds,'extentRawGltf':extent.tolist(),
                           'bodyCoreStillExteriorCells':leaked,'flood':statistics})
        print(json.dumps({'phase':'localized-cut',**iterations[-1],'elapsed':time.perf_counter()-begun}),flush=True)
        if leaked==0:break
    require(not np.any(body&outside),'Localized operations did not isolate the intended body core')
    initial_count=int(patch.sum())
    # Inclusion-minimal proof: remove each candidate voxel only when the full
    # original six-connected flood still seals the body. This is not a claim of
    # globally minimum cardinality over arbitrary geometric repairs.
    deletions=[]
    indispensable=[]
    for index in np.argwhere(patch):
        key=tuple(index)
        patch[key]=False
        trial,statistics=flood(g['surface']|patch)
        if np.any(trial&body):
            patch[key]=True
            indispensable.append(index.tolist())
        else:
            outside=trial
            deletions.append(index.tolist())
    outside,statistics=flood(g['surface']|patch)
    require(not np.any(body&outside),'Final minimal patch leaks')
    patch_indices=np.argwhere(patch)
    centres=origin+(patch_indices+.5)*pitch
    nearest=support_distances(centres,source)
    require(len(nearest)==len(patch_indices),'Incomplete exact source support')
    distance=np.array([r['distanceSourceCoordinates'] for r in nearest])
    require(distance.max()<=np.sqrt(3)/384,'Patch exceeds coarse conservative source-support envelope')
    # Every original occupied voxel survives; additions must be empty before.
    require(not np.any(g['surface']&patch),'Patch replaces existing source raster cells')
    final_surface=g['surface']|patch
    final_filled=~outside
    clear_records=[]
    for point,(y,z) in zip(clear,protected_lines):
        before=g['outside'][:,y,z];after=outside[:,y,z]
        require(np.array_equal(before,after),'Closure changes an exact source-clear line occupancy')
        require(not np.any(patch[:,max(0,y-2):y+3,max(0,z-2):z+3]),'Patch reaches grip guard')
        clear_records.append({'originRawGltf':point,'baselineVoxelWholeLineClear':bool(before.all()),
                              'finalVoxelWholeLineClear':bool(after.all()),'occupancyExactBaseline':True})
    core_records=[]
    for point in [[0,-.175,.05],[0,-.19,.05],[0,-.175,.035],[0,-.16,.035]]:
        value,idx=support.at_point(outside,point,origin,pitch)
        require(bool(value) and np.all(outside[:,idx[1],idx[2]]),'Central grip witness closed')
        core_records.append({'pointRawGltf':point,'axisExterior':True,'wholeLineClear':True})
    c=support.grid(coarse_path)
    axes=[]
    for axis in range(3):
        coords=origin[axis]+(np.arange(shape[axis])+.5)*pitch
        axes.append(np.floor((coords-c['origin'][axis])/c['pitch']).astype(int))
    coarse_filled=(~c['outside'])[np.ix_(*axes)]
    coarse_surface=c['surface'][np.ix_(*axes)]
    patch_rows=[{'index':idx.tolist(),'centreRawGltf':q.tolist(),**n,
                 'coarseSurfaceCell':bool(coarse_surface[tuple(idx)]),'coarseFilledCell':bool(coarse_filled[tuple(idx)])}
                for idx,q,n in zip(patch_indices,centres,nearest)]
    indices=np.where(patch)
    bounds=support.world_bounds(indices,origin,pitch)
    comparison={'filledCells':int(final_filled.sum()),'filledVolume':float(final_filled.sum()*pitch**3),
                'beforeFilledCells':int(np.count_nonzero(~g['outside'])),
                'finalFineCentresOutsideCoarseFilled':int(np.count_nonzero(final_filled&~coarse_filled)),
                'coarseFilledFineCentresNotFinalFilled':int(np.count_nonzero(coarse_filled&~final_filled)),
                'largestBodyCoreExteriorCells':int(np.count_nonzero(outside&body)),
                'surfaceCellAdditions':int(patch.sum()),'coarseSurfaceMappedPatchCells':int(np.count_nonzero(patch&coarse_surface)),
                'coarseFilledMappedPatchCells':int(np.count_nonzero(patch&coarse_filled))}
    OUT.mkdir()
    np.savez_compressed(OUT/'patched-grid.npz',shape=np.array(shape),origin=origin,pitch=pitch,
                        surfacePacked=np.packbits(final_surface.ravel(),bitorder='big'),
                        outsidePacked=np.packbits(outside.ravel(),bitorder='big'))
    np.savez_compressed(OUT/'patch-cells.npz',indices=patch_indices,centres=centres,pitch=pitch,origin=origin,shape=np.array(shape))
    shutil.copy2(__file__,OUT/'executed-closure.py')
    for path,pin in inputs.items():require(sha(path)==pin,'Changed immutable input during localized repair')
    report={'schemaVersion':1,'operation':'Localized additive SAT512 microleak cross-section closure followed by exact six-connected exterior flood.',
            'sourceAdopted':False,'meshCreated':False,'originalGridsMutated':False,'sourceGeometryMutated':False,
            'gpuUsed':False,'clientControlled':False,'frozenInputs':inputs,
            'sameGridTransform':True,'originalSurfaceCellsExact':True,'patchCellsPreviouslyEmpty':True,
            'iterations':iterations,'initialCandidateCells':initial_count,'removedRedundantCells':deletions,
            'finalPatchCells':int(patch.sum()),'inclusionMinimalProof':'Each remaining voxel is indispensable under one-cell removal with every other selected voxel retained; no globally optimal cardinality claim.',
            'indispensableIndices':indispensable,'patchBoundsRawGltf':bounds,
            'patchExtentRawGltf':(np.array(bounds[1])-bounds[0]).tolist(),
            'maximumPatchCentreSourceDistance':float(distance.max()),'coarseConservativeSupportLimit':float(np.sqrt(3)/384),
            'exactNearestSourceTriangleRecords':patch_rows,'filledComparisonToCoarse384':comparison,'finalFlood':statistics,
            'all22ClearLineOccupanciesExactBeforeAfter':True,'clearLineRecords':clear_records,'coreGripRecords':core_records,
            'sourceGridsBaselineMarginalLineLimitation':'Both original SAT caches contact one exact source-clear near-edge line; final additive repair preserves that baseline occupancy. Final continuous extracted-surface line clearance still requires independent proof.',
            'grid':{'path':str(OUT/'patched-grid.npz'),'sha256':sha(OUT/'patched-grid.npz')},
            'elapsedSeconds':time.perf_counter()-begun,
            'remainingGates':['Root extraction and bounded simplification; actual serialized closed manifold/vertex links/crossings and orientation.',
                              'Independent actual source-envelope distances, anatomy/grip clear rays and ordinary wrist-cap shape.',
                              'UV/material/normal transfer, stock uniform fit/placement, bounded hidden taper, detached mirror and native/cumulative/client checks.']}
    (OUT/'closure.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'phase':'completed','finalPatchCells':int(patch.sum()),'patchBounds':bounds,
                      'filled':comparison,'maximumSourceSupportDistance':float(distance.max()),
                      'output':str(OUT/'closure.json'),'sha256':sha(OUT/'closure.json'),'elapsed':time.perf_counter()-begun}),flush=True)


if __name__=='__main__':main()
