"""Blinking indicator lights on a fixture a texture draws (user, 2026-11-24: the arcology's wall console "needs a
few glowing and blinking lights"). The steady lights are the texture's glow map (`material.glow`, its `boxes`). A
blinking one is a small lamp pane laid just over the mesh where the texture draws the indicator, shown and hidden by
a tile loop. The pane draws the fixture's own material at a lit patch of its glow map, with no surface colour and a
glow colour of its own: the game tints a glow map by a mesh's glow colour, so one near-white patch gives a lamp of
any colour and no texture is added. The panes hang from the tile's animated node (`daylight.animated`), where the
game plays a tile's animations, and rest clear, so a tile whose loop is off has its steady lights alone.

The list (`docs/tilesets/<set>/blink.json`): {"texture": the fixture's texture, "patch": [left, top, right, bottom]
of a lit place of its glow map (0-1 of the picture, the top first), "loop": the tile loop, "period": its seconds,
"lift": metres over the mesh, "lights": {name: {"boxes": [[left, top, right, bottom]], "colour": [red, green, blue],
"on": [[from, to] seconds]}}}."""
import re
from pathlib import Path

from . import daylight, inventory, lamps, require

LAMP = re.compile(r'(?i)^blink\d{2,}$')  # a lamp pane's name
EDGE = 0.02  # seconds a lamp takes to come on or go off


def _rows(body, word, width):
    at = re.search(r'(?mi)^[ \t]*' + word + r'[ \t]+(\d+)[ \t]*\r?\n', body)
    if not at:
        return []
    return [line.split()[:width] for line in body[at.end():].splitlines()[:int(at.group(1))]]


def _mesh(body):
    """(verts, [(three vert indices, three tvert indices)], tverts) of a mesh's block."""
    verts = [tuple(map(float, row)) for row in _rows(body, 'verts', 3)]; tverts = [tuple(map(float, row)) for row in _rows(body, 'tverts', 2)]
    faces = [(tuple(map(int, row[:3])), tuple(map(int, row[4:7]))) for row in _rows(body, 'faces', 8)]
    return verts, faces, tverts


