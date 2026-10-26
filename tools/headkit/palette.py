"""Per-texel ownership, palette quantization and isolated channel diagnostics."""
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
from .common import require, verify, pin, read, write
from .gltf import mesh
from .textures import surface,pad
from .rays import EmbreeScene


def project_ownership(source, views, embree, output, *, max_subtexel_fraction=.005):
    """View labels are measured annotations, not RGB-threshold skin/hair guesses. The 1K sampling gate uses the same
    reviewed sub-texel allowance as unwrap and bake."""
    verify([embree]);value=mesh(source);positions,owners,_=surface(value,1024,max_subtexel_fraction);mapped=owners>=0
    labels=np.full((1024,1024),255,np.uint8);points=positions[mapped];chosen=np.full(len(points),255,np.uint8)
    scene=EmbreeScene(embree['path'],value['positions'],value['faces']);reports=[]
    try:
        for row in views:
            require(row.get('calibrationReviewed') is True,'Review camera and withheld landmark alignment first')
            with Image.open(row['mask']) as image:
                require(image.mode=='L','Ownership masks must be eight-bit L images')
                mask=np.asarray(image).copy()
            require(np.all((mask<=9)|(mask==255)),'Invalid semantic labels')
            matrix=np.asarray(row['viewProjection'],float);origin=np.asarray(row['cameraOrigin'],float)
            require(matrix.shape==(4,4) and origin.shape==(3,) and np.isfinite(matrix).all() and np.isfinite(origin).all(),'Perspective camera matrix/origin required')
            clip=np.c_[points,np.ones(len(points))]@matrix.T;positive=clip[:,3]>0
            uv=clip[:,:2]/np.maximum(clip[:,3,None],1e-20);uv=uv*np.array([.5,-.5])+.5
            valid=positive&(uv>=0).all(1)&(uv<1).all(1)&(chosen==255)
            index=np.flatnonzero(valid);delta=points[index]-origin;distance=np.linalg.norm(delta,axis=1)
            require(np.all(distance>0),'Camera lies on sampled surface')
            directions=delta/distance[:,None];depth,face_ids,_=scene.query(np.broadcast_to(origin,delta.shape),directions)
            diagonal=float(np.linalg.norm(np.ptp(value['positions'],axis=0)))
            visible=(face_ids>=0)&(np.abs(depth-distance)<=diagonal*1e-5)
            ii=index[visible];q=uv[ii];samples=mask[(q[:,1]*len(mask)).astype(int),(q[:,0]*mask.shape[1]).astype(int)]
            accepted=samples<=9;chosen[ii[accepted]]=samples[accepted]
            reports.append({'name':row['name'],'visible':int(visible.sum()),'assigned':int(accepted.sum())})
    finally:scene.close()
    labels[mapped]=chosen;unresolved=int(np.count_nonzero(chosen==255))
    Image.fromarray(labels).save(output)
    require(unresolved==0,'Unobserved ownership remains; annotate a qualified atlas fallback instead of defaulting to hair')
    labels=pad(labels,mapped);Image.fromarray(labels).save(output)
    return {'output':pin(output),'views':reports,'unresolvedMappedSamples':unresolved}


def rank_rows(color, ownership, palette_files, *, keep=4, chunk=512):
    """Exact per-channel row ranking: count-weighted mean squared RGB distance of every pixel to its nearest eligible
    shade. Distances are computed on unique colours as integer-exact float32 products. Rows are scored on the heaviest
    colours first and dropped once their partial error exceeds the keep-th best complete error, which cannot change
    the top rows. Ties keep the lower row."""
    rgb=np.asarray(Image.open(color).convert('RGB'),np.uint8)
    with Image.open(ownership) as image:
        require(image.mode=='L','Ownership masks must be eight-bit L images');layers=np.asarray(image).copy()
    require(rgb.shape[:2]==layers.shape and type(keep) is int and keep>0,'Ranking colour and ownership must match');result={}
    for key,path in palette_files.items():
        selected=layers==int(key);require(selected.any(),'Automatic row selection needs mapped pixels; give channel '+key+' an explicit row')
        packed=rgb[selected].astype(np.int32)@np.array([65536,256,1],np.int32)
        values,counts=np.unique(packed,return_counts=True);order=np.argsort(-counts,kind='stable');values,counts=values[order],counts[order]
        colours=np.c_[values>>16,(values>>8)&255,values&255,np.ones_like(values)].astype(np.float32);norms=(colours[:,:3]**2).sum(1)
        palette=np.asarray(Image.open(path).convert('RGBA'));require(palette.shape[1]==256,'Stock palettes have 256 shades')
        # |c-t|^2 = |c|^2 + min over t of (|t|^2 - 2c.t): one GEMM per chunk; every term is an integer below 2^24.
        tables={row:np.r_[-2*table.T,(table*table).sum(1)[None,:]] for row in range(len(palette))
                for table in [palette[row,(palette[row,:,3]>0)&(np.arange(256)<255),:3].astype(np.float32)] if len(table)}
        require(tables,'No palette row has opaque shades')
        def error(row,lo,hi):
            return float(np.dot((norms[lo:hi]+(colours[lo:hi]@tables[row]).min(1)).astype(np.float64),counts[lo:hi]))
        best=[]
        for estimate,row in sorted((error(row,0,chunk),row) for row in tables):
            limit=best[-1][0] if len(best)==keep else np.inf;total=estimate;done=chunk
            while total<=limit and done<len(colours):step=min(done,16384);total+=error(row,done,done+step);done+=step
            if total<=limit:best=sorted(best+[(total,row)])[:keep]
        result[key]={'row':best[0][1],'pixels':int(counts.sum()),'uniqueColours':len(colours),'rowsScored':len(tables),
                     'top':[{'row':row,'meanSquaredDistance':total/counts.sum()} for total,row in best]}
    return result


