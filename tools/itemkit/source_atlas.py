"""4K donor atlas: bounded UV-only repairs, unchanged source-frame geometry."""
from pathlib import Path
import time
import numpy as np
from tools.headkit.common import library,pin,write,require
from tools.headkit.uv import physical_fans,_pack,raster_audit,chart_ids
from .atlas import region_gutters


def repair_uv(vertices,faces,initial,size=4096,diagnostic_path=None):
    """Keep healthy chart domains fixed; move only bounded defective triangles."""
    require(size==4096,'Source atlas is audited at the 4K donor sampling resolution')
    uv=np.asarray(initial,np.float32).astype(float)
    require(uv.shape==(len(faces),3,2) and np.isfinite(uv).all()
            and np.all((uv>=0)&(uv<=1)),'Finite source UV triangles inside the atlas required')
    uv[:,:,0]*=.90;uv=uv.astype(np.float32).astype(float)
    original=uv.copy();regions=chart_ids(original);original_regions=regions.copy()
    tri=np.asarray(vertices)[faces];areas=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)*.5
    require(np.isfinite(areas).all() and np.all(areas>0),'Source atlas requires nondegenerate geometry')
    isolated=set();iterations=[]
    for iteration in range(4):
        uv=uv.astype(np.float32).astype(float);audit,owners=raster_audit(uv,size)
        charts=chart_ids(uv);mapped=np.unique(owners[owners>=0])
        missing_charts=np.setdiff1d(np.unique(charts),np.unique(charts[mapped]))
        bad=set(audit['overlapFaces']+audit['degenerateUvFaces'])
        bad.update(np.flatnonzero(np.isin(charts,missing_charts)).tolist())
        iterations.append({'iteration':iteration,'badFaces':sorted(bad),'unmappedCharts':missing_charts.tolist()})
        if not bad:break
        isolated.update(bad);ids=np.asarray(sorted(isolated),int)
        require(len(ids)<len(faces)*.03 and areas[ids].sum()<areas.sum()*.03,
                'Source UV repair exceeds bounded local face/area scope')
        columns=max(1,int(np.ceil(np.sqrt(len(ids)*.08/.90))));rows=int(np.ceil(len(ids)/columns))
        cw=.08/columns;ch=.90/rows;gap=3/size
        require(min(cw,ch)>2*gap+2/size,'Insufficient 4K sampling room for source UV repair')
        for k,fi in enumerate(ids):
            x=.91+(k%columns)*cw;y=.05+(k//columns)*ch
            uv[fi]=((x+gap,y+gap),(x+cw-gap,y+gap),(x+gap,y+ch-gap))
        regions=original_regions.copy();regions[ids]=int(regions.max()+1)+np.arange(len(ids))
    else:raise ValueError('Source UV defects remain after bounded UV-only repair')
    ids=np.asarray(sorted(isolated),int);healthy=np.setdiff1d(np.arange(len(uv)),ids)
    require(np.array_equal(uv[healthy],original[healthy]),'Healthy source chart domain changed')
    missing=np.setdiff1d(np.arange(len(faces)),mapped)
    missing_fraction=float(areas[missing].sum()/areas.sum())
    gutters=region_gutters(owners,regions)
    proof={'originalUV':original,'originalRegions':original_regions,'finalUV':uv,
           'finalRegions':regions,'isolatedFaces':ids}
    report={'iterations':iterations,'audit':audit,'gutters':gutters,'isolatedFaces':ids.tolist(),
            'isolatedAreaFraction':float(areas[ids].sum()/areas.sum()),
            'unmappedFaces':missing.tolist(),'unmappedSurfaceFraction':missing_fraction,
            'unmappedCharts':missing_charts.tolist(),'healthyDomainsUnchanged':True,
            'samplingResolution':size,'diagnosticMapsAreNotDonorSamplingInputs':True}
    if diagnostic_path is not None:write(diagnostic_path,report,fresh=True)
    require(not missing_charts.size and missing_fraction<.001,'Unsampled source atlas surface/chart')
    require(audit['coverageFraction']>=.30,
            f"Insufficient useful source UV coverage ({audit['coverageFraction']:.6f} < 0.30)")
    return uv,proof,report


def unwrap(mesh,local,output):
    output=Path(output);output.mkdir(exist_ok=False);begun=time.monotonic()
    vertices,faces=physical_fans(mesh,preserve_authored_seams=False)
    xatlas=library(local,'xatlas');attempts=[]
    # Qualify at 4K rather than inheriting the final 1K atlas's larger padding.
    # Small padding preserves source sampling area; measured gutters still gate it.
    for padding in (4,8,16):
        started=time.monotonic()
        initial,atlas,count=_pack(xatlas,vertices,faces,[np.arange(len(faces))],padding=padding)
        candidate=output/f'candidate-padding-{padding}.npz'
        np.savez_compressed(candidate,positions=vertices,faces=faces,uv=initial)
        row={'padding':padding,'charts':count,'atlasDimensions':[atlas.width,atlas.height],
             'candidate':pin(candidate),'packingSeconds':time.monotonic()-started}
        attempts.append(row)
        try:
            uv,proof,report=repair_uv(vertices,faces,initial,diagnostic_path=output/f'repair-padding-{padding}.json')
            row['repair']=report
            if report['gutters']['nearbyChartPixelsByRadius']['2']:
                row['state']='insufficient-source-gutter';continue
            require(count<=max(256,int(len(faces)*.3)),'Severe source UV fragmentation')
            proof_path=output/'region-proof.npz';np.savez_compressed(proof_path,**proof)
            row['state']='accepted'
            result={'attempts':attempts,'regionProof':pin(proof_path),'geometryUnchanged':True,
                    'preserveAuthoredSeams':False,'samplingResolution':4096,
                    'elapsedSeconds':time.monotonic()-begun,'visualReview':'required'}
            write(output/'atlas.json',result,fresh=True)
            return dict(mesh,uv=uv,chart_ids=chart_ids(uv),uv_pending_unwrap=False),result
        except Exception as exc:
            row.update(state='failed',error=str(exc));raise
        finally:write(output/'attempts.json',{'attempts':attempts,'elapsedSeconds':time.monotonic()-begun})
    raise ValueError('Source atlas cannot meet its measured two-pixel 4K gutter')
