"""Build the SRN dynamic skies into srn_skybox and srn_2da (docs/skies/dynamic-skies.md).

  python -m tools.skykit build      panoramas -> DDS halves and light masks, models, materials, fallback pictures,
                                    skyboxes.2da rows, previews and the manifest
  python -m tools.skykit preview    previews only, from the panoramas' intermediate TGAs of the last build

Intermediate pictures and previews go to output/skykit/ (ignored); the HAK resources and the manifest are tracked.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = 'tools.skykit'

from . import panorama, profiles, sphere

ROOT = Path(__file__).resolve().parents[2]
ART = Path(__file__).resolve().parent / 'art'
PACK = ROOT / 'srn_skybox'
TABLE = ROOT / 'srn_2da' / 'skyboxes.2da'
OUTPUT = ROOT / 'output' / 'skykit'
MANIFEST = ROOT / 'docs' / 'skies' / 'manifest.json'
SHADERS = ('srn_sky_fs.shd', 'srn_sky_math.shd')
VERTEX_SHADER = 'vsvt'  # the game's own: unlit, unfogged, passes the texture coordinate
FALLBACK = (1024, 512)
PARAMETER_ORDER = ('SkyPhase', 'SkyBand', 'SkyZenith', 'SkyHorizon', 'SkyCloud', 'SkyLand', 'SkySun',
                   'SkySunColor', 'SkyMotion', 'SkyNight', 'SkyExtra', 'SkyGlow')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assembled_land(key):
    """The assembled panorama (float RGB, wrapped, at the source size) cropped to its land and a few rows of key."""
    spec = profiles.PANORAMAS[key]
    if 'chain' in spec:
        # one start view grown to the right by redrawn extensions, wrapped by a closing join
        start, *extensions = [panorama.view_rgb(ART / name) for name in spec['chain']]
        whole = panorama.chain(start, extensions, panorama.view_rgb(ART / spec['close']), key=spec['key'])
    elif 'joins' in spec:
        # views read left to right as a viewer turns clockwise; the joins between them are redrawn seams
        views = [panorama.view_rgb(ART / name) for name in spec['views']]
        joins = [panorama.view_rgb(ART / name) for name in spec['joins']]
        if 'match' in spec:  # grade every other picture like the named view
            reference = views[spec['match']]
            views = [v if i == spec['match'] else panorama.match_colours(v, reference, spec['key']) for i, v in enumerate(views)]
            joins = [panorama.match_colours(j, reference, spec['key'], 0.5) for j in joins]
        whole = panorama.assemble(views, joins, panorama.WIDE if spec.get('wide') else panorama.LAYOUT, spec['key'])
    else:
        raise ValueError(f'{key}: a panorama is a chain or views with joins')
    rows = panorama.land_rows(panorama.cut(whole, spec['key']))[0]
    return np.ascontiguousarray(whole[max(rows - 8, 0):])


UPSCALED = {}
NORMALS = {}
DETAILED = {}


def build_panorama(key, scale=2):
    """(halves, (bottom, top, roofs) degrees) of one panorama, its intermediate pictures written to output/skykit/<key>/.

    With `scale` above 1 the land is enlarged: by its tracked detail tiles when it has them (detail.py), otherwise by
    the 2x upscaler (upscale.py); `scale` becomes the enlargement."""
    spec = profiles.PANORAMAS[key]
    whole = assembled_land(key)
    if scale > 1:
        tiles = ART / spec['detail'] if 'detail' in spec else None
        if tiles and (tiles / 'detail.json').is_file():
            from . import detail
            whole, scale = detail.assemble(whole, spec['key'], tiles)
            DETAILED[key] = spec['detail']
        else:
            from . import upscale
            whole, cache = upscale.upscale(whole, OUTPUT / key)
            UPSCALED[key] = cache
        whole = panorama.sharpen(whole)
    rgba = panorama.cut(whole, spec['key'], scale)
    strip = rgba[panorama.land_rows(rgba)[0]:]
    # u grows counter-clockwise, which from inside the dome is to the viewer's left: flip so pictures read the right way
    strip = np.ascontiguousarray(strip[:, ::-1])
    mask = panorama.lights(strip, spec.get('city_from', 0.0), scale)
    if scale > 1:  # faces' normals (MoGe-2) go in the mask's b and a, for the shader's relighting
        from . import normals
        field, cache = normals.normals(strip, OUTPUT / key)
        NORMALS[key] = cache
    else:
        field = np.zeros(strip.shape[:2] + (3,), np.float32)
    mask = np.dstack([mask[..., :2], field[..., :2] * 0.5 + 0.5]).astype(np.float32)
    band = panorama.band_degrees(strip, spec['below'], spec['stretch'])
    band = (*band, panorama.roof_degrees(mask, band))
    halves = panorama.halves(strip, mask, panorama.half_size(band))
    folder = OUTPUT / key
    folder.mkdir(parents=True, exist_ok=True)
    panorama.save_png(strip, folder / 'strip.png')
    panorama.save_png(mask, folder / 'lights.png')
    for name, (rgba, lights) in zip(('a', 'b'), halves):
        (folder / f'srn_sky{key}_p{name}.tga').write_bytes(panorama.tga(rgba))
        (folder / f'srn_sky{key}_m{name}.tga').write_bytes(panorama.tga(lights))
    return halves, band


def crunch_tool(inputs):
    sys.path.insert(0, str(ROOT / 'tools' / 'phenotypes'))
    from tool_runtime import tool
    return tool('crunch', inputs=[{'path': str(Path(p).resolve()), 'sha256': sha(p)} for p in inputs])


def to_dds(crunch, tga, target, compression):
    target = Path(target)
    if target.exists():
        target.unlink()
    done = subprocess.run([str(crunch), '-file', str(tga), '-out', str(target), '-fileformat', 'nwn', '-' + compression,
                           '-mipMode', 'Generate', '-noprogress', '-nostats'], capture_output=True, text=True, errors='replace',
                          timeout=600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if done.returncode != 0 or not target.is_file():
        raise RuntimeError(f'NWN Crunch failed on {tga}: ' + (done.stdout + done.stderr)[-1500:])


def material_text(key, parameters, band):
    values = dict(parameters)
    extra = values.get('SkyBand', (0, 0, 0, 0))
    values['SkyBand'] = (band[0], band[1], extra[2], extra[3])
    if len(band) > 2:  # the searchlights' foot: the city's rooftops, measured by the build
        values['SkyGlow'] = (*values['SkyGlow'][:3], band[2])
    textures = profiles.texture_names(key)
    # written by tools/skykit from profiles.py; no comment line, as the engine's material parser is not known to take one
    lines = [f'customshaderVS {VERTEX_SHADER}', 'customshaderFS srn_sky_fs']
    lines += [f'texture{unit} {name}' for unit, name in enumerate(textures)]
    for name in PARAMETER_ORDER:
        value = values[name]
        numbers = value if isinstance(value, (tuple, list)) else (value,)
        lines.append(f'parameter float {name} ' + ' '.join(f'{float(v):.4f}' for v in numbers))
    return '\n'.join(lines) + '\n', values


def table_rows():
    rows = {}
    for row, (label, cyclical, key, phases, columns) in profiles.SKIES.items():
        rows[row] = (label, cyclical, [profiles.model_name(key, suffix) for suffix in columns])
    return rows


def write_table(rows, path=TABLE):
    """Replace or append our rows of skyboxes.2da, keeping every other line as it is. A row of ours (an SRN_ label
    from our first row on) that the profiles no longer define is dropped: rows must stay in order."""
    lines = Path(path).read_text(encoding='ascii').splitlines()

    def ours(line):
        parts = line.split()
        if not (parts and parts[0].isdigit()):
            return False
        row = int(parts[0])
        return row in rows or (bool(rows) and row >= min(rows) and len(parts) > 1 and parts[1].startswith('SRN_'))
    kept = [line for line in lines if not ours(line)]
    for row in sorted(rows):
        label, cyclical, models = rows[row]
        kept.append(f'{row:<4}{label:<24}****        {cyclical:<12}' + ''.join(f'{m:<16}' for m in models).rstrip())
    Path(path).write_text('\n'.join(kept) + '\n', encoding='ascii', newline='\n')


def preview_sheet(renderer, materials, folder):
    """Contact sheet: each model at three headings from a player's height, plus its equirect."""
    from PIL import ImageDraw
    tiles = []
    for name, (key, values) in materials.items():
        row = [renderer.render(values, (480, 270), camera=(yaw, 8.0, 70.0), time_ms=900000) for yaw in (20.0, 140.0, 260.0)]
        image = np.concatenate(row, axis=1)
        tiles.append((name, image))
        panorama.save_png(renderer.render(values, (2048, 1024), time_ms=900000), folder / f'{name}_equirect.png')
    sheet = np.concatenate([t for _, t in tiles], axis=0)
    picture = Image.fromarray((sheet[..., :3] * 255).astype(np.uint8))
    draw = ImageDraw.Draw(picture)
    for index, (name, _) in enumerate(tiles):
        draw.text((8, index * 270 + 6), name, fill=(255, 255, 255))
    picture.save(folder / 'contact_sheet.png')
    return folder / 'contact_sheet.png'


