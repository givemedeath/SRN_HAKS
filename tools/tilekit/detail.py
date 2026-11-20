"""Kit pieces added to a tileset's tiles: air conditioners, pipes, fire escapes, signs, roof clutter.

A placement spec says which pieces go on which tile, where and turned how far: {tileset, tiles: {tile model:
[{piece, at: [x, y, z], turn: degrees about the vertical, scale}]}}. A piece is an uncompiled model in the kit folder,
`<piece>.mdl`, its origin where it is fixed to the building. Its rendered trimesh nodes are baked into the tile's
coordinates, and the tile's added geometry is merged into one node per look (material and drawing settings), so a
tile gains as few draws as the materials it adds.

A placement is refused where it would put geometry outside the tile's cell, other than flush to its side or out over
the neighbouring street above a player's head (`geometry.overhanging`: a facade stands on the cell's side), or between `geometry.LOW` and
`geometry.HEAD` metres over any walkable face, the street and walkable roofs alike: the walkmesh is not changed, so
a player would walk through it. A piece marked `blocks` is cover instead: it stands on a walkable roof, and its
footprint is raised out of the roof's walkmesh to the piece's top (`cuts`), so nothing walks through it or sees past it.
The walkmesh is hashed before and after. Changed models are written into a review's
overlay, with `models-from.json`, as the lamps and shadows are, and a model there already (the lamps') is the one
changed; a tile's earlier pieces there are replaced, so the spec can be run again as it changes."""
import math
from pathlib import Path

from . import cuts, effects, geometry, inventory, lamps, require

MARK = '_kit'  # added nodes are named <tile>_kitNN
STANDOFF = 0.2  # metres off the cell's side beyond which a tile's own geometry is a fixture on its wall, not the wall


def turned(at, turn, scale):
    """The move of a piece's point to the tile's coordinates: scaled, turned about the vertical, then put `at`."""
    angle = math.radians(turn); c, s = math.cos(angle), math.sin(angle)

    def move(point):
        x, y, z = (value * scale for value in point)
        return (x * c - y * s + at[0], x * s + y * c + at[1], z + at[2])
    return move


def _ending(text):
    return '\r\n' if '\r\n' in text else '\n'


def is_kit(name):
    """Whether a node is one an earlier run of `detail` added."""
    head, said, number = name.lower().rpartition(MARK)
    return bool(head and said and number.isdigit())


def without_kit(text):
    """The model's text with the kit nodes an earlier run added taken out."""
    lines, _, nodes = geometry.parse(text); drop = set()
    for node in nodes:
        if is_kit(node.name):
            drop.update(range(node.start, node.end + 1))
    return _ending(text).join(line for index, line in enumerate(lines) if index not in drop)


def added(text, name, parts, mark=MARK):
    """(text, nodes added) of the model with `parts` [(look, verts, tverts, faces)], already in the tile's coordinates,
    merged by look and added under its root just before its geometry ends, named <name><mark>NN."""
    lines, root, nodes = geometry.parse(text)
    end = next(index for index, line in enumerate(lines) if line.split()[:1] and line.split()[0].lower() == 'endmodelgeom')
    made, joined = [], geometry.merged(parts); taken = {node.name.lower() for node in nodes}
    for number, (look, verts, tverts, faces) in enumerate(joined):
        node = f'{name}{mark}{number:02d}'; require(node.lower() not in taken, f'{name} already has a node named {node}')
        made += geometry.mesh_text(node, root, look, verts, tverts, faces)
    return _ending(text).join(lines[:end] + made + lines[end:]), len(joined)


def piece_parts(kit, piece, cache):
    if piece not in cache:
        path = Path(kit) / f'{piece}.mdl'; require(path.is_file(), f'No kit piece {piece} in {kit}')
        data = path.read_bytes(); require(not inventory.compiled(data), f'{piece}: a kit piece is an uncompiled model')
        _, _, nodes = geometry.parse(data.decode('cp1252')); cache[piece] = nodes
    return cache[piece]


