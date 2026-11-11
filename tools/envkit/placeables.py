"""Rows for envkit models in the placeables table.

The table is appended to and never renumbered: a placed object names its row by number, so a row once given stays
that model's. New rows follow the last row's own layout, column for column, so the file reads as before."""
import re

from .convert import require

COLUMNS = ('Label', 'StrRef', 'ModelName', 'LightColor', 'LightOffsetX', 'LightOffsetY', 'LightOffsetZ', 'SoundAppType', 'ShadowSize', 'BodyBag',
           'LowGore', 'Reflection', 'Static')
TOKEN = re.compile(r'"[^"]*"|\S+')
PREFIX = '[envkit]'


def register(text, entries):
    """(text, {model: row}) with one row appended per entry: [{model, label, sound}]. `sound` is the row of
    placeableobjsnds.2da the object sounds like when struck or used. A model the table already names is refused."""
    end = '\r\n' if '\r\n' in text else '\n'; lines = text.rstrip('\r\n').split(end)
    require(lines[0].startswith('2DA V2.0') and tuple(lines[2].split()) == COLUMNS, 'Unexpected placeables table')
    last = lines[-1]; spans = [match.start() for match in TOKEN.finditer(last)]
    require(len(spans) == len(COLUMNS) + 1 and last.split()[0].isdigit(), 'The last row of the placeables table is not a full row')
    named = {TOKEN.findall(line)[3].lower() for line in lines[3:] if len(TOKEN.findall(line)) > 3}
    number, rows = int(last.split()[0]), {}
    for entry in entries:
        model, label = entry['model'], entry['label']
        require(model == model.lower() and re.fullmatch(r'[a-z0-9_]{1,16}', model), 'A placeable model is a lowercase resref: ' + model)
        require(model not in named, 'The placeables table already names ' + model)
        require(label and '"' not in label and isinstance(entry['sound'], int) and entry['sound'] >= 0, 'A placeable needs a label and a sound row: ' + model)
        number += 1; named.add(model); rows[model] = number
        values = [str(number), f'"{PREFIX}{label}"', '****', model, '****', '****', '****', '****', str(entry['sound']), '1', '0', '****', '****', '1']
        line = ''
        for start, value in zip(spans, values):
            line = (line.ljust(start) if len(line) < start else line + ' ') + value  # at the column, or one space on where a value ran long
        lines.append(line.ljust(len(last)))
    return end.join(lines) + end, rows
