"""LEAN step 5: single-PLT-per-part atlas assembly with dye-layer garments (user rules 2026-10-08).

Every node of a part model samples the one PLT named exactly like the model (<model>.plt), with <model>n.tga and
<model>r.tga as its only normal/roughness maps and <model>.mtr as its only material. Garment regions (brief, bra) are
encoded in the PLT dye layers that the stock underwear of that part uses, so they take the creature/armour colour
channels like stock NWN underwear.

Per multi-node part:
  * the main skin node (material == model) keeps its UVs and its PLT/normal/roughness texels exactly;
  * every UV island of every other node keeps its position when its gutter ring (4 texels) is free, else it is
    translated (integer texels, no rotation; one uniform scale per node, only when an island would not fit) into
    free atlas space found by FFT correlation; its texels (PLT, normal, roughness, gutter ring included) move 1:1 with
    the island, so tangent-space normal maps stay valid (a translation or uniform scale keeps the UV gradients) and no
    texel is shared between nodes; skin overlays are placed before garments;
  * garment layers: the stock layer of the nearest stock underwear texel (3D, same rig frame), restricted to the cloth
    layers (cloth1/cloth2) the stock part actually uses, mode-filtered; PLT intensity = garment luminance re-centred
    on the stock layer's median intensity with detail gain = stock/garment p10-p90 spread clamped to [1, 1.5];
  * garment roughness: the garment roughness map where one exists, else the garment MTR Roughness parameter.
Node bitmap/materialname -> the model name; per-node garment/overlay resources are no longer produced. Single-node
parts keep their maps. All vertex UVs are clamped into [0,1] (sub-texel moves, counted).

Usage: lean_single_plt_atlas.py --basis <basis dir> --normal-maps <lean_normal_maps dir> --stock-ascii <dir>
       --stock-raw <dir> --output <fresh dir>
"""
import argparse
from collections import deque
from pathlib import Path
import re
import struct

import numpy as np

import lean_common as L
import single_plt_part_contract as single_plt
from nwn_ascii_trimesh import AsciiModel, fmt
from uv_atlas_raster import raster

W = H = L.ATLAS; G = 4
LAYER_NAMES = single_plt.LAYER_NAMES


class Sources:
    """Resolve material resources: re-encoded normal maps first, then the basis (parent per-node) resources."""
    def __init__(self, frozen, basis, normals):
        self.frozen = frozen; self.basis = basis; self.normals = normals

    def path(self, name):
        name = name.lower(); candidate = self.normals/'resources'/name
        if name.endswith('.tga') and candidate.is_file() and name in self.normal_names:
            return self.frozen.take(candidate)
        return self.frozen.take(self.basis/'resources'/name)

    def plt(self, name):
        data = self.path(name).read_bytes(); intensity, layer = single_plt.read_plt(data)
        L.require(intensity.shape == (H, W), 'Atlas PLT size differs: '+name); return data[:24], intensity, layer

    def mtr(self, material):
        return L.mtr_textures(self.path(material+'.mtr').read_text(encoding='cp1252'))


def islands(P, U, F):
    """UV islands: faces joined through corners with identical (position, uv)."""
    k = np.concatenate([np.round(P/1e-6), np.round(U/1e-7)], 1).astype(np.int64)
    _, cid = np.unique(k, axis=0, return_inverse=True); cid = cid.ravel(); C = cid[F]
    parent = np.arange(len(F))

    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    owner = {}
    for f in range(len(F)):
        for c in C[f]:
            if c in owner:
                a, b = find(f), find(owner[c])
                if a != b: parent[a] = b
            else: owner[c] = f
    roots = np.array([find(f) for f in range(len(F))]); _, label = np.unique(roots, return_inverse=True); return label


def uv2px(U):
    return np.stack([U[:, 0]*W, (1-U[:, 1])*H], 1)


def raster_mask(U, F):
    fid, bc = raster(uv2px(U), F, W, H); return fid >= 0, fid, bc


def dilate(mask, r):
    m = mask.copy()
    for _ in range(r):
        n = m.copy(); n[1:] |= m[:-1]; n[:-1] |= m[1:]; n[:, 1:] |= m[:, :-1]; n[:, :-1] |= m[:, 1:]; m = n
    return m


