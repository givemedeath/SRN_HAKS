"""Condition an angled colour/clay reference pair and bind it to a fresh `<ID>.oblique-v1` manifest.

The pair is two images on a plain white background from the Codex image tool (`drive image DESIGN colour|clay`): the
weapon at the same angle, once in colour and once as smooth clay. This keys alpha from the white background (largest
component, enclosed highlight holes filled: only for designs without intended openings), measures how well the two
outlines overlay, and runs the archived pair conditioning (`reference_conditioning.prepare`, route
preserve-reviewed-pair-alpha). A pair that does not overlay is regenerated, never conditioned.

Two phases: the first keys and measures and stops for a person to look at the keyed pair; the second, given the
user's words and the two keyed-image hashes, conditions the pair and writes the background, pair and view approvals
with those words. The geometry stage still needs its own camera calibration.
"""
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
from PIL import Image
from tools.headkit.common import require

ROLES = {'reference': 'detail-foreground-native.png', 'clayReference': 'clay-foreground-native.png', 'geometry': 'clay-conditioning-2048.png',
         'detail': 'detail-conditioning-2048.png', 'foregroundMask': 'detail-mask-2048.png', 'geometryForegroundMask': 'clay-mask-2048.png',
         'mask': 'clay-mask-2048.png', 'calibrationReference': 'clay-rgba-2048.png', 'calibrationDetail': 'detail-rgba-2048.png'}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def pin(path): return {'path': str(Path(path).resolve()), 'sha256': sha(path)}


def key(source, target):
    """RGBA cut-out of the largest non-white component; edge colour from the nearest solid pixel."""
    from scipy import ndimage
    with Image.open(source) as image: rgb = np.asarray(image.convert('RGB')).astype(np.int32)
    solid = (255 - rgb.min(2)) > 18
    labels, count = ndimage.label(solid); require(count > 0, f'No object on the white background of {Path(source).name}'); sizes = ndimage.sum(solid, labels, range(1, count + 1))
    solid = labels == (1 + int(np.argmax(sizes)))
    filled = ndimage.binary_fill_holes(solid); holes = int(filled.sum() - solid.sum())
    core = ndimage.binary_erosion(filled, iterations=1)                       # drop the white-blended antialias ring
    alpha = np.clip(ndimage.gaussian_filter(core.astype(np.float32), .7) * 255, 0, 255)
    alpha[~ndimage.binary_dilation(core, iterations=2)] = 0
    index = ndimage.distance_transform_edt(~core, return_distances=False, return_indices=True)
    out = np.dstack([rgb[index[0], index[1]], alpha[..., None]]).astype(np.uint8); out[alpha == 0, :3] = 0
    Image.fromarray(out, 'RGBA').save(target)
    return {'componentsDropped': int(count - 1), 'droppedPixels': int(sizes.sum() - sizes.max()), 'holePixelsFilled': holes}


def registration(masks):
    """Overlap and outline agreement of the two masks along the weapon's diagonal (lower-left butt, upper-right tip)."""
    height, width = masks['detail'].shape
    iou = float((masks['detail'] & masks['clay']).sum() / (masks['detail'] | masks['clay']).sum())
    along, across = np.array([1, -1]) / np.sqrt(2), np.array([1, 1]) / np.sqrt(2)
    def extremes(mask):
        ys, xs = np.nonzero(mask); p = np.stack([xs, ys], 1).astype(float); a, b = p @ along, p @ across
        pick = lambda i: [float(p[i, 0] / width), float(p[i, 1] / height)]; c = p.mean(0)
        return {'butt-end': pick(int(np.argmin(a))), 'tip-end': pick(int(np.argmax(a))), 'across-upper': pick(int(np.argmin(b))),
                'across-lower': pick(int(np.argmax(b))), 'centroid': [float(c[0] / width), float(c[1] / height)]}, (a, b)
    ld, (ad, bd) = extremes(masks['detail']); lc, (ac, bc) = extremes(masks['clay'])
    landmarks = [{'name': k, 'detail': ld[k], 'clay': lc[k]} for k in ld]
    lo, hi = max(ad.min(), ac.min()), min(ad.max(), ac.max()); edges = []
    for i, t in enumerate((.35, .5, .65, .8, .92)):
        s = lo + (hi - lo) * t
        for side, f in (('upper', np.min), ('lower', np.max)):
            bands = [b[np.abs(a - s) < 1.5] for a, b in ((ad, bd), (ac, bc))]
            require(all(len(band) for band in bands), f'Colour/clay outlines differ at section {i + 1}: regenerate the clay')
            e = [f(band) for band in bands]
            edges.append({'name': f'section-{i + 1}-{side}-edge', 'offsetPixels': float(e[0] - e[1])})
    worst_landmark = max(np.hypot((l['detail'][0] - l['clay'][0]) * width, (l['detail'][1] - l['clay'][1]) * height) for l in landmarks)
    worst_edge = max(abs(e['offsetPixels']) for e in edges)
    return iou, landmarks, edges, float(worst_landmark), float(worst_edge)


