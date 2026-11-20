"""What each of a tileset's tiles costs to draw: faces, rendered mesh nodes and materials, against a budget.

In this engine every rendered mesh node is a draw of its own, and so may cost more than its faces; a tile's budget
holds all three. A review's overlay is read first, so a detailed or rebuilt tile is counted as it would be applied.
Compiled models are listed as such: their counts are not read."""
import statistics

from . import geometry, inventory, lamps, require

KEYS = ('faces', 'nodes', 'materials')


def of(text):
    """{faces, nodes, materials} of an uncompiled model: its rendered meshes, and their distinct textures or materials."""
    _, _, nodes = geometry.parse(text); shown = [node for node in nodes if node.rendered]
    return {'faces': sum(len(node.faces) for node in shown), 'nodes': len(shown), 'materials': len({node.material for node in shown if node.material})}


def count(repo, tileset, folder=None, budget=None):
    """{tiles: {model: counts}, over: {model: [what is over]}, summary: {key: {median, p90, max}}} of a tileset's
    uncompiled tile models, read from `folder` where it holds a copy. budget: {faces, nodes, materials}, any of them."""
    budget = budget or {}; require(set(budget) <= set(KEYS), 'A budget is any of ' + ', '.join(KEYS))
    tiles = {name: of(text) for name, _, text, _, _ in inventory.drawn_copies(repo, tileset.lower(), folder or repo, lamps.PACKS)}
    require(tiles, f'No uncompiled model of {tileset}')
    over = {name: [f'{key} {said[key]} > {budget[key]}' for key in KEYS if key in budget and said[key] > budget[key]] for name, said in tiles.items()}
    summary = {}
    for key in KEYS:
        values = sorted(said[key] for said in tiles.values())
        summary[key] = {'median': statistics.median(values), 'p90': values[min(len(values) - 1, int(len(values) * 0.9))], 'max': values[-1]}
    return {'tiles': tiles, 'over': {name: said for name, said in over.items() if said}, 'summary': summary}
