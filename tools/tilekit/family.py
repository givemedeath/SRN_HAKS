"""A placement spec for a whole family of a tileset's tiles, proposed by the placers (`placer`) and checked by `detail`.

A family spec says what the tiles are and who proposes their pieces:
{tileset, families: [{terrains, match, placer, options, add}], building, taken, skip, budget}
- `terrains`: names or patterns (`Slums*`). A tile belongs to the first family one of whose terrains is at a corner of
  it; with `match` 'all', only where every corner is of them (a street: the default terrain).
- `placer`: 'propose', 'propose_corporate' or 'propose_street', with its `options`: look, above, ledges, watch, sign, eye,
  beside as the placer takes them; `grids` true for the windows painted in textures (`placer.GRIDS`); `plant` 'roof',
  'corporate' or null for none. `add`: more of the same, after it: [{placer, options, pieces}], of which only
  `pieces` are kept where that is said (a secure site: the corporate placer's cameras alone).
- `building`: the terrains that count as building, so a side between two such corners is no street (`placer.open_sides`);
  without it, every family's own.
- `taken`: placement specs of earlier batches, whose tiles are left out; `skip`: model patterns left out (envkit's `ek_*`
  as a rule); `budget`: {faces, effects} a tile's pieces are told against.

A proposal is a start. A piece `detail` refuses is dropped (a junction box with its sparks) and the tile tried again;
a tile that still does not pass is told with the reason, and so is one other tilesets draw. The base of a proposal is a
tile without kit pieces: once a batch is applied, `detail` refuses its tiles, and a new proposal for them starts from
the copies before that apply."""
import fnmatch
import json
from collections import Counter
from pathlib import Path

from . import detail, effects, inventory, merged, placer, require

TRIES = 12
BUDGET = {'faces': 2700, 'effects': 4}
SKIP = ('ek_*',)
PLANTS = {'roof': placer.ROOF, 'corporate': placer.CORPORATE_ROOF, None: None}
OPTIONS = {'propose': {'look', 'grids', 'above', 'plant'}, 'propose_corporate': {'plant', 'ledges', 'watch', 'sign', 'eye', 'beside'}, 'propose_street': set()}

SPEC, FAMILY, STEP = {'tileset', 'families', 'building', 'taken', 'skip', 'budget'}, {'terrains', 'match', 'placer', 'options', 'pieces', 'add'}, {'placer', 'options', 'pieces'}


def _is(name, patterns):
    return any(fnmatch.fnmatchcase(name.lower(), pattern.lower()) for pattern in patterns)


def read(path):
    """The family spec in the file `path`, its `taken` specs read relative to it: {..., taken: the tiles they hold}."""
    path = Path(path); spec = json.loads(path.read_text(encoding='utf-8-sig')); taken = set(); require(isinstance(spec, dict), f'{path} is no family spec: it holds no object')
    for one in spec.get('taken', ()):
        taken |= {name.lower() for name in json.loads((path.parent / one).read_text(encoding='utf-8-sig'))['tiles']}
    return {**spec, 'taken': taken}


def _checked(spec, terrains=None):
    """terrains: the set's, which every pattern of the spec is held against (None: not)."""
    require(isinstance(spec, dict) and spec.get('tileset') and spec.get('families'), 'A family spec names its tileset and its families')
    unknown = sorted({*(set(spec) - SPEC), *(key for one in spec['families'] for key in set(one) - FAMILY), *(key for one in spec['families'] for step in one.get('add', ()) for key in set(step) - STEP),
                      *(set(spec.get('budget', {})) - set(BUDGET))}); require(not unknown, 'A family spec has no ' + ', '.join(unknown))
    for one in spec['families']:
        require(one.get('terrains') and one.get('match', 'any') in ('any', 'all'), 'A family names its terrains; its match is any or all')
        for step in (one, *one.get('add', ())):
            require(step.get('placer') in OPTIONS, 'A family\'s placer is ' + ', '.join(OPTIONS))
            unknown = sorted(set(step.get('options', {})) - OPTIONS[step['placer']])
            require(not unknown, f'{step["placer"]} has no option ' + ', '.join(unknown))
            require(step.get('options', {}).get('plant') in PLANTS, 'A plant is ' + ', '.join(key for key in PLANTS if key) + ' or null')

    if terrains is not None:
        named = [*spec.get('building', ()), *(terrain for one in spec['families'] for terrain in one['terrains'])]
        unknown = sorted({pattern for pattern in named if not any(_is(terrain, [pattern]) for terrain in terrains)})
        require(not unknown, f'No terrain of {spec["tileset"]} is ' + ', '.join(unknown))


