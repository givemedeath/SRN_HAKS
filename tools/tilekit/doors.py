"""The door models of the door pack, listed for choosing which to restyle: each model's family, what it costs to draw,
its textures, and who uses it. Doors are used in two ways:

- **Tile doors**: a doortypes.2da row names the model and its tileset. A tile's door hook in a set file (`[TILEnDOORm]`,
  `Type=` that row) puts one in a doorway.
- **Placed doors**: a genericdoors.2da row names the model. A builder places it anywhere, so no file in the packs says
  where it stands.

Reads only; writes nothing but what `write` is given."""
import csv
import io
import json
import re
from pathlib import Path

from . import geometry, inventory, require

PACK = 'srn_door'


def _rows(path, column):
    """[(row number, label, model, tileset or None)] of a 2DA whose model is in `column`."""
    lines = Path(path).read_text(encoding='cp1252').splitlines()
    head = inventory.words(lines[2]); found = []
    model, tileset = head.index(column), head.index('TileSet') if 'TileSet' in head else None
    for line in lines[3:]:
        cells = inventory.words(line)
        if len(cells) > model + 1 and cells[model + 1] != '****':
            found.append((int(cells[0]), cells[1].strip('"'), cells[model + 1].lower(), cells[tileset + 1].lower() if tileset is not None and cells[tileset + 1] != '****' else None))
    return found


def _hooks(repo):
    """{doortypes row: {tileset: number of tile door hooks}} over every set file of the packs."""
    told = {}
    for path in sorted(Path(repo).glob('srn_t_*/*.set')):
        tileset = path.stem.lower()
        for name, keys in inventory.sections(path.read_text(encoding='cp1252')):
            if re.fullmatch(r'TILE\d+DOOR\d+', name, re.I) and keys.get('Type', '').lstrip('-').isdigit():
                counts = told.setdefault(int(keys['Type']), {}); counts[tileset] = counts.get(tileset, 0) + 1
    return told


def family(model):
    return re.sub(r'[_0-9]+$', '', model)


def kind(model, labels):
    """A first guess at what a door is, from its model's name and its rows' labels; the pictures settle it."""
    said = ' '.join([model] + labels).lower()
    for word, what in (('curtain', 'curtain'), ('gdoor', 'gate'), ('gate', 'gate'), ('fence', 'gate'), ('portcullis', 'gate'), ('window', 'window'), ('glass', 'glass')):
        if word in said:
            return what
    return 'door'


def doors(repo):
    """[{model, family, kind, form, faces, nodes, textures, doortypes, genericdoors, tileHooks}] of the door pack's models."""
    repo = Path(repo); pack = repo / PACK; require(pack.is_dir(), f'No {PACK} folder in {repo}')
    tile_rows, placed_rows, hooks = _rows(repo / 'srn_2da' / 'doortypes.2da', 'Model'), _rows(repo / 'srn_2da' / 'genericdoors.2da', 'ModelName'), _hooks(repo)
    found = []
    for path in sorted(pack.glob('*.mdl')):
        model = path.stem.lower(); data = path.read_bytes(); entry = {'model': model, 'family': family(model)}
        if inventory.compiled(data):
            entry.update(form='compiled', faces=None, nodes=None, textures=[])
        else:
            _, _, nodes = geometry.parse(data.decode('cp1252')); shown = [node for node in nodes if node.rendered]
            entry.update(form='ascii', faces=sum(len(node.faces) for node in shown), nodes=len(shown), textures=sorted({node.material for node in shown if node.material}))
        mine = [row for row in tile_rows if row[2] == model]; placed = [row for row in placed_rows if row[2] == model]
        entry['doortypes'] = [{'row': row, 'label': label, 'tileset': tileset} for row, label, _, tileset in mine]
        entry['genericdoors'] = [{'row': row, 'label': label} for row, label, _, _ in placed]
        entry['tileHooks'] = {tileset: count for row, *_ in mine for tileset, count in hooks.get(row, {}).items()}
        entry['kind'] = kind(model, [label for _, label, _, _ in mine + placed])
        entry['walkmesh'] = (pack / f'{path.stem}.dwk').is_file()
        found.append(entry)
    return found


def write(folder, found):
    """Write doors.json and doors.csv into `folder`; returns their paths."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    text = io.StringIO(); table = csv.writer(text, lineterminator='\n')
    table.writerow(['model', 'family', 'kind', 'form', 'faces', 'nodes', 'textures', 'doortypes rows', 'genericdoors rows', 'tile hooks'])
    for door in found:
        table.writerow([door['model'], door['family'], door['kind'], door['form'], door['faces'], door['nodes'], ' '.join(door['textures']),
                        ' '.join(str(row['row']) for row in door['doortypes']), ' '.join(str(row['row']) for row in door['genericdoors']),
                        ' '.join(f'{tileset}:{count}' for tileset, count in sorted(door['tileHooks'].items()))])
    (folder / 'doors.json').write_text(json.dumps({'schemaVersion': 1, 'pack': PACK, 'doors': found}, indent=1) + '\n', encoding='utf-8', newline='\n')
    (folder / 'doors.csv').write_text(text.getvalue(), encoding='utf-8', newline='\n')
    return [str(folder / 'doors.json'), str(folder / 'doors.csv')]