def build(args):
    PACK.mkdir(exist_ok=True)
    for table in (UPSCALED, NORMALS, DETAILED):  # this build's record only
        table.clear()
    materials = profiles.materials()
    keys = sorted({key for key, _ in materials.values()})
    built = {key: build_panorama(key, 1 if args.no_upscale else 2) for key in keys}
    crunch = None if args.no_dds else crunch_tool([p for key in keys for p in (OUTPUT / key).glob('*.tga')])
    written = []
    if crunch:
        for key in keys:
            for name in profiles.texture_names(key):
                compression = 'DXT5'  # land: alpha is coverage; masks: b and a carry the normals
                to_dds(crunch, OUTPUT / key / f'{name}.tga', PACK / f'{name}.dds', compression)
                written.append(PACK / f'{name}.dds')
    resolved = {}
    for name, (key, parameters) in materials.items():
        text, values = material_text(key, parameters, built[key][1])
        (PACK / f'{name}.mtr').write_text(text, encoding='ascii', newline='\n')
        (PACK / f'{name}.mdl').write_text(sphere.ascii_model(name, name), encoding='ascii', newline='\n')
        written += [PACK / f'{name}.mtr', PACK / f'{name}.mdl']
        resolved[name] = (key, values)
    write_table(table_rows())
    folder = OUTPUT / 'previews'
    folder.mkdir(parents=True, exist_ok=True)
    renderer = None
    if not args.no_render:
        from .preview import Renderer
        renderer = Renderer()
        for key in keys:
            sheet_folder = folder / key
            sheet_folder.mkdir(exist_ok=True)
            renderer.bind(built[key][0])
            mine = {n: v for n, v in resolved.items() if v[0] == key}
            for name, (_, values) in mine.items():
                fallback = renderer.render(values, FALLBACK, time_ms=900000)
                tga = OUTPUT / f'{name}.tga'
                tga.write_bytes(panorama.tga(fallback[..., :3]))
                if crunch:
                    to_dds(crunch, tga, PACK / f'{name}.dds', 'DXT1')
                    written.append(PACK / f'{name}.dds')
            print('contact sheet:', preview_sheet(renderer, mine, sheet_folder))
    # the build owns every srn_sky* resource but the shaders: drop what it no longer writes, once the new set is
    # written. Textures a --no-dds or --no-render build skipped are kept as they were.
    expected = {f'{name}.{ext}' for name in materials for ext in ('mtr', 'mdl', 'dds')}
    expected |= {f'{name}.dds' for key in keys for name in profiles.texture_names(key)}
    for old in PACK.glob('srn_sky*'):
        if old.name not in SHADERS and old.name not in expected:
            old.unlink()
    written = [p for p in PACK.glob('srn_sky*') if p.name not in SHADERS]
    manifest = {
        'schema': 1,
        'shaders': {name: sha(PACK / name) for name in SHADERS},
        'vertexShader': VERTEX_SHADER,
        'panoramas': {key: {'key': profiles.PANORAMAS[key]['key'],
                            'sources': {name: sha(ART / name) for name in profiles.sources(key)},
                            'band': [round(b, 4) for b in built[key][1]],
                            'upscale': ({'model': 'RealESRGAN_x2plus.pth', 'scale': 2, 'cache': UPSCALED[key].name}
                                        if key in UPSCALED else None),
                            'detail': ({'profile': 'qwen21-int8-v1', 'tiles': DETAILED[key]} if key in DETAILED else None),
                            'normals': ({'model': 'moge_2_vitl_normal_fp16.safetensors', 'cache': NORMALS[key].name}
                                        if key in NORMALS else None)} for key in keys},
        'rows': {str(row): {'label': label, 'cyclical': cyclical, 'models': models}
                 for row, (label, cyclical, models) in table_rows().items()},
        'resources': {p.name: sha(p) for p in sorted(set(written))},
        'runtimeTestedInNwn': False,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(f'{len(written)} resources written; rows {sorted(profiles.SKIES)}')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='skykit', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build')
    b.add_argument('--no-dds', action='store_true', help='skip NWN Crunch (no DDS written)')
    b.add_argument('--no-render', action='store_true', help='skip the GL previews and fallback pictures')
    b.add_argument('--no-upscale', action='store_true', help='skip the 2x RealESRGAN upscale (a ComfyUI job unless cached)')
    args = parser.parse_args(argv)
    if args.command == 'build':
        build(args)


if __name__ == '__main__':
    main()
