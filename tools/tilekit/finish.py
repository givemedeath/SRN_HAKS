"""Finishes laid over a redrawn picture before its maps are made: what the drawing model could not be brought to draw
(a clean row of lit segments, a legible caption, lamps bright enough to read). Three arcology pictures were finished by
hand on 2026-11-24 with no record; this is that hand, written down, so the pictures can be made again from their
redraws (user, 2026-11-24: the rest of the open items).

A texture's `finish` in the redraw list (`docs/tilesets/<set>/redraw.json`) is a list of steps, done in turn on the
redrawn picture (pixels of the picture, the top first):
- {"segments": {"band": [left, top, right, bottom], "fill": [r, g, b], "row": [top, bottom], "from": x, "to": x,
  "end": x, "widths": [...], "colours": [[r, g, b], ...], "gap": pixels, "seed": n}}: the band painted over and an even row of
  lit segments drawn in it from `from` while one starts before `to` and ends by `end`, their widths and colours
  taken in a seeded order;
- {"caption": {"band": [...], "fill": [r, g, b], "text": words, "font": a font file's name, "size": points, "colour":
  [r, g, b], "middle": y}}: the band painted over and lettered, centred;
- {"lift": {"above": 0-255, "over": 0-255, "to": [r, g, b]}}: every pixel brighter than `above` moved towards `to`,
  wholly so from `above + over` up; the dark left as it is.

The finished pictures alone are written: lay them over a copy of the redraw folder for `material --redrawn`. A finish
is done on the redraw itself, never on a picture finished before (a second lift brightens again)."""
import random
from pathlib import Path

from . import require

STEPS = ('segments', 'caption', 'lift')


def finished(picture, steps):
    """A PIL picture with the steps of a `finish` done on it (RGBA)."""
    from PIL import ImageDraw, ImageFont
    picture = picture.convert('RGBA'); require(isinstance(steps, list) and steps, 'A finish is a list of steps')
    for step in steps:
        require(isinstance(step, dict) and len(step) == 1 and next(iter(step)) in STEPS and isinstance(step[next(iter(step))], dict), 'A finish step is one of ' + ', '.join(STEPS)); kind, how = next(iter(step.items()))
        draw = ImageDraw.Draw(picture)
        if kind == 'segments':
            require(set(how) == {'band', 'fill', 'row', 'from', 'to', 'end', 'widths', 'colours', 'gap', 'seed'}, 'Segments have a band, fill, row, from, to, end, widths, colours, gap and seed')
            require(how['widths'] and min(how['widths']) + how['gap'] > 0, 'A segment and its gap are wider than nothing')
            chance = random.Random(how['seed']); draw.rectangle(tuple(how['band']), fill=tuple(how['fill']) + (255,)); x = how['from']
            while x < how['to']:
                wide = chance.choice(how['widths']); colour = chance.choice(how['colours'])
                if x + wide > how['end']:
                    break
                draw.rectangle((x, how['row'][0], x + wide, how['row'][1]), fill=tuple(colour) + (255,)); x += wide + how['gap']
        elif kind == 'caption':
            require(set(how) == {'band', 'fill', 'text', 'font', 'size', 'colour', 'middle'}, 'A caption has a band, fill, text, font, size, colour and middle')
            require(Path(how['font']).name == how['font'], 'A caption\'s font is a font file\'s name, found among the system\'s fonts')
            draw.rectangle(tuple(how['band']), fill=tuple(how['fill']) + (255,))
            try:
                font = ImageFont.truetype(how['font'], how['size'])
            except OSError:
                require(False, f'The font {how["font"]} is not among this system\'s fonts')
            box = draw.textbbox((0, 0), how['text'], font=font)
            draw.text(((picture.width - (box[2] - box[0])) / 2 - box[0], how['middle'] - (box[3] + box[1]) / 2), how['text'], font=font, fill=tuple(how['colour']) + (255,))
        else:
            require(set(how) == {'above', 'over', 'to'} and how['over'] > 0, 'A lift has above, over and to')
            pixels = picture.load()
            for y in range(picture.height):
                for x in range(picture.width):
                    r, g, b, a = pixels[x, y]; peak = max(r, g, b)
                    if peak > how['above']:
                        share = min(1.0, (peak - how['above']) / how['over'])
                        pixels[x, y] = (int(r + (how['to'][0] - r) * share), int(g + (how['to'][1] - g) * share), int(b + (how['to'][2] - b) * share), a)
    return picture


def write(spec, redrawn, out, only=None):
    """Finish the redrawn pictures of a list that have a `finish`, from the folder `redraw` filled into `out` (each
    picture with its record beside it, as `material` reads them), and tell the names done. A picture the folder lacks
    is refused."""
    from PIL import Image
    redrawn, out = Path(redrawn), Path(out); require(redrawn.resolve() != out.resolve(), 'A finish is written to another folder than the redraws'); out.mkdir(parents=True, exist_ok=True); told = []
    unknown = sorted(set(only or ()) - {name for name, how in spec['textures'].items() if how.get('finish')}); require(not unknown, 'No finish in the list for: ' + ', '.join(unknown))
    for name, how in spec['textures'].items():
        if not how.get('finish') or (only and name not in only):
            continue
        require((redrawn / f'{name}.png').is_file(), f'No redrawn picture {name}.png in {redrawn}')
        finished(Image.open(redrawn / f'{name}.png'), how['finish']).save(out / f'{name}.png')
        if (redrawn / f'{name}.json').is_file():
            (out / f'{name}.json').write_bytes((redrawn / f'{name}.json').read_bytes())
        told.append(name)
    return told
