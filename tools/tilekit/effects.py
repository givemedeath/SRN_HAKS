"""Particle effects added to tiles: sparks from a broken junction box, water dripping from a fire escape or an air
conditioner, smoke from a roof vent.

An effect is a placement in the same spec as the kit pieces, `{piece: <effect>, at: [x, y, z], fall?}`, where `at`
is the emitter's point in the tile's coordinates. It becomes an emitter node under the tile's root named
<tile>_fxNN. Its picture is a sprite sheet of `GRID` by `GRID` frames, `<texture>.tga` in the kit folder, copied
into the overlay beside the model; each particle takes a frame at random. Smoke uses the game's own smoke sheet.

Sparks come in bursts as irregular as the engine allows: the emitter's birth rate is keyed in every animation the
tile has, `tiledefault` and its `animloopNN`s, as a tile plays its animation loops instead of `tiledefault` where
they are on (a key only in `tiledefault` never fires there). Each is a loop of `LOOP` seconds (lengthened to it where
it is shorter; their other nodes carry no timed keys, only a value at time 0). Each emitter
draws its own bursts from a seed of its tile and number (`bursts`): one to four pulses of a random length and
strength, then a quiet gap of random length, again and again through the loop, so two emitters never keep step and a
pattern only repeats after `LOOP` seconds. The engine starts every copy of a tile's animation together, so copies of
the same tile model in one area do keep step. A placement may give its own `seed`.

Drips fall at a steady rate, each living as long as a drop takes to fall `fall` metres, so it ends at the surface below instead of passing through it. Effects add no geometry and
leave the walkmesh alone; an emitter stands inside the tile's cell, or out over the street above a player's head, as
a piece may."""
import math
import random

from . import geometry, require

MARK = '_fx'
GRID = 4
LOOP = 29.0  # seconds; long and odd, so a repeat is hard to notice
GRAVITY = 9.8
WATER = (150, 172, 190)  # the colour a drop's body is lifted to
COMMON = {'update': 'Fountain', 'render': 'Normal', 'spawnType': 0, 'inherit': 0, 'inherit_local': 1, 'inheritvel': 0, 'inherit_part': 0, 'renderorder': 0,
          'threshold': 0.0, 'combinetime': 0.0, 'deadspace': 0.0, 'opacity': 1.0, 'particleRot': 0.0, 'bounce_co': 0.0, 'blurlength': 10.0, 'loop': 0,
          'bounce': 0, 'm_isTinted': 0, 'splat': 0, 'affectedByWind': 'false', 'twosidedtex': 1, 'xgrid': GRID, 'ygrid': GRID, 'fps': 0,
          'framestart': 0, 'frameend': GRID * GRID - 1, 'random': 1, 'lightningDelay': 0.0, 'lightningRadius': 0.0, 'lightningSubDiv': 0,
          'lightningScale': 0.0, 'blastRadius': 0.0, 'blastLength': 0.0, 'p2p': 0, 'p2p_type': 'Bezier', 'p2p_sel': 1, 'p2p_bezier2': 0.0,
          'p2p_bezier3': 0.0, 'grav': 0.0, 'drag': 0.0}
EFFECTS = {
    'sparks': {'texture': 'dgt04_fx_spark', 'Blend': 'Lighten', 'xSize': 4.0, 'ySize': 4.0, 'colorStart': (1.0, 0.92, 0.65), 'colorEnd': (1.0, 0.45, 0.1),
               'alphaStart': 1.0, 'alphaEnd': 0.0, 'sizeStart': 0.14, 'sizeEnd': 0.05, 'sizeStart_y': 0.0, 'sizeEnd_y': 0.0, 'birthrate': 0.0,
               'lifeExp': 0.8, 'mass': 1.0, 'spread': 1.4, 'velocity': 2.2, 'randvel': 1.6,
               'keys': 'bursts'},
    'smoke': {'texture': 'fxpa_mist', 'stock': True, 'Blend': 'Normal', 'xSize': 20.0, 'ySize': 20.0, 'colorStart': (0.55, 0.55, 0.55),
              'colorEnd': (0.3, 0.3, 0.3), 'alphaStart': 0.35, 'alphaEnd': 0.0, 'sizeStart': 0.25, 'sizeEnd': 1.6, 'sizeStart_y': 0.25,
              'sizeEnd_y': 1.6, 'birthrate': 5.0, 'lifeExp': 3.5, 'mass': -0.04, 'spread': 0.5, 'velocity': 0.4, 'randvel': 0.25,
              'particleRot': 3.0, 'affectedByWind': 'true', 'fps': 12, 'frameend': 11, 'keys': None},
    'drip': {'texture': 'dgt04_fx_drip', 'Blend': 'Normal', 'xSize': 6.0, 'ySize': 6.0, 'colorStart': (0.75, 0.82, 0.9), 'colorEnd': (0.6, 0.68, 0.78),
             'alphaStart': 0.9, 'alphaEnd': 0.8, 'sizeStart': 0.07, 'sizeEnd': 0.06, 'sizeStart_y': 0.18, 'sizeEnd_y': 0.22, 'birthrate': 2.0,
             'lifeExp': None, 'mass': 1.0, 'spread': 0.0, 'velocity': 0.0, 'randvel': 0.05, 'keys': None},
}


