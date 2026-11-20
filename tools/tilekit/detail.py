"""Kit pieces added to a tileset's tiles: air conditioners, pipes, fire escapes, signs, roof clutter.

A placement spec says which pieces go on which tile, where and turned how far: {tileset, tiles: {tile model:
[{piece, at: [x, y, z], turn: degrees about the vertical, scale}]}}. A piece is an uncompiled model in the kit folder,
`<piece>.mdl`, its origin where it is fixed to the building. Its rendered trimesh nodes are baked into the tile's
coordinates, and the tile's added geometry is merged into one node per look (material and drawing settings), so a
tile gains as few draws as the materials it adds. A piece with a turning head (`kit.SWEEPS`: a security camera) has
its head as a node of its own at the pivot, swept slowly from side to side in the tile's always-on animation.

A placement is refused where it would put geometry outside the tile's cell, other than flush to its side or out over
the neighbouring street above a player's head (`geometry.overhanging`: a facade stands on the cell's side), or between `geometry.LOW` and
`geometry.HEAD` metres over any walkable face, the street and walkable roofs alike: the walkmesh is not changed, so
a player would walk through it. A piece marked `blocks` is cover instead: it stands on a walkable roof, and its
footprint is raised out of the roof's walkmesh to the piece's top (`cuts`), so nothing walks through it or sees past it.
The walkmesh is hashed before and after. Changed models are written into a review's
overlay, with `models-from.json`, as the lamps and shadows are, and a model there already (the lamps') is the one
changed; a tile's earlier pieces there are replaced, so the spec can be run again as it changes. The kit's atlas
(its material and maps, from `<kit>/atlas`) and the effects' pictures are copied in beside them and recorded in
`apply.KIT_FILES`, so `apply` brings them to the tileset's own pack."""
import hashlib
import json
import math
from pathlib import Path

from . import cuts, effects, geometry, inventory, lamps, require

MARK = '_kit'  # added nodes are named <tile>_kitNN
STANDOFF = 0.2  # metres off the cell's side beyond which a tile's own geometry is a fixture on its wall, not the wall


def turned(at, turn, scale):
    """The move of a piece's point to the tile's coordinates: scaled (one number, or [across, out, up] in the piece's
    own axes), turned about the vertical, then put `at`."""
    angle = math.radians(turn); c, s = math.cos(angle), math.sin(angle)
    scales = tuple(scale) if isinstance(scale, (list, tuple)) else (scale,) * 3

    def move(point):
        x, y, z = (value * factor for value, factor in zip(point, scales))
        return (x * c - y * s + at[0], x * s + y * c + at[1], z + at[2])
    return move


def _ending(text):
    return '\r\n' if '\r\n' in text else '\n'


def is_kit(name):
    """Whether a node is one an earlier run of `detail` added."""
    head, said, number = name.lower().rpartition(MARK)
    return bool(head and said and number.isdigit())


def without_kit(text):
    """The model's text with the kit nodes an earlier run added taken out, from its geometry and its animations (a
    turning head's keys)."""
    def dropped(text, gone):
        out, skipping = [], False
        for line in text.replace('\r\n', '\n').split('\n'):
            words = line.split()
            if not skipping and len(words) >= 3 and words[0].lower() == 'node' and gone(words[2]):
                skipping = True; continue
            if skipping:
                skipping = not (words[:1] and words[0].lower() == 'endnode'); continue
            out.append(line)
        return _ending(text).join(out)
    text = dropped(text, is_kit)
    lines, root, nodes = geometry.parse(text); dummy = f'{root}a'.lower()  # the animation dummy `heads` added (marked), now holding nothing
    ours = [node for node in nodes if node.name.lower() == dummy and any(line.strip() == DUMMY_MARK for line in lines[node.start:node.end])]
    if ours and not any((node.parent or '').lower() == dummy for node in nodes):
        text = dropped(text, lambda name: name.lower() == dummy)
    return text


LOOPS = ('animloop01', 'animloop02', 'animloop03')  # a tile's looping animations, each played where its AnimLoop flag is on
STUB = 0.5  # seconds: a tile's own loop no longer than this moves nothing, so a sweep may take it and lengthen it
KEYS = 32  # orientation keys in one sweep there and back
DUMMY_MARK = '# tilekit: animation dummy for turning heads'  # on a dummy `heads` adds; most tiles have an empty one of their own, kept


