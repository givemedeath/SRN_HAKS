"""LEAN step 2b: bounded border and crease repairs of reduced nodes (versioned, config-declared, no shelves).

Three explicit, bounded operations, each declared in the repair configuration:
  * borderSmoothing: shared borders between declared node pairs (e.g. pelvis skin / skin1 / skin2 overlay shells)
    that became jagged under reduction are snapped back to the parent outline: while the parent border polyline
    deviates more than the tolerance from a LEAN border edge, that edge is split at the farthest parent border vertex
    (exact parent position and per-node normal; UV interpolated along the LEAN edge so it stays on the painted LEAN
    island), splitting the one adjacent triangle on each side. Splits that would fold a triangle are skipped and
    counted. Protected nodes (the garment) are never touched. Bounded by a maximum number of new triangles.
  * crackWelds: a node's sub-0.1 mm open-boundary sliver (two vertices micrometres apart) is closed by welding the
    pair (positions only; degenerate faces removed).
  * garmentPullback: skin vertices hidden under a garment in the parent that sit in front of, or closer than KEEP
    behind, the LEAN garment are pushed inward along their normal; vertices shared with the garment rim never move,
    so no visible step is introduced. Garment geometry never changes.
Only the repaired nodes are written; every other node stays the reduced node. Usage:
  lean_border_repair.py --parent <manifest> --reduction <reduction.json> [...] --config <repair config> --output <fresh dir>
"""
import argparse
from collections import defaultdict, deque
import heapq
from pathlib import Path

import numpy as np

import lean_common as L

Q = 1e-6
CONFIG = 'lean-border-repair-config'


def key(p):
    return tuple(np.round(np.asarray(p, float)/Q).astype(np.int64))


class Node:
    def __init__(self, name, arrays):
        self.name = name; self.P = arrays['position'].astype(np.float64).copy(); self.U = arrays['uv'].astype(np.float64).copy()
        self.N = arrays['normal'].astype(np.float64).copy(); self.F = arrays['faces'].astype(np.int64).copy()

    def keys(self):
        return [key(p) for p in self.P]

    def open_edges(self, gid):
        g = np.array([gid[k] for k in self.keys()]); W = g[self.F]
        e = np.sort(np.concatenate([W[:, [0, 1]], W[:, [1, 2]], W[:, [2, 0]]]), 1); u, c = np.unique(e, axis=0, return_counts=True)
        return {tuple(x) for x in u[c == 1]}

    def save(self, path):
        np.savez_compressed(path, position=self.P.astype('f4'), normal=(self.N/np.linalg.norm(self.N, axis=1)[:, None]).astype('f4'),
                            uv=self.U.astype('f4'), faces=self.F.astype('<u4' if len(self.P) > 65535 else '<u2'))


def gids(nodes):
    gid = {}; pos = []
    for n in nodes.values():
        for k, p in zip(n.keys(), n.P):
            if k not in gid: gid[k] = len(pos); pos.append(p)
    return gid, np.array(pos)


def raycast(O, D, P, F, tmin, tmax):
    v0 = P[F[:, 0]]; e1 = P[F[:, 1]]-v0; e2 = P[F[:, 2]]-v0; out = np.full(len(O), np.nan)
    for i in range(0, len(O), 128):
        o = O[i:i+128, None, :]; d = D[i:i+128, None, :]
        pv = np.cross(d, e2[None]); det = (e1[None]*pv).sum(2); inv = 1/np.where(np.abs(det) < 1e-15, np.nan, det)
        tv = o-v0[None]; u = (tv*pv).sum(2)*inv; qv = np.cross(tv, e1[None]); v = (d*qv).sum(2)*inv; t = (e2[None]*qv).sum(2)*inv
        ok = (u >= 0) & (v >= 0) & (u+v <= 1) & (t > tmin) & (t < tmax)
        tt = np.where(ok, t, np.inf); j = tt.argmin(1); best = tt[np.arange(len(j)), j]; out[i:i+128] = np.where(np.isfinite(best), best, np.nan)
    return out


def seg_dist(X, a, b):
    ab = b-a; t = np.clip(((X-a)@ab)/max(ab@ab, 1e-20), 0, 1); return np.linalg.norm(X-(a+t[:, None]*ab), axis=1)


