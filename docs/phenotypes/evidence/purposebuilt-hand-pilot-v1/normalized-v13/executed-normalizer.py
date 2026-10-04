"""Normalize inspected four/six-view sheets with one shared isotropic scale."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from collections import deque

import numpy as np
from PIL import Image


def label(mask):
    labels = np.zeros(mask.shape, dtype=np.int32)
    height, width = mask.shape
    count = 0
    for y, x in zip(*np.nonzero(mask)):
        if labels[y, x]:
            continue
        count += 1
        labels[y, x] = count
        pending = deque([(int(y), int(x))])
        while pending:
            cy, cx = pending.popleft()
            for ny, nx in ((cy-1,cx), (cy+1,cx), (cy,cx-1), (cy,cx+1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny,nx] and not labels[ny,nx]:
                    labels[ny,nx] = count
                    pending.append((ny,nx))
    return labels, count


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--notes', required=True)
    p.add_argument('--layout-components', action='store_true',
                   help='Find four complete alpha components before quadrant assignment; never clip a view at sheet midlines')
    p.add_argument('--six-views', action='store_true',
                   help='2 columns by 3 rows: front,left/back,right/top,bottom; requires complete alpha components')
    p.add_argument('--center-origin', action='store_true',
                   help='Center all silhouette bounds in each square, suitable for centered orthographic cameras')
    p.add_argument('--end-view-min-area-ratio', type=float, default=.25,
                   help='Reviewed minimum alpha area/max area for top/bottom only; .05-.25. Long-axis views of elongated donors can be smaller. Other views remain .25.')
    p.add_argument('--layout-columns', type=int, choices=(2, 3), default=2,
                   help='Explicit observed sheet columns; three is only supported for six complete components. View names remain row-major front,left,back,right,top,bottom.')
    a = p.parse_args()
    if a.six_views and (not a.layout_components or not a.center_origin):
        raise RuntimeError('Six orthographic views require complete components and centered origin')
    if not .05 <= a.end_view_min_area_ratio <= .25 or (a.end_view_min_area_ratio != .25 and not a.six_views):
        raise RuntimeError('End-view ratio requires six views and a reviewed value in .05-.25')
    if a.layout_columns == 3 and not a.six_views:
        raise RuntimeError('Three-column layout requires six complete views')
    names = ('front', 'left', 'back', 'right', 'top', 'bottom') if a.six_views else ('front', 'left', 'back', 'right')
    columns = a.layout_columns
    rows = len(names) // columns
    if a.output.exists():
        raise RuntimeError('Fresh output required')
    source = Image.open(a.source).convert('RGBA')
    w, h = source.size
    panels = []
    if a.layout_components:
        rgba = np.asarray(source)
        alpha = rgba[:, :, 3] > 8
        if alpha.mean() > .9:
            raise RuntimeError('Meaningful transparent alpha required, not an opaque sheet')
        components, count = label(alpha)
        sizes = np.bincount(components.ravel()); sizes[0] = 0
        chosen = np.argsort(sizes)[-len(names):]
        if count < len(names):
            raise RuntimeError('Require '+str(len(names))+' substantial detached object components')
        other = sizes.copy(); other[chosen] = 0
        if other.max() > sizes.max() * .05:
            raise RuntimeError('Ambiguous extra substantial component; inspect source layout')
        assigned = {}
        component_areas = {}
        for component in chosen:
            ys, xs = np.nonzero(components == component)
            column, row = min(columns-1, int(xs.mean()*columns/w)), min(rows-1, int(ys.mean()*rows/h))
            name = names[row * columns + column]
            if name in assigned:
                raise RuntimeError('Two source objects assigned to the same view')
            area_ratio = float(sizes[component] / sizes.max())
            minimum = a.end_view_min_area_ratio if name in ('top', 'bottom') else .25
            if area_ratio < minimum:
                raise RuntimeError('Require substantial detached object component for '+name+': ratio '+str(area_ratio)+' below '+str(minimum))
            box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
            x0, y0, x1, y1 = box
            if x0 == 0 or y0 == 0 or x1 == w or y1 == h:
                raise RuntimeError('Silhouette touches source boundary: '+name)
            component_areas[name] = {'alphaPixels': int(sizes[component]), 'areaRatio': area_ratio,
                                     'minimumAreaRatio': minimum}
            crop = rgba[y0:y1, x0:x1].copy()
            crop[components[y0:y1, x0:x1] != component] = 0
            clean = Image.fromarray(crop)
            assigned[name] = (name, box, clean, (0, 0, x1-x0, y1-y0), 0)
        if set(assigned) != set(names):
            raise RuntimeError('Missing view in source layout')
        panels = [assigned[name] for name in names]
    for name, box in ([] if a.layout_components else zip(('front', 'left', 'back', 'right'),
                         ((0, 0, w//2, h//2), (w//2, 0, w, h//2),
                          (0, h//2, w//2, h), (w//2, h//2, w, h)))):
        panel = source.crop(box)
        rgba = np.array(panel)
        components, count = label(rgba[:, :, 3] > 8)
        sizes = np.bincount(components.ravel())
        if count == 0:
            raise RuntimeError('Empty panel: ' + name)
        sizes[0] = 0
        keep = components == sizes.argmax()
        removed = int(((rgba[:, :, 3] > 8) & ~keep).sum())
        # Remove only disconnected alpha debris; retain the connected silhouette.
        rgba[~keep] = 0
        clean = Image.fromarray(rgba)
        bound = clean.getchannel('A').getbbox()
        if bound[0] == 0 or bound[1] == 0 or bound[2] == panel.width or bound[3] == panel.height:
            raise RuntimeError('Silhouette touches quadrant boundary; inspect and use --layout-components if complete objects cross the midline: ' + name)
        panels.append((name, box, clean, bound, removed))
    common_scale = 896 / max(max(b[2]-b[0], b[3]-b[1]) for _, _, _, b, _ in panels)
    a.output.mkdir(parents=True)
    shutil.copyfile(a.source, a.output/'source.png')
    shutil.copyfile(__file__, a.output/'executed-normalizer.py')
    views = {}
    for name, box, panel, bound, removed in panels:
        # The same isotropic scale applies to every view; only translations vary.
        crop = panel.crop(bound)
        resized = crop.resize((round(crop.width*common_scale), round(crop.height*common_scale)), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
        origin = ((1024-resized.width)//2, (1024-resized.height)//2 if a.center_origin else 64)
        canvas.alpha_composite(resized, origin)
        canvas.save(a.output/(name+'-alpha.png'))
        black = Image.new('RGBA', canvas.size, (0, 0, 0, 255))
        black.alpha_composite(canvas)
        target = a.output/(name+'.png')
        black.convert('RGB').save(target)
        views[name] = {'panelCrop': box, 'alphaBounds': bound, 'detachedAlphaPixelsRemoved': removed,
                       'normalizedBounds': [*origin, resized.width, resized.height],
                       'sha256': sha(target)}
    record = {'schemaVersion': 1, 'source': str(a.source.resolve()), 'sourceSha256': sha(a.source),
              'layout': str(columns)+'x'+str(rows)+': '+ '/'.join(','.join(names[i:i+columns]) for i in range(0,len(names),columns)), 'imagegenMode': 'built-in',
              'scale': common_scale, 'normalization': 'shared isotropic scale, '+('bounds-centered' if a.center_origin else 'top-aligned')+' translation only',
              'layoutMethod': 'complete alpha components assigned by centroid' if a.layout_components else 'fixed quadrants with clipping guard',
              'notes': a.notes, 'views': views, 'clientAccepted': False}
    if a.layout_components:
        record['componentAreas'] = component_areas
        record['endViewMinimumAreaRatio'] = a.end_view_min_area_ratio
    (a.output/'provenance.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
