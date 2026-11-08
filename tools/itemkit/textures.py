"""Only unmapped padding is extended; visible bake failures remain failures."""
from pathlib import Path
import numpy as np
from PIL import Image
from tools.headkit.common import require, pin


def normalize_source_colour(values):
    require(np.isfinite(values).all(),'Nonfinite source colour')
    low=float(values.min());high=float(values.max());tolerance=1e-5
    require(low>=-tolerance and high<=1+tolerance,'Out-of-range source colour exceeds floating-point tolerance')
    counts=np.count_nonzero((values<0)|(values>1),axis=tuple(range(values.ndim-1))).tolist()
    return np.clip(values,0,1),{'tolerance':tolerance,'rawMinimum':low,'rawMaximum':high,'clippedValuesByChannel':counts}


def material_palette(pixels,mapped,palettes):
    """Author constant-material cells only in reserved, unmapped atlas space."""
    require(isinstance(palettes,(list,tuple)) and len(palettes)<=8,'Bounded uniform material palette required')
    require(pixels.ndim==3 and pixels.shape[2]==3 and mapped.shape==pixels.shape[:2]
            and mapped.dtype==bool,'RGB atlas and mapped-texel mask required')
    height,width=mapped.shape;planned=[];names=set()
    for row in palettes:
        require(isinstance(row,dict) and set(row)=={'name','uvMin','uvMax','linearColour'},'Explicit uniform palette cell required')
        low=np.asarray(row['uvMin'],float);high=np.asarray(row['uvMax'],float);colour=np.asarray(row['linearColour'],float)
        require(isinstance(row['name'],str) and row['name'] and row['name'] not in names
                and low.shape==high.shape==(2,) and colour.shape==(3,) and np.isfinite([low,high]).all()
                and np.isfinite(colour).all() and np.all(low>=0) and np.all(high<=1) and np.all(low<high)
                and np.all((colour>=0)&(colour<=1)),'Finite unique uniform palette cell required')
        names.add(row['name']);x0,y0=np.floor(low*[width,height]).astype(int);x1,y1=np.ceil(high*[width,height]).astype(int)
        require(not mapped[y0:y1,x0:x1].any(),'Uniform material palette overlaps mapped source colour')
        require(all(x1<=p[0] or p[2]<=x0 or y1<=p[1] or p[3]<=y0 for p in planned),
                'Uniform material palette cells overlap')
        planned.append((x0,y0,x1,y1,colour,row))
    records=[]
    for x0,y0,x1,y1,colour,row in planned:
        pixels[y0:y1,x0:x1]=colour
        records.append({**row,'pixelBounds':[int(x0),int(y0),int(x1),int(y1)]})
    return records


def finish_bake(linear_path, masks_path, output, *, palettes=()):
    from tools.headkit.textures import pad
    values = np.load(linear_path, allow_pickle=False)
    with np.load(masks_path, allow_pickle=False) as masks:
        require(set(masks.files) == {'owners', 'hiddenCaps', 'visibleMisses'}, 'Explicit bake classification required')
        mapped = masks['owners'] >= 0
        require(values.shape == (*mapped.shape, 3) and mapped.shape == (4096, 4096), 'Expected 4K RGB source bake')
        require(not masks['visibleMisses'].any(), 'Visible bake misses cannot be padded')
    values,normalization=normalize_source_colour(values)
    padded = pad(values, mapped)
    require(np.array_equal(padded[mapped], values[mapped]), 'Padding changed a mapped surface colour')
    palette=material_palette(padded,mapped,palettes)
    srgb = np.where(padded <= .0031308, 12.92*padded, 1.055*np.power(padded, 1/2.4)-.055)
    image = Image.fromarray(np.flipud(np.rint(srgb*255).astype(np.uint8)), 'RGB')
    output = Path(output); output.mkdir(parents=True, exist_ok=False); maps = {}
    for size in (4096, 2048, 1024, 512):
        path = output/f'diffuse-{size}.png'
        (image if size == 4096 else image.resize((size, size), Image.Resampling.BOX)).save(path)
        maps[str(size)] = pin(path)
    return {'maps': maps, 'visibleMisses': 0, 'mappedColoursPreserved': not any(normalization['clippedValuesByChannel']),
            'mappedColoursPreservedAfterFloatRangeNormalization':True,'floatRangeNormalization':normalization,
            'uniformMaterialPalette':palette}