def _minus(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _placed(face, verts, tverts):
    """(a function from a place in the texture to the place on the face, the face's unit normal), or None for a face
    its texture does not spread over."""
    (a, b, c), (ta, tb, tc) = ([verts[at] for at in face[0]], [tverts[at] for at in face[1]])
    (u1, v1), (u2, v2) = _minus(tb, ta), _minus(tc, ta); area = u1 * v2 - u2 * v1
    if abs(area) < 1e-12:
        return None
    along, up = _minus(b, a), _minus(c, a); normal = _cross(along, up); length = sum(value * value for value in normal) ** 0.5
    if length < 1e-12:
        return None

    def place(u, v):
        s, t = ((u - ta[0]) * v2 - (v - ta[1]) * u2) / area, ((v - ta[1]) * u1 - (u - ta[0]) * v1) / area
        return tuple(p + s * q + t * r for p, q, r in zip(a, along, up)), (s, t)
    return place, tuple(value / length for value in normal)


def panes(body, boxes, lift):
    """[four corners] of the lamp panes over a mesh for the `boxes` of its texture ([left, top, right, bottom], the top
    of the picture first): one for each face pair that draws a box's middle, `lift` over it. A box that runs off
    the flat it lies on is refused."""
    verts, faces, tverts = _mesh(body); found = []; flats = [(face, _placed(face, verts, tverts)) for face in faces]
    for left, top, right, bottom in boxes:
        middle = ((left + right) / 2, 1 - (top + bottom) / 2); corners = [(left, 1 - top), (right, 1 - top), (right, 1 - bottom), (left, 1 - bottom)]
        for face, flat in flats:
            if not flat:
                continue
            place, normal = flat; s, t = place(*middle)[1]
            if min(s, t) < -1e-6 or s + t > 1 + 1e-6:
                continue
            for corner in corners:  # each corner on a face of the same flat: a box over a fold would stand off the fixture
                at = place(*corner)[0]
                held = any(other and sum(a * b for a, b in zip(other[1], normal)) > 0.999 and min(other[0](*corner)[1]) > -1e-6 and sum(other[0](*corner)[1]) < 1 + 1e-6
                           and max(abs(a - b) for a, b in zip(other[0](*corner)[0], at)) < 1e-6 for _, other in flats)
                require(held, f'The box {[left, top, right, bottom]} runs off the flat it lies on')
            quad = [tuple(p + lift * n for p, n in zip(place(*corner)[0], normal)) for corner in corners]
            if sum(a * b for a, b in zip(_cross(_minus(quad[1], quad[0]), _minus(quad[2], quad[0])), normal)) < 0:
                quad.reverse()  # facing as the face under it does
            if not any(max(abs(a - b) for one, other in zip(quad, had) for a, b in zip(one, other)) < 1e-6 for had in found):
                found.append(quad)  # a middle on the edge two faces share is in both: one pane for the place
    return found


def without(text):
    """The model's text without its lamp panes, and without an animation that blinked them and keyed nothing else.
    Another animation is left though it keys nothing: a tile's own `tiledefault` names its emitters alone."""
    bare = lambda block: daylight.NODE.sub(lambda at: '' if LAMP.match(at.group(2).split()[0]) else at.group(0), block)
    text = re.sub(r'(?mis)^[ \t]*newanim[ \t]+\S+[ \t].*?^[ \t]*doneanim[^\n]*\n',
                  lambda at: '' if bare(at.group(0)) != at.group(0) and not re.search(r'(?i)key\b', bare(at.group(0))) else at.group(0), text)
    return bare(text)


def with_lights(text, spec):
    """(the model's text with the lamp panes of `spec` over its meshes that draw the fixture, and the loop that blinks
    them; how many panes). A model that draws none of the fixture's lights is given back as it is; one that has the
    loop already, or lamp panes, is refused."""
    require(isinstance(spec.get('lights'), dict) and isinstance(spec.get('texture'), str) and len(spec.get('patch', ())) == 4 and isinstance(spec.get('period'), (int, float)),
            'A blink list has a texture, a patch of four numbers, a period and its lights')
    texture = spec['texture'].lower(); loop = spec.get('loop', 'animloop01'); period = float(spec['period']); lift = float(spec.get('lift', 0.005))
    name = re.search(r'(?mi)^[ \t]*newmodel[ \t]+(\S+)', text).group(1); ending = '\r\n' if '\r\n' in text else '\n'
    left, top, right, bottom = spec['patch']; require(0 <= left < right <= 1 and 0 <= top < bottom <= 1, 'A patch is [left, top, right, bottom] in 0-1')
    patch = [(left, 1 - top), (right, 1 - top), (right, 1 - bottom), (left, 1 - bottom)]
    meshes = [at for at in daylight.NODE.finditer(daylight._geometry(text)) if at.group(1).lower() == 'trimesh' and (daylight._field(at.group(3), 'bitmap') or '').lower() == texture]
    made = []  # (light, the mesh's block, its panes)
    for light, how in spec['lights'].items():
        require(len(how.get('colour', ())) == 3 and all(0 <= value <= 1 for value in how['colour']), f'{light}: a colour is red, green and blue in 0-1')
        require(how.get('boxes') and all(len(box) == 4 for box in how['boxes']), f'{light}: its boxes are [left, top, right, bottom]')
        require(how.get('on') and all(len(span) == 2 for span in how['on']) and all(0 <= start < finish <= period - EDGE for start, finish in how['on']) and all(a[1] + 2 * EDGE <= b[0] for a, b in zip(how['on'], how['on'][1:])),
                f'{light}: its times on are [from, to] seconds in turn, within the period')
        for mesh in meshes:
            quads = panes(mesh.group(3), how['boxes'], lift)
            if quads:
                made.append((light, mesh, quads))
    if not made:
        return text, 0
    require(not any(LAMP.match(at.group(2).split()[0]) for at in daylight.NODE.finditer(daylight._geometry(text))), f'{name} has lamp panes already')
    require(not re.search(rf'(?mi)^[ \t]*newanim[ \t]+{loop}[ \t]', text), f'{name} has the loop {loop} already')
    geometry = daylight._geometry(text); end = re.search(r'(?mi)^[ \t]*endmodelgeom', geometry); require(end, f'{name} has no endmodelgeom line')
    blocks, keyed = [], []
    for index, (light, mesh, quads) in enumerate(made):
        how = spec['lights'][light]; node = f'blink{index:02d}'; body = mesh.group(3)
        lines = [f'node trimesh {node}'] + [f'  {word} {daylight._field(body, word)}' for word in ('parent', 'position', 'orientation', 'scale') if daylight._field(body, word)]
        lines += ['  render 1', '  shadow 0', '  alpha 0.0', '  transparencyhint 1', '  selfillumcolor ' + ' '.join(f'{value:g}' for value in how['colour']),
                  '  ambient 0 0 0', '  diffuse 0 0 0', '  specular 0 0 0', '  shininess 1', f'  bitmap {texture}', f'  verts {4 * len(quads)}']
        lines += ['    ' + ' '.join(f'{value:.5f}' for value in corner) for quad in quads for corner in quad]
        lines += [f'  faces {2 * len(quads)}'] + [f'    {4 * at + a} {4 * at + b} {4 * at + c}  1  {a} {b} {c}  1' for at in range(len(quads)) for a, b, c in ((0, 1, 2), (0, 2, 3))]
        lines += ['  tverts 4'] + [f'    {u:.6f} {v:.6f} 0' for u, v in patch] + ['endnode']
        blocks.append(ending.join(lines) + ending); keyed.append((node, how['on']))
    text = text[:end.start()] + ''.join(blocks) + text[end.start():]
    for node, _ in keyed:
        text, parent = daylight.animated(text, node)
    root = next(at.group(2).split()[0] for at in daylight.NODE.finditer(daylight._geometry(text)) if (daylight._field(at.group(3), 'parent') or 'NULL').split()[0].upper() == 'NULL')
    lines = [f'newanim {loop} {name}', f'  length {period:.5f}', '  transtime 0.0', f'  animroot {name}', f'  node dummy {root}', '    parent NULL', '  endnode',
             f'  node dummy {parent}', f'    parent {root}', '  endnode']
    for node, on in keyed:
        keys = [(0.0, 0)] if on[0][0] > 0 else []
        for start, finish in on:
            keys += ([(start - EDGE, 0)] if start >= EDGE and (not keys or keys[-1][0] < start - EDGE) else []) + [(start, 1), (finish, 1), (finish + EDGE, 0)]
        keys += [(period, 0)] if keys[-1][0] < period else []
        lines += [f'  node trimesh {node}', f'    parent {parent}', f'    alphakey {len(keys)}'] + [f'      {at:.5f} {value}' for at, value in keys] + ['    endlist', '  endnode']
    lines += [f'doneanim {loop} {name}']
    at = re.search(r'(?mi)^[ \t]*donemodel', text); require(at, f'{name} has no donemodel line')
    return text[:at.start()] + ending.join(lines) + ending + text[at.start():], sum(len(quads) for _, _, quads in made)


def write(repo, tileset, folder, spec, shared=(), again=False):
    """Write the models of a tileset that draw the fixture's lights, with their lamp panes, into `folder` (a review's
    overlay) and tell {'models': {model: panes}, 'refused': {model: why}, 'done': how many had them already}. again:
    a model that has its lamp panes is made anew from the list. shared: as `daylight.write`."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {'models': {}, 'refused': {}, 'done': 0}
    from .apply import noted
    for name, file, text, others, source in inventory.drawn_copies(repo, tileset.lower(), folder, lamps.PACKS):
        if set(others) - {one.lower() for one in shared}:
            continue
        if any(LAMP.match(at.group(2).split()[0]) for at in daylight.NODE.finditer(daylight._geometry(text))):
            told['done'] += 1
            if not again:
                continue
        try:
            new, count = with_lights(without(text) if again else text, spec)
        except ValueError as error:
            told['refused'][name] = str(error); continue
        if count and new != text:
            require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
            noted(folder, file, source); (folder / file).write_bytes(new.encode('cp1252')); told['models'][name] = count
    return told
