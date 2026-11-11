"""Rows for envkit models in the placeables table.

The table is appended to and never renumbered: a placed object names its row by number, so a row once given stays
that model's. New rows follow the last row's own layout, column for column, so the file reads as before."""
import re

from . import require

COLUMNS = ('Label', 'StrRef', 'ModelName', 'LightColor', 'LightOffsetX', 'LightOffsetY', 'LightOffsetZ', 'SoundAppType', 'ShadowSize', 'BodyBag',
           'LowGore', 'Reflection', 'Static')
TOKEN = re.compile(r'"[^"]*"|\S+')
PREFIX = '[envkit]'


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
        require(model == model.lower() and re.fullmatch(r'[a-z0-9_]{1,16}', model), 'A placeable model is a lowercase resref: ' + model)
        require(model not in named, 'The placeables table already names ' + model)
        sound = entry['sound']
        require(label and '"' not in label and (sound is None or (isinstance(sound, int) and sound >= 0)), 'A placeable needs a label and a sound row: ' + model)
        number += 1; named.add(model); made[model] = number
        values = [str(number), f'"{PREFIX}{label}"', '****', model, '****', '****', '****', '****', '****' if sound is None else str(sound), '1', '0', '****', '****', '1']
        line = ''
        for start, value in zip(spans, values):
            line = (line.ljust(start) if len(line) < start else line + ' ') + value  # at the column, or one space on where a value ran long
        lines.append(line.ljust(len(last)))
    return end.join(lines) + end, made
