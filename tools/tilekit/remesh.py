"""A tile's visible meshes replaced by rebuilt ones, everything else kept.

A rebuild is an uncompiled model `<tile>.mdl` in a source folder, drawn in the tile's coordinates. Its rendered
trimesh nodes replace the tile's rendered meshes; the tile's walkmesh, door hooks, lamps, emitters, unrendered meshes
and the kit pieces `detail` added stay as they are. The rebuilt meshes are merged into one node per look.

The shape may change only where a player does not stand. A rebuild is refused:

- where it leaves the tile's cell;
- where its massing below `geometry.HEAD` metres over the tile's root reaches a grid cell the original's does not
  (one step of tolerance);
- where it stands in the space over a walkable face, street or roof, that the original left clear;
- where it no longer draws a floor the original drew over a walkable face (a walkable roof stays where it is);
- where its profile on the cell's sides has a point the original's lacks, so a neighbour still meets it.

With `joins` (a terrain, every tile of it rebuilt or left as it is), a side may change: a side whose two corners are
not of the terrain (a facade, the street's) only rises where its wall reaches its top already (a parapet); any other
side only where every side it can meet, of a tile of the terrain with the same corners the other way round, draws the
same (a crown running on across the tiles, `crown`).

Changed models are written into a review's overlay with `models-from.json`, as `lamps`, `shadows` and `detail` do."""
from pathlib import Path

from . import detail, geometry, inventory, lamps, require

MARK = '_rm'  # rebuilt meshes are named <tile>_rmNN
SIDES = {'n': (1, 0), 'w': (0, 2), 's': (2, 3), 'e': (3, 1)}  # a side's two corners (TopLeft, TopRight, BottomLeft, BottomRight), counter-clockwise round the tile


def _round(side, along):
    """A side's step `along` counted counter-clockwise round the tile: two tiles that meet count their shared side the
    opposite ways, so one's step t is the other's -1 - t."""
    return along if side in ('s', 'e') else -1 - along


def _profiles(found):
    """{side: {(step round the tile, height)}} of `geometry.sides`."""
    made = {side: set() for side in SIDES}
    for side, along, height in found:
        made[side].add((_round(side, along), height))
    return made


def _grown_sides(found):
    return {(side, along + da, height + dh) for side, along, height in found for da in (-1, 0, 1) for dh in (-1, 0, 1)}


def _say(cells, step=geometry.STEP, most=4):
    return ', '.join(f'({key[0] * step:.2f}, {key[1] * step:.2f})' for key in sorted(cells)[:most]) + (f' and {len(cells) - most} more' if len(cells) > most else '')


def _unlisted(text, gone):
    """`text` with the animation entries of the nodes named in `gone` taken out (their geometry is gone already)."""
    out, skipping = [], False
    for line in text.replace('\r\n', '\n').split('\n'):
        words = line.split()
        if not skipping and len(words) >= 3 and words[0].lower() == 'node' and words[2].lower() in gone:
            skipping = True; continue
        if skipping:
            skipping = not (words[:1] and words[0].lower() == 'endnode'); continue
        out.append(line)
    return detail._ending(text).join(out)