def is_fx(name):
    head, said, number = name.lower().rpartition(MARK)
    return bool(head and said and number.isdigit())


def _value(value):
    if isinstance(value, tuple):
        return ' '.join(f'{one:g}' for one in value)
    return f'{value:g}' if isinstance(value, float) else str(value)


def life(effect, fall):
    """Seconds a particle lives: a drop as long as it takes to fall `fall` metres."""
    if EFFECTS[effect]['lifeExp'] is not None:
        return EFFECTS[effect]['lifeExp']
    require(isinstance(fall, (int, float)) and fall > 0, f'A {effect} says how far it falls (`fall`, metres)')
    return round(math.sqrt(2 * fall / GRAVITY), 3)


def emitter(node, parent, at, effect, fall=None):
    """The geometry lines of an emitter node for `effect` at `at` (the parent's coordinates)."""
    settings = {**COMMON, **{key: value for key, value in EFFECTS[effect].items() if key not in ('keys', 'texture', 'stock')}}
    settings['lifeExp'] = life(effect, fall)
    out = [f'node emitter {node}', f'  parent {parent}', f'  position {at[0]:.5f} {at[1]:.5f} {at[2]:.5f}', '  orientation 1.0 0.0 0.0 0.0',
           '  update_sel 1', '  render_sel 1', '  blend_sel 1', '  spawntype_sel 0']
    out += [f'  {key} {_value(value)}' for key, value in settings.items()]
    out += [f'  texture {EFFECTS[effect]["texture"]}', 'endnode']
    return out


def bursts(seed, loop=LOOP):
    """[(seconds, particles a second)] of an emitter's bursts through the loop, drawn from `seed`: a step function (each
    change held between two keys 0.01 s apart, as keys are interpolated), quiet at both ends so the loop joins."""
    rng = random.Random(str(seed)); keys = [(0.0, 0.0)]; at = rng.uniform(0.2, 4.0)
    while at < loop - 1.0:
        for _ in range(rng.choice((1, 1, 2, 2, 3, 4))):  # a burst: pulses close together
            length = rng.uniform(0.03, 0.18); rate = rng.uniform(25.0, 140.0)
            if at + length + 0.02 > loop - 0.5:
                break
            keys += [(at, 0.0), (at + 0.01, rate), (at + 0.01 + length, rate), (at + 0.02 + length, 0.0)]
            at += 0.02 + length + rng.uniform(0.04, 0.35)
        at += min(max(rng.expovariate(1 / 3.2), 0.5), 9.0)  # then quiet, mostly short, now and then long
    keys.append((loop, 0.0))
    return [(round(time, 3), round(rate, 1)) for time, rate in keys]


def keyed(node, parent, effect, seed):
    """The animation lines that key an effect's birth rate, or [] for a steady one."""
    keys = bursts(seed) if EFFECTS[effect]['keys'] == 'bursts' else None
    if not keys:
        return []
    return ([f'  node emitter {node}', f'    parent {parent}', f'    birthratekey {len(keys)}'] + [f'      {time:.5f} {rate:.5f}' for time, rate in keys]
            + ['    endlist', '  endnode'])


def without_fx(text):
    """The model's text with the effect nodes an earlier run added taken out, from its geometry and its animations."""
    out, skipping = [], False
    for line in text.replace('\r\n', '\n').split('\n'):
        words = line.split()
        if not skipping and len(words) >= 3 and words[0].lower() == 'node' and is_fx(words[2]):
            skipping = True; continue
        if skipping:
            skipping = not (words[:1] and words[0].lower() == 'endnode'); continue
        out.append(line)
    return ('\r\n' if '\r\n' in text else '\n').join(out)


