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


def sharpen_policy(settings):
    """A reviewed unsharp mask for the derived maps: `radius` in texels of each map, `amount` 0-1."""
    require(isinstance(settings, dict) and set(settings) == {'radius', 'amount'}
            and all(type(settings[key]) in (int, float) for key in settings)
            and .3 <= settings['radius'] <= 2 and 0 < settings['amount'] <= 1,
            'Texture sharpening needs a radius of 0.3-2 texels and an amount up to 1')
    return {'radius': float(settings['radius']), 'amount': float(settings['amount'])}


def metal_policy(settings):
    """How the baked metallic map changes the game texture. `darken`: the colour factor on full metal (1 leaves it; the
    generator gives metal a bright albedo that the game, which has no metal shading, shows as pale steel). `reflection`:
    how far full metal lowers the texture's alpha, which the game uses as its environment-map mask the way the base
    game's own metal textures do (0 writes no alpha at all)."""
    require(isinstance(settings, dict) and set(settings) == {'darken', 'reflection'}
            and all(type(settings[key]) in (int, float) for key in settings)
            and .3 <= settings['darken'] <= 1 and 0 <= settings['reflection'] <= .6
            and (settings['darken'] < 1 or settings['reflection'] > 0),
            'Metal treatment needs darken 0.3-1 and reflection 0-0.6, and one of them must change something')
    return {'darken': float(settings['darken']), 'reflection': float(settings['reflection'])}


def finish_bake(linear_path, masks_path, output, *, palettes=(), sharpen=None, metal=None, metallic_path=None):
    """`sharpen` (sharpen_policy) is applied to each derived map after it is reduced: the 4K bake is box-filtered down,
    which softens every edge the donor drew. The padded image is sharpened, so an island's edge is compared with its
    own extended colour and never with empty atlas; the 4K source map stays exactly the bake."""
    from PIL import ImageFilter
    if sharpen is not None: sharpen = sharpen_policy(sharpen)
    require((metal is None) == (metallic_path is None), 'A metal treatment and a baked metallic map go together')
    if metal is not None: metal = metal_policy(metal)
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
    alpha = None; metal_report = None
    if metal is not None:
        layer = np.load(metallic_path, allow_pickle=False)
        require(layer.shape == mapped.shape, 'Expected a 4K metallic bake')
        known = mapped & np.isfinite(layer); require(known.sum() >= .98*mapped.sum(), 'The metallic bake missed too much of the surface')
        layer = np.clip(pad(np.where(known, layer, 0), known), 0, 1)
        padded = padded * (1 - layer*(1 - metal['darken']))[..., None]
        if metal['reflection']: alpha = Image.fromarray(np.flipud(np.rint((1 - metal['reflection']*layer)*255).astype(np.uint8)), 'L')
        metal_report = {**metal, 'metalFraction': float(layer[mapped].mean()), 'metallicTexelsFilled': int((mapped & ~known).sum()),
                        'alphaChannel': alpha is not None}
    palette=material_palette(padded,mapped,palettes)
    srgb = np.where(padded <= .0031308, 12.92*padded, 1.055*np.power(padded, 1/2.4)-.055)
    image = Image.fromarray(np.flipud(np.rint(srgb*255).astype(np.uint8)), 'RGB')
    output = Path(output); output.mkdir(parents=True, exist_ok=False); maps = {}
    for size in (4096, 2048, 1024, 512):
        path = output/f'diffuse-{size}.png'; derived = image
        if size != 4096:
            derived = image.resize((size, size), Image.Resampling.BOX)
            if sharpen: derived = derived.filter(ImageFilter.UnsharpMask(radius=sharpen['radius'], percent=round(sharpen['amount']*100), threshold=0))
        # The mask is reduced on its own and never sharpened: it is a reflection amount, not a drawn edge.
        if alpha is not None: derived = derived.copy(); derived.putalpha(alpha if size == 4096 else alpha.resize((size, size), Image.Resampling.BOX))
        derived.save(path); maps[str(size)] = pin(path)
    return {'maps': maps, 'visibleMisses': 0, 'derivedMapSharpening': sharpen, 'mappedColoursPreserved': not any(normalization['clippedValuesByChannel']),
            'mappedColoursPreservedAfterFloatRangeNormalization':True,'floatRangeNormalization':normalization,
            'uniformMaterialPalette':palette, 'metalTreatment': metal_report}
