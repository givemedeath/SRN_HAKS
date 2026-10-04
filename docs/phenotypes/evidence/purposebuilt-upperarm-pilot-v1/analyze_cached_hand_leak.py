"""Read-only cached-grid leak diagnosis; no source edit or surface reconstruction."""
from pathlib import Path
import hashlib
import json
import shutil
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
PILOT = Path(__file__).resolve().parent
FORE = ROOT/'output/phenotypes/purposebuilt-forearm-pilot-v1/hand-shell-diagnosis-v1'
HAND = ROOT/'output/phenotypes/purposebuilt-hand-pilot-v1'
OUT = PILOT/'hand-leak-independent-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def six_dilation(mask):
    out=mask.copy()
    for axis in range(3):
        low=[slice(None)]*3;high=low.copy()
        low[axis]=slice(None,-1);high[axis]=slice(1,None)
        out[tuple(low)] |= mask[tuple(high)]
        out[tuple(high)] |= mask[tuple(low)]
    return out


def six_erosion(mask):
    out=mask.copy()
    for axis in range(3):
        low=[slice(None)]*3;high=low.copy()
        low[axis]=slice(None,-1);high[axis]=slice(1,None)
        out[tuple(low)] &= mask[tuple(high)]
        out[tuple(high)] &= mask[tuple(low)]
        boundary=[slice(None)]*3;boundary[axis]=0;out[tuple(boundary)]=False
        boundary[axis]=-1;out[tuple(boundary)]=False
    return out


def components(mask):
    """Exact six-connectivity: Z-run vertices with parallel union hooking.

    Adjacent run-pairs are emitted only where either Z-run ID changes, avoiding
    tens of millions of repeated cell adjacency records and external libraries.
    """
    starts=mask.copy()
    starts[:,:,1:] &= ~mask[:,:,:-1]
    ids=np.cumsum(starts.ravel(),dtype=np.int32).reshape(mask.shape)-1
    nruns=int(starts.sum())
    ids[~mask]=-1
    del starts
    if nruns==0:return np.zeros(mask.shape,np.int32),0
    aa=[];bb=[]
    for axis in [0,1]:
        lower=[slice(None)]*3;upper=lower.copy()
        lower[axis]=slice(None,-1);upper[axis]=slice(1,None)
        a=ids[tuple(lower)];b=ids[tuple(upper)]
        for row in range(0,a.shape[0],24):
            x=a[row:row+24];y=b[row:row+24]
            valid=(x>=0)&(y>=0)
            changed=valid.copy()
            changed[:,:,1:] &= ((x[:,:,1:]!=x[:,:,:-1])|(y[:,:,1:]!=y[:,:,:-1])|~valid[:,:,:-1])
            aa.append(x[changed]);bb.append(y[changed])
    a=np.concatenate(aa);b=np.concatenate(bb)
    del aa,bb
    parent=np.arange(nruns,dtype=np.int32)
    for round_index in range(80):
        while True:
            compressed=parent[parent]
            if np.array_equal(compressed,parent):break
            parent=compressed
        x=parent[a];y=parent[b]
        if np.array_equal(x,y):break
        np.minimum.at(parent,np.maximum(x,y),np.minimum(x,y))
    else:raise RuntimeError('Run-component hooking did not converge')
    component_count=int(len(np.unique(parent)))
    for row in range(0,mask.shape[0],24):
        active=mask[row:row+24]
        sub=ids[row:row+24]
        sub[active]=parent[sub[active]]+1
        sub[~active]=0
    return ids,component_count


def self_test():
    rng=np.random.default_rng(17)
    for probability in [.1,.45,.8]:
        mask=rng.random((9,10,11))<probability
        labels,_=components(mask)
        # Independent tiny scalar BFS oracle, rather than mirroring union code.
        seen=np.zeros(mask.shape,bool)
        known=[]
        for start in zip(*np.where(mask)):
            if seen[start]:continue
            stack=[start];seen[start]=True;members=[]
            while stack:
                p=stack.pop();members.append(p)
                for axis in range(3):
                    for delta in [-1,1]:
                        q=list(p);q[axis]+=delta;q=tuple(q)
                        if all(0<=q[k]<mask.shape[k] for k in range(3)) and mask[q] and not seen[q]:
                            seen[q]=True;stack.append(q)
            observed={int(labels[p]) for p in members}
            require(len(observed)==1 and 0 not in observed,'Components split a BFS oracle component')
            known.append(next(iter(observed)))
        require(len(set(known))==len(known) and np.all(labels[~mask]==0),'Components merge independent BFS components')


def grid(path):
    with np.load(path) as data:
        shape=tuple(int(x) for x in data['shape'])
        n=int(np.prod(shape))
        return {'shape':shape,'origin':data['origin'].copy(),'pitch':float(data['pitch']),
                'surface':np.unpackbits(data['surfacePacked'],bitorder='big')[:n].reshape(shape).astype(bool),
                'outside':np.unpackbits(data['outsidePacked'],bitorder='big')[:n].reshape(shape).astype(bool)}


