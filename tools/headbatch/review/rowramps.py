"""rowramps.py HEAD_DIR: after a palette run, one sheet (review-evidence/rowramps.png) with each mapped channel's chosen row and
its next ranked rows as ramps, plus the median design colour of that channel's texels, so a hue-wrong winner (rose-brown hair
row 65 for silver hair, maroon accent row 64 for a dark undercut) is caught before the render (RUNBOOK 61)."""
import json, os, sys
from PIL import Image, ImageDraw
from headbatch.head_files import complete
head = sys.argv[1]; A = str(complete(head, 'palette'))
rows = json.load(open(A+'/receipt.json'))['result']['rows']; rank = json.load(open(A+'/row-ranking.json')) if os.path.exists(A+'/row-ranking.json') else {}  # every row pinned: no ranking
man = json.load(open(head+'/manifest.json')); inputs = man['palette']['inputs']
files = {k: v['path'] for k, v in man['inputs'].items() if k.startswith('palette')}
lines = []
for ch, row in rows.items():
    cands = [row] + [t['row'] for t in rank.get(ch, {}).get('top', []) if t['row'] != row][:2]
    pal = Image.open(head+'/'+files[inputs[ch]]).convert('RGB')
    for r in cands: lines.append((f'ch {ch} row {r}' + (' (chosen)' if r == row else ''), pal.crop((0, r, 256, r+1)).resize((448, 18))))
sheet = Image.new('RGB', (600, 22*len(lines)), 'black'); d = ImageDraw.Draw(sheet)
for i, (label, strip) in enumerate(lines): sheet.paste(strip, (148, i*22)); d.text((4, i*22+4), label, fill='white')
os.makedirs(head+'/review-evidence', exist_ok=True); sheet.save(head+'/review-evidence/rowramps.png'); print(head+'/review-evidence/rowramps.png', rows)
