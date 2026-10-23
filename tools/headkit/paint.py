"""Configured texture repairs: 3D-selected recolors, region fills, rule-driven ownership and per-channel colour adjustment.
Selections are manifest data (bbox-relative regions, colour predicates, priority order); nothing here is head-specific."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt
from scipy.sparse import coo_matrix
from .common import require, pin, write
from .gltf import mesh
from .uv import raster_audit

COMPARE={'gt':np.greater,'lt':np.less,'ge':np.greater_equal,'le':np.less_equal}
PREVIEW=np.array([[150,120,100],[30,30,30],[80,160,255],[60,90,140],[120,60,160],[160,90,200],[110,80,40],[150,110,60],[240,220,150],[230,30,40]],np.uint8)


class Values(dict):
    """Named arrays of one shape (texels or faces), computed on first use."""
    def __init__(self, factories):super().__init__();self.factories=factories
    def __missing__(self, key):
        require(key in self.factories,'Unavailable condition quantity: '+str(key))
        self[key]=value=self.factories[key]();return value


def colour_values(rgb, extra=None):
    c=lambda i:rgb[...,i].astype(np.int16)
    factories={'r':lambda:c(0),'g':lambda:c(1),'b':lambda:c(2),'lum':lambda:rgb.sum(-1,dtype=np.int32)/3,
               'sat':lambda:rgb.max(-1).astype(np.int16)-rgb.min(-1),'red':lambda:c(0)-np.maximum(c(1),c(2)),'rb':lambda:c(0)-c(2)}
    factories.update(extra or {});return Values(factories)


def when(condition, values, regions, depth=0):
    """JSON predicate: all/any/not, region (named), mask (paint output), channel, mapped, or {of, center?, gt/lt/ge/le}."""
    require(isinstance(condition,dict) and condition and depth<32,'Condition must be a non-empty object')
    keys=set(condition)
    for key in ('all','any'):
        if key in keys:
            require(keys=={key} and isinstance(condition[key],list) and condition[key],'Non-empty '+key+' list required')
            parts=[when(row,values,regions,depth+1) for row in condition[key]]
            return np.logical_and.reduce(parts) if key=='all' else np.logical_or.reduce(parts)
    if 'not' in keys:require(keys=={'not'},'Bare not required');return ~when(condition['not'],values,regions,depth+1)
    if 'region' in keys:
        require(keys=={'region'} and condition['region'] in regions,'Unknown region: '+str(condition['region']))
        return when(regions[condition['region']],values,regions,depth+1)
    if 'mask' in keys:require(keys=={'mask'},'Bare mask required');return values['mask:'+str(condition['mask'])]
    if 'channel' in keys:
        require(keys=={'channel'} and type(condition['channel']) is int and 0<=condition['channel']<=9,'Channel 0..9 required')
        return values['channel']==condition['channel']
    if 'mapped' in keys:
        require(keys=={'mapped'} and type(condition['mapped']) is bool,'Boolean mapped required')
        return values['mapped'] if condition['mapped'] else ~values['mapped']
    bounds=keys-{'of','center'}
    require('of' in keys and bounds and bounds<=set(COMPARE),'Comparison needs of plus gt/lt/ge/le')
    value=values[condition['of']]
    if 'center' in keys:value=np.abs(value-float(condition['center']))
    result=np.ones(value.shape,bool)
    for key in bounds:
        require(type(condition[key]) in (int,float),'Numeric bound required');result&=COMPARE[key](value,condition[key])
    return result


def face_mask(uv, selected, size):
    image=Image.new('L',(size,size));draw=ImageDraw.Draw(image)
    for face in np.flatnonzero(selected):draw.polygon([(u*size,v*size) for u,v in uv[face]],fill=255)
    return np.asarray(image)>0


def adjacency(positions, faces):
    """Edge-sharing faces after welding by position: UV seams split vertices but do not split the surface."""
    _,welded=np.unique(np.round(positions,6),axis=0,return_inverse=True);corners=welded.reshape(-1)[faces]
    edges=np.sort(np.stack([corners[:,[0,1]],corners[:,[1,2]],corners[:,[2,0]]],1).reshape(-1,2),1)
    _,edge=np.unique(edges,axis=0,return_inverse=True);owner=np.repeat(np.arange(len(faces)),3)
    incidence=coo_matrix((np.ones(len(owner),np.int32),(edge.reshape(-1),owner)),shape=(edge.max()+1,len(faces))).tocsr()
    result=(incidence.T@incidence).tolil();result.setdiag(0);result=result.tocsr();result.eliminate_zeros();return result


def frame(value):
    positions,faces=value['positions'],value['faces'];lo,hi=positions.min(0),positions.max(0)
    return positions[faces].mean(1),lo,hi


def crest_faces(value, rgb, op):
    """Raised midline strands above a per-slab skull envelope, grown through light-gray untextured neighbours.
    Head frame: x lateral, y up, z front; angles are about a pivot at pivotHeight of the bbox, 0 = straight back."""
    centre,lo,hi=frame(value);uv=np.asarray(value['uv']);size=len(rgb);width,height=hi[0]-lo[0],hi[1]-lo[1]
    mid=(lo[0]+hi[0])/2;lateral=np.abs(centre[:,0]-mid)
    dy=centre[:,1]-(lo[1]+op['pivotHeight']*height);dz=centre[:,2]-(lo[2]+hi[2])/2
    radius,angle=np.hypot(dy,dz),np.degrees(np.arctan2(dy,-dz))  # 0 = straight back, 90 = up
    low,high=op['angleRange'];upper=(lateral<op['midlineHalfWidth']*width)&(angle>low)&(angle<high)
    slab=np.floor((centre[:,0]-lo[0])/(op['slabWidth']*width)).astype(int)
    _,cell=np.unique(np.c_[np.floor(angle/op['angleBinDegrees']).astype(int),slab],axis=0,return_inverse=True);cell=cell.reshape(-1)
    envelope=np.full(cell.max()+1,np.inf);np.minimum.at(envelope,cell[upper],radius[upper]);skull=envelope[cell]
    band=upper&(radius>skull+op['envelopeClearance']*height)
    grow=op.get('grow',{});grown=0
    if grow.get('rounds',0):
        pixel=(uv.mean(1)*size).astype(int).clip(0,size-1);colour=rgb[pixel[:,1],pixel[:,0]].astype(float)
        gray=(colour.mean(1)>grow['grayMinimumLuminance'])&(colour.max(1)-colour.min(1)<grow['grayMaximumSpread'])
        eligible=gray&(lateral<grow['halfWidth']*width)&(radius>skull-grow['skullTolerance']*height);neighbours=adjacency(value['positions'],value['faces'])
        for _ in range(grow['rounds']):
            add=eligible&~band&(neighbours@band.astype(np.int32)>0)
            if not add.any():break
            band|=add;grown+=int(add.sum())
    stripe=band&(lateral<op['stripeHalfWidth']*width) if 'stripeHalfWidth' in op else np.zeros_like(band)
    return band,stripe,grown


def crest(value, rgb, op, report):
    """Paint the crest faces' untextured texels (not already dark or red) with grain; the central stripe separately."""
    band,stripe,grown=crest_faces(value,rgb,op);uv=np.asarray(value['uv']);size=len(rgb)
    masks={op['name']:face_mask(uv,band,size)};masks[op['name']+'-stripe']=face_mask(uv,stripe,size)
    rgbf=rgb.astype(float);lum=rgbf.mean(2);keep=op.get('preserve',{})
    untextured=~((lum<keep.get('darkBelow',-1))|((rgbf[...,0]-rgbf[...,1:].max(-1))>keep.get('redAbove',np.inf)))
    grain=np.random.default_rng(op.get('grainSeed',0)).normal(0,op.get('grainSigma',0),rgb.shape[:2])
    painted={}
    for name,colour in ((op['name'],op['color']),(op['name']+'-stripe',op.get('stripeColor'))):
        if colour is None:continue
        selected=masks[name]&untextured;rgb[selected]=np.clip(np.asarray(colour,float)+grain[selected][:,None],0,255)
        painted[name]=int(selected.sum())
    report.update(faces=int(band.sum()),grownFaces=grown,stripeFaces=int(stripe.sum()),paintedTexels=painted)
    return masks