def heads(text, root, turning):
    """(text, loop number) of `text` with each of `turning` [(node, look, verts, tverts, faces, pivot, turn, sweep,
    period)] added as its own node at its pivot, its vertices about the pivot, and turned slowly from side to side about
    the vertical in one of the tile's looping animations: `turn` ± `sweep` degrees, there and back in `period` seconds,
    slowing at each end. The client animates only what hangs from the tile's animation dummy, <root>a, at the root's
    origin (nwn.wiki, Animations: tile animations; heads hung from the root sat still, 2026-11-20), and plays a loop
    only where the tile's AnimLoop flag is on (the .set's, copied into each area tile as Tile_AnimLoopN); `tiledefault`
    only puts a tile back to rest. The loop taken is the first the tile has no moving animation in."""
    if not turning:
        return text, None
    ending = _ending(text); lines = text.replace('\r\n', '\n').split('\n')
    end = next(index for index, line in enumerate(lines) if line.split()[:1] and line.split()[0].lower() == 'endmodelgeom')
    dummy = f'{root}a'; made = []
    if dummy.lower() not in {node.name.lower() for node in geometry.parse(text)[2]}:
        made += [f'node dummy {dummy}', f'  parent {root}', '  position 0.0 0.0 0.0', '  orientation 0.0 0.0 0.0 0.0', '  ' + DUMMY_MARK, 'endnode']
    for node, look, verts, tverts, faces, pivot, turn, sweep, period in turning:
        mesh = geometry.mesh_text(node, dummy, look, verts, tverts, faces)
        mesh[2] = '  position ' + ' '.join(f'{value:.5f}' for value in pivot); mesh[3] = f'  orientation 0.0 0.0 1.0 {math.radians(turn):.6f}'
        made += mesh
    lines = lines[:end] + made + lines[end:]
    periods = {one[-1] for one in turning}; require(len(periods) == 1, f'{root}: turning heads with different periods share one animation')
    period = periods.pop(); keyed = {}
    for node, _, _, _, _, pivot, turn, sweep, _ in turning:  # it stays at its pivot, and turns
        rows = [f'      {period * step / KEYS:.5f} 0.00000 0.00000 1.00000 {math.radians(turn + sweep * math.sin(2 * math.pi * step / KEYS)):.5f}' for step in range(KEYS + 1)]
        still = [f'      {time:.5f} ' + ' '.join(f'{value:.5f}' for value in pivot) for time in (0.0, period)]
        keyed[node.lower()] = [f'    orientationkey {len(rows)}', *rows, f'    positionkey {len(still)}', *still]
    _, _, nodes = geometry.parse(ending.join(lines))  # a loop lists the model's nodes in its geometry's order, as the tiles' own do

    def entry(node):
        return [f'  node {node.kind} {node.name}', f'    parent {node.parent or "null"}', *keyed.get(node.name.lower(), []), '  endnode']

    def block_of(name):
        start = next((index for index, line in enumerate(lines) if line.split()[:2] and line.split()[0].lower() == 'newanim' and line.split()[1].lower() == name), None)
        if start is None:
            return None
        stop = next(index for index in range(start, len(lines)) if lines[index].split()[:1] and lines[index].split()[0].lower() == 'doneanim')
        length = next((index for index in range(start, stop) if lines[index].split()[:1] and lines[index].split()[0].lower() == 'length'), None)
        require(length is not None, f'{root}: its {name} animation has no length')
        return start, stop, length
    for number, name in enumerate(LOOPS, 1):
        found = block_of(name)
        if found is None:  # none yet: one of its own, before the model ends
            done = max(index for index, line in enumerate(lines) if line.split()[:1] and line.split()[0].lower() == 'donemodel')
            block = [f'newanim {name} {root}', f'  length {period:.4f}', '  transtime 0.0', f'  animroot {root}', *[line for node in nodes for line in entry(node)], f'doneanim {name} {root}', '']
            return ending.join(lines[:done] + block + lines[done:]), number
        start, stop, length = found; had = float(lines[length].split()[1])
        if had > STUB and abs(had - period) >= 1e-3:  # it moves something of the tile's own: the next loop
            continue
        listed = [words[2].lower() for words in (line.split() for line in lines[start:stop]) if len(words) >= 3 and words[0].lower() == 'node']
        require(listed == [node.name.lower() for node in nodes][:len(listed)], f'{root}: its {name} animation does not list the model\'s nodes in their order, so nodes added after them cannot be')
        lines[length] = f'  length {period:.4f}'
        return ending.join(lines[:stop] + [line for node in nodes[len(listed):] for line in entry(node)] + lines[stop:]), number
    require(False, f'{root}: all three of its looping animations move parts of its own; a turning head has none to play in')


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


