"""LEAN step 2 (Blender): UV/seam-aware quadric collapse of each parent part to its LEAN triangle budget.

Ported unchanged from the poly-budget study decimator (tiers mode, one tier). Per part every node (skin, skin overlay
shells, garments) is welded into ONE manifold-by-position mesh with per-corner UVs and one material index per node, so
shared node borders stay coincident; Blender collapse decimation interpolates UVs per side of a UV seam and preserves
open boundaries; the split is restored by material afterwards, so node names, node count and each node's UV layout
are kept (the rig and hierarchy are never touched: geometry stays in the part's attachment-local frame). A layer guard
pushes hidden co-layered vertices back beneath the covering node; per-corner normals are transferred from the parent
surface of the same node. Connector bands (within 8 mm of a posed neighbour at the idle sample) are measured, not
weighted (measured harmful in the study). Metrics: surface error both ways, silhouette offsets, UV drift, closure.

Usage: blender ... --python lean_reduce_parts.py -- --parent <manifest.json> --budgets <budget-decision.json>
       --tier tier-lean --output <fresh dir> [--parts a,b,...]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lean_common as L  # noqa: E402
from lean_reduction_core import bary, sample, silhouette_metrics, split_by_material, topo, weld  # noqa: E402

BAND_MM = 8.0; VG_FACTOR = 0.0; SAMPLES = 40000
args = argparse.ArgumentParser()
args.add_argument('--parent', type=Path, required=True); args.add_argument('--budgets', type=Path, required=True)
args.add_argument('--tier', default='tier-lean'); args.add_argument('--output', type=Path, required=True); args.add_argument('--parts')
A = args.parse_args(sys.argv[sys.argv.index('--')+1:])
frozen = L.Frozen(); OUT = L.fresh(A.output); (OUT/'lean').mkdir()
MAN = L.read_json(frozen.take(A.parent)); L.require(MAN.get('kind') == 'lean-parent-representation', 'LEAN parent representation required')
BUDGETS = L.read_json(frozen.take(A.budgets))[MAN['sex']]
SELECTED = A.parts.split(',') if A.parts else list(L.PARTS)
L.require(set(SELECTED) <= set(L.PARTS) and len(set(SELECTED)) == len(SELECTED), 'Unknown or duplicate parts')
idle = {k: np.asarray(v, float) for k, v in MAN['poses']['idle'].items()}
for ob in list(bpy.data.objects): bpy.data.objects.remove(ob)


def load_part(part):
    Ps, Fs, Us, Ns, Ms, names = [], [], [], [], [], []; base = 0
    for mi, m in enumerate(MAN['parts'][part]['meshes']):
        a = np.load(frozen.pinned(m['arrays'])); F = a['faces'].astype(np.int64)
        Ps.append(a['position'].astype(np.float64)); Ns.append(a['normal'].astype(np.float64)); Us.append(a['uv'].astype(np.float64))
        Fs.append(F+base); Ms.append(np.full(len(F), mi)); base += len(a['position']); names.append(m['mesh'])
    return np.concatenate(Ps), np.concatenate(Fs), np.concatenate(Us), np.concatenate(Ns), np.concatenate(Ms), names


def bvh(P, F): return BVHTree.FromPolygons([tuple(p) for p in P], [tuple(int(i) for i in f) for f in F], all_triangles=True)


def nearest(tree, X):
    D = np.empty(len(X)); I = np.empty(len(X), np.int64); Lc = np.empty((len(X), 3))
    for k, x in enumerate(X):
        loc, nor, idx, dist = tree.find_nearest(Vector(x))
        D[k] = dist; I[k] = idx; Lc[k] = loc
    return D, I, Lc


def neighbour_tree(part):
    pts, tris = [], []; base = 0; Mi = np.linalg.inv(idle[MAN['parts'][part]['joint']])
    for q in L.NEIGHBOURS[part]:
        P, F, U, N, M, _ = load_part(q); joint = MAN['parts'][q]['joint']
        T = Mi@idle[joint]; X = P@T[:3, :3].T+T[:3, 3]; pts.append(X); tris.append(F+base); base += len(X)
    if part == 'chest':
        for c in MAN.get('context', []):
            if c['name'].endswith('neck001'):
                a = np.load(frozen.pinned(c['arrays'])); P = a['position'].astype(float); F = a['faces'].astype(int)
                T = Mi@idle[c['joint']]; X = P@T[:3, :3].T+T[:3, 3]; pts.append(X); tris.append(F+base); base += len(X)
    return bvh(np.concatenate(pts), np.concatenate(tris))


def build(part):
    P, F, U, N, M, names = load_part(part)
    Pw, Fw, Uc, Nc, Mf, dropped = weld(P, F, U, N, M)
    bnd, nonman = topo(Fw)
    tree = neighbour_tree(part); D, _, _ = nearest(tree, Pw)
    band = np.clip(1-D/(BAND_MM/1000), 0, 1); band[np.unique(bnd)] = 1.0
    me = bpy.data.meshes.new(part); me.from_pydata(Pw.tolist(), [], Fw.tolist()); me.update()
    L.require(len(me.polygons) == len(Fw), 'Blender changed the welded face count')
    lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv); L.require(np.array_equal(lv.reshape(-1, 3), Fw), 'Loop order differs')
    uvl = me.uv_layers.new(name='UV'); uvl.data.foreach_set('uv', Uc.reshape(-1).astype(np.float32))
    for i in range(len(names)): me.materials.append(bpy.data.materials.new('%s-m%d' % (part, i)))
    me.polygons.foreach_set('material_index', Mf.astype(np.int32))
    ob = bpy.data.objects.new(part, me); bpy.context.scene.collection.objects.link(ob)
    vg = ob.vertex_groups.new(name='decim')
    for wv in np.unique(np.round(1-band, 3)):
        idx = np.nonzero(np.round(1-band, 3) == wv)[0].tolist(); vg.add(idx, float(wv), 'REPLACE')
    return dict(ob=ob, P=P, F=F, U=U, N=N, M=M, names=names, Pw=Pw, Fw=Fw, Uc=Uc, Nc=Nc, Mf=Mf, band=band, dropped=dropped,
                bnd=len(bnd), nonman=nonman, hi_tree=bvh(Pw, Fw))


def decimate(B, target):
    ob = B['ob']; n0 = len(B['Fw']); ratio = min(1.0, target/n0); iterations = []
    for it in range(4):
        mod = ob.modifiers.new('dec', 'DECIMATE'); mod.decimate_type = 'COLLAPSE'; mod.ratio = ratio; mod.use_collapse_triangulate = True
        if VG_FACTOR > 0: mod.vertex_group = 'decim'; mod.vertex_group_factor = VG_FACTOR
        dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg)); ob.modifiers.remove(mod)
        nf = len(me.polygons); iterations.append({'ratio': ratio, 'triangles': nf})
        if abs(nf-target) <= max(4, target*0.003) or ratio >= 1.0 or it == 3: break
        ratio = min(1.0, ratio*target/nf); bpy.data.meshes.remove(me)
    P = np.empty(len(me.vertices)*3); me.vertices.foreach_get('co', P); P = P.reshape(-1, 3)
    lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    ls = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', ls); L.require((ls == 3).all(), 'Non-triangle after collapse')
    U = np.empty(len(me.loops)*2, np.float32); me.uv_layers[0].data.foreach_get('uv', U)
    Mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('material_index', Mi)
    bpy.data.meshes.remove(me)
    return P, lv.reshape(-1, 3).astype(np.int64), U.reshape(-1, 3, 2).astype(np.float64), Mi, iterations


def metrics(B, P, F, U, Mi):
    t0 = time.monotonic(); lo_tree = bvh(P, F)
    Xh, fh, bh = sample(B['Pw'], B['Fw'], SAMPLES, 1); dh, _, _ = nearest(lo_tree, Xh)
    Xl, fl, bl = sample(P, F, SAMPLES, 2); dl, il, Ll = nearest(B['hi_tree'], Xl)
    ul = (U[fl]*bl[:, :, None]).sum(1); bb = bary(B['Pw'], B['Fw'], il, Ll); uh = (B['Uc'][il]*bb[:, :, None]).sum(1)
    same = Mi[fl] == B['Mf'][il]; drift = np.linalg.norm(ul-uh, axis=1)*2048; dd = drift[same & (drift < 8)]
    bandw = (B['band'][B['Fw'][fh]]*bh).sum(1); dband = dh[bandw > 0.5]
    bnd, nonman = topo(F)
    mm = lambda a: {'meanMm': float(a.mean()*1000), 'p95Mm': float(np.percentile(a, 95)*1000), 'maxMm': float(a.max()*1000)} if len(a) else None
    return {'triangles': int(len(F)), 'highToLow': mm(dh), 'lowToHigh': mm(dl), 'hausdorffMm': float(max(dh.max(), dl.max())*1000),
            'connectorBand': mm(dband), 'uvDriftTexels': {'median': float(np.median(dd)), 'p95': float(np.percentile(dd, 95)), 'fractionOver2': float((dd > 2).mean())},
            'openBoundaryEdges': {'parent': B['bnd'], 'lean': len(bnd)}, 'nonManifoldEdges': {'parent': B['nonman'], 'lean': nonman},
            'silhouette': silhouette_metrics(B['Pw'], B['Fw'], P, F), 'metricSeconds': round(time.monotonic()-t0, 2)}


def layer_guard(B, P, F, Mi, reach=0.004, keep=0.0001, iters=3):
    """Hidden co-layered vertices that lay beneath another node in the parent stay beneath its LEAN surface."""
    mats = np.unique(Mi); moved = 0
    if len(mats) < 2: return P, 0
    owner = np.full(len(P), -1); multi = np.zeros(len(P), bool)
    for m in mats:
        v = np.unique(F[Mi == m]); multi[v[owner[v] >= 0]] = True; owner[v] = m
    hi_trees = {k: bvh(B['Pw'], B['Fw'][B['Mf'] == k]) for k in mats}
    P = P.copy()
    for _ in range(iters):
        changed = 0
        for k in mats:
            lo_tree = bvh(P, F[Mi == k]); cand = np.nonzero((owner >= 0) & (owner != k) & ~multi)[0]
            for v in cand:
                x = Vector(P[v]); h = hi_trees[k].find_nearest(x, reach)
                if h[0] is None: continue
                sh = (x-h[0]).dot(h[1])
                if sh > -0.00005: continue
                lw = lo_tree.find_nearest(x, reach)
                if lw[0] is None: continue
                sl = (x-lw[0]).dot(lw[1]); tgt = min(keep, -sh/2)
                if sl > -tgt:
                    P[v] = P[v]-np.asarray(lw[1])*(sl+tgt); changed += 1
        moved += changed
        if not changed: break
    return P, moved


TRANSFER = {'checked': 0, 'reoriented': 0, 'geometricFallback': 0}


def transfer_normals(B, P, F, Mi):
    """Per (vertex, node) corner normal = barycentric parent corner normal at the nearest parent point of that node."""
    out = np.zeros((len(F), 3, 3))
    for m in np.unique(Mi):
        hs = B['Mf'] == m; Fh = B['Fw'][hs]; Nh = B['Nc'][hs]; tree = bvh(B['Pw'], Fh)
        corners = F[Mi == m]; verts = np.unique(corners)
        _, idx, loc = nearest(tree, P[verts]); bb = bary(B['Pw'], Fh, idx, loc)
        n = (Nh[idx]*bb[:, :, None]).sum(1); n /= np.linalg.norm(n, axis=1)[:, None]
        Fm = F[Mi == m]; fn = np.cross(P[Fm[:, 1]]-P[Fm[:, 0]], P[Fm[:, 2]]-P[Fm[:, 0]]); g = np.zeros((len(P), 3))
        for k in range(3): np.add.at(g, Fm[:, k], fn)
        g = g[verts]; g /= np.maximum(np.linalg.norm(g, axis=1), 1e-30)[:, None]
        bad = np.nonzero((n*g).sum(1) < 0.3)[0]; TRANSFER['checked'] += len(verts); TRANSFER['reoriented'] += len(bad)
        for i in bad:
            hit = None
            for s in (1, -1):
                h = tree.ray_cast(Vector(P[verts[i]]+g[i]*0.002*s), Vector(-g[i]*s), 0.004)
                if h[0] is not None and Vector(h[1]).dot(Vector(g[i])) > 0.3: hit = h; break
            if hit is None: n[i] = g[i]; TRANSFER['geometricFallback'] += 1; continue
            b1 = bary(B['Pw'], Fh, np.array([hit[2]]), np.array([hit[0]]))
            v = (Nh[hit[2]]*b1[0][:, None]).sum(0); n[i] = v/np.linalg.norm(v) if (v@g[i]) > 0.3*np.linalg.norm(v) else g[i]
        lut = np.zeros((len(P), 3)); lut[verts] = n; out[Mi == m] = lut[corners]
    return out


report = {'schemaVersion': 1, 'kind': 'lean-part-reduction', 'sex': MAN['sex'], 'prefix': MAN['prefix'], 'tier': A.tier,
          'parent': L.pin(A.parent), 'budgets': L.pin(A.budgets), 'bandMm': BAND_MM, 'vertexGroupFactor': VG_FACTOR, 'samples': SAMPLES,
          'blenderVersion': bpy.app.version_string, 'parts': {}}
T0 = time.monotonic()
for part in SELECTED:
    t0 = time.monotonic(); B = build(part); budget = int(BUDGETS[part][A.tier])
    P, F, U, Mi, iterations = decimate(B, budget); P, moved = layer_guard(B, P, F, Mi)
    met = metrics(B, P, F, U, Mi); met['layerGuardVertexMoves'] = moved; N = transfer_normals(B, P, F, Mi)
    nodes = split_by_material(B['names'], P, F, U, N, Mi)
    L.require(sorted(nodes) == sorted(B['names']), 'Every parent node must survive the reduction: '+part)
    pins = {}
    for name, arr in nodes.items():
        path = OUT/'lean'/(name+'.npz'); np.savez_compressed(path, **arr); pins[name] = L.pin(path)
    report['parts'][part] = {'meshes': B['names'], 'budget': budget, 'parentTriangles': int(len(B['F'])), 'weldedTriangles': int(len(B['Fw'])),
                             'droppedDegenerateOrDuplicate': B['dropped'], 'collapseIterations': iterations, **met,
                             'nodes': {n: {'triangles': int(len(a['faces'])), 'vertices': int(len(a['position'])), 'arrays': pins[n]} for n, a in nodes.items()},
                             'nodeInventoryPreserved': True, 'withinBudget': int(len(F)) <= budget, 'seconds': round(time.monotonic()-t0, 1)}
    print(json.dumps({'part': part, 'triangles': int(len(F)), 'budget': budget, 'p95': met['highToLow']['p95Mm']}), flush=True)
    bpy.data.objects.remove(B['ob'])
report['seconds'] = round(time.monotonic()-T0, 1); report['normalTransfer'] = TRANSFER
report['frozenInputs'] = {**frozen.verify(), **L.helper_pins('lean_reduce_parts.py', 'lean_reduction_core.py', 'uv_atlas_raster.py')}
report.update(geometryEdited=True, rigEdited=False, uvLayoutPerNodePreserved=True, selected=False, clientAccepted=False, productionAccepted=False)
L.save_json(OUT/'reduction.json', report)
print('done', report['seconds'])