def fill(value, rgb, op, report, texels, regions):
    """Paint selected faces flat over their own texels and the padding nearest to them; the colour is literal or the
    median of a mapped texel region outside those faces."""
    centre,lo,hi=frame(value);rel=(centre-lo)/(hi-lo);uv=np.asarray(value['uv'])
    pixel=(uv.mean(1)*len(rgb)).astype(int).clip(0,len(rgb)-1)
    faces=colour_values(rgb[pixel[:,1],pixel[:,0]],{'x':lambda:rel[:,0],'y':lambda:rel[:,1],'z':lambda:rel[:,2],'index':lambda:np.arange(len(rel))})
    selected=when(op['faces'],faces,regions);require(selected.any(),'Fill selects no faces: '+op['name'])
    values=texels();mask=selected[values['nearest']];colour=op['color']
    if isinstance(colour,dict):
        sample=when(colour['median'],values,regions)&values['mapped']&~mask
        require(sample.any(),'Empty median sample: '+op['name']);colour=np.rint(np.median(rgb[sample],axis=0)).astype(int).tolist()
        report['medianSamples']=int(sample.sum())
    require(len(colour)==3 and all(type(c) is int and 0<=c<=255 for c in colour),'Fill colour must be three bytes')
    rgb[mask]=colour;report.update(faces=int(selected.sum()),color=colour,paintedTexels=int(mask.sum()))
    return {op['name']:mask}