def family_of(spec, *tiles):
    """The first family one of the tiles (each its corners) belongs to, or None."""
    for one in spec['families']:
        if any((all if one.get('match') == 'all' else any)(_is(corner, one['terrains']) for corner in corners) for corners in tiles):
            return one
    return None


def _step(step, base, name, open_):
    options = dict(step.get('options', {}))
    if 'plant' in options:
        options['plant'] = PLANTS[options['plant']]
    if 'grids' in options:
        options['grids'] = placer.GRIDS if options['grids'] else None
    found = placer.propose_street(base, name) if step['placer'] == 'propose_street' else getattr(placer, step['placer'])(base, name, open=open_, **options)
    return [one for one in found if 'pieces' not in step or one['piece'] in step['pieces']]


def proposed(spec, family, base, name, *tiles):
    """The placers' pieces for one model, not yet checked. tiles: the corners of each tile that draws it; a side is on a
    street only where it is for all of them."""
    building = spec.get('building') or [terrain for one in spec['families'] for terrain in one['terrains']]
    open_ = set.intersection(*(set(placer.open_sides(corners, lambda terrain: _is(terrain, building))) for corners in tiles))
    return [one for step in (family, *family.get('add', ())) for one in _step(step, base, name, open_)]


def settled(place, placements):
    """(placements, what `place` told, [what was dropped and why]) once `place` passes them, dropping what it refuses."""
    dropped = []
    while True:
        try:
            return placements, place(placements), dropped
        except detail.Refused as error:
            if len(dropped) == TRIES:
                raise ValueError(f'{TRIES} pieces refused, and no end: ' + dropped[-1]) from error
            gone = placements[error.number]; dropped.append(f"{gone['piece']} at {gone['at']}: {str(error)[:160]}")
            placements = [one for number, one in enumerate(placements) if number != error.number and not (gone['piece'] == 'junction_box' and one['piece'] == 'sparks')]


def propose(repo, spec, kit):
    """(placement spec, {tiles, passed, refused, dropped, over, pieces, mostFaces, effects}) of a family spec (`read`)."""
    from .kit import SWEEPS
    repo = Path(repo); tileset = spec['tileset'].lower(); budget = {**BUDGET, **spec.get('budget', {})}; cache = {}
    laid = inventory.read_set((repo / f'srn_t_{tileset}' / f'{tileset}.set').read_bytes().decode('cp1252'))
    _checked(spec, {*laid['terrains'], *(corner for tile in laid['tiles'] for corner in tile['corners'])}); corners = {}  # a set may draw a terrain it does not declare
    for tile in laid['tiles']:  # a model may be drawn by several tiles, of different terrains
        corners.setdefault(tile['model'], []).append(tile['corners'])
    taken = set(spec.get('taken', ()))
    tiles, said, refused, dropped, seen = {}, {}, {}, {}, 0
    for name, _, text, others, source in inventory.drawn_copies(repo, tileset, None, merged.packs(repo, tileset)):
        family = family_of(spec, *corners[name]) if name in corners and name not in taken and not _is(name, spec.get('skip', SKIP)) else None
        if family is None:
            continue
        seen += 1
        if others:
            refused[name] = 'drawn by other tilesets too: ' + ', '.join(others); continue
        wok_path = (repo / source.parent.name / source.name).with_suffix('.wok')  # in the pack, beside a compiled model too
        wok = wok_path.read_bytes().decode('cp1252') if wok_path.is_file() else None
        placements = proposed(spec, family, effects.without_fx(detail.without_kit(text)), name, *corners[name])
        for piece in {one['piece'] for one in placements} - set(effects.EFFECTS):  # the kit's own lack, not the tile's
            for part in (piece, *([SWEEPS[piece]['head']] if piece in SWEEPS else [])):
                require((Path(kit) / f'{part}.mdl').is_file(), f'No kit piece {part} in {kit}')
        if not placements:
            continue
        try:
            placements, told, gone = settled(lambda them: detail.place(text, name, them, kit, cache, pack_text=text, wok=wok)[1], placements)
        except ValueError as error:
            refused[name] = str(error); continue
        if gone:
            dropped[name] = gone
        if placements:
            tiles[name], said[name] = placements, told
    over = {name: one for name, one in said.items() if one['faces'] > budget['faces'] or one['effects'] > budget['effects']}
    return {'tileset': tileset, 'tiles': tiles}, {
        'tiles': seen, 'passed': len(tiles), 'refused': dict(sorted(refused.items())), 'dropped': dict(sorted(dropped.items())), 'over': over,
        'pieces': dict(Counter(one['piece'] for placements in tiles.values() for one in placements)),
        'mostFaces': max((one['faces'] for one in said.values()), default=0), 'effects': sum(one['effects'] for one in said.values())}
