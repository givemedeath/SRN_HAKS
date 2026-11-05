"""skirtzone.py HEAD_DIR ATTEMPT OUT.png GAP...: the neck cut skirt's hair zone (neck.neck_cut: below the plane down to depth,
more than GAP outside the body neck, outside the front cone) on the repair's uncut master, for each GAP: front and left
views, kept skirt hair red, the rest of the below-plane surface grey (removed), above the plane light. Read-only."""
import sys
import numpy as np
from PIL import Image, ImageDraw
import headkit.neck as N
from _frame import head_neck, local_positions
head, attempt, out = sys.argv[1:4]; gaps = [float(g) for g in sys.argv[4:]]
man, pol, bv, bf = head_neck(head); cut = pol['cut']; skirt = cut['skirt']
L = local_positions(pol, f'{head}/run/repair/{attempt}/master-uncut.glb')
if cut['height'] == 'measured': cut['height'] = N.measured_jaw(L, bv, bf, cut)['height']-cut['clearance']
above = L[:, 2]-(cut['height']+cut['slope']*L[:, 1]); region = np.flatnonzero((above >= -skirt['depth']) & (above < cut['band']))
low = max(float(bv[:, 2].min())+1e-4, float(L[:, 2].min())); high = float(bv[:, 2].max())-1e-4
_, surface, offset = N.body_profile(bv, bf, low, high)(L[region], L[region, 2]); dist = np.linalg.norm(offset, axis=1)-surface; ang = N.face_angle(offset)
S = 420; lo, hi = L.min(0), L.max(0); ctr = (lo+hi)/2; ext = (hi-lo).max()*1.05; sheet = Image.new('RGB', (2*S*len(gaps), S+20), (30, 30, 30)); d = ImageDraw.Draw(sheet)
for g, gap in enumerate(gaps):
    hair = np.zeros(len(L), bool); hair[region] = (dist > gap) & (ang >= cut['cone']); hair &= above < 0
    col = np.where(above[:, None] >= 0, [210, 210, 210], [110, 110, 110]).astype(np.uint8); col[hair] = (230, 50, 50)
    for j, (ax, sgn) in enumerate(((0, -1), (1, 1))):  # front: image x = -x (character right on image left); left: image x = y
        u = sgn*(L[:, ax]-ctr[ax]); depth = L[:, 1] if ax == 0 else -L[:, 0]; o = np.argsort(depth)
        px = ((u/ext+.5)*S).astype(int).clip(0, S-1); py = ((.5-(L[:, 2]-ctr[2])/ext)*S).astype(int).clip(0, S-1)
        img = np.full((S, S, 3), 30, np.uint8); img[py[o], px[o]] = col[o]; sheet.paste(Image.fromarray(img), ((2*g+j)*S, 20))
    d.text((2*g*S+4, 4), f'gap {gap}: {int(hair.sum())} hair vertices (front | left)', fill='yellow')
sheet.save(out); print(out, {g: int(((dist > g) & (ang >= cut['cone']) & (above[region] < 0)).sum()) for g in gaps})