def rebuilt(text, name, source_text, facades=None, add=False):
    """(new text, {faces before, faces after, nodes before, nodes after}, {side: added profile} or None, what it draws
    after) of a tile model with its visible meshes replaced by those of `source_text`, refused where the shape changes
    where a player stands. `facades` (the sides whose corners are the street's) lets its sides change as `joins` says.
    `add`: the tile's own meshes stay as they are, under the parents and in the animations they have (a tile's lit
    windows hang from its animated dummy), and `source_text` is drawn as well (a crown)."""
    lines, _, nodes = geometry.parse(text)
    replaced = [node for node in nodes if node.rendered and not detail.is_kit(node.name)]
    require(replaced, f'{name} draws nothing to replace')
    gone = set() if add else {node.name.lower() for node in replaced}
    orphans = [node.name for node in nodes if node.name.lower() not in gone and node.parent and node.parent.lower() in gone]
    require(not orphans, f'{name}: {", ".join(orphans[:4])} hang from meshes the rebuild replaces; give them a parent that stays')
    _, _, source = geometry.parse(source_text); parts = geometry.baked(source); require(parts, f'The rebuild of {name} draws nothing')
    before = list(geometry.triangles(nodes, lambda node: node in replaced))  # placed through the whole model's hierarchy
    after = (before if add else []) + list(geometry.faces_of(parts))
    walk = geometry.walkable(nodes)
    reach = geometry.reach(before)  # the original may overhang its cell (cornices); the rebuild no further than it did
    out = geometry.beyond(after, reach); require(not out, f'The rebuild of {name} reaches past its cell further than the original at ' + ', '.join(map(str, out[:3])))
    wider = geometry.low_massing(after) - geometry.grown(geometry.low_massing(before))
    require(not wider, f'The rebuild of {name} changes the shape below {geometry.HEAD} m at {_say(wider)}')
    blocking = set(geometry.in_the_way(after, walk)) - geometry.grown(set(geometry.in_the_way(before, walk)))
    require(not blocking, f'The rebuild of {name} stands where a player walks at {_say(blocking)}')
    lost = geometry.floors(before, walk) - geometry.grown(geometry.floors(after, walk))
    require(not lost, f'The rebuild of {name} draws no floor over walkable ground it had at {_say(lost)}')
    was = geometry.sides(before); edge = geometry.sides(after) - _grown_sides(was); added = None
    if facades is not None:  # `joins`: a facade's wall may rise; the other sides' changes are checked against the sides they meet
        tops = {}
        for side, along, height in was:
            tops[(side, along)] = max(height, tops.get((side, along), height))
        highest = {side: max((height for (where, _), height in tops.items() if where == side), default=None) for side in SIDES}
        risen = {(side, along, height) for side, along, height in edge if side in facades and highest[side] is not None
                 and any(tops.get((side, along + shift), -1) >= highest[side] - 1 for shift in (-1, 0, 1))}
        added = _profiles({point for point in edge if point[0] not in facades}); edge = {point for point in edge if point[0] in facades} - risen
    require(not edge, f'The rebuild of {name} changes its sides where a neighbour meets them: ' + ', '.join(f'{side} {along * geometry.STEP:.2f} m along at {height * geometry.STEP:.2f} m' for side, along, height in sorted(edge)[:4]))
    drop = {index for node in replaced if not add for index in range(node.start, node.end + 1)}
    kept = detail._ending(text).join(line for index, line in enumerate(lines) if index not in drop)
    kept = _unlisted(kept, gone)  # the animations name them no longer: a node they list is one the model has
    new, count = detail.added(kept, name, parts, mark=MARK)  # not named as kit pieces: a later `detail` keeps them
    require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
    return new, {'faces': [len(before), len(after)], 'nodes': [len(replaced), count + (len(replaced) if add else 0)]}, added, after


def _laid(repo, tileset, folder):
    """{model: corners} of the tileset's set file, the overlay's copy (a copied terrain's) before the pack's."""
    path = next((one for one in (Path(folder) / f'{tileset}.set', Path(repo) / f'srn_t_{tileset}' / f'{tileset}.set') if one.is_file()), None)
    require(path, f'No set file of {tileset}')
    laid = {}
    for tile in inventory.read_set(path.read_bytes().decode('cp1252'))['tiles']:
        laid.setdefault(tile['model'].lower(), [corner.lower() for corner in tile['corners']])
    return laid