def smooth_borders(Lean, High, pairs, tol, max_new):
    gidL, posL = gids(Lean); gidH, posH = gids(High)
    pairs = [tuple(pair) for pair in pairs]
    hedges = {pr: High[pr[0]].open_edges(gidH) & High[pr[1]].open_edges(gidH) for pr in pairs}
    graph = {}
    for pr, es in hedges.items():
        g = defaultdict(list)
        for a, b in es: g[a].append(b); g[b].append(a)
        graph[pr] = g
    hverts = {pr: np.array(sorted(graph[pr])) for pr in pairs}
    Hall = {n: defaultdict(list) for n in High}
    for n in High:
        for i, k in enumerate(High[n].keys()): Hall[n][k].append(i)
    keyH = {v: k for k, v in gidH.items()}
    report = {'skippedSplits': 0}

    def path(pr, ha, hb):
        g = graph[pr]; prev = {ha: None}; dq = deque([ha])
        while dq:
            x = dq.popleft()
            if x == hb: break
            if len(prev) > 4000: return None
            for y in g[x]:
                if y not in prev: prev[y] = x; dq.append(y)
        if hb not in prev: return None
        out = [hb]
        while prev[out[-1]] is not None: out.append(prev[out[-1]])
        return out[::-1]

    def nearest_h(pr, p):
        hv = hverts[pr]; d = np.linalg.norm(posH[hv]-p, axis=1); return int(hv[d.argmin()]), float(d.min())

    def evaluate(pr, pa, pb):
        if not len(hverts[pr]): return 0.0, None
        ha, _ = nearest_h(pr, pa); hb, _ = nearest_h(pr, pb)
        if ha == hb: return 0.0, None
        pth = path(pr, ha, hb)
        if pth is None or len(pth) < 3: return 0.0, None
        inner = pth[1:-1]; d = seg_dist(posH[inner], pa, pb); i = int(d.argmax()); return float(d[i]), inner[i]

    heap = []
    for pr in pairs:
        for a, b in Lean[pr[0]].open_edges(gidL) & Lean[pr[1]].open_edges(gidL):
            dev, hv = evaluate(pr, posL[a], posL[b])
            if hv is not None and dev > tol: heapq.heappush(heap, (-dev, pr, a, b, hv))
    splits = 0; posL = list(posL); gmap = dict(gidL)

    def find_face(node, ga, gb):
        g = np.array([gmap[k] for k in node.keys()]); W = g[node.F]
        for fi, w in enumerate(W):
            for s in range(3):
                if w[s] == ga and w[(s+1) % 3] == gb or w[s] == gb and w[(s+1) % 3] == ga:
                    return fi, s
        return None, None

    def unit(A, B, C):
        n = np.cross(B-A, C-A); return n/max(np.linalg.norm(n), 1e-20)

    while heap and splits*2 <= max_new-2:
        _, pr, a, b, hv = heapq.heappop(heap)
        k = keyH[hv]; ph = posH[hv]; gnew = len(posL); posL.append(ph); gmap[key(ph)] = gnew
        plan = []
        for name in pr:
            node = Lean[name]; fi, s = find_face(node, a, b); hi = Hall[name].get(k)
            if fi is None or not hi: plan = None; break
            f = node.F[fi]; i0, i1, i2 = f[s], f[(s+1) % 3], f[(s+2) % 3]
            n0 = unit(node.P[i0], node.P[i1], node.P[i2])
            if min(n0@unit(node.P[i0], ph, node.P[i2]), n0@unit(ph, node.P[i1], node.P[i2])) < 0.5:  # would fold a triangle
                plan = None; break
            plan.append((name, fi, s, hi))
        if plan is None:
            posL.pop(); del gmap[key(ph)]; report['skippedSplits'] += 1; continue
        for name, fi, s, hi in plan:
            node = Lean[name]; f = node.F[fi].copy(); i0, i1, i2 = f[s], f[(s+1) % 3], f[(s+2) % 3]
            t = np.linalg.norm(ph-node.P[i0])/max(np.linalg.norm(node.P[i1]-node.P[i0]), 1e-12)
            uv_lerp = node.U[i0]*(1-t)+node.U[i1]*t
            j = min(hi, key=lambda j: np.linalg.norm(High[name].U[j]-uv_lerp))
            node.P = np.vstack([node.P, ph]); node.U = np.vstack([node.U, uv_lerp]); node.N = np.vstack([node.N, High[name].N[j]])
            nv = len(node.P)-1; node.F[fi] = [i0, nv, i2]; node.F = np.vstack([node.F, [nv, i1, i2]])
        splits += 1
        for ea, eb in ((a, gnew), (gnew, b)):
            dev, h2 = evaluate(pr, posL[ea], posL[eb])
            if h2 is not None and dev > tol: heapq.heappush(heap, (-dev, pr, ea, eb, h2))
    remaining = [-h[0] for h in heap]
    report.update(toleranceMm=tol*1000, splits=splits, addedTriangles=splits*2, remainingEdgesOverTolerance=len(remaining),
                  maxRemainingDeviationMm=round(max(remaining)*1000, 3) if remaining else 0.0)
    return report