REFERENCES=Path(__file__).with_name('stock-shades.json');GRID=(.05,.25,.5,.75,.95)
# Design-referenced rows (toneMatch rowFrom 'design'): lightness weight of the Lab distance (the matched shades already
# set lightness, so hue and chroma decide), front-view size, label erosion and the minimum design sample. Validated on the
# troll heads' hand-pinned skin rows: closer to the pin than the bake-referenced row on 16 of 20 (median 6.0 vs 10.6).
DESIGN_LIGHTNESS_WEIGHT,FRONT_SIZE,FRONT_EROSION,MINIMUM_DESIGN_PIXELS=.25,512,2,200


def lab(rgb):
    """CIE Lab (D65) of sRGB rows."""
    c=np.asarray(rgb,float).reshape(-1,3)/255;c=np.where(c>.04045,((c+.055)/1.055)**2.4,c/12.92)
    xyz=c@np.array([[.4124,.3576,.1805],[.2126,.7152,.0722],[.0193,.1192,.9505]]).T/np.array([.95047,1,1.08883])
    f=np.where(xyz>.008856,np.cbrt(xyz),7.787*xyz+16/116);return np.c_[116*f[:,1]-16,500*(f[:,0]-f[:,1]),200*(f[:,1]-f[:,2])]


def front_labels(value, layers, size=FRONT_SIZE):
    """Front (+z, glTF) orthographic channel view of a UV mesh: interior barycentric lattice points of every face turned
    toward the viewer splat to pixels (nearest wins) and read the 1K ownership label at their UV; gaps inside the
    silhouette take the nearest label. Each face gets about one point per pixel of its projected edge length, so large
    faces leave no holes; interior points avoid chart-border gutters, and front-facing faces keep the back of the head
    out of sample gaps."""
    from scipy import ndimage
    p=np.asarray(value['positions'],float);corners=p[np.asarray(value['faces'])];uv=np.asarray(value['uv'],float).reshape(-1,3,2)
    lo,hi=p.min(0),p.max(0);span=max(hi[0]-lo[0],hi[1]-lo[1])*1.02;centre=(lo+hi)/2
    facing=np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0])[:,2]>0;corners,uv=corners[facing],uv[facing]
    edge=np.max(np.linalg.norm((corners-np.roll(corners,1,axis=1))[...,:2],axis=-1),axis=1)/span*size
    levels=np.clip(np.ceil(edge).astype(int)+2,6,256);points=[];texels=[]
    for level in np.unique(levels):  # one lattice per density, vectorized over its faces
        i,j=np.mgrid[1:level,1:level];keep=i+j<level;w=np.c_[i[keep],j[keep],level-i[keep]-j[keep]]/level;chosen=levels==level
        points.append(np.einsum('sk,fkd->fsd',w,corners[chosen]).reshape(-1,3));texels.append(np.einsum('sk,fkd->fsd',w,uv[chosen]).reshape(-1,2))
    points,texels=np.concatenate(points),np.concatenate(texels)
    n=len(layers);labels=layers[np.clip((texels[:,1]*n).astype(int),0,n-1),np.clip((texels[:,0]*n).astype(int),0,n-1)].astype(int)
    x=np.clip(((points[:,0]-centre[0])/span*size+size/2).astype(int),0,size-1);y=np.clip(((centre[1]-points[:,1])/span*size+size/2).astype(int),0,size-1)
    pixel=y*size+x;order=np.lexsort((-points[:,2],pixel));first=np.r_[True,np.diff(pixel[order])!=0]
    out=np.full(size*size,-1);out[pixel[order][first]]=labels[order][first];out=out.reshape(size,size)
    inside=ndimage.binary_fill_holes(ndimage.binary_closing(out>=0,iterations=2));_,(iy,ix)=ndimage.distance_transform_edt(out<0,return_indices=True)
    return np.where(inside,out[iy,ix],-1)


