"""Audited final item atlas, with bounded UV-only isolation and unchanged geometry."""
from pathlib import Path
import time
import numpy as np
from tools.headkit.common import library, pin, write, require
from tools.headkit.uv import physical_fans, _pack, raster_audit, gutter_audit, chart_ids
from .geometry import topology


def region_gutters(owners, regions):
    """Pieces left in one original chart share one continuous UV colour domain.

    Isolating a bad triangle can disconnect that chart without moving its other
    triangles. Those pieces are safe neighbours; relocated triangles receive
    distinct regions and must clear every other region by the full gutter.
    """
    covered=owners>=0;high=np.full(owners.shape,-1,np.int32)
    high[covered]=regions[owners[covered]]
    low=np.full(owners.shape,np.iinfo(np.int32).max,np.int32);low[covered]=high[covered]
    del covered
    scratch=np.empty_like(low)
    def expand(values, buffer, axis, distance, operation):
        buffer[:]=values
        for offset in range(1,min(distance+1,values.shape[axis])):
            left=[slice(None),slice(None)];right=list(left)
            left[axis]=slice(None,-offset);right[axis]=slice(offset,None)
            left,right=tuple(left),tuple(right)
            operation(buffer[left],values[right],out=buffer[left])
            operation(buffer[right],values[left],out=buffer[right])
        return buffer,values
    collisions={};previous=0
    for radius in (1,2,4):
        # Square neighbourhoods are separable. Radius increments compose exactly,
        # including empty borders, so reuse low/high and one scratch array.
        for axis in (0,1):
            low,scratch=expand(low,scratch,axis,radius-previous,np.minimum)
            high,scratch=expand(high,scratch,axis,radius-previous,np.maximum)
        collisions[str(radius)]=int(np.count_nonzero((low<high)&(high>=0)))
        previous=radius
    return {'regionCount':int(len(np.unique(regions))),'nearbyChartPixelsByRadius':collisions}