def weld_crack(nodes, target, max_separation):
    gid, pos = gids(nodes); open_edges = sorted(nodes[target].open_edges(gid))
    short = [(a, b) for a, b in open_edges if np.linalg.norm(pos[a]-pos[b]) < max_separation]
    report = {'node': target, 'openEdgesBefore': len(open_edges), 'weldedPairs': []}
    for a, b in short:
        mid = (pos[a]+pos[b])/2; ka, kb = key(pos[a]), key(pos[b])
        for n in nodes.values():
            for i, k in enumerate(n.keys()):
                if k in (ka, kb): n.P[i] = mid
            g = [key(p) for p in n.P]; degenerate = np.array([len({g[x] for x in f}) < 3 for f in n.F]); n.F = n.F[~degenerate]
        report['weldedPairs'].append({'separationUm': float(np.linalg.norm(pos[a]-pos[b])*1e6)})
    gid2, _ = gids(nodes); report['openEdgesAfter'] = len(nodes[target].open_edges(gid2))
    return report


def pullback(Lean, High, garment, skins, keep):
    garment_keys = set(Lean[garment].keys()); G = Lean[garment]; GH = High[garment]
    hs_pos, hs_val = [], []
    for s in skins:
        h = High[s]; n = h.N/np.linalg.norm(h.N, axis=1)[:, None]
        t = raycast(h.P+n*0.006, -n, GH.P, GH.F, 0.0, 0.010); hs_pos.append(h.P); hs_val.append(0.006-t)
    hs_pos = np.concatenate(hs_pos); hs_val = np.concatenate(hs_val); moved = 0; maxmove = 0.0
    for _ in range(2):
        cand = {}
        for s in skins:
            for i, k in enumerate(Lean[s].keys()):
                if k not in garment_keys: cand.setdefault(k, []).append((s, i))
        klist = list(cand); P = np.array([Lean[cand[k][0][0]].P[cand[k][0][1]] for k in klist])
        N = np.array([sum(Lean[s].N[i] for s, i in cand[k]) for k in klist]); N /= np.linalg.norm(N, axis=1)[:, None]
        t = raycast(P+N*0.006, -N, G.P, G.F, 0.0, 0.010); sL = 0.006-t; near = ~np.isnan(sL)
        if not near.any(): break
        idx = np.nonzero(near)[0]; hv = np.empty(len(idx))
        for j0 in range(0, len(idx), 2000):
            sub = idx[j0:j0+2000]; d = ((P[sub][:, None, :]-hs_pos[None])**2).sum(2); hv[j0:j0+2000] = hs_val[d.argmin(1)]
        need = (hv > 0.00005) & (sL[idx] < keep); changed = 0
        for jj in np.nonzero(need)[0]:
            v = idx[jj]; delta = keep-sL[v]; maxmove = max(maxmove, delta)
            for s, i in cand[klist[v]]: Lean[s].P[i] = Lean[s].P[i]-N[v]*delta
            changed += 1
        moved += changed
        if not changed: break
    return {'garment': garment, 'skins': list(skins), 'keepMm': keep*1000, 'vertexMoves': moved, 'maxMoveMm': round(maxmove*1000, 3)}


def validate_config(config):
    L.require(config.get('kind') == CONFIG and config.get('schemaVersion') == 1, 'Explicit LEAN repair configuration required')
    for row in config.get('borderSmoothing', []):
        L.require(0 < row['toleranceM'] <= 0.002 and 0 < row['maxNewTriangles'] <= 2000, 'Bounded border smoothing required')
    for row in config.get('crackWelds', []):
        L.require(0 < row['maxSeparationM'] <= 1e-4, 'Crack welds are limited to sub-0.1 mm slivers')
    for row in config.get('garmentPullback', []):
        L.require(0 < row['keepM'] <= 0.002, 'Bounded garment pull-back required')
    return config


