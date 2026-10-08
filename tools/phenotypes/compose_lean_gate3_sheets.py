"""Compose labelled Gate 3 review sheets from pinned offline views (layout/resizing only; no pixel edits).

Sheets: full-body idle (rows = colour variants, columns = front/left/rear); worst-case motion (one sheet per variant:
rows = motion samples, columns = views); close-up groups (rows = views, columns = variants). Every rendered view must
appear on a sheet exactly once per variant; renders are verified by sha256 before use. Writes PNG sheets and a
receipt; it accepts nothing.

Usage: compose_lean_gate3_sheets.py --views <render-report.json> [...] --groups <json {name: [view ids]}> --title <text>
       --output <fresh dir>
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import lean_common as L


def font(size=18):
    try:
        return ImageFont.truetype('arial.ttf', size)
    except OSError:
        return ImageFont.load_default()


def compose(view_paths, groups_path, title, output):
    frozen = L.Frozen(); reports = [L.read_json(frozen.take(p)) for p in view_paths]; groups = L.read_json(frozen.take(groups_path))
    renders = {}
    for report in reports:
        for row in report['renders']:
            L.require(L.sha(row['path']) == row['sha256'], 'Rendered view changed: '+row['path']); frozen.take(row['path'])
            key = (row['id'], row['variant']); L.require(key not in renders, 'Duplicate rendered view: '+str(key)); renders[key] = row
    variants = list(dict.fromkeys(row['variant'] for report in reports for row in report['renders']))
    ids = sorted({key[0] for key in renders}); output = L.fresh(output); typeface = font(); used = set()

    def tile(key, scale):
        row = renders[key]; used.add(key); image = Image.open(row['path']).convert('RGB')
        image = image.resize((int(image.width*scale), int(image.height*scale)), Image.LANCZOS); draw = ImageDraw.Draw(image)
        draw.rectangle([0, 0, image.width, 24], fill=(0, 0, 0))
        draw.text((4, 3), f"{row['id']}  {row['variant']}  {row['clip']}@{row['fraction']:g}", fill=(255, 255, 255), font=typeface)
        return image

    def grid(name, rows, scale, caption):
        rows = [[k for k in row if k in renders] for row in rows]; rows = [row for row in rows if row]
        if not rows: return None
        tiles = [[tile(k, scale) for k in row] for row in rows]
        width = max(sum(t.width for t in row) for row in tiles); height = sum(max(t.height for t in row) for row in tiles)+34
        sheet = Image.new('RGB', (width, height), (40, 40, 40)); ImageDraw.Draw(sheet).text((6, 6), caption, fill=(255, 255, 160), font=typeface); y = 34
        for row in tiles:
            x = 0
            for t in row: sheet.paste(t, (x, y)); x += t.width
            y += max(t.height for t in row)
        path = output/(name+'.png'); sheet.save(path)
        return {'sheet': L.pin(path), 'tiles': [[f'{k[0]}|{k[1]}' for k in row] for row in rows]}

    sheets = {}
    sheets['01-full-idle'] = grid('sheet-01-full-body-idle', [[(f'full-idle-{v}', var) for v in ('front', 'left', 'rear')] for var in variants], .5,
                                  title+' - idle - rows: '+', '.join(variants))
    motions = sorted({i[len('full-'):].rsplit('-', 1)[0] for i in ids if i.startswith('full-') and not i.startswith('full-idle-')})
    for var in variants:
        sheets['02-motion-'+var] = grid('sheet-02-motion-'+var, [[(f'full-{m}-{v}', var) for v in ('front', 'left', 'rear')] for m in motions], .45,
                                        title+' - worst-case motion samples - variant '+var)
    for index, (name, members) in enumerate(groups.items(), start=3):
        sheets[f'{index:02d}-{name}'] = grid(f'sheet-{index:02d}-{name}', [[(m, var) for var in variants] for m in members], .5,
                                            title+' close-ups: '+name+' (columns: '+', '.join(variants)+')')
    missing = sorted(set(renders)-used)
    L.require(not missing, 'Rendered views missing from every sheet: '+str(missing[:10]))
    receipt = {'schemaVersion': 1, 'kind': 'lean-gate3-review-sheets', 'title': title, 'views': [L.pin(p) for p in view_paths], 'groups': L.pin(groups_path),
               'variants': variants, 'sheets': {k: v for k, v in sheets.items() if v}, 'renderCount': len(renders),
               'frozenInputs': {**frozen.verify(), **L.helper_pins('compose_lean_gate3_sheets.py')}, 'reviewPending': True,
               'selected': False, 'clientAccepted': False, 'productionAccepted': False}
    return L.save_json(output/'sheets.json', receipt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--views', type=Path, action='append', required=True); parser.add_argument('--groups', type=Path, required=True)
    parser.add_argument('--title', required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); print(compose(args.views, args.groups, args.title, args.output))
