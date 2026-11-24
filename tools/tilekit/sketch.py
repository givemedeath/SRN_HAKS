"""Pictures of tile models and kit pieces without the game: flat orthographic sketches, and Blender renders of the pieces.

`sketch` draws a model from the top, the front (-y) and the side (+x), shaded by how its faces lie, the cell outlined in
red. `props` exports every kit piece and the kit's atlas, renders each on a grey wall or roof in Blender (four threads)
by day, and by night where it glows, and puts the renders on sheets."""
import json
import math
import subprocess
from pathlib import Path

from . import geometry, require

VIEWS = (('top', 0, 1, 2, 1), ('front -y', 0, 2, 1, -1), ('side +x', 1, 2, 0, 1))  # across, up, depth, and which way is nearer
SCALE, PAD, HALF = 9, 20, 6  # pixels a metre, pixels between, metres drawn round the middle
THREADS = 4  # the repository's rule for preview renders
SKIPPED = ('camera_head',)  # a part of another piece


def _shade(triangle):
    a, b, c = triangle; u, v = ([end[axis] - a[axis] for axis in range(3)] for end in (b, c))
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]); size = math.hypot(*n) or 1
    return int(60 + 170 * abs(n[0] * 0.4 + n[1] * 0.6 + n[2] * 0.7) / size)


def sketch(text, title):
    """A picture of a model from three sides."""
    from PIL import Image, ImageDraw
    triangles = geometry.triangles(geometry.parse(text)[2]); require(triangles, f'{title} draws nothing')
    tall = max(point[2] for triangle in triangles for point in triangle) + 2; panels = []
    for label, across, up, depth, near in VIEWS:
        high = 2 * HALF if label == 'top' else tall; base = HALF if label == 'top' else 0; wide = 2 * HALF * SCALE
        picture = Image.new('RGB', (wide, max(1, int(high * SCALE))), (250, 250, 245)); draw = ImageDraw.Draw(picture)
        for triangle in sorted(triangles, key=lambda triangle: near * sum(point[depth] for point in triangle)):
            grey = _shade(triangle)
            draw.polygon([((point[across] + HALF) * SCALE, (high - point[up] - base) * SCALE) for point in triangle], fill=(grey, grey, min(255, grey + 15)), outline=(40, 40, 40))
        low, far = (HALF - geometry.HALF) * SCALE, (HALF + geometry.HALF) * SCALE
        draw.rectangle([low, low, far, far] if label == 'top' else [low, 0, far, picture.height - 1], outline=(220, 0, 0)); panels.append((label, picture))
    page = Image.new('RGB', (sum(picture.width for _, picture in panels) + PAD * 4, max(picture.height for _, picture in panels) + 40), 'white'); draw = ImageDraw.Draw(page); x = PAD
    draw.text((PAD, 4), title, fill='black')
    for label, picture in panels:
        page.paste(picture, (x, 30)); draw.text((x, 18), label, fill='black'); x += picture.width + PAD
    return page


def sketches(texts, output):
    """One picture of several models {name: text}, side by side."""
    from PIL import Image
    require(texts, 'No model to sketch'); pictures = [sketch(text, name) for name, text in texts.items()]
    page = Image.new('RGB', (sum(one.width for one in pictures), max(one.height for one in pictures)), 'white'); x = 0
    for one in pictures:
        page.paste(one, (x, 0)); x += one.width
    page.save(output)
    return len(pictures)


def export(folder, masters):
    """Write every kit piece's mesh (pieces.json) and the atlas's maps as PNG into `folder`. Returns the pieces' names."""
    import numpy as np
    from PIL import Image
    from . import kit
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); maps = kit.atlas(masters); pieces = {}
    for name, key, scale in (('atlas', 'colour', 1), ('glow', 'glow', 1), ('metal', 'metal', 255), ('rough', 'roughness', 255)):
        Image.fromarray(np.uint8(maps[key] * scale) if scale > 1 else maps[key]).save(folder / f'{name}.png')
    for name, build in kit.PIECES.items():
        if name not in SKIPPED:
            mesh, roof = kit.camera_whole() if name == 'camera' else build()
            pieces[name] = {'verts': [list(vertex) for vertex in mesh.verts], 'uvs': [list(uv[:2]) for uv in mesh.tverts], 'faces': [list(face[:3]) + list(face[4:7]) for face in mesh.faces], 'roof': bool(roof)}
    (folder / 'pieces.json').write_text(json.dumps(pieces), encoding='utf-8')
    return list(pieces)


def command(blender, folder):
    return [str(blender), '-b', '--factory-startup', '-t', str(THREADS), '--python-exit-code', '1', '--python', str(Path(__file__).with_name('props_blender.py')), '--', str(folder)]


def sheets(folder):
    """sheet-wall.jpg and sheet-roof.jpg of the renders in `folder`: each piece from the front, the side, and by night."""
    from PIL import Image, ImageDraw
    folder = Path(folder); pieces = json.loads((folder / 'pieces.json').read_text(encoding='utf-8')); wide, high, label = 400, 300, 18; made = []
    for kind, roof in (('wall', False), ('roof', True)):
        names = [name for name, data in pieces.items() if data['roof'] == roof]
        if not names:
            continue
        page = Image.new('RGB', (6 * wide, -(-len(names) // 2) * (high + label)), 'white'); draw = ImageDraw.Draw(page)
        for index, name in enumerate(names):
            x, y = index % 2 * 3 * wide, index // 2 * (high + label); draw.text((x + 4, y + 3), name, fill='black')
            for slot, view in enumerate(('front', 'side', 'night')):
                path = folder / f'{name}-{view}.png'
                if path.is_file():
                    with Image.open(path) as picture:
                        page.paste(picture.convert('RGB').resize((wide, high)), (x + slot * wide, y + label))
        page.save(folder / f'sheet-{kind}.jpg', quality=88); made.append(f'sheet-{kind}.jpg')
    return made


def props(folder, masters, blender, run=subprocess.run):
    folder = Path(folder).resolve(); names = export(folder, masters)
    for name in names:  # an earlier run's renders are not this one's
        for path in folder.glob(f'{name}-*.png'):
            path.unlink()
    result = run(command(blender, folder), capture_output=True, timeout=3600)
    require(result.returncode == 0, 'Blender failed: ' + (result.stderr or b'').decode(errors='replace')[-1500:])
    missing = [name for name in names if not (folder / f'{name}-front.png').is_file()]; require(not missing, 'No render of ' + ', '.join(missing[:6]))
    return {'pieces': len(names), 'sheets': sheets(folder)}