def texel_values(value, rgb, owners, extra=None):
    mapped=owners>=0;centre,lo,hi=frame(value);rel=(centre-lo)/(hi-lo)
    def axis(i):
        result=np.full(owners.shape,-1.0);result[mapped]=rel[owners[mapped],i];return result
    factories={'x':lambda:axis(0),'y':lambda:axis(1),'z':lambda:axis(2),'mapped':lambda:mapped,'face':lambda:owners}
    factories.update(extra or {});return colour_values(rgb,factories)


def texel_source(value, rgb):
    """Texel quantities of the current (mutated) colour map; the face raster and nearest-owner map are built once."""
    cache={}
    def texels():
        if 'owners' not in cache:
            owners=cache['owners']=raster_audit(value['uv'],len(rgb))[1];require((owners>=0).any(),'No mapped texture samples')
            cache['nearest']=owners[tuple(distance_transform_edt(owners<0,return_distances=False,return_indices=True))]
        return texel_values(value,rgb,cache['owners'],{'nearest':lambda:cache['nearest']})
    return texels


def paint(source, color, config, output):
    """Apply configured recolor/fill operations in order; each emits a 4K face mask for review and ownership rules."""
    value=mesh(source);rgb=np.asarray(Image.open(color).convert('RGB')).copy()
    require(rgb.shape==(4096,4096,3),'Paint source must be an actual 4096x4096 colour map')
    operations=config.get('operations');require(isinstance(operations,list) and operations,'Configured paint operations required')
    output=Path(output);output.mkdir(parents=True,exist_ok=False);texels=texel_source(value,rgb);regions=config.get('regions',{})
    masks={};reports=[]
    for op in operations:
        require(op.get('op') in ('crest','fill') and isinstance(op.get('name'),str) and op['name'].replace('-','').isalnum(),'Named crest/fill operation required')
        report={'op':op['op'],'name':op['name']}
        created=crest(value,rgb,op,report) if op['op']=='crest' else fill(value,rgb,op,report,texels,regions)
        require(not set(created)&set(masks),'Duplicate paint mask name');masks.update(created);reports.append(report)
    image=Image.fromarray(rgb);files={}
    for size in (4096,2048,1024):
        path=output/f'basecolor-{size}.png';(image if size==4096 else image.resize((size,size),Image.Resampling.BOX)).save(path);files[path.name]=pin(path)
    pins={}
    for name,mask in masks.items():
        path=output/f'{name}-faces-4096.png';Image.fromarray(mask.astype(np.uint8)*255).save(path);pins[name]=pin(path)
    result={'source':pin(source),'color':pin(color),'maps':files,'masks':pins,'operations':reports,'visualReviewRequired':True}
    write(output/'paint.json',result,fresh=True);return result