def with_walkmesh_of(text, pack_text):
    """`text` with its walkmesh node taken from `pack_text`: a run cuts the pack's walkmesh again, never its own cut."""
    lines, _, nodes = geometry.parse(text); theirs, _, their_nodes = geometry.parse(pack_text)
    mine = [node for node in nodes if node.kind == 'aabb']; pack = [node for node in their_nodes if node.kind == 'aabb']
    if not mine and not pack:
        return text
    require(len(mine) == 1 and len(pack) == 1 and mine[0].name.lower() == pack[0].name.lower(), 'The overlay copy and the pack copy have different walkmesh nodes')
    return _ending(text).join(lines[:mine[0].start] + theirs[pack[0].start:pack[0].end + 1] + lines[mine[0].end + 1:])


def place(text, name, placements, kit, cache=None, *, pack_text=None, wok=None):
    """(new text, {pieces, faces, nodes, cuts}, new .wok text or None) of a tile model with its placements added,
    refused where a piece leaves the cell or stands where a player walks. A piece that `blocks` stands on a walkable
    roof instead, and its footprint is cut out of the roof's walkmesh (`cuts`): `wok`, the tile's .wok, is cut with it."""
    cache = {} if cache is None else cache; text = effects.without_fx(without_kit(text))
    if pack_text is not None:
        text = with_walkmesh_of(text, pack_text)
    _, root, nodes = geometry.parse(text); walk = geometry.walkable(nodes); parts, footprints, fx = [], [], []
    moves = geometry.placed(nodes)  # what the tile already hangs off its walls (lamps, signs): a wall piece keeps clear of it
    fixtures = [(node.name, point) for node in nodes if node.rendered for point in map(moves[id(node)], node.verts)
                if max(abs(point[0]), abs(point[1])) - geometry.HALF > STANDOFF]
    for number, placement in enumerate(placements):
        piece = placement['piece']; at = placement['at']
        if piece in effects.EFFECTS:  # an emitter, not geometry (`effects`)
            effects.check(name, number, at, piece); fx.append((piece, at, placement.get('fall'), placement.get('seed'))); continue
        require(isinstance(at, list) and len(at) == 3 and all(isinstance(value, (int, float)) for value in at), f'{name} #{number}: `at` is [x, y, z]')
        scale = placement.get('scale', 1.0); require(isinstance(scale, (int, float)) and scale > 0, f'{name} #{number}: `scale` is a positive number')
        blocks = placement.get('blocks', False); require(isinstance(blocks, bool), f'{name} #{number}: `blocks` is true or false')
        mine = geometry.baked(piece_parts(kit, piece, cache), turned(at, placement.get('turn', 0.0), scale))
        require(mine, f'{piece} draws nothing'); faces = geometry.faces_of(mine)
        out = geometry.overhanging(faces); require(not out, f'{name} #{number} ({piece}) leaves the cell, other than flush to its side or over the street above {geometry.OVER} m, at ' + ', '.join(map(str, out[:3])))
        if blocks:  # cover: cut out of the roof it stands on, so nothing walks through it or sees past it
            heights = walk.get(geometry.cell(at), [])
            roof = min(heights, key=lambda height: abs(height - at[2]), default=None)
            require(roof is not None and abs(roof - at[2]) <= cuts.STOREY, f'{name} #{number} ({piece}) blocks, so it stands on a walkable surface: there is none at {at}')
            require(roof > geometry.HEAD, f'{name} #{number} ({piece}) blocks, and only on a roof: the walkable surface at {at} is {roof:.2f} m up, street level')
            cover = placement.get('cover')  # a block smaller than the piece: a mast's foot, not its crossbars
            if cover is None:
                polygon, top = cuts.hull([(x, y) for _, verts, _, _ in mine for x, y, _ in verts]), max(z for _, verts, _, _ in mine for _, _, z in verts)
            else:
                require(isinstance(cover, dict) and len(cover.get('size', ())) == 2 and isinstance(cover.get('height'), (int, float)), f'{name} #{number}: `cover` is {{size: [width, depth], height}}')
                move = turned(at, placement.get('turn', 0.0), scale); width, depth = (value / 2 for value in cover['size'])
                polygon = cuts.hull([move((x, y, 0.0))[:2] for x, y in ((-width, -depth), (width, -depth), (width, depth), (-width, depth))]); top = at[2] + cover['height'] * scale
            footprints.append((polygon, roof, top))
            outside = {key: heights for key, heights in geometry.in_the_way(faces, walk).items()
                       if not cuts.covers(polygon, ((key[0] + 0.5) * geometry.STEP, (key[1] + 0.5) * geometry.STEP), geometry.STEP)}
            require(not outside, f'{name} #{number} ({piece}) reaches past its cover where a player walks; raise that part above head height or widen `cover`')
        else:
            low = [min(point[axis] for face in faces for point in face) - 0.02 for axis in range(3)]
            high = [max(point[axis] for face in faces for point in face) + 0.02 for axis in range(3)]
            hit = sorted({fixture for fixture, point in fixtures if all(low[axis] <= point[axis] <= high[axis] for axis in range(3))})
            require(not hit, f'{name} #{number} ({piece}) runs into what the tile already has there ({", ".join(hit)}); move it clear')
            blocked = geometry.in_the_way(faces, walk)
            require(not blocked, f'{name} #{number} ({piece}) stands where a player walks, over the walkable surface at '
                    + ', '.join(f'{heights}' for heights in list(blocked.values())[:3]) + ' m; move it off the walkable faces or above head height, or make it block (roofs only)')
        parts += mine
    new, count = added(text, name, parts); new, emitters = effects.added(new, root, fx); cut = None
    if footprints:
        require(wok is not None, f'{name} has no .wok to cut'); new, cut = cuts.cut_walkmesh(new, wok, footprints)
    else:
        require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
    return new, {'pieces': len(placements) - emitters, 'faces': sum(len(part[3]) for part in parts), 'nodes': count, 'effects': emitters, 'cuts': len(footprints)}, cut, footprints