def _clear(name, number, piece, faces, fixtures, walk):
    """Refuse a wall piece's `faces` where they run into what the tile hangs on its walls already, or stand where a player walks."""
    low = [min(point[axis] for face in faces for point in face) - 0.02 for axis in range(3)]
    high = [max(point[axis] for face in faces for point in face) + 0.02 for axis in range(3)]
    hit = sorted({fixture for fixture, point in fixtures if all(low[axis] <= point[axis] <= high[axis] for axis in range(3))})
    require(not hit, f'{name} #{number} ({piece}) runs into what the tile already has there ({", ".join(hit)}); move it clear')
    blocked = geometry.in_the_way(faces, walk)
    require(not blocked, f'{name} #{number} ({piece}) stands where a player walks, over the walkable surface at '
            + ', '.join(f'{heights}' for heights in list(blocked.values())[:3]) + ' m; move it off the walkable faces or above head height, or make it block (roofs only)')


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
    """(new text, {pieces, faces, nodes, cuts}, new .wok text or None, footprints [(polygon, roof, top)]) of a tile model with its placements added,
    refused where a piece leaves the cell or stands where a player walks. A piece that `blocks` stands on a walkable
    roof instead, and its footprint is cut out of the roof's walkmesh (`cuts`): `wok`, the tile's .wok, is cut with it."""
    from .kit import SWEEPS
    cache = {} if cache is None else cache; text = effects.without_fx(without_kit(text)); turning = []
    if pack_text is not None:  # an applied batch: its walkmesh is cut already, and cut again it refuses its own roof clutter
        require(not any(is_kit(node.name) for node in geometry.parse(pack_text)[2]), f'{name}: the pack copy has kit pieces already (an applied batch): detail it again from the copy before that apply')
        text = with_walkmesh_of(text, pack_text)
    _, root, nodes = geometry.parse(text); walk = geometry.walkable(nodes); parts, footprints, fx = [], [], []
    moves = geometry.placed(nodes)  # what the tile already hangs off its walls (lamps, signs): a wall piece keeps clear of it
    fixtures = [(node.name, point) for node in nodes if node.rendered for point in map(moves[id(node)], node.verts)
                if max(abs(point[0]), abs(point[1])) - geometry.HALF > STANDOFF]
    for number, placement in enumerate(placements):
        piece = placement['piece']; at = placement['at']
        if piece in effects.EFFECTS:  # an emitter, not geometry (`effects`)
            effects.check(name, number, at, piece); fx.append((piece, at, placement.get('fall'))); continue
        require(isinstance(at, list) and len(at) == 3 and all(isinstance(value, (int, float)) for value in at), f'{name} #{number}: `at` is [x, y, z]')
        scale = placement.get('scale', 1.0)
        require(isinstance(scale, (int, float)) and scale > 0 or isinstance(scale, list) and len(scale) == 3 and all(isinstance(value, (int, float)) and value > 0 for value in scale),
                f'{name} #{number}: `scale` is a positive number, or three: [across, out, up]')
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
                polygon, top = cuts.outline([(x, y) for _, verts, _, _ in mine for x, y, _ in verts]), max(z for _, verts, _, _ in mine for _, _, z in verts)
            else:
                require(isinstance(cover, dict) and len(cover.get('size', ())) == 2 and isinstance(cover.get('height'), (int, float)), f'{name} #{number}: `cover` is {{size: [width, depth], height}}')
                move = turned(at, placement.get('turn', 0.0), scale); width, depth = (value / 2 for value in cover['size'])
                polygon = cuts.hull([move((x, y, 0.0))[:2] for x, y in ((-width, -depth), (width, -depth), (width, depth), (-width, depth))]); top = move((0.0, 0.0, cover['height']))[2]
            footprints.append((polygon, roof, top))
            outside = {key: heights for key, heights in geometry.in_the_way(faces, walk).items()
                       if not cuts.covers(polygon, ((key[0] + 0.5) * geometry.STEP, (key[1] + 0.5) * geometry.STEP), geometry.STEP)}
            require(not outside, f'{name} #{number} ({piece}) reaches past its cover where a player walks; raise that part above head height or widen `cover`')
        else:
            _clear(name, number, piece, faces, fixtures, walk)
        parts += mine
        if piece in SWEEPS:  # its head, a node of its own turning about the pivot: clear of everything at both ends of its sweep
            sweep = SWEEPS[piece]; turn = placement.get('turn', 0.0); scales = tuple(scale) if isinstance(scale, list) else (scale,) * 3
            look, verts, tverts, faces = geometry.merged(geometry.baked(piece_parts(kit, sweep['head'], cache), lambda point: tuple(value * factor for value, factor in zip(point, scales))))[0]
            pivot = turned(at, turn, scale)(sweep['pivot'])
            for aside in (-sweep['sweep'], 0.0, sweep['sweep']):
                move = turned(pivot, turn + aside, 1.0); swung = [tuple(move(verts[corner]) for corner in face[:3]) for face in faces]
                out = geometry.overhanging(swung); require(not out, f'{name} #{number} ({sweep["head"]}) leaves the cell turned {aside:+.0f} degrees, at ' + ', '.join(map(str, out[:3])))
                _clear(name, number, sweep['head'], swung, fixtures, walk)
            turning.append((look, verts, tverts, faces, pivot, turn, sweep['sweep'], sweep['period']))
    new, count = added(text, name, parts); new, emitters = effects.added(new, root, fx); cut = None
    taken = {node.name.lower() for node in geometry.parse(new)[2]}; named = [f'{name}{MARK}{count + index:02d}' for index in range(len(turning))]
    require(not taken & {one.lower() for one in named}, f'{name} already has a node named like its turning heads')
    new, loop = heads(new, root, [(node, *head) for node, head in zip(named, turning)]); count += len(turning)
    if footprints:
        require(wok is not None, f'{name} has no .wok to cut'); new, cut = cuts.cut_walkmesh(new, wok, footprints)
    else:
        require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
    return new, {'pieces': len(placements) - emitters, 'faces': sum(len(part[3]) for part in parts), 'nodes': count, 'effects': emitters, 'cuts': len(footprints), **({'loop': loop} if loop else {})}, cut, footprints