def repair(parent_path, reduction_paths, config_path, output):
    frozen = L.Frozen(); manifest = L.read_json(frozen.take(parent_path)); config = validate_config(L.read_json(frozen.take(config_path)))
    lean = {}; parent_arrays = {m['mesh']: m['arrays'] for row in manifest['parts'].values() for m in row['meshes']}
    for path in reduction_paths:
        receipt = L.read_json(frozen.take(path)); L.require(receipt['parent']['sha256'] == L.sha(parent_path), 'Reduction from another parent')
        for row in receipt['parts'].values():
            for node, entry in row['nodes'].items(): lean[node] = entry['arrays']
    touched = sorted({n for row in config.get('borderSmoothing', []) for n in row.get('nodes', [])} |
                     {n for row in config.get('borderSmoothing', []) for pair in row['pairs'] for n in pair} |
                     {n for row in config.get('crackWelds', []) for n in row['nodes']} |
                     {n for row in config.get('garmentPullback', []) for n in [row['garment'], *row['skins']]})
    Lean = {n: Node(n, np.load(frozen.pinned(lean[n]))) for n in touched}
    High = {n: Node(n, np.load(frozen.pinned(parent_arrays[n]))) for n in touched}
    protected = sorted(set(config.get('protectedNodes', [])) | {n for row in config.get('borderSmoothing', []) for n in row.get('protectedNodes', [])})
    L.require(set(protected) <= set(Lean), 'Protected nodes must be declared repair nodes')
    before = {n: (Lean[n].P.copy(), Lean[n].F.copy(), Lean[n].U.copy()) for n in protected}
    counts = {n: (len(Lean[n].F), len(Lean[n].P)) for n in Lean}
    output = L.fresh(output); report = {'borderSmoothing': [], 'crackWelds': [], 'garmentPullback': []}
    for row in config.get('borderSmoothing', []):
        # Vertex identity spans the declared node set in its declared order (the garment included, never edited).
        names = row.get('nodes') or sorted({n for pair in row['pairs'] for n in pair})
        L.require({n for pair in row['pairs'] for n in pair} <= set(names), 'Border pairs outside the declared node set')
        report['borderSmoothing'].append({'part': row['part'], **smooth_borders({n: Lean[n] for n in names}, {n: High[n] for n in names},
                                                                            row['pairs'], row['toleranceM'], row['maxNewTriangles'])})
    for row in config.get('crackWelds', []):
        report['crackWelds'].append({'part': row['part'], **weld_crack({n: Lean[n] for n in row['nodes']}, row['node'], row['maxSeparationM'])})
    for row in config.get('garmentPullback', []):
        names = [row['garment'], *row['skins']]
        report['garmentPullback'].append({'label': row['label'], **pullback({n: Lean[n] for n in names}, {n: High[n] for n in names},
                                                                            row['garment'], row['skins'], row['keepM'])})
    for n, (P, F, U) in before.items():
        L.require(np.array_equal(Lean[n].P, P) and np.array_equal(Lean[n].F, F) and np.array_equal(Lean[n].U, U), 'Protected node changed: '+n)
    nodes = {}
    for n in touched:
        path = output/(n+'.npz'); Lean[n].save(path)
        nodes[n] = {'input': lean[n], 'arrays': L.pin(path), 'trianglesBefore': counts[n][0], 'trianglesAfter': int(len(Lean[n].F)),
                    'verticesBefore': counts[n][1], 'verticesAfter': int(len(Lean[n].P)), 'protected': n in protected}
    receipt = {'schemaVersion': 1, 'kind': 'lean-border-repair', 'sex': manifest['sex'], 'parent': L.pin(parent_path),
               'reductions': [L.pin(p) for p in reduction_paths], 'config': L.pin(config_path), 'report': report, 'nodes': nodes,
               'protectedNodesUnchanged': protected, 'frozenInputs': {**frozen.verify(), **L.helper_pins('lean_border_repair.py')},
               'selected': False, 'clientAccepted': False, 'productionAccepted': False}
    return L.save_json(output/'repair.json', receipt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True); parser.add_argument('--reduction', type=Path, action='append', required=True)
    parser.add_argument('--config', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); print(repair(args.parent, args.reduction, args.config, args.output))