def detail(repo, spec, kit, folder):
    """Add the spec's pieces to its tiles' models, written into `folder` (a review's overlay), with the walkmeshes of
    tiles that have blocking pieces cut and recorded (`cuts.WALK_CUTS`). {tile: what was added}."""
    from .apply import noted
    require(isinstance(spec, dict) and isinstance(spec.get('tiles'), dict) and spec['tiles'], 'A placement spec names its tileset and its tiles')
    tileset = spec['tileset'].lower(); folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    wanted = {name.lower(): placements for name, placements in spec['tiles'].items()}; told, cache, made = {}, {}, {}
    for name, file, text, others, source in inventory.drawn_copies(repo, tileset, folder, lamps.PACKS):
        if name not in wanted:
            continue
        require(not others, f'{name} is drawn by other tilesets too ({", ".join(others)}): its pieces would show there')
        pack_text = Path(source).read_bytes().decode('cp1252'); wok_path = Path(source).with_suffix('.wok')
        wok = wok_path.read_bytes().decode('cp1252') if wok_path.is_file() else None
        made[name] = (file, source, wok_path, wok, pack_text, *place(text, name, wanted[name], kit, cache, pack_text=pack_text, wok=wok))
    missing = sorted(set(wanted) - set(made)); require(not missing, 'No uncompiled model of the tileset is ' + ', '.join(missing))
    pictures = sorted({effects.EFFECTS[one['piece']]['texture'] for placements in wanted.values() for one in placements
                       if one.get('piece') in effects.EFFECTS and not effects.EFFECTS[one['piece']].get('stock')})
    for picture in pictures:
        require((Path(kit) / f'{picture}.tga').is_file(), f'No effect picture {picture}.tga in {kit}')
    for picture in pictures:
        (folder / f'{picture}.tga').write_bytes((Path(kit) / f'{picture}.tga').read_bytes())
    for name, (file, source, wok_path, wok, pack_text, new, said, cut, footprints) in made.items():  # every tile checked before any is written
        noted(folder, file, source); (folder / file).write_bytes(new.encode('cp1252')); told[name] = said
        if cut is not None:
            noted(folder, wok_path.name, wok_path); (folder / wok_path.name).write_bytes(cut.encode('cp1252'))
            cuts.noted(folder, tileset, name, pack_text, new, wok, cut, footprints)
        else:  # no blocking piece now: an earlier run's cut walkmesh goes, and the model keeps the pack's
            (folder / wok_path.name).unlink(missing_ok=True); cuts.forget(folder, name)
    return told