def rule_ownership(source, color, config, *, metallic=None, masks=None):
    """First matching rule wins (list order is priority); padding takes the label of the nearest mapped texel."""
    value=mesh(source);rgb=np.asarray(Image.open(color).convert('RGB'))
    require(rgb.shape[0]==rgb.shape[1],'Rule ownership needs a square colour atlas')
    extra={'mask:'+name:(lambda path=path:np.asarray(Image.open(path).convert('L'))>0) for name,path in (masks or {}).items()}
    if metallic is not None:extra['metallic']=lambda:np.asarray(Image.open(metallic).convert('L'))
    values=texel_values(value,rgb,raster_audit(value['uv'],len(rgb))[1],extra);mapped=values['mapped']
    default=config.get('default',0);require(type(default) is int and 0<=default<=9,'Default channel 0..9 required')
    labels=np.full(mapped.shape,default,np.uint8);free=np.ones(mapped.shape,bool);counts=[]
    for rule in config['rules']:
        require(type(rule.get('channel')) is int and 0<=rule['channel']<=9 and isinstance(rule.get('name'),str),'Named rule with channel 0..9 required')
        selected=when(rule['when'],values,config.get('regions',{}))&free&mapped;labels[selected]=rule['channel'];free&=~selected
        counts.append({'name':rule['name'],'channel':rule['channel'],'texels':int(selected.sum())})
    labels=labels[tuple(distance_transform_edt(~mapped,return_distances=False,return_indices=True))]
    return labels,{'rules':counts,'defaultTexels':int((free&mapped).sum()),'channels':{str(k):int(n) for k,n in enumerate(np.bincount(labels.reshape(-1),minlength=10)) if n}}


def adjust(color, ownership, config, palettes, output):
    """Per-channel colour operations without a reference image; no operations is an explicit pass-through.
    Conditions read the input colour and ownership, so operation order only matters where selections overlap."""
    rgb=np.asarray(Image.open(color).convert('RGB'));result=rgb.copy()
    with Image.open(ownership) as image:
        require(image.mode=='L','Ownership masks must be eight-bit L images');labels=np.asarray(image).copy()
    require(labels.shape==rgb.shape[:2] and np.all(labels<=9),'Discrete 0..9 ownership required')
    values=colour_values(rgb,{'channel':lambda:labels});report=[]
    for op in config.get('operations',[]):
        selected=when(op['when'],values,config.get('regions',{}))
        if op['op']=='set':
            colour=op['color'];require(len(colour)==3 and all(type(c) is int and 0<=c<=255 for c in colour),'Set colour must be three bytes')
            result[selected]=colour
        else:
            # Keep each texel's brightness, take its hue from a stock palette row (nearest scaled row luminance).
            require(op['op']=='paletteRamp' and op.get('palette') in palettes,'Unknown adjust operation or palette')
            table=np.asarray(Image.open(palettes[op['palette']]).convert('RGB'))
            require(type(op['row']) is int and 0<=op['row']<len(table) and table.shape[1]==256,'Invalid stock palette row')
            ramp=table[op['row'],:255].astype(float);brightness=ramp.mean(1)
            unique,inverse=np.unique(values['lum'][selected],return_inverse=True)
            pick=np.abs(unique[:,None]*float(op.get('luminanceScale',1))-brightness[None,:]).argmin(1)
            result[selected]=ramp[pick[inverse.reshape(-1)]].astype(np.uint8)
        report.append({'op':op['op'],'texels':int(selected.sum())})
    Image.fromarray(result).save(output)
    return {'source':pin(color),'ownership':pin(ownership),'output':pin(output),'mode':'adjust','operations':report}
