"""Automatic face quality gate on the quantized PLT before any client check (step 5 of docs/heads/head-texture-quality-plan.md).

Everything is measured on the head's own front render (from the masks stage) at game size, a FACE_PX-wide face, decoded with
hair row 117 and tattoo1 row 26 (skin and the rest at the palette's rows). Limits live in quality-thresholds.json, calibrated on
elf-male-c/-d shipped (fail) vs prototypes (pass) with elf-male-a held out (RUNBOOK 132-134)."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from scipy.ndimage import label, binary_dilation, binary_erosion, binary_opening
from scipy.spatial import cKDTree
from .common import require, pin, write, read
from .gltf import mesh
from .face_masks import EYE_RING, EYES, IRIS, LIPS, NOSE_BASE, polygon, face_hull, brow_seed, brow_mask, plain_skin, hair_locks, sample, nearest

THRESHOLDS = Path(__file__).with_name('quality-thresholds.json')
FACE_PX = 100; DECODE_ROWS = {'1': 117, '8': 26}; TOP = 12
CROSS = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], bool)
CHECKS = {'featureFocusMin', 'blotchPxMax', 'specksMax', 'hairLockOnSkinPxMax', 'designSpecksWarn', 'browsOnHairMin', 'irisOnTattoo1Min',
          'whitesOnSkinMin', 'hairOnFaceSkinMax', 'shadeSpanMin', 'seamStepRatioMax', 'skinMedianOffsetMax', 'bodySkinSpanMin',
          'faceDarkRatioMin', 'hairEndTieExempt'}
SEAM_RADIUS = .012   # head widths: about 1.5 1K texels on the face, the neighbours a seam step is seen against
LIP_POLYGON = (61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146)


def eligible(row):
    """First and last shade of a palette row that is opaque and has an opaque successor (never 255 next to transparency)."""
    ok = (row[:, 3] > 0) & (np.roll(row[:, 3], -1) > 0) & (np.arange(256) < 255); index = np.flatnonzero(ok)
    return (int(index.min()), int(index.max())) if len(index) else (0, 254)


def shade_span_failures(spans, palette, minimum, body_minimum=None, hair_end_tie=None):
    """Failed shadeSpan checks and the exempt channels: a channel the palette left flat (shadeRange.checked false, its source
    luminance spread below FLAT_LUMA) has no span to keep, as quantize(full_range=True) itself exempts it. A skin pinned to the
    body skin's median (shadeRange.skinMedian) needs only `body_minimum`: when the face is the brightest skin, the capped highlights
    leave the top of the row unused (user decision 2026-10-31, RUNBOOK 154). Hair with more than `hair_end_tie` of its texels on the
    source luma value at its p1 or p99 (shadeRange.endTie) is exempt: rank order cannot spread one flat value (human-female-d,
    14% of its hair on one value, mostly UV gutters and the back of the head; user decision 2026-10-31, RUNBOOK 159)."""
    layers = palette.get('layers') or {}
    flat = {k for k, layer in layers.items() if (layer.get('shadeRange') or {}).get('checked') is False}
    if hair_end_tie is not None and ((layers.get('1') or {}).get('shadeRange') or {}).get('endTie', 0) > hair_end_tie: flat.add('1')
    limit = lambda k: body_minimum if body_minimum is not None and ((layers.get(k) or {}).get('shadeRange') or {}).get('skinMedian') else minimum
    return [f'shadeSpan{k}' for k, v in spans.items() if v < limit(k) and k not in flat], sorted(flat & set(spans))


def seam_step_ratio(points, charts, shades, width):
    """Mean skin shade difference between surface neighbours (within SEAM_RADIUS head widths) on different UV charts over that
    between neighbours on the same chart. Near 1 when shading runs on across seams; flat tone patches meeting at chart
    borders raise it (dwarf-female-c per-chart shading 1.47-1.55, surface shading 0.68-0.79 on outer faces; RUNBOOK 153, 164)."""
    pairs = cKDTree(points).query_pairs(SEAM_RADIUS*width, output_type='ndarray')
    if not len(pairs): return None
    step = np.abs(shades[pairs[:, 0]].astype(float)-shades[pairs[:, 1]]); cross = charts[pairs[:, 0]] != charts[pairs[:, 1]]
    return round(float(step[cross].mean()/max(step[~cross].mean(), 1e-6)), 3) if cross.any() and (~cross).any() else None


def skin_median_offset(palette):
    """How far the stretched skin's median shade landed from the body skin's (palette matchBodySkin): None when the skin was
    stretched without the body anchor (a face that reads as a different skin from the neck, RUNBOOK 154), 0 for a flat skin."""
    skin = ((palette.get('layers') or {}).get('0') or {}).get('shadeRange') or {}
    if not skin.get('checked'): return 0.0
    median = skin.get('skinMedian'); return None if median is None else abs(median['achieved']-median['target'])


def face_dark_ratio(palette, face_skin, plain_skin):
    """The darkest face skin shade (p1 of the front-visible face skin) over the plain skin's median, for a body-pinned skin
    (palette skinMedian; None otherwise): its stretch once sent lips, lip lines and sockets to shade 0, black on the skin rows
    (RUNBOOK 158)."""
    pinned = (((palette.get('layers') or {}).get('0') or {}).get('shadeRange') or {}).get('skinMedian')
    if not pinned or not len(face_skin) or not len(plain_skin): return None
    return round(float(np.percentile(face_skin, 1)/max(np.median(plain_skin), 1)), 3)


def quality(source, masks, palette, palettes, output, thresholds=None, settings=None, embree=None):
    """masks: the masks stage result; palette: the palette stage result; palettes: {layer: palette image path}; embree: the
    bound Embree DLL path (seam steps count outer faces only, RUNBOOK 164).
    settings (the manifest quality section): `cybereyeImageSide` 'left' or 'right' leaves that eye and brow out of the role
    checks (RUNBOOK 150): a cybereye housing has no iris, whites or brow for the parser to find."""
    settings = settings or {}; side = settings.get('cybereyeImageSide')
    require(set(settings) <= {'cybereyeImageSide'} and side in (None, 'left', 'right'), 'quality.cybereyeImageSide must be left or right')
    require(embree is not None, 'Quality needs the bound Embree runtime')
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
    # The landmark iris circle runs under the lids on narrow eyes: like the iris mask, count only the parser's eye opening
    # (RUNBOOK 146). Whites stay measured outside the full circle.
    iris &= eyes; whites = eyes & ~binary_dilation(iris, iterations=4); iris &= np.isin(labels, EYES); brows = brow_seed(labels, pts, eyes, view['hit'])
    # Plain skin also excludes the colour-grown brow edges, which ownership rightly puts on hair (RUNBOOK 147).
    plain = plain_skin(labels, face, eyes, brows | brow_mask(render, labels, brows, eyes, view['hit']))
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
    if side is not None:   # image left is the subject's right; the midline runs through the nose bridge (landmark 168)
        cyber = (xs < pts[168, 0]) if side == 'left' else (xs >= pts[168, 0]); brows, iris, whites = brows & ~cyber, iris & ~cyber, whites & ~cyber
        r['cybereyeImageSide'] = side
    share = lambda region, layer: round(float(np.isin(channel[region], layer).mean()), 3) if region.any() else None
    r['browsOnHair'] = share(brows, (1,)); r['irisOnTattoo1'] = share(iris, (8,)); r['whitesOnSkin'] = share(whites, (0,))
    # Above the nose only: below it the parser has no beard class and ownership keeps hair-coloured beards hair (RUNBOOK 145).
    upper = plain & (ys < pts[NOSE_BASE, 1]); r['hairOnFaceSkin'] = share(upper & ~locks if locks is not None else upper, (1,))
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
    from .textures import surface
    from .uv import chart_ids
    from .rays import outer_faces
    # Seam steps on outer faces only: the repaired shell is double-walled, and its hidden inner wall sits within SEAM_RADIUS of
    # the visible skin on other charts (83-90% of the cross-chart pairs on the race validation copies, RUNBOOK 164).
    positions = value['positions'].astype(float); outer, _ = outer_faces(embree, positions, value['faces'], float(np.ptp(positions[:, 1])))
    require(outer.any(), 'No outer faces: the UV mesh must face outward')
    points, owners, _ = surface(value, shades.shape[0], enforce=False); skin = (owners >= 0) & (layers == 0) & outer[np.maximum(owners, 0)]
    r['seamOuterFaces'] = int(outer.sum()); r['seamSkinTexels'] = int(skin.sum())
    r['seamStepRatio'] = seam_step_ratio(points[skin].astype(float), np.asarray(chart_ids(uv))[owners[skin]], shades[skin], float(np.ptp(value['positions'][:, 0])))
    r['skinMedianOffset'] = skin_median_offset(palette)
    r['faceDarkRatio'] = face_dark_ratio(palette, shade[face & view['hit'] & (channel == 0)], shade[plain & (channel == 0)])
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
             ('hairOnFaceSkin', r['hairOnFaceSkin'] is None or r['hairOnFaceSkin'] <= limits['hairOnFaceSkinMax']),
             ('seamStep', r['seamStepRatio'] is None or r['seamStepRatio'] <= limits['seamStepRatioMax']),
             ('bodySkin', r['skinMedianOffset'] is not None and r['skinMedianOffset'] <= limits['skinMedianOffsetMax']),
             ('faceDark', r['faceDarkRatio'] is None or r['faceDarkRatio'] >= limits['faceDarkRatioMin'])) if not ok]
    span_fails, r['shadeSpanExempt'] = shade_span_failures(r['shadeSpan'], palette, limits['shadeSpanMin'], limits['bodySkinSpanMin'], limits['hairEndTieExempt']); fails += span_fails
    warnings = [f"{r['designSpecks']} design-channel specks: thin marks break up at game size"] if r['designSpecks'] > limits['designSpecksWarn'] else []
    preview = np.repeat(np.clip(luma, 0, 255).astype(np.uint8)[..., None], 3, 2)
    Image.fromarray(preview).resize((preview.shape[1]*3, preview.shape[0]*3), Image.Resampling.NEAREST).save(output/'game-size.png')
    result = {'source': pin(source), 'masks': masks['files']['frontView'], 'palette': palette['shades'], 'limits': limits, 'metrics': r,
              'failed': fails, 'warnings': warnings, 'passed': not fails, 'decodeRows': DECODE_ROWS, 'preview': pin(output/'game-size.png'),
              'visualReviewRequired': True}
    write(output/'quality.json', result, fresh=True)
    require(not fails, 'Face quality gate failed: '+', '.join(fails)+' (see quality.json)')
    return result