def check(name, number, at, effect):
    require(effect in EFFECTS, f'{name} #{number}: no effect {effect}')
    require(isinstance(at, list) and len(at) == 3 and all(isinstance(value, (int, float)) for value in at), f'{name} #{number}: `at` is [x, y, z]')
    out = geometry.overhanging([(tuple(at), tuple(at), tuple(at))])
    require(not out, f'{name} #{number} ({effect}) is outside the cell, other than over the street above {geometry.OVER} m')


def added(text, root, placed):
    """`text` with the emitters of `placed` [(effect, at, fall, seed)] added: their nodes before the geometry ends, their
    keys in every animation of the model (a `tiledefault` made where it has none). Returns (text, emitters)."""
    if not placed:
        return text, 0
    ending = '\r\n' if '\r\n' in text else '\n'; lines = text.replace('\r\n', '\n').split('\n')
    nodes, keys = [], []
    for number, (effect, at, fall, seed) in enumerate(placed):
        node = f'{root}{MARK}{number:02d}'
        nodes += emitter(node, root, at, effect, fall); keys += keyed(node, root, effect, f'{root}:{number}' if seed is None else seed)
    end = next(index for index, line in enumerate(lines) if line.split()[:1] and line.split()[0].lower() == 'endmodelgeom')
    lines = lines[:end] + nodes + lines[end:]
    if keys:
        if not any(line.split()[:1] and line.split()[0].lower() == 'newanim' for line in lines):
            done = max(index for index, line in enumerate(lines) if line.split()[:1] and line.split()[0].lower() == 'donemodel')
            lines = lines[:done] + [f'newanim tiledefault {root}', f'  length {LOOP:.5f}', '  transtime 0.0', f'  animroot {root}', f'doneanim tiledefault {root}', ''] + lines[done:]
        out, inside = [], False
        for line in lines:
            words = line.split(); head = words[0].lower() if words else ''
            if head == 'newanim':
                inside = True
            elif inside and head == 'length' and float(words[1]) < LOOP:
                line = f'  length {LOOP:.5f}'
            elif head == 'doneanim':
                out += keys; inside = False
            out.append(line)
        lines = out
    return ending.join(lines), len(placed)


def sheet(picture, *, filled=False, frame=64, floor=10, body=0.35):
    """An emitter's sprite sheet (RGBA, `GRID` x `GRID` frames of `frame` pixels) from a drawn picture of `GRID` x `GRID`
    effects on black: each cell's effect, the pixels brighter than `floor`, is cut out square around its middle with a
    margin and scaled to the frame. Alpha is the brightness, for sparks drawn added to the scene; `filled` also gives
    the inside of each shape (a water drop drawn as its rim and highlight) at least `body`, so it reads as a body of
    water over a lit wall."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    picture = picture.convert('RGB'); width, height = picture.size; out = Image.new('RGBA', (GRID * frame, GRID * frame), (0, 0, 0, 0))
    for row in range(GRID):
        for column in range(GRID):
            cell = picture.crop((column * width // GRID, row * height // GRID, (column + 1) * width // GRID, (row + 1) * height // GRID))
            bright = cell.convert('L'); shape = bright.point(lambda value: 255 if value > floor else 0)
            box = shape.getbbox(); require(box is not None, f'Frame {row * GRID + column} of the picture is empty')
            side = int(max(box[2] - box[0], box[3] - box[1]) * 1.25) + 4; middle = ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
            square = (middle[0] - side // 2, middle[1] - side // 2, middle[0] - side // 2 + side, middle[1] - side // 2 + side)
            colour, alpha = cell.crop(square), bright.crop(square).point(lambda value: min(255, int(value * 1.6)))
            if filled:  # the shape's inside: what the black outside cannot reach
                outside = shape.crop(square).filter(ImageFilter.MaxFilter(3)).convert('L'); ImageDraw.floodfill(outside, (0, 0), 128)
                inside = outside.point(lambda value: int(255 * body) if value == 0 else 0)
                alpha = ImageChops.lighter(alpha, inside)
                colour = ImageChops.lighter(colour, Image.new('RGB', colour.size, WATER))  # a dark inside would read as a hole
            one = colour.convert('RGBA'); one.putalpha(alpha)
            out.paste(one.resize((frame, frame), Image.LANCZOS), (column * frame, row * frame))
    return out