def world_bounds(indices, origin, pitch):
    return [list(origin+np.array([x.min() for x in indices])*pitch),
            list(origin+(np.array([x.max() for x in indices])+1)*pitch)]


def at_point(array, point, origin, pitch):
    index=np.floor((np.array(point)-origin)/pitch).astype(int)
    require(np.all(index>=0) and np.all(index<array.shape),'Point outside diagnostic grid')
    return array[tuple(index)],index.tolist()


def main():
    start=time.perf_counter()
    require(not OUT.exists(),'Fresh diagnosis required')
    self_test()
    paths=[FORE/(name+'/diagnostic-grid.npz') for name in ['conservative-fill-diagnostic-384-v1','conservative-fill-diagnostic-512-v2']]
    measure_paths=[p.parent/'measurement.json' for p in paths]
    grip_path=HAND/'grip-pocket-rays-v1/measurement.json'
    clear_path=FORE/'grip-clearance-proof-v1.json'
    measures=[json.loads(p.read_text()) for p in measure_paths]
    source=Path(measures[0]['source'])
    require(measures[0]['sourceSha256']==measures[1]['sourceSha256']==sha(source), 'Cached grids use changed/different source')
    require(all(m['outsideConnectivity']==6 and m['noDilationClosingOrSmoothing'] for m in measures),'Unexpected grid construction')
    pins={str(p.resolve()):sha(p) for p in [*paths,*measure_paths,grip_path,clear_path,source,Path(__file__)]}
    c,f=[grid(p) for p in paths]
    require(all(g['surface'].shape==g['outside'].shape for g in [c,f]),'Grid shape mismatch')
    require(not any(np.any(g['surface']&g['outside']) for g in [c,f]),'Surface declared exterior')
    coarse_internal=~c['outside']&~c['surface']
    labels,nlabels=components(coarse_internal)
    counts=np.bincount(labels.ravel());counts[0]=0
    largest_id=int(counts.argmax())
    largest=labels==largest_id
    coarse_proof={'enclosedComponents':nlabels,'largestComponentCells':int(counts[largest_id]),
                  'largestComponentVolume':float(counts[largest_id]*c['pitch']**3),
                  'sourceOrigin':c['origin'].tolist(),'sourcePitch':c['pitch'],'gridShape':list(c['shape'])}
    del labels,counts,coarse_internal
    mapped_axes=[]
    for axis in range(3):
        centres=f['origin'][axis]+(np.arange(f['shape'][axis])+.5)*f['pitch']
        ix=np.floor((centres-c['origin'][axis])/c['pitch']).astype(int)
        require(np.all(ix>=0) and np.all(ix<c['shape'][axis]),'Fine grid centres outside coarse parent domain')
        mapped_axes.append(ix)
    target=largest[np.ix_(*mapped_axes)]
    coarse_surface=c['surface'][np.ix_(*mapped_axes)]
    coarse_filled=(~c['outside'])[np.ix_(*mapped_axes)]
    grip=json.loads(grip_path.read_text())
    rows=[]
    for record in grip['records']:
        if record['entireAxialLineClear']:
            point=record['rayOriginRawGltf']
            _,idx=at_point(f['outside'],point,f['origin'],f['pitch'])
            rows.append({'sourcePointRawGltf':point,'originalWholeLineClear':True,
                         'fineWholeLineClear':bool(np.all(f['outside'][:,idx[1],idx[2]])),
                         'fineSurfaceLineCells':int(np.count_nonzero(f['surface'][:,idx[1],idx[2]])),
                         'fineAxisOutside':bool(f['outside'][tuple(idx)]),
                         'fineIndex':idx})
    witness_points=[[0,-.175,.05],[0,-.19,.05],[0,-.175,.035],[0,-.16,.035]]
    witnesses=[]
    for point in witness_points:
        row={'pointRawGltf':point}
        for label,g in [('coarse',c),('fine',f)]:
            value,idx=at_point(g['outside'],point,g['origin'],g['pitch'])
            row[label]={'outsideAtAxis':bool(value),'surfaceAtAxis':bool(g['surface'][tuple(idx)]),
                        'wholeLineClear':bool(np.all(g['outside'][:,idx[1],idx[2]])),'index':idx}
        witnesses.append(row)
    compare={'fineCellsMappingToCoarseLargestInterior':int(target.sum()),
             'fineExteriorCellsMappingToCoarseLargestInterior':int(np.count_nonzero(target&f['outside'])),
             'fineSurfaceCellsMappingToCoarseLargestInterior':int(np.count_nonzero(target&f['surface'])),
             'fineCurrentlyFilledCells':int(np.count_nonzero(~f['outside'])),
             'fineCentresMappingToCoarseFilled':int(coarse_filled.sum()),
             'mapping':'Fine cell centres mapped by actual world coordinates and floor to coarse cells; no array-index rescaling.'}
    print(json.dumps({'phase':'grid-comparison','coarse':coarse_proof,'comparison':compare,'elapsed':time.perf_counter()-start}),flush=True)
    # Face erosion only diagnoses a one-cell free-space throat. Nothing is added
    # to the source grid or mesh here; global dilation is explicitly not adopted.
    free=f['outside']
    thick=six_erosion(free)
    lbl,n=components(thick)
    totals=np.bincount(lbl.ravel())
    overlaps=np.bincount(lbl[target].ravel(),minlength=len(totals))
    overlaps[0]=0
    body_id=int(overlaps.argmax())
    border=np.unique(np.concatenate([lbl[1].ravel(),lbl[-2].ravel(),lbl[:,1].ravel(),lbl[:,-2].ravel(),lbl[:,:,1].ravel(),lbl[:,:,-2].ravel()]))
    exterior_ids=border[border!=0]
    require(len(exterior_ids)>0,'No thick free-space exterior component')
    exterior_id=int(exterior_ids[np.argmax(totals[exterior_ids])])
    top_ids=np.argsort(overlaps)[-10:][::-1]
    thick_proof={'freeSpaceFaceErosionCells':1,'diagnosticOnly':True,'componentCount':int(n),
                 'bodyComponentId':body_id,'bodyCells':int(totals[body_id]),'bodyCoarseInteriorCells':int(overlaps[body_id]),
                 'largestExteriorId':exterior_id,'largestExteriorCells':int(totals[exterior_id]),
                 'bodyRemainsExterior':body_id in exterior_ids.tolist(),
                 'largestInteriorOverlapComponents':[{'id':int(i),'cells':int(totals[i]),'coarseInteriorCells':int(overlaps[i]),
                                                      'touchesGridBorder':bool(i in exterior_ids)} for i in top_ids if overlaps[i]>0]}
    print(json.dumps({'phase':'throat-diagnostic','proof':thick_proof,'elapsed':time.perf_counter()-start}),flush=True)
    body=lbl==body_id
    exterior=lbl==exterior_id
    # Thin bridge suspects: one free cell simultaneously adjacent to thick body
    # and exterior. Each connected suspect is separately measured; no adoption.
    if body_id!=exterior_id:
        body_boundary=six_dilation(body)&~body
        exterior_boundary=six_dilation(exterior)&~exterior
        bridges=free&body_boundary&exterior_boundary
    else:
        bridges=np.zeros(f['shape'],bool)
    blbl,bcount=components(bridges)
    bc=np.bincount(blbl.ravel());bc[0]=0
    bridge_rows=[]
    for bid in np.argsort(bc)[-24:][::-1]:
        if bc[bid]==0:continue
        indices=np.where(blbl==bid)
        bridge_rows.append({'componentId':int(bid),'cells':int(bc[bid]),'boundsRawGltf':world_bounds(indices,f['origin'],f['pitch']),
                            'centroidRawGltf':(f['origin']+(np.array([x.mean() for x in indices])+.5)*f['pitch']).tolist(),
                            'coarseSurfaceMappedCells':int(np.count_nonzero(coarse_surface[indices])),
                            'coarseFilledMappedCells':int(np.count_nonzero(coarse_filled[indices]))})
    OUT.mkdir()
    np.savez_compressed(OUT/'diagnostic-regions.npz',shape=np.array(f['shape']),origin=f['origin'],pitch=f['pitch'],
                        coarseInteriorMappedPacked=np.packbits(target.ravel(),bitorder='big'),
                        bodyThickPacked=np.packbits(body.ravel(),bitorder='big'),
                        exteriorThickPacked=np.packbits(exterior.ravel(),bitorder='big'),
                        bridgeSuspectsPacked=np.packbits(bridges.ravel(),bitorder='big'))
    shutil.copy2(__file__,OUT/'executed-diagnosis.py')
    for path,pin in pins.items():require(sha(path)==pin,'Changed source/cache during read-only diagnosis')
    report={'schemaVersion':1,'readOnly':True,'sourceMutation':False,'gridMutation':False,'sourceAdopted':False,
            'gpuUsed':False,'clientControlled':False,'frozenInputs':pins,'sourceFrame':'Untouched raw glTF compact master coordinates.',
            'coarseLargestEnclosure':coarse_proof,'fineVersusCoarse':compare,'protectedClearLines':rows,'coreWitnesses':witnesses,
            'throatDiagnostic':thick_proof,'directOneCellBridgeSuspectCount':int(bridges.sum()),'bridgeComponentCount':int(bcount),
            'bridgeSuspects':bridge_rows,'elapsedSeconds':time.perf_counter()-start,
            'limits':['Face-eroded free-space labels only diagnose a narrow path; no global morphology or filled384 geometry adopted.',
                      'Closed coarse fill is not anatomical ground truth; compare actual exterior envelope and all grip witnesses before reconstruction.',
                      'Both original caches already touch one of22 exact source-clear near-edge lines. Additive closure must not silently claim22/22 voxel clearance.',
                      'Any final patch must prove minimum extent, exterior source support, flood separation and all current protected witness states without changing selected neighbouring parts.']}
    (OUT/'diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'phase':'completed','bridgeSuspectCells':int(bridges.sum()),'bridgeComponents':int(bcount),
                      'output':str(OUT/'diagnosis.json'),'sha256':sha(OUT/'diagnosis.json'),'elapsed':time.perf_counter()-start}),flush=True)


if __name__=='__main__':main()
