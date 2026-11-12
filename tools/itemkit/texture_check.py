"""Advisory texture outlier check: local streaks and blotches that differ sharply from their surroundings.

The wave-1 Club shipped a dark squiggle across its grip texture that no gate noticed. This finds texels whose
lightness departs from their neighbourhood's median by far more than that part's typical texture variation, joins
them into connected blobs and reports the large ones with a heatmap. It never fails a stage: generated textures carry
intended detail (wraps, scratches, lettering), so a person decides what a flagged blob is.

    python -m tools.itemkit.texture_check BAKE_ATTEMPT_FOLDER [--output DIR]
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.headkit.common import pin, require

SIZE = 1024          # checked at the runtime map's resolution
WINDOW = 31          # neighbourhood for the local median (texels at SIZE): wider than a stroke, narrower than an island
SMOOTH = 2.0         # Gaussian sigma on the residual: stipple and grain cancel, a coherent stroke survives
SPREAD = 5.0         # an outlier is beyond this many robust deviations of its UV island's smoothed residual ...
FLOOR = .08          # ... and at least this far from its neighbourhood (0..1 lightness)
EDGE = 4             # texels trimmed from each island edge, where the neighbourhood is gutter padding
MINIMUM_AREA = 40    # texels in a blob worth reporting
MINIMUM_ISLAND = 200


def lightness(rgb):
    rgb = np.asarray(rgb, float) / 255.
    return rgb @ np.array([.2126, .7152, .0722])


def outliers(image, mapped, *, window=WINDOW, smooth=SMOOTH, spread=SPREAD, floor=FLOOR, edge=EDGE, minimum_area=MINIMUM_AREA):
    """Blobs much lighter or darker than their surroundings, judged per UV island: (report, boolean outlier mask).

    On the wave-1 bakes this finds the Club's grip squiggle and, as expected, also intended sharp detail such as
    blade edges and fuller lines on the swords; the report ranks blobs by area for a person to look at."""
    from scipy import ndimage
    image = np.asarray(image); mapped = np.asarray(mapped, bool)
    require(image.ndim == 3 and image.shape[:2] == mapped.shape, 'Texture and coverage differ in size')
    value = lightness(image[..., :3])
    residual = ndimage.gaussian_filter(value - ndimage.median_filter(value, size=window, mode='nearest'), smooth)
    inner = ndimage.binary_erosion(mapped, iterations=edge); islands, count = ndimage.label(mapped)
    flagged = np.zeros(mapped.shape, bool); checked = 0
    # Each island is judged inside its own bounding box, not by a full-map comparison per island.
    for island, box in enumerate(ndimage.find_objects(islands), start=1):
        if box is None: continue
        region = inner[box] & (islands[box] == island)
        if region.sum() < MINIMUM_ISLAND: continue
        r = residual[box][region]; deviation = float(np.median(np.abs(r - np.median(r)))) * 1.4826 + 1e-6
        flagged[box] |= region & (np.abs(residual[box]) > max(spread * deviation, floor)); checked += 1
    labels, count = ndimage.label(flagged, structure=np.ones((3, 3))); areas = np.bincount(labels.ravel())
    means = ndimage.mean(residual, labels, np.arange(1, count + 1)) if count else []
    blobs = []
    for index, box in enumerate(ndimage.find_objects(labels), start=1):
        if box is None or areas[index] < minimum_area: continue
        height, width = box[0].stop - box[0].start, box[1].stop - box[1].start
        blobs.append({'area': int(areas[index]), 'bounds': [box[1].start, box[0].start, box[1].stop, box[0].stop],
                      'elongation': float(max(height, width) / max(1, min(height, width))),
                      'meanResidual': float(means[index - 1])})
    blobs.sort(key=lambda b: -b['area'])
    keep = np.isin(labels, [i for i, a in enumerate(areas) if i and a >= minimum_area])
    return {'advisory': True, 'size': list(mapped.shape), 'islandsChecked': checked, 'flaggedTexels': int(keep.sum()),
            'blobCount': len(blobs), 'blobs': blobs[:20],
            'settings': {'window': window, 'smooth': smooth, 'spread': spread, 'floor': floor, 'edge': edge, 'minimumArea': minimum_area}}, keep


def heatmap(image, mapped, mask, path):
    """The texture dimmed to a third, unmapped texels black, flagged texels in red."""
    rgb = np.asarray(image)[..., :3].astype(float) / 3; rgb[~np.asarray(mapped, bool)] = 0; rgb[mask] = [255, 40, 40]
    Image.fromarray(rgb.astype(np.uint8), 'RGB').save(path)
    return pin(path)


def check_bake(texture_path, masks_path, output):
    """Run the check on a finished runtime map with the bake's coverage (owners >= 0) at the map's resolution."""
    with Image.open(texture_path) as im: image = np.asarray(im.convert('RGB').resize((SIZE, SIZE), Image.Resampling.BOX))
    with np.load(masks_path, allow_pickle=False) as masks: owners = masks['owners']
    k = owners.shape[0] // SIZE
    mapped = np.flipud((owners.reshape(SIZE, k, SIZE, k) >= 0).all((1, 3)))   # the finished map is stored flipped (finish_bake)
    report, mask = outliers(image, mapped)
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    report['heatmap'] = heatmap(image, mapped, mask, output/'texture-outliers.png'); report['texture'] = pin(texture_path)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0]); parser.add_argument('bake', type=Path)
    parser.add_argument('--output', type=Path); a = parser.parse_args(argv)
    receipt = json.loads((a.bake/'receipt.json').read_text(encoding='utf-8')); result = receipt['result']
    report = check_bake(result['maps'][str(SIZE)]['path'], result['masks']['path'], a.output or a.bake/'texture-check')
    (Path(report['heatmap']['path']).parent/'texture-outliers.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('flaggedTexels', 'blobCount')} | {'largest': report['blobs'][:5], 'heatmap': report['heatmap']['path']}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
