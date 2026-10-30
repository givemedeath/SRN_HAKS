"""Automatic face quality gate on the quantized PLT before any client check (step 5 of docs/heads/head-texture-quality-plan.md).

Everything is measured on the head's own front render (from the masks stage) at game size, a FACE_PX-wide face, decoded with
hair row 117 and tattoo1 row 26 (skin and the rest at the palette's rows). Limits live in quality-thresholds.json, calibrated on
elf-male-c/-d shipped (fail) vs prototypes (pass) with elf-male-a held out (RUNBOOK 132-134)."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from scipy.ndimage import label, binary_dilation, binary_erosion, binary_opening
from .common import require, pin, write, read
from .gltf import mesh
from .face_masks import EYE_RING, IRIS, BROWS, LIPS, polygon, face_hull, plain_skin, hair_locks, sample, nearest

THRESHOLDS = Path(__file__).with_name('quality-thresholds.json')
FACE_PX = 100; DECODE_ROWS = {'1': 117, '8': 26}; TOP = 12
CROSS = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
CHECKS = {'featureFocusMin', 'blotchPxMax', 'specksMax', 'hairLockOnSkinPxMax', 'designSpecksWarn', 'browsOnHairMin', 'irisOnTattoo1Min',
          'whitesOnSkinMin', 'hairOnFaceSkinMax', 'shadeSpanMin'}
LIP_POLYGON = (61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146)


def eligible(row):
    """First and last shade of a palette row that is opaque and has an opaque successor (never 255 next to transparency)."""
    ok = (row[:, 3] > 0) & (np.roll(row[:, 3], -1) > 0) & (np.arange(256) < 255); index = np.flatnonzero(ok)
    return (int(index.min()), int(index.max())) if len(index) else (0, 254)


def quality(source, masks, palette, palettes, output, thresholds=None):
    """masks: the masks stage result; palette: the palette stage result; palettes: {layer: palette image path}."""
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    limits = thresholds if thresholds is not None else read(THRESHOLDS)['limits']; require(set(limits) == CHECKS, 'Incomplete quality thresholds')
    require(masks['source']['sha256'] == pin(source)['sha256'], 'Quality must read the masks of this UV mesh')
    files = masks['files']; value = mesh(source); uv = value['uv'].astype(float)
    with np.load(files['frontView']['path']) as data: view = {k: data[k] for k in ('hit', 'face', 'bary')}
    pts = np.load(files['frontLandmarks']['path'])
    with Image.open(files['frontLabels']['path']) as image: labels = np.asarray(image)
    with Image.open(files['frontRender']['path']) as image: render = np.asarray(image.convert('RGB'))
    with Image.open(palette['shades']['path']) as image: shades = np.asarray(image)
    with Image.open(palette['ownership']['path']) as image: layers = np.asarray(image)
    rows = {str(k): v for k, v in palette['rows'].items()}; tables = {}
    for layer, path in palettes.items():
        with Image.open(path) as image: tables[str(layer)] = np.asarray(image.convert('RGBA'))
    S = labels.shape[0]; ys, xs = np.mgrid[0:S, 0:S]; width = np.ptp(pts[:, 0]); scale = FACE_PX/width
    x0, x1 = int(pts[:, 0].min()-.05*width), int(pts[:, 0].max()+.05*width); y0, y1 = int(pts[:, 1].min()-.12*width), int(pts[:, 1].max()+.03*width)

    def small(a, exact=False):
        return np.asarray(Image.fromarray(a[y0:y1, x0:x1]).resize((int((x1-x0)*scale), int((y1-y0)*scale)), Image.Resampling.NEAREST if exact else Image.Resampling.BOX))
    def mask(a): return small(a.astype(np.uint8)*255, True) > 127

    # Regions from the render's landmarks and labels.
    face = face_hull(labels.shape, pts); eyes = polygon(labels.shape, pts, EYE_RING['R']) | polygon(labels.shape, pts, EYE_RING['L'])
    iris = np.zeros((S, S), bool)
    for c, ring in IRIS.values(): iris |= np.hypot(xs-pts[c, 0], ys-pts[c, 1]) < .8*np.linalg.norm(pts[list(ring)]-pts[c], axis=1).mean()
    iris &= eyes; whites = eyes & ~binary_dilation(iris, iterations=4); brows = np.isin(labels, BROWS); plain = plain_skin(labels, face, eyes)
    cheeks = np.zeros((S, S), bool)
    for i in (50, 280): cheeks |= np.hypot(xs-pts[i, 0], ys-pts[i, 1]) < .07*width
    features = eyes | polygon(labels.shape, pts, LIP_POLYGON) | brows
    locks = hair_locks(render, labels, view['hit'], face, plain)
    # Decoded colour and exact channels at every rendered pixel.
    decoded = np.zeros(shades.shape+(3,), np.float32)
    for k in np.unique(layers):
        table = tables.get(str(k), tables['0']); row = DECODE_ROWS.get(str(k), rows.get(str(k), 0)); row = 0 if row == 'auto' else int(row)
        selected = layers == k; decoded[selected] = table[row, shades[selected], :3]
    rgb = sample(view, decoded, uv); channel = nearest(view, layers, uv); shade = nearest(view, shades, uv)
    luma = small((rgb@np.array([.299, .587, .114], np.float32)).astype(np.float32))
    high = np.zeros_like(luma); high[1:-1, 1:-1] = luma[1:-1, 1:-1]-(luma[:-2, 1:-1]+luma[2:, 1:-1]+luma[1:-1, :-2]+luma[1:-1, 2:])/4
    # Cheek pixels whose 4 neighbours are skin too, so design lines on a cheek do not count as skin noise.
    cheek = binary_erosion(mask((np.rint(sample(view, layers.astype(np.float32)[..., None], uv)[..., 0]) == 0) & view['hit']), CROSS) & mask(cheeks)
    feature = mask(features); r = {}
    require(cheek.any() and feature.any(), 'No cheek or feature pixels at game size')
    r['cheekNoise'] = round(float(high[cheek].std()), 2); r['featureFocus'] = round(float(high[feature].std()/max(high[cheek].std(), 1e-6)), 2)
    # Blotch: largest patch of top skin shades on plain skin, opened 2x2 so 1 px highlight rims are not blotches.
    top = eligible(tables['0'][0 if rows.get('0', 0) == 'auto' else int(rows.get('0', 0))])[1]-TOP
    parts, n = label(binary_opening(small((plain & (channel == 0) & (shade >= top)).astype(np.uint8)*255) > 127, np.ones((2, 2))))
    r['blotchPx'] = int(np.bincount(parts.ravel())[1:].max()) if n else 0
    share = lambda region, layer: round(float(np.isin(channel[region], layer).mean()), 3) if region.any() else None
    r['browsOnHair'] = share(brows, (1,)); r['irisOnTattoo1'] = share(iris, (8,)); r['whitesOnSkin'] = share(whites, (0,))
    r['hairOnFaceSkin'] = share(plain & ~locks if locks is not None else plain, (1,))
    r['hairLockOnSkinPx'] = None
    if locks is not None:
        parts, n = label(small((locks & (channel == 0)).astype(np.uint8)*255) > 127, np.ones((3, 3))); r['hairLockOnSkinPx'] = int(np.bincount(parts.ravel())[1:].max()) if n else 0
    # Specks: 1-2 px channel islands inside the face at game size. Skin/hair/iris islands are ownership speckle; tattoo2/metal
    # islands are thin design marks breaking up (a design matter, warning only). Islands touching the face outline are the hull
    # clipping a hair/skin edge (face-edge locks, RUNBOOK 138), not speckle, and do not count.
    game = small(np.where(face, channel, 255).astype(np.uint8), True).astype(int); inside = mask(face); r['specks'] = r['designSpecks'] = 0
    outline = inside & ~binary_erosion(inside, np.ones((3, 3)))
    for k in np.unique(game[inside]):
        if k == 255: continue
        parts, n = label((game == k) & inside, np.ones((3, 3)))
        if not n: continue
        small_parts = np.bincount(parts.ravel()) <= 2; small_parts[0] = False; small_parts[np.unique(parts[outline])] = False
        r['specks' if k in (0, 1, 8) else 'designSpecks'] += int(small_parts.sum())
    r['shadeSpan'] = {}
    for k in np.unique(layers):
        values = shades[layers == k]
        if len(values) < 1024: continue
        row = rows.get(str(k), 0); lo, hi = eligible(tables.get(str(k), tables['0'])[0 if row == 'auto' else int(row)])
        r['shadeSpan'][str(k)] = round(float((np.percentile(values, 99)-np.percentile(values, 1))/max(hi-lo, 1)), 3)
    fails = [name for name, ok in (('featureFocus', r['featureFocus'] >= limits['featureFocusMin']), ('blotch', r['blotchPx'] <= limits['blotchPxMax']),
             ('specks', r['specks'] <= limits['specksMax']), ('hairLockOnSkin', (r['hairLockOnSkinPx'] or 0) <= limits['hairLockOnSkinPxMax']),
             ('browsOnHair', (r['browsOnHair'] or 0) >= limits['browsOnHairMin']), ('irisOnTattoo1', (r['irisOnTattoo1'] or 0) >= limits['irisOnTattoo1Min']),
             ('whitesOnSkin', (r['whitesOnSkin'] or 0) >= limits['whitesOnSkinMin']),
             ('hairOnFaceSkin', r['hairOnFaceSkin'] is None or r['hairOnFaceSkin'] <= limits['hairOnFaceSkinMax'])) if not ok]
    fails += [f'shadeSpan{k}' for k, v in r['shadeSpan'].items() if v < limits['shadeSpanMin']]
    warnings = [f"{r['designSpecks']} design-channel specks: thin marks break up at game size"] if r['designSpecks'] > limits['designSpecksWarn'] else []
    preview = np.repeat(np.clip(luma, 0, 255).astype(np.uint8)[..., None], 3, 2)
    Image.fromarray(preview).resize((preview.shape[1]*3, preview.shape[0]*3), Image.Resampling.NEAREST).save(output/'game-size.png')
    result = {'source': pin(source), 'masks': masks['files']['frontView'], 'palette': palette['shades'], 'limits': limits, 'metrics': r,
              'failed': fails, 'warnings': warnings, 'passed': not fails, 'decodeRows': DECODE_ROWS, 'preview': pin(output/'game-size.png'),
              'visualReviewRequired': True}
    write(output/'quality.json', result, fresh=True)
    require(not fails, 'Face quality gate failed: '+', '.join(fails)+' (see quality.json)')
    return result