def measure_pair(folder):
    """Key both images into `conditioning-v1/` and measure their registration (the first, review-free phase)."""
    folder = Path(folder); work = folder/'conditioning-v1'
    if not (work/'pair-measurement.json').exists():
        require(not work.exists(), 'An unfinished conditioning folder exists; regenerate into a fresh design folder'); work.mkdir()
        keyed = {role: key(folder/f'{role}-original.png', work/f'{role}-keyed.png') for role in ('detail', 'clay')}
        masks = {}
        for role in keyed:
            with Image.open(work/f'{role}-keyed.png') as image: masks[role] = np.asarray(image)[..., 3] >= 128
        require(masks['detail'].shape == masks['clay'].shape, 'Colour and clay images differ in size')
        height, width = masks['detail'].shape
        iou, landmarks, edges, worst_landmark, worst_edge = registration(masks)
        measured = {'keying': keyed, 'iou': iou, 'landmarks': landmarks, 'edgeMeasurements': edges, 'worstLandmarkPixels': worst_landmark,
                    'worstEdgePixels': worst_edge, 'size': [width, height],
                    'detailSha256': sha(work/'detail-keyed.png'), 'claySha256': sha(work/'clay-keyed.png'),
                    'originalSha256': {role: sha(folder/f'{role}-original.png') for role in ('detail', 'clay')}}
        (work/'pair-measurement.json').write_text(json.dumps(measured, indent=2), encoding='utf-8')
    measured = json.loads((work/'pair-measurement.json').read_text(encoding='utf-8'))
    require(sha(work/'detail-keyed.png') == measured['detailSha256'] and sha(work/'clay-keyed.png') == measured['claySha256'],
            'Keyed images changed since they were measured')
    require(measured.get('originalSha256') == {role: sha(folder/f'{role}-original.png') for role in ('detail', 'clay')},
            'The original images changed since they were keyed: regenerate into a fresh design folder')
    return work, measured


