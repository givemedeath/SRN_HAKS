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


def finish_bake(linear_path, masks_path, output):
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
    srgb = np.where(padded <= .0031308, 12.92*padded, 1.055*np.power(padded, 1/2.4)-.055)
    image = Image.fromarray(np.flipud(np.rint(srgb*255).astype(np.uint8)), 'RGB')
    output = Path(output); output.mkdir(parents=True, exist_ok=False); maps = {}
    for size in (4096, 2048, 1024, 512):
        path = output/f'diffuse-{size}.png'
        (image if size == 4096 else image.resize((size, size), Image.Resampling.BOX)).save(path)
        maps[str(size)] = pin(path)
    return {'maps': maps, 'visibleMisses': 0, 'mappedColoursPreserved': not any(normalization['clippedValuesByChannel']),
            'mappedColoursPreservedAfterFloatRangeNormalization':True,'floatRangeNormalization':normalization}