def place(occ, mask, prefer):
    """Integer translation (dy, dx) placing `mask` with no overlap with `occ`, nearest to `prefer` (FFT search at 1/4)."""
    ys, xs = np.nonzero(mask); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max(); crop = mask[y0:y1+1, x0:x1+1]
    f = 4; ho, wo = H//f, W//f
    occ4 = occ.reshape(ho, f, wo, f).any((1, 3))
    ch, cw = crop.shape; ph, pw = -(-ch//f)+1, -(-cw//f)+1
    k4 = np.zeros((ph*f, pw*f), bool); k4[:ch, :cw] = crop; k4 = k4.reshape(ph, f, pw, f).any((1, 3)); k4 = dilate(k4, 1)
    A = np.fft.rfft2(occ4.astype(float), s=(ho+ph, wo+pw)); B = np.fft.rfft2(k4[::-1, ::-1].astype(float), s=(ho+ph, wo+pw))
    corr = np.fft.irfft2(A*B, s=(ho+ph, wo+pw))[ph-1:ph-1+ho-ph+1, pw-1:pw-1+wo-pw+1]
    free = np.argwhere(corr < 0.5)
    if not len(free): return None
    ty, tx = prefer[0]-y0, prefer[1]-x0
    order = np.argsort((free[:, 0]*f-ty)**2+(free[:, 1]*f-tx)**2)
    for i in order[:400]:
        oy, ox = free[i]*f; dy, dx = oy-y0, ox-x0
        if oy+ch > H or ox+cw > W: continue
        if not (occ[oy:oy+ch, ox:ox+cw] & crop).any(): return int(dy), int(dx)
    return None


def stock_garment_layers(stock_plt):
    """Cloth dye layers the stock part's underwear actually uses."""
    _, layer = single_plt.read_plt(stock_plt)
    return tuple(int(value) for value in np.unique(layer) if int(value) in single_plt.GARMENT_LAYERS)


def ascii_trimesh(text):
    """Minimal stock ASCII trimesh reader (verts, faces with tvert indices, tverts, position)."""
    out = []
    for m in re.finditer(r'(?ms)^\s*node trimesh (\S+)\s*\n(.*?)^\s*endnode', text):
        body = m.group(2)

        def block(key, ncols):
            mm = re.search(r'(?m)^\s*%s\s+(\d+)\s*\n' % key, body)
            if not mm: return None
            n = int(mm.group(1)); lines = body[mm.end():].splitlines()[:n]
            return np.array([[float(x) for x in line.split()[:ncols]] for line in lines])
        v = block('verts', 3); f = block('faces', 8); t = block('tverts', 2)
        pos = re.search(r'(?m)^\s*position\s+(\S+)\s+(\S+)\s+(\S+)', body)
        if v is None or f is None: continue
        out.append({'name': m.group(1), 'verts': v, 'faces': f[:, :3].astype(int), 'tfaces': f[:, 4:7].astype(int), 'tverts': t,
                    'position': [float(x) for x in pos.groups()] if pos else [0, 0, 0]})
    return out


def stock_labels(ascii_path, plt_path, allowed):
    """3D surface points, layers and intensities of the stock underwear texels in the allowed layers."""
    nodes = ascii_trimesh(Path(ascii_path).read_text(encoding='latin-1')); data = Path(plt_path).read_bytes()
    w, h = struct.unpack('<II', data[16:24]); px = np.frombuffer(data[24:], 'u1').reshape(h, w, 2)[::-1]
    X, Lb, I = [], [], []
    for n in nodes:
        P = n['verts']+np.array(n['position']); Pc = P[n['faces']].reshape(-1, 3); Uc = n['tverts'][n['tfaces']].reshape(-1, 2); Fc = np.arange(len(Pc)).reshape(-1, 3)
        fid, bc = raster(np.stack([Uc[:, 0]*w, (1-Uc[:, 1])*h], 1), Fc, w, h); ys, xs = np.nonzero(fid >= 0)
        X.append((Pc[Fc[fid[ys, xs]]]*bc[ys, xs][:, :, None]).sum(1)); Lb.append(px[ys, xs, 1]); I.append(px[ys, xs, 0])
    X, Lb, I = np.concatenate(X), np.concatenate(Lb), np.concatenate(I); keep = np.isin(Lb, allowed)
    return X[keep], Lb[keep], I[keep]


def majority(lab, mask, layers, r=4):
    if len(layers) == 1: return np.where(mask, layers[0], lab)
    out = lab.copy(); ys, xs = np.nonzero(mask); cnt = {}
    for layer in layers:
        ind = (lab == layer) & mask; c = np.pad(ind.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
        y0, y1 = np.clip(ys-r, 0, H), np.clip(ys+r+1, 0, H); x0, x1 = np.clip(xs-r, 0, W), np.clip(xs+r+1, 0, W)
        cnt[layer] = c[y1, x1]-c[y0, x1]-c[y1, x0]+c[y0, x0]
    best = np.array(layers)[np.argmax(np.stack([cnt[layer] for layer in layers]), 0)]; out[ys, xs] = best; return out


def rank_map(src, target, ref=None):
    """Garment luminance re-centred on the stock layer median; detail gain = stock/garment p10-p90 spread in [1, 1.5]."""
    ref = src if ref is None else ref
    gs = max(np.percentile(ref, 90)-np.percentile(ref, 10), 1e-6); ts = np.percentile(target, 90)-np.percentile(target, 10)
    gain = float(np.clip(ts/gs, 1.0, 1.5))
    return np.clip(np.round(np.median(target)+(src-np.median(ref))*gain), 0, 255).astype(np.uint8)


def bilinear(img, sx, sy):
    sx = np.clip(sx-0.5, 0, W-1.001); sy = np.clip(sy-0.5, 0, H-1.001); x0 = np.floor(sx).astype(int); y0 = np.floor(sy).astype(int)
    fx = sx-x0; fy = sy-y0
    if img.ndim == 3: fx = fx[:, None]; fy = fy[:, None]
    v = img[y0, x0]*(1-fx)*(1-fy)+img[y0, x0+1]*fx*(1-fy)+img[y0+1, x0]*(1-fx)*fy+img[y0+1, x0+1]*fx*fy
    return np.clip(np.round(v), 0, 255).astype(np.uint8)


def garment_texels(x, cov_all, fid_all, bc_all, Y, garment_layers, stock, sI, sL, layer_stats):
    """Assign dye layers (nearest stock texel, mode-filtered) and shading intensity over the node's coverage + ring."""
    Xs, Ls, Is = stock
    ring = dilate(cov_all, G); ys, xs = np.nonzero(ring); fidc = fid_all.copy(); bcc = bc_all.copy()
    queue = deque(zip(*np.nonzero(cov_all))); seen = cov_all.copy()
    while queue:  # gutter texels take the nearest covered texel's surface point
        y, xx = queue.popleft()
        for yy, x2 in ((y+1, xx), (y-1, xx), (y, xx+1), (y, xx-1)):
            if 0 <= yy < H and 0 <= x2 < W and ring[yy, x2] and not seen[yy, x2]:
                seen[yy, x2] = True; fidc[yy, x2] = fidc[y, xx]; bcc[yy, x2] = bcc[y, xx]; queue.append((yy, x2))
    Xt = (x['P'][x['F'][fidc[ys, xs]]]*bcc[ys, xs][:, :, None]).sum(1); near = np.empty(len(Xt), int)
    for j in range(0, len(Xt), 4000):
        d = ((Xt[j:j+4000, None, :]-Xs[None])**2).sum(2); near[j:j+4000] = d.argmin(1)
    labimg = np.zeros((H, W), np.uint8); labimg[ys, xs] = Ls[near]; labimg = majority(labimg, ring, list(garment_layers))
    sL[ys, xs] = labimg[ys, xs]
    for layer in garment_layers:
        m = ring & (sL == layer)
        if m.any():
            covm = cov_all & (sL == layer); sI[m] = rank_map(Y[m], Is[Ls == layer], Y[covm] if covm.any() else None)
            layer_stats['%s:%d' % (x['name'], layer)] = {
                'layer': LAYER_NAMES[layer], 'texels': int(covm.sum()),
                'garmentLumP10P50P90': np.percentile(Y[covm], [10, 50, 90]).round(1).tolist() if covm.any() else None,
                'stockIntensityP10P50P90': np.percentile(Is[Ls == layer], [10, 50, 90]).tolist(),
                'pltIntensityP10P50P90': np.percentile(sI[covm], [10, 50, 90]).tolist() if covm.any() else None}


def assemble_part(model, nodes, src, stock_ascii, stock_raw, frozen):
    """Repack one multi-node part into its model atlas. Returns (PLT bytes, normal (meta, img), rough (meta, img), part report)."""
    base = next(x for x in nodes if x['material'] == model)
    header, I, Lyr = src.plt(model+'.plt')
    nmeta, Nmap = L.tga_read(src.path(model+'n.tga')); rmeta, Rmap = L.tga_read(src.path(model+'r.tga'))
    Nmap = Nmap.copy(); Rmap = Rmap.copy()
    bm, _, _ = raster_mask(base['U'], base['F']); occ = dilate(bm, 2*G); owner = np.where(bm, 0, -1)
    stock_plt = frozen.take(Path(stock_raw)/(model+'.plt')); garment_layers = stock_garment_layers(stock_plt.read_bytes())
    stock = None; placements = []; layer_stats = {}; slots = {base['name']: {'role': 'skin', 'pltLayers': [0]}}
    ordered = sorted(enumerate(nodes), key=lambda t: 'texture0' in src.mtr(t[1]['material']))  # skin overlays first, garments last
    for ni, x in ordered:
        if x is base: continue
        t = src.mtr(x['material']); garment = 'texture0' in t
        if garment:
            L.require(garment_layers, 'Stock part has no cloth dye layer for its garment: '+model)
            if stock is None: stock = stock_labels(frozen.take(Path(stock_ascii)/(model+'.mdl')), stock_plt, list(garment_layers))
            _, col = L.tga_read(src.path(t['texture0']+'.tga')); Y = col.astype(float)@np.array([0.2126, 0.7152, 0.0722])
            sI = np.zeros((H, W), np.uint8); sL = np.zeros((H, W), np.uint8)
        else:
            _, sI, sL = src.plt(x['material']+'.plt')
        _, sN = L.tga_read(src.path(t['texture1']+'.tga'))
        if 'texture3' in t: _, sR = L.tga_read(src.path(t['texture3']+'.tga'))
        else: sR = np.full((H, W, 3), int(round(t.get('roughness', 0.72)*255)), np.uint8)
        lab = islands(x['P'], x['U'], x['F']); cov_all, fid_all, bc_all = raster_mask(x['U'], x['F'])
        if garment:
            garment_texels(x, cov_all, fid_all, bc_all, Y, garment_layers, stock, sI, sL, layer_stats)
        isl = []
        for il in range(lab.max()+1):
            fsel = lab == il; m, _, _ = raster_mask(x['U'], x['F'][fsel]); isl.append((int(m.sum()), il, fsel))
        isl.sort(key=lambda t_: -t_[0]); failed = True
        for scale in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5):  # one uniform scale per node keeps its texel density consistent
            occ_try = occ.copy(); plan = []; failed = False
            for area, il, fsel in isl:
                vs = np.unique(x['F'][fsel]); org = uv2px(x['U'][vs]).min(0)
                Ut = x['U'].copy(); pt = org+(uv2px(x['U'][vs])-org)*scale; Ut[vs, 0] = pt[:, 0]/W; Ut[vs, 1] = 1-pt[:, 1]/H
                m, _, _ = raster_mask(Ut, x['F'][fsel])
                if not m.any():  # sub-texel sliver island: reserve the texels under its vertices
                    q = uv2px(Ut[vs]); m = np.zeros((H, W), bool); m[np.clip(q[:, 1].astype(int), 0, H-1), np.clip(q[:, 0].astype(int), 0, W-1)] = True
                md = dilate(m, G); ys0, xs0 = np.nonzero(m)
                if scale == 1.0 and not (occ_try & md).any(): dy = dx = 0
                else:
                    r = place(occ_try, md, (int(ys0.min()), int(xs0.min())))
                    if r is None: failed = True; break
                    dy, dx = r
                plan.append((il, fsel, vs, Ut, m, dy, dx, org))
                yy, xx = np.nonzero(dilate(m, 2*G)); yy = yy+dy; xx = xx+dx; ok = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < W); occ_try[yy[ok], xx[ok]] = True
            if not failed: break
        L.require(not failed, 'No free atlas space for '+x['name'])
        occ = occ_try; newU = x['U'].copy()
        for il, fsel, vs, Ut, m, dy, dx, org in plan:
            md = dilate(m, G); ty0, tx0 = np.nonzero(md); ty, tx = ty0+dy, tx0+dx
            if scale == 1.0:
                I[ty, tx] = sI[ty0, tx0]; Lyr[ty, tx] = sL[ty0, tx0]; Nmap[ty, tx] = sN[ty0, tx0]; Rmap[ty, tx] = sR[ty0, tx0]
            else:
                sxp = org[0]+(tx0+0.5-org[0])/scale; syp = org[1]+(ty0+0.5-org[1])/scale
                I[ty, tx] = bilinear(sI.astype(float), sxp, syp); Nmap[ty, tx] = bilinear(sN.astype(float), sxp, syp); Rmap[ty, tx] = bilinear(sR.astype(float), sxp, syp)
                Lyr[ty, tx] = sL[np.clip(syp.astype(int), 0, H-1), np.clip(sxp.astype(int), 0, W-1)]
                if garment: Lyr[ty, tx] = np.where(Lyr[ty, tx] == 0, garment_layers[0], Lyr[ty, tx])  # resampled edge texels stay in the dye layer
            oy, ox = np.nonzero(m); clash = owner[oy+dy, ox+dx] >= 0; owner[oy+dy, ox+dx] = ni
            newU[vs, 0] = Ut[vs, 0]+dx/W; newU[vs, 1] = Ut[vs, 1]-dy/H
            placements.append({'node': x['name'], 'island': il, 'faces': int(fsel.sum()), 'texels': int(m.sum()), 'offset': [dx, dy], 'scale': scale,
                               'moved': bool(dx or dy or scale != 1.0), 'ownershipClashTexels': int(clash.sum())})
        x['U'] = newU
        used = sorted({int(k.split(':')[1]) for k in layer_stats if k.startswith(x['name']+':')}) if garment else [0]
        slots[x['name']] = {'role': 'garment' if garment else 'skin', 'pltLayers': used or [garment_layers[0]]}
    plt = single_plt.write_plt(I, Lyr)  # pixels; the parent PLT header is kept
    report = {'placements': placements, 'garmentLayers': layer_stats, 'stockGarmentLayers': list(garment_layers),
              'layerTexels': {LAYER_NAMES.get(int(k), str(k)): int(c) for k, c in zip(*np.unique(Lyr, return_counts=True))}}
    return header+plt[24:], (nmeta, Nmap), (rmeta, Rmap), slots, report


