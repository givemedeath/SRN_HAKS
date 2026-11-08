"""own_draft.py HEAD_DIR RULES.json OUT.png [NAME=CONDITION_JSON ...]: offline ownership preview of a draft rule set (no launch, no
attempt). Evaluates RULES.json (the ownership block: regions, rules, default)
with the toolkit's own rule_ownership on the head's newest complete bake, draws colour / ownership (toolkit preview colours: skin brown,
hair black, metal blue, tattoo1 cream, tattoo2 red), prints channel and per-rule texel counts, and for each NAME=CONDITION prints
the 10/50/90th percentiles of lum, sat, red, rb, r, g, b and metallic of the texels it selects (rule thresholds)."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image
from headkit.paint import rule_ownership, texel_values, PREVIEW
from headkit.predicates import when
from headkit.preview import splat, sheet
from headkit.gltf import mesh
from headbatch.head_files import complete, read
from headkit.uv import raster_audit

head, rules, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]); name = head.name
config = json.loads(rules.read_text(encoding='utf-8'))
bake = read(complete(head, 'bake')/'receipt.json')
source = json.loads(Path(bake['dependencies']['unwrap']['path']).read_text())['result']['mesh']['path']; maps = bake['result']['maps']
colour, metallic = maps['basecolor-4096.png']['path'], maps['metallic-4096.png']['path']
labels, report = rule_ownership(source, colour, config, metallic=metallic)
rgb = np.asarray(Image.open(colour).convert('RGB')); value = mesh(source)
sheet(splat(value, [rgb, PREVIEW[labels]], size=400, samples=2500000), 2, f'{name}: colour / ownership ' + json.dumps(report['channels']), 400).save(out)
NAMES = ['skin', 'hair', 'metal1', 'metal2', 'cloth1', 'cloth2', 'leather1', 'leather2', 'tattoo1', 'tattoo2']  # NWN PLT layers (RUNBOOK 97)
print('Face-profile convention: 0 skin including design ink, 1 hair/brows/beard, 2/3 cyberware, 8 iris only, 9 horns/tusks.')
print(name, {f'{k} {NAMES[int(k)]}': v for k, v in report['channels'].items()})
for row in report['rules']: print(f"  {row['channel']} {NAMES[row['channel']]} {row['name']}: {row['texels']}")
if len(sys.argv) > 4:
    m = np.asarray(Image.open(metallic).convert('L'))
    values = texel_values(value, rgb, raster_audit(value['uv'], len(rgb))[1], {'metallic': lambda: m})
    for arg in sys.argv[4:]:
        label, condition = arg.split('=', 1); selected = when(json.loads(condition), values, config.get('regions', {})) & values['mapped']
        row = [f'{label}: {int(selected.sum())} texels']
        for q in ('lum', 'sat', 'red', 'rb', 'r', 'g', 'b', 'metallic'):
            v = np.asarray(values[q])[selected] if selected.any() else np.zeros(1)
            row.append(f'{q} ' + '/'.join(str(int(x)) for x in np.percentile(v, [10, 50, 90])))
        print('  '.join(row))