def condition(folder, handoff, design_id, source='wave1-v2-contract', *, notes=None, keyed_sha256=None):
    """Key and measure the pair; with the user's review of the keyed images, condition it and write the manifest.

    The first call (no `notes`) only keys and measures and returns the keyed image hashes for a person to look at: keying
    keeps the largest component and fills enclosed holes, so whether intentional openings and thin members survived is
    a visual judgement the overlap numbers cannot make. The second call passes `notes` (the user's own words about
    the keyed images) and `keyed_sha256` = [detail, clay] hashes from the first call, which binds the review to those
    exact files before any approval is written."""
    from tools.itemkit import reference_conditioning as rc
    folder = Path(folder); handoff = Path(handoff)
    work, measured = measure_pair(folder)
    keyed, iou, landmarks, edges = measured['keying'], measured['iou'], measured['landmarks'], measured['edgeMeasurements']
    width, height = measured['size']; worst_landmark, worst_edge = measured['worstLandmarkPixels'], measured['worstEdgePixels']
    # Hard gates: limits scale with the image size.
    require(iou >= .95, f'Colour/clay mask overlap {iou:.3f} is below 0.95: regenerate the clay from the colour image')
    require(worst_landmark <= .01 * max(width, height) and worst_edge <= .006 * max(width, height), 'Colour/clay outlines are misaligned: regenerate the clay')
    require(all(v['droppedPixels'] <= .002 * width * height for v in keyed.values()), 'Background keying dropped a large second object')
    if not (isinstance(notes, str) and notes.strip()):
        return {'reviewRequired': True, 'detail': str(work/'detail-keyed.png'), 'clay': str(work/'clay-keyed.png'),
                'keyedSha256': [measured['detailSha256'], measured['claySha256']], 'keying': keyed, 'iou': iou,
                'worstLandmarkPixels': worst_landmark, 'worstEdgePixels': worst_edge}
    require(list(keyed_sha256 or ()) == [measured['detailSha256'], measured['claySha256']],
            'The review must name the keyed detail and clay hashes it looked at')
    require(not (work/'conditioned').exists(), 'Conditioning already ran for this pair; regenerate into a fresh design folder')
    out = handoff/f'{design_id}.oblique-v1.asset.json'; require(not out.exists(), out.name+' exists')   # before anything is written
    manifest = json.loads((handoff/f'{design_id}.{source}.asset.json').read_text(encoding='utf-8'))   # read before conditioning runs
    notes = (f'{notes.strip()} Measured: angled colour/clay pair from the Codex built-in image tool (prompts in PROMPTS.md), alpha keyed '
             f'from the plain white background, largest component kept, enclosed holes filled: {json.dumps(keyed)}. Mask IoU {iou:.4f}.')
    evidence = {'actualImagesViewed': True, 'pairMasksVisuallyReviewed': True, 'intentionalOpeningsReviewed': True, 'thinMembersReviewed': True,
                'detailSha256': measured['detailSha256'], 'claySha256': measured['claySha256'], 'landmarks': landmarks,
                'edgeMeasurements': edges, 'notes': notes}
    (work/'registration.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    spec = {'designId': design_id, 'canvasSize': 2048, 'paddingPixels': 102, 'sourceAlphaFloor': 16, 'route': 'preserve-reviewed-pair-alpha',
            'detail': pin(work/'detail-keyed.png'), 'clay': pin(work/'clay-keyed.png'), 'registrationEvidence': pin(work/'registration.json'),
            'provenanceRawSources': {'detail': pin(folder/'detail-original.png'), 'clay': pin(folder/'clay-original.png')},
            'sourceKeying': {'method': 'largest-component-holes-filled', **keyed}}
    (work/'conditioning-spec.json').write_text(json.dumps(spec, indent=2), encoding='utf-8')
    result = rc.prepare(work/'conditioning-spec.json', work/'conditioned')
    for role, name in ROLES.items():
        digest = sha(work/'conditioned'/name); target = handoff/'inputs'/f'{digest}.png'; target.parent.mkdir(exist_ok=True)
        if not target.exists(): shutil.copy(work/'conditioned'/name, target)
        manifest['inputs'][role] = {'path': f'inputs/{digest}.png', 'sha256': digest}
    i = manifest['inputs']
    background = lambda ref, image, mask: {'decision': 'approved', 'route': 'preserve-alpha', 'referenceSha256': i[ref]['sha256'],
                                           'imageSha256': i[image]['sha256'], 'maskSha256': i[mask]['sha256'], 'notes': notes}
    manifest['approval']['background'] = background('reference', 'detail', 'foregroundMask')
    manifest['approval']['geometryBackground'] = background('clayReference', 'geometry', 'geometryForegroundMask')
    manifest['approval']['referencePair'] = {'decision': 'approved', 'notes': notes,
        'landmarks': [{'name': r['name'], 'detail': r['detail'], 'geometry': r['clay']} for r in result['conditionedPairedLandmarks']],
        **{k + 'Sha256': i[k]['sha256'] for k in ('reference', 'geometry', 'detail', 'foregroundMask', 'geometryForegroundMask')}}
    manifest['landmarks'] = [{'name': r['name'], 'pixel': [r['detail'][0] * width, r['detail'][1] * height]} for r in landmarks]
    manifest['approval']['referenceView'] = {'view': 'oblique', 'decision': 'approved', 'notes': notes}
    manifest['camera'] = {'reviewed': False, 'fovDegrees': None}
    manifest['notes'] = manifest.get('notes', '') + ' Oblique-v1: angled reference pair replaces the side view; camera FOV requires recalibration.'
    out.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    from tools.itemkit.contracts import manifest as load_manifest
    from tools.itemkit.conditioning import require_conditioning_review
    from tools.headkit.common import verification_pass
    try:
        with verification_pass('oblique-'+design_id):
            report = require_conditioning_review(out, load_manifest(out, validate_native=True))
    except BaseException:
        out.unlink(missing_ok=True)      # its approvals stand only for a pair that passed its review: never leave it behind
        raise
    return {'manifest': str(out), 'iou': iou, 'worstLandmarkPixels': worst_landmark, 'worstEdgePixels': worst_edge,
            'fringe': {k: v.get('resamplingFringePixels') for k, v in report.items()}}
