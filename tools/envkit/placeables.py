"""Rows for envkit models in the placeables table.

The table is appended to and never renumbered: a placed object names its row by number, so a row once given stays
that model's. New rows follow the last row's own layout, column for column, so the file reads as before."""
import re

from . import require

COLUMNS = ('Label', 'StrRef', 'ModelName', 'LightColor', 'LightOffsetX', 'LightOffsetY', 'LightOffsetZ', 'SoundAppType', 'ShadowSize', 'BodyBag',
           'LowGore', 'Reflection', 'Static')
TOKEN = re.compile(r'"[^"]*"|\S+')
PREFIX = '[envkit]'
RESREF = re.compile(r'[a-z0-9_]{1,16}')
LIGHT = slice(4, 8)  # a row's LightColor and LightOffsetX, Y and Z, counting its number as the first value  # a model or blueprint name: the game reads these letters alike whatever the code page


def rows(text):
    """{model: row number} of every row in the table, by the model it names (lower case)."""
    end = '\r\n' if '\r\n' in text else '\n'; found = {}
    for line in text.rstrip('\r\n').split(end)[3:]:
        tokens = TOKEN.findall(line)
        if len(tokens) > 3 and tokens[0].isdigit():
            found.setdefault(tokens[3].lower(), int(tokens[0]))
    return found


def register(text, entries, *, again=False):
    """(text, {model: row}) with one row appended per entry: [{model, label, sound}]. `sound` is the row of
    placeableobjsnds.2da the object sounds like when struck or used, or None for no sound. A model the table already
    names is refused, unless `again`: a fixture's throwaway table gives the model under test a row of its own."""
    end = '\r\n' if '\r\n' in text else '\n'; lines = text.rstrip('\r\n').split(end)
    require(lines[0].startswith('2DA V2.0') and tuple(lines[2].split()) == COLUMNS, 'Unexpected placeables table')
    last = lines[-1]; spans = [match.start() for match in TOKEN.finditer(last)]
    require(len(spans) == len(COLUMNS) + 1 and last.split()[0].isdigit(), 'The last row of the placeables table is not a full row')
    named = set() if again else set(rows(text))
    number, made = int(last.split()[0]), {}
    for entry in entries:
        model, label = entry['model'], entry['label']
        require(RESREF.fullmatch(model), 'A placeable model is a lowercase resref: ' + model)
        require(model not in named, 'The placeables table already names ' + model)
        sound = entry['sound']
        require(label and '"' not in label and (sound is None or (isinstance(sound, int) and sound >= 0)), 'A placeable needs a label and a sound row: ' + model)
        number += 1; named.add(model); made[model] = number
        values = [str(number), f'"{PREFIX}{label}"', '****', model, *light_values(entry.get('light')), '****' if sound is None else str(sound), '1', '0', '****', '****', '1']
        lines.append(_laid(spans, values, len(last)))
    return end.join(lines) + end, made


def light_values(light):
    """The four light values of a row: a light {colour, at} gives its row of lightcolor.2da and where it stands from
    the object's origin, in metres (x, y, z); None gives none (`****`). A row that names a light colour makes the game
    light what stands round the object, as the stock lamp post's does; `SetPlaceableIllumination` and
    `RecomputeStaticLighting` put it out and back on."""
    if light is None:
        return ['****'] * 4
    require(isinstance(light, dict) and set(light) == {'colour', 'at'} and type(light['colour']) is int and 0 <= light['colour'] <= 255
            and isinstance(light['at'], list) and len(light['at']) == 3 and all(type(v) in (int, float) for v in light['at']),
            'A light is {colour: a row of lightcolor.2da, at: [x, y, z] metres from the object}')
    return [str(light['colour']), *(f'{float(v):.4f}' for v in light['at'])]


def lights(text, wanted):
    """(text) with the light values of each model's own row ({model: light or None}) set as given: a model converted
    again keeps its row, and its light follows the game set. Nothing else of the table changes."""
    end = '\r\n' if '\r\n' in text else '\n'; lines = text.rstrip('\r\n').split(end); found = rows(text)
    require(all(model in found for model in wanted), 'These have no row to light: ' + ', '.join(sorted(set(wanted) - set(found))))
    for index in range(3, len(lines)):
        tokens = TOKEN.findall(lines[index])
        if len(tokens) == len(COLUMNS) + 1 and tokens[0].isdigit() and tokens[3].lower() in wanted and found[tokens[3].lower()] == int(tokens[0]):
            values = list(tokens); values[LIGHT] = light_values(wanted[tokens[3].lower()])
            if values != tokens:
                lines[index] = _laid([match.start() for match in TOKEN.finditer(lines[index])], values, len(lines[index]))
    return end.join(lines) + end


def _laid(spans, values, width):
    """A row with each value at its column, or one space on where the one before ran long."""
    line = ''
    for start, value in zip(spans, values):
        line = (line.ljust(start) if len(line) < start else line + ' ') + value
    return line.ljust(width)