def unwrap_parts(source, local, output, runtime_size=1024, *, packing_paddings=None, parts=('b','m','t')):
    paddings=(16,32) if packing_paddings is None else packing_paddings
    require(isinstance(paddings,(list,tuple)) and 1<=len(paddings)<=3
            and all(type(n) is int and 8<=n<=32 for n in paddings)
            and list(paddings)==sorted(set(paddings)), 'Ordered unique atlas paddings in 8..32 required')
    require(tuple(parts) in (('b','m','t'),('b',),('m',),('t',)), 'Explicit native processing parts required')
    output=Path(output);output.mkdir();begun=time.monotonic()
    with np.load(source,allow_pickle=False) as archive:
        values={key:archive[key].copy() for key in archive.files}
    require(set(values)=={p+'_'+key for p in parts for key in ('positions','faces','hiddenCaps')},
            'Atlas input parts differ from the declared visible assembly')
    vertices=[];faces=[];groups=[];visible_parts={};offset=0;face_offset=0
    for part in parts:
        p=values[part+'_positions'];f=values[part+'_faces'];require(topology(p,f)['closedWound'],'Final atlas requires closed native parts')
        caps=values[part+'_hiddenCaps'];require(caps.dtype==bool and caps.shape==(len(f),),'Explicit geometric cap mask required')
        visible_parts[part]=np.flatnonzero(~caps);f=f[~caps]
        v,indices=physical_fans({'positions':p,'faces':f,'uv':np.zeros((len(f),3,2))},False)
        vertices.append(v);faces.append(indices+offset);groups.append(np.arange(face_offset,face_offset+len(f)))
        offset+=len(v);face_offset+=len(f)
    vertices=np.concatenate(vertices);faces=np.concatenate(faces);triangles=vertices[faces]
    areas=np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1)*.5
    xatlas=library(local,'xatlas');attempts=[];accepted=None
    for padding in paddings:
        uv,atlas,count=_pack(xatlas,vertices,faces,groups,padding=padding);uv[:,:,0]*=.94;isolated=set()
        original_uv=uv.astype(np.float32).astype(np.float64);original_regions=chart_ids(original_uv)
        for iteration in range(3):
            uv=uv.astype(np.float32).astype(np.float64)
            audits={};owners={};bad=set()
            for size in (4096,2048,runtime_size,512):
                key=str(size);audits[key],owners[size]=raster_audit(uv,size)
                bad.update(audits[key]['overlapFaces']);bad.update(audits[key]['degenerateUvFaces'])
            current_charts=chart_ids(uv)
            for size in (4096,runtime_size):
                mapped=np.unique(owners[size][owners[size]>=0]);missing_charts=np.setdiff1d(np.unique(current_charts),np.unique(current_charts[mapped]))
                bad.update(np.flatnonzero(np.isin(current_charts,missing_charts)))
            if not bad:break
            isolated.update(map(int,bad));ids=np.array(sorted(isolated),int)
            require(len(ids)<len(faces)*.03 and areas[ids].sum()<areas.sum()*.03,'Final UV repair exceeds bounded local scope')
            columns=4;rows=int(np.ceil(len(ids)/columns));cw=.05/columns;ch=.89/rows;gap=3/runtime_size
            require(min(cw,ch)>2*gap,'Insufficient runtime filtering room for UV repair')
            for k,fi in enumerate(ids):
                x=.95+(k%columns)*cw;y=.10+(k//columns)*ch
                uv[fi]=((x+gap,y+gap),(x+cw-gap,y+gap),(x+gap,y+ch-gap))
        else:raise ValueError('Final UV overlaps remain after bounded repair')
        palette=np.array([[.96,.02],[.985,.02],[.96,.045]])
        ids=np.array(sorted(isolated),int);regions=original_regions.copy();start=int(regions.max()+1)
        regions[ids]=start+np.arange(len(ids))
        require(np.array_equal(uv[np.setdiff1d(np.arange(len(uv)),ids)],original_uv[np.setdiff1d(np.arange(len(uv)),ids)]),'Healthy atlas domain changed during local repair')
        all_uv=np.concatenate([uv,palette[None]]);_,filter_owners=raster_audit(all_uv,runtime_size)
        gutters=region_gutters(filter_owners,np.r_[regions,int(regions.max()+1)])
        connected_gutters=gutter_audit(all_uv,runtime_size);charts=chart_ids(uv);coverage=[]
        for size,owner in owners.items():
            mapped=np.unique(owner[owner>=0]);missing=np.setdiff1d(np.arange(len(faces)),mapped)
            missing_charts=np.setdiff1d(np.unique(charts),np.unique(charts[mapped]))
            coverage.append({'size':size,'unmappedFaces':missing.tolist(),'unmappedSurfaceFraction':float(areas[missing].sum()/areas.sum()),'unmappedCharts':missing_charts.tolist()})
        attempts.append({'padding':padding,'atlasDimensions':[atlas.width,atlas.height],'isolatedFaces':sorted(isolated),'audits':audits,'gutters':gutters,'connectedComponentGutters':connected_gutters,'sampling':coverage})
        write(output/'packing-audit.json',{'attempts':attempts,'visibleFaces':len(faces),'caps':{p:int(values[p+'_hiddenCaps'].sum()) for p in parts}})
        require(audits[str(runtime_size)]['coverageFraction']>=.30,'Insufficient final useful UV coverage')
        # Subtexel triangles may interpolate within a sampled chart. Never lose an entire
        # chart or substantial surface at runtime; 512 is diagnostic, not runtime acceptance.
        for row in coverage:
            if row['size'] in (4096,runtime_size):
                require(not row['unmappedCharts'] and row['unmappedSurfaceFraction']<.001,'Unsampled final UV surface/chart')
        if gutters['nearbyChartPixelsByRadius']['2']==0:
            accepted=uv;break
    require(accepted is not None,'Final runtime two-pixel gutter check failed')
    for part,group_ids in zip(parts,groups):
        final=np.tile(palette,(len(values[part+'_faces']),1,1));final[visible_parts[part]]=accepted[group_ids]
        values[part+'_uv']=final.astype(np.float32)
        labels=np.full(len(final),int(regions.max()+1),np.int32)
        labels[visible_parts[part]]=regions[group_ids]
        values[part+'_uvRegions']=labels
    target=output/'final-atlas.npz';np.savez_compressed(target,**values)
    proof=output/'region-proof.npz';np.savez_compressed(proof,originalUV=original_uv,originalRegions=original_regions,finalVisibleUV=accepted,finalRegions=regions,isolatedFaces=ids)
    result={'atlas':pin(target),'source':pin(source),'regionProof':pin(proof),'attempts':attempts,'runtimeTextureSize':runtime_size,'geometryUnchanged':True,'explicitHiddenCaps':{p:int(values[p+'_hiddenCaps'].sum()) for p in parts},'intentionalCapPaletteOverlap':True,'capPaletteUV':palette.tolist(),'elapsedSeconds':time.monotonic()-begun}
    write(output/'atlas.json',result,fresh=True);return result
