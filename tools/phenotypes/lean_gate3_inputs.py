"""Offline Gate 3 inputs for a compiled single-PLT body: decoded native arrays and per-variant palette colours.

Every mesh is read from the compiled native binary (literal P/N/UV/T/sign/faces, constrained decoder; node names from
the composed ASCII). Colour is a categorical per-texel palette lookup of the compiled-input PLT before any filtering,
per layer: skin (0) -> pal_skin01 row = skin palette; cloth1/cloth2 (4/5) -> pal_cloth01 row = dye; metal (2/3) ->
pal_armor01/02 row; leather (6/7) -> pal_leath01 row; hair (1) -> pal_hair01 row. Each variant is (skin row, dye row):
dye row 0 is the stock default (undyed) garment colour. Normal and roughness maps are the exact runtime TGAs
transcoded to PNG without pixel change. Head/neck context and the rig recipe are pinned inputs. Worst-case motion
samples are measured from the recipe (largest summed joint bend per clip). Writes inputs only; no render/acceptance.

Usage: lean_gate3_inputs.py --converted <compiled composition> --rig-recipe <json> --palettes <stock raw dir>
       --context <json list of {name, joint, arrays:{path,sha256}, colors:{key:{path,sha256}}}> --variant KEY:SKIN:DYE [...]
       --clips <comma list> --idle CLIP:FRACTION --closeups <json> --output <fresh dir>
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import lean_common as L
import single_plt_part_contract as single_plt
from audit_target_native_part import decode
from nwn_ascii_trimesh import AsciiModel

LAYER_PALETTE = {0: 'pal_skin01.tga', 1: 'pal_hair01.tga', 2: 'pal_armor01.tga', 3: 'pal_armor02.tga', 4: 'pal_cloth01.tga',
                 5: 'pal_cloth01.tga', 6: 'pal_leath01.tga', 7: 'pal_leath01.tga'}
PAIRS = [('pelvis_g', 'lthigh_g'), ('pelvis_g', 'rthigh_g'), ('lthigh_g', 'lshin_g'), ('rthigh_g', 'rshin_g'), ('lshin_g', 'lfoot_g'),
         ('rshin_g', 'rfoot_g'), ('torso_g', 'lbicep_g'), ('torso_g', 'rbicep_g'), ('lbicep_g', 'lforearm_g'), ('rbicep_g', 'rforearm_g'),
         ('lforearm_g', 'lhand_g'), ('rforearm_g', 'rhand_g'), ('pelvis_g', 'torso_g'), ('torso_g', 'neck_g')]


def colour(intensity, layer, palettes, skin_row, dye_row):
    """Categorical palette lookup per PLT layer; other skin-like layers use the dye row of their palette."""
    out = np.zeros(intensity.shape+(3,), np.uint8)
    for value in np.unique(layer):
        mask = layer == value; name = LAYER_PALETTE.get(int(value), 'pal_cloth01.tga')
        row = skin_row if int(value) == 0 else dye_row
        out[mask] = palettes[name][row][intensity[mask]]
    return out


def worst_case(samples, idle, clips):
    def rot(m): return np.asarray(m, float)[:3, :3]

    def angle(a, b):
        r = rot(a).T@rot(b); return float(np.degrees(np.arccos(np.clip((np.trace(r)-1)/2, -1, 1))))

    def relative(s, a, b): return np.linalg.inv(np.asarray(s['matrices'][a]))@np.asarray(s['matrices'][b])
    scores = []
    for i, s in enumerate(samples):
        pairs = [(a, b) for a, b in PAIRS if a in s['matrices'] and b in s['matrices']]
        per = {f'{a}->{b}': angle(relative(idle, a, b), relative(s, a, b)) for a, b in pairs}
        scores.append({'index': i, 'clip': s['clip'], 'fraction': s['fraction'], 'totalJointBendDeg': sum(per.values()), 'perJointDeg': per})
    worst = {}
    for clip in clips:
        rows = [x for x in scores if x['clip'] == clip]
        L.require(rows, 'Rig recipe lacks clip '+clip)
        worst[clip] = max(rows, key=lambda x: x['totalJointBendDeg'])
    return worst, scores


def prepare(converted, rig_recipe, palettes_dir, context_path, variants, clips, idle_spec, closeups_path, output):
    frozen = L.Frozen(); converted = Path(converted).resolve()
    composition = L.read_json(frozen.take(converted/'conversion.json')); native = L.read_json(frozen.take(converted/'native-compile.json'))
    L.require(composition.get('completeBodyComposed') is True and composition.get('materialLayout') == single_plt.LAYOUT, 'Complete single-PLT composition required')
    L.require(native.get('complete') is True and native.get('executionMode') == 'compilemodel', 'Complete native compile required')
    rig = L.read_json(frozen.take(rig_recipe)); samples = rig['samples']
    palettes = {name: np.asarray(Image.open(frozen.take(Path(palettes_dir)/name)).convert('RGB')) for name in sorted(set(LAYER_PALETTE.values()))}
    output = L.fresh(output); (output/'arrays').mkdir(); (output/'textures').mkdir()
    binaries = {row['name']: row for row in native['models']}; models = []
    for row in composition['parts']:
        part, model = row['part'], row['model']; mdl = frozen.take(converted/'resources'/(model+'.mdl')); ascii_path = frozen.take(converted/'ascii'/(model+'.mdl'))
        L.require(L.sha(mdl) == binaries[model+'.mdl']['binarySha256'] and L.sha(ascii_path) == composition['asciiModelHashes'][model+'.mdl'], 'Stale compiled model: '+model)
        names = [n.name for n in AsciiModel.read(ascii_path).trimeshes()]; meshes, _ = decode(mdl.read_bytes(), model, names)
        intensity, layer = single_plt.read_plt(frozen.take(converted/'resources'/(model+'.plt')).read_bytes())
        colours = {}
        for key, skin_row, dye_row in variants:
            path = output/'textures'/f'{model}-{key}.png'; Image.fromarray(colour(intensity, layer, palettes, skin_row, dye_row)).save(path); colours[key] = L.pin(path)
        maps = {}
        for key, suffix in (('normal', 'n'), ('roughness', 'r')):
            _, pixels = L.tga_read(frozen.take(converted/'resources'/(model+suffix+'.tga'))); path = output/'textures'/f'{model}{suffix}.png'
            Image.fromarray(pixels).save(path); L.require(np.array_equal(np.asarray(Image.open(path)), pixels), 'PNG transcode changed pixels'); maps[key] = L.pin(path)
        rows = []
        for name in names:
            m = meshes[name]; arrays = output/'arrays'/(name+'.npz')
            np.savez_compressed(arrays, position=m['position'], normal=m['normal'], uv=m['uv'], tangent=m['tangent'], sign=m['sign'], faces=m['faces'].astype('<u2'))
            slot = composition['partMaterialSlots'][part][name]
            rows.append({'mesh': name, 'role': slot['role'], 'pltLayers': slot['pltLayers'], 'arrays': L.pin(arrays), 'colors': colours,
                         'normal': maps['normal'], 'roughness': maps['roughness'], 'vertices': int(len(m['position'])), 'triangles': int(len(m['faces']))})
        models.append({'part': part, 'model': model, 'joint': L.JOINTS[part], 'binary': L.pin(mdl), 'meshes': rows})
    context = L.read_json(frozen.take(context_path))
    for row in context:
        frozen.pinned(row['arrays']); L.require(set(row['colors']) >= {key for key, _, _ in variants}, 'Context colours must cover every variant')
        for value in row['colors'].values(): frozen.pinned(value)
    clip, fraction = idle_spec
    idle = next(s for s in samples if s['clip'] == clip and abs(s['fraction']-fraction) < 1e-9)
    worst, scores = worst_case(samples, idle, clips)
    closeups = L.read_json(frozen.take(closeups_path))
    manifest = {'schemaVersion': 1, 'kind': 'lean-gate3-offline-inputs', 'sex': composition['modelPrefix'], 'composition': L.pin(converted/'conversion.json'),
                'nativeCompile': L.pin(converted/'native-compile.json'), 'rigRecipe': L.pin(rig_recipe), 'palettes': L.pin(palettes_dir/'pal_skin01.tga'),
                'variants': [{'key': key, 'skinRow': skin, 'dyeRow': dye} for key, skin, dye in variants], 'models': models, 'context': context,
                'idleSample': {'clip': clip, 'fraction': fraction}, 'worstCaseMotion': {k: {x: v[x] for x in ('index', 'clip', 'fraction', 'totalJointBendDeg')} for k, v in worst.items()},
                'motionScores': scores, 'closeups': closeups, 'decoder': 'audit_target_native_part.decode (constrained literal native layout)',
                'frozenInputs': {**frozen.verify(), **L.helper_pins('lean_gate3_inputs.py', 'single_plt_part_contract.py', 'audit_target_native_part.py')},
                'workingGlbUsed': False, 'selected': False, 'clientAccepted': False}
    return L.save_json(output/'manifest.json', manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('converted', 'rig-recipe', 'palettes', 'context', 'closeups', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--variant', action='append', required=True); parser.add_argument('--clips', required=True); parser.add_argument('--idle', required=True)
    args = parser.parse_args()
    variants = [(v.split(':')[0], int(v.split(':')[1]), int(v.split(':')[2])) for v in args.variant]
    clip, fraction = args.idle.split(':')
    print(prepare(args.converted, args.rig_recipe, args.palettes.resolve(), args.context, variants, args.clips.split(','), (clip, float(fraction)), args.closeups, args.output))
