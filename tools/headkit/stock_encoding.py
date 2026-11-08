"""Validated import of approved PLT indices after a source-bound local mesh repair."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from .common import require,pin,write,verify
from .gltf import mesh
from .local_seal import geometry_fingerprint
from .palette import FULL_RANGE_PIXELS,FULL_RANGE_SPAN,FLAT_LUMA



def body_calibration(source,shades,layers,body_skin):
    from .palette import body_skin_median
    from .uv import face_region,raster_audit
    value=mesh(source);front=face_region(value['positions'],value['faces'])[0]
    owners=raster_audit(value['uv'],1024)[1]
    chosen=(owners>=0)&(layers==0)&front[np.maximum(owners,0)]
    require(chosen.sum()>=FULL_RANGE_PIXELS,'Too few preserved face-skin texels for body calibration')
    return {'target':body_skin_median(body_skin),'achieved':float(np.median(shades[chosen])),
            'faceTexels':int(chosen.sum()),'preserved':True}

def preserve(color,ownership,palette_files,rows,source,output,*,full_range=False,body_skin=None):
    """Preserve indices exactly; refuse stale geometry, rows, ownership or decoded colour."""
    inputs=[pin(p) for p in [color,ownership,source,*palette_files.values(),*([body_skin] if body_skin else [])]]
    require(isinstance(rows,dict) and all(type(v) is int for v in rows.values()),
            'Preserving stock encoding requires explicit palette rows')
    with np.load(color,allow_pickle=False) as data:
        require(str(data['kind'])=='headkit-stock-runtime-v1','Not a stock runtime encoding package')
        require(str(data['geometryFingerprint'])==geometry_fingerprint(mesh(source)),'Stock encoding geometry changed')
        require(json.loads(str(data['rows']))==rows,'Stock encoding palette rows changed')
        shades,layers,rgb=(data[key].copy() for key in ('shades','layers','rgb'))
    require(shades.dtype==layers.dtype==rgb.dtype==np.uint8 and shades.shape==layers.shape==(1024,1024)
            and rgb.shape==(1024,1024,3),'Stock runtime encoding must be uint8 at 1K')
    require(np.max(layers)<=9 and np.max(shades)<255,'Invalid stock layer/shade')
    with Image.open(ownership) as image:
        require(image.mode=='L' and np.array_equal(np.asarray(image),layers),'Stock encoding ownership changed')
    report={};tables={}
    for channel in np.unique(layers):
        key=str(int(channel));require(key in rows and key in palette_files,'Missing stock channel '+key)
        with Image.open(palette_files[key]) as image:palette=np.asarray(image.convert('RGBA'))
        row=rows[key];require(palette.shape[1]==256 and 0<=row<len(palette),'Invalid stock palette row')
        selected=layers==channel;picked=shades[selected];table=palette[row]
        eligible=(table[:,3]>0)&(np.roll(table[:,3],-1)>0)&(np.arange(256)<255)
        require(eligible[picked].all(),'Stock shade can interpolate into transparency')
        require(np.array_equal(table[picked,:3],rgb[selected]),'Stored stock decode disagrees with the palette')
        lo,hi=np.flatnonzero(eligible)[[0,-1]]
        luma=rgb[selected].astype(float)@np.array([.299,.587,.114])
        varied=float(np.ptp(np.percentile(luma,[1,99])))>=FLAT_LUMA
        checked=full_range and varied and len(picked)>=FULL_RANGE_PIXELS
        p1,p99=np.percentile(picked,[1,99]);span=float(p99-p1)/max(int(hi)-int(lo),1)
        require(not checked or span>=FULL_RANGE_SPAN,'Preserved stock channel '+key+' fails the shade range floor')
        report[key]={'pixels':int(selected.sum()),'preserved':True,'shadeRange':{
            'eligible':[int(lo),int(hi)],'p1':float(p1),'p99':float(p99),'spanFraction':round(span,3),'checked':checked}}
        tables[key]=table[:,:3]
    if body_skin is not None:
        require('0' in report,'Body-pinned stock encoding needs a skin channel')
        report['0']['shadeRange']['skinMedian']=body_calibration(source,shades,layers,body_skin)
    verify(inputs,fresh=True)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    for name,array in [('shades',shades),('layers',layers),('decoded',rgb)]:Image.fromarray(array).save(output/(name+'.png'))
    isolation=[]
    for key in tables:
        image=rgb.copy();image[layers==int(key)]=[255,0,255]
        path=output/('isolate-'+key+'.png');Image.fromarray(image).save(path);isolation.append(pin(path))
    result={'layers':report,'isolation':isolation,'shades':pin(output/'shades.png'),'ownership':pin(output/'layers.png'),
            'decoded':pin(output/'decoded.png'),'rows':rows,'visualReviewRequired':True,
            'preservedStockEncoding':{'input':inputs[0],'geometryFingerprint':geometry_fingerprint(mesh(source)),
                                      'reprocessedTexels':0}}
    write(output/'palette.json',result,fresh=True);return result