def register(design_mask, front_mask):
    """Scale and offset mapping front-view pixels to design pixels from the top edge and horizontal extent of each
    silhouette's upper 60% (below the jaw the design keeps a neck the head no longer has)."""
    def upper(mask):
        ys,xs=np.nonzero(mask);cut=ys.min()+int((ys.max()-ys.min())*.6);ys,xs=np.nonzero(mask[:cut]);return xs.min(),xs.max(),ys.min()
    fx0,fx1,fy0=upper(front_mask);dx0,dx1,dy0=upper(design_mask);require(fx1>fx0 and dx1>dx0,'Degenerate silhouette')
    scale=(dx1-dx0)/(fx1-fx0);return scale,dx0-scale*fx0,dy0-scale*fy0


def design_reference(design_rgb, design_mask, value, layers, output):
    """Mean Lab of the design's visible pixels per ownership channel, sampled through the registered front view
    (labels eroded so registration error stays inside the channel). Writes design-reference.png for review."""
    from scipy import ndimage
    from .paint import PREVIEW
    front=front_labels(value,layers);scale,ox,oy=register(design_mask,front>=0);h,w=front.shape;ys,xs=np.mgrid[0:h,0:w]
    sy=np.clip(np.rint(ys*scale+oy).astype(int),0,design_rgb.shape[0]-1);sx=np.clip(np.rint(xs*scale+ox).astype(int),0,design_rgb.shape[1]-1)
    warped=design_rgb[sy,sx];visible=design_mask[sy,sx];targets={}
    for key in np.unique(front[front>=0]):
        chosen=ndimage.binary_erosion(front==key,iterations=FRONT_EROSION)&visible;samples=warped[chosen]
        targets[str(key)]={'pixels':int(len(samples)),**({'lab':lab(samples).mean(0).round(2).tolist()} if len(samples) else {})}
    overlay=np.where((front>=0)[...,None],(warped*.6+PREVIEW[np.clip(front,0,9)].astype(float)*.4),warped*.35).astype(np.uint8)
    Image.fromarray(np.concatenate([warped,overlay],1)).save(output)
    return {'channels':targets,'registration':{'scale':round(float(scale),4),'offset':[round(float(ox),1),round(float(oy),1)]},'image':pin(output)}


def design_rows(target, shades, palette, *, keep=4):
    """Rows ranked by Lab distance of their decoded mean colour (shades fixed, count-weighted) to the design's mean
    colour for the channel, lightness weighted DESIGN_LIGHTNESS_WEIGHT."""
    used=np.unique(shades);counts=np.bincount(shades,minlength=256)[used].astype(float)
    usable=np.flatnonzero(np.all(palette[:,used,3]>0,axis=1))  # rows that can show every matched shade
    means=(lab(palette[usable][:,used,:3]).reshape(len(usable),len(used),3)*counts[None,:,None]).sum(1)/counts.sum()
    delta=means-np.asarray(target,float);distance=np.sqrt(DESIGN_LIGHTNESS_WEIGHT*delta[:,0]**2+delta[:,1]**2+delta[:,2]**2)
    rows=sorted(zip(distance.tolist(),usable.tolist()))
    return [{'row':row,'designDistance':round(distance,3)} for distance,row in sorted(rows)[:keep]]


def plt_shades(path):
    """Top-down shade and layer maps of a PLT V1: a 24-byte header (width, height at 16..23) and width*height
    (shade, layer) byte pairs, bottom row first."""
    raw=Path(path).read_bytes();require(raw[:8]==b'PLT V1  ' and len(raw)>=24,'Not a PLT V1 file')
    width,height=(int(v) for v in np.frombuffer(raw[16:24],'<u4'));require(len(raw)==24+2*width*height,'PLT size mismatch')
    pixels=np.frombuffer(raw[24:],np.uint8).reshape(height,width,2)[::-1];return pixels[...,0].copy(),pixels[...,1].copy()


