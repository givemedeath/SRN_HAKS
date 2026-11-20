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

Changed models are written into a review's overlay with `models-from.json`, as `lamps`, `shadows` and `detail` do."""
from pathlib import Path

from . import detail, geometry, inventory, lamps, require

MARK = '_rm'  # rebuilt meshes are named <tile>_rmNN


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


def rebuilt(text, name, source_text):
    """(new text, {faces before, faces after, nodes before, nodes after}) of a tile model with its visible meshes
    replaced by those of `source_text`, refused where the shape changes where a player stands."""
    lines, _, nodes = geometry.parse(text)
    replaced = [node for node in nodes if node.rendered and not detail.is_kit(node.name)]
    require(replaced, f'{name} draws nothing to replace')
    gone = {node.name.lower() for node in replaced}
    orphans = [node.name for node in nodes if node.name.lower() not in gone and node.parent and node.parent.lower() in gone]
    require(not orphans, f'{name}: {", ".join(orphans[:4])} hang from meshes the rebuild replaces; give them a parent that stays')
    _, _, source = geometry.parse(source_text); parts = geometry.baked(source); require(parts, f'The rebuild of {name} draws nothing')
    before, after = geometry.triangles(nodes, lambda node: node in replaced), geometry.faces_of(parts)  # placed through the whole model's hierarchy
    walk = geometry.walkable(nodes)
    reach = geometry.reach(before)  # the original may overhang its cell (cornices); the rebuild no further than it did
    out = geometry.beyond(after, reach); require(not out, f'The rebuild of {name} reaches past its cell further than the original at ' + ', '.join(map(str, out[:3])))
    wider = geometry.low_massing(after) - geometry.grown(geometry.low_massing(before))
    require(not wider, f'The rebuild of {name} changes the shape below {geometry.HEAD} m at {_say(wider)}')
    blocking = set(geometry.in_the_way(after, walk)) - geometry.grown(set(geometry.in_the_way(before, walk)))
    require(not blocking, f'The rebuild of {name} stands where a player walks at {_say(blocking)}')
    lost = geometry.floors(before, walk) - geometry.grown(geometry.floors(after, walk))
    require(not lost, f'The rebuild of {name} draws no floor over walkable ground it had at {_say(lost)}')
    edge = geometry.sides(after) - _grown_sides(geometry.sides(before))
    require(not edge, f'The rebuild of {name} changes its sides where a neighbour meets them: ' + ', '.join(f'{side} {along * geometry.STEP:.2f} m along at {height * geometry.STEP:.2f} m' for side, along, height in sorted(edge)[:4]))
    drop = {index for node in replaced for index in range(node.start, node.end + 1)}
    kept = detail._ending(text).join(line for index, line in enumerate(lines) if index not in drop)
    kept = _unlisted(kept, gone)  # the animations name them no longer: a node they list is one the model has
    new, count = detail.added(kept, name, parts, mark=MARK)  # not named as kit pieces: a later `detail` keeps them
    require(inventory.walk_hash(new) == inventory.walk_hash(text), f'{name}: the walkmesh would change')
    return new, {'faces': [len(before), len(after)], 'nodes': [len(replaced), count]}


def remesh(repo, tileset, tiles, source, folder):
    """Replace the visible meshes of `tiles` with the rebuilds in `source`, written into `folder` (a review's
    overlay). {tile: faces and nodes before and after}."""
    from .apply import noted
    require(tiles, 'Name the tiles to rebuild'); wanted = {name.lower() for name in tiles}; folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    made, told = {}, {}
    for name, file, text, others, pack in inventory.drawn_copies(repo, tileset.lower(), folder, lamps.PACKS):
        if name not in wanted:
            continue
        require(not others, f'{name} is drawn by other tilesets too ({", ".join(others)}): its rebuild would show there')
        path = Path(source) / file; require(path.is_file(), f'No rebuild of {name} in {source}')
        data = path.read_bytes(); require(not inventory.compiled(data), f'The rebuild of {name} is an uncompiled model')
        made[name] = (file, pack, *rebuilt(text, name, data.decode('cp1252')))
    missing = sorted(wanted - set(made)); require(not missing, 'No uncompiled model of the tileset is ' + ', '.join(missing))
    for name, (file, pack, new, said) in made.items():
        noted(folder, file, pack); (folder / file).write_bytes(new.encode('cp1252')); told[name] = said
    return told
