"""Review previews of manifest texture rules and repair relief on a run's bound outputs, in seconds and without a stage
attempt: paint + ownership rules splatted over four views, colour statistics of bbox-relative regions, and relief
diagnostics (finned surface cells, vertices whose shading normal cancels). Previews never approve anything; the
stages and their reviews remain the record."""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.sparse import coo_matrix
from .common import require, write
from .gltf import mesh

VIEWS = {'front': (0, 1), 'char-left': (1, 1), 'back': (0, -1), 'char-right': (1, -1)}  # glTF: +z faces front, +y up


def splat(value, layers, size=512, samples=1500000, seed=0):
    """Orthographic, z-buffered point splats of uv-mapped colour layers (each an HxWx3 atlas) from four views.
    Returns one tile per (view, layer) in view order."""
    p, f, uv = np.asarray(value['positions'], float), np.asarray(value['faces']), np.asarray(value['uv'])
    rng = np.random.default_rng(seed); tri = p[f]; normal = np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0])
    area = np.linalg.norm(normal, axis=1); require(area.sum() > 0, 'Preview needs a mesh with area')
    pick = rng.choice(len(f), samples, p=area/area.sum()); a, b = rng.random(samples), rng.random(samples)
    flip = a+b > 1; a[flip], b[flip] = 1-a[flip], 1-b[flip]
    points = tri[pick, 0]+a[:, None]*(tri[pick, 1]-tri[pick, 0])+b[:, None]*(tri[pick, 2]-tri[pick, 0])
    corner = uv[pick] if uv.ndim == 3 else uv[f][pick]; st = corner[:, 0]+a[:, None]*(corner[:, 1]-corner[:, 0])+b[:, None]*(corner[:, 2]-corner[:, 0])
    normal = (normal/np.maximum(area[:, None], 1e-30))[pick]
    colours = []
    for layer in layers:
        n = len(layer); x = np.clip((st[:, 0]*n).astype(int), 0, n-1); y = np.clip((st[:, 1]*n).astype(int), 0, n-1); colours.append(layer[y, x])
    centre = (p.min(0)+p.max(0))/2; half = np.abs(p-centre).max()*1.05; tiles = []
    for name, (axis, sign) in VIEWS.items():
        if axis == 0: u, d, depth, light = sign*(points[:, 0]-centre[0]), points[:, 1]-centre[1], sign*points[:, 2], sign*normal[:, 2]
        else: u, d, depth, light = -sign*(points[:, 2]-centre[2]), points[:, 1]-centre[1], sign*points[:, 0], sign*normal[:, 0]
        x = ((u/half*.5+.5)*size).astype(int); y = ((.5-d/half*.5)*size).astype(int); ok = (x >= 0) & (x < size) & (y >= 0) & (y < size)
        order = np.argsort(depth[ok]); xi, yi = x[ok][order], y[ok][order]; shade = np.clip(.45+.55*light[ok][order], .3, 1)[:, None]
        for colour in colours:
            image = np.full((size, size, 3), 70, np.uint8); image[yi, xi] = (colour[ok][order]*shade).astype(np.uint8); tiles.append((name, image))
    return tiles


def sheet(tiles, rows, title, size):
    canvas = Image.new('RGB', (size*len(VIEWS), size*rows+20), (30, 30, 30)); draw = ImageDraw.Draw(canvas)
    for i, (name, image) in enumerate(tiles):
        column, row = i//rows, i % rows; canvas.paste(Image.fromarray(image), (column*size, 20+row*size)); draw.text((column*size+4, 22+row*size), name, fill='white')
    draw.text((4, 4), title, fill='white'); return canvas


def region_stats(value, rgb, regions):
    """10/50/90th percentiles of each colour quantity inside each named bbox-relative predicate."""
    from .paint import texel_values
    from .predicates import when
    from .uv import raster_audit
    values = texel_values(value, rgb, raster_audit(value['uv'], len(rgb))[1]); rows = {}
    for name, predicate in regions.items():
        selected = when(predicate, values, regions) & values['mapped']
        rows[name] = {'texels': int(selected.sum())}
        if selected.any():
            rows[name].update({key: [float(q) for q in np.percentile(values[key][selected], [10, 50, 90])] for key in ('r', 'g', 'b', 'lum', 'sat', 'rb', 'red')})
    return rows


def pinched(vertices, faces, threshold=.2):
    """Vertices whose area-weighted normal nearly cancels (|sum a n| / sum a < threshold): smooth shading turns them
    dark. Tight crevices (horn meets skull) and reduction pinches produce them."""
    vertices = np.asarray(vertices, float); raw = np.cross(vertices[faces[:, 1]]-vertices[faces[:, 0]], vertices[faces[:, 2]]-vertices[faces[:, 0]])
    total = np.zeros_like(vertices); np.add.at(total, faces.ravel(), np.repeat(raw, 3, 0))
    weight = np.zeros(len(vertices)); np.add.at(weight, faces.ravel(), np.repeat(np.linalg.norm(raw, axis=1), 3))
    used = weight > 0; ratio = np.ones(len(vertices)); ratio[used] = np.linalg.norm(total[used], axis=1)/weight[used]
    return ratio < threshold


