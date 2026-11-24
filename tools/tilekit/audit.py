"""Audits of a restyle in hand: which building tiles are plainest, who else draws the restyled textures, and which applied
pieces run into what their tile draws.

`rank` scores each building tile by its own geometry (kit pieces apart): few faces for its surface above a player's
head, much of that surface on box planes, few roof levels; bigger tiles first among the plain. `shared` lists the models
outside the tileset that name one of a material spec's textures, by the tileset or pack that draws them. `placements`
holds a placement spec's wall pieces against their tiles' own geometry, as `detail` does when it places them: a spec
applied before a guard was made is checked against it afterwards."""
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import detail, effects, geometry, inventory, lamps, require
from .compiled import source

LOWEST = 6.0  # metres: a lower tile is no building
WORDS = re.compile(rb'[a-z0-9_]+')


def _laid(repo, tileset):
    return inventory.read_set((Path(repo) / f'srn_t_{tileset}' / f'{tileset}.set').read_bytes().decode('cp1252'))


def plainness(text):
    """{height, faces, kitFaces, highArea, facesPerM2, boxy, roofLevels, plain} of a tile model, or None for no building."""
    _, _, nodes = geometry.parse(text)
    own = lambda node: node.rendered and not detail.is_kit(node.name)
    triangles = geometry.triangles(nodes, own); top = max((point[2] for triangle in triangles for point in triangle), default=0.0)
    if top < LOWEST:
        return None
    high = [triangle for triangle in triangles if min(point[2] for point in triangle) > geometry.HEAD]; area = boxy = 0.0; roofs = Counter()
    for a, b, c in high:
        u, v = ([end[axis] - a[axis] for axis in range(3)] for end in (b, c))
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]); size = math.hypot(*n) / 2
        if size < 1e-6:
            continue
        area += size
        if max(abs(value) for value in n) / (2 * size) > 0.999:
            boxy += size
        if n[2] / (2 * size) > 0.9:
            roofs[round((a[2] + b[2] + c[2]) / 3 / 0.5)] += size
    levels = sum(weight > 2.0 for weight in roofs.values()); density = len(high) / area if area else 0.0; share = boxy / area if area else 0.0
    return {'height': round(top, 1), 'faces': sum(len(node.faces) for node in nodes if own(node)), 'kitFaces': sum(len(node.faces) for node in nodes if node.rendered and detail.is_kit(node.name)),
            'highArea': round(area), 'facesPerM2': round(density, 3), 'boxy': round(share, 2), 'roofLevels': levels,
            'plain': round((1 - min(density / 0.5, 1)) * 0.45 + share * 0.35 + 1 / max(levels, 1) * 0.2, 3)}


def rank(repo, tileset, ground=()):
    """The building tiles of a tileset, the plainest and biggest first. `ground`: the terrains that are no building,
    with the set's default."""
    tileset = tileset.lower(); laid = _laid(repo, tileset); plain = {name.lower() for name in (*ground, laid['default'], '')}; families = defaultdict(Counter)
    unknown = sorted({name.lower() for name in ground} - {name.lower() for name in laid['terrains']}); require(not unknown, f'No terrain of {tileset} is ' + ', '.join(unknown))
    for tile in laid['tiles']:
        kinds = [corner for corner in tile['corners'] if corner.lower() not in plain]
        if kinds:
            families[tile['model']].update(kinds)
    rows = [{'tile': name, 'family': families[name].most_common(1)[0][0], **told} for name, _, text, _, _ in inventory.drawn_copies(repo, tileset, None, lamps.PACKS)
            if name in families for told in [plainness(text)] if told]
    return sorted(rows, key=lambda row: -row['plain'] * math.log10(max(row['highArea'], 10)))


def shared(repo, tileset, textures):
    """{tileset or pack: {model: [textures]}} of the models outside the tileset's own that name one of `textures`."""
    repo, tileset = Path(repo), tileset.lower(); wanted = {name.lower().encode() for name in textures}; drawn = inventory.drawn_models(repo, tileset); others = inventory._other_sets(repo, tileset, edges=True)
    found = defaultdict(dict)
    for pack in inventory._packs(repo):
        for path in sorted(pack.glob('*.mdl')):
            name = path.stem.lower()
            if name not in drawn:
                names = sorted(word.decode() for word in set(WORDS.findall(source(repo, path).read_bytes().lower())) & wanted)
                if names:
                    found[','.join(sorted(others[name])) if name in others else pack.name][name] = names
    return {owner: found[owner] for owner in sorted(found)}


def placements(repo, spec, kit):
    """[{tile, piece, number, why}] of a placement spec's wall pieces that run into their tile's own geometry, the kit and
    the effects taken out of it."""
    tileset = spec['tileset'].lower(); wanted = {name.lower(): them for name, them in spec['tiles'].items()}; cache, found, seen = {}, [], set()
    for name, _, text, _, _ in inventory.drawn_copies(repo, tileset, None, lamps.PACKS):
        if name not in wanted:
            continue
        seen.add(name); _, _, nodes = geometry.parse(effects.without_fx(detail.without_kit(text))); moves = geometry.placed(nodes); drawn = []
        for node in nodes:
            if node.rendered:
                points = [moves[id(node)](vertex) for vertex in node.verts]
                drawn += [(node.name, point) for face in node.faces if max(face[:3]) < len(points) for point in geometry.samples(tuple(points[corner] for corner in face[:3]), 0.15)]
        for number, one in enumerate(wanted[name]):
            if one['piece'] in effects.EFFECTS or one['piece'] in detail.CLIMBERS or one.get('blocks') or one.get('obstacle'):
                continue
            faces = geometry.faces_of(geometry.baked(detail.piece_parts(kit, one['piece'], cache), detail.turned(one['at'], one.get('turn', 0.0), one.get('scale', 1.0))))
            turn = math.radians(one.get('turn', 0.0)); out = (-math.sin(turn), math.cos(turn))
            try:
                detail._clear(name, number, one['piece'], faces, [], {}, (out, one['at'][0] * out[0] + one['at'][1] * out[1]), drawn)
            except ValueError as error:
                found.append({'tile': name, 'piece': one['piece'], 'number': number, 'why': str(error)})
    missing = sorted(set(wanted) - seen); require(not missing, 'No uncompiled model of the tileset is ' + ', '.join(missing))
    return found