def shade_reference(paths, layer, *, knots=101):
    """Mean per-texture quantile function (1-D Wasserstein barycentre) of one channel's shades at evenly spaced
    probabilities. Textures whose channel holds the same multiset of shades (stock heads reuse skins) count once."""
    unique={}
    for path in paths:
        shades,layers=plt_shades(path);values=np.sort(shades[layers==layer])
        if len(values):unique.setdefault(values.tobytes(),values)
    require(unique,'No reference texels for channel '+str(layer))
    return np.mean([np.quantile(v,np.linspace(0,1,knots)) for v in unique.values()],axis=0).round(2).tolist(),len(unique)


def shade_reference_entry(paths, layer, description):
    """One stock-shades.json reference (headkit `shade-reference`): the measured quantiles plus every source PLT's
    resref and SHA-256, so the numbers stay bound to the base-game files they came from."""
    paths=sorted(Path(p) for p in paths);require(paths and len({p.name.lower() for p in paths})==len(paths),'Distinct stock PLT files required')
    quantiles,unique=shade_reference(paths,layer)
    return {'layer':layer,'description':description,'uniqueTextures':unique,
            'method':'headkit.palette.shade_reference(paths, layer): mean of the per-texture quantile functions at 101 evenly spaced '
                     'probabilities; textures whose channel holds an identical shade multiset count once',
            'quantiles':quantiles,'sources':[{'resref':p.name.lower(),'sha256':pin(p)['sha256']} for p in paths]}