def rough_cells(vertices, faces, local, fraction=.02, cell=.02, limit=25):
    """Head-local cells (metres) holding the most vertices of the roughest `fraction` by normal deviation: where fins
    and crust sit, to aim a reviewed smoothing region."""
    vertices = np.asarray(vertices, float); raw = np.cross(vertices[faces[:, 1]]-vertices[faces[:, 0]], vertices[faces[:, 2]]-vertices[faces[:, 0]])
    face = raw/np.maximum(np.linalg.norm(raw, axis=1, keepdims=True), 1e-30)
    vertex = np.zeros_like(vertices); np.add.at(vertex, faces.ravel(), np.repeat(face, 3, 0)); vertex /= np.maximum(np.linalg.norm(vertex, axis=1, keepdims=True), 1e-30)
    deviation = np.zeros(len(vertices)); np.add.at(deviation, faces.ravel(), 1-(np.repeat(face, 3, 0)*vertex[faces.ravel()]).sum(1))
    deviation /= np.maximum(np.bincount(faces.ravel(), minlength=len(vertices)), 1)
    rough = deviation > np.quantile(deviation, 1-fraction); keys, counts = np.unique(np.floor(local[rough]/cell).astype(int), axis=0, return_counts=True)
    order = np.argsort(-counts, kind='stable')[:limit]
    return [{'centre': [round(float(c), 4) for c in (keys[i]+.5)*cell], 'vertices': int(counts[i])} for i in order]


def preview(runner, what, output, regions=None):
    """Preview against the run's bound, current upstream outputs (unwrap/bake/repair need not be reviewed yet)."""
    output = Path(output); output.mkdir(parents=True, exist_ok=False); m = runner.data
    if what == 'relief':
        from .mesh import physical, transform, checked_fit, BASIS
        repair = runner.result('repair', require_review=False)
        matrix = runner.result('fit', require_review=False)['matrix'] if runner._staged_fit() else m['fit']['matrix']
        rows = {}
        for name, row in (('final', repair['source']), ('master', repair['master'])):
            value = mesh(row['path']); v, f = physical(value['positions'], value['faces']); local = transform(checked_fit(matrix) @ BASIS, v)
            rows[name] = {'path': row['path'], 'pinchedVertices': int(pinched(v, f).sum()), 'roughCells': rough_cells(v, f, local)}
        write(output/'relief.json', rows, fresh=True); return {'relief': str(output/'relief.json'), **{k: r['pinchedVertices'] for k, r in rows.items()}}
    # Rules are authored before their gates close, so the bake itself need not be reviewed yet (its unwrap must be).
    inputs = m['inputs']
    source = runner.input('uvMesh') if 'uvMesh' in inputs else runner.result('unwrap', require_review=False)['mesh']['path']; value = mesh(source)
    colour = runner.input('basecolor4k') if 'basecolor4k' in inputs else runner.result('bake', require_review=False)['maps']['basecolor-4096.png']['path']
    masks = {}
    if 'paint' in m:
        from .paint import paint
        seal = runner.result('repair', require_review=False)['neck']['seal']['shellTriangles'] if runner._sealed() else None
        painted = paint(source, colour, m['paint'], output/'paint', seal_start=seal)
        colour = painted['maps']['basecolor-4096.png']['path']; masks = {name: row['path'] for name, row in painted['masks'].items()}
    rgb = np.asarray(Image.open(colour).convert('RGB'))
    if what == 'stats':
        require(isinstance(regions, dict) and regions, 'Colour statistics need named regions')
        rows = region_stats(value, rgb, regions); write(output/'stats.json', rows, fresh=True); return {'stats': str(output/'stats.json'), 'regions': rows}
    require(what == 'ownership', 'Preview is ownership, stats or relief')
    from .paint import rule_ownership, PREVIEW
    config = m.get('ownership', {}); require(config.get('mode') == 'rules', 'Ownership preview needs rules mode')
    metallic = runner.input('metallic4k') if 'metallic4k' in m['inputs'] else runner.result('bake', require_review=False)['maps']['metallic-4096.png']['path']
    labels, report = rule_ownership(source, colour, config, metallic=metallic, masks=masks)
    size = 512; image = sheet(splat(value, [rgb, PREVIEW[labels]]), 2, 'top: colour, bottom: ownership '+json.dumps(report['channels']), size)
    image.save(output/'ownership-preview.png'); write(output/'ownership-report.json', report, fresh=True)
    return {'preview': str(output/'ownership-preview.png'), 'report': report}