def detail(repo, spec, kit, folder):
    """Add the spec's pieces to its tiles' models, written into `folder` (a review's overlay), with the walkmeshes of
    tiles that have blocking pieces cut and recorded (`cuts.WALK_CUTS`). {tile: what was added}."""
    from .apply import KIT_FILES, files_of, noted
    from .kit import ATLAS
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
    copied = [Path(kit) / f'{picture}.tga' for picture in pictures]
    if (Path(kit) / 'atlas' / f'{ATLAS}.mtr').is_file() and any(one.get('piece') not in effects.EFFECTS for placements in wanted.values() for one in placements):  # kit pieces draw with the kit's atlas (`kit.build` makes it)
        copied += files_of(Path(kit) / 'atlas', ATLAS)
    for path in copied:
        (folder / path.name).write_bytes(path.read_bytes())
    (folder / KIT_FILES).write_text(json.dumps({'kind': 'tilekit-kit-files', 'tileset': tileset, 'files': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in copied}},
                                               indent=1) + '\n', encoding='utf-8', newline='\n')
    for name, (file, source, wok_path, wok, pack_text, new, said, cut, footprints) in made.items():  # every tile checked before any is written
        noted(folder, file, source); (folder / file).write_bytes(new.encode('cp1252')); told[name] = said
        if cut is not None:
            noted(folder, wok_path.name, wok_path); (folder / wok_path.name).write_bytes(cut.encode('cp1252'))
            cuts.noted(folder, tileset, name, pack_text, new, wok, cut, footprints)
        else:  # no blocking piece now: an earlier run's cut walkmesh goes, and the model keeps the pack's
            (folder / wok_path.name).unlink(missing_ok=True); cuts.forget(folder, name)
    return told