def _joined(joins, laid, texts, rebuilds, added):
    """Refuse a side a rebuild changed where a side of the terrain `joins` that can meet it does not draw the same.
    `rebuilds` {model: what it draws rebuilt}, `added` {model: {side: added profile}}."""
    ours = {model: corners for model, corners in laid.items() if joins in corners}
    strays = sorted(set(rebuilds) - set(ours)); require(not strays, f'{", ".join(strays)}: no tile of {joins}, which only its own tiles join')
    profiles = {}
    for model in ours:
        require(model in texts, f'{model} ({joins}) has no uncompiled model')
        if model in rebuilds:
            drawn = rebuilds[model]
        else:
            drawn = geometry.triangles(geometry.parse(texts[model])[2], lambda node: node.rendered and not detail.is_kit(node.name))
        profiles[model] = _profiles(geometry.sides(drawn))
    ends = lambda model, side: tuple(ours[model][corner] for corner in SIDES[side])
    for model in sorted(added):
        for side, points in sorted(added[model].items()):
            if not points:
                continue
            meets = [(other, across) for other in sorted(ours) for across in SIDES if ends(other, across) == ends(model, side)[::-1]]
            require(meets, f'{model}: its {side} side changes, and no tile of {joins} meets it there')
            for other, across in meets:
                there = {(-1 - step + shift, height + lift) for step, height in profiles[other][across] for shift in (-1, 0, 1) for lift in (-1, 0, 1)}
                lacking = sorted(points - there)
                require(not lacking, f"{model}: its {side} side draws what {other}'s {across} side, which meets it, does not, at "
                        + ', '.join(f'{step * geometry.STEP:.2f} m round, {height * geometry.STEP:.2f} m up' for step, height in lacking[:3]) + '; draw both alike')


def remesh(repo, tileset, tiles, source, folder, joins=None, add=False):
    """Replace the visible meshes of `tiles` with the rebuilds in `source`, written into `folder` (a review's
    overlay). `joins`: a terrain whose tiles' sides may change where they meet one another alike (`crown`). `add`:
    keep the tiles' own meshes and draw the rebuilds as well. {tile: faces and nodes before and after}."""
    from .apply import noted
    require(tiles, 'Name the tiles to rebuild'); wanted = {name.lower() for name in tiles}; folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    joins = joins.lower() if joins else None; laid = _laid(repo, tileset.lower(), folder)
    made, told, texts, rebuilds, added = {}, {}, {}, {}, {}
    drawn = list(inventory.drawn_copies(repo, tileset.lower(), folder, lamps.PACKS)); known = {entry[0] for entry in drawn}
    for name in sorted(set(laid) - known):  # a copied terrain's new tiles, in the overlay alone (`terrain`): no pack copy to note
        path = folder / f'{name}.mdl'
        if path.is_file() and not inventory.compiled(path.read_bytes()):
            drawn.append((name, path.name, path.read_bytes().decode('cp1252'), [], None))
    for name, file, text, others, pack in drawn:
        texts[name] = text
        if name not in wanted:
            continue
        require(not others, f'{name} is drawn by other tilesets too ({", ".join(others)}): its rebuild would show there')
        path = Path(source) / file; require(path.is_file(), f'No rebuild of {name} in {source}')
        data = path.read_bytes(); require(not inventory.compiled(data), f'The rebuild of {name} is an uncompiled model')
        require(not joins or name in laid, f'{name} is no tile of the set file, so `joins` cannot say which of its sides meet')
        fronts = {side for side, (one, other) in SIDES.items() if joins not in (laid[name][one], laid[name][other])} if joins else None
        new, said, added[name], rebuilds[name] = rebuilt(text, name, data.decode('cp1252'), fronts, add); made[name] = (file, pack, new, said)
    missing = sorted(wanted - set(made)); require(not missing, 'No uncompiled model of the tileset is ' + ', '.join(missing))
    if joins:
        _joined(joins, laid, texts, rebuilds, added)
    for name, (file, pack, new, said) in made.items():
        if pack is not None:
            noted(folder, file, pack)
        (folder / file).write_bytes(new.encode('cp1252')); told[name] = said
    return told