def assemble(basis_dir, normals_dir, stock_ascii, stock_raw, output):
    frozen = L.Frozen(); basis_dir = Path(basis_dir).resolve(); normals_dir = Path(normals_dir).resolve()
    basis = L.read_json(frozen.take(basis_dir/'basis.json')); normals = L.read_json(frozen.take(normals_dir/'normal-maps.json'))
    L.require(basis.get('kind') == 'lean-basis-composition' and normals.get('kind') == 'lean-normal-maps', 'LEAN basis and normal maps required')
    L.require(normals['basis']['sha256'] == L.sha(basis_dir/'basis.json'), 'Normal maps were encoded for a different basis')
    src = Sources(frozen, basis_dir, normals_dir); src.normal_names = set(normals['maps'])
    for name, row in normals['maps'].items(): L.require(L.sha(normals_dir/'resources'/name) == row['sha256'], 'Normal map changed: '+name)
    output = L.fresh(output); (output/'ascii').mkdir(); (output/'resources').mkdir()
    parts = {}; clamped = {}
    for part in L.PARTS:
        row = basis['parts'][part]; model = row['model']; ascii_path = frozen.pinned(row['ascii']); am = AsciiModel.read(ascii_path)
        nodes = []
        for n in am.trimeshes():
            V, _, TV, F = am.arrays(n)
            L.require(np.array_equal(F[:, :3], F[:, 4:7]) and len(V) == len(TV), 'Expected 1:1 render-vertex LEAN ASCII')
            nodes.append(dict(name=n.name, material=n.fields['materialname'][0].lower(), P=V.astype(float), U=TV[:, :2].astype(float).copy(), F=F[:, :3].astype(np.int64)))
        report = {'nodes': [x['name'] for x in nodes], 'materialsBefore': {x['name']: x['material'] for x in nodes}}
        if len(nodes) > 1:
            plt, (nmeta, Nmap), (rmeta, Rmap), slots, extra = assemble_part(model, nodes, src, stock_ascii, stock_raw, frozen)
            (output/'resources'/(model+'.plt')).write_bytes(plt)
            L.tga_write(output/'resources'/(model+'n.tga'), nmeta, Nmap); L.tga_write(output/'resources'/(model+'r.tga'), rmeta, Rmap)
            report.update(extra)
        else:
            L.require(nodes[0]['material'] == model, 'Single-node part must use its model material: '+model)
            for suffix in ('.plt', 'n.tga', 'r.tga'):
                (output/'resources'/(model+suffix)).write_bytes(src.path(model+suffix).read_bytes())
            slots = {nodes[0]['name']: {'role': 'skin', 'pltLayers': [0]}}
        main = src.mtr(model)
        L.require(main.get('texture1') == model+'n' and main.get('texture3') == model+'r' and 'texture0' not in main, 'Main skin MTR must bind the model maps: '+model)
        (output/'resources'/(model+'.mtr')).write_bytes(src.path(model+'.mtr').read_bytes())
        count = 0
        for x in nodes:
            n = am.node(x['name']); U = np.clip(x['U'], 0.0, 1.0); count += int((np.abs(U-x['U']) > 0).any(1).sum())
            h, cnt = n.sections['tverts']; L.require(cnt == len(U), 'tvert count differs')
            indent = re.match(r'\s*', am.lines[h+1]).group(0)
            for i, t in enumerate(U): am.lines[h+1+i] = indent+fmt(t[0])+' '+fmt(t[1])+' 0'
            for field in ('bitmap', 'materialname'):
                for li in range(n.start, n.end):
                    s = am.lines[li].split()
                    if s and s[0] == field: am.lines[li] = re.match(r'\s*', am.lines[li]).group(0)+field+' '+model
            am.parse()
        clamped[model] = count; am.write(output/'ascii'/(model+'.mdl'))
        text = (output/'ascii'/(model+'.mdl')).read_text(encoding='cp1252')
        proof = single_plt.check_part(model, text, (output/'resources'/(model+'.mtr')).read_text(encoding='cp1252'),
                                      (output/'resources'/(model+'.plt')).read_bytes(), slots)
        report.update(materialsAfter={x['name']: model for x in nodes}, materialSlots=slots, singlePltContract=proof['nodes'],
                      ascii=L.pin(output/'ascii'/(model+'.mdl')),
                      resources={model+s: L.sha(output/'resources'/(model+s)) for s in ('.mtr', '.plt', 'n.tga', 'r.tga')})
        parts[part] = report
        print(model, len(nodes), 'nodes', sum(1 for p in report.get('placements', []) if p['moved']), 'moved islands', flush=True)
    before = sorted(basis['resourceHashes'])
    after = sorted(p.name for p in (output/'resources').iterdir())
    receipt = {'schemaVersion': 1, 'kind': 'lean-single-plt-atlas', 'sex': basis['sex'], 'prefix': basis['prefix'],
               'materialLayout': single_plt.LAYOUT, 'basis': L.pin(basis_dir/'basis.json'), 'normalMaps': L.pin(normals_dir/'normal-maps.json'),
               'compiledBasis': normals['compiledBasis'], 'parts': parts, 'uvClamp': clamped,
               'removedResources': sorted(set(before)-set(after)), 'inventory': {'nonModelResources': after, 'count': len(after),
               'models': len(parts), 'closure': len(after)+len(parts)},
               'frozenInputs': {**frozen.verify(), **L.helper_pins('lean_single_plt_atlas.py', 'single_plt_part_contract.py', 'uv_atlas_raster.py', 'nwn_ascii_trimesh.py')},
               'selected': False, 'clientAccepted': False, 'productionAccepted': False}
    return L.save_json(output/'atlas.json', receipt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('basis', 'normal-maps', 'stock-ascii', 'stock-raw', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args(); print(assemble(args.basis, args.normal_maps, args.stock_ascii, args.stock_raw, args.output))