def shade_stats(shades):
    return {'mean':float(shades.mean()),'std':float(shades.std()),**{f'p{round(q*100)}':float(v) for q,v in zip(GRID,np.quantile(shades,GRID))},
            'histogram16':np.bincount(shades//16,minlength=16).tolist()}


def match_shades(target, allowed, quantiles):
    """Rank-preserving histogram match: each texel's luma rank in its channel (mid-rank for ties) reads the reference
    quantile function, rounds and snaps to the nearest eligible shade. A brighter source texel never gets a darker shade,
    and the result does not depend on the row, unlike nearest-colour indices."""
    luma=np.asarray(target,float)@np.array([.299,.587,.114]);_,inverse,counts=np.unique(luma,return_inverse=True,return_counts=True)
    quantiles=np.asarray(quantiles,float);require(quantiles.ndim==1 and len(quantiles)>1 and np.all(np.diff(quantiles)>=0)
        and quantiles[0]>=0 and quantiles[-1]<=254,'Reference quantiles must be a non-decreasing 0..254 list')
    shade=np.rint(np.interp((np.cumsum(counts)-counts/2)/counts.sum(),np.linspace(0,1,len(quantiles)),quantiles))
    _,near=cKDTree(allowed[:,None]).query(shade[:,None]);return allowed[near][inverse.ravel()]


def rows_for_shades(target, shades, palette, *, keep=4):
    """Rows ranked by meanSquaredColorError (per RGB component) with the shades fixed: the rows that best show the source colours."""
    counts=np.bincount(shades,minlength=256);used=counts>0;target=np.asarray(target,float)
    sums=np.stack([np.bincount(shades,target[:,c],256) for c in range(3)],1);squares=np.bincount(shades,(target**2).sum(1),256)
    scores=sorted((float((counts[used]*(t*t).sum(1)-2*(t*sums[used]).sum(1)+squares[used]).sum()/(3*len(shades))),row)
                  for row in range(len(palette)) if np.all(palette[row,used,3]>0) for t in [palette[row,used,:3].astype(float)])
    return [{'row':row,'meanSquaredColorError':error} for error,row in scores[:keep]]


def quantize(color, ownership, palette_files, rows, output, *, shade_offsets=None, tone_match=None, design=None):
    """Nearest-colour shades per channel. Opt-in `tone_match` ({channel: {'reference': name}}) instead remaps a channel's shades
    by luma rank onto a measured stock shade distribution, so every in-game palette row reads like it does on stock heads.
    A tone-matched 'auto' row comes from the source colours, or with `rowFrom: 'design'` from the design's colour for the
    channel (`design`: design_reference channels), keeping the source-colour row in the report."""
    require(set(rows)==set(palette_files),'Every selected layer needs its own stock palette image')
    rgb=np.asarray(Image.open(color).convert('RGB'),np.uint8)
    with Image.open(ownership) as image:
        require(image.mode=='L','Ownership masks must be eight-bit L images')
        layers=np.asarray(image).copy()
    require(rgb.shape==(1024,1024,3) and layers.shape==(1024,1024),'Runtime maps must be 1K')
    require(np.all(layers<=9),'Resolve all palette ownership before export')
    shades=np.zeros_like(layers);decoded=np.zeros_like(rgb);report={};tables={};resolved=dict(rows)
    shade_offsets=shade_offsets or {};tone_match=tone_match or {}
    require(type(tone_match) is dict and set(tone_match)<={str(v) for v in np.unique(layers)},'Tone matching names a channel without mapped texels')
    references=read(REFERENCES)['references'] if tone_match else {}
    for layer in np.unique(layers):
        key=str(layer);require(key in rows and key in palette_files,'No palette binding for mapped channel')
        palette=np.asarray(Image.open(palette_files[key]).convert('RGBA'));row=rows[key];spec=tone_match.get(key)
        selected=layers==layer;target=rgb[selected].astype(float)
        if spec is not None:
            require(type(spec) is dict and set(spec)-{'rowFrom'}=={'reference'} and spec['reference'] in references
                    and spec.get('rowFrom','bake') in ('bake','design'),'Tone matching needs one known stock shade reference (rowFrom bake or design)')
            quantiles=references[spec['reference']]['quantiles']
        if row=='auto':
            # Matched shades depend only on luma rank, so the row follows them: the one that best shows the source colours.
            require(spec is not None and palette.shape[1]==256,'Rank automatic rows before quantization unless the channel is tone matched')
            matched_shades=match_shades(target,np.arange(255),quantiles);candidates=rows_for_shades(target,matched_shades,palette,keep=1)
            require(candidates,'No palette row shows every tone-matched shade');row=candidates[0]['row']
            if spec.get('rowFrom')=='design':
                reference=(design or {}).get(key,{'pixels':0});chosen={'bakeRow':row,'designPixels':reference['pixels']}
                if reference['pixels']>=MINIMUM_DESIGN_PIXELS:
                    ranked=design_rows(reference['lab'],matched_shades,palette);require(ranked,'No palette row shows every tone-matched shade')
                    row=ranked[0]['row'];chosen.update(designLab=reference['lab'],rows=ranked)
                else:chosen['fallback']=f'Fewer than {MINIMUM_DESIGN_PIXELS} design pixels in this channel: row from the source colours'
            resolved[key]=row
        require(type(row) is int and 0<=row<len(palette) and palette.shape[1]==256,'Invalid stock palette row')
        eligible=(palette[row,:,3]>0)&(np.arange(256)<255);allowed=np.flatnonzero(eligible)
        require(len(allowed)>0,'No opaque palette shades available')
        table=palette[row,:,:3]
        distance,index=cKDTree(table[allowed].astype(float)).query(target,k=1,workers=4)
        picked=allowed[index];offset=shade_offsets.get(key,0)
        require(type(offset) is int and abs(offset)<=32,'Bounded reviewed stock-skin shade offset required')
        if offset:
            shifted=np.clip(picked+offset,0,254);_,near=cKDTree(allowed[:,None]).query(shifted[:,None]);picked=allowed[near]
        if spec is not None:
            require(not offset,'Use a shade offset or tone matching for a channel, not both')
            nearest=picked;picked=match_shades(target,allowed,quantiles)
            matched={'reference':spec['reference'],'referenceFile':pin(REFERENCES),'before':shade_stats(nearest),'after':shade_stats(picked),
                     'referencePercentiles':{f'p{round(q*100)}':float(np.interp(q,np.linspace(0,1,len(quantiles)),quantiles)) for q in GRID},
                     'meanSquaredColorErrorBefore':float(np.mean((target-table[nearest])**2)),'rowsAfter':rows_for_shades(target,picked,palette)}
        shades[selected]=picked;decoded[selected]=table[picked];tables[key]=table
        report[key]={'pixels':int(selected.sum()),'meanSquaredColorError':float(np.mean((target-table[picked])**2)),'shadeOffset':offset}
        if spec is not None:report[key]['toneMatch']=matched
        if spec is not None and spec.get('rowFrom')=='design' and rows[key]=='auto':report[key]['designRow']=chosen
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    Image.fromarray(shades).save(output/'shades.png');Image.fromarray(layers).save(output/'layers.png');Image.fromarray(decoded).save(output/'decoded.png')
    # Every channel is varied independently; other channels must remain byte-identical.
    isolation=[]
    for key,table in tables.items():
        isolated=decoded.copy();selected=layers==int(key);isolated[selected]=np.array([255,0,255],np.uint8)
        require(np.array_equal(isolated[~selected],decoded[~selected]),'Channel isolation failure')
        path=output/f'isolate-{key}.png';Image.fromarray(isolated).save(path);isolation.append(pin(path))
    result={'layers':report,'isolation':isolation,'shades':pin(output/'shades.png'),'ownership':pin(output/'layers.png'),
            'decoded':pin(output/'decoded.png'),'visualReviewRequired':True,'rows':resolved}
    write(output/'palette.json',result,fresh=True);return result
